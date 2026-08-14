"""Train, select, and audit the production-grade 30-day model candidate.

The command is intentionally two phase. ``select`` may only open known-series
files and writes the frozen architecture/blend/calibration decision. ``audit``
then opens the physically separate cold-series files exactly once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

# This pipeline is PyTorch-only.  Some developer machines also have Keras 3;
# explicitly disabling Transformers' optional TensorFlow integration avoids an
# unrelated tf-keras compatibility import during Chronos-2 fine-tuning.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import torch

HORIZON = 30
CONTEXT = 365
QUANTILES = (0.1, 0.5, 0.9)
PORTUGAL_VALIDATION_ORIGINS = tuple(
    np.datetime64(value) for value in ("2013-07-01", "2013-12-01")
)
PORTUGAL_TEST_ORIGINS = tuple(
    np.datetime64(f"2014-{month:02d}-01") for month in range(1, 13)
)
MOROCCO_COLD_IDS = {
    "Laayoune::Zone 5",
    "Boujdour::Zone 3",
    "Foum eloued::Zone 7",
    "Marrakech::Zone 2",
}


@dataclass(frozen=True)
class Window:
    unique_id: str
    origin: np.datetime64
    context: np.ndarray
    target: np.ndarray


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_history(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError("Cannot interpolate a history without observations.")
    positions = np.arange(len(values))
    return np.interp(positions, positions[finite], values[finite]).astype(np.float32)


def model_context(values: np.ndarray) -> np.ndarray:
    values = finite_history(values)
    if len(values) > CONTEXT:
        return values[-CONTEXT:]
    if len(values) < 270:
        raise ValueError(f"At least 270 observations are required, got {len(values)}.")
    if len(values) < CONTEXT:
        values = np.pad(values, (CONTEXT - len(values), 0), mode="edge")
    return values.astype(np.float32)


def seasonal_baselines(context: np.ndarray) -> dict[str, np.ndarray]:
    context = finite_history(context)
    weekday = np.arange(len(context)) % 7
    future_weekday = np.arange(len(context), len(context) + HORIZON) % 7
    recent = context[-56:]
    recent_weekday = weekday[-56:]
    weekday_profile = np.asarray(
        [np.median(recent[recent_weekday == day]) for day in future_weekday],
        dtype=np.float32,
    )
    last28 = np.resize(context[-28:], HORIZON).astype(np.float32)
    annual = context[-365:-335].astype(np.float32)
    return {
        "weekday_8week_median": np.maximum(weekday_profile, 0),
        "last28_repeat": np.maximum(last28, 0),
        "annual": np.maximum(annual, 0),
        "weekday_annual_50_50": np.maximum(0.5 * weekday_profile + 0.5 * annual, 0),
    }


def windows_from_matrix(
    values: np.ndarray,
    dates: np.ndarray,
    ids: list[str],
    origins: tuple[np.datetime64, ...],
) -> list[Window]:
    result: list[Window] = []
    for origin in origins:
        index = int(np.searchsorted(dates, origin))
        if index < CONTEXT or index + HORIZON > len(dates) or dates[index] != origin:
            continue
        for row, unique_id in enumerate(ids):
            context = values[row, index - CONTEXT : index]
            target = values[row, index : index + HORIZON]
            if np.isfinite(context).mean() >= 0.95 and np.isfinite(target).all():
                result.append(
                    Window(
                        unique_id,
                        origin,
                        finite_history(context),
                        target.astype(np.float32),
                    )
                )
    if not result:
        raise RuntimeError("No valid matrix evaluation windows were found.")
    return result


def windows_from_long(
    frame: pd.DataFrame,
    ids: set[str] | None,
    *,
    test: bool,
) -> list[Window]:
    result: list[Window] = []
    source = frame if ids is None else frame[frame["unique_id"].isin(ids)]
    for unique_id, group in source.groupby("unique_id", sort=True):
        group = group.sort_values("ds")
        dates = group["ds"].to_numpy(dtype="datetime64[D]")
        values = group["y"].to_numpy(dtype=np.float32)
        n_windows = 3 if test else 2
        for offset in range(n_windows, 0, -1):
            index = len(values) - offset * HORIZON
            if index < 270:
                continue
            history_start = max(0, index - CONTEXT)
            expected = np.arange(
                dates[history_start], dates[index] + np.timedelta64(HORIZON, "D")
            )
            actual = dates[history_start : index + HORIZON]
            if not np.array_equal(actual, expected):
                continue
            context = values[history_start:index]
            target = values[index : index + HORIZON]
            if (
                len(context) >= 270
                and np.isfinite(context).mean() >= 0.95
                and np.isfinite(target).all()
            ):
                result.append(
                    Window(str(unique_id), dates[index], model_context(context), target)
                )
    if not result:
        raise RuntimeError("No valid Morocco evaluation windows were found.")
    return result


def training_frame_portugal(
    values: np.ndarray, dates: np.ndarray, ids: list[str], end: np.datetime64
) -> pd.DataFrame:
    cutoff = int(np.searchsorted(dates, end, side="right"))
    frames: list[pd.DataFrame] = []
    timestamps = pd.to_datetime(dates[:cutoff])
    for row, unique_id in enumerate(ids):
        y = values[row, :cutoff]
        valid = np.isfinite(y)
        frames.append(
            pd.DataFrame(
                {"unique_id": unique_id, "ds": timestamps[valid], "y": y[valid]}
            )
        )
    return pd.concat(frames, ignore_index=True)


def training_frame_morocco(frame: pd.DataFrame, reserve_days: int) -> pd.DataFrame:
    chunks = []
    for _, group in frame.groupby("unique_id", sort=False):
        chunks.append(group.sort_values("ds").iloc[:-reserve_days])
    return pd.concat(chunks, ignore_index=True)


def baseline_predictions(windows: list[Window]) -> dict[str, np.ndarray]:
    names = tuple(seasonal_baselines(windows[0].context))
    return {
        name: np.stack([seasonal_baselines(window.context)[name] for window in windows])
        for name in names
    }


def targets(windows: list[Window]) -> np.ndarray:
    return np.stack([window.target for window in windows]).astype(np.float32)


def series_scales(windows: list[Window]) -> np.ndarray:
    scales = []
    for window in windows:
        differences = np.abs(np.diff(window.context[-90:]))
        scale = float(np.mean(differences))
        scales.append(max(scale, 1e-6))
    return np.asarray(scales, dtype=np.float32)


def metrics(y: np.ndarray, prediction: np.ndarray, windows: list[Window]) -> dict:
    center = prediction[:, :, 1] if prediction.ndim == 3 else prediction
    error = center - y
    groups: dict[str, list[int]] = {}
    for index, window in enumerate(windows):
        groups.setdefault(window.unique_id, []).append(index)
    group_mae = []
    group_r2 = []
    group_mase = []
    scales = series_scales(windows)
    for indices in groups.values():
        actual = y[indices].reshape(-1)
        forecast = center[indices].reshape(-1)
        group_mae.append(float(np.mean(np.abs(forecast - actual))))
        denominator = float(np.sum((actual - actual.mean()) ** 2))
        group_r2.append(
            1.0 - float(np.sum((forecast - actual) ** 2)) / denominator
            if denominator > 0
            else 0.0
        )
        group_mase.append(
            float(np.mean(np.abs(center[indices] - y[indices]) / scales[indices, None]))
        )
    payload = {
        "daily_mae": float(np.mean(np.abs(error))),
        "daily_macro_mae": float(np.mean(group_mae)),
        "daily_macro_r2": float(np.mean(group_r2)),
        "daily_global_r2": 1.0
        - float(np.sum(error**2)) / float(np.sum((y - y.mean()) ** 2)),
        "macro_mase": float(np.mean(group_mase)),
        "month_total_mae": float(np.mean(np.abs(center.sum(axis=1) - y.sum(axis=1)))),
    }
    if prediction.ndim == 3:
        payload["interval_80_coverage"] = float(
            np.mean((y >= prediction[:, :, 0]) & (y <= prediction[:, :, 2]))
        )
        payload["interval_80_mean_width"] = float(
            np.mean(prediction[:, :, 2] - prediction[:, :, 0])
        )
    return payload


def mae(y: np.ndarray, prediction: np.ndarray) -> float:
    center = prediction[:, :, 1] if prediction.ndim == 3 else prediction
    return float(np.mean(np.abs(center - y)))


def conformal_offsets(
    y: np.ndarray, prediction: np.ndarray, windows: list[Window]
) -> tuple[float, float]:
    scale = series_scales(windows)[:, None]
    lower_error = (prediction[:, :, 0] - y) / scale
    upper_error = (y - prediction[:, :, 2]) / scale
    # Split conformal for a central 80% interval uses the 90th percentile on
    # each one-sided nonconformity score. Negative values are valid and shrink
    # an overly conservative raw interval.
    return float(np.quantile(lower_error, 0.9)), float(np.quantile(upper_error, 0.9))


def apply_conformal(
    prediction: np.ndarray,
    offsets: tuple[float, float],
    windows: list[Window],
) -> np.ndarray:
    calibrated = prediction.copy()
    scale = series_scales(windows)[:, None]
    calibrated[:, :, 0] = np.maximum(0, calibrated[:, :, 0] - offsets[0] * scale)
    calibrated[:, :, 2] = calibrated[:, :, 2] + offsets[1] * scale
    calibrated = np.sort(calibrated, axis=2)
    return calibrated


def chronos_predict(
    pipeline: Any, windows: list[Window], batch_size: int
) -> np.ndarray:
    result: list[np.ndarray] = []
    for start in range(0, len(windows), batch_size):
        batch = windows[start : start + batch_size]
        quantiles, _ = pipeline.predict_quantiles(
            [window.context for window in batch],
            prediction_length=HORIZON,
            quantile_levels=list(QUANTILES),
            batch_size=batch_size,
            cross_learning=False,
        )
        result.append(np.stack([item[0].float().cpu().numpy() for item in quantiles]))
    return np.maximum(np.concatenate(result), 0).astype(np.float32)


def make_supervised_model(name: str, steps: int, seed: int) -> Any:
    from neuralforecast.losses.pytorch import HuberMQLoss
    from neuralforecast.models import NHITS, TiDE

    common = dict(
        h=HORIZON,
        input_size=CONTEXT,
        loss=HuberMQLoss(quantiles=list(QUANTILES), delta=1.0),
        valid_loss=HuberMQLoss(quantiles=list(QUANTILES), delta=1.0),
        max_steps=steps,
        learning_rate=5e-4,
        val_check_steps=100,
        early_stop_patience_steps=3,
        batch_size=64,
        valid_batch_size=64,
        windows_batch_size=1024,
        inference_windows_batch_size=256,
        scaler_type="robust",
        random_seed=seed,
        accelerator="gpu",
        devices=1,
        precision="16-mixed",
        enable_progress_bar=False,
        logger=False,
        enable_checkpointing=False,
    )
    if name == "nhits":
        return NHITS(
            stack_types=["identity", "identity", "identity"],
            n_blocks=[1, 1, 1],
            mlp_units=[[256, 256], [256, 256], [256, 256]],
            n_pool_kernel_size=[7, 3, 1],
            n_freq_downsample=[7, 3, 1],
            dropout_prob_theta=0.1,
            alias="nhits",
            **common,
        )
    if name == "tide":
        return TiDE(
            hidden_size=256,
            decoder_output_dim=32,
            temporal_decoder_dim=64,
            dropout=0.2,
            num_encoder_layers=2,
            num_decoder_layers=2,
            alias="tide",
            **common,
        )
    raise ValueError(name)


def train_supervised(
    name: str,
    frame: pd.DataFrame,
    validation_windows: list[Window],
    output: Path,
    steps: int,
    seed: int,
) -> tuple[Any, np.ndarray]:
    from neuralforecast import NeuralForecast

    model = make_supervised_model(name, steps, seed)
    forecast = NeuralForecast(models=[model], freq="D")
    forecast.fit(df=frame, val_size=60, verbose=False)
    output.mkdir(parents=True, exist_ok=True)
    forecast.save(str(output), save_dataset=False, overwrite=True)
    prediction = supervised_predict(forecast, validation_windows)
    return forecast, prediction


def supervised_predict(forecast: Any, windows: list[Window]) -> np.ndarray:
    frames = []
    for index, window in enumerate(windows):
        frames.append(
            pd.DataFrame(
                {
                    "unique_id": f"window-{index:05d}",
                    "ds": pd.date_range(
                        end=pd.Timestamp(window.origin) - pd.Timedelta(days=1),
                        periods=CONTEXT,
                    ),
                    "y": window.context,
                }
            )
        )
    prediction = forecast.predict(
        df=pd.concat(frames, ignore_index=True), quantiles=list(QUANTILES)
    )
    model_name = forecast.models[0].alias
    columns = [f"{model_name}-lo-80.0", f"{model_name}-median", f"{model_name}-hi-80.0"]
    values = (
        prediction[columns].to_numpy(dtype=np.float32).reshape(len(windows), HORIZON, 3)
    )
    return np.maximum(values, 0)


def choose_baseline(
    y: np.ndarray, candidates: dict[str, np.ndarray]
) -> tuple[str, np.ndarray]:
    name = min(
        candidates, key=lambda item: float(np.mean(np.abs(candidates[item] - y)))
    )
    return name, candidates[name]


def choose_blend(
    y: np.ndarray, candidates: dict[str, np.ndarray], baseline: np.ndarray
) -> tuple[str, float, np.ndarray, list[dict]]:
    scores = []
    best: tuple[float, str, float, np.ndarray] | None = None
    baseline_q = np.repeat(baseline[:, :, None], 3, axis=2)
    for name, prediction in candidates.items():
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            blended = np.sort(weight * prediction + (1.0 - weight) * baseline_q, axis=2)
            score = mae(y, blended)
            scores.append({"model": name, "model_weight": weight, "daily_mae": score})
            candidate = (score, name, weight, blended)
            if best is None or candidate[0] < best[0]:
                best = candidate
    assert best is not None
    return best[1], best[2], best[3], sorted(scores, key=lambda item: item["daily_mae"])


def choose_multidataset_blend(
    portugal_y: np.ndarray,
    morocco_y: np.ndarray,
    portugal_candidates: dict[str, np.ndarray],
    morocco_candidates: dict[str, np.ndarray],
    portugal_baseline: np.ndarray,
    morocco_baseline: np.ndarray,
    morocco_windows: list[Window],
) -> tuple[str, float, np.ndarray, np.ndarray, list[dict]]:
    common_names = sorted(set(portugal_candidates) & set(morocco_candidates))
    p_base_mae = float(np.mean(np.abs(portugal_baseline - portugal_y)))
    m_base_mase = metrics(morocco_y, morocco_baseline, morocco_windows)["macro_mase"]
    p_baseline_q = np.repeat(portugal_baseline[:, :, None], 3, axis=2)
    m_baseline_q = np.repeat(morocco_baseline[:, :, None], 3, axis=2)
    leaderboard = []
    best: tuple[float, str, float, np.ndarray, np.ndarray] | None = None
    for name in common_names:
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            p_blend = np.sort(
                weight * portugal_candidates[name] + (1.0 - weight) * p_baseline_q,
                axis=2,
            )
            m_blend = np.sort(
                weight * morocco_candidates[name] + (1.0 - weight) * m_baseline_q,
                axis=2,
            )
            p_mae = mae(portugal_y, p_blend)
            m_mase = metrics(morocco_y, m_blend, morocco_windows)["macro_mase"]
            objective = 0.5 * (p_mae / p_base_mae) + 0.5 * (m_mase / m_base_mase)
            leaderboard.append(
                {
                    "model": name,
                    "model_weight": weight,
                    "normalized_cross_dataset_objective": objective,
                    "portugal_daily_mae": p_mae,
                    "morocco_macro_mase": m_mase,
                }
            )
            candidate = (objective, name, weight, p_blend, m_blend)
            if best is None or candidate[0] < best[0]:
                best = candidate
    assert best is not None
    return (
        best[1],
        best[2],
        best[3],
        best[4],
        sorted(
            leaderboard, key=lambda item: item["normalized_cross_dataset_objective"]
        ),
    )


def select(args: argparse.Namespace) -> dict:
    seed_everything(args.seed)
    prepared = args.prepared.resolve()
    output = args.output.resolve()
    models_dir = output / "models"
    output.mkdir(parents=True, exist_ok=True)
    start = time.time()

    # These are the only target files this phase is permitted to open.
    portugal = np.load(prepared / "portugal_known_daily_kwh.npy")
    dates = np.load(prepared / "portugal_dates.npy")
    portugal_ids = json.loads(
        (prepared / "portugal_known_clients.json").read_text(encoding="utf-8")
    )
    morocco = pd.read_parquet(prepared / "morocco_known_daily.parquet")

    portugal_windows = windows_from_matrix(
        portugal, dates, portugal_ids, PORTUGAL_VALIDATION_ORIGINS
    )
    morocco_windows = windows_from_long(morocco, None, test=False)
    y_portugal = targets(portugal_windows)
    y_morocco = targets(morocco_windows)
    portugal_baselines = baseline_predictions(portugal_windows)
    morocco_baselines = baseline_predictions(morocco_windows)
    portugal_baseline_name, portugal_baseline = choose_baseline(
        y_portugal, portugal_baselines
    )
    morocco_baseline_name, morocco_baseline = choose_baseline(
        y_morocco, morocco_baselines
    )

    # Train supervised specialists only on known Portugal and known Morocco data.
    portugal_frame = training_frame_portugal(
        portugal, dates, portugal_ids, np.datetime64("2013-06-30")
    )
    morocco_frame = training_frame_morocco(morocco, reserve_days=90)
    # N-HiTS/TiDE require input_size observations plus a validation tail.  The
    # Marrakech development series is shorter than that at this selection
    # cutoff, so it remains an out-of-domain validation series for supervised
    # models and is still included in Chronos-2 domain adaptation.
    supervised_morocco = morocco_frame.groupby("unique_id").filter(
        lambda group: len(group) >= CONTEXT + 60
    )
    supervised_portugal = portugal_frame.groupby("unique_id").filter(
        lambda group: len(group) >= CONTEXT + 60
    )
    supervised_frame = pd.concat(
        [supervised_portugal, supervised_morocco], ignore_index=True
    )
    supervised_portugal: dict[str, np.ndarray] = {}
    supervised_morocco: dict[str, np.ndarray] = {}
    for name in ("nhits", "tide"):
        print(f"Training {name} supervised specialist...", flush=True)
        model, p_prediction = train_supervised(
            name,
            supervised_frame,
            portugal_windows,
            models_dir / name,
            args.supervised_steps,
            args.seed,
        )
        supervised_portugal[name] = p_prediction
        supervised_morocco[name] = supervised_predict(model, morocco_windows)
        del model
        torch.cuda.empty_cache()

    from chronos import Chronos2Pipeline

    print("Loading Chronos-2 and forecasting zero-shot validation...", flush=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    base = Chronos2Pipeline.from_pretrained(
        "amazon/chronos-2", device_map=device, dtype=dtype
    )
    chronos_portugal: dict[str, np.ndarray] = {
        "chronos2_zero_shot": chronos_predict(base, portugal_windows, args.batch_size)
    }
    chronos_morocco: dict[str, np.ndarray] = {
        "chronos2_zero_shot": chronos_predict(base, morocco_windows, args.batch_size)
    }
    train_cutoff = int(
        np.searchsorted(dates, np.datetime64("2013-06-30"), side="right")
    )
    train_sequences = [
        finite_history(row[:train_cutoff][np.isfinite(row[:train_cutoff])])
        for row in portugal
    ]
    train_sequences.extend(
        [
            group.sort_values("ds")["y"].to_numpy(dtype=np.float32)[:-90]
            for _, group in morocco.groupby("unique_id")
        ]
    )
    validation_sequences = [
        np.concatenate([window.context, window.target])
        for window in portugal_windows[:64]
    ]
    lora_scores: list[dict] = []
    for steps in args.lora_steps:
        print(f"Training Chronos-2 LoRA for {steps} steps...", flush=True)
        directory = models_dir / f"chronos2_lora_{steps}"
        pipeline = base.fit(
            inputs=train_sequences,
            validation_inputs=validation_sequences,
            prediction_length=HORIZON,
            finetune_mode="lora",
            context_length=CONTEXT,
            learning_rate=1e-5,
            num_steps=steps,
            batch_size=args.lora_batch_size,
            output_dir=directory,
            min_past=180,
            remove_printer_callback=True,
            logging_steps=50,
        )
        key = f"chronos2_lora_{steps}"
        chronos_portugal[key] = chronos_predict(
            pipeline, portugal_windows, args.batch_size
        )
        chronos_morocco[key] = chronos_predict(
            pipeline, morocco_windows, args.batch_size
        )
        lora_scores.append(
            {
                "steps": steps,
                "portugal_daily_mae": mae(y_portugal, chronos_portugal[key]),
                "morocco_macro_mase": metrics(
                    y_morocco, chronos_morocco[key], morocco_windows
                )["macro_mase"],
            }
        )
        del pipeline
        torch.cuda.empty_cache()

    all_portugal = {**supervised_portugal, **chronos_portugal}
    all_morocco = {**supervised_morocco, **chronos_morocco}
    model_name, weight, selected_portugal, selected_morocco, leaderboard = (
        choose_multidataset_blend(
            y_portugal,
            y_morocco,
            all_portugal,
            all_morocco,
            portugal_baseline,
            morocco_baseline,
            morocco_windows,
        )
    )
    combined_y = np.concatenate([y_portugal, y_morocco], axis=0)
    combined_prediction = np.concatenate([selected_portugal, selected_morocco], axis=0)
    combined_windows = portugal_windows + morocco_windows
    offsets = conformal_offsets(combined_y, combined_prediction, combined_windows)
    selected_portugal = apply_conformal(selected_portugal, offsets, portugal_windows)
    selected_morocco = apply_conformal(selected_morocco, offsets, morocco_windows)

    # Freeze the winning design, then refit that design on all allowed known
    # Portugal observations through 2013. Cold clients remain unopened.
    production_dir = models_dir / "production_model"
    if production_dir.exists():
        shutil.rmtree(production_dir)
    if model_name in {"nhits", "tide"}:
        print(f"Refitting selected {model_name} production model...", flush=True)
        refit_portugal = training_frame_portugal(
            portugal, dates, portugal_ids, np.datetime64("2013-12-31")
        )
        refit_portugal = refit_portugal.groupby("unique_id").filter(
            lambda group: len(group) >= CONTEXT + 60
        )
        refit_frame = pd.concat([refit_portugal, supervised_morocco], ignore_index=True)
        final_model, _ = train_supervised(
            model_name,
            refit_frame,
            portugal_windows[:1],
            production_dir,
            args.supervised_steps,
            args.seed,
        )
        del final_model
        torch.cuda.empty_cache()
    elif model_name.startswith("chronos2_lora_"):
        selected_steps = int(model_name.rsplit("_", 1)[-1])
        refit_cutoff = int(
            np.searchsorted(dates, np.datetime64("2013-12-31"), side="right")
        )
        refit_sequences = [
            finite_history(row[:refit_cutoff][np.isfinite(row[:refit_cutoff])])
            for row in portugal
        ]
        refit_sequences.extend(
            [
                group.sort_values("ds")["y"].to_numpy(dtype=np.float32)[:-90]
                for _, group in morocco.groupby("unique_id")
            ]
        )
        print(
            f"Refitting selected Chronos-2 LoRA ({selected_steps} steps)...", flush=True
        )
        final_model = base.fit(
            inputs=refit_sequences,
            prediction_length=HORIZON,
            finetune_mode="lora",
            context_length=CONTEXT,
            learning_rate=1e-5,
            num_steps=selected_steps,
            batch_size=args.lora_batch_size,
            output_dir=production_dir,
            min_past=180,
            remove_printer_callback=True,
            logging_steps=50,
        )
        del final_model
        torch.cuda.empty_cache()

    selection = {
        "selection_version": 1,
        "frozen_before_cold_audit": True,
        "seed": args.seed,
        "architecture": model_name,
        "production_model_path": "models/production_model",
        "model_weight": weight,
        "baseline_weight": 1.0 - weight,
        "portugal_baseline": portugal_baseline_name,
        "morocco_baseline": morocco_baseline_name,
        "conformal_offsets": list(offsets),
        "supervised_steps": args.supervised_steps,
        "lora_candidates": lora_scores,
        "leaderboard": leaderboard,
        "validation": {
            "portugal_baseline": metrics(
                y_portugal, portugal_baseline, portugal_windows
            ),
            "portugal_candidate": metrics(
                y_portugal, selected_portugal, portugal_windows
            ),
            "morocco_baseline": metrics(y_morocco, morocco_baseline, morocco_windows),
            "morocco_candidate": metrics(y_morocco, selected_morocco, morocco_windows),
            "n_portugal_windows": len(portugal_windows),
            "n_morocco_windows": len(morocco_windows),
        },
        "runtime_seconds": time.time() - start,
    }
    atomic_json(output / "selection.json", selection)
    print(json.dumps(selection, indent=2), flush=True)
    return selection


def load_selected_model(output: Path, selection: dict, device: str) -> tuple[str, Any]:
    name = selection["architecture"]
    if name in {"nhits", "tide"}:
        from neuralforecast import NeuralForecast

        return name, NeuralForecast.load(str(output / "models" / "production_model"))
    from chronos import Chronos2Pipeline

    if name == "chronos2_zero_shot":
        return name, Chronos2Pipeline.from_pretrained(
            "amazon/chronos-2", device_map=device, dtype=torch.float32
        )
    checkpoint = output / "models" / "production_model" / "finetuned-ckpt"
    return name, Chronos2Pipeline.from_pretrained(
        checkpoint, device_map=device, dtype=torch.float32
    )


def predict_selected(
    name: str, model: Any, windows: list[Window], batch_size: int
) -> np.ndarray:
    if name in {"nhits", "tide"}:
        return supervised_predict(model, windows)
    return chronos_predict(model, windows, batch_size)


def improvement(baseline: float, candidate: float) -> float:
    return (baseline - candidate) / baseline


def audit(args: argparse.Namespace) -> dict:
    prepared = args.prepared.resolve()
    output = args.output.resolve()
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.resolve().read_text(encoding="utf-8"))
    start = time.time()

    # Cold target files are first opened here, after selection.json exists.
    portugal = np.load(prepared / "portugal_cold_daily_kwh.npy")
    dates = np.load(prepared / "portugal_dates.npy")
    portugal_ids = json.loads(
        (prepared / "portugal_cold_clients.json").read_text(encoding="utf-8")
    )
    morocco = pd.read_parquet(prepared / "morocco_cold_daily.parquet")
    tetouan = pd.read_parquet(prepared / "tetouan_cold_daily.parquet")
    portugal_windows = windows_from_matrix(
        portugal, dates, portugal_ids, PORTUGAL_TEST_ORIGINS
    )
    morocco_windows = windows_from_long(morocco, MOROCCO_COLD_IDS, test=True)
    tetouan_windows = windows_from_long(tetouan, None, test=True)
    y_portugal = targets(portugal_windows)
    y_morocco = targets(morocco_windows)
    y_tetouan = targets(tetouan_windows)
    portugal_baseline = baseline_predictions(portugal_windows)[
        selection["portugal_baseline"]
    ]
    morocco_baseline = baseline_predictions(morocco_windows)[
        selection["morocco_baseline"]
    ]
    tetouan_baseline_name = selection["portugal_baseline"]
    tetouan_baseline = baseline_predictions(tetouan_windows)[tetouan_baseline_name]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    name, model = load_selected_model(output, selection, device)
    raw_portugal = predict_selected(name, model, portugal_windows, args.batch_size)
    raw_morocco = predict_selected(name, model, morocco_windows, args.batch_size)
    raw_tetouan = predict_selected(name, model, tetouan_windows, args.batch_size)
    weight = float(selection["model_weight"])
    offsets = tuple(selection["conformal_offsets"])
    portugal_prediction = apply_conformal(
        np.sort(
            weight * raw_portugal + (1.0 - weight) * portugal_baseline[:, :, None],
            axis=2,
        ),
        offsets,
        portugal_windows,
    )
    morocco_prediction = apply_conformal(
        np.sort(
            weight * raw_morocco + (1.0 - weight) * morocco_baseline[:, :, None], axis=2
        ),
        offsets,
        morocco_windows,
    )
    tetouan_prediction = apply_conformal(
        np.sort(
            weight * raw_tetouan + (1.0 - weight) * tetouan_baseline[:, :, None],
            axis=2,
        ),
        offsets,
        tetouan_windows,
    )
    portugal_metrics = metrics(y_portugal, portugal_prediction, portugal_windows)
    portugal_baseline_metrics = metrics(y_portugal, portugal_baseline, portugal_windows)
    morocco_metrics = metrics(y_morocco, morocco_prediction, morocco_windows)
    morocco_baseline_metrics = metrics(y_morocco, morocco_baseline, morocco_windows)
    tetouan_metrics = metrics(y_tetouan, tetouan_prediction, tetouan_windows)
    tetouan_baseline_metrics = metrics(y_tetouan, tetouan_baseline, tetouan_windows)

    p_gate = protocol["production_gates"]["portugal_cold_2014_diagnostic"]
    m_gate = protocol["production_gates"]["morocco_cold_transfer_diagnostic"]
    t_gate = protocol["production_gates"]["tetouan_fresh_transfer"]
    del model
    torch.cuda.empty_cache()
    _, reloaded = load_selected_model(output, selection, device)
    reload_prediction = predict_selected(
        name, reloaded, portugal_windows[:1], args.batch_size
    )
    reload_max_abs_error = float(np.max(np.abs(raw_portugal[:1] - reload_prediction)))
    reload_relative_error = reload_max_abs_error / max(
        1.0, float(np.max(np.abs(raw_portugal[:1])))
    )
    del reloaded
    torch.cuda.empty_cache()
    diagnostic_gates = {
        "portugal_daily_mae": improvement(
            portugal_baseline_metrics["daily_mae"], portugal_metrics["daily_mae"]
        )
        >= p_gate["daily_mae_improvement_over_baseline_min"],
        "portugal_month_total_mae": improvement(
            portugal_baseline_metrics["month_total_mae"],
            portugal_metrics["month_total_mae"],
        )
        >= p_gate["month_total_mae_improvement_over_baseline_min"],
        "portugal_macro_r2": portugal_metrics["daily_macro_r2"]
        >= p_gate["daily_macro_r2_min"],
        "portugal_coverage": p_gate["interval_80_coverage_min"]
        <= portugal_metrics["interval_80_coverage"]
        <= p_gate["interval_80_coverage_max"],
        "morocco_macro_mase": improvement(
            morocco_baseline_metrics["macro_mase"], morocco_metrics["macro_mase"]
        )
        >= m_gate["macro_scaled_mae_improvement_over_baseline_min"],
        "morocco_macro_r2": morocco_metrics["daily_macro_r2"]
        >= m_gate["daily_macro_r2_min"],
        "morocco_coverage": m_gate["interval_80_coverage_min"]
        <= morocco_metrics["interval_80_coverage"]
        <= m_gate["interval_80_coverage_max"],
    }
    production_gates = {
        "tetouan_macro_mase": improvement(
            tetouan_baseline_metrics["macro_mase"], tetouan_metrics["macro_mase"]
        )
        >= t_gate["macro_scaled_mae_improvement_over_baseline_min"],
        "tetouan_macro_r2": tetouan_metrics["daily_macro_r2"]
        >= t_gate["daily_macro_r2_min"],
        "tetouan_coverage": t_gate["interval_80_coverage_min"]
        <= tetouan_metrics["interval_80_coverage"]
        <= t_gate["interval_80_coverage_max"],
        "finite_nonnegative": bool(
            np.isfinite(portugal_prediction).all()
            and np.isfinite(morocco_prediction).all()
            and np.isfinite(tetouan_prediction).all()
            and np.min(portugal_prediction) >= 0
            and np.min(morocco_prediction) >= 0
            and np.min(tetouan_prediction) >= 0
        ),
        "artifact_reload": reload_relative_error
        <= protocol["production_gates"]["artifact"][
            "reload_predictions_relative_error_max"
        ],
    }
    audit_payload = {
        "audit_version": 1,
        "architecture": name,
        "portugal": {
            "baseline": portugal_baseline_metrics,
            "candidate": portugal_metrics,
            "daily_mae_improvement": improvement(
                portugal_baseline_metrics["daily_mae"], portugal_metrics["daily_mae"]
            ),
            "month_total_mae_improvement": improvement(
                portugal_baseline_metrics["month_total_mae"],
                portugal_metrics["month_total_mae"],
            ),
            "windows": len(portugal_windows),
        },
        "morocco": {
            "baseline": morocco_baseline_metrics,
            "candidate": morocco_metrics,
            "macro_mase_improvement": improvement(
                morocco_baseline_metrics["macro_mase"], morocco_metrics["macro_mase"]
            ),
            "windows": len(morocco_windows),
        },
        "tetouan_fresh_transfer": {
            "baseline_name": tetouan_baseline_name,
            "baseline": tetouan_baseline_metrics,
            "candidate": tetouan_metrics,
            "macro_mase_improvement": improvement(
                tetouan_baseline_metrics["macro_mase"],
                tetouan_metrics["macro_mase"],
            ),
            "windows": len(tetouan_windows),
        },
        "diagnostic_gates": diagnostic_gates,
        "production_gates": production_gates,
        "artifact_reload_predictions_max_abs_error": reload_max_abs_error,
        "artifact_reload_predictions_relative_error": reload_relative_error,
        "promoted": all(production_gates.values()),
        "runtime_seconds": time.time() - start,
    }
    atomic_json(output / "audit.json", audit_payload)
    manifest = {
        "model_name": "month_production_v3",
        "status": (
            "production_eligible"
            if audit_payload["promoted"]
            else "research_only_failed_gate"
        ),
        "architecture": name,
        "horizon_days": HORIZON,
        "context_days": CONTEXT,
        "protocol_sha256": sha256(args.protocol.resolve()),
        "selection_sha256": sha256(output / "selection.json"),
        "audit_sha256": sha256(output / "audit.json"),
        "dependencies": {
            "python": "3.11",
            "torch": torch.__version__,
            "chronos_forecasting": "2.3.1",
            "neuralforecast": "3.1.8",
        },
        "promotion_note": "Backend artifacts are replaced only when all frozen gates pass.",
    }
    atomic_json(output / "manifest.json", manifest)
    print(json.dumps(audit_payload, indent=2), flush=True)
    return audit_payload


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    root = repository / "models" / "lcl_global_forecasting" / "month_production_v3"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("select", "audit", "all"))
    parser.add_argument("--prepared", type=Path, default=root / "data" / "prepared")
    parser.add_argument("--output", type=Path, default=root / "runs" / "production_v1")
    parser.add_argument("--protocol", type=Path, default=root / "protocol.json")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lora-batch-size", type=int, default=8)
    parser.add_argument("--lora-steps", type=int, nargs="+", default=[100, 300, 600])
    parser.add_argument("--supervised-steps", type=int, default=1000)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.phase in {"select", "all"}:
        select(parsed)
    if parsed.phase in {"audit", "all"}:
        audit(parsed)
