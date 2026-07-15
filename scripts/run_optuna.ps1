$ErrorActionPreference = 'Stop'
Write-Host "Running XGBoost Optimization (100 trials)..."
python training/tune.py --dataset ihepc --model xgboost --n-trials 100
if ($LASTEXITCODE -ne 0) { throw "XGBoost tuning failed" }

Write-Host "Running PatchTST Optimization (30 trials)..."
python training/tune.py --dataset ihepc --model patchtst --n-trials 30
if ($LASTEXITCODE -ne 0) { throw "PatchTST tuning failed" }

Write-Host "Re-collecting benchmarks..."
python scripts/collect_benchmarks.py --dataset ihepc --horizon 24

Write-Host "Done!"
