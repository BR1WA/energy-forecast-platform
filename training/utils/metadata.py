import yaml
import subprocess
import datetime
import os
from typing import Dict, Any

def get_git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
    except Exception:
        return "unknown"

def generate_experiment_id() -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"exp_{timestamp}"

def create_metadata_dict(
    exp_id: str,
    name: str,
    architecture: str,
    dataset: str,
    horizon: int,
    lookback: int,
    seed: int,
    epochs: int,
    batch_size: int,
    optimizer: str,
    learning_rate: float,
    training_time_seconds: float,
    metrics: Dict[str, float] = None
) -> Dict[str, Any]:
    
    return {
        "experiment": {
            "id": exp_id,
            "name": name,
            "architecture": architecture,
            "dataset": dataset,
            "horizon": horizon,
            "lookback": lookback,
            "seed": seed,
            "git_commit": get_git_commit()
        },
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "optimizer": optimizer,
            "learning_rate": learning_rate,
            "training_time_seconds": round(training_time_seconds, 2)
        },
        "metrics": metrics or {}
    }

def save_metadata(metadata: Dict[str, Any], filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
