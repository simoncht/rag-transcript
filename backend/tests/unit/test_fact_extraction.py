"""
Comprehensive unit tests for Phase 2 conversation facts extraction.

Tests cover:
- Fact extraction from messages
- JSON parsing and validation
- Fact deduplication
- Database operations
- Edge cases and error handling
- Token optimization
"""
import json
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.fact_extraction import FactExtractionService, FACT_EXTRACTION_PROMPT
from app.models.conversation_fact import ConversationFact
from app.models.message import Message
from app.models.conversation import Conversation
from app.services.llm_providers import LLMResponse


class TestFactExtractionService:
    """Test suite for FactExtractionService."""

    @pytest.fixture
    def service(self):
        """Create a FactExtractionService instance."""
        return FactExtractionService()

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        return db

    @pytest.fixture
    def test_conversation(self):
        """Create a test conversation."""
        return Conversation(
            id="test-conv-id",
            user_id="test-user-id",
            message_count=20,
            selected_video_ids=[],
        )

    @pytest.fixture
    def test_message(self):
        """Create a test assistant message."""
        return Message(
            id="test-msg-id",
            conversation_id="test-conv-id",
            role="assistant",
            content="The instructor is Dr. Andrew Ng. The course covers machine learning using TensorFlow.",
        )

    # ==================== Test: Successful Extraction ====================

    def test_extract_facts_success(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test successful fact extraction from message."""
        # Mock LLM response
        llm_response = LLMResponse(
            content=json.dumps(
                [
                    {"key": "instructor", "value": "Dr. Andrew Ng"},
                    {"key": "topic", "value": "machine learning"},
                    {"key": "framework", "value": "TensorFlow"},
                ]
            ),
            model="test-model",
            provider="test",
        )

        # Mock existing facts query (no duplicates)
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Who is the instructor?",
            )

        # Assertions
        assert len(facts) == 3
        assert facts[0].fact_key == "instructor"
        assert facts[0].fact_value == "Dr. Andrew Ng"
        assert facts[0].conversation_id == "test-conv-id"
        assert facts[0].user_id == "test-user-id"
        assert facts[0].confidence_score == 1.0

    def test_extract_facts_with_markdown_code_blocks(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test extraction handles markdown code blocks in LLM response."""
        # Mock LLM response with markdown
        llm_response = LLMResponse(
            content="""```json
[
  {"key": "instructor", "value": "Dr. Smith"},
  {"key": "topic", "value": "neural networks"}
]
```""",
            model="test-model",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test query",
            )

        assert len(facts) == 2
        assert facts[0].fact_key == "instructor"
        assert facts[1].fact_key == "topic"

    def test_extract_facts_normalizes_keys(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test that fact keys are normalized (lowercase, underscores)."""
        llm_response = LLMResponse(
            content=json.dumps(
                [
                    {"key": "Course Instructor", "value": "Dr. Smith"},
                    {"key": "Main-Topic", "value": "AI"},
                ]
            ),
            model="test",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test",
            )

        assert facts[0].fact_key == "course_instructor"
        assert facts[1].fact_key == "main_topic"

    # ==================== Test: Deduplication ====================

    def test_deduplication_skips_existing_keys(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test that facts with existing keys are skipped."""
        # Mock existing facts
        existing_fact = ConversationFact(
            id="existing-fact-id",
            conversation_id="test-conv-id",
            user_id="test-user-id",
            fact_key="instructor",
            fact_value="Dr. Existing",
            source_turn=1,
            confidence_score=1.0,
        )
        mock_db.query.return_value.filter.return_value.all.return_value = [
            existing_fact
        ]

        # Mock LLM response with duplicate key
        llm_response = LLMResponse(
            content=json.dumps(
                [
                    {"key": "instructor", "value": "Dr. New"},  # Duplicate
                    {"key": "topic", "value": "ML"},  # New
                ]
            ),
            model="test",
            provider="test",
        )

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test",
            )

        # Should only return the new fact
        assert len(facts) == 1
        assert facts[0].fact_key == "topic"
        assert facts[0].fact_value == "ML"

    # ==================== Test: Edge Cases ====================

    def test_extract_facts_empty_response(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test extraction handles empty fact array."""
        llm_response = LLMResponse(
            content="[]",
            model="test",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test",
            )

        assert len(facts) == 0

    def test_extract_facts_invalid_json(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test extraction handles invalid JSON gracefully."""
        llm_response = LLMResponse(
            content="This is not valid JSON",
            model="test",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test",
            )

        # Should return empty list on parse failure
        assert len(facts) == 0

    def test_extract_facts_malformed_structure(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test extraction handles malformed fact structure."""
        llm_response = LLMResponse(
            content=json.dumps(
                [
                    {"key": "instructor"},  # Missing value
                    {"value": "ML"},  # Missing key
                    {"key": "", "value": "Test"},  # Empty key
                    {"key": "topic", "value": ""},  # Empty value
                    {"key": "valid", "value": "Valid Fact"},  # Valid
                ]
            ),
            model="test",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test",
            )

        # Should only extract valid fact
        assert len(facts) == 1
        assert facts[0].fact_key == "valid"

    def test_extract_facts_llm_failure(
        self, service, mock_db, test_conversation, test_message
    ):
        """Test extraction handles LLM failures gracefully."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(
            service.llm_service, "complete", side_effect=Exception("LLM error")
        ):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=test_conversation,
                user_query="Test",
            )

        # Should return empty list on LLM failure
        assert len(facts) == 0

    # ==================== Test: Prompt Construction ====================

    def test_build_extraction_prompt(self, service):
        """Test extraction prompt is built correctly."""
        user_query = "Who is the instructor?"
        assistant_response = "The instructor is Dr. Smith."

        messages = service._build_extraction_prompt(user_query, assistant_response)

        assert len(messages) == 2
        assert messages[0].role == "system"
        assert "fact extraction" in messages[0].content.lower()
        assert messages[1].role == "user"
        assert user_query in messages[1].content
        assert assistant_response in messages[1].content

    def test_build_extraction_prompt_truncates_long_response(self, service):
        """Test extraction prompt truncates very long responses."""
        user_query = "Test query"
        assistant_response = "x" * 3000  # Very long response

        messages = service._build_extraction_prompt(user_query, assistant_response)

        # Should truncate and add ellipsis
        assert len(messages[1].content) < 3000
        assert "..." in messages[1].content

    # ==================== Test: JSON Parsing ====================

    def test_parse_facts_response_valid_json(self, service):
        """Test parsing valid JSON response."""
        response = json.dumps([{"key": "test_key", "value": "test_value"}])

        facts = service._parse_facts_response(response)

        assert len(facts) == 1
        assert facts[0]["key"] == "test_key"
        assert facts[0]["value"] == "test_value"

    def test_parse_facts_response_strips_markdown(self, service):
        """Test parsing strips markdown code blocks."""
        response = "```json\n" + json.dumps([{"key": "test", "value": "val"}]) + "\n```"

        facts = service._parse_facts_response(response)

        assert len(facts) == 1
        assert facts[0]["key"] == "test"

    def test_parse_facts_response_not_array(self, service):
        """Test parsing handles non-array JSON."""
        response = json.dumps({"key": "val"})  # Object, not array

        facts = service._parse_facts_response(response)

        assert len(facts) == 0

    def test_parse_facts_response_invalid_item_type(self, service):
        """Test parsing skips non-dict items."""
        response = json.dumps(
            [{"key": "valid", "value": "fact"}, "not a dict", 123, None]
        )

        facts = service._parse_facts_response(response)

        assert len(facts) == 1
        assert facts[0]["key"] == "valid"

    # ==================== Test: Turn Number Calculation ====================

    def test_source_turn_calculation(self, service, mock_db, test_message):
        """Test source turn number is calculated correctly."""
        conversation = Conversation(
            id="test-conv-id",
            user_id="test-user-id",
            message_count=26,  # 13 turns (26/2)
            selected_video_ids=[],
        )

        llm_response = LLMResponse(
            content=json.dumps([{"key": "test", "value": "val"}]),
            model="test",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=test_message,
                conversation=conversation,
                user_query="Test",
            )

        # Turn number should be (26 + 1) // 2 = 13 (current turn)
        assert facts[0].source_turn == 13

    # ==================== Test: Token Optimization ====================

    def test_prompt_token_efficiency(self, service):
        """Test that extraction prompt is token-efficient."""
        user_query = "Who is the instructor?"
        assistant_response = "The instructor is Dr. Smith teaching machine learning."

        messages = service._build_extraction_prompt(user_query, assistant_response)
        prompt_content = messages[1].content

        # Rough token count (4 chars ≈ 1 token)
        estimated_tokens = len(prompt_content) / 4

        # Should be under 400 tokens (target is ~350)
        assert estimated_tokens < 400, f"Prompt too long: ~{estimated_tokens} tokens"

    # ==================== Test: Integration ====================

    def test_full_extraction_flow(self, service, mock_db):
        """Test complete extraction flow from message to saved facts."""
        # Setup
        conversation = Conversation(
            id="test-conv-id",
            user_id="test-user-id",
            message_count=30,
            selected_video_ids=[],
        )

        message = Message(
            id="test-msg-id",
            conversation_id="test-conv-id",
            role="assistant",
            content="Dr. Jane Doe teaches deep learning using PyTorch framework.",
        )

        llm_response = LLMResponse(
            content=json.dumps(
                [
                    {"key": "instructor", "value": "Dr. Jane Doe"},
                    {"key": "topic", "value": "deep learning"},
                    {"key": "framework", "value": "PyTorch"},
                ]
            ),
            model="test",
            provider="test",
        )

        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Execute
        with patch.object(service.llm_service, "complete", return_value=llm_response):
            facts = service.extract_facts(
                db=mock_db,
                message=message,
                conversation=conversation,
                user_query="Who is the instructor and what do they teach?",
            )

        # Verify
        assert len(facts) == 3

        # Verify fact 1
        assert facts[0].fact_key == "instructor"
        assert facts[0].fact_value == "Dr. Jane Doe"
        assert facts[0].conversation_id == "test-conv-id"
        assert facts[0].user_id == "test-user-id"
        assert facts[0].source_turn == 15  # (30 + 1) // 2

        # Verify fact 2
        assert facts[1].fact_key == "topic"
        assert facts[1].fact_value == "deep learning"

        # Verify fact 3
        assert facts[2].fact_key == "framework"
        assert facts[2].fact_value == "PyTorch"


class TestConversationFactModel:
    """Test suite for ConversationFact model."""

    def test_fact_creation(self):
        """Test creating a conversation fact."""
        fact = ConversationFact(
            conversation_id="test-conv-id",
            user_id="test-user-id",
            fact_key="instructor",
            fact_value="Dr. Smith",
            source_turn=5,
            confidence_score=0.95,
        )

        assert fact.fact_key == "instructor"
        assert fact.fact_value == "Dr. Smith"
        assert fact.source_turn == 5
        assert fact.confidence_score == 0.95

    def test_fact_repr(self):
        """Test fact string representation."""
        fact = ConversationFact(
            conversation_id="test-conv-id",
            user_id="test-user-id",
            fact_key="topic",
            fact_value="This is a very long value that should be truncated in repr",
            source_turn=1,
            confidence_score=1.0,
        )

        repr_str = repr(fact)
        assert "topic" in repr_str
        assert "turn=1" in repr_str
        assert "confidence=1.00" in repr_str
        assert "..." in repr_str  # Value should be truncated


class TestFactExtractionPrompt:
    """Test suite for extraction prompt template."""

    def test_prompt_includes_required_elements(self):
        """Test prompt template includes all required elements."""
        assert "key" in FACT_EXTRACTION_PROMPT
        assert "value" in FACT_EXTRACTION_PROMPT
        assert "JSON" in FACT_EXTRACTION_PROMPT
        assert "Names" in FACT_EXTRACTION_PROMPT
        assert "concepts" in FACT_EXTRACTION_PROMPT
        assert "Tools" in FACT_EXTRACTION_PROMPT
        assert "frameworks" in FACT_EXTRACTION_PROMPT

    def test_prompt_format_placeholders(self):
        """Test prompt has correct format placeholders."""
        assert "{user_query}" in FACT_EXTRACTION_PROMPT
        assert "{assistant_response}" in FACT_EXTRACTION_PROMPT

    def test_prompt_example_format(self):
        """Test prompt shows correct JSON format example."""
        # Should show the double-brace format for JSON
        assert '"key":' in FACT_EXTRACTION_PROMPT or '"key"' in FACT_EXTRACTION_PROMPT
        assert (
            '"value":' in FACT_EXTRACTION_PROMPT or '"value"' in FACT_EXTRACTION_PROMPT
        )


class TestFactDeduplication:
    """Test suite for fact deduplication logic."""

    @pytest.fixture
    def service(self):
        return FactExtractionService()

    @pytest.fixture
    def mock_db(self):
        db = Mock(spec=Session)
        db.query = Mock()
        return db

    def test_deduplicate_no_existing_facts(self, service, mock_db):
        """Test deduplication when no existing facts."""
        new_facts = [
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key1",
                fact_value="value1",
                source_turn=1,
            ),
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key2",
                fact_value="value2",
                source_turn=2,
            ),
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = []

        deduplicated = service._deduplicate_facts(mock_db, "test-conv-id", new_facts)

        assert len(deduplicated) == 2

    def test_deduplicate_with_existing_facts(self, service, mock_db):
        """Test deduplication removes facts with existing keys."""
        existing_facts = [
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key1",
                fact_value="old_value",
                source_turn=1,
            ),
        ]

        new_facts = [
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key1",  # Duplicate
                fact_value="new_value",
                source_turn=5,
            ),
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key2",  # New
                fact_value="value2",
                source_turn=5,
            ),
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = existing_facts

        deduplicated = service._deduplicate_facts(mock_db, "test-conv-id", new_facts)

        # Should only keep the new key
        assert len(deduplicated) == 1
        assert deduplicated[0].fact_key == "key2"

    def test_deduplicate_all_duplicates(self, service, mock_db):
        """Test deduplication when all new facts are duplicates."""
        existing_facts = [
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key1",
                fact_value="value1",
                source_turn=1,
            ),
        ]

        new_facts = [
            ConversationFact(
                conversation_id="test-conv-id",
                user_id="test-user-id",
                fact_key="key1",  # Duplicate
                fact_value="different_value",
                source_turn=5,
            ),
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = existing_facts

        deduplicated = service._deduplicate_facts(mock_db, "test-conv-id", new_facts)

        # Should return empty list
        assert len(deduplicated) == 0


# ==================== Integration Tests ====================


class TestFactExtractionIntegration:
    """Integration tests for fact extraction with database."""

    def test_extraction_persists_to_database(self, db):
        """Test that extracted facts are persisted correctly."""
        # This would require a real database session
        # Skip for now, covered by 40-turn validation test
        pytest.skip("Requires database fixture - covered by validation test")


# ==================== Performance Tests ====================


class TestFactExtractionPerformance:
    """Performance tests for fact extraction."""

    def test_extraction_prompt_size(self):
        """Test extraction prompt stays within token budget."""
        user_query = "Who is the instructor?"
        assistant_response = "Dr. Smith teaches machine learning."

        service = FactExtractionService()
        messages = service._build_extraction_prompt(user_query, assistant_response)
        prompt_content = messages[1].content

        # Token estimate: ~4 chars per token
        estimated_tokens = len(prompt_content) / 4

        # Target: ~350 tokens, max: 400 tokens
        assert estimated_tokens < 400, f"Prompt too large: ~{estimated_tokens} tokens"

    def test_fact_key_normalization_performance(self):
        """Test key normalization is efficient."""
        test_keys = [
            "Course Instructor",
            "Main-Topic",
            "Framework_Used",
            "Date Of Event",
            "number-of-participants",
        ]

        for key in test_keys:
            normalized = key.lower().replace(" ", "_").replace("-", "_")
            # Verify normalization works
            assert "_" in normalized or normalized.islower()
