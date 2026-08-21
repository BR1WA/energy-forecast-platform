# EnergyAI repository guidance

These rules apply repository-wide. Also follow the migration guidance in `.agents/AGENTS.md` and the version-specific Next.js guidance in `frontend/AGENTS.md`; do not duplicate or override them.

## Architecture

EnergyAI is a Master PFE electricity-consumption forecasting platform.

- `frontend/`: Next.js 16 application (`src/`) and Playwright browser journeys (`e2e/`).
- `backend/`: FastAPI application (`app/`), Alembic migrations (`alembic/`), model artifacts, and backend tests (`tests/`). PostgreSQL 16 is the production-equivalent database.
- `models/`, `training/`, `experiments/`, and `notebooks/`: governed forecasting/model research and release inputs; training validation also lives in `tests/training/`.
- Background work is exposed through `backend/app/cli.py` and implemented by dedicated simulation, alerts, email, and avatar-cleanup workers. `docker-compose.yml` defines the API, workers, PostgreSQL, and frontend as separate services.
- `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`: container builds and the local seven-service stack.
- `.github/workflows/ci.yml`: backend, PostgreSQL, frontend, browser, audit, image, secret-scan, and Compose gates. `.github/workflows/azure-release-images.yml` packages an explicitly supplied tested Git SHA for Azure Container Apps.
- `report/source/`: LaTeX PFE report; `report/evidence/` and `report/qa/` hold verified evidence and QA records.

## Engineering rules

- Inspect the established architecture before editing and prefer the smallest correct fix. Extend existing subsystems; do not create parallel implementations.
- Preserve API compatibility unless a breaking change is explicitly required.
- Preserve `backend/alembic/versions/` history. Never delete, rewrite, or retroactively modify a committed/generated migration; add a corrective migration and follow `.agents/AGENTS.md`.
- Never weaken tests, authentication, authorization, ownership checks, security headers, rate limiting, or dependency integrity to make a gate pass.
- Never fabricate data, timestamps, model metrics, scientific results, validation evidence, or deployment evidence. Keep forecast provenance and scientific limitations explicit and honest.
- Never silently present a historical forecast as current.
- Preserve the API/worker boundary. Simulation advancement belongs in the dedicated simulation worker, never API request handling.
- Do not destroy or rewrite CSV, push-ingested, or measured data to support demo behavior.

## Autonomy and safety

For implementation or fix requests, freely inspect the repository, edit in-scope local files, run non-destructive tests, linters, builds, audits, and local validation, and investigate failures to their root cause. Normal local inspection, editing, and testing need no confirmation.

Require explicit approval before pushing Git changes; deploying; publishing a release or tag; rewriting Git history; performing destructive database operations; deleting user data; creating or deleting cloud resources with material cost or risk; or substantially broadening scope. An explicit user authorization overrides only its corresponding restriction.

## Validation

Use `.github/workflows/ci.yml` as the canonical full-gate definition and `README.md` (`Useful checks`) for the short local workflow. Install locked dependencies with `backend/requirements-*.lock` and `frontend/package-lock.json`; do not substitute a new dependency manager.

- Backend/training tests, from the repository root: `python -m pytest -q`. The CI coverage gate is `python -m pytest -q --cov=app --cov-report=term --cov-fail-under=70`.
- PostgreSQL-backed suite: provide the CI-required `DATABASE_URL`, `DEBUG`, JWT/admin, and legal/support environment variables; run `python -m app.cli migrate` and `python -m alembic check` from `backend/`, then run the CI coverage command from the root. The PostgreSQL service and exact environment are defined in the CI `backend` job.
- Frontend, from `frontend/`: `npm run lint`, `npm run typecheck`, `npm run build`, and `npm run test:browser`. The Playwright command runs the six projects in `frontend/playwright.config.ts`.
- Dependency/security audits: from `backend/`, run `pip-audit -r requirements.lock`, `pip-audit -r requirements-dev.lock`, `pip-audit -r requirements-ml.lock`, and `pip-audit -r requirements-foundation.lock`; from `frontend/`, run `npm audit --audit-level=high`. Full-history secret scanning is the CI `secret-scan` job.
- Backend test image, from the root: `docker build --build-arg INSTALL_TORCH=0 --target test -t energy-backend-test -f backend/Dockerfile .`, then use the exact `docker run` test command from the CI `backend` job.
- Compose smoke: `docker compose config --quiet`, `docker compose up --build --detach`, verify `/api/v1/system/live`, `/api/v1/system/ready`, and the frontend as in the CI `docker-smoke` job, then `docker compose down`. Do not remove volumes without approval.

For changes, run focused validation first and the broader relevant suite afterward. Report exact pass, fail, and skip counts, and never claim a check passed unless it was executed.

## Release and report discipline

- A final/deployed release must map to a known Git SHA. CI status, immutable image/Azure revision evidence, README claims, and report claims must describe the same release state.
- Freeze the application release and complete validation and deployment verification before updating final report deployment claims or creating the final tag.
- The PFE report must reflect verified repository, deployment, and model evidence.
- Never invent jury members, university administrative details, laboratory or host details, supervisor approvals, or AI-use policy/disclosure requirements; obtain human confirmation.
