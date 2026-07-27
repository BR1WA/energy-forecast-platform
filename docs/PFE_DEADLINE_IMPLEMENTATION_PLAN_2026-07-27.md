# EnergyAI Final PFE Modifications

**Date:** 2026-07-27  
**Status:** Implemented and validated locally  
**Goal:** Deliver the smallest convincing product reconstruction without
changing the proven backend architecture or adding deadline-risk features.

## Scope

The normal-user product will expose five primary destinations:

1. Dashboard
2. Usage
3. Forecast
4. Actions
5. Settings

Admin remains role-gated. Reports and Simulator will not appear in primary
navigation.

## Work packages

### 1. Navigation and compatibility routes

- Rename Consumption to Usage.
- Add `/usage` as the canonical usage route.
- Add `/actions` as the canonical alert/action route.
- Remove Reports, Recommendations, and Alerts from primary navigation.
- Keep Admin role-gated.
- Redirect:
  - `/consumption` to `/usage`;
  - `/alerts` to `/actions`;
  - `/recommendations` to `/actions`;
  - `/reports` to `/usage`.
- Update global search, notification links, Settings links, and Dashboard links.

### 2. Unified Actions page

- Load alerts and recommendations using the existing APIs.
- Display active alerts first.
- Associate a recommendation with its source alert through `alert_id`.
- Present unlinked recommendations as follow-up actions.
- Avoid contradictory presentation:
  - a recommendation linked to a resolved alert is labelled as follow-up work;
  - alert state and action state remain separately visible;
  - no backend lifecycle migration is introduced.
- Preserve alert acknowledge, resolve, and reopen operations.
- Preserve recommendation complete, dismiss, and reopen operations.
- Keep alert-rule configuration on the Actions page.

### 3. Contextual exports

- Retain consumption CSV export on Usage.
- Move latest-forecast PDF export onto Forecast.
- Remove Reports from navigation and redirect the old route.
- Do not add scheduled or custom report generation.

### 4. Dead-end fixes

- Landing page reads authentication capabilities.
- When registration is unavailable, replace Create account/Get started calls
  to action with Sign in and an honest availability message.
- Explain that displayed costs are estimates based on configured tariff rates.
- Publish a downloadable forecast-ready CSV/demo dataset.
- Link the sample from Setup, Usage, and blocked Forecast states.
- Forecast readiness explains the 336-hour, 95% coverage, and three-hour
  maximum-gap requirements and provides direct next actions.

### 5. Dashboard polish

- Keep the existing APIs and live WebSocket logic.
- Default to Today and keep the current period selector.
- Prioritize:
  - current source/freshness and latest load;
  - today's energy and estimated cost;
  - monthly budget trajectory;
  - latest forecast or forecast readiness link;
  - one highest-priority action.
- Replace separate alert and recommendation counters with one prioritized
  action surface.
- Remove the generic data-controls block and repeated links.
- Keep data-quality details when they affect trust.

## Explicitly deferred

- New tariff database models or provider integrations.
- New Dashboard aggregation endpoint.
- Alert/recommendation database migration.
- Advanced usage-pattern detection.
- Scheduled reports.
- Multi-site support.
- New forecasting models.
- Large visual redesign.
- Admin audit-event UI.

## Dual-horizon forecast completion

- Keep the documented default at 24 hours.
- Enable the independently packaged 168-hour Global TFT artifact in the final
  Compose runtime.
- Preserve the selected horizon in the Forecast URL.
- Use the existing readiness, generation, latest, history, ownership, and report
  APIs with an explicit `horizon_hours` value.
- Group the 168 hourly chart targets into daily totals while retaining all 168
  hourly values in the persisted forecast and PDF.
- Export the exact selected forecast ID and identify PDFs as either next 24 hours
  or 7 days / 168 hours.
- Hide the weekly selector when the runtime does not advertise a warmed weekly
  capability; a direct weekly URL must show an actionable error without requesting
  or substituting 24-hour forecast data.

## Implementation order

1. Add this plan and capture the starting worktree state.
2. Add canonical routes and redirects.
3. Update navigation and all internal links.
4. Build the unified Actions page.
5. Add Forecast PDF export.
6. Add the forecast-ready CSV and contextual links.
7. Fix capability-aware landing calls to action.
8. Add tariff-estimate disclosures.
9. Simplify Dashboard action and control surfaces.
10. Run frontend lint, typecheck, build, backend regression tests, and focused
    browser journeys.
11. Update PFE release documentation and screenshots if the UI changed
    materially.

## Acceptance checklist

- [x] Normal users see exactly five primary navigation destinations.
- [x] Admin sees the same five plus Admin.
- [x] Old routes redirect without a not-found page.
- [x] Actions displays incidents and linked follow-up actions together.
- [x] Consumption CSV is available from Usage.
- [x] Forecast PDF is available from Forecast when a forecast exists.
- [x] Reports is absent from navigation.
- [x] Simulator is absent from primary navigation but remains accessible from
      Settings → Data sources.
- [x] Registration-disabled deployments do not advertise account creation.
- [x] Costs are labelled as estimates using configured tariffs.
- [x] A forecast-ready sample CSV is downloadable.
- [x] Blocked forecast states explain requirements and link to the sample and
      Usage.
- [x] A blocked user can explicitly prepare non-destructive, labelled synthetic
      history in one click; the operation is user-owned and idempotent per hour.
- [x] Dashboard contains one prioritized Actions surface rather than separate
      Alerts and Recommendations cards.
- [x] Existing backend ownership, ingestion, forecast, session, and account
      tests continue to pass.
- [x] Frontend lint, typecheck, production build, and focused browser tests
      pass.
- [x] Both packaged model manifests and checkpoints pass size, SHA-256, strict
      load, output-shape, finite-output, and deterministic smoke checks.
- [x] A normal-user API test generates real Global TFT forecasts with exactly 24
      and 168 sequential hourly points.
- [x] Switching both directions and refreshing the selected 168-hour horizon pass
      browser validation.
- [x] The selected 24-hour and 168-hour forecast IDs produce horizon-specific PDFs.
- [x] Weekly loading, blocked, empty, error, success, chart, and unavailable
      capability states pass browser validation.
- [x] Ownership isolation is enforced for both horizons.

## Definition of done

The deadline reconstruction is done when every checklist item is satisfied,
the old pages are reachable only through compatibility redirects, no unshipped
feature is advertised, and the PFE demonstration can move from data import to
monitoring, real 24-hour forecasting, real 7-day / 168-hour forecasting,
horizon-specific export, and Actions without explaining away a dead-end page.

## Demo testing shortcut

When current simulator readings move the forecast anchor beyond an older sample
CSV, Forecast offers **Prepare demo history** in the blocked state. It fills the
active 336-hour window with `forecast_demo` readings, skips timestamp duplicates,
does not delete existing rows, retains an established meter cadence, and can be
run again safely. The normal CSV workflow remains available for ingestion demos.
