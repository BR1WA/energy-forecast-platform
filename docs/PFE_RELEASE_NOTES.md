# PFE Release Notes

**Branch:** `release/pfe`
**Release validation date:** 2026-07-20
**Product scope:** one user, one site, one primary meter

## Demonstration Walkthrough

1. Register a user and complete the one-site setup with tariff and monthly budget.
2. Choose CSV import, push API, or the explicitly labelled simulator as the data source.
3. Use Dashboard for source, freshness, consumption, cost, peak, budget, forecast,
   alert, and recommendation summaries.
4. Use Consumption for Live, Today, 7 days, Month, Year, All, or Custom history and
   drill down through paginated raw readings.
5. Generate a 24-hour forecast. The Global TFT runs only when the 336-hour input,
   95% coverage, three-hour gap, and finite-value gates pass. Otherwise the UI shows
   the explicit reason or a labelled seasonal-naive fallback.
6. Acknowledge and resolve evidence-backed alerts; complete or dismiss their
   deterministic recommendations.
7. Download the owned monthly consumption CSV and forecast PDF with calculation,
   source, coverage, tariff, method, and limitation metadata.
8. Sign in as an admin to manage user roles/activation and inspect database and
   fixed-model readiness. No training or model activation controls are exposed.

## Release Evidence

- Local backend suite: 44 passed.
- Docker test image: 43 passed, 1 skipped because Torch is deliberately excluded
  from the CI test target; the Torch inference test passed in the local full suite.
- Frontend lint, TypeScript check, and production build: passed; 16 routes built.
- Fresh PostgreSQL database migrated from the initial revision to Alembic head.
- Isolated Docker runtime returned `alive` and `ready`; the Global TFT warmed with
  artifact SHA-256 `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d`.
- PostgreSQL custom-format backup restored into a separate database and both
  verification rows matched.
- Chrome journey passed registration validation, one-site simulator setup, all
  timeframe selectors, settings persistence, logout/sign-in, admin readiness,
  360px dashboard/drawer layout, insufficient-history forecast disclosure, raw
  readings, reports, alerts, and recommendations.
- Final source audit found no P0 or P1 issue after removing dormant connector,
  fabricated appliance simulation, stale model-selection, retraining, multi-site,
  and notification preference paths.

## Known Limitations

- The production forecast horizon is 24 hours. Week and month forecasting remain
  Product V1 work and must use independently validated artifacts.
- Simulator readings are synthetic and always carry the simulator source label.
- Email verification, password reset email, alert email, Google authentication, and
  Gemini features are intentionally deferred; the PFE UI makes no claim that they work.
- Avatar files use local storage, and the simulator loop assumes one backend process.
  These are acceptable for the single-instance PFE deployment, not horizontal scale.
- The packaged TFT is a global model. Its uncertainty interval is native model output
  and has not been recalibrated for each client's site.

## Presentation Rehearsal

Repeat the core walkthrough with the presentation dataset and record screenshots for
the PFE report. The release browser pass used disposable simulator data; rehearse CSV
import and the intended jury account once deployment credentials are configured.

## PFE Report Notes

Frame the contribution around truthful multi-timeframe monitoring plus gated forecasting,
not the number of model architectures. Present the one-site constraint as deliberate
scope control, distinguish measured data from simulation and model output, document the
fallback path, and include the migration, ownership, CI, Docker readiness, and restore
evidence above. Future-work claims should remain limited to the deferred Product V1 list.
