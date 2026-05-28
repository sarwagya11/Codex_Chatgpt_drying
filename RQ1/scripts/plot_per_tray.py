"""Per-tray T-drop, RH-rise, and moisture content plots for the n_bend=4 KTM E2 runs."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "quarterly_test_compare"
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_TRAYS = 10
CASES = [
    ("Q1 batch0 Jan (KTM, N_bend=4)", "outputs/quarterly_test_nbend4/config_E2/kathmandu/Q1/batch0_Ac_10m2_hrx0.70.csv"),
    ("Q3 batch0 Jul (KTM, N_bend=4)", "outputs/quarterly_test_nbend4/config_E2/kathmandu/Q3/batch0_Ac_10m2_hrx0.70.csv"),
]

cmap = plt.cm.viridis(np.linspace(0, 1, N_TRAYS))

for label, rel in CASES:
    df = pd.read_csv(PROJECT_ROOT / rel)
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # 1. T at each tray outlet (time series)
    ax = axes[0, 0]
    ax.plot(df["time_h"], df["T_to_chamber_C"], "k-", lw=2.5, label="Chamber inlet (T_in)")
    for k in range(N_TRAYS):
        ax.plot(df["time_h"], df[f"T_tray_{k}_out_C"], color=cmap[k], lw=1, label=f"After tray {k+1}")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("T [°C]")
    ax.set_title("Air T after each tray")
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    ax.grid(True, alpha=0.3)

    # 2. RH at each tray outlet
    ax = axes[0, 1]
    ax.plot(df["time_h"], df["RH_to_chamber_frac"]*100, "k-", lw=2.5, label="Chamber inlet")
    for k in range(N_TRAYS):
        ax.plot(df["time_h"], df[f"RH_tray_{k}_out_frac"]*100, color=cmap[k], lw=1, label=f"After tray {k+1}")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("RH [%]")
    ax.set_title("Air RH after each tray")
    ax.legend(fontsize=7, ncol=2, loc="lower right")
    ax.grid(True, alpha=0.3)

    # 3. Per-tray moisture content X_db
    ax = axes[0, 2]
    for k in range(N_TRAYS):
        ax.plot(df["time_h"], df[f"X_tray_{k}"], color=cmap[k], lw=1.2, label=f"Tray {k+1}")
    ax.plot(df["time_h"], df["X_db_avg"], "k--", lw=2.5, label="Chamber avg")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("X_db [kg w / kg dm]")
    ax.set_title("Per-tray moisture content X_db")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)

    # 4. T drop across each tray (snapshot at start, middle, end of drying)
    ax = axes[1, 0]
    times_h = [0.5, 2.0, 5.0, 10.0, df["time_h"].iloc[-1]]
    for t_target in times_h:
        idx = (df["time_h"] - t_target).abs().idxmin()
        row = df.iloc[idx]
        T_profile = [row["T_to_chamber_C"]] + [row[f"T_tray_{k}_out_C"] for k in range(N_TRAYS)]
        positions = list(range(N_TRAYS + 1))  # 0 = chamber inlet, 1-10 = after each tray
        ax.plot(positions, T_profile, marker="o", lw=1.5, label=f"t={row['time_h']:.1f} h")
    ax.set_xlabel("Position (0=inlet, 1-10=after tray k)"); ax.set_ylabel("T [°C]")
    ax.set_title("Air T axial profile (snapshots)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 5. RH rise across each tray (same snapshots)
    ax = axes[1, 1]
    for t_target in times_h:
        idx = (df["time_h"] - t_target).abs().idxmin()
        row = df.iloc[idx]
        RH_profile = [row["RH_to_chamber_frac"]*100] + [row[f"RH_tray_{k}_out_frac"]*100 for k in range(N_TRAYS)]
        positions = list(range(N_TRAYS + 1))
        ax.plot(positions, RH_profile, marker="s", lw=1.5, label=f"t={row['time_h']:.1f} h")
    ax.set_xlabel("Position (0=inlet, 1-10=after tray k)"); ax.set_ylabel("RH [%]")
    ax.set_title("Air RH axial profile (snapshots)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 6. Per-tray drying rate (dm_w / dt)  -- use kg per timestep, convert to kg/h
    ax = axes[1, 2]
    dt_h = df["time_h"].diff().iloc[1] if len(df) > 1 else 1.0
    for k in range(N_TRAYS):
        ax.plot(df["time_h"], df[f"dm_w_tray_{k}_kg"] / dt_h, color=cmap[k], lw=1.2, label=f"Tray {k+1}")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("Drying rate [kg water/h per tray]")
    ax.set_title("Per-tray drying rate")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)

    plt.suptitle(label + f"  |  SEC={df['SEC_elec_kWh_per_kg'].iloc[-1]:.4f} kWh/kg, t_dry={df['time_h'].iloc[-1]:.2f} h", fontsize=12)
    plt.tight_layout()
    safe = label.replace(" ", "_").replace(",", "").replace("(", "").replace(")", "").replace("=", "")
    out_path = OUT_DIR / f"per_tray_{safe}.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")

    # Print summary
    last = df.iloc[-1]
    print(f"  Final X per tray: " + ", ".join(f"T{k+1}={last[f'X_tray_{k}']:.3f}" for k in range(N_TRAYS)))
    # Snapshot at first 30 min: T inlet -> T after each tray
    early = df.iloc[(df["time_h"] - 0.5).abs().idxmin()]
    T_drops = [early["T_to_chamber_C"] - early[f"T_tray_{k}_out_C"] for k in range(N_TRAYS)]
    RH_rises = [early[f"RH_tray_{k}_out_frac"]*100 - early["RH_to_chamber_frac"]*100 for k in range(N_TRAYS)]
    print(f"  T drops @ t=0.5h (deg C per tray): " + ", ".join(f"{d:.2f}" for d in T_drops))
    print(f"  RH rises @ t=0.5h (pct pts per tray): " + ", ".join(f"{r:.2f}" for r in RH_rises))
    print()
