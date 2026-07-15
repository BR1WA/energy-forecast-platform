import os
import time
import logging
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

log = logging.getLogger(__name__)

class Trainer:
    """
    A generic PyTorch training engine for forecasting models.
    Handles optimization, scheduling, early stopping (via MAE), 
    mixed precision (AMP), and metric logging.
    """
    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler=None,
        loss_fn: nn.Module = nn.MSELoss(),
        epochs: int = 50,
        batch_size: int = 64,
        patience: int = 10,
        clip_grad_norm: float = 1.0,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        log_dir: str = None,
        trial = None
    ):
        self.model = model.to(device)
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.loss_fn = loss_fn.to(device)
        self.epochs = epochs
        self.batch_size = batch_size
        self.patience = patience
        self.clip_grad_norm = clip_grad_norm
        self.device = device
        self.log_dir = log_dir
        self.trial = trial

        self.scaler = torch.amp.GradScaler('cuda') if "cuda" in device else None
        
        self.history = {
            "epoch": [],
            "train_loss": [],
            "val_loss": [],
            "val_mae": [],
            "lr": []
        }

    def _create_dataloader(self, X: np.ndarray, Y: np.ndarray, shuffle: bool = True) -> DataLoader:
        # X: (N, L, F), Y: (N, H, T)
        dataset = TensorDataset(
            torch.tensor(X, dtype=torch.float32),
            torch.tensor(Y, dtype=torch.float32)
        )
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=shuffle, num_workers=0)

    def _train_epoch(self, dataloader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0
        
        for X_batch, Y_batch in dataloader:
            X_batch = X_batch.to(self.device)
            Y_batch = Y_batch.to(self.device)
            
            self.optimizer.zero_grad()
            
            if self.scaler is not None:
                with torch.amp.autocast('cuda'):
                    outputs = self.model(X_batch)
                    loss = self.loss_fn(outputs, Y_batch)
                
                self.scaler.scale(loss).backward()
                if self.clip_grad_norm > 0:
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.clip_grad_norm)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                outputs = self.model(X_batch)
                loss = self.loss_fn(outputs, Y_batch)
                loss.backward()
                if self.clip_grad_norm > 0:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.clip_grad_norm)
                self.optimizer.step()
                
            total_loss += loss.item() * X_batch.size(0)
            
        return total_loss / len(dataloader.dataset)

    def _validate(self, dataloader: DataLoader):
        self.model.eval()
        total_loss = 0.0
        total_mae = 0.0
        
        with torch.no_grad():
            for X_batch, Y_batch in dataloader:
                X_batch = X_batch.to(self.device)
                Y_batch = Y_batch.to(self.device)
                
                if self.scaler is not None:
                    with torch.amp.autocast('cuda'):
                        outputs = self.model(X_batch)
                        loss = self.loss_fn(outputs, Y_batch)
                else:
                    outputs = self.model(X_batch)
                    loss = self.loss_fn(outputs, Y_batch)
                
                total_loss += loss.item() * X_batch.size(0)
                mae = torch.abs(outputs - Y_batch).mean()
                total_mae += mae.item() * X_batch.size(0)
                
        n_samples = len(dataloader.dataset)
        return total_loss / n_samples, total_mae / n_samples

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray, Y_val: np.ndarray):
        train_loader = self._create_dataloader(X_train, Y_train, shuffle=True)
        val_loader = self._create_dataloader(X_val, Y_val, shuffle=False)
        
        best_val_mae = float('inf')
        patience_counter = 0
        best_model_state = None
        
        log.info(f"Training on {self.device} with {len(X_train)} samples, validating on {len(X_val)} samples")
        
        for epoch in range(1, self.epochs + 1):
            t0 = time.time()
            train_loss = self._train_epoch(train_loader)
            val_loss, val_mae = self._validate(val_loader)
            
            # Step scheduler if it's ReduceLROnPlateau, else just step
            if isinstance(self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                self.scheduler.step(val_mae)
            elif self.scheduler is not None:
                self.scheduler.step()
                
            current_lr = self.optimizer.param_groups[0]['lr']
            
            self.history["epoch"].append(epoch)
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["val_mae"].append(val_mae)
            self.history["lr"].append(current_lr)
            
            elapsed = time.time() - t0
            log.info(f"Epoch {epoch:03d}/{self.epochs} [{elapsed:.1f}s] - "
                     f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
                     f"Val MAE: {val_mae:.4f} | LR: {current_lr:.2e}")
            
            if val_mae < best_val_mae:
                best_val_mae = val_mae
                best_model_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                patience_counter = 0
                log.info(f"  --> Best Val MAE improved to {best_val_mae:.4f}")
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    log.info(f"Early stopping triggered after {epoch} epochs (patience={self.patience})")
                    break
                    
            # Optuna Pruning Support
            if self.trial is not None:
                import optuna
                self.trial.report(val_mae, epoch)
                if self.trial.should_prune():
                    log.info(f"Trial pruned at epoch {epoch} (Val MAE: {val_mae:.4f})")
                    raise optuna.exceptions.TrialPruned()
                    
        if best_model_state is not None:
            log.info("Restoring best model weights from early stopping...")
            self.model.load_state_dict(best_model_state)
            
        if self.log_dir:
            self._save_logs()
            
    def _save_logs(self):
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Save history CSV
        df = pd.DataFrame(self.history)
        df.to_csv(os.path.join(self.log_dir, "history.csv"), index=False)
        
        # Plot losses
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df["epoch"], df["train_loss"], label="Train Loss")
        ax.plot(df["epoch"], df["val_loss"], label="Val Loss")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("MSE Loss")
        ax.set_title("Training and Validation Loss")
        ax.legend()
        plt.tight_layout()
        fig.savefig(os.path.join(self.log_dir, "loss_curve.png"), dpi=150)
        plt.close(fig)
        
        # Plot LR
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df["epoch"], df["lr"], color='purple', label="Learning Rate")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("LR")
        ax.set_yscale('log')
        ax.set_title("Learning Rate Schedule")
        ax.legend()
        plt.tight_layout()
        fig.savefig(os.path.join(self.log_dir, "lr_curve.png"), dpi=150)
        plt.close(fig)
        
        # Save best model
        torch.save(self.model.state_dict(), os.path.join(self.log_dir, "best.pt"))
        log.info(f"Saved training history, plots, and best.pt to {self.log_dir}")
