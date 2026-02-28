"""
Pydantic schemas for universal content (document upload) API endpoints.
"""
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


# Supported content types (excluding 'youtube' which uses video endpoints)
DOCUMENT_CONTENT_TYPES = [
    "pdf", "docx", "pptx", "xlsx", "txt", "md", "html", "epub", "csv", "rtf", "email",
]

# File extension to content_type mapping
EXTENSION_TO_CONTENT_TYPE = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
    ".html": "html",
    ".htm": "html",
    ".epub": "epub",
    ".csv": "csv",
    ".rtf": "rtf",
    ".eml": "email",
    ".msg": "email",
}


# Request schemas
class ContentUploadResponse(BaseModel):
    """Response from content upload."""

    content_id: UUID
    status: str
    content_type: str
    title: str
    original_filename: str
    file_size_bytes: int
    message: str
    warning: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "content_type": "pdf",
                "title": "Research Paper.pdf",
                "original_filename": "Research Paper.pdf",
                "file_size_bytes": 1048576,
                "message": "Document upload started. Processing will begin shortly.",
            }
        }


class ContentDetail(BaseModel):
    """Detailed content information."""

    id: UUID
    user_id: UUID
    content_type: str
    title: str
    description: Optional[str] = None

    # Document-specific
    original_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    source_url: Optional[str] = None
    page_count: Optional[int] = None
    source_metadata: Optional[Dict] = None

    # Processing
    status: str
    progress_percent: float
    error_message: Optional[str] = None

    # Enrichment progress
    chunks_enriched: Optional[int] = None
    total_chunks: Optional[int] = None
    eta_seconds: Optional[int] = None
    is_active: bool = True
    activity_status: Optional[str] = None
    seconds_since_update: Optional[int] = None
    processing_rate: Optional[float] = None

    # Stats
    chunk_count: int = 0
    summary: Optional[str] = None
    key_topics: Optional[List[str]] = None

    # Storage
    storage_total_mb: Optional[float] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContentList(BaseModel):
    """List of content items."""

    total: int
    items: List[ContentDetail]


class ContentDeleteResponse(BaseModel):
    """Response from content deletion."""

    deleted_count: int
    total_savings_mb: float
    message: str


class ContentStatusUpdate(BaseModel):
    """Status of a content item (for polling)."""

    id: UUID
    status: str
    progress_percent: float
    error_message: Optional[str] = None
    chunk_count: int = 0
    completed_at: Optional[datetime] = None

    # Enrichment progress
    chunks_enriched: Optional[int] = None
    total_chunks: Optional[int] = None
    eta_seconds: Optional[int] = None
    is_active: bool = True
    activity_status: Optional[str] = None
    seconds_since_update: Optional[int] = None
    processing_rate: Optional[float] = None

    class Config:
        from_attributes = True
