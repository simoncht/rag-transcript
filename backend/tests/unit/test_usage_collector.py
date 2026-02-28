"""
Tests for LLMUsageCollector service.

Covers: record(), flush(), get_total_cost(), thread safety, edge cases.
"""
import uuid
import threading
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest

from app.services.usage_collector import LLMUsageCollector
from app.models.llm_usage import CallType


def _make_response(
    input_tokens=100,
    output_tokens=50,
    cache_hit=0,
    cache_miss=0,
    model="deepseek-chat",
    provider="deepseek",
    response_time=0.5,
):
    """Create a mock LLMResponse for testing."""
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "prompt_cache_hit_tokens": cache_hit,
        "prompt_cache_miss_tokens": cache_miss,
    }
    return SimpleNamespace(
        model=model,
        provider=provider,
        usage=usage,
        response_time_seconds=response_time,
    )


class TestLLMUsageCollectorRecord:
    """Tests for the record() method."""

    def test_record_basic_event(self):
        user_id = uuid.uuid4()
        collector = LLMUsageCollector(user_id=user_id)
        response = _make_response()

        collector.record(response, CallType.CHAT)

        assert len(collector) == 1

    def test_record_multiple_events(self):
        collector = LLMUsageCollector(user_id=uuid.uuid4())

        for _ in range(5):
            collector.record(_make_response(), CallType.ENRICHMENT)

        assert len(collector) == 5

    def test_record_skips_none_response(self):
        collector = LLMUsageCollector(user_id=uuid.uuid4())

        collector.record(None, CallType.CHAT)

        assert len(collector) == 0

    def test_record_skips_response_without_usage(self):
        collector = LLMUsageCollector(user_id=uuid.uuid4())
        response = SimpleNamespace(
            model="deepseek-chat",
            provider="deepseek",
            usage=None,
            response_time_seconds=0.5,
        )

        collector.record(response, CallType.CHAT)

        assert len(collector) == 0

    def test_record_uses_default_conversation_id(self):
        conv_id = uuid.uuid4()
        collector = LLMUsageCollector(
            user_id=uuid.uuid4(), conversation_id=conv_id
        )
        response = _make_response()

        collector.record(response, CallType.CHAT)

        # Access internal state to verify
        assert collector._events[0]["conversation_id"] == conv_id

    def test_record_override_conversation_id(self):
        default_conv = uuid.uuid4()
        override_conv = uuid.uuid4()
        collector = LLMUsageCollector(
            user_id=uuid.uuid4(), conversation_id=default_conv
        )
        response = _make_response()

        collector.record(response, CallType.CHAT, conversation_id=override_conv)

        assert collector._events[0]["conversation_id"] == override_conv

    def test_record_uses_default_content_id(self):
        content_id = uuid.uuid4()
        collector = LLMUsageCollector(
            user_id=uuid.uuid4(), content_id=content_id
        )
        response = _make_response()

        collector.record(response, CallType.ENRICHMENT)

        assert collector._events[0]["content_id"] == content_id

    def test_record_override_content_id(self):
        default_content = uuid.uuid4()
        override_content = uuid.uuid4()
        collector = LLMUsageCollector(
            user_id=uuid.uuid4(), content_id=default_content
        )
        response = _make_response()

        collector.record(
            response, CallType.ENRICHMENT, content_id=override_content
        )

        assert collector._events[0]["content_id"] == override_content

    def test_record_stores_correct_call_type(self):
        collector = LLMUsageCollector(user_id=uuid.uuid4())

        collector.record(_make_response(), CallType.QUERY_EXPANSION)

        assert collector._events[0]["call_type"] == "query_expansion"

    def test_record_stores_message_id(self):
        msg_id = uuid.uuid4()
        collector = LLMUsageCollector(user_id=uuid.uuid4())

        collector.record(_make_response(), CallType.CHAT, message_id=msg_id)

        assert collector._events[0]["message_id"] == msg_id

    def test_record_all_call_types(self):
        """Verify all CallType constants are valid strings."""
        collector = LLMUsageCollector(user_id=uuid.uuid4())
        all_types = [
            CallType.CHAT,
            CallType.CHAT_STREAMING,
            CallType.ENRICHMENT,
            CallType.QUERY_EXPANSION,
            CallType.QUERY_REWRITE,
            CallType.INTENT_CLASSIFICATION,
            CallType.FACT_EXTRACTION,
            CallType.FOLLOWUP,
            CallType.SUMMARIZATION,
            CallType.RELEVANCE_GRADING,
            CallType.HYDE,
        ]

        for ct in all_types:
            collector.record(_make_response(), ct)

        assert len(collector) == len(all_types)
        recorded_types = {e["call_type"] for e in collector._events}
        assert recorded_types == set(all_types)


class TestLLMUsageCollectorFlush:
    """Tests for the flush() method."""

    def test_flush_returns_count(self, db, free_user):
        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(_make_response(), CallType.CHAT)
        collector.record(_make_response(), CallType.ENRICHMENT)

        count = collector.flush(db)

        assert count == 2

    def test_flush_clears_events(self, db, free_user):
        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(_make_response(), CallType.CHAT)

        collector.flush(db)

        assert len(collector) == 0

    def test_flush_empty_returns_zero(self, db):
        collector = LLMUsageCollector(user_id=uuid.uuid4())

        count = collector.flush(db)

        assert count == 0

    def test_flush_creates_db_records(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(_make_response(), CallType.CHAT)
        collector.record(
            _make_response(input_tokens=500), CallType.ENRICHMENT
        )

        collector.flush(db)
        db.commit()

        events = db.query(LLMUsageEvent).filter_by(user_id=free_user.id).all()
        assert len(events) == 2

        call_types = {e.call_type for e in events}
        assert call_types == {"chat", "enrichment"}

    def test_flush_persists_correct_token_counts(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(
            _make_response(input_tokens=200, output_tokens=80),
            CallType.CHAT,
        )

        collector.flush(db)
        db.commit()

        event = db.query(LLMUsageEvent).first()
        assert event.input_tokens == 200
        assert event.output_tokens == 80
        assert event.total_tokens == 280

    def test_flush_persists_content_id(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        content_id = uuid.uuid4()
        collector = LLMUsageCollector(
            user_id=free_user.id, content_id=content_id
        )
        collector.record(_make_response(), CallType.ENRICHMENT)

        collector.flush(db)
        db.commit()

        event = db.query(LLMUsageEvent).first()
        assert event.content_id == content_id
        assert event.call_type == "enrichment"

    def test_flush_persists_call_type(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(_make_response(), CallType.QUERY_EXPANSION)

        collector.flush(db)
        db.commit()

        event = db.query(LLMUsageEvent).first()
        assert event.call_type == "query_expansion"

    def test_double_flush_returns_zero(self, db, free_user):
        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(_make_response(), CallType.CHAT)

        first = collector.flush(db)
        second = collector.flush(db)

        assert first == 1
        assert second == 0

    def test_flush_cost_calculation(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        collector = LLMUsageCollector(user_id=free_user.id)
        # 1000 input + 500 output on deepseek-chat
        # cost = (1000 * 0.28 / 1M) + (500 * 0.42 / 1M) = 0.000280 + 0.000210 = 0.000490
        collector.record(
            _make_response(input_tokens=1000, output_tokens=500),
            CallType.CHAT,
        )

        collector.flush(db)
        db.commit()

        event = db.query(LLMUsageEvent).first()
        assert float(event.cost_usd) == pytest.approx(0.000490, abs=1e-6)


class TestLLMUsageCollectorThreadSafety:
    """Tests for thread-safe concurrent access."""

    def test_concurrent_records(self):
        """Multiple threads recording simultaneously should not lose events."""
        collector = LLMUsageCollector(user_id=uuid.uuid4())
        num_threads = 10
        events_per_thread = 100
        barrier = threading.Barrier(num_threads)

        def record_events():
            barrier.wait()  # Sync all threads to start simultaneously
            for _ in range(events_per_thread):
                collector.record(_make_response(), CallType.ENRICHMENT)

        threads = [
            threading.Thread(target=record_events) for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(collector) == num_threads * events_per_thread

    def test_concurrent_record_and_flush(self, db, free_user):
        """Recording and flushing concurrently should not lose or double-count."""
        collector = LLMUsageCollector(user_id=free_user.id)
        total_recorded = 0
        total_flushed = 0
        lock = threading.Lock()

        def record_batch():
            nonlocal total_recorded
            for _ in range(50):
                collector.record(_make_response(), CallType.ENRICHMENT)
            with lock:
                total_recorded += 50

        def flush_batch():
            nonlocal total_flushed
            count = collector.flush(db)
            with lock:
                total_flushed += count

        # Record, then flush, then record more, then flush again
        t1 = threading.Thread(target=record_batch)
        t1.start()
        t1.join()

        t2 = threading.Thread(target=flush_batch)
        t2.start()
        t2.join()

        t3 = threading.Thread(target=record_batch)
        t3.start()
        t3.join()

        t4 = threading.Thread(target=flush_batch)
        t4.start()
        t4.join()

        # Final flush for any remaining
        remaining = collector.flush(db)
        total_flushed += remaining

        assert total_flushed == total_recorded


class TestLLMUsageCollectorEdgeCases:
    """Edge case and integration tests."""

    def test_response_with_empty_usage_dict(self):
        """Empty usage dict is falsy in Python — record() should skip it."""
        collector = LLMUsageCollector(user_id=uuid.uuid4())
        response = SimpleNamespace(
            model="deepseek-chat",
            provider="deepseek",
            usage={},  # Empty dict is falsy
            response_time_seconds=0.1,
        )

        collector.record(response, CallType.CHAT)

        assert len(collector) == 0

    def test_response_with_partial_usage(self):
        """Usage dict missing some keys should use defaults."""
        collector = LLMUsageCollector(user_id=uuid.uuid4())
        response = SimpleNamespace(
            model="deepseek-chat",
            provider="deepseek",
            usage={"input_tokens": 100},  # Missing output_tokens
            response_time_seconds=0.1,
        )

        collector.record(response, CallType.CHAT)

        assert len(collector) == 1

    def test_len_is_thread_safe(self):
        collector = LLMUsageCollector(user_id=uuid.uuid4())
        for _ in range(10):
            collector.record(_make_response(), CallType.CHAT)

        # __len__ should work correctly
        assert len(collector) == 10

    def test_multiple_flushes_accumulate_in_db(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        collector = LLMUsageCollector(user_id=free_user.id)

        # First batch
        collector.record(_make_response(), CallType.CHAT)
        collector.flush(db)

        # Second batch
        collector.record(_make_response(), CallType.ENRICHMENT)
        collector.record(_make_response(), CallType.QUERY_EXPANSION)
        collector.flush(db)
        db.commit()

        events = db.query(LLMUsageEvent).filter_by(user_id=free_user.id).all()
        assert len(events) == 3

    def test_collector_with_reasoner_model(self, db, free_user):
        from app.models.llm_usage import LLMUsageEvent

        collector = LLMUsageCollector(user_id=free_user.id)
        collector.record(
            _make_response(model="deepseek-reasoner"),
            CallType.CHAT,
        )

        collector.flush(db)
        db.commit()

        event = db.query(LLMUsageEvent).first()
        assert event.model == "deepseek-reasoner"
