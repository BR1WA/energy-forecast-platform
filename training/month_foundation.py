"""Zero-shot foundation-model audit for the serious 30-day experiment.

The candidate is selected and calibrated on the fixed August--October 2013
validation period.  Only after that configuration is frozen is it evaluated
on the cold-start November 2013--January 2014 windows.  The script deliberately
keeps this audit separate from :mod:`training.month_serious`: the cold-start
holdout has already been reported for that earlier candidate, so this is a
second locked candidate rather than a claim that the holdout is globally new.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

try:
    from training.month_serious import (
        EVALUATION_ORIGIN_STRIDE,
        HORIZON_DAYS,
        LOOKBACK_DAYS,
        TEST_LAST_ORIGIN_DATE,
        TEST_START_DATE,
        TRAIN_END_DATE,
        VALIDATION_END_DATE,
        _window_components,
        causal_interpolate,
        date_index,
        valid_windows,
    )
    from training.month_strong import (
        ForecastMatrix,
        atomic_json,
        baseline_metrics,
        point_metrics,
        promotion_decision,
        sha256,
    )
except ModuleNotFoundError:  # direct ``python training/month_foundation.py``
    from month_serious import (
        EVALUATION_ORIGIN_STRIDE,
        HORIZON_DAYS,
        LOOKBACK_DAYS,
        TEST_LAST_ORIGIN_DATE,
        TEST_START_DATE,
        TRAIN_END_DATE,
        VALIDATION_END_DATE,
        _window_components,
        causal_interpolate,
        date_index,
        valid_windows,
    )
    from month_strong import (
        ForecastMatrix,
        atomic_json,
        baseline_metrics,
        point_metrics,
        promotion_decision,
        sha256,
    )


MODEL_ID = "amazon/chronos-bolt-small"
MODEL_REVISION = "772f3d25d38aec6d914c8949dab4462e2d46f5d8"
MODEL_SHA256 = "06a6a19bbe74bc10a9cd193bd4bf2bf638ae07f7e0d51653ae7ab8ea968a21dd"
CHRONOS_VERSION = "2.3.1"
QUANTILE_INDICES = (0, 4, 8)  # Chronos-Bolt emits q0.1, ..., q0.9.
GRID = np.linspace(0.0, 1.0, 21)


def _matrix(
    targets: np.ndarray,
    households: np.ndarray,
    origins: np.ndarray,
    baselines: dict[str, np.ndarray],
) -> ForecastMatrix:
    """Build the minimal ForecastMatrix needed by the shared metric contract."""

    n_windows = len(targets)
    flat_target = np.asarray(targets, dtype=np.float32).reshape(-1)
    point_households = np.repeat(np.asarray(households, dtype=np.int32), HORIZON_DAYS)
    return ForecastMatrix(
        point_features=np.empty((n_windows * HORIZON_DAYS, 0), dtype=np.float32),
        total_features=np.empty((n_windows, 0), dtype=np.float32),
        target_residual_z=np.zeros(n_windows * HORIZON_DAYS, dtype=np.float32),
        target_total_residual_z=np.zeros(n_windows, dtype=np.float32),
        target=flat_target,
        mean4=np.asarray(baselines["annual_recent_25_75"], dtype=np.float32).reshape(
            -1
        ),
        baselines={
            name: np.asarray(values, dtype=np.float32).reshape(-1)
            for name, values in baselines.items()
        },
        scales=np.ones(n_windows * HORIZON_DAYS, dtype=np.float32),
        point_steps=np.tile(np.arange(HORIZON_DAYS, dtype=np.int16), n_windows),
        point_households=point_households,
        window_households=np.asarray(households, dtype=np.int32),
        window_origins=np.asarray(origins, dtype=np.int32),
    )


def materialize(
    values: np.ndarray,
    dates: np.ndarray,
    actual_weather: np.ndarray,
    climate_weather: np.ndarray,
    calendar: np.ndarray,
    windows: list[tuple[int, int]],
) -> tuple[np.ndarray, np.ndarray, ForecastMatrix]:
    """Materialize causal contexts, targets, and mandatory strong baselines."""

    contexts = np.empty((len(windows), LOOKBACK_DAYS), dtype=np.float32)
    targets = np.empty((len(windows), HORIZON_DAYS), dtype=np.float32)
    households = np.empty(len(windows), dtype=np.int32)
    origins = np.empty(len(windows), dtype=np.int32)
    baseline_store: dict[str, np.ndarray] | None = None
    for index, (household, origin) in enumerate(windows):
        contexts[index] = causal_interpolate(
            np.asarray(values[household, origin - LOOKBACK_DAYS : origin])
        )
        component = _window_components(
            np.asarray(values[household]),
            dates,
            actual_weather,
            climate_weather,
            calendar,
            origin,
        )
        targets[index] = np.asarray(component["target"], dtype=np.float32)
        if baseline_store is None:
            baseline_store = {
                name: np.empty((len(windows), HORIZON_DAYS), dtype=np.float32)
                for name in component["baselines"]
            }
        for name, prediction in component["baselines"].items():
            baseline_store[name][index] = prediction
        households[index] = household
        origins[index] = origin
    assert baseline_store is not None
    return contexts, targets, _matrix(targets, households, origins, baseline_store)


@torch.inference_mode()
def forecast(
    pipeline: Any,
    contexts: np.ndarray,
    *,
    batch_size: int,
) -> np.ndarray:
    batches: list[np.ndarray] = []
    for start in range(0, len(contexts), batch_size):
        raw = pipeline.predict(
            torch.from_numpy(contexts[start : start + batch_size]),
            prediction_length=HORIZON_DAYS,
        )
        selected = raw[:, QUANTILE_INDICES, :].transpose(1, 2)
        batches.append(selected.float().cpu().numpy())
    return np.maximum(np.concatenate(batches), 0.0).astype(np.float32)


def _horizon_offsets(target: np.ndarray, center: np.ndarray) -> np.ndarray:
    return np.median(target - center, axis=0).astype(np.float32)


def _macro_daily_mae(
    matrix: ForecastMatrix,
    center: np.ndarray,
) -> float:
    # This scorer is called hundreds of times during validation selection.
    # ``point_metrics`` is the authoritative final metric implementation, but
    # repeatedly constructing one boolean mask per household is unnecessarily
    # expensive here.  Grouped sums are algebraically identical.
    households = np.asarray(matrix.point_households, dtype=np.int64)
    absolute_error = np.abs(
        np.asarray(center, dtype=np.float64).reshape(-1)
        - np.asarray(matrix.target, dtype=np.float64)
    )
    counts = np.bincount(households)
    sums = np.bincount(households, weights=absolute_error, minlength=len(counts))
    present = counts > 0
    return float(np.mean(sums[present] / counts[present]))


def select_daily(
    matrix: ForecastMatrix,
    target: np.ndarray,
    raw_quantiles: np.ndarray,
) -> dict[str, Any]:
    """Select baseline, Chronos weight, and horizon bias on validation only."""

    best: tuple[float, str, float, np.ndarray] | None = None
    median = raw_quantiles[:, :, 1]
    for baseline_name, flat_baseline in matrix.baselines.items():
        baseline = flat_baseline.reshape(-1, HORIZON_DAYS)
        for weight in GRID:
            uncalibrated = weight * median + (1.0 - weight) * baseline
            offsets = _horizon_offsets(target, uncalibrated)
            center = np.maximum(uncalibrated + offsets[None, :], 0.0)
            score = _macro_daily_mae(matrix, center)
            candidate = (score, baseline_name, float(weight), offsets)
            if best is None or candidate[0] < best[0] - 1e-12:
                best = candidate
    assert best is not None
    return {
        "validation_daily_macro_mae_kwh": best[0],
        "baseline": best[1],
        "chronos_weight": best[2],
        "horizon_offsets_kwh": best[3].tolist(),
    }


def daily_center(
    matrix: ForecastMatrix,
    raw_quantiles: np.ndarray,
    selection: dict[str, Any],
) -> np.ndarray:
    baseline = matrix.baselines[selection["baseline"]].reshape(-1, HORIZON_DAYS)
    weight = float(selection["chronos_weight"])
    offsets = np.asarray(selection["horizon_offsets_kwh"], dtype=np.float32)
    return np.maximum(
        weight * raw_quantiles[:, :, 1] + (1.0 - weight) * baseline + offsets,
        0.0,
    ).astype(np.float32)


def select_total(
    matrix: ForecastMatrix,
    target: np.ndarray,
    raw_quantiles: np.ndarray,
) -> dict[str, Any]:
    best: tuple[float, str, float, float] | None = None
    target_total = target.sum(axis=1)
    chronos_total = raw_quantiles[:, :, 1].sum(axis=1)
    for baseline_name, flat_baseline in matrix.baselines.items():
        baseline_total = flat_baseline.reshape(-1, HORIZON_DAYS).sum(axis=1)
        for weight in GRID:
            uncalibrated = weight * chronos_total + (1.0 - weight) * baseline_total
            offset = float(np.median(target_total - uncalibrated))
            prediction = np.maximum(uncalibrated + offset, 0.0)
            score = float(np.mean(np.abs(prediction - target_total)))
            candidate = (score, baseline_name, float(weight), offset)
            if best is None or candidate[0] < best[0] - 1e-12:
                best = candidate
    assert best is not None
    return {
        "validation_month_total_mae_kwh": best[0],
        "baseline": best[1],
        "chronos_weight": best[2],
        "offset_kwh": best[3],
    }


def total_center(
    matrix: ForecastMatrix,
    raw_quantiles: np.ndarray,
    selection: dict[str, Any],
) -> np.ndarray:
    baseline_total = (
        matrix.baselines[selection["baseline"]].reshape(-1, HORIZON_DAYS).sum(axis=1)
    )
    chronos_total = raw_quantiles[:, :, 1].sum(axis=1)
    weight = float(selection["chronos_weight"])
    return np.maximum(
        weight * chronos_total
        + (1.0 - weight) * baseline_total
        + float(selection["offset_kwh"]),
        0.0,
    ).astype(np.float32)


def select_reconciliation(
    matrix: ForecastMatrix,
    target: np.ndarray,
    daily: np.ndarray,
    total: np.ndarray,
) -> dict[str, float]:
    """Balance validation daily and total error against their best baselines."""

    baseline_scores = baseline_metrics(matrix)
    best_daily = min(float(v["daily_macro_mae_kwh"]) for v in baseline_scores.values())
    best_total = min(float(v["month_total_mae_kwh"]) for v in baseline_scores.values())
    target_total = target.sum(axis=1)
    daily_total = daily.sum(axis=1)
    best: tuple[float, float, float, float] | None = None
    for weight in GRID:
        reconciled_total = weight * total + (1.0 - weight) * daily_total
        reconciled_daily = np.maximum(
            daily + (reconciled_total - daily_total)[:, None] / HORIZON_DAYS,
            0.0,
        )
        daily_mae = _macro_daily_mae(matrix, reconciled_daily)
        total_mae = float(np.mean(np.abs(reconciled_total - target_total)))
        objective = daily_mae / best_daily + total_mae / best_total
        candidate = (objective, float(weight), daily_mae, total_mae)
        if best is None or candidate[0] < best[0] - 1e-12:
            best = candidate
    assert best is not None
    return {
        "total_head_weight": best[1],
        "validation_objective": best[0],
        "validation_daily_macro_mae_kwh": best[2],
        "validation_month_total_mae_kwh": best[3],
    }


def reconcile(
    daily: np.ndarray,
    total: np.ndarray,
    weight: float,
) -> tuple[np.ndarray, np.ndarray]:
    daily_total = daily.sum(axis=1)
    reconciled_total = weight * total + (1.0 - weight) * daily_total
    reconciled_daily = np.maximum(
        daily + (reconciled_total - daily_total)[:, None] / HORIZON_DAYS,
        0.0,
    )
    return reconciled_daily.astype(np.float32), reconciled_total.astype(np.float32)


def calibrate_intervals(
    target: np.ndarray,
    center: np.ndarray,
    raw_quantiles: np.ndarray,
) -> list[float]:
    lower_width = raw_quantiles[:, :, 1] - raw_quantiles[:, :, 0]
    upper_width = raw_quantiles[:, :, 2] - raw_quantiles[:, :, 1]
    expansion: list[float] = []
    for step in range(HORIZON_DAYS):
        conformity = np.maximum(
            center[:, step] - lower_width[:, step] - target[:, step],
            target[:, step] - center[:, step] - upper_width[:, step],
        )
        level = min(
            1.0,
            math.ceil((len(conformity) + 1) * 0.80) / len(conformity),
        )
        try:
            value = float(np.quantile(conformity, level, method="higher"))
        except TypeError:
            value = float(np.quantile(conformity, level, interpolation="higher"))
        expansion.append(max(value, 0.0))
    return expansion


def quantiles_from_center(
    center: np.ndarray,
    raw_quantiles: np.ndarray,
    expansion: list[float],
) -> np.ndarray:
    lower_width = raw_quantiles[:, :, 1] - raw_quantiles[:, :, 0]
    upper_width = raw_quantiles[:, :, 2] - raw_quantiles[:, :, 1]
    extra = np.asarray(expansion, dtype=np.float32)[None, :]
    return np.stack(
        [
            np.maximum(center - lower_width - extra, 0.0),
            center,
            np.maximum(center + upper_width + extra, 0.0),
        ],
        axis=2,
    ).astype(np.float32)


def evaluate(
    matrix: ForecastMatrix,
    target: np.ndarray,
    raw_quantiles: np.ndarray,
    daily_selection: dict[str, Any],
    total_selection: dict[str, Any],
    reconciliation: dict[str, float],
    interval_expansion: list[float],
) -> dict[str, Any]:
    raw = point_metrics(
        matrix,
        raw_quantiles[:, :, 1].reshape(-1),
        raw_quantiles.reshape(-1, 3),
    )
    daily = daily_center(matrix, raw_quantiles, daily_selection)
    total = total_center(matrix, raw_quantiles, total_selection)
    daily, total = reconcile(daily, total, reconciliation["total_head_weight"])
    quantiles = quantiles_from_center(daily, raw_quantiles, interval_expansion)
    candidate = point_metrics(matrix, daily.reshape(-1), quantiles.reshape(-1, 3))
    target_total = target.sum(axis=1)
    candidate.update(
        {
            "month_total_central_80_coverage_percent": float(
                100.0
                * np.mean(
                    (target_total >= quantiles[:, :, 0].sum(axis=1))
                    & (target_total <= quantiles[:, :, 2].sum(axis=1))
                )
            ),
            "month_total_central_80_mean_width_kwh": float(
                np.mean(quantiles[:, :, 2].sum(axis=1) - quantiles[:, :, 0].sum(axis=1))
            ),
            "reconciled_month_total_mae_kwh": float(
                np.mean(np.abs(total - target_total))
            ),
        }
    )
    return {
        "raw_chronos": raw,
        "candidate": candidate,
        "baselines": baseline_metrics(matrix),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    try:
        import importlib.metadata
        from chronos import BaseChronosPipeline
    except ImportError as error:
        raise RuntimeError(
            f"Install chronos-forecasting=={CHRONOS_VERSION} before running this audit."
        ) from error

    installed_version = importlib.metadata.version("chronos-forecasting")
    if installed_version != CHRONOS_VERSION:
        raise RuntimeError(
            f"Expected chronos-forecasting=={CHRONOS_VERSION}, got {installed_version}."
        )
    if args.model_file is not None and args.model_file.exists():
        local_hash = sha256(args.model_file)
        if local_hash != MODEL_SHA256:
            raise RuntimeError(
                f"Chronos-Bolt checkpoint checksum mismatch: {local_hash}."
            )

    data = args.data.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    values = np.load(data / "daily_kwh.npy", mmap_mode="r")
    dates = np.load(data / "dates.npy")
    actual_weather = np.load(data / "actual_weather.npy", mmap_mode="r")
    climate_weather = np.load(data / "climatology_weather.npy", mmap_mode="r")
    calendar = np.load(data / "calendar.npy", mmap_mode="r")
    known = np.load(data / "known_households.npy")
    cold = np.load(data / "cold_households.npy")

    validation_origins = np.arange(
        date_index(dates, TRAIN_END_DATE),
        date_index(dates, VALIDATION_END_DATE) + 1,
        EVALUATION_ORIGIN_STRIDE,
        dtype=np.int32,
    )
    test_origins = np.arange(
        date_index(dates, TEST_START_DATE),
        date_index(dates, TEST_LAST_ORIGIN_DATE) + 1,
        EVALUATION_ORIGIN_STRIDE,
        dtype=np.int32,
    )
    validation_windows = valid_windows(values, known, validation_origins)
    print(f"materializing validation windows={len(validation_windows)}", flush=True)
    validation_context, validation_target, validation_matrix = materialize(
        values,
        dates,
        actual_weather,
        climate_weather,
        calendar,
        validation_windows,
    )

    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    pipeline = BaseChronosPipeline.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        device_map=device,
        dtype=dtype,
    )
    print(f"forecasting validation on {device}", flush=True)
    validation_raw = forecast(pipeline, validation_context, batch_size=args.batch_size)
    daily_selection = select_daily(validation_matrix, validation_target, validation_raw)
    total_selection = select_total(validation_matrix, validation_target, validation_raw)
    validation_daily = daily_center(validation_matrix, validation_raw, daily_selection)
    validation_total = total_center(validation_matrix, validation_raw, total_selection)
    reconciliation = select_reconciliation(
        validation_matrix,
        validation_target,
        validation_daily,
        validation_total,
    )
    validation_center, _ = reconcile(
        validation_daily,
        validation_total,
        reconciliation["total_head_weight"],
    )
    interval_expansion = calibrate_intervals(
        validation_target, validation_center, validation_raw
    )
    selection = {
        "daily": daily_selection,
        "month_total": total_selection,
        "reconciliation": reconciliation,
        "daily_interval_expansion_kwh": interval_expansion,
    }
    atomic_json(output / "frozen_selection.json", selection)

    validation_evaluation = evaluate(
        validation_matrix,
        validation_target,
        validation_raw,
        daily_selection,
        total_selection,
        reconciliation,
        interval_expansion,
    )
    del validation_context, validation_raw
    if device == "cuda":
        torch.cuda.empty_cache()

    # The cold-start targets are not materialized or forecast until all
    # foundation-model choices above have been frozen to disk.
    cold_windows = valid_windows(values, cold, test_origins)
    print(f"materializing cold-start test windows={len(cold_windows)}", flush=True)
    cold_context, cold_target, cold_matrix = materialize(
        values,
        dates,
        actual_weather,
        climate_weather,
        calendar,
        cold_windows,
    )
    print("forecasting locked cold-start candidate", flush=True)
    cold_raw = forecast(pipeline, cold_context, batch_size=args.batch_size)
    cold_evaluation = evaluate(
        cold_matrix,
        cold_target,
        cold_raw,
        daily_selection,
        total_selection,
        reconciliation,
        interval_expansion,
    )
    promotion = promotion_decision(
        cold_evaluation["candidate"], cold_evaluation["baselines"]
    )

    payload: dict[str, Any] = {
        "status": "success",
        "experiment": "month_foundation_v1",
        "promoted": bool(promotion["promoted"]),
        "promotion": promotion,
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "model_sha256": MODEL_SHA256,
            "chronos_forecasting_version": installed_version,
            "parameters": 47_700_000,
            "mode": "zero_shot_direct_multi_step_quantiles",
            "context_days": LOOKBACK_DAYS,
            "prediction_days": HORIZON_DAYS,
            "realized_future_weather_used": False,
        },
        "protocol": {
            "selection_period": "2013-08-01 through 2013-10-31 weekly origins",
            "cold_start_period": "2013-11-01 through 2014-01-29 weekly origins",
            "cold_start_households_seen_in_training": False,
            "test_access_order": "foundation selection frozen before test materialization",
            "global_holdout_caveat": (
                "This same aggregate cold-start holdout was previously opened for "
                "month_serious_v2; this is a second locked candidate, not a globally "
                "pristine holdout."
            ),
        },
        "windows": {
            "validation": len(validation_windows),
            "cold_start_test": len(cold_windows),
        },
        "selection": selection,
        "evaluation": {
            "validation": validation_evaluation,
            "cold_start_test": cold_evaluation,
        },
        "device": device,
        "training_seconds": 0.0,
        "evaluation_seconds": time.time() - started,
        "limitations": [
            "Chronos-Bolt is zero-shot here; no London-specific weights were trained.",
            "Chronos-Bolt does not consume the future ERA5 climatology covariates.",
            "The official meter release spans about 27 months, not a full unseen year.",
            "The test period is a second candidate audit after the earlier serious model.",
        ],
    }
    if args.model_file is not None and args.model_file.exists():
        payload["model"]["local_file_sha256"] = sha256(args.model_file)
        payload["model"]["local_file_bytes"] = args.model_file.stat().st_size
    atomic_json(output / "metrics.json", payload)
    print(json.dumps(cold_evaluation["candidate"], indent=2), flush=True)
    print(json.dumps(promotion, indent=2), flush=True)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("models/lcl_global_forecasting/month_serious_v2/data/prepared"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "models/lcl_global_forecasting/month_serious_v2/runs/foundation_v1"
        ),
    )
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--model-file", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
