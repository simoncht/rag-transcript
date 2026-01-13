"""
Fact Extraction Service.

Extracts key facts from conversation messages for long-distance recall.
Enables the system to remember important information from early turns.
"""
import json
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.models.conversation_fact import ConversationFact
from app.models.message import Message
from app.models.conversation import Conversation
from app.services.llm_providers import Message as LLMMessage, LLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


FACT_EXTRACTION_PROMPT = """Extract key facts from this Q&A pair as simple key-value pairs.

Q: {user_query}
A: {assistant_response}

Return JSON array of facts:
[
  {{"key": "instructor", "value": "Dr. Andrew Ng"}},
  {{"key": "topic", "value": "machine learning"}},
  {{"key": "framework", "value": "TensorFlow"}}
]

Extract ONLY:
- Names (people, organizations, places)
- Key concepts or topics
- Tools, frameworks, or technologies
- Important dates, numbers, or findings

Use short, descriptive keys (lowercase, underscore-separated).
Return empty array if no facts.
"""


class FactExtractionService:
    """Extract factual claims from conversation messages."""

    def __init__(self):
        """Initialize the fact extraction service."""
        self.llm_service = LLMService()
        self.temperature = 0.2  # Low temperature for consistency
        self.max_tokens = 500  # Enough for JSON response

    def extract_facts(
        self,
        db: Session,
        message: Message,
        conversation: Conversation,
        user_query: str
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

            # Create ConversationFact objects
            facts = []
            current_turn = (conversation.message_count + 1) // 2  # Estimate turn number

            for fact_dict in facts_data:
                fact = ConversationFact(
                    conversation_id=conversation.id,
                    user_id=conversation.user_id,
                    fact_key=fact_dict["key"],
                    fact_value=fact_dict["value"],
                    source_turn=current_turn,
                    confidence_score=1.0,  # Simple extraction has high confidence
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
        self,
        user_query: str,
        assistant_response: str
    ) -> List[LLMMessage]:
        """Create prompt for fact extraction."""
        # Truncate very long responses to save tokens
        if len(assistant_response) > 2000:
            assistant_response = assistant_response[:2000] + "..."

        prompt_content = FACT_EXTRACTION_PROMPT.format(
            user_query=user_query,
            assistant_response=assistant_response
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
            List of fact dictionaries with 'key' and 'value'
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

                validated_facts.append(fact)

            return validated_facts

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse facts JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error parsing facts response: {e}")
            return []

    def _deduplicate_facts(
        self,
        db: Session,
        conversation_id: str,
        new_facts: List[ConversationFact]
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
        # Get existing fact keys for this conversation
        existing_facts = (
            db.query(ConversationFact)
            .filter(ConversationFact.conversation_id == conversation_id)
            .all()
        )

        existing_keys = {fact.fact_key: fact for fact in existing_facts}

        # Filter out duplicates (keep new facts only if key doesn't exist)
        deduplicated = []
        for fact in new_facts:
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
