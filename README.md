# EnergyAI

EnergyAI is a Master's PFE energy-intelligence application for a household or
small site. It lets each user import or ingest owned meter readings, calculate
interval-based energy cost with a site tariff, run a validated 24-hour forecast,
and act on recorded load or data-quality alerts.

## What Works

- Account registration, login, refresh-token rotation, password change, and
  administrator-managed account activation.
- Per-user sites, meters, budgets, forecasts, alerts, reports, and data export.
- CSV import with preview/validation, authenticated push ingestion, and a
  clearly labelled simulator.
- Timeframe consumption history, interval-based tariff/budget calculations, and
  source/freshness labels.
- Three compatible, validated 24-hour artifacts: PatchTST, CNN-BiLSTM, and SOTA
  Hybrid. Forecasts preserve model and input provenance and are labelled as point
  forecasts until calibrated uncertainty is available.
- Persistent high-load and missing-push-data alerts with cooldowns, evidence,
  in-app acknowledgement, and evidence-backed actions that can be completed or
  dismissed.
- Docker Compose deployment, liveness/readiness probes, audit events, CI checks,
  and documented backup/restore procedures.

## Deliberately Out Of Scope

- Remote appliance, battery, or demand-response control.
- Pull connectors to third-party utilities.
- Subscriptions, billing, plans, and payment flows. The PFE release is free.
- 168-hour and 720-hour serving. The files in `models/active/168h` and
  `models/active/720h` are not promoted because they do not yet include the
  portable preprocessing/configuration contract required by the API.
- The `models/ecl_deep_benchmark` research artifacts are multi-household ECL
  experiments and are intentionally not connected to the single-site product.

## Run Locally

See [docs/operations.md](docs/operations.md) for local development, Docker,
quality gates, readiness checks, backup/restore, and deployment configuration.

Core checks:

```powershell
cd backend
python -m pytest -q

cd ..\frontend
npm run lint
npm run typecheck
npm run build
```
