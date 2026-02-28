#!/usr/bin/env python3
"""
Generate a golden dataset for RAG evaluation from existing pipeline results.

Creates queries from indexed content, runs them through retrieval, and records
retrieved chunk IDs as ground truth. This creates a regression-detection baseline
(not human-labeled gold standard, but sufficient to measure pipeline changes).

Usage:
    python scripts/generate_golden_dataset.py                     # Template-based
    python scripts/generate_golden_dataset.py --use-llm           # LLM-based queries
    python scripts/generate_golden_dataset.py --dry-run            # Preview only
    python scripts/generate_golden_dataset.py --num-queries 30     # More queries
    python scripts/generate_golden_dataset.py --video-ids id1,id2  # Specific videos
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models import Video
from app.models.chunk import Chunk
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store_service

GOLDEN_DATASET_PATH = (
    Path(__file__).parent.parent / "tests" / "evaluation" / "golden_dataset.json"
)

# --- Query Templates ---

PRECISION_TEMPLATES = [
    "What does the speaker say about {topic}?",
    "What is mentioned about {topic}?",
    "Explain the concept of {topic} as discussed",
    "What specific details are given about {topic}?",
    "How is {topic} described?",
    "What points are made about {topic}?",
]

COVERAGE_TEMPLATES = [
    "Summarize the main points about {topic} across videos",
    "What are the different perspectives on {topic}?",
    "How is {topic} discussed across the content?",
    "Compare what is said about {topic} in different videos",
]

HYBRID_TEMPLATES = [
    "Give an overview of {topic} with specific examples",
    "What are the key takeaways about {topic}?",
    "Explain {topic} and provide supporting details",
    "What practical advice is given about {topic}?",
]

CONCEPTUAL_TEMPLATES = [
    "Why is {topic} important according to the speakers?",
    "What are the implications of {topic}?",
    "How does {topic} relate to the broader discussion?",
    "What challenges are associated with {topic}?",
]

LLM_QUERY_PROMPT = """Given the following transcript chunk from a video, generate a single natural question that this chunk would answer well. The question should be specific enough to retrieve this chunk but natural enough that a real user would ask it.

Chunk title: {title}
Chunk summary: {summary}
Keywords: {keywords}

Chunk text:
{text}

Respond with ONLY the question, nothing else."""


def load_content(
    db: Session, video_ids: Optional[List[str]] = None
) -> List[Dict]:
    """Load completed videos with sample chunks from the database."""
    query = (
        db.query(Video)
        .filter(Video.status == "completed", Video.is_deleted == False)
        .order_by(Video.created_at.desc())
    )

    if video_ids:
        uuid_ids = [UUID(vid) for vid in video_ids]
        query = query.filter(Video.id.in_(uuid_ids))

    videos = query.all()

    results = []
    for video in videos:
        chunks = (
            db.query(Chunk)
            .filter(Chunk.video_id == video.id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        if chunks:
            results.append({"video": video, "chunks": chunks})

    return results


def extract_topics(chunks: List, rng: random.Random) -> List[Tuple[str, "Chunk"]]:
    """Extract topics from chunks using keywords, titles, or text."""
    topics = []
    for chunk in chunks:
        # Prefer keywords
        if chunk.keywords:
            for kw in chunk.keywords:
                if len(kw) > 2 and len(kw.split()) <= 4:
                    topics.append((kw, chunk))
        # Fall back to chunk title
        elif chunk.chunk_title:
            topics.append((chunk.chunk_title, chunk))
        # Last resort: first meaningful phrase from text
        elif chunk.text:
            first_sentence = chunk.text.split(".")[0].strip()
            if 10 < len(first_sentence) < 100:
                topics.append((first_sentence[:60], chunk))

    rng.shuffle(topics)
    return topics


def generate_template_queries(
    video_data: List[Dict],
    num_queries: int,
    rng: random.Random,
) -> List[Dict]:
    """Generate queries using templates and extracted topics."""
    queries = []
    num_videos = len(video_data)

    # Determine intent distribution
    if num_videos < 3:
        # Few videos: skip coverage, more precision
        intent_counts = {
            "precision": max(6, num_queries // 2),
            "coverage": 0,
            "hybrid": num_queries // 4,
            "conceptual": num_queries - max(6, num_queries // 2) - num_queries // 4,
        }
    else:
        intent_counts = {
            "precision": max(5, num_queries * 3 // 10),
            "coverage": max(3, num_queries * 2 // 10),
            "hybrid": max(3, num_queries * 2 // 10),
            "conceptual": 0,  # remainder
        }
        intent_counts["conceptual"] = num_queries - sum(intent_counts.values())

    # Collect all topics across videos
    all_topics = []
    for vd in video_data:
        topics = extract_topics(vd["chunks"], rng)
        for topic, chunk in topics:
            all_topics.append((topic, chunk, vd["video"]))

    if not all_topics:
        print("WARNING: No topics extracted from chunks. Cannot generate queries.")
        return []

    # Track used topics to avoid duplicates
    used_topics = set()

    def pick_topic() -> Optional[Tuple[str, "Chunk", "Video"]]:
        for topic, chunk, video in all_topics:
            if topic.lower() not in used_topics:
                used_topics.add(topic.lower())
                return (topic, chunk, video)
        return None

    templates_by_intent = {
        "precision": PRECISION_TEMPLATES,
        "coverage": COVERAGE_TEMPLATES,
        "hybrid": HYBRID_TEMPLATES,
        "conceptual": CONCEPTUAL_TEMPLATES,
    }

    difficulty_by_intent = {
        "precision": ["easy", "medium"],
        "coverage": ["hard"],
        "hybrid": ["medium"],
        "conceptual": ["medium", "hard"],
    }

    tags_by_intent = {
        "precision": ["specific-fact"],
        "coverage": ["multi-video", "summary"],
        "hybrid": ["overview", "evidence"],
        "conceptual": ["reasoning"],
    }

    for intent, count in intent_counts.items():
        if count <= 0:
            continue
        templates = templates_by_intent[intent]
        difficulties = difficulty_by_intent[intent]

        for _ in range(count):
            pick = pick_topic()
            if not pick:
                # Exhausted unique topics, allow reuse with different templates
                rng.shuffle(all_topics)
                used_topics.clear()
                pick = pick_topic()
                if not pick:
                    break

            topic, chunk, video = pick
            template = rng.choice(templates)
            query_text = template.format(topic=topic)

            # Derive expected_answer_contains from keywords
            answer_keywords = []
            if chunk.keywords:
                answer_keywords = chunk.keywords[:3]
            elif topic:
                answer_keywords = [topic]

            tags = list(tags_by_intent[intent])
            if num_videos == 1:
                tags.append("single-video")

            queries.append(
                {
                    "query": query_text,
                    "intent": intent,
                    "difficulty": rng.choice(difficulties),
                    "expected_answer_contains": answer_keywords,
                    "tags": tags,
                    "source_video_title": video.title,
                    "source_chunk_index": chunk.chunk_index,
                }
            )

    return queries[:num_queries]


def generate_llm_queries(
    video_data: List[Dict],
    num_queries: int,
    rng: random.Random,
) -> List[Dict]:
    """Generate queries using LLM, with template fallback."""
    try:
        from app.services.llm_providers import llm_service, Message

        print("LLM service available — generating natural queries...")
    except Exception as e:
        print(f"WARNING: LLM unavailable ({e}), falling back to templates")
        return generate_template_queries(video_data, num_queries, rng)

    queries = []
    num_videos = len(video_data)

    # Sample chunks across videos
    candidate_chunks = []
    for vd in video_data:
        video = vd["video"]
        chunks = vd["chunks"]
        # Sample up to 8 chunks per video, preferring those with enrichment
        enriched = [c for c in chunks if c.keywords or c.chunk_title]
        sample_pool = enriched if enriched else chunks
        sample_size = min(8, len(sample_pool))
        sampled = rng.sample(sample_pool, sample_size)
        for chunk in sampled:
            candidate_chunks.append((chunk, video))

    rng.shuffle(candidate_chunks)

    # Assign intents round-robin
    if num_videos < 3:
        intents = ["precision", "hybrid", "conceptual"]
    else:
        intents = ["precision", "coverage", "hybrid", "conceptual"]

    difficulty_by_intent = {
        "precision": ["easy", "medium"],
        "coverage": ["hard"],
        "hybrid": ["medium"],
        "conceptual": ["medium", "hard"],
    }

    for i, (chunk, video) in enumerate(candidate_chunks[:num_queries]):
        intent = intents[i % len(intents)]
        prompt = LLM_QUERY_PROMPT.format(
            title=chunk.chunk_title or "N/A",
            summary=chunk.chunk_summary or "N/A",
            keywords=", ".join(chunk.keywords) if chunk.keywords else "N/A",
            text=chunk.text[:1000],
        )

        try:
            response = llm_service.complete(
                [Message(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=100,
            )
            query_text = response.content.strip().strip('"').strip("'")
            if not query_text or len(query_text) < 10:
                raise ValueError("LLM returned empty/short query")
        except Exception as e:
            print(f"  LLM failed for chunk {chunk.chunk_index}: {e}")
            # Fallback to template
            topic = (
                (chunk.keywords[0] if chunk.keywords else None)
                or chunk.chunk_title
                or chunk.text.split(".")[0][:60]
            )
            template = rng.choice(PRECISION_TEMPLATES)
            query_text = template.format(topic=topic)

        answer_keywords = []
        if chunk.keywords:
            answer_keywords = chunk.keywords[:3]

        tags = []
        if intent == "coverage":
            tags.append("multi-video")
        if num_videos == 1:
            tags.append("single-video")

        queries.append(
            {
                "query": query_text,
                "intent": intent,
                "difficulty": rng.choice(difficulty_by_intent[intent]),
                "expected_answer_contains": answer_keywords,
                "tags": tags,
                "source_video_title": video.title,
                "source_chunk_index": chunk.chunk_index,
            }
        )

    return queries


def record_ground_truth(
    queries: List[Dict],
    embedding_service: EmbeddingService,
    top_k: int,
) -> List[Dict]:
    """Run retrieval for each query and record chunk/video IDs as ground truth."""
    valid_queries = []

    for i, q in enumerate(queries):
        print(f"  [{i + 1}/{len(queries)}] Retrieving: {q['query'][:60]}...")

        try:
            query_embedding = embedding_service.embed_text(
                q["query"], is_query=True
            )
            if isinstance(query_embedding, tuple):
                query_embedding = np.array(query_embedding, dtype=np.float32)

            chunks = vector_store_service.search_chunks(
                query_embedding=query_embedding,
                top_k=top_k,
            )

            chunk_ids = [str(c.chunk_id) for c in chunks if c.chunk_id]
            video_ids = list(
                dict.fromkeys(str(c.video_id) for c in chunks if c.video_id)
            )

            if not chunk_ids:
                print(f"    0 results — skipping")
                continue

            # Enrich expected_answer_contains from retrieved chunks
            extra_keywords = set()
            for c in chunks[:3]:
                if c.keywords:
                    extra_keywords.update(c.keywords[:2])
            existing = set(q.get("expected_answer_contains", []))
            merged = list(existing | extra_keywords)[:5]

            q["expected_chunk_ids"] = chunk_ids
            q["expected_video_ids"] = video_ids
            q["expected_answer_contains"] = merged
            valid_queries.append(q)

            print(f"    {len(chunk_ids)} chunks, {len(video_ids)} videos")

        except Exception as e:
            print(f"    ERROR: {e}")
            continue

    return valid_queries


def build_dataset(
    queries: List[Dict],
    config: Dict,
) -> Dict:
    """Build the final golden dataset JSON structure."""
    formatted_queries = []
    for i, q in enumerate(queries, 1):
        formatted_queries.append(
            {
                "id": f"q{i:03d}",
                "query": q["query"],
                "intent": q["intent"],
                "expected_chunk_ids": q.get("expected_chunk_ids", []),
                "expected_video_ids": q.get("expected_video_ids", []),
                "expected_answer_contains": q.get("expected_answer_contains", []),
                "difficulty": q["difficulty"],
                "tags": q.get("tags", []),
            }
        )

    return {
        "version": "2.0",
        "description": "Auto-generated from pipeline results",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_config": config,
        "queries": formatted_queries,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate golden dataset for RAG evaluation"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(GOLDEN_DATASET_PATH),
        help="Output path (default: tests/evaluation/golden_dataset.json)",
    )
    parser.add_argument(
        "--num-queries",
        type=int,
        default=20,
        help="Target query count (default: 20)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Chunks to record as ground truth (default: 10)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for natural query generation",
    )
    parser.add_argument(
        "--video-ids",
        type=str,
        help="Comma-separated video UUIDs to restrict to",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without running retrieval",
    )

    args = parser.parse_args()
    rng = random.Random(args.seed)
    video_id_list = args.video_ids.split(",") if args.video_ids else None

    config = {
        "num_queries": args.num_queries,
        "top_k": args.top_k,
        "seed": args.seed,
        "use_llm": args.use_llm,
        "video_ids": video_id_list,
    }

    print("=" * 60)
    print("Golden Dataset Generator")
    print("=" * 60)

    # Phase 1: Load content
    print("\n--- Phase 1: Loading content from database ---")
    db: Session = SessionLocal()
    try:
        video_data = load_content(db, video_id_list)
    finally:
        db.close()

    if not video_data:
        print("ERROR: No completed videos with indexed chunks found.")
        print("Process some videos first, then re-run this script.")
        sys.exit(1)

    total_chunks = sum(len(vd["chunks"]) for vd in video_data)
    print(f"Found {len(video_data)} videos with {total_chunks} total chunks:")
    for vd in video_data:
        v = vd["video"]
        print(f"  - {v.title[:60]} ({len(vd['chunks'])} chunks)")

    # Phase 2: Generate queries
    print(f"\n--- Phase 2: Generating {args.num_queries} queries ---")
    if args.use_llm:
        queries = generate_llm_queries(video_data, args.num_queries, rng)
    else:
        queries = generate_template_queries(video_data, args.num_queries, rng)

    if not queries:
        print("ERROR: Failed to generate any queries.")
        sys.exit(1)

    print(f"Generated {len(queries)} queries:")
    intent_counts = {}
    for q in queries:
        intent_counts[q["intent"]] = intent_counts.get(q["intent"], 0) + 1
    for intent, count in sorted(intent_counts.items()):
        print(f"  {intent}: {count}")

    if args.dry_run:
        print("\n--- Dry Run: Preview ---")
        for i, q in enumerate(queries, 1):
            print(f"  q{i:03d} [{q['intent']}] {q['query'][:70]}")
        print(f"\nDry run complete. {len(queries)} queries would be generated.")
        print("Run without --dry-run to execute retrieval and save.")
        return

    # Phase 3: Record ground truth
    print(f"\n--- Phase 3: Recording ground truth (top_k={args.top_k}) ---")
    embedding_service = EmbeddingService()
    print(f"Embedding model: {embedding_service.get_model_name()}")

    start_time = time.time()
    valid_queries = record_ground_truth(queries, embedding_service, args.top_k)
    elapsed = time.time() - start_time

    if not valid_queries:
        print("ERROR: No queries returned results. Check vector store connectivity.")
        sys.exit(1)

    print(f"\n{len(valid_queries)}/{len(queries)} queries have results ({elapsed:.1f}s)")

    # Phase 4: Write output
    print(f"\n--- Phase 4: Writing golden dataset ---")
    dataset = build_dataset(valid_queries, config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"Written to: {output_path}")
    print(f"  Version: {dataset['version']}")
    print(f"  Queries: {len(dataset['queries'])}")
    print(f"  Generated at: {dataset['generated_at']}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Next steps:")
    print(f"  1. Review: cat {output_path}")
    print(f"  2. Evaluate: python scripts/run_evaluation.py --report")
    print(f"  3. Baseline: python scripts/run_evaluation.py --baseline --baseline-name v1")
    print(f"  4. Compare:  python scripts/run_evaluation.py --compare v1")
    print("=" * 60)


if __name__ == "__main__":
    main()
