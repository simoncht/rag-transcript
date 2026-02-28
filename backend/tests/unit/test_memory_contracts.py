"""
Tests for memory behavioral contracts.

Validates contracts defined in .claude/references/behavioral-contracts.md:
- MEM-001: No memory dead zone
- MEM-002: Identity facts survive consolidation
- MEM-003: Consolidation respects max limit
- MEM-004: Fact scoring prioritizes early identity facts
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# Import all models so Base.metadata has all tables for SQLite creation
import app.models  # noqa: F401


# ── MEM-001: No Memory Dead Zone ─────────────────────────────────────


class TestMemoryDeadZone:
    """MEM-001: Fact extraction must cover turns before they leave history window."""

    def test_history_limit_and_fact_threshold_constants(self):
        """Extract history limit and fact threshold, assert no dead zone gap.

        History limit: how many recent messages are loaded (.limit(N))
        Fact threshold: minimum messages before fact extraction triggers (>= M)

        Dead zone exists if threshold > limit (turns limit+1 through threshold-1 are lost).
        """
        import os
        import re

        # Support both local and Docker paths
        candidates = [
            "backend/app/api/routes/conversations.py",
            "app/api/routes/conversations.py",
        ]
        filepath = None
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break
        assert filepath, f"conversations.py not found in {candidates}"

        with open(filepath, "r") as f:
            content = f.read()

        # Find fact extraction threshold: message_count >= N
        threshold_matches = re.findall(r"message_count\s*>=\s*(\d+)", content)
        assert threshold_matches, "Could not find fact extraction threshold in conversations.py"
        fact_threshold = int(threshold_matches[0])

        # Find history limit: .limit(N) near message history query
        # Look for .limit() calls — the one on line ~1242 is the history query
        limit_matches = re.findall(r"\.limit\((\d+)\)", content)
        assert limit_matches, "Could not find .limit() in conversations.py"

        # The history limit is typically a small number (10-20)
        history_limits = [int(m) for m in limit_matches if int(m) <= 50]
        assert history_limits, "No reasonable history limit found"

        # Document the gap for visibility
        min_history_limit = min(history_limits)

        # The contract: injection threshold should be <= history_limit to ensure
        # facts are available in prompt as soon as they could be lost from history.
        # Note: facts are extracted unconditionally on every turn — the threshold
        # only gates when facts are INJECTED into the LLM prompt.
        assert fact_threshold <= min_history_limit, (
            f"MEM-001 BROKEN: Fact injection threshold ({fact_threshold}) > history limit "
            f"({min_history_limit}). Facts extracted from turns {min_history_limit + 1}-"
            f"{fact_threshold - 1} exist in DB but won't be injected into the prompt."
        )

    def test_fact_threshold_is_reasonable(self):
        """Fact threshold should not be so high that many turns are missed."""
        import os
        import re

        candidates = [
            "backend/app/api/routes/conversations.py",
            "app/api/routes/conversations.py",
        ]
        filepath = None
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break
        assert filepath, f"conversations.py not found in {candidates}"

        with open(filepath, "r") as f:
            content = f.read()

        threshold_matches = re.findall(r"message_count\s*>=\s*(\d+)", content)
        assert threshold_matches, "Could not find fact extraction threshold"
        fact_threshold = int(threshold_matches[0])

        # Threshold should be reasonable (not > 50)
        assert fact_threshold <= 50, (
            f"Fact threshold {fact_threshold} is unreasonably high — "
            f"facts won't be extracted until very late in conversations"
        )


# ── MEM-002: Identity Facts Survive Consolidation ─────────────────────


class TestIdentityFactSurvival:
    """MEM-002: Identity facts must survive consolidation indefinitely."""

    def test_identity_facts_skip_decay(self, db, free_user):
        """Identity facts should not have decay applied during consolidation."""
        from app.models.conversation import Conversation
        from app.models.conversation_fact import ConversationFact, FactCategory
        from app.services.memory_consolidation import MemoryConsolidationService

        # Create conversation
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=free_user.id,
            title="Test",
            message_count=30,
            selected_video_ids=[],
        )
        db.add(conv)
        db.commit()

        # Create an identity fact from turn 1 (old, but identity)
        identity_fact = ConversationFact(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            user_id=free_user.id,
            fact_key="user_name",
            fact_value="Alice",
            source_turn=1,
            importance=0.95,
            category=FactCategory.IDENTITY.value,
            created_at=datetime.utcnow() - timedelta(days=30),
            last_accessed=None,  # Never accessed — worst case for decay
            access_count=0,
        )
        db.add(identity_fact)
        db.commit()

        original_importance = identity_fact.importance

        # Run consolidation
        service = MemoryConsolidationService()
        service.consolidate_conversation(db, str(conv.id))

        # Refresh and verify identity fact was NOT decayed
        db.refresh(identity_fact)
        assert identity_fact.importance == original_importance, (
            f"Identity fact importance changed from {original_importance} to {identity_fact.importance}. "
            f"MEM-002 violated: identity facts must not decay."
        )

    def test_identity_facts_never_pruned(self, db, free_user):
        """Identity facts should never be pruned, even when over MAX_FACTS limit."""
        from app.models.conversation import Conversation
        from app.models.conversation_fact import ConversationFact, FactCategory
        from app.services.memory_consolidation import (
            MAX_FACTS_PER_CONVERSATION,
            MemoryConsolidationService,
        )

        conv = Conversation(
            id=uuid.uuid4(),
            user_id=free_user.id,
            title="Test",
            message_count=100,
            selected_video_ids=[],
        )
        db.add(conv)
        db.commit()

        # Create identity facts
        identity_ids = []
        for i in range(5):
            fact = ConversationFact(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                user_id=free_user.id,
                fact_key=f"identity_{i}",
                fact_value=f"Identity value {i}",
                source_turn=i + 1,
                importance=0.95,
                category=FactCategory.IDENTITY.value,
                created_at=datetime.utcnow() - timedelta(days=30),
            )
            db.add(fact)
            identity_ids.append(fact.id)

        # Fill up to exceed MAX_FACTS with non-identity facts
        for i in range(MAX_FACTS_PER_CONVERSATION + 10):
            fact = ConversationFact(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                user_id=free_user.id,
                fact_key=f"topic_{i}",
                fact_value=f"Some topic fact {i}",
                source_turn=i + 10,
                importance=0.3,
                category=FactCategory.TOPIC.value,
                created_at=datetime.utcnow() - timedelta(days=10),
            )
            db.add(fact)

        db.commit()

        # Run consolidation
        service = MemoryConsolidationService()
        service.consolidate_conversation(db, str(conv.id))

        # Verify ALL identity facts survived
        remaining_identity = (
            db.query(ConversationFact)
            .filter(
                ConversationFact.conversation_id == conv.id,
                ConversationFact.category == FactCategory.IDENTITY.value,
            )
            .all()
        )
        remaining_ids = {f.id for f in remaining_identity}

        for iid in identity_ids:
            assert iid in remaining_ids, (
                f"Identity fact {iid} was pruned during consolidation. "
                f"MEM-002 violated: identity facts must never be pruned."
            )


# ── MEM-003: Consolidation Respects Max Limit ────────────────────────


class TestConsolidationLimit:
    """Consolidation should reduce fact count to MAX_FACTS or below."""

    def test_consolidation_reduces_to_max(self, db, free_user):
        """After consolidation, non-identity fact count should be <= MAX_FACTS."""
        from app.models.conversation import Conversation
        from app.models.conversation_fact import ConversationFact, FactCategory
        from app.services.memory_consolidation import (
            MAX_FACTS_PER_CONVERSATION,
            MemoryConsolidationService,
        )

        conv = Conversation(
            id=uuid.uuid4(),
            user_id=free_user.id,
            title="Test",
            message_count=100,
            selected_video_ids=[],
        )
        db.add(conv)
        db.commit()

        # Create 100 unique low-importance topic facts (well over MAX)
        for i in range(100):
            fact = ConversationFact(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                user_id=free_user.id,
                fact_key=f"unique_topic_{i}",
                fact_value=f"Completely unique value number {i} that is different",
                source_turn=i + 1,
                importance=0.35,
                category=FactCategory.TOPIC.value,
                created_at=datetime.utcnow() - timedelta(days=10),
            )
            db.add(fact)

        db.commit()

        service = MemoryConsolidationService()
        stats = service.consolidate_conversation(db, str(conv.id))

        assert stats["total_after"] <= MAX_FACTS_PER_CONVERSATION, (
            f"Consolidation left {stats['total_after']} facts "
            f"(max is {MAX_FACTS_PER_CONVERSATION}). "
            f"Consolidation did not reduce to limit."
        )


# ── MEM-004: Fact Scoring Prioritizes Early Identity ──────────────────


class TestFactScoringPriority:
    """Identity facts from early turns should score highest."""

    def test_identity_category_has_highest_priority(self):
        """Identity category priority should be 1.0 (highest)."""
        from app.services.memory_scoring import CATEGORY_PRIORITIES
        from app.models.conversation_fact import FactCategory

        identity_priority = CATEGORY_PRIORITIES[FactCategory.IDENTITY.value]
        assert identity_priority == 1.0, (
            f"Identity priority is {identity_priority}, expected 1.0"
        )

        # Verify it's the highest
        for cat, priority in CATEGORY_PRIORITIES.items():
            assert priority <= identity_priority, (
                f"Category {cat} has priority {priority} >= identity {identity_priority}"
            )

    def test_early_turn_identity_scores_higher_than_late_topic(self):
        """An identity fact from turn 1 should score higher than a topic fact from turn 50."""
        from app.services.memory_scoring import calculate_composite_score
        from app.models.conversation_fact import ConversationFact, FactCategory

        # Identity fact from turn 1
        identity_fact = ConversationFact(
            id=uuid.uuid4(),
            fact_key="user_name",
            fact_value="Alice",
            source_turn=1,
            importance=0.95,
            category=FactCategory.IDENTITY.value,
            created_at=datetime.utcnow() - timedelta(hours=48),
            last_accessed=None,
            access_count=0,
            confidence_score=1.0,
            conversation_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        # Topic fact from turn 50 (recent, high importance)
        topic_fact = ConversationFact(
            id=uuid.uuid4(),
            fact_key="main_topic",
            fact_value="Machine learning",
            source_turn=50,
            importance=0.8,
            category=FactCategory.TOPIC.value,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            access_count=3,
            confidence_score=1.0,
            conversation_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        max_turn = 50
        identity_score = calculate_composite_score(identity_fact, max_turn)
        topic_score = calculate_composite_score(topic_fact, max_turn)

        assert identity_score > topic_score, (
            f"Identity fact scored {identity_score:.3f} <= topic fact {topic_score:.3f}. "
            f"Early identity facts should always outrank later topic facts."
        )

    def test_source_turn_priority_early_turns(self):
        """Turns 1-3 should get maximum source turn priority (1.0)."""
        from app.services.memory_scoring import calculate_source_turn_priority

        for turn in [1, 2, 3]:
            priority = calculate_source_turn_priority(turn, max_turn=100)
            assert priority == 1.0, (
                f"Turn {turn} got priority {priority}, expected 1.0"
            )
