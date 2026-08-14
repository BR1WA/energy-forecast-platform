# Serious 30-day forecasting experiment

## Outcome

The project now has a substantially stronger 30-day research candidate. It is
not a production model yet.

The best locked cold-start result forecasts 30 daily household totals with a
daily macro MAE of **2.5037 kWh**, a 30-day-total MAE of **38.7437 kWh**, and
central-80 daily interval coverage of **80.64%**. Relative to the strongest
mandatory weather/climatology baseline, this is a **7.19% daily improvement**
and a **9.59% monthly-total improvement**.

It passes four of the five promotion gates. Household-level macro R2 remains
negative at **-0.1337**, so the pipeline correctly leaves the backend and its
advertised forecast horizons unchanged.

## Data acquired and prepared

The experiment uses the official partitioned Low Carbon London smart-meter
release, not the earlier one-year derivative:

- 795,722,689-byte official ZIP, SHA-256
  `149a6a9c43c622fd0a14b7d11be055665317d3018d9fb7e1043bd51420bfaea5`;
- 4,438 source standard-tariff households;
- 1,653 households retained after an 80% daily-coverage gate;
- 828 energy days from 2011-11-23 through 2014-02-27;
- 1,322 known households and 331 fixed cold-start households;
- 168 compressed CSV partitions streamed directly without extracting the
  roughly 8.5 GB CSV corpus;
- exact duplicate household/timestamp rows removed;
- end-of-interval meter timestamps shifted by 30 minutes before energy-day
  assignment;
- daily targets accepted only with at least 46 of 48 half-hours, with 46-47
  interval days scaled to 48.

Historical London ERA5 weather was downloaded through Open-Meteo for 1991-2014.
The eight daily channels are mean/min/max temperature, mean apparent
temperature, precipitation, sunshine duration, maximum wind speed, and
shortwave radiation. Actual weather is available only before a forecast
origin. Every future day uses a 1991-2010 day-of-year climatology, so realized
target-period weather never leaks into a feature.

The prepared matrix and downloaded source files are intentionally ignored by
Git. Their URLs, byte sizes, hashes, quality policy, and split counts are
recorded in `models/lcl_global_forecasting/month_serious_v2/experiment_manifest.json`.

## Frozen protocol

- Lookback: 365 daily totals.
- Horizon: 30 daily totals and their coherent monthly sum.
- History eligibility: at least 95% observed and no gap longer than seven days.
- History gaps: interpolated causally within the available lookback.
- Target gaps: never imputed; incomplete 30-day targets are not scored.
- Training: weekly origins whose targets end before 2013-08-01.
- Validation: weekly origins from 2013-08-01 through 2013-10-31.
- Cold-start test: weekly origins from 2013-11-01 through 2014-01-29.
- Test cohort: 331 households excluded from London-specific model training.
- Promotion thresholds: fixed before test evaluation and never relaxed.

The full run produced 22,751 training windows, 17,902 validation windows,
16,167 known-household test windows, and 4,125 cold-start test windows. The
cold-start score covers 123,750 daily targets.

## Models evaluated

### London-trained ensemble

`training/month_serious.py` trains three-seed daily and monthly XGBoost
q10/q50/q90 residual ensembles plus three multiscale residual neural networks.
The point model has 87 features and the direct 30-day network/total head has
1,228 causal features. Validation selected 80% XGBoost and 20% neural weight,
then the models were refit on train plus validation.

The neural heads overfit quickly (best epochs 2-3), and the London-trained
ensemble reached 2.6463 kWh/day and 41.9223 kWh/month on cold-start households.

### Foundation-model challenges

The next locked candidates use Amazon checkpoints pinned by revision and
SHA-256:

- `amazon/chronos-bolt-small`, 47.7M parameters;
- `amazon/chronos-2`, 120M parameters.

Chronos-2 was evaluated both univariately and with the causal weather/calendar
contract above. Validation selected an equal blend of Chronos-2 univariate and
covariate forecasts, then blended its median 80% with the household-specific
weather/climatology ridge. Monthly-total reconciliation uses a separately
validated 70% foundation weight and 80% total-head weight. Horizon bias and
conformal interval adjustments were also frozen on validation.

## Cold-start leaderboard

All rows below use the same 331 households and 4,125 rolling windows.

| Candidate | Daily MAE | Daily bias | Daily macro R2 | Daily global R2 | 30-day MAE | Daily central-80 coverage |
|---|---:|---:|---:|---:|---:|---:|
| Chronos-2 causal ensemble | **2.5037** | -0.2953 | **-0.1337** | **0.7993** | **38.7437** | 80.64% |
| Chronos-Bolt-small ensemble | 2.5742 | -0.3737 | -0.1717 | 0.7919 | 39.8763 | 79.22% |
| London XGBoost/neural ensemble | 2.6463 | +0.3446 | -0.2292 | 0.7948 | 41.9223 | 78.79% |
| Weather/climatology ridge | 2.6975 | +0.0229 | -0.3360 | 0.7876 | 42.8538 | n/a |
| Four-week weekday mean | 2.8362 | not selected | -0.4098 | not selected | not selected | n/a |
| Last-week seasonal naive | 3.1245 | not selected | -0.8386 | not selected | not selected | n/a |

## Promotion decision

| Gate | Required | Chronos-2 result | Status |
|---|---:|---:|---|
| Daily MAE improvement | at least 5% | 7.19% | Pass |
| Monthly-total MAE improvement | at least 5% | 9.59% | Pass |
| Household daily macro R2 | at least 0 | -0.1337 | **Fail** |
| Absolute daily bias | at most 0.50 kWh | 0.2953 kWh | Pass |
| Central-80 daily coverage | 75-85% | 80.64% | Pass |

The negative macro R2 is not inconsistent with the strong global R2 of 0.7993.
Global R2 benefits from large consumption differences between households;
macro R2 asks whether the model explains each household's smaller day-to-day
variation, then weights every household equally. The remaining weakness is
therefore individual temporal dynamics, not population-scale level prediction.

Monthly intervals are also conservative: summing daily q10/q90 bounds yields
95.76% coverage rather than the nominal 80%. That interval is recorded but is
not used to claim monthly calibration.

## Reproduction

Install the pinned research dependencies after installing the appropriate
Torch build:

```powershell
python -m pip install -r training/requirements-month-serious.txt
```

Prepare the official archive and ERA5 inputs:

```powershell
python training/prepare_month_serious.py
```

Train the London ensemble and run the two foundation audits:

```powershell
python training/month_serious.py
python training/month_foundation.py
python training/month_foundation_chronos2.py
```

Exact frozen selection parameters are tracked in
`models/lcl_global_forecasting/month_serious_v2/foundation_selection.json`.
Large source data, third-party weights, and serialized research runs remain
outside Git. No file was copied to `backend/model_artifacts`.

## What would make the next attempt decisive

The official London release spans about 27 months, not a complete unseen final
year. A production-grade next round needs at least three complete years of the
project's target population, especially Moroccan households or organizations,
plus a truly untouched final year and operational 30-day weather forecasts.
The current Chronos-2 candidate is suitable as the benchmark and transfer
starting point for that data, but not as evidence of Moroccan production
performance.
