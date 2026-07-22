# Product V1 Baseline

**Branch:** `release/product-v1`  
**Base revision:** `102f8cd` (`main`, merged PFE pull request #2)  
**Recorded:** 2026-07-22

This file freezes the accepted PFE behavior that Product V1 must preserve.

## Release contract

- One normal user owns exactly one Site and one primary Meter.
- Persisted primary-meter readings are the only input to product forecasts.
- The production forecast is a 24-hour Global TFT with an explicit seasonal-naive
  fallback and visible method/provenance.
- Forecast input requires 336 hourly slots, at least 95% coverage, no gap longer
  than three hours, and finite values after bounded interpolation.
- Alerts and recommendations are evidence-backed, owner-scoped, and persisted.
- Reports export owned consumption CSV and forecast PDF data.
- Admin model readiness is read-only; no training/model-selection controls exist.

## Accepted evidence at the branch point

| Gate | Accepted PFE result |
|---|---|
| Backend tests | 44 passed in the full local runtime |
| Container tests | 43 passed, 1 Torch-specific test skipped in the Torch-free test image |
| Frontend | ESLint, TypeScript, and production build passed; 16 routes built |
| Database | Fresh PostgreSQL upgraded to Alembic head `d3a9f6c1b208` |
| Docker | Backend/frontend live; database and fixed 24-hour model ready |
| Restore | PostgreSQL custom-format backup restored into an isolated database |
| Browser | Registration, setup, timeframes, settings, auth, admin readiness, 360 px layout, forecast disclosure, reports, alerts, and recommendations passed |

## Fixed 24-hour artifact

- Name: `global_tft_24h`
- Version: `1.0.0`
- Checkpoint SHA-256:
  `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d`
- Checkpoint size: `5,600,105` bytes
- Lookback/horizon: `336/24` hourly steps
- Cold-start macro MAE: `0.1849280672 kWh`
- Improvement over seasonal naive: `26.4815%`

## G0 safe defaults

The following Product V1 capabilities are disabled by default and must not create
visible controls until their own readiness gates pass:

- `FORECAST_168H_ENABLED=false`
- `EMAIL_DELIVERY_ENABLED=false`
- `GOOGLE_AUTH_ENABLED=false`

Enabling email or Google with incomplete configuration is a startup error. Enabling
the 168-hour flag does not make the service globally unready when the optional week
artifact is invalid; it keeps that capability hidden while the accepted 24-hour
path remains independently healthy.
