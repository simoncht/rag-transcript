"""
Fact Extraction Service.

Extracts key facts from conversation messages for long-distance recall.
Enables the system to remember important information from early turns.

Enhanced with multi-factor scoring based on OpenAI/Anthropic memory best practices:
- importance: LLM-rated significance (0.0-1.0)
- category: Fact type for scope separation (identity, topic, preference, session)
"""
import json
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.models.conversation_fact import ConversationFact, FactCategory
from app.models.message import Message
from app.models.conversation import Conversation
from app.services.llm_providers import Message as LLMMessage, LLMService

logger = logging.getLogger(__name__)


# Enhanced prompt with importance scoring and category classification
FACT_EXTRACTION_PROMPT = """Extract key facts from this Q&A pair with importance scoring.

Q: {user_query}
A: {assistant_response}

Return JSON array with importance (0.0-1.0) and category for each fact:
[
  {{"key": "instructor", "value": "Bashar", "importance": 0.95, "category": "identity"}},
  {{"key": "topic", "value": "consciousness expansion", "importance": 0.7, "category": "topic"}},
  {{"key": "frequency", "value": "333 kHz", "importance": 0.6, "category": "topic"}}
]

IMPORTANCE SCORING (critical for memory retrieval):
- 0.9-1.0: Core identity facts (names, roles, relationships) - MOST IMPORTANT
- 0.7-0.9: Key concepts that define the subject matter
- 0.5-0.7: Supporting details and context
- 0.3-0.5: Tangential information
- 0.0-0.3: Ephemeral/session-specific details

CATEGORIES (for scope separation):
- "identity": Names, roles, relationships (e.g., "Bashar is a channeled entity")
- "topic": Core concepts, subjects (e.g., "discusses parallel realities")
- "preference": User preferences, opinions
- "session": Current session context only
- "ephemeral": Single-use facts

EXTRACTION RULES:
- Prioritize identity facts (who/what the source is)
- Extract names (people, entities, organizations)
- Extract key concepts and frameworks
- Use short, descriptive keys (lowercase, underscore-separated)
- Rate importance honestly - not everything is 0.9+
- Return empty array if no significant facts

IMPORTANT: Identity facts should almost always have importance >= 0.85"""


class FactExtractionService:
    """Extract factual claims from conversation messages."""

    def __init__(self):
        """Initialize the fact extraction service."""
        self.llm_service = LLMService()
        self.temperature = 0.2  # Low temperature for consistency
        self.max_tokens = 500  # Enough for JSON response

    def extract_facts(
        self, db: Session, message: Message, conversation: Conversation, user_query: str
    ) -> List[ConversationFact]:
        """
        Extract facts from assistant message.

        Args:
            db: Database session
            message: Assistant message to extract from
            conversation: The conversation context
            user_query: The user's query that prompted this response

        Returns:
            List of ConversationFact objects (not yet committed)
        """
        try:
            # Build extraction prompt
            messages = self._build_extraction_prompt(user_query, message.content)

            # Call LLM
            response = self.llm_service.complete(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                retry=False,  # Handle retries here
            )

            # Parse JSON response
            facts_data = self._parse_facts_response(response.content)

            # Create ConversationFact objects with enhanced scoring
            facts = []
            current_turn = (conversation.message_count + 1) // 2  # Estimate turn number

            for fact_dict in facts_data:
                # Extract importance (default 0.5 if not provided)
                importance = fact_dict.get("importance", 0.5)
                if not isinstance(importance, (int, float)):
                    importance = 0.5
                importance = max(0.0, min(1.0, float(importance)))  # Clamp to [0, 1]

                # Extract category (default to "topic")
                category = fact_dict.get("category", "topic")
                valid_categories = [c.value for c in FactCategory]
                if category not in valid_categories:
                    category = FactCategory.TOPIC.value

                fact = ConversationFact(
                    conversation_id=conversation.id,
                    user_id=conversation.user_id,
                    fact_key=fact_dict["key"],
                    fact_value=fact_dict["value"],
                    source_turn=current_turn,
                    confidence_score=1.0,  # Extraction confidence (separate from importance)
                    importance=importance,
                    category=category,
                )
                facts.append(fact)

            # Deduplicate against existing facts
            facts = self._deduplicate_facts(db, conversation.id, facts)

            logger.info(
                f"Extracted {len(facts)} facts from message in conversation {conversation.id}"
            )

            return facts

        except Exception as e:
            logger.warning(f"Fact extraction failed: {e}")
            # Return empty list on failure (graceful degradation)
            return []

    def _build_extraction_prompt(
        self, user_query: str, assistant_response: str
    ) -> List[LLMMessage]:
        """Create prompt for fact extraction."""
        # Truncate very long responses to save tokens
        if len(assistant_response) > 2000:
            assistant_response = assistant_response[:2000] + "..."

        prompt_content = FACT_EXTRACTION_PROMPT.format(
            user_query=user_query, assistant_response=assistant_response
        )

        return [
            LLMMessage(role="system", content="You are a fact extraction assistant."),
            LLMMessage(role="user", content=prompt_content),
        ]

    def _parse_facts_response(self, response: str) -> List[Dict]:
        """
        Parse LLM JSON response into fact dictionaries.

        Args:
            response: JSON string from LLM

        Returns:
            List of fact dictionaries with 'key', 'value', 'importance', 'category'
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]  # Remove ```json
            if response.startswith("```"):
                response = response[3:]  # Remove ```
            if response.endswith("```"):
                response = response[:-3]  # Remove ```
            response = response.strip()

            facts = json.loads(response)

            # Validate structure
            if not isinstance(facts, list):
                logger.warning(f"Expected list, got {type(facts)}")
                return []

            validated_facts = []
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                if "key" not in fact or "value" not in fact:
                    continue
                if not fact["key"] or not fact["value"]:
                    continue

                # Normalize key (lowercase, underscore-separated)
                fact["key"] = fact["key"].lower().replace(" ", "_").replace("-", "_")

                # Validate importance if provided
                if "importance" in fact:
                    try:
                        fact["importance"] = float(fact["importance"])
                    except (ValueError, TypeError):
                        fact["importance"] = 0.5

                # Validate category if provided
                if "category" in fact:
                    valid_categories = [c.value for c in FactCategory]
                    if fact["category"] not in valid_categories:
                        # Infer category from key patterns
                        fact["category"] = self._infer_category(fact["key"])
                else:
                    # Infer category from key patterns
                    fact["category"] = self._infer_category(fact["key"])

                validated_facts.append(fact)

            return validated_facts

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse facts JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error parsing facts response: {e}")
            return []

    def _infer_category(self, fact_key: str) -> str:
        """
        Infer fact category from key patterns.

        Args:
            fact_key: The normalized fact key

        Returns:
            Category string (identity, topic, preference, session, ephemeral)
        """
        identity_patterns = [
            "instructor", "teacher", "speaker", "host", "channeler", "entity",
            "source", "author", "creator", "name", "person", "who", "role"
        ]
        preference_patterns = [
            "preference", "favorite", "likes", "dislikes", "wants", "user_"
        ]
        session_patterns = [
            "current", "today", "now", "this_session", "recent"
        ]

        key_lower = fact_key.lower()

        for pattern in identity_patterns:
            if pattern in key_lower:
                return FactCategory.IDENTITY.value

        for pattern in preference_patterns:
            if pattern in key_lower:
                return FactCategory.PREFERENCE.value

        for pattern in session_patterns:
            if pattern in key_lower:
                return FactCategory.SESSION.value

        return FactCategory.TOPIC.value

    def _deduplicate_facts(
        self, db: Session, conversation_id: str, new_facts: List[ConversationFact]
    ) -> List[ConversationFact]:
        """
        Deduplicate facts against existing conversation facts.

        If a fact with the same key exists, keep the one with higher confidence.
        For simple extraction, we'll just skip duplicates.

        Args:
            db: Database session
            conversation_id: Conversation UUID
            new_facts: List of new facts to add

        Returns:
            List of facts to actually add (deduplicated)
        """
        # First, deduplicate within new_facts (keep first occurrence of each key)
        seen_keys = set()
        deduplicated_new = []
        for fact in new_facts:
            if fact.fact_key not in seen_keys:
                deduplicated_new.append(fact)
                seen_keys.add(fact.fact_key)
            else:
                logger.debug(
                    f"Skipping duplicate fact key within new facts: {fact.fact_key} "
                    f"(value: {fact.fact_value})"
                )

        # Get existing fact keys for this conversation
        existing_facts = (
            db.query(ConversationFact)
            .filter(ConversationFact.conversation_id == conversation_id)
            .all()
        )

        existing_keys = {fact.fact_key: fact for fact in existing_facts}

        # Filter out duplicates against existing facts
        deduplicated = []
        for fact in deduplicated_new:
            if fact.fact_key not in existing_keys:
                deduplicated.append(fact)
            else:
                # Key exists - skip (we could update value here if needed)
                logger.debug(
                    f"Skipping duplicate fact key: {fact.fact_key} "
                    f"(already exists with value: {existing_keys[fact.fact_key].fact_value})"
                )

        return deduplicated


# Global service instance
fact_extraction_service = FactExtractionService()


def backfill_fact_scores(
    db: Session,
    conversation_id: str = None,
    dry_run: bool = False,
    force_rescore: bool = False,
) -> int:
    """
    Backfill importance and category scores for existing facts.

    Uses heuristic patterns to estimate scores for facts created before
    the multi-factor scoring system was implemented.

    Args:
        db: Database session
        conversation_id: Optional - only backfill facts for this conversation
        dry_run: If True, log changes but don't commit
        force_rescore: If True, re-score all facts (not just NULL/default values)

    Returns:
        Number of facts updated
    """
    from sqlalchemy import or_, and_

    # Find facts that need scoring:
    # 1. NULL importance or category
    # 2. Default values from migration (0.5 importance AND 'topic' category)
    if force_rescore:
        query = db.query(ConversationFact)
    else:
        query = db.query(ConversationFact).filter(
            or_(
                ConversationFact.importance.is_(None),
                ConversationFact.category.is_(None),
                # Facts with migration defaults that may be mis-categorized
                and_(
                    ConversationFact.importance == 0.5,
                    ConversationFact.category == FactCategory.TOPIC.value,
                ),
            )
        )

    if conversation_id:
        query = query.filter(ConversationFact.conversation_id == conversation_id)

    facts_to_update = query.all()

    if not facts_to_update:
        logger.info("[Backfill] No facts need backfilling")
        return 0

    logger.info(f"[Backfill] Found {len(facts_to_update)} facts to backfill")

    # Heuristic importance scoring based on key patterns
    identity_keys = {
        "instructor", "teacher", "speaker", "host", "channeler", "entity",
        "source", "author", "creator", "name", "person", "who", "role",
        "bashar", "darryl", "channeled_entity", "alien", "et", "extraterrestrial"
    }

    high_importance_keys = {
        "concept", "framework", "principle", "teaching", "method", "technique",
        "frequency", "vibration", "consciousness", "reality", "permission"
    }

    updated_count = 0

    for fact in facts_to_update:
        key_lower = fact.fact_key.lower()
        value_lower = fact.fact_value.lower() if fact.fact_value else ""

        # Check if it's an identity fact (by key or value patterns)
        is_identity = any(pattern in key_lower for pattern in identity_keys)
        is_identity = is_identity or any(
            pattern in value_lower for pattern in ["bashar", "darryl", "channeler", "entity"]
        )

        # Determine category based on patterns
        new_category = fact.category
        if is_identity:
            new_category = FactCategory.IDENTITY.value
        elif any(p in key_lower for p in ["preference", "favorite", "likes", "user_"]):
            new_category = FactCategory.PREFERENCE.value
        elif any(p in key_lower for p in ["current", "today", "now", "this_session"]):
            new_category = FactCategory.SESSION.value
        elif fact.category is None:
            new_category = FactCategory.TOPIC.value

        # Determine importance based on category and patterns
        new_importance = fact.importance
        if new_category == FactCategory.IDENTITY.value:
            # Identity facts are critical
            new_importance = 0.9
        elif any(pattern in key_lower for pattern in high_importance_keys):
            # Key concepts
            new_importance = 0.75
        elif fact.source_turn and fact.source_turn <= 5:
            # Early facts often establish identity/context
            new_importance = 0.7
        elif new_category == FactCategory.PREFERENCE.value:
            new_importance = 0.6
        elif new_category == FactCategory.SESSION.value:
            new_importance = 0.4
        elif fact.importance is None or fact.importance == 0.5:
            # Keep default for unclassified topics
            new_importance = 0.5

        # Only count as updated if values actually changed
        if fact.category != new_category or fact.importance != new_importance:
            fact.category = new_category
            fact.importance = new_importance
            updated_count += 1

            if dry_run:
                logger.info(
                    f"[Backfill DRY RUN] Would update fact '{fact.fact_key}': "
                    f"importance={new_importance:.2f}, category={new_category}"
                )

    if not dry_run:
        db.commit()
        logger.info(f"[Backfill] Updated {updated_count} facts")
    else:
        db.rollback()
        logger.info(f"[Backfill DRY RUN] Would update {updated_count} facts")

    return updated_count


def backfill_historical_facts(
    db: Session,
    conversation_id: str,
    start_turn: int = 1,
    end_turn: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 10,
) -> dict:
    """
    Extract facts from historical message pairs that were missed.

    This function processes message pairs (user question + assistant response)
    from conversations created before fact extraction was implemented, or for
    turns that were skipped during processing.

    Args:
        db: Database session
        conversation_id: Conversation UUID to backfill
        start_turn: First turn to process (1-indexed, default: 1)
        end_turn: Last turn to process (None = all turns)
        dry_run: If True, log what would be extracted but don't save
        batch_size: Commit after this many turns (to avoid memory issues)

    Returns:
        Dict with stats: turns_processed, facts_extracted, turns_skipped, errors
    """
    from app.models.conversation import Conversation

    logger.info(
        f"[Backfill] Starting historical fact extraction for conversation {conversation_id}"
    )
    logger.info(f"[Backfill] Range: turn {start_turn} to {end_turn or 'end'}, dry_run={dry_run}")

    # Get conversation
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conversation:
        logger.error(f"[Backfill] Conversation {conversation_id} not found")
        return {
            "turns_processed": 0,
            "facts_extracted": 0,
            "turns_skipped": 0,
            "errors": ["Conversation not found"],
        }

    # Get all messages ordered by created_at ascending
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    logger.info(f"[Backfill] Found {len(messages)} total messages")

    # Get existing fact turns to avoid duplicates
    existing_turns = set(
        row[0]
        for row in db.query(ConversationFact.source_turn)
        .filter(ConversationFact.conversation_id == conversation_id)
        .distinct()
        .all()
    )
    logger.info(f"[Backfill] Existing facts at turns: {sorted(existing_turns)}")

    # Initialize service
    service = FactExtractionService()

    stats = {
        "turns_processed": 0,
        "facts_extracted": 0,
        "turns_skipped": 0,
        "errors": [],
    }

    # Process message pairs (user at i, assistant at i+1)
    i = 0

    while i < len(messages) - 1:
        user_msg = messages[i]
        assistant_msg = messages[i + 1]

        # Verify pair structure
        if user_msg.role != "user":
            logger.debug(f"[Backfill] Skipping index {i}: not a user message (role={user_msg.role})")
            i += 1
            continue

        if assistant_msg.role != "assistant":
            logger.debug(f"[Backfill] Skipping index {i}: next message not assistant (role={assistant_msg.role})")
            i += 1
            continue

        # Calculate turn number (1-indexed)
        # Turn 1 = messages[0,1], Turn 2 = messages[2,3], etc.
        turn = (i // 2) + 1

        # Check if turn is in range
        if turn < start_turn:
            i += 2
            continue
        if end_turn is not None and turn > end_turn:
            break

        # Skip if turn already has facts
        if turn in existing_turns:
            logger.debug(f"[Backfill] Turn {turn} already has facts, skipping")
            stats["turns_skipped"] += 1
            i += 2
            continue

        logger.info(f"[Backfill] Processing turn {turn}: '{user_msg.content[:50]}...'")

        try:
            # Build extraction prompt and call LLM
            prompt_messages = service._build_extraction_prompt(
                user_msg.content, assistant_msg.content
            )

            response = service.llm_service.complete(
                messages=prompt_messages,
                temperature=service.temperature,
                max_tokens=service.max_tokens,
                retry=False,
            )

            # Parse response
            facts_data = service._parse_facts_response(response.content)

            # Create ConversationFact objects with correct turn
            turn_facts = []
            for fact_dict in facts_data:
                importance = fact_dict.get("importance", 0.5)
                if not isinstance(importance, (int, float)):
                    importance = 0.5
                importance = max(0.0, min(1.0, float(importance)))

                category = fact_dict.get("category", "topic")
                valid_categories = [c.value for c in FactCategory]
                if category not in valid_categories:
                    category = FactCategory.TOPIC.value

                fact = ConversationFact(
                    conversation_id=conversation.id,
                    user_id=conversation.user_id,
                    fact_key=fact_dict["key"],
                    fact_value=fact_dict["value"],
                    source_turn=turn,  # Use calculated turn, not conversation.message_count
                    confidence_score=1.0,
                    importance=importance,
                    category=category,
                )
                turn_facts.append(fact)

            # Deduplicate against existing facts in DB (only this turn's facts)
            deduplicated_facts = service._deduplicate_facts(
                db, conversation_id, turn_facts
            )

            if dry_run:
                for fact in deduplicated_facts:
                    logger.info(
                        f"[Backfill DRY RUN] Would extract: turn={fact.source_turn}, "
                        f"key={fact.fact_key}, value={fact.fact_value[:50]}..., "
                        f"importance={fact.importance:.2f}, category={fact.category}"
                    )
                stats["facts_extracted"] += len(deduplicated_facts)
            else:
                # Add facts to session and commit immediately for this turn
                for fact in deduplicated_facts:
                    db.add(fact)
                # Commit after each turn to avoid batch issues with duplicate keys
                db.commit()
                stats["facts_extracted"] += len(deduplicated_facts)
                logger.info(f"[Backfill] Turn {turn}: extracted {len(deduplicated_facts)} facts")

            stats["turns_processed"] += 1

        except Exception as e:
            error_msg = f"Turn {turn}: {str(e)}"
            logger.warning(f"[Backfill] Error processing turn {turn}: {e}")
            stats["errors"].append(error_msg)
            # Rollback any pending changes for this turn
            db.rollback()

        i += 2  # Move to next pair

    logger.info(
        f"[Backfill] Complete: processed={stats['turns_processed']}, "
        f"extracted={stats['facts_extracted']}, skipped={stats['turns_skipped']}, "
        f"errors={len(stats['errors'])}"
    )

    return stats
