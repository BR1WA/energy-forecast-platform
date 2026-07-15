import os
import yaml
import subprocess
from copy import deepcopy

# The base configuration dictionary
BASE_CONFIG = {
    "model": {
        "patch_length": 16,
        "stride": 8,
        "d_model": 64,
        "encoder_layers": 3,
        "dropout": 0.1,
        "attention_dropout": 0.1,
        "head_dropout": 0.1
    },
    "training": {
        "epochs": 50,
        "batch_size": 64,
        "lr": 0.001,
        "weight_decay": 0.0001,
        "patience": 10,
        "clip_grad_norm": 1.0
    }
}

# The grid of experiments to run
EXPERIMENTS = [
    {"patch_length": 24, "stride": 12, "d_model": 64, "lr": 1e-3}, # Larger patch
    {"patch_length": 8, "stride": 4, "d_model": 64, "lr": 1e-3},   # Smaller patch
    {"patch_length": 16, "stride": 8, "d_model": 128, "lr": 1e-3}, # More capacity
    {"patch_length": 16, "stride": 8, "d_model": 32, "lr": 1e-3},  # Less capacity
    {"patch_length": 16, "stride": 8, "d_model": 64, "lr": 5e-4},  # Lower LR
    {"patch_length": 16, "stride": 8, "d_model": 64, "lr": 2e-3},  # Higher LR
    {"patch_length": 24, "stride": 12, "d_model": 128, "lr": 1e-3},# Large patch + High capacity
    {"patch_length": 8, "stride": 4, "d_model": 32, "lr": 1e-3},   # Small patch + Low capacity
]

def main():
    config_path = "configs/patchtst.yaml"
    
    print("Starting PatchTST Ablation Study on IHEPC-24h...")
    
    for i, exp in enumerate(EXPERIMENTS):
        print(f"\n[{i+1}/{len(EXPERIMENTS)}] Running experiment with: {exp}")
        
        # Build config
        cfg = deepcopy(BASE_CONFIG)
        cfg["model"]["patch_length"] = exp["patch_length"]
        cfg["model"]["stride"] = exp["stride"]
        cfg["model"]["d_model"] = exp["d_model"]
        cfg["training"]["lr"] = exp["lr"]
        
        # Save to yaml
        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False)
            
        # Run training
        try:
            # Setting environment variables using os.environ wrapper
            env = os.environ.copy()
            # Ensure it sees the project root in PYTHONPATH
            env["PYTHONPATH"] = os.path.abspath(".") + ";" + os.path.abspath("backend")
            
            subprocess.run([
                "python", "training/train.py", 
                "--dataset", "ihepc", 
                "--model", "patchtst", 
                "--horizon", "24", 
                "--lookback", "96"
            ], check=True, env=env)
        except subprocess.CalledProcessError as e:
            print(f"Experiment {exp} failed! Continuing to next.")
            continue
            
    print("\nAblation study complete! Running collect_benchmarks.py...")
    subprocess.run(["python", "scripts/collect_benchmarks.py", "--dataset", "ihepc", "--horizon", "24"])

if __name__ == "__main__":
    main()
