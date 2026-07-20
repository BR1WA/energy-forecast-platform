# EnergyAI

EnergyAI is a Master's PFE energy-intelligence application for a household or
small site. It lets each user import or ingest owned meter readings, calculate
interval-based energy cost with a site tariff, run a validated 24-hour forecast,
and act on recorded load or data-quality alerts.

## What Works

- Account registration, login, refresh-token rotation, password change, and
  administrator-managed account activation.
- One private site and primary meter per user, with budgets, forecasts, alerts,
  reports, and owned data export.
- CSV import with preview/validation, authenticated push ingestion, and a
  clearly labelled simulator.
- Live, Today, 7 days, Month, Year, All, and Custom tracking with interval-based
  tariff/budget calculations plus source, coverage, and freshness labels.
- One packaged Global TFT 24-hour artifact with a 336-hour readiness contract,
  native model quantiles, persisted preprocessing provenance, and an explicit
  weekly seasonal fallback.
- Persistent high-load and missing-push-data alerts with evidence, cooldown,
  acknowledgement/resolution lifecycle, and actions that can be completed,
  dismissed, or reopened.
- Docker Compose deployment, liveness/readiness probes, audit events, CI checks,
  and documented backup/restore procedures.

## Deliberately Out Of Scope

- Remote appliance, battery, or demand-response control.
- Pull connectors to third-party utilities.
- Subscriptions, billing, plans, and payment flows. The PFE release is free.
- 168-hour and monthly production forecasting. Research outputs are not exposed
  until they have independent product contracts and target-client validation.
- The `models/ecl_deep_benchmark` research artifacts are multi-household ECL
  experiments and are intentionally not connected to the single-site product.

## Run Locally

See [docs/operations.md](docs/operations.md) for local development, Docker,
quality gates, readiness checks, backup/restore, and deployment configuration.

Core checks:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
# Required only for local TFT inference:
python -m pip install -r requirements-ml.txt
python -m pytest -q

cd ..\frontend
npm run lint
npm run typecheck
npm run build
```
