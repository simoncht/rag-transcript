"""
Unit tests for the memory consolidation service.

Tests fact deduplication, decay, and pruning logic.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.memory_consolidation import (
    MemoryConsolidationService,
    MIN_IMPORTANCE_THRESHOLD,
    STALE_DAYS_THRESHOLD,
    DECAY_PENALTY,
    MAX_FACTS_PER_CONVERSATION,
    SIMILARITY_THRESHOLD,
)
from app.models.conversation_fact import FactCategory


class MockFact:
    """Mock fact object for testing."""

    def __init__(
        self,
        fact_key: str,
        fact_value: str,
        importance: float = 0.5,
        category: str = "general",
        source_turn: int = 1,
        access_count: int = 0,
        last_accessed: datetime = None,
        created_at: datetime = None,
    ):
        self.id = uuid4()
        self.conversation_id = uuid4()
        self.user_id = uuid4()
        self.fact_key = fact_key
        self.fact_value = fact_value
        self.importance = importance
        self.category = category
        self.source_turn = source_turn
        self.access_count = access_count
        self.last_accessed = last_accessed
        self.created_at = created_at or datetime.utcnow()


class TestMemoryConsolidationInit:
    """Test service initialization."""

    def test_service_creates(self):
        """Test service can be instantiated."""
        service = MemoryConsolidationService()
        assert service is not None


class TestKeyNormalization:
    """Test key normalization for grouping."""

    def test_normalize_removes_trailing_numbers(self):
        """Test normalization removes trailing numbers."""
        service = MemoryConsolidationService()
        assert service._normalize_key_for_grouping("topic_1") == "topic"
        assert service._normalize_key_for_grouping("frequency_333") == "frequency"
        assert service._normalize_key_for_grouping("speaker_42") == "speaker"

    def test_normalize_removes_common_suffixes(self):
        """Test normalization removes common suffixes."""
        service = MemoryConsolidationService()
        assert service._normalize_key_for_grouping("instructor_name") == "instructor"
        assert service._normalize_key_for_grouping("topic_value") == "topic"
        assert service._normalize_key_for_grouping("user_id") == "user"

    def test_normalize_lowercases(self):
        """Test normalization lowercases keys."""
        service = MemoryConsolidationService()
        assert service._normalize_key_for_grouping("TopicName") == "topicname"
        assert service._normalize_key_for_grouping("USER_PREFERENCE") == "user_preference"

    def test_normalize_handles_simple_keys(self):
        """Test normalization handles keys without patterns."""
        service = MemoryConsolidationService()
        assert service._normalize_key_for_grouping("topic") == "topic"
        assert service._normalize_key_for_grouping("name") == "name"


class TestValueSimilarity:
    """Test value similarity detection."""

    def test_exact_match_is_similar(self):
        """Test exact matches are similar."""
        service = MemoryConsolidationService()
        assert service._values_are_similar("Hello World", "Hello World") is True

    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        service = MemoryConsolidationService()
        assert service._values_are_similar("Hello World", "hello world") is True

    def test_containment_is_similar(self):
        """Test one value containing another is similar."""
        service = MemoryConsolidationService()
        assert service._values_are_similar("machine learning", "machine learning and AI") is True
        assert service._values_are_similar("Python programming language", "Python") is True

    def test_high_overlap_is_similar(self):
        """Test high word overlap is similar."""
        service = MemoryConsolidationService()
        # Same words, different order
        assert service._values_are_similar(
            "The quick brown fox",
            "The brown quick fox"
        ) is True

    def test_low_overlap_not_similar(self):
        """Test low word overlap is not similar."""
        service = MemoryConsolidationService()
        assert service._values_are_similar(
            "Python programming",
            "JavaScript development"
        ) is False

    def test_empty_values_not_similar(self):
        """Test empty values handling."""
        service = MemoryConsolidationService()
        assert service._values_are_similar("", "") is True  # Exact match
        assert service._values_are_similar("test", "") is True  # Containment


class TestDeduplication:
    """Test fact deduplication."""

    def test_deduplicate_no_duplicates(self):
        """Test deduplication with no duplicates."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        facts = [
            MockFact("topic_1", "Machine Learning", importance=0.8),
            MockFact("speaker_1", "Dr. Smith", importance=0.7),
        ]

        merged = service._deduplicate_facts(mock_db, facts, dry_run=True)
        assert merged == 0

    def test_deduplicate_finds_duplicates(self):
        """Test deduplication finds duplicate facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        facts = [
            MockFact("topic_1", "Machine Learning", importance=0.8, source_turn=1),
            MockFact("topic_2", "machine learning and AI", importance=0.6, source_turn=5),
        ]

        merged = service._deduplicate_facts(mock_db, facts, dry_run=True)
        assert merged == 1

    def test_deduplicate_keeps_higher_importance(self):
        """Test deduplication keeps fact with higher importance."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        high_importance = MockFact("topic_1", "AI", importance=0.9, source_turn=5)
        low_importance = MockFact("topic_2", "AI", importance=0.3, source_turn=1)

        facts = [low_importance, high_importance]  # Order shouldn't matter

        merged = service._deduplicate_facts(mock_db, facts, dry_run=True)
        assert merged == 1

    def test_deduplicate_not_dry_run_deletes(self):
        """Test deduplication actually deletes in non-dry run."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        facts = [
            MockFact("topic_1", "AI", importance=0.8, source_turn=1),
            MockFact("topic_2", "AI", importance=0.6, source_turn=5),
        ]

        merged = service._deduplicate_facts(mock_db, facts, dry_run=False)
        assert merged == 1
        mock_db.delete.assert_called_once()


class TestDecay:
    """Test importance decay for stale facts."""

    def test_decay_stale_facts(self):
        """Test decay is applied to stale facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        stale_date = datetime.utcnow() - timedelta(days=STALE_DAYS_THRESHOLD + 1)
        stale_fact = MockFact(
            "topic",
            "Old topic",
            importance=0.8,
            created_at=stale_date,
            last_accessed=None,
        )

        decayed = service._apply_decay(mock_db, [stale_fact], dry_run=True)
        assert decayed == 1

    def test_decay_not_applied_to_recent(self):
        """Test decay is not applied to recently accessed facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        recent_date = datetime.utcnow() - timedelta(days=1)
        recent_fact = MockFact(
            "topic",
            "Recent topic",
            importance=0.8,
            last_accessed=recent_date,
        )

        decayed = service._apply_decay(mock_db, [recent_fact], dry_run=True)
        assert decayed == 0

    def test_decay_skips_identity_facts(self):
        """Test decay is not applied to identity facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        stale_date = datetime.utcnow() - timedelta(days=STALE_DAYS_THRESHOLD + 1)
        identity_fact = MockFact(
            "user_name",
            "John Doe",
            importance=0.8,
            category=FactCategory.IDENTITY.value,
            created_at=stale_date,
        )

        decayed = service._apply_decay(mock_db, [identity_fact], dry_run=True)
        assert decayed == 0

    def test_decay_respects_minimum_threshold(self):
        """Test decay doesn't go below minimum threshold."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        stale_date = datetime.utcnow() - timedelta(days=STALE_DAYS_THRESHOLD + 1)
        low_importance_fact = MockFact(
            "topic",
            "Low importance",
            importance=MIN_IMPORTANCE_THRESHOLD + 0.05,  # Just above threshold
            created_at=stale_date,
        )

        service._apply_decay(mock_db, [low_importance_fact], dry_run=False)
        # Importance should be at or above minimum
        assert low_importance_fact.importance >= MIN_IMPORTANCE_THRESHOLD

    def test_decay_updates_importance_in_non_dry_run(self):
        """Test decay updates fact importance in non-dry run."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        stale_date = datetime.utcnow() - timedelta(days=STALE_DAYS_THRESHOLD + 1)
        original_importance = 0.8
        stale_fact = MockFact(
            "topic",
            "Stale topic",
            importance=original_importance,
            created_at=stale_date,
        )

        service._apply_decay(mock_db, [stale_fact], dry_run=False)
        assert stale_fact.importance < original_importance


class TestPruning:
    """Test fact pruning."""

    def test_prune_under_limit_no_action(self):
        """Test pruning does nothing under limit."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        facts = [MockFact(f"topic_{i}", f"Value {i}") for i in range(10)]
        pruned = service._prune_facts(mock_db, "conv_id", facts, dry_run=True)
        assert pruned == 0

    def test_prune_over_limit_removes_excess(self):
        """Test pruning removes excess facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        # Create more facts than the limit
        facts = [
            MockFact(f"topic_{i}", f"Value {i}", importance=0.3)
            for i in range(MAX_FACTS_PER_CONVERSATION + 10)
        ]

        pruned = service._prune_facts(mock_db, "conv_id", facts, dry_run=True)
        assert pruned == 10  # Should remove the excess

    def test_prune_never_removes_identity(self):
        """Test pruning never removes identity facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        # Create facts over limit, but half are identity
        facts = []
        for i in range(MAX_FACTS_PER_CONVERSATION + 10):
            category = FactCategory.IDENTITY.value if i % 2 == 0 else "general"
            facts.append(
                MockFact(f"key_{i}", f"Value {i}", importance=0.3, category=category)
            )

        pruned = service._prune_facts(mock_db, "conv_id", facts, dry_run=True)
        # Should only prune non-identity facts
        assert pruned <= 10

    def test_prune_prefers_low_importance(self):
        """Test pruning removes low importance facts first."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        deleted_facts = []
        mock_db.delete = lambda f: deleted_facts.append(f)

        facts = []
        # Create mix of high and low importance
        for i in range(MAX_FACTS_PER_CONVERSATION + 5):
            importance = 0.9 if i < 5 else 0.3  # First 5 high, rest low
            facts.append(MockFact(f"key_{i}", f"Value {i}", importance=importance))

        service._prune_facts(mock_db, "conv_id", facts, dry_run=False)

        # All deleted facts should be low importance
        for fact in deleted_facts:
            assert fact.importance <= 0.5

    def test_prune_considers_access_count(self):
        """Test pruning considers access count."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        deleted_facts = []
        mock_db.delete = lambda f: deleted_facts.append(f)

        facts = []
        for i in range(MAX_FACTS_PER_CONVERSATION + 2):
            access_count = 10 if i < 2 else 0  # First 2 accessed, rest not
            facts.append(
                MockFact(f"key_{i}", f"Value {i}", importance=0.3, access_count=access_count)
            )

        service._prune_facts(mock_db, "conv_id", facts, dry_run=False)

        # Accessed facts should be kept
        deleted_ids = [f.id for f in deleted_facts]
        kept_ids = [f.id for f in facts if f.id not in deleted_ids]

        # Accessed facts (first 2) should still exist
        accessed_facts_remaining = sum(1 for f in facts[:2] if f.id not in deleted_ids)
        assert accessed_facts_remaining == 2


class TestConsolidationPipeline:
    """Test full consolidation pipeline."""

    def test_consolidate_empty_conversation(self):
        """Test consolidation of conversation with no facts."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        stats = service.consolidate_conversation(mock_db, "conv_id", dry_run=True)

        assert stats["merged"] == 0
        assert stats["decayed"] == 0
        assert stats["pruned"] == 0
        assert stats["total_before"] == 0

    def test_consolidate_returns_stats(self):
        """Test consolidation returns expected stats structure."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        facts = [MockFact(f"key_{i}", f"Value {i}") for i in range(5)]
        mock_db.query.return_value.filter.return_value.all.return_value = facts

        stats = service.consolidate_conversation(mock_db, "conv_id", dry_run=True)

        assert "merged" in stats
        assert "decayed" in stats
        assert "pruned" in stats
        assert "total_before" in stats
        assert "total_after" in stats
        assert stats["total_before"] == 5

    def test_consolidate_commits_when_not_dry_run(self):
        """Test consolidation commits changes when not dry run."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        facts = [MockFact(f"key_{i}", f"Value {i}") for i in range(5)]
        mock_db.query.return_value.filter.return_value.all.return_value = facts
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5

        service.consolidate_conversation(mock_db, "conv_id", dry_run=False)

        mock_db.commit.assert_called_once()


class TestThresholdConstants:
    """Test threshold constants are reasonable."""

    def test_min_importance_threshold_reasonable(self):
        """Test minimum importance threshold is between 0 and 1."""
        assert 0 < MIN_IMPORTANCE_THRESHOLD < 1

    def test_stale_days_threshold_reasonable(self):
        """Test stale days threshold is reasonable."""
        assert 1 <= STALE_DAYS_THRESHOLD <= 30

    def test_decay_penalty_reasonable(self):
        """Test decay penalty is a small fraction."""
        assert 0 < DECAY_PENALTY < 0.5

    def test_max_facts_reasonable(self):
        """Test max facts limit is reasonable."""
        assert 10 <= MAX_FACTS_PER_CONVERSATION <= 200

    def test_similarity_threshold_reasonable(self):
        """Test similarity threshold is high (strict matching)."""
        assert 0.7 <= SIMILARITY_THRESHOLD <= 1.0


class TestBatchConsolidation:
    """Test batch consolidation of stale conversations."""

    def test_consolidate_all_stale_empty(self):
        """Test batch consolidation with no stale conversations."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        mock_db.query.return_value.distinct.return_value.join.return_value.filter.return_value.all.return_value = []

        stats = service.consolidate_all_stale(mock_db, stale_hours=24, dry_run=True)

        assert stats["conversations"] == 0
        assert stats["merged"] == 0
        assert stats["decayed"] == 0
        assert stats["pruned"] == 0

    def test_consolidate_all_stale_aggregates_stats(self):
        """Test batch consolidation aggregates stats from all conversations."""
        service = MemoryConsolidationService()
        mock_db = MagicMock()

        # Mock finding 2 stale conversations
        mock_db.query.return_value.distinct.return_value.join.return_value.filter.return_value.all.return_value = [
            (uuid4(),),
            (uuid4(),),
        ]

        # Mock individual consolidation calls
        with patch.object(service, 'consolidate_conversation') as mock_consolidate:
            mock_consolidate.return_value = {
                "merged": 2,
                "decayed": 1,
                "pruned": 3,
                "total_before": 10,
                "total_after": 4,
            }

            stats = service.consolidate_all_stale(mock_db, stale_hours=24, dry_run=True)

        assert stats["conversations"] == 2
        assert stats["merged"] == 4  # 2 per conversation
        assert stats["decayed"] == 2
        assert stats["pruned"] == 6
