"""
Full application verification -- problem statement compliance.
Accurate to actual API contract.
"""
import httpx
import time
import sys

BASE = "http://127.0.0.1:8000/api/v1"
results = []


def check(label, ok, detail=""):
    sym = "PASS" if ok else "FAIL"
    results.append((label, ok, detail))
    suffix = f"  [{detail}]" if detail else ""
    print(f"  [{sym}]  {label}{suffix}")


def section(title):
    print(f"\n--- {title} ---")


print("=" * 70)
print("YottaFlex Complaint Intelligence Platform -- Full Verification")
print("Backend : http://127.0.0.1:8000")
print("Frontend: http://localhost:5173")
print("=" * 70)

client = httpx.Client(timeout=60)

# ------------------------------------------------------------------ #
section("1. Health & OpenAPI")
r = client.get("http://127.0.0.1:8000/health")
hj = r.json()
check("Health endpoint returns healthy",
      r.status_code == 200 and hj.get("status") == "healthy", hj.get("status",""))
check("Health has app_name", "app_name" in hj, hj.get("app_name",""))
check("Health has version",  "version" in hj, hj.get("version",""))
check("Swagger UI reachable", client.get("http://127.0.0.1:8000/docs").status_code == 200)
oa = client.get("http://127.0.0.1:8000/openapi.json").json()
paths = list(oa.get("paths", {}).keys())
check("OpenAPI schema has 20+ routes", len(paths) >= 20, f"{len(paths)} routes")

# ------------------------------------------------------------------ #
section("2. Dashboard KPIs & Charts")
r = client.get(f"{BASE}/dashboard/stats")
d = r.json()
check("Dashboard stats reachable", r.status_code == 200)
check("Dashboard -- total_complaints >= 2000",
      d.get("total_complaints", 0) >= 2000, f"total={d.get('total_complaints')}")
check("Dashboard -- open_complaints",        "open_complaints"       in d, str(d.get("open_complaints")))
check("Dashboard -- escalated_complaints",   "escalated_complaints"  in d, str(d.get("escalated_complaints")))
check("Dashboard -- sla_breached_count",     "sla_breached_count"    in d, str(d.get("sla_breached_count")))
check("Dashboard -- safety_incidents",       "safety_incidents"      in d, str(d.get("safety_incidents")))
check("Dashboard -- p1_complaints",          "p1_complaints"         in d, str(d.get("p1_complaints")))
check("Dashboard -- sla_compliance_rate",    "sla_compliance_rate"   in d, str(d.get("sla_compliance_rate")))
check("Dashboard -- csat_average",           "csat_average"          in d, str(d.get("csat_average")))
check("Dashboard -- total_customers=5000",   d.get("total_customers") == 5000,
      f"customers={d.get('total_customers')}")
check("Dashboard -- active_agents_count=48", d.get("active_agents_count") == 48,
      f"agents={d.get('active_agents_count')}")
r = client.get(f"{BASE}/dashboard/charts")
check("Charts endpoint 200 + non-empty", r.status_code == 200 and len(r.json()) > 0)

# ------------------------------------------------------------------ #
section("3. Complaints List, Pagination & Filters")
r = client.get(f"{BASE}/complaints?limit=20&offset=0")
d = r.json()
check("Complaints list -- 20 items", len(d.get("items", [])) == 20,
      f"count={len(d.get('items',[]))}")
check("Complaints list -- total >= 2000", d.get("total", 0) >= 2000,
      f"total={d.get('total')}")

for p in ["P1","P2","P3","P4"]:
    r2 = client.get(f"{BASE}/complaints?priority={p}&limit=1")
    d2 = r2.json()
    check(f"Priority filter {p}", r2.status_code == 200 and d2.get("total",0) > 0,
          f"total={d2.get('total')}")

for s in ["open","closed","escalated","in_progress","pending"]:
    check(f"Status filter '{s}'",
          client.get(f"{BASE}/complaints?status={s}&limit=1").status_code == 200)

check("Safety-only filter",
      client.get(f"{BASE}/complaints?safety_only=true&limit=1").json().get("total",0) > 0,
      f"found={client.get(f'{BASE}/complaints?safety_only=true&limit=1').json().get('total')}")
check("Escalated filter",
      client.get(f"{BASE}/complaints?escalated=true&limit=1").status_code == 200)
check("Full-text search",
      client.get(f"{BASE}/complaints?search=delivery&limit=5").status_code == 200)
check("Non-existent complaint 404",
      client.get(f"{BASE}/complaints/CMP-9999-999999").status_code == 404)

# ------------------------------------------------------------------ #
section("4. Complaint Detail -- Nested Relationships")
first_id = client.get(f"{BASE}/complaints?limit=1").json()["items"][0]["id"]
r = client.get(f"{BASE}/complaints/{first_id}")
det = r.json()
check("Complaint detail reachable", r.status_code == 200)
for field in ["sla_clock","assignments","messages","customer",
              "status_events","resolutions","surveys","related_complaints"]:
    check(f"Complaint detail has '{field}'", field in det)
sla = det.get("sla_clock") or {}
for sla_field in ["original_deadline","current_deadline","is_breached",
                  "resolution_hours","first_response_hours","escalation_hours",
                  "accumulated_paused_hours","is_escalated"]:
    check(f"SLA clock has '{sla_field}'", sla_field in sla)
check("SLA priority P1-P4", sla.get("priority") in ("P1","P2","P3","P4"),
      f"priority={sla.get('priority')}")

# ------------------------------------------------------------------ #
section("5. Complaint Lifecycle (Create -> Message -> Escalate)")
cust_id = client.get(f"{BASE}/customers?limit=1").json()["items"][0]["id"]
r = client.post(f"{BASE}/complaints", json={
    "customer_id": cust_id,
    "subject": "URGENT safety defect -- product fire",
    "description": "Product caused a fire hazard safety incident",
    "channel": "email",
})
d = r.json()
new_id = d.get("id")
check("Create complaint -- 201",        r.status_code == 201)
check("Create -- auto-classified P1",   d.get("priority") == "P1",
      f"priority={d.get('priority')}")
check("Create -- safety category",
      d.get("category_code") in ("PRODUCT_SAFETY","SAFETY_INCIDENT"),
      f"cat={d.get('category_code')}")

r = client.post(f"{BASE}/complaints/{new_id}/messages",
                json={"body": "Follow-up", "sender_type": "customer"})
check("Add message (body field) -- 201", r.status_code in (200, 201))

r = client.patch(f"{BASE}/complaints/{new_id}", json={"status": "escalated"})
check("Escalate via PATCH", r.status_code == 200 and r.json().get("status") == "escalated",
      f"status={r.json().get('status')}")

det2 = client.get(f"{BASE}/complaints/{new_id}").json()
events = [e for e in (det2.get("status_events") or []) if e.get("to_status") == "escalated"]
check("Status_event 'escalated' recorded", len(events) >= 1, f"count={len(events)}")
check("Message in complaint detail",
      len(det2.get("messages") or []) >= 1,
      f"messages={len(det2.get('messages') or [])}")

# ------------------------------------------------------------------ #
section("6. Customers")
check("Customers -- 5000 total",
      client.get(f"{BASE}/customers?limit=1").json().get("total") == 5000)
check("Vulnerable customer filter",
      client.get(f"{BASE}/customers?vulnerable_only=true&limit=1").json().get("total",0) > 0,
      f"found={client.get(f'{BASE}/customers?vulnerable_only=true&limit=1').json().get('total')}")
check("Tier filter GOLD",
      client.get(f"{BASE}/customers?tier=GOLD&limit=1").json().get("total",0) > 0)
c_id = client.get(f"{BASE}/customers?limit=1").json()["items"][0]["id"]
cd = client.get(f"{BASE}/customers/{c_id}").json()
check("Customer detail -- has complaints", "complaints" in cd)

# ------------------------------------------------------------------ #
section("7. Products, Teams, Agents")
check("Products -- 200 total",
      client.get(f"{BASE}/products?limit=1").json().get("total") == 200)
teams = client.get(f"{BASE}/teams").json()
check("Teams -- 6 teams", len(teams) == 6, f"count={len(teams)}")
for team in teams[:3]:
    check(f"Team '{team.get('name')}' -- has specializations", "specializations" in team)
agents = client.get(f"{BASE}/agents").json()
check("Agents -- 48 total",
      isinstance(agents, list) and len(agents) == 48,
      f"count={len(agents) if isinstance(agents,list) else '?'}")

# ------------------------------------------------------------------ #
section("8. Five-Domain Validation Engine")
t0 = time.time()
r = client.post(f"{BASE}/validate", timeout=20)
elapsed = time.time() - t0
d = r.json()
findings = d.get("findings", [])
summary  = d.get("summary", {})
passes   = summary.get("passed", 0)
warns    = summary.get("warned", 0)
fails    = summary.get("failed", 0)
total_c  = summary.get("total", len(findings))
check("Validation POST under 15 s", elapsed < 15, f"{elapsed:.2f} s")
check("Validation -- 15 findings",  total_c == 15, f"{total_c} findings")
check("Validation -- 0 FAIL",       fails == 0,    f"fail={fails}")
check("Validation -- >= 14 PASS",   passes >= 14,  f"pass={passes} warn={warns}")
print(f"         {elapsed:.3f} s  |  {passes} PASS  {warns} WARN  {fails} FAIL")
check("Validation GET -- has summary+findings",
      "summary" in client.get(f"{BASE}/validate").json())

# Confirm 5 domains present in category field
categories = {f.get("category") for f in findings}
print(f"         Domains covered: {sorted(categories)}")
check("All 5 validation domains present",
      len(categories) >= 5, f"domains={sorted(categories)}")

# ------------------------------------------------------------------ #
section("9. Six Required Anomaly Scenarios (isolated run)")
# Restore clean state first so anomaly "clean check" is accurate
client.post(f"{BASE}/generate", json={"seed": 20261022, "scale": "full", "clear": True},
            timeout=60)

REQUIRED_TYPES = {
    "MISSING_CUSTOMER_RELATIONSHIP",
    "RESOLUTION_BEFORE_CREATION",
    "SLA_PAUSE_RESUME_INCONSISTENCY",
    "REPEAT_COMPLAINT_NOT_LINKED",
    "SURVEY_BEFORE_CLOSURE",
    "SAFETY_LOW_PRIORITY",
}
r = client.get(f"{BASE}/anomalies")
d = r.json()
check("Anomaly GET on clean DB -- 0 detected",
      d.get("detected_count", 0) == 0, f"detected={d.get('detected_count')}")

r = client.post(f"{BASE}/anomalies/inject")
inj = r.json()
check("Inject -- 6 records", inj.get("injected_count") == 6,
      f"count={inj.get('injected_count')}")
injected_types = {a.get("anomaly_type") for a in inj.get("anomalies", [])}
check("All 6 required types injected",
      injected_types == REQUIRED_TYPES, str(sorted(injected_types)))

r = client.get(f"{BASE}/anomalies")
d = r.json()
check("Detect -- finds 6",      d.get("detected_count") == 6, f"detected={d.get('detected_count')}")
check("Detect -- Precision=1.0", d.get("precision") == 1.0,   f"precision={d.get('precision')}")
check("Detect -- Recall=1.0",    d.get("recall") == 1.0,      f"recall={d.get('recall')}")
check("Detect -- F1=1.0",        d.get("f1_score") == 1.0,    f"f1={d.get('f1_score')}")
check("Ground truth count=6",    d.get("ground_truth_count") == 6,
      f"gt={d.get('ground_truth_count')}")

cat_m = d.get("category_metrics", {})
check("Per-category -- 6 categories",    len(cat_m) == 6, str(len(cat_m)))
check("All 6 categories F1=1.0",
      all(v.get("f1_score",0) == 1.0 for v in cat_m.values()))
detected_types = {a.get("anomaly_type") for a in d.get("anomalies", [])}
check("Detected types == required 6",
      detected_types == REQUIRED_TYPES, str(sorted(detected_types)))

print()
print("  Per-category breakdown:")
for cat, m in sorted(cat_m.items()):
    tp = m.get("true_positives",0); fp = m.get("false_positives",0)
    fn = m.get("false_negatives",0); f1 = m.get("f1_score",0)
    print(f"    {cat:<42}  TP={tp} FP={fp} FN={fn}  F1={f1:.2f}")

# ------------------------------------------------------------------ #
section("10. Reports & Baseline Manifest")
r = client.get(f"{BASE}/reports")
reps_wrapper = r.json()
report_items = reps_wrapper.get("reports", [])  # list of dicts with report_id
check("Reports list non-empty", len(report_items) > 0, f"{len(report_items)} reports")

for rep in report_items:
    rid = rep.get("report_id","")
    url = rep.get("url","")
    # Some reports are virtual pointers to other endpoints (validation, anomalies)
    # Use the declared URL if it differs from the /reports/{id} convention
    if url and not url.startswith(f"/api/v1/reports/{rid}"):
        r2 = client.get(f"http://127.0.0.1:8000{url}")
        check(f"Report '{rid}' (via declared URL) reachable", r2.status_code == 200,
              f"url={url} status={r2.status_code}")
    else:
        r2 = client.get(f"{BASE}/reports/{rid}")
        check(f"Report '{rid}' retrievable", r2.status_code == 200)

# Baseline manifest is returned directly (no nested payload)
r = client.get(f"{BASE}/reports/baseline_manifest")
mj = r.json()
check("Manifest has 35 files", len(mj.get("files", {})) == 35,
      f"files={len(mj.get('files',{}))}")
check("Manifest scale=full",   mj.get("scale") == "full",   f"scale={mj.get('scale')}")
check("Manifest seed=20261022", mj.get("seed") == 20261022, f"seed={mj.get('seed')}")

# ------------------------------------------------------------------ #
section("11. Data Ingestion Endpoints")
csv_data = (
    "customer_name,customer_email,subject,description,channel\n"
    "Test User,test@ingest.com,Delivery missing,Package never arrived,email"
)
r = client.post(f"{BASE}/ingest/complaints",
                files={"file": ("test.csv", csv_data.encode(), "text/csv")})
check("CSV ingest endpoint",
      r.status_code in (200, 201, 207, 422), f"status={r.status_code}")
check("Ingest schema/complaints",
      client.get(f"{BASE}/ingest/schema/complaints").status_code == 200)
check("Ingest schema/customers",
      client.get(f"{BASE}/ingest/schema/customers").status_code == 200)

# ------------------------------------------------------------------ #
client.close()

print()
print("=" * 70)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)
print(f"FINAL RESULT:  {passed}/{total} PASSED  |  {failed} FAILED")
print("=" * 70)

if failed:
    print("\nFAILED CHECKS:")
    for label, ok, detail in results:
        if not ok:
            print(f"  FAIL: {label}  [{detail}]")

sys.exit(0 if failed == 0 else 1)
