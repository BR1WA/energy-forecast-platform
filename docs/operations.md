# EnergyAI Operations Guide

## Required runtimes

- Python 3.11
- Node.js 20
- Docker Engine with Docker Compose v2 for the container workflow

## Local backend

1. Copy `backend/.env.example` to `backend/.env`.
2. Set a random JWT secret of at least 32 characters and an admin password of
   at least 12 characters.
3. Set `DEBUG=True` only for local development.
4. Install and migrate:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m app.cli migrate
python -m app.cli create-admin
python -m uvicorn app.main:app --reload --port 8000
```

The application no longer creates an administrator during startup. Running
`create-admin` twice exits without changing the existing account.

## Local frontend

```powershell
cd frontend
npm ci
npm run dev
```

The frontend uses a system font stack and does not download fonts while building.

## Docker Compose

1. Copy `.env.example` to `.env`.
2. Replace every `replace_with_...` value.
3. Start the stack:

```powershell
docker compose up --build -d
docker compose ps
```

4. Create the first administrator:

```powershell
docker compose exec backend python -m app.cli create-admin
```

Compose refuses to render when required secrets are missing. Production should
keep `DEBUG=false`.

## Demo data

Demo seeding is intentionally separate from startup and is blocked outside debug
mode. It creates presentation users and generated forecast history.

```powershell
cd backend
$env:ALLOW_DEMO_SEED="true"
$env:DEMO_USER_PASSWORD="choose-a-demo-password"
python seed_db.py
```

Never run the demo seed command against a client or production database.

## Quality gates

```powershell
cd backend
python -m app.cli migrate
python -m pytest -q

cd ..\frontend
npm run lint
npm run typecheck
npm run build
```

The backend Dockerfile also provides a test target:

```powershell
docker build --target test -t energy-backend-test -f backend/Dockerfile .
docker run --rm --env-file backend/.env energy-backend-test
```

## Health endpoints

- `GET /health`: process liveness alias.
- `GET /api/v1/system/live`: process liveness for orchestration.
- `GET /api/v1/system/ready`: database and active-model artifact readiness.
- `GET /api/v1/system/health`: backward-compatible health summary.

Readiness returns HTTP 503 when the database is unavailable, there is no active
model, or required model artifacts are missing. Liveness remains available so
operators can distinguish a dead process from an unready dependency.

## Startup failure policy

Database migrations run before background tasks start. Any migration error stops
backend startup. Inspect backend logs, correct the migration or configuration,
and restart; do not bypass a failed migration.
