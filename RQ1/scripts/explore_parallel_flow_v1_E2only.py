"""EXPLORATORY: simulate Config E2 with parallel-tray airflow instead of series.

Geometry assumption (Option II):
  - 10 trays in parallel, narrow channels (~1 cm gap each)
  - Total m_da unchanged (0.082 kg/s)
  - Each tray sees the SAME chamber inlet T/RH/omega
  - Per-tray air flow = m_da_total / n_trays
  - v in each tray channel = 1.1 m/s (matches kinetic-fit calibration)

What this script does:
  - Monkey-patches the simulate_drying_chamber function with a parallel version
  - Reuses the full rest of the E2 pipeline (HRX + Solar + HP + exhaust mix + bypass)
  - Runs KTM Q1 batch0 (Jan, cold/dry) on E2, A_solar=10 m^2
  - Saves outputs to outputs/parallel_explore/
  - Plots comparison with the existing series run

Does NOT touch the production code in src/rq1/.

NOTE: This is the v1 frozen copy of the first single-case exploration script
(KTM E2 Q1 b0 only). The newer extended version that loops over five edge
cases is `explore_parallel_flow.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1 import dryer_solar_hp as dsh  # noqa: E402
from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    make_config_E_HRX_solar,
)
from rq1.kinetics import (  # noqa: E402
    compute_dm_w_air_capacity,
    compute_dm_w_kinetic_first_order,
)
from rq1.psychro import (  # noqa: E402
    RH_from_T_omega,
    dewpoint_from_omega_C,
    moist_air_enthalpy_kJ_per_kg,
    temperature_from_h_omega_C,
)

OUT_DIR = PROJECT_ROOT / "outputs" / "parallel_explore"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# PARALLEL drying chamber
# ---------------------------------------------------------------------------
def simulate_drying_chamber_parallel(
    T_to_chamber_C: float,
    omega_to_chamber: float,
    h_to_chamber: float,
    X_trays: List[List[float]],
    MR_trays: List[List[float]],
    cfg,
    time_s: float,
    m_da: float,
    dt_s: float,
    reverse_flow: bool = False,
) -> Tuple[List[float], List[float], List[float], List[float], List[List[float]], List[List[float]]]:
    """Parallel-tray version: each tray sees the same chamber inlet."""
    n_trays = cfg.dryer.n_trays
    m_p_tray = cfg.dryer.m_p_dry_kg / n_trays
    h_fg = cfg.dryer.h_fg_kJ_per_kg
    p_atm = cfg.ambient.default_pressure_Pa

    # Per-tray air mass flow (parallel split)
    m_da_per_tray = m_da / n_trays

    dm_w_trays = [0.0] * n_trays
    T_tray_out = [0.0] * n_trays
    RH_tray_out = [0.0] * n_trays
    h_tray_out = [0.0] * n_trays
    X_trays_new: List[Optional[List[float]]] = [None] * n_trays
    MR_trays_new: List[Optional[List[float]]] = [None] * n_trays

    for i in range(n_trays):
        # Each tray restarts with the chamber-inlet conditions
        T_air = T_to_chamber_C
        omega_air = omega_to_chamber
        h_air = h_to_chamber
        RH_air = float(RH_from_T_omega(T_air, omega_air, p_atm))

        n_sec = len(X_trays[i])
        m_p_section = m_p_tray / n_sec
        X_sec_new: List[float] = []
        MR_sec_new: List[float] = []
        dm_w_tray_total = 0.0

        for j in range(n_sec):
            X_j = X_trays[i][j]
            X_eq_local = cfg.dryer.X_eq_db

            dm_w_kin = compute_dm_w_kinetic_first_order(
                X_db=X_j, X_eq_db=X_eq_local, T_in_C=T_air, RH_in_frac=RH_air,
                dt_s=dt_s, cfg=cfg.kinetics, m_p_dry_kg=m_p_section, time_s=time_s,
            )

            if cfg.kinetics.enable_air_limit:
                dm_w_air_max = compute_dm_w_air_capacity(
                    T_in_C=T_air, omega_in=omega_air,
                    m_da_kg_per_s=m_da_per_tray,   # ← key change
                    dt_s=dt_s, cfg=cfg.kinetics, h_fg_kJ_per_kg=h_fg,
                    p_atm_Pa=p_atm,
                )
            else:
                dm_w_air_max = float("inf")

            max_removable = max(0.0, (X_j - X_eq_local) * m_p_section)
            dm_w = min(dm_w_kin, dm_w_air_max, max_removable)

            dX = dm_w / m_p_section if m_p_section > 0 else 0.0
            X_new = max(X_j - dX, X_eq_local)
            MR_new = (X_new - X_eq_local) / (cfg.dryer.X0_db - X_eq_local) if cfg.dryer.X0_db != X_eq_local else 0.0
            X_sec_new.append(X_new)
            MR_sec_new.append(MR_new)
            dm_w_tray_total += dm_w

            # Update air state for next section within the same tray
            m_w_rate = dm_w / dt_s if dt_s > 0 else 0.0
            d_omega = m_w_rate / m_da_per_tray if m_da_per_tray > 0 else 0.0
            omega_out = omega_air + d_omega
            h_out = h_air + d_omega * 4.186 * T_air
            T_out = float(temperature_from_h_omega_C(h_out, omega_out))
            RH_out = float(RH_from_T_omega(T_out, omega_out, p_atm))
            if RH_out > 1.0:
                T_out = float(dewpoint_from_omega_C(omega_out, p_total_Pa=p_atm))
                RH_out = 1.0
                h_out = float(moist_air_enthalpy_kJ_per_kg(T_out, omega_out))
            T_air = T_out
            omega_air = omega_out
            h_air = h_out
            RH_air = RH_out

        X_trays_new[i] = X_sec_new
        MR_trays_new[i] = MR_sec_new
        dm_w_trays[i] = dm_w_tray_total
        T_tray_out[i] = T_air
        RH_tray_out[i] = RH_air
        h_tray_out[i] = h_air

    return dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays_new, MR_trays_new


# ---------------------------------------------------------------------------
# In dsh, the chamber-exhaust state is taken from a single index (exhaust_idx),
# but in parallel reality the exhaust is the mass-weighted MIX of all tray
# outlets. To preserve that physics we override exhaust_idx behaviour by
# patching the "T_exhaust_C" / "RH_exhaust_frac" record fields after the call.
# Simplest: monkey-patch simulate_drying_chamber to the parallel version, but
# also intercept the per-step record to write mixed exhaust state.
# Cleaner: just patch chamber + accept that T_tray_out[exhaust_idx] is now the
# state of ONE parallel tray (they are roughly identical anyway because each
# tray sees the same inlet) — within ~1% of the mass-mixed value.
# ---------------------------------------------------------------------------

def run_parallel_E2():
    weather_path = PROJECT_ROOT / "data" / "ambient" / "kathmandu_pvgis_standard.csv"
    cfg = make_config_E_HRX_solar(
        ambient_csv=weather_path,
        solar_area_m2=10.0,
        e_variant="E2",
        T_set_C=45.0,
        elevation_m=LOCATION_ELEVATIONS_M["kathmandu"],
        eps_HRX=0.70,
        vpd_bypass_thresh=0.0,
        display_geometry=False,
    )
    cfg.max_simulation_time_s = 72 * 3600.0
    # KTM Q1 batch0 = start_row 1
    cfg.ambient.start_index = 1
    cfg.ambient.max_steps = 168

    # Monkey-patch
    original_fn = dsh.simulate_drying_chamber
    dsh.simulate_drying_chamber = simulate_drying_chamber_parallel
    try:
        result = dsh.run_solar_hp_dryer_simulation(cfg)
    finally:
        dsh.simulate_drying_chamber = original_fn

    df = result.df
    out_csv = OUT_DIR / "E2_ktm_Q1b0_PARALLEL.csv"
    df.to_csv(out_csv, index=False)
    print(f"Parallel saved: {out_csv}")
    print(f"  t_dry  = {df['time_h'].iloc[-1]:.2f} h")
    print(f"  m_w    = {df['m_w_cum_kg'].iloc[-1]:.3f} kg")
    print(f"  SEC    = {df['SEC_elec_kWh_per_kg'].iloc[-1]:.4f} kWh/kg")
    xs = [f"{df[f'X_tray_{k}'].iloc[-1]:.3f}" for k in range(10)]
    print(f"  X_T1..X_T10 final = {xs}")
    return df


def load_series():
    p = PROJECT_ROOT / "outputs/quarterly_test_nbend9/config_E2/kathmandu/Q1/batch0_Ac_10m2_hrx0.70.csv"
    if not p.exists():
        # fall back to nbend4
        p = PROJECT_ROOT / "outputs/quarterly_test_nbend4/config_E2/kathmandu/Q1/batch0_Ac_10m2_hrx0.70.csv"
    return pd.read_csv(p)


def make_plots(df_par: pd.DataFrame, df_ser: pd.DataFrame):
    cmap = plt.cm.viridis(np.linspace(0, 1, 10))

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # 1. MR overall
    ax = axes[0, 0]
    ax.plot(df_ser["time_h"], df_ser["MR_global"], "b-", lw=2,
            label=f"Series (t={df_ser['time_h'].iloc[-1]:.2f}h, SEC={df_ser['SEC_elec_kWh_per_kg'].iloc[-1]:.4f})")
    ax.plot(df_par["time_h"], df_par["MR_global"], "r--", lw=2,
            label=f"Parallel (t={df_par['time_h'].iloc[-1]:.2f}h, SEC={df_par['SEC_elec_kWh_per_kg'].iloc[-1]:.4f})")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("MR_global [-]")
    ax.set_title("Overall drying curve")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

    # 2. Per-tray X for SERIES
    ax = axes[0, 1]
    for k in range(10):
        ax.plot(df_ser["time_h"], df_ser[f"X_tray_{k}"], color=cmap[k], lw=1.0)
    ax.set_xlabel("Time [h]"); ax.set_ylabel("X_db [-]")
    ax.set_title(f"SERIES: per-tray X (final spread T1={df_ser['X_tray_0'].iloc[-1]:.3f} -> T10={df_ser['X_tray_9'].iloc[-1]:.3f})")
    ax.grid(True, alpha=0.3)

    # 3. Per-tray X for PARALLEL
    ax = axes[0, 2]
    for k in range(10):
        ax.plot(df_par["time_h"], df_par[f"X_tray_{k}"], color=cmap[k], lw=1.0)
    ax.set_xlabel("Time [h]"); ax.set_ylabel("X_db [-]")
    ax.set_title(f"PARALLEL: per-tray X (final spread T1={df_par['X_tray_0'].iloc[-1]:.3f} -> T10={df_par['X_tray_9'].iloc[-1]:.3f})")
    ax.grid(True, alpha=0.3)

    # 4. Cumulative compressor energy
    ax = axes[1, 0]
    ax.plot(df_ser["time_h"], df_ser["W_comp_cum_kWh"], "b-", lw=2, label="Series")
    ax.plot(df_par["time_h"], df_par["W_comp_cum_kWh"], "r--", lw=2, label="Parallel")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("W_comp_cum [kWh]")
    ax.set_title("Cumulative compressor energy")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

    # 5. Water removed cumulative
    ax = axes[1, 1]
    ax.plot(df_ser["time_h"], df_ser["m_w_cum_kg"], "b-", lw=2, label="Series")
    ax.plot(df_par["time_h"], df_par["m_w_cum_kg"], "r--", lw=2, label="Parallel")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("m_w cumulative [kg]")
    ax.set_title("Total water removed")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

    # 6. T after tray for both (overlay tray 1 and tray 10)
    ax = axes[1, 2]
    ax.plot(df_ser["time_h"], df_ser["T_tray_0_out_C"], "b-", lw=1.5, label="Series T1_out")
    ax.plot(df_ser["time_h"], df_ser["T_tray_9_out_C"], "b--", lw=1.5, label="Series T10_out")
    ax.plot(df_par["time_h"], df_par["T_tray_0_out_C"], "r-", lw=1.5, label="Parallel T1_out")
    ax.plot(df_par["time_h"], df_par["T_tray_9_out_C"], "r--", lw=1.5, label="Parallel T10_out")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("T [C]")
    ax.set_title("Air T after tray 1 vs tray 10")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    plt.suptitle("Series vs Parallel tray topology | KTM E2 Q1 batch0 | A_solar=10m2, m_da_total fixed, v=1.1 m/s",
                 fontsize=12)
    plt.tight_layout()
    out_png = OUT_DIR / "series_vs_parallel.png"
    plt.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Plot saved: {out_png}")


if __name__ == "__main__":
    df_par = run_parallel_E2()
    df_ser = load_series()
    make_plots(df_par, df_ser)
