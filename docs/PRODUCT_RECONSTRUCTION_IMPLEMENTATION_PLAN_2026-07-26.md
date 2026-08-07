# EnergyAI Product Reconstruction Implementation Plan

**Date:** 2026-07-26

**Status:** Proposed
**Scope:** Reconstruct the user-facing product around useful decisions, merge
overlapping surfaces, remove shallow pages, and preserve the existing
ownership, ingestion, monitoring, forecast, and account-security foundations.

## 1. Objective

EnergyAI must become one connected workflow:

```text
Connect trustworthy data
        ↓
Understand current and historical energy use
        ↓
Anticipate near-term demand and cost
        ↓
Review one prioritized set of incidents and actions
        ↓
Export the relevant evidence where it is used
```

Every retained page must:

1. Answer one clear user question.
2. Use persisted user-owned data.
3. Explain data quality or uncertainty when it affects the answer.
4. Offer a meaningful next action.
5. Avoid duplicating another page's primary job.

A feature should be removed or merged when it has no unique user decision,
uses only decorative data, or exists solely because a backend endpoint exists.

## 2. Product Success Criteria

The reconstruction is complete when:

- A new user can register, configure a site, connect or import data, and reach
  a useful first result without operator intervention.
- The primary navigation contains no more than five normal-user destinations:
  Dashboard, Usage, Forecast, Actions, and Settings.
- Dashboard, Usage, Forecast, and Actions have distinct responsibilities.
- Alerts and recommendations share one lifecycle and cannot contradict each
  other.
- Costs are explicitly based on user-confirmed tariff inputs or a validated
  tariff profile.
- Forecast readiness provides a practical path to becoming ready.
- Reports are contextual exports instead of a shallow standalone destination.
- Simulation is clearly a demo/development data source and is not presented as
  a primary product capability.
- Admins can inspect user access, system/model readiness, and audit activity.
- Automated tests cover the complete user journey and the lifecycle links
  between ingestion, monitoring, forecasts, incidents, actions, and exports.

## 3. Target Information Architecture

### 3.1 Primary navigation

| Destination | User question | Primary responsibility |
| --- | --- | --- |
| Dashboard | Is my energy situation okay right now? | Current status, important changes, budget trajectory, forecast highlight, and top action |
| Usage | Where and when am I consuming energy and money? | Historical exploration, comparisons, cost analysis, data quality, raw readings, CSV import, and consumption export |
| Forecast | What should I expect next? | Readiness, forecast output, expected cost, peaks, uncertainty, provenance, and forecast export |
| Actions | What needs my attention? | Unified incidents and recommended actions with evidence and lifecycle |
| Settings | How is my site, data connection, tariff, budget, and account configured? | Configuration and account controls |

Admin remains role-gated and visually separated from the normal user workflow.

### 3.2 Removed or merged destinations

| Current page | Decision |
| --- | --- |
| `/reports` | Remove from primary navigation. Move consumption export to Usage and forecast PDF export to Forecast. Redirect `/reports` to `/usage` during the transition. |
| `/alerts` | Merge into `/actions`. Keep a temporary redirect for bookmarks and email links. |
| `/recommendations` | Merge into `/actions`. Keep a temporary redirect. |
| `/consumption` | Rename to `/usage`. Redirect the old path. |
| `/simulation` | Retain as an internal route reached from Settings → Data sources. Do not show it in primary navigation or global search unless demo mode is enabled. |

### 3.3 Public and onboarding routes

Retain:

- `/`
- `/login`
- `/register`
- `/verify-email`
- `/verify-email/pending`
- `/forgot-password`
- `/reset-password`
- `/setup`
- `/privacy`
- `/terms`
- `/support`

The landing page must read authentication capabilities before advertising
registration. When registration is unavailable, the primary call to action
must become Sign in or Request access rather than lead to a disabled form.

## 4. Page Reconstruction Specifications

## 4.1 Dashboard

### Purpose

Provide a concise operational answer, not a second analytics workspace.

### Required content

1. **Current status**
   - Current load and timestamp.
   - Source and freshness.
   - Status: normal, elevated, stale, disconnected, or no data.
   - One sentence explaining the status.

2. **Today at a glance**
   - Energy and estimated cost.
   - Comparison with yesterday and a recent comparable-day baseline.
   - Peak load and timestamp.
   - Coverage warning only when it materially affects totals.

3. **Budget trajectory**
   - Spent, budget, projected month-end cost, and variance.
   - Direct action to update budget or tariff.

4. **Forecast highlight**
   - Next forecast peak time and expected load/energy.
   - Expected forecast-period cost.
   - Readiness progress when no forecast can run.

5. **Top action**
   - Highest-priority open action with evidence and direct link.
   - Calm empty state when nothing needs attention.

### Remove from Dashboard

- Full multi-period history exploration.
- Raw data controls.
- Multiple low-value cards that merely count records.
- Repeated links to every feature.

### Backend work

Create one bounded dashboard endpoint:

```http
GET /api/v1/dashboard/summary
```

It should return a consistent snapshot with:

- current reading status;
- today and comparison-period summaries;
- monthly budget projection;
- latest forecast highlight or readiness state;
- highest-priority open action;
- data-quality summary.

The endpoint prevents the client from composing several asynchronously
inconsistent snapshots and reduces Dashboard request fan-out.

### Acceptance criteria

- The first viewport answers current status, today, budget, and top action.
- No Dashboard metric silently treats missing coverage as zero consumption.
- All timestamps use the configured site timezone.
- Dashboard remains useful in no-data, stale-data, partial-data, and
  forecast-unavailable states.

## 4.2 Usage

### Purpose

Turn readings into historical understanding and cost insight.

### Required content

1. Period selector: Today, 7 days, Month, Year, All, Custom.
2. Energy, estimated cost, peak load, and coverage.
3. Comparison with the immediately preceding equivalent period.
4. Peak/off-peak energy and cost split.
5. Time-of-day or day-of-week pattern, depending on selected period.
6. Clearly identified recurring high-use windows when enough observations
   exist.
7. Consumption curve with source and aggregation explanation.
8. Collapsible data-quality section:
   - sample count;
   - source mix;
   - coverage;
   - longest unsupported gap;
   - expected interval.
9. Collapsible raw readings table with keyset pagination.
10. CSV import panel with:
    - downloadable template;
    - downloadable forecast-ready demo dataset when demo mode is enabled;
    - preview;
    - mapped columns;
    - row-level validation errors;
    - accepted, duplicate, and rejected results.
11. Contextual CSV export for the selected period, not only the current month.

### Backend work

- Extend period summaries with comparison values and peak/off-peak breakdown.
- Add a bounded pattern summary endpoint or include the result in the period
  response.
- Extend CSV export to accept the same validated period contract used by the
  Usage page.
- Keep interval integration and coverage semantics as the single source of
  truth.

### Acceptance criteria

- Changing the period updates every displayed metric from the same period.
- Comparisons are omitted rather than invented when the prior period lacks
  adequate data.
- Imported, pushed, and simulated readings remain visibly distinguishable.
- A user can understand why energy totals are incomplete.

## 4.3 Forecast

### Purpose

Help the user anticipate near-term energy use and cost without overstating
model accuracy.

### Required states

1. **Not configured**
   - Explain the missing site or meter configuration.
   - Link directly to the relevant Settings tab.

2. **Collecting history**
   - Show completed hours, coverage, longest gap, and remaining requirements.
   - Offer CSV template/demo history where permitted.
   - Explain that live simulation does not instantly create two weeks of
     history.

3. **Fallback ready**
   - Identify the seasonal method before generation.
   - Explain the difference between fallback and model output.

4. **Model ready**
   - Show artifact/model readiness separately from account-data readiness.

5. **Forecast available**
   - Median forecast and uncertainty interval.
   - Forecast-period total energy and estimated cost.
   - Highest expected hours.
   - Historical baseline comparison.
   - Method, model version, source, coverage, imputation, artifact fingerprint,
     and client-site accuracy limitation in a secondary details section.
   - Contextual PDF export for the displayed forecast.

### Backend work

- Add tariff-aware forecast cost calculation using target timestamps in the
  site timezone.
- Add comparable historical baseline calculations.
- Preserve the 336-hour, 95% coverage, three-hour maximum-gap, finite-value,
  artifact-integrity, and warm-up gates.
- Do not silently replace failed model inference with a fallback; retain the
  explicit method and reason.
- Allow PDF export by owned forecast identifier from the Forecast page.

### Acceptance criteria

- The generate button is enabled only when a declared method can run.
- Every displayed forecast is persisted and reproducible from stored
  provenance.
- The page never presents research performance as client-specific accuracy.
- The 168-hour selector appears only when the backend advertises it as enabled
  and warmed.

## 4.4 Actions

### Purpose

Replace separate Alerts and Recommendations pages with one incident-to-action
workflow.

### Domain model

Retain Alert as the measured incident and Recommendation as the user action,
but expose them as one aggregate:

```text
Action item
├── incident state and severity
├── measured evidence
├── recommended response
├── action state
└── lifecycle timestamps
```

### Required content

- Filters: Needs attention, Monitoring, Completed, Dismissed, All.
- Priority ordering based on severity, freshness, and status.
- Incident type, measured evidence, configured threshold, occurrence time,
  source, and current condition.
- One recommended response.
- Acknowledge, mark complete, dismiss, resolve, and reopen actions with clear
  semantics.
- History that shows both automatic and user-driven lifecycle changes.

### Lifecycle rules

1. Creating an alert may create one linked action.
2. Automatically resolving an incident must update the aggregate state.
3. An action may remain open after incident resolution only when the response
   still requires work; the UI must explicitly label it `follow-up required`.
4. Reopening an incident reopens its linked action unless the action was
   explicitly dismissed.
5. Completing an action does not falsely claim the measured condition ended.
6. Every transition records an audit event.

### Backend work

- Add an aggregate actions endpoint that returns linked alert and
  recommendation data.
- Move lifecycle synchronization into one transactional service.
- Add migration-safe fields only if the aggregate cannot be derived reliably
  from existing timestamps and statuses.
- Backfill or reconcile existing contradictory records, including open
  recommendations linked to resolved alerts.
- Update critical-alert email links to `/actions#action-{id}`.

### Acceptance criteria

- No open action appears without explaining whether its incident remains
  active.
- Automatic resolution and manual actions remain transactionally consistent.
- Duplicate actions are not created during cooldowns or repeated ingestion.
- Existing owned alerts and recommendations remain accessible after migration.

## 4.5 Settings

### Purpose

Centralize configuration and keep operational pages focused.

### Sections

1. **Site**
   - Name, country, region, timezone, provider.

2. **Tariff and budget**
   - Validated provider profile when available, or explicit custom tariff.
   - Currency, peak/off-peak rates, peak schedule, and monthly budget.
   - Clear `estimated cost` wording for custom or incomplete tariffs.

3. **Data sources**
   - Primary meter identity and expected interval.
   - Push API key creation/rotation and a safe test request.
   - CSV import link.
   - Demo simulator controls/link only when demo mode is available.

4. **Notifications**
   - Critical-alert email capability and opt-in.
   - Explain when delivery is disabled or email is unverified.

5. **Account and privacy**
   - Profile and avatar.
   - Password and Google identity where enabled.
   - Session revocation.
   - Account archive and deletion.

### Tariff reconstruction

- Remove silent hardcoded tariff assumptions from setup.
- Either select a validated provider tariff profile or require confirmation of
  custom rates.
- Store the tariff source, effective date, and calculation method.
- Do not imply that a two-rate estimate reproduces a utility bill when taxes,
  fixed fees, or tiered blocks are not modeled.

### Acceptance criteria

- Every cross-page settings link opens the intended section.
- Costs are not shown until the tariff is confirmed, or they are clearly
  marked as using provisional defaults.
- Push key values remain one-time reveal secrets.

## 4.6 Admin

### Purpose

Support safe operation rather than expose unused technical controls.

### Required content

- User search, role, activation, verification status, and last login.
- Protection for the final active administrator.
- Database, process, worker, email, and model readiness.
- Forecast capability state for each horizon.
- Paginated audit-event viewer with actor, event, target, timestamp, and safe
  metadata.
- Counts that distinguish all-time product data from current operational
  incidents.

### Remove or avoid

- Training controls.
- Arbitrary model activation.
- Cross-user data inspection.
- Raw secrets or sensitive payloads.

### Acceptance criteria

- Admin claims in README and release notes match the UI.
- Audit metadata never exposes password hashes, tokens, meter keys, or provider
  credentials.

## 5. Onboarding Reconstruction

## 5.1 Registration capability

- Landing and registration use the same public capabilities response.
- If email registration is disabled:
  - do not advertise Create account as the primary CTA;
  - show Sign in and configured support/request-access guidance;
  - capability-gate forgot-password messaging so users are not told to expect
    undeliverable email.
- When email delivery is enabled, preserve verified-email activation.

## 5.2 Setup steps

1. Site identity and timezone.
2. Tariff mode:
   - validated provider profile; or
   - custom rates and schedule.
3. Monthly budget.
4. Data source:
   - CSV;
   - push API;
   - labelled demo.
5. First-result screen:
   - show imported/live data;
   - show forecast readiness;
   - provide the next recommended setup action.

Setup completion must reflect minimum usable configuration, not merely that a
database flag was set.

## 6. Shared Backend and Data Contracts

## 6.1 Preserve

- One user-owned site and primary meter.
- Server-side ownership resolution.
- Validated ingestion and key hashing.
- Idempotency and duplicate rejection.
- Interval-integrated energy and explicit coverage.
- Fixed packaged forecast artifacts with integrity checks.
- HttpOnly refresh-session design.
- Account export and deletion.

## 6.2 Add or revise

- Dashboard summary service and schema.
- Comparable-period usage calculations.
- Tariff provenance and confirmation fields.
- Forecast cost and historical baseline fields.
- Unified action aggregate and lifecycle service.
- Audit-event listing endpoint for administrators.
- Period-aware consumption export.
- Demo/sample asset endpoint or static download contract.

## 6.3 Migration rules

- Never rewrite existing Alembic history.
- Add forward-only migrations for new tariff or lifecycle fields.
- Write explicit backfill logic.
- Test upgrade from an existing populated Product V1 database.
- Reconcile alert/recommendation state inside a transaction and record the
  migration/reconciliation version.

## 7. Delivery Phases

## Phase 0 — Baseline and contract freeze

**Goal:** Protect current behavior before structural changes.

Tasks:

- Capture API schemas for Dashboard, Consumption, Forecast, Alerts,
  Recommendations, Reports, Settings, and Admin.
- Add regression tests for current ownership and forecast gates.
- Add a database fixture containing mixed CSV, push, and simulator readings,
  partial coverage, resolved/open alerts, and linked recommendations.
- Record current page-level performance and request counts.

Exit gate:

- Existing backend, typecheck, build, and critical browser tests pass from a
  clean database and an upgraded populated database.

## Phase 1 — Navigation and route skeleton

**Goal:** Establish the final information architecture without losing access.

Tasks:

- Create `/usage` and `/actions`.
- Update sidebar, global search, navbar descriptions, and page titles.
- Add redirects from `/consumption`, `/alerts`, `/recommendations`, and
  `/reports`.
- Move simulator discovery into Settings → Data sources.
- Add route-level empty, loading, and error states.

Exit gate:

- Five-item normal-user navigation works at desktop and 360/390/768 px.
- Old bookmarks redirect without losing intended context.

## Phase 2 — Tariff and onboarding foundations

**Goal:** Ensure monitoring and cost outputs start from trustworthy setup.

Tasks:

- Add tariff provenance/confirmation model and migration.
- Replace hardcoded setup tariffs with explicit profile/custom selection.
- Make landing, registration, verification, and recovery capability-aware.
- Add CSV template and forecast-ready demo dataset.
- Add a first-result setup completion screen.

Exit gate:

- A new user can reach a useful Dashboard through CSV, push, or demo paths.
- No dead-end Create account CTA exists.
- Every displayed cost has a declared tariff source.

## Phase 3 — Usage reconstruction

**Goal:** Deliver useful historical analysis.

Tasks:

- Implement comparable-period and peak/off-peak calculations.
- Rebuild the Usage layout.
- Add pattern summaries and data-quality disclosure.
- Move consumption export into Usage and make it period-aware.
- Retain raw-reading pagination and CSV validation.

Exit gate:

- Usage answers total, cost, comparison, timing, and trustworthiness for every
  supported period.

## Phase 4 — Unified Actions

**Goal:** Remove alert/recommendation duplication and contradictions.

Tasks:

- Implement transactional lifecycle service.
- Add aggregate action schemas and endpoints.
- Reconcile existing records.
- Build `/actions`.
- Redirect and then remove standalone page implementations.
- Update dashboard, notifications, and emails to link to aggregate actions.

Exit gate:

- Lifecycle invariant tests pass.
- No resolved incident produces an unexplained open action.

## Phase 5 — Forecast reconstruction

**Goal:** Make forecast readiness understandable and output actionable.

Tasks:

- Add forecast cost and baseline calculations.
- Rebuild readiness states.
- Add expected peaks and forecast-period cost.
- Move forecast PDF export into the page.
- Add a forecast-ready onboarding/demo path without weakening production data
  gates.

Exit gate:

- A prepared demonstration account can reach a persisted forecast.
- An unprepared account receives a precise and achievable next step.
- Model, fallback, and client-site limitations remain visible.

## Phase 6 — Dashboard reconstruction

**Goal:** Compose the product's highest-value information into one stable
snapshot.

Tasks:

- Implement dashboard summary endpoint.
- Replace request fan-out with the summary contract.
- Rebuild current status, today comparison, budget trajectory, forecast
  highlight, and top action.
- Remove full analytics and generic counters.

Exit gate:

- Dashboard answers the operational question without requiring another page.
- Snapshot fields have consistent timestamps and calculation periods.

## Phase 7 — Settings and Admin completion

**Goal:** Finish configuration and operational management.

Tasks:

- Reorganize Settings sections.
- Add notification capability state.
- Add session-revocation UI if not already exposed.
- Add paginated admin audit-event API and viewer.
- Align documentation with actual capabilities.

Exit gate:

- All configuration links open the correct section.
- Admin can verify access, system readiness, forecast readiness, and audit
  history without viewing user energy data.

## Phase 8 — Removal and release hardening

**Goal:** Delete obsolete implementations and prepare a defensible release.

Tasks:

- Remove old Alerts, Recommendations, Reports, and Consumption page
  implementations after redirects have been validated.
- Remove unused API client methods and types.
- Remove dead translations, components, and tests.
- Resolve production configuration prerequisites: SMTP, public origins, legal
  identity, durable backups, and secret validation.
- Perform repository-hygiene review for tracked datasets, checkpoints, and
  notebook outputs.
- Update README, operations guide, release notes, screenshots, and PFE
  presentation material.

Exit gate:

- No navigation or documentation advertises removed or disabled functionality.
- Production readiness and backup/restore checks pass.

## 8. Testing Strategy

## 8.1 Backend

- Ownership isolation for every new endpoint.
- Dashboard snapshot period consistency.
- Usage integration and comparison math.
- Tariff provenance and cost calculations across peak boundaries and
  timezones.
- Alert/action lifecycle invariant tests.
- Forecast cost, baseline, readiness, fallback, and artifact-gate tests.
- Migration from existing populated PostgreSQL data.
- Audit-event redaction and pagination.

## 8.2 Frontend

- Lint, typecheck, and production build.
- Component tests for every state model.
- Browser journeys:
  - registration unavailable;
  - verified registration and setup;
  - CSV setup with validation errors;
  - push connection and test reading;
  - demo setup;
  - partial data and stale data;
  - forecast blocked, fallback-ready, model-ready, and persisted;
  - incident creation, automatic resolution, action follow-up, completion, and
    reopen;
  - contextual exports;
  - admin audit history;
  - account archive and deletion.
- Run critical journeys on Chromium, Firefox, WebKit, 360 px, 390 px, and
  768 px viewports.

## 8.3 Non-functional

- Bound response sizes and query counts.
- Test large reading histories and forecast histories.
- Verify no browser storage contains refresh credentials or meter keys.
- Confirm secrets and user-owned exports are excluded from logs.
- Verify WebSocket reconnect and stale-state behavior.
- Confirm accessibility names, keyboard navigation, contrast, and focus
  management.

## 9. Metrics

Track:

- Registration CTA success rate.
- Setup completion rate by data source.
- Time from registration to first valid reading.
- Time from first reading to first useful Dashboard state.
- Percentage of configured users forecast-ready.
- Forecast generation success/fallback/block rates.
- Open action age and completion/dismissal rates.
- Percentage of periods with adequate coverage.
- Export usage by context.
- API error and stale-data rates.

Do not use page count or number of cards as success metrics.

## 10. Implementation Order and Dependencies

```text
Baseline tests
    ↓
Routes/navigation
    ↓
Tariff + onboarding contracts
    ↓
Usage calculations
    ↓
Unified action lifecycle
    ↓
Forecast value layer
    ↓
Dashboard composition
    ↓
Settings/Admin completion
    ↓
Delete obsolete surfaces and release hardening
```

Dashboard is intentionally reconstructed late because it depends on stable
Usage, Forecast, Action, and tariff contracts.

## 11. Definition of Done

A phase is done only when:

- code and migrations are implemented;
- old and new database upgrade paths pass;
- backend and frontend automated tests pass;
- the relevant browser journey passes;
- loading, empty, partial, error, and success states are verified;
- documentation describes only shipped behavior;
- no obsolete page, API method, or navigation entry remains unless it is an
  intentional compatibility redirect.

## 12. Immediate First Sprint

The first sprint should contain only foundation work:

1. Add a full reconstruction test fixture and lifecycle invariant tests.
2. Introduce `/usage` and `/actions` route skeletons.
3. Reduce the sidebar to Dashboard, Usage, Forecast, Actions, and Settings.
4. Add compatibility redirects for the four replaced routes.
5. Add tariff provenance fields and a forward-only migration.
6. Define the dashboard summary and aggregate action API schemas without yet
   replacing the existing implementations.
7. Add capability-aware landing and password-recovery states.

This sprint creates the safe structure needed for subsequent page-by-page
reconstruction without mixing visual redesign, domain migration, and endpoint
replacement in one change.
