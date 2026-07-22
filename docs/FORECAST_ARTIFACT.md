# Production Forecast Artifact

The PFE release serves one fixed inference artifact:

- name: `global_tft_24h`
- version: `1.0.0`
- task: next 24 hourly energy values
- input/output unit: kWh per hour
- lookback: 336 hours
- quantiles: 0.1, 0.5, 0.9

The checkpoint and its machine-readable contract are stored in
`backend/model_artifacts/global_tft_24h/`. The manifest records the expected
SHA-256 fingerprint, byte size, calendar feature order, readiness gates,
research metrics, provenance, and limitations. Startup readiness validates the
fingerprint and loads the state dict into the matching inference architecture.

## Input contract

The adapter uses only the authenticated user's primary meter. It integrates
persisted power intervals into site-local hourly energy, then checks:

1. the latest 336 hourly bins;
2. at least 95% observed interval coverage;
3. no missing run longer than three hours; and
4. finite values after bounded linear interpolation.

The accepted window is normalized with a rolling per-site z-score. Scaler values
and imputed timestamps are persisted with every forecast.

## Fallback

If the input passes the gates but the TFT runtime or artifact cannot run, the API
uses the matching hours from the previous week. It persists method
`seasonal_naive`, the runtime failure reason, and no uncertainty interval.

## Runtime dependency

Ordinary API tests do not require Torch. For local inference install both files:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-ml.txt
```

The Docker runtime installs the CPU-only Torch wheel. The Docker test target uses
`INSTALL_TORCH=0`, and Torch-dependent tests skip there while artifact integrity,
readiness gates, fallback, API, and ownership tests still run.
