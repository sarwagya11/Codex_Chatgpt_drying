"""Run Config A at Kathmandu (start_row=0, Jan 1) under two chamber topologies:
   - series (10 cm gap, single serpentine, default behaviour)
   - parallel (1.5 cm gap, 10 channels, m_da auto-scaled to keep v=1.1 m/s)

Saves both CSVs and produces a side-by-side per-tray plot in the same style
as outputs/parallel_explore/per_tray_KTM_E2_Q1b0.png.

Run:
    python scripts/demo_config_A_KTM_topology.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import LOCATION_ELEVATIONS_M, make_config_A_HP_only  # noqa: E402
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation  # noqa: E402

OUT_DIR = PROJECT_ROOT / "outputs" / "parallel_explore"
OUT_DIR.mkdir(parents=True, exist_ok=True)
WEATHER = PROJECT_ROOT / "data" / "ambient" / "kathmandu_pvgis_standard.csv"
PHASE2_ROOT = PROJECT_ROOT / "phase2_models"
ELEV = LOCATION_ELEVATIONS_M["kathmandu"]
START_ROW = 0   # Jan 1 of the KTM PVGIS year


def run(topology: str, air_gap_m: float, tag: str) -> pd.DataFrame:
    cfg = make_config_A_HP_only(
        ambient_csv=WEATHER,
        T_set_C=45.0,
        m_p_dry_kg=3.0,
        n_trays=10,
        elevation_m=ELEV,
        phase2_root=PHASE2_ROOT,
        display_geometry=True,
        tray_topology=topology,
        air_gap_m=air_gap_m,
    )
    cfg.ambient.start_index = START_ROW
    print(f"--- running Config A KTM | topology={topology} gap={air_gap_m*100:.1f}cm "
          f"m_da={cfg.dryer.m_da_kg_per_s:.4f} kg/s ---")
    result = run_solar_hp_dryer_simulation(cfg)
    df = result.df.copy()
    out_csv = OUT_DIR / f"A_KTM_annual_{tag}.csv"
    df.to_csv(out_csv, index=False)
    print(f"wrote {out_csv}  ({len(df)} rows, final t={df['time_h'].iloc[-1]:.2f} h, "
          f"final X={df['X_db_avg'].iloc[-1]:.3f})")
    return df


def per_tray_panel(ax_row, df, title, n_trays=10):
    cmap = plt.cm.viridis(np.linspace(0, 1, n_trays))

    ax = ax_row[0]
    ax.plot(df["time_h"], df["T_to_chamber_C"], "k-", lw=2.2, label="T_in")
    for k in range(n_trays):
        ax.plot(df["time_h"], df[f"T_tray_{k}_out_C"], color=cmap[k], lw=1,
                label=f"T{k+1}_out")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("T [C]")
    ax.set_title(f"{title}  -  Air T per tray outlet")
    ax.legend(fontsize=6, ncol=2, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = ax_row[1]
    ax.plot(df["time_h"], df["RH_to_chamber_frac"] * 100, "k-", lw=2.2, label="RH_in")
    for k in range(n_trays):
        ax.plot(df["time_h"], df[f"RH_tray_{k}_out_frac"] * 100, color=cmap[k], lw=1)
    ax.set_xlabel("Time [h]"); ax.set_ylabel("RH [%]")
    ax.set_title("Air RH per tray outlet")
    ax.grid(True, alpha=0.3)

    ax = ax_row[2]
    for k in range(n_trays):
        ax.plot(df["time_h"], df[f"X_tray_{k}"], color=cmap[k], lw=1.1,
                label=f"T{k+1}")
    ax.plot(df["time_h"], df["X_db_avg"], "k--", lw=2.2, label="avg")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("X_db [kg w/kg dm]")
    ax.set_title("Per-tray X_db")
    ax.legend(fontsize=6, ncol=2)
    ax.grid(True, alpha=0.3)


def main():
    # Reuse cached CSVs if present, otherwise simulate.
    csv_s = OUT_DIR / "A_KTM_annual_series_10cm.csv"
    csv_p = OUT_DIR / "A_KTM_annual_parallel_1p5cm.csv"
    if csv_s.exists():
        print(f"reusing cached {csv_s}")
        df_s = pd.read_csv(csv_s)
    else:
        df_s = run("series", air_gap_m=0.10, tag="series_10cm")
    if csv_p.exists():
        print(f"reusing cached {csv_p}")
        df_p = pd.read_csv(csv_p)
    else:
        df_p = run("parallel", air_gap_m=0.015, tag="parallel_1p5cm")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    sec_s = df_s["SEC_elec_kWh_per_kg"].iloc[-1]
    sec_p = df_p["SEC_elec_kWh_per_kg"].iloc[-1]
    t_s = df_s["time_h"].iloc[-1]
    t_p = df_p["time_h"].iloc[-1]
    title_s = f"SERIES  (10 cm gap)   t={t_s:.2f} h, SEC={sec_s:.4f} kWh/kg"
    title_p = f"PARALLEL (1.5 cm gap, 10 ch)   t={t_p:.2f} h, SEC={sec_p:.4f} kWh/kg"

    per_tray_panel(axes[0, :], df_s, title_s)
    per_tray_panel(axes[1, :], df_p, title_p)

    fig.suptitle(
        "Config A | Kathmandu | Jan 1 start | T_set=45 C | m_p_dry=3 kg | 10 trays",
        fontsize=13,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.985])
    out_png = OUT_DIR / "per_tray_KTM_A_topology_compare.png"
    plt.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"saved {out_png}")

    # Console comparison summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'metric':<28}  {'series':>14}  {'parallel':>14}  {'ratio':>8}")
    rows = [
        ("dry time [h]",          t_s, t_p),
        ("SEC [kWh/kg water]",    sec_s, sec_p),
        ("final X_avg [kg/kg]",   df_s["X_db_avg"].iloc[-1], df_p["X_db_avg"].iloc[-1]),
        ("m_w_cum [kg]",          df_s["m_w_cum_kg"].iloc[-1], df_p["m_w_cum_kg"].iloc[-1]),
    ]
    for name, a, b in rows:
        ratio = b / a if a else float("nan")
        print(f"{name:<28}  {a:>14.4f}  {b:>14.4f}  {ratio:>8.3f}x")


if __name__ == "__main__":
    main()
