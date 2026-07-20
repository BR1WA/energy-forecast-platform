# EnergyAI

EnergyAI is a Master's PFE platform for monitoring and forecasting electricity
consumption for one household or small site. It gives each user one private
site and primary meter, then turns validated meter readings into live and
historical monitoring, tariff-aware cost tracking, alerts, recommendations,
reports, and a truthful 24-hour forecast.

The product is deliberately focused: it is free to use, has two roles
(admin and user), and exposes only workflows that are implemented and backed
by persisted data.

## Product Workflow

~~~text
Register -> configure one site -> import/connect/simulate readings
         -> monitor Live and historical periods
         -> understand energy, cost, freshness, and coverage
         -> generate a gated 24-hour forecast
         -> review alerts and recommendations -> export reports
~~~

### Client features

- One private site and one primary meter per user.
- CSV import with preview, validation, bounded file/row limits, and owned data.
- Authenticated push API with one-time key reveal, key rotation, test samples,
  idempotency support, and last-seen status.
- Explicitly labelled simulator for demonstrations and development.
- Live monitoring for committed push and simulator readings.
- Historical tracking for Live, Today, 7 days, Month, Year, All, and Custom
  periods, with source, freshness, coverage, and quality indicators.
- Tariff-aware energy cost, peak load, monthly budget, and period summaries.
- High-load and missing-push-data alerts with evidence, cooldown, and lifecycle
  actions.
- Deterministic recommendations based on recorded alert evidence.
- CSV and PDF exports containing ownership, source, coverage, tariff, and method
  context.
- A packaged Global TFT model for the next 24 hourly kWh values. It runs only
  when the 336-hour history, 95% coverage, maximum-gap, and finite-value gates
  pass; otherwise the UI explains the missing-data state or shows a labelled
  seasonal-naive fallback.

### Administrator features

- View users and account status.
- Change user roles and activation status while protecting the final active
  administrator.
- Inspect database, process, and packaged forecast readiness.
- Review audit events and release-facing system health.

## Architecture

~~~text
Next.js frontend (port 3000)
          |
          | REST / WebSocket live monitoring
          v
FastAPI backend (port 8000)
          |
          +-- SQLAlchemy + Alembic -> SQLite locally or PostgreSQL in Compose
          +-- packaged Global TFT artifact -> gated 24-hour inference
          +-- alert/recommendation/report services
          +-- background missing-data alert worker
~~~

Important ownership rule: normal users never select a site or meter in a
request. The backend resolves the authenticated user's single site and primary
meter server-side.

## Repository Layout

| Path | Purpose |
| --- | --- |
| backend/ | FastAPI application, database models, migrations, services, tests, and model runtime |
| frontend/ | Next.js client dashboard and user workflows |
| backend/model_artifacts/ | Versioned production forecast artifact and manifest |
| docs/operations.md | Local setup, Docker, health checks, backups, and restore procedure |
| docs/PFE_RELEASE_NOTES.md | Demonstration walkthrough, validation evidence, and known limitations |
| docs/PRODUCT_IMPLEMENTATION_PLAN_2026-07-20.md | Product scope and completed PFE milestones |
| scripts/ | Backup and restore helpers |
| models/, notebooks/, research/ | Research and training material, not automatically used by production runtime |

## Requirements

- Python 3.11
- Node.js 20 and npm
- Docker Engine with Docker Compose v2 for the container workflow
- PostgreSQL 16 when running the production-like Compose stack

## Quick Start: Local Development

### 1. Configure the backend

From the repository root:

~~~powershell
Copy-Item backend\.env.example backend\.env
~~~

Edit backend/.env and set a JWT secret with at least 32 characters and an
admin password with at least 12 characters. SQLite is the default local
database.

### 2. Install and migrate the backend

~~~powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-ml.txt
python -m app.cli migrate
python -m app.cli create-admin
python -m uvicorn app.main:app --reload --port 8000
~~~

The ML dependency file is required for local Global TFT inference. The normal
test target intentionally excludes Torch to keep CI resource usage bounded.

### 3. Start the frontend

In another terminal:

~~~powershell
cd frontend
npm ci
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
~~~

Open http://localhost:3000. The backend API and interactive OpenAPI
documentation are available at http://localhost:8000/docs.

## Quick Start: Docker Compose

From the repository root:

~~~powershell
Copy-Item .env.example .env
~~~

Replace the database password, JWT secret, and admin password in .env, then
start the stack:

~~~powershell
docker compose up --build -d
docker compose ps
docker compose exec backend python -m app.cli create-admin
~~~

Open http://localhost:3000. The backend is exposed at port 8000, PostgreSQL at
5432, and the alert worker runs as a separate Compose service.

Stop the stack with:

~~~powershell
docker compose down
~~~

Use docs/operations.md for production configuration, readiness troubleshooting,
backup, restore, and deployment details.

## CSV Input Contract

CSV files must be UTF-8 and contain:

- timestamp, including a timezone or an unambiguous ISO-8601 offset
- active_power_kw or the accepted GAP alias

Optional columns include reactive_power_kvar, voltage_v, and current_a.
The application validates rows before persistence. The current UI limit is
5 MB and 10,000 rows per import.

Example:

~~~csv
timestamp,active_power_kw,voltage_v
2026-07-20T08:00:00+01:00,0.42,230.1
2026-07-20T08:05:00+01:00,0.47,230.4
~~~

## Push API

Users generate a meter key from Settings. The key is shown once and should be
stored by the sending device. Push samples are authenticated with that key and
are rejected when invalid, out of order, duplicated, or incompatible with the
meter configuration. The interactive API contract is available at /docs after
the backend starts.

## Forecast Contract

The production forecast is intentionally limited to 24 hourly values. The
Global TFT artifact requires:

- 336 hourly input values
- at least 95% observed coverage
- no unresolved gap longer than 3 hours
- finite, valid hourly energy values

The UI displays the model name, version, source, coverage, target timestamps,
quantiles, preprocessing provenance, inference method, and fallback reason.
Research checkpoints and multi-household experiments are not loaded by the
production service.

## Quality Gates

Backend:

~~~powershell
cd backend
python -m pytest -q
~~~

Frontend:

~~~powershell
cd frontend
npm run lint
npm run typecheck
npm run build
~~~

Docker test image:

~~~powershell
docker build --target test -t energy-backend-test -f backend/Dockerfile .
docker run --rm --env-file backend\.env energy-backend-test
~~~

Runtime checks:

- GET /health is a liveness alias.
- GET /api/v1/system/live checks process liveness.
- GET /api/v1/system/ready checks database readiness and packaged model
  integrity/warm-up.
- GET /api/v1/system/health returns a compatibility health summary.

## Scope Boundaries

The following are intentionally deferred until independently validated and
implemented:

- 168-hour, weekly, and monthly production forecasting
- Pull connectors to utility providers
- Google authentication, email verification, password reset email, and alert
  email delivery
- Gemini chatbot and AI recommendations
- Subscriptions, plans, billing, and payment flows
- Remote appliance, battery, or demand-response control
- Multi-site management

These boundaries are part of the PFE product design. They keep the current
application honest and usable while leaving a clear Product V1 path.

## Documentation

- Operations guide: docs/operations.md
- PFE release notes: docs/PFE_RELEASE_NOTES.md
- Product implementation plan: docs/PRODUCT_IMPLEMENTATION_PLAN_2026-07-20.md
- Forecast artifact contract: docs/FORECAST_ARTIFACT.md

## License and Academic Context

EnergyAI is a Master's PFE project. Add the repository's final academic or
institutional license before public redistribution.
