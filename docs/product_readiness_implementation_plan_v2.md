# EnergyAI Product Readiness Implementation Plan v2

Date: 2026-07-17

## 1. Product Goal

Turn EnergyAI into a trustworthy Moroccan energy intelligence product for
households, small businesses, and facilities. The first sellable version must
let an organization connect or import meter data, understand consumption and
cost, receive a reliable 24-hour forecast, and act on evidence-based alerts and
recommendations.

The first production release is not a hardware control platform. Multi-site
monitoring is in scope; battery dispatch, demand response, and remote appliance
control remain explicitly simulated until a real device integration exists.

## 2. Product Truth Rules

These rules apply to every phase and every screen:

1. Every value has an organization, site, meter, timestamp, unit, and source.
2. Every value is labeled as live, imported, historical, simulated, or seeded.
3. A failed live connector must show an error; it must never silently substitute
   simulated data.
4. A forecast is available only when a compatible active model exists for the
   requested horizon and input schema.
5. Recommendations must include the calculation or evidence that produced them.
6. Features that do not exist on the backend are not presented as operational.

## 3. Target Release Scope

### Required for the first client pilot

- Organization and member accounts with owner, admin, analyst, and viewer roles.
- One or more sites and meters per organization.
- CSV import and authenticated telemetry ingestion.
- Correct hourly, daily, and monthly energy and cost aggregation.
- Honest 24-hour forecasting with uncertainty and model provenance.
- Budget, peak-load, missing-data, and abnormal-usage alerts.
- Dashboard, consumption history, forecast, alerts, reports, and settings.
- Per-organization isolation, audit logs, backups, monitoring, and deployment.

### Deferred until after the pilot

- Real remote battery or appliance control.
- Automatic model training on customer infrastructure.
- 168-hour and 720-hour forecasts unless validated artifacts are ready.
- Real payments. During pilot, subscriptions are admin-managed.
- Native mobile applications.

## 4. Delivery Strategy

The critical path is:

`Build gates -> tenant ownership -> ingestion -> correct calculations -> trusted forecast -> client workflows -> security/operations -> pilot`

Do not add more dashboard widgets before Phases 0 through 4 are complete.

## Phase 0 - Restore Engineering Gates

Estimated effort: 2-4 working days

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

## Phase 1 - Tenant and Site Ownership

Estimated effort: 5-8 working days

### Database model

Add the following entities:

- `organizations`: id, name, timezone, currency, country, created_at.
- `organization_members`: organization_id, user_id, role, status.
- `sites`: organization_id, name, address, region, timezone, provider.
- `meters`: site_id, external_id, name, meter_type, status, source_type,
  expected_interval_seconds, last_seen_at.
- `meter_readings`: meter_id, timestamp, active_power_kw, energy_kwh,
  reactive_power_kvar, voltage_v, current_a, power_factor, submeter payload,
  source, quality, ingestion_id.
- `site_settings`: site_id, tariff configuration, notification defaults.
- `simulation_sessions`: site_id, owner_user_id, configuration, state.
- `audit_events`: organization_id, actor_user_id, event_type, target, metadata.

Add indexes for `(meter_id, timestamp)`, `(site_id, timestamp)`, and alert lookup.
Use a uniqueness or idempotency constraint for duplicate meter samples.

### Migration and backfill

- Create one default organization and site for each existing user with data.
- Assign existing readings to an explicit demo meter only; never guess ownership
  for production users.
- Move global settings into site settings.
- Add organization and site ownership to forecasts, alerts, budgets, reports,
  connector configurations, and import jobs.
- Preserve the old database until migration and rollback have been rehearsed.

### Authorization

- Resolve organization membership in one dependency/service.
- Require organization and site scope on every data endpoint.
- Test cross-tenant reads, writes, exports, WebSockets, forecasts, and admin APIs.
- Separate platform-admin permissions from organization-owner permissions.

### Acceptance criteria

- User A cannot observe or affect User B's readings, simulator, settings,
  forecasts, alerts, exports, or reports.
- A user can belong to multiple organizations without data mixing.
- Multi-site records come from the database rather than static arrays.

## Phase 2 - Trustworthy Data Ingestion

Estimated effort: 7-10 working days

### Canonical ingestion contract

Create one internal `MeterSample` schema used by every source. Validate:

- Timestamp and timezone.
- Power and energy units.
- Finite numeric ranges.
- Monotonicity where the meter reports cumulative energy.
- Duplicate and out-of-order samples.
- Maximum batch size and payload size.
- Required fields for the selected meter type.

### Ingestion paths

1. CSV import
   - Upload to controlled storage.
   - Column mapping and unit selection.
   - Preview, validation summary, rejected-row download, and explicit import.
   - Asynchronous import status for large files.

2. Push API
   - Per-meter API key stored as a hash.
   - Optional HMAC request signatures.
   - Single and batch ingestion endpoints.
   - Idempotency keys and rate limits.

3. Pull connector
   - Store secrets encrypted, never return them to the browser.
   - Run fetches in a worker with SSRF protection, host allowlists, response size
     limits, schema validation, retries, and circuit breaking.
   - Record connector runs and errors.

4. Simulator
   - Persist sessions by site.
   - Generate readings through the same canonical ingestion pipeline.
   - Display a persistent `SIMULATION` badge throughout the product.

Remove silent fallback from real connector mode. When live ingestion fails, keep
the last known reading and show stale age and connector status.

### Acceptance criteria

- A pilot client can upload a CSV without developer assistance.
- Two meters can ingest concurrently without overwriting each other.
- Replaying a batch does not create duplicates.
- Invalid units, timestamps, private connector URLs, and oversized responses are
  rejected with actionable errors.

## Phase 3 - Correct Energy, Tariff, and Budget Calculations

Estimated effort: 4-7 working days

### Aggregation engine

- Calculate interval energy as `kWh = average_kW * elapsed_hours` when direct
  energy is unavailable.
- Use actual timestamp deltas, not assumed one-minute or five-second intervals.
- Mark long gaps as missing instead of integrating across them.
- Build hourly and daily aggregates and refresh them after imports.
- Calculate site totals from owned meters without double counting.
- Apply organization/site timezone at reporting boundaries and DST transitions.

### Tariff engine

- Represent tariff versions with effective dates, tiers, time-of-use windows,
  taxes, and fixed charges.
- Keep provider presets editable and show their effective date/source.
- Calculate bills from site tariff settings, never alert thresholds.
- Use `EnergyBudget` for budget progress and projected-overrun alerts.
- Store calculation version and tariff version on generated reports.

### Verification

- Create golden fixtures with hand-calculated 5-second, 1-minute, 15-minute,
  and hourly samples.
- Test missing intervals, duplicate timestamps, month boundaries, timezone
  conversion, tariff tiers, and mixed direct-energy/power meters.

### Acceptance criteria

- Golden-fixture totals match manual calculations within documented tolerance.
- Dashboard, CSV, PDF, API, and alerts show the same energy and cost totals.
- Changing an alert threshold cannot change the user's monthly budget.

## Phase 4 - Production Forecast Contract

Estimated effort: 8-12 working days

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

Estimated effort: 6-9 working days

### Onboarding

- Create organization and first site.
- Select timezone, provider, tariff, and budget.
- Connect a meter, upload a CSV, or deliberately choose simulation.
- Show a data-quality check before completing setup.

### Dashboard

- Current consumption and last-seen age.
- Today and month-to-date energy/cost.
- Budget projection based on the real budget.
- Data-source badge and connector health.
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
- Include organization, site, period, source, tariff version, model version, and
  uncertainty disclosure in exported reports.

### Acceptance criteria

- A client can answer: What am I using? What will it cost? What happens next?
  What should I do? How trustworthy is this answer?
- No production screen fabricates an event, appliance state, saving, or trend.

## Phase 6 - Alerts and Evidence-Based Recommendations

Estimated effort: 5-8 working days

### Alert engine

- Move alert evaluation out of the web process into a scheduled worker.
- Evaluate per site/meter and support peak, budget risk, anomaly, missing data,
  connector failure, forecast risk, and power-factor rules where supported.
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

## Phase 7 - Security and Operational Readiness

Estimated effort: 5-8 working days

### Security

- Use short-lived access tokens and secure, HttpOnly, SameSite refresh cookies,
  or document and test an equivalent secure token design.
- Add token rotation, session revocation, password reset, and email verification.
- Restrict CORS to deployed origins.
- Validate upload type and size, sanitize filenames, and scan where appropriate.
- Add CSRF protection for cookie-authenticated mutations.
- Encrypt connector and notification credentials at rest.
- Add audit events for login, membership, settings, data import, connector,
  subscription, export, and model activation changes.
- Run dependency, secret, and container vulnerability scans in CI.

### Operations

- Separate web, worker, database, and optional scheduler processes.
- Add structured logs, request IDs, error tracking, metrics, and alerting.
- Track ingestion lag, connector failures, forecast latency, model load failures,
  queue depth, API errors, and notification delivery.
- Configure automated database backups and perform a restore rehearsal.
- Add retention and deletion policies for raw files, readings, tokens, and logs.
- Document deployment, rollback, backup, restore, and incident procedures.

### Initial service objectives

- API availability: 99.5% monthly during beta.
- Dashboard p95 response: under 1.5 seconds excluding cold model loading.
- 24-hour forecast p95: under 10 seconds on declared production hardware.
- Ingestion acceptance: under 5 seconds for normal batches.
- Backup RPO: 24 hours; restore RTO: 4 hours.

### Acceptance criteria

- Security and ownership tests pass in CI.
- A failed database/model dependency makes readiness fail without killing
  liveness.
- A database backup can be restored into a clean environment.
- No production secret or customer data is committed to Git.

## Phase 8 - Pilot, Billing, and Launch

Estimated effort: 5-10 working days plus pilot observation

### Pilot first

- Recruit 2-3 pilot organizations with different meter formats.
- Run onboarding sessions and record time-to-first-useful-dashboard.
- Compare forecast against actual outcomes for at least two weeks.
- Track import failures, missing data, alert usefulness, and recommendation use.
- Keep plan assignment admin-managed during the pilot.

### Billing after value is proven

- Select a supported payment provider for the target market.
- Create checkout server-side and activate subscriptions only from verified,
  signed provider webhooks.
- Add idempotent webhook handling, invoice history, cancellation, renewal, and
  failed-payment states.
- Remove the browser-callable simulated confirmation endpoint.
- Enforce plan limits on the backend by organizations, sites, meters, retention,
  forecast horizons, exports, and members.

### Launch gates

- No open critical/high security findings.
- All P0/P1 defects closed and regression-tested.
- Pilot organizations complete onboarding without developer database changes.
- At least 95% of valid readings are ingested without manual intervention.
- Forecast and billing calculations are validated against actual outcomes.
- Terms, privacy notice, data deletion, support, and incident contacts exist.

## 5. Test Matrix

### Unit tests

- Unit conversion, interval integration, tariff calculations, budgets.
- Input schemas, model compatibility, alert cooldowns, recommendation math.
- Entitlements and role decisions.

### Integration tests

- Empty Postgres migration and seed.
- CSV import through aggregate/report generation.
- Push ingestion through dashboard and forecast.
- Connector failure without simulator fallback.
- Model activation, forecast, rollback, and outcome recording.
- Subscription webhook idempotency when billing is implemented.

### Security tests

- Cross-organization IDOR attempts on every resource.
- WebSocket ownership and token expiry.
- SSRF, oversized responses, hostile CSVs, upload paths, and rate limits.
- Disabled users, revoked sessions, role changes, and audit trail.

### End-to-end tests

- Register -> organization -> site -> import -> dashboard -> forecast -> report.
- Owner invites analyst and viewer; permissions differ correctly.
- Simulation and live data are visibly distinct.
- Connector becomes stale and the UI reports it honestly.

### Performance tests

- Batch ingestion and duplicate replay.
- Dashboard with at least one year of readings.
- Concurrent forecasts within documented hardware capacity.
- Worker recovery after restart.

## 6. Suggested Milestones

### Milestone A - Safe engineering baseline

Phases 0 and 1 complete. The app builds cleanly and tenant isolation is proven.

### Milestone B - Useful client MVP

Phases 2 through 4 complete. A client can ingest real data, receive correct
energy/cost totals, and run a trustworthy 24-hour forecast.

### Milestone C - Pilot-ready beta

Phases 5 through 7 complete. Workflows, alerts, reports, security, backups, and
monitoring are operational.

### Milestone D - Sellable release

Pilot evidence is reviewed, major findings are fixed, and real billing is added
only if self-service sales are required.

## 7. Realistic Schedule

For one focused developer, expect 9-13 weeks to reach pilot-ready beta, excluding
the observation period needed to measure forecast performance. Two developers
can parallelize frontend workflows with backend/data work, but Phases 0, 1, 3,
and 4 remain critical-path work.

- Weeks 1-2: Phases 0 and 1.
- Weeks 3-4: Phase 2.
- Week 5: Phase 3.
- Weeks 6-7: Phase 4.
- Weeks 8-9: Phases 5 and 6.
- Weeks 10-11: Phase 7 and full regression testing.
- Weeks 12-13: Pilot onboarding and fixes.

## 8. Immediate Backlog - First 15 Tickets

1. Fix lint failures and remove unused frontend code.
2. Self-host the frontend font and restore an offline production build.
3. Add backend test dependencies and CI test execution.
4. Remove insecure Docker defaults and require secrets.
5. Make migrations fail readiness/startup visibly.
6. Add organization, membership, site, and meter migrations.
7. Add meter ownership and source fields to readings.
8. Backfill existing readings into an explicit demo organization/site/meter.
9. Scope settings, budgets, forecasts, alerts, and reports by organization/site.
10. Replace the global simulator with site-owned persisted sessions.
11. Add cross-tenant API and WebSocket tests.
12. Implement timestamp-based energy integration with golden fixtures.
13. Build the canonical ingestion schema and batch endpoint.
14. Build CSV preview, validation, and import flow.
15. Enforce model horizon/schema compatibility and hide unsupported horizons.

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
- At least one pilot client confirms that the dashboard changes a real decision.
