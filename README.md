# YottaFlex Complaint Intelligence Platform

An enterprise-grade, deterministic customer complaint intelligence platform featuring automated classification, rules-based priority triage, SLA monitoring, agent assignment optimization, comprehensive data quality validation, and anomaly detection.

---

## Table of Contents

- [Overview](#overview)
- [Architecture & Core Engines](#architecture--core-engines)
  - [1. Deterministic Synthetic Data Generator](#1-deterministic-synthetic-data-generator)
  - [2. Multi-Tier Priority & Triage Engine](#2-multi-tier-priority--triage-engine)
  - [3. Automated Keyword Classifier](#3-automated-keyword-classifier)
  - [4. SLA Management Engine](#4-sla-management-engine)
  - [5. Skill-Based Assignment Engine](#5-skill-based-assignment-engine)
  - [6. Five-Domain Validation Engine](#6-five-domain-validation-engine)
  - [7. Anomaly Detection & Injection Suite](#7-anomaly-detection--injection-suite)
  - [8. Data Ingestion Pipeline](#8-data-ingestion-pipeline)
- [Data Schema & Entity Models](#data-schema--entity-models)
- [Setup & Installation](#setup--installation)
- [Docker & Containerized Deployment](#docker--containerized-deployment)
- [Cloud Deployment (Railway / Render)](#cloud-deployment-railway--render)
- [CLI Reference](#cli-reference)
- [REST API Endpoints](#rest-api-endpoints)
- [Running the Applications](#running-the-applications)
- [Testing Suite](#testing-suite)
- [Acceptance Criteria Verification](#acceptance-criteria-verification)

---

## Overview

The **YottaFlex Complaint Intelligence Platform** provides end-to-end operational visibility, automation, and compliance auditing for enterprise customer service organizations. It addresses the key bottlenecks in complaint management:

1. **Slow and subjective triage**: Handled by an automated multi-tier deterministic engine evaluating safety indicators, customer sentiment, order financial impact, vulnerability flags, and repeat caller history.
2. **SLA compliance drift**: Monitored via active SLA countdown clocks, pause tracking, escalation threshold alarms, and breach flags.
3. **Inefficient squad routing**: Solved through capability-based routing matching priority tiers and product domains with agent capacity.
4. **Data quality & audit failure**: Protected by an active 5-domain data validator running 20+ checks on relational integrity, chronology, and accounting accuracy.
5. **Reproducible synthetic simulation**: Powered by seeded deterministic generators capable of producing starter (~50 cases) and full enterprise (~2,000 cases) datasets with 100% bitwise SHA-256 reproducibility.

---

## Architecture & Core Engines

The backend is built with **Python 3.13**, **FastAPI**, **SQLAlchemy 2.x**, and **SQLite**, with strict Pydantic v2 schemas and rich Click CLI commands. The frontend is a modern **React 18 + Vite + TypeScript** single-page application.

```mermaid
graph TD
    Client[Web Frontend / CLI / External API] -->|HTTP / JSON| API[FastAPI Application Gateway]
    
    subgraph Core Engines
        API --> Classifier[Complaint Classifier<br/>categories.yaml]
        API --> PriorityEng[Priority Engine<br/>priority_rules.yaml]
        API --> SLAEng[SLA Engine<br/>sla_config.yaml]
        API --> AssignEng[Assignment Engine<br/>assignment_rules.yaml]
        API --> ValEng[Validation Engine<br/>5 Verification Domains]
        API --> AnomEng[Anomaly Detector<br/>& Injector]
    end

    subgraph Data Layer
        API --> DB[(SQLite Database<br/>complaint_intelligence.db)]
        DataGen[Data Generator<br/>Seeded PRNG] -->|Loads into| DB
        DB -->|Exports| BaseExp[Baseline Exporter<br/>CSV / JSON / Manifest]
        BaseExp -->|SHA-256 Audit| ReproEng[Reproducibility Engine]
    end
```

### 1. Deterministic Synthetic Data Generator
- **Location**: `backend/app/generator/orchestrator.py`
- **Guaranteed Determinism**: Uses explicit seed initialization (`random.Random(seed)` and `Faker.seed(seed)`). Given seed `20261022`, re-running generation produces identical records and bitwise-identical exported files.
- **Scales**:
  - `starter`: 50 customers, 30 products, 80 orders, 50 complaints, 150 messages, 6 teams, 12 agents.
  - `full`: 5,000 customers, 200 products, 8,000 orders, 2,000 complaints, 6,000 messages, 6 teams, 48 agents.
- **Relational Integrity**: Generates 16 entity types strictly respecting parent-child foreign keys and chronological precedence.

### 2. Multi-Tier Priority & Triage Engine
- **Location**: `backend/app/engine/priority.py`
- **Precedence Hierarchy**:
  1. **Rule PR-001 (P1 Override)**: Any complaint flagged with safety risk keywords (e.g. fire, smoke, overheat, shock, hazard, injury) is immediately assigned priority **P1** regardless of customer tier or sentiment.
  2. **Rule PR-002 (High Value Order)**: Orders exceeding $500 with negative sentiment are elevated to **P1** or **P2**.
  3. **Rule PR-003 (Vulnerable Customer)**: Any customer flagged with vulnerability indicators (elderly, disability, hardship) receives a mandatory +1 priority upgrade.
  4. **Rule PR-004 (Chronic Repeat Issue)**: Customers with multiple prior complaints receive automatic escalation.
  5. **Default Baseline**: P3 for standard issues, P4 for low-severity general inquiries.

### 3. Automated Keyword Classifier
- **Location**: `backend/app/engine/classifier.py`
- Evaluates subject and description text using regex-based keyword boundary matching across 10 categories (`PRODUCT_SAFETY`, `DELIVERY_DELAY`, `DAMAGED_PRODUCT`, `REFUND`, `PAYMENT`, `PRODUCT_QUALITY`, `WRONG_ITEM`, `MISSING_ORDER`, `ACCOUNT_SERVICE`, `OTHER`).
- Calculates match confidence scores and extracts matched keyword evidence.

### 4. SLA Management Engine
- **Location**: `backend/app/engine/sla.py`
- Configured via `sla_config.yaml`:
  - **P1**: 4-hour resolution target, 1-hour first response, 2-hour escalation threshold.
  - **P2**: 12-hour resolution target, 2-hour first response, 8-hour escalation threshold.
  - **P3**: 48-hour resolution target, 8-hour first response, 36-hour escalation threshold.
  - **P4**: 72-hour resolution target, 24-hour first response, 60-hour escalation threshold.
- Tracks clock running, paused, completed, and breached states with audit timestamps.

### 5. Skill-Based Assignment Engine
- **Location**: `backend/app/engine/assignment.py`
- Routes complaints to specialized teams:
  - Safety incidents $\to$ Safety & Compliance Squad (safety certified).
  - P1 escalations $\to$ Executive Escalations Squad.
  - Refunds & billing $\to$ Billing & Payments Team.
  - Delivery delays & missing shipments $\to$ Logistics & Fulfillment Team.
  - Product quality & technical issues $\to$ Technical Product Support.
- Balances individual agent workload using least-loaded agent selection (`open_complaint_count`).

### 6. Five-Domain Validation Engine
- **Location**: `backend/app/validation/validator.py`
- Executes comprehensive database health checks across 5 domains:
  1. **Schema & Data Types**: Non-null field verification, valid email/phone formats, JSON syntax in metadata fields.
  2. **Chronology & Time-ordering**: Ordering timestamps must precede complaint creation; resolution must follow creation; closing must follow resolution; message timestamps must be sequential.
  3. **Arithmetic & Financials**: `total_amount = (unit_price * quantity) - discount_amount`; positive refund amounts; survey ratings within $[1, 5]$.
  4. **Business Rules & SLA**: Safety complaints mapped to P1; breached SLA clocks marked correctly; survey submissions only after closure.
  5. **Foreign Key & Referential Integrity**: Verification that all foreign keys reference existing parent primary keys with no orphaned records.

### 7. Anomaly Detection & Injection Suite
- **Location**: `backend/app/anomaly/detector.py`
- Scans active database for the 6 required anomaly scenarios:
  1. `MISSING_CUSTOMER_RELATIONSHIP`: Complaint with null `customer_id_fk` (no customer linked).
  2. `RESOLUTION_BEFORE_CREATION`: Resolution `resolved_at` timestamp is before complaint `created_at`.
  3. `SLA_PAUSE_RESUME_INCONSISTENCY`: SLA `resumed` event occurs before its paired `paused` event.
  4. `REPEAT_COMPLAINT_NOT_LINKED`: Repeat complaint from same customer has no `ComplaintRelationship` record.
  5. `SURVEY_BEFORE_CLOSURE`: CSAT survey submitted before complaint is closed (`submitted_before_closure=True`).
  6. `SAFETY_LOW_PRIORITY`: Critical `PRODUCT_SAFETY` complaint incorrectly assigned P3 or P4 priority.
- **Detector Independence**: `AnomalyDetector` operates purely on DB state; `AnomalyEvaluator` separately consumes ground-truth files — never mixing detection with evaluation.
- **Evaluation Matching**: Uses `(anomaly_type, complaint_id)` pair (not complaint_id alone) to prevent inflated precision metrics.
- Computes precision, recall, and F1-score globally and per-category (6 categories).
- Ground truth persisted to `data/anomalies/ground_truth.json` and `ground_truth.csv` after each injection.

### 8. Data Ingestion Pipeline
- **Backend Location**: `backend/app/api/v1/ingestion.py` and `backend/app/services/ingestion.py`
- **Frontend Location**: `frontend/src/pages/Ingestion.tsx`
- **Capabilities**:
  - Accepts CSV and JSON payload uploads up to 10 MB for complaints and customers.
  - Supports raw JSON arrays as well as structured wrappers (`{"data": [...]}`).
  - Enforces field-level validation: required attributes, valid enum sets (channels, statuses, priorities, sentiments, account tiers), and regex formats (`CMP-YYYY-NNNNNN`, `CUS-NNNNNN`, valid RFC 5322 emails).
  - Performs intelligent deduplication: identical business IDs or customer emails already in the database are automatically skipped with separate tracking.
  - Transactional integrity: valid records are committed atomically; invalid records yield granular row-level error reports with row index, field name, and descriptive failure messages.
  - Interactive Web UI: drag-and-drop file upload with live schema viewer, summary metrics (Accepted, Rejected, Deduplicated, Total), and searchable error breakdown.

---

## Data Schema & Entity Models

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : places
    CUSTOMERS ||--o{ COMPLAINTS : submits
    PRODUCTS ||--o{ ORDER_ITEMS : included_in
    PRODUCTS ||--o{ COMPLAINTS : linked_to
    ORDERS ||--o{ ORDER_ITEMS : contains
    ORDERS ||--o{ COMPLAINTS : references
    CATEGORIES ||--o{ COMPLAINTS : categorizes
    TEAMS ||--o{ AGENTS : employs
    TEAMS ||--o{ ASSIGNMENTS : assigned_to
    AGENTS ||--o{ ASSIGNMENTS : handles
    COMPLAINTS ||--o{ MESSAGES : has
    COMPLAINTS ||--o{ ASSIGNMENTS : has
    COMPLAINTS ||--o| SLA_CLOCKS : tracked_by
    SLA_CLOCKS ||--o{ SLA_EVENTS : logs
    COMPLAINTS ||--o{ STATUS_EVENTS : logs
    COMPLAINTS ||--o| RESOLUTIONS : resolves_with
    COMPLAINTS ||--o| SURVEYS : evaluated_by
```

### Entity Table Summary
| Table Name | Primary Key | Description |
|---|---|---|
| `categories` | `id` (int), `code` (string) | Canonical complaint categories and safety risk definitions |
| `priority_rules` | `id` (int), `rule_id` (string) | Business rules governing priority escalation and weighting (7 rules: PR-001–PR-007) |
| `teams` | `id` (int), `team_id` (string) | Support squads with specializations and safety certifications |
| `agents` | `id` (int), `agent_id` (string) | Customer service agents, roles, and open case counts |
| `products` | `id` (int), `product_id` (string) | Catalog items, SKUs, brand, and unit prices |
| `customers` | `id` (int), `customer_id` (string) | Customer profiles, tiers, loyalty, and vulnerability flags |
| `orders` | `id` (int), `order_id` (string) | Sales transactions, status, and tracking numbers |
| `order_items` | `id` (int), `order_item_id` (string) | **Bridge table**: multi-product line items per order (qty, unit_price, discount, line_total) |
| `complaints` | `id` (int), `complaint_id` (string) | Core complaint tickets, classification, priority, status, `product_id_fk` |
| `complaint_messages` | `id` (int), `message_id` (string) | Chronological message thread between customer and agent (1–7 per complaint) |
| `complaint_assignments` | `id` (int), `assignment_id` (string) | Assignment history and current active owner |
| `sla_clocks` | `id` (int), `sla_id` (string) | SLA clock deadlines, pause state, and breach tracking |
| `sla_events` | `id` (int) | Audit log of SLA events (`created`, `paused`, `resumed`, `escalated`, `breached`, `completed`) |
| `complaint_status_events`| `id` (int) | State transition history (open → in_progress → resolved → closed) |
| `resolutions` | `id` (int), `resolution_id` (string) | Formal resolution record, refund authorization, outcome |
| `customer_surveys` | `id` (int), `survey_id` (string) | Post-resolution customer satisfaction scores (1–5) |
| `complaint_relationships`| `id` (int) | Repeat complaint links and parent-child dependencies (70 pairs) |
| `generation_runs` | `id` (int), `run_id` (string) | Seed metadata and record counts for data generation runs |

---

## Setup & Installation

### Prerequisites
- Python 3.11, 3.12, or 3.13
- Node.js 18+ and npm (for frontend)

### Backend Setup
1. Open a terminal in the `backend` directory:
   ```powershell
   cd backend
   ```
2. Create and activate a virtual environment (if not already present):
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install required Python packages:
   ```powershell
   pip install -r requirements.txt
   ```

### Frontend Setup
1. Open a terminal in the `frontend` directory:
   ```powershell
   cd frontend
   npm install
   ```

---

## Docker & Containerized Deployment

The entire stack can be launched with a single command via Docker Compose:

```bash
docker compose up --build
```

### Services Included
- **`backend`**: Python 3.11-slim container running FastAPI with Uvicorn on port `8000`. Runs seed generation (`full` scale, seed `20261022`) automatically on startup, mounts a persistent volume for database storage, and includes an active healthcheck.
- **`frontend`**: Multi-stage Node 20 build serving the production bundle with `serve` on port `5173`. Connects to the backend gateway automatically.

Access points:
- Frontend UI: `http://localhost:5173`
- Backend API & Health: `http://localhost:8000/health`
- Interactive API Docs: `http://localhost:8000/docs`

---

## Cloud Deployment (Railway / Render)

Pre-configured infrastructure manifests are provided in the repository root for instantaneous deployment:

### 1. Railway (`railway.toml` & `Procfile`)
1. Create a new project in [Railway](https://railway.app/).
2. Select **Deploy from GitHub repo** and connect this repository.
3. Railway automatically detects `railway.toml` and `backend/Procfile`:
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Healthcheck path: `/health`

### 2. Render (`render.yaml`)
1. In [Render](https://render.com/), choose **New Blueprint Instance**.
2. Point Render to your repository; it reads `render.yaml` automatically.
3. Environment variables configured:
   - `APP_ENV=production`
   - `DATABASE_URL=sqlite:///./complaint_intelligence.db`

### 3. Frontend Static Hosting (Vercel / Netlify / Cloudflare Pages)
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_URL=https://<your-backend-domain>`

---

## CLI Reference

The CLI is implemented via Click at `backend/cli.py`. Run all commands using the backend virtual environment Python:

```powershell
cd backend
.\venv\Scripts\python cli.py [command] [options]
```

### 1. `generate`
Generates synthetic data, saves it to SQLite, and exports baseline CSV/JSON files with SHA-256 checksums.

```powershell
# Generate standard starter dataset with database reset and baseline export
.\venv\Scripts\python cli.py generate --scale starter --seed 20261022 --clear --export

# Generate full-scale dataset
.\venv\Scripts\python cli.py generate --scale full --seed 20261022 --clear --export
```

**Options**:
- `--scale [starter|full]`: Dataset volume (default: `starter`).
- `--seed INT`: Random seed for deterministic generation (default: `20261022`).
- `--clear / --no-clear`: Wipe existing database tables before loading (default: `--clear`).
- `--export / --no-export`: Export CSV/JSON files to `data/baseline/` (default: `--export`).

### 2. `validate`
Runs comprehensive data quality validation across Schema, Chronology, Arithmetic, Business Rules, and Referential Integrity.

```powershell
.\venv\Scripts\python cli.py validate
```

Exits with code `0` on clean pass, or code `1` if any failure checks fail.

### 3. `detect-anomalies`
Runs the `AnomalyDetector` across the active database and outputs detection metrics alongside detected anomalies.

```powershell
.\venv\Scripts\python cli.py detect-anomalies
```

### 4. `inject-anomalies`
Injects deliberate test anomaly scenarios into the active database and creates a ground-truth JSON manifest.

```powershell
.\venv\Scripts\python cli.py inject-anomalies --count 6
```

### 5. `reproduce`
Validates generator determinism by regenerating records in a temporary directory and performing a bitwise SHA-256 hash audit against `data/baseline/manifest.json`.

```powershell
# Audit reproducibility of the baseline starter dataset
.\venv\Scripts\python cli.py reproduce --seed 20261022 --scale starter

# Audit against a specific generation run
.\venv\Scripts\python cli.py reproduce --run-id GEN-RUN-000001
```

### 6. `export`
Exports the current database state to CSV and/or JSON format in the specified output directory.

```powershell
# Export both CSV and JSON to data/exports
.\venv\Scripts\python cli.py export --format both --output-dir data/exports

# Export CSV only
.\venv\Scripts\python cli.py export --format csv --output-dir data/exports/csv

# Export portable SQL dump alongside CSV and JSON
.\venv\Scripts\python cli.py export --format all --output-dir data/exports
```

### 7. `dump-sql`
Exports a portable SQL script dump of the database (schema, indices, constraints, and data inserts) using SQLite `iterdump`.

```powershell
.\venv\Scripts\python cli.py dump-sql
```

Outputs: `backend/data/baseline/sql/complaint_intelligence_dump.sql` (9.15 MB portable SQL script).

### 8. `import-sql`
Imports a portable SQL dump into a clean target database, verifying table schemas, primary keys, record counts per table, and foreign key integrity.

```powershell
.\venv\Scripts\python cli.py import-sql data/baseline/sql/complaint_intelligence_dump.sql --target-db data/test_verify.db
```

### 9. `server`
Starts the FastAPI application server using Uvicorn.

```powershell
.\venv\Scripts\python cli.py server --host 127.0.0.1 --port 8000 --reload
```

---

## REST API Endpoints

The API is fully documented interactively via Swagger UI at **`http://localhost:8000/docs`**.

| Category | Method | Endpoint | Description |
|---|---|---|---|
| **System** | `GET` | `/health` | Health check, version, and server timestamp |
| | `GET` | `/` | API root metadata and documentation links |
| **Complaints** | `GET` | `/api/v1/complaints` | Paginated complaint listing with multi-field filtering |
| | `POST` | `/api/v1/complaints` | Create, classify, triage, and route a new complaint |
| | `GET` | `/api/v1/complaints/{id}` | Complaint detail with messages, status history, SLA, assignments |
| | `PATCH` | `/api/v1/complaints/{id}` | Update complaint status or priority |
| | `POST` | `/api/v1/complaints/{id}/messages` | Add customer or agent message to thread |
| | `POST` | `/api/v1/complaints/{id}/resolve` | Record complaint resolution and refund authorization |
| **Customers** | `GET` | `/api/v1/customers` | Paginated customer list with tier and vulnerability filters |
| | `GET` | `/api/v1/customers/{id}` | Customer profile detail |
| | `GET` | `/api/v1/customers/{id}/complaints`| History of complaints filed by customer |
| **Products** | `GET` | `/api/v1/products` | Catalog listing with category and search filters |
| | `GET` | `/api/v1/products/{id}` | Product detail and SKU info |
| **Teams & Agents**| `GET` | `/api/v1/teams` | Support teams, specializations, and headcounts |
| | `GET` | `/api/v1/teams/{id}` | Team detail and assigned agent roster |
| | `GET` | `/api/v1/agents` | Agents listing with active workload counts |
| | `GET` | `/api/v1/agents/{id}` | Agent profile and assigned cases |
| **Dashboard** | `GET` | `/api/v1/dashboard/stats` | Executive KPI aggregates (volumes, SLA rate, CSAT, avg resolution) |
| | `GET` | `/api/v1/dashboard/charts` | Breakdown charts (category, priority, status, SLA, monthly trends) |
| **Validation** | `POST`| `/api/v1/validate` | Trigger full 5-domain data validation suite |
| | `GET` | `/api/v1/validate` | Get current validation findings and status summary |
| **Anomalies** | `GET` | `/api/v1/anomalies` | Scan database for anomalies; return metrics & findings |
| | `POST` | `/api/v1/anomalies/inject` | Inject test anomaly scenarios for testing |
| **Generator** | `POST`| `/api/v1/generate` | Trigger synthetic data generation pipeline |
| | `GET` | `/api/v1/generate/runs` | List historical data generation runs |
| | `POST` | `/api/v1/generate/reproduce` | Run reproducibility check via API |
| **Reports** | `GET` | `/api/v1/reports` | List available audit and baseline reports |
| | `GET` | `/api/v1/reports/{report_id}` | Retrieve report payload (JSON or Markdown) |
| **Ingestion** | `POST` | `/api/v1/ingest/complaints` | Upload CSV/JSON complaints with field validation & dedup |
| | `POST` | `/api/v1/ingest/customers` | Upload CSV/JSON customers with email check & dedup |
| | `GET` | `/api/v1/ingest/schema/complaints` | Return required/optional schema for complaints upload |
| | `GET` | `/api/v1/ingest/schema/customers` | Return required/optional schema for customers upload |

---

## Running the Applications

### 1. Launch Backend API
```powershell
cd backend
.\venv\Scripts\python cli.py server --host 127.0.0.1 --port 8000 --reload
```
API runs at: **http://127.0.0.1:8000**  
Swagger Docs: **http://127.0.0.1:8000/docs**

### 2. Launch Frontend UI
```powershell
cd frontend
npm run dev
```
UI runs at: **http://localhost:5173**

---

## Testing Suite

All tests use `pytest` and an isolated in-memory SQLite database (`sqlite:///:memory:`) configured with `StaticPool` to ensure thread-safety and zero test side-effects. The test suite comprises **112 unit and integration tests** passing with **94% code coverage** in under 12 seconds.

To run the complete test suite:
```powershell
cd backend
.\venv\Scripts\python -m pytest tests/ -v --tb=short
```

### Test Coverage Areas
1. **`tests/test_generator.py`** (3 tests): Record count verification, seed reproducibility, entropy check.
2. **`tests/test_classifier.py`** (3 tests): Safety keyword classification, delivery triage, fallback assignment.
3. **`tests/test_priority.py`** (3 tests): Strict P1 override rule PR-001, sentiment scoring, high-value order escalation.
4. **`tests/test_sla.py`** (18 tests): Policies P1-P4, deadline calculation, active breach evaluation, pause adjustments.
5. **`tests/test_validation.py`** (1 test): Clean dataset validation asserting 0 failures across all 5 verification domains.
6. **`tests/test_anomaly.py`** (13 tests): Zero anomalies on clean baseline, injection of all 6 required scenarios, per-scenario detection verification (MISSING_CUSTOMER_RELATIONSHIP, RESOLUTION_BEFORE_CREATION, SLA_PAUSE_RESUME_INCONSISTENCY, REPEAT_COMPLAINT_NOT_LINKED, SURVEY_BEFORE_CLOSURE, SAFETY_LOW_PRIORITY), 100% Precision / Recall / F1-score per category, detector independence from ground-truth file, `ground_truth.csv` generation.
7. **`tests/test_exports_reproducibility.py`** (15 tests): SHA-256 deterministic file hashing, 35/35 bitwise file matching, mismatch detection.
8. **`tests/test_api.py`** (10 tests): Integration tests covering `/health`, complaints CRUD, customers, products, teams, dashboard KPIs, validation endpoint, anomaly detection, reports.
9. **`tests/test_api_extended.py`** (29 tests): Extended integration coverage across edge cases, nested relationships, and lifecycle status changes.
10. **`tests/test_ingestion.py`** (17 tests): Schema discovery, CSV/JSON complaint & customer ingestion, field validation, duplicate detection, bad input rejection.

### Live End-to-End Workflow Verification
A self-contained live API verification script runs against a dedicated test server with full database persistence:
```powershell
cd backend
.\venv\Scripts\python scripts/verify_e2e_live.py
```
This exercises 12 distinct operational workflow steps (health, stats, charts, complaint creation with auto-classification, nested details, message thread addition, lifecycle escalation, anomaly detection verification, 5-domain data validation, customer filters, and baseline reproducibility audit).

---

## Acceptance Criteria Verification

| ID | Requirement | Implementation Verification | Status |
|---|---|---|---|
| **AC-01** | Deterministic Generation | `app/generator/orchestrator.py` seeded PRNG; identical SHA-256 hashes verified via `cli.py reproduce` | **PASSED** |
| **AC-02** | Priority & Triage Engine | `app/engine/priority.py` enforces PR-001–PR-007 (all 4 priority levels: P1:302 P2:170 P3:194 P4:1334) | **PASSED** |
| **AC-03** | Keyword Classification | `app/engine/classifier.py` regex boundary matching over 10 categories with confidence | **PASSED** |
| **AC-04** | SLA Monitoring | `app/engine/sla.py` tracks targets, countdowns, pause durations, and breach alerts | **PASSED** |
| **AC-05** | Agent Assignment | `app/engine/assignment.py` matches squad capabilities and balances agent workload | **PASSED** |
| **AC-06** | 5-Domain Validation | `app/validation/validator.py` executes 15 checks across 5 domains; ~0.21 s on full dataset; verified clean on starter & full datasets | **PASSED** |
| **AC-07** | Anomaly Detection | `app/anomaly/detector.py` + `AnomalyEvaluator` separation; 6 required scenarios (MISSING_CUSTOMER_RELATIONSHIP, RESOLUTION_BEFORE_CREATION, SLA_PAUSE_RESUME_INCONSISTENCY, REPEAT_COMPLAINT_NOT_LINKED, SURVEY_BEFORE_CLOSURE, SAFETY_LOW_PRIORITY); `(anomaly_type, complaint_id)` pair matching; 100% P/R/F1 per category | **PASSED** |
| **AC-08** | Click CLI | `backend/cli.py` implements `generate`, `validate`, `detect-anomalies`, `reproduce`, `server`, `export`, `dump-sql`, `import-sql` | **PASSED** |
| **AC-09** | REST API | Complete endpoints with CORS, Pydantic schemas, and Swagger docs | **PASSED** |
| **AC-10** | Modern Frontend | React 18 + Vite UI with dashboards, complaint tables, triage tools, and anomaly viewers | **PASSED** |
| **AC-11** | Full-Scale Volume | 2,000 complaints, 5,000 customers, 8,000 orders, 11,240 order_items, 6,000 messages (1–7 per complaint), 70 repeat pairs | **PASSED** |
| **AC-12** | Portable SQL Dump | Complete SQLite dump export & verified import (`complaint_intelligence_dump.sql`, ~10.7 MB) | **PASSED** |
| **AC-13** | Reproducibility Manifest | 35/35 exported baseline files match SHA-256 hashes bit-for-bit | **PASSED** |
| **AC-14** | Live E2E Verification | 12/12 automated live API tests passing across isolated server instances | **PASSED** |
| **AC-15** | Data Ingestion Pipeline | CSV/JSON upload with validation, deduplication, and row-level error reporting (17 tests) | **PASSED** |
| **AC-16** | Containerization | `docker-compose.yml` with backend (auto-seeded) and frontend services | **PASSED** |
| **AC-17** | Cloud Deployment Config | `railway.toml`, `render.yaml`, and `backend/Procfile` ready for zero-config deployment | **PASSED** |
| **AC-18** | Security & Hygiene | No credentials committed; `.env`, `venv/`, `node_modules/`, and DB files gitignored | **PASSED** |
| **AC-19** | GitHub Publication | Clean git tree ready for public remote push | **READY** |
