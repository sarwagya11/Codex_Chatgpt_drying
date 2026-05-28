"""Valley-of-death plot for Config A: SEC vs recirculation ratio across 3 locations.

Reads outputs/config_A/<location>/baseline_r{r:.1f}.csv (and r0.95) for the
fine-grained r sweep and overlays SEC, drying time, and time-averaged COP curves
for biratnagar, kathmandu, and taplejung. Marks each curve's minimum
("valley bottom") and an annotated panel summarising where each location sits.

Usage:
    python scripts/plot_valley_of_death.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots" / "valley_of_death"

R_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
LOCATIONS = {
    "biratnagar": ("Biratnagar (72 m, ~100.5 kPa)", "#1f77b4"),
    "kathmandu":  ("Kathmandu (1350 m, ~86.1 kPa)", "#d62728"),
    "taplejung":  ("Taplejung (1820 m, ~81.0 kPa)", "#2ca02c"),
}


def _load_run(location: str, r: float) -> dict | None:
    path = OUTPUTS / "config_A" / location / f"baseline_r{r:.1f}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    final = df.iloc[-1]
    sec = float(final.get("SEC_elec_kWh_per_kg", np.nan))
    if not np.isfinite(sec):
        # fallback: recompute from cum kWh / m_w
        w_total = float(final["W_comp_cum_kWh"]) + float(final["W_fan_cum_kWh"])
        m_w = float(final["m_w_cum_kg"])
        sec = w_total / m_w if m_w > 0 else np.nan
    cop_series = df["COP"].replace(0, np.nan)
    time_h = float(final["time_s"]) / 3600.0
    # Final-tray check: if any tray is still above X_final (≈ 0.176 db),
    # the run hit the time-limit and didn't actually finish drying.
    x_final_thresh = 0.20
    last_x_avg = float(final.get("X_db_avg", np.nan))
    converged = bool(np.isfinite(last_x_avg) and last_x_avg <= x_final_thresh
                     and time_h < 71.5)
    return dict(
        r=r,
        sec=sec,
        time_h=time_h,
        cop_mean=float(cop_series.mean()),
        w_comp_kWh=float(final["W_comp_cum_kWh"]),
        w_fan_kWh=float(final["W_fan_cum_kWh"]),
        m_water_kg=float(final["m_w_cum_kg"]),
        converged=converged,
        X_db_avg_final=last_x_avg,
    )


def _collect(location: str) -> pd.DataFrame:
    rows = [_load_run(location, r) for r in R_GRID]
    rows = [r for r in rows if r is not None]
    return pd.DataFrame(rows).sort_values("r").reset_index(drop=True)


def _annotate_min(ax, x, y, mask_ok, color):
    """Mark the minimum among CONVERGED points only."""
    y_ok = np.where(mask_ok, y, np.inf)
    if not np.any(np.isfinite(y_ok)) or np.all(y_ok == np.inf):
        return
    idx = int(np.argmin(y_ok))
    ax.scatter([x[idx]], [y[idx]], s=110, color=color, edgecolor="black",
               zorder=5, marker="v")
    ax.annotate(f"min @ r={x[idx]:.2f}\nSEC={y[idx]:.3f}",
                xy=(x[idx], y[idx]),
                xytext=(8, -28), textcoords="offset points",
                fontsize=9, color=color,
                arrowprops=dict(arrowstyle="-", color=color, alpha=0.5))


def make_valley_plot(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    ax_sec, ax_time, ax_cop = axes

    summaries: dict[str, pd.DataFrame] = {}
    for loc, (label, color) in LOCATIONS.items():
        df = _collect(loc)
        if df.empty:
            print(f"[skip] {loc}: no data found")
            continue
        summaries[loc] = df
        r = df["r"].to_numpy()
        ok = df["converged"].to_numpy()
        # Solid line for converged segment, hollow markers for failures
        ax_sec.plot(r, df["sec"], "-", color=color, lw=1.5, alpha=0.5)
        ax_sec.scatter(r[ok], df["sec"][ok], color=color, edgecolor="black",
                       s=55, label=label + "  (dried)", zorder=4)
        if np.any(~ok):
            ax_sec.scatter(r[~ok], df["sec"][~ok], facecolor="white",
                           edgecolor=color, s=55, marker="X",
                           label=label + "  (TIME-LIMITED)", zorder=4)
        ax_time.plot(r, df["time_h"], "-", color=color, lw=1.5, alpha=0.5)
        ax_time.scatter(r[ok], df["time_h"][ok], color=color, edgecolor="black",
                        s=55, label=label, zorder=4)
        if np.any(~ok):
            ax_time.scatter(r[~ok], df["time_h"][~ok], facecolor="white",
                            edgecolor=color, s=55, marker="X", zorder=4)
        ax_cop.plot(r, df["cop_mean"], "o-", color=color, label=label, lw=2, ms=6)
        _annotate_min(ax_sec, r, df["sec"].to_numpy(), ok, color)
    # Reference: 72h time limit
    ax_time.axhline(72.0, color="grey", linestyle="--", alpha=0.7, lw=1)
    ax_time.text(0.02, 71.5, "72 h sim time-limit", fontsize=8,
                 color="grey", va="top")

    for ax, ylabel, title in [
        (ax_sec, "SEC [kWh / kg water]", "Specific energy consumption"),
        (ax_time, "Drying time [h]", "Drying time"),
        (ax_cop, "Time-averaged HP COP [-]", "Heat-pump COP"),
    ]:
        ax.set_xlabel("Recirculation ratio r [-]")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=9, loc="best")

    fig.suptitle("Config A (HP-only): valley of death across recirculation ratio",
                 fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {out_path}")

    # Also dump the merged summary table
    if summaries:
        merged = []
        for loc, df in summaries.items():
            df = df.copy()
            df["location"] = loc
            merged.append(df)
        merged_df = pd.concat(merged, ignore_index=True)
        csv_out = out_path.with_suffix(".csv")
        merged_df.to_csv(csv_out, index=False, float_format="%.5g")
        print(f"Saved: {csv_out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=PLOTS / "config_A_valley_of_death.png")
    args = parser.parse_args()
    make_valley_plot(args.out)


if __name__ == "__main__":
    main()
