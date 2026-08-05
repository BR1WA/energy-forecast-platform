# EnergyAI Full Application Audit

**Audit date:** 2026-07-31

**Workspace:** local Product V1 worktree

**Branch:** `release/product-v1`

**Revision:** `1e67921` (`test(product): cover final settings and search rules`)

**Snapshot status:** Dirty working tree; the audit includes tracked code plus the local changes visible at audit time.
**Overall verdict:** **Live operational release candidate; conditional release pending the red CI dependency gate and documented hardening items.**

## 1. Executive summary

EnergyAI is a substantial, coherent PFE application rather than a UI-only prototype. The audited source contains a Next.js 16 frontend, an 80-operation FastAPI API, SQLAlchemy/Alembic persistence, authenticated single-site ownership, bounded ingestion, monitoring, alerts, recommendations, reports, account lifecycle controls, background delivery workers, and packaged 24-hour and optional 168-hour Global TFT forecasting.

The source-level and live deployment quality gates are strong:

- Backend on SQLite: **96 passed, 4 PostgreSQL-only skips**.
- Backend on a disposable PostgreSQL database migrated from an empty schema: **100 passed, 0 skipped**. The isolated audit database was removed after the run.
- Frontend: ESLint, TypeScript, and the 25-route production build passed.
- Browser matrix: **107/108 passed**; the one WebKit reload failure passed on its isolated rerun (**1/1**), indicating a flaky gate rather than a reproduced application failure.
- Production npm dependency audit: **0 known vulnerabilities**.
- Compose configuration is valid and all six services are running with zero restarts.
- PostgreSQL, backend, and frontend Docker health checks pass; alert, email, and avatar-cleanup workers are running.
- Live readiness is HTTP 200. PostgreSQL is at Alembic head, both forecast artifacts are warmed, and email reports no processing/retry/dead backlog.

The current machine is now suitable for a controlled demonstration. Remaining release conditions are:

1. The exact frontend dependency audit used by CI currently fails because of high-severity advisories in development tooling. The production dependency tree remains clean.
2. The full Playwright matrix has a WebKit reload flake and CI is configured with zero retries, creating a false-negative risk.
3. The separate local-development SQLite profile remains at Alembic revision `d3a9f6c1b208` and uses intentionally incomplete debug configuration. This does not affect the running Compose/PostgreSQL deployment, which is at head and fully configured.
4. The dirty working tree still prevents the live evidence from mapping to a reproducible clean commit.

No P0 data-loss or authentication-bypass defect was found during this audit. The release should remain blocked until the environment and CI items in section 10 are cleared.

## 2. Audit scope and evidence policy

The audit covered:

- application architecture and exposed product workflow;
- frontend lint, type safety, production compilation, routes, and browser behavior;
- backend tests, migration graph, configuration validation, API surface, ownership, authentication, ingestion, alerts, reporting, account controls, and workers;
- model packaging and local warm-up;
- current local database revision and aggregate row counts;
- Docker/Compose definitions and CI gates;
- production and development dependency vulnerability scans;
- source/repository hygiene and documentation consistency.

The audit did **not** mutate live application data, send email, call Google OAuth, or exercise a real external client. It did start/rebuild the configured Compose stack. A uniquely named disposable PostgreSQL database was created, migrated, tested, and removed to verify the complete suite without touching the product database. SMTP authentication and inbox delivery were not retested. Historical reports were treated as context, not current evidence.

## 3. Scorecard

| Dimension | Score | Status | Basis |
|---|---:|---|---|
| Functional completeness | 8.8/10 | Strong | Coherent user/admin workflow, persisted data, real exports, gated integrations |
| Backend correctness | 9.5/10 | Strong | 100/100 passed against isolated PostgreSQL; SQLite run passed 96 with four expected skips |
| Frontend correctness | 8.7/10 | Strong with flake | Lint/type/build pass; 107/108 matrix plus isolated rerun pass |
| Security design | 8.0/10 | Good, hardening remains | Refresh-token rotation, origin checks, RBAC, ownership tests, secret fail-fast; headers/resource controls incomplete |
| Data integrity | 9.2/10 | Strong deployment | PostgreSQL is at head; constraints/migrations/ownership pass the full suite; separate SQLite dev file is stale |
| ML product integrity | 9.2/10 | Strong | Both live artifacts warmed with verified hashes, readiness gates, provenance, truthful fallback |
| Operations/observability | 8.8/10 | Strong | Six live services, healthy core containers, ready API, workers, backup scripts, Compose/CI |
| Dependency/reproducibility | 6.8/10 | Needs action | Runtime npm tree clean; dev advisories and loose Python/ML bounds |
| Documentation/current-state accuracy | 6.5/10 | Drift present | Older audits and README scope statements conflict with current implementation |
| Current release readiness | 8.4/10 | **Conditional** | Live stack is healthy; full backend suite passes; CI dev audit and browser flake remain |

## 4. Current snapshot

### 4.1 Repository state

| Item | Observed state |
|---|---|
| Branch / commit | `release/product-v1` / `1e67921` |
| Tracked files | 330 |
| Tracked app files measured | 165 Python/TypeScript files |
| Tracked app lines measured | 18,835 |
| Working tree | Modified `app_status_audit.md`; 19 untracked non-ignored files (about 6.75 MiB) plus untracked directories |
| Ignored experiment/research output in inspected roots | 7,445 files, about 1.19 GiB |
| Git object database | About 1.10 GiB of loose objects plus about 107 MiB reported as garbage |
| Secret hygiene | `.env` files are ignored and none are tracked; no secret-looking untracked filename was found |

The dirty tree is not inherently defective, but it prevents this report from representing a reproducible commit. The large ignored experimental footprint also makes backup, cloning, and accidental inclusion riskier.

### 4.2 Current configuration profiles (values redacted)

The repository has two distinct current profiles. The running Compose profile is the deployment evidence; `backend/.env` is a separate local-development profile.

#### Running Compose/PostgreSQL profile

| Setting | Live state | Assessment |
|---|---|---|
| Database | PostgreSQL 16 | Ready and at Alembic head |
| `DEBUG` | Deployment configuration accepted | No startup secret/legal validation failure |
| Legal owner/contact/effective date | Configured | `/api/v1/system/legal` reports `configured: true`; personal values are omitted here |
| 24-hour forecast | Enabled and warmed | Ready |
| 168-hour forecast | Enabled and warmed | Ready |
| Email delivery | Enabled; outbox healthy | 0 processing, 0 retry, 0 dead |
| Google authentication | Configuration not exposed by the health endpoint | Not externally exercised in this audit |

#### Separate local SQLite profile

| Setting | State | Assessment |
|---|---|---|
| Database | SQLite | Suitable for local development only |
| `DEBUG` | Enabled | Development-only |
| JWT secret | Passed the local strength check | Good |
| Admin password | Insecure default | Allowed only because debug is enabled; not used by Compose |
| Legal owner/contact/effective date | Incomplete | Local-only; production validation would reject it |
| 24-hour forecast | Enabled, artifact available and warmed | Ready locally |
| 168-hour forecast | Disabled | Not advertised in the current local capability set |
| Email delivery | Disabled | Verification/reset/critical delivery cannot operate end to end locally |
| Google authentication | Disabled | Correctly capability-gated |

The application correctly refuses insecure or incomplete configuration when `DEBUG=false`. The incomplete SQLite profile is a local setup/maintenance issue, not evidence that the running Compose deployment is insecure.

### 4.3 Current runtime state

| Probe | Result |
|---|---|
| Docker daemon | Available |
| PostgreSQL container | Running, healthy, 0 restarts |
| Backend container | Running, healthy, 0 restarts |
| Frontend container | Running, healthy, 0 restarts |
| Alert worker | Running, 0 restarts |
| Email worker | Running, 0 restarts |
| Avatar-cleanup worker | Running, 0 restarts |
| `GET /api/v1/system/live` | HTTP 200, alive |
| `GET /api/v1/system/ready` | HTTP 200, `ready: true` |
| `GET /api/v1/system/health` | HTTP 200; backend/database/forecast/email ready |
| `GET /api/v1/system/legal` | HTTP 200, configured |
| `http://127.0.0.1:3000/` | HTTP 200 |
| `docker compose config --quiet` | Passed |

One early `docker stats --no-stream` sample showed approximately 264 MiB for the backend, 99 MiB for the frontend, 48 MiB for PostgreSQL, and 67 MiB per worker. The backend CPU sample was elevated during model warm-up and is not a steady-state performance measurement.

## 5. Architecture and implemented product surface

```text
Next.js 16 / React 19 frontend
        |
        | REST + authenticated live-monitoring channel
        v
FastAPI application (80 OpenAPI operations / 74 paths)
        |
        +-- SQLAlchemy + Alembic (SQLite dev / PostgreSQL deployment)
        +-- owned site, primary meter, readings, forecasts, alerts, actions
        +-- Global TFT 24h artifact + independently gated 168h artifact
        +-- alert, email, and avatar-cleanup workers
        +-- CSV/PDF/account archive generation
```

### 5.1 Frontend routes

The production build generated 25 routes, including:

- public landing, login, registration, verification, password recovery, privacy, terms, and support;
- setup, dashboard, usage, forecast, actions, settings, and admin;
- legacy compatibility routes for alerts, consumption, recommendations, reports, and simulation;
- the dynamically generated forecast-ready sample CSV route.

### 5.2 Backend API

The generated OpenAPI schema contains **80 operations across 74 paths**:

| Method | Operations |
|---|---:|
| GET | 38 |
| POST | 28 |
| PUT | 5 |
| PATCH | 5 |
| DELETE | 4 |

Routers cover authentication, account lifecycle, forecast, alerts, analytics, administration, settings, system health, consumption, simulation, ingestion, monitoring, and recommendations.

### 5.3 Product truthfulness

The implementation consistently separates real, simulated, CSV, push, forecast-demo, and fallback data. Forecast capability advertisement depends on feature flags, artifact manifests, checkpoint integrity, runtime availability, and warm-up. Forecast execution validates lookback length, coverage, gap length, and finite values. This is a material strength for an academic forecasting product because the UI does not silently substitute a different horizon or an unlabeled fabricated series.

## 6. Verification results

### 6.1 Backend

SQLite command: `python -m pytest -q`

```text
96 passed, 4 skipped, 1 warning in 39.29s
```

The four skipped tests are explicit SQLite environment gaps:

- three PostgreSQL email-outbox locking/lease tests;
- one PostgreSQL ownership/cascade verification test.

The warning reports the insecure development admin password. Real PyTorch model-contract and dual-horizon API tests ran; the skips were not ML skips on this machine.

PostgreSQL verification used a uniquely named disposable database on the live PostgreSQL server. The audit migrated it from an empty schema through all 17 revisions, ran the entire backend suite, and removed the database in a `finally` cleanup:

```text
100 passed, 0 skipped, 1 warning in 42.78s
```

This closes the locking, outbox lease, cascade, and ownership gap without modifying the product database.

Additional backend checks:

| Check | Result |
|---|---|
| Python bytecode compilation for `app` | Passed |
| Alembic source graph | One head: `c8f4a1b2d306` |
| Empty PostgreSQL migration path | All 17 revisions applied successfully |
| Full PostgreSQL backend suite | 100 passed, 0 skipped |
| Installed-package consistency (`pip check`) | Passed |
| Coverage report | Not available; `pytest-cov` is not installed in the active environment despite being declared in `requirements-dev.txt` |

### 6.2 Frontend

| Gate | Result |
|---|---|
| `npm run lint` | Passed, no reported warnings/errors |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; 25 routes generated |
| Playwright six-project matrix | 107 passed, 1 failed in WebKit desktop |
| Failed case isolated rerun | Passed 1/1 |

The failing case was `concurrent expired requests share one refresh, reload restores, and logout has no token body`; WebKit reported `page.reload: Frame load interrupted`. Because the same test passed alone, this audit classifies it as **gate flakiness**, not a confirmed session-management regression.

### 6.3 Dependency audits

| Scope | Result | Interpretation |
|---|---|---|
| `npm audit --omit=dev` | 0 vulnerabilities | Production frontend dependency graph is clean |
| Full `npm audit` | 9 high-severity affected packages | Development tooling chain rooted in ESLint/minimatch/brace-expansion; CI-blocking, not shipped runtime exposure |
| `pip-audit` against backend requirements | 1 advisory | `pytest 8.4.2` / `PYSEC-2026-1845`; fixed in 9.0.3, but current dev constraint is `<9` |

The CI frontend job runs full `npm audit --audit-level=high`, so it is expected to fail until the development-tool chain is remediated or the policy is deliberately scoped. The backend CI audit currently checks `requirements.txt`, not `requirements-dev.txt`, so the pytest advisory does not fail that job.

## 7. Security and privacy assessment

### 7.1 Controls that are present

- Access tokens remain in memory; refresh tokens are HttpOnly cookies rather than browser storage.
- Refresh tokens are hashed at rest, rotated on use, and replay is rejected.
- Cookie-mutating session endpoints enforce trusted-origin checks.
- Refresh cookies use `SameSite=Lax`, and the secure flag is enabled outside debug mode.
- Authentication endpoints have targeted rate limits and neutral account-recovery responses.
- Google identities require signed credentials plus one-time state/nonce challenges and explicit account linking.
- Normal users resolve their owned site/meter server-side; ownership tests cover cross-user access.
- Account export and irreversible deletion are implemented with reauthentication.
- Avatar uploads have byte, image, and dimension validation plus cleanup jobs.
- CSV uploads are bounded at 5 MiB and 10,000 rows; push batches are bounded at 1,000 samples.
- Deployment startup rejects weak JWT/admin secrets and missing legal/integration configuration.
- CI includes a full-history gitleaks job.

### 7.2 Security gaps and constraints

1. **Application security headers are absent.** `frontend/next.config.ts` defines no headers and no reverse proxy is included in Compose. Unless an external ingress adds them, responses lack an application-defined CSP, HSTS, `X-Content-Type-Options`, frame policy, and referrer policy.
2. **Expensive authenticated operations have no explicit rate limit or queue.** Forecast inference and report generation are not covered by the targeted authentication rate limits. A valid user could create avoidable CPU/memory pressure.
3. **Rate limiting is process-local.** SlowAPI uses the remote address without a shared backend, which matches the documented single-instance scope but will not enforce a global limit if the API is horizontally scaled.
4. **API documentation is public in all environments.** `/docs`, `/redoc`, and `/openapi.json` are always enabled. This is often acceptable, but production policy should be explicit.
5. **Password policy is length-only at eight characters.** This is acceptable for a PFE prototype with rate limiting and bcrypt, but a public deployment should consider breached-password screening and a longer minimum.

No committed environment file or obvious secret-bearing untracked filename was found. This is a filename/tracking check, not a substitute for the CI history scan.

## 8. Database and migration assessment

### 8.1 Source schema

The source contains 17 Alembic revisions and one current head (`c8f4a1b2d306`). The model includes database-level uniqueness, checks, and query indexes for:

- one site per user and one primary configuration per site;
- meter/timestamp deduplication and ingestion idempotency;
- Google identity uniqueness and one-time OAuth challenges;
- email outbox deduplication, state constraints, leases, and due-work indexing;
- one recommendation per alert;
- account-action purpose constraints;
- avatar cleanup job deduplication and retry state.

This is considerably stronger than enforcing integrity only in route handlers.

### 8.2 Running PostgreSQL database

The Compose PostgreSQL database reports `c8f4a1b2d306 (head)`. Aggregate counts were collected without exposing user content:

| Table | Rows |
|---|---:|
| users | 7 |
| sites | 7 |
| meters | 7 |
| smart_meter_readings | 42,629 |
| forecasts | 4 |
| alerts | 8 |
| recommendations | 8 |
| audit_events | 34 |
| email_outbox | 1 |
| avatar_cleanup_jobs | 0 |

The sole outbox row is `sent`; there are zero queued, processing, retry, or dead rows. The empty-database migration and complete 100-test PostgreSQL run provide additional evidence that the current schema works independently of accumulated product data.

### 8.3 Separate local SQLite database

The local file `backend/energy_forecast.db` is 372,736 bytes and reports revision `d3a9f6c1b208`. It is behind source head. A read-only ORM census failed with:

```text
sqlite3.OperationalError: no such column: users.email_verified_at
```

Raw read-only aggregate counts from the stale file:

| Table | Rows |
|---|---:|
| users | 7 |
| sites | 7 |
| meters | 7 |
| smart_meter_readings | 11 |
| forecasts | 20 |
| alerts | 22 |
| recommendations | 0 |
| audit_events | 1 |
| refresh_tokens | 1 |
| email_outbox | Not present in the stale schema |

The local application calls Alembic during startup and should migrate this file before serving. A backup is still required before first local-SQLite startup because the audit did not execute the in-place upgrade against this specific file. This does not affect the running PostgreSQL deployment.

## 9. ML and forecasting assessment

### 9.1 Current capability state

| Horizon | Capability | Warm-up | Artifact fingerprint |
|---|---|---|---|
| 24 hours | Enabled/available in Compose | Passed live readiness | `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d` |
| 168 hours | Enabled/available in Compose | Passed live readiness | `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93` |

The separate SQLite development profile disables 168 hours, but the running Compose profile advertises and warms both artifacts. The readiness response preserves the independent status and fingerprint of each horizon.

### 9.2 Strengths

- independent manifests and checkpoints per horizon;
- artifact fingerprint validation and warm-up readiness;
- strict 336-hour input contract, coverage and maximum-gap gates;
- persisted horizon, model identity, targets, quantiles, input coverage, and fallback reason;
- cross-user result isolation tests;
- UI and PDF behavior tested for both horizons;
- research and experiment folders are not loaded as production artifacts.

### 9.3 Constraints

- `torch>=2.0.0` and several scientific packages use lower bounds rather than a locked, tested production environment, reducing build reproducibility;
- CPU inference is executed in the API process and has no explicit concurrency/backpressure control;
- the runtime is intentionally single-instance for simulation/live behavior;
- model quality is artifact-specific and should continue to be reported separately from software correctness.

## 10. Findings and remediation priority

### P0 — critical

No P0 finding was identified.

### P1 — release blockers

#### P1.1 CI frontend dependency audit is red

Full `npm audit` reports nine high-severity affected packages in the development tooling graph. The production-only audit is clean, but CI intentionally audits the full graph and will exit nonzero.

**Required action:** Upgrade the compatible ESLint/Next tooling chain and regenerate the lockfile. If no compatible upstream resolution exists, document a time-bounded exception based on non-runtime reachability; do not silently weaken the gate.

### P2 — high-priority hardening

#### P2.1 Browser matrix is flaky under WebKit load

One session reload test failed in the full run and passed in isolation. CI has `retries: 0`.

**Required action:** Make the reload synchronization deterministic, run the WebKit project repeatedly, and consider retaining one CI retry with trace collection only after the underlying race is understood.

#### P2.2 Security response headers are not defined

No security-header policy exists in Next.js or FastAPI/Compose.

**Required action:** Add and test CSP, HSTS for HTTPS deployments, content-type sniffing protection, frame policy, referrer policy, and an explicit permissions policy at the application or ingress layer.

#### P2.3 Expensive endpoints lack resource controls

Forecast inference, PDF creation, and large authenticated workflows are outside the targeted auth rate limits.

**Required action:** Add per-user limits and concurrency control, record latency/resource metrics, and define an overload response.

#### P2.4 Documentation has current-state drift

The README still lists Google authentication, verification/reset email, and alert email as deferred even though the implementation and browser tests now expose them behind capability gates. Older audits claim healthy containers, 44 tests, and an earlier migration head.

**Required action:** Update the README scope language to “implemented but disabled until configured,” label historical audits as superseded, and use this report or a generated status file for current evidence.

### P3 — maintainability and reproducibility

#### P3.1 Python environments are not fully locked

Core scientific and ML packages use broad lower bounds; `torch` is `>=2.0.0`. Rebuilding later can select materially different binaries.

**Recommended action:** Produce a Python 3.11 lock/constraints file for CI and release images while retaining readable top-level requirement declarations.

#### P3.2 Development dependency advisory and environment drift

`pytest 8.4.2` is affected by `PYSEC-2026-1845`, the fix is in 9.0.3, and the project currently constrains pytest below 9. The active environment also lacks declared `pytest-cov`.

**Recommended action:** Validate pytest 9 compatibility, update the constraint, reinstall the development environment from the declared file, and establish a coverage baseline.

#### P3.3 Repository hygiene

The workspace contains large ignored experiment output and a large loose Git object store with reported garbage. There are also historical/untracked research and audit artifacts.

**Recommended action:** Classify files as product source, reproducible research evidence, external artifact storage, or disposable output; commit only intentional evidence, add precise ignores, and perform a safe Git maintenance pass after backing up and confirming no needed dangling objects.

#### P3.4 Legacy frontend API surface

`frontend/src/services/api-client.ts` and `frontend/src/services/system.ts` coexist with the primary API client, while the shared type still includes a `refresh_token` field even though the current response contract intentionally omits refresh tokens from JSON.

**Recommended action:** Remove the unused client/types after confirming no imports outside the measured source. This reduces the chance of reintroducing browser token storage assumptions.

#### P3.5 Local SQLite profile is stale

The ignored local SQLite database and local-only configuration lag behind the Compose deployment. This can confuse developers who follow the local quick-start path.

**Recommended action:** Back up and migrate the local file, refresh `backend/.env` with non-placeholder development values, and document clearly that its capability set can differ from Compose.

## 11. Release plan

### Gate A — reproducible source

- Decide which current untracked/modified files belong in the release.
- Commit a clean snapshot and record its full commit SHA.
- Regenerate/install Python and Node dependencies from controlled manifests.
- Resolve or formally time-box development dependency advisories.

### Gate B — database and configuration

- **Verified:** Running PostgreSQL is at the sole Alembic head.
- **Verified:** An empty disposable PostgreSQL database migrated through all revisions.
- **Verified:** Live legal configuration is complete and both forecast horizons/email are ready.
- Remaining: back up and migrate `backend/energy_forecast.db` before using the local SQLite profile.
- Remaining: verify production backup/restore and keep only intentionally enabled integrations.

### Gate C — automated quality

- **Verified:** Backend SQLite suite passed 96 with four expected PostgreSQL skips.
- **Verified:** Backend PostgreSQL suite passed 100 with no skips.
- **Verified:** Frontend lint/type/build passed.
- Remaining: stabilize and pass the Playwright six-project matrix without the WebKit reload interruption.
- Remaining: make the full dependency audits pass or approve an expiring, evidence-based exception.
- Remaining: confirm the CI full-history secret scan on the release commit.

### Gate D — deployment evidence

- **Verified:** `docker compose up --build -d` completed.
- **Verified:** Database, backend, and frontend report healthy with zero restarts.
- **Verified:** Alert, email, and avatar cleanup workers are running with zero restarts.
- **Verified:** `/api/v1/system/live` returns 200.
- **Verified:** `/api/v1/system/ready` returns 200 with database, 24-hour, 168-hour, and email readiness.
- Remaining: verify Google capability behavior if it is intended to be enabled for release.
- Perform one owned CSV/push/simulator workflow, one 24-hour forecast, one export, and one account lifecycle smoke test.
- Verify backup and restore using the documented scripts.

## 12. Final verdict

**Codebase verdict:** Strong PFE release candidate. The application has credible engineering depth, honest forecasting behavior, meaningful ownership/privacy controls, and broad automated coverage.

**Current-state verdict:** **Operational and ready for a controlled PFE demonstration. Conditional no-go for an immutable public release until the CI dependency audit is resolved or formally excepted.** The live stack, PostgreSQL schema, two model artifacts, email readiness, frontend, and complete backend suite are healthy. The remaining red evidence is development-tool dependency auditing plus one non-reproduced WebKit matrix interruption.

**Recommended decision:** The app can be demonstrated now. Before tagging or publishing a release, resolve P1.1, stabilize the browser gate, commit a clean reproducible snapshot, and complete the remaining external smoke/backup checks. No major product rewrite is indicated by this audit.

## Appendix A — commands executed

```text
git status --short
git branch --show-current
git rev-parse --short HEAD
python -m pytest -q
python -m pytest -q -rs <Postgres/model-focused tests>
python -m compileall -q app
python -m alembic heads
python -m alembic current
python -m pip check
python -m pip_audit -r requirements.txt -r requirements-dev.txt --progress-spinner off
npm run lint
npm run typecheck
npm run build
npm run test:browser
npx playwright test <failed case> --project=webkit-desktop
npm audit --omit=dev --json
npm audit --json
docker compose config --quiet
docker compose ps --format json
docker compose up --build --detach
docker compose exec -T backend python -m alembic current
python -m alembic upgrade head  # isolated PostgreSQL audit database
python -m pytest -q             # isolated PostgreSQL audit database
```

The first `docker compose ps` attempt found Docker unavailable. After Docker Desktop was launched, the Compose stack was built and started successfully. A disposable audit database was created and removed; no live product rows were changed by the database test run. No email or OAuth action was initiated by the audit.

## Appendix B — superseded evidence warning

The following files contain useful history but must not be used as current status without rerunning their checks:

- `app_status_audit.md`
- `docs/PFE_FULL_AUDIT_2026-07-22.md`
- `docs/PFE_DEADLINE_VALIDATION_EVIDENCE_2026-07-27.md`

They describe earlier commits, test counts, configuration, migrations, and container states.
