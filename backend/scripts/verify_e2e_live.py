"""
End-to-end verification script for YottaFlex Complaint Intelligence Platform.

Self-contained: injects anomalies into an isolated copy of the production DB,
exercises all 12 critical API workflows, then cleans up the temp DB.

Usage:
    python scripts/verify_e2e_live.py [--run-n N]

Design:
- Creates a temp DB copy, injects anomalies, runs API server against the temp DB.
- Never modifies the canonical baseline database.
- Fully repeatable — second run produces the same results.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parent.parent
CANONICAL_DB = BACKEND_DIR / "complaint_intelligence.db"
# Use port 8001 to avoid conflicts with any development server running on 8000
API_URL = "http://127.0.0.1:8001"


def wait_for_server(max_wait=25):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            req = urllib.request.Request(f"{API_URL}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def http_get(path):
    req = urllib.request.Request(f"{API_URL}{path}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_patch(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_tests(run_n=1):
    print("=" * 60)
    print(f"YottaFlex E2E Verification  (Run #{run_n})")
    print("=" * 60)

    passed = 0
    failed = 0

    def ok(label, msg):
        nonlocal passed
        passed += 1
        print(f"  [PASS] {label}: {msg}")

    def fail(label, msg):
        nonlocal failed
        failed += 1
        print(f"  [FAIL] {label}: {msg}")
        raise AssertionError(msg)

    # 1. Health check
    h = http_get("/health")
    assert h["status"] in ("ok", "healthy"), f"Health check failed: {h}"
    ok("E2E-01", f"Health check passed (/health -> {h['status']})")

    # 2. Dashboard KPIs
    stats = http_get("/api/v1/dashboard/stats")
    assert "total_complaints" in stats
    assert stats["total_complaints"] >= 2000, f"Expected >=2000, got {stats['total_complaints']}"
    ok("E2E-02", f"Dashboard stats loaded (total_complaints={stats['total_complaints']:,})")

    # 3. Dashboard charts
    charts = http_get("/api/v1/dashboard/charts")
    assert "priority_breakdown" in charts, "priority_breakdown missing"
    assert "status_breakdown" in charts, "status_breakdown missing"
    ok("E2E-03", "Dashboard charts data loaded (priority and status breakdowns present)")

    # 4. Create new complaint (Safety incident)
    created = http_post("/api/v1/complaints", {
        "customer_id": 1,
        "title": "Severe battery smoke and fire hazard reported",
        "description": "The device battery overheated and emitted visible smoke and chemical odor.",
        "channel": "phone",
        "is_safety_incident": True,
    })
    new_cid = created["complaint_id"]
    assert new_cid.startswith("CMP-"), f"Unexpected complaint_id: {new_cid}"
    assert created["priority"] == "P1", f"Expected P1 for safety incident, got {created['priority']}"
    assert created["is_safety_incident"] is True
    ok("E2E-04", f"Created complaint {new_cid} — auto-classified P1 Safety Incident")

    # 5. Fetch complaint detail with nested objects
    detail = http_get(f"/api/v1/complaints/{new_cid}")
    assert detail["complaint_id"] == new_cid
    assert detail["customer"] is not None, "customer nested object missing"
    assert detail["sla_clock"] is not None, "sla_clock nested object missing"
    assert detail["current_assignment"] is not None, "current_assignment nested object missing"
    ok("E2E-05", f"Retrieved complaint detail with nested customer, SLA clock, and assignment")

    # 6. Post customer message
    msg = http_post(f"/api/v1/complaints/{new_cid}/messages", {
        "sender_type": "customer",
        "sender_id": "CUST-000001",
        "body": "Can someone please expedite this? The unit is completely unusable.",
        "channel": "phone",
    })
    assert msg["body"].startswith("Can someone"), f"Unexpected body: {msg['body']}"
    ok("E2E-06", f"Added customer interaction message to complaint {new_cid}")

    # 7. Escalate complaint via PATCH
    updated = http_patch(f"/api/v1/complaints/{new_cid}", {
        "status": "escalated",
        "notes": "Escalated to Executive Squad per customer safety protocol",
    })
    assert updated["status"] == "escalated", f"Expected 'escalated', got {updated['status']}"
    ok("E2E-07", f"Escalated complaint {new_cid} to status 'escalated'")

    # 8. Anomaly detection — anomalies injected into isolated DB before test
    anom = http_get("/api/v1/anomalies/detect")
    assert anom["detected_count"] >= 6, f"Expected >=6 detected anomalies, got {anom['detected_count']}"
    assert anom["precision"] == 1.0, f"Expected precision=1.0, got {anom['precision']}"
    ok("E2E-08", f"Anomaly detection verified (Detected={anom['detected_count']}, Precision={anom['precision']:.0%})")

    # 9. Validation endpoint
    val = http_post("/api/v1/validate", {})
    assert val["summary"]["total"] >= 15, f"Expected >=15 checks, got {val['summary']['total']}"
    ok("E2E-09", f"Data validation engine passed ({val['summary']['passed']}/{val['summary']['total']} checks, "
       f"{val['summary']['warned']} warnings)")

    # 10. Vulnerable customer filtering
    vulnerable_custs = http_get("/api/v1/customers?vulnerable_only=true")
    assert len(vulnerable_custs["items"]) > 0, "No vulnerable customers found"
    ok("E2E-10", f"Vulnerable customer filter verified ({len(vulnerable_custs['items'])} found)")

    # 11. Safety complaint filtering
    safety_comps = http_get("/api/v1/complaints?safety_only=true")
    assert len(safety_comps["items"]) > 0, "No safety complaints found"
    ok("E2E-11", f"Safety complaint filter verified ({len(safety_comps['items'])} found)")

    # 12. Baseline manifest report
    manifest_rep = http_get("/api/v1/reports/baseline-manifest")
    assert "files" in manifest_rep, "'files' key missing from manifest report"
    assert manifest_rep.get("scale") == "full", f"Expected scale='full', got {manifest_rep.get('scale')}"
    ok("E2E-12", f"Baseline manifest report verified ({len(manifest_rep['files'])} files, scale={manifest_rep['scale']})")

    print()
    print("=" * 60)
    print(f"E2E RESULT (Run #{run_n}): {passed} PASSED | {failed} FAILED")
    if failed == 0:
        print("ALL E2E WORKFLOW CHECKS PASSED")
    print("=" * 60)
    return failed == 0


def prepare_isolated_db(temp_dir: Path) -> Path:
    """Copy canonical DB to isolated temp path, inject anomalies, return path."""
    test_db = temp_dir / "e2e_test.db"
    shutil.copy2(CANONICAL_DB, test_db)
    print(f"  [setup] Copied canonical DB ({CANONICAL_DB.stat().st_size // 1024:,} KB) to {test_db.name}")

    # Inject anomalies via SQLAlchemy against the isolated copy
    sys.path.insert(0, str(BACKEND_DIR))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.anomaly.detector import inject_anomalies

    engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine)
    with Session() as session:
        result = inject_anomalies(session, count=6)
        session.commit()
    print(f"  [setup] Injected {result.injected_count} anomaly records into isolated DB.")
    return test_db


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YottaFlex E2E Live Verification")
    parser.add_argument("--run-n", type=int, default=1, help="Run number label (for repeated runs)")
    args = parser.parse_args()

    if not CANONICAL_DB.exists():
        print(f"ERROR: Canonical database not found at {CANONICAL_DB}", file=sys.stderr)
        print("Run:  python cli.py generate --scale full --seed 20261022 --clear --export", file=sys.stderr)
        sys.exit(1)

    temp_dir = Path(tempfile.mkdtemp(prefix="yottaflex_e2e_"))
    success = False
    try:
        print(f"\n[setup] Preparing isolated E2E environment in {temp_dir} ...")
        test_db = prepare_isolated_db(temp_dir)

        env = {**os.environ, "DATABASE_URL": f"sqlite:///{test_db}"}
        cmd = [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", "8001",
        ]
        print(f"[setup] Starting API server at {API_URL} (port 8001) ...")
        server_proc = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(BACKEND_DIR),
        )
        try:
            if not wait_for_server(25):
                print("ERROR: Server failed to start within 25s", file=sys.stderr)
                server_proc.terminate()
                sys.exit(1)
            print(f"[setup] Server ready.\n")

            success = run_tests(run_n=args.run_n)
        finally:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except Exception:
                server_proc.kill()
            print("\n[teardown] Server process shut down cleanly.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[teardown] Cleaned up temp directory.")

    sys.exit(0 if success else 1)
