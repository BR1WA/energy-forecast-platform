# Model Registry Architecture

This document describes the offline-to-online model promotion workflow implemented in `v0.3.0`.

## Directory Structure

All production models are stored in `backend/experiments/`.

```
backend/experiments/
    24h_patchtst/
        model.pt          # PyTorch weights (state_dict)
        pipeline.pkl      # Pickled FeaturePipeline with scaler
        config.yaml       # Architecture configuration
        metrics.json      # Offline benchmarking metrics and fingerprint
```

## How It Works

1. **Experiments are Immutable**: Once a model is imported or trained, it is stored in its own folder and should never be overwritten. New improvements create new experiment folders (e.g., `24h_patchtst_v2`).
2. **Database State**: The SQLite database `energy_forecast.db` stores the *state* of the registry (e.g., which model is currently `active=True`).
3. **Synchronization**: On startup, `forecast_service.py` scans `backend/experiments/` and registers any missing experiments in the database.
4. **Promotion**: Use `scripts/promote_model.py` to change the active model without editing code.

## Available Scripts

All scripts are located in the `scripts/` directory. Run them from the project root.

### `import_legacy_model.py`

Imports a legacy trained `.pth` model and `scaler.pkl` into the new registry format.

```bash
python scripts/import_legacy_model.py \
    --architecture PatchTST \
    --weights models/active/24h/patchtst_weights.pth \
    --scaler models/active/24h/scaler.pkl \
    --name 24h_patchtst
```

### `validate_registry.py`

Performs an offline compatibility check. It iterates over all experiments, resolves the architecture from `backend/app/ml/model_registry.py`, instantiates the PyTorch model, and loads the weights to verify there are no missing or unexpected keys.

```bash
python scripts/validate_registry.py
```

### `benchmark_models.py`

Runs all registered experiments against the 2010 test set and computes R2, MAE, RMSE, and latency.

```bash
python scripts/benchmark_models.py
```

### `promote_model.py`

Changes the active production model in the database.

```bash
python scripts/promote_model.py --name 24h_patchtst
```

## Adding New Architectures

To add a new architecture to the backend:

1. Add the PyTorch `nn.Module` to `backend/app/ml/architectures.py` (or import it if external).
2. Register it in `backend/app/ml/model_registry.py`:
   ```python
   MODEL_REGISTRY = {
       "PatchTST": PatchTST,
       "MyNewModel": MyNewModel,
   }
   ```
3. Your `config.yaml` should define exactly the kwargs expected by `MyNewModel.__init__`.
