"""
Conversation insights service.

Generates a small topic graph (5-10 topics) from selected video transcript chunks
and caches the result for fast re-use.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set, Tuple

import numpy as np

from sqlalchemy.orm import Session

from app.models import Chunk, Video, ConversationInsight
from app.services.llm_providers import Message, LLMService

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT_VERSION = 4
DEFAULT_MAX_CHUNKS_ANALYZED = 50
DEFAULT_TARGET_TOPICS = 7
DEFAULT_MAX_CHUNKS_PER_TOPIC = 15
DEFAULT_MAX_SUBTOPICS_PER_TOPIC = 3
DEFAULT_MAX_POINTS_PER_SUBTOPIC = 2
DEFAULT_MAX_MOMENTS_PER_POINT = 2
DEFAULT_MIN_TOPIC_SIMILARITY = 0.25
DEFAULT_MIN_TOPIC_GAP = 0.04


@dataclass(frozen=True)
class TopicNode:
    id: str
    label: str
    description: str
    keywords: List[str]


@dataclass(frozen=True)
class TopicChunk:
    chunk_id: uuid.UUID
    video_id: uuid.UUID
    video_title: str
    start_timestamp: float
    end_timestamp: float
    timestamp_display: str
    text: str
    chunk_title: Optional[str]
    chapter_title: Optional[str] = None
    chunk_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": str(self.chunk_id),
            "video_id": str(self.video_id),
            "video_title": self.video_title,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "timestamp_display": self.timestamp_display,
            "text": self.text,
            "chunk_title": self.chunk_title,
            "chapter_title": self.chapter_title,
            "chunk_summary": self.chunk_summary,
        }


class EmbeddingServiceProtocol(Protocol):
    def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> List[np.ndarray]:
        ...


@dataclass(frozen=True)
class InsightGraph:
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    topic_chunks: Dict[str, List[TopicChunk]]
    metadata: Dict[str, Any]

    def graph_dict(self) -> Dict[str, Any]:
        return {"nodes": self.nodes, "edges": self.edges}

    def topic_chunks_dict(self) -> Dict[str, Any]:
        return {
            topic_id: [c.to_dict() for c in chunks]
            for topic_id, chunks in self.topic_chunks.items()
        }


def _canonicalize_video_ids(video_ids: Sequence[uuid.UUID]) -> List[uuid.UUID]:
    # Sort to treat the set of selected videos as the cache key (order-independent).
    return sorted((uuid.UUID(str(v)) for v in video_ids), key=lambda v: str(v))


def _strip_markdown_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _normalize_tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


class ConversationInsightsService:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        embedding_service: Optional[EmbeddingServiceProtocol] = None,
    ) -> None:
        from app.services.llm_providers import llm_service as default_llm_service

        self.llm_service = llm_service or default_llm_service

        if embedding_service is None:
            from app.services.embeddings import (
                embedding_service as default_embedding_service,
            )

            self.embedding_service = default_embedding_service
        else:
            self.embedding_service = embedding_service

    def _sample_chunks_for_extraction(
        self,
        chunks: Sequence[Chunk],
        max_chunks: int = DEFAULT_MAX_CHUNKS_ANALYZED,
    ) -> List[Chunk]:
        if not chunks:
            return []

        chunks_by_video: Dict[uuid.UUID, List[Chunk]] = {}
        for chunk in chunks:
            chunks_by_video.setdefault(chunk.video_id, []).append(chunk)

        # Deterministic ordering for stable prompts.
        for vid, vid_chunks in chunks_by_video.items():
            chunks_by_video[vid] = sorted(vid_chunks, key=lambda c: c.chunk_index)

        num_videos = max(1, len(chunks_by_video))
        per_video_budget = max(1, max_chunks // num_videos)

        selected: List[Chunk] = []

        for vid in sorted(chunks_by_video.keys(), key=lambda v: str(v)):
            vid_chunks = chunks_by_video[vid]
            by_chapter: Dict[int, List[Chunk]] = {}
            for c in vid_chunks:
                if c.chapter_index is not None:
                    by_chapter.setdefault(int(c.chapter_index), []).append(c)

            if by_chapter:
                chapter_indices = sorted(by_chapter.keys())
                # Aim for 2 chunks per chapter while respecting budget.
                per_chapter = max(1, per_video_budget // max(1, len(chapter_indices)))
                for chapter_index in chapter_indices:
                    chapter_chunks = sorted(
                        by_chapter[chapter_index], key=lambda c: c.chunk_index
                    )
                    if not chapter_chunks:
                        continue
                    picks = self._evenly_spaced(chapter_chunks, per_chapter)
                    selected.extend(picks)
            else:
                selected.extend(self._evenly_spaced(vid_chunks, per_video_budget))

        if len(selected) <= max_chunks:
            remaining = [c for c in chunks if c not in set(selected)]
            selected.extend(
                self._pick_by_keyword_diversity(remaining, max_chunks - len(selected))
            )
            return selected[:max_chunks]

        # Too many from chapter-heavy videos: downsample by diversity.
        return self._pick_by_keyword_diversity(selected, max_chunks)

    @staticmethod
    def _evenly_spaced(chunks: Sequence[Chunk], k: int) -> List[Chunk]:
        if k <= 0 or not chunks:
            return []
        if k >= len(chunks):
            return list(chunks)
        step = (len(chunks) - 1) / float(k - 1) if k > 1 else 0.0
        indices = (
            {int(round(i * step)) for i in range(k)} if k > 1 else {len(chunks) // 2}
        )
        return [chunks[i] for i in sorted(indices)]

    @staticmethod
    def _pick_by_keyword_diversity(chunks: Sequence[Chunk], k: int) -> List[Chunk]:
        if k <= 0 or not chunks:
            return []

        remaining = list(chunks)
        selected: List[Chunk] = []
        seen_keywords: Set[str] = set()

        while remaining and len(selected) < k:
            best_idx = 0
            best_gain = -1
            best_len = -1
            for i, chunk in enumerate(remaining):
                kws = {
                    (kw or "").strip().lower() for kw in (chunk.keywords or []) if kw
                }
                gain = len(kws - seen_keywords)
                # Tie-breaker: prefer chunks with more keywords (more informative).
                if gain > best_gain or (gain == best_gain and len(kws) > best_len):
                    best_idx = i
                    best_gain = gain
                    best_len = len(kws)

            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            for kw in chosen.keywords or []:
                if kw:
                    seen_keywords.add(kw.strip().lower())

        return selected

    def _build_prompt(
        self,
        videos: Sequence[Video],
        sampled_chunks: Sequence[Chunk],
        target_topics: int,
    ) -> List[Message]:
        system_prompt = (
            "You are an expert at analyzing educational video content and identifying main themes.\n\n"
            "Your task: Given summaries from video transcripts, extract 5-10 HIGH-LEVEL topics that organize the content.\n\n"
            "Guidelines:\n"
            "1. Topics should be BROAD themes, not specific facts\n"
            "2. Each topic should encompass multiple chunks (3-15 chunks per topic)\n"
            "3. Topics should be mutually exclusive where possible\n"
            "4. Use clear, descriptive labels (3-8 words)\n"
            "5. Provide a 2-3 sentence description of what the topic covers\n\n"
            "Return ONLY valid JSON with this structure:\n"
            "{\n"
            '  "topics": [\n'
            "    {\n"
            '      "id": "topic-1",\n'
            '      "label": "Neural Network Fundamentals",\n'
            '      "description": "Covers basic architecture, layers, and forward propagation concepts...",\n'
            '      "keywords": ["neural network", "layers", "activation", "forward pass"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "IMPORTANT:\n"
            f"- Aim for around {target_topics} topics (min 5, max 10)\n"
            "- Keywords help map topics to chunks (3-7 per topic)\n"
            "- No external knowledge - only extract from provided content\n"
        )

        formatted_chunks: List[str] = []
        for idx, chunk in enumerate(sampled_chunks, 1):
            video_title = next(
                (v.title for v in videos if v.id == chunk.video_id), "Unknown Video"
            )
            title = chunk.chunk_title or (chunk.chapter_title or "Transcript segment")
            summary_source = chunk.chunk_summary or chunk.text
            summary = _truncate(summary_source.replace("\n", " ").strip(), 280)
            kw_list = [kw for kw in (chunk.keywords or []) if kw]
            kws = ", ".join(kw_list[:10])
            formatted_chunks.append(
                "\n".join(
                    [
                        f"{idx}. Video: {video_title}",
                        f"   Time: {chunk.timestamp_display}",
                        f"   Title: {title}",
                        f"   Summary: {summary}",
                        f"   Keywords: {kws}" if kws else "   Keywords: (none)",
                    ]
                )
            )

        user_prompt = (
            "Video Context:\n"
            f"Videos: {', '.join(v.title for v in videos)}\n\n"
            f"Chunk Summaries (from {len(sampled_chunks)} segments across {len(videos)} videos):\n\n"
            f"{chr(10).join(formatted_chunks)}\n\n"
            "Extract 5-10 main topics from this content. Return JSON only."
        )

        return [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

    @staticmethod
    def _parse_topics_response(response_text: str) -> List[TopicNode]:
        text = _strip_markdown_code_fences(response_text)
        data = json.loads(text)
        topics_raw = data.get("topics")
        if not isinstance(topics_raw, list):
            raise ValueError("Response JSON missing 'topics' list")

        topics: List[TopicNode] = []
        for i, item in enumerate(topics_raw, 1):
            if not isinstance(item, dict):
                continue
            topic_id = str(item.get("id") or f"topic-{i}")
            label = str(item.get("label") or "").strip()
            description = str(item.get("description") or "").strip()
            keywords_raw = item.get("keywords") or []
            keywords: List[str] = (
                [str(k).strip() for k in keywords_raw if str(k).strip()]
                if isinstance(keywords_raw, list)
                else []
            )
            if not label:
                continue
            if not description:
                description = f"Content related to {label}."
            if not keywords:
                keywords = _normalize_tokens(label)[:5]
            topics.append(
                TopicNode(
                    id=topic_id,
                    label=label,
                    description=description,
                    keywords=keywords[:7],
                )
            )

        # Ensure stable unique IDs.
        seen: Set[str] = set()
        normalized: List[TopicNode] = []
        for idx, t in enumerate(topics, 1):
            tid = t.id
            if tid in seen:
                tid = f"topic-{idx}"
            seen.add(tid)
            normalized.append(
                TopicNode(
                    id=tid,
                    label=t.label,
                    description=t.description,
                    keywords=t.keywords,
                )
            )

        return normalized

    @staticmethod
    def _fallback_topics_from_keywords(
        chunks: Sequence[Chunk], target_topics: int
    ) -> List[TopicNode]:
        freq: Dict[str, int] = {}
        for chunk in chunks:
            for kw in chunk.keywords or []:
                if not kw:
                    continue
                token = kw.strip().lower()
                if len(token) < 3:
                    continue
                freq[token] = freq.get(token, 0) + 1

        if not freq:
            # Last resort: use the most common words from chunk titles/summaries.
            for chunk in chunks:
                text = " ".join([chunk.chunk_title or "", chunk.chunk_summary or ""])
                for token in _normalize_tokens(text):
                    if len(token) < 4:
                        continue
                    freq[token] = freq.get(token, 0) + 1

        top = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[
            : max(5, min(10, target_topics))
        ]
        topics: List[TopicNode] = []
        for i, (token, _) in enumerate(top, 1):
            label = token.replace("_", " ").title()
            topics.append(
                TopicNode(
                    id=f"topic-{i}",
                    label=label,
                    description=f"Content related to {label}.",
                    keywords=[token],
                )
            )
        return topics

    @staticmethod
    def _chunk_topic_score(topic: TopicNode, chunk: Chunk) -> float:
        topic_tokens: Set[str] = set()
        for kw in topic.keywords:
            topic_tokens.update(_normalize_tokens(kw))

        chunk_tokens: Set[str] = set()
        for kw in chunk.keywords or []:
            chunk_tokens.update(_normalize_tokens(kw))

        for field in (chunk.chunk_title, chunk.chapter_title, chunk.chunk_summary):
            chunk_tokens.update(_normalize_tokens(field or ""))

        if not topic_tokens or not chunk_tokens:
            return 0.0

        overlap = topic_tokens & chunk_tokens
        return float(len(overlap))

    def _map_topics_to_chunks(
        self,
        topics: Sequence[TopicNode],
        chunks: Sequence[Chunk],
        videos_by_id: Dict[uuid.UUID, Video],
        *,
        user_id: uuid.UUID,
        max_chunks_per_topic: int = DEFAULT_MAX_CHUNKS_PER_TOPIC,
    ) -> Tuple[
        Dict[str, List[TopicChunk]],
        Dict[uuid.UUID, np.ndarray],
        Dict[str, Any],
        Dict[str, int],
    ]:
        """
        Map topics to chunks using semantic embeddings, with strict evidence rules:
        - Each chunk is assigned to at most one topic (prevents repeats across branches).
        - No "filler" chunks. If we don't have strong evidence, we return fewer chunks.
        """

        def normalize(vec: np.ndarray) -> np.ndarray:
            norm = float(np.linalg.norm(vec))
            if norm <= 0:
                return vec
            return vec / norm

        topic_ids = [t.id for t in topics]
        topic_chunks: Dict[str, List[TopicChunk]] = {tid: [] for tid in topic_ids}
        total_counts: Dict[str, int] = {tid: 0 for tid in topic_ids}

        # Default empty result.
        if not topics or not chunks:
            return (
                topic_chunks,
                {},
                {
                    "assignment_method": "none",
                    "min_similarity": DEFAULT_MIN_TOPIC_SIMILARITY,
                    "min_gap": DEFAULT_MIN_TOPIC_GAP,
                    "assigned_chunks": 0,
                    "unassigned_chunks": len(chunks),
                    "total_chunks_considered": len(chunks),
                },
                total_counts,
            )

        # Build embedding inputs.
        chunk_ids: List[uuid.UUID] = []
        chunk_texts: List[str] = []
        for c in chunks:
            chunk_ids.append(c.id)
            if c.embedding_text and c.embedding_text.strip():
                chunk_texts.append(c.embedding_text.strip())
                continue

            parts: List[str] = []
            title = (c.chunk_title or "").strip() or (c.chapter_title or "").strip()
            if title:
                parts.append(f"Title: {title}")
            if c.chunk_summary and c.chunk_summary.strip():
                parts.append(f"Summary: {_truncate(c.chunk_summary.strip(), 320)}")
            kws = [kw.strip() for kw in (c.keywords or []) if kw and kw.strip()]
            if kws:
                parts.append(f"Keywords: {', '.join(kws[:12])}")
            transcript = _truncate(c.text.replace("\n", " ").strip(), 420)
            parts.append(f"Transcript: {transcript}")
            chunk_texts.append("\n".join(parts))

        topic_texts: List[str] = []
        for t in topics:
            kws = ", ".join([kw for kw in (t.keywords or []) if kw][:10])
            topic_texts.append(
                "\n".join(
                    [
                        f"Topic: {t.label}",
                        f"Description: {t.description}",
                        f"Keywords: {kws}" if kws else "Keywords: (none)",
                    ]
                )
            )

        try:
            from app.services.embeddings import resolve_collection_name
            from app.services.vector_store import vector_store_service

            topic_embs = [
                normalize(v) for v in self.embedding_service.embed_batch(topic_texts)
            ]

            topic_matrix = np.vstack(topic_embs)  # (n_topics, dim)
            dimensions = int(topic_matrix.shape[1]) if topic_matrix.size else 0

            reused_vectors = 0
            indexed_vectors: Dict[Tuple[uuid.UUID, int], np.ndarray] = {}
            try:
                collection_name = resolve_collection_name(self.embedding_service)
                indexed_vectors = vector_store_service.fetch_video_chunk_vectors(
                    user_id=user_id,
                    video_ids=list(videos_by_id.keys()),
                    collection_name=collection_name,
                )
            except Exception:
                logger.exception(
                    "Failed to fetch vectors from Qdrant; embedding chunks instead"
                )
                indexed_vectors = {}

            chunk_vecs: List[Optional[np.ndarray]] = [None] * len(chunks)
            missing_texts: List[str] = []
            missing_indices: List[int] = []

            for i, c in enumerate(chunks):
                candidate = indexed_vectors.get((c.video_id, int(c.chunk_index)))
                if candidate is not None and dimensions and candidate.shape[-1] == dimensions:
                    chunk_vecs[i] = normalize(candidate)
                    reused_vectors += 1
                    continue

                missing_indices.append(i)
                missing_texts.append(chunk_texts[i])

            if missing_texts:
                computed = [
                    normalize(v)
                    for v in self.embedding_service.embed_batch(missing_texts)
                ]
                for idx, vec in zip(missing_indices, computed):
                    chunk_vecs[idx] = vec

            best_idx = np.zeros(len(chunks), dtype=int)
            best = np.zeros(len(chunks), dtype=float)
            gap = np.zeros(len(chunks), dtype=float)

            for i, vec in enumerate(chunk_vecs):
                if vec is None:
                    continue
                sims = vec @ topic_matrix.T
                bi = int(np.argmax(sims))
                bv = float(sims[bi])
                if sims.shape[0] > 1:
                    second = float(np.partition(sims, -2)[-2])
                else:
                    second = 0.0
                best_idx[i] = bi
                best[i] = bv
                gap[i] = bv - second

            # Adaptive threshold so we don't over-prune on diverse content.
            threshold = max(
                DEFAULT_MIN_TOPIC_SIMILARITY, float(np.percentile(best, 40))
            )
            gap_threshold = DEFAULT_MIN_TOPIC_GAP

            assigned_topic_idx = np.full(len(chunks), -1, dtype=int)

            def assign_pass(min_sim: float, min_gap: float) -> None:
                nonlocal assigned_topic_idx
                assigned_topic_idx = np.full(len(chunks), -1, dtype=int)
                for i in range(len(chunks)):
                    if float(best[i]) < min_sim:
                        continue
                    if float(gap[i]) < min_gap:
                        continue
                    assigned_topic_idx[i] = int(best_idx[i])

            assign_pass(threshold, gap_threshold)

            # If too sparse, relax once (still no filler: only evidence-based assignments).
            assigned_count = int(np.sum(assigned_topic_idx >= 0))
            if assigned_count < min(8, len(chunks)):
                relaxed_threshold = max(0.18, float(np.percentile(best, 20)))
                assign_pass(relaxed_threshold, 0.02)
                threshold = relaxed_threshold
                gap_threshold = 0.02
                assigned_count = int(np.sum(assigned_topic_idx >= 0))

            # Total counts (un-capped) for accurate topic chunk_count values.
            total_counts = {tid: 0 for tid in topic_ids}
            for idx in assigned_topic_idx:
                if idx < 0:
                    continue
                total_counts[topic_ids[int(idx)]] += 1

            # Evidence chunks: keep top-N per topic for UI + clustering.
            per_topic: Dict[str, List[Tuple[float, Chunk, np.ndarray]]] = {
                tid: [] for tid in topic_ids
            }
            order = np.argsort(-best)  # descending by confidence
            for i in order:
                assigned = int(assigned_topic_idx[int(i)])
                if assigned < 0:
                    continue
                tid = topic_ids[assigned]
                if len(per_topic[tid]) >= max_chunks_per_topic:
                    continue
                vec = chunk_vecs[int(i)]
                if vec is None:
                    continue
                per_topic[tid].append((float(best[int(i)]), chunks[int(i)], vec))

            # Convert assignments into TopicChunk objects (sorted by score).
            chunk_embeddings_by_id: Dict[uuid.UUID, np.ndarray] = {}
            for tid, scored_chunks in per_topic.items():
                scored_chunks.sort(key=lambda t: t[0], reverse=True)
                converted: List[TopicChunk] = []
                for score, chunk, vec in scored_chunks[:max_chunks_per_topic]:
                    video = videos_by_id.get(chunk.video_id)
                    video_title = video.title if video else "Unknown"
                    chunk_embeddings_by_id[chunk.id] = vec
                    converted.append(
                        TopicChunk(
                            chunk_id=chunk.id,
                            video_id=chunk.video_id,
                            video_title=video_title,
                            start_timestamp=float(chunk.start_timestamp),
                            end_timestamp=float(chunk.end_timestamp),
                            timestamp_display=chunk.timestamp_display,
                            text=_truncate(chunk.text.replace("\n", " ").strip(), 800),
                            chunk_title=chunk.chunk_title,
                            chapter_title=chunk.chapter_title,
                            chunk_summary=(
                                _truncate(chunk.chunk_summary.strip(), 320)
                                if chunk.chunk_summary
                                else None
                            ),
                        )
                    )
                topic_chunks[tid] = converted

            diagnostics = {
                "assignment_method": "embeddings_qdrant"
                if reused_vectors
                else "embeddings",
                "min_similarity": round(float(threshold), 3),
                "min_gap": round(float(gap_threshold), 3),
                "assigned_chunks": int(assigned_count),
                "unassigned_chunks": int(len(chunks) - assigned_count),
                "total_chunks_considered": int(len(chunks)),
                "reused_vectors": int(reused_vectors),
                "evidence_chunks": int(sum(len(v) for v in topic_chunks.values())),
            }

            return topic_chunks, chunk_embeddings_by_id, diagnostics, total_counts
        except Exception:
            logger.exception(
                "Embedding-based topic mapping failed; falling back to token overlap"
            )

        # Fallback: token overlap (still evidence-only, no filler).
        per_topic_fallback: Dict[str, List[Tuple[float, Chunk]]] = {
            tid: [] for tid in topic_ids
        }
        total_counts = {tid: 0 for tid in topic_ids}

        # Greedy: score each chunk against topics, assign to best if any overlap.
        for chunk in chunks:
            best_score = 0.0
            best_tid: Optional[str] = None
            for topic in topics:
                score = self._chunk_topic_score(topic, chunk)
                if score > best_score:
                    best_score = score
                    best_tid = topic.id
            if best_tid and best_score > 0:
                total_counts[best_tid] += 1
                per_topic_fallback[best_tid].append((best_score, chunk))

        for tid, scored_chunks in per_topic_fallback.items():
            scored_chunks.sort(key=lambda t: t[0], reverse=True)
            converted: List[TopicChunk] = []
            for score, chunk in scored_chunks[:max_chunks_per_topic]:
                video = videos_by_id.get(chunk.video_id)
                video_title = video.title if video else "Unknown"
                converted.append(
                    TopicChunk(
                        chunk_id=chunk.id,
                        video_id=chunk.video_id,
                        video_title=video_title,
                        start_timestamp=float(chunk.start_timestamp),
                        end_timestamp=float(chunk.end_timestamp),
                        timestamp_display=chunk.timestamp_display,
                        text=_truncate(chunk.text.replace("\n", " ").strip(), 800),
                        chunk_title=chunk.chunk_title,
                        chapter_title=chunk.chapter_title,
                        chunk_summary=(
                            _truncate(chunk.chunk_summary.strip(), 320)
                            if chunk.chunk_summary
                            else None
                        ),
                    )
                )
            topic_chunks[tid] = converted

        diagnostics = {
            "assignment_method": "token_overlap",
            "min_similarity": None,
            "min_gap": None,
            "assigned_chunks": int(sum(total_counts.values())),
            "unassigned_chunks": int(len(chunks) - sum(total_counts.values())),
            "total_chunks_considered": int(len(chunks)),
            "evidence_chunks": int(sum(len(v) for v in topic_chunks.values())),
        }

        return topic_chunks, {}, diagnostics, total_counts

    @staticmethod
    def _graph_needs_upgrade(graph_data: Any) -> bool:
        if not isinstance(graph_data, dict):
            return True
        nodes = graph_data.get("nodes") or []
        if not isinstance(nodes, list):
            return True
        has_root = any(
            isinstance(n, dict) and n.get("type") == "root"
            for n in nodes  # noqa: SIM102
        )
        has_video = any(isinstance(n, dict) and n.get("type") == "video" for n in nodes)
        return (not has_root) or has_video

    @staticmethod
    def _mind_map_layout(
        root_id: str,
        children: Dict[str, List[str]],
        *,
        x_spacing: float = 340.0,
        y_spacing: float = 130.0,
    ) -> Dict[str, Dict[str, float]]:
        """
        Simple tree layout (left-to-right) optimized for small mind maps.

        - Leaves are placed top-to-bottom, evenly spaced.
        - Internal nodes are centered over their children.
        """

        positions: Dict[str, Dict[str, float]] = {}
        next_y = 0.0

        def dfs(node_id: str, depth: int) -> float:
            nonlocal next_y
            kids = children.get(node_id, [])
            if not kids:
                y = next_y
                next_y += y_spacing
            else:
                child_ys = [dfs(child_id, depth + 1) for child_id in kids]
                y = sum(child_ys) / float(len(child_ys))
            positions[node_id] = {"x": float(depth) * x_spacing, "y": float(y)}
            return float(y)

        dfs(root_id, 0)

        ys = [p["y"] for p in positions.values()]
        if ys:
            mid = (min(ys) + max(ys)) / 2.0
            for p in positions.values():
                p["y"] -= mid

        return positions

    def _build_graph_structure(
        self,
        *,
        root_label: str,
        topics: Sequence[TopicNode],
        topic_chunks: Dict[str, Sequence[TopicChunk]],
        chunk_embeddings_by_id: Optional[Dict[uuid.UUID, np.ndarray]] = None,
        topic_total_counts: Optional[Dict[str, int]] = None,
        root_metadata: Optional[Dict[str, Any]] = None,
        max_subtopics_per_topic: int = DEFAULT_MAX_SUBTOPICS_PER_TOPIC,
        max_points_per_subtopic: int = DEFAULT_MAX_POINTS_PER_SUBTOPIC,
        max_moments_per_point: int = DEFAULT_MAX_MOMENTS_PER_POINT,
        enable_llm_labels: bool = True,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, List[TopicChunk]]]:
        """
        Evidence-first semantic mind map (max 5 layers):
        root -> topic -> subtopic(cluster) -> point(cluster) -> moment(chunk).
        """

        def normalize(vec: np.ndarray) -> np.ndarray:
            norm = float(np.linalg.norm(vec))
            if norm <= 0:
                return vec
            return vec / norm

        def chunk_embed_text(c: TopicChunk) -> str:
            parts: List[str] = []
            if c.chunk_title:
                parts.append(f"Title: {c.chunk_title}")
            if c.chunk_summary:
                parts.append(f"Summary: {c.chunk_summary}")
            if c.chapter_title:
                parts.append(f"Chapter: {c.chapter_title}")
            parts.append(f"Transcript: {_truncate((c.text or '').strip(), 480)}")
            return "\n".join(parts)

        def ensure_unique_labels(labels: List[str]) -> List[str]:
            seen: Dict[str, int] = {}
            out: List[str] = []
            for label in labels:
                key = label.strip().lower()
                if key not in seen:
                    seen[key] = 1
                    out.append(label)
                    continue
                seen[key] += 1
                out.append(f"{label} ({seen[key]})")
            return out

        def agglomerative_clusters(emb: np.ndarray, target_k: int) -> List[List[int]]:
            n = emb.shape[0]
            if n <= 0:
                return []
            if target_k <= 1 or n == 1:
                return [list(range(n))]
            target_k = min(target_k, n)

            sim = emb @ emb.T
            clusters: List[List[int]] = [[i] for i in range(n)]

            def cluster_sim(a: List[int], b: List[int]) -> float:
                block = sim[np.ix_(a, b)]
                return float(block.mean()) if block.size else -1.0

            while len(clusters) > target_k:
                best_pair: Optional[Tuple[int, int]] = None
                best_score = -1.0
                for i in range(len(clusters)):
                    for j in range(i + 1, len(clusters)):
                        score = cluster_sim(clusters[i], clusters[j])
                        if score > best_score:
                            best_score = score
                            best_pair = (i, j)

                if not best_pair:
                    break
                i, j = best_pair
                clusters[i] = clusters[i] + clusters[j]
                del clusters[j]

            return clusters

        def medoid_index(sim: np.ndarray, indices: List[int]) -> int:
            if not indices:
                return 0
            if len(indices) == 1:
                return indices[0]
            best_i = indices[0]
            best_score = -1.0
            for i in indices:
                score = float(sim[i, indices].mean())
                if score > best_score:
                    best_score = score
                    best_i = i
            return best_i

        def node_label_from_chunk(c: TopicChunk, *, max_len: int) -> str:
            candidate = (
                (c.chunk_title or "").strip()
                or (c.chapter_title or "").strip()
                or f"{c.video_title} {c.timestamp_display}".strip()
            )
            return _truncate(candidate or "Key idea", max_len)

        def moment_label(c: TopicChunk) -> str:
            title = (c.chunk_title or "").strip() or (c.chapter_title or "").strip()
            if title:
                base = _truncate(title, 34)
                return _truncate(f"{base} • {c.timestamp_display}", 60)
            return _truncate(f"{c.video_title} • {c.timestamp_display}", 60)

        # Core containers.
        root_id = "insights-root"
        children: Dict[str, List[str]] = {root_id: []}
        augmented_chunks: Dict[str, List[TopicChunk]] = {
            tid: list(chunks) for tid, chunks in topic_chunks.items()
        }
        fallback_labels: Dict[str, str] = {}
        fallback_desc: Dict[str, Optional[str]] = {}

        # Build semantic clusters for each topic (no cross-links, no filler).
        for topic in topics:
            children[root_id].append(topic.id)
            children.setdefault(topic.id, [])

            topic_level = list(topic_chunks.get(topic.id, []) or [])
            if not topic_level:
                continue

            # Get embeddings for this topic's chunks (prefer precomputed).
            embs: List[Optional[np.ndarray]] = [None] * len(topic_level)
            missing_texts: List[str] = []
            missing_idxs: List[int] = []
            for i, c in enumerate(topic_level):
                if chunk_embeddings_by_id and c.chunk_id in chunk_embeddings_by_id:
                    embs[i] = chunk_embeddings_by_id[c.chunk_id]
                else:
                    missing_idxs.append(i)
                    missing_texts.append(chunk_embed_text(c))

            if missing_texts:
                computed = [
                    normalize(v)
                    for v in self.embedding_service.embed_batch(missing_texts)
                ]
                for i, vec in zip(missing_idxs, computed):
                    embs[i] = vec

            emb = np.vstack([normalize(v) for v in embs if v is not None])
            sim = emb @ emb.T

            n = len(topic_level)
            if n <= 4:
                k_sub = 1
            elif n <= 10:
                k_sub = min(2, max_subtopics_per_topic)
            else:
                k_sub = min(3, max_subtopics_per_topic)

            sub_clusters = agglomerative_clusters(emb, k_sub)
            sub_clusters.sort(key=lambda idxs: (len(idxs), min(idxs)), reverse=True)

            for sub_index, sub_idxs in enumerate(sub_clusters, 1):
                sub_id = f"{topic.id}-sub-{sub_index}"
                children[topic.id].append(sub_id)
                children.setdefault(sub_id, [])

                sub_chunks = [topic_level[i] for i in sub_idxs]
                augmented_chunks[sub_id] = list(sub_chunks)

                med = medoid_index(sim, sub_idxs)
                fallback_labels[sub_id] = node_label_from_chunk(
                    topic_level[med], max_len=56
                )
                fallback_desc[sub_id] = (
                    _truncate(topic_level[med].chunk_summary, 140)
                    if topic_level[med].chunk_summary
                    else None
                )

                # Points within the subtopic.
                if len(sub_idxs) <= 3:
                    k_point = 1
                elif len(sub_idxs) <= 8:
                    k_point = min(2, max_points_per_subtopic)
                else:
                    k_point = min(3, max_points_per_subtopic)

                sub_emb = emb[sub_idxs, :]
                point_clusters = agglomerative_clusters(sub_emb, k_point)
                point_clusters.sort(
                    key=lambda idxs: (len(idxs), min(idxs)), reverse=True
                )

                for point_index, point_local in enumerate(point_clusters, 1):
                    point_id = f"{sub_id}-p-{point_index}"
                    children[sub_id].append(point_id)
                    children.setdefault(point_id, [])

                    point_abs = [sub_idxs[i] for i in point_local]
                    point_chunks = [topic_level[i] for i in point_abs]
                    augmented_chunks[point_id] = list(point_chunks)

                    p_med = medoid_index(sim, point_abs)
                    fallback_labels[point_id] = node_label_from_chunk(
                        topic_level[p_med], max_len=60
                    )
                    fallback_desc[point_id] = (
                        _truncate(topic_level[p_med].chunk_summary, 140)
                        if topic_level[p_med].chunk_summary
                        else None
                    )

                    # Moments: representative chunks (leaf evidence).
                    centroid = normalize(emb[point_abs, :].mean(axis=0))
                    scored = [(float(emb[i, :] @ centroid), i) for i in point_abs]
                    scored.sort(key=lambda t: t[0], reverse=True)
                    moment_abs = [i for _, i in scored[:max_moments_per_point]]

                    for moment_index, abs_i in enumerate(moment_abs, 1):
                        moment_id = f"{point_id}-m-{moment_index}"
                        children[point_id].append(moment_id)
                        augmented_chunks[moment_id] = [topic_level[abs_i]]

        # Optional one-shot LLM relabeling for subtopic/point nodes.
        label_overrides: Dict[str, Dict[str, Optional[str]]] = {}
        if enable_llm_labels and topics:
            try:
                items: List[Dict[str, Any]] = []
                for topic in topics:
                    for sub_id in children.get(topic.id, []):
                        sub_chunks = augmented_chunks.get(sub_id, [])
                        if sub_chunks:
                            items.append(
                                {
                                    "id": sub_id,
                                    "level": "subtopic",
                                    "parent_topic": topic.label,
                                    "evidence": [
                                        {
                                            "video": c.video_title,
                                            "time": c.timestamp_display,
                                            "title": c.chunk_title,
                                            "summary": c.chunk_summary,
                                            "text": _truncate(
                                                (c.text or "").strip(), 180
                                            ),
                                        }
                                        for c in sub_chunks[:4]
                                    ],
                                }
                            )
                        for point_id in children.get(sub_id, []):
                            point_chunks = augmented_chunks.get(point_id, [])
                            if not point_chunks:
                                continue
                            items.append(
                                {
                                    "id": point_id,
                                    "level": "point",
                                    "parent_topic": topic.label,
                                    "evidence": [
                                        {
                                            "video": c.video_title,
                                            "time": c.timestamp_display,
                                            "title": c.chunk_title,
                                            "summary": c.chunk_summary,
                                            "text": _truncate(
                                                (c.text or "").strip(), 180
                                            ),
                                        }
                                        for c in point_chunks[:3]
                                    ],
                                }
                            )

                if items:
                    system = (
                        "You label clusters of transcript evidence.\n"
                        "Return concise labels grounded in the evidence.\n\n"
                        "Rules:\n"
                        "- Use ONLY the evidence provided; do not invent facts.\n"
                        "- Labels: 3-8 words, Title Case.\n"
                        "- Descriptions: 1 sentence max.\n"
                        "- Keep labels unique within the same parent_topic.\n\n"
                        "Return ONLY valid JSON:\n"
                        '{ "labels": { "<id>": { "label": "...", "description": "..." } } }'
                    )
                    user = json.dumps({"items": items}, ensure_ascii=False)
                    response = self.llm_service.complete(
                        [
                            Message(role="system", content=system),
                            Message(role="user", content=user),
                        ],
                        temperature=0.2,
                        max_tokens=1200,
                    )
                    parsed = json.loads(_strip_markdown_code_fences(response.content))
                    labels = parsed.get("labels") if isinstance(parsed, dict) else None
                    if isinstance(labels, dict):
                        for node_id, payload in labels.items():
                            if not isinstance(payload, dict):
                                continue
                            label = str(payload.get("label") or "").strip()
                            desc = str(payload.get("description") or "").strip() or None
                            if label:
                                label_overrides[str(node_id)] = {
                                    "label": label,
                                    "description": desc,
                                }
            except Exception:
                logger.exception("LLM labeling failed; using deterministic labels")

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # Root.
        root_data: Dict[str, Any] = {
            "label": _truncate(root_label.strip() or "Conversation", 60),
            "topics_count": len(topics),
        }
        if root_metadata:
            root_data.update(root_metadata)
        nodes.append(
            {
                "id": root_id,
                "type": "root",
                "position": {"x": 0.0, "y": 0.0},
                "data": root_data,
            }
        )

        # Topics.
        for topic in topics:
            evidence_count = len(topic_chunks.get(topic.id, []) or [])
            total_count = (
                int(topic_total_counts.get(topic.id, evidence_count))
                if topic_total_counts
                else evidence_count
            )
            nodes.append(
                {
                    "id": topic.id,
                    "type": "topic",
                    "position": {"x": 0.0, "y": 0.0},
                    "data": {
                        "label": topic.label,
                        "description": topic.description,
                        "chunk_count": total_count,
                        "evidence_chunk_count": evidence_count,
                    },
                }
            )
            edges.append(
                {
                    "id": f"{root_id}->{topic.id}",
                    "source": root_id,
                    "target": topic.id,
                    "type": "smoothstep",
                }
            )

        # Subtopics/points/moments.
        for topic in topics:
            sub_ids = children.get(topic.id, [])
            sub_labels = ensure_unique_labels(
                [
                    label_overrides.get(sub_id, {}).get("label")
                    or fallback_labels.get(sub_id)
                    or "Subtopic"
                    for sub_id in sub_ids
                ]
            )

            for sub_id, sub_label in zip(sub_ids, sub_labels):
                sub_chunks = augmented_chunks.get(sub_id, [])
                nodes.append(
                    {
                        "id": sub_id,
                        "type": "subtopic",
                        "position": {"x": 0.0, "y": 0.0},
                        "data": {
                            "label": _truncate(sub_label, 56),
                            "description": label_overrides.get(sub_id, {}).get(
                                "description"
                            )
                            or fallback_desc.get(sub_id),
                            "chunk_count": len(sub_chunks),
                            "parent_topic_id": topic.id,
                        },
                    }
                )
                edges.append(
                    {
                        "id": f"{topic.id}->{sub_id}",
                        "source": topic.id,
                        "target": sub_id,
                        "type": "smoothstep",
                    }
                )

                point_ids = children.get(sub_id, [])
                point_labels = ensure_unique_labels(
                    [
                        label_overrides.get(point_id, {}).get("label")
                        or fallback_labels.get(point_id)
                        or "Point"
                        for point_id in point_ids
                    ]
                )
                for point_id, point_label in zip(point_ids, point_labels):
                    point_chunks = augmented_chunks.get(point_id, [])
                    nodes.append(
                        {
                            "id": point_id,
                            "type": "point",
                            "position": {"x": 0.0, "y": 0.0},
                            "data": {
                                "label": _truncate(point_label, 60),
                                "description": label_overrides.get(point_id, {}).get(
                                    "description"
                                )
                                or fallback_desc.get(point_id),
                                "chunk_count": len(point_chunks),
                                "parent_topic_id": topic.id,
                            },
                        }
                    )
                    edges.append(
                        {
                            "id": f"{sub_id}->{point_id}",
                            "source": sub_id,
                            "target": point_id,
                            "type": "smoothstep",
                        }
                    )

                    for moment_id in children.get(point_id, []):
                        moment_chunks = augmented_chunks.get(moment_id, [])
                        chunk = moment_chunks[0] if moment_chunks else None
                        nodes.append(
                            {
                                "id": moment_id,
                                "type": "moment",
                                "position": {"x": 0.0, "y": 0.0},
                                "data": {
                                    "label": moment_label(chunk) if chunk else "Moment",
                                    "description": None,
                                    "chunk_count": len(moment_chunks),
                                    "parent_topic_id": topic.id,
                                },
                            }
                        )
                        edges.append(
                            {
                                "id": f"{point_id}->{moment_id}",
                                "source": point_id,
                                "target": moment_id,
                                "type": "smoothstep",
                            }
                        )

        # Layout.
        positions = self._mind_map_layout(root_id, children)
        for node in nodes:
            pos = positions.get(node["id"])
            if pos:
                node["position"] = pos

        return nodes, edges, augmented_chunks

    def extract_topics_from_videos(
        self,
        db: Session,
        user_id: uuid.UUID,
        video_ids: Sequence[uuid.UUID],
        root_label: str = "Conversation",
        target_topics: int = DEFAULT_TARGET_TOPICS,
        max_chunks_analyzed: int = DEFAULT_MAX_CHUNKS_ANALYZED,
    ) -> InsightGraph:
        start = time.time()
        canonical_video_ids = _canonicalize_video_ids(video_ids)

        videos: List[Video] = (
            db.query(Video)
            .filter(
                Video.id.in_(canonical_video_ids),
                Video.user_id == user_id,
                Video.is_deleted == False,  # noqa: E712
                Video.status == "completed",
            )
            .all()
        )
        videos_by_id = {v.id: v for v in videos}
        if len(videos) != len(set(canonical_video_ids)):
            raise ValueError("One or more videos not found or not completed processing")

        all_chunks: List[Chunk] = (
            db.query(Chunk)
            .filter(
                Chunk.video_id.in_(canonical_video_ids),
                Chunk.user_id == user_id,
            )
            .order_by(Chunk.video_id, Chunk.chunk_index)
            .all()
        )

        if not all_chunks:
            raise ValueError("No transcript chunks found for selected videos")

        sampled_chunks = self._sample_chunks_for_extraction(
            all_chunks, max_chunks=max_chunks_analyzed
        )
        prompt_messages = self._build_prompt(
            videos, sampled_chunks, target_topics=target_topics
        )

        topics: List[TopicNode] = []
        llm_provider = None
        llm_model = None
        last_error: Optional[str] = None

        for attempt in range(2):
            try:
                response = self.llm_service.complete(
                    prompt_messages,
                    temperature=0.2,
                    max_tokens=1200,
                )
                llm_provider = response.provider
                llm_model = response.model
                topics = self._parse_topics_response(response.content)
                break
            except Exception as e:
                last_error = str(e)
                logger.exception(
                    "Topic extraction failed (attempt %s): %s", attempt + 1, str(e)
                )
                # Retry once with stricter instruction.
                if attempt == 0:
                    prompt_messages = [
                        prompt_messages[0],
                        Message(
                            role="user",
                            content=prompt_messages[1].content
                            + "\n\nIMPORTANT: Output raw JSON only (no markdown fences, no commentary).",
                        ),
                    ]

        if not topics:
            topics = self._fallback_topics_from_keywords(
                sampled_chunks, target_topics=target_topics
            )
            llm_provider = llm_provider or "fallback"
            llm_model = llm_model or "keywords"

        # Clamp topics to 5-10.
        topics = topics[:10]
        if len(topics) < 5:
            # Pad with fallback topics to reach minimum UI density.
            extra = self._fallback_topics_from_keywords(
                sampled_chunks, target_topics=5 - len(topics)
            )
            existing_labels = {t.label.lower() for t in topics}
            existing_ids = {t.id for t in topics}
            for t in extra:
                if t.label.lower() in existing_labels:
                    continue
                topic_id = t.id
                if topic_id in existing_ids:
                    suffix = 1
                    while f"topic-{suffix}" in existing_ids:
                        suffix += 1
                    topic_id = f"topic-{suffix}"
                topics.append(
                    TopicNode(
                        id=topic_id,
                        label=t.label,
                        description=t.description,
                        keywords=t.keywords,
                    )
                )
                existing_ids.add(topic_id)
                existing_labels.add(t.label.lower())
                if len(topics) >= 5:
                    break

        (
            topic_chunks,
            chunk_embeddings,
            assignment_meta,
            topic_total_counts,
        ) = self._map_topics_to_chunks(topics, all_chunks, videos_by_id, user_id=user_id)
        nodes, edges, expanded_chunks = self._build_graph_structure(
            root_label=root_label,
            topics=topics,
            topic_chunks=topic_chunks,
            chunk_embeddings_by_id=chunk_embeddings,
            topic_total_counts=topic_total_counts,
            root_metadata={
                "total_chunks_considered": int(len(all_chunks)),
                "sampled_chunks_analyzed": int(len(sampled_chunks)),
                **assignment_meta,
            },
            enable_llm_labels=True,
        )

        generation_time = time.time() - start

        metadata: Dict[str, Any] = {
            "topics_count": len(topics),
            "total_chunks_analyzed": len(sampled_chunks),
            "generation_time_seconds": round(generation_time, 3),
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "extraction_prompt_version": EXTRACTION_PROMPT_VERSION,
        }
        metadata.update({f"assignment_{k}": v for k, v in assignment_meta.items()})
        if last_error and llm_provider == "fallback":
            metadata[
                "warning"
            ] = f"LLM parsing failed, used fallback extraction: {last_error}"

        return InsightGraph(
            nodes=nodes,
            edges=edges,
            topic_chunks=expanded_chunks,
            metadata=metadata,
        )

    def get_or_generate_insights(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        video_ids: Sequence[uuid.UUID],
        force_regenerate: bool = False,
        root_label: str = "Conversation",
    ) -> Tuple[ConversationInsight, bool]:
        canonical_video_ids = _canonicalize_video_ids(video_ids)

        existing: Optional[ConversationInsight] = (
            db.query(ConversationInsight)
            .filter(
                ConversationInsight.conversation_id == conversation_id,
                ConversationInsight.user_id == user_id,
            )
            .order_by(ConversationInsight.created_at.desc())
            .first()
        )

        if existing and not force_regenerate:
            existing_video_ids = _canonicalize_video_ids(existing.video_ids or [])
            if existing_video_ids == canonical_video_ids:
                needs_upgrade = self._graph_needs_upgrade(existing.graph_data) or (
                    (existing.extraction_prompt_version or 0)
                    != EXTRACTION_PROMPT_VERSION
                )
                if not needs_upgrade:
                    return existing, True

                # New algorithm version or incompatible cached graph: regenerate.
                try:
                    insights = self.extract_topics_from_videos(
                        db,
                        user_id=user_id,
                        video_ids=canonical_video_ids,
                        root_label=root_label,
                    )
                    now = datetime.utcnow()
                    existing.video_ids = canonical_video_ids
                    existing.llm_provider = insights.metadata.get("llm_provider")
                    existing.llm_model = insights.metadata.get("llm_model")
                    existing.extraction_prompt_version = EXTRACTION_PROMPT_VERSION
                    existing.graph_data = insights.graph_dict()
                    existing.topic_chunks = insights.topic_chunks_dict()
                    existing.topics_count = int(
                        insights.metadata.get("topics_count") or 0
                    )
                    existing.total_chunks_analyzed = int(
                        insights.metadata.get("total_chunks_analyzed") or 0
                    )
                    existing.generation_time_seconds = float(
                        insights.metadata.get("generation_time_seconds") or 0.0
                    )
                    existing.created_at = now
                    db.commit()
                    db.refresh(existing)
                    return existing, False
                except Exception:
                    # If regeneration fails, fall back to returning the cached graph.
                    logger.exception(
                        "Insights regeneration failed; returning cached data"
                    )
                    return existing, True

        insights = self.extract_topics_from_videos(
            db,
            user_id=user_id,
            video_ids=canonical_video_ids,
            root_label=root_label,
        )

        now = datetime.utcnow()
        graph_data = insights.graph_dict()
        topic_chunks = insights.topic_chunks_dict()

        llm_provider = insights.metadata.get("llm_provider")
        llm_model = insights.metadata.get("llm_model")
        topics_count = int(insights.metadata.get("topics_count") or 0)
        if topics_count <= 0:
            topics_count = sum(
                1 for n in (graph_data.get("nodes") or []) if n.get("type") == "topic"
            )
        total_chunks_analyzed = int(insights.metadata.get("total_chunks_analyzed") or 0)
        generation_time_seconds = float(
            insights.metadata.get("generation_time_seconds") or 0.0
        )

        if existing:
            existing.video_ids = canonical_video_ids
            existing.llm_provider = llm_provider
            existing.llm_model = llm_model
            existing.extraction_prompt_version = EXTRACTION_PROMPT_VERSION
            existing.graph_data = graph_data
            existing.topic_chunks = topic_chunks
            existing.topics_count = topics_count
            existing.total_chunks_analyzed = total_chunks_analyzed
            existing.generation_time_seconds = generation_time_seconds
            existing.created_at = now
            db.commit()
            db.refresh(existing)
            return existing, False

        new_row = ConversationInsight(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            user_id=user_id,
            video_ids=canonical_video_ids,
            llm_provider=llm_provider,
            llm_model=llm_model,
            extraction_prompt_version=EXTRACTION_PROMPT_VERSION,
            graph_data=graph_data,
            topic_chunks=topic_chunks,
            topics_count=topics_count,
            total_chunks_analyzed=total_chunks_analyzed,
            generation_time_seconds=generation_time_seconds,
            created_at=now,
        )
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        return new_row, False

    def get_topic_chunks(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        topic_id: str,
    ) -> Dict[str, Any]:
        existing: Optional[ConversationInsight] = (
            db.query(ConversationInsight)
            .filter(
                ConversationInsight.conversation_id == conversation_id,
                ConversationInsight.user_id == user_id,
            )
            .order_by(ConversationInsight.created_at.desc())
            .first()
        )

        if not existing:
            raise ValueError("No cached insights found for conversation")

        topic_chunks = (existing.topic_chunks or {}).get(topic_id)
        if not topic_chunks:
            raise ValueError("Topic not found in cached insights")

        topic_label = topic_id
        try:
            for node in (existing.graph_data or {}).get("nodes", []):
                if node.get("id") == topic_id:
                    topic_label = (node.get("data") or {}).get("label") or topic_id
                    break
        except Exception:
            topic_label = topic_id

        return {
            "topic_id": topic_id,
            "topic_label": topic_label,
            "chunks": topic_chunks,
        }


insights_service = ConversationInsightsService()
