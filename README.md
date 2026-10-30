# YottaFlex Complaint Intelligence Platform

An enterprise-grade customer complaint intelligence and operations platform. Features deterministic synthetic dataset generation, automated 10-category classification, rule-based priority triage with absolute safety overrides, SLA countdown monitoring, skill-based agent routing, automated data validation, and operational anomaly detection evaluated against ground-truth benchmarks.

---

## Live Deployments & Documentation

- **Web Dashboard**: [https://complaint-intelligence-frontend.onrender.com](https://complaint-intelligence-frontend.onrender.com)
- **Production API**: [https://yottaflex-backend.onrender.com](https://yottaflex-backend.onrender.com)
- **Interactive Swagger Documentation**: [https://yottaflex-backend.onrender.com/docs](https://yottaflex-backend.onrender.com/docs)
- **System Health Diagnostics**: [https://yottaflex-backend.onrender.com/health](https://yottaflex-backend.onrender.com/health)

---

## Problem Statement & Solution

### The Challenge
Modern enterprise customer support teams handle thousands of complaints across disparate channels (Email, Web, Phone, Chat, Social Media). Common operational bottlenecks include:
- Inconsistent and slow manual categorization.
- Misassigned urgency levels, causing safety defects to languish without immediate attention.
- Unmonitored SLA breaches that damage customer retention and regulatory compliance.
- Fragmented customer histories and orphaned communication records.
- Subtle data quality degradation (chronological timeline inversions, pause/resume clock corruption).

### The Solution
The **YottaFlex Complaint Intelligence Platform** provides an automated operational pipeline:
1. **Intake & Auto-Classification**: Matches complaint subjects and descriptions against 10 domain categories using deterministic keyword and pattern classification rules.
2. **Safety-First Priority Scoring**: Assigns priority tiers from **P1 (Critical)** to **P4 (Low)**, enforcing non-negotiable P1 safety overrides whenever hazardous product conditions are detected.
3. **Automated SLA Countdown Tracking**: Enforces priority-dependent resolution deadlines (4h for P1, 12h for P2, 48h for P3, 72h for P4), tracking paused/running intervals and triggering automated escalation warnings.
4. **Skill & Capacity Routing**: Routes cases to specialized squads and individual agents based on product category competency and concurrent active workload caps.
5. **Continuous Quality & Anomaly Auditing**: Runs a 15-check validation suite across schema, chronology, arithmetic, and business rules, while auditing 6 distinct anomaly patterns against ground-truth datasets.

---

## Key Features

- **Executive Operations Dashboard**: Real-time KPI summaries for complaint volume, safety incidents, SLA compliance rates, average resolution times, CSAT scores, category breakdowns, priority distributions, and 30-day intake trends.
- **Complaint Registry & Detail Views**: Full lifecycle management supporting status transitions (`open`, `in_progress`, `escalated`, `resolved`, `closed`, `reopened`), multi-threaded customer communications, and resolution logging.
- **Customer Intelligence**: Comprehensive customer profiles tracking vulnerability flags, lifetime complaint counts, and tiered loyalty standings (**VIP**, **Premium**, **Standard**).
- **Dual-Database Support**: Seamless operation on **Managed PostgreSQL** in production and zero-configuration **SQLite** for local development, with dynamic dialect detection.
- **Deterministic Data Seeding**: Reproducible dataset generator (default seed: `20261022`) generating relational entities across all 18 tables with SHA-256 bitwise export manifests.
- **Enterprise Concurrency Safety**: PostgreSQL advisory locks and database-backed run state tracking preventing duplicate or race-condition data generation across concurrent workers.

---

## Technology Stack

- **Backend**:
  - Python 3.11 / 3.12 / 3.13
  - FastAPI (REST API framework)
  - SQLAlchemy 2.0 (ORM with dual PostgreSQL/SQLite dialect compatibility)
  - Pydantic v2 (Schema validation and serialization)
  - Uvicorn (ASGI web server)
  - Psycopg2-binary (PostgreSQL database adapter)
  - Click & Rich (Command-line interface and diagnostic tooling)
- **Frontend**:
  - React 18 & TypeScript
  - Vite 5 (Build tool and development server)
  - Recharts (Data visualizations and trend charts)
  - Lucide React (System icons)
  - Axios (HTTP client with cold-start retry interceptors)
  - React Router v6 (Client-side routing with static rewrite support)
- **Database**:
  - Production: Managed PostgreSQL on Render
  - Local / Testing: SQLite with WAL journaling and foreign key enforcement
- **Testing & Quality**:
  - Pytest & Pytest-Asyncio (136+ automated backend unit and integration tests)
  - ESLint (TypeScript linting)

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │            React 18 SPA                │
                      │  (Vite + TypeScript + Recharts + CSS)  │
                      └───────────────────┬────────────────────┘
                                          │ REST / JSON (Axios)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          FastAPI ASGI Server           │
                      │   (Uvicorn + Pydantic v2 Validation)   │
                      └─────┬──────────────┬─────────────┬─────┘
                            │              │             │
        ┌───────────────────┴──┐    ┌──────┴──────┐   ┌──┴──────────────────┐
        │  Classification &    │    │ SLA Engine  │   │ Validation & Anomaly│
        │   Priority Rules     │    │ & Routing   │   │  Detection Engine   │
        └──────────────────────┘    └─────────────┘   └─────────────────────┘
                                           │
                                           │ SQLAlchemy 2.0 Core / ORM
                                           ▼
                      ┌────────────────────────────────────────┐
                      │         Database Abstraction           │
                      │  - Production: Managed PostgreSQL      │
                      │  - Development / Testing: SQLite (WAL) │
                      └────────────────────────────────────────┘
```

---

## Project Structure

```
Complaint_Intelligence_Platform/
├── backend/
│   ├── app/
│   │   ├── anomaly/          # Anomaly detection & ground-truth evaluation
│   │   ├── api/v1/           # FastAPI REST endpoints (complaints, dashboard, etc.)
│   │   ├── classifier/       # Keyword-based category classification engine
│   │   ├── generator/        # Deterministic synthetic data generator & DB loader
│   │   ├── ingestion/        # CSV/JSON ingestion pipeline & validation
│   │   ├── models/           # 18 SQLAlchemy ORM models
│   │   ├── priority/         # Priority assignment rules & safety overrides
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── sla/              # SLA deadline calculation & breach monitoring
│   │   ├── validation/       # 15-check data quality validation engine
│   │   ├── config.py         # Application settings & environment variables
│   │   ├── database.py       # Engine creation, connection pooling & dialect detection
│   │   └── main.py           # FastAPI application factory & health check
│   ├── data/                 # Baseline dataset exports & anomaly benchmarks
│   ├── scripts/              # Migration, verification & diagnostic scripts
│   ├── tests/                # 136+ unit, integration & regression tests
│   ├── cli.py                # Command-line interface
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/            # Dashboard, Complaints, Customers, Reports, etc.
│   │   ├── api.ts            # Typed Axios client & endpoint wrappers
│   │   ├── App.tsx           # Layout, navigation & dynamic DB dialect indicator
│   │   └── main.tsx          # Application entry point
│   ├── package.json          # Node.js dependencies & scripts
│   └── vite.config.ts        # Vite build configuration
├── render.yaml               # Render Infrastructure-as-Code Blueprint
├── .gitignore                # Version control exclusions
└── README.md                 # Project documentation
```

---

## Prerequisites

Before setting up the project locally, verify that your development machine has the following tools installed:

- **Git**: Version 2.30+ (`git --version`)
- **Python**: Version 3.11, 3.12, or 3.13 (`python --version`)
- **Node.js**: Version 18+ and npm 9+ (`node -v` and `npm -v`)

---

## Local Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/raghu-122/Complaint_Intelligence_Platform.git
cd Complaint_Intelligence_Platform
```

### 2. Backend Setup

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   - **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure local environment variables:
   ```bash
   # Copy template
   cp .env.example .env
   ```
   *Note: By default, `DATABASE_URL` is configured to use a local SQLite database (`sqlite:///./complaint_intelligence.db`). No cloud credentials are required for local development.*

5. Seed initial data for local development (using the deterministic canonical seed `20261022`):
   ```bash
   # Generates ~50 complaints for local development (SQLite only):
   python cli.py generate --scale starter --seed 20261022 --clear

   # Or generate the full dataset for local testing:
   # python cli.py generate --scale full --seed 20261022 --clear
   ```
   *Note: Destructive `--clear` commands are strictly restricted to local development environments and are rejected by production server guards. Production dataset restoration must use the administrative migration procedure below.*

### 3. Frontend Setup

1. Open a new terminal and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

---

## Running the Application Locally

### Step 1: Start the Backend Server

From the `backend/` directory with your virtual environment activated:

```bash
python cli.py server --port 8000
```

- **API Base**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Diagnostics**: [http://localhost:8000/health](http://localhost:8000/health)

### Step 2: Start the Frontend Development Server

From the `frontend/` directory:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your web browser. The dynamic topbar badge will display `DB SQLite` when running against your local database.

---

## Database Migration (SQLite to PostgreSQL)

To migrate an existing SQLite database into a managed PostgreSQL instance (e.g., Render Managed PostgreSQL):

1. **Preflight Verification (Read-Only)**:
   Confirms destination connectivity, ensures PostgreSQL tables exist, widens column definitions, and verifies the destination database is completely empty:
   ```powershell
   $env:DATABASE_URL = "postgresql://user:password@hostname:5432/dbname"
   python backend/scripts/migrate_sqlite_to_pg.py --sqlite-path backend/complaint_intelligence.db --preflight-only
   ```

2. **Execute Safe Live Migration**:
   Migrates all 18 tables in topological foreign-key order inside a single atomic transaction, synchronizes serial primary-key sequences, and asserts exact source-vs-destination row count matches:
   ```powershell
   python backend/scripts/migrate_sqlite_to_pg.py --sqlite-path backend/complaint_intelligence.db
   ```

3. **Production Dataset Restoration (Approved Administrative Procedure)**:
   Restoring an existing production PostgreSQL database from a verified backup must never use synthetic data generators. Restorations must use the administrative restoration flag `--clean-destination-for-restore`. This purges tables in exact reverse foreign-key dependency order, streams and loads all 18 tables from backup, synchronizes auto-increment sequences, and asserts 100% row-count equality within a **single atomic transaction** (rolling back both deletions and insertions on any failure):
   ```powershell
   python backend/scripts/migrate_sqlite_to_pg.py --sqlite-path backend/complaint_intelligence_backup_20261030_063936.db --pg-url "postgresql://user:password@hostname:5432/dbname" --clean-destination-for-restore
   ```

---

## Test Execution

### 1. Full Backend Test Suite
Run the complete test suite (136+ unit and integration tests):
```bash
cd backend
pytest
```
*Expected output: `136 passed, 0 failures`.*

### 2. Live End-to-End Workflow Verification
Execute the self-contained live verification script (creates an isolated database copy, verifies full complaint lifecycle, customer messaging, escalation, validation, and anomaly evaluation):
```bash
cd backend
python scripts/verify_e2e_live.py
```
*Expected output: `12 PASSED | 0 FAILED`.*

### 3. Frontend Lint & Production Build
```bash
cd frontend
npm run lint
npm run build
```
*Expected output: Exit code 0, 0 ESLint errors, production bundle compiled to `dist/`.*

---

## Security & Reliability Notes

- **Zero Hardcoded Secrets**: All connection strings, credentials, and configuration flags are loaded via environment variables (`DATABASE_URL`, `APP_ENV`, `CORS_ORIGINS`).
- **SQL Injection Prevention**: All queries utilize SQLAlchemy parameterized statements and ORM expressions. No dynamic string interpolation is executed.
- **Connection Pool Tuning**: PostgreSQL engine connections use configured pool limits (`pool_size=5`, `max_overflow=10`, `pool_recycle=1800`) to prevent connection exhaustion on cloud database starter plans.
- **Transactional Integrity**: Multi-table insertions and migrations operate within atomic transactions with automatic rollback on error.
