from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuotaStat(BaseModel):
    used: float
    limit: float
    remaining: float
    percentage: float


class StorageBreakdown(BaseModel):
    total_mb: float
    limit_mb: float
    remaining_mb: float
    percentage: float
    audio_mb: float
    transcript_mb: float
    disk_usage_mb: float


class UsageCounts(BaseModel):
    videos_total: int
    videos_completed: int
    videos_processing: int
    videos_failed: int
    transcripts: int
    chunks: int


class VectorStoreStat(BaseModel):
    collection_name: str
    total_points: int
    vectors_count: int
    indexed_vectors_count: int


class UsageSummary(BaseModel):
    period_start: datetime
    period_end: datetime
    videos: QuotaStat
    minutes: QuotaStat
    messages: QuotaStat
    storage_mb: QuotaStat
    storage_breakdown: StorageBreakdown
    counts: UsageCounts
    vector_store: Optional[VectorStoreStat] = None
