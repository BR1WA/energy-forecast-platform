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
python -m pip install -r requirements-ml.txt
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

The 168-hour forecast is disabled by default. After the packaged week artifact
has passed its integrity and CPU warm-up checks, enable it explicitly:

```dotenv
FORECAST_168H_ENABLED=true
```

If the optional week artifact later fails, the backend keeps the accepted
24-hour readiness independent and removes Week from advertised capabilities.

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
- `GET /api/v1/system/ready`: database and primary 24-hour Global TFT warm-up,
  plus per-artifact details for any enabled optional horizon.
- `GET /api/v1/system/health`: backward-compatible health summary.

Readiness returns HTTP 503 when the database is unavailable or the primary
24-hour checkpoint fails integrity validation or warm-up. An optional 168-hour
failure is reported under `forecast_artifacts` without taking the stable day
service offline. Liveness remains available so
operators can distinguish a dead process from an unready dependency.

## Startup failure policy

Database migrations run before background tasks start. Any migration error stops
backend startup. Inspect backend logs, correct the migration or configuration,
and restart; do not bypass a failed migration.

## Product backups and restore

Run backups from the repository root while the Compose stack is running. Store
the resulting file outside this repository and outside the application host when
possible:

```powershell
.\scripts\backup_product.ps1 -OutputDirectory "D:\energyai-backups\energyai-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

The restore command replaces data in the Compose database. Verify the backup and
target first, stop application writes, then use the explicit `-Force` switch:

```powershell
docker compose stop frontend backend alerts-worker email-worker avatar-cleanup-worker
.\scripts\restore_product.ps1 -BackupDirectory "D:\energyai-backups\energyai-20260719-120000" -Force
docker compose up -d backend alerts-worker email-worker avatar-cleanup-worker frontend
curl --fail http://localhost:8000/api/v1/system/ready
```

Do not test restores against a client database. Rehearse the procedure on a
separate environment before deployment.

Each Product V1 backup contains a PostgreSQL custom-format dump, the complete
avatar volume, and SHA-256 checksums in `manifest.json`. After an isolated restore,
verify user/site/meter/readings counts, representative ownership joins, forecast
artifact fingerprints, every outbox status count, and avatar hashes. Fetch at least
one restored avatar through `/static/avatars/<opaque-key>.webp` and decode it. The
repeatable database/avatar fixture verifier is
`backend/scripts/verify_g6_restore.py`.

## Mail worker operation

- Deploy: migrate first, start the backend, then start `email-worker`; readiness
  reports the configured provider independently from queue backlog.
- Drain: disable new email-producing features, leave the worker running until no
  `pending`, `retry`, or live `processing` rows remain, then stop it. Expired leases
  are safe for another worker to claim.
- Retry: use the audited administrative dead-letter retry command/API only after
  correcting the provider failure. Never edit attempts, leases, or payloads by hand.
- Provider outage: leave in-app alerts/auth responses available, monitor retry/dead
  counts, and disable email-dependent registration if delivery is unavailable.
  Restoring the provider resumes bounded backoff; it does not duplicate sent rows.
- Rollback: stop producers and workers, drain or snapshot the outbox, roll back the
  application image, and keep the database at the newest migration understood by
  that image. Restore a backup instead of manually reversing delivered mail.

## Credential and feature rotation

- JWT/action-token key: drain the mail queue first. Rotation invalidates existing
  refresh sessions and sealed action links, so revoke sessions and require new
  verification/reset requests. Never run old and new keys concurrently unless an
  explicit multi-key verifier has been implemented.
- SMTP/provider credentials: stop the mail worker, update the secret manager or
  deployment environment, restart, verify readiness, send a controlled message,
  then retry eligible dead letters.
- Google client credential: disable `GOOGLE_AUTH_ENABLED`, rotate the server/client
  IDs together, deploy backend and frontend, run a controlled login/link/unlink
  journey, then re-enable. Local-password users remain able to sign in.
- Feature disable: email, Google authentication, and the optional 168-hour model
  have independent configuration gates. Disable the affected capability and keep
  the stable local session, in-app alerts, and 24-hour forecast surfaces available.

## Avatar cleanup worker

Run one or more `avatar-cleanup-worker` instances against the shared durable avatar
volume. Jobs are created in the same transaction as the account/avatar database
change, then objects are removed only after commit. Failures use bounded retry and
move to `dead`; inspect the sanitized error and retry operationally after fixing the
storage condition. Do not delete database rows to hide orphaned files.

## G7 production handoff

Automated Product V1 validation does not substitute for operator-owned integration
acceptance. Before enabling production capabilities, provide legal owner/contact/
support values, public frontend/API URLs and cookie origins, durable backup paths,
an approved SMTP sender and credentials, and Google OAuth client credentials with
approved staging origins. Keep email and Google authentication disabled until their
controlled staging journeys complete. Record the real-provider result separately;
captured mail and Google test-double results are not proof of external delivery or
console configuration.

The Product V1 release gate also requires a clean-source audit. Do not ship while
tracked raw datasets, checkpoints, notebooks, notebook outputs, caches, or cloned
repositories remain in the release tree. Removing or relocating legacy tracked
research material requires a separately approved repository-hygiene change; it is
not safe to delete it as part of deployment.
