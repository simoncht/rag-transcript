"""
LLM Usage Collector - Thread-safe accumulator for LLM usage events.

Services that make LLM calls don't have DB sessions. This collector
accumulates usage events in memory and flushes them in one batch at the
orchestration layer (route handler or Celery task) where a DB session
is available.

Thread-safe via threading.Lock (enrichment uses ThreadPoolExecutor).
"""
import logging
import threading
import uuid
from typing import Optional

from app.models.llm_usage import LLMUsageEvent, CallType, calculate_llm_cost

logger = logging.getLogger(__name__)


class LLMUsageCollector:
    """
    Accumulates LLM usage events in memory for batch DB insert.

    Usage:
        collector = LLMUsageCollector(user_id=user.id)
        # Pass to services...
        collector.record(response, "enrichment", content_id=video.id)
        # At the end, flush to DB:
        count = collector.flush(db)
    """

    def __init__(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        content_id: Optional[uuid.UUID] = None,
    ):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.content_id = content_id
        self._events: list[dict] = []
        self._lock = threading.Lock()

    def record(
        self,
        response,
        call_type: str,
        content_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
    ):
        """
        Record an LLM usage event from an LLMResponse object.

        Args:
            response: LLMResponse from llm_service.complete()
            call_type: One of CallType constants
            content_id: Override default content_id
            conversation_id: Override default conversation_id
            message_id: Optional message ID
        """
        if not response or not response.usage:
            return

        event_data = {
            "user_id": self.user_id,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
            "call_type": call_type,
            "content_id": content_id or self.content_id,
            "conversation_id": conversation_id or self.conversation_id,
            "message_id": message_id,
            "response_time_seconds": response.response_time_seconds,
        }

        with self._lock:
            self._events.append(event_data)

    def flush(self, db) -> int:
        """
        Batch insert all accumulated events into the database.

        Args:
            db: SQLAlchemy Session

        Returns:
            Number of events flushed
        """
        with self._lock:
            events_to_flush = list(self._events)
            self._events.clear()

        if not events_to_flush:
            return 0

        total_cost = 0.0
        for event_data in events_to_flush:
            usage_event = LLMUsageEvent.create_from_response(**event_data)
            db.add(usage_event)
            total_cost += float(usage_event.cost_usd)

        count = len(events_to_flush)
        logger.info(
            f"[LLM Usage] Flushed {count} events, total cost: ${total_cost:.6f}"
        )
        return count

    def get_total_cost(self) -> float:
        """Get total cost of accumulated events (for logging before flush)."""
        with self._lock:
            total = 0.0
            for event_data in self._events:
                usage = event_data["usage"]
                cost = calculate_llm_cost(
                    model=event_data["model"],
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    cache_hit_tokens=usage.get("prompt_cache_hit_tokens", 0),
                    cache_miss_tokens=usage.get("prompt_cache_miss_tokens", 0),
                )
                total += float(cost)
            return total

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
