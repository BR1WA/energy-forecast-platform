# EnergyAI Jury-Impact Implementation Plan

**Created:** 2026-07-31

**Baseline branch:** `release/product-v1`

**Baseline revision:** `1e67921`

**Related audit:** `docs/PFE_FULL_APP_AUDIT_2026-07-31.md`
**Target outcome:** Turn the existing operational release candidate into a memorable, defensible jury demonstration without weakening product truthfulness or release stability.

## 1. Product story

The implementation should make one narrative obvious within the first minute:

```text
Measure -> Understand -> Predict -> Act -> Quantify impact -> Prove trust
```

The jury should leave with five clear conclusions:

1. EnergyAI processes owned, persisted meter data rather than displaying static charts.
2. Its 24-hour and 168-hour forecasts are real, independently packaged model capabilities.
3. The model is evaluated against a seasonal-naive baseline and its limitations are disclosed.
4. Forecasts lead to concrete, tariff-aware actions and estimated MAD savings.
5. The system is engineered as a complete product: authentication, data integrity, privacy, readiness, tests, workers, and exports are visible and verifiable.

## 2. Planning assumptions

- The defense is close, so jury impact and reliability matter more than expanding product scope.
- The current Compose stack, PostgreSQL schema, two forecast artifacts, email readiness, and backend suite are healthy.
- Existing APIs and persisted models should be reused wherever possible.
- New database migrations are avoided unless absolutely required.
- Presentation features must work with email and Google disabled as well as enabled.
- Every metric shown to the jury must come from a versioned evidence source and include its cohort/limitations.
- “Confidence” must distinguish input-data quality from predictive uncertainty. It must never imply calibrated accuracy that has not been measured.

## 3. Explicit non-goals

Do not add these before the defense:

- chatbot or generative-AI advice;
- subscriptions, billing, or plans;
- multi-site management;
- appliance-level disaggregation;
- a third forecast horizon;
- live utility-provider connectors;
- remote appliance control;
- a new ML architecture or last-minute model retraining;
- a complete visual-system rewrite.

These would increase risk without strengthening the central PFE argument.

## 4. Delivery strategy

### Critical path

```text
J0 Reliability baseline
   -> J1 Guided jury journey
   -> J2 Model evidence
   -> J3 Forecast explanation
   -> J4 Savings scenario
   -> J5 Dashboard and visual polish
   -> J6 Technical evidence and final rehearsal
```

### Recommended schedule

| Milestone | Scope | Estimate | Priority |
|---|---|---:|---:|
| J0 | Release-gate stabilization | 0.5–1.0 day | P0 |
| J1 | Guided jury journey | 1.0–1.5 days | P0 |
| J2 | Model evidence experience | 1.0–1.5 days | P0 |
| J3 | Forecast explanation and trust | 1.0 day | P0 |
| J4 | Tariff-aware savings scenario | 1.5–2.0 days | P1 |
| J5 | Dashboard hierarchy and motion polish | 1.0–1.5 days | P1 |
| J6 | Technical evidence, localization, rehearsal | 1.0–1.5 days | P1 |
| Buffer | Defects, cross-browser fixes, final capture | 1.0 day | Required |

**Expected total:** 8–10 focused working days. A compressed three-day option appears in section 15.

## 5. J0 — Stabilize the release gates

### Objective

Begin visual work only after the current red or flaky gates have an explicit resolution. A stunning demo that fails during navigation is worse than a simpler reliable one.

### Work items

#### J0.1 Resolve the frontend development dependency audit

- Identify the minimum compatible ESLint, `eslint-config-next`, minimatch, and brace-expansion update path.
- Regenerate `frontend/package-lock.json` through `npm install` or an intentional package update.
- Do not use `npm audit fix --force` without reviewing the resulting Next/ESLint compatibility changes.
- Keep both checks:
  - `npm audit --omit=dev` for deployed runtime exposure;
  - full `npm audit --audit-level=high` for the CI policy.
- If upstream packages make an immediate clean resolution impossible, create a written, expiring exception that records advisory IDs, reachability, runtime exclusion, owner, and expiry date.

Likely files:

- `frontend/package.json`
- `frontend/package-lock.json`
- `.github/workflows/ci.yml` only if the policy is intentionally clarified
- `docs/PRODUCT_V1_NEXT_POSTCSS_SECURITY_VALIDATION.md` or a new dependency exception record

#### J0.2 Stabilize the WebKit refresh test

- Reproduce `concurrent expired requests share one refresh, reload restores, and logout has no token body` repeatedly under the WebKit project.
- Replace ambiguous navigation timing with an explicit wait for the expected URL and restored session state.
- Preserve trace-on-failure.
- Add a retry only after the synchronization problem is understood; do not use retries to hide a deterministic defect.

Likely files:

- `frontend/e2e/auth-product-v1.spec.ts`
- `frontend/playwright.config.ts`

#### J0.3 Add baseline security headers

- Define a conservative header policy in Next.js or at the documented ingress layer.
- Include content-type sniffing protection, referrer policy, frame protection, and permissions policy.
- Add HSTS only for HTTPS deployments.
- Introduce CSP in report-only mode first if Google Identity or chart rendering requires policy tuning.
- Add a browser/API assertion for the chosen headers.

Likely files:

- `frontend/next.config.ts`
- `frontend/e2e/product-hardening.spec.ts`
- `docs/operations.md`

### Acceptance criteria

- `npm audit --omit=dev` reports zero known vulnerabilities.
- The full CI audit passes or an approved, expiring exception exists.
- The WebKit session test passes at least 10 consecutive isolated executions.
- The complete six-project Playwright matrix passes.
- Security headers are present in the production Next server response and documented.
- Existing lint, typecheck, build, and 100-test PostgreSQL suite remain green.

## 6. J1 — Guided jury journey

### Objective

Provide a predictable, restartable walkthrough that uses the existing product rather than a parallel fake interface.

### Experience

Add a “Presentation mode” entry point for authenticated users. It should open a compact guide with these steps:

1. **Observe:** Dashboard shows live/history, cost, coverage, and source.
2. **Prepare:** If necessary, call the existing idempotent forecast-demo history preparation operation.
3. **Predict day:** Generate or display the 24-hour Global TFT forecast.
4. **Predict week:** Switch to and explain the independent 168-hour capability.
5. **Act:** Open the highest-priority evidence-backed action.
6. **Simulate savings:** Adjust a tariff-aware load-shift scenario.
7. **Prove:** Open model/system evidence and export a forecast report.

### Implementation approach

- Keep guide progress in React state plus `sessionStorage`; never place tokens or sensitive data there.
- Use query parameters such as `?presentation=1&step=forecast-day` so each step is directly recoverable.
- “Restart walkthrough” resets only guide progress. It must not delete product data.
- Reuse `forecastApi.prepareDemoHistory()` when history is insufficient. This operation is already owned, idempotent, provenance-labelled, and tested.
- Never auto-send email, delete accounts, rotate meter keys, or start external OAuth during presentation mode.
- Each step must have a “Skip” option and a direct destination link so the demo remains usable if one optional capability is unavailable.
- Add a keyboard shortcut for next/previous step only if it does not interfere with form fields.

### Proposed frontend structure

```text
frontend/src/components/jury/
  presentation-launcher.tsx
  presentation-guide.tsx
  presentation-step.tsx
  presentation-steps.ts
  presentation-summary.tsx
```

Likely integration files:

- `frontend/src/components/layout/navbar.tsx`
- `frontend/src/components/layout/app-layout.tsx`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/forecast/page.tsx`
- `frontend/src/app/actions/page.tsx`
- `frontend/src/lib/api.ts`

No backend route is required for the first version. Add one only if the existing preparation contract cannot supply a deterministic and safe journey.

### Acceptance criteria

- A prepared user can complete the seven-step walkthrough in under five minutes.
- A user with insufficient history is guided through preparation without losing existing CSV, push, or simulator readings.
- Restarting the walkthrough does not modify application data.
- Refresh preserves the current guide step within the browser session.
- Closing presentation mode restores normal product navigation.
- The guide works at 1366×768, 1920×1080, 768px, and 390px widths.
- Playwright covers the happy path and a readiness-blocked path.

## 7. J2 — Model evidence experience

### Objective

Make the validated ML contribution visible without confusing unrelated benchmark files with production-artifact evidence.

### Evidence source

Use the production artifact manifests as the primary source:

- `backend/model_artifacts/global_tft_24h/manifest.json`
- `backend/model_artifacts/global_tft_168h/manifest.json`

Current evidence that may be displayed with its cohort label:

| Horizon | Cold-start macro MAE | Seasonal-naive MAE | Improvement | Households beating seasonal |
|---|---:|---:|---:|---:|
| 24 hours | 0.1849 kWh | 0.2515 kWh | 26.48% | 99.00% |
| 168 hours | 0.1973 kWh | 0.2491 kWh | 20.77% | 98.40% |

These are Low Carbon London cold-start cohort metrics. They are not guaranteed client-site accuracy.

Do not use `results/benchmark.csv` as proof of the production TFT models; it represents a different IHEPC experiment and does not contain the deployed Global TFT artifact.

### Backend work

Add a read-only authenticated endpoint such as:

```text
GET /api/v1/forecast/model-evidence
```

The service should return an allowlisted schema, not arbitrary manifest JSON:

- artifact name, display name, version, task, horizon, lookback;
- checkpoint fingerprint and parameter count;
- evaluation dataset and cohort;
- MAE, RMSE where available, baseline MAE, improvement percentage;
- percentage of households beating baseline;
- quantiles, calendar features, data gates;
- manifest limitations;
- live enabled/available/warmed state.

Validation rules:

- reject missing or non-finite metrics;
- do not advertise a model as live unless capability warm-up succeeds;
- preserve the exact metric labels and units from the manifest;
- never expose filesystem paths or entire checkpoints.

Likely files:

- `backend/app/routers/forecast.py`
- `backend/app/services/product_forecast_service.py`
- `backend/app/schemas/schemas.py`
- `backend/tests/test_model_contract.py`
- `backend/tests/test_product_forecast_api.py`

### Frontend work

Add a focused “Model evidence” view reachable from Forecast and presentation mode. It can be a route or a large dialog; a route is preferable for jury navigation and deep linking.

Suggested sections:

1. Two horizon cards with baseline improvement.
2. TFT versus seasonal-naive comparison bars.
3. Cohort and chronological evaluation explanation.
4. Architecture summary: 1,386,262 trainable parameters, four attention heads where manifest-backed.
5. Data gates and artifact fingerprints.
6. Prominent limitations panel.

Likely files:

- `frontend/src/app/model-evidence/page.tsx`
- `frontend/src/components/forecast/model-evidence-card.tsx`
- `frontend/src/components/forecast/baseline-comparison.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/types/index.ts`
- `frontend/src/app/forecast/page.tsx`

### Acceptance criteria

- Every displayed number is traceable to an artifact manifest.
- Both horizon cards show dataset, cohort, unit, and limitations.
- No claim uses the word “accuracy” as a substitute for MAE/RMSE.
- Disabled/unavailable artifacts remain visible only as clearly unavailable evidence, never as an active capability.
- API tests detect a mismatch between returned evidence and the manifest.
- Browser tests cover desktop/mobile and enabled/disabled 168-hour states.

## 8. J3 — Forecast explanation and trust

### Objective

Answer “Why should I trust this forecast?” using faithful model/input provenance rather than invented causal explanations.

### UI content

Add an explanation section beside or directly below the forecast chart:

#### Input quality

- 336-hour required lookback;
- observed hours and coverage percentage;
- maximum consecutive gap;
- latest reading timestamp and freshness;
- source types;
- imputation count if exposed by the existing result contract.

#### Forecast method

- selected horizon;
- Global TFT or seasonal-naive fallback;
- artifact version and fingerprint;
- input/output units;
- normalization and calendar context;
- exact fallback reason when applicable.

#### Predictive uncertainty

- p10/p50/p90 explanation in plain language;
- shaded interval already present in the chart;
- a reminder that the band is model-estimated and not site-calibrated.

#### Context, not causality

Show the calendar features the model receives—hour, weekday, month, workday, holiday—and recent input trend. Label this section “Context used by the model,” not “Reasons the model predicted this.” Do not present attention weights as causal importance.

### Confidence language

Use two separate labels:

- **Input quality:** high/medium/blocked, derived deterministically from coverage, gap, freshness, and finite-value gates.
- **Forecast range:** p10–p90 model interval width, reported numerically without calling it calibrated confidence.

### Proposed components

```text
frontend/src/components/forecast/
  forecast-explanation.tsx
  input-quality-badge.tsx
  uncertainty-guide.tsx
  provenance-grid.tsx
```

Likely files:

- `frontend/src/app/forecast/page.tsx`
- `frontend/src/types/index.ts`
- `backend/app/schemas/schemas.py` only if existing provenance fields are insufficient
- `backend/app/routers/forecast.py` only for missing computed metadata

Prefer no database migration: derive the view from existing persisted forecast provenance and readiness results.

### Acceptance criteria

- A jury member can identify model, horizon, data coverage, fallback state, and uncertainty meaning without opening developer tools.
- The UI never labels input quality as prediction accuracy.
- Fallback and missing-data states remain as informative as success states.
- The explanation matches PDF/export provenance.
- Tests cover real model, fallback, insufficient history, disabled week, and partial-imputation states.

## 9. J4 — Tariff-aware savings scenario

### Objective

Connect forecasts to a concrete action and quantify its estimated impact in MAD without pretending to control a real appliance.

### User interaction

From a persisted forecast, let the user configure:

- energy to shift in kWh;
- source hour or peak window;
- target hour or off-peak window;
- optional peak-load reduction cap;
- scenario label.

Display:

- original and adjusted forecast series;
- before/after peak demand;
- before/after estimated tariff cost;
- daily scenario saving in MAD;
- projected monthly saving, explicitly labelled as a simple extrapolation;
- assumptions, tariff values, timezone, and method;
- a “planning estimate—not a control command” disclaimer.

### Backend design

Add a pure calculation endpoint:

```text
POST /api/v1/simulation/savings
```

Suggested request:

```json
{
  "forecast_id": 123,
  "shift_kwh": 1.5,
  "from_hour": 19,
  "to_hour": 23
}
```

Suggested response:

```json
{
  "currency": "MAD",
  "timezone": "Africa/Casablanca",
  "energy_conserved": true,
  "before_cost": 18.42,
  "after_cost": 17.31,
  "estimated_saving": 1.11,
  "projected_30_day_saving": 33.30,
  "before_peak_kw": 2.80,
  "after_peak_kw": 2.20,
  "tariff": {},
  "adjusted_points": [],
  "assumptions": []
}
```

Calculation rules:

- resolve the forecast through the authenticated owner;
- use the site timezone and persisted peak/off-peak tariff;
- conserve total energy within floating-point tolerance;
- reject negative values, shifts larger than source energy, identical source/target hours, and unsupported horizons;
- never persist adjusted points as measured readings or real forecasts;
- do not claim savings when source and target tariffs are equal;
- keep the result deterministic for the same inputs;
- optionally record only an audit event, not a new domain table, for the first release.

Likely backend files:

- `backend/app/routers/simulation.py`
- `backend/app/services/simulation_service.py` or a new `savings_scenario_service.py`
- `backend/app/schemas/schemas.py`
- `backend/tests/test_energy_calculations.py`
- new `backend/tests/test_savings_scenario.py`

### Frontend design

Place the scenario panel on Forecast under a “Plan an action” section rather than promoting the legacy simulator route into the main navigation.

Proposed components:

```text
frontend/src/components/simulation/
  savings-scenario.tsx
  before-after-chart.tsx
  savings-summary.tsx
  assumptions-panel.tsx
```

Likely integration files:

- `frontend/src/app/forecast/page.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/types/index.ts`

### Acceptance criteria

- Energy before and after differs by less than the documented tolerance.
- Cost calculations reuse the same tariff interpretation as consumption reports.
- Cross-user forecast IDs return 404 or the established neutral ownership response.
- The original forecast and readings remain unchanged.
- Equal-rate scenarios return zero savings honestly.
- The chart works for both 24-hour and 168-hour forecasts without becoming unreadable.
- Unit tests cover peak-to-off-peak, off-peak-to-peak, equal rate, DST/timezone edge cases, invalid inputs, and ownership.

## 10. J5 — Dashboard hierarchy and visual polish

### Objective

Make the first authenticated screen answer four questions immediately:

1. What is happening now?
2. Is anything abnormal?
3. What happens next?
4. What should I do?

### Above-the-fold layout

Recommended desktop hierarchy:

```text
Live status + freshness       Today energy/cost       Monthly budget

Primary consumption chart with source and coverage

Next predicted peak          Highest-priority action  Potential scenario saving
```

On mobile, preserve this order vertically rather than shrinking every card into a dense grid.

### Work items

- Strengthen the live-state indicator with connected/reconnecting/stale semantics already available in the page.
- Promote one primary number per card; move provenance details into secondary lines.
- Add a “next predicted peak” summary derived from the latest stored forecast.
- Show the first open action with evidence and a direct action link.
- Show budget progress with explicit tariff/currency basis.
- Use skeletons instead of layout jumps during loading.
- Add restrained number/chart transitions and honor `prefers-reduced-motion`.
- Standardize empty, blocked, error, and stale states across Dashboard, Forecast, and Actions.
- Keep the current dark visual identity; avoid a theme rewrite.

Likely files:

- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/components/consumption/consumption-chart.tsx`
- new focused dashboard components under `frontend/src/components/dashboard/`

### Visual rules

- Cyan: live/forecast information.
- Emerald: savings, ready, completed.
- Amber: attention, assumptions, demo source.
- Red: critical or destructive only.
- No more than one animated focal element per viewport.
- All chart meaning must remain available without color alone.
- Avoid “AI sparkle” decoration unless it communicates the forecasting step.

### Acceptance criteria

- The four core questions are answered above the fold at 1366×768.
- No card displays a fabricated zero while loading or unavailable.
- Live freshness and source are always visible.
- Keyboard focus and contrast remain accessible.
- Mobile widths have no horizontal page overflow.
- Performance remains acceptable on the production build; animations do not continuously consume CPU.

## 11. J6 — Technical evidence, localization, and defense package

### Objective

Expose invisible engineering quality and ensure the final presentation works for the intended Moroccan context.

### Technical evidence view

Create an authenticated “System evidence” route or presentation-mode final step containing:

- simplified architecture diagram;
- live liveness/readiness summary;
- PostgreSQL migration revision;
- 24-hour and 168-hour artifact status/fingerprints;
- email queue health without recipient content;
- ownership/privacy guarantees;
- latest validated release commit and test evidence;
- links to download the audit and forecast report.

Do not hardcode “100 tests passed” as timeless runtime state. Package a validation manifest tied to a commit, for example:

```json
{
  "revision": "full-git-sha",
  "validated_at": "ISO-8601 timestamp",
  "backend_postgres": { "passed": 100, "skipped": 0 },
  "frontend_build_routes": 25,
  "browser": { "passed": 108, "failed": 0 },
  "production_dependency_vulnerabilities": 0
}
```

The UI must label this “Validation for revision …,” not “current live tests.” CI or the release process should generate it only after all gates pass.

Likely files:

- `frontend/src/app/system-evidence/page.tsx`
- `frontend/src/services/system.ts` or the primary `frontend/src/lib/api.ts`
- `frontend/public/validation-manifest.json` or a generated equivalent
- `.github/workflows/ci.yml`
- `backend/app/routers/system.py` if a safe migration/version field is needed

### Morocco and language polish

- Review French and Arabic strings for Dashboard, Forecast, Actions, model evidence, and savings.
- Verify RTL order for cards, charts, tooltips, dialogs, and presentation guide controls.
- Use `MAD`, Morocco-friendly number formatting, and `Africa/Casablanca` consistently.
- Keep tariff assumptions editable and visible; do not imply one universal national tariff.
- Use a Morocco-relevant demo household description while retaining the model’s London training-cohort disclosure.

Likely files:

- `frontend/src/lib/i18n.tsx`
- affected pages/components from J1–J5
- `frontend/src/lib/morocco.ts`

### Defense assets

Prepare:

- a five-minute primary demo script;
- a two-minute compressed demo;
- screenshots of every critical success state;
- a short screen recording as a hardware/network fallback;
- one architecture slide;
- one model-evidence slide;
- one limitations/future-work slide;
- an offline PDF export and audit copy.

### Acceptance criteria

- Evidence is tied to an exact revision and cannot silently become stale.
- The page exposes no secrets, personal email content, or raw user data.
- French/Arabic layouts work for the jury-critical path.
- A complete demo can be delivered with the network disconnected after local containers start.
- The presenter can recover from any step by using direct links or prepared screenshots.

## 12. Test plan

### Backend

- Unit tests for model-evidence schema and manifest validation.
- Unit/property tests for tariff calculations and energy conservation.
- Ownership tests for model evidence where authentication is required and for forecast-based scenarios.
- Regression tests for 24-hour and 168-hour capability gating.
- Full SQLite suite for fast iteration.
- Full isolated PostgreSQL suite before merge/release.

### Frontend

- ESLint and TypeScript after every milestone.
- Production build after route/config changes.
- Component-level pure-function tests if a test runner is introduced intentionally; do not add a large testing framework only for cosmetic components.
- Playwright coverage for:
  - presentation journey;
  - history preparation;
  - 24h/168h evidence;
  - explanation success/fallback/blocked states;
  - savings scenario math presentation;
  - system evidence;
  - mobile and RTL critical path;
  - security headers.

### Live release validation

```text
docker compose up --build -d
docker compose ps
GET /api/v1/system/live
GET /api/v1/system/ready
GET /
```

Then perform one normal-user journey:

```text
Sign in
-> prepare/verify history
-> generate 24h
-> generate 168h
-> inspect explanation/evidence
-> calculate savings scenario
-> inspect action
-> export PDF
-> open system evidence
```

## 13. Definition of done

The jury-impact release is complete only when:

- all J0 gates are green or have an approved expiring exception;
- the working tree is clean and the validation manifest matches the release commit;
- the complete PostgreSQL backend suite passes with zero skips;
- lint, typecheck, and production build pass;
- the six-project browser matrix passes;
- both forecast horizons warm in the release Compose environment;
- presentation mode completes in under five minutes;
- every ML metric is traceable to the deployed artifact manifest;
- the savings scenario conserves energy and states all assumptions;
- no presentation operation deletes or silently overwrites real user data;
- French/Arabic critical-path review is complete;
- a screen-recorded fallback and static evidence package exist;
- the presenter has rehearsed at least three full runs from a cold browser session.

## 14. Risk register

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Last-minute scope growth | High | High | Enforce non-goals and milestone acceptance criteria |
| Model metric misrepresentation | Medium | Critical | Source only from artifact manifests; always show cohort and limitations |
| Demo data contaminates real data | Low | High | Reuse owned/idempotent forecast-demo preparation; reset only UI guide state |
| Savings estimate appears guaranteed | Medium | High | Label assumptions, tariff source, and projection method prominently |
| WebKit/session flake returns | Medium | Medium | Deterministic waits, repeated isolated run, full matrix |
| Visual polish breaks mobile/RTL | Medium | Medium | Test critical widths and Arabic after every UI milestone |
| Validation counts become stale | High | Medium | Tie evidence manifest to an exact commit and generate after CI |
| External email/OAuth disrupts demo | Low | High | Do not trigger them in presentation mode; show readiness/evidence only |
| Model warm-up delays presentation | Low | Medium | Start Compose early and verify readiness before jury arrival |
| Docker/hardware failure | Low | Critical | Prepared recording, screenshots, PDF, and architecture/model slides |

## 15. Compressed three-day plan

If less than one week remains, implement only the highest-return work.

### Day 1 — Trust and stability

- Resolve or document dependency audit.
- Fix WebKit flake.
- Add model-evidence endpoint and simple evidence cards.
- Add forecast input-quality/provenance panel.

### Day 2 — Jury journey

- Add presentation-mode guide using existing routes.
- Reorganize Dashboard above the fold.
- Add direct links between Forecast, Actions, evidence, and export.
- Add restrained loading/motion polish.

### Day 3 — Proof and rehearsal

- Add a minimal non-persisted savings calculator if calculation tests can be completed; otherwise omit it.
- Generate revision-tied validation evidence.
- Run full PostgreSQL, frontend, browser, dependency, and Compose gates.
- Capture screenshots/video and rehearse three times.

In the compressed plan, omit the savings simulator rather than shipping unverified tariff mathematics.

## 16. Five-minute jury walkthrough target

### 0:00–0:30 — Problem and live product

“EnergyAI helps a household understand consumption, anticipate demand, and act before expensive peaks.” Show the live status, today’s energy/cost, source, freshness, and coverage.

### 0:30–1:20 — Data integrity

Show that data is owned, persisted, labelled by source, and subject to quality gates. Briefly mention CSV, push API, and explicit simulator without navigating through every setup screen.

### 1:20–2:30 — Real forecasting

Generate/open the 24-hour forecast, show p10/p50/p90, input quality, model version, and fingerprint. Switch to the independently packaged 168-hour forecast.

### 2:30–3:15 — Scientific evidence

Open model evidence. State the exact cold-start MAE improvement over seasonal naive for both horizons, then immediately disclose the London cohort and site-generalization limitation.

### 3:15–4:10 — Action and value

Open the evidence-backed action and savings scenario. Shift energy from a peak to an off-peak period, then show the before/after curve and estimated MAD saving with assumptions.

### 4:10–4:45 — Complete product engineering

Open system evidence: PostgreSQL head, two warmed artifacts, workers, email queue health, ownership/privacy, test validation tied to the release commit.

### 4:45–5:00 — Closing statement

“EnergyAI does not only predict consumption. It validates the input, explains the forecast contract, recommends a measurable action, and quantifies the potential impact while preserving data ownership and provenance.”

## 17. Immediate next action

Start with J0 and do not begin the savings scenario until the CI audit and browser flake have an explicit disposition. After J0, implement J1 and J2 together because the guided journey needs model evidence as its strongest proof point.
