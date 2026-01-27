"""
LLM provider abstraction for multiple backends.

Supports:
- DeepSeek (DeepSeek-V3 chat and reasoner models)
- Ollama (local LLMs via HTTP API)
- OpenAI (GPT models)
- Anthropic (Claude models)
- Azure OpenAI

Provides unified interface for chat completion with retry logic and streaming support.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Iterator
from dataclasses import dataclass
import time
import httpx

from app.core.config import settings


@dataclass
class Message:
    """Chat message."""

    role: str  # 'system', 'user', or 'assistant'
    content: str


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    provider: str
    usage: Optional[
        Dict[str, int]
    ] = None  # {input_tokens, output_tokens, total_tokens, prompt_cache_hit_tokens, prompt_cache_miss_tokens}
    finish_reason: Optional[str] = None
    response_time_seconds: Optional[float] = None
    reasoning_content: Optional[str] = None  # For DeepSeek Reasoner chain-of-thought


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a completion for the given messages.

        Args:
            messages: List of messages (conversation history)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse object
        """
        pass

    @abstractmethod
    def stream_complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """
        Generate a streaming completion.

        Args:
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Content chunks as they are generated
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict:
        """Get information about the model."""
        pass


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider for local models.

    Connects to Ollama HTTP API (typically running on localhost:11434).
    """

    def __init__(self, base_url: str = None, model: str = None, timeout: int = 300):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL
            model: Model name (e.g., "llama2", "mistral")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self.timeout = timeout
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using Ollama."""
        start_time = time.time()

        # Allow per-request model override (e.g., from API request)
        override_model = kwargs.pop("model", None)

        # Convert messages to Ollama format
        ollama_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        payload = {
            "model": override_model or self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {},
        }

        if temperature is not None:
            payload["options"]["temperature"] = temperature

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        # Debug logging
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Ollama request: model={payload['model']}, num_predict={payload['options'].get('num_predict', 'NOT SET')}, max_tokens_param={max_tokens}"
        )

        try:
            response = self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

            response_time = time.time() - start_time

            return LLMResponse(
                content=data["message"]["content"],
                model=override_model or self.model,
                provider="ollama",
                usage={
                    "input_tokens": data.get("prompt_eval_count", 0),
                    "output_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0)
                    + data.get("eval_count", 0),
                },
                finish_reason=data.get("done_reason"),
                response_time_seconds=response_time,
            )

        except httpx.HTTPError as e:
            raise Exception(f"Ollama API error: {str(e)}")

    def stream_complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Generate streaming completion using Ollama."""
        override_model = kwargs.pop("model", None)
        ollama_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        payload = {
            "model": override_model or self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {},
        }

        if temperature is not None:
            payload["options"]["temperature"] = temperature

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        try:
            with self.client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        import json

                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]

        except httpx.HTTPError as e:
            raise Exception(f"Ollama streaming error: {str(e)}")

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {"provider": "ollama", "model": self.model, "base_url": self.base_url}


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider (GPT models)."""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "gpt-4-turbo-preview")
        """
        import openai

        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.model = model or settings.openai_model
        self.client = openai.OpenAI(api_key=self.api_key)

    def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using OpenAI."""
        start_time = time.time()

        # Allow per-request model override
        override_model = kwargs.pop("model", None)

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        params = {
            "model": override_model or self.model,
            "messages": openai_messages,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        try:
            response = self.client.chat.completions.create(**params)

            response_time = time.time() - start_time

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                provider="openai",
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
                response_time_seconds=response_time,
            )

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def stream_complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Generate streaming completion using OpenAI."""
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        params = {
            "model": self.model,
            "messages": openai_messages,
            "stream": True,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        try:
            stream = self.client.chat.completions.create(**params)

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise Exception(f"OpenAI streaming error: {str(e)}")

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {"provider": "openai", "model": self.model}


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider (Claude models)."""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (e.g., "claude-3-sonnet-20240229")
        """
        import anthropic

        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.model = model or settings.anthropic_model
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using Anthropic."""
        start_time = time.time()

        # Allow per-request model override
        override_model = kwargs.pop("model", None)

        # Extract system message if present
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({"role": msg.role, "content": msg.content})

        params = {
            "model": override_model or self.model,
            "messages": conversation_messages,
            "max_tokens": max_tokens or settings.llm_max_tokens,
        }

        if system_message:
            params["system"] = system_message

        if temperature is not None:
            params["temperature"] = temperature

        try:
            response = self.client.messages.create(**params)

            response_time = time.time() - start_time

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                provider="anthropic",
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens
                    + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
                response_time_seconds=response_time,
            )

        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def stream_complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Generate streaming completion using Anthropic."""
        # Extract system message
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({"role": msg.role, "content": msg.content})

        params = {
            "model": self.model,
            "messages": conversation_messages,
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "stream": True,
        }

        if system_message:
            params["system"] = system_message

        if temperature is not None:
            params["temperature"] = temperature

        try:
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise Exception(f"Anthropic streaming error: {str(e)}")

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {"provider": "anthropic", "model": self.model}


class DeepSeekProvider(LLMProvider):
    """
    DeepSeek LLM provider using OpenAI-compatible API.

    Supports:
    - deepseek-chat: Fast responses, standard chat completion
    - deepseek-reasoner: Advanced reasoning with chain-of-thought

    Note: deepseek-reasoner returns `reasoning_content` which must NOT be
    included in subsequent messages (returns 400 error if included).
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize DeepSeek provider.

        Args:
            api_key: DeepSeek API key
            model: Model name (deepseek-chat or deepseek-reasoner)
        """
        import openai
        import logging

        self.logger = logging.getLogger(__name__)
        self.api_key = api_key or settings.deepseek_api_key
        if not self.api_key:
            raise ValueError("DeepSeek API key is required")

        self.model = model or settings.deepseek_model
        self.base_url = settings.deepseek_base_url
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion using DeepSeek API.

        For deepseek-reasoner model, extracts reasoning_content but does NOT
        include it in the response content (to prevent errors in multi-turn).
        """
        start_time = time.time()

        # Allow per-request model override
        override_model = kwargs.pop("model", None)
        effective_model = override_model or self.model

        # Convert messages to OpenAI format
        deepseek_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        params = {
            "model": effective_model,
            "messages": deepseek_messages,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        try:
            response = self.client.chat.completions.create(**params)

            response_time = time.time() - start_time

            # Extract reasoning_content if present (for deepseek-reasoner)
            reasoning_content = None
            message = response.choices[0].message
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                reasoning_content = message.reasoning_content
                self.logger.info(
                    f"[DeepSeek Reasoner] Generated {len(reasoning_content)} chars of chain-of-thought"
                )

            # Build usage dict with cache metrics
            usage_dict = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            # Add cache metrics if available (DeepSeek automatic caching)
            if hasattr(response.usage, "prompt_cache_hit_tokens"):
                usage_dict["prompt_cache_hit_tokens"] = response.usage.prompt_cache_hit_tokens
            if hasattr(response.usage, "prompt_cache_miss_tokens"):
                usage_dict["prompt_cache_miss_tokens"] = response.usage.prompt_cache_miss_tokens

            # Log cache performance
            cache_hit = usage_dict.get("prompt_cache_hit_tokens", 0)
            cache_miss = usage_dict.get("prompt_cache_miss_tokens", 0)
            if cache_hit > 0 or cache_miss > 0:
                total_prompt = cache_hit + cache_miss
                hit_rate = cache_hit / total_prompt if total_prompt > 0 else 0
                # Price difference: $0.28/M (miss) vs $0.028/M (hit) = $0.252/M savings
                savings = cache_hit * 0.000000252
                self.logger.info(
                    f"[DeepSeek Cache] Hit: {cache_hit} tokens ({hit_rate:.1%}), "
                    f"Miss: {cache_miss} tokens, Est. savings: ${savings:.6f}"
                )

            return LLMResponse(
                content=message.content,
                model=response.model,
                provider="deepseek",
                usage=usage_dict,
                finish_reason=response.choices[0].finish_reason,
                response_time_seconds=response_time,
                reasoning_content=reasoning_content,
            )

        except Exception as e:
            raise Exception(f"DeepSeek API error: {str(e)}")

    def stream_complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Generate streaming completion using DeepSeek API."""
        override_model = kwargs.pop("model", None)
        effective_model = override_model or self.model

        deepseek_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        params = {
            "model": effective_model,
            "messages": deepseek_messages,
            "stream": True,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        try:
            stream = self.client.chat.completions.create(**params)

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise Exception(f"DeepSeek streaming error: {str(e)}")

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "provider": "deepseek",
            "model": self.model,
            "base_url": self.base_url,
        }


class LLMService:
    """
    High-level LLM service with retry logic and error handling.

    Provides a unified interface for all LLM providers with automatic retries.
    Supports dynamic provider routing based on model name.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        """
        Initialize LLM service.

        Args:
            provider: LLM provider (defaults to configured provider)
        """
        if provider:
            self.provider = provider
        else:
            self.provider = self._create_provider()

        # Cache additional providers for dynamic routing
        self._ollama_provider = None
        self._anthropic_provider = None
        self._openai_provider = None
        self._deepseek_provider = None

        self.max_retries = 3

    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on configuration."""
        provider_type = settings.llm_provider

        if provider_type == "deepseek":
            return DeepSeekProvider()
        elif provider_type == "ollama":
            return OllamaProvider()
        elif provider_type == "openai":
            return OpenAIProvider()
        elif provider_type == "anthropic":
            return AnthropicProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_type}")

    def _get_provider_for_model(self, model_name: Optional[str]) -> LLMProvider:
        """
        Determine which provider to use based on model name.

        Routes to:
        - DeepSeek: for models starting with "deepseek-" (e.g., "deepseek-chat", "deepseek-reasoner")
        - Ollama: for models with ":" in name (e.g., "qwen3-vl:235b", "llama2:7b")
        - Anthropic: for models starting with "claude-"
        - OpenAI: for models starting with "gpt-"
        - Default: configured provider

        Args:
            model_name: Model name to route

        Returns:
            LLMProvider instance
        """
        if not model_name:
            return self.provider

        # DeepSeek models (deepseek-chat, deepseek-reasoner)
        if model_name.startswith("deepseek-"):
            if self._deepseek_provider is None:
                self._deepseek_provider = DeepSeekProvider()
            return self._deepseek_provider

        # Ollama models typically use "model:tag" format
        if ":" in model_name:
            if self._ollama_provider is None:
                self._ollama_provider = OllamaProvider()
            return self._ollama_provider

        # Anthropic Claude models
        if model_name.startswith("claude-"):
            if self._anthropic_provider is None:
                self._anthropic_provider = AnthropicProvider()
            return self._anthropic_provider

        # OpenAI models
        if model_name.startswith("gpt-"):
            if self._openai_provider is None:
                self._openai_provider = OpenAIProvider()
            return self._openai_provider

        # Default to configured provider
        return self.provider

    def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        retry: bool = True,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion with automatic retry on failure.

        Automatically routes to the correct provider based on model name:
        - Models with ":" (e.g., "qwen3-vl:235b") → Ollama
        - Models starting with "claude-" → Anthropic
        - Models starting with "gpt-" → OpenAI
        - No model specified → Default configured provider

        Args:
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            retry: Whether to retry on failure
            model: Optional explicit model name to use
            **kwargs: Additional parameters

        Returns:
            LLMResponse object
        """
        temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        # Select provider based on model name
        provider = self._get_provider_for_model(model)

        if not retry:
            return provider.complete(
                messages,
                temperature,
                max_tokens,
                model=model,
                **kwargs,
            )

        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return provider.complete(
                    messages,
                    temperature,
                    max_tokens,
                    model=model,
                    **kwargs,
                )
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                else:
                    raise last_exception

    def stream_complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> Iterator[str]:
        """
        Generate streaming completion.

        Automatically routes to the correct provider based on model name.

        Args:
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model: Optional explicit model name to use
            **kwargs: Additional parameters

        Yields:
            Content chunks
        """
        temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        # Select provider based on model name
        provider = self._get_provider_for_model(model)

        yield from provider.stream_complete(
            messages, temperature, max_tokens, model=model, **kwargs
        )

    def get_model_info(self) -> Dict:
        """Get model information."""
        return self.provider.get_model_info()


# Global LLM service instance
llm_service = LLMService()
