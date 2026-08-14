"""Locked Chronos-2/covariate challenge for the 30-day London experiment.

This extends ``month_foundation_v1`` with Amazon Chronos-2 and the known-future
ERA5 climatology/calendar channels.  Source models, blend weights, strong
baseline blending, horizon offsets, reconciliation, and interval calibration
are all selected on the fixed validation period before cold-start test windows
are materialized.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

try:
    from training.month_foundation import (
        CHRONOS_VERSION,
        MODEL_ID as BOLT_MODEL_ID,
        MODEL_REVISION as BOLT_REVISION,
        MODEL_SHA256 as BOLT_SHA256,
        calibrate_intervals,
        daily_center,
        forecast as forecast_bolt,
        materialize,
        quantiles_from_center,
        reconcile,
        select_daily,
        select_reconciliation,
        select_total,
        total_center,
    )
    from training.month_serious import (
        EVALUATION_ORIGIN_STRIDE,
        HORIZON_DAYS,
        TEST_LAST_ORIGIN_DATE,
        TEST_START_DATE,
        TRAIN_END_DATE,
        VALIDATION_END_DATE,
        causal_interpolate,
        date_index,
        valid_windows,
    )
    from training.month_strong import (
        atomic_json,
        baseline_metrics,
        point_metrics,
        promotion_decision,
        sha256,
    )
except ModuleNotFoundError:  # direct execution
    from month_foundation import (
        CHRONOS_VERSION,
        MODEL_ID as BOLT_MODEL_ID,
        MODEL_REVISION as BOLT_REVISION,
        MODEL_SHA256 as BOLT_SHA256,
        calibrate_intervals,
        daily_center,
        forecast as forecast_bolt,
        materialize,
        quantiles_from_center,
        reconcile,
        select_daily,
        select_reconciliation,
        select_total,
        total_center,
    )
    from month_serious import (
        EVALUATION_ORIGIN_STRIDE,
        HORIZON_DAYS,
        TEST_LAST_ORIGIN_DATE,
        TEST_START_DATE,
        TRAIN_END_DATE,
        VALIDATION_END_DATE,
        causal_interpolate,
        date_index,
        valid_windows,
    )
    from month_strong import (
        atomic_json,
        baseline_metrics,
        point_metrics,
        promotion_decision,
        sha256,
    )


CHRONOS2_MODEL_ID = "amazon/chronos-2"
CHRONOS2_REVISION = "29ec3766d36d6f73f0696f85560a422f50e8498c"
CHRONOS2_SHA256 = "ddcda3c7508bf2528087723e98a20707cc04b7f370ae275a9fd88078ddba4f42"
WEATHER_NAMES = (
    "temperature_mean",
    "temperature_min",
    "temperature_max",
    "apparent_temperature_mean",
    "precipitation_sum",
    "sunshine_duration",
    "wind_speed_max",
    "shortwave_radiation_sum",
)
CALENDAR_NAMES = (
    "weekday_sin",
    "weekday_cos",
    "year_sin",
    "year_cos",
    "is_workday",
    "is_holiday",
    "is_month_start",
    "is_month_end",
)


@torch.inference_mode()
def forecast_chronos2(
    pipeline: Any,
    values: np.ndarray,
    actual_weather: np.ndarray,
    climate_weather: np.ndarray,
    calendar: np.ndarray,
    windows: list[tuple[int, int]],
    *,
    batch_size: int,
    covariates: bool,
) -> np.ndarray:
    """Forecast in bounded batches without retaining duplicated covariates."""

    predictions: list[np.ndarray] = []
    for start in range(0, len(windows), batch_size):
        batch = windows[start : start + batch_size]
        if covariates:
            inputs: Any = []
            for household, origin in batch:
                past: dict[str, np.ndarray] = {}
                future: dict[str, np.ndarray] = {}
                for feature, name in enumerate(WEATHER_NAMES):
                    past[name] = np.asarray(
                        actual_weather[origin - 365 : origin, feature],
                        dtype=np.float32,
                    )
                    future[name] = np.asarray(
                        climate_weather[origin : origin + HORIZON_DAYS, feature],
                        dtype=np.float32,
                    )
                for feature, name in enumerate(CALENDAR_NAMES):
                    past[name] = np.asarray(
                        calendar[origin - 365 : origin, feature], dtype=np.float32
                    )
                    future[name] = np.asarray(
                        calendar[origin : origin + HORIZON_DAYS, feature],
                        dtype=np.float32,
                    )
                inputs.append(
                    {
                        "target": causal_interpolate(
                            np.asarray(values[household, origin - 365 : origin])
                        ),
                        "past_covariates": past,
                        "future_covariates": future,
                    }
                )
        else:
            inputs = np.stack(
                [
                    causal_interpolate(
                        np.asarray(values[household, origin - 365 : origin])
                    )
                    for household, origin in batch
                ]
            )[:, None, :]
        quantiles, _ = pipeline.predict_quantiles(
            inputs,
            prediction_length=HORIZON_DAYS,
            quantile_levels=[0.1, 0.5, 0.9],
            batch_size=batch_size,
            cross_learning=False,
        )
        predictions.append(
            np.stack([item[0].float().cpu().numpy() for item in quantiles])
        )
    return np.maximum(np.concatenate(predictions), 0.0).astype(np.float32)


def candidate_sources(
    bolt: np.ndarray,
    univariate: np.ndarray,
    covariate: np.ndarray,
) -> dict[str, np.ndarray]:
    sources = {
        "chronos_bolt_small": bolt,
        "chronos2_univariate": univariate,
        "chronos2_covariates": covariate,
    }
    for weight in (0.25, 0.50, 0.75):
        label = int(weight * 100)
        sources[f"chronos2_cov{label}_bolt{100-label}"] = np.sort(
            weight * covariate + (1.0 - weight) * bolt, axis=2
        )
        sources[f"chronos2_cov{label}_univariate{100-label}"] = np.sort(
            weight * covariate + (1.0 - weight) * univariate, axis=2
        )
    return sources


def select_sources(
    matrix: Any,
    target: np.ndarray,
    sources: dict[str, np.ndarray],
) -> dict[str, Any]:
    daily_runs: dict[str, dict[str, Any]] = {}
    total_runs: dict[str, dict[str, Any]] = {}
    for name, raw in sources.items():
        daily_runs[name] = select_daily(matrix, target, raw)
        total_runs[name] = select_total(matrix, target, raw)
    daily_name = min(
        daily_runs,
        key=lambda name: float(daily_runs[name]["validation_daily_macro_mae_kwh"]),
    )
    total_name = min(
        total_runs,
        key=lambda name: float(total_runs[name]["validation_month_total_mae_kwh"]),
    )
    return {
        "daily_source": daily_name,
        "daily": daily_runs[daily_name],
        "month_total_source": total_name,
        "month_total": total_runs[total_name],
        "source_validation": {
            name: {
                "daily_macro_mae_kwh": float(
                    daily_runs[name]["validation_daily_macro_mae_kwh"]
                ),
                "month_total_mae_kwh": float(
                    total_runs[name]["validation_month_total_mae_kwh"]
                ),
            }
            for name in sources
        },
    }


def evaluate(
    matrix: Any,
    target: np.ndarray,
    daily_raw: np.ndarray,
    total_raw: np.ndarray,
    selection: dict[str, Any],
) -> dict[str, Any]:
    daily = daily_center(matrix, daily_raw, selection["daily"])
    total = total_center(matrix, total_raw, selection["month_total"])
    daily, reconciled_total = reconcile(
        daily, total, selection["reconciliation"]["total_head_weight"]
    )
    quantiles = quantiles_from_center(
        daily, daily_raw, selection["daily_interval_expansion_kwh"]
    )
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
                np.mean(np.abs(reconciled_total - target_total))
            ),
        }
    )
    return {"candidate": candidate, "baselines": baseline_metrics(matrix)}


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    import importlib.metadata
    from chronos import BaseChronosPipeline, Chronos2Pipeline

    installed = importlib.metadata.version("chronos-forecasting")
    if installed != CHRONOS_VERSION:
        raise RuntimeError(
            f"Expected chronos-forecasting=={CHRONOS_VERSION}, got {installed}."
        )
    for label, path, expected in (
        ("Chronos-Bolt", args.bolt_model_file, BOLT_SHA256),
        ("Chronos-2", args.chronos2_model_file, CHRONOS2_SHA256),
    ):
        if path is not None and path.exists():
            local_hash = sha256(path)
            if local_hash != expected:
                raise RuntimeError(
                    f"{label} checkpoint checksum mismatch: {local_hash}."
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
        values, dates, actual_weather, climate_weather, calendar, validation_windows
    )
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    bolt_pipeline = BaseChronosPipeline.from_pretrained(
        BOLT_MODEL_ID,
        revision=BOLT_REVISION,
        device_map=device,
        dtype=dtype,
    )
    chronos2_pipeline = Chronos2Pipeline.from_pretrained(
        CHRONOS2_MODEL_ID,
        revision=CHRONOS2_REVISION,
        device_map=device,
        dtype=dtype,
    )
    print("forecasting validation: Bolt, Chronos-2, Chronos-2+covariates", flush=True)
    validation_bolt = forecast_bolt(
        bolt_pipeline, validation_context, batch_size=args.batch_size
    )
    validation_univariate = forecast_chronos2(
        chronos2_pipeline,
        values,
        actual_weather,
        climate_weather,
        calendar,
        validation_windows,
        batch_size=args.batch_size,
        covariates=False,
    )
    validation_covariate = forecast_chronos2(
        chronos2_pipeline,
        values,
        actual_weather,
        climate_weather,
        calendar,
        validation_windows,
        batch_size=args.batch_size,
        covariates=True,
    )
    validation_sources = candidate_sources(
        validation_bolt, validation_univariate, validation_covariate
    )
    selection = select_sources(validation_matrix, validation_target, validation_sources)
    validation_daily_raw = validation_sources[selection["daily_source"]]
    validation_total_raw = validation_sources[selection["month_total_source"]]
    validation_daily = daily_center(
        validation_matrix, validation_daily_raw, selection["daily"]
    )
    validation_total = total_center(
        validation_matrix, validation_total_raw, selection["month_total"]
    )
    selection["reconciliation"] = select_reconciliation(
        validation_matrix,
        validation_target,
        validation_daily,
        validation_total,
    )
    validation_center, _ = reconcile(
        validation_daily,
        validation_total,
        selection["reconciliation"]["total_head_weight"],
    )
    selection["daily_interval_expansion_kwh"] = calibrate_intervals(
        validation_target, validation_center, validation_daily_raw
    )
    atomic_json(output / "frozen_selection.json", selection)
    validation_evaluation = evaluate(
        validation_matrix,
        validation_target,
        validation_daily_raw,
        validation_total_raw,
        selection,
    )

    # Nothing below is built until the full design is frozen above.
    cold_windows = valid_windows(values, cold, test_origins)
    print(f"materializing cold-start test windows={len(cold_windows)}", flush=True)
    cold_context, cold_target, cold_matrix = materialize(
        values, dates, actual_weather, climate_weather, calendar, cold_windows
    )
    print("forecasting locked cold-start candidate", flush=True)
    cold_bolt = forecast_bolt(bolt_pipeline, cold_context, batch_size=args.batch_size)
    cold_univariate = forecast_chronos2(
        chronos2_pipeline,
        values,
        actual_weather,
        climate_weather,
        calendar,
        cold_windows,
        batch_size=args.batch_size,
        covariates=False,
    )
    cold_covariate = forecast_chronos2(
        chronos2_pipeline,
        values,
        actual_weather,
        climate_weather,
        calendar,
        cold_windows,
        batch_size=args.batch_size,
        covariates=True,
    )
    cold_sources = candidate_sources(cold_bolt, cold_univariate, cold_covariate)
    cold_evaluation = evaluate(
        cold_matrix,
        cold_target,
        cold_sources[selection["daily_source"]],
        cold_sources[selection["month_total_source"]],
        selection,
    )
    promotion = promotion_decision(
        cold_evaluation["candidate"], cold_evaluation["baselines"]
    )
    models: dict[str, Any] = {
        "chronos_bolt_small": {
            "id": BOLT_MODEL_ID,
            "revision": BOLT_REVISION,
            "sha256": BOLT_SHA256,
            "parameters": 47_700_000,
        },
        "chronos2": {
            "id": CHRONOS2_MODEL_ID,
            "revision": CHRONOS2_REVISION,
            "sha256": CHRONOS2_SHA256,
            "parameters": 120_000_000,
        },
        "chronos_forecasting_version": installed,
    }
    for label, path in (
        ("bolt_local", args.bolt_model_file),
        ("chronos2_local", args.chronos2_model_file),
    ):
        if path is not None and path.exists():
            models[label] = {
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
    payload = {
        "status": "success",
        "experiment": "month_foundation_chronos2_v1",
        "promoted": bool(promotion["promoted"]),
        "promotion": promotion,
        "models": models,
        "protocol": {
            "lookback_days": 365,
            "horizon_days": HORIZON_DAYS,
            "selection_period": "2013-08-01 through 2013-10-31 weekly origins",
            "cold_start_period": "2013-11-01 through 2014-01-29 weekly origins",
            "realized_future_weather_used": False,
            "future_weather": "1991-2010 ERA5 day-of-year climatology",
            "cross_learning": False,
            "selection_frozen_before_test_materialization": True,
            "global_holdout_caveat": (
                "This aggregate holdout was previously opened for earlier candidates; "
                "the Chronos-2 design itself was frozen on validation before its test run."
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
            "Foundation weights are zero-shot; London-specific learning is limited to validation calibration and blending.",
            "ERA5 day-of-year climatology cannot represent actual future weather anomalies.",
            "The official meter release spans about 27 months, not a complete unseen year.",
            "The aggregate cold-start holdout was opened by prior candidates in this research sequence.",
        ],
    }
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
        default=Path("models/lcl_global_forecasting/month_serious_v2/runs/chronos2_v1"),
    )
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--bolt-model-file", type=Path)
    parser.add_argument("--chronos2-model-file", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
