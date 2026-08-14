"""Prepare the fresh Portugal and Morocco 30-day production challenge.

The Portugal source is the official UCI 2011--2014 15-minute load matrix.
The values are average kW per interval, so daily energy is ``sum(kW) / 4``.
Leading zeroes before a meter becomes active are represented as missing.

The Morocco workbook contains three ampere datasets and one kW dataset.  The
ampere channels remain daily mean current (they cannot honestly be converted
to energy without voltage and power factor); Marrakech is integrated to kWh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import polars as pl

SEED = 2026
PORTUGAL_MEMBER = "LD2011_2014.txt"
PORTUGAL_SHA256 = "F6C4D0E0DF12ECDB9EA008DD6EEF3518ADB52C559D04A9BAC2E1B81DCFC8D4E1"
MOROCCO_SHA256 = "04A9A3CC5ADDFFBD0D2E2EAC898B51065D7D9F7EA457C9C28DBA6B703CA19021"
TETOUAN_SHA256 = "3C4BF684161180937043A9FB65701A83D44B740B0D42F0492B6E7AEC57DDBBFE"
MOROCCO_COLD = {
    "Laayoune::Zone 5",
    "Boujdour::Zone 3",
    "Foum eloued::Zone 7",
    "Marrakech::Zone 2",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


def extract_portugal(archive_path: Path, extraction_dir: Path) -> Path:
    extraction_dir.mkdir(parents=True, exist_ok=True)
    output = extraction_dir / PORTUGAL_MEMBER
    if output.exists() and output.stat().st_size == 710_998_915:
        return output
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Portugal UCI archive failed ZIP integrity checking.")
        with archive.open(PORTUGAL_MEMBER) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
    return output


def prepare_portugal(csv_path: Path, output: Path) -> dict:
    print("Reading the 711 MB Portugal UCI matrix with Polars...", flush=True)
    with csv_path.open("r", encoding="utf-8") as handle:
        header = handle.readline().strip().split(";")
    source_clients = [column.strip('"') for column in header[1:]]
    frame = pl.read_csv(
        csv_path,
        separator=";",
        decimal_comma=True,
        try_parse_dates=True,
        infer_schema_length=10_000,
        schema_overrides={client: pl.Float32 for client in source_clients},
        rechunk=True,
    )
    timestamp_column = frame.columns[0]
    timestamps = frame[timestamp_column].to_numpy().astype("datetime64[m]")
    if frame.height % 96:
        raise RuntimeError(
            f"Expected complete 96-interval days, got {frame.height} rows."
        )
    interval_minutes = np.diff(timestamps).astype("timedelta64[m]").astype(np.int64)
    if not np.all(interval_minutes == 15):
        raise RuntimeError("Portugal timestamps are not a continuous 15-minute grid.")

    clients = frame.columns[1:]
    intervals = frame.select(clients).to_numpy().astype(np.float32, copy=False)
    n_days = frame.height // 96
    daily = intervals.reshape(n_days, 96, len(clients)).sum(axis=1).T / 4.0
    # Timestamps label the end of each interval.  Subtracting 15 minutes makes
    # the last interval of a day land on 23:45 instead of midnight next day.
    dates = (timestamps[::96] - np.timedelta64(15, "m")).astype("datetime64[D]")
    expected = np.arange(dates[0], dates[0] + np.timedelta64(n_days, "D"))
    if not np.array_equal(dates, expected):
        raise RuntimeError(
            "Portugal source does not materialize one complete row per day."
        )

    first_positive = np.full(len(clients), n_days, dtype=np.int32)
    for client in range(len(clients)):
        positive = np.flatnonzero(daily[client] > 0)
        if positive.size:
            first_positive[client] = int(positive[0])
            daily[client, : positive[0]] = np.nan

    evaluation_mask = (dates >= np.datetime64("2013-01-01")) & (
        dates <= np.datetime64("2014-12-31")
    )
    active_by = np.searchsorted(dates, np.datetime64("2013-01-01"))
    positive_fraction = np.mean(daily[:, evaluation_mask] > 0, axis=1)
    eligible = (first_positive <= active_by) & (positive_fraction >= 0.90)
    retained_indices = np.flatnonzero(eligible)
    daily = daily[eligible]
    retained_clients = [clients[index] for index in retained_indices]

    rng = np.random.default_rng(SEED)
    shuffled = rng.permutation(len(retained_clients))
    n_cold = max(1, int(round(0.20 * len(retained_clients))))
    cold = np.sort(shuffled[:n_cold]).astype(np.int32)
    known = np.sort(shuffled[n_cold:]).astype(np.int32)

    np.save(output / "portugal_daily_kwh.npy", daily.astype(np.float32))
    np.save(output / "portugal_dates.npy", dates)
    np.save(output / "portugal_known.npy", known)
    np.save(output / "portugal_cold.npy", cold)
    np.save(output / "portugal_known_daily_kwh.npy", daily[known].astype(np.float32))
    np.save(output / "portugal_cold_daily_kwh.npy", daily[cold].astype(np.float32))
    (output / "portugal_known_clients.json").write_text(
        json.dumps([retained_clients[index] for index in known], indent=2),
        encoding="utf-8",
    )
    (output / "portugal_cold_clients.json").write_text(
        json.dumps([retained_clients[index] for index in cold], indent=2),
        encoding="utf-8",
    )
    (output / "portugal_clients.json").write_text(
        json.dumps(retained_clients, indent=2), encoding="utf-8"
    )
    return {
        "source_clients": len(clients),
        "eligible_clients": len(retained_clients),
        "known_clients": len(known),
        "cold_clients": len(cold),
        "shape": list(daily.shape),
        "first_date": str(dates[0]),
        "last_date": str(dates[-1]),
        "missing_fraction": float(np.mean(~np.isfinite(daily))),
        "positive_fraction_2013_2014_min": float(positive_fraction[eligible].min()),
        "split_seed": SEED,
    }


def normalize_zone_name(value: str) -> str:
    text = str(value).strip()
    if text.lower().startswith("zone"):
        suffix = text[4:].strip()
        if suffix:
            return f"Zone {suffix}"
    return text


def prepare_morocco(workbook_path: Path, output: Path) -> dict:
    print("Aggregating the four Morocco workbook sheets...", flush=True)
    excel = pd.ExcelFile(workbook_path, engine="openpyxl")
    frames: list[pd.DataFrame] = []
    series_metadata: list[dict] = []
    for sheet in excel.sheet_names:
        source = pd.read_excel(excel, sheet_name=sheet)
        date_column = source.columns[0]
        source[date_column] = pd.to_datetime(source[date_column], errors="raise")
        source = source.set_index(date_column).sort_index()
        normalized_site = "Foum eloued" if sheet.lower().startswith("foum") else sheet
        minutes = int(
            np.median(np.diff(source.index.values).astype("timedelta64[m]").astype(int))
        )
        expected_per_day = 24 * 60 // minutes
        for original_zone in source.columns:
            zone = normalize_zone_name(original_zone)
            unique_id = f"{normalized_site}::{zone}"
            values = pd.to_numeric(source[original_zone], errors="coerce")
            daily_count = values.resample("D").count()
            if normalized_site == "Marrakech":
                daily = values.resample("D").sum(min_count=max(1, expected_per_day - 2))
                daily = daily * (minutes / 60.0)
                unit = "daily_kwh"
            else:
                daily = values.resample("D").mean()
                daily[daily_count < expected_per_day - 7] = np.nan
                unit = "daily_mean_ampere"
            frame = pd.DataFrame(
                {
                    "unique_id": unique_id,
                    "ds": daily.index,
                    "y": daily.to_numpy(dtype=np.float32),
                }
            ).dropna(subset=["y"])
            frames.append(frame)
            series_metadata.append(
                {
                    "unique_id": unique_id,
                    "site": normalized_site,
                    "zone": zone,
                    "source_interval_minutes": minutes,
                    "unit": unit,
                    "observations": len(frame),
                    "first_date": frame["ds"].min().date().isoformat(),
                    "last_date": frame["ds"].max().date().isoformat(),
                    "cold": unique_id in MOROCCO_COLD,
                }
            )
    daily_long = pd.concat(frames, ignore_index=True).sort_values(["unique_id", "ds"])
    missing_cold = MOROCCO_COLD - set(daily_long["unique_id"].unique())
    if missing_cold:
        raise RuntimeError(
            f"Frozen Morocco cold series are absent: {sorted(missing_cold)}"
        )
    daily_long.to_parquet(output / "morocco_daily.parquet", index=False)
    daily_long[~daily_long["unique_id"].isin(MOROCCO_COLD)].to_parquet(
        output / "morocco_known_daily.parquet", index=False
    )
    daily_long[daily_long["unique_id"].isin(MOROCCO_COLD)].to_parquet(
        output / "morocco_cold_daily.parquet", index=False
    )
    return {
        "sheets": excel.sheet_names,
        "series": series_metadata,
        "n_series": len(series_metadata),
        "n_known": sum(not item["cold"] for item in series_metadata),
        "n_cold": sum(item["cold"] for item in series_metadata),
        "rows": len(daily_long),
    }


def prepare_tetouan(archive_path: Path, output: Path) -> dict:
    """Materialize the fresh transfer gate without inspecting model scores."""

    print("Aggregating the fresh Tetouan transfer dataset...", flush=True)
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Tetouan UCI archive failed ZIP integrity checking.")
        with archive.open("Tetuan City power consumption.csv") as source:
            frame = pd.read_csv(source)
    timestamp_column = frame.columns[0]
    frame[timestamp_column] = pd.to_datetime(
        frame[timestamp_column], dayfirst=False, errors="raise"
    )
    frame = frame.set_index(timestamp_column).sort_index()
    zone_columns = [column for column in frame if "Power Consumption" in column]
    chunks = []
    metadata = []
    for zone in zone_columns:
        values = pd.to_numeric(frame[zone], errors="raise")
        counts = values.resample("D").count()
        daily = values.resample("D").mean()
        daily[counts < 137] = np.nan
        unique_id = zone.replace(" Power Consumption", "")
        chunk = pd.DataFrame(
            {
                "unique_id": unique_id,
                "ds": daily.index,
                "y": daily.to_numpy(dtype=np.float32),
            }
        ).dropna(subset=["y"])
        chunks.append(chunk)
        metadata.append(
            {
                "unique_id": unique_id,
                "unit": "daily_mean_reported_power",
                "observations": len(chunk),
                "first_date": chunk["ds"].min().date().isoformat(),
                "last_date": chunk["ds"].max().date().isoformat(),
            }
        )
    daily_long = pd.concat(chunks, ignore_index=True).sort_values(["unique_id", "ds"])
    daily_long.to_parquet(output / "tetouan_cold_daily.parquet", index=False)
    return {
        "n_series": len(metadata),
        "rows": len(daily_long),
        "series": metadata,
        "future_weather_columns_dropped": [
            column for column in frame if column not in zone_columns
        ],
    }


def prepare(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    portugal_archive = args.portugal_archive.resolve()
    morocco_archive = args.morocco_archive.resolve()
    morocco_workbook = args.morocco_workbook.resolve()
    tetouan_archive = args.tetouan_archive.resolve()
    if sha256(portugal_archive) != PORTUGAL_SHA256:
        raise RuntimeError(
            "Portugal archive checksum differs from the frozen protocol."
        )
    if sha256(morocco_archive) != MOROCCO_SHA256:
        raise RuntimeError("Morocco archive checksum differs from the frozen protocol.")
    if sha256(tetouan_archive) != TETOUAN_SHA256:
        raise RuntimeError("Tetouan archive checksum differs from the frozen protocol.")
    portugal_csv = extract_portugal(
        portugal_archive, portugal_archive.parent / "portugal_uci"
    )
    portugal = prepare_portugal(portugal_csv, output)
    morocco = prepare_morocco(morocco_workbook, output)
    tetouan = prepare_tetouan(tetouan_archive, output)
    manifest = {
        "preprocessing_version": 1,
        "portugal_archive": {
            "path": str(portugal_archive),
            "bytes": portugal_archive.stat().st_size,
            "sha256": PORTUGAL_SHA256,
        },
        "morocco_archive": {
            "path": str(morocco_archive),
            "bytes": morocco_archive.stat().st_size,
            "sha256": MOROCCO_SHA256,
        },
        "tetouan_archive": {
            "path": str(tetouan_archive),
            "bytes": tetouan_archive.stat().st_size,
            "sha256": TETOUAN_SHA256,
        },
        "portugal": portugal,
        "morocco": morocco,
        "tetouan": tetouan,
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
    target = (
        repository
        / "models"
        / "lcl_global_forecasting"
        / "month_production_v3"
        / "data"
        / "prepared"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--portugal-archive",
        type=Path,
        default=raw / "uci_electricity_load_diagrams_2011_2014.zip",
    )
    parser.add_argument(
        "--morocco-archive",
        type=Path,
        default=raw / "uci_morocco_high_resolution_load.zip",
    )
    parser.add_argument(
        "--morocco-workbook",
        type=Path,
        default=raw / "morocco_uci" / "Data Morocco.xlsx",
    )
    parser.add_argument(
        "--tetouan-archive",
        type=Path,
        default=repository
        / "models"
        / "lcl_global_forecasting"
        / "month_production_v3"
        / "data"
        / "raw"
        / "uci_tetouan_power_consumption.zip",
    )
    parser.add_argument("--output", type=Path, default=target)
    return parser.parse_args()


if __name__ == "__main__":
    prepare(parse_args())
