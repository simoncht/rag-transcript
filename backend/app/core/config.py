"""
Application configuration and settings.
"""
import sys
from typing import List, Literal, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    _ENV_FILE = None if "pytest" in sys.modules else ".env"
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "RAG Transcript System"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = "change-this-in-production"

    # API
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8000",
    ]

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        # Allow any localhost/127.0.0.1 origin in development for flexibility
        if isinstance(v, list):
            return v
        return v

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [email.strip() for email in v.split(",") if email.strip()]
        return v

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/rag_transcript"
    db_echo_sql: bool = False

    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Qdrant Vector Database
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "transcript_chunks"
    qdrant_api_key: str = ""

    # NextAuth.js Authentication
    nextauth_secret: Optional[str] = Field(default=None, env="NEXTAUTH_SECRET")
    admin_emails: List[str] = []

    # Storage
    storage_backend: Literal["local", "azure"] = "local"
    local_storage_path: str = "./storage"

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    azure_storage_account_key: str = ""
    azure_audio_container: str = "audio-files"
    azure_transcript_container: str = "transcripts"

    # Whisper Transcription
    whisper_model: Literal["tiny", "base", "small", "medium", "large"] = "base"
    whisper_device: Literal["cpu", "cuda"] = "cpu"
    whisper_compute_type: Literal["int8", "float16", "float32"] = "int8"

    # Chunking Configuration
    chunk_target_tokens: int = 256
    chunk_min_tokens: int = 16
    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 80
    chunk_max_duration_seconds: int = 90

    # Contextual Enrichment
    enable_contextual_enrichment: bool = True
    enrichment_batch_size: int = 10
    enrichment_max_retries: int = 3

    # Embedding Configuration
    embedding_model: str = "bert-base-uncased"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 32
    embedding_provider: Literal["local", "openai", "azure"] = "local"

    # LLM Provider Configuration
    llm_provider: Literal["deepseek", "ollama", "openai", "anthropic", "azure"] = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_max_tokens: int = 1500
    llm_temperature: float = 0.7

    # Tier-Based Model Configuration (see pricing.py for full config)
    # DeepSeek models: deepseek-chat (fast), deepseek-reasoner (advanced reasoning)
    llm_model_free: str = "deepseek-chat"  # DeepSeek Chat - fast, non-thinking mode
    llm_model_pro: str = "deepseek-reasoner"  # DeepSeek Reasoner - thinking mode
    llm_model_enterprise: str = "deepseek-reasoner"  # Same as Pro with SLA

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    openai_embedding_model: str = "text-embedding-3-small"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-sonnet-20240229"

    # DeepSeek (recommended for RAG - OpenAI-compatible API)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"  # Options: deepseek-chat, deepseek-reasoner

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: str = ""

    # RAG Configuration
    retrieval_top_k: int = 20

    # RAG Relevance Filtering (Phase 1)
    min_relevance_score: float = 0.50
    fallback_relevance_score: float = 0.15
    weak_context_threshold: float = 0.40

    # RAG Re-ranking (Phase 2)
    enable_reranking: bool = True
    reranking_top_k: int = 7
    reranking_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # RAG Query Expansion (Performance Optimization)
    enable_query_expansion: bool = True
    query_expansion_variants: int = 2  # Number of query variants to generate

    # Video Processing Limits
    max_video_duration_seconds: int = 14400  # 4 hours
    max_video_file_size_mb: int = 2048  # 2 GB
    cleanup_audio_after_transcription: bool = True  # Auto-delete audio after transcription

    # Caption Extraction (YouTube auto-captions)
    enable_caption_extraction: bool = True  # Try YouTube captions before Whisper
    caption_preferred_language: str = "en"  # Preferred caption language

    # Usage Quotas
    free_tier_video_limit: int = 2
    free_tier_minutes_limit: int = 1000
    free_tier_messages_limit: int = 50
    free_tier_storage_mb_limit: int = 1000

    # Stripe Payment Integration
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # Stripe Price IDs (monthly/yearly for each tier)
    stripe_pro_monthly_price_id: str = ""
    stripe_pro_yearly_price_id: str = ""
    stripe_enterprise_monthly_price_id: str = ""
    stripe_enterprise_yearly_price_id: str = ""

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    @model_validator(mode="after")
    def validate_production_security(self):
        """Validate critical security settings in production environment."""
        if self.environment == "production":
            # Check for weak SECRET_KEY
            weak_keys = ["change-this", "your-secret", "changeme", "secret"]
            if any(weak in self.secret_key.lower() for weak in weak_keys):
                raise ValueError(
                    "SECURITY: SECRET_KEY must be changed in production. "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )

            # Check NextAuth secret is configured
            if not self.nextauth_secret:
                raise ValueError(
                    "SECURITY: NEXTAUTH_SECRET must be configured in production. "
                    "Generate a secure key with: openssl rand -base64 32"
                )

            # Check debug mode is disabled
            if self.debug:
                raise ValueError(
                    "SECURITY: DEBUG must be False in production. "
                    "Debug mode exposes sensitive information and detailed error messages."
                )

        return self

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Global settings instance
settings = Settings()
