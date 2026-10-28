"""
Teams and Agents API router.
"""
from __future__ import annotations

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.team import Team
from app.models.agent import Agent
from app.schemas.team import AgentDetail, AgentListItem, TeamDetail, TeamListItem

router = APIRouter(tags=["Teams & Agents"])


def _parse_json_list(val: str) -> list[str]:
    try:
        return json.loads(val)
    except Exception:
        return []


@router.get("/teams", response_model=List[TeamListItem])
def list_teams(db: Session = Depends(get_db)):
    """List all support teams with specializations."""
    teams = db.scalars(select(Team).options(selectinload(Team.agents))).all()
    return [
        TeamListItem(
            id=t.id,
            team_id=t.team_id,
            code=t.code,
            name=t.name,
            description=t.description,
            specializations=_parse_json_list(t.specializations),
            handles_priority=_parse_json_list(t.handles_priority),
            safety_capable=t.safety_capable,
            is_active=t.is_active,
            agent_count=len(t.agents),
            created_at=t.created_at,
        )
        for t in teams
    ]


@router.get("/teams/{team_id}", response_model=TeamDetail)
def get_team(team_id: str, db: Session = Depends(get_db)):
    """Get team by business ID or code."""
    query = select(Team).options(selectinload(Team.agents))
    if team_id.isdigit():
        t = db.scalar(query.where(Team.id == int(team_id)))
    else:
        t = db.scalar(query.where((Team.team_id == team_id) | (Team.code == team_id)))

    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found",
        )

    agents = [
        AgentListItem(
            id=a.id,
            agent_id=a.agent_id,
            team_id_fk=a.team_id_fk,
            team_code=t.code,
            team_name=t.name,
            name=a.name,
            email=a.email,
            role=a.role,
            is_active=a.is_active,
            max_concurrent_cases=a.max_concurrent_cases,
            open_complaint_count=a.open_complaint_count,
            created_at=a.created_at,
        )
        for a in t.agents
    ]

    return TeamDetail(
        id=t.id,
        team_id=t.team_id,
        code=t.code,
        name=t.name,
        description=t.description,
        specializations=_parse_json_list(t.specializations),
        handles_priority=_parse_json_list(t.handles_priority),
        safety_capable=t.safety_capable,
        is_active=t.is_active,
        agent_count=len(t.agents),
        created_at=t.created_at,
        agents=agents,
    )


@router.get("/agents", response_model=List[AgentListItem])
def list_agents(
    team_code: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List all agents across teams with current workload."""
    query = select(Agent).options(selectinload(Agent.team))

    if is_active is not None:
        query = query.where(Agent.is_active == is_active)
    if team_code:
        query = query.join(Agent.team).where(Team.code == team_code)

    agents = db.scalars(query).all()
    return [
        AgentListItem(
            id=a.id,
            agent_id=a.agent_id,
            team_id_fk=a.team_id_fk,
            team_code=a.team.code if a.team else None,
            team_name=a.team.name if a.team else None,
            name=a.name,
            email=a.email,
            role=a.role,
            is_active=a.is_active,
            max_concurrent_cases=a.max_concurrent_cases,
            open_complaint_count=a.open_complaint_count,
            created_at=a.created_at,
        )
        for a in agents
    ]


@router.get("/agents/{agent_id}", response_model=AgentDetail)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get single agent detail by ID."""
    query = select(Agent).options(selectinload(Agent.team))
    if agent_id.isdigit():
        a = db.scalar(query.where(Agent.id == int(agent_id)))
    else:
        a = db.scalar(query.where(Agent.agent_id == agent_id))

    if not a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    return AgentDetail(
        id=a.id,
        agent_id=a.agent_id,
        team_id_fk=a.team_id_fk,
        team_code=a.team.code if a.team else None,
        team_name=a.team.name if a.team else None,
        name=a.name,
        email=a.email,
        role=a.role,
        is_active=a.is_active,
        max_concurrent_cases=a.max_concurrent_cases,
        open_complaint_count=a.open_complaint_count,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )
