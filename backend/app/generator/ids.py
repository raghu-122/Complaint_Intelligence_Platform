"""
Deterministic ID generation for all entity types.

ID conventions:
- Customers: CUS-000001
- Orders: ORD-2026-000001
- Complaints: CMP-2026-000001
- Messages: MSG-CMP-2026-000001-001
- SLA clocks: SLA-CMP-2026-000001
- Resolutions: RES-CMP-2026-000001
- Products: PRD-000001
- Agents: AGT-000001
- Teams: TM-001
- Surveys: SRV-CMP-2026-000001
- Assignments: ASN-CMP-2026-000001-001
- Runs: GEN-RUN-000001
"""
from __future__ import annotations


REFERENCE_YEAR = "2026"


def customer_id(n: int) -> str:
    """CUS-000001"""
    return f"CUS-{n:06d}"


def product_id(n: int) -> str:
    """PRD-000001"""
    return f"PRD-{n:06d}"


def order_id(n: int, year: str = REFERENCE_YEAR) -> str:
    """ORD-2026-000001"""
    return f"ORD-{year}-{n:06d}"


def complaint_id(n: int, year: str = REFERENCE_YEAR) -> str:
    """CMP-2026-000001"""
    return f"CMP-{year}-{n:06d}"


def message_id(complaint_num: int, message_seq: int, year: str = REFERENCE_YEAR) -> str:
    """MSG-CMP-2026-000001-001"""
    return f"MSG-CMP-{year}-{complaint_num:06d}-{message_seq:03d}"


def sla_id(complaint_num: int, year: str = REFERENCE_YEAR) -> str:
    """SLA-CMP-2026-000001"""
    return f"SLA-CMP-{year}-{complaint_num:06d}"


def resolution_id(complaint_num: int, year: str = REFERENCE_YEAR) -> str:
    """RES-CMP-2026-000001"""
    return f"RES-CMP-{year}-{complaint_num:06d}"


def survey_id(complaint_num: int, year: str = REFERENCE_YEAR) -> str:
    """SRV-CMP-2026-000001"""
    return f"SRV-CMP-{year}-{complaint_num:06d}"


def agent_id(n: int) -> str:
    """AGT-000001"""
    return f"AGT-{n:06d}"


def team_id(n: int) -> str:
    """TM-001"""
    return f"TM-{n:03d}"


def assignment_id(complaint_num: int, seq: int, year: str = REFERENCE_YEAR) -> str:
    """ASN-CMP-2026-000001-001"""
    return f"ASN-CMP-{year}-{complaint_num:06d}-{seq:03d}"


def generation_run_id(n: int | None = None) -> str:
    """GEN-RUN-000001"""
    if n is None:
        import time
        return f"GEN-RUN-{int(time.time() * 1000) % 1000000:06d}"
    return f"GEN-RUN-{n:06d}"


def sku(product_num: int, category: str) -> str:
    """SKU: e.g. SKU-ELEC-000001"""
    prefix = category[:4].upper().replace(" ", "")
    return f"SKU-{prefix}-{product_num:06d}"


def anomaly_id(scenario: int, n: int) -> str:
    """ANM-SCN001-001"""
    return f"ANM-SCN{scenario:03d}-{n:03d}"
