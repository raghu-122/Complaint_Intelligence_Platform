"""
Pydantic schemas package.
"""
from app.schemas.common import BaseSchema, MessageResponse, PaginatedResponse
from app.schemas.complaint import (
    ComplaintListItem, ComplaintDetail, ComplaintFilter,
    ComplaintStatusEventSchema, ComplaintMessageSchema, AssignmentSchema,
    SLAClockSchema, ResolutionSchema, SurveySchema, ComplaintRelationshipSchema
)
from app.schemas.customer import CustomerListItem, CustomerDetail, CustomerOrderSummary, CustomerComplaintSummary
from app.schemas.product import ProductListItem, ProductDetail
from app.schemas.team import TeamListItem, TeamDetail, AgentListItem, AgentDetail
from app.schemas.dashboard import DashboardStats, ChartData, BreakdownItem, TrendItem, SLAStats
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.schemas.validation import ValidationReport, ValidationFinding, ValidationSummary
from app.schemas.anomaly import (
    AnomalyItem, AnomalyDetectionResult, InjectAnomalyRequest, InjectAnomalyResponse
)
from app.schemas.report import ReportListItem, ReportListResponse

__all__ = [
    "BaseSchema",
    "MessageResponse",
    "PaginatedResponse",
    "ComplaintListItem",
    "ComplaintDetail",
    "ComplaintFilter",
    "ComplaintStatusEventSchema",
    "ComplaintMessageSchema",
    "AssignmentSchema",
    "SLAClockSchema",
    "ResolutionSchema",
    "SurveySchema",
    "ComplaintRelationshipSchema",
    "CustomerListItem",
    "CustomerDetail",
    "CustomerOrderSummary",
    "CustomerComplaintSummary",
    "ProductListItem",
    "ProductDetail",
    "TeamListItem",
    "TeamDetail",
    "AgentListItem",
    "AgentDetail",
    "DashboardStats",
    "ChartData",
    "BreakdownItem",
    "TrendItem",
    "SLAStats",
    "GenerateRequest",
    "GenerateResponse",
    "ValidationReport",
    "ValidationFinding",
    "ValidationSummary",
    "AnomalyItem",
    "AnomalyDetectionResult",
    "InjectAnomalyRequest",
    "InjectAnomalyResponse",
    "ReportListItem",
    "ReportListResponse",
]
