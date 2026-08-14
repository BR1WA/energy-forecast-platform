# Strong 30-day forecasting experiment

## Outcome

A stronger monthly research pipeline was implemented and trained, but it was
not promoted into the EnergyAI production service. The selected candidate
improves cold-start daily MAE over the strongest causal baseline, has bounded
bias, and produces a well-calibrated central-80% interval. It still misses the
predeclared daily and monthly-total improvement thresholds and retains negative
household-level macro R2.

This is a scientific no-promotion decision, not a failed training run.

## Forecasting design

The experiment predicts 30 daily energy totals from the preceding 90 daily
totals. Daily resolution was selected instead of a direct 720-hour output
because the product use case is monthly budget planning and the available
one-year household history is insufficient to support reliable intraday detail
at every hour of a month.

The implementation in `training/month_strong.py` includes:

- per-origin rolling normalization, with no household identity or scaler learned
  from the test household;
- residual prediction over a trailing four-week weekday profile;
- 12 causal weekly lags, recent-window statistics, robust trend summaries,
  future calendar features, and scale features;
- XGBoost q10/q50/q90 residual models for each future day and the 30-day total;
- optional squared-error center heads evaluated as a separate ablation;
- validation-only location and conformal interval calibration;
- coherent reconciliation between the 30 daily medians and monthly total;
- deterministic origins and seeds, with no wall-clock-dependent sampling;
- explicit promotion gates that prevent a weak checkpoint from entering the
  backend artifact directory.

After validation selected the design and tree counts, the candidate was refit
on every pre-test train-plus-validation target. The final chronological test
region and all cold-start household identities remained excluded from fitting.

## Frozen cold-start results

The final cohort contains 487 households and 11,580 rolling windows.

| Model | Daily macro MAE | Daily macro bias | Daily macro R2 | Global R2 | 30-day-total MAE | Central-80 coverage |
|---|---:|---:|---:|---:|---:|---:|
| Selected quantile-residual refit | **2.6908 kWh/day** | -0.4357 | -0.4923 | 0.7432 | 48.0871 kWh | 78.65% |
| MSE-center ablation | 2.7216 kWh/day | **-0.2364** | -7.9136 | **0.7460** | **46.8560 kWh** | 79.04% |
| Damped four-week trend | 2.8261 kWh/day | -0.9611 | -0.4152 | 0.7281 | 48.8525 kWh | n/a |
| Previous MultiCycleNet experiment | 2.8408 kWh/day | -1.4191 | -0.6078 | 0.7178 | not originally reported | n/a |
| Last-week seasonal naive | 3.1046 kWh/day | -0.7333 | -0.7859 | 0.6972 | 49.9602 kWh | n/a |

The selected candidate improves daily MAE by 4.79% and monthly-total MAE by
1.57% over the damped-trend baseline. The MSE-center ablation improves the
monthly total by 4.09%, but worsens daily MAE and produces unstable
household-level R2. Combining heads using weights favored only by the test set
was explicitly rejected.

## Promotion decision

The thresholds were declared in code before the final run:

| Gate | Required | Selected result | Status |
|---|---:|---:|---|
| Daily MAE improvement | at least 5% | 4.79% | Fail |
| Monthly-total MAE improvement | at least 5% | 1.57% | Fail |
| Household daily macro R2 | at least 0 | -0.4923 | Fail |
| Absolute daily bias | at most 0.50 kWh | 0.4357 kWh | Pass |
| Central-80 daily coverage | 75–85% | 78.65% | Pass |

No files were added to `backend/model_artifacts`, no API horizon was changed,
and the product continues to advertise only its validated 24-hour and 168-hour
artifacts.

## What is required for a deployable month model

The main bottleneck is now data rather than model size. The frozen cohort has
only one calendar year, while a 30-day forecast needs repeated annual seasons
and unusual-event examples. The next credible training round should use at
least two or three years per household or organization, include Moroccan
temperature and calendar effects, preserve a truly unseen final year, and
repeat the finalist over multiple seeds. Until then, the application should
retain its existing coverage-gated monthly budget estimate instead of labeling
this checkpoint as a production forecast.

Exact machine-readable results are in
`models/lcl_global_forecasting/month_strong_v1/experiment_manifest.json` and
`leaderboard.csv`. Large run artifacts remain intentionally ignored by Git.
