import json
import os
import time
import torch
import subprocess
import matplotlib.pyplot as plt
from datetime import datetime

class ExperimentTracker:
    def __init__(self, config, experiment_dir="experiments", checkpoint_dir="checkpoints"):
        self.config = config
        self.experiment_dir = experiment_dir
        self.checkpoint_dir = checkpoint_dir
        
        # Ensure directories exist
        os.makedirs(self.experiment_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        self.experiment_id = f"{config.get('experiment_name', 'experiment')}_{int(time.time())}"
        self.start_time = time.time()
        self.metrics = {}
        
        # Collect environment details for reproducibility
        self.env_details = self._get_env_details()

    def _get_env_details(self):
        env = {
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        }
        if env["cuda_available"]:
            env["cuda_version"] = torch.version.cuda
            env["device_name"] = torch.cuda.get_device_name(0)
            
        try:
            git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
            env["git_commit"] = git_commit
        except Exception:
            env["git_commit"] = "unknown"
            
        return env

    def log_metrics(self, metrics_dict, epoch=None):
        if epoch is not None:
            if "epochs" not in self.metrics:
                self.metrics["epochs"] = []
            self.metrics["epochs"].append({"epoch": epoch, "metrics": metrics_dict})
        else:
            self.metrics["final"] = metrics_dict

    def save_checkpoint(self, model, optimizer, epoch, val_loss):
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{self.experiment_id}_best.pth")
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'val_loss': val_loss,
            'config': self.config
        }, checkpoint_path)
        return checkpoint_path

    def end_experiment(self):
        duration = time.time() - self.start_time
        
        report = {
            "experiment_id": self.experiment_id,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "config": self.config,
            "environment": self.env_details,
            "metrics": self.metrics
        }
        
        report_path = os.path.join(self.experiment_dir, f"{self.experiment_id}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=4)
            
        return report_path

    def plot_predictions(self, actuals, predictions, horizon, save_dir="logs"):
        os.makedirs(save_dir, exist_ok=True)
        plt.figure(figsize=(10, 5))
        plt.plot(actuals[:horizon], label="Actual")
        plt.plot(predictions[:horizon], label="Predicted", linestyle='dashed')
        plt.title(f"Prediction vs Actual ({self.config.get('experiment_name')})")
        plt.legend()
        plt.tight_layout()
        plot_path = os.path.join(save_dir, f"{self.experiment_id}_pred.png")
        plt.savefig(plot_path)
        plt.close()
        
    def plot_residuals(self, residuals, save_dir="logs"):
        os.makedirs(save_dir, exist_ok=True)
        plt.figure(figsize=(10, 5))
        plt.hist(residuals, bins=50, alpha=0.75)
        plt.title(f"Residuals Histogram ({self.config.get('experiment_name')})")
        plt.tight_layout()
        plot_path = os.path.join(save_dir, f"{self.experiment_id}_residuals.png")
        plt.savefig(plot_path)
        plt.close()
