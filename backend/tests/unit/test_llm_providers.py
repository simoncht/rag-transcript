"""
Unit tests for the LLM providers service.

Tests Message and LLMResponse dataclasses, and basic provider patterns.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_providers import (
    Message,
    LLMResponse,
)


class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_roles(self):
        """Test different message roles."""
        system_msg = Message(role="system", content="You are helpful")
        user_msg = Message(role="user", content="Hi")
        assistant_msg = Message(role="assistant", content="Hello!")

        assert system_msg.role == "system"
        assert user_msg.role == "user"
        assert assistant_msg.role == "assistant"

    def test_message_empty_content(self):
        """Test message with empty content."""
        msg = Message(role="user", content="")
        assert msg.content == ""

    def test_message_long_content(self):
        """Test message with long content."""
        long_content = "x" * 10000
        msg = Message(role="user", content=long_content)
        assert len(msg.content) == 10000


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_response_basic(self):
        """Test creating a basic response."""
        response = LLMResponse(
            content="Hello there!",
            model="test-model",
            provider="test-provider",
        )
        assert response.content == "Hello there!"
        assert response.model == "test-model"
        assert response.provider == "test-provider"
        assert response.usage is None
        assert response.finish_reason is None

    def test_response_with_usage(self):
        """Test response with usage stats."""
        response = LLMResponse(
            content="Response",
            model="test-model",
            provider="test-provider",
            usage={
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
        )
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.usage["total_tokens"] == 30

    def test_response_with_cache_info(self):
        """Test response with cache hit information."""
        response = LLMResponse(
            content="Cached response",
            model="deepseek-chat",
            provider="deepseek",
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 20,
            },
        )
        assert response.usage["prompt_cache_hit_tokens"] == 80
        assert response.usage["prompt_cache_miss_tokens"] == 20

    def test_response_with_reasoning(self):
        """Test response with reasoning content (DeepSeek Reasoner)."""
        response = LLMResponse(
            content="The answer is 42",
            model="deepseek-reasoner",
            provider="deepseek",
            reasoning_content="Let me think about this step by step...",
        )
        assert response.reasoning_content is not None
        assert "step by step" in response.reasoning_content

    def test_response_with_timing(self):
        """Test response with response time."""
        response = LLMResponse(
            content="Quick response",
            model="test",
            provider="test",
            response_time_seconds=0.5,
        )
        assert response.response_time_seconds == 0.5

    def test_response_with_finish_reason(self):
        """Test response with finish reason."""
        response = LLMResponse(
            content="Complete response",
            model="test",
            provider="test",
            finish_reason="stop",
        )
        assert response.finish_reason == "stop"

    def test_response_empty_content(self):
        """Test response with empty content."""
        response = LLMResponse(
            content="",
            model="test",
            provider="test",
        )
        assert response.content == ""


class TestLLMServiceBasics:
    """Test basic LLM service functionality."""

    def test_llm_service_import(self):
        """Test LLMService can be imported."""
        from app.services.llm_providers import LLMService
        assert LLMService is not None

    def test_llm_service_singleton_import(self):
        """Test global llm_service can be imported."""
        from app.services.llm_providers import llm_service
        assert llm_service is not None


class TestMessageConversion:
    """Test message format conversion patterns."""

    def test_message_to_dict(self):
        """Test converting Message to dict format."""
        msg = Message(role="user", content="Hello")
        msg_dict = {"role": msg.role, "content": msg.content}
        assert msg_dict == {"role": "user", "content": "Hello"}

    def test_messages_list_conversion(self):
        """Test converting list of Messages to list of dicts."""
        messages = [
            Message(role="system", content="Be helpful"),
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]

        converted = [{"role": m.role, "content": m.content} for m in messages]

        assert len(converted) == 3
        assert converted[0]["role"] == "system"
        assert converted[1]["role"] == "user"
        assert converted[2]["role"] == "assistant"


class TestResponseValidation:
    """Test LLMResponse validation patterns."""

    def test_response_has_required_fields(self):
        """Test response requires content, model, and provider."""
        response = LLMResponse(
            content="test",
            model="test-model",
            provider="test-provider",
        )
        assert hasattr(response, "content")
        assert hasattr(response, "model")
        assert hasattr(response, "provider")

    def test_response_optional_fields_default_none(self):
        """Test optional fields default to None."""
        response = LLMResponse(
            content="test",
            model="test-model",
            provider="test-provider",
        )
        assert response.usage is None
        assert response.finish_reason is None
        assert response.response_time_seconds is None
        assert response.reasoning_content is None


class TestUsageTracking:
    """Test usage tracking in responses."""

    def test_usage_dict_structure(self):
        """Test usage dict can contain various token counts."""
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
        }

        response = LLMResponse(
            content="test",
            model="test",
            provider="test",
            usage=usage,
        )

        assert response.usage["input_tokens"] == 100
        assert response.usage["output_tokens"] == 50
        assert response.usage["total_tokens"] == 150
        assert response.usage["prompt_cache_hit_tokens"] == 80
        assert response.usage["prompt_cache_miss_tokens"] == 20

    def test_cache_hit_ratio_calculation(self):
        """Test calculating cache hit ratio from usage."""
        usage = {
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
        }

        total = usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
        cache_hit_ratio = usage["prompt_cache_hit_tokens"] / total

        assert cache_hit_ratio == 0.8


class TestReasonerMaxTokensConfig:
    """Test reasoner max_tokens config setting."""

    def test_default_reasoner_max_tokens(self):
        """New config has correct default."""
        from app.core.config import Settings

        s = Settings()
        assert s.llm_max_tokens == 1500
        assert s.llm_max_tokens_reasoner == 8192

    def test_reasoner_max_tokens_greater_than_default(self):
        """Reasoner budget must exceed standard budget."""
        from app.core.config import Settings

        s = Settings()
        assert s.llm_max_tokens_reasoner > s.llm_max_tokens


class TestProviderPatterns:
    """Test common provider patterns."""

    def test_provider_has_complete_method(self):
        """Test providers have complete method."""
        from app.services.llm_providers import LLMProvider

        # LLMProvider is abstract, check it defines complete
        assert hasattr(LLMProvider, "complete")

    def test_provider_has_stream_complete_method(self):
        """Test providers have stream_complete method."""
        from app.services.llm_providers import LLMProvider

        assert hasattr(LLMProvider, "stream_complete")

    def test_provider_has_get_model_info_method(self):
        """Test providers have get_model_info method."""
        from app.services.llm_providers import LLMProvider

        assert hasattr(LLMProvider, "get_model_info")
