"""Aggregate the latest A/B/C1/C2/D1/D2/D3/E1/E2/E3 baseline (10 m², r=0/0.9/1.0)
runs into a single tidy CSV + a per-location SEC-vs-config bar chart.

Reads the canonical filenames produced by `scripts/run_solar_hp_configs.py`:
  config_A : baseline_r{X.X}.csv
  config_B/C1/C2 : Ac_10m2.csv (r=0)  |  Ac_10m2_r{X.X}.csv (r>0)
  config_D{1,2,3} : hrx_eps0.70.csv      (r=0 only)
  config_E{1,2,3} : Ac_10m2_hrx0.70.csv  (r=0 only)

Skips files in season subdirectories (autumn_oct_nov etc.) and Phase-2 area
sweeps (Ac_5m2.csv, Ac_15m2_hrx*.csv, ...).

Outputs:
  outputs/master_summary_2026-04-30.csv
  plots/master_comparison/SEC_by_config_<location>.png
  plots/master_comparison/SEC_all_configs_3locations.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots" / "master_comparison"

LOCATIONS = ["biratnagar", "kathmandu", "taplejung"]
LOC_LABELS = {
    "biratnagar": "Biratnagar (72 m)",
    "kathmandu":  "Kathmandu (1350 m)",
    "taplejung":  "Taplejung (1820 m)",
}
LOC_COLORS = {"biratnagar": "#1f77b4", "kathmandu": "#d62728", "taplejung": "#2ca02c"}


def _filename_for(config: str, r: float) -> str | None:
    if config == "A":
        return f"baseline_r{r:.1f}.csv"
    if config in ("B", "C1", "C2"):
        return "Ac_10m2.csv" if r == 0.0 else f"Ac_10m2_r{r:.1f}.csv"
    if config in ("D1", "D2", "D3"):
        return "hrx_eps0.70.csv" if r == 0.0 else None
    if config in ("E1", "E2", "E3"):
        return "Ac_10m2_hrx0.70.csv" if r == 0.0 else None
    return None


def _summarise(path: Path, config: str, location: str, r: float) -> dict | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    final = df.iloc[-1]
    sec = float(final.get("SEC_elec_kWh_per_kg", np.nan))
    if not np.isfinite(sec):
        w_elec = float(final.get("W_elec_cum_kWh", 0.0) or 0.0)
        w_total = float(final["W_comp_cum_kWh"]) + float(final["W_fan_cum_kWh"]) + w_elec
        m_w = float(final["m_w_cum_kg"])
        sec = w_total / m_w if m_w > 0 else np.nan
    time_h = float(final["time_s"]) / 3600.0
    last_x = float(final.get("X_db_avg", np.nan))
    converged = bool(np.isfinite(last_x) and last_x <= 0.20 and time_h < 71.5)
    cop = df["COP"].replace(0, np.nan).mean()
    q_solar = float(final.get("Q_solar_cum_kWh", 0.0))
    q_hrx = float(final.get("Q_HRX_cum_kWh", 0.0))
    return dict(
        config=config, location=location, r=r,
        sec=sec, time_h=time_h, converged=converged,
        cop_mean=float(cop) if np.isfinite(cop) else np.nan,
        w_comp_kWh=float(final["W_comp_cum_kWh"]),
        w_fan_kWh=float(final["W_fan_cum_kWh"]),
        q_solar_kWh=q_solar,
        q_hrx_kWh=q_hrx,
        m_water_kg=float(final["m_w_cum_kg"]),
        x_db_final=last_x,
        file=str(path.relative_to(PROJECT_ROOT)),
    )


def aggregate() -> pd.DataFrame:
    rows: list[dict] = []
    config_r_map = {
        "A":  [0.0, 0.9, 1.0],
        "B":  [0.0, 0.9, 1.0],
        "C1": [0.0, 0.9, 1.0],
        "C2": [0.0, 0.9, 1.0],
        "D1": [0.0],
        "D2": [0.0],
        "D3": [0.0],
        "E1": [0.0],
        "E2": [0.0],
        "E3": [0.0],
    }
    for cfg, rs in config_r_map.items():
        for loc in LOCATIONS:
            for r in rs:
                fname = _filename_for(cfg, r)
                if fname is None:
                    continue
                path = OUTPUTS / f"config_{cfg}" / loc / fname
                row = _summarise(path, cfg, loc, r)
                if row is None:
                    print(f"  [missing] {cfg}/{loc}/{fname}")
                    continue
                rows.append(row)
    return pd.DataFrame(rows)


def plot_by_location(df: pd.DataFrame, out_dir: Path) -> None:
    """One bar chart per location, all 10 configs side by side (r=0 only)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    config_order = ["A", "B", "C1", "C2", "D1", "D2", "D3", "E1", "E2", "E3"]
    palette = ["#aec7e8", "#2ca02c", "#98df8a", "#79b779",
               "#ffbb78", "#ff9896", "#c49c94",
               "#9467bd", "#c5b0d5", "#8c564b"]

    for loc in LOCATIONS:
        sub = df[(df["location"] == loc) & (df["r"] == 0.0)]
        if sub.empty:
            continue
        sub = sub.set_index("config").reindex(config_order)
        fig, ax = plt.subplots(figsize=(11, 5.5))
        x = np.arange(len(config_order))
        secs = sub["sec"].to_numpy()
        ok = sub["converged"].to_numpy()
        bars = ax.bar(x, secs, color=palette, edgecolor="black", lw=0.8)
        for i, (bar, s, c) in enumerate(zip(bars, secs, ok)):
            if not np.isfinite(s):
                bar.set_alpha(0.2)
                continue
            ax.text(bar.get_x() + bar.get_width() / 2, s + 0.01,
                    f"{s:.3f}", ha="center", va="bottom", fontsize=9,
                    fontweight="bold" if c else "normal",
                    color="black" if c else "red")
            if not c:
                ax.text(bar.get_x() + bar.get_width() / 2, s + 0.05,
                        "TIME-LIMITED", ha="center", va="bottom",
                        fontsize=8, color="red", rotation=90)
        ax.set_xticks(x)
        ax.set_xticklabels(config_order)
        ax.set_xlabel("Configuration")
        ax.set_ylabel("SEC [kWh / kg water]")
        ax.set_title(f"r = 0 (open-loop) baseline SEC, {LOC_LABELS[loc]}\n"
                     f"Solar = 10 m² for B/C/E configs; HRX ε=0.70 for D/E configs",
                     fontsize=12)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / f"SEC_by_config_{loc}.png", dpi=150)
        plt.close(fig)
        print(f"  Saved: SEC_by_config_{loc}.png")


def plot_all_3_locations(df: pd.DataFrame, out_dir: Path) -> None:
    """Single grouped bar chart: 10 configs × 3 locations (r=0 only)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    config_order = ["A", "B", "C1", "C2", "D1", "D2", "D3", "E1", "E2", "E3"]
    fig, ax = plt.subplots(figsize=(13, 6))
    width = 0.27
    x = np.arange(len(config_order))
    for i, loc in enumerate(LOCATIONS):
        sub = df[(df["location"] == loc) & (df["r"] == 0.0)]
        sub = sub.set_index("config").reindex(config_order)
        secs = sub["sec"].to_numpy()
        ok = sub["converged"].to_numpy()
        bars = ax.bar(x + (i - 1) * width, secs, width,
                      color=LOC_COLORS[loc], edgecolor="black", lw=0.6,
                      label=LOC_LABELS[loc])
        for bar, s, c in zip(bars, secs, ok):
            if not c and np.isfinite(s):
                bar.set_hatch("///")
                bar.set_alpha(0.5)
            if np.isfinite(s):
                ax.text(bar.get_x() + bar.get_width() / 2, s + 0.005,
                        f"{s:.2f}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(config_order)
    ax.set_xlabel("Configuration")
    ax.set_ylabel("SEC [kWh / kg water]")
    ax.set_title("Baseline SEC (r = 0 open-loop) across 10 configurations and 3 locations\n"
                 "Hatched bars = simulation hit 72 h time-limit (didn't dry)", fontsize=12)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "SEC_all_configs_3locations.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: SEC_all_configs_3locations.png")


def main() -> None:
    df = aggregate()
    if df.empty:
        print("No simulation results found.")
        return
    out_csv = OUTPUTS / "master_summary_2026-04-30.csv"
    df.to_csv(out_csv, index=False, float_format="%.6g")
    print(f"\nSaved master summary: {out_csv}  ({len(df)} rows)")

    plot_by_location(df, PLOTS)
    plot_all_3_locations(df, PLOTS)

    # Print compact summary
    print("\n" + "=" * 78)
    print("SEC summary (r=0, kWh/kg)  (* = TIME-LIMITED, didn't dry)")
    print("=" * 78)
    sub = df[df["r"] == 0.0].pivot(index="config", columns="location", values="sec")
    cnv = df[df["r"] == 0.0].pivot(index="config", columns="location", values="converged")
    config_order = ["A", "B", "C1", "C2", "D1", "D2", "D3", "E1", "E2", "E3"]
    sub = sub.reindex(config_order)
    cnv = cnv.reindex(config_order)
    print(f"{'Config':<6} {'Biratnagar':>12} {'Kathmandu':>12} {'Taplejung':>12}")
    for cfg in config_order:
        line = f"{cfg:<6}"
        for loc in LOCATIONS:
            v = sub.loc[cfg, loc]
            ok = cnv.loc[cfg, loc]
            tag = " " if ok else "*"
            line += f"  {v:>10.4f}{tag}" if np.isfinite(v) else "       —    "
        print(line)


if __name__ == "__main__":
    main()
