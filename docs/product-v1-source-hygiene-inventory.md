# Product V1 source-hygiene inventory

**Audit phase:** inventory, dependency verification, preservation, and Product V1 cleanup (Phases 1-6)
**Audit date:** 2026-07-23
**Starting branch:** `release/product-v1`
**Starting commit:** `ef95b50d845a7beaf65b0e96387514dac6416973`
**Cleanup branch:** `chore/product-v1-source-hygiene`
**Remote default branch:** `origin/main`

## Safety boundary

The 50 `RESEARCH_VALUABLE` artifacts were preserved in the owner-confirmed
private repository `BR1WA/PFE-research` at preservation commit `35f4eb3`.
Source/destination checksums matched 50/50, Git LFS verification passed, and a
clean-clone rehearsal restored all 50 files. Product V1 cleanup is limited to
the exact approved list; no history rewrite is performed.

## Repository state captured before the cleanup branch

`git status --short --untracked-files=all` captured the following state before
the branch was created. The modified and untracked files are preserved exactly
as found and are outside this audit's cleanup scope.

```text
 M app_status_audit.md
 M docs/PRODUCT_V1_G7_VALIDATION_EVIDENCE.md
 M docs/PRODUCT_V1_IMPLEMENTATION_LOG.md
 M docs/PRODUCT_V1_RELEASE_NOTES.md
?? docs/PFE_FULL_AUDIT_2026-07-22.md
?? docs/research/new paper/applsci-09-04237.pdf
?? docs/research/paper.pdf
?? models/ecl_deep_benchmark/leaderboard.csv
?? models/ecl_deep_benchmark/paper_comparison_metrics.csv
?? models/ecl_deep_benchmark/train_worker.py
?? models/lcl_global_forecasting/full_selected_v1/experiment_manifest.json
?? models/lcl_global_forecasting/full_selected_v1/leaderboard.csv
?? models/lcl_global_forecasting/full_selected_v1/production_candidates.json
?? models/lcl_global_forecasting/full_selected_v1/train_worker.py
?? notebooks/ecl-deep-models-dual-t4-benchmark.ipynb
?? notebooks/ecl_deep_models_dual_t4_benchmark.ipynb
?? notebooks/lcl-global-household-forecasting-full-selected-pro.ipynb
```

The cleanup branch was created only after confirming that
`chore/product-v1-source-hygiene` did not already exist. The branch currently
inherits this dirty-but-preserved working tree.

`git count-objects -vH` reported a repository size of approximately 1.10 GiB
of loose objects and 107.48 MiB of garbage objects across 9 garbage entries.
Those objects were not pruned or otherwise modified. The largest tracked files
include the 720-hour research checkpoint (68,520,663 bytes), three 24-hour
research checkpoints (14,399,342 bytes each), the two packaged Product V1
models (5,600,105 bytes each), and the active research weights.

## Classification rules

The required classifications are used exactly as follows:

- `RUNTIME_REQUIRED`: required by deployed application or inference pipeline;
  retain in the Product V1 tree.
- `RESEARCH_VALUABLE`: dataset, notebook, checkpoint, model output, or result
  worth preserving externally or in a separate research repository before any
  removal.
- `REGENERABLE`: generated output, fixture, cache, or export reproducible from
  tracked code and documented inputs.
- `UNKNOWN_REQUIRES_REVIEW`: purpose or dependency is uncertain; do not remove.

## Count reconciliation

The previous G7 source audit reported 26 legacy blockers. This audit found:

- 55 tracked files matching the requested artifact extensions.
- 53 non-runtime files among those extension matches.
- 1 additional non-extension research output: `models/archive/config.json`;
  `results/benchmark.md` is retained as an unknown benchmark output.
- 4 tracked packaged-artifact files under `backend/model_artifacts/`; their two
  `model.pt` files and two manifests are runtime-required and are not cleanup
  candidates.
- Therefore, 55 non-runtime research/data/output artifacts require disposition.
  The expected 26 are the legacy audit subset below; 27 additional model
  outputs under `models/active/` and `models/archive/`, plus the two additional
  non-extension outputs documented below, were not included in the earlier
  26-item count and are explicitly classified here.
- Final classification totals after preservation and reclassification are: 4
  `RUNTIME_REQUIRED`, 50 `RESEARCH_VALUABLE`, 0 `REGENERABLE`, and 5
  `UNKNOWN_REQUIRES_REVIEW` (59 audited files total; 55 non-runtime files).

The 26-item legacy subset is: 3 checkpoints, 3 data files, 1 archived result,
17 notebooks, 1 benchmark CSV, and 1 dummy export. The additional 27 are 10
active model/scaler files and 17 archived model files.

## Runtime artifacts retained

The deployed backend loads only the fixed packaged artifacts from
`backend/model_artifacts/`. `backend/app/services/product_forecast_service.py`
resolves this directory, reads each manifest, validates size and SHA-256, then
loads the manifest-declared checkpoint on CPU. `backend/Dockerfile` copies the
whole `backend/` tree into the runtime image. These four files are therefore
`RUNTIME_REQUIRED` and must remain.

| Path | Type | Size (bytes) | Tracked | Runtime purpose | Classification | Planned action / removal risk |
|---|---:|---:|---|---|---|---|
| `backend/model_artifacts/global_tft_24h/model.pt` | PyTorch checkpoint | 5,600,105 | yes | Fixed 24-hour forecast inference | `RUNTIME_REQUIRED` | Retain; removal breaks the default forecast and readiness warm-up. Phase 3 hash verification passed. |
| `backend/model_artifacts/global_tft_24h/manifest.json` | JSON manifest | 1,591 | yes | Contract, size, and SHA-256 metadata for 24-hour artifact | `RUNTIME_REQUIRED` | Retain with its checkpoint; removal disables integrity validation. |
| `backend/model_artifacts/global_tft_168h/model.pt` | PyTorch checkpoint | 5,600,105 | yes | Feature-gated 168-hour forecast inference | `RUNTIME_REQUIRED` | Retain; removal breaks the optional weekly capability. Phase 3 hash verification passed. |
| `backend/model_artifacts/global_tft_168h/manifest.json` | JSON manifest | 2,635 | yes | Contract, size, and SHA-256 metadata for 168-hour artifact | `RUNTIME_REQUIRED` | Retain with its checkpoint; removal disables integrity validation. |

## Expected 26 legacy research-related items

Every row below is tracked and is not referenced by the deployed Product V1
forecast loader. Dataset-provider and training references are research/training
paths, not application startup or request paths.

| Path | Type | Size (bytes) | Runtime reference | Classification | Planned action | Preservation / removal risk |
|---|---|---:|---|---|---|---|
| `checkpoints/24h_hybrid_v2_baseline_1782855695_best.pth` | PyTorch checkpoint | 14,399,342 | No; training baseline only | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of a dated baseline checkpoint and reproducibility evidence. |
| `checkpoints/24h_hybrid_v2_baseline_1782856150_best.pth` | PyTorch checkpoint | 14,399,342 | No; training baseline only | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of a dated baseline checkpoint and reproducibility evidence. |
| `checkpoints/24h_hybrid_v2_baseline_1782856368_best.pth` | PyTorch checkpoint | 14,399,342 | No; training baseline only | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of a dated baseline checkpoint and reproducibility evidence. |
| `data/app_test_samples.csv` | CSV generated sample | 150,209 | No direct runtime/test import found; generated by `scripts/generate_test_samples.py` | `UNKNOWN_REQUIRES_REVIEW` | Do not remove until the missing tracked configuration and authoritative raw-input retrieval are resolved | The raw household input exists only as a local ignored file; `models/config.json` is absent and no authoritative retrieval record is documented. |
| `data/clamart_weather_2006_2010.csv` | Raw weather dataset | 1,150,001 | Training validator/provider path only | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of the weather covariate source used by the IHEPC research pipeline. |
| `data/steel_industry_energy.csv` | Raw energy dataset | 2,305,961 | No deployed runtime reference found | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of a research dataset used by notebooks/legacy experiments. |
| `models/archive/results.csv` | CSV experiment result | 1,131 | No runtime reference | `UNKNOWN_REQUIRES_REVIEW` | Do not remove until an exact generator and complete inputs are identified | Its historical result purpose is clear, but no exact tracked generator or known reproducible inputs were found. |
| `notebooks/EECP_CBL_Replication.ipynb` | Jupyter notebook | 24,676 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of research method and recorded experiment context. |
| `notebooks/PatchTST_Forecasting.ipynb` | Jupyter notebook | 533,991 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of forecasting experiment and notebook outputs. |
| `notebooks/advanced_patchtst_kaggle.ipynb` | Jupyter notebook | 32,908 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of model comparison workflow. |
| `notebooks/cnnbilstm.ipynb` | Jupyter notebook | 247,469 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of baseline experiment workflow. |
| `notebooks/depm-on-steel-industry-energy-consumption.ipynb` | Jupyter notebook | 448,238 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of dataset-specific research analysis. |
| `notebooks/depm-variants.ipynb` | Jupyter notebook | 511,101 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of model-variant comparison context. |
| `notebooks/depm_final.ipynb` | Jupyter notebook | 769,300 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of final research experiment record. |
| `notebooks/depm_final_noleak.ipynb` | Jupyter notebook | 766,356 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of leakage-controlled experiment record. |
| `notebooks/depm_proposed.ipynb` | Jupyter notebook | 348,654 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of proposed-model research record. |
| `notebooks/fair_comparison.ipynb` | Jupyter notebook | 383,524 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of model fairness/comparison evidence. |
| `notebooks/hybrid_patch_forecasting.ipynb` | Jupyter notebook | 301,481 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of hybrid forecasting experiment. |
| `notebooks/presentation_evaluation.ipynb` | Jupyter notebook | 31,266 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of presentation evaluation source. |
| `notebooks/presentation_evaluation_out.ipynb` | Jupyter notebook | 238,829 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of generated presentation/evaluation record. |
| `notebooks/proper_regression_forecasting.ipynb` | Jupyter notebook | 7,601 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of regression experiment record. |
| `notebooks/sota-time-series-forecasting.ipynb` | Jupyter notebook | 330,990 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of SOTA comparison workflow. |
| `notebooks/state-of-the-art-long-term-time-series-forecasting.ipynb` | Jupyter notebook | 651,656 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of long-horizon research record. |
| `notebooks/weather_sota_forecasting.ipynb` | Jupyter notebook | 28,602 | No runtime reference | `RESEARCH_VALUABLE` | Preserve externally or in a separate research repository before removal | Loss of weather-aware forecasting research. |
| `results/benchmark.csv` | CSV generated benchmark | 1,943 | No runtime reference; generated by `scripts/collect_benchmarks.py` | `UNKNOWN_REQUIRES_REVIEW` | Retain; reclassify after source metrics are tracked and reproducible | Relevant source metrics are untracked, so regeneration is not currently durable. |
| `static/dummy_export.csv` | CSV demo export | 557 | No direct runtime reference found | `UNKNOWN_REQUIRES_REVIEW` | Do not remove until an exact fixture generator and inputs are identified | No exact generator, authoritative input, or runtime owner was found. |

## Additional model-output artifacts found by the expanded audit

These 27 files explain the difference between the historical 26-item report and
the full requested model-output inventory. They are loaded only by research
scripts or scratch evaluation code, not by `ProductForecastService` or the
runtime Docker image's packaged-artifact path.

| Path | Type | Size (bytes) | Runtime reference | Classification | Planned action | Preservation / removal risk |
|---|---|---:|---|---|---|---|
| `models/active/168h/advancedpatchtst_1_week_weights.pth` | PyTorch checkpoint | 7,668,196 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected weekly research model. |
| `models/active/168h/itransformer_1_week_weights.pth` | PyTorch checkpoint | 1,985,419 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected weekly research model. |
| `models/active/168h/scaler_1_week.pkl` | Pickled scaler | 584 | Research scripts only | `RESEARCH_VALUABLE` | Preserve with its model or regenerate from the same training pipeline | Incorrect scaling would invalidate reproduction if the model is kept. |
| `models/active/24h/cnn_bilstm_baseline.pth` | PyTorch checkpoint | 858,749 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected daily baseline model. |
| `models/active/24h/patchtst_weights.pth` | PyTorch checkpoint | 1,759,347 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected daily research model. |
| `models/active/24h/scaler.pkl` | Pickled scaler | 735 | Research scripts only | `RESEARCH_VALUABLE` | Preserve with its model or regenerate from the same training pipeline | Incorrect scaling would invalidate reproduction if the model is kept. |
| `models/active/24h/sota_model_weights.pth` | PyTorch checkpoint | 5,097,381 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected daily research model. |
| `models/active/720h/advancedpatchtst_1_month_weights.pth` | PyTorch checkpoint | 68,520,663 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected monthly research model. |
| `models/active/720h/itransformer_1_month_weights.pth` | PyTorch checkpoint | 2,749,249 | Research scripts only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of selected monthly research model. |
| `models/active/720h/scaler_1_month.pkl` | Pickled scaler | 584 | Research scripts only | `RESEARCH_VALUABLE` | Preserve with its model or regenerate from the same training pipeline | Incorrect scaling would invalidate reproduction if the model is kept. |
| `models/archive/depm_bigru_dl.pt` | PyTorch model output | 1,725,023 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_bigru_xgb.pkl` | Pickled model output | 3,394,605 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_bilstm_dl.pt` | PyTorch model output | 2,254,444 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_bilstm_xgb.pkl` | Pickled model output | 3,362,303 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_dnn_dl.pt` | PyTorch model output | 239,193 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_dnn_xgb.pkl` | Pickled model output | 3,194,129 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_gru_dl.pt` | PyTorch model output | 667,973 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_gru_xgb.pkl` | Pickled model output | 3,376,446 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_lstm_dl.pt` | PyTorch model output | 867,154 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/depm_lstm_xgb.pkl` | Pickled model output | 3,343,322 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived DEPM model output. |
| `models/archive/pca.pkl` | Pickled preprocessing output | 2,567 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve with the archived model family or regenerate | Loss of preprocessing state needed to reproduce archived results. |
| `models/archive/resnet.pt` | PyTorch model output | 587,161 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived model output. |
| `models/archive/standalone_bigru.pt` | PyTorch model output | 1,725,062 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived model output. |
| `models/archive/standalone_bilstm.pt` | PyTorch model output | 2,254,483 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived model output. |
| `models/archive/standalone_dnn.pt` | PyTorch model output | 239,301 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived model output. |
| `models/archive/standalone_gru.pt` | PyTorch model output | 668,012 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived model output. |
| `models/archive/standalone_lstm.pt` | PyTorch model output | 867,193 | Archive/scratch only | `RESEARCH_VALUABLE` | Preserve externally/separately before removal | Loss of archived model output. |

## Additional non-extension research outputs

| Path | Type | Size (bytes) | Runtime reference | Classification | Planned action | Preservation / removal risk |
|---|---|---:|---|---|---|---|
| `models/archive/config.json` | JSON research configuration | 256 | No deployed runtime reference | `RESEARCH_VALUABLE` | Preserve with the archived model family before removal | Loss of threshold/features needed to interpret archived outputs. |
| `results/benchmark.md` | Markdown generated report | 2,591 | No runtime reference; generated by `scripts/collect_benchmarks.py` | `UNKNOWN_REQUIRES_REVIEW` | Retain; reclassify after source metrics are tracked and reproducible | Relevant source metrics are untracked, so regeneration is not currently durable. |

## Dependency observations for the next phase

Read-only inspection found the following boundaries:

- `backend/app/services/product_forecast_service.py` loads only
  `backend/model_artifacts/{global_tft_24h,global_tft_168h}` and validates each
  manifest's declared size and SHA-256 before CPU inference.
- `backend/Dockerfile` copies `backend/` into the runtime image; repository-root
  `models/`, `data/`, `checkpoints/`, `notebooks/`, `results/`, and `training/`
  are not copied into the backend runtime image.
- `models/active/` is referenced by `scripts/build_notebook.py` and
  `scratch/evaluate_active_models.py`, both research tooling.
- `data/clamart_weather_2006_2010.csv` is referenced by the training-side
  IHEPC provider; the deployed forecast service consumes persisted application
  readings instead.
- `data/app_test_samples.csv` is written by `scripts/generate_test_samples.py`
  and has no direct runtime import found in tracked code.
- `results/benchmark.csv` and `results/benchmark.md` are generated by
  `scripts/collect_benchmarks.py`, but their relevant source metrics are
  untracked; both are therefore retained as `UNKNOWN_REQUIRES_REVIEW`.

Phase 3 dependency tracing, deployment inspection, runtime hashing, and model
loading verification are recorded in the sections below. Phase 4 preservation
is complete and the exact 50-file Product V1 cleanup is recorded in
`docs/PRODUCT_V1_SOURCE_HYGIENE_COMPLETION.md`.

## Preservation gate

`SATISFIED`: `BR1WA/PFE-research` is owner-confirmed private at commit
`35f4eb3`. All 50 source and destination SHA-256 hashes matched, Git LFS
verification passed, and a clean-clone rehearsal restored all 50 files.

## Phase 3A: dependency-trace findings

The read-only trace is now complete for the four retained packaged-artifact
files.

### Runtime path and selection

- `backend/app/services/product_forecast_service.py` is the only runtime loader.
  It sets `ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "model_artifacts"`.
  The root is fixed relative to the installed backend package; it is not read
  from an environment variable or database setting.
- The 24-hour `ForecastArtifactSpec` is `global_tft_24h`, is always enabled, and
  resolves to `backend/model_artifacts/global_tft_24h/`.
- The 168-hour `ForecastArtifactSpec` is `global_tft_168h`, resolves to
  `backend/model_artifacts/global_tft_168h/`, and is selected only when the
  `FORECAST_168H_ENABLED` feature flag is enabled.
- For each horizon, `_load_manifest()` reads the manifest-declared
  `checkpoint_file`, checks its exact byte size, computes SHA-256, and compares
  it with `checkpoint_sha256`. `_load_model()` then loads that checkpoint on
  CPU, constructs `app.ml.global_tft.GlobalTFT` from manifest architecture
  metadata, and performs a strict state-dict load.
- Runtime routers (`forecast`, `system`, and `admin`) call the service for
  readiness, capabilities, forecast inference, and packaged-artifact status;
  they do not resolve any other model directory.

### Deployment and test boundaries

- `backend/Dockerfile` copies only `backend/` into the application image. The
  runtime image therefore includes `backend/model_artifacts/` but does not
  include repository-root `models/`, `data/`, `checkpoints/`, `notebooks/`,
  `results/`, or `training/` artifacts.
- `docker-compose.yml` builds the backend from `backend/Dockerfile` and mounts
  only the durable avatar volume. It does not mount research directories.
- CI builds the same backend Dockerfile and runs the model-contract tests; no
  workflow references `models/active/` or `models/archive/` for serving.
- `backend/tests/test_model_contract.py` uses the two packaged artifact
  directories directly and validates their manifests, hashes, contracts, and
  CPU inference. It does not depend on any research artifact.
- `scripts/measure_g6_performance.py` and `scripts/verify_g6_restore.py` use
  persisted forecast metadata; they do not load research weights.

### Non-runtime references

No runtime code path references `models/active/`, `models/archive/`,
`data/`, `notebooks/`, or `results/`. The references found are bounded as
follows:

| Location | Reference kind | Impact if removed |
|---|---|---|
| `scripts/build_notebook.py` | Research notebook builder reads selected `models/active` weights and writes a notebook | That research script would need its optional model inputs or an explicit missing-input path; no application impact. |
| `scratch/evaluate_active_models.py` and `scratch/sota_*` | Scratch evaluation reads `data/household_power_consumption.txt` and selected active weights | Scratch evaluation would not run; no application impact. |
| `training/*`, `scripts/validate_datasets.py`, `backend/app/ml/datasets/*` | Training-side dataset providers and validators reference dataset paths | Training/validation workflows need external datasets; no deployed inference impact. |
| `scripts/generate_test_samples.py` | Generates `data/app_test_samples.csv` from an ignored raw input and tracked config | The sample can be regenerated when the external input exists; no runtime import found. |
| `scripts/collect_benchmarks.py` | Generates `results/benchmark.csv`, `results/benchmark.md`, and an ignored JSON report from experiment metrics | Benchmark reports disappear but the collector can recreate them from experiment metrics. |
| `docs/PRODUCT_AUDIT_2026-07-19.md` and presentation documents | Documentation-only references to old experiment/model/notebook paths | Documentation links and claims must be updated in a later cleanup commit; no runtime impact. |
| `docs/PRODUCT_V1_*` | Release evidence records the pre-existing source-audit finding | The evidence should be updated only after approved cleanup and rerun validation. |

The old `docs/PRODUCT_AUDIT_2026-07-19.md` statement about an experiment
registry is historical audit material and does not describe the current
`ProductForecastService` path. It is documentation-only, not evidence of a
runtime dependency.

### Removal impact

All 55 non-runtime candidates have been exact-path and filename searched. The
candidate matrix above records their individual status. The conservative
impact conclusion is:

- The 3 checkpoints, 2 raw research datasets, 17 notebooks, 10 active model
  outputs, 17 archived model outputs, and archived model config are the 50
  `RESEARCH_VALUABLE` research/training files. Removal would affect research
  reproducibility and requires approved external preservation first.
- `results/benchmark.csv` and `results/benchmark.md` are retained as
  `UNKNOWN_REQUIRES_REVIEW`: their relevant source metrics are untracked even
  though `scripts/collect_benchmarks.py` is known.
- `data/app_test_samples.csv`, `models/archive/results.csv`, and
  `static/dummy_export.csv` are `UNKNOWN_REQUIRES_REVIEW`. They have no safe
  removal path until their inputs/generators are established.
- No candidate removal would alter Docker startup, migrations, API imports,
  frontend builds, model readiness, or production forecast inference.

The Phase 3 corrective review changed three classifications from
`REGENERABLE` to `UNKNOWN_REQUIRES_REVIEW`; Phase 5B changed both benchmark
outputs for the same source-integrity reason. All five unknown files remain
untouched and cannot be removed.

## Phase 3B: runtime artifact integrity

Both retained checkpoints were read without modification. Manifest filename,
size, and SHA-256 comparisons all passed.

| Horizon | Artifact | Manifest version | Task | Lookback / horizon | Input -> output | Declared bytes | Actual bytes | SHA-256 | Result |
|---:|---|---|---|---:|---|---:|---:|---|---|
| 24h | `backend/model_artifacts/global_tft_24h/model.pt` | 1.0.0 | `day_24h` | 336 / 24 | kWh per hour -> kWh per hour | 5,600,105 | 5,600,105 | `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d` | Match |
| 168h | `backend/model_artifacts/global_tft_168h/model.pt` | 1.0.0 | `week_168h` | 336 / 168 | kWh per hour -> kWh per hour | 5,600,105 | 5,600,105 | `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93` | Match |

Both manifests declare quantiles `[0.1, 0.5, 0.9]`. The 168-hour manifest
declares `app.ml.global_tft.GlobalTFT`, hidden size 128, four attention heads,
dropout 0.1, 186 state-dict tensors, and 1,386,262 trainable parameters. The
24-hour manifest uses the same fixed contract and does not require a separate
runtime architecture override.

## Phase 3C: model-loading smoke tests

The existing non-mutating smoke coverage passed:

```text
python -m pytest -q backend/tests/test_model_contract.py
10 passed in 13.86s
```

The application loading path was also exercised directly with both capability
horizons enabled:

```text
python -c "from app.services.product_forecast_service import ProductForecastService; s=ProductForecastService(forecast_168h_enabled=True); print('24h', s.warmup(24)); print('168h', s.warmup(168))"
24h: available=True, warmed=True, name=global_tft_24h, version=1.0.0
168h: available=True, warmed=True, name=global_tft_168h, version=1.0.0
```

Both checkpoints deserialized on CPU, passed strict model loading, and returned
the expected horizon-specific artifact fingerprints. The local process emitted
an existing DEBUG-only warning about the development admin-password placeholder;
no secret value was printed. No external data or service was needed for this
model-loading smoke test.

## Phase 3D: regeneration instructions

These are planning instructions only. They were not run because the commands
would write generated files and the phase is read-only.

| Artifact | Generator | Required inputs | Expected output | Verification status |
|---|---|---|---|---|
| `data/app_test_samples.csv` | `python scripts/generate_test_samples.py` | Local ignored `data/household_power_consumption.txt` exists, but tracked `models/config.json` is absent and no authoritative retrieval source is documented | `data/app_test_samples.csv` | Reclassified `UNKNOWN_REQUIRES_REVIEW`; command is known but reproducible inputs are not sufficiently available. Not executed. |
| `models/archive/results.csv` | No exact tracked generator found; historical archive result format only | Unknown legacy experiment inputs | `models/archive/results.csv` | Reclassified `UNKNOWN_REQUIRES_REVIEW`; not verified and removal blocked. |
| `results/benchmark.csv` | `python scripts/collect_benchmarks.py` | 18 local `experiments/**/metrics.json` files exist, but they are untracked; 15 match the collector's expected layout | `results/benchmark.csv` | `UNKNOWN_REQUIRES_REVIEW`; retain until source metrics are tracked and reproducible. Not executed. |
| `results/benchmark.md` | `python scripts/collect_benchmarks.py` | Same untracked metric inputs as the CSV | `results/benchmark.md` | `UNKNOWN_REQUIRES_REVIEW`; retain until source metrics are tracked and reproducible. Not executed. |
| `static/dummy_export.csv` | No exact tracked generator found; no runtime reference found | Unknown demo-fixture inputs | `static/dummy_export.csv` | Reclassified `UNKNOWN_REQUIRES_REVIEW`; not verified and removal blocked. |

## Preservation checksum manifest (planning metadata only)

The following 50 `RESEARCH_VALUABLE` files were hashed in place. These checksums
are not evidence of external preservation and no copies were made.

| Path | Size (bytes) | SHA-256 | Group |
|---|---:|---|---|
| `checkpoints/24h_hybrid_v2_baseline_1782855695_best.pth` | 14,399,342 | `bdb0e6a6ca5a6b20e8cef6538d82f4d19126ede9c01c7d943cd1ef953c2f96bb` | research-checkpoints |
| `checkpoints/24h_hybrid_v2_baseline_1782856150_best.pth` | 14,399,342 | `168f3f9c2c6212c9fb8aa23e7ca5c510609083fab9e3b48b69d22b6524c7eea0` | research-checkpoints |
| `checkpoints/24h_hybrid_v2_baseline_1782856368_best.pth` | 14,399,342 | `2797d97218e824469a3babe21988627ccf9f926e6926faf6a5f0bb582f195caf` | research-checkpoints |
| `data/clamart_weather_2006_2010.csv` | 1,150,001 | `bc82f61b04690112a48a3bac3bea1ac8ea1bdf4365f21ca706aa4b5e6d0dabe9` | research-data |
| `data/steel_industry_energy.csv` | 2,305,961 | `8ba505bd12e85add8f620a2206b87f96a9667089cc3b6f7153526445f76724ee` | research-data |
| `notebooks/EECP_CBL_Replication.ipynb` | 24,676 | `84d14c22dc03cf80f2965615fcc3e69c4bfa8e23203ad30c74a3563f2c6f72e1` | research-notebooks |
| `notebooks/PatchTST_Forecasting.ipynb` | 533,991 | `e408c12ffc331377123410cfae1901fb6ef935d10f62f80ffc51880bc1c78e97` | research-notebooks |
| `notebooks/advanced_patchtst_kaggle.ipynb` | 32,908 | `c27c38920c6670d8bdc7ff9af9c87ab0702a1136a3cc4f8f1bdd8dad2714b188` | research-notebooks |
| `notebooks/cnnbilstm.ipynb` | 247,469 | `12958ed90a674b64acfc2f825741e4a4f177b7b7eba3c9a091a0abce5824161b` | research-notebooks |
| `notebooks/depm-on-steel-industry-energy-consumption.ipynb` | 448,238 | `3044dddcc59a0f268bac67e093634046fdb74a6dd274ef804d7643980685e9ec` | research-notebooks |
| `notebooks/depm-variants.ipynb` | 511,101 | `fadb72b7899ddf9d8c8daf612ee5a141efdc3f7b5ac49a6a64e778c9041074c4` | research-notebooks |
| `notebooks/depm_final.ipynb` | 769,300 | `e6483c07b18a446dd09e64a99a22707a94a83b133de10dc7775b404cb01c2589` | research-notebooks |
| `notebooks/depm_final_noleak.ipynb` | 766,356 | `d097f493a79e76040af6ad0d90833886963354706ef3d2e2f72eebd5751ba41e` | research-notebooks |
| `notebooks/depm_proposed.ipynb` | 348,654 | `85217ca3ad4df275d7edcfc0e5d4070fe6fb8e2be86f13e8921ac729c1a2aff1` | research-notebooks |
| `notebooks/fair_comparison.ipynb` | 383,524 | `922e0aef17ca821ae8cb9244fd725104c19cdd1c9af0288767eb0eda458e75a6` | research-notebooks |
| `notebooks/hybrid_patch_forecasting.ipynb` | 301,481 | `a8633319a26a788efd065eef4d0d961be459c17123130acb1ed0aaf8ada39985` | research-notebooks |
| `notebooks/presentation_evaluation.ipynb` | 31,266 | `be44b4401fba4992bf007cff7474313bb1411e2eca03a80f375aa94a865a8e2a` | research-notebooks |
| `notebooks/presentation_evaluation_out.ipynb` | 238,829 | `ec6d3a3f0819eec9eb4f4a6fa18eadaa5df8cb4ead6cbc1fd89d6c85143e0eeb` | research-notebooks |
| `notebooks/proper_regression_forecasting.ipynb` | 7,601 | `5d7745ef434bb6341e58c29f0acf583d5433bedc141eb902aeabd3b9acaf992e` | research-notebooks |
| `notebooks/sota-time-series-forecasting.ipynb` | 330,990 | `2de3c3f4d96338b20bf32ed4eb15be345a2d9956604f7a5657b96655ed62f510` | research-notebooks |
| `notebooks/state-of-the-art-long-term-time-series-forecasting.ipynb` | 651,656 | `1f97ccd1a0e70ceefd7a105cdbb4a8c9b9f39fb7dc632d76c8839a2f625030f6` | research-notebooks |
| `notebooks/weather_sota_forecasting.ipynb` | 28,602 | `658d28fc5a4c5480de1946cb90893596c58056d670a70a188f5ea4c1f4a46eb9` | research-notebooks |
| `models/active/168h/advancedpatchtst_1_week_weights.pth` | 7,668,196 | `106a43f50835df1d7427d7fa5dd9233a9703a1d8f6156455b81e440804ced45a` | research-active-models |
| `models/active/168h/itransformer_1_week_weights.pth` | 1,985,419 | `83ce15b28a208b51c573f91276d108753c0c746d8543eb48489701ce1a7f0aae` | research-active-models |
| `models/active/168h/scaler_1_week.pkl` | 584 | `04977ef88cc8e295bdc5892547fae735bf077a10ec8789368f560e09eae07e1b` | research-active-models |
| `models/active/24h/cnn_bilstm_baseline.pth` | 858,749 | `26155dd2c84e6a52ae4d51d6d166b7f1c92755fa214e1a33db4fb8e5e90df350` | research-active-models |
| `models/active/24h/patchtst_weights.pth` | 1,759,347 | `cc6751e521d6f945038b5bde57ad915736f28a03d6abb33bcbc511acd15ba6d7` | research-active-models |
| `models/active/24h/scaler.pkl` | 735 | `3c3884c81bb8d94b27860026aafafb3da7de2fcf94ffcdce688d21145aed5a9e` | research-active-models |
| `models/active/24h/sota_model_weights.pth` | 5,097,381 | `6947d687c43b48c929a2ebf085af4d746d3eeb54d69b851cfac83cb1455a6d23` | research-active-models |
| `models/active/720h/advancedpatchtst_1_month_weights.pth` | 68,520,663 | `c2ac13827dc5ab87250fa8371669b4c7f9f4e4fd654b7765ff8ae145d5d5a7b3` | research-active-models |
| `models/active/720h/itransformer_1_month_weights.pth` | 2,749,249 | `b4c39673dc6816fe9a2a227afddd65632d7acd6d066e08c5934e23e06190a8c6` | research-active-models |
| `models/active/720h/scaler_1_month.pkl` | 584 | `04977ef88cc8e295bdc5892547fae735bf077a10ec8789368f560e09eae07e1b` | research-active-models |
| `models/archive/config.json` | 256 | `235cbb2c7087883328785270ce57ddb1154f6ca2a63b5a76a1025b9dbdf4ae97` | research-archive |
| `models/archive/depm_bigru_dl.pt` | 1,725,023 | `ddf91dc44084eaa7dab7df48b095f10d35f40f07a2279959f239ce60fa551a7c` | research-archive |
| `models/archive/depm_bigru_xgb.pkl` | 3,394,605 | `02b9cf8da47b5adc0c1268fe283537fb966aad587ed78f115c76a067b5a55246` | research-archive |
| `models/archive/depm_bilstm_dl.pt` | 2,254,444 | `229991f10aa2adf05ee8a2c23e14d938efe5593b92ae79755450c076e1ed3877` | research-archive |
| `models/archive/depm_bilstm_xgb.pkl` | 3,362,303 | `2854586f8205070040892afefde2c1afe1a8377f575a82962dd96c54d261d7d8` | research-archive |
| `models/archive/depm_dnn_dl.pt` | 239,193 | `25d7f9e8fd2c3837efd2c8ce6c6b06f23fd4e92dbf3c959f5215e4dd737c8595` | research-archive |
| `models/archive/depm_dnn_xgb.pkl` | 3,194,129 | `63c26503cebac9f3954531cbcb008833c53a8d3d3847b8680116c035ecdfc8d7` | research-archive |
| `models/archive/depm_gru_dl.pt` | 667,973 | `100fd31d470f31a35fc3964ee4b146711947fc2edbe4946d181b17c3ae835659` | research-archive |
| `models/archive/depm_gru_xgb.pkl` | 3,376,446 | `c53e21e39a466458f6a05e7949517c4ed5679ec817e3d5e0acda3b6d98c00e7c` | research-archive |
| `models/archive/depm_lstm_dl.pt` | 867,154 | `b203490aeb22039d81981f2715c0aaf7d4453cf7f61b5301ceb66d0db17b79b3` | research-archive |
| `models/archive/depm_lstm_xgb.pkl` | 3,343,322 | `261508b2415c054b7665d0dd6b4f14818a2300eefb5c8a64ecd2ca3a7054b963` | research-archive |
| `models/archive/pca.pkl` | 2,567 | `2bf1b2e9e840fdaefe7aa6d9dc306fdf0aaee80e9270ecbd2eea9d05580f978f` | research-archive |
| `models/archive/resnet.pt` | 587,161 | `6935b179c2f8251ad29cb1e3969e663b63d436630b515e208b07136a88c4d2c9` | research-archive |
| `models/archive/standalone_bigru.pt` | 1,725,062 | `a3e226ea2041435134e404d891c0bfee11559d448610d58747439fbcaf7c86b4` | research-archive |
| `models/archive/standalone_bilstm.pt` | 2,254,483 | `bad822f065039916e3e10628822c7b0b9fcc8b487a1e5122333d581e2d83d378` | research-archive |
| `models/archive/standalone_dnn.pt` | 239,301 | `97c370abe681de024055a35eed5f855e7a5f1e7288be0f673871d9adffb42852` | research-archive |
| `models/archive/standalone_gru.pt` | 668,012 | `2c091a82b6c30928144ede4f522a80342c442f50fdf447d9398f7a1ebd57d9dc` | research-archive |
| `models/archive/standalone_lstm.pt` | 867,193 | `d680a55d69ba2b0d81cd2f1d93eab45d3795ab57461e647fb03be2c2256546d1` | research-archive |

The preservation manifest is complete for the 50 `RESEARCH_VALUABLE` rows and
was verified against the private research repository, Git LFS, and a clean
clone. The preservation gate is `SATISFIED`.

## Phase 3 integrity result and cleanup handoff

The runtime dependency trace, manifest comparisons, hashes, and CPU loading
smoke tests passed. No runtime-required artifact outside
`backend/model_artifacts/` was discovered. Current hashes prove the identity of
files in this checkout only; external preservation is now proven by the
private research repository, 50/50 checksum match, Git LFS verification, and
clean-clone rehearsal. The exact 50 preserved research paths are removed from
Product V1; runtime artifacts and all five unknown files remain in place.
Historical Git objects are not rewritten or pruned, so repository size will not
shrink fully until unreachable objects age out or a separately approved history
rewrite occurs.
