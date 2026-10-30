"""
Data generation API router.
"""
from __future__ import annotations

import json
import time
import threading
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.generator.orchestrator import DataGenerator
from app.generator.loader import load_all
from app.generator.ids import generation_run_id
from app.models.generation_run import GenerationRun
from app.exports.exporter import BaselineExporter
from app.schemas.generate import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/generate", tags=["Generation"])

_generation_lock = threading.Lock()


@router.post("", response_model=GenerateResponse)
def trigger_generation(
    request: GenerateRequest,
    db: Session = Depends(get_db),
):
    """Trigger synthetic dataset generation, persist to DB, and optionally update baseline exports."""
    # Guard against accidental destructive data resets in production
    if settings.app_env == "production" and request.clear_existing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Destructive dataset reset (clear_existing=True) is forbidden in production environment.",
        )

    if not _generation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A dataset generation task is already in progress. Please wait for it to complete.",
        )

    has_advisory_lock = False
    is_pg = False
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "postgresql":
            is_pg = True
    except Exception:
        pass

    try:
        if is_pg:
            # Atomic cluster-wide advisory lock for PostgreSQL (key 987654321)
            # Rejects concurrent workers across multiple instances before touching table state
            lock_res = db.execute(text("SELECT pg_try_advisory_lock(987654321)")).scalar()
            if not lock_res:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A dataset generation task is already in progress across active workers. Please wait for it to complete.",
                )
            has_advisory_lock = True

        # Cross-process concurrency check via database state:
        # 15-minute threshold ensures long-running full dataset generation jobs
        # are never prematurely treated as stale, while recovering from hard worker terminations.
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
        active_run = db.execute(
            select(GenerationRun).where(
                GenerationRun.status == "running",
                GenerationRun.started_at > stale_threshold,
            )
        ).scalars().first()

        if active_run:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A dataset generation task is already in progress across active workers. Please wait for it to complete.",
            )

        start_time = time.time()
        run_code = generation_run_id()

        # Create GenerationRun log
        run_log = GenerationRun(
            run_id=run_code,
            scale=request.scale,
            seed=request.seed,
            generator_version="1.0.0",
            config_version="1.0.0",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(run_log)
        db.commit()

        try:
            # 1. Generate data
            generator = DataGenerator(seed=request.seed, scale=request.scale)
            data = generator.generate_all()

            # 2. Persist to DB
            counts = load_all(db=db, data=data, clear_first=request.clear_existing)

            # When clearing database, also reset anomaly ground truth to prevent stale mismatch
            if request.clear_existing:
                from app.anomaly.detector import reset_anomalies
                reset_anomalies(db=db)

            # 3. Export baseline files if requested
            manifest_hash = None
            if request.export_baseline:
                exporter = BaselineExporter()
                manifest = exporter.export_and_create_manifest(
                    data=data,
                    seed=request.seed,
                    scale=request.scale,
                )
                manifest_hash = manifest.get("files", {}).get("json/summary.json", {}).get("sha256")

            duration = round(time.time() - start_time, 2)

            # Update run log
            run_log.status = "completed"
            run_log.customer_count = counts.get("customers", 0)
            run_log.product_count = counts.get("products", 0)
            run_log.order_count = counts.get("orders", 0)
            run_log.complaint_count = counts.get("complaints", 0)
            run_log.message_count = counts.get("messages", 0)
            run_log.team_count = counts.get("teams", 0)
            run_log.agent_count = counts.get("agents", 0)
            run_log.resolution_count = counts.get("resolutions", 0)
            run_log.survey_count = counts.get("surveys", 0)
            run_log.checksums = json.dumps({"summary_sha256": manifest_hash}) if manifest_hash else None
            run_log.completed_at = datetime.now(timezone.utc)
            db.commit()

            return GenerateResponse(
                status="success",
                run_id=run_code,
                seed=request.seed,
                scale=request.scale,
                duration_seconds=duration,
                counts=counts,
                message=f"Generated and loaded dataset at scale '{request.scale}' with seed {request.seed} in {duration}s",
                manifest_checksum=manifest_hash,
            )

        except Exception as e:
            db.rollback()
            try:
                failed_run = db.execute(
                    select(GenerationRun).where(GenerationRun.run_id == run_code)
                ).scalars().first()
                if failed_run:
                    failed_run.status = "failed"
                    failed_run.error_message = str(e)
                    failed_run.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Generation failed: {str(e)}",
            )
    finally:
        if has_advisory_lock and is_pg:
            try:
                db.execute(text("SELECT pg_advisory_unlock(987654321)"))
            except Exception:
                pass
        if _generation_lock.locked():
            _generation_lock.release()
