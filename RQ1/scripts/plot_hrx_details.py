"""Plot HRX inlet/outlet temperatures and heat flows for D1, D2, D3 configs.

Creates a multi-panel figure showing:
- HRX hot/cold side inlet and outlet temperatures
- Q_HRX recovered heat over time
- Q_evap, Q_cond, W_comp comparison
- COP comparison across D configs
"""

from pathlib import Path
import sys
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.gridspec import GridSpec

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def plot_hrx_detail(location: str = "kathmandu", output_dir: Path = None):
    """Create detailed HRX comparison plot for D1, D2, D3."""

    outputs = PROJECT_ROOT / "outputs"
    csvs = {}
    for d in ["D1", "D2", "D3"]:
        p = outputs / f"config_{d}" / location / "hrx_eps0.70.csv"
        if p.exists():
            csvs[d] = pd.read_csv(p).iloc[5:]  # skip first 5 rows (init transient)

    # Also load E1/E2 (HRX + Solar)
    for e in ["E1", "E2"]:
        # find first matching CSV
        e_dir = outputs / f"config_{e}" / location
        if e_dir.exists():
            e_csvs = sorted(e_dir.glob("*.csv"))
            if e_csvs:
                csvs[e] = pd.read_csv(e_csvs[0]).iloc[5:]

    # Also load Config A r=0 for comparison
    a_path = outputs / "config_A" / location / "baseline_r0.0.csv"
    if a_path.exists():
        csvs["A(r=0)"] = pd.read_csv(a_path).iloc[5:]

    if not csvs:
        print(f"No D/E config CSVs found for {location}")
        return

    colors = {"D1": "#1f77b4", "D2": "#ff7f0e", "D3": "#2ca02c", "A(r=0)": "#d62728",
              "E1": "#9467bd", "E2": "#8c564b"}

    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.suptitle(f"HRX Detail — {location.title()}", fontsize=14, fontweight="bold")

    # --- Panel 1: HRX Hot Side (Exhaust In → Cooled Out) ---
    ax = axes[0, 0]
    for d in ["D1", "D2", "D3"]:
        if d not in csvs:
            continue
        df = csvs[d]
        ax.plot(df["time_h"], df["T_exhaust_C"], "--", color=colors[d], alpha=0.5,
                label=f"{d} Exhaust In (hot)")
        ax.plot(df["time_h"], df["T_exh_cooled_C"], "-", color=colors[d], linewidth=2,
                label=f"{d} Exhaust Out (cooled)")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("HRX Hot Side: Exhaust In → Cooled Out")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)

    # --- Panel 2: HRX Cold Side (Ambient In → Heated Out) ---
    ax = axes[0, 1]
    for d in ["D1", "D2", "D3"]:
        if d not in csvs:
            continue
        df = csvs[d]
        ax.plot(df["time_h"], df["T_amb_C"], "--", color=colors[d], alpha=0.5,
                label=f"{d} Ambient In (cold)")
        ax.plot(df["time_h"], df["T_amb_heated_C"], "-", color=colors[d], linewidth=2,
                label=f"{d} Ambient Out (heated)")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("HRX Cold Side: Ambient In → Heated Out")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Q_HRX recovered heat ---
    ax = axes[1, 0]
    for d in ["D1", "D2", "D3"]:
        if d not in csvs:
            continue
        df = csvs[d]
        ax.plot(df["time_h"], df["Q_HRX_kW"], "-", color=colors[d], linewidth=2, label=d)
    ax.set_ylabel("Q_HRX [kW]")
    ax.set_title("Heat Recovered by HRX")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Panel 4: Q_evap + Q_cond comparison ---
    ax = axes[1, 1]
    for key in ["D1", "D2", "D3", "E1", "E2", "A(r=0)"]:
        if key not in csvs:
            continue
        df = csvs[key]
        ax.plot(df["time_h"], df["Q_cond_kW"], "-", color=colors[key], linewidth=2,
                label=f"{key} Q_cond")
        ax.plot(df["time_h"], df["Q_evap_kW"], "--", color=colors[key], linewidth=1.5,
                label=f"{key} Q_evap")
    ax.set_ylabel("Heat [kW]")
    ax.set_title("HP Condenser & Evaporator Heat")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)

    # --- Panel 5: COP comparison ---
    ax = axes[2, 0]
    for key in ["D1", "D2", "D3", "E1", "E2", "A(r=0)"]:
        if key not in csvs:
            continue
        df = csvs[key]
        ax.plot(df["time_h"], df["COP"], "-", color=colors[key], linewidth=2, label=key)
    ax.set_xlabel("Time [hours]")
    ax.set_ylabel("COP")
    ax.set_title("Heat Pump COP")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Panel 6: W_comp comparison ---
    ax = axes[2, 1]
    for key in ["D1", "D2", "D3", "E1", "E2", "A(r=0)"]:
        if key not in csvs:
            continue
        df = csvs[key]
        ax.plot(df["time_h"], df["W_comp_kW"], "-", color=colors[key], linewidth=2, label=key)
        # Also show cumulative in secondary axis
    ax.set_xlabel("Time [hours]")
    ax.set_ylabel("W_comp [kW]")
    ax.set_title("Compressor Power")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_dir is None:
        output_dir = PROJECT_ROOT / "plots" / "hrx_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"hrx_detail_{location}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {out_path}")
    plt.close(fig)

    # --- Summary table ---
    print(f"\n{'='*70}")
    print(f"SUMMARY — {location.title()}")
    print(f"{'='*70}")
    print(f"{'Config':<10} {'Time[h]':>8} {'W_tot[kWh]':>11} {'Q_cond_tot':>11} {'Q_HRX_tot':>10} {'Q_solar':>8} {'Avg COP':>8} {'SEC':>8}")
    for key in ["A(r=0)", "D1", "D2", "D3", "E1", "E2"]:
        if key not in csvs:
            continue
        # Find the full CSV (re-read without skipping rows)
        if key == "A(r=0)":
            full_path = outputs / "config_A" / location / "baseline_r0.0.csv"
        elif key.startswith("D"):
            full_path = outputs / f"config_{key}" / location / "hrx_eps0.70.csv"
        elif key.startswith("E"):
            e_dir = outputs / f"config_{key}" / location
            e_csvs = sorted(e_dir.glob("*.csv")) if e_dir.exists() else []
            full_path = e_csvs[0] if e_csvs else None
        else:
            full_path = None
        if full_path is None or not full_path.exists():
            continue
        full = pd.read_csv(full_path)
        t = full["time_h"].iloc[-1]
        w = full["W_comp_cum_kWh"].iloc[-1]
        qc = full["Q_cond_cum_kWh"].iloc[-1]
        qh = full.get("Q_HRX_cum_kWh", pd.Series([0])).iloc[-1]
        qs = full.get("Q_solar_cum_kWh", pd.Series([0])).iloc[-1]
        cop = full["COP"].mean()
        sec = full["SEC_elec_kWh_per_kg"].iloc[-1]
        print(f"{key:<10} {t:>8.1f} {w:>11.2f} {qc:>11.2f} {qh:>10.2f} {qs:>8.2f} {cop:>8.2f} {sec:>8.3f}")


if __name__ == "__main__":
    for loc in ["kathmandu", "biratnagar"]:
        plot_hrx_detail(loc)
