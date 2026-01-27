"""
Memory Consolidation Service.

Post-session cleanup of conversation facts based on OpenAI/Anthropic best practices:
1. Deduplication: Merge semantically equivalent memories
2. Decay: Apply time-based decay to old, unused facts
3. Pruning: Remove low-importance facts that haven't been accessed

This prevents fact accumulation (98→142 in one session) and keeps memory focused.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.conversation_fact import ConversationFact, FactCategory

logger = logging.getLogger(__name__)

# Consolidation thresholds
MIN_IMPORTANCE_THRESHOLD = 0.3  # Facts below this get pruned if unused
STALE_DAYS_THRESHOLD = 7  # Days without access before decay penalty
DECAY_PENALTY = 0.1  # Importance reduction for stale facts
MAX_FACTS_PER_CONVERSATION = 50  # Soft limit before aggressive pruning
SIMILARITY_THRESHOLD = 0.85  # For deduplication (if embeddings available)


class MemoryConsolidationService:
    """Consolidate and prune conversation facts."""

    def consolidate_conversation(
        self,
        db: Session,
        conversation_id: str,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """
        Run consolidation pipeline for a single conversation.

        Args:
            db: Database session
            conversation_id: Conversation UUID
            dry_run: If True, don't commit changes

        Returns:
            Dict with consolidation stats (merged, decayed, pruned)
        """
        stats = {
            "merged": 0,
            "decayed": 0,
            "pruned": 0,
            "total_before": 0,
            "total_after": 0,
        }

        # Get all facts for this conversation
        facts = (
            db.query(ConversationFact)
            .filter(ConversationFact.conversation_id == conversation_id)
            .all()
        )

        if not facts:
            return stats

        stats["total_before"] = len(facts)

        # 1. Deduplicate similar facts
        merged_count = self._deduplicate_facts(db, facts, dry_run)
        stats["merged"] = merged_count

        # Refresh facts list after deduplication
        if not dry_run:
            facts = (
                db.query(ConversationFact)
                .filter(ConversationFact.conversation_id == conversation_id)
                .all()
            )

        # 2. Apply decay to stale facts
        decayed_count = self._apply_decay(db, facts, dry_run)
        stats["decayed"] = decayed_count

        # 3. Prune low-importance, unused facts
        pruned_count = self._prune_facts(db, conversation_id, facts, dry_run)
        stats["pruned"] = pruned_count

        # Final count
        if not dry_run:
            db.commit()
            remaining = (
                db.query(func.count(ConversationFact.id))
                .filter(ConversationFact.conversation_id == conversation_id)
                .scalar()
            )
            stats["total_after"] = remaining
        else:
            stats["total_after"] = stats["total_before"] - stats["merged"] - stats["pruned"]

        logger.info(
            f"[Memory Consolidation] Conversation {conversation_id}: "
            f"merged={merged_count}, decayed={decayed_count}, pruned={pruned_count}, "
            f"total: {stats['total_before']} → {stats['total_after']}"
        )

        return stats

    def _deduplicate_facts(
        self,
        db: Session,
        facts: List[ConversationFact],
        dry_run: bool,
    ) -> int:
        """
        Merge semantically equivalent facts.

        Uses key similarity and value overlap to identify duplicates.
        Keeps the fact with higher importance/earlier turn.

        Returns:
            Number of facts merged (deleted)
        """
        merged_count = 0

        # Group facts by normalized key patterns
        key_groups = defaultdict(list)
        for fact in facts:
            # Normalize key: remove underscores/numbers for grouping
            base_key = self._normalize_key_for_grouping(fact.fact_key)
            key_groups[base_key].append(fact)

        # Process groups with multiple facts
        for base_key, group_facts in key_groups.items():
            if len(group_facts) <= 1:
                continue

            # Sort by importance desc, then source_turn asc (prefer earlier + more important)
            group_facts.sort(key=lambda f: (-f.importance, f.source_turn))

            # Keep the first (best), merge/delete the rest
            keeper = group_facts[0]
            for fact in group_facts[1:]:
                # Check if values are similar enough to merge
                if self._values_are_similar(keeper.fact_value, fact.fact_value):
                    logger.debug(
                        f"[Memory Consolidation] Merging duplicate: "
                        f"{fact.fact_key}={fact.fact_value[:30]} into "
                        f"{keeper.fact_key}={keeper.fact_value[:30]}"
                    )

                    if not dry_run:
                        # Update keeper with any higher values from duplicate
                        if fact.access_count > keeper.access_count:
                            keeper.access_count = fact.access_count
                        if fact.last_accessed and (
                            not keeper.last_accessed or fact.last_accessed > keeper.last_accessed
                        ):
                            keeper.last_accessed = fact.last_accessed

                        # Delete the duplicate
                        db.delete(fact)

                    merged_count += 1

        return merged_count

    def _normalize_key_for_grouping(self, key: str) -> str:
        """
        Normalize a fact key for grouping similar facts.

        Examples:
            frequency_333_khz → frequency
            instructor_name → instructor
            topic_1 → topic
        """
        import re

        # Remove trailing numbers and underscores
        normalized = re.sub(r"_?\d+$", "", key)
        # Remove common suffixes
        normalized = re.sub(r"_(name|value|type|id)$", "", normalized)

        return normalized.lower()

    def _values_are_similar(self, value1: str, value2: str) -> bool:
        """
        Check if two fact values are similar enough to be considered duplicates.

        Uses simple heuristics (could be enhanced with embeddings).
        """
        v1_lower = value1.lower().strip()
        v2_lower = value2.lower().strip()

        # Exact match
        if v1_lower == v2_lower:
            return True

        # One contains the other
        if v1_lower in v2_lower or v2_lower in v1_lower:
            return True

        # Word overlap (Jaccard similarity)
        words1 = set(v1_lower.split())
        words2 = set(v2_lower.split())
        if not words1 or not words2:
            return False

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        jaccard = intersection / union if union > 0 else 0

        return jaccard >= SIMILARITY_THRESHOLD

    def _apply_decay(
        self,
        db: Session,
        facts: List[ConversationFact],
        dry_run: bool,
    ) -> int:
        """
        Apply decay to stale facts that haven't been accessed recently.

        Facts that are accessed regularly maintain their importance.
        Unused facts gradually lose importance over time.

        Returns:
            Number of facts that had decay applied
        """
        decayed_count = 0
        now = datetime.utcnow()
        stale_threshold = now - timedelta(days=STALE_DAYS_THRESHOLD)

        for fact in facts:
            # Skip identity facts (they don't decay)
            if fact.category == FactCategory.IDENTITY.value:
                continue

            # Check if fact is stale (never accessed or accessed long ago)
            is_stale = (
                fact.last_accessed is None and fact.created_at < stale_threshold
            ) or (
                fact.last_accessed is not None and fact.last_accessed < stale_threshold
            )

            if is_stale and fact.importance > MIN_IMPORTANCE_THRESHOLD:
                new_importance = max(
                    MIN_IMPORTANCE_THRESHOLD,
                    fact.importance - DECAY_PENALTY
                )

                if new_importance < fact.importance:
                    logger.debug(
                        f"[Memory Consolidation] Decay: {fact.fact_key} "
                        f"importance {fact.importance:.2f} → {new_importance:.2f}"
                    )

                    if not dry_run:
                        fact.importance = new_importance

                    decayed_count += 1

        return decayed_count

    def _prune_facts(
        self,
        db: Session,
        conversation_id: str,
        facts: List[ConversationFact],
        dry_run: bool,
    ) -> int:
        """
        Remove low-importance facts when conversation has too many.

        Prioritizes keeping:
        1. Identity facts (never pruned)
        2. Recently accessed facts
        3. High importance facts

        Returns:
            Number of facts pruned
        """
        pruned_count = 0

        # Only prune if over the soft limit
        if len(facts) <= MAX_FACTS_PER_CONVERSATION:
            return 0

        # Calculate how many to remove
        excess = len(facts) - MAX_FACTS_PER_CONVERSATION

        # Identify pruning candidates (low importance, not identity, unused)
        candidates = []
        for fact in facts:
            # Never prune identity facts
            if fact.category == FactCategory.IDENTITY.value:
                continue

            # Score for pruning (lower = more likely to prune)
            prune_score = fact.importance
            if fact.access_count > 0:
                prune_score += 0.2  # Bonus for used facts
            if fact.last_accessed:
                days_since_access = (datetime.utcnow() - fact.last_accessed).days
                if days_since_access < 1:
                    prune_score += 0.3  # Bonus for recently accessed

            candidates.append((fact, prune_score))

        # Sort by prune score ascending (lowest first = most likely to prune)
        candidates.sort(key=lambda x: x[1])

        # Prune the lowest scoring facts
        for fact, score in candidates[:excess]:
            logger.debug(
                f"[Memory Consolidation] Pruning: {fact.fact_key}={fact.fact_value[:30]} "
                f"(importance={fact.importance:.2f}, accessed={fact.access_count})"
            )

            if not dry_run:
                db.delete(fact)

            pruned_count += 1

        return pruned_count

    def consolidate_all_stale(
        self,
        db: Session,
        stale_hours: int = 24,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """
        Consolidate all conversations that haven't been active recently.

        Useful for scheduled cleanup tasks.

        Args:
            db: Database session
            stale_hours: Hours since last message to consider stale
            dry_run: If True, don't commit changes

        Returns:
            Aggregate stats for all consolidated conversations
        """
        from app.models.conversation import Conversation

        stale_threshold = datetime.utcnow() - timedelta(hours=stale_hours)

        # Find conversations with facts that are stale
        stale_conversations = (
            db.query(ConversationFact.conversation_id)
            .distinct()
            .join(Conversation)
            .filter(
                Conversation.last_message_at < stale_threshold,
                Conversation.last_message_at.isnot(None),
            )
            .all()
        )

        total_stats = {
            "conversations": 0,
            "merged": 0,
            "decayed": 0,
            "pruned": 0,
        }

        for (conversation_id,) in stale_conversations:
            stats = self.consolidate_conversation(db, str(conversation_id), dry_run)
            total_stats["conversations"] += 1
            total_stats["merged"] += stats["merged"]
            total_stats["decayed"] += stats["decayed"]
            total_stats["pruned"] += stats["pruned"]

        logger.info(
            f"[Memory Consolidation] Completed batch: "
            f"{total_stats['conversations']} conversations, "
            f"merged={total_stats['merged']}, decayed={total_stats['decayed']}, "
            f"pruned={total_stats['pruned']}"
        )

        return total_stats


# Global service instance
memory_consolidation_service = MemoryConsolidationService()
