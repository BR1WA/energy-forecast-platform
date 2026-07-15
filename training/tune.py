"""
training/tune.py — Optuna Hyperparameter Optimization entrypoint.

Usage
-----
  python training/tune.py --dataset ihepc --model xgboost --n-trials 100
  python training/tune.py --dataset ihepc --model patchtst --n-trials 30
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import random
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import optuna
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from training.baselines import get_model, list_models
from training.splitters.chronological import ChronologicalSplitter
from training.utils.metrics import calculate_metrics
from backend.app.ml.datasets import get_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Make optuna quiet
optuna.logging.set_verbosity(optuna.logging.WARNING)

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass

def get_search_space(trial: optuna.Trial, model_name: str) -> dict:
    if model_name == "xgboost":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 50, 400, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 7),
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma": trial.suggest_float("gamma", 1e-8, 1.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }
    elif model_name == "patchtst":
        d_model = trial.suggest_categorical("d_model", [16, 32, 64, 128])
        # User requested ff_dim = 4 * d_model, handled automatically in patchtst wrapper or here
        return {
            "patch_length": trial.suggest_categorical("patch_length", [8, 16, 24]),
            "stride": trial.suggest_categorical("stride", [4, 8, 12]),
            "d_model": d_model,
            "d_ff": d_model * 4,
            "num_heads": trial.suggest_categorical("num_heads", [4, 8, 16]),
            "encoder_layers": trial.suggest_int("encoder_layers", 2, 6),
            "dropout": trial.suggest_float("dropout", 0.0, 0.3),
            "lr": trial.suggest_float("lr", 1e-4, 5e-3, log=True),
            "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [32, 64, 128]),
        }
    else:
        raise ValueError(f"Tuning not implemented for {model_name}")

def _generate_artifacts(study: optuna.Study, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save best params
    with open(out_dir / "best_params.yaml", "w") as f:
        yaml.dump(study.best_params, f, default_flow_style=False)
        
    # Save trials dataframe
    df = study.trials_dataframe()
    df.to_csv(out_dir / "trials.csv", index=False)
    
    # Visualizations
    from optuna.visualization.matplotlib import plot_optimization_history, plot_param_importances, plot_parallel_coordinate, plot_slice, plot_contour
    
    try:
        fig = plot_optimization_history(study)
        fig.figure.savefig(out_dir / "optimization_history.png", dpi=150, bbox_inches="tight")
        plt.close(fig.figure)
        
        fig = plot_param_importances(study)
        fig.figure.savefig(out_dir / "parameter_importance.png", dpi=150, bbox_inches="tight")
        plt.close(fig.figure)
        
        fig = plot_parallel_coordinate(study)
        fig.figure.savefig(out_dir / "parallel_coordinate.png", dpi=150, bbox_inches="tight")
        plt.close(fig.figure)
        
        fig = plot_slice(study)
        fig.figure.savefig(out_dir / "slice.png", dpi=150, bbox_inches="tight")
        plt.close(fig.figure)
        
        fig = plot_contour(study)
        fig.figure.savefig(out_dir / "contour.png", dpi=150, bbox_inches="tight")
        plt.close(fig.figure)
    except Exception as e:
        log.warning(f"Could not generate all Optuna plots: {e}")

def run(args):
    set_seed(args.seed)
    log.info(f"=== Tuning: dataset={args.dataset}, model={args.model}, horizon={args.horizon} ===")
    
    # Load and prep data
    provider = get_dataset(args.dataset, "data")
    df_raw = provider.load()
    df_clean = provider.preprocess(df_raw)
    df_features = provider.create_features(df_clean)
    meta = provider.get_metadata()
    target_cols = [meta["targets"][0]]
    freq = meta["frequency"]
    
    splitter = ChronologicalSplitter(train_ratio=0.7, val_ratio=0.1)
    train_df, val_df, _ = splitter.split(df_features) # Test set is strictly held out
    
    from training.features.feature_engineering import FeaturePipeline
    pipeline = FeaturePipeline(time_col="Datetime", target_cols=target_cols)
    pipeline.fit(train_df, freq=freq)
    train_scaled = pipeline.transform(train_df, freq=freq)
    val_scaled   = pipeline.transform(val_df,   freq=freq)
    
    from training.train import make_windows
    X_train, Y_train, _ = make_windows(train_scaled, target_cols, args.lookback, args.horizon)
    X_val,   Y_val,   _ = make_windows(val_scaled,   target_cols, args.lookback, args.horizon)

    n_features = X_train.shape[2]
    n_targets = Y_train.shape[2]
    
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    study_name = f"{args.dataset}_{args.model}_{ts}"
    out_dir = PROJECT_ROOT / "experiments" / args.dataset / f"lookback{args.lookback}" / f"horizon{args.horizon}" / args.model / "tuning" / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    
    def objective(trial: optuna.Trial):
        set_seed(args.seed + trial.number) # Varies slightly per trial but deterministic
        params = get_search_space(trial, args.model)
        
        model_kwargs = params.copy()
        if args.model == "xgboost":
            from optuna.integration import XGBoostPruningCallback
            model_kwargs["callbacks"] = [XGBoostPruningCallback(trial, "validation_0-rmse")]
            
        try:
            model = get_model(
                args.model, 
                exp_dir=None, # no need to save disk artifacts per trial for XGBoost
                trial=trial,
                **model_kwargs
            )
            model.fit(X_train, Y_train, X_val, Y_val)
            
            # Evaluate strictly on validation set
            Y_pred_scaled = model.predict(X_val)
            
            Y_val_inv = pipeline.inverse_transform_targets(
                Y_val.reshape(-1, n_targets)
            ).reshape(len(Y_val), args.horizon, n_targets)
            
            Y_pred_inv = pipeline.inverse_transform_targets(
                Y_pred_scaled.reshape(-1, n_targets)
            ).reshape(len(Y_pred_scaled), args.horizon, n_targets)
            
            metrics = calculate_metrics(Y_val_inv, Y_pred_inv)
            
            # Print intermediate progress
            if trial.number % 5 == 0:
                log.info(f"Trial {trial.number}/{args.n_trials} complete - Val MAE: {metrics['mae']:.4f}")
                
            return metrics["mae"] # Minimize MAE
            
        except optuna.exceptions.TrialPruned:
            raise
        except Exception as e:
            log.warning(f"Trial {trial.number} failed with exception: {e}")
            raise optuna.exceptions.TrialPruned()

    sampler = optuna.samplers.TPESampler(seed=args.seed)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5)
    
    # Sqlite backend for persistence
    db_path = out_dir / "study.db"
    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        storage=f"sqlite:///{db_path}"
    )
    
    log.info(f"Starting {args.n_trials} trials...")
    study.optimize(objective, n_trials=args.n_trials)
    
    log.info(f"Best trial: {study.best_trial.number}")
    log.info(f"Best Val MAE: {study.best_value:.4f}")
    log.info(f"Best params: {study.best_params}")
    
    _generate_artifacts(study, out_dir)
    log.info(f"Tuning artifacts saved to {out_dir}")
    
    # Automatically retrain with best parameters
    import subprocess
    log.info("\n=== Starting Automated Retraining with Best Parameters ===")
    cmd = [
        "python", "training/train.py",
        "--dataset", args.dataset,
        "--model", args.model,
        "--tag", "tuned",
        "--horizon", str(args.horizon),
        "--lookback", str(args.lookback),
        "--seed", str(args.seed)
    ]
    for k, v in study.best_params.items():
        cmd.extend([f"--{k}", str(v)])
        
    log.info(f"Command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    log.info("=== Automated Retraining Complete ===")

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--lookback", type=int, default=96)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()

if __name__ == "__main__":
    run(_parse_args())
