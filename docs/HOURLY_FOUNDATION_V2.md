# Hourly Foundation V2 Challengers

The same Chronos-2 plus LoRA process used for the successful month model was
applied to the 24-hour and 168-hour tasks. Both resulting adapters beat the
packaged Global TFTs under the frozen gate, but they are retained as
production-eligible challengers rather than deployed replacements in this
release because their operational cost is disproportionate to the measured
accuracy gain.

## Architecture and protocol

- Base: pinned `amazon/chronos-2` 120M revision
  `29ec3766d36d6f73f0696f85560a422f50e8498c`.
- Adaptation: separate rank-8 LoRA adapters for 24 and 168 hourly targets.
- Context: 672 hourly kWh values (28 days).
- Candidates: zero-shot, 100-update LoRA, and 300-update LoRA.
- Selection: 250 known Low Carbon London households and six chronological
  validation origins; the 300-update candidate won both horizons.
- Audit: 499 cold households and 24 chronological origins, opened only after
  `selection.json` was written.
- Comparators: the exact packaged TFT with production rolling normalization,
  previous-week repeat, previous-day repeat, and same-hour four-week median.
- Uncertainty: validation-only scale-normalized asymmetric conformal
  calibration of the Chronos p10/p90 outputs.

The architecture choice was informed by the official
[Chronos-2](https://github.com/amazon-science/chronos-forecasting) implementation,
[TimesFM 2.5](https://github.com/google-research/timesfm), and the official
[NeuralForecast](https://github.com/Nixtla/neuralforecast) implementations of
N-HiTS, TiDE, and PatchTST. Chronos-2 was selected for this controlled attempt
because it already won the month experiment, supports direct probabilistic
multi-step output, and reuses the base model required by the new month runtime.

## Locked cold-household results

| Metric | 24h TFT | 24h Chronos | 168h TFT | 168h Chronos |
|---|---:|---:|---:|---:|
| Macro MAE (kWh) | 0.18207 | **0.17679** | 0.19377 | **0.18870** |
| MAE improvement | — | **2.90%** | — | **2.62%** |
| Macro R² | 0.28470 | **0.29203** | 0.24433 | **0.24720** |
| Central-80 coverage | 81.01% | 79.72% | 78.20% | 78.41% |
| Households beating TFT | — | 79.96% | — | 80.96% |
| Evaluation windows | 11,789 | 11,789 | 11,751 | 11,751 |

Every frozen accuracy, calibration, finite-output, household-win, and FP32
reload gate passed. FP32 reload relative error was below `3e-7` for both
artifacts. The cold cohort was not accessed by this challenger pipeline until
selection was frozen, but it had been used by earlier incumbent experiments;
it is therefore not a pristine project-level holdout. London results also do
not establish Moroccan household efficacy.

## Operational decision

CPU warm inference is acceptable: 111 ms for 24 hours and 127 ms for 168 hours.
The first Chronos load increased process RSS by about 904 MB, and loading another
adapter in the same process added about 220 MB. Each challenger also doubles the
current input requirement from 336 to 672 hours.

The month model fills a missing product horizon, so its Chronos base-memory cost
is justified. Replacing both compact TFTs for a 2.6–2.9% London-cohort gain would
increase memory and readiness requirements without a Moroccan transfer gate.
The current application therefore keeps the TFTs deployed while preserving
both checksum-addressed Chronos adapters under
`models/lcl_global_forecasting/hourly_foundation_v2/release/`.

Deployment should be reconsidered after:

1. a shared-base multi-adapter loader avoids three independent Chronos copies;
2. the 672-hour API/readiness migration is verified across demo and real meters;
3. a container memory/start-up gate passes in the target cloud SKU; and
4. a geographically relevant hourly transfer audit passes.

## Reproduce

```powershell
python training/hourly_foundation_challenger.py select
python training/hourly_foundation_challenger.py audit
python training/hourly_foundation_challenger.py package
```

`training.hourly_foundation_inference.HourlyFoundationForecaster` verifies the
adapter and pinned base-model checksums, runs FP32 inference, clips negative
outputs, and applies the frozen conformal offsets.
