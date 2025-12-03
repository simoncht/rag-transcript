"""
Celery application configuration.

Handles background tasks for:
- Video download
- Transcription
- Chunking and enrichment
- Embedding and indexing
"""
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "rag_transcript",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.video_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Take one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Requeue task if worker dies
)

# Task routes (assign tasks to specific queues)
celery_app.conf.task_routes = {
    "app.tasks.video_tasks.*": {"queue": "celery"},
}


@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Handler called before task execution."""
    print(f"Task starting: {task.name} (ID: {task_id})")


@task_postrun.connect
def task_postrun_handler(task_id, task, *args, retval=None, **kwargs):
    """Handler called after task execution."""
    print(f"Task completed: {task.name} (ID: {task_id})")


@task_failure.connect
def task_failure_handler(task_id, exception, *args, **kwargs):
    """Handler called on task failure."""
    print(f"Task failed: {task_id}, Exception: {str(exception)}")
