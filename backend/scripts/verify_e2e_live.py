"""
End-to-end verification script for YottaFlex Complaint Intelligence Platform.
Starts the server, exercises critical API workflows against real SQLite DB,
and asserts responses and persistence.
"""
import io
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

API_URL = "http://127.0.0.1:8000"

def wait_for_server(max_wait=15):
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
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_patch(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_tests():
    print("=" * 60)
    print("YottaFlex Complaint Intelligence Platform - Live E2E Verification")
    print("=" * 60)

    # 1. Health check
    h = http_get("/health")
    assert h["status"] in ("ok", "healthy"), f"Health check failed: {h}"
    print(f"✓ E2E-01: Health check passed (/health -> {h['status']})")

    # 2. Dashboard KPIs
    stats = http_get("/api/v1/dashboard/stats")
    assert "total_complaints" in stats
    assert stats["total_complaints"] >= 2000
    print(f"✓ E2E-02: Dashboard stats loaded (Total complaints: {stats['total_complaints']:,})")

    # 3. Dashboard charts
    charts = http_get("/api/v1/dashboard/charts")
    assert "priority_breakdown" in charts
    assert "status_breakdown" in charts
    print("✓ E2E-03: Dashboard charts data loaded (priority and status breakdowns present)")

    # 4. Create new complaint (Safety incident)
    payload = {
        "customer_id": 1,
        "title": "Severe battery smoke and fire hazard reported",
        "description": "The device battery overheated and emitted visible smoke and chemical odor.",
        "channel": "phone",
        "is_safety_incident": True,
    }
    created = http_post("/api/v1/complaints", payload)
    new_cid = created["complaint_id"]
    assert new_cid.startswith("CMP-")
    assert created["priority"] == "P1", f"Expected P1 for safety incident, got {created['priority']}"
    assert created["is_safety_incident"] is True
    print(f"✓ E2E-04: Created complaint {new_cid} - auto-classified P1 Safety Incident")

    # 5. Fetch complaint detail
    detail = http_get(f"/api/v1/complaints/{new_cid}")
    assert detail["complaint_id"] == new_cid
    assert detail["customer"] is not None
    assert detail["sla_clock"] is not None
    assert detail["current_assignment"] is not None
    print(f"✓ E2E-05: Retrieved complaint detail with nested customer, SLA clock, and assignment")

    # 6. Post customer message
    msg = http_post(
        f"/api/v1/complaints/{new_cid}/messages",
        {
            "sender_type": "customer",
            "sender_id": "CUST-000001",
            "body": "Can someone please expedite this? The unit is completely unusable.",
            "channel": "phone",
        },
    )
    assert msg["body"].startswith("Can someone")
    print(f"✓ E2E-06: Added customer interaction message to complaint {new_cid}")

    # 7. Escalate complaint via PATCH
    updated = http_patch(
        f"/api/v1/complaints/{new_cid}",
        {
            "status": "escalated",
            "notes": "Escalated to Executive Squad per customer safety protocol",
        },
    )
    assert updated["status"] == "escalated"
    print(f"✓ E2E-07: Escalated complaint {new_cid} to status 'escalated'")

    # 8. Anomaly detection endpoint
    anom = http_get("/api/v1/anomalies/detect")
    assert anom["detected_count"] >= 6
    assert anom["precision"] == 1.0
    print(f"✓ E2E-08: Anomaly detection endpoint verified (Detected: {anom['detected_count']}, Precision: {anom['precision']:.0%})")

    # 9. Validation endpoint
    val = http_post("/api/v1/validate", {})
    assert val["summary"]["total"] >= 15
    print(f"✓ E2E-09: Data validation engine endpoint passed ({val['summary']['passed']}/{val['summary']['total']} checks passed)")

    # 10. Customer filtering
    vulnerable_custs = http_get("/api/v1/customers?vulnerable_only=true")
    assert len(vulnerable_custs["items"]) > 0
    print(f"✓ E2E-10: Vulnerable customer filtering verified ({len(vulnerable_custs['items'])} vulnerable customers found)")

    # 11. Complaint filtering
    safety_comps = http_get("/api/v1/complaints?safety_only=true")
    assert len(safety_comps["items"]) > 0
    print(f"✓ E2E-11: Safety complaint filtering verified ({len(safety_comps['items'])} safety complaints found)")

    # 12. Baseline manifest report
    manifest_rep = http_get("/api/v1/reports/baseline-manifest")
    assert "files" in manifest_rep
    assert manifest_rep.get("scale") == "full"
    print(f"✓ E2E-12: Baseline manifest report endpoint verified ({len(manifest_rep['files'])} baseline files recorded, scale={manifest_rep['scale']})")

    print("\n" + "=" * 60)
    print("ALL 12 E2E WORKFLOW CHECKS PASSED WITH 100% SUCCESS")
    print("=" * 60)

if __name__ == "__main__":
    server_proc = None
    try:
        # Start uvicorn server
        cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
        server_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("Waiting for server to become ready at http://127.0.0.1:8000 ...")
        if not wait_for_server(20):
            print("ERROR: Server failed to start within 20s", file=sys.stderr)
            sys.exit(1)
        
        run_tests()
    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except Exception:
                server_proc.kill()
            print("Server process shut down cleanly.")
