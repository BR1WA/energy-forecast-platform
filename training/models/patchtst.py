import os
import yaml
import json
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from transformers import PatchTSTConfig, PatchTSTForPrediction
from training.baselines.base import ForecastModel
from training.engine.trainer import Trainer

class PatchTSTWrapper(nn.Module):
    def __init__(self, hf_model, n_targets: int):
        super().__init__()
        self.hf_model = hf_model
        self.n_targets = n_targets

    def forward(self, x):
        # x is (batch, lookback, n_features)
        outputs = self.hf_model(past_values=x)
        # outputs.prediction_outputs is (batch, horizon, n_features)
        return outputs.prediction_outputs[:, :, :self.n_targets]


class PatchTSTModel(ForecastModel):
    name = "patchtst"
    supports_feature_importance = False
    supports_gpu = True

    def __init__(self, config_path: str = "configs/patchtst.yaml", exp_dir: str = None, **kwargs):
        self.exp_dir = exp_dir
        self.config_path = config_path
        self.trial = kwargs.pop("trial", None)
        
        # Load config
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {"model": {}, "training": {}}

        # Optuna kwargs override config
        for k, v in kwargs.items():
            if k in ["patch_length", "stride", "d_model", "encoder_layers", "dropout", "attention_dropout", "head_dropout", "num_heads", "d_ff"]:
                self.config["model"][k] = v
            elif k in ["epochs", "batch_size", "lr", "weight_decay", "patience", "clip_grad_norm"]:
                self.config["training"][k] = v

        self._model = None
        self.n_features = None
        self.horizon = None
        self.n_targets = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def _init_model(self, lookback: int, horizon: int, n_features: int):
        model_cfg = self.config.get("model", {})
        
        d_model = model_cfg.get("d_model", 64)
        
        hf_config = PatchTSTConfig(
            context_length=lookback,
            prediction_length=horizon,
            num_input_channels=n_features,
            patch_length=model_cfg.get("patch_length", 16),
            stride=model_cfg.get("stride", 8),
            d_model=d_model,
            encoder_layers=model_cfg.get("encoder_layers", 3),
            encoder_attention_heads=model_cfg.get("num_heads", 16),
            encoder_ffn_dim=model_cfg.get("d_ff", d_model * 4),
            dropout=model_cfg.get("dropout", 0.1),
            attention_dropout=model_cfg.get("attention_dropout", 0.1),
            head_dropout=model_cfg.get("head_dropout", 0.1),
            distribution_output=None, # deterministic
        )
        
        hf_model = PatchTSTForPrediction(hf_config)
        self._model = PatchTSTWrapper(hf_model, self.n_targets)

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        if X_val is None or Y_val is None:
            raise ValueError("PatchTST requires validation data for early stopping.")

        self.n_features = X_train.shape[2]
        self.horizon = Y_train.shape[1]
        self.n_targets = Y_train.shape[2]
        lookback = X_train.shape[1]

        self._init_model(lookback, self.horizon, self.n_features)
        
        train_cfg = self.config.get("training", {})
        epochs = train_cfg.get("epochs", 50)
        batch_size = train_cfg.get("batch_size", 64)
        lr = train_cfg.get("lr", 1e-3)
        weight_decay = train_cfg.get("weight_decay", 1e-4)
        patience = train_cfg.get("patience", 10)
        clip_grad_norm = train_cfg.get("clip_grad_norm", 1.0)

        optimizer = torch.optim.AdamW(self._model.parameters(), lr=lr, weight_decay=weight_decay)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=patience//2)
        
        trainer = Trainer(
            model=self._model,
            optimizer=optimizer,
            scheduler=scheduler,
            loss_fn=torch.nn.MSELoss(),
            epochs=epochs,
            batch_size=batch_size,
            patience=patience,
            clip_grad_norm=clip_grad_norm,
            device=self.device,
            log_dir=self.exp_dir,
            trial=self.trial
        )
        
        trainer.fit(X_train, Y_train, X_val, Y_val)
        self._model = trainer.model # Load best model back

    def predict(self, X: np.ndarray) -> np.ndarray:
        self._model.eval()
        self._model.to(self.device)
        
        batch_size = self.config.get("training", {}).get("batch_size", 64)
        preds = []
        
        with torch.no_grad():
            for i in range(0, len(X), batch_size):
                batch_X = torch.tensor(X[i:i+batch_size], dtype=torch.float32).to(self.device)
                pred = self._model(batch_X)
                preds.append(pred.cpu().numpy())

        return np.concatenate(preds, axis=0)

    def save(self, path: str) -> None:
        """
        Saves the model weights and configs.
        """
        if self._model is not None and self.exp_dir is not None:
            self._model.hf_model.config.save_pretrained(self.exp_dir)
            with open(Path(self.exp_dir) / "training_config.yaml", "w") as f:
                yaml.dump(self.config, f)
            # torch.save is already handled by Trainer (`best.pt`)
