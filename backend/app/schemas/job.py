"""
Pydantic schemas for job tracking.
"""
from typing import Optional, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class JobStatus(BaseModel):
    """Job status response."""
    id: UUID
    job_type: str
    status: str = Field(..., description="Status: pending, running, completed, failed, canceled")
    progress_percent: float = Field(..., ge=0, le=100)
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    completed_steps: int = 0

    error_message: Optional[str] = None
    result: Optional[Dict] = None

    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    video_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class JobDetail(JobStatus):
    """Detailed job information."""
    user_id: UUID
    celery_task_id: Optional[str] = None
    retry_count: int
    max_retries: int

    class Config:
        from_attributes = True
