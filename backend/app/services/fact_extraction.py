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
from typing import List, Dict
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
