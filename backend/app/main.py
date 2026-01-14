"""
FastAPI Application Entry Point
Main application configuration and router setup.
"""
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Configure CORS
# Use configured origins if available, otherwise allow all (development only)
cors_origins = settings.BACKEND_CORS_ORIGINS if settings.BACKEND_CORS_ORIGINS else ["*"]

logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "Data Intelligence Platform API", "status": "healthy"}


@app.get("/health")
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "ollama_url": settings.OLLAMA_BASE_URL,
        "chat_model": settings.OLLAMA_CHAT_MODEL,
    }


# Import and include routers
from app.api.endpoints import chat, upload, relationships, history

app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["Chat"])
app.include_router(upload.router, prefix=settings.API_V1_STR, tags=["Upload"])
app.include_router(relationships.router, prefix=settings.API_V1_STR, tags=["Relationships"])
app.include_router(history.router, prefix=f"{settings.API_V1_STR}/history", tags=["History"])

logger.info(f"Application '{settings.PROJECT_NAME}' started successfully")
