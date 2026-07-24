# Product V1 source-hygiene completion

## Scope and preservation

This record documents the Product V1 source-hygiene cleanup on
`chore/product-v1-source-hygiene`. The audit baseline is
`ef95b50d845a7beaf65b0e96387514dac6416973` and the verified pre-cleanup audit
checkpoint is `9ca06137780f5507b6105c0ad6b314f0a5ab55c1`.

The preservation gate is `SATISFIED`. The 50 research artifacts listed below
were preserved in the owner-confirmed private repository
`BR1WA/PFE-research` at commit `35f4eb3`. Source and destination SHA-256
verification matched 50/50, Git LFS verification passed, and a clean-clone
rehearsal restored all 50 files. No credentials or private authentication
details are recorded here.

## Classification outcome

Final audited totals are:

- `RUNTIME_REQUIRED`: 4
- `RESEARCH_VALUABLE`: 50 (preserved externally and removed from Product V1)
- `REGENERABLE`: 0
- `UNKNOWN_REQUIRES_REVIEW`: 5 (retained)

The retained unknown files are:

- `data/app_test_samples.csv`
- `models/archive/results.csv`
- `static/dummy_export.csv`
- `results/benchmark.csv`
- `results/benchmark.md`

The two benchmark outputs were reclassified because their relevant source
metrics are untracked. They require later review before any removal.

## Runtime artifacts retained

Product V1 inference loads only packaged artifacts below through
`backend/app/services/product_forecast_service.py`. The service validates each
manifest's declared size and SHA-256, loads the selected checkpoint on CPU,
and performs strict model loading. Repository-root research directories are
not runtime model sources.

| Horizon | File | Bytes | SHA-256 |
|---|---|---:|---|
| 24h | `backend/model_artifacts/global_tft_24h/model.pt` | 5,600,105 | `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d` |
| 24h | `backend/model_artifacts/global_tft_24h/manifest.json` | 1,591 | Manifest contract retained |
| 168h | `backend/model_artifacts/global_tft_168h/model.pt` | 5,600,105 | `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93` |
| 168h | `backend/model_artifacts/global_tft_168h/manifest.json` | 2,635 | Manifest contract retained |

## Exact preserved files removed from Product V1

The cleanup removes only these 50 explicitly verified paths:

### Checkpoints and datasets

- `checkpoints/24h_hybrid_v2_baseline_1782855695_best.pth`
- `checkpoints/24h_hybrid_v2_baseline_1782856150_best.pth`
- `checkpoints/24h_hybrid_v2_baseline_1782856368_best.pth`
- `data/clamart_weather_2006_2010.csv`
- `data/steel_industry_energy.csv`

### Research notebooks

- `notebooks/EECP_CBL_Replication.ipynb`
- `notebooks/PatchTST_Forecasting.ipynb`
- `notebooks/advanced_patchtst_kaggle.ipynb`
- `notebooks/cnnbilstm.ipynb`
- `notebooks/depm-on-steel-industry-energy-consumption.ipynb`
- `notebooks/depm-variants.ipynb`
- `notebooks/depm_final.ipynb`
- `notebooks/depm_final_noleak.ipynb`
- `notebooks/depm_proposed.ipynb`
- `notebooks/fair_comparison.ipynb`
- `notebooks/hybrid_patch_forecasting.ipynb`
- `notebooks/presentation_evaluation.ipynb`
- `notebooks/presentation_evaluation_out.ipynb`
- `notebooks/proper_regression_forecasting.ipynb`
- `notebooks/sota-time-series-forecasting.ipynb`
- `notebooks/state-of-the-art-long-term-time-series-forecasting.ipynb`
- `notebooks/weather_sota_forecasting.ipynb`

### Active research models

- `models/active/168h/advancedpatchtst_1_week_weights.pth`
- `models/active/168h/itransformer_1_week_weights.pth`
- `models/active/168h/scaler_1_week.pkl`
- `models/active/24h/cnn_bilstm_baseline.pth`
- `models/active/24h/patchtst_weights.pth`
- `models/active/24h/scaler.pkl`
- `models/active/24h/sota_model_weights.pth`
- `models/active/720h/advancedpatchtst_1_month_weights.pth`
- `models/active/720h/itransformer_1_month_weights.pth`
- `models/active/720h/scaler_1_month.pkl`

### Archived research models and configuration

- `models/archive/config.json`
- `models/archive/depm_bigru_dl.pt`
- `models/archive/depm_bigru_xgb.pkl`
- `models/archive/depm_bilstm_dl.pt`
- `models/archive/depm_bilstm_xgb.pkl`
- `models/archive/depm_dnn_dl.pt`
- `models/archive/depm_dnn_xgb.pkl`
- `models/archive/depm_gru_dl.pt`
- `models/archive/depm_gru_xgb.pkl`
- `models/archive/depm_lstm_dl.pt`
- `models/archive/depm_lstm_xgb.pkl`
- `models/archive/pca.pkl`
- `models/archive/resnet.pt`
- `models/archive/standalone_bigru.pt`
- `models/archive/standalone_bilstm.pt`
- `models/archive/standalone_dnn.pt`
- `models/archive/standalone_gru.pt`
- `models/archive/standalone_lstm.pt`

## Future artifact handling

Research datasets, notebooks, checkpoints, experiment outputs, and training
weights belong in the private research repository or another explicitly
approved preservation destination. Product V1 should retain only packaged
runtime artifacts and required application source. The focused `.gitignore`
rules protect common research locations and binary extensions while leaving
`backend/model_artifacts/**` available to Git and explicitly retaining the
five unknown files.

Runtime integrity can be checked against the two manifest files with SHA-256
and the model-contract test:

```text
python -m pytest -q backend/tests/test_model_contract.py
```

No Git history was rewritten, pruned, rebased, or force-pushed. Removing files
from the current tree does not immediately shrink the repository's complete
historical storage; unreachable historical objects age out only through normal
repository maintenance, or through a separately approved history rewrite.
