"""
Celery tasks for conversation memory (fact extraction).

Moves fact extraction out of the request/response cycle so chat messages
return faster. The LLM call for extraction (~1-2s) now happens in the
background worker instead of blocking the user.
"""
import logging

from app.core.celery_app import celery_app
from app.db.base import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=30,
    time_limit=60,
)
def extract_facts_from_turn(
    self,
    conversation_id: str,
    message_id: str,
    user_query: str,
):
    """
    Extract facts from a conversation turn in the background.

    Args:
        conversation_id: Conversation UUID
        message_id: Assistant message UUID (the response to extract from)
        user_query: The user's query that prompted the response
    """
    db = SessionLocal()

    try:
        from app.models.conversation import Conversation
        from app.models.message import Message
        from app.services.fact_extraction import FactExtractionService

        # Load conversation and message
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if not conversation:
            logger.warning(
                f"[FactTask] Conversation {conversation_id} not found, skipping"
            )
            return {"status": "skipped", "reason": "conversation_not_found"}

        message = (
            db.query(Message)
            .filter(Message.id == message_id)
            .first()
        )
        if not message:
            logger.warning(
                f"[FactTask] Message {message_id} not found, skipping"
            )
            return {"status": "skipped", "reason": "message_not_found"}

        # Extract facts (no usage_collector in background — tracked separately)
        fact_service = FactExtractionService()
        extracted_facts = fact_service.extract_facts(
            db=db,
            message=message,
            conversation=conversation,
            user_query=user_query,
        )

        # Save facts to database
        for fact in extracted_facts:
            db.add(fact)

        if extracted_facts:
            db.commit()
            logger.info(
                f"[FactTask] Saved {len(extracted_facts)} facts for "
                f"conversation {conversation_id}"
            )

        # MEM-003: Inline consolidation when fact count exceeds threshold
        from app.models.conversation_fact import ConversationFact
        from sqlalchemy import func

        fact_count = (
            db.query(func.count(ConversationFact.id))
            .filter(ConversationFact.conversation_id == conversation_id)
            .scalar()
        )

        if fact_count > 50:  # MAX_FACTS_PER_CONVERSATION
            from app.services.memory_consolidation import memory_consolidation_service

            logger.info(
                f"[FactTask] Fact count ({fact_count}) exceeds threshold, "
                f"running inline consolidation for {conversation_id}"
            )
            consolidation_stats = memory_consolidation_service.consolidate_conversation(
                db, conversation_id
            )
            logger.info(
                f"[FactTask] Inline consolidation complete: {consolidation_stats}"
            )

        return {
            "status": "ok",
            "facts_extracted": len(extracted_facts),
            "conversation_id": conversation_id,
        }

    except Exception as e:
        logger.warning(f"[FactTask] Fact extraction failed: {e}")
        db.rollback()
        # Retry on transient failures (LLM timeout, DB connection)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(
                f"[FactTask] Max retries exceeded for conversation "
                f"{conversation_id}: {e}"
            )
            return {"status": "failed", "error": str(e)}
    finally:
        db.close()
