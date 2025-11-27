"""Core Phase-1 dryer simulation with recirculation and first-order drying."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from .ambient import load_ambient_series
from .config import SimulationConfig
from .kinetics import update_X_db_first_order
from .psychro import (
    RH_from_T_omega,
    humidity_ratio_from_T_RH,
    moist_air_enthalpy_kJ_per_kg,
    temperature_from_h_omega_C,
    dewpoint_from_omega_C,
)


@dataclass
class Phase1Result:
    times_s: pd.Series
    df: pd.DataFrame


def run_phase1_simulation(cfg: SimulationConfig) -> Phase1Result:
    """Run Phase-1 simulation for the given configuration."""

    amb_df = load_ambient_series(cfg.ambient)
    dt_s = cfg.dryer.dt_s
    m_da = cfg.dryer.m_da_kg_per_s
    r = cfg.dryer.r_recirc
    T_set_C = cfg.dryer.T_set_C
    X_db = cfg.dryer.X0_db
    X_eq_db = cfg.dryer.X_eq_db
    m_p_dry = cfg.dryer.m_p_dry_kg
    h_fg = cfg.dryer.h_fg_kJ_per_kg

    records: List[dict] = []

    # Initialize recirculation state from first ambient point
    T_amb0 = amb_df.iloc[0]["T_amb_C"]
    RH_amb0 = amb_df.iloc[0]["RH_amb_pct"] / 100.0
    omega_amb0 = humidity_ratio_from_T_RH(T_amb0, RH_amb0)
    h_amb0 = moist_air_enthalpy_kJ_per_kg(T_amb0, omega_amb0)
    T_e_prev_C = T_amb0
    omega_e_prev = omega_amb0
    h_e_prev = h_amb0

    m_w_cum = 0.0
    Q_heater_cum_kJ = 0.0

    for k, row in amb_df.iterrows():
        T_amb_C = float(row["T_amb_C"])
        RH_amb_frac = float(row["RH_amb_pct"]) / 100.0
        omega_f = humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac)
        h_f = moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_f)

        omega_mix = (1 - r) * omega_f + r * omega_e_prev
        h_mix = (1 - r) * h_f + r * h_e_prev
        T_mix_C = temperature_from_h_omega_C(h_mix, omega_mix)
        RH_mix_frac = RH_from_T_omega(T_mix_C, omega_mix)

        T_in_C = T_set_C
        omega_in = omega_mix
        h_in = moist_air_enthalpy_kJ_per_kg(T_in_C, omega_in)
        Qdot_heater_kW = m_da * (h_in - h_mix)

        X_db_new = update_X_db_first_order(
            X_db=X_db,
            X_eq_db=X_eq_db,
            T_in_C=T_in_C,
            dt_s=dt_s,
            cfg=cfg.kinetics,
        )
        dX = X_db - X_db_new
        dm_w_kg = m_p_dry * dX
        m_w_rate_kg_per_s = dm_w_kg / dt_s

        # 5) Chamber outlet air
        omega_out = omega_in + m_w_rate_kg_per_s / m_da

        # First, assume adiabatic (constant enthalpy) to get a trial state
        h_out = h_in
        T_out_C = temperature_from_h_omega_C(h_out, omega_out)
        RH_out_frac = RH_from_T_omega(T_out_C, omega_out)

        # Saturation clamp: if RH_out > 1, force saturation and recompute T_out, h_out
        if RH_out_frac > 1.0:
            # Dewpoint temperature at this humidity ratio (saturated state)
            T_out_C = dewpoint_from_omega_C(omega_out)
            RH_out_frac = 1.0
            # Update enthalpy for the saturated outlet state
            h_out = moist_air_enthalpy_kJ_per_kg(T_out_C, omega_out)


        m_w_cum += dm_w_kg
        Q_heater_step_kJ = Qdot_heater_kW * dt_s
        Q_heater_cum_kJ += Q_heater_step_kJ

        MR = (X_db_new - X_eq_db) / (cfg.dryer.X0_db - X_eq_db) if cfg.dryer.X0_db != X_eq_db else 0.0

        records.append(
            {
                "time_s": k*dt_s,
                "T_amb_C": T_amb_C,
                "RH_amb_pct": row["RH_amb_pct"],
                "T_mix_C": T_mix_C,
                "RH_mix_frac": RH_mix_frac,
                "omega_mix": omega_mix,
                "h_mix_kJ_per_kg": h_mix,
                "T_in_C": T_in_C,
                "RH_in_frac": RH_from_T_omega(T_in_C, omega_in),
                "omega_in": omega_in,
                "h_in_kJ_per_kg": h_in,
                "T_out_C": T_out_C,
                "RH_out_frac": RH_out_frac,
                "omega_out": omega_out,
                "h_out_kJ_per_kg": h_out,
                "r_recirc": r,
                "X_db": X_db_new,
                "MR": MR,
                "dm_w_kg": dm_w_kg,
                "m_w_cum_kg": m_w_cum,
                "Qdot_heater_kW": Qdot_heater_kW,
                "Q_heater_step_kJ": Q_heater_step_kJ,
                "Q_heater_cum_kJ": Q_heater_cum_kJ,
            }
        )

        # Update recirculation states for next step
        T_e_prev_C = T_out_C
        omega_e_prev = omega_out
        h_e_prev = h_out
        X_db = X_db_new

        if X_db_new <= X_eq_db + 1e-6:
            break

    result_df = pd.DataFrame.from_records(records)

    if not result_df.empty:
        Q_total_kWh = result_df["Q_heater_step_kJ"].sum() / 3600.0
        SEC_kWh_per_kg = Q_total_kWh / result_df["m_w_cum_kg"].iloc[-1] if result_df["m_w_cum_kg"].iloc[-1] > 0 else None
        result_df.loc[result_df.index[-1], "SEC_kWh_per_kg"] = SEC_kWh_per_kg

    times_s = result_df["time_s"] if "time_s" in result_df else pd.Series(dtype=float)
    return Phase1Result(times_s=times_s, df=result_df)
