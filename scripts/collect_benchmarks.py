"""
scripts/collect_benchmarks.py

Scan the experiments directory and compile a benchmark table from
all metrics.json files. Outputs a markdown table + CSV file.

Usage:
    python scripts/collect_benchmarks.py
    python scripts/collect_benchmarks.py --dataset ihepc --horizon 24
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"


def collect(dataset: str = None, horizon: int = None) -> pd.DataFrame:
    rows = []
    for metrics_path in sorted(EXPERIMENTS_DIR.rglob("metrics.json")):
        parts = metrics_path.parts
        # Structure: experiments/<dataset>/lookback<N>/horizon<N>/<model>/<timestamp>/metrics.json
        try:
            ds_idx = parts.index("experiments") + 1
            ds = parts[ds_idx]
            lookback_str = parts[ds_idx + 1]   # e.g. lookback96
            horizon_str = parts[ds_idx + 2]    # e.g. horizon24
            model = parts[ds_idx + 3]
            timestamp = parts[ds_idx + 4]
        except (ValueError, IndexError):
            continue

        h = int(horizon_str.replace("horizon", ""))
        lb = int(lookback_str.replace("lookback", ""))

        if dataset and ds != dataset:
            continue
        if horizon and h != horizon:
            continue

        with open(metrics_path) as f:
            m = json.load(f)

        # Enhance model name with hyperparameters if training_config.yaml exists
        config_path = metrics_path.parent / "training_config.yaml"
        if config_path.exists():
            import yaml
            try:
                with open(config_path) as cf:
                    cfg = yaml.safe_load(cf)
                    if cfg and "model" in cfg and "training" in cfg:
                        p = cfg["model"].get("patch_length", 16)
                        s = cfg["model"].get("stride", 8)
                        d = cfg["model"].get("d_model", 64)
                        lr = cfg["training"].get("lr", 0.001)
                        # Format nicely
                        model = f"{model} (p={p},s={s},d={d},lr={lr})"
            except Exception:
                pass

        rows.append({
            "dataset":   ds,
            "lookback":  lb,
            "horizon":   h,
            "model":     model,
            "timestamp": timestamp,
            "MAE":       round(m.get("mae", float("nan")), 4),
            "RMSE":      round(m.get("rmse", float("nan")), 4),
            "MAPE%":     round(m.get("mape", float("nan")), 2),
            "sMAPE%":    round(m.get("smape", float("nan")), 2),
            "R2":        round(m.get("r2", float("nan")), 4),
            "MedAE":     round(m.get("median_ae", float("nan")), 4),
            "MaxAE":     round(m.get("max_ae", float("nan")), 4),
            "Fit(s)":    round(m.get("fit_time_s", 0), 1),
            "Inf(ms)":   round(m.get("inference_ms_per_sample", 0), 4),
            "Size(MB)":  round(m.get("model_size_mb", 0) or 0, 3),
        })

    if not rows:
        print("No experiments found.")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Keep only the latest run per (dataset, horizon, model) combo
    df = (
        df.sort_values("timestamp")
          .groupby(["dataset", "lookback", "horizon", "model"], as_index=False)
          .last()
    )
    df = df.sort_values(["dataset", "horizon", "MAE"])
    return df


def to_markdown(df: pd.DataFrame) -> str:
    display_cols = ["model", "MAE", "RMSE", "R2", "MedAE", "MaxAE", "MAPE%", "sMAPE%", "Fit(s)", "Inf(ms)", "Size(MB)"]
    available = [c for c in display_cols if c in df.columns]

    lines = []
    for (ds, lb, h), group in df.groupby(["dataset", "lookback", "horizon"]):
        lines.append(f"\n## Dataset: {ds.upper()} | Lookback: {lb}h | Horizon: {h}h\n")
        sub = group[available].copy()
        # Bold the best (lowest) MAE row
        best_idx = sub["MAE"].idxmin()
        lines.append(sub.to_markdown(index=False))
        lines.append(f"\n*Best MAE: **{sub.loc[best_idx, 'model']}** ({sub.loc[best_idx, 'MAE']:.4f})*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--horizon", type=int, default=None)
    parser.add_argument("--output", default=None, help="Optional path to write markdown report")
    args = parser.parse_args()

    df = collect(args.dataset, args.horizon)
    if df.empty:
        return

    print("\n" + "=" * 72)
    print("BENCHMARK RESULTS")
    print("=" * 72)
    md = to_markdown(df)
    print(md)

    # Save CSV
    csv_path = PROJECT_ROOT / "results" / "benchmark.csv"
    csv_path.parent.mkdir(exist_ok=True)
    df.to_csv(csv_path, index=False)
    print(f"\nSaved CSV: {csv_path}")

    # Save JSON
    json_path = PROJECT_ROOT / "results" / "benchmark.json"
    df.to_json(json_path, orient="records", indent=2)
    print(f"Saved JSON: {json_path}")
    
    # Save markdown
    out_path = Path(args.output) if args.output else PROJECT_ROOT / "results" / "benchmark.md"
    out_path.write_text("# Benchmark Results\n" + md)
    print(f"Saved Markdown: {out_path}")


if __name__ == "__main__":
    main()
