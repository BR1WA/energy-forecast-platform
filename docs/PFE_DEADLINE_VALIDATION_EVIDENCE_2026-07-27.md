# EnergyAI Deadline Reconstruction Validation

**Date:** 2026-07-27  
**Scope:** Final PFE deadline reconstruction

## Implemented product path

The normal-user workflow is now intentionally limited to Dashboard, Usage,
Forecast, Actions, and Settings. Admin remains role-gated. Legacy Consumption,
Alerts, Recommendations, and Reports URLs are compatibility redirects.

Actions combines measured incidents with their linked recommendations through the
existing `alert_id`; it does not introduce a lifecycle or database migration.
Usage owns consumption CSV import/export, and Forecast owns persisted-forecast PDF
export.

The landing page follows live authentication capabilities, estimated costs disclose
their tariff basis, and Setup, Usage, and blocked Forecast states link to a generated
forecast-ready sample CSV.

## Real dual-horizon forecasting

The final runtime enables both independently packaged Global TFT capabilities:

| Horizon | Model | Checkpoint SHA-256 | API result |
|---|---|---|---|
| Next 24 hours | `global_tft_24h` | `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d` | `global_tft`, 24 sequential hourly points |
| Next 7 days / 168 hours | `global_tft_168h` | `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93` | `global_tft`, 168 sequential hourly points |

The real-model API test uses a normal-user token, the existing primary-meter input
preparation, the packaged PyTorch checkpoints, and the production forecast routes.
It verifies capability advertisement, readiness, exact model selection, artifact
fingerprints, point counts, one-hour timestamp sequences, forecast-window length,
latest-forecast filtering, and another user's inability to read either result.
Neither model inference path is mocked.

The Forecast URL preserves `horizon=24` or `horizon=168`. The weekly chart groups
the 168 hourly points into local calendar-day totals for readability without
changing the stored or exported hourly values. PDF export passes the selected
forecast ID; extracted PDF text identifies either “Next 24 Hours” or
“7-Day / 168-Hour” and the correct hourly target count.

## Automated evidence

| Check | Result |
|---|---|
| Frontend lint | Passed |
| Frontend TypeScript | Passed |
| Next.js production build | Passed; 25 routes generated |
| Backend suite | 95 passed, 4 skipped |
| ML-enabled dual-artifact contract suite | 11 passed in 7.05s |
| Real normal-user dual-horizon API test | 1 passed in 5.22s |
| Horizon-specific 24h/168h PDF test | 1 passed in 3.06s |
| Full frontend browser suite | 16 passed on Chromium in 30.6s |
| Dual-horizon UI journey | 24h and 168h generation, both PDFs, both switch directions, and refresh persistence passed |
| Weekly state coverage | Loading, readiness-blocked, empty, error, success, daily chart, and disabled capability passed |
| Dual-horizon responsive matrix | 24/24 relevant tests passed across Chromium, Firefox, WebKit, 360px, 390px, and 768px projects |
| Complete six-project browser run | 95 passed, 1 unrelated WebKit registration test timed out under parallel load; its isolated rerun passed 1/1 |
| Local frontend smoke | HTTP 200 at `http://localhost:3000/` |
| Local backend liveness | HTTP 200 at `http://localhost:8000/api/v1/system/live` |
| Live forecast readiness | HTTP 200; `global_tft_24h` and `global_tft_168h` both warmed with no artifact error |
| Live authenticated capabilities | HTTP 200; advertised horizons `[24, 168]` with their corresponding model names |
| Docker services | Database, backend, and frontend healthy; alert and email workers running |
| SMTP configuration | Enabled and complete inside the backend container |
| SMTP authentication | Gmail SMTP authentication succeeded; no test email was sent |

## Forecast demo-history repair evidence

The blocked Forecast state now includes **Prepare demo history**. This authenticated
operation adds synthetic `forecast_demo` readings only to the current user's
primary meter. It preserves existing CSV, push, and simulator rows, keeps an
established live meter interval, skips duplicate timestamps, records an audit
event, and is idempotent within the current hour.

The affected local account was repaired through the production API without
deleting its existing data:

| Check | Exact result |
|---|---|
| Preparation | `ready`; 88 added, 249 duplicates skipped |
| Active input | 99.76% coverage; 335/336 observed hours; longest gap 1 hour |
| 24-hour readiness | `ready`; `global_tft_24h` |
| 168-hour readiness | `ready`; `global_tft_168h` |
| Real 24-hour generation | Forecast ID 1; `global_tft`; 24 hourly points from 2026-07-27 16:00 UTC through 2026-07-28 15:00 UTC |
| Real 168-hour generation | Forecast ID 2; `global_tft`; 168 hourly points from 2026-07-27 16:00 UTC through 2026-08-03 15:00 UTC |
| Selected 24-hour PDF | HTTP 200; `application/pdf`; 4,474 bytes |
| Selected 168-hour PDF | HTTP 200; `application/pdf`; 12,909 bytes |
| Demo-history backend test | 1 passed; ownership, preservation, cadence, readiness, repeat safety, and audit coverage |
| Weekly blocked-to-ready browser flow | Passed on Chromium desktop |

## Notes

- The backend suite reports the expected development warning for the default admin
  password while `DEBUG` is enabled.
- No deferred database, tariff-provider, forecasting-model, multi-site, reporting,
  or administration expansion was introduced.
- No model artifact, manifest, hash, architecture, or forecast aggregation endpoint
  was changed. The only runtime capability change is enabling the already packaged
  and validated 168-hour artifact.
- Real inbox delivery remains a separate end-to-end check because it requires a
  chosen recipient and sends an external email.
