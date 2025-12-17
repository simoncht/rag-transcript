"""
API endpoints for job tracking.

Endpoints:
- GET /jobs/{job_id} - Get job status
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models import Job, User
from app.schemas import JobDetail

router = APIRouter()


@router.get("/{job_id}", response_model=JobDetail)
async def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get job status and progress.

    Use this endpoint to poll for job updates during video processing.

    Args:
        job_id: Job UUID

    Returns:
        JobDetail with current status and progress
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobDetail.model_validate(job)
