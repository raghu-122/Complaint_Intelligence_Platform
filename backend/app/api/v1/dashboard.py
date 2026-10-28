"""
Dashboard analytics API router.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.complaint import Complaint
from app.models.customer import Customer
from app.models.order import Order
from app.models.agent import Agent
from app.models.sla import SLAClock
from app.models.survey import Survey
from app.models.category import Category
from app.schemas.dashboard import (
    BreakdownItem, ChartData, DashboardStats, SLAStats, TrendItem,
    SLAPriorityItem, DailyTrendItem
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Summary KPI metrics for executive and operational dashboards."""
    total_complaints = db.scalar(select(func.count(Complaint.id))) or 0
    open_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.status == "open")) or 0
    in_progress_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.status == "in_progress")) or 0
    resolved_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.status.in_(["resolved", "closed"]))) or 0
    closed_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.status == "closed")) or 0
    escalated_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.is_escalated == True)) or 0
    reopened_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.is_reopened == True)) or 0
    p1_complaints = db.scalar(select(func.count(Complaint.id)).where(Complaint.priority == "P1")) or 0
    safety_incidents = db.scalar(select(func.count(Complaint.id)).where(Complaint.is_safety_incident == True)) or 0

    # SLA stats
    total_sla = db.scalar(select(func.count(SLAClock.id))) or 0
    breached_sla = db.scalar(select(func.count(SLAClock.id)).where(SLAClock.is_breached == True)) or 0
    compliance_rate = round(((total_sla - breached_sla) / total_sla) * 100, 1) if total_sla > 0 else 100.0

    # Resolution time calculation
    # In SQLite, julianday(resolved_at) - julianday(created_at) * 24
    resolved_times = db.execute(
        select(Complaint.created_at, Complaint.resolved_at).where(Complaint.resolved_at.is_not(None))
    ).all()
    avg_hours = 0.0
    if resolved_times:
        hours_list = []
        for c, r in resolved_times:
            if c and r:
                c_clean = c.replace(tzinfo=None) if c.tzinfo else c
                r_clean = r.replace(tzinfo=None) if r.tzinfo else r
                hours_list.append(max(0.0, (r_clean - c_clean).total_seconds() / 3600))
        if hours_list:
            avg_hours = round(sum(hours_list) / len(hours_list), 1)

    # CSAT average rating
    avg_csat = db.scalar(select(func.avg(Survey.rating)))
    csat_score = round(float(avg_csat), 2) if avg_csat is not None else 0.0

    total_customers = db.scalar(select(func.count(Customer.id))) or 0
    total_orders = db.scalar(select(func.count(Order.id))) or 0
    vuln_customers = db.scalar(select(func.count(Customer.id)).where(Customer.vulnerability_flag == True)) or 0
    active_agents = db.scalar(select(func.count(Agent.id)).where(Agent.is_active == True)) or 0

    return DashboardStats(
        total_complaints=total_complaints,
        open_complaints=open_complaints,
        in_progress_complaints=in_progress_complaints,
        resolved_complaints=resolved_complaints,
        closed_complaints=closed_complaints,
        escalated_complaints=escalated_complaints,
        reopened_complaints=reopened_complaints,
        p1_complaints=p1_complaints,
        safety_incidents=safety_incidents,
        sla_breached_count=breached_sla,
        sla_compliance_rate=compliance_rate,
        avg_resolution_time_hours=avg_hours,
        csat_average=csat_score,
        total_customers=total_customers,
        total_orders=total_orders,
        vulnerable_customers_count=vuln_customers,
        active_agents_count=active_agents,
    )


@router.get("/charts", response_model=ChartData)
def get_dashboard_charts(db: Session = Depends(get_db)):
    """Chart breakdown data across category, priority, status, SLA, and timelines."""
    total = db.scalar(select(func.count(Complaint.id))) or 1

    # Category breakdown
    cat_query = select(Complaint.category_code, func.count(Complaint.id)).group_by(Complaint.category_code)
    cat_rows = db.execute(cat_query).all()
    cat_names = {c.code: c.name for c in db.scalars(select(Category)).all()}

    cat_breakdown = [
        BreakdownItem(
            code=code or "UNKNOWN",
            name=cat_names.get(code, code or "Unknown"),
            count=count,
            value=count,
            percentage=round((count / total) * 100, 1),
        )
        for code, count in sorted(cat_rows, key=lambda x: x[1], reverse=True)
    ]

    # Priority breakdown
    pri_query = select(Complaint.priority, func.count(Complaint.id)).group_by(Complaint.priority)
    pri_rows = db.execute(pri_query).all()
    pri_order = ["P1", "P2", "P3", "P4"]
    pri_dict = {p: c for p, c in pri_rows}
    pri_breakdown = [
        BreakdownItem(
            name=p,
            code=p,
            count=pri_dict.get(p, 0),
            value=pri_dict.get(p, 0),
            percentage=round((pri_dict.get(p, 0) / total) * 100, 1),
        )
        for p in pri_order
    ]

    # Status breakdown
    st_query = select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)
    st_rows = db.execute(st_query).all()
    status_breakdown = [
        BreakdownItem(
            name=status.replace("_", " ").title(),
            code=status,
            count=count,
            value=count,
            percentage=round((count / total) * 100, 1),
        )
        for status, count in st_rows
    ]

    # Channel breakdown
    ch_query = select(Complaint.channel, func.count(Complaint.id)).group_by(Complaint.channel)
    ch_rows = db.execute(ch_query).all()
    channel_breakdown = [
        BreakdownItem(
            name=ch.replace("_", " ").title(),
            code=ch,
            count=count,
            value=count,
            percentage=round((count / total) * 100, 1),
        )
        for ch, count in ch_rows
    ]

    # Sentiment breakdown
    snt_query = select(Complaint.sentiment, func.count(Complaint.id)).group_by(Complaint.sentiment)
    snt_rows = db.execute(snt_query).all()
    sentiment_breakdown = [
        BreakdownItem(
            name=snt.title(),
            code=snt,
            count=count,
            value=count,
            percentage=round((count / total) * 100, 1),
        )
        for snt, count in snt_rows
    ]

    # SLA stats - overall aggregate
    total_clocks = db.scalar(select(func.count(SLAClock.id))) or 0
    breached_count = db.scalar(select(func.count(SLAClock.id)).where(SLAClock.is_breached == True)) or 0
    completed_count = db.scalar(select(func.count(SLAClock.id)).where(SLAClock.status == "completed")) or 0
    running_count = db.scalar(select(func.count(SLAClock.id)).where(SLAClock.status == "running")) or 0
    compliance_rate = round(((total_clocks - breached_count) / total_clocks) * 100, 1) if total_clocks > 0 else 100.0

    sla_overview = SLAStats(
        total_clocks=total_clocks,
        breached_count=breached_count,
        completed_count=completed_count,
        running_count=running_count,
        compliance_rate=compliance_rate,
        avg_resolution_hours=round(
            float(db.scalar(select(func.avg(SLAClock.resolution_hours))) or 0.0), 1
        ),
    )

    # SLA compliance broken down by priority tier for dashboard table
    pri_sla_query = select(
        SLAClock.priority,
        func.count(SLAClock.id),
        func.sum(case((SLAClock.is_breached == True, 1), else_=0)),
    ).group_by(SLAClock.priority)
    pri_sla_rows = db.execute(pri_sla_query).all()
    sla_map = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in pri_sla_rows}
    sla_priority_list = []
    for p in pri_order:
        tot, brch = sla_map.get(p, (0, 0))
        pct = round(((tot - brch) / tot) * 100, 1) if tot > 0 else 100.0
        sla_priority_list.append(
            SLAPriorityItem(
                priority=p,
                total=tot,
                breached=brch,
                compliance_pct=pct,
            )
        )

    # Monthly trends
    trend_query = select(
        func.strftime("%Y-%m", Complaint.created_at).label("month"),
        func.count(Complaint.id).label("total"),
        func.sum(case((Complaint.status.in_(["resolved", "closed"]), 1), else_=0)).label("resolved"),
    ).group_by("month").order_by("month")

    trend_rows = db.execute(trend_query).all()
    monthly_trends = [
        TrendItem(
            period=str(row[0] or "N/A"),
            total=int(row[1] or 0),
            resolved=int(row[2] or 0),
            breached=0,
        )
        for row in trend_rows
    ]

    # Daily trends (last 30 active days for line chart)
    daily_query = select(
        func.strftime("%Y-%m-%d", Complaint.created_at).label("dt"),
        func.count(Complaint.id).label("total"),
    ).group_by("dt").order_by("dt")
    daily_rows = db.execute(daily_query).all()
    daily_trends = [
        DailyTrendItem(date=str(r[0] or "N/A"), count=int(r[1] or 0))
        for r in daily_rows[-30:]
    ]

    return ChartData(
        category_breakdown=cat_breakdown,
        priority_breakdown=pri_breakdown,
        status_breakdown=status_breakdown,
        channel_breakdown=channel_breakdown,
        sentiment_breakdown=sentiment_breakdown,
        sla_stats=sla_priority_list,
        sla_overview=sla_overview,
        monthly_trends=monthly_trends,
        daily_trends=daily_trends,
    )
