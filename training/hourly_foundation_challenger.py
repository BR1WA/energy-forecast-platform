"""Train and gate Chronos-2 LoRA challengers for 24 h and 168 h forecasts.

The command is deliberately two phase. ``select`` trains and chooses candidates
using only known-household targets, writes ``selection.json``, and exits. ``audit``
then opens the frozen cold-household cohort and decides promotion without changing
the declared gates.
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
from typing import Any

import numpy as np
import torch

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

QUANTILES = (0.1, 0.5, 0.9)
CONTEXT = 672
HORIZONS = (24, 168)
SEED = 2026


@dataclass(frozen=True)
class WindowSet:
    contexts: np.ndarray
    targets: np.ndarray
    houses: np.ndarray
    origins: np.ndarray
    baselines: dict[str, np.ndarray]
    x_calendar: np.ndarray
    y_calendar: np.ndarray


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


def fixed_origins(start: int, end: int, horizon: int, count: int) -> np.ndarray:
    latest = end - horizon
    if latest < start:
        raise ValueError("The requested split cannot support this horizon.")
    return np.unique(np.linspace(start, latest, count, dtype=np.int64))


def baseline_candidates(context: np.ndarray, horizon: int) -> dict[str, np.ndarray]:
    index = np.arange(horizon)
    last_week = context[-168:][index % 168]
    last_day = context[-24:][index % 24]
    offsets = np.asarray([168, 336, 504, 672], dtype=np.int64)
    positions = len(context) + index[None, :] - offsets[:, None]
    four_week = np.median(context[positions], axis=0)
    return {
        "last_week_repeat": last_week.astype(np.float32),
        "last_day_repeat": last_day.astype(np.float32),
        "same_hour_four_week_median": four_week.astype(np.float32),
    }


def materialize(
    values: np.ndarray,
    calendar: np.ndarray,
    households: np.ndarray,
    origins: np.ndarray,
    horizon: int,
) -> WindowSet:
    contexts: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    houses: list[int] = []
    kept_origins: list[int] = []
    past_calendar: list[np.ndarray] = []
    future_calendar: list[np.ndarray] = []
    baseline_store: dict[str, list[np.ndarray]] = {
        "last_week_repeat": [],
        "last_day_repeat": [],
        "same_hour_four_week_median": [],
    }
    for house in households:
        row = np.asarray(values[int(house)], dtype=np.float32)
        for origin in origins:
            context = row[int(origin) - CONTEXT : int(origin)]
            target = row[int(origin) : int(origin) + horizon]
            if len(context) != CONTEXT or len(target) != horizon:
                continue
            if not np.isfinite(context).all() or not np.isfinite(target).all():
                continue
            baselines = baseline_candidates(context, horizon)
            contexts.append(context)
            targets.append(target)
            houses.append(int(house))
            kept_origins.append(int(origin))
            past_calendar.append(
                np.asarray(calendar[int(origin) - 336 : int(origin)], dtype=np.float32)
            )
            future_calendar.append(
                np.asarray(
                    calendar[int(origin) : int(origin) + horizon], dtype=np.float32
                )
            )
            for name, prediction in baselines.items():
                baseline_store[name].append(prediction)
    if not contexts:
        raise RuntimeError("No finite evaluation windows were materialized.")
    return WindowSet(
        contexts=np.stack(contexts),
        targets=np.stack(targets),
        houses=np.asarray(houses, dtype=np.int32),
        origins=np.asarray(kept_origins, dtype=np.int32),
        baselines={name: np.stack(rows) for name, rows in baseline_store.items()},
        x_calendar=np.stack(past_calendar),
        y_calendar=np.stack(future_calendar),
    )


def chronos_predict(
    pipeline: Any, contexts: np.ndarray, horizon: int, batch_size: int
) -> np.ndarray:
    result: list[np.ndarray] = []
    for start in range(0, len(contexts), batch_size):
        batch = contexts[start : start + batch_size]
        quantiles, _ = pipeline.predict_quantiles(
            [row for row in batch],
            prediction_length=horizon,
            quantile_levels=list(QUANTILES),
            batch_size=batch_size,
            cross_learning=False,
        )
        result.append(np.stack([item[0].float().cpu().numpy() for item in quantiles]))
    prediction = np.maximum(np.concatenate(result), 0).astype(np.float32)
    prediction.sort(axis=2)
    return prediction


def load_tft(repository: Path, horizon: int, device: torch.device) -> Any:
    import sys

    backend = repository / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.ml.global_tft import GlobalTFT

    artifact = repository / "backend" / "model_artifacts" / f"global_tft_{horizon}h"
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = torch.load(
        artifact / manifest["checkpoint_file"], map_location=device, weights_only=True
    )
    architecture = manifest.get("architecture", {})
    model = GlobalTFT(
        hidden_size=int(architecture.get("hidden_size", 128)),
        n_heads=int(architecture.get("attention_heads", 4)),
        dropout=float(architecture.get("dropout", 0.1)),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    return model


@torch.inference_mode()
def tft_predict(
    model: Any, windows: WindowSet, device: torch.device, batch_size: int
) -> np.ndarray:
    rows: list[np.ndarray] = []
    for start in range(0, len(windows.contexts), batch_size):
        context = windows.contexts[start : start + batch_size]
        mean = context.mean(axis=1, keepdims=True)
        std = np.maximum(context.std(axis=1, keepdims=True), 1e-6)
        normalized = (context[:, -336:] - mean) / std
        batch = {
            "x": torch.from_numpy(normalized[:, :, None].astype(np.float32)).to(device),
            "x_calendar": torch.from_numpy(
                windows.x_calendar[start : start + batch_size]
            ).to(device),
            "y_calendar": torch.from_numpy(
                windows.y_calendar[start : start + batch_size]
            ).to(device),
        }
        output = model(batch)["quantiles"].cpu().numpy()
        output = output * std[:, :, None] + mean[:, :, None]
        output = np.maximum(output, 0)
        output.sort(axis=2)
        rows.append(output.astype(np.float32))
    return np.concatenate(rows)


def point_metrics(
    targets: np.ndarray,
    prediction: np.ndarray,
    houses: np.ndarray,
    comparator: np.ndarray | None = None,
) -> dict[str, float | int]:
    median = prediction[:, :, 1] if prediction.ndim == 3 else prediction
    unique = np.unique(houses)
    household_mae = []
    household_r2 = []
    comparator_mae = []
    for house in unique:
        mask = houses == house
        y = targets[mask].reshape(-1)
        p = median[mask].reshape(-1)
        household_mae.append(float(np.mean(np.abs(y - p))))
        variance = float(np.sum(np.square(y - y.mean())))
        household_r2.append(
            float(1.0 - np.sum(np.square(y - p)) / variance)
            if variance > 1e-12
            else math.nan
        )
        if comparator is not None:
            comparator_mae.append(
                float(np.mean(np.abs(y - comparator[mask].reshape(-1))))
            )
    result: dict[str, float | int] = {
        "windows": int(len(targets)),
        "households": int(len(unique)),
        "macro_mae_kwh": float(np.mean(household_mae)),
        "median_household_mae_kwh": float(np.median(household_mae)),
        "p90_household_mae_kwh": float(np.percentile(household_mae, 90)),
        "macro_r2": float(np.nanmean(household_r2)),
    }
    if prediction.ndim == 3:
        result["central_80_coverage_percent"] = float(
            100
            * np.mean(
                (targets >= prediction[:, :, 0]) & (targets <= prediction[:, :, 2])
            )
        )
        result["central_80_mean_width_kwh"] = float(
            np.mean(prediction[:, :, 2] - prediction[:, :, 0])
        )
    if comparator is not None:
        result["households_beating_comparator_percent"] = float(
            100 * np.mean(np.asarray(household_mae) < np.asarray(comparator_mae))
        )
    return result


def best_baseline(windows: WindowSet) -> tuple[str, np.ndarray, list[dict[str, float]]]:
    scores = []
    for name, prediction in windows.baselines.items():
        score = float(np.mean(np.abs(windows.targets - prediction)))
        scores.append({"name": name, "mae_kwh": score})
    scores.sort(key=lambda item: item["mae_kwh"])
    return scores[0]["name"], windows.baselines[scores[0]["name"]], scores


def conformal_offsets(
    targets: np.ndarray, prediction: np.ndarray, contexts: np.ndarray
) -> tuple[float, float]:
    scales = np.maximum(
        np.mean(np.abs(np.diff(contexts[:, -168:], axis=1)), axis=1), 1e-6
    )[:, None]
    lower = (prediction[:, :, 0] - targets) / scales
    upper = (targets - prediction[:, :, 2]) / scales
    return float(np.quantile(lower, 0.9)), float(np.quantile(upper, 0.9))


def apply_conformal(
    prediction: np.ndarray,
    offsets: tuple[float, float],
    contexts: np.ndarray,
) -> np.ndarray:
    result = prediction.copy()
    scales = np.maximum(
        np.mean(np.abs(np.diff(contexts[:, -168:], axis=1)), axis=1), 1e-6
    )[:, None]
    result[:, :, 0] = np.maximum(0, result[:, :, 0] - offsets[0] * scales)
    result[:, :, 2] += offsets[1] * scales
    result.sort(axis=2)
    return result


def load_bundle(root: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    data = root / "data"
    values = np.load(data / "hourly_raw.npy", mmap_mode="r")
    calendar = np.load(data / "hourly_calendar.npy", mmap_mode="r")
    metadata = json.loads((data / "prepared.json").read_text(encoding="utf-8"))
    expected = "353d5e21355ada4dd662b74474f021afabcb2300cd1f3cf934a3792bc6487646"
    if sha256(data / "hourly_raw.npy") != expected:
        raise RuntimeError(
            "The hourly prepared-data checksum does not match the protocol."
        )
    return values, calendar, metadata


def train_sequences(
    values: np.ndarray, households: np.ndarray, cutoff: int
) -> list[np.ndarray]:
    sequences = []
    for house in households:
        row = np.asarray(values[int(house), :cutoff], dtype=np.float32)
        if np.isfinite(row).mean() < 0.99:
            continue
        finite = np.isfinite(row)
        positions = np.arange(len(row))
        row = np.interp(positions, positions[finite], row[finite]).astype(np.float32)
        sequences.append(row)
    return sequences


def select(args: argparse.Namespace) -> dict[str, Any]:
    from chronos import Chronos2Pipeline

    seed_everything(args.seed)
    values, calendar, metadata = load_bundle(args.data_root)
    known = np.load(args.data_root / "data" / "known_households.npy")
    train_end = int(metadata["hourly_train_end"])
    val_end = int(metadata["hourly_val_end"])
    validation_households = known[: args.validation_households]
    sequences = train_sequences(values, known, train_end)
    device_name = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device_name == "cuda" else torch.float32
    device = torch.device(device_name)
    output = args.output.resolve()
    models_dir = output / "runs"
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    selected: dict[str, Any] = {}

    for horizon in HORIZONS:
        origins = fixed_origins(train_end, val_end, horizon, args.validation_origins)
        windows = materialize(values, calendar, validation_households, origins, horizon)
        baseline_name, baseline, baseline_scores = best_baseline(windows)
        tft = load_tft(args.repository, horizon, device)
        tft_prediction = tft_predict(tft, windows, device, args.tft_batch_size)
        candidate_scores: list[dict[str, Any]] = []
        candidate_predictions: dict[str, np.ndarray] = {}

        print(
            f"[{horizon}h] zero-shot validation on {len(windows.targets)} windows",
            flush=True,
        )
        base = Chronos2Pipeline.from_pretrained(
            "amazon/chronos-2", device_map=device_name, dtype=dtype
        )
        candidate_predictions["chronos2_zero_shot"] = chronos_predict(
            base, windows.contexts, horizon, args.inference_batch_size
        )
        for steps in args.lora_steps:
            name = f"chronos2_lora_{steps}"
            directory = models_dir / f"{horizon}h" / name
            if directory.exists():
                raise RuntimeError(
                    f"Refusing to overwrite existing candidate directory: {directory}"
                )
            print(f"[{horizon}h] training {name}", flush=True)
            pipeline = base.fit(
                inputs=sequences,
                validation_inputs=[
                    np.concatenate([row, target])
                    for row, target in zip(windows.contexts[:32], windows.targets[:32])
                ],
                prediction_length=horizon,
                finetune_mode="lora",
                context_length=CONTEXT,
                learning_rate=1e-5,
                num_steps=steps,
                batch_size=args.lora_batch_size,
                output_dir=directory,
                min_past=336,
                remove_printer_callback=True,
                logging_steps=25,
            )
            candidate_predictions[name] = chronos_predict(
                pipeline, windows.contexts, horizon, args.inference_batch_size
            )
            del pipeline
            torch.cuda.empty_cache()

        for name, prediction in candidate_predictions.items():
            metrics = point_metrics(windows.targets, prediction, windows.houses)
            candidate_scores.append({"name": name, **metrics})
        candidate_scores.sort(key=lambda item: item["macro_mae_kwh"])
        winner = candidate_scores[0]["name"]
        winning_prediction = candidate_predictions[winner]
        offsets = conformal_offsets(
            windows.targets, winning_prediction, windows.contexts
        )
        calibrated = apply_conformal(winning_prediction, offsets, windows.contexts)
        selected[str(horizon)] = {
            "architecture": winner,
            "model_path": (
                None
                if winner == "chronos2_zero_shot"
                else str(Path("runs") / f"{horizon}h" / winner)
            ),
            "conformal_offsets": list(offsets),
            "baseline": baseline_name,
            "baseline_scores": baseline_scores,
            "candidate_scores": candidate_scores,
            "validation": {
                "candidate": point_metrics(
                    windows.targets, calibrated, windows.houses, tft_prediction[:, :, 1]
                ),
                "packaged_tft": point_metrics(
                    windows.targets, tft_prediction, windows.houses
                ),
                "strongest_baseline": point_metrics(
                    windows.targets, baseline, windows.houses
                ),
                "origins": origins.tolist(),
            },
        }
        del base, tft
        torch.cuda.empty_cache()

    payload = {
        "selection_version": 1,
        "frozen_before_cold_audit": True,
        "seed": args.seed,
        "base_model": "amazon/chronos-2",
        "base_revision": "29ec3766d36d6f73f0696f85560a422f50e8498c",
        "context_hours": CONTEXT,
        "training_sequences": len(sequences),
        "tasks": selected,
        "runtime_seconds": time.time() - started,
    }
    atomic_json(output / "selection.json", payload)
    print(json.dumps(payload, indent=2), flush=True)
    return payload


def load_selected_pipeline(
    output: Path, task: dict[str, Any], device_name: str, dtype: torch.dtype
) -> Any:
    from chronos import Chronos2Pipeline

    path = (
        "amazon/chronos-2"
        if task["architecture"] == "chronos2_zero_shot"
        else output / task["model_path"]
    )
    if isinstance(path, Path) and (path / "finetuned-ckpt").is_dir():
        path = path / "finetuned-ckpt"
    return Chronos2Pipeline.from_pretrained(path, device_map=device_name, dtype=dtype)


def audit(args: argparse.Namespace) -> dict[str, Any]:
    seed_everything(args.seed)
    output = args.output.resolve()
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.resolve().read_text(encoding="utf-8"))
    values, calendar, metadata = load_bundle(args.data_root)
    # Cold targets are first indexed after the immutable selection file exists.
    cold = np.load(args.data_root / "data" / "cold_households.npy")
    val_end = int(metadata["hourly_val_end"])
    test_end = int(metadata["hourly_length"])
    device_name = "cuda" if torch.cuda.is_available() else "cpu"
    # Audit and prospective production inference use FP32 so an adapter reload
    # is checked independently of BF16 quantization-step variation.
    dtype = torch.float32
    device = torch.device(device_name)
    gates = protocol["promotion_gates"]
    results: dict[str, Any] = {}
    started = time.time()

    for horizon in HORIZONS:
        origins = fixed_origins(val_end, test_end, horizon, args.audit_origins)
        windows = materialize(values, calendar, cold, origins, horizon)
        task = selection["tasks"][str(horizon)]
        pipeline = load_selected_pipeline(output, task, device_name, dtype)
        raw = chronos_predict(
            pipeline, windows.contexts, horizon, args.inference_batch_size
        )
        prediction = apply_conformal(
            raw, tuple(task["conformal_offsets"]), windows.contexts
        )
        tft = load_tft(args.repository, horizon, device)
        tft_prediction = tft_predict(tft, windows, device, args.tft_batch_size)
        baseline_name, baseline, baseline_scores = best_baseline(windows)
        candidate_metrics = point_metrics(
            windows.targets, prediction, windows.houses, tft_prediction[:, :, 1]
        )
        tft_metrics = point_metrics(windows.targets, tft_prediction, windows.houses)
        baseline_metrics = point_metrics(windows.targets, baseline, windows.houses)
        improvement = (
            float(tft_metrics["macro_mae_kwh"])
            - float(candidate_metrics["macro_mae_kwh"])
        ) / float(tft_metrics["macro_mae_kwh"])
        finite_nonnegative = bool(
            np.isfinite(prediction).all() and float(np.min(prediction)) >= 0
        )

        reload_relative_error = 0.0
        if task["architecture"] != "chronos2_zero_shot":
            del pipeline
            torch.cuda.empty_cache()
            reloaded = load_selected_pipeline(output, task, device_name, dtype)
            repeated = chronos_predict(
                reloaded, windows.contexts[:1], horizon, args.inference_batch_size
            )
            reload_relative_error = float(np.max(np.abs(raw[:1] - repeated))) / max(
                1.0, float(np.max(np.abs(raw[:1])))
            )
            del reloaded

        task_gates = {
            "macro_mae": improvement
            >= gates["macro_mae_improvement_over_packaged_tft_min"],
            "macro_r2": float(candidate_metrics["macro_r2"]) >= gates["macro_r2_min"],
            "coverage": gates["central_80_coverage_min"] * 100
            <= float(candidate_metrics["central_80_coverage_percent"])
            <= gates["central_80_coverage_max"] * 100,
            "households_beating_tft": float(
                candidate_metrics["households_beating_comparator_percent"]
            )
            >= gates["households_beating_packaged_tft_percent_min"],
            "finite_nonnegative": finite_nonnegative,
            "artifact_reload": reload_relative_error
            <= gates["artifact_reload_relative_error_max"],
        }
        results[str(horizon)] = {
            "architecture": task["architecture"],
            "candidate": candidate_metrics,
            "packaged_tft": tft_metrics,
            "strongest_baseline_name": baseline_name,
            "strongest_baseline": baseline_metrics,
            "baseline_scores": baseline_scores,
            "macro_mae_improvement_over_tft_percent": 100 * improvement,
            "artifact_reload_relative_error": reload_relative_error,
            "gates": task_gates,
            "promoted": all(task_gates.values()),
            "origins": origins.tolist(),
        }
        del tft
        torch.cuda.empty_cache()

    payload = {
        "audit_version": 1,
        "selection_sha256": sha256(output / "selection.json"),
        "protocol_sha256": sha256(args.protocol.resolve()),
        "audit_inference_dtype": "float32",
        "tasks": results,
        "all_horizons_promoted": all(result["promoted"] for result in results.values()),
        "runtime_seconds": time.time() - started,
        "limitations": [
            "The cold London cohort was unseen by these challengers until selection was frozen, but prior incumbent experiments had already evaluated it.",
            "London evidence does not establish accuracy for the application's Moroccan households.",
        ],
    }
    atomic_json(output / "audit.json", payload)
    print(json.dumps(payload, indent=2), flush=True)
    return payload


def package(args: argparse.Namespace) -> dict[str, Any]:
    """Copy only promoted adapters into a small, checksum-addressed release."""
    output = args.output.resolve()
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    audit_payload = json.loads((output / "audit.json").read_text(encoding="utf-8"))
    if not audit_payload.get("all_horizons_promoted"):
        raise RuntimeError("The hourly challengers did not pass every frozen gate.")
    release_root = output / "release"
    releases: dict[str, Any] = {}
    for horizon in HORIZONS:
        task = selection["tasks"][str(horizon)]
        evidence = audit_payload["tasks"][str(horizon)]
        if not evidence["promoted"] or task["architecture"] == "chronos2_zero_shot":
            raise RuntimeError(f"The {horizon}h task has no promotable local adapter.")
        source = output / task["model_path"] / "finetuned-ckpt"
        destination = release_root / f"{horizon}h"
        destination.mkdir(parents=True, exist_ok=True)
        for filename in ("adapter_config.json", "adapter_model.safetensors"):
            target = destination / filename
            if target.exists():
                raise RuntimeError(
                    f"Refusing to overwrite existing release file: {target}"
                )
            shutil.copy2(source / filename, target)
        adapter = destination / "adapter_model.safetensors"
        manifest = {
            "schema_version": 1,
            "model_name": f"hourly_chronos2_lora_{horizon}h_v2",
            "version": "2.0.0",
            "status": "production_eligible_challenger",
            "deployed": False,
            "architecture": "Chronos-2 120M plus rank-8 LoRA domain adapter",
            "base_model": {
                "model_id": "amazon/chronos-2",
                "revision": selection["base_revision"],
                "model_sha256": "ddcda3c7508bf2528087723e98a20707cc04b7f370ae275a9fd88078ddba4f42",
            },
            "adapter": {
                "filename": "adapter_model.safetensors",
                "bytes": adapter.stat().st_size,
                "sha256": sha256(adapter),
                "rank": 8,
                "training_updates": int(task["architecture"].rsplit("_", 1)[-1]),
                "learning_rate": 1e-5,
            },
            "contract": {
                "horizon_hours": horizon,
                "target_count": horizon,
                "target_interval_hours": 1,
                "target_frequency": "hourly",
                "context_hours": CONTEXT,
                "minimum_observed_hours": CONTEXT,
                "quantiles": list(QUANTILES),
                "inference_dtype": "float32",
                "negative_output_policy": "clip_to_zero",
            },
            "calibration": {
                "method": "scale-normalized asymmetric split conformal",
                "scale": "mean absolute first difference over the latest 168 context hours",
                "lower_offset": task["conformal_offsets"][0],
                "upper_offset": task["conformal_offsets"][1],
                "nominal_coverage": 0.8,
            },
            "cold_household_audit": {
                "households": evidence["candidate"]["households"],
                "windows": evidence["candidate"]["windows"],
                "macro_mae_kwh": evidence["candidate"]["macro_mae_kwh"],
                "packaged_tft_macro_mae_kwh": evidence["packaged_tft"]["macro_mae_kwh"],
                "macro_mae_improvement_over_tft_percent": evidence[
                    "macro_mae_improvement_over_tft_percent"
                ],
                "macro_r2": evidence["candidate"]["macro_r2"],
                "central_80_coverage_percent": evidence["candidate"][
                    "central_80_coverage_percent"
                ],
                "households_beating_tft_percent": evidence["candidate"][
                    "households_beating_comparator_percent"
                ],
                "artifact_reload_relative_error": evidence[
                    "artifact_reload_relative_error"
                ],
            },
            "reproducibility": {
                "protocol_sha256": sha256(args.protocol.resolve()),
                "selection_sha256": sha256(output / "selection.json"),
                "audit_sha256": sha256(output / "audit.json"),
                "seed": args.seed,
            },
            "limitations": audit_payload["limitations"]
            + [
                "This release is not deployed until CPU latency, memory, container start-up, and API compatibility checks pass.",
                "It requires 672 observed hours, twice the deployed TFT input window.",
            ],
        }
        atomic_json(destination / "manifest.json", manifest)
        releases[str(horizon)] = manifest
    payload = {"package_version": 1, "releases": releases}
    atomic_json(release_root / "manifest.json", payload)
    print(json.dumps(payload, indent=2), flush=True)
    return payload


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    data_root = repository / "models" / "lcl_global_forecasting" / "full_selected_v1"
    output = repository / "models" / "lcl_global_forecasting" / "hourly_foundation_v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("select", "audit", "package", "all"))
    parser.add_argument("--repository", type=Path, default=repository)
    parser.add_argument("--data-root", type=Path, default=data_root)
    parser.add_argument("--output", type=Path, default=output)
    parser.add_argument("--protocol", type=Path, default=output / "protocol.json")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--validation-households", type=int, default=250)
    parser.add_argument("--validation-origins", type=int, default=6)
    parser.add_argument("--audit-origins", type=int, default=24)
    parser.add_argument("--lora-steps", type=int, nargs="+", default=[100, 300])
    parser.add_argument("--lora-batch-size", type=int, default=8)
    parser.add_argument("--inference-batch-size", type=int, default=32)
    parser.add_argument("--tft-batch-size", type=int, default=256)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.phase in {"select", "all"}:
        select(parsed)
    if parsed.phase in {"audit", "all"}:
        audit(parsed)
    if parsed.phase in {"package", "all"}:
        package(parsed)
