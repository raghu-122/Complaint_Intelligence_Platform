"""
Main FastAPI application for YottaFlex Complaint Intelligence Platform.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — runs startup and shutdown tasks."""
    # Initialize database tables on startup
    init_db()
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Automated Complaint Classification, Priority Triage, SLA Monitoring, and Intelligence API",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router)


@app.get("/health", tags=["System"])
def health_check():
    """Health status and service metadata."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["System"])
def root():
    """Root redirect / information endpoint."""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1_base": "/api/v1",
    }
