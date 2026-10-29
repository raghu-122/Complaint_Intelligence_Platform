# Complaint Intelligence Platform

An enterprise customer complaint intelligence system featuring deterministic synthetic data generation, automated category classification, rule-based priority triage, SLA countdown monitoring, agent assignment routing, data quality validation, and anomaly detection with ground-truth evaluation.

---

## Key Features

- **End-to-End Complaint Lifecycle**: Tracks customer complaints from intake, order and product association, through priority triage, squad assignment, customer messaging, resolution recording, and post-resolution satisfaction surveys.
- **Automated Classification & Priority Triage**: Classifies complaints across 10 business categories using deterministic rules and assigns priority tiers (**P1 Critical** to **P4 Low**) with absolute safety overrides for hazardous products.
- **SLA Clock & Breach Tracking**: Calculates resolution deadlines (4h for P1, 12h for P2, 48h for P3, 72h for P4), tracks pause/resume intervals, and monitors breach and escalation states.
- **Skill-Based Agent Assignment**: Routes complaints to eligible agents and specialized squads based on category expertise and active workload capacity.
- **Data Validation Suite**: Runs 15 automated validation checks across referential integrity, timestamp chronology, arithmetic reconciliation, and business lifecycle rules.
- **Anomaly Detection & Benchmark Evaluation**: Injects and detects 6 distinct operational anomalies (e.g., missing customer links, resolution before creation, SLA clock inconsistencies, safety priority mismatches) evaluated against an independent ground-truth dataset.
- **Operations Dashboard**: Interactive dark-themed web interface displaying real-time complaint volumes, SLA compliance rates, status breakdowns, priority distributions, and trend analytics.
- **Full Data Export & Reproducibility**: Exports complete baseline data to CSV, JSON, and portable SQL dumps, with SHA-256 manifest verification proving 100% bitwise reproducibility under fixed seeds.

---

## Technology Stack

- **Backend**: Python 3.11+ / 3.13, FastAPI, SQLAlchemy 2.x, Pydantic v2, Uvicorn, Click, Rich
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Recharts, Lucide Icons, Axios
- **Database**: SQLite (zero-configuration local default)
- **Data & Testing**: Pandas, NumPy, Faker, Pytest, Pytest-Asyncio, HTTPX

---

## Prerequisites

Ensure the following tools are installed on your system:

- **Git**: Version 2.30+ (`git --version`)
- **Python**: Version 3.11, 3.12, or 3.13 (`python --version`)
- **Node.js & npm**: Node.js 18+ and npm 9+ (`node -v` and `npm -v`)

---

## Clone the Repository

Verify that Git is installed on your machine:

```bash
git --version
```

Clone the repository and navigate into the project directory:

```bash
# Replace <YOUR_USERNAME> and <YOUR_REPOSITORY> with your repository details
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY>.git
cd <YOUR_REPOSITORY>
```

> **Note**: If you downloaded this repository as a ZIP archive or are working locally, open a terminal in the unpacked `Complaint_Intelligence_Platform` root folder.

---

## Installation and Setup

### 1. Backend Setup

Open a terminal in the repository root and navigate to `backend/`:

```bash
cd backend
```

Create and activate a Python virtual environment:

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

- **Windows (Command Prompt)**:
  ```cmd
  python -m venv venv
  .\venv\Scripts\activate.bat
  ```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Create your local environment configuration from `.env.example`:

- **macOS / Linux**:
  ```bash
  cp .env.example .env
  ```
- **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```

> **Note**: The default `.env` configuration uses a local SQLite database (`sqlite:///./complaint_intelligence.db`) and requires no external API keys or cloud services.

### 2. Generate Initial Database & Baseline Data

Run the CLI data generator to initialize SQLite tables and generate the baseline dataset with the canonical seed (`20261022`):

```bash
# Generate the full evaluation dataset (5,000 customers, 8,000 orders, 2,000 complaints, 6,000 messages)
python cli.py generate --scale full --seed 20261022 --clear

# Or for a quick lightweight developer dataset (~50 complaints):
# python cli.py generate --scale starter --seed 20261022 --clear
```

### 3. Frontend Setup

In a new terminal, navigate to the `frontend/` directory and install npm packages:

```bash
cd frontend
npm install
```

---

## Run the Application

The platform runs as two local services: the FastAPI backend server and the Vite React frontend.

### Step 1: Start the Backend Server

In your backend terminal (with the virtual environment activated):

```bash
cd backend
python cli.py server --port 8000
```

The backend server will start at:
- **API Server**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

Confirm the backend is running by visiting [http://localhost:8000/health](http://localhost:8000/health) in your browser. It should return:
```json
{"status": "healthy", "service": "complaint-intelligence-platform"}
```

### Step 2: Start the Frontend Application

In your frontend terminal:

```bash
cd frontend
npm run dev
```

The frontend development server will start at:
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)

Open [http://localhost:5173](http://localhost:5173) in your browser to view the application.

---

## Basic Usage

Follow this quick walkthrough to explore the primary workflows of the application:

1. **Dashboard (`/`)**: View executive KPIs including total active complaints, SLA compliance rates, average resolution times, category distribution, and priority breakdowns.
2. **Complaints (`/complaints`)**: Browse the complete complaint registry. Use search, filter by priority (**P1–P4**), status (**Open, In Progress, Resolved, Closed**), category, or toggle **Safety Issues Only**. Click any complaint to view its full details, message history, assignment trail, and SLA clock.
3. **Customers (`/customers`)**: View customer accounts, complaint frequencies, vulnerability indicators, and account tiers (**VIP, Premium, Standard**).
4. **Validation Suite (`/validation`)**: Run the automated 15-check data quality suite. You can also run this via CLI:
   ```bash
   cd backend
   python cli.py validate
   ```
5. **Anomaly Detection (`/anomalies`)**: Test the anomaly engine. Inject test anomalies and run detection to compare flagged records against independent ground truth:
   ```bash
   cd backend
   python cli.py inject-anomalies --count 6
   python cli.py detect-anomalies
   ```
6. **Reports & Exports (`/reports`)**: Browse exported CSV, JSON, and SQL dumps. Download individual entity files directly through the UI, or verify baseline reproducibility:
   ```bash
   cd backend
   python cli.py reproduce --scale full --seed 20261022
   ```

---

## Tests

### Backend Automated Test Suite

Run the full pytest suite from the `backend/` directory:

```bash
cd backend
pytest tests/ -q
```

- **Verified Result**: **112 passed** in ~10 seconds across 9 test modules covering APIs, generator logic, priority rules, SLA engine, validation, anomaly detection, exports, and reproducibility.

### Frontend Production Build & Type Check

Run TypeScript validation and the production bundle build from the `frontend/` directory:

```bash
cd frontend
npm run build
```

- **Verified Result**: **Exit code 0**, 0 TypeScript errors. Assets compiled to `dist/`.

### Live End-to-End Workflow Verification

Execute the self-contained live API test script against an isolated test database:

```bash
cd backend
python scripts/verify_e2e_live.py
```

- **Verified Result**: **12 / 12 checks passed** (E2E lifecycle, CRUD persistence, and SLA validation).

---

## Troubleshooting

### 1. Python Virtual Environment Activation Error (Windows)
- **Symptom**: PowerShell displays `cannot be loaded because running scripts is disabled on this system`.
- **Fix**: Temporarily allow script execution in your PowerShell session:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\venv\Scripts\Activate.ps1
  ```

### 2. Port 8000 or 5173 Already in Use
- **Symptom**: `OSError: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`.
- **Fix**: Either terminate the existing process using the port, or run the backend on an alternate port:
  ```bash
  python cli.py server --port 8001
  ```
  If changing the backend port, set `VITE_API_URL=http://localhost:8001` in a `frontend/.env` file.

### 3. SQLite Database Locked
- **Symptom**: `sqlite3.OperationalError: database is locked`.
- **Fix**: Ensure that the FastAPI backend server is stopped before running generator resets with `python cli.py generate --clear`.

### 4. Missing Dependencies or Clean Reinstallation
- **Backend Fix**:
  ```bash
  pip install --force-reinstall -r requirements.txt
  ```
- **Frontend Fix**:
  ```bash
  cd frontend
  rm -rf node_modules package-lock.json
  npm install
  ```
