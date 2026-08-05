"""Evaluate frozen LCL TFT checkpoints with production rolling normalization.

This is an inference-only evidence generator. It reconstructs the exact frozen
cold-start windows from preserved local arrays, keeps the checkpoints fixed,
and applies the production 336-hour rolling-window z-score plus the production
inverse transform, non-negative clamp, and per-step quantile ordering.

It never writes to the experiment directory and never changes the frozen
research metrics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import torch


WORKSPACE = Path(__file__).resolve().parents[2]
BACKEND = WORKSPACE / "backend"
EXPERIMENT = WORKSPACE / "models" / "lcl_global_forecasting" / "full_selected_v1"
DATA = EXPERIMENT / "data"
EVIDENCE = WORKSPACE / "report" / "evidence"
PRODUCTION_SERVICE = BACKEND / "app" / "services" / "product_forecast_service.py"
START = datetime(2013, 1, 1)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
TASKS = {
    "day_24h": {"horizon": 24, "lookback": 336, "seasonal_period": 168},
    "week_168h": {"horizon": 168, "lookback": 336, "seasonal_period": 168},
}

sys.path.insert(0, str(BACKEND))
from app.ml.global_tft import GlobalTFT  # noqa: E402
from app.services.product_forecast_service import (  # noqa: E402
    PreparedForecastInput,
    ProductForecastService,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to write empty evidence: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pinball(target: np.ndarray, prediction: np.ndarray, quantile: float) -> np.ndarray:
    error = target - prediction
    return np.maximum((quantile - 1.0) * error, quantile * error)


def reconstruct_pairs(
    values: np.ndarray,
    cold_households: np.ndarray,
    val_end: int,
    lookback: int,
    horizon: int,
    seasonal_period: int,
) -> tuple[list[tuple[int, int]], np.ndarray]:
    origins = np.unique(
        np.linspace(
            max(val_end, lookback),
            values.shape[1] - horizon,
            num=24,
            dtype=np.int64,
        )
    )
    pairs: list[tuple[int, int]] = []
    for raw_household in cold_households:
        household = int(raw_household)
        row = values[household]
        for raw_origin in origins:
            origin = int(raw_origin)
            required = np.asarray(row[origin - lookback : origin + horizon])
            seasonal = np.asarray(row[origin - seasonal_period : origin])
            if (
                required.size == lookback + horizon
                and np.isfinite(required).all()
                and seasonal.size == seasonal_period
                and np.isfinite(seasonal).all()
            ):
                pairs.append((household, origin))
    if not pairs:
        raise RuntimeError("No exact frozen cold-start evaluation windows were reconstructed.")
    return pairs, origins


def serving_inverse(
    standardized_quantiles: np.ndarray,
    means: np.ndarray,
    standard_deviations: np.ndarray,
) -> np.ndarray:
    """Vectorized equivalent of ProductForecastService._predict_tft output handling."""
    output = np.maximum(
        0.0,
        standardized_quantiles
        * standard_deviations[:, None, None]
        + means[:, None, None],
    )
    output.sort(axis=2)
    return output


class PreservedCalendarService(ProductForecastService):
    """Use preserved calendar rows while executing the exact production method."""

    def __init__(self, calendar: np.ndarray) -> None:
        super().__init__(forecast_168h_enabled=True)
        self._preserved_calendar = calendar

    def _calendar(self, timestamps, site, country):  # noqa: ANN001, ARG002
        indices = [
            int((timestamp - START).total_seconds() // 3600)
            for timestamp in timestamps
        ]
        return np.asarray(self._preserved_calendar[indices], dtype=np.float32)


def exact_method_parity(
    task: str,
    pair: tuple[int, int],
    values: np.ndarray,
    calendar: np.ndarray,
    vectorized_prediction: np.ndarray,
) -> dict:
    horizon = TASKS[task]["horizon"]
    lookback = TASKS[task]["lookback"]
    household, origin = pair
    history = np.asarray(values[household, origin - lookback : origin], dtype=np.float32)
    mean = float(history.mean())
    standard_deviation = max(float(history.std()), 1e-6)
    prepared = PreparedForecastInput(
        site=object(),
        origin=START + timedelta(hours=origin),
        values=history,
    )
    service = PreservedCalendarService(calendar)
    q10, q50, q90 = service._predict_tft(
        prepared,
        "United Kingdom",
        mean,
        standard_deviation,
        horizon,
    )
    exact = np.stack([q10, q50, q90], axis=1)
    maximum_difference = float(np.max(np.abs(exact - vectorized_prediction)))
    parity_tolerance = 1e-3
    if maximum_difference > parity_tolerance:
        raise RuntimeError(
            f"{task}: vectorized evaluation diverged from the exact production method "
            f"by {maximum_difference:.8f} kWh"
        )
    return {
        "household_index": household,
        "origin_index": origin,
        "maximum_absolute_difference_kwh": maximum_difference,
        "tolerance_kwh": parity_tolerance,
        "comparison": "GPU batched evaluation versus CPU production method",
        "passed": True,
    }


def summarize(
    predictions: np.ndarray,
    targets: np.ndarray,
    baselines: np.ndarray,
    households: np.ndarray,
    origins: np.ndarray,
) -> tuple[dict, list[dict]]:
    median = predictions[:, :, 1]
    household_rows: list[dict] = []
    by_household: dict[int, list[int]] = defaultdict(list)
    for row_index, household in enumerate(households):
        by_household[int(household)].append(row_index)

    total_squared_error = 0.0
    total_target_sum = 0.0
    total_target_squared = 0.0
    total_count = 0
    for household in sorted(by_household):
        indices = np.asarray(by_household[household], dtype=np.int64)
        actual = targets[indices]
        forecast = median[indices]
        baseline = baselines[indices]
        error = forecast - actual
        count = int(actual.size)
        squared_error = float(np.square(error).sum())
        target_sum = float(actual.sum())
        target_squared = float(np.square(actual).sum())
        target_sst = target_squared - target_sum**2 / max(count, 1)
        mae = float(np.abs(error).mean())
        baseline_mae = float(np.abs(baseline - actual).mean())
        household_rows.append(
            {
                "household_index": household,
                "evaluation_windows": len(indices),
                "forecast_points": count,
                "mae_kwh": mae,
                "rmse_kwh": float(np.sqrt(squared_error / count)),
                "bias_kwh": float(error.mean()),
                "r2": float(1.0 - squared_error / target_sst) if target_sst > 1e-12 else "",
                "seasonal_naive_mae_kwh": baseline_mae,
                "beats_seasonal_naive": int(mae < baseline_mae),
            }
        )
        total_squared_error += squared_error
        total_target_sum += target_sum
        total_target_squared += target_squared
        total_count += count

    household_mae = np.asarray([row["mae_kwh"] for row in household_rows], dtype=np.float64)
    household_rmse = np.asarray([row["rmse_kwh"] for row in household_rows], dtype=np.float64)
    household_bias = np.asarray([row["bias_kwh"] for row in household_rows], dtype=np.float64)
    household_r2 = np.asarray(
        [row["r2"] for row in household_rows if row["r2"] != ""], dtype=np.float64
    )
    household_baseline = np.asarray(
        [row["seasonal_naive_mae_kwh"] for row in household_rows], dtype=np.float64
    )
    wins = int(sum(row["beats_seasonal_naive"] for row in household_rows))
    global_sst = total_target_squared - total_target_sum**2 / max(total_count, 1)
    crossing = (predictions[:, :, 0] > predictions[:, :, 1]) | (
        predictions[:, :, 1] > predictions[:, :, 2]
    )

    summary = {
        "evaluated_households": len(household_rows),
        "evaluation_windows": len(households),
        "forecast_points": int(targets.size),
        "macro_mae_kwh": float(household_mae.mean()),
        "median_household_mae_kwh": float(np.median(household_mae)),
        "p90_household_mae_kwh": float(np.percentile(household_mae, 90)),
        "macro_rmse_kwh": float(household_rmse.mean()),
        "macro_bias_kwh": float(household_bias.mean()),
        "macro_r2": float(np.nanmean(household_r2)),
        "global_r2": float(1.0 - total_squared_error / max(global_sst, 1e-12)),
        "seasonal_naive_macro_mae_kwh": float(household_baseline.mean()),
        "households_beating_seasonal_count": wins,
        "households_beating_seasonal_percent": float(100.0 * wins / len(household_rows)),
        "q10_pinball_kwh": float(pinball(targets, predictions[:, :, 0], 0.1).mean()),
        "q50_pinball_kwh": float(pinball(targets, predictions[:, :, 1], 0.5).mean()),
        "q90_pinball_kwh": float(pinball(targets, predictions[:, :, 2], 0.9).mean()),
        "central_80_empirical_coverage_percent": float(
            100.0
            * np.mean(
                (targets >= predictions[:, :, 0])
                & (targets <= predictions[:, :, 2])
            )
        ),
        "central_80_mean_width_kwh": float(
            (predictions[:, :, 2] - predictions[:, :, 0]).mean()
        ),
        "quantile_crossing_rate_percent": float(100.0 * crossing.mean()),
        "first_origin_index": int(origins.min()),
        "last_origin_index": int(origins.max()),
    }
    return summary, household_rows


def evaluate_task(
    task: str,
    values: np.ndarray,
    calendar: np.ndarray,
    cold_households: np.ndarray,
    val_end: int,
    batch_size: int = 128,
) -> dict:
    config = TASKS[task]
    horizon = config["horizon"]
    lookback = config["lookback"]
    period = config["seasonal_period"]
    pairs, fixed_origins = reconstruct_pairs(
        values, cold_households, val_end, lookback, horizon, period
    )

    checkpoint_path = EXPERIMENT / "runs" / "global_tft" / task / "best.pt"
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE, weights_only=True)
    model = GlobalTFT().to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()

    prediction_rows: list[np.ndarray] = []
    target_rows: list[np.ndarray] = []
    baseline_rows: list[np.ndarray] = []
    household_rows: list[int] = []
    origin_rows: list[int] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(pairs), batch_size):
            batch_pairs = pairs[offset : offset + batch_size]
            histories = np.stack(
                [
                    np.asarray(values[household, origin - lookback : origin], dtype=np.float32)
                    for household, origin in batch_pairs
                ]
            )
            means = histories.mean(axis=1).astype(np.float32)
            standard_deviations = histories.std(axis=1).astype(np.float32)
            standard_deviations = np.maximum(standard_deviations, np.float32(1e-6))
            normalized = (
                (histories - means[:, None]) / standard_deviations[:, None]
            ).astype(np.float32)
            past_calendar = np.stack(
                [
                    np.asarray(calendar[origin - lookback : origin], dtype=np.float32)
                    for _, origin in batch_pairs
                ]
            )
            future_calendar = np.stack(
                [
                    np.asarray(calendar[origin : origin + horizon], dtype=np.float32)
                    for _, origin in batch_pairs
                ]
            )
            output = model(
                {
                    "x": torch.from_numpy(normalized[:, :, None]).to(DEVICE),
                    "x_calendar": torch.from_numpy(past_calendar).to(DEVICE),
                    "y_calendar": torch.from_numpy(future_calendar).to(DEVICE),
                }
            )["quantiles"].float().cpu().numpy()
            prediction_rows.append(serving_inverse(output, means, standard_deviations))
            targets = np.stack(
                [
                    np.asarray(values[household, origin : origin + horizon], dtype=np.float32)
                    for household, origin in batch_pairs
                ]
            )
            baselines = np.stack(
                [
                    np.asarray(
                        values[household, origin - period : origin], dtype=np.float32
                    )[np.arange(horizon) % period]
                    for household, origin in batch_pairs
                ]
            )
            target_rows.append(targets)
            baseline_rows.append(baselines)
            household_rows.extend(household for household, _ in batch_pairs)
            origin_rows.extend(origin for _, origin in batch_pairs)
    elapsed = time.perf_counter() - started

    predictions = np.concatenate(prediction_rows).astype(np.float64)
    targets = np.concatenate(target_rows).astype(np.float64)
    baselines = np.concatenate(baseline_rows).astype(np.float64)
    households = np.asarray(household_rows, dtype=np.int64)
    origins = np.asarray(origin_rows, dtype=np.int64)
    summary, per_household = summarize(
        predictions, targets, baselines, households, origins
    )
    parity = exact_method_parity(
        task, pairs[0], values, calendar, predictions[0]
    )

    household_path = EVIDENCE / f"lcl_tft_serving_{task}_households.csv"
    write_csv(household_path, per_household)
    return {
        "task": task,
        "normalization": "production_rolling_336h_zscore",
        "checkpoint": str(checkpoint_path.relative_to(WORKSPACE)).replace("\\", "/"),
        "checkpoint_sha256": sha256(checkpoint_path),
        "fixed_origin_count": len(fixed_origins),
        "fixed_origins": [int(value) for value in fixed_origins],
        "inference_seconds": elapsed,
        "exact_production_method_parity": parity,
        "household_evidence": str(household_path.relative_to(WORKSPACE)).replace("\\", "/"),
        **summary,
    }


def research_rows(tasks: list[dict]) -> list[dict]:
    diagnostics = json.loads(
        (EVIDENCE / "lcl_tft_reanalysis_manifest.json").read_text(encoding="utf-8")
    )
    diagnostic_by_task = {item["task"]: item for item in diagnostics["tasks"]}
    rows: list[dict] = []
    for serving in tasks:
        task = serving["task"]
        frozen = json.loads(
            (
                EXPERIMENT
                / "runs"
                / "global_tft"
                / task
                / "metrics.json"
            ).read_text(encoding="utf-8")
        )["cold_start_households"]
        diagnostic = diagnostic_by_task[task]
        research_wins = round(
            frozen["n_evaluated_households"]
            * frozen["households_beating_seasonal_percent"]
            / 100.0
        )
        common = {
            "task": task,
            "evaluated_households": frozen["n_evaluated_households"],
            "evaluation_windows": frozen["evaluation_windows"],
        }
        rows.append(
            {
                **common,
                "normalization": "research_train_only_household_zscore",
                "macro_mae_kwh": frozen["macro_mae_kwh"],
                "median_household_mae_kwh": frozen["median_mae_kwh"],
                "p90_household_mae_kwh": frozen["p90_household_mae_kwh"],
                "macro_rmse_kwh": frozen["macro_rmse_kwh"],
                "macro_bias_kwh": frozen["macro_bias_kwh"],
                "macro_r2": frozen["macro_r2"],
                "global_r2": frozen["global_r2"],
                "seasonal_naive_macro_mae_kwh": frozen[
                    "seasonal_naive_macro_mae_kwh"
                ],
                "households_beating_seasonal_count": research_wins,
                "households_beating_seasonal_percent": frozen[
                    "households_beating_seasonal_percent"
                ],
                "q10_pinball_kwh": diagnostic["q10_pinball_kwh"],
                "q50_pinball_kwh": diagnostic["q50_pinball_kwh"],
                "q90_pinball_kwh": diagnostic["q90_pinball_kwh"],
                "central_80_empirical_coverage_percent": diagnostic[
                    "central_80_empirical_coverage_percent"
                ],
                "central_80_mean_width_kwh": diagnostic[
                    "central_80_mean_width_kwh"
                ],
                "quantile_crossing_rate_percent": diagnostic[
                    "quantile_crossing_rate_percent"
                ],
            }
        )
        rows.append(
            {
                key: serving[key]
                for key in rows[-1]
            }
        )
    return rows


def git_state() -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=WORKSPACE,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=WORKSPACE,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unavailable", True


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((DATA / "prepared.json").read_text(encoding="utf-8"))
    values = np.load(DATA / "hourly_raw.npy", mmap_mode="r")
    calendar = np.load(DATA / "hourly_calendar.npy", mmap_mode="r")
    cold = np.load(DATA / "cold_households.npy")
    known = np.load(DATA / "known_households.npy")
    households = json.loads((DATA / "households.json").read_text(encoding="utf-8"))

    if values.shape != (len(households), metadata["hourly_length"]):
        raise RuntimeError("Prepared hourly values do not match preserved metadata and identities.")
    if calendar.shape != (metadata["hourly_length"], 9):
        raise RuntimeError("Prepared calendar does not satisfy the frozen TFT feature contract.")
    if set(map(int, cold)) & set(map(int, known)):
        raise RuntimeError("Known and cold-start household assignments overlap.")
    if len(set(map(int, cold)) | set(map(int, known))) != len(households):
        raise RuntimeError("Known and cold-start assignments do not cover all preserved identities.")

    task_summaries = [
        evaluate_task(
            task,
            values,
            calendar,
            cold,
            int(metadata["hourly_val_end"]),
        )
        for task in TASKS
    ]
    comparison_rows = research_rows(task_summaries)
    comparison_path = EVIDENCE / "lcl_tft_serving_normalization_comparison.csv"
    write_csv(comparison_path, comparison_rows)

    commit, dirty = git_state()
    prepared_files = [
        "prepared.json",
        "hourly_raw.npy",
        "hourly_calendar.npy",
        "cold_households.npy",
        "known_households.npy",
        "households.json",
        "hourly_scalers.npz",
    ]
    manifest_path = EVIDENCE / "lcl_tft_serving_normalization_manifest.json"
    manifest = {
        "purpose": (
            "Inference-only serving-normalization comparison. Frozen research metrics "
            "and production checkpoints remain unchanged."
        ),
        "evaluation_possible_from_preserved_local_evidence": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "working_tree_dirty_at_execution": dirty,
        "script": str(Path(__file__).relative_to(WORKSPACE)).replace("\\", "/"),
        "script_sha256": sha256(Path(__file__)),
        "production_preprocessing": {
            "function": (
                "backend/app/services/product_forecast_service.py::"
                "ProductForecastService._predict_tft"
            ),
            "source_sha256": sha256(PRODUCTION_SERVICE),
            "history_length_hours": 336,
            "normalization": "mean = history.mean(); std = max(history.std(), 1e-6); x = (history - mean) / std",
            "inverse_transform": "quantiles_kwh = max(0, quantiles_z * std + mean)",
            "postprocessing": "sort q10/q50/q90 independently at every horizon step",
            "calendar_handling": (
                "Preserved hourly_calendar.npy rows were used because they are the exact "
                "calendar inputs of the frozen samples."
            ),
            "batch_implementation": (
                "Vectorized equivalent, checked against the exact production method on "
                "one preserved sample per horizon."
            ),
        },
        "preserved_evidence": {
            "hourly_values": "raw or exactly recoverable hourly household values",
            "households": "ordered household identities",
            "known_and_cold_assignments": "disjoint complete assignments",
            "split_boundaries": {
                "hourly_train_end": metadata["hourly_train_end"],
                "hourly_val_end": metadata["hourly_val_end"],
                "hourly_test_end": metadata["hourly_length"],
            },
            "fixed_origins": "reconstructed with the frozen 24-origin linspace protocol",
            "history_and_targets": "sliced exactly from hourly_raw.npy",
            "seasonal_naive": "recomputed from the preserved preceding 168 hours",
            "calendar_features": "sliced exactly from hourly_calendar.npy",
            "checkpoint_integrity": "research and packaged checkpoint SHA-256 values match",
        },
        "prepared_data_sha256": {
            name: sha256(DATA / name) for name in prepared_files
        },
        "checkpoint_sha256": {
            task: summary["checkpoint_sha256"] for task, summary in zip(TASKS, task_summaries)
        },
        "packaged_checkpoint_sha256": {
            "day_24h": sha256(BACKEND / "model_artifacts" / "global_tft_24h" / "model.pt"),
            "week_168h": sha256(BACKEND / "model_artifacts" / "global_tft_168h" / "model.pt"),
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "device": str(DEVICE),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "cuda": torch.version.cuda,
            "float16_autocast": False,
        },
        "tasks": task_summaries,
        "generated_outputs": [
            str(comparison_path.relative_to(WORKSPACE)).replace("\\", "/"),
            *[summary["household_evidence"] for summary in task_summaries],
            str(manifest_path.relative_to(WORKSPACE)).replace("\\", "/"),
        ],
    }
    if manifest["checkpoint_sha256"] != manifest["packaged_checkpoint_sha256"]:
        raise RuntimeError("Research and production checkpoint hashes differ.")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, allow_nan=False))


if __name__ == "__main__":
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    main()
