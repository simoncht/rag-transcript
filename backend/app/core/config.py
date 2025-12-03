"""
Application configuration and settings.
"""
from typing import List, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "RAG Transcript System"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: str = "change-this-in-production"

    # API
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
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
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    embedding_batch_size: int = 32
    embedding_provider: Literal["local", "openai", "azure"] = "local"

    # LLM Provider Configuration
    llm_provider: Literal["ollama", "openai", "anthropic", "azure"] = "ollama"
    llm_model: str = "llama2"
    llm_max_tokens: int = 1500
    llm_temperature: float = 0.7

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

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: str = ""

    # RAG Configuration
    retrieval_top_k: int = 10
    reranking_top_k: int = 5
    enable_reranking: bool = False
    conversation_history_token_limit: int = 2000
    system_prompt_token_limit: int = 200
    chunks_token_limit: int = 2500

    # Video Processing Limits
    max_video_duration_seconds: int = 14400  # 4 hours
    max_video_file_size_mb: int = 2048  # 2 GB
    cleanup_audio_after_transcription: bool = False

    # Usage Quotas
    free_tier_video_limit: int = 2
    free_tier_minutes_limit: int = 60
    free_tier_messages_limit: int = 50
    free_tier_storage_mb_limit: int = 1000

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Global settings instance
settings = Settings()
