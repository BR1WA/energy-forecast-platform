"""Prepare the official multi-year Low Carbon London monthly dataset.

The official partitioned archive contains about 167 million half-hour rows.
This script streams its 168 compressed members with Polars, removes exact
duplicate meter timestamps, converts end-of-interval timestamps to energy-day
labels, and materializes a compact household-by-day matrix without extracting
the 8.5 GB CSV corpus.

Historical ERA5 weather is split into two causal roles:

* actual observations may only be consumed before a forecast origin;
* future dates receive 1991--2010 day-of-year climatology, never realized
  target-period weather.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from zipfile import ZipFile

import holidays
import numpy as np
import pandas as pd
import polars as pl

OFFICIAL_ARCHIVE_URL = (
    "https://data.london.gov.uk/download/vqm0d/"
    "04feba67-f1a3-4563-98d0-f3071e3d56d1/Partitioned%20LCL%20Data.zip"
)
WEATHER_API_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=51.5074&"
    "longitude=-0.1278&start_date=1991-01-01&end_date=2014-02-28&"
    "daily=temperature_2m_mean,temperature_2m_min,temperature_2m_max,"
    "apparent_temperature_mean,precipitation_sum,sunshine_duration,"
    "wind_speed_10m_max,shortwave_radiation_sum&timezone=Europe%2FLondon&"
    "models=era5"
)
CLIMATOLOGY_START = np.datetime64("1991-01-01")
CLIMATOLOGY_END = np.datetime64("2010-12-31")
MIN_HALF_HOURS_PER_DAY = 46
MIN_HOUSEHOLD_COVERAGE = 0.80
SEED = 2026


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


def member_number(name: str) -> int:
    match = re.search(r"_(\d+)\.csv$", name)
    if match is None:
        raise ValueError(f"Unexpected LCL archive member: {name}")
    return int(match.group(1))


def aggregate_member(archive: ZipFile, member: str) -> pl.DataFrame:
    """Read, deduplicate, and aggregate one million-row archive member."""

    with archive.open(member) as stream:
        frame = pl.read_csv(stream, infer_schema_length=0)
    value_column = next(
        (column for column in frame.columns if column.strip().startswith("KWH/hh")),
        None,
    )
    if value_column is None:
        raise RuntimeError(f"No energy column found in {member}: {frame.columns}")

    frame = (
        frame.filter(pl.col("stdorToU") == "Std")
        .unique(
            subset=["LCLid", "DateTime"],
            keep="first",
            maintain_order=True,
        )
        .with_columns(
            (
                pl.col("DateTime").str.to_datetime("%Y-%m-%d %H:%M:%S%.f", strict=False)
                - pl.duration(minutes=30)
            )
            .dt.date()
            .alias("date"),
            pl.col(value_column)
            .str.strip_chars()
            .cast(pl.Float32, strict=False)
            .alias("kwh"),
        )
        .filter(pl.col("date").is_not_null() & pl.col("kwh").is_not_null())
    )
    return frame.group_by(["LCLid", "date"]).agg(
        pl.col("kwh").sum().alias("kwh_sum"),
        pl.col("kwh").count().alias("half_hours"),
    )


def aggregate_archive(archive_path: Path) -> pl.DataFrame:
    started = time.time()
    partial: list[pl.DataFrame] = []
    with ZipFile(archive_path) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            raise RuntimeError(f"Corrupt ZIP member: {corrupt}")
        members = sorted(
            [item.filename for item in archive.infolist() if not item.is_dir()],
            key=member_number,
        )
        for index, member in enumerate(members, start=1):
            partial.append(aggregate_member(archive, member))
            if index == 1 or index % 10 == 0 or index == len(members):
                print(
                    f"Aggregated {index}/{len(members)} members in "
                    f"{time.time() - started:.1f}s",
                    flush=True,
                )

    # A household-day can straddle two one-million-row members. Re-aggregate
    # member-level results, but partition boundaries themselves do not overlap.
    daily = (
        pl.concat(partial, rechunk=True)
        .group_by(["LCLid", "date"])
        .agg(
            pl.col("kwh_sum").sum().alias("kwh_sum"),
            pl.col("half_hours").sum().alias("half_hours"),
        )
        .with_columns(
            pl.when(pl.col("half_hours") >= MIN_HALF_HOURS_PER_DAY)
            .then(
                pl.col("kwh_sum") * (48.0 / pl.col("half_hours").clip(upper_bound=48))
            )
            .otherwise(None)
            .cast(pl.Float32)
            .alias("daily_kwh")
        )
    )
    return daily


def dense_household_matrix(
    daily: pl.DataFrame,
) -> tuple[np.ndarray, np.ndarray, list[str], dict]:
    first_date = np.datetime64(daily["date"].min(), "D")
    last_date = np.datetime64(daily["date"].max(), "D")
    dates = np.arange(first_date, last_date + np.timedelta64(1, "D"))
    households = sorted(daily["LCLid"].unique().to_list())
    household_index = {household: index for index, household in enumerate(households)}

    matrix = np.full((len(households), len(dates)), np.nan, dtype=np.float32)
    counts = np.zeros((len(households), len(dates)), dtype=np.uint8)
    compact = daily.select("LCLid", "date", "daily_kwh", "half_hours")
    house_rows = np.fromiter(
        (household_index[item] for item in compact["LCLid"]),
        dtype=np.int32,
        count=compact.height,
    )
    date_values = compact["date"].to_numpy().astype("datetime64[D]")
    day_rows = (date_values - first_date).astype(np.int32)
    energy = compact["daily_kwh"].to_numpy().astype(np.float32)
    half_hours = compact["half_hours"].to_numpy().astype(np.int16)
    finite = np.isfinite(energy)
    matrix[house_rows[finite], day_rows[finite]] = energy[finite]
    counts[house_rows, day_rows] = np.minimum(half_hours, 255).astype(np.uint8)

    coverage = np.isfinite(matrix).mean(axis=1)
    eligible = coverage >= MIN_HOUSEHOLD_COVERAGE
    matrix = matrix[eligible]
    counts = counts[eligible]
    retained_households = [
        household for household, keep in zip(households, eligible) if keep
    ]
    retained_coverage = coverage[eligible]
    summary = {
        "source_households": len(households),
        "retained_households": len(retained_households),
        "minimum_coverage": MIN_HOUSEHOLD_COVERAGE,
        "retained_coverage_min": float(retained_coverage.min()),
        "retained_coverage_median": float(np.median(retained_coverage)),
        "retained_coverage_max": float(retained_coverage.max()),
        "first_energy_date": str(first_date),
        "last_energy_date": str(last_date),
        "n_days": len(dates),
    }
    return matrix, counts, retained_households, summary


def weather_arrays(
    weather_path: Path, dates: np.ndarray
) -> tuple[np.ndarray, np.ndarray, list[str], dict]:
    payload = json.loads(weather_path.read_text(encoding="utf-8"))
    daily = payload["daily"]
    weather_dates = np.asarray(daily["time"], dtype="datetime64[D]")
    variables = [name for name in daily if name != "time"]
    values = np.column_stack(
        [np.asarray(daily[name], dtype=np.float32) for name in variables]
    )
    if not np.isfinite(values).all():
        raise RuntimeError("Weather archive contains missing or non-finite values.")

    frame = pd.DataFrame(values, columns=variables)
    frame["date"] = pd.to_datetime(weather_dates)
    climate_mask = (weather_dates >= CLIMATOLOGY_START) & (
        weather_dates <= CLIMATOLOGY_END
    )
    climate = frame.loc[climate_mask].copy()
    climate["month_day"] = climate["date"].dt.strftime("%m-%d")
    normals = climate.groupby("month_day", sort=False)[variables].mean()

    wanted_index = pd.DatetimeIndex(dates.astype("datetime64[ns]"))
    month_day = wanted_index.strftime("%m-%d")
    climatology = np.empty((len(dates), len(variables)), dtype=np.float32)
    for row, key in enumerate(month_day):
        if key == "02-29" and key not in normals.index:
            climatology[row] = (
                normals.loc["02-28"].to_numpy(dtype=np.float32)
                + normals.loc["03-01"].to_numpy(dtype=np.float32)
            ) / 2.0
        else:
            climatology[row] = normals.loc[key].to_numpy(dtype=np.float32)

    lookup = {date: index for index, date in enumerate(weather_dates)}
    actual = np.stack([values[lookup[date]] for date in dates]).astype(np.float32)
    summary = {
        "provider": "Open-Meteo historical weather API",
        "model": "ERA5",
        "latitude": payload["latitude"],
        "longitude": payload["longitude"],
        "elevation_m": payload.get("elevation"),
        "climatology_start": str(CLIMATOLOGY_START),
        "climatology_end": str(CLIMATOLOGY_END),
        "variables": variables,
        "units": payload["daily_units"],
        "future_policy": "1991-2010 day-of-year climatology only",
    }
    return actual, climatology, variables, summary


def calendar_array(dates: np.ndarray) -> tuple[np.ndarray, list[str]]:
    index = pd.DatetimeIndex(dates.astype("datetime64[ns]"))
    uk_holidays = holidays.UnitedKingdom(years=sorted(set(index.year)))
    angle_weekday = 2.0 * np.pi * index.dayofweek.to_numpy() / 7.0
    angle_year = 2.0 * np.pi * (index.dayofyear.to_numpy() - 1) / 365.2425
    is_holiday = np.asarray(
        [timestamp.date() in uk_holidays for timestamp in index], dtype=np.float32
    )
    is_workday = np.asarray(
        [
            timestamp.dayofweek < 5 and timestamp.date() not in uk_holidays
            for timestamp in index
        ],
        dtype=np.float32,
    )
    calendar = np.column_stack(
        [
            np.sin(angle_weekday),
            np.cos(angle_weekday),
            np.sin(angle_year),
            np.cos(angle_year),
            is_workday,
            is_holiday,
            index.is_month_start.astype(np.float32),
            index.is_month_end.astype(np.float32),
        ]
    ).astype(np.float32)
    names = [
        "weekday_sin",
        "weekday_cos",
        "year_sin",
        "year_cos",
        "is_workday",
        "is_holiday",
        "is_month_start",
        "is_month_end",
    ]
    return calendar, names


def prepare(args: argparse.Namespace) -> dict:
    archive_path = args.archive.resolve()
    weather_path = args.weather.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists() or not weather_path.exists():
        raise FileNotFoundError("Official LCL archive and weather JSON are required.")

    print("Streaming official LCL archive...", flush=True)
    daily = aggregate_archive(archive_path)
    print("Building dense household matrix...", flush=True)
    values, counts, households, household_summary = dense_household_matrix(daily)
    dates = np.arange(
        np.datetime64(household_summary["first_energy_date"]),
        np.datetime64(household_summary["last_energy_date"]) + np.timedelta64(1, "D"),
    )
    actual_weather, climate_weather, weather_names, weather_summary = weather_arrays(
        weather_path, dates
    )
    calendar, calendar_names = calendar_array(dates)

    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(households))
    cold_size = int(round(0.20 * len(households)))
    cold = np.sort(order[:cold_size]).astype(np.int32)
    known = np.sort(order[cold_size:]).astype(np.int32)

    np.save(output / "daily_kwh.npy", values)
    np.save(output / "daily_half_hour_counts.npy", counts)
    np.save(output / "dates.npy", dates)
    np.save(output / "actual_weather.npy", actual_weather)
    np.save(output / "climatology_weather.npy", climate_weather)
    np.save(output / "calendar.npy", calendar)
    np.save(output / "known_households.npy", known)
    np.save(output / "cold_households.npy", cold)
    (output / "households.json").write_text(
        json.dumps(households, indent=2), encoding="utf-8"
    )

    manifest = {
        "preprocessing_version": 1,
        "seed": SEED,
        "official_archive": {
            "url": OFFICIAL_ARCHIVE_URL,
            "path": str(archive_path),
            "bytes": archive_path.stat().st_size,
            "sha256": sha256(archive_path),
            "license": "Creative Commons Attribution",
            "duplicate_policy": "drop exact duplicate LCLid+DateTime rows",
            "timestamp_policy": "subtract 30 minutes before energy-day assignment",
            "daily_quality_gate_half_hours": MIN_HALF_HOURS_PER_DAY,
            "partial_day_adjustment": "scale 46-47 accepted intervals to 48; cap divisor at 48",
        },
        "weather_source": {
            "url": WEATHER_API_URL,
            "path": str(weather_path),
            "bytes": weather_path.stat().st_size,
            "sha256": sha256(weather_path),
            **weather_summary,
        },
        "households": household_summary,
        "n_known": int(len(known)),
        "n_cold_start": int(len(cold)),
        "daily_shape": list(values.shape),
        "weather_shape": list(actual_weather.shape),
        "calendar_shape": list(calendar.shape),
        "weather_features": weather_names,
        "calendar_features": calendar_names,
        "missing_daily_fraction": float(np.mean(~np.isfinite(values))),
    }
    atomic_json(output / "prepared.json", manifest)
    print(json.dumps(manifest, indent=2), flush=True)
    return manifest


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    raw = (
        repository
        / "models"
        / "lcl_global_forecasting"
        / "month_serious_v2"
        / "data"
        / "raw"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=raw / "Partitioned_LCL_Data.zip"
    )
    parser.add_argument(
        "--weather", type=Path, default=raw / "london_weather_1991_2014.json"
    )
    parser.add_argument("--output", type=Path, default=raw.parent / "prepared")
    return parser.parse_args()


if __name__ == "__main__":
    prepare(parse_args())
