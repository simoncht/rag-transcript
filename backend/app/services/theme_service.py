"""
Theme aggregation and clustering service for collections.

Aggregates key_topics from videos, ranks by frequency, caches in Collection.meta JSONB field.
Also embeds video summaries, clusters with k-means, and generates LLM theme labels per cluster.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from app.models import Collection, CollectionVideo, Video

logger = logging.getLogger(__name__)

THEME_CACHE_TTL_SECONDS = 3600  # 1 hour
MAX_THEMES_PER_COLLECTION = 20


class ThemeService:
    """Aggregates and caches themes for collections."""

    def aggregate_collection_themes(
        self,
        db: Session,
        collection_id: UUID,
        user_id: UUID,
        force_refresh: bool = False,
    ) -> list[dict]:
        """
        Aggregate key_topics from all videos in a collection.

        Returns cached result if available and not expired,
        unless force_refresh=True.
        """
        collection = (
            db.query(Collection)
            .filter(
                Collection.id == collection_id,
                Collection.user_id == user_id,
                Collection.is_deleted.is_(False),
            )
            .first()
        )

        if not collection:
            return []

        # Check cache
        if not force_refresh:
            cached = self._get_cached_themes(collection)
            if cached is not None:
                return cached

        # Query videos with key_topics
        videos = (
            db.query(Video)
            .join(CollectionVideo, CollectionVideo.video_id == Video.id)
            .filter(
                CollectionVideo.collection_id == collection_id,
                Video.is_deleted.is_(False),
                Video.key_topics.isnot(None),
            )
            .all()
        )

        themes = self._compute_themes(videos)

        # Cache in collection meta
        self._cache_themes(db, collection, themes)

        return themes

    def _compute_themes(self, videos: list) -> list[dict]:
        """Compute theme aggregation from video key_topics."""
        topic_counter: Counter = Counter()
        topic_videos: dict[str, list[str]] = {}

        for video in videos:
            if not video.key_topics:
                continue
            for raw_topic in video.key_topics:
                normalized = self._normalize_topic(raw_topic)
                if not normalized:
                    continue
                topic_counter[normalized] += 1
                if normalized not in topic_videos:
                    topic_videos[normalized] = []
                video_id_str = str(video.id)
                if video_id_str not in topic_videos[normalized]:
                    topic_videos[normalized].append(video_id_str)

        # Sort by frequency (descending), then alphabetically
        sorted_topics = sorted(
            topic_counter.items(),
            key=lambda x: (-x[1], x[0]),
        )

        # Cap at max themes
        themes = []
        for topic, count in sorted_topics[:MAX_THEMES_PER_COLLECTION]:
            themes.append(
                {
                    "topic": topic,
                    "count": count,
                    "video_ids": topic_videos[topic],
                }
            )

        return themes

    @staticmethod
    def _normalize_topic(topic: str) -> str:
        """Normalize a topic string: lowercase, strip whitespace."""
        return topic.lower().strip()

    def _get_cached_themes(self, collection: Collection) -> Optional[list[dict]]:
        """Return cached themes if they exist and haven't expired."""
        meta = collection.meta or {}
        cached_themes = meta.get("cached_themes")
        cached_at_str = meta.get("cached_themes_at")

        if cached_themes is None or cached_at_str is None:
            return None

        try:
            cached_at = datetime.fromisoformat(cached_at_str)
        except (ValueError, TypeError):
            return None

        if datetime.utcnow() - cached_at > timedelta(seconds=THEME_CACHE_TTL_SECONDS):
            return None

        return cached_themes

    def _cache_themes(
        self, db: Session, collection: Collection, themes: list[dict]
    ) -> None:
        """Store computed themes in collection meta JSONB."""
        meta = dict(collection.meta or {})
        meta["cached_themes"] = themes
        meta["cached_themes_at"] = datetime.utcnow().isoformat()
        collection.meta = meta
        db.commit()

        logger.info(
            f"[Themes] Cached {len(themes)} themes for collection {collection.id}"
        )

    # ── Video Similarity ─────────────────────────────────────────────────

    def find_similar_videos(
        self,
        db: Session,
        video_id: UUID,
        user_id: UUID,
        limit: int = 5,
        min_similarity: float = 0.1,
    ) -> list[dict]:
        """
        Find videos similar to the given video based on shared key_topics.

        Uses Jaccard similarity on normalized topic sets.
        Scoped to the user's own videos only.
        """
        # Get the source video
        source_video = (
            db.query(Video)
            .filter(
                Video.id == video_id,
                Video.user_id == user_id,
                Video.is_deleted.is_(False),
            )
            .first()
        )

        if not source_video or not source_video.key_topics:
            return []

        source_topics = {self._normalize_topic(t) for t in source_video.key_topics if t}

        if not source_topics:
            return []

        # Get all other user videos with key_topics
        candidates = (
            db.query(Video)
            .filter(
                Video.user_id == user_id,
                Video.id != video_id,
                Video.is_deleted.is_(False),
                Video.key_topics.isnot(None),
            )
            .all()
        )

        # Score each candidate
        scored = []
        for candidate in candidates:
            if not candidate.key_topics:
                continue
            candidate_topics = {
                self._normalize_topic(t) for t in candidate.key_topics if t
            }
            if not candidate_topics:
                continue

            similarity = self._jaccard_similarity(source_topics, candidate_topics)
            if similarity < min_similarity:
                continue

            shared = sorted(source_topics & candidate_topics)
            scored.append(
                {
                    "video_id": str(candidate.id),
                    "title": candidate.title,
                    "content_type": getattr(candidate, "content_type", "youtube"),
                    "similarity": round(similarity, 3),
                    "shared_topics": shared,
                    "thumbnail_url": candidate.thumbnail_url,
                    "duration_seconds": candidate.duration_seconds,
                }
            )

        # Sort by similarity descending
        scored.sort(key=lambda x: -x["similarity"])
        return scored[:limit]

    @staticmethod
    def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
        """Compute Jaccard similarity between two topic sets."""
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    # ── LLM-Powered Clustering (Phase 4) ─────────────────────────────────

    MIN_VIDEOS_FOR_CLUSTERING = 3

    def cluster_collection_themes(
        self,
        db: Session,
        collection_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        """
        Cluster videos in a collection by embedding similarity,
        then generate LLM theme labels for each cluster.

        Requires at least 3 videos with summaries.
        Falls back to simple aggregation if clustering fails.
        """

        # Verify collection
        collection = (
            db.query(Collection)
            .filter(
                Collection.id == collection_id,
                Collection.user_id == user_id,
                Collection.is_deleted.is_(False),
            )
            .first()
        )
        if not collection:
            return []

        # Get videos with summaries
        videos = (
            db.query(Video)
            .join(CollectionVideo, CollectionVideo.video_id == Video.id)
            .filter(
                CollectionVideo.collection_id == collection_id,
                Video.is_deleted.is_(False),
                Video.summary.isnot(None),
            )
            .all()
        )

        if len(videos) < self.MIN_VIDEOS_FOR_CLUSTERING:
            logger.info(
                f"[Themes] Collection {collection_id} has {len(videos)} videos "
                f"with summaries (min {self.MIN_VIDEOS_FOR_CLUSTERING}), "
                "falling back to simple aggregation"
            )
            return self.aggregate_collection_themes(
                db, collection_id, user_id, force_refresh=True
            )

        # Embed summaries
        try:
            embeddings = self._embed_summaries(videos)
        except Exception as e:
            logger.error(f"[Themes] Embedding failed: {e}")
            return self.aggregate_collection_themes(
                db, collection_id, user_id, force_refresh=True
            )

        # Cluster
        k = self._select_k(len(videos))
        labels = self._run_kmeans(embeddings, k)

        # Group videos by cluster
        clusters = self._group_by_cluster(videos, labels)

        # Generate LLM labels
        clustered_themes = []
        for cluster_idx, cluster_videos in clusters.items():
            theme = self._label_cluster(cluster_idx, cluster_videos)
            clustered_themes.append(theme)

        # Sort by relevance score (cluster size)
        clustered_themes.sort(key=lambda t: -t["relevance_score"])

        # Persist to collection_themes table
        self._save_clustered_themes(db, collection_id, clustered_themes)

        return clustered_themes

    @staticmethod
    def _select_k(n_videos: int) -> int:
        """Select number of clusters: max(2, min(n // 3, 10))."""
        return max(2, min(n_videos // 3, 10))

    def _embed_summaries(self, videos: list) -> np.ndarray:
        """Embed video summaries using the embedding service."""
        from app.services.embeddings import embedding_service

        texts = []
        for video in videos:
            text = video.summary or ""
            if video.key_topics:
                text += " " + " ".join(video.key_topics)
            texts.append(text)

        embeddings = embedding_service.embed_batch(texts)
        return np.array(embeddings)

    @staticmethod
    def _run_kmeans(embeddings: np.ndarray, k: int) -> np.ndarray:
        """Run k-means clustering on embeddings."""
        from sklearn.cluster import KMeans

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        return labels

    @staticmethod
    def _group_by_cluster(
        videos: list, labels: np.ndarray
    ) -> dict[int, list]:
        """Group videos by their cluster label."""
        clusters: dict[int, list] = {}
        for video, label in zip(videos, labels):
            label_int = int(label)
            if label_int not in clusters:
                clusters[label_int] = []
            clusters[label_int].append(video)
        return clusters

    def _label_cluster(
        self, cluster_idx: int, cluster_videos: list
    ) -> dict:
        """Generate a theme label for a cluster using LLM."""
        # Collect titles and topics for the prompt
        titles = [v.title for v in cluster_videos]
        all_topics = []
        for v in cluster_videos:
            if v.key_topics:
                all_topics.extend(v.key_topics)

        topic_counts = Counter(all_topics)
        top_keywords = [t for t, _ in topic_counts.most_common(10)]

        video_ids = [str(v.id) for v in cluster_videos]
        relevance_score = len(cluster_videos)

        # Try LLM labeling
        try:
            label, description = self._llm_label_cluster(titles, top_keywords)
        except Exception as e:
            logger.warning(f"[Themes] LLM labeling failed for cluster {cluster_idx}: {e}")
            label = ", ".join(top_keywords[:3]) if top_keywords else f"Cluster {cluster_idx + 1}"
            description = f"Contains {len(cluster_videos)} videos"

        return {
            "theme_label": label,
            "theme_description": description,
            "video_ids": video_ids,
            "relevance_score": relevance_score,
            "topic_keywords": [self._normalize_topic(t) for t in top_keywords],
        }

    @staticmethod
    def _llm_label_cluster(
        titles: list[str], keywords: list[str]
    ) -> tuple[str, str]:
        """Use LLM to generate a human-readable theme label and description."""
        from app.services.llm_providers import llm_service

        titles_str = "\n".join(f"- {t}" for t in titles[:10])
        keywords_str = ", ".join(keywords[:10])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a theme labeling assistant. Given a group of video titles "
                    "and their key topics, generate a concise theme label (3-6 words) "
                    "and a brief description (1-2 sentences).\n\n"
                    "Respond in JSON format:\n"
                    '{"label": "Theme Label Here", "description": "Brief description."}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Video titles:\n{titles_str}\n\n"
                    f"Key topics: {keywords_str}\n\n"
                    "Generate a theme label and description."
                ),
            },
        ]

        response = llm_service.complete(messages, temperature=0.3, max_tokens=150)

        # Parse JSON from response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        parsed = json.loads(content)
        label = parsed.get("label", "Unnamed Theme")[:255]
        description = parsed.get("description", "")

        return label, description

    def _save_clustered_themes(
        self,
        db: Session,
        collection_id: UUID,
        themes: list[dict],
    ) -> None:
        """Persist clustered themes, replacing any previous ones."""
        from app.models.collection_theme import CollectionTheme

        # Delete old themes for this collection
        db.query(CollectionTheme).filter(
            CollectionTheme.collection_id == collection_id
        ).delete()

        # Insert new themes
        for theme_data in themes:
            theme = CollectionTheme(
                collection_id=collection_id,
                theme_label=theme_data["theme_label"],
                theme_description=theme_data.get("theme_description"),
                video_ids=theme_data["video_ids"],
                relevance_score=theme_data.get("relevance_score"),
                topic_keywords=theme_data.get("topic_keywords", []),
            )
            db.add(theme)

        db.commit()
        logger.info(
            f"[Themes] Saved {len(themes)} clustered themes for collection {collection_id}"
        )


# Module-level singleton
_theme_service: Optional[ThemeService] = None


def get_theme_service() -> ThemeService:
    global _theme_service
    if _theme_service is None:
        _theme_service = ThemeService()
    return _theme_service
