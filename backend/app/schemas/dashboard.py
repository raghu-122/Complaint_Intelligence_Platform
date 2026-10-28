"""
Dashboard stats and chart schemas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class BreakdownItem(BaseModel):
    name: str
    code: Optional[str] = None
    count: int
    value: int = 0
    percentage: float = 0.0


class TrendItem(BaseModel):
    period: str
    total: int
    resolved: int = 0
    breached: int = 0


class DailyTrendItem(BaseModel):
    date: str
    count: int


class SLAPriorityItem(BaseModel):
    priority: str
    total: int
    breached: int
    compliance_pct: float


class SLAStats(BaseModel):
    total_clocks: int
    breached_count: int
    completed_count: int
    running_count: int
    compliance_rate: float
    avg_resolution_hours: float


class DashboardStats(BaseModel):
    total_complaints: int
    open_complaints: int
    in_progress_complaints: int
    resolved_complaints: int
    closed_complaints: int
    escalated_complaints: int
    reopened_complaints: int
    p1_complaints: int
    safety_incidents: int
    sla_breached_count: int
    sla_compliance_rate: float
    avg_resolution_time_hours: float
    csat_average: float
    total_customers: int
    total_orders: int
    vulnerable_customers_count: int
    active_agents_count: int


class ChartData(BaseModel):
    category_breakdown: List[BreakdownItem]
    priority_breakdown: List[BreakdownItem]
    status_breakdown: List[BreakdownItem]
    channel_breakdown: List[BreakdownItem]
    sentiment_breakdown: List[BreakdownItem]
    sla_stats: List[SLAPriorityItem]
    sla_overview: Optional[SLAStats] = None
    monthly_trends: List[TrendItem]
    daily_trends: List[DailyTrendItem] = []
