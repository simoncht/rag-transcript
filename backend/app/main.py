"""
FastAPI main application.

Handles:
- Application initialization
- Middleware configuration
- Route mounting
- CORS setup
- Startup/shutdown events
"""
# IMPORTANT: Import SSL patch FIRST to bypass corporate SSL interception
from app.core import ssl_patch  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.api.routes import videos, jobs, conversations, collections, usage, auth, insights, admin

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "environment": settings.environment
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
        "health": "/health"
    }


# Mount API routes
app.include_router(
    videos.router,
    prefix=f"{settings.api_v1_prefix}/videos",
    tags=["videos"]
)

app.include_router(
    jobs.router,
    prefix=f"{settings.api_v1_prefix}/jobs",
    tags=["jobs"]
)

app.include_router(
    conversations.router,
    prefix=f"{settings.api_v1_prefix}/conversations",
    tags=["conversations"]
)

app.include_router(
    insights.router,
    prefix=f"{settings.api_v1_prefix}/conversations",
    tags=["insights"]
)

app.include_router(
    collections.router,
    prefix=f"{settings.api_v1_prefix}/collections",
    tags=["collections"]
)

app.include_router(
    usage.router,
    prefix=f"{settings.api_v1_prefix}/usage",
    tags=["usage"]
)

app.include_router(
    auth.router,
    prefix=f"{settings.api_v1_prefix}/auth",
    tags=["auth"]
)

app.include_router(
    admin.router,
    prefix=f"{settings.api_v1_prefix}/admin",
    tags=["admin"]
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Uncaught exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
