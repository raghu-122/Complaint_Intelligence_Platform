"""
Team and Agent Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.common import BaseSchema


class AgentListItem(BaseSchema):
    id: int
    agent_id: str
    team_id_fk: int
    team_code: Optional[str] = None
    team_name: Optional[str] = None
    name: str
    email: str
    role: str
    is_active: bool
    max_concurrent_cases: int
    open_complaint_count: int
    created_at: datetime


class AgentDetail(AgentListItem):
    updated_at: datetime


class TeamListItem(BaseSchema):
    id: int
    team_id: str
    code: str
    name: str
    description: Optional[str] = None
    specializations: List[str] = []
    handles_priority: List[str] = []
    safety_capable: bool
    is_active: bool
    agent_count: int = 0
    created_at: datetime


class TeamDetail(TeamListItem):
    agents: List[AgentListItem] = []
