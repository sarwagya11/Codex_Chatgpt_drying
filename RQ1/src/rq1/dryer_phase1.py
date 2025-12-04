"""Core Phase-1 dryer simulation with recirculation and first-order drying."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from .ambient import load_ambient_series
from .config import SimulationConfig
from .kinetics import compute_dm_w_air_capacity, compute_dm_w_kinetic_first_order
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
    X_eq_db = cfg.dryer.X_eq_db
    m_p_dry_total = cfg.dryer.m_p_dry_kg
    n_trays = cfg.dryer.n_trays
    m_p_tray = m_p_dry_total / n_trays if n_trays > 0 else 0.0
    X_db_init = cfg.dryer.X0_db

    if n_trays <= 1:
        n_trays = 1
        X_trays: list[float] = [X_db_init]
    else:
        X_trays = [X_db_init for _ in range(n_trays)]
    h_fg = cfg.dryer.h_fg_kJ_per_kg

    records: List[dict] = []

    total_time_s = (
        cfg.ambient.max_steps * cfg.dryer.dt_s if cfg.ambient.max_steps is not None else len(amb_df) * cfg.dryer.dt_s
    )

    # Initialize recirculation state from first ambient point
    T_amb0 = float(amb_df.iloc[0]["T_amb_C"])
    RH_amb0 = float(amb_df.iloc[0]["RH_amb_pct"]) / 100.0
    omega_amb0 = float(humidity_ratio_from_T_RH(T_amb0, RH_amb0))
    h_amb0 = float(moist_air_enthalpy_kJ_per_kg(T_amb0, omega_amb0))
    T_e_prev_C = T_amb0
    omega_e_prev = omega_amb0
    h_e_prev = h_amb0

    m_w_cum = 0.0
    Q_heater_cum_kJ = 0.0

    for step_idx, row in enumerate(amb_df.itertuples(index=False)):
        T_amb_C = float(row.T_amb_C)
        RH_amb_frac = float(row.RH_amb_pct) / 100.0
        omega_f = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))
        h_f = float(moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_f))

        omega_mix = float((1 - r) * omega_f + r * omega_e_prev)
        h_mix = float((1 - r) * h_f + r * h_e_prev)
        T_mix_C = float(temperature_from_h_omega_C(h_mix, omega_mix))
        RH_mix_frac = float(RH_from_T_omega(T_mix_C, omega_mix))

        T_in_C = T_set_C
        omega_in = omega_mix
        h_in = float(moist_air_enthalpy_kJ_per_kg(T_in_C, omega_in))
        Qdot_heater_kW = m_da * (h_in - h_mix)

        RH_in_frac = float(RH_from_T_omega(T_in_C, omega_in))
        time_s = float(step_idx) * dt_s

        if n_trays == 1:
            dm_w_kin_kg = compute_dm_w_kinetic_first_order(
                X_db=X_trays[0],
                X_eq_db=X_eq_db,
                T_in_C=T_in_C,
                RH_in_frac=RH_in_frac,
                dt_s=dt_s,
                cfg=cfg.kinetics,
                m_p_dry_kg=m_p_tray,
            )

            if cfg.kinetics.enable_air_limit:
                dm_w_air_max_kg = compute_dm_w_air_capacity(
                    T_in_C=T_in_C,
                    omega_in=omega_in,
                    m_da_kg_per_s=m_da,
                    dt_s=dt_s,
                    cfg=cfg.kinetics,
                )
            else:
                dm_w_air_max_kg = float("inf")

            dm_w_kg = min(dm_w_kin_kg, dm_w_air_max_kg)

            if m_p_tray > 0.0:
                X_db_new = X_trays[0] - dm_w_kg / m_p_tray
            else:
                X_db_new = X_trays[0]

            if X_db_new < X_eq_db:
                X_db_new = X_eq_db
                dm_w_kg = max(0.0, (X_trays[0] - X_eq_db) * m_p_tray)

            m_w_rate_kg_per_s = dm_w_kg / dt_s

            omega_out = float(omega_in + m_w_rate_kg_per_s / m_da)
            h_out = h_in
            T_out_C = float(temperature_from_h_omega_C(h_out, omega_out))
            RH_out_frac = float(RH_from_T_omega(T_out_C, omega_out))

            if RH_out_frac > 1.0:
                T_out_C = float(dewpoint_from_omega_C(omega_out))
                RH_out_frac = 1.0
                h_out = float(moist_air_enthalpy_kJ_per_kg(T_out_C, omega_out))

            X_trays[0] = X_db_new
            dm_w_list = [dm_w_kg]
            T_out_last = T_out_C
            RH_out_last = RH_out_frac
            omega_out_last = omega_out
        else:
            dm_w_list: list[float] = []
            air_T = T_in_C
            air_omega = omega_in
            air_h = h_in
            for i in range(n_trays):
                RH_in_tray = float(RH_from_T_omega(air_T, air_omega))

                dm_w_kin_kg = compute_dm_w_kinetic_first_order(
                    X_db=X_trays[i],
                    X_eq_db=X_eq_db,
                    T_in_C=air_T,
                    RH_in_frac=RH_in_tray,
                    dt_s=dt_s,
                    cfg=cfg.kinetics,
                    m_p_dry_kg=m_p_tray,
                )

                if cfg.kinetics.enable_air_limit:
                    dm_w_air_max_kg = compute_dm_w_air_capacity(
                        T_in_C=air_T,
                        omega_in=air_omega,
                        m_da_kg_per_s=m_da,
                        dt_s=dt_s,
                        cfg=cfg.kinetics,
                    )
                else:
                    dm_w_air_max_kg = float("inf")

                dm_w_kg = min(dm_w_kin_kg, dm_w_air_max_kg)

                if m_p_tray > 0.0:
                    X_new = X_trays[i] - dm_w_kg / m_p_tray
                else:
                    X_new = X_trays[i]

                if X_new < X_eq_db:
                    X_new = X_eq_db
                    dm_w_kg = max(0.0, (X_trays[i] - X_eq_db) * m_p_tray)

                X_trays[i] = X_new
                dm_w_list.append(dm_w_kg)

                m_w_rate_kg_per_s = dm_w_kg / dt_s
                omega_out = float(air_omega + m_w_rate_kg_per_s / m_da)
                h_out = air_h
                T_out_C = float(temperature_from_h_omega_C(h_out, omega_out))
                RH_out_frac = float(RH_from_T_omega(T_out_C, omega_out))

                if RH_out_frac > 1.0:
                    T_out_C = float(dewpoint_from_omega_C(omega_out))
                    RH_out_frac = 1.0
                    h_out = float(moist_air_enthalpy_kJ_per_kg(T_out_C, omega_out))

                air_T = T_out_C
                air_omega = omega_out
                air_h = h_out

            T_out_last = air_T
            RH_out_last = RH_out_frac
            omega_out_last = air_omega

        m_w_cum += sum(dm_w_list)
        Q_heater_step_kJ = Qdot_heater_kW * dt_s
        Q_heater_cum_kJ += Q_heater_step_kJ

        X_avg = sum(X_trays) / n_trays if n_trays > 0 else 0.0
        MR = (X_avg - X_eq_db) / (cfg.dryer.X0_db - X_eq_db) if cfg.dryer.X0_db != X_eq_db else 0.0

        records.append(
            {
                "time_s": time_s,
                "T_amb_C": T_amb_C,
                "RH_amb_pct": float(row.RH_amb_pct),
                "T_mix_C": T_mix_C,
                "RH_mix_frac": RH_mix_frac,
                "omega_mix": omega_mix,
                "h_mix_kJ_per_kg": h_mix,
                "T_in_C": T_in_C,
                "RH_in_frac": RH_in_frac,
                "omega_in": omega_in,
                "h_in_kJ_per_kg": h_in,
                "T_out_C": T_out_last,
                "RH_out_frac": RH_out_last,
                "omega_out": omega_out_last,
                "h_out_kJ_per_kg": h_out,
                "r_recirc": r,
                "X_db": X_avg,
                "MR": MR,
                "dm_w_kg": sum(dm_w_list),
                "m_w_cum_kg": m_w_cum,
                "Qdot_heater_kW": Qdot_heater_kW,
                "Q_heater_step_kJ": Q_heater_step_kJ,
                "Q_heater_cum_kJ": Q_heater_cum_kJ,
                "X_tray_0": X_trays[0],
                "X_tray_last": X_trays[-1],
            }
        )

        # Update recirculation states for next step
        T_e_prev_C = T_out_last
        omega_e_prev = omega_out_last
        h_e_prev = h_out

        if all(x <= X_eq_db + 1e-6 for x in X_trays):
            break

    result_df = pd.DataFrame.from_records(records)

    if not result_df.empty:
        Q_total_kWh = result_df["Q_heater_step_kJ"].sum() / 3600.0
        SEC_kWh_per_kg = Q_total_kWh / result_df["m_w_cum_kg"].iloc[-1] if result_df["m_w_cum_kg"].iloc[-1] > 0 else None
        result_df.loc[result_df.index[-1], "SEC_kWh_per_kg"] = SEC_kWh_per_kg

    times_s = result_df["time_s"] if "time_s" in result_df else pd.Series(dtype=float)
    return Phase1Result(times_s=times_s, df=result_df)
