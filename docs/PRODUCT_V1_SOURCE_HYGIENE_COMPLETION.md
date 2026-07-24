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

## Validation record

- `python -m pytest -q backend/tests`: 92 passed, 4 expected skips.
- `python -m pytest -q backend/tests/test_model_contract.py`: 10 passed.
- Fresh SQLite Alembic upgrade reached `c8f4a1b2d306` (head).
- Both runtime checkpoints matched their manifest hashes and warmed on CPU
  with strict loading for 24h and 168h.
- Frontend lint, TypeScript checking, and production build passed.
- The complete six-project Playwright matrix passed 66/66 with one worker.
  A parallel run had three WebKit engine allocation failures; the
  single-worker rerun passed all WebKit projects.
- `pip-audit -r backend/requirements.txt` reported no known vulnerabilities.
- Docker-backed Gitleaks history scanning passed on the remediation commit
  (`0ee4477`): 287 commits scanned and no leaks found.
- Docker-backed Gitleaks directory scanning passed on a fresh clean checkout
  of the remediation commit; no committed tracked path triggered a finding.
  The restore-verification fixture key is now derived from a non-secret
  deterministic value with an optional environment override, and the tracked
  investigation text retains its research meaning with AWS-shaped substrings
  redacted in place. No suspected credential was copied to the research
  repository.
- Cleanup repository secret validation: `PASSED`.
- Product release security validation remains `BLOCKED` by the two high
  production dependency advisories documented below; this cleanup did not
  change dependencies.
- `docker compose config --quiet` passed. Docker engine/build/liveness checks
  were recorded separately in the Product V1 G7 evidence.
- `npm audit --omit=dev --audit-level=high` reports two high PostCSS advisories
  inherited through Next.js; fixing them requires a breaking dependency
  upgrade and was intentionally outside this source-hygiene cleanup.

## Reference audit and outcome

Remaining references to removed research paths in `docs/` are historical or
preservation records. References in `scripts/build_notebook.py`,
`scratch/evaluate_active_models.py`, and presentation planning documents are
research tooling/documentation that now requires the private research
repository; none is a Product V1 runtime dependency. No broken runtime
reference was found and no unrelated source file was changed.

	The cleanup commits are local and the branch was not pushed. The
pre-existing dirty files and 13 pre-existing untracked files were unchanged,
unstaged, and uncommitted.
