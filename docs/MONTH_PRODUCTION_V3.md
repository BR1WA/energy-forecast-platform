# Month Production V3

`month_production_v3` is the first production-eligible 30-day model release in
this repository. It is a Chronos-2 120M foundation model adapted with rank-8
LoRA for 600 updates on known Portugal electricity clients and known Morocco
load zones. It outputs daily p10/p50/p90 forecasts from 365 historical daily
values and accepts a causal minimum of 270 days.

## Why this architecture

The experiment compared the official N-HiTS and TiDE implementations with
zero-shot Chronos-2 and three Chronos-2 LoRA schedules (100, 300, 600 updates).
N-HiTS contributes hierarchical multirate interpolation; TiDE contributes a
dense long-horizon encoder/decoder; Chronos-2 contributes pretrained global
time-series representations and parameter-efficient adaptation. Selection used
a normalized Portugal-Morocco objective, and the 600-update LoRA won narrowly.

No realized future weather enters the model. This avoids a common offline
leakage pattern where actual target-period weather is available in evaluation
but not at forecast time.

The architecture survey covered [Chronos-2 and its official LoRA training
path](https://github.com/amazon-science/chronos-forecasting),
[TimesFM 2.5](https://github.com/google-research/timesfm),
[N-HiTS](https://arxiv.org/abs/2201.12886),
[TiDE](https://arxiv.org/abs/2304.08424), and
[PatchTST](https://arxiv.org/abs/2211.14730). N-HiTS and TiDE were promoted
from the survey into the actual controlled experiment through the official
[NeuralForecast](https://github.com/Nixtla/neuralforecast) implementations;
Chronos-2 LoRA won the frozen cross-dataset selection objective.

## Evidence

Architecture, blend weight, LoRA schedule, and conformal calibration were
selected on development series. UCI Tetouan was identified, protocol-frozen,
then downloaded and used only as a fresh geographic transfer gate. Across nine
non-overlapping 30-day Tetouan windows:

| Metric | Seasonal baseline | Candidate |
|---|---:|---:|
| Macro MASE | 5.910 | 1.095 |
| Daily macro R² | -8.792 | 0.450 |
| Daily MAE | 4,215.55 | 866.75 |
| 30-day-total MAE | 124,079.39 | 16,118.69 |
| Central-80 coverage | — | 88.15% |

The scale-free point error improved 81.47%, and every frozen fresh-transfer and
artifact gate passed. On the secondary Portugal cold-client diagnostic, daily
MAE improved 34.04% and 30-day-total MAE improved 28.48%. A southern-Morocco
held-out-zone diagnostic did not improve point accuracy, so rollout to that
meter population must be monitored and locally recalibrated.

As a stricter post-gate robustness check, the candidate was also compared with
the best of every declared causal seasonal baseline on Tetouan. The strongest
was the repeated-last-28-days baseline (MASE 2.182); the model remained 49.82%
better at MASE 1.095. This check did not influence selection or loosen a gate.

The official data sources were UCI
[ElectricityLoadDiagrams20112014](https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014),
[High-Resolution Load Dataset from Smart Meters Across Various Cities in
Morocco](https://archive-beta.ics.uci.edu/dataset/1158/high-resolution%2Bload%2Bdataset%2Bfrom%2Bsmart%2Bmeters%2Bacross%2Bvarious%2Bcities%2Bin%2Bmorocco),
and the fresh [Power Consumption of Tetouan
City](https://archive.ics.uci.edu/dataset/849/power%2Bconsumption%2B) transfer
gate. All source archives are checksum-pinned in the preparation manifest or
protocol.

“Fresh” here means unseen by this project’s training, selection, blending,
calibration, and refit stages. Chronos-2 is an upstream foundation model, so
independent proof that its broad pretraining corpus never included a public
Tetouan record is not available; the audit should therefore be read as a strong
geographic transfer result, not a formal proof of zero upstream exposure.

## Reproduce

Use Python 3.11 and install `training/requirements-month-production.txt`.

```powershell
python training/prepare_month_production.py
python training/month_production.py select --output models/lcl_global_forecasting/month_production_v3/runs/production_v2
python training/month_production.py audit --output models/lcl_global_forecasting/month_production_v3/runs/production_v2
```

Load the release through `training.month_production_inference.MonthProductionForecaster`.
The wrapper verifies the adapter SHA-256, loads the pinned base through
Chronos-2, runs FP32 inference, clips negative outputs, and applies the frozen
scale-normalized asymmetric conformal correction.

On the development machine, FP32 CPU cold load took 9.04 seconds and median
warm inference for one 30-day series took 76.8 ms across three repetitions.

## Deployment boundary

The artifact is deployed in the application as an independently gated 30-day
daily capability. The persistence layer retains `720` as the duration identifier,
while the API explicitly returns `target_count=30`,
`target_interval_hours=24`, and `resolution="daily"`; it is never represented as
a 720-step hourly model. Readiness requires at least 270 complete rolling daily
blocks within the 365-day context and does not offer the short demo-history
shortcut as a bypass.

The container build installs the pinned Chronos dependencies, copies the exact
adapter, downloads and checksum-verifies the pinned base revision at build time,
and serves locally cached weights at request time. Operators expose the
capability with `FORECAST_30D_ENABLED=true` only after its warm-up succeeds.
