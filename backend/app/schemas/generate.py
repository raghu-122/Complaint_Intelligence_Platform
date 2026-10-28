"""
Data generation request and response schemas.
"""
from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    seed: int = Field(default=20261022, description="Random seed for reproducible generation")
    scale: str = Field(default="starter", description="'starter' (~50 complaints) or 'full' (~2000 complaints)")
    clear_existing: bool = Field(default=True, description="Clear existing tables before loading")
    export_baseline: bool = Field(default=True, description="Export CSV/JSON baseline files and manifest")


class GenerateResponse(BaseModel):
    status: str
    run_id: str
    seed: int
    scale: str
    duration_seconds: float
    counts: Dict[str, int]
    message: str
    manifest_checksum: Optional[str] = None
