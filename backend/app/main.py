"""
Main FastAPI application for YottaFlex Complaint Intelligence Platform.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import init_db, get_db
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
    expose_headers=["Content-Disposition", "X-Checksum-SHA256"],
)

# Mount API routers
app.include_router(api_router)


@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Health status and service metadata with database dialect diagnostics."""
    db_status = "connected"
    db_dialect = "unknown"
    try:
        bind = db.get_bind()
        if bind:
            db_dialect = bind.dialect.name
            db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    commit_sha = os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", settings.app_version))

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "commit_sha": commit_sha,
        "database": {
            "status": db_status,
            "dialect": db_dialect,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["System"])
def root(db: Session = Depends(get_db)):
    """Root redirect / information endpoint."""
    db_dialect = "unknown"
    try:
        bind = db.get_bind()
        if bind:
            db_dialect = bind.dialect.name
    except Exception:
        pass

    commit_sha = os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", settings.app_version))

    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "commit_sha": commit_sha,
        "database_dialect": db_dialect,
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1_base": "/api/v1",
    }
