"""
API v1 router aggregating all modular sub-routers.
"""
from fastapi import APIRouter

from app.api.v1.complaints import router as complaints_router
from app.api.v1.customers import router as customers_router
from app.api.v1.products import router as products_router
from app.api.v1.teams import router as teams_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.generate import router as generate_router
from app.api.v1.anomalies import router as anomalies_router
from app.api.v1.validate import router as validate_router
from app.api.v1.reports import router as reports_router
from app.api.v1.ingestion import router as ingestion_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(complaints_router)
api_router.include_router(customers_router)
api_router.include_router(products_router)
api_router.include_router(teams_router)
api_router.include_router(dashboard_router)
api_router.include_router(generate_router)
api_router.include_router(anomalies_router)
api_router.include_router(validate_router)
api_router.include_router(reports_router)
api_router.include_router(ingestion_router)

__all__ = ["api_router"]
