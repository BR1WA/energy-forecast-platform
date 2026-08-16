"""
training/train.py — Unified training entrypoint for all forecasting models.

Usage
-----
  python training/train.py --dataset ihepc --model persistence --horizon 24
  python training/train.py --dataset ihepc --model xgboost     --horizon 168 --lookback 96 --seed 42
  python training/train.py --dataset ecl   --model random_forest --horizon 24

Every model — baseline or deep learning — runs through this same pipeline.
That ensures any performance differences are attributable to the model,
not to differences in preprocessing, splitting, or evaluation.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Path setup so this can be run from the project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from training.baselines import get_model, list_models
from training.splitters.chronological import ChronologicalSplitter
from training.utils.metrics import calculate_metrics, measure_inference_time, model_size_mb
from backend.app.ml.datasets import get_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def load_real_data(filepath: str | Path, limit_rows: int | None = None) -> pd.DataFrame:
    """Load and hourly-resample the UCI household power dataset.

    This compatibility helper remains the canonical loader for the metric
    recomputation utility; the main training CLI uses the dataset registry.
    """
    data = pd.read_csv(filepath, sep=";", na_values=["?"], nrows=limit_rows)
    required = {"Date", "Time", "Global_active_power"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    data["timestamp"] = pd.to_datetime(
        data["Date"] + " " + data["Time"],
        format="%d/%m/%Y %H:%M:%S",
        errors="raise",
    )
    data["gap"] = pd.to_numeric(data["Global_active_power"], errors="coerce")
    return (
        data[["timestamp", "gap"]]
        .set_index("timestamp")
        .resample("1h")
        .mean()
        .reset_index()
    )


def prepare_tensors(
    data: pd.DataFrame,
    time_col: str,
    target_col: str,
    lookback: int,
    horizon: int,
):
    """Create legacy deep-model tensors without making Torch a CLI import dependency."""
    import torch

    if lookback <= 0 or horizon <= 0:
        raise ValueError("lookback and horizon must both be positive")
    required = {time_col, target_col}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Processed data is missing required columns: {sorted(missing)}")

    features = data.drop(columns=[time_col, target_col]).to_numpy(dtype=np.float32)
    targets = data[target_col].to_numpy(dtype=np.float32)
    window_count = len(data) - lookback - horizon + 1
    if window_count <= 0:
        raise ValueError(
            f"Dataset needs at least {lookback + horizon} rows; got {len(data)}"
        )

    x_values = np.stack(
        [targets[index : index + lookback] for index in range(window_count)]
    )
    y_values = np.stack(
        [
            targets[index + lookback : index + lookback + horizon]
            for index in range(window_count)
        ]
    )
    temporal_values = np.stack(
        [features[index : index + lookback] for index in range(window_count)]
    )
    return (
        torch.from_numpy(x_values).unsqueeze(-1),
        torch.from_numpy(y_values).unsqueeze(-1),
        torch.from_numpy(temporal_values),
    )


# ---------------------------------------------------------------------------
# Window generation
# ---------------------------------------------------------------------------

def make_windows(
    data: pd.DataFrame,
    target_cols: list,
    lookback: int,
    horizon: int,
    step: int = 1,
):
    """
    Slide a window over `data` to produce (X, Y, timestamps) arrays.

    Parameters
    ----------
    data        : scaled DataFrame, must be sorted chronologically
    target_cols : column names used for Y (targets)
    lookback    : encoder length (input steps)
    horizon     : decoder length (output steps)
    step        : slide step (1 = dense, horizon = non-overlapping)

    Returns
    -------
    X          : (n_windows, lookback, n_features)  — all columns
    Y          : (n_windows, horizon, n_targets)    — target columns only
    timestamps : list of pd.Timestamp — start of each Y window
    """
    feature_cols = [c for c in data.columns if c != "Datetime"]
    values = data[feature_cols].values.astype(np.float32)
    target_idx = [feature_cols.index(c) for c in target_cols]

    X_list, Y_list, ts_list = [], [], []
    n = len(values)
    for i in range(0, n - lookback - horizon + 1, step):
        X_list.append(values[i : i + lookback])
        Y_list.append(values[i + lookback : i + lookback + horizon][:, target_idx])
        if "Datetime" in data.columns:
            ts_list.append(data["Datetime"].iloc[i + lookback])

    if not X_list:
        raise ValueError(
            f"Dataset too small to generate any windows "
            f"(need >= {lookback + horizon} rows, got {n})."
        )

    return (
        np.stack(X_list).astype(np.float32),
        np.stack(Y_list).astype(np.float32),
        ts_list,
    )


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------

def _build_exp_dir(
    base: Path, dataset: str, lookback: int, horizon: int, model_name: str
) -> Path:
    """experiments/<dataset>/lookback<N>/horizon<N>/<model>/<timestamp>/"""
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = base / dataset / f"lookback{lookback}" / f"horizon{horizon}" / model_name / ts
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_config(path: Path, args, meta: dict, n_features: int, n_targets: int) -> None:
    cfg = {
        "experiment": {
            "dataset":    args.dataset,
            "model":      args.model,
            "lookback":   args.lookback,
            "horizon":    args.horizon,
            "seed":       args.seed,
        },
        "data": {
            "n_features": n_features,
            "n_targets":  n_targets,
        },
    }
    cfg["experiment"].update(meta.get("experiment_meta", {}))
    with open(path / "config.yaml", "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)


def _save_metrics(path: Path, metrics: dict, timing: dict) -> None:
    payload = {**metrics, **timing}
    with open(path / "metrics.json", "w") as f:
        json.dump(payload, f, indent=2)


def _save_predictions(
    path: Path,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    timestamps: list,
    target_cols: list,
    split: str = "test",
) -> None:
    """
    Save predictions with rich metadata columns.

    Columns: timestamp, target, prediction, split, window_id
    """
    rows = []
    n_windows, horizon, n_targets = y_true.shape
    for w in range(n_windows):
        for h in range(horizon):
            for t_idx, col in enumerate(target_cols):
                rows.append({
                    "window_id":  w,
                    "horizon_step": h,
                    "target":     col,
                    "timestamp":  timestamps[w] if timestamps else None,
                    "y_true":     float(y_true[w, h, t_idx]),
                    "y_pred":     float(y_pred[w, h, t_idx]),
                    "split":      split,
                })
    pd.DataFrame(rows).to_csv(path / "predictions.csv", index=False)


def _save_feature_importance(
    path: Path,
    model,
    feature_names: list,
    lookback: int,
) -> None:
    """Save feature_importance.csv and top20_features.png."""
    importances = model.get_feature_importance(feature_names)
    if importances is None:
        return

    # For flat models: importances has shape (lookback * n_features,)
    # We expand names to (feature, lag) pairs
    if len(importances) == lookback * len(feature_names):
        rows = []
        for lag in range(lookback):
            for feat in feature_names:
                rows.append({"feature": feat, "lag": lag})
        imp_df = pd.DataFrame(rows)
        imp_df["importance"] = importances
    else:
        imp_df = pd.DataFrame({
            "feature": feature_names[:len(importances)],
            "importance": importances,
        })

    imp_df = imp_df.sort_values("importance", ascending=False)
    imp_df.to_csv(path / "feature_importance.csv", index=False)

    # Bar chart of top 20
    top20 = imp_df.head(20)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top20["feature"].astype(str) + " (lag " + top20["lag"].astype(str) + ")"
            if "lag" in top20.columns else top20["feature"].astype(str),
            top20["importance"], color="#4C9BE8")
    ax.invert_yaxis()
    ax.set_xlabel("Feature Importance")
    ax.set_title("Top 20 Most Important Features")
    plt.tight_layout()
    fig.savefig(path / "top20_features.png", dpi=150)
    plt.close(fig)
    log.info("Saved feature importance chart.")


def _save_forecast_plot(
    path: Path,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    target_cols: list,
    n_windows: int = 5,
) -> None:
    """Save a multi-panel forecast plot for the first `n_windows` windows."""
    n_show = min(n_windows, len(y_true))
    n_targets = len(target_cols)
    fig, axes = plt.subplots(n_show, n_targets, figsize=(6 * n_targets, 3 * n_show), squeeze=False)

    for w in range(n_show):
        for t, col in enumerate(target_cols):
            ax = axes[w][t]
            ax.plot(y_true[w, :, t], label="Actual", color="#333")
            ax.plot(y_pred[w, :, t], label="Predicted", color="#E84C4C", linestyle="--")
            ax.set_title(f"Window {w} — {col}")
            ax.legend(fontsize=8)

    plt.suptitle("Forecast vs Actual (Test Set)", fontsize=14)
    plt.tight_layout()
    fig.savefig(path / "plots.png", dpi=150)
    plt.close(fig)
    log.info("Saved forecast plots.")


def _save_metadata(path: Path, args, exp_dir: Path, timing: dict) -> None:
    import subprocess
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        git_commit = "unknown"

    environment = {
        "python": sys.version,
        "torch": None,
        "transformers": None,
        "cuda_available": False,
        "device_name": "CPU"
    }
    try:
        import torch
        environment["torch"] = torch.__version__
        environment["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            environment["device_name"] = torch.cuda.get_device_name(0)
        import transformers
        environment["transformers"] = transformers.__version__
    except ImportError:
        pass

    meta = {
        "experiment": {
            "dataset": args.dataset,
            "model":   args.model,
            "horizon": args.horizon,
            "lookback": args.lookback,
            "seed":    args.seed,
            "device":  args.device,
        },
        "reproducibility": {
            "git_commit":       git_commit,
            "python_version":   sys.version,
            "created_at":       datetime.now(timezone.utc).isoformat(),
            "output_directory": str(exp_dir),
            "environment":      environment,
        },
        "timing": timing,
    }
    with open(path / "metadata.yaml", "w") as f:
        yaml.dump(meta, f, default_flow_style=False)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace, kwargs: dict) -> None:
    np.random.seed(args.seed)
    log.info(f"=== Training: dataset={args.dataset}, model={args.model}, "
             f"lookback={args.lookback}, horizon={args.horizon} ===")
    if kwargs:
        log.info(f"   Hyperparameters: {kwargs}")

    # 1. Load & preprocess dataset
    log.info("[1/7] Loading dataset...")
    provider = get_dataset(args.dataset, args.data_dir)
    df_raw = provider.load()
    df_clean = provider.preprocess(df_raw)
    df_features = provider.create_features(df_clean)
    meta = provider.get_metadata()
    # Option A: Benchmark ONLY the primary target (e.g. Global_active_power) for EVERY model.
    # This ensures an apples-to-apples comparison across all architectures.
    target_cols = [meta["targets"][0]]
    log.info(f"   Target: predicting '{target_cols[0]}' only")
    freq = meta["frequency"]

    # 2. Chronological split
    log.info("[2/7] Splitting data chronologically...")
    splitter = ChronologicalSplitter(train_ratio=0.7, val_ratio=0.1)
    train_df, val_df, test_df = splitter.split(df_features)

    # 3. Scale — fit ONLY on train
    log.info("[3/7] Fitting scaler on training data only...")
    from training.features.feature_engineering import FeaturePipeline
    pipeline = FeaturePipeline(time_col="Datetime", target_cols=target_cols)
    pipeline.fit(train_df, freq=freq)
    train_scaled = pipeline.transform(train_df, freq=freq)
    val_scaled   = pipeline.transform(val_df,   freq=freq)
    test_scaled  = pipeline.transform(test_df,  freq=freq)

    feature_cols = [c for c in train_scaled.columns if c != "Datetime"]

    # 4. Window generation
    log.info("[4/7] Generating sliding windows...")
    X_train, Y_train, _  = make_windows(train_scaled, target_cols, args.lookback, args.horizon)
    X_val,   Y_val,   _  = make_windows(val_scaled,   target_cols, args.lookback, args.horizon)
    X_test,  Y_test,  ts_test = make_windows(test_scaled, target_cols, args.lookback, args.horizon)

    log.info(f"   Train: {X_train.shape} → {Y_train.shape}")
    log.info(f"   Val:   {X_val.shape}   → {Y_val.shape}")
    log.info(f"   Test:  {X_test.shape}  → {Y_test.shape}")

    # 5. Create experiment dir and Instantiate model
    log.info("[5/7] Fitting model...")
    base_dir = PROJECT_ROOT / "experiments"
    model_dir_name = f"{args.model}_{args.tag}" if args.tag else args.model
    exp_dir = _build_exp_dir(
        base_dir, args.dataset, args.lookback, args.horizon, model_dir_name
    )
    model = get_model(args.model, exp_dir=str(exp_dir), **kwargs)
    set_seed(args.seed)

    t0_fit = time.perf_counter()
    model.fit(X_train, Y_train, X_val, Y_val)
    fit_time_s = time.perf_counter() - t0_fit
    log.info(f"   Fit time: {fit_time_s:.2f}s")

    # 6. Predict + evaluate
    log.info("[6/7] Evaluating on test set...")
    Y_pred = model.predict(X_test)

    # Inverse-transform predictions and targets to real-world scale
    n_windows_test = len(Y_test)
    Y_test_inv = pipeline.inverse_transform_targets(
        Y_test.reshape(-1, len(target_cols))
    ).reshape(n_windows_test, args.horizon, len(target_cols))
    
    Y_pred_inv = pipeline.inverse_transform_targets(
        Y_pred.reshape(-1, len(target_cols))
    ).reshape(n_windows_test, args.horizon, len(target_cols))

    metrics = calculate_metrics(Y_test_inv, Y_pred_inv)
    inf_time_ms = measure_inference_time(model, X_test[:50])

    # Model artifact size
    import tempfile, pickle
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        tmp_path = tmp.name
    model.save(tmp_path)
    size_mb = model_size_mb(tmp_path)
    os.unlink(tmp_path)

    timing = {
        "fit_time_s":         round(fit_time_s, 3),
        "inference_ms_per_sample": round(inf_time_ms, 4),
        "model_size_mb":      round(size_mb, 3) if size_mb else None,
    }

    log.info("Metrics (unscaled):")
    for k, v in {**metrics, **timing}.items():
        log.info(f"   {k:30s}: {v}")

    # 7. Save artifacts
    log.info("[7/7] Saving artifacts...")

    _save_config(exp_dir, args, {"experiment_meta": {}},
                 n_features=len(feature_cols), n_targets=len(target_cols))
    _save_metrics(exp_dir, metrics, timing)
    _save_predictions(exp_dir, Y_test_inv, Y_pred_inv, ts_test, target_cols)
    _save_metadata(exp_dir, args, exp_dir, timing)
    model.save(exp_dir / "model.pkl")

    if model.supports_feature_importance:
        _save_feature_importance(exp_dir, model, feature_cols, args.lookback)

    _save_forecast_plot(exp_dir, Y_test_inv, Y_pred_inv, target_cols[:1])

    log.info(f"\nArtifacts saved to: {exp_dir}")
    log.info("=== Run complete ===")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> tuple[argparse.Namespace, dict]:
    parser = argparse.ArgumentParser(
        description="Unified forecast model training entrypoint."
    )
    parser.add_argument("--dataset",  required=True, help="Dataset name (ihepc, ecl, ...)")
    parser.add_argument("--model",    required=True, help=f"Model name. Available: {list_models()}")
    parser.add_argument("--tag",      default="",    help="Optional tag to distinguish experiments")
    parser.add_argument("--horizon",  type=int, default=24,  help="Forecast horizon in hours")
    parser.add_argument("--lookback", type=int, default=96,  help="Encoder / lookback window")
    parser.add_argument("--seed",     type=int, default=42,  help="Global random seed")
    parser.add_argument("--device",   default="cpu",         help="Compute device (cpu / cuda)")
    parser.add_argument("--data-dir", dest="data_dir", default="data", help="Path to data files")
    
    args, unknown = parser.parse_known_args()
    
    kwargs = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith("--"):
            key = unknown[i].lstrip("-")
            if i + 1 < len(unknown) and not unknown[i+1].startswith("--"):
                val = unknown[i+1]
                # Try to parse to int or float if possible
                try:
                    if '.' in val or 'e' in val.lower():
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass
                kwargs[key] = val
                i += 2
            else:
                kwargs[key] = True
                i += 1
        else:
            i += 1
            
    return args, kwargs


if __name__ == "__main__":
    args, kwargs = _parse_args()
    run(args, kwargs)
