import argparse
import os
import shutil
import json
import yaml
import hashlib
import joblib
import pickle

def calculate_sha256(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def import_model(architecture: str, weights_path: str, scaler_path: str, name: str, horizon: int = 24):
    experiments_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "experiments")
    os.makedirs(experiments_dir, exist_ok=True)
    
    target_dir = os.path.join(experiments_dir, name)
    if os.path.exists(target_dir):
        print(f"Warning: Directory {target_dir} already exists. Overwriting contents.")
    os.makedirs(target_dir, exist_ok=True)

    target_weights = os.path.join(target_dir, "model.pt")
    target_scaler = os.path.join(target_dir, "pipeline.pkl")
    
    shutil.copy2(weights_path, target_weights)
    
    # Wrap scaler into FeaturePipeline dict format
    scaler = joblib.load(scaler_path)
    pipeline_data = {
        'scaler': scaler,
        'feature_columns': ['gap', 'grp', 'voltage', 'gi', 'sub_metering_1', 'sub_metering_2', 'sub_metering_3', 'hour', 'weekday', 'month', 'day_of_year'],
        'time_col': 'timestamp',
        'target_cols': ['gap', 'grp', 'voltage', 'gi', 'sub_metering_1', 'sub_metering_2', 'sub_metering_3']
    }
    with open(target_scaler, 'wb') as f:
        pickle.dump(pipeline_data, f)
    
    # Calculate hash
    model_hash = calculate_sha256(target_weights)
    
    # Generate config.yaml
    config = {
        "version": "1.0.0",
        "architecture": {
            "name": architecture,
            "num_targets": 7,
            "forecast_horizon": horizon,
            "lookback": 96 if horizon == 24 else (512 if horizon == 168 else 1440),
            # Set generic kwargs for Transformer models, they will be ignored if not supported by **kwargs
            "d_model": 128,
            "n_heads": 8,
            "n_layers": 3,
            "d_ff": 256,
            "dropout": 0.2
        }
    }
    
    # Add HybridV2 specific configs if needed
    if architecture in ("Hybrid_v2", "HybridV2"):
        config["model"] = {
            "name": architecture,
            "num_targets": 7,
            "forecast_horizon": horizon,
            "lookback": 96,
            "gru_hidden_size": 64,
            "gru_num_layers": 2,
            "d_model": 128,
            "n_heads": 8,
            "n_layers": 3,
            "d_ff": 256,
            "dropout": 0.2
        }
    # Add architecture specific configs
    if architecture in ("PatchTST", "AdvancedPatchTST"):
        config["architecture"].update({
            "lookback": 96 if horizon == 24 else (512 if horizon == 168 else 1440),
            "d_model": 128,
            "n_heads": 8,
            "n_layers": 3,
            "d_ff": 256,
            "dropout": 0.2
        })
    elif architecture == "CNN-BiLSTM":
        config["architecture"].update({
            "cnn_filters": 64,
            "lstm_hidden": 64
        })
    elif architecture == "SOTAForecastingModel":
        config["architecture"].update({
            "lookback": 96 if horizon == 24 else (512 if horizon == 168 else 1440),
            "d_model": 64,
            "d_channel": 256
        })
        
    with open(os.path.join(target_dir, "config.yaml"), "w") as f:
        yaml.dump(config, f)
        
    # Generate metrics.json
    metrics = {
        "model_fingerprint": model_hash,
        "final_unscaled": {
            "mae": 0.0,
            "rmse": 0.0,
            "r2": 0.0,
            "mape": 0.0
        }
    }
    with open(os.path.join(target_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=4)
        
    print(f"Successfully imported {architecture} as '{name}' to {target_dir}")
    print(f"Fingerprint: {model_hash}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--scaler", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--horizon", type=int, default=24)
    args = parser.parse_args()
    
    import_model(args.architecture, args.weights, args.scaler, args.name, args.horizon)
