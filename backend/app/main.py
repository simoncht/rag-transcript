"""
FastAPI main application.

Handles:
- Application initialization
- Middleware configuration
- Route mounting
- CORS setup
- Startup/shutdown events
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.rate_limit import (
    limiter,
    rate_limit_exception,
    rate_limit_handler,
)
from app.api.routes import (
    videos,
    jobs,
    conversations,
    collections,
    usage,
    auth,
    insights,
    admin,
    webhooks,
    subscriptions,
)

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="RAG-powered YouTube video transcript system with semantic search and contextual chat",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Register rate limiter
app.state.limiter = limiter
app.add_exception_handler(rate_limit_exception, rate_limit_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize vector store
    try:
        from app.services.vector_store import vector_store_service
        from app.services.embeddings import embedding_service

        vector_store_service.initialize(embedding_service.get_dimensions())
        logger.info("Vector store initialized")
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {str(e)}")

    # Backfill fact scores for existing facts (one-time migration, safe to re-run)
    try:
        from app.db.base import SessionLocal
        from app.services.fact_extraction import backfill_fact_scores

        db = SessionLocal()
        try:
            updated = backfill_fact_scores(db)
            if updated > 0:
                logger.info(f"Backfilled importance/category for {updated} facts")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Fact backfill skipped: {str(e)}")

    logger.info("Application startup complete")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
        "health": "/health",
    }


# Mount API routes
app.include_router(
    videos.router, prefix=f"{settings.api_v1_prefix}/videos", tags=["videos"]
)

app.include_router(jobs.router, prefix=f"{settings.api_v1_prefix}/jobs", tags=["jobs"])

app.include_router(
    conversations.router,
    prefix=f"{settings.api_v1_prefix}/conversations",
    tags=["conversations"],
)

app.include_router(
    insights.router, prefix=f"{settings.api_v1_prefix}/conversations", tags=["insights"]
)

app.include_router(
    collections.router,
    prefix=f"{settings.api_v1_prefix}/collections",
    tags=["collections"],
)

app.include_router(
    usage.router, prefix=f"{settings.api_v1_prefix}/usage", tags=["usage"]
)

app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])

app.include_router(
    admin.router, prefix=f"{settings.api_v1_prefix}/admin", tags=["admin"]
)

app.include_router(
    webhooks.router, prefix=f"{settings.api_v1_prefix}/webhooks", tags=["webhooks"]
)

app.include_router(
    subscriptions.router, prefix=f"{settings.api_v1_prefix}/subscriptions", tags=["subscriptions"]
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Uncaught exception: {str(exc)}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
