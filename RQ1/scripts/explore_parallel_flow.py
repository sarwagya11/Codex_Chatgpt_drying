"""EXPLORATORY: simulate dryer chamber with PARALLEL airflow (10 tray channels) vs.
SERIES airflow (1 channel, 10 serpentine passes), across 5 edge-case batches.

Geometry assumption (Option II — parallel narrow channels):
  - 10 trays in parallel, narrow channels (~1 cm gap each)
  - Total m_da unchanged (matches series cfg)
  - Each tray sees the SAME chamber inlet T/RH/omega
  - Per-tray air flow = m_da_total / n_trays
  - Per-channel v = m_da_per_ch / (rho * W * gap_parallel) ≈ 1.1 m/s

What this script does:
  - Defines a drop-in `simulate_drying_chamber_parallel` (monkey-patched in).
  - Runs FIVE cases on both topologies (series, parallel):
      (1) KTM E2 Q1 batch0  — cold/dry winter
      (2) KTM E2 Q3 batch0  — monsoon, very high RH
      (3) Namche E2 Q1 b0   — sub-alpine, high altitude
      (4) KTM Config A Q1 b0 — HP-only, no HRX/no solar
      (5) BTN E2 Q4 batch0  — warm/humid late autumn
  - Verifies first-law and mass balance on the parallel df.
  - Estimates analytical ΔP penalty for narrow-channel parallel.
  - Aggregates everything to outputs/parallel_explore/edge_case_summary.csv
    and prints a punch-list summary table to stdout.

Does NOT touch production code in src/rq1/.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1 import dryer_solar_hp as dsh  # noqa: E402
from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    SimulationConfig,
    make_config_A_HP_only,
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

# Parallel-topology geometry assumptions
GAP_PARALLEL_M = 0.01     # 1 cm per-channel gap
K_BEND_PARALLEL = 0.5     # manifold turn-in/out (90 deg elbow, Idelchik)
N_BEND_PARALLEL = 6       # 2 inlet header turns + 2 outlet header turns + 2 duct elbows
K_PLENUM = 0.5            # diffuser + accelerator per plenum (count 2)


# ---------------------------------------------------------------------------
# PARALLEL drying chamber (drop-in for dsh.simulate_drying_chamber)
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

    m_da_per_tray = m_da / n_trays

    dm_w_trays = [0.0] * n_trays
    T_tray_out = [0.0] * n_trays
    RH_tray_out = [0.0] * n_trays
    h_tray_out = [0.0] * n_trays
    X_trays_new: List[Optional[List[float]]] = [None] * n_trays
    MR_trays_new: List[Optional[List[float]]] = [None] * n_trays

    for i in range(n_trays):
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
                    m_da_kg_per_s=m_da_per_tray,
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
# Case definitions
# ---------------------------------------------------------------------------
@dataclass
class Case:
    name: str
    config_tag: str         # for filenames
    weather_file: str       # under data/ambient/
    location_key: str       # for elevation lookup
    start_row: int          # row index in standardized PVGIS CSV
    factory: Callable[..., SimulationConfig]
    factory_kwargs: dict


CASES: List[Case] = [
    Case(
        name="KTM E2 Q1 b0 (winter / cold-dry)",
        config_tag="E2_ktm_Q1b0",
        weather_file="kathmandu_pvgis_standard.csv",
        location_key="kathmandu",
        start_row=1,
        factory=make_config_E_HRX_solar,
        factory_kwargs={"solar_area_m2": 10.0, "e_variant": "E2", "eps_HRX": 0.70,
                        "vpd_bypass_thresh": 0.0},
    ),
    Case(
        name="KTM E2 Q3 b0 (monsoon / hot-humid)",
        config_tag="E2_ktm_Q3b0",
        weather_file="kathmandu_pvgis_standard.csv",
        location_key="kathmandu",
        start_row=4345,
        factory=make_config_E_HRX_solar,
        factory_kwargs={"solar_area_m2": 10.0, "e_variant": "E2", "eps_HRX": 0.70,
                        "vpd_bypass_thresh": 0.0},
    ),
    Case(
        name="Namche E2 Q1 b0 (sub-alpine / cold high-altitude)",
        config_tag="E2_namche_Q1b0",
        weather_file="namche_pvgis_standard.csv",
        location_key="namche",
        start_row=1,
        factory=make_config_E_HRX_solar,
        factory_kwargs={"solar_area_m2": 10.0, "e_variant": "E2", "eps_HRX": 0.70,
                        "vpd_bypass_thresh": 0.0},
    ),
    Case(
        name="KTM Config A Q1 b0 (HP-only baseline)",
        config_tag="A_ktm_Q1b0",
        weather_file="kathmandu_pvgis_standard.csv",
        location_key="kathmandu",
        start_row=1,
        factory=make_config_A_HP_only,
        factory_kwargs={},
    ),
    Case(
        name="BTN E2 Q4 b0 (late autumn warm-humid)",
        config_tag="E2_btn_Q4b0",
        weather_file="biratnagar_pvgis_standard.csv",
        location_key="biratnagar",
        start_row=6553,
        factory=make_config_E_HRX_solar,
        factory_kwargs={"solar_area_m2": 10.0, "e_variant": "E2", "eps_HRX": 0.70,
                        "vpd_bypass_thresh": 0.0},
    ),
]


def build_config(case: Case) -> SimulationConfig:
    weather_path = PROJECT_ROOT / "data" / "ambient" / case.weather_file
    elev = LOCATION_ELEVATIONS_M[case.location_key]
    cfg = case.factory(
        ambient_csv=weather_path,
        T_set_C=45.0,
        elevation_m=elev,
        display_geometry=False,
        **case.factory_kwargs,
    )
    cfg.max_simulation_time_s = 72 * 3600.0
    cfg.ambient.start_index = case.start_row
    cfg.ambient.max_steps = 168
    return cfg


# ---------------------------------------------------------------------------
# Run a single case in series or parallel mode
# ---------------------------------------------------------------------------
def run_case(case: Case, mode: str) -> pd.DataFrame:
    assert mode in ("series", "parallel")
    cfg = build_config(case)
    if mode == "parallel":
        original = dsh.simulate_drying_chamber
        dsh.simulate_drying_chamber = simulate_drying_chamber_parallel
    try:
        result = dsh.run_solar_hp_dryer_simulation(cfg)
    finally:
        if mode == "parallel":
            dsh.simulate_drying_chamber = original
    df = result.df.copy()
    out_csv = OUT_DIR / f"{case.config_tag}_{mode.upper()}.csv"
    df.to_csv(out_csv, index=False)
    return df


# ---------------------------------------------------------------------------
# Energy / mass balance check
# ---------------------------------------------------------------------------
def energy_mass_balance(df: pd.DataFrame, dt_s: float = 60.0, eta_mech: float = 0.90) -> dict:
    """Verify first-law and mass-balance invariants on a result df.

    W_comp_kW in the CSV is the ELECTRICAL input to the compressor; the
    refrigerant cycle's shaft work is W_shaft = eta_mech * W_comp_elec.
    First-law on the cycle therefore reads
        Q_cond = Q_evap + W_shaft = Q_evap + eta_mech * W_comp_elec
    """
    cond = df["Q_cond_kW"].values
    evap = df["Q_evap_kW"].values
    comp = df["W_comp_kW"].values
    e_resid = cond - evap - eta_mech * comp
    e_max = float(np.max(np.abs(e_resid)))
    e_rel_max = float(np.max(np.abs(e_resid) / np.maximum(np.abs(cond), 1e-9)))

    # Per-step mass balance: sum_k dm_w_tray_k == dm_w_total
    tray_cols = [f"dm_w_tray_{k}_kg" for k in range(10)]
    if all(c in df.columns for c in tray_cols):
        tray_sum = df[tray_cols].sum(axis=1).values
        total = df["dm_w_total_kg"].values
        m_resid = tray_sum - total
        m_max = float(np.max(np.abs(m_resid)))
    else:
        m_max = float("nan")

    # Cumulative consistency: sum(dm_w_total) == m_w_cum at every t
    cumsum = df["dm_w_total_kg"].cumsum().values
    cum_resid = cumsum - df["m_w_cum_kg"].values
    cum_max = float(np.max(np.abs(cum_resid)))

    return {
        "first_law_max_abs_kW": e_max,
        "first_law_max_rel": e_rel_max,
        "tray_sum_max_abs_kg": m_max,
        "cum_water_max_abs_kg": cum_max,
    }


# ---------------------------------------------------------------------------
# ΔP estimate — analytical, no simulation
# ---------------------------------------------------------------------------
def dp_estimate(cfg: SimulationConfig) -> dict:
    """Return chamber-side ΔP under current series geometry and under
    proposed parallel narrow-channel geometry (single ΔP path, since parallel
    paths share ΔP)."""
    d = cfg.dryer
    rho = d.air_density_kg_per_m3
    mu = d.mu_air_Pa_s
    W = d.tray_width_m
    L = d.tray_length_m
    n_trays = d.n_trays
    m_da = d.m_da_kg_per_s

    # --- SERIES (current cfg-installed geometry) ---
    h_s = d.air_gap_m
    A_cross_s = W * h_s
    v_s = m_da / (rho * A_cross_s)
    D_h_s = 2.0 * W * h_s / (W + h_s)
    Re_s = rho * v_s * D_h_s / mu
    f_s = 64.0 / Re_s if Re_s < 2300 else 0.316 * Re_s ** -0.25
    q_s = 0.5 * rho * v_s ** 2
    dP_ch_series = f_s * (L / D_h_s) * q_s * n_trays
    dP_bend_series = d.K_bend * q_s * max(0, n_trays - 1)

    # --- PARALLEL (Option II: shrink gap, split m_da 10-way) ---
    h_p = GAP_PARALLEL_M
    A_cross_p = W * h_p
    m_da_per_ch = m_da / n_trays
    v_p = m_da_per_ch / (rho * A_cross_p)
    D_h_p = 2.0 * W * h_p / (W + h_p)
    Re_p = rho * v_p * D_h_p / mu
    f_p = 64.0 / Re_p if Re_p < 2300 else 0.316 * Re_p ** -0.25
    q_p = 0.5 * rho * v_p ** 2
    # parallel: only ONE channel's friction (paths share ΔP)
    dP_ch_parallel = f_p * (L / D_h_p) * q_p
    dP_bend_parallel = K_BEND_PARALLEL * q_p * N_BEND_PARALLEL
    dP_plenum_parallel = K_PLENUM * q_p * 2.0   # inlet + outlet plenum

    # other ΔP terms (cond, HRX, solar, duct) are unchanged between modes
    fixed_other = (d.dP_cond_Pa
                   + (2.0 * d.dP_HRX_side_Pa if d.d_variant in ("D1", "D2", "D3", "E1", "E2", "E3") else 0.0)
                   + (d.dP_solar_Pa if cfg.solar.enabled and cfg.solar.area_m2 > 0
                      and d.d_variant in ("B1", "B2", "E1", "E2", "E3") else 0.0)
                   + d.dP_duct_Pa)

    dP_total_series = dP_ch_series + dP_bend_series + fixed_other
    dP_total_parallel = dP_ch_parallel + dP_bend_parallel + dP_plenum_parallel + fixed_other

    V_dot = m_da / rho
    W_fan_series_W = V_dot * dP_total_series / d.eta_fan
    W_fan_parallel_W = V_dot * dP_total_parallel / d.eta_fan

    return {
        "v_series_m_s": v_s,
        "v_parallel_m_s": v_p,
        "Re_series": Re_s,
        "Re_parallel": Re_p,
        "D_h_series_mm": D_h_s * 1000,
        "D_h_parallel_mm": D_h_p * 1000,
        "dP_chan_series_Pa": dP_ch_series,
        "dP_chan_parallel_Pa": dP_ch_parallel,
        "dP_bend_series_Pa": dP_bend_series,
        "dP_bend_parallel_Pa": dP_bend_parallel,
        "dP_plenum_parallel_Pa": dP_plenum_parallel,
        "dP_other_Pa": fixed_other,
        "dP_total_series_Pa": dP_total_series,
        "dP_total_parallel_Pa": dP_total_parallel,
        "W_fan_series_W": W_fan_series_W,
        "W_fan_parallel_W": W_fan_parallel_W,
    }


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------
def summarize_run(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    return {
        "t_dry_h": float(last["time_h"]),
        "m_w_kg": float(last["m_w_cum_kg"]),
        "SEC_kWh_per_kg": float(last["SEC_elec_kWh_per_kg"]),
        "W_comp_kWh": float(last["W_comp_cum_kWh"]),
        "W_fan_kWh": float(last["W_fan_cum_kWh"]),
        "W_elec_kWh": float(last["W_elec_cum_kWh"]),
        "X_T1_final": float(last["X_tray_0"]),
        "X_T10_final": float(last["X_tray_9"]),
        "X_spread": float(last["X_tray_0"]) - float(last["X_tray_9"]),
    }


def main():
    rows = []
    for case in CASES:
        print(f"\n{'=' * 78}\n>>> {case.name}\n{'=' * 78}")

        # SERIES
        df_s = run_case(case, "series")
        s = summarize_run(df_s)
        eb_s = energy_mass_balance(df_s)

        # PARALLEL
        df_p = run_case(case, "parallel")
        p = summarize_run(df_p)
        eb_p = energy_mass_balance(df_p)

        # ΔP estimate (cfg geometry is identical to series for this estimate;
        # parallel column shows what the fan would actually see if rewired)
        cfg_eval = build_config(case)
        dp = dp_estimate(cfg_eval)

        row = {
            "case": case.name,
            "tag": case.config_tag,
            # series headline
            "series_t_h": s["t_dry_h"], "series_SEC": s["SEC_kWh_per_kg"],
            "series_Wcomp_kWh": s["W_comp_kWh"], "series_Wfan_kWh": s["W_fan_kWh"],
            "series_X_T1": s["X_T1_final"], "series_X_T10": s["X_T10_final"],
            # parallel headline
            "parallel_t_h": p["t_dry_h"], "parallel_SEC": p["SEC_kWh_per_kg"],
            "parallel_Wcomp_kWh": p["W_comp_kWh"], "parallel_Wfan_kWh": p["W_fan_kWh"],
            "parallel_X_T1": p["X_T1_final"], "parallel_X_T10": p["X_T10_final"],
            # deltas
            "dt_dry_pct": 100.0 * (p["t_dry_h"] - s["t_dry_h"]) / s["t_dry_h"],
            "dSEC_pct": 100.0 * (p["SEC_kWh_per_kg"] - s["SEC_kWh_per_kg"]) / s["SEC_kWh_per_kg"],
            # balance
            "series_E_err_kW": eb_s["first_law_max_abs_kW"],
            "parallel_E_err_kW": eb_p["first_law_max_abs_kW"],
            "series_M_err_kg": eb_s["tray_sum_max_abs_kg"],
            "parallel_M_err_kg": eb_p["tray_sum_max_abs_kg"],
            "series_Wcum_err_kg": eb_s["cum_water_max_abs_kg"],
            "parallel_Wcum_err_kg": eb_p["cum_water_max_abs_kg"],
            # ΔP estimate
            "v_series": dp["v_series_m_s"], "v_parallel": dp["v_parallel_m_s"],
            "Re_series": dp["Re_series"], "Re_parallel": dp["Re_parallel"],
            "dP_total_series_Pa": dp["dP_total_series_Pa"],
            "dP_total_parallel_Pa": dp["dP_total_parallel_Pa"],
            "W_fan_series_W": dp["W_fan_series_W"],
            "W_fan_parallel_W": dp["W_fan_parallel_W"],
        }
        rows.append(row)

        print(f"  SERIES   t={s['t_dry_h']:6.2f} h  SEC={s['SEC_kWh_per_kg']:.4f}  X(T1->T10)={s['X_T1_final']:.3f} -> {s['X_T10_final']:.3f}")
        print(f"  PARALLEL t={p['t_dry_h']:6.2f} h  SEC={p['SEC_kWh_per_kg']:.4f}  X(T1->T10)={p['X_T1_final']:.3f} -> {p['X_T10_final']:.3f}")
        print(f"  delta:   dt={row['dt_dry_pct']:+.1f}%  dSEC={row['dSEC_pct']:+.1f}%")
        print(f"  balance: series E_max={eb_s['first_law_max_abs_kW']:.2e} kW  M_max={eb_s['tray_sum_max_abs_kg']:.2e} kg")
        print(f"           parallel E_max={eb_p['first_law_max_abs_kW']:.2e} kW  M_max={eb_p['tray_sum_max_abs_kg']:.2e} kg")
        print(f"  dP:      series {dp['dP_total_series_Pa']:.1f} Pa  W_fan {dp['W_fan_series_W']:.1f} W")
        print(f"           parallel {dp['dP_total_parallel_Pa']:.1f} Pa  W_fan {dp['W_fan_parallel_W']:.1f} W  (Re_p={dp['Re_parallel']:.0f})")

    summary_df = pd.DataFrame(rows)
    summary_csv = OUT_DIR / "edge_case_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nSummary CSV: {summary_csv}")

    # Compact headline table
    print(f"\n{'=' * 100}\nHEADLINE TABLE\n{'=' * 100}")
    print(f"{'Case':<48} {'t_ser':>7} {'t_par':>7} {'dt%':>6} {'SEC_s':>7} {'SEC_p':>7} {'dSEC%':>6}")
    for r in rows:
        print(f"{r['case']:<48} {r['series_t_h']:>7.2f} {r['parallel_t_h']:>7.2f} "
              f"{r['dt_dry_pct']:>+6.1f} {r['series_SEC']:>7.4f} {r['parallel_SEC']:>7.4f} "
              f"{r['dSEC_pct']:>+6.1f}")

    print(f"\n{'=' * 100}\nBALANCE CHECKS (max abs residual)\n{'=' * 100}")
    print(f"{'Case':<48} {'1st-law ser':>14} {'1st-law par':>14} {'mass ser':>12} {'mass par':>12}")
    for r in rows:
        print(f"{r['case']:<48} {r['series_E_err_kW']:>14.2e} {r['parallel_E_err_kW']:>14.2e} "
              f"{r['series_M_err_kg']:>12.2e} {r['parallel_M_err_kg']:>12.2e}")

    print(f"\n{'=' * 100}\ndP & FAN POWER (chamber loop)\n{'=' * 100}")
    print(f"{'Case':<48} {'dP_ser':>9} {'dP_par':>9} {'W_ser':>8} {'W_par':>8} {'Re_par':>8}")
    for r in rows:
        print(f"{r['case']:<48} {r['dP_total_series_Pa']:>9.1f} {r['dP_total_parallel_Pa']:>9.1f} "
              f"{r['W_fan_series_W']:>8.1f} {r['W_fan_parallel_W']:>8.1f} {r['Re_parallel']:>8.0f}")


if __name__ == "__main__":
    main()
