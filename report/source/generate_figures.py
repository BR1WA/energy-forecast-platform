from __future__ import annotations

from pathlib import Path
import json
import math

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Ellipse, Circle, FancyArrowPatch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "report" / "assets" / "figures"
DIA = ROOT / "report" / "assets" / "diagrams"
FIG.mkdir(parents=True, exist_ok=True)
DIA.mkdir(parents=True, exist_ok=True)

NAVY = "#17324d"
BLUE = "#2474b5"
CYAN = "#2f9eae"
GREEN = "#3b8c6e"
AMBER = "#d8952a"
RED = "#b84a4a"
LIGHT = "#edf3f7"
MID = "#b8c8d5"
DARK = "#1e2933"
GREY = "#637381"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9.5,
        "axes.titlesize": 12,
        "axes.labelsize": 9.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def canvas(width=10, height=4.6):
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fc=LIGHT, ec=BLUE, size=9.5, weight="normal", radius=0.02):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=fc, edgecolor=ec, linewidth=1.25,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, weight=weight, color=DARK)
    return patch


def arrow(ax, x1, y1, x2, y2, color=GREY, style="-|>", lw=1.3, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=color, lw=lw, linestyle=ls))


def project_timeline():
    fig, ax = canvas(11, 4.4)
    ax.text(0.02, 0.93, "From critical replication to an evidence-governed forecasting platform", fontsize=14, weight="bold", color=NAVY)
    phases = [
        ("Apr", "DEPM replication", "Architecture rebuilt\n98-99% reproduced", BLUE),
        ("May", "Leakage audit", "Target/proxy leakage\nidentified", RED),
        ("May", "Scientific pivot", "Continuous target\ncausal validation", AMBER),
        ("Jun", "Modern benchmarks", "CNN-BiLSTM, PatchTST\niTransformer, xPatch", CYAN),
        ("Jul", "Global household models", "TFT, N-BEATS\ncold-start evaluation", GREEN),
        ("Jul", "Product V1", "24 h and 168 h\nartifact contracts", NAVY),
    ]
    xs = np.linspace(0.08, 0.92, len(phases))
    ax.plot([xs[0], xs[-1]], [0.52, 0.52], color=MID, lw=3)
    for i, (date, title, note, color) in enumerate(phases):
        x = xs[i]
        ax.add_patch(Circle((x, 0.52), 0.026, facecolor=color, edgecolor="white", lw=1.5, zorder=3))
        above = i % 2 == 0
        y = 0.61 if above else 0.16
        h = 0.24
        box(ax, x - 0.075, y, 0.15, h, f"{date}\n{title}\n{note}", fc="white", ec=color, size=8.2, weight="normal", radius=0.015)
        ax.plot([x, x], [0.55 if above else 0.49, y if above else y + h], color=color, lw=1)
    save(fig, FIG / "project_timeline.pdf")


def leaky_vs_causal():
    fig, ax = canvas(11, 4.8)
    ax.text(0.02, 0.93, "Why the initial score did not measure future forecasting ability", fontsize=14, weight="bold", color=NAVY)
    ax.text(0.245, 0.83, "Historical leaky pipeline", ha="center", fontsize=11, weight="bold", color=RED)
    ax.text(0.755, 0.83, "Corrected causal pipeline", ha="center", fontsize=11, weight="bold", color=GREEN)
    left = [
        (0.05, "Full time series"), (0.05, "Target-derived features"), (0.05, "Scaler/PCA on all data"),
        (0.05, "Random row split"), (0.05, "Classification accuracy")
    ]
    right = [
        (0.55, "Chronological raw series"), (0.55, "Shifted causal features"), (0.55, "Chronological split"),
        (0.55, "Scaler fit on train only"), (0.55, "Physical-unit forecast metrics")
    ]
    ys = [0.66, 0.53, 0.40, 0.27, 0.14]
    for (_, txt), y in zip(left, ys):
        box(ax, 0.06, y, 0.37, 0.085, txt, fc="#fff3f3", ec=RED, size=9)
    for (_, txt), y in zip(right, ys):
        box(ax, 0.57, y, 0.37, 0.085, txt, fc="#eff8f3", ec=GREEN, size=9)
    for y1, y2 in zip(ys[:-1], ys[1:]):
        arrow(ax, 0.245, y1, 0.245, y2 + 0.087, color=RED)
        arrow(ax, 0.755, y1, 0.755, y2 + 0.087, color=GREEN)
    ax.plot([0.5, 0.5], [0.08, 0.82], color=MID, lw=1.2)
    save(fig, FIG / "leaky_vs_causal.pdf")


def physical_proxy():
    fig, ax = canvas(10, 4.2)
    ax.text(0.02, 0.92, "A physically reconstructible target creates proxy leakage", fontsize=14, weight="bold", color=NAVY)
    box(ax, 0.08, 0.52, 0.2, 0.18, "Voltage\nV (volts)", fc="#eef6fb", ec=BLUE, size=11, weight="bold")
    box(ax, 0.4, 0.52, 0.2, 0.18, "Global intensity\nI (amperes)", fc="#eef6fb", ec=BLUE, size=11, weight="bold")
    box(ax, 0.72, 0.52, 0.2, 0.18, "Active power\nP (watts)", fc="#fff3f3", ec=RED, size=11, weight="bold")
    ax.text(0.34, 0.61, "x", ha="center", va="center", fontsize=20, weight="bold", color=GREY)
    ax.text(0.66, 0.61, "approximately", ha="center", va="center", fontsize=9, color=GREY)
    arrow(ax, 0.61, 0.61, 0.71, 0.61, color=RED, lw=2)
    ax.text(0.5, 0.32, "If the class label is derived from active power, V and I can nearly reconstruct it.", ha="center", fontsize=10.5, color=DARK)
    ax.text(0.5, 0.20, "A simple classifier can therefore score highly without learning temporal demand dynamics.", ha="center", fontsize=10.5, color=RED, weight="bold")
    save(fig, FIG / "physical_proxy.pdf")


def chronological_split():
    fig, ax = canvas(11, 4.5)
    ax.text(0.02, 0.92, "Low Carbon London: one shared 2013 chronology for every household", fontsize=14, weight="bold", color=NAVY)
    x0, y, total_w, h = 0.06, 0.50, 0.88, 0.19
    parts = [
        (6132 / 8760, "Train\n1 Jan 00:00 -- 13 Sep 11:00", BLUE),
        ((7008 - 6132) / 8760, "Validation\n13 Sep 12:00 -- 19 Oct 23:00", AMBER),
        ((8760 - 7008) / 8760, "Test\n20 Oct 00:00 -- 31 Dec 23:00", GREEN),
    ]
    cursor = x0
    for frac, label, color in parts:
        w = total_w * frac
        ax.add_patch(Rectangle((cursor, y), w, h, facecolor=color, edgecolor="white", lw=1.5))
        ax.text(cursor + w / 2, y + h / 2, label, ha="center", va="center", color="white", weight="bold", fontsize=9.5)
        cursor += w
    arrow(ax, x0, 0.35, x0 + total_w, 0.35, color=NAVY, lw=1.6)
    ax.text(0.5, 0.30, "8,760 hourly UTC-aligned positions; boundaries are common to all 2,500 households", ha="center", color=GREY)
    ax.text(0.5, 0.18, "2,000 known households: gradient updates only in train; validation and test are future-time windows.", ha="center", fontsize=9.1)
    ax.text(0.5, 0.09, "500 cold-start households: no gradient updates; test evaluates both future time and unseen-household transfer.", ha="center", fontsize=9.1, color=GREEN, weight="bold")
    save(fig, FIG / "chronological_split.pdf")


def depm_architecture():
    fig, ax = canvas(11, 4.0)
    ax.text(0.02, 0.91, "Simplified DEPM architecture reconstructed during the initial phase", fontsize=14, weight="bold", color=NAVY)
    items = [
        (0.04, "IHEPC\nfeatures", BLUE), (0.22, "Scaling\nand PCA", AMBER), (0.40, "Cascaded\nResNet", CYAN),
        (0.58, "DNN feature\nrepresentation", GREEN), (0.76, "XGBoost\nclassifier", NAVY), (0.90, "High / low\nclass", RED),
    ]
    widths = [0.12, 0.12, 0.13, 0.13, 0.12, 0.08]
    for (x, text, color), w in zip(items, widths):
        box(ax, x, 0.43, w, 0.22, text, fc="white", ec=color, size=9.5, weight="bold")
    for i in range(len(items) - 1):
        x1 = items[i][0] + widths[i]
        x2 = items[i + 1][0]
        arrow(ax, x1 + 0.005, 0.54, x2 - 0.005, 0.54)
    ax.text(0.5, 0.24, "The architecture was reproducible; the central problem was the target and validation protocol.", ha="center", color=RED, weight="bold")
    save(fig, FIG / "depm_architecture.pdf")


def cnn_bilstm_architecture():
    fig, ax = canvas(11, 4.0)
    ax.text(0.02, 0.91, "CNN-BiLSTM forecasting architecture", fontsize=14, weight="bold", color=NAVY)
    labels = ["Causal input\nwindow", "1D convolutions\nlocal patterns", "Pooling /\nregularization", "BiLSTM layers\nsequence context", "Dense head\ncontinuous output", "Future energy\nforecast"]
    colors = [BLUE, CYAN, AMBER, GREEN, NAVY, RED]
    xs = [0.03, 0.20, 0.38, 0.55, 0.73, 0.90]
    ws = [0.12, 0.13, 0.12, 0.13, 0.13, 0.08]
    for x, w, label, color in zip(xs, ws, labels, colors):
        box(ax, x, 0.43, w, 0.22, label, fc="white", ec=color, size=9, weight="bold")
    for i in range(len(xs) - 1):
        arrow(ax, xs[i] + ws[i] + 0.004, 0.54, xs[i + 1] - 0.004, 0.54)
    ax.text(0.5, 0.24, "Chronological evaluation and train-only scaling determine validity more than architectural complexity.", ha="center", color=GREY)
    save(fig, FIG / "cnn_bilstm_architecture.pdf")


def transformer_comparison():
    fig, ax = canvas(11, 4.8)
    ax.text(0.02, 0.93, "Two complementary Transformer views of multivariate forecasting", fontsize=14, weight="bold", color=NAVY)
    ax.text(0.26, 0.83, "PatchTST", ha="center", fontsize=12, weight="bold", color=BLUE)
    ax.text(0.75, 0.83, "iTransformer", ha="center", fontsize=12, weight="bold", color=GREEN)
    for i in range(4):
        ax.add_patch(Rectangle((0.08 + 0.085 * i, 0.58), 0.065, 0.12, facecolor="#dcecf7", edgecolor=BLUE))
        ax.text(0.112 + 0.085 * i, 0.64, f"time\npatch {i+1}", ha="center", va="center", fontsize=7.5)
    arrow(ax, 0.18, 0.52, 0.34, 0.40, color=BLUE)
    box(ax, 0.18, 0.26, 0.20, 0.13, "Attention over\ntime patches", fc="white", ec=BLUE, size=9)
    for i in range(4):
        ax.add_patch(Rectangle((0.58, 0.66 - 0.11 * i), 0.18, 0.075, facecolor="#e2f2ea", edgecolor=GREEN))
        ax.text(0.67, 0.697 - 0.11 * i, f"variable token {i+1}", ha="center", va="center", fontsize=8)
    arrow(ax, 0.77, 0.50, 0.87, 0.50, color=GREEN)
    box(ax, 0.82, 0.30, 0.14, 0.15, "Attention across\nvariables", fc="white", ec=GREEN, size=9)
    ax.text(0.26, 0.14, "Channel-independent temporal representation", ha="center", color=GREY)
    ax.text(0.75, 0.14, "Inverted tokenization for cross-variable relations", ha="center", color=GREY)
    save(fig, FIG / "transformer_comparison.pdf")


def global_tft_flow():
    fig, ax = canvas(11, 4.8)
    ax.text(0.02, 0.94, "Packaged Global TFT serving flow and its validation boundary", fontsize=14, weight="bold", color=NAVY)
    labels = ["Site history\n336 hourly values", "Data gates\ncoverage and gaps", "Serving-time\nwindow z-score", "Calendar\ncovariates", "Frozen Global TFT\nshared weights", "0.1 / 0.5 / 0.9\nquantile forecasts"]
    colors = [BLUE, AMBER, CYAN, GREEN, NAVY, RED]
    xs = [0.025, 0.19, 0.355, 0.52, 0.685, 0.85]
    ws = [0.12] * 5 + [0.13]
    for x, w, label, color in zip(xs, ws, labels, colors):
        box(ax, x, 0.43, w, 0.22, label, fc="white", ec=color, size=8.7, weight="bold")
    for i in range(len(xs) - 1):
        arrow(ax, xs[i] + ws[i] + 0.003, 0.54, xs[i + 1] - 0.003, 0.54)
    ax.text(0.5, 0.26, "Frozen research metrics used per-household statistics fitted on each household's training segment.", ha="center", color=RED, weight="bold")
    ax.text(0.5, 0.16, "The rolling 336-hour serving transform is operationally implemented but not validated by those headline metrics.", ha="center", color=RED)
    save(fig, FIG / "global_tft_flow.pdf")


def model_selection_flow():
    fig, ax = canvas(10.5, 5.2)
    ax.text(0.02, 0.94, "Evidence-gated model promotion", fontsize=14, weight="bold", color=NAVY)
    ys = [0.78, 0.62, 0.46, 0.30, 0.14]
    labels = [
        "Comparable causal protocol and fixed test cohort",
        "Positive improvement over seasonal naive",
        "Robust household distribution: median, p90, cold-start",
        "Reproducible artifact: manifest, hash, shape, finite outputs",
        "Package capability with explicit evidence boundary",
    ]
    colors = [BLUE, CYAN, AMBER, GREEN, NAVY]
    for y, label, color in zip(ys, labels, colors):
        box(ax, 0.20, y, 0.60, 0.095, label, fc="white", ec=color, size=9.5, weight="bold")
    for y1, y2 in zip(ys[:-1], ys[1:]):
        arrow(ax, 0.50, y1, 0.50, y2 + 0.098, color=GREY)
    ax.text(0.84, 0.50, "Fail any gate", color=RED, weight="bold", rotation=90, va="center")
    ax.text(0.91, 0.50, "archive or experimental", color=RED, rotation=90, va="center")
    save(fig, FIG / "model_selection_flow.pdf")


def baseline_chart():
    rows = []
    for h in ("24h", "168h"):
        manifest = json.loads((ROOT / "backend" / "model_artifacts" / f"global_tft_{h}" / "manifest.json").read_text())
        t = manifest["training"]
        rows.append((h, t["cold_start_macro_mae_kwh"], t["cold_start_seasonal_naive_macro_mae_kwh"], t["cold_start_mae_improvement_percent"]))
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(len(rows))
    width = 0.34
    model = [r[1] for r in rows]
    baseline = [r[2] for r in rows]
    ax.bar(x - width/2, model, width, color=BLUE, label="Global TFT")
    ax.bar(x + width/2, baseline, width, color=MID, label="Seasonal naive")
    ax.set_xticks(x, ["24-hour forecast", "168-hour forecast"])
    ax.set_ylabel("Cold-start macro MAE (kWh per hourly interval)")
    ax.set_title("Frozen LCL checkpoints outperform the seasonal baseline")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    for i, (_, m, b, imp) in enumerate(rows):
        ax.text(i - width/2, m + 0.006, f"{m:.3f}", ha="center", fontsize=9)
        ax.text(i + width/2, b + 0.006, f"{b:.3f}", ha="center", fontsize=9)
        ax.text(i, max(m, b) + 0.032, f"{imp:.1f}% lower MAE", ha="center", color=GREEN, weight="bold")
    ax.set_ylim(0, max(baseline) * 1.42)
    save(fig, FIG / "tft_baseline_comparison.pdf")


def ecl_chart():
    df = pd.read_csv(ROOT / "models" / "ecl_deep_benchmark" / "leaderboard.csv")
    models = [m for m in ["itransformer", "patchtst", "xpatch", "cnn_bilstm"] if m in set(df.model)]
    horizons = sorted(df.horizon.unique())
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    colors = [NAVY, BLUE, CYAN, AMBER]
    labels = {"itransformer": "iTransformer", "patchtst": "PatchTST", "xpatch": "xPatch", "cnn_bilstm": "CNN-BiLSTM"}
    for model, color in zip(models, colors):
        part = df[df.model == model].sort_values("horizon")
        ax.plot(part.horizon, part.normalized_mae, marker="o", lw=2, label=labels[model], color=color)
    ax.set_title("ECL benchmark: normalized MAE increases with forecast horizon")
    ax.set_xlabel("Forecast horizon (hours)")
    ax.set_ylabel("Normalized MAE")
    ax.set_xticks(horizons)
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2)
    save(fig, FIG / "ecl_benchmark.pdf")


def tft_training_curves():
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2), sharey=False)
    for ax, task, title in zip(axes, ["day_24h", "week_168h"], ["24-hour TFT", "168-hour TFT"]):
        path = ROOT / "models" / "lcl_global_forecasting" / "full_selected_v1" / "runs" / "global_tft" / task / "history.json"
        history = pd.DataFrame(json.loads(path.read_text()))
        ax.plot(history.epoch, history.training_loss, color=BLUE, marker="o", label="Training pinball loss")
        ax.plot(history.epoch, history.validation_loss, color=AMBER, marker="o", label="Validation pinball loss")
        best = int(history.validation_loss.idxmin())
        ax.scatter(history.epoch.iloc[best], history.validation_loss.iloc[best], s=55, color=GREEN, zorder=3)
        ax.annotate(
            f"best {history.validation_loss.iloc[best]:.4f}",
            (history.epoch.iloc[best], history.validation_loss.iloc[best]),
            xytext=(5, 8), textcoords="offset points", fontsize=8, color=GREEN,
        )
        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Normalized mean pinball loss")
        ax.grid(alpha=0.22)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Frozen Global TFT optimization histories", fontsize=13, weight="bold", color=NAVY)
    fig.tight_layout()
    save(fig, FIG / "tft_training_curves.pdf")


def tft_checkpoint_diagnostics():
    evidence = ROOT / "report" / "evidence"
    day_h = pd.read_csv(evidence / "lcl_tft_day_24h_horizon.csv")
    week_h = pd.read_csv(evidence / "lcl_tft_week_168h_horizon.csv")
    day_house = pd.read_csv(evidence / "lcl_tft_day_24h_households.csv")
    week_house = pd.read_csv(evidence / "lcl_tft_week_168h_households.csv")
    manifest = json.loads((evidence / "lcl_tft_reanalysis_manifest.json").read_text())
    summaries = {row["task"]: row for row in manifest["tasks"]}

    fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.4))
    for frame, label, color in [(day_h, "24 h", BLUE), (week_h, "168 h", GREEN)]:
        axes[0, 0].plot(frame.horizon_step, frame.mae_kwh, color=color, lw=1.8, label=label)
        axes[0, 1].plot(frame.horizon_step, frame.central_80_coverage_percent, color=color, lw=1.8, label=label)
    axes[0, 0].set_title("Median-forecast error by lead time")
    axes[0, 0].set_xlabel("Lead time (hours)")
    axes[0, 0].set_ylabel("MAE (kWh per hourly interval)")
    axes[0, 1].set_title("Central 80% interval coverage by lead time")
    axes[0, 1].set_xlabel("Lead time (hours)")
    axes[0, 1].set_ylabel("Empirical coverage (%)")
    axes[0, 1].axhline(80, color=RED, ls="--", lw=1.2, label="Nominal 80%")
    axes[1, 0].boxplot(
        [day_house.mae_kwh, week_house.mae_kwh], tick_labels=["24 h", "168 h"],
        showfliers=False, patch_artist=True,
        boxprops={"facecolor": LIGHT, "edgecolor": NAVY}, medianprops={"color": RED, "linewidth": 1.5},
    )
    axes[1, 0].set_title("Cold-start household error distribution")
    axes[1, 0].set_ylabel("Household MAE (kWh per hourly interval)")
    hours_day = pd.read_csv(evidence / "lcl_tft_day_24h_hour_of_day.csv")
    hours_week = pd.read_csv(evidence / "lcl_tft_week_168h_hour_of_day.csv")
    axes[1, 1].plot(hours_day.hour_utc, hours_day.mae_kwh, marker="o", color=BLUE, label="24 h")
    axes[1, 1].plot(hours_week.hour_utc, hours_week.mae_kwh, marker="o", color=GREEN, label="168 h")
    axes[1, 1].set_title("Median-forecast error by UTC hour")
    axes[1, 1].set_xlabel("Hour of day (UTC)")
    axes[1, 1].set_ylabel("MAE (kWh per hourly interval)")
    axes[1, 1].set_xticks(range(0, 24, 3))
    for ax in axes.flat:
        ax.grid(alpha=0.22)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(frameon=False)
    axes[0, 1].legend(frameon=False)
    axes[1, 1].legend(frameon=False)
    day_cov = summaries["day_24h"]["central_80_empirical_coverage_percent"]
    week_cov = summaries["week_168h"]["central_80_empirical_coverage_percent"]
    fig.suptitle(
        f"Post-hoc checkpoint diagnostics (overall coverage: {day_cov:.2f}% at 24 h; {week_cov:.2f}% at 168 h)",
        fontsize=12.5, weight="bold", color=NAVY,
    )
    fig.tight_layout()
    save(fig, FIG / "tft_checkpoint_diagnostics.pdf")


def tft_representative_forecasts():
    frame = pd.read_csv(ROOT / "report" / "evidence" / "lcl_tft_day_24h_representative_windows.csv")
    fig, axes = plt.subplots(3, 1, figsize=(10.0, 7.4), sharex=True)
    for ax, profile in zip(axes, ["p10", "median", "p90"]):
        part = frame[frame.profile == profile]
        x = part.horizon_step
        ax.fill_between(x, part.q10_kwh, part.q90_kwh, color=BLUE, alpha=0.16, label="q10--q90")
        ax.plot(x, part.actual_kwh, color=DARK, lw=1.8, label="Observed")
        ax.plot(x, part.median_kwh, color=BLUE, lw=1.6, label="TFT median")
        ax.plot(x, part.seasonal_naive_kwh, color=AMBER, lw=1.1, ls="--", label="Seasonal naive")
        household = int(part.household_index.iloc[0])
        ax.set_title(f"{profile.upper()} household-error profile (index {household}); one preregistered test origin", loc="left", fontsize=9.5)
        ax.set_ylabel("kWh / hour")
        ax.grid(alpha=0.20)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xlabel("Forecast lead time (hours)")
    axes[0].legend(frameon=False, ncol=4, fontsize=8)
    fig.suptitle("Representative 24-hour cold-start forecasts", fontsize=13, weight="bold", color=NAVY)
    fig.tight_layout()
    save(fig, FIG / "tft_representative_forecasts.pdf")


def layered_architecture():
    fig, ax = canvas(10.5, 5.6)
    ax.text(0.02, 0.95, "EnergyAI layered architecture", fontsize=14, weight="bold", color=NAVY)
    layers = [
        (0.76, "Experience layer", "Next.js 16 / React 19\nDashboard, Usage, Forecast, Actions, Settings", BLUE),
        (0.58, "API and policy layer", "FastAPI routers, JWT sessions, RBAC, validation", CYAN),
        (0.40, "Domain services", "Forecasting, ingestion, analytics, alerts, email, account lifecycle", GREEN),
        (0.22, "Persistence and background work", "PostgreSQL 16; alert, email, and\navatar-cleanup workers", AMBER),
        (0.04, "Model artifacts", "Global TFT 24 h and 168 h, manifests, hashes, readiness gates", NAVY),
    ]
    for y, title, text, color in layers:
        ax.add_patch(FancyBboxPatch((0.08, y), 0.84, 0.13, boxstyle="round,pad=0.012,rounding_size=0.015", facecolor="white", edgecolor=color, lw=1.4))
        ax.text(0.12, y + 0.065, title, va="center", ha="left", color=color, weight="bold", fontsize=9.6)
        description_x = 0.47 if title == "Persistence and background work" else 0.44
        ax.text(description_x, y + 0.065, text, va="center", ha="left", color=DARK, fontsize=8.5)
    save(fig, FIG / "energyai_layered_architecture.pdf")


def request_lifecycle():
    fig, ax = canvas(11, 4.5)
    ax.text(0.02, 0.93, "Forecast request lifecycle", fontsize=14, weight="bold", color=NAVY)
    stages = [
        ("1", "Authenticated\nrequest"), ("2", "Capability and\nreadiness check"), ("3", "Owned site and\nhistory query"),
        ("4", "Data-quality\ngates"), ("5", "Artifact load and\ninference"), ("6", "Persist forecast\nand return quantiles"),
    ]
    xs = np.linspace(0.08, 0.92, len(stages))
    for i, (num, label) in enumerate(stages):
        ax.add_patch(Circle((xs[i], 0.57), 0.055, facecolor=BLUE if i < 4 else GREEN, edgecolor="white", lw=1.4))
        ax.text(xs[i], 0.57, num, ha="center", va="center", color="white", weight="bold", fontsize=12)
        ax.text(xs[i], 0.35, label, ha="center", va="center", fontsize=8.5)
        if i < len(stages)-1:
            arrow(ax, xs[i] + 0.06, 0.57, xs[i+1] - 0.06, 0.57, color=MID, lw=2)
    ax.text(0.5, 0.16, "Any failed gate returns a controlled error; no forecast is fabricated.", ha="center", color=RED, weight="bold")
    save(fig, FIG / "forecast_request_lifecycle.pdf")


def use_case():
    fig, ax = canvas(11, 7.2)
    ax.text(0.02, 0.96, "EnergyAI use-case diagram", fontsize=14, weight="bold", color=NAVY)
    ax.add_patch(Rectangle((0.18, 0.08), 0.64, 0.82, facecolor="#fbfdfe", edgecolor=NAVY, lw=1.3))
    ax.text(0.50, 0.875, "EnergyAI system boundary", ha="center", color=NAVY, weight="bold")
    actors = {"User": (0.08, 0.60), "Administrator": (0.08, 0.25)}
    for name, (x, y) in actors.items():
        ax.add_patch(Circle((x, y + 0.08), 0.025, fill=False, ec=DARK, lw=1.2))
        ax.plot([x, x], [y + 0.055, y - 0.02], color=DARK, lw=1.2)
        ax.plot([x - 0.035, x + 0.035], [y + 0.025, y + 0.025], color=DARK, lw=1.2)
        ax.plot([x, x - 0.03], [y - 0.02, y - 0.07], color=DARK, lw=1.2)
        ax.plot([x, x + 0.03], [y - 0.02, y - 0.07], color=DARK, lw=1.2)
        ax.text(x, y - 0.12, name, ha="center", va="top", fontsize=8.5)
    cases = [
        (0.34, 0.74, "FR-01  Authenticate"), (0.58, 0.74, "FR-02  Complete setup"),
        (0.34, 0.58, "FR-03  Preview/import CSV"), (0.58, 0.58, "FR-04  Inspect usage"),
        (0.34, 0.42, "FR-05  Generate 24 h / 168 h forecast"),
        (0.58, 0.42, "FR-06  Review alerts and actions"),
        (0.34, 0.25, "FR-07  Manage settings/account"),
        (0.62, 0.25, "FR-08  Administer users/readiness"),
    ]
    for x, y, label in cases:
        e = Ellipse((x, y), 0.25, 0.10, facecolor="white", edgecolor=BLUE, lw=1.1)
        ax.add_patch(e)
        ax.text(x, y, label, ha="center", va="center", fontsize=7.8)
    for target in [(0.34,0.74),(0.58,0.74),(0.34,0.58),(0.58,0.58),(0.34,0.42),(0.58,0.42),(0.34,0.25)]:
        ax.plot([0.11, target[0]-0.13], [0.62, target[1]], color=GREY, lw=0.8)
    ax.plot([0.11, 0.49], [0.27, 0.25], color=GREY, lw=0.9)
    save(fig, DIA / "use_case.pdf")


def class_domain():
    fig, ax = canvas(12, 8.5)
    ax.text(0.02, 0.96, "Core domain class diagram", fontsize=14, weight="bold", color=NAVY)
    classes = {
        "User": (0.03, 0.71, ["PK id: int", "email: string", "role: enum", "is_active: bool"]),
        "Site": (0.28, 0.71, ["PK id: int", "FK owner_id: int", "name: string", "timezone: string"]),
        "Meter": (0.53, 0.71, ["PK id: int", "FK site_id: int", "name: string", "status: enum"]),
        "SmartMeterReading": (0.78, 0.71, ["PK id: int", "FK meter_id: int", "timestamp: datetime", "energy_kwh: float"]),
        "AlertConfig": (0.03, 0.36, ["PK/FK user_id: int", "thresholds: JSON", "enabled: bool"]),
        "Alert": (0.28, 0.36, ["PK id: int", "FK user_id: int", "type/status: enum", "timestamp: datetime"]),
        "Forecast": (0.53, 0.36, ["PK id: int", "FK user_id/site_id", "horizon_hours: int", "values: JSON"]),
        "IngestionBatch": (0.78, 0.36, ["PK id: int", "FK meter_id: int", "rows: int", "status: enum"]),
        "Recommendation": (0.28, 0.03, ["PK id: int", "FK user_id: int", "category: string", "status: enum"]),
    }
    pos = {}
    for name, (x, y, attrs) in classes.items():
        w, h = 0.18, 0.19
        ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=NAVY, lw=1.2))
        ax.add_patch(Rectangle((x, y+h-0.055), w, 0.055, facecolor=LIGHT, edgecolor=NAVY, lw=1.0))
        title_size = 7.6 if len(name) > 15 else 8.5
        ax.text(x+w/2, y+h-0.027, name, ha="center", va="center", weight="bold", fontsize=title_size)
        ax.text(x+0.012, y+h-0.07, "\n".join(attrs), ha="left", va="top", fontsize=7.4, linespacing=1.25)
        pos[name] = (x, y, w, h)

    def anchor(name, side):
        x, y, w, h = pos[name]
        return {
            "left": (x, y + h / 2),
            "right": (x + w, y + h / 2),
            "top": (x + w / 2, y + h),
            "bottom": (x + w / 2, y),
        }[side]

    def relation(a, b, side_a, side_b, label, mult_a, mult_b, via=(), label_at=None):
        start = anchor(a, side_a)
        end = anchor(b, side_b)
        points = [start, *via, end]
        ax.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            color=GREY,
            lw=1.0,
            zorder=0,
        )
        if label_at is None:
            label_at = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(
            label_at[0],
            label_at[1],
            label,
            ha="center",
            va="center",
            fontsize=6.6,
            color=DARK,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.96),
            zorder=3,
        )
        def outside(point, side, distance=0.014):
            offsets = {
                "left": (-distance, 0),
                "right": (distance, 0),
                "top": (0, distance),
                "bottom": (0, -distance),
            }
            dx, dy = offsets[side]
            return point[0] + dx, point[1] + dy

        for point, side, multiplicity in (
            (start, side_a, mult_a),
            (end, side_b, mult_b),
        ):
            x_text, y_text = outside(point, side)
            ax.text(
                x_text,
                y_text,
                multiplicity,
                ha="center",
                va="center",
                fontsize=6.4,
                color=GREY,
                bbox=dict(fc="white", ec="none", pad=0.05),
                zorder=3,
            )

    relation("User", "Site", "right", "left", "owns", "1", "0..*", label_at=(0.255, 0.825))
    relation("Site", "Meter", "right", "left", "contains", "1", "0..*", label_at=(0.505, 0.825))
    relation("Meter", "SmartMeterReading", "right", "left", "records", "1", "0..*", label_at=(0.755, 0.825))
    relation("User", "AlertConfig", "bottom", "top", "configures", "1", "0..1", label_at=(0.075, 0.635))
    relation(
        "User", "Alert", "bottom", "top", "receives", "1", "0..*",
        via=((0.12, 0.66), (0.37, 0.66)), label_at=(0.245, 0.66),
    )
    relation(
        "Site", "Forecast", "bottom", "top", "has", "1", "0..*",
        via=((0.37, 0.62), (0.62, 0.62)), label_at=(0.495, 0.62),
    )
    relation(
        "Meter", "IngestionBatch", "bottom", "top", "imports", "1", "0..*",
        via=((0.62, 0.60), (0.87, 0.60)), label_at=(0.745, 0.60),
    )
    relation("Alert", "Recommendation", "bottom", "top", "motivates", "0..1", "0..*", label_at=(0.39, 0.295))
    save(fig, DIA / "class_domain.pdf")


def sequence(path: Path, title: str, actors: list[str], messages: list[tuple[int,int,str]], notes=None):
    fig, ax = canvas(11, 6.4)
    ax.text(0.02, 0.96, title, fontsize=14, weight="bold", color=NAVY)
    xs = np.linspace(0.10, 0.90, len(actors))
    for x, actor in zip(xs, actors):
        box(ax, x-0.075, 0.83, 0.15, 0.075, actor, fc=LIGHT, ec=NAVY, size=8.5, weight="bold", radius=0.008)
        ax.plot([x,x],[0.14,0.83],color=MID,lw=1,ls="--")
    top, step = 0.76, 0.095
    for idx,(src,dst,label) in enumerate(messages):
        y=top-idx*step
        x1,x2=xs[src],xs[dst]
        arrow(ax,x1,y,x2,y,color=BLUE if dst>=src else GREEN,lw=1.1)
        ax.text((x1+x2)/2,y+0.018,label,ha="center",va="bottom",fontsize=7.4,color=DARK)
    if notes:
        ax.text(0.5,0.06,notes,ha="center",fontsize=8.2,color=GREY)
    save(fig,path)


def uml_sequences():
    sequence(
        DIA / "sequence_authentication.pdf",
        "Sequence diagram - local authentication",
        ["User", "Next.js", "FastAPI", "PostgreSQL"],
        [(0,1,"submit email and password"),(1,2,"POST /auth/login"),(2,3,"load user and verify hash"),(3,2,"user record"),(2,3,"store refresh-token hash and audit"),(2,1,"access token plus HttpOnly refresh cookie"),(1,0,"authenticated dashboard")],
        "Refresh credentials remain outside JSON and browser storage.",
    )
    sequence(
        DIA / "sequence_csv_import.pdf",
        "Sequence diagram - CSV preview and import",
        ["User", "Next.js", "FastAPI", "PostgreSQL"],
        [(0,1,"select CSV"),(1,2,"POST /meters/{id}/csv/preview"),(2,1,"columns, validation summary, bounded sample"),(0,1,"confirm import"),(1,2,"POST /meters/{id}/csv/import"),(2,3,"ownership check and transactional insert"),(3,2,"batch and reading records"),(2,1,"accepted/rejected counts"),(1,0,"updated usage view")],
        "Preview and import are separate operations; malformed rows are not silently accepted.",
    )
    sequence(
        DIA / "sequence_forecast.pdf",
        "Sequence diagram - 24-hour or 168-hour forecast",
        ["User", "Next.js", "FastAPI", "Forecast service", "PostgreSQL"],
        [(0,1,"choose horizon and run"),(1,2,"POST /forecast/run"),(2,4,"load owned site history"),(4,2,"336-hour context"),(2,3,"validate capability and data gates"),(3,3,"load hash-verified artifact and infer"),(3,2,"quantile forecast"),(2,4,"persist forecast and audit event"),(2,1,"forecast response"),(1,0,"chart, interval, provenance")],
        "No unsupported horizon is generated; readiness failures are returned explicitly.",
    )


def azure_deployment_topology():
    fig, ax = canvas(11, 5.4)
    ax.text(0.02, 0.95, "Verified Product V1 deployment on Microsoft Azure", fontsize=14, weight="bold", color=NAVY)
    ax.text(0.02, 0.90, "Resource group rg-energyai-pfe - Italy North - verified 9 August 2026", fontsize=9.2, color=GREY)

    resource_group = FancyBboxPatch(
        (0.16, 0.10), 0.81, 0.75,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor="#f8fafc", edgecolor=NAVY, linewidth=1.4,
    )
    ax.add_patch(resource_group)
    ax.text(0.175, 0.825, "Azure resource boundary", fontsize=9.5, weight="bold", color=NAVY)

    environment = FancyBboxPatch(
        (0.21, 0.40), 0.56, 0.34,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        facecolor="#edf5fb", edgecolor=BLUE, linewidth=1.2,
    )
    ax.add_patch(environment)
    ax.text(0.225, 0.715, "Container Apps environment: cae-energyai-pfe", fontsize=8.5, weight="bold", color=BLUE)

    box(ax, 0.25, 0.56, 0.20, 0.11, "Web Container App\nca-energyai-web\n0.5 CPU / 1 GiB / 0-1", fc="white", ec=BLUE, size=7.8, weight="bold")
    box(ax, 0.53, 0.56, 0.20, 0.11, "API Container App\nca-energyai-api\n2 CPU / 4 GiB / 0-1", fc="white", ec=GREEN, size=7.8, weight="bold")
    box(ax, 0.39, 0.42, 0.20, 0.09, "Email worker\nca-energyai-email-worker\n1 running replica", fc="white", ec=AMBER, size=7.5, weight="bold")
    box(ax, 0.22, 0.20, 0.20, 0.13, "Private ACR\nacrenergyaipfe2691\nrelease image digests", fc="#fff8e9", ec=AMBER, size=8.0)
    box(ax, 0.48, 0.20, 0.22, 0.13, "Managed PostgreSQL 16\npsql-energyai-br1wa-2691\n32 GiB / 7-day retention", fc="#eef8f3", ec=GREEN, size=8.0)
    box(ax, 0.76, 0.20, 0.18, 0.13, "Key Vault\nkv-energyai-pfe-2691\nexternalized secrets", fc="#f5f0fb", ec="#75529b", size=8.0)

    box(ax, 0.03, 0.53, 0.10, 0.12, "Public\nbrowser", fc=LIGHT, ec=NAVY, size=8.5, weight="bold")
    box(ax, 0.80, 0.67, 0.14, 0.10, "Budget alerts\n80% actual\n100% forecast", fc="#fff8e9", ec=AMBER, size=7.8)

    arrow(ax, 0.13, 0.59, 0.25, 0.61, color=BLUE)
    ax.text(0.185, 0.625, "HTTPS", ha="center", fontsize=7.8, color=BLUE)
    arrow(ax, 0.45, 0.615, 0.53, 0.615, color=BLUE)
    ax.text(0.49, 0.635, "HTTPS API", ha="center", fontsize=7.4, color=BLUE)
    arrow(ax, 0.63, 0.56, 0.59, 0.33, color=GREEN)
    ax.text(0.64, 0.42, "TLS", fontsize=7.6, color=GREEN)
    arrow(ax, 0.49, 0.42, 0.55, 0.33, color=GREEN)
    arrow(ax, 0.34, 0.33, 0.34, 0.56, color=AMBER, ls="--")
    arrow(ax, 0.40, 0.31, 0.56, 0.56, color=AMBER, ls="--")
    arrow(ax, 0.39, 0.30, 0.44, 0.42, color=AMBER, ls="--")
    ax.text(0.35, 0.39, "image pulls", fontsize=7.3, color=AMBER)
    arrow(ax, 0.80, 0.33, 0.70, 0.56, color="#75529b", ls="--")
    arrow(ax, 0.78, 0.28, 0.59, 0.46, color="#75529b", ls="--")
    ax.text(0.75, 0.42, "secrets", fontsize=7.3, color="#75529b")

    ax.text(0.18, 0.055, "Managed HTTPS, the email worker, SMTP capability, and Google identity are verified; alert/avatar workers and durable avatar storage remain outside this boundary.", fontsize=7.9, color=GREY)
    save(fig, DIA / "azure_deployment_topology.pdf")


def main():
    project_timeline()
    leaky_vs_causal()
    physical_proxy()
    chronological_split()
    depm_architecture()
    cnn_bilstm_architecture()
    transformer_comparison()
    global_tft_flow()
    model_selection_flow()
    baseline_chart()
    ecl_chart()
    tft_training_curves()
    tft_checkpoint_diagnostics()
    tft_representative_forecasts()
    layered_architecture()
    request_lifecycle()
    use_case()
    class_domain()
    uml_sequences()
    azure_deployment_topology()
    print(f"Generated figures in {FIG} and {DIA}")


if __name__ == "__main__":
    main()
