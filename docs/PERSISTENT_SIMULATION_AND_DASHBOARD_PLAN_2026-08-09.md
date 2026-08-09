# Persistent Simulation History and Communicative Dashboard Plan

Date: 2026-08-09

## Outcome

Deliver a truthful, persistent demo-data experience that survives Azure scale-to-zero and a dashboard that explains the numbers in plain language. Synthetic electricity must remain visibly distinct from measured CSV or push-meter data.

## Product rules

1. Only an explicitly started simulator may generate simulation readings.
2. A brand-new empty meter receives 30 days of deterministic history at 15-minute intervals on its first simulator start.
3. Existing CSV, push, forecast-demo, or legacy history is preserved. Starting the simulator must not fill gaps inside those sources.
4. Existing simulator history is also preserved when this feature is first deployed. A persisted continuity marker establishes the point after which automatic catch-up is allowed, so the already-observed 12-hour hole is not silently rewritten.
5. Catch-up runs only for a session that stayed in the running state while the backend slept. Stopping and later starting the simulator establishes a new continuity boundary and leaves the stopped interval visible.
6. Every generated row uses `source="simulation"` and simulated quality metadata.
7. `(meter_id, timestamp)` remains the database-level idempotency guarantee. Deterministic batch keys provide replay safety at the operation level.
8. Catch-up uses 15-minute samples normally and progressively coarser intervals for exceptional outages, with a hard point limit.
9. “Reset demo data” is explicit and confirmed. It removes only `simulation` readings and their ingestion batches, restores the default seeded scenario, and regenerates 30 days. CSV and push readings are never deleted.
10. Login and ordinary dashboard reads never trigger history generation.

## Implementation stages

### 1. Deterministic simulation engine

- Replace unseeded random load generation with a timestamp-based household profile.
- Model weekday and weekend differences, morning and evening peaks, an overnight base load, and bounded seeded variation.
- Use the site timezone for household behavior and UTC for stored timestamps.
- Make voltage, reactive power, and current deterministic and physically consistent with active power.

### 2. Persistent bootstrap and continuity catch-up

- Store the profile version, stable household seed, continuity boundary, and last catch-up metadata inside the owned `SimulationSession.configuration` JSON.
- Bootstrap 30 days / 720 hours at 15-minute cadence only when the primary meter is empty.
- On backend wake, advance every already-running session from its latest eligible simulation reading to the current time.
- Never search for or fill arbitrary historical holes; catch-up is forward-only from the most recent simulation timestamp and cannot cross the continuity boundary.
- Generate an immediate deterministic live reading, then continue the existing five-second live loop.

### 3. Explicit reset and API contract

- Upgrade `POST /api/v1/simulation/reset` into “Reset demo data.”
- Delete only simulator-owned readings and batches, preserve all measured/imported data, reset the stable scenario, regenerate history, and leave the feed stopped.
- Extend simulator status with history span, point count, forecast-history readiness, profile label, seed reproducibility, and last catch-up details.
- Record simulator start, stop, configuration, and reset operations in the audit trail.

### 4. Ingestion integrity and performance

- Mark synthetic ingestion quality as `simulated`.
- Preload existing timestamps for a batch so a 2,881-point bootstrap does not perform one duplicate lookup per row.
- Retain nested inserts and the unique meter/timestamp constraint as the final concurrency guard.

### 5. Communicative dashboard UX

- Add an “At a glance” narrative that turns the selected period into a plain-language summary of energy, cost, peak, comparison, data freshness, and next action.
- Make simulation provenance prominent whenever the selected period contains synthetic readings.
- Add short explanations to numeric KPI cards so users understand what each number means.
- Add a chart interpretation sentence and a trust/coverage sentence without hiding gaps or uncertainty.
- Keep the existing detailed cards, chart controls, and data-quality evidence for users who want to inspect the numbers.

### 6. Simulator UX

- Explain automatic history preparation and Azure wake catch-up on the simulator page.
- Display persisted history coverage and catch-up status.
- Rename and confirm the destructive simulator-only reset action, clearly stating that real/imported rows remain untouched.

### 7. Verification

- Backend tests: deterministic profile, weekday/weekend shape, 30-day bootstrap, 336-hour readiness, replay idempotency, forward catch-up, legacy-gap preservation, stopped-gap preservation, coarser capped catch-up, reset isolation, ownership, and source/quality labels.
- Frontend checks: TypeScript, ESLint, production build, and Playwright coverage for narrative dashboard and simulator reset/status states.
- Regression tests: ingestion, ownership, forecasting readiness, consumption calculations, and live monitoring.

## Acceptance criteria

- A new empty simulator has at least 720 hours of labelled history after first start.
- Repeating start, tick, wake, or reset requests at the same anchor cannot create duplicate timestamps.
- A backend restart while a session is running produces forward catch-up; a user stop/start does not backfill the stopped interval.
- The pre-existing 12-hour gap remains unless the user explicitly resets demo data.
- No CSV or push reading is deleted, relabelled, or used as a trigger for gap filling.
- Today, Week, Month, and Year views render persisted context; the UI clearly calls simulation synthetic.
- The first dashboard screen gives a useful sentence-level interpretation before requiring the user to decode KPI cards.
