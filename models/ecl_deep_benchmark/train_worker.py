
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--model", type=str, required=True)
    p.add_argument("--horizon", type=int, required=True)
    p.add_argument("--gpu", type=int, required=True)
    p.add_argument("--seq-len", type=int, default=96)
    p.add_argument("--label-len", type=int, default=48)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--patience", type=int, default=3)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--train-stride", type=int, default=1)
    p.add_argument("--eval-stride", type=int, default=1)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--smoke-test", action="store_true")
    return p.parse_args()


ARGS = parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = str(ARGS.gpu)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = ARGS.root
REPOS = ROOT / "repos"
DATA = ROOT / "data"
RUN_DIR = ROOT / "runs" / ARGS.model / f"h{ARGS.horizon}"
RUN_DIR.mkdir(parents=True, exist_ok=True)

METRICS_PATH = RUN_DIR / "metrics.json"
CHECKPOINT_PATH = RUN_DIR / "best.pt"
HISTORY_PATH = RUN_DIR / "history.json"
SAMPLE_PATH = RUN_DIR / "prediction_sample.npz"


def atomic_json(path: Path, payload: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, allow_nan=False))
    tmp.replace(path)


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


seed_everything(ARGS.seed)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True

DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
AMP_ENABLED = DEVICE.type == "cuda"


class WindowDataset(Dataset):
    def __init__(
        self,
        values,
        time_features,
        region_start: int,
        region_end: int,
        seq_len: int,
        pred_len: int,
        stride: int = 1,
        max_windows: int | None = None,
    ):
        first = int(region_start)
        last_inclusive = int(region_end - seq_len - pred_len)
        if last_inclusive < first:
            raise ValueError(
                f"No windows: start={first}, end={region_end}, "
                f"seq={seq_len}, pred={pred_len}"
            )
        starts = np.arange(first, last_inclusive + 1, stride, dtype=np.int32)
        if max_windows is not None:
            starts = starts[:max_windows]
        self.starts = starts
        self.values = values
        self.time_features = time_features
        self.seq_len = seq_len
        self.pred_len = pred_len

    def __len__(self):
        return len(self.starts)

    def __getitem__(self, idx):
        s = int(self.starts[idx])
        e = s + self.seq_len
        y_e = e + self.pred_len
        x = np.asarray(self.values[s:e], dtype=np.float32)
        y = np.asarray(self.values[e:y_e], dtype=np.float32)
        x_mark = np.asarray(self.time_features[s:e], dtype=np.float32)
        y_mark = np.asarray(self.time_features[e:y_e], dtype=np.float32)
        return (
            torch.from_numpy(x.copy()),
            torch.from_numpy(y.copy()),
            torch.from_numpy(x_mark.copy()),
            torch.from_numpy(y_mark.copy()),
        )


def make_loader(dataset, batch_size, shuffle):
    kwargs = dict(
        dataset=dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=ARGS.workers,
        pin_memory=True,
        drop_last=shuffle,
        persistent_workers=ARGS.workers > 0,
    )
    if ARGS.workers > 0:
        kwargs["prefetch_factor"] = 2
    return DataLoader(**kwargs)


def batch_size_for(model: str, horizon: int) -> int:
    # Conservative defaults for 321 variables on a 16-GB T4.
    if ARGS.smoke_test:
        return 2
    base = 16
    if horizon >= 192:
        base = 8
    if horizon >= 336:
        base = 4
    if horizon >= 720:
        base = 2
    if model == "itransformer":
        base = min(base, 8)
    if model == "cnn_bilstm":
        base = min(base, 8)
    return max(1, base)


def learning_rate_for(model: str, horizon: int) -> float:
    if model == "timepro":
        return 5e-4 if horizon in (24, 96) else 3e-4
    if model == "xpatch":
        return 1e-4
    if model == "itransformer":
        return 1e-4
    if model == "patchtst":
        return 1e-4
    if model == "cnn_bilstm":
        return 3e-4
    raise KeyError(model)



class CNNBiLSTM(nn.Module):
    """
    Efficient multivariate CNN-BiLSTM for direct multi-horizon forecasting.

    Input:
        [batch, seq_len, n_features]

    Output:
        [batch, pred_len, n_features]

    The CNN mixes client channels while extracting local temporal patterns.
    The bidirectional LSTM models the encoded sequence, and a low-rank direct
    head predicts all future timestamps and clients in one forward pass.
    """

    def __init__(
        self,
        pred_len: int,
        n_features: int,
        conv_channels: int = 96,
        lstm_hidden: int = 64,
        lstm_layers: int = 2,
        latent_dim: int = 48,
        dropout: float = 0.2,
    ):
        super().__init__()

        self.pred_len = pred_len
        self.latent_dim = latent_dim

        self.temporal_cnn = nn.Sequential(
            nn.Conv1d(
                in_channels=n_features,
                out_channels=conv_channels,
                kernel_size=3,
                padding=1,
            ),
            nn.BatchNorm1d(conv_channels),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(
                in_channels=conv_channels,
                out_channels=64,
                kernel_size=5,
                padding=2,
            ),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.bilstm = nn.LSTM(
            input_size=64,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )

        context_dim = 2 * lstm_hidden
        self.context_norm = nn.LayerNorm(context_dim)

        # A low-rank direct head avoids an enormous
        # context_dim -> pred_len * n_features projection.
        self.horizon_projection = nn.Sequential(
            nn.Linear(context_dim, pred_len * latent_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.channel_projection = nn.Linear(latent_dim, n_features)

    def forward(self, x):
        # [B, L, N] -> [B, N, L] -> [B, 64, L] -> [B, L, 64]
        encoded = self.temporal_cnn(x.transpose(1, 2)).transpose(1, 2)

        _, (hidden, _) = self.bilstm(encoded)

        # Final forward and backward hidden states from the last LSTM layer.
        context = torch.cat([hidden[-2], hidden[-1]], dim=-1)
        context = self.context_norm(context)

        future_latent = self.horizon_projection(context)
        future_latent = future_latent.view(
            x.size(0),
            self.pred_len,
            self.latent_dim,
        )

        return self.channel_projection(future_latent)

def clear_conflicting_modules():
    # Each worker only imports one repository, but this protects notebook
    # reruns and subprocess environments from stale top-level package names.
    for name in list(sys.modules):
        if name == "models" or name.startswith("models."):
            del sys.modules[name]
        if name == "layers" or name.startswith("layers."):
            del sys.modules[name]


def build_model(name: str, pred_len: int, n_features: int):
    clear_conflicting_modules()

    if name == "timepro":
        repo = REPOS / "TimePro"
        sys.path.insert(0, str(repo))
        from model.TimePro import Model

        cfg = SimpleNamespace(
            seq_len=ARGS.seq_len,
            pred_len=pred_len,
            use_norm=True,
            patch_len=8,
            stride=4,
            d_model=32,
            dropout=0.1,
            e_layers=2,
            enc_in=n_features,
            dec_in=n_features,
            c_out=n_features,
        )
        return Model(cfg), "encoder_decoder"

    if name == "xpatch":
        repo = REPOS / "xPatch"
        sys.path.insert(0, str(repo))
        from models.xPatch import Model

        cfg = SimpleNamespace(
            seq_len=ARGS.seq_len,
            pred_len=pred_len,
            enc_in=n_features,
            patch_len=16,
            stride=8,
            padding_patch="end",
            revin=True,
            ma_type="ema",
            alpha=0.3,
            beta=0.1,
        )
        return Model(cfg), "x_only"

    if name in {"patchtst", "itransformer"}:
        repo = REPOS / "Time-Series-Library"
        sys.path.insert(0, str(repo))

        common = dict(
            task_name="long_term_forecast",
            seq_len=ARGS.seq_len,
            label_len=ARGS.label_len,
            pred_len=pred_len,
            enc_in=n_features,
            dec_in=n_features,
            c_out=n_features,
            output_attention=False,
            embed="timeF",
            freq="h",
            activation="gelu",
            dropout=0.1,
            factor=3,
            d_layers=1,
            moving_avg=25,
            distil=True,
        )

        if name == "itransformer":
            from models.iTransformer import Model
            cfg = SimpleNamespace(
                **common,
                d_model=512,
                n_heads=8,
                e_layers=4,
                d_ff=512,
                use_norm=True,
                class_strategy="projection",
            )
            return Model(cfg), "encoder_decoder"

        from models.PatchTST import Model
        cfg = SimpleNamespace(
            **common,
            e_layers=3,
            n_heads=16,
            d_model=128,
            d_ff=256,
            fc_dropout=0.2,
            head_dropout=0.0,
            patch_len=16,
            stride=8,
            padding_patch="end",
            revin=1,
            affine=0,
            subtract_last=0,
            decomposition=0,
            kernel_size=25,
            individual=0,
        )
        return Model(cfg), "encoder_decoder"


    if name == "cnn_bilstm":
        model = CNNBiLSTM(
            pred_len=pred_len,
            n_features=n_features,
            conv_channels=96,
            lstm_hidden=64,
            lstm_layers=2,
            latent_dim=48,
            dropout=0.2,
        )
        return model, "x_only"

    raise KeyError(f"Unknown model: {name}")


def forward_model(model, interface, x, y, x_mark, y_mark):
    if interface == "x_only":
        return model(x)

    # The selected TimePro/iTransformer/PatchTST implementations are
    # encoder-centric; a conventional decoder tensor keeps the interface
    # compatible even when the model ignores it.
    label = x[:, -ARGS.label_len :, :]
    zeros = torch.zeros(
        x.size(0),
        ARGS.horizon,
        x.size(2),
        device=x.device,
        dtype=x.dtype,
    )
    dec_inp = torch.cat([label, zeros], dim=1)
    label_mark = x_mark[:, -ARGS.label_len :, :]
    dec_mark = torch.cat([label_mark, y_mark], dim=1)
    out = model(x, x_mark, dec_inp, dec_mark)
    if isinstance(out, tuple):
        out = out[0]
    return out[:, -ARGS.horizon :, :]


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


@torch.no_grad()
def normalized_mse(model, interface, loader):
    model.eval()
    squared_sum = 0.0
    count = 0
    for x, y, x_mark, y_mark in loader:
        x = x.to(DEVICE, non_blocking=True)
        y = y.to(DEVICE, non_blocking=True)
        x_mark = x_mark.to(DEVICE, non_blocking=True)
        y_mark = y_mark.to(DEVICE, non_blocking=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=AMP_ENABLED):
            pred = forward_model(model, interface, x, y, x_mark, y_mark)
        diff = pred.float() - y.float()
        squared_sum += float(torch.sum(diff * diff).item())
        count += diff.numel()
    return squared_sum / max(count, 1)


class StreamingMetrics:
    def __init__(self, n_features, mean, scale, mase_denominator):
        self.n_features = n_features
        self.mean = mean.astype(np.float64)
        self.scale = scale.astype(np.float64)
        self.mase_denom = np.maximum(mase_denominator.astype(np.float64), 1e-8)

        self.n = 0
        self.norm_abs = 0.0
        self.norm_sq = 0.0

        self.raw_abs = 0.0
        self.raw_sq = 0.0
        self.raw_signed = 0.0
        self.smape_sum = 0.0
        self.mase_sum = 0.0

        self.y_sum = 0.0
        self.y_sq_sum = 0.0
        self.sse = 0.0

        self.ch_count = np.zeros(n_features, dtype=np.int64)
        self.ch_y_sum = np.zeros(n_features, dtype=np.float64)
        self.ch_y_sq_sum = np.zeros(n_features, dtype=np.float64)
        self.ch_sse = np.zeros(n_features, dtype=np.float64)

    def update(self, pred_z, true_z):
        pred_z = np.asarray(pred_z, dtype=np.float64)
        true_z = np.asarray(true_z, dtype=np.float64)
        diff_z = pred_z - true_z

        self.norm_abs += np.abs(diff_z).sum()
        self.norm_sq += np.square(diff_z).sum()

        pred = pred_z * self.scale + self.mean
        true = true_z * self.scale + self.mean
        diff = pred - true

        self.raw_abs += np.abs(diff).sum()
        self.raw_sq += np.square(diff).sum()
        self.raw_signed += diff.sum()
        self.smape_sum += (
            2.0 * np.abs(diff) / (np.abs(pred) + np.abs(true) + 1e-8)
        ).sum()
        self.mase_sum += (np.abs(diff) / self.mase_denom).sum()

        self.n += true.size
        self.y_sum += true.sum()
        self.y_sq_sum += np.square(true).sum()
        self.sse += np.square(diff).sum()

        axes = tuple(range(true.ndim - 1))
        points_per_channel = int(np.prod(true.shape[:-1]))
        self.ch_count += points_per_channel
        self.ch_y_sum += true.sum(axis=axes)
        self.ch_y_sq_sum += np.square(true).sum(axis=axes)
        self.ch_sse += np.square(diff).sum(axis=axes)

    def compute(self):
        n = max(self.n, 1)
        global_sst = self.y_sq_sum - (self.y_sum ** 2) / n
        r2_global = 1.0 - self.sse / max(global_sst, 1e-12)

        ch_sst = self.ch_y_sq_sum - (
            np.square(self.ch_y_sum) / np.maximum(self.ch_count, 1)
        )
        valid = ch_sst > 1e-12
        ch_r2 = np.full(self.n_features, np.nan, dtype=np.float64)
        ch_r2[valid] = 1.0 - self.ch_sse[valid] / ch_sst[valid]

        return {
            "normalized_mse": self.norm_sq / n,
            "normalized_mae": self.norm_abs / n,
            "normalized_rmse": math.sqrt(self.norm_sq / n),
            "physical_mae_kwh": self.raw_abs / n,
            "physical_rmse_kwh": math.sqrt(self.raw_sq / n),
            "physical_bias_kwh": self.raw_signed / n,
            "smape_percent": 100.0 * self.smape_sum / n,
            "mase_24h": self.mase_sum / n,
            "r2_global": float(r2_global),
            "r2_macro_clients": float(np.nanmean(ch_r2)),
            "r2_median_clients": float(np.nanmedian(ch_r2)),
        }


@torch.no_grad()
def evaluate(model, interface, loader, mean, scale, mase_denom):
    model.eval()
    meter = StreamingMetrics(
        n_features=len(mean),
        mean=mean,
        scale=scale,
        mase_denominator=mase_denom,
    )
    saved_pred = []
    saved_true = []
    start = time.perf_counter()

    for x, y, x_mark, y_mark in loader:
        x = x.to(DEVICE, non_blocking=True)
        y = y.to(DEVICE, non_blocking=True)
        x_mark = x_mark.to(DEVICE, non_blocking=True)
        y_mark = y_mark.to(DEVICE, non_blocking=True)

        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=AMP_ENABLED):
            pred = forward_model(model, interface, x, y, x_mark, y_mark)

        pred_np = pred.float().cpu().numpy()
        true_np = y.float().cpu().numpy()
        meter.update(pred_np, true_np)

        remaining = 16 - len(saved_pred)
        if remaining > 0:
            take = min(remaining, pred_np.shape[0])
            saved_pred.extend(pred_np[:take])
            saved_true.extend(true_np[:take])

    elapsed = time.perf_counter() - start
    metrics = meter.compute()
    metrics["test_inference_seconds"] = elapsed
    metrics["test_windows"] = len(loader.dataset)
    metrics["seconds_per_window"] = elapsed / max(len(loader.dataset), 1)

    if saved_pred:
        np.savez_compressed(
            SAMPLE_PATH,
            pred_standardized=np.asarray(saved_pred, dtype=np.float32),
            true_standardized=np.asarray(saved_true, dtype=np.float32),
            mean=mean.astype(np.float32),
            scale=scale.astype(np.float32),
        )
    return metrics


def main():
    started = time.time()
    split = json.loads((DATA / "split.json").read_text())
    values = np.load(DATA / "ecl_321_standardized.npy", mmap_mode="r")
    raw = np.load(DATA / "ecl_321_hourly_kwh.npy", mmap_mode="r")
    marks = np.load(DATA / "time_features.npy", mmap_mode="r")
    scaler = np.load(DATA / "scaler.npz")
    mean = scaler["mean"]
    scale = scaler["scale"]
    n_features = values.shape[1]

    train_end = split["train_end"]
    val_end = split["val_end"]
    test_end = split["test_end"]

    # MASE seasonal denominator from training only.
    seasonality = 24
    train_raw = np.asarray(raw[:train_end], dtype=np.float64)
    mase_denom = np.mean(
        np.abs(train_raw[seasonality:] - train_raw[:-seasonality]),
        axis=0,
    )
    del train_raw

    max_windows = 64 if ARGS.smoke_test else None
    train_ds = WindowDataset(
        values, marks,
        0, train_end,
        ARGS.seq_len, ARGS.horizon,
        stride=max(ARGS.train_stride, 16 if ARGS.smoke_test else ARGS.train_stride),
        max_windows=max_windows,
    )
    val_ds = WindowDataset(
        values, marks,
        train_end - ARGS.seq_len, val_end,
        ARGS.seq_len, ARGS.horizon,
        stride=max(ARGS.eval_stride, 16 if ARGS.smoke_test else ARGS.eval_stride),
        max_windows=max_windows,
    )
    test_ds = WindowDataset(
        values, marks,
        val_end - ARGS.seq_len, test_end,
        ARGS.seq_len, ARGS.horizon,
        stride=max(ARGS.eval_stride, 16 if ARGS.smoke_test else ARGS.eval_stride),
        max_windows=max_windows,
    )

    batch_size = batch_size_for(ARGS.model, ARGS.horizon)
    train_loader = make_loader(train_ds, batch_size, shuffle=True)
    val_loader = make_loader(val_ds, batch_size, shuffle=False)
    test_loader = make_loader(test_ds, batch_size, shuffle=False)

    model, interface = build_model(ARGS.model, ARGS.horizon, n_features)
    model = model.to(DEVICE)
    params = count_parameters(model)
    print(model)
    print(f"Trainable parameters: {params:,}")
    print(
        f"Windows train/val/test: "
        f"{len(train_ds)}/{len(val_ds)}/{len(test_ds)}"
    )
    print(f"Batch size: {batch_size}")

    lr = learning_rate_for(ARGS.model, ARGS.horizon)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(ARGS.epochs, 1),
        eta_min=lr * 0.05,
    )
    try:
        scaler_amp = torch.amp.GradScaler(
            "cuda", enabled=AMP_ENABLED
        )
    except (AttributeError, TypeError):
        scaler_amp = torch.cuda.amp.GradScaler(
            enabled=AMP_ENABLED
        )
    criterion = nn.MSELoss()

    best_val = float("inf")
    bad_epochs = 0
    history = []
    training_start = time.perf_counter()

    for epoch in range(1, ARGS.epochs + 1):
        model.train()
        loss_sum = 0.0
        element_count = 0
        epoch_start = time.perf_counter()

        for x, y, x_mark, y_mark in train_loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            x_mark = x_mark.to(DEVICE, non_blocking=True)
            y_mark = y_mark.to(DEVICE, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type="cuda",
                dtype=torch.float16,
                enabled=AMP_ENABLED,
            ):
                pred = forward_model(
                    model, interface, x, y, x_mark, y_mark
                )
                loss = criterion(pred, y)

            scaler_amp.scale(loss).backward()
            scaler_amp.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler_amp.step(optimizer)
            scaler_amp.update()

            loss_sum += float(loss.item()) * y.numel()
            element_count += y.numel()

        scheduler.step()
        train_mse = loss_sum / max(element_count, 1)
        val_mse = normalized_mse(model, interface, val_loader)
        epoch_seconds = time.perf_counter() - epoch_start

        row = {
            "epoch": epoch,
            "train_mse": train_mse,
            "val_mse": val_mse,
            "lr": optimizer.param_groups[0]["lr"],
            "seconds": epoch_seconds,
        }
        history.append(row)
        atomic_json(HISTORY_PATH, history)
        print(json.dumps(row))

        if val_mse < best_val - 1e-7:
            best_val = val_mse
            bad_epochs = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "model": ARGS.model,
                    "horizon": ARGS.horizon,
                    "seq_len": ARGS.seq_len,
                    "n_features": n_features,
                    "best_val_mse": best_val,
                    "seed": ARGS.seed,
                },
                CHECKPOINT_PATH,
            )
        else:
            bad_epochs += 1
            if bad_epochs >= ARGS.patience:
                print(f"Early stopping after epoch {epoch}")
                break

    training_seconds = time.perf_counter() - training_start

    try:
        checkpoint = torch.load(
            CHECKPOINT_PATH, map_location=DEVICE, weights_only=False
        )
    except TypeError:
        checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])

    metrics = evaluate(
        model,
        interface,
        test_loader,
        mean=mean,
        scale=scale,
        mase_denom=mase_denom,
    )
    metrics.update(
        {
            "status": "success",
            "model": ARGS.model,
            "horizon": ARGS.horizon,
            "seq_len": ARGS.seq_len,
            "label_len": ARGS.label_len,
            "seed": ARGS.seed,
            "epochs_completed": len(history),
            "best_val_normalized_mse": best_val,
            "training_seconds": training_seconds,
            "total_wall_seconds": time.time() - started,
            "trainable_parameters": params,
            "batch_size": batch_size,
            "learning_rate": lr,
            "gpu_visible": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "implementation_note": (
                "Project-native multivariate CNN-BiLSTM"
                if ARGS.model == "cnn_bilstm"
                else "official/repository-aligned implementation"
            ),
        }
    )
    atomic_json(METRICS_PATH, metrics)
    print("\nFINAL_METRICS")
    print(json.dumps(metrics, indent=2))

    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        payload = {
            "status": "failed",
            "model": ARGS.model,
            "horizon": ARGS.horizon,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        atomic_json(METRICS_PATH, payload)
        print(payload["traceback"], file=sys.stderr)
        sys.exit(1)
