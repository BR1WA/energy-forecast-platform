"""Recompute diagnostic evidence from the frozen LCL TFT checkpoints.

This script does not replace or modify the experiment metrics.  It reproduces
the frozen cold-start evaluation protocol and emits supplementary calibration,
horizon and household diagnostics for the PFE report.  It fails if the
recomputed headline MAE or household win count does not match the frozen JSON.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


WORKSPACE = Path(__file__).resolve().parents[2]
EXPERIMENT = WORKSPACE / "models" / "lcl_global_forecasting" / "full_selected_v1"
DATA = EXPERIMENT / "data"
EVIDENCE = WORKSPACE / "report" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
AMP_ENABLED = DEVICE.type == "cuda"
START = datetime(2013, 1, 1)
QUANTILES = (0.1, 0.5, 0.9)
TASKS = {
    "day_24h": {"horizon": 24, "lookback": 336, "seasonal_period": 168},
    "week_168h": {"horizon": 168, "lookback": 336, "seasonal_period": 168},
}


class GatedResidualNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, output_size=None, dropout=0.1):
        super().__init__()
        output_size = output_size or input_size
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size * 2)
        self.dropout = nn.Dropout(dropout)
        self.skip = nn.Identity() if input_size == output_size else nn.Linear(input_size, output_size)
        self.norm = nn.LayerNorm(output_size)

    def forward(self, x):
        residual = self.skip(x)
        hidden = self.dropout(F.elu(self.fc1(x)))
        value, gate = self.fc2(hidden).chunk(2, dim=-1)
        return self.norm(residual + value * torch.sigmoid(gate))


class VariableSelectionNetwork(nn.Module):
    def __init__(self, n_variables, hidden_size, dropout=0.1):
        super().__init__()
        self.embeddings = nn.ModuleList([nn.Linear(1, hidden_size) for _ in range(n_variables)])
        self.grns = nn.ModuleList(
            [GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout) for _ in range(n_variables)]
        )
        self.weight_network = nn.Sequential(
            nn.Linear(n_variables, hidden_size), nn.ELU(), nn.Linear(hidden_size, n_variables)
        )

    def forward(self, variables):
        weights = torch.softmax(self.weight_network(variables), dim=-1)
        transformed = []
        for index, (embedding, grn) in enumerate(zip(self.embeddings, self.grns)):
            transformed.append(grn(embedding(variables[..., index : index + 1])))
        stacked = torch.stack(transformed, dim=-2)
        return (stacked * weights.unsqueeze(-1)).sum(dim=-2), weights


class GlobalTFT(nn.Module):
    def __init__(self, hidden_size=128, n_heads=4, dropout=0.1, quantiles=QUANTILES):
        super().__init__()
        self.quantiles = tuple(quantiles)
        self.past_selection = VariableSelectionNetwork(10, hidden_size, dropout)
        self.future_selection = VariableSelectionNetwork(9, hidden_size, dropout)
        self.encoder_lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.decoder_lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.post_lstm = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
        self.attention = nn.MultiheadAttention(hidden_size, n_heads, dropout=dropout, batch_first=True)
        self.post_attention = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
        self.output = nn.Linear(hidden_size, len(self.quantiles))

    def forward(self, batch):
        past, _ = self.past_selection(torch.cat([batch["x"], batch["x_calendar"]], dim=-1))
        future, _ = self.future_selection(batch["y_calendar"])
        encoded, state = self.encoder_lstm(past)
        decoded, _ = self.decoder_lstm(future, state)
        sequence = self.post_lstm(torch.cat([encoded, decoded], dim=1))
        length = sequence.size(1)
        mask = torch.triu(torch.ones(length, length, device=sequence.device, dtype=torch.bool), diagonal=1)
        attended, _ = self.attention(sequence, sequence, sequence, attn_mask=mask, need_weights=False)
        quantiles = self.output(self.post_attention(attended)[:, -decoded.size(1) :])
        return quantiles


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to create empty evidence file: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pinball(target: np.ndarray, prediction: np.ndarray, quantile: float) -> np.ndarray:
    error = target - prediction
    return np.maximum((quantile - 1.0) * error, quantile * error)


def frozen_metrics(task: str) -> dict:
    path = EXPERIMENT / "runs" / "global_tft" / task / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))["cold_start_households"]


def evaluate_task(task: str, batch_size: int = 128) -> dict:
    config = TASKS[task]
    horizon = config["horizon"]
    lookback = config["lookback"]
    period = config["seasonal_period"]
    metadata = json.loads((DATA / "prepared.json").read_text(encoding="utf-8"))
    values = np.load(DATA / "hourly_raw.npy", mmap_mode="r")
    calendar = np.load(DATA / "hourly_calendar.npy", mmap_mode="r")
    cold = np.load(DATA / "cold_households.npy")
    scalers = np.load(DATA / "hourly_scalers.npz")
    means = scalers["mean"].astype(np.float32)
    stds = scalers["std"].astype(np.float32)
    val_end = int(metadata["hourly_val_end"])
    test_end = int(values.shape[1])
    origins = np.unique(np.linspace(max(val_end, lookback), test_end - horizon, num=24, dtype=np.int64))

    pairs = []
    for raw_house in cold:
        house = int(raw_house)
        row = values[house]
        for raw_origin in origins:
            origin = int(raw_origin)
            required = np.asarray(row[origin - lookback : origin + horizon])
            seasonal = np.asarray(row[origin - period : origin])
            if np.isfinite(required).all() and len(seasonal) == period and np.isfinite(seasonal).all():
                pairs.append((house, origin))

    checkpoint_path = EXPERIMENT / "runs" / "global_tft" / task / "best.pt"
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE, weights_only=False)
    model = GlobalTFT().to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()

    prediction_rows = []
    target_rows = []
    baseline_rows = []
    house_rows = []
    origin_rows = []
    started = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(pairs), batch_size):
            batch_pairs = pairs[offset : offset + batch_size]
            x, y_calendar = [], []
            targets, baselines, houses, batch_origins = [], [], [], []
            for house, origin in batch_pairs:
                raw = values[house]
                x.append(((np.asarray(raw[origin - lookback : origin], dtype=np.float32) - means[house]) / stds[house])[:, None])
                y_calendar.append(np.asarray(calendar[origin : origin + horizon], dtype=np.float32))
                targets.append(np.asarray(raw[origin : origin + horizon], dtype=np.float32))
                profile = np.asarray(raw[origin - period : origin], dtype=np.float32)
                baselines.append(profile[np.arange(horizon) % period])
                houses.append(house)
                batch_origins.append(origin)
            x_tensor = torch.from_numpy(np.stack(x)).to(DEVICE)
            x_calendar = torch.from_numpy(
                np.stack([np.asarray(calendar[o - lookback : o], dtype=np.float32) for o in batch_origins])
            ).to(DEVICE)
            y_calendar_tensor = torch.from_numpy(np.stack(y_calendar)).to(DEVICE)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=AMP_ENABLED):
                predicted_z = model({"x": x_tensor, "x_calendar": x_calendar, "y_calendar": y_calendar_tensor})
            predicted_z = predicted_z.float().cpu().numpy()
            batch_means = means[np.asarray(houses)][:, None, None]
            batch_stds = stds[np.asarray(houses)][:, None, None]
            prediction_rows.append(predicted_z * batch_stds + batch_means)
            target_rows.append(np.stack(targets))
            baseline_rows.append(np.stack(baselines))
            house_rows.extend(houses)
            origin_rows.extend(batch_origins)
    elapsed = time.perf_counter() - started

    predictions = np.concatenate(prediction_rows, axis=0).astype(np.float64)
    targets = np.concatenate(target_rows, axis=0).astype(np.float64)
    baselines = np.concatenate(baseline_rows, axis=0).astype(np.float64)
    houses = np.asarray(house_rows, dtype=np.int64)
    sample_origins = np.asarray(origin_rows, dtype=np.int64)
    median = predictions[:, :, 1]

    household_rows = []
    by_house = defaultdict(list)
    for index, house in enumerate(houses):
        by_house[int(house)].append(index)
    for house in sorted(by_house):
        indices = np.asarray(by_house[house], dtype=np.int64)
        mae = float(np.abs(median[indices] - targets[indices]).mean())
        baseline_mae = float(np.abs(baselines[indices] - targets[indices]).mean())
        household_rows.append(
            {
                "household_index": house,
                "evaluation_windows": len(indices),
                "mae_kwh": mae,
                "seasonal_naive_mae_kwh": baseline_mae,
                "beats_seasonal_naive": int(mae < baseline_mae),
                "central_80_coverage_percent": float(
                    100.0
                    * np.mean(
                        (targets[indices] >= predictions[indices, :, 0])
                        & (targets[indices] <= predictions[indices, :, 2])
                    )
                ),
                "central_80_width_kwh": float((predictions[indices, :, 2] - predictions[indices, :, 0]).mean()),
            }
        )

    step_rows = []
    for step in range(horizon):
        actual = targets[:, step]
        q10, q50, q90 = (predictions[:, step, i] for i in range(3))
        step_rows.append(
            {
                "horizon_step": step + 1,
                "mae_kwh": float(np.abs(q50 - actual).mean()),
                "seasonal_naive_mae_kwh": float(np.abs(baselines[:, step] - actual).mean()),
                "central_80_coverage_percent": float(100.0 * np.mean((actual >= q10) & (actual <= q90))),
                "central_80_width_kwh": float(np.mean(q90 - q10)),
                "q10_pinball_kwh": float(pinball(actual, q10, 0.1).mean()),
                "q50_pinball_kwh": float(pinball(actual, q50, 0.5).mean()),
                "q90_pinball_kwh": float(pinball(actual, q90, 0.9).mean()),
            }
        )

    hour_accumulator = defaultdict(lambda: {"actual": [], "q10": [], "q50": [], "q90": [], "baseline": []})
    for row, origin in enumerate(sample_origins):
        for step in range(horizon):
            hour = (START + timedelta(hours=int(origin + step))).hour
            bucket = hour_accumulator[hour]
            bucket["actual"].append(targets[row, step])
            bucket["q10"].append(predictions[row, step, 0])
            bucket["q50"].append(predictions[row, step, 1])
            bucket["q90"].append(predictions[row, step, 2])
            bucket["baseline"].append(baselines[row, step])
    hour_rows = []
    for hour in range(24):
        bucket = {name: np.asarray(data) for name, data in hour_accumulator[hour].items()}
        hour_rows.append(
            {
                "hour_utc": hour,
                "observations": len(bucket["actual"]),
                "mae_kwh": float(np.abs(bucket["q50"] - bucket["actual"]).mean()),
                "seasonal_naive_mae_kwh": float(np.abs(bucket["baseline"] - bucket["actual"]).mean()),
                "central_80_coverage_percent": float(
                    100.0
                    * np.mean((bucket["actual"] >= bucket["q10"]) & (bucket["actual"] <= bucket["q90"]))
                ),
                "central_80_width_kwh": float(np.mean(bucket["q90"] - bucket["q10"])),
            }
        )

    maes = np.asarray([row["mae_kwh"] for row in household_rows])
    representative_rows = []
    representative = {
        "p10": int(np.argmin(np.abs(maes - np.percentile(maes, 10)))),
        "median": int(np.argmin(np.abs(maes - np.median(maes)))),
        "p90": int(np.argmin(np.abs(maes - np.percentile(maes, 90)))),
    }
    for label, household_row_index in representative.items():
        house = int(household_rows[household_row_index]["household_index"])
        row_index = int(np.flatnonzero(houses == house)[len(np.flatnonzero(houses == house)) // 2])
        origin = int(sample_origins[row_index])
        for step in range(horizon):
            representative_rows.append(
                {
                    "profile": label,
                    "household_index": house,
                    "origin_index": origin,
                    "timestamp_utc": (START + timedelta(hours=origin + step)).isoformat(),
                    "horizon_step": step + 1,
                    "actual_kwh": float(targets[row_index, step]),
                    "q10_kwh": float(predictions[row_index, step, 0]),
                    "median_kwh": float(predictions[row_index, step, 1]),
                    "q90_kwh": float(predictions[row_index, step, 2]),
                    "seasonal_naive_kwh": float(baselines[row_index, step]),
                }
            )

    frozen = frozen_metrics(task)
    macro_mae = float(np.mean(maes))
    wins = int(sum(row["beats_seasonal_naive"] for row in household_rows))
    expected_wins = round(frozen["n_evaluated_households"] * frozen["households_beating_seasonal_percent"] / 100.0)
    if abs(macro_mae - frozen["macro_mae_kwh"]) > 1e-5:
        raise RuntimeError(f"{task}: recomputed MAE {macro_mae} != frozen {frozen['macro_mae_kwh']}")
    if wins != expected_wins:
        raise RuntimeError(f"{task}: recomputed win count {wins} != frozen {expected_wins}")
    if len(household_rows) != frozen["n_evaluated_households"] or len(pairs) != frozen["evaluation_windows"]:
        raise RuntimeError(f"{task}: reproduced evaluation cohort/window count differs from frozen metrics")

    write_csv(EVIDENCE / f"lcl_tft_{task}_households.csv", household_rows)
    write_csv(EVIDENCE / f"lcl_tft_{task}_horizon.csv", step_rows)
    write_csv(EVIDENCE / f"lcl_tft_{task}_hour_of_day.csv", hour_rows)
    write_csv(EVIDENCE / f"lcl_tft_{task}_representative_windows.csv", representative_rows)

    crossing = (predictions[:, :, 0] > predictions[:, :, 1]) | (predictions[:, :, 1] > predictions[:, :, 2])
    return {
        "task": task,
        "checkpoint": str(checkpoint_path.relative_to(WORKSPACE)).replace("\\", "/"),
        "checkpoint_sha256": sha256(checkpoint_path),
        "evaluation_windows": len(pairs),
        "evaluated_households": len(household_rows),
        "recomputed_macro_mae_kwh": macro_mae,
        "frozen_macro_mae_kwh": frozen["macro_mae_kwh"],
        "mae_absolute_difference_kwh": abs(macro_mae - frozen["macro_mae_kwh"]),
        "households_beating_seasonal_count": wins,
        "central_80_nominal_coverage_percent": 80.0,
        "central_80_empirical_coverage_percent": float(
            100.0 * np.mean((targets >= predictions[:, :, 0]) & (targets <= predictions[:, :, 2]))
        ),
        "central_80_mean_width_kwh": float((predictions[:, :, 2] - predictions[:, :, 0]).mean()),
        "q10_pinball_kwh": float(pinball(targets, predictions[:, :, 0], 0.1).mean()),
        "q50_pinball_kwh": float(pinball(targets, predictions[:, :, 1], 0.5).mean()),
        "q90_pinball_kwh": float(pinball(targets, predictions[:, :, 2], 0.9).mean()),
        "mean_pinball_kwh": float(
            np.mean(
                [
                    pinball(targets, predictions[:, :, 0], 0.1).mean(),
                    pinball(targets, predictions[:, :, 1], 0.5).mean(),
                    pinball(targets, predictions[:, :, 2], 0.9).mean(),
                ]
            )
        ),
        "quantile_crossing_rate_percent": float(100.0 * crossing.mean()),
        "diagnostic_inference_seconds": elapsed,
    }


def main() -> None:
    task_summaries = [evaluate_task(task) for task in TASKS]
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=WORKSPACE, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        git_commit = "unavailable"
    manifest = {
        "purpose": "Supplementary diagnostics; frozen headline experiment metrics remain authoritative.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "script": str(Path(__file__).relative_to(WORKSPACE)).replace("\\", "/"),
        "script_sha256": sha256(Path(__file__)),
        "prepared_metadata_sha256": sha256(DATA / "prepared.json"),
        "hourly_values_sha256": sha256(DATA / "hourly_raw.npy"),
        "hourly_calendar_sha256": sha256(DATA / "hourly_calendar.npy"),
        "hourly_scalers_sha256": sha256(DATA / "hourly_scalers.npz"),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "amp_float16": AMP_ENABLED,
        "tasks": task_summaries,
    }
    (EVIDENCE / "lcl_tft_reanalysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    main()
