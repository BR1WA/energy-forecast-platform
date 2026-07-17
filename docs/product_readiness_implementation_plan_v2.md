# EnergyAI Product Readiness Implementation Plan v2

Date: 2026-07-17

## 1. Product Goal

Turn EnergyAI into a trustworthy Moroccan energy intelligence product for
households, small businesses, and facilities. The first evaluation-ready version must
let a client connect or import meter data, understand consumption and
cost, receive a reliable 24-hour forecast, and act on evidence-based alerts and
recommendations.

The first production release is not a hardware control platform. Multi-site
monitoring is in scope; battery dispatch, demand response, and remote appliance
control remain explicitly simulated until a real device integration exists.

## 2. Product Truth Rules

These rules apply to every phase and every screen:

1. Every value has an owning user, site, meter, timestamp, unit, and source.
2. Every value is labeled as live, imported, historical, simulated, or seeded.
3. A failed live-ingestion path must show an error; it must never silently substitute
   simulated data.
4. A forecast is available only when a compatible active model exists for the
   requested horizon and input schema.
5. Recommendations must include the calculation or evidence that produced them.
6. Features that do not exist on the backend are not presented as operational.

## 3. Target Release Scope

### Required for the first PFE release

- Two account roles only: `admin` and `user`.
- One or more sites and meters per user account.
- CSV import, authenticated push telemetry ingestion, and a clearly labeled
  simulator.
- Correct hourly, daily, and monthly energy and cost aggregation.
- Honest 24-hour forecasting with uncertainty and model provenance.
- Budget, peak-load, missing-data, and abnormal-usage alerts.
- Dashboard, consumption history, forecast, alerts, reports, and settings.
- Per-user isolation, audit logs, backups, monitoring, and deployment.

### Deferred until after the PFE

- Real remote battery or appliance control.
- Automatic model training on customer infrastructure.
- 168-hour and 720-hour forecasts unless validated artifacts are ready.
- Organizations, shared workspaces, and member invitations.
- Pull connectors to third-party energy providers.
- Subscriptions, plans, entitlements, billing, and payments. The PFE release is
  free for all users.
- Native mobile applications.

## 4. Delivery Strategy

The critical path is:

`Build gates -> user/site ownership -> ingestion -> correct calculations -> trusted forecast -> client workflows -> security/deployment -> validation`

Do not add more dashboard widgets before Phases 0 through 4 are complete.

## Phase 0 - Restore Engineering Gates

Estimated effort: 2-4 working days

Status: Complete on 2026-07-17.

### Backend

- Add development and test dependencies, including `pytest`, `pytest-asyncio`,
  HTTP client support, coverage, Ruff, and type checking if adopted.
- Make migrations fail startup when they fail. Do not continue in a partially
  migrated state.
- Replace health placeholders with separate liveness and readiness endpoints.
- Readiness must check the database, active model artifact, and required storage.
- Remove runtime demo seeding from application startup.
- Create explicit commands for migration, seed, test, and server startup.

### Frontend

- Fix all 6 lint errors and 30 warnings.
- Remove `typescript.ignoreBuildErrors` after resolving generated type issues or
  pinning a stable compatible Next.js version.
- Self-host Inter or use a system font so builds do not require Google Fonts.
- Add error, loading, empty, offline, and unauthorized states for API screens.

### Docker and CI

- Remove default database, JWT, and admin secrets from Docker Compose.
- Require secrets with Compose `${VARIABLE:?message}` checks.
- Pass `DEBUG=false` explicitly in production configuration.
- Add backend and frontend health checks.
- Add CI jobs for backend tests, migrations on an empty Postgres database,
  frontend lint, typecheck, build, and a Docker smoke test.
- Use reproducible dependency installation (`npm ci` and pinned Python ranges).

### Acceptance criteria

- Backend tests run in the same image used by CI.
- Frontend lint has zero errors and zero warnings.
- Frontend typecheck and production build pass without network access.
- A fresh Postgres database migrates to head and starts successfully.
- Deployment refuses insecure or missing secrets.

## Phase 1 - User, Site, and Meter Ownership

Estimated effort: 3-5 working days

Status: Complete on 2026-07-17.

### Database model

Keep authorization intentionally small. The existing `users.role` field accepts
only `admin` and `user`:

- `admin`: manages user accounts (activation, reset, disable) and platform
  operations. It does not silently browse customer energy data.
- `user`: owns their sites, meters, settings, imports, forecasts, alerts, and
  reports.

Add or adapt the following entities:

- `sites`: user_id, name, address, region, timezone, provider.
- `meters`: site_id, external_id, name, meter_type, status, source_type,
  expected_interval_seconds, last_seen_at.
- `meter_readings`: meter_id, timestamp, active_power_kw, energy_kwh,
  reactive_power_kvar, voltage_v, current_a, power_factor, submeter payload,
  source, quality, ingestion_id.
- `site_settings`: site_id, tariff configuration, notification defaults.
- `simulation_sessions`: site_id, user_id, configuration, state.
- `audit_events`: actor_user_id, target_user_id, site_id, event_type, target,
  metadata.

Add indexes for `(meter_id, timestamp)`, `(site_id, timestamp)`, and alert lookup.
Use a uniqueness or idempotency constraint for duplicate meter samples.

### Migration and backfill

- Create one default site for each existing user with data.
- Assign existing readings to an explicit demo meter only; never guess ownership
  for production users.
- Move global settings into site settings.
- Add user and site ownership to forecasts, alerts, budgets, reports,
  push-ingestion credentials, and import jobs.
- Preserve the old database until migration and rollback have been rehearsed.

### Authorization

- Resolve the current user once in a shared ownership dependency/service.
- Require user and site scope on every client-data endpoint.
- Limit admin endpoints to user-account administration and platform operations.
- Test cross-user reads, writes, exports, WebSockets, forecasts, and admin APIs.

### Acceptance criteria

- User A cannot observe or affect User B's readings, simulator, settings,
  forecasts, alerts, exports, or reports.
- An admin can activate, disable, and reset a user account without becoming that
  user's data owner.
- Multi-site records come from the database rather than static arrays.

## Phase 2 - Trustworthy Data Ingestion

Estimated effort: 5-7 working days

Status: Complete on 2026-07-17.

### Canonical ingestion contract

Create one internal `MeterSample` schema used by every source. Validate:

- Timestamp and timezone.
- Power and energy units.
- Finite numeric ranges.
- Monotonicity where the meter reports cumulative energy.
- Duplicate and out-of-order samples.
- Maximum batch size and payload size.
- Required fields for the selected meter type.

### In-scope ingestion paths

1. CSV import
   - UTF-8 upload with a 5 MB / 10,000-row limit.
   - Recognize canonical headers plus legacy `Datetime`/`GAP` field names.
   - Preview validation summary, rejected-row feedback, and explicit import.

2. Push API
   - Per-meter API key stored as a hash.
   - Single and batch ingestion endpoints.
   - Idempotency keys and bounded batches.

3. Simulator
   - Persist sessions by site.
   - Generate readings through the same canonical ingestion pipeline.

Pull connectors are deliberately deferred. They require credential management,
scheduling, worker retries, SSRF protection, and circuit breaking; none of that
is needed to demonstrate the PFE's ingestion contract.

Remove silent fallback from push ingestion. When telemetry stops or fails, keep
the last known reading and show its age and source status.

Deferred to future work: custom column mapping and unit conversion, rejected-row
file download, asynchronous large imports, HMAC signatures, and per-meter rate
limits. These add operational complexity without changing the PFE's core data
integrity demonstration.

### Acceptance criteria

- A representative user can upload a CSV without developer assistance.
- Two meters can ingest concurrently without overwriting each other.
- Replaying a batch does not create duplicates.
- Invalid units, timestamps, and oversized payloads are rejected with
  actionable errors.

## Phase 3 - Correct Energy, Tariff, and Budget Calculations

Estimated effort: 3-5 working days

Status: Complete on 2026-07-17.

### Aggregation engine

- Calculate interval energy as `kWh = average_kW * elapsed_hours` when direct
  energy is unavailable.
- Use actual timestamp deltas, not assumed one-minute or five-second intervals.
- Mark long gaps as missing instead of integrating across them.
- Build daily aggregates at query time from the canonical readings. Persisted
  rollups can be added when data volume requires them.
- Calculate site totals from owned meters without double counting.
- Apply each user's site timezone at reporting boundaries.

### Tariff engine

- Apply editable site peak/off-peak rates and time-of-use windows.
- Calculate bills from site tariff settings, never alert thresholds.
- Use `EnergyBudget` for budget progress and projected-overrun alerts.
- Use the same calculation service for dashboard, budget progress, and CSV
  exports.

### Verification

- Test hand-calculated 5-second, 15-minute, hourly, direct-energy, tariff,
  budget, and long-gap samples.

### Acceptance criteria

- Golden-fixture totals match manual calculations within documented tolerance.
- Dashboard, budget, CSV, API, and budget alerts show the same energy and cost
  totals.
- Changing an alert threshold cannot change the user's monthly budget.

Deferred to future work: tariff version history, tax/fixed-charge modelling,
provider preset administration, persisted rollups for high-volume accounts,
and full DST edge-case reporting.

## Phase 4 - Production Forecast Contract

Estimated effort: 5-7 working days

### Model artifact contract

Every promoted artifact must contain:

- Immutable model ID, version, architecture, dataset, horizon, lookback, and
  sampling interval.
- Exact feature schema and target units.
- Preprocessing artifact and dependency versions.
- Evaluation metrics, evaluation period, baseline comparison, and fingerprint.
- Model file, smoke-test input, and expected output shape.

Store portable artifact locations rather than host-specific absolute paths.

### Registry and serving

- Enforce one active model per `(dataset/schema, horizon, target)` contract.
- Reject requests when no compatible model exists. Never fall back to another
  horizon or silently skip failed models.
- Hide 168h and 720h UI options until compatible models are registered and pass
  evaluation.
- Validate artifacts before activation and warm the candidate before switching.
- Keep the previous active artifact available for rollback.
- Return model ID/version, generated timestamp, input source, and confidence
  method with each forecast.

### Forecast quality

- Compare every model against persistence and seasonal-naive baselines.
- Use time-based backtesting with no leakage.
- Add uncertainty using calibrated residual intervals or conformal prediction.
- Evaluate accuracy by horizon and by client data when sufficient history exists.
- Record actual outcomes later so forecast error can be measured continuously.

### Acceptance criteria

- The deployed 24-hour model beats the declared baseline on a held-out period.
- A 168-hour request cannot be served by a 24-hour artifact.
- Every forecast is reproducible from its model version and input snapshot.
- Model load failure makes readiness fail and returns a clear API error.

## Phase 5 - Client Workflows and Honest UI

Estimated effort: 4-6 working days

### Onboarding

- Create the user's first site.
- Select timezone, provider, tariff, and budget.
- Connect a meter, upload a CSV, or deliberately choose simulation.
- Show a data-quality check before completing setup.

### Dashboard

- Current consumption and last-seen age.
- Today and month-to-date energy/cost.
- Budget projection based on the real budget.
- Data-source badge and ingestion status.
- One primary recommendation with evidence.
- Empty state when there is insufficient data.

### Consumption and forecast

- Server-backed time ranges and pagination.
- Consistent units and timezone labels.
- Forecast confidence band and model provenance.
- Actual-versus-forecast chart after observations arrive.
- Real CSV export generated for the selected site and period.

### Multi-site

- Start as monitoring and comparison only.
- Replace static sites and client-side load curves with site/meter aggregates.
- Remove battery and load-shedding controls or label them as scenario simulation.
- Add actual commands only after a device integration and authorization model
  exist.

### Analytics and reports

- Remove generated weekly, heatmap, comparison, and timeline values.
- Render only backend aggregates or an explicit demo dataset.
- Include account, site, period, source, tariff version, model version, and
  uncertainty disclosure in exported reports.

### Acceptance criteria

- A client can answer: What am I using? What will it cost? What happens next?
  What should I do? How trustworthy is this answer?
- No production screen fabricates an event, appliance state, saving, or trend.

## Phase 6 - Alerts and Evidence-Based Recommendations

Estimated effort: 3-5 working days

### Alert engine

- Move alert evaluation out of the web process into a scheduled worker.
- Evaluate per site/meter and support peak, budget risk, anomaly, missing data,
  forecast risk, and power-factor rules where supported.
- Add deduplication windows, cooldowns, lifecycle states, and acknowledgement.
- Store rule inputs and calculation results for auditability.
- Deliver in-app notifications first, then verified SMTP/email.

### Recommendation engine

- Start with deterministic, testable rules.
- Calculate savings from measured load, tariff windows, and explicit assumptions.
- Include confidence, evidence window, estimated impact, and expiration.
- Track accepted, dismissed, and completed recommendations.
- Do not infer appliance identity without sub-meter/device evidence.

### Acceptance criteria

- The same condition does not generate a new alert every 30 seconds.
- Every recommendation explains its source data and calculation.
- Notification failures are retried and observable.

## Phase 7 - PFE Security and Deployment Readiness

Estimated effort: 3-5 working days

### Required for the PFE

- Use short-lived access tokens and secure, HttpOnly, SameSite refresh cookies,
  or document and test an equivalent secure token design.
- Implement password reset and email verification.
- Restrict CORS to deployed origins.
- Validate upload type and size, sanitize filenames, and scan where appropriate.
- Add CSRF protection for cookie-authenticated mutations.
- Add audit events for login, user-account administration, settings, data import,
  export, and model activation changes.
- Deploy the frontend, backend, worker/scheduler where used, and database with
  Docker Compose and environment-specific secrets.
- Create documented database backup and restore commands, and keep backups
  outside the application container.
- Document deployment, rollback, backup, and basic incident steps.

### Future operational maturity

- Token rotation and session revocation.
- Request IDs, structured logs, error tracking, metrics, Prometheus, Grafana,
  and alerting.
- Dependency, secret, and container vulnerability scanning in CI.
- Automated backup restore rehearsals, formal RPO/RTO targets, retention
  automation, and SIEM integration.
- Pull-connector credential encryption, scheduling, retries, and circuit
  breaking when that ingestion path is added.

### Acceptance criteria

- Security and ownership tests pass in CI.
- A failed database/model dependency makes readiness fail without killing
  liveness.
- Docker deployment and documented database-backup commands work in a clean
  environment.
- No production secret or customer data is committed to Git.

## Phase 8 - Validation and PFE Launch

Estimated effort: 2-3 working days plus validation time

### Validation

- Validate with volunteer users when available, or with representative datasets
  and documented user scenarios when volunteers are unavailable.
- Demonstrate onboarding, CSV import, push ingestion, simulation, dashboard,
  forecast, alert, and report workflows using at least two meter-data formats.
- Compare forecasts with held-out historical actuals and record the error.
- Record import failures, missing-data handling, alert usefulness, and
  recommendation evidence.
- Keep every feature free during the PFE release. Remove subscription, tier,
  entitlement, checkout, and payment UI/API paths rather than leaving simulated
  commercial flows exposed.
- Record the product decision that future monetization is out of scope until
  clients demonstrate repeat usage and a real payment provider is selected.

### Launch gates

- No open critical/high security findings.
- All P0/P1 defects closed and regression-tested.
- The documented validation scenario completes without developer database
  changes.
- Representative valid readings are ingested without manual intervention.
- Forecast and cost calculations are validated against actual outcomes.
- Terms, privacy notice, data deletion, support, and incident contacts exist.

## 5. Test Matrix

### Unit tests

- Unit conversion, interval integration, tariff calculations, budgets.
- Input schemas, model compatibility, alert cooldowns, recommendation math.
- Admin/user authorization decisions.

### Integration tests

- Empty Postgres migration and seed.
- CSV import through aggregate/report generation.
- Push ingestion through dashboard and forecast.
- Push-ingestion failure without simulator fallback.
- Model activation, forecast, rollback, and outcome recording.

### Security tests

- Cross-user IDOR attempts on every resource.
- WebSocket ownership and token expiry.
- Oversized payloads, hostile CSVs, upload paths, and rate limits.
- Disabled users, revoked sessions, role changes, and audit trail.

### End-to-end tests

- Register -> site -> import -> dashboard -> forecast -> report.
- Admin manages account activation; users cannot access each other's data.
- Simulation and live data are visibly distinct.
- Push ingestion becomes stale and the UI reports it honestly.

### Performance tests

- Batch ingestion and duplicate replay.
- Dashboard with at least one year of readings.
- Concurrent forecasts within documented hardware capacity.
- Worker recovery after restart.

## 6. Suggested Milestones

### Milestone A - Safe engineering baseline

Phases 0 and 1 complete. The app builds cleanly and per-user isolation is proven.

### Milestone B - Useful client MVP

Phases 2 through 4 complete. A client can ingest real data, receive correct
energy/cost totals, and run a trustworthy 24-hour forecast.

### Milestone C - Evaluation-ready beta

Phases 5 through 7 complete. Workflows, alerts, reports, security, backups, and
monitoring are operational.

### Milestone D - PFE release

Validation evidence is reviewed and major findings are fixed. Commercial plans and
billing remain a separate post-PFE product decision.

## 7. Realistic Schedule

For one focused developer, expect 6-8 weeks to reach an evaluation-ready beta,
excluding
the observation period needed to measure forecast performance. Two developers
can parallelize frontend workflows with backend/data work, but Phases 0, 1, 3,
and 4 remain critical-path work.

- Week 1: Phase 1.
- Weeks 2-3: Phase 2.
- Week 4: Phase 3.
- Week 5: Phase 4.
- Week 6: Phases 5 and 6.
- Week 7: Phase 7 and full regression testing.
- Week 8: Volunteer/dataset validation and fixes.

## 8. Immediate Backlog - First 15 Tickets

Phase 0 is complete. Start the remaining work in this order:

1. Restrict account roles to `admin` and `user`, and migrate existing roles.
2. Remove subscription, tier, entitlement, checkout, and payment API/UI logic.
3. Add user-owned site and meter migrations.
4. Add meter ownership and source fields to readings.
5. Backfill existing readings into an explicit demo user/site/meter.
6. Scope settings, budgets, forecasts, alerts, and reports by user and site.
7. Replace the global simulator with site-owned persisted sessions.
8. Add cross-user API and WebSocket isolation tests.
9. Build the canonical ingestion schema and authenticated batch endpoint.
10. Build CSV preview, validation, and import flow.
11. Implement timestamp-based energy integration with golden fixtures.
12. Make tariffs and `EnergyBudget` the only source of cost and budget values.
13. Enforce model horizon/schema compatibility and hide unsupported horizons.
14. Replace static dashboard and report values with source-labeled backend data.
15. Move alert evaluation to a worker with cooldown and evidence storage.

## 9. Definition of Ready Functional Product

EnergyAI is ready for real client use only when all of the following are true:

- A new deployment starts from an empty database using documented commands.
- A client can onboard and import/connect data without developer intervention.
- Data isolation is demonstrated by automated adversarial tests.
- Energy, tariff, budget, and report calculations share one tested engine.
- Forecasts use a compatible validated artifact and disclose uncertainty.
- Live failures never become simulated success responses.
- Dashboards and reports contain no fabricated production values.
- Lint, typecheck, build, backend tests, migrations, and end-to-end tests pass.
- Secrets, backups, monitoring, audit logs, and incident procedures are in place.
- At least one volunteer user or representative validation scenario demonstrates
  a realistic decision supported by the dashboard.
