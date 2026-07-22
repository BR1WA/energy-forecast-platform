# Global TFT 168-Hour Artifact

**Product artifact:** `backend/model_artifacts/global_tft_168h`  
**Product version:** `1.0.0`  
**Promotion date:** 2026-07-22  
**Feature flag:** `FORECAST_168H_ENABLED`

## Contract

| Property | Value |
|---|---|
| Task | Week-ahead hourly energy forecast |
| Input | Latest 336 hourly kWh values from the owned primary meter |
| Output | 168 hourly `p10`, `p50`, and `p90` kWh values |
| Normalization | Per-site rolling-window z-score |
| Data gate | At least 95% coverage, maximum three-hour gap, finite values |
| Checkpoint size | 5,600,105 bytes |
| SHA-256 | `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93` |

The decoder length is driven by the future-calendar input, so the fixed 24-hour
and 168-hour checkpoints share the same `GlobalTFT` architecture without sharing
model state, manifest state, readiness, or feature availability.

## Recorded independent cohort evidence

The source experiment is `full_selected_v1`, seed `2026`, trained on Low Carbon
London smart-meter households.

| Metric | Known households | Cold-start households |
|---|---:|---:|
| Evaluated households | 2,000 | 499 |
| Evaluation windows | 47,258 | 11,830 |
| Macro MAE | 0.19497 kWh | 0.19732 kWh |
| Macro RMSE | 0.33866 kWh | 0.34109 kWh |
| Seasonal-naive macro MAE | 0.24777 kWh | 0.24906 kWh |
| MAE improvement over seasonal naive | 21.31% | 20.77% |
| Households beating seasonal naive | 97.55% | 98.40% |
| P90 household MAE | 0.38535 kWh | 0.38987 kWh |

These metrics meet the Product V1 promotion thresholds of positive macro-MAE
improvement and at least 75% of cold-start households beating seasonal naive.

## Product promotion checks

- Checkpoint digest and byte size match the production manifest.
- All 186 tensors load strictly into `app.ml.global_tft.GlobalTFT`.
- The prepared split contains 2,000 unique known households and 500 unique
  cold-start households with zero identifier overlap. The reported evaluation
  used the 499 cold-start households that supplied valid evaluation windows.
- A deterministic CPU smoke fixture returns shape `(1, 168, 3)` with finite,
  ordered raw quantiles.
- Repeating the smoke inference and three reference target vectors (indices 0,
  83, and 167) are checked at an absolute tolerance of `1e-5`. This catches
  meaningful artifact/preprocessing changes without treating last-bit CPU
  attention differences as a model failure.
- Product inference applies the same rolling-window z-score and calendar feature
  order declared in the experiment and manifest.
- The deployable directory contains only the checkpoint and manifest. Raw data,
  notebooks, logs, predictions, cloned repositories, and training runs remain
  outside the application artifact tree.

## Runtime and visibility

The week capability is not advertised merely because files exist. It is visible
only when:

1. `FORECAST_168H_ENABLED=true`;
2. the manifest contract and checkpoint integrity checks pass;
3. PyTorch is installed;
4. the checkpoint strictly loads and warms on the running backend.

Failure of the optional 168-hour artifact does not change 24-hour readiness.
Once a valid week artifact has been advertised, an unexpected inference failure
uses a labelled weekly seasonal-naive fallback based on the previous 168 hours.

## Limitations

- London-cohort metrics are not a guarantee for a particular client site.
- Client-site accuracy is unknown until enough actual outcomes are collected.
- Native quantiles are not recalibrated per site.
- Uncertainty generally increases deeper into the week.
- The forecast is energy information, not appliance detection or device control.
