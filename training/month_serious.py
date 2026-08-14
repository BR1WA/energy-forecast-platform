"""Serious multi-year 30-day household forecasting experiment.

This experiment consumes the official 2011--2014 Low Carbon London daily
matrix prepared by :mod:`training.prepare_month_serious`.  It combines:

* a validation-selected annual/recent seasonal baseline;
* a three-seed XGBoost quantile residual ensemble;
* a three-seed multiscale neural residual ensemble;
* causal historical ERA5 observations and future ERA5 climatology;
* validation-only model blending and conformal interval calibration;
* final refitting on train plus validation before one untouched cold-start test.

The script writes research artifacts only.  Promotion remains governed by the
predeclared gates in ``training.month_strong``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

try:
    from training.month_strong import (
        HORIZON_DAYS,
        QUANTILES,
        ForecastMatrix,
        apply_daily_calibration,
        apply_total_calibration,
        atomic_json,
        baseline_metrics,
        calibrate_daily_quantiles,
        calibrate_total_quantiles,
        point_metrics,
        promotion_decision,
        reconcile_daily_to_total,
        refit_quantile_model,
        sha256,
        train_quantile_model,
    )
except ModuleNotFoundError:  # direct ``python training/month_serious.py``
    from month_strong import (
        HORIZON_DAYS,
        QUANTILES,
        ForecastMatrix,
        apply_daily_calibration,
        apply_total_calibration,
        atomic_json,
        baseline_metrics,
        calibrate_daily_quantiles,
        calibrate_total_quantiles,
        point_metrics,
        promotion_decision,
        reconcile_daily_to_total,
        refit_quantile_model,
        sha256,
        train_quantile_model,
    )


LOOKBACK_DAYS = 365
MIN_HISTORY_COVERAGE = 0.95
MAX_HISTORY_GAP_DAYS = 7
TRAIN_END_DATE = np.datetime64("2013-08-01")
VALIDATION_END_DATE = np.datetime64("2013-10-31")
TEST_START_DATE = np.datetime64("2013-11-01")
TEST_LAST_ORIGIN_DATE = np.datetime64("2014-01-29")
TRAIN_ORIGIN_STRIDE = 7
EVALUATION_ORIGIN_STRIDE = 7
SEEDS = (2026, 2027, 2028)
ANNUAL_BASELINE_WEIGHT = 0.25


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def maximum_missing_run(values: np.ndarray) -> int:
    best = current = 0
    for missing in ~np.isfinite(values):
        current = current + 1 if missing else 0
        best = max(best, current)
    return best


def causal_interpolate(history: np.ndarray) -> np.ndarray:
    history = np.asarray(history, dtype=np.float32)
    finite = np.isfinite(history)
    if not finite.any():
        raise ValueError("Cannot interpolate an empty history.")
    positions = np.arange(history.size)
    return np.interp(positions, positions[finite], history[finite]).astype(np.float32)


def date_index(dates: np.ndarray, date: np.datetime64) -> int:
    index = int(np.searchsorted(dates, date))
    if index >= len(dates) or dates[index] != date:
        raise ValueError(f"Date {date} is absent from prepared data.")
    return index


def valid_windows(
    values: np.ndarray,
    households: np.ndarray,
    origins: np.ndarray,
) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    for raw_household in households:
        household = int(raw_household)
        row = np.asarray(values[household])
        for raw_origin in origins:
            origin = int(raw_origin)
            history = row[origin - LOOKBACK_DAYS : origin]
            target = row[origin : origin + HORIZON_DAYS]
            if history.size != LOOKBACK_DAYS or target.size != HORIZON_DAYS:
                continue
            if np.isfinite(history).mean() < MIN_HISTORY_COVERAGE:
                continue
            if maximum_missing_run(history) > MAX_HISTORY_GAP_DAYS:
                continue
            if not np.isfinite(target).all():
                continue
            windows.append((household, origin))
    if not windows:
        raise RuntimeError("No valid serious-month forecasting windows were found.")
    return windows


def _slope(sequence: np.ndarray) -> float:
    sequence = np.asarray(sequence, dtype=np.float64)
    x = np.arange(sequence.size, dtype=np.float64)
    x -= x.mean()
    return float(np.sum(x * (sequence - sequence.mean())) / max(np.sum(x * x), 1e-8))


def _window_components(
    row: np.ndarray,
    dates: np.ndarray,
    actual_weather: np.ndarray,
    climate_weather: np.ndarray,
    calendar: np.ndarray,
    origin: int,
) -> dict[str, np.ndarray | float]:
    raw_history = np.asarray(row[origin - LOOKBACK_DAYS : origin], dtype=np.float32)
    history = causal_interpolate(raw_history)
    target = np.asarray(row[origin : origin + HORIZON_DAYS], dtype=np.float32)
    mean = float(history.mean(dtype=np.float64))
    scale = max(float(history.std(dtype=np.float64)), 0.10, abs(mean) * 0.02)
    history_z = (history - mean) / scale

    steps = np.arange(HORIZON_DAYS, dtype=np.int64)
    slots = steps % 7
    weekly = np.stack(
        [
            history[LOOKBACK_DAYS - 7 * (week + 1) : LOOKBACK_DAYS - 7 * week]
            for week in range(12)
        ]
    ).astype(np.float32)
    weekly_lags = weekly[:, slots].T
    last_week = weekly_lags[:, 0]
    mean4 = weekly[:4].mean(axis=0)[slots]
    mean8 = weekly[:8].mean(axis=0)[slots]
    annual = history[steps]
    annual_recent = (
        ANNUAL_BASELINE_WEIGHT * annual + (1.0 - ANNUAL_BASELINE_WEIGHT) * mean4
    ).astype(np.float32)
    annual_recent_50_50 = (0.50 * annual + 0.50 * mean4).astype(np.float32)

    history_weather = np.asarray(
        actual_weather[origin - LOOKBACK_DAYS : origin], dtype=np.float32
    )
    history_climate = np.asarray(
        climate_weather[origin - LOOKBACK_DAYS : origin], dtype=np.float32
    )
    future_climate = np.asarray(
        climate_weather[origin : origin + HORIZON_DAYS], dtype=np.float32
    )
    future_calendar = np.asarray(
        calendar[origin : origin + HORIZON_DAYS], dtype=np.float32
    )
    history_calendar = np.asarray(
        calendar[origin - LOOKBACK_DAYS : origin], dtype=np.float32
    )
    annual_weather = history_weather[:HORIZON_DAYS]
    weather_mean = history_weather.mean(axis=0)
    weather_std = np.maximum(history_weather.std(axis=0), 1e-3)
    future_weather_z = (future_climate - weather_mean) / weather_std
    future_annual_weather_delta = (future_climate - annual_weather) / weather_std

    # Household-specific weather response uses only past observations. Remove
    # weekday means before computing robust standardized sensitivities.
    weekday_channels = calendar[origin - LOOKBACK_DAYS : origin, :2]
    weekday_angle = np.arctan2(weekday_channels[:, 0], weekday_channels[:, 1])
    weekday = np.mod(np.rint(weekday_angle * 7.0 / (2.0 * np.pi)), 7).astype(int)
    weekday_profile = np.asarray(
        [history[weekday == day].mean() for day in range(7)], dtype=np.float32
    )
    consumption_residual = history - weekday_profile[weekday]
    weather_z_history = (history_weather - weather_mean) / weather_std
    response = np.asarray(
        [
            np.mean(
                ((consumption_residual - consumption_residual.mean()) / scale)
                * weather_z_history[:, feature]
            )
            for feature in range(weather_z_history.shape[1])
        ],
        dtype=np.float32,
    )

    # A causal weather/calendar ridge is retained as a mandatory strong
    # baseline. Future design rows use climatological temperature only.
    history_temperature = history_weather[:, 0]
    future_temperature = future_climate[:, 0]
    ridge_history = np.column_stack(
        [
            np.ones(LOOKBACK_DAYS),
            history_calendar,
            np.maximum(15.5 - history_temperature, 0.0),
            np.maximum(history_temperature - 22.0, 0.0),
            np.arange(LOOKBACK_DAYS) / (LOOKBACK_DAYS - 1),
        ]
    ).astype(np.float64)
    ridge_future = np.column_stack(
        [
            np.ones(HORIZON_DAYS),
            future_calendar,
            np.maximum(15.5 - future_temperature, 0.0),
            np.maximum(future_temperature - 22.0, 0.0),
            (LOOKBACK_DAYS + steps) / (LOOKBACK_DAYS - 1),
        ]
    ).astype(np.float64)
    penalty = 10.0 * np.eye(ridge_history.shape[1])
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        ridge_history.T @ ridge_history + penalty,
        ridge_history.T @ history.astype(np.float64),
    )
    weather_climatology_ridge = np.clip(ridge_future @ coefficients, 0.0, None).astype(
        np.float32
    )

    recent_stats: list[float] = []
    for days in (7, 14, 28, 56, 90, 180, 365):
        recent = history[-days:]
        recent_stats.extend(
            [
                (float(recent.mean()) - mean) / scale,
                float(recent.std()) / scale,
            ]
        )
    recent_stats_array = np.asarray(recent_stats, dtype=np.float32)

    monthly_blocks = history[-360:].reshape(12, 30)
    monthly_means_z = (monthly_blocks.mean(axis=1) - mean) / scale
    monthly_stds_z = monthly_blocks.std(axis=1) / scale
    weekly_means_z = (history[-364:].reshape(52, 7).mean(axis=1) - mean) / scale
    trend_features = np.asarray(
        [
            _slope(weekly[:4].mean(axis=1)) / scale,
            _slope(weekly[:8].mean(axis=1)) / scale,
            _slope(weekly[:12].mean(axis=1)) / scale,
            _slope(monthly_blocks.mean(axis=1)) / scale,
        ],
        dtype=np.float32,
    )

    repeated_recent = np.repeat(recent_stats_array[None], HORIZON_DAYS, axis=0)
    repeated_monthly = np.repeat(monthly_means_z[None], HORIZON_DAYS, axis=0)
    repeated_response = np.repeat(response[None], HORIZON_DAYS, axis=0)
    repeated_trends = np.repeat(trend_features[None], HORIZON_DAYS, axis=0)
    horizon_features = np.column_stack(
        [
            steps / (HORIZON_DAYS - 1),
            steps // 7 / 4.0,
            np.sin(2.0 * np.pi * steps / 7.0),
            np.cos(2.0 * np.pi * steps / 7.0),
        ]
    ).astype(np.float32)
    magnitude = np.repeat(
        np.asarray([math.log1p(max(mean, 0.0)), math.log1p(scale)], dtype=np.float32)[
            None
        ],
        HORIZON_DAYS,
        axis=0,
    )

    point_features = np.concatenate(
        [
            (weekly_lags - mean) / scale,
            np.column_stack(
                [
                    (annual - mean) / scale,
                    (mean4 - mean) / scale,
                    (mean8 - mean) / scale,
                    (annual_recent - mean) / scale,
                    (annual_recent_50_50 - mean) / scale,
                    (weather_climatology_ridge - mean) / scale,
                    weekly[:4].std(axis=0)[slots] / scale,
                ]
            ),
            repeated_recent,
            repeated_monthly,
            repeated_response,
            repeated_trends,
            future_weather_z,
            future_annual_weather_delta,
            future_calendar,
            horizon_features,
            magnitude,
        ],
        axis=1,
    ).astype(np.float32)

    weather_history_summary = np.concatenate(
        [
            weather_z_history.mean(axis=0),
            weather_z_history.std(axis=0),
            (history_weather - history_climate).mean(axis=0) / weather_std,
            (history_weather - history_climate).std(axis=0) / weather_std,
        ]
    ).astype(np.float32)
    baseline_totals = np.asarray(
        [
            last_week.sum(),
            mean4.sum(),
            mean8.sum(),
            annual.sum(),
            annual_recent.sum(),
            annual_recent_50_50.sum(),
            weather_climatology_ridge.sum(),
        ],
        dtype=np.float32,
    )
    total_features = np.concatenate(
        [
            history_z,
            weekly_means_z,
            monthly_means_z,
            monthly_stds_z,
            recent_stats_array,
            trend_features,
            response,
            weather_history_summary,
            future_weather_z.reshape(-1),
            future_annual_weather_delta.reshape(-1),
            future_calendar.reshape(-1),
            (baseline_totals - HORIZON_DAYS * mean) / (HORIZON_DAYS * scale),
            np.asarray(
                [math.log1p(max(mean, 0.0)), math.log1p(scale)], dtype=np.float32
            ),
        ]
    ).astype(np.float32)

    baselines = {
        "last_week": last_week.astype(np.float32),
        "mean4": mean4.astype(np.float32),
        "mean8": mean8.astype(np.float32),
        "annual": annual.astype(np.float32),
        "annual_recent_25_75": annual_recent,
        "annual_recent_50_50": annual_recent_50_50,
        "weather_climatology_ridge": weather_climatology_ridge,
    }
    return {
        "point_features": point_features,
        "total_features": total_features,
        "target": target,
        "base": annual_recent,
        "target_residual_z": ((target - annual_recent) / scale).astype(np.float32),
        "target_total_residual_z": np.float32(
            (float(target.sum()) - float(annual_recent.sum())) / (HORIZON_DAYS * scale)
        ),
        "scale": np.float32(scale),
        "baselines": baselines,
    }


def build_matrix(
    values: np.ndarray,
    dates: np.ndarray,
    actual_weather: np.ndarray,
    climate_weather: np.ndarray,
    calendar: np.ndarray,
    windows: list[tuple[int, int]],
) -> ForecastMatrix:
    first = _window_components(
        np.asarray(values[windows[0][0]]),
        dates,
        actual_weather,
        climate_weather,
        calendar,
        windows[0][1],
    )
    point_width = np.asarray(first["point_features"]).shape[1]
    total_width = np.asarray(first["total_features"]).shape[0]
    n_windows = len(windows)
    n_points = n_windows * HORIZON_DAYS
    point_x = np.empty((n_points, point_width), np.float32)
    total_x = np.empty((n_windows, total_width), np.float32)
    target = np.empty(n_points, np.float32)
    target_r = np.empty(n_points, np.float32)
    target_total_r = np.empty(n_windows, np.float32)
    base = np.empty(n_points, np.float32)
    scales = np.empty(n_points, np.float32)
    point_houses = np.empty(n_points, np.int32)
    window_houses = np.empty(n_windows, np.int32)
    window_origins = np.empty(n_windows, np.int32)
    baselines = {name: np.empty(n_points, np.float32) for name in first["baselines"]}
    for index, (household, origin) in enumerate(windows):
        component = _window_components(
            np.asarray(values[household]),
            dates,
            actual_weather,
            climate_weather,
            calendar,
            origin,
        )
        start = index * HORIZON_DAYS
        end = start + HORIZON_DAYS
        point_x[start:end] = component["point_features"]
        total_x[index] = component["total_features"]
        target[start:end] = component["target"]
        target_r[start:end] = component["target_residual_z"]
        target_total_r[index] = component["target_total_residual_z"]
        base[start:end] = component["base"]
        scales[start:end] = component["scale"]
        point_houses[start:end] = household
        window_houses[index] = household
        window_origins[index] = origin
        for name in baselines:
            baselines[name][start:end] = component["baselines"][name]
    return ForecastMatrix(
        point_features=point_x,
        total_features=total_x,
        target_residual_z=target_r,
        target_total_residual_z=target_total_r,
        target=target,
        mean4=base,
        baselines=baselines,
        scales=scales,
        point_steps=np.tile(np.arange(HORIZON_DAYS, dtype=np.int16), n_windows),
        point_households=point_houses,
        window_households=window_houses,
        window_origins=window_origins,
    )


def concatenate_matrices(
    first: ForecastMatrix, second: ForecastMatrix
) -> ForecastMatrix:
    return ForecastMatrix(
        point_features=np.concatenate([first.point_features, second.point_features]),
        total_features=np.concatenate([first.total_features, second.total_features]),
        target_residual_z=np.concatenate(
            [first.target_residual_z, second.target_residual_z]
        ),
        target_total_residual_z=np.concatenate(
            [first.target_total_residual_z, second.target_total_residual_z]
        ),
        target=np.concatenate([first.target, second.target]),
        mean4=np.concatenate([first.mean4, second.mean4]),
        baselines={
            name: np.concatenate([first.baselines[name], second.baselines[name]])
            for name in first.baselines
        },
        scales=np.concatenate([first.scales, second.scales]),
        point_steps=np.concatenate([first.point_steps, second.point_steps]),
        point_households=np.concatenate(
            [first.point_households, second.point_households]
        ),
        window_households=np.concatenate(
            [first.window_households, second.window_households]
        ),
        window_origins=np.concatenate([first.window_origins, second.window_origins]),
    )


class MultiScaleResidualNet(nn.Module):
    """Multiscale direct 30-day quantile head over engineered causal history."""

    def __init__(self, input_size: int, hidden: int = 384, dropout: float = 0.15):
        super().__init__()
        self.input_norm = nn.LayerNorm(input_size)
        self.input = nn.Linear(input_size, hidden)
        self.blocks = nn.ModuleList(
            [
                nn.Sequential(
                    nn.LayerNorm(hidden),
                    nn.Linear(hidden, hidden * 2),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden * 2, hidden),
                    nn.Dropout(dropout),
                )
                for _ in range(4)
            ]
        )
        self.output = nn.Sequential(
            nn.LayerNorm(hidden), nn.Linear(hidden, HORIZON_DAYS * len(QUANTILES))
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        hidden = torch.nn.functional.gelu(self.input(self.input_norm(features)))
        for block in self.blocks:
            hidden = hidden + block(hidden)
        return self.output(hidden).reshape(-1, HORIZON_DAYS, len(QUANTILES))


def pinball(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    levels = torch.as_tensor(QUANTILES, device=prediction.device)
    error = target[..., None] - prediction
    return torch.maximum((levels - 1.0) * error, levels * error).mean()


@dataclass
class DeepRun:
    model: MultiScaleResidualNet
    best_epoch: int
    validation_loss: float


def train_deep(
    train: ForecastMatrix,
    validation: ForecastMatrix,
    *,
    seed: int,
    epochs: int,
    device: torch.device,
) -> DeepRun:
    seed_everything(seed)
    model = MultiScaleResidualNet(train.total_features.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    train_y = train.target_residual_z.reshape(-1, HORIZON_DAYS)
    validation_y = validation.target_residual_z.reshape(-1, HORIZON_DAYS)
    train_loader = DataLoader(
        TensorDataset(
            torch.from_numpy(train.total_features), torch.from_numpy(train_y)
        ),
        batch_size=256,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
        num_workers=0,
    )
    validation_loader = DataLoader(
        TensorDataset(
            torch.from_numpy(validation.total_features),
            torch.from_numpy(validation_y),
        ),
        batch_size=512,
        shuffle=False,
        num_workers=0,
    )
    best_state: dict[str, torch.Tensor] | None = None
    best_loss = float("inf")
    best_epoch = 0
    bad = 0
    for epoch in range(1, epochs + 1):
        model.train()
        for features, target in train_loader:
            features = features.to(device)
            target = target.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = pinball(model(features), target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        total = count = 0
        with torch.no_grad():
            for features, target in validation_loader:
                batch_loss = pinball(model(features.to(device)), target.to(device))
                total += float(batch_loss) * len(features)
                count += len(features)
        value = total / max(count, 1)
        print(
            f"deep seed={seed} epoch={epoch} validation_pinball={value:.6f}", flush=True
        )
        if value < best_loss - 1e-5:
            best_loss = value
            best_epoch = epoch
            best_state = {
                key: tensor.detach().cpu().clone()
                for key, tensor in model.state_dict().items()
            }
            bad = 0
        else:
            bad += 1
            if bad >= 5:
                break
    if best_state is None:
        raise RuntimeError("Deep model never produced a validation checkpoint.")
    model.load_state_dict(best_state)
    return DeepRun(model=model, best_epoch=best_epoch, validation_loss=best_loss)


def refit_deep(
    development: ForecastMatrix,
    *,
    seed: int,
    epochs: int,
    device: torch.device,
) -> MultiScaleResidualNet:
    seed_everything(seed)
    model = MultiScaleResidualNet(development.total_features.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    target = development.target_residual_z.reshape(-1, HORIZON_DAYS)
    loader = DataLoader(
        TensorDataset(
            torch.from_numpy(development.total_features), torch.from_numpy(target)
        ),
        batch_size=256,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
        num_workers=0,
    )
    for _ in range(max(1, epochs)):
        model.train()
        for features, target_batch in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = pinball(model(features.to(device)), target_batch.to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
    return model


@torch.no_grad()
def deep_predict(
    model: MultiScaleResidualNet,
    matrix: ForecastMatrix,
    device: torch.device,
) -> np.ndarray:
    model.eval()
    predictions: list[np.ndarray] = []
    loader = DataLoader(
        TensorDataset(torch.from_numpy(matrix.total_features)),
        batch_size=1024,
        shuffle=False,
    )
    for (features,) in loader:
        predictions.append(model(features.to(device)).cpu().numpy())
    return np.concatenate(predictions).reshape(-1, len(QUANTILES)).astype(np.float32)


def xgb_ensemble_predict(models: list[Any], features: np.ndarray) -> np.ndarray:
    return np.mean(
        [np.asarray(model.predict(features), dtype=np.float32) for model in models],
        axis=0,
    ).astype(np.float32)


def select_model_blend(
    validation: ForecastMatrix,
    xgb: np.ndarray,
    deep: np.ndarray,
) -> float:
    target = validation.target_residual_z
    best = (float("inf"), 1.0)
    for xgb_weight in np.linspace(0.0, 1.0, 11):
        center = xgb_weight * xgb[:, 1] + (1.0 - xgb_weight) * deep[:, 1]
        score = float(np.mean(np.abs(center - target)))
        if score < best[0] - 1e-12:
            best = (score, float(xgb_weight))
    return best[1]


def blend_quantiles(xgb: np.ndarray, deep: np.ndarray, xgb_weight: float) -> np.ndarray:
    return np.sort(
        xgb_weight * np.asarray(xgb) + (1.0 - xgb_weight) * np.asarray(deep),
        axis=1,
    ).astype(np.float32)


def evaluate_candidate(
    matrix: ForecastMatrix,
    residual_quantiles: np.ndarray,
    calibration: dict[str, list[float]],
    total_residual_quantiles: np.ndarray,
    total_calibration: dict[str, float],
    total_weight: float,
) -> dict[str, Any]:
    daily = apply_daily_calibration(matrix, residual_quantiles, calibration)
    total = apply_total_calibration(matrix, total_residual_quantiles, total_calibration)
    daily, total = reconcile_daily_to_total(matrix, daily, total, total_weight)
    candidate = point_metrics(matrix, daily[:, 1], daily)
    target_total = matrix.target.reshape(matrix.n_windows, HORIZON_DAYS).sum(axis=1)
    candidate.update(
        {
            "month_total_central_80_coverage_percent": float(
                100.0
                * np.mean((target_total >= total[:, 0]) & (target_total <= total[:, 2]))
            ),
            "month_total_central_80_mean_width_kwh": float(
                np.mean(total[:, 2] - total[:, 0])
            ),
        }
    )
    return {"candidate": candidate, "baselines": baseline_metrics(matrix)}


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
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
    known = known[: args.max_known or len(known)]
    cold = cold[: args.max_cold or len(cold)]
    active_seeds = SEEDS[: args.seed_count]
    prepared = json.loads((data / "prepared.json").read_text(encoding="utf-8"))

    train_end = date_index(dates, TRAIN_END_DATE)
    validation_end = date_index(dates, VALIDATION_END_DATE)
    test_start = date_index(dates, TEST_START_DATE)
    test_last = date_index(dates, TEST_LAST_ORIGIN_DATE)
    train_origins = np.arange(
        LOOKBACK_DAYS,
        train_end - HORIZON_DAYS + 1,
        TRAIN_ORIGIN_STRIDE,
        dtype=np.int32,
    )
    validation_origins = np.arange(
        train_end,
        validation_end + 1,
        EVALUATION_ORIGIN_STRIDE,
        dtype=np.int32,
    )
    test_origins = np.arange(
        test_start,
        test_last + 1,
        EVALUATION_ORIGIN_STRIDE,
        dtype=np.int32,
    )
    train_windows = valid_windows(values, known, train_origins)
    validation_windows = valid_windows(values, known, validation_origins)
    known_test_windows = valid_windows(values, known, test_origins)
    cold_test_windows = valid_windows(values, cold, test_origins)
    print(
        "windows train/validation/known-test/cold-test",
        len(train_windows),
        len(validation_windows),
        len(known_test_windows),
        len(cold_test_windows),
        flush=True,
    )

    train = build_matrix(
        values, dates, actual_weather, climate_weather, calendar, train_windows
    )
    validation = build_matrix(
        values, dates, actual_weather, climate_weather, calendar, validation_windows
    )
    print(
        "features point/total",
        train.point_features.shape,
        train.total_features.shape,
        flush=True,
    )
    device = torch.device(
        "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    )

    xgb_daily: list[Any] = []
    xgb_total: list[Any] = []
    deep_runs: list[DeepRun] = []
    for seed in active_seeds:
        print(f"training XGBoost seed {seed}", flush=True)
        xgb_daily.append(
            train_quantile_model(
                train.point_features,
                train.target_residual_z,
                validation.point_features,
                validation.target_residual_z,
                seed=seed,
                device="cpu" if args.cpu else "cuda",
                estimators=args.xgb_estimators,
                depth=7,
                learning_rate=0.035,
            )
        )
        xgb_total.append(
            train_quantile_model(
                train.total_features,
                train.target_total_residual_z,
                validation.total_features,
                validation.target_total_residual_z,
                seed=seed + 100,
                device="cpu" if args.cpu else "cuda",
                estimators=args.xgb_estimators,
                depth=6,
                learning_rate=0.035,
            )
        )
        print(f"training multiscale neural seed {seed}", flush=True)
        deep_runs.append(
            train_deep(
                train,
                validation,
                seed=seed,
                epochs=args.deep_epochs,
                device=device,
            )
        )

    validation_xgb = xgb_ensemble_predict(xgb_daily, validation.point_features)
    validation_deep = np.mean(
        [deep_predict(run.model, validation, device) for run in deep_runs], axis=0
    ).astype(np.float32)
    xgb_weight = select_model_blend(validation, validation_xgb, validation_deep)
    validation_residual = blend_quantiles(validation_xgb, validation_deep, xgb_weight)
    daily_calibration = calibrate_daily_quantiles(validation, validation_residual)
    validation_total_residual = xgb_ensemble_predict(
        xgb_total, validation.total_features
    )
    total_calibration = calibrate_total_quantiles(validation, validation_total_residual)

    validation_daily = apply_daily_calibration(
        validation, validation_residual, daily_calibration
    )
    validation_total = apply_total_calibration(
        validation, validation_total_residual, total_calibration
    )
    target_total = validation.target.reshape(validation.n_windows, HORIZON_DAYS).sum(
        axis=1
    )
    best_total = (float("inf"), 0.0)
    daily_sum = (
        validation_daily[:, 1].reshape(validation.n_windows, HORIZON_DAYS).sum(axis=1)
    )
    for weight in np.linspace(0.0, 1.0, 21):
        total_center = weight * validation_total[:, 1] + (1.0 - weight) * daily_sum
        score = float(np.mean(np.abs(total_center - target_total)))
        if score < best_total[0] - 1e-12:
            best_total = (score, float(weight))
    total_weight = best_total[1]
    print(
        f"validation selected xgb_weight={xgb_weight:.2f} "
        f"total_head_weight={total_weight:.2f}",
        flush=True,
    )

    development = concatenate_matrices(train, validation)
    final_xgb_daily: list[Any] = []
    final_xgb_total: list[Any] = []
    final_deep: list[MultiScaleResidualNet] = []
    for index, seed in enumerate(active_seeds):
        daily_iterations = (
            int(getattr(xgb_daily[index], "best_iteration", args.xgb_estimators - 1))
            + 1
        )
        total_iterations = (
            int(getattr(xgb_total[index], "best_iteration", args.xgb_estimators - 1))
            + 1
        )
        final_xgb_daily.append(
            refit_quantile_model(
                development.point_features,
                development.target_residual_z,
                seed=seed,
                device="cpu" if args.cpu else "cuda",
                estimators=daily_iterations,
                depth=7,
                learning_rate=0.035,
            )
        )
        final_xgb_total.append(
            refit_quantile_model(
                development.total_features,
                development.target_total_residual_z,
                seed=seed + 100,
                device="cpu" if args.cpu else "cuda",
                estimators=total_iterations,
                depth=6,
                learning_rate=0.035,
            )
        )
        final_deep.append(
            refit_deep(
                development,
                seed=seed,
                epochs=deep_runs[index].best_epoch,
                device=device,
            )
        )

    # The test matrices and predictions are intentionally materialized only
    # after every architecture, calibration, iteration, and blend choice freezes.
    known_test = build_matrix(
        values, dates, actual_weather, climate_weather, calendar, known_test_windows
    )
    cold_test = build_matrix(
        values, dates, actual_weather, climate_weather, calendar, cold_test_windows
    )

    def predict(matrix: ForecastMatrix) -> tuple[np.ndarray, np.ndarray]:
        xgb_prediction = xgb_ensemble_predict(final_xgb_daily, matrix.point_features)
        deep_prediction = np.mean(
            [deep_predict(model, matrix, device) for model in final_deep], axis=0
        ).astype(np.float32)
        daily_residual = blend_quantiles(xgb_prediction, deep_prediction, xgb_weight)
        total_residual = xgb_ensemble_predict(final_xgb_total, matrix.total_features)
        return daily_residual, total_residual

    known_daily, known_total = predict(known_test)
    cold_daily, cold_total = predict(cold_test)
    evaluation = {
        "known_test": evaluate_candidate(
            known_test,
            known_daily,
            daily_calibration,
            known_total,
            total_calibration,
            total_weight,
        ),
        "cold_start_test": evaluate_candidate(
            cold_test,
            cold_daily,
            daily_calibration,
            cold_total,
            total_calibration,
            total_weight,
        ),
    }
    decision = promotion_decision(
        evaluation["cold_start_test"]["candidate"],
        evaluation["cold_start_test"]["baselines"],
    )

    artifacts: list[dict[str, Any]] = []
    for index, model in enumerate(final_xgb_daily):
        path = output / f"xgb_daily_seed_{active_seeds[index]}.ubj"
        model.save_model(path)
        artifacts.append(
            {"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
        )
    for index, model in enumerate(final_xgb_total):
        path = output / f"xgb_total_seed_{active_seeds[index]}.ubj"
        model.save_model(path)
        artifacts.append(
            {"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
        )
    for index, model in enumerate(final_deep):
        path = output / f"multiscale_seed_{active_seeds[index]}.pt"
        torch.save(model.state_dict(), path)
        artifacts.append(
            {"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
        )

    result = {
        "status": "success",
        "experiment": "month_serious_v2",
        "promoted": decision["promoted"],
        "promotion": decision,
        "protocol": {
            "lookback_days": LOOKBACK_DAYS,
            "horizon_days": HORIZON_DAYS,
            "train_targets_end_before": str(TRAIN_END_DATE),
            "validation_origins": [str(TRAIN_END_DATE), str(VALIDATION_END_DATE)],
            "untouched_test_origins": [
                str(TEST_START_DATE),
                str(TEST_LAST_ORIGIN_DATE),
            ],
            "history_coverage_minimum": MIN_HISTORY_COVERAGE,
            "maximum_history_gap_days": MAX_HISTORY_GAP_DAYS,
            "target_imputation": "none",
            "history_imputation": "causal within-window interpolation after gate",
            "future_weather": "1991-2010 ERA5 day-of-year climatology",
            "realized_future_weather_used": False,
            "baseline": "25% previous-year same-date + 75% trailing four-week weekday profile",
            "baseline_selected_on": "known-household validation only",
            "seeds": list(active_seeds),
        },
        "prepared_data": prepared,
        "windows": {
            "train": len(train_windows),
            "validation": len(validation_windows),
            "known_test": len(known_test_windows),
            "cold_start_test": len(cold_test_windows),
        },
        "features": {
            "daily_point": int(train.point_features.shape[1]),
            "window_total_and_deep": int(train.total_features.shape[1]),
        },
        "selection": {
            "xgboost_weight": xgb_weight,
            "deep_weight": 1.0 - xgb_weight,
            "month_total_head_weight": total_weight,
            "deep_best_epochs": [run.best_epoch for run in deep_runs],
            "deep_validation_pinball": [run.validation_loss for run in deep_runs],
        },
        "calibration": {
            "daily": daily_calibration,
            "month_total": total_calibration,
        },
        "evaluation": evaluation,
        "artifacts": artifacts,
        "training_seconds": time.time() - started,
        "device": str(device),
        "limitations": [
            "The official meter release spans about 27 months, not a complete unseen final year.",
            "ERA5 climatology is available at inference but cannot represent actual 30-day weather anomalies.",
            "London cold-start evidence does not establish Moroccan transfer.",
        ],
    }
    atomic_json(output / "metrics.json", result)
    print(json.dumps(decision, indent=2), flush=True)
    print(json.dumps(evaluation["cold_start_test"]["candidate"], indent=2), flush=True)
    return result


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    root = repository / "models" / "lcl_global_forecasting" / "month_serious_v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=root / "data" / "prepared")
    parser.add_argument("--output", type=Path, default=root / "runs" / "ensemble_v1")
    parser.add_argument("--xgb-estimators", type=int, default=450)
    parser.add_argument("--deep-epochs", type=int, default=30)
    parser.add_argument("--seed-count", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--max-known", type=int, default=None)
    parser.add_argument("--max-cold", type=int, default=None)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
