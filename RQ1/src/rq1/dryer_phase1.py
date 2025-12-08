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
    """Run Phase-1 simulation for the given configuration.

    Physics outline:
    * Heater raises mixed air from (T_mix, ω_mix) -> (T_set, ω_mix).
    * Air passes through n_trays in series; each tray removes dm_w_tray at fixed enthalpy.
    * Outlet of tray j is inlet of tray j+1.
    * Total dm_w in a step = sum over trays; global X_db is tray-average.
    """

    amb_df = load_ambient_series(cfg.ambient)
    dt_s = cfg.dryer.dt_s
    m_da = cfg.dryer.m_da_kg_per_s
    r = cfg.dryer.r_recirc
    T_set_C = cfg.dryer.T_set_C
    X_eq_db = cfg.dryer.X_eq_db
    m_p_dry_total = cfg.dryer.m_p_dry_kg
    n_trays = max(1, int(cfg.dryer.n_trays))
    m_p_tray = m_p_dry_total / n_trays if n_trays > 0 else m_p_dry_total
    X_db_init = cfg.dryer.X0_db
    X_trays: list[float] = [X_db_init for _ in range(n_trays)]
    MR_trays: list[float] = [1.0 for _ in range(n_trays)]
    h_fg = cfg.dryer.h_fg_kJ_per_kg

    records: List[dict] = []

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

        tau_tray_s = None
        if cfg.dryer.tray_area_m2 is not None and cfg.dryer.tray_depth_m is not None and m_da > 0:
            V_tray_m3 = cfg.dryer.tray_area_m2 * cfg.dryer.tray_depth_m
            rho_da = cfg.dryer.air_density_kg_per_m3
            m_air_in_tray = rho_da * V_tray_m3
            tau_tray_s = m_air_in_tray / m_da

        X_db_mean = sum(X_trays) / n_trays if n_trays > 0 else 0.0
        dm_w_kin_total_kg = compute_dm_w_kinetic_first_order(
            X_db=X_db_mean,
            X_eq_db=X_eq_db,
            T_in_C=T_in_C,
            RH_in_frac=RH_in_frac,
            dt_s=dt_s,
            cfg=cfg.kinetics,
            m_p_dry_kg=m_p_dry_total,
            time_s=time_s,
        )

        T_air_in = T_in_C
        omega_air_in = omega_in
        h_air_in = h_in
        RH_air_in = RH_in_frac

        # Ensure tray state vectors remain aligned with n_trays in case a config
        # change slipped through.
        if len(X_trays) < n_trays:
            X_trays.extend([X_db_init] * (n_trays - len(X_trays)))
        elif len(X_trays) > n_trays:
            X_trays = X_trays[:n_trays]

        if len(MR_trays) < n_trays:
            MR_trays.extend([1.0] * (n_trays - len(MR_trays)))
        elif len(MR_trays) > n_trays:
            MR_trays = MR_trays[:n_trays]

        dm_w_list: list[float] = []
        T_tray_out_list: list[float] = []
        RH_tray_out_list: list[float] = []

        for i in range(n_trays):
            X_j = X_trays[i]
            dm_w_air_max_kg = compute_dm_w_air_capacity(
                T_in_C=T_air_in,
                omega_in=omega_air_in,
                m_da_kg_per_s=m_da,
                dt_s=dt_s,
                cfg=cfg.kinetics,
                h_fg_kJ_per_kg=h_fg,
            ) if cfg.kinetics.enable_air_limit else float("inf")

            dm_w_kin_kg = dm_w_kin_total_kg / n_trays if n_trays > 0 else 0.0
            max_removable = max(0.0, (X_j - X_eq_db) * m_p_tray)
            dm_w_tray_kg = max(0.0, min(dm_w_kin_kg, dm_w_air_max_kg, max_removable))

            if m_p_tray > 0.0:
                X_new = X_j - dm_w_tray_kg / m_p_tray
            else:
                X_new = X_j

            if X_new < X_eq_db:
                X_new = X_eq_db
            X_trays[i] = X_new

            MR_trays[i] = (
                (X_new - X_eq_db) / (cfg.dryer.X0_db - X_eq_db) if cfg.dryer.X0_db != X_eq_db else 0.0
            )

            m_w_rate_kg_per_s = dm_w_tray_kg / dt_s if dt_s > 0 else 0.0
            omega_air_out = (
                float(omega_air_in + m_w_rate_kg_per_s / m_da) if m_da > 0 else omega_air_in
            )

            if m_da > 0 and dt_s > 0:
                Qdot_latent_kW = m_w_rate_kg_per_s * h_fg
                h_air_out = h_air_in - Qdot_latent_kW / m_da
            else:
                h_air_out = h_air_in
            T_air_out = float(temperature_from_h_omega_C(h_air_out, omega_air_out))
            RH_air_out = float(RH_from_T_omega(T_air_out, omega_air_out))

            if RH_air_out > 1.0:
                T_air_out = float(dewpoint_from_omega_C(omega_air_out))
                RH_air_out = 1.0
                h_air_out = float(moist_air_enthalpy_kJ_per_kg(T_air_out, omega_air_out))

            dm_w_list.append(dm_w_tray_kg)
            T_tray_out_list.append(T_air_out)
            RH_tray_out_list.append(RH_air_out)

            T_air_in = T_air_out
            omega_air_in = omega_air_out
            h_air_in = h_air_out
            RH_air_in = RH_air_out

        if n_trays > 0:
            T_out_last = T_tray_out_list[-1]
            RH_out_last = RH_tray_out_list[-1]
            omega_out_last = omega_air_out
            h_out_last = h_air_out
        else:
            T_out_last = T_in_C
            RH_out_last = RH_in_frac
            omega_out_last = omega_in
            h_out_last = h_in

        m_w_step = sum(dm_w_list)
        m_w_cum += m_w_step
        Q_heater_step_kJ = Qdot_heater_kW * dt_s
        Q_heater_cum_kJ += Q_heater_step_kJ

        X_avg = sum(X_trays) / n_trays if n_trays > 0 else 0.0
        MR_global = sum(MR_trays) / n_trays if n_trays > 0 else 0.0

        dm_mismatch = m_w_step - dm_w_kin_total_kg

        record = {
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
            "h_out_kJ_per_kg": h_out_last,
            "r_recirc": r,
            "X_db": X_avg,
            "MR": MR_global,
            "dm_w_kg": m_w_step,
            "m_w_cum_kg": m_w_cum,
            "Qdot_heater_kW": Qdot_heater_kW,
            "Q_heater_step_kJ": Q_heater_step_kJ,
            "Q_heater_cum_kJ": Q_heater_cum_kJ,
            "tau_tray_s": tau_tray_s,
            "dm_w_trays_sum_minus_total_kg": dm_mismatch,
        }

        for i in range(n_trays):
            record[f"X_tray_{i}"] = X_trays[i]
            record[f"MR_tray{i}"] = MR_trays[i]
            record[f"T_tray{i}_out_C"] = T_tray_out_list[i]
            record[f"RH_tray{i}_out_frac"] = RH_tray_out_list[i]
            record[f"dm_w_tray{i}_kg"] = dm_w_list[i]

        record["X_tray_last"] = X_trays[-1]

        records.append(record)

        T_e_prev_C = T_out_last
        omega_e_prev = omega_out_last
        h_e_prev = h_out_last

        if all(X <= X_eq_db + 1e-6 for X in X_trays):
            break

    result_df = pd.DataFrame.from_records(records)

    if cfg.dryer.debug_checks and not result_df.empty:
        dMR_max = result_df["MR"].diff().dropna().max()
        if dMR_max > 1e-5:
            print(f"Warning: MR increased over time (max dMR = {dMR_max:.3e})")

        for i in range(n_trays):
            mr_col = f"MR_tray{i}"
            if mr_col in result_df.columns:
                dMR_tray_max = result_df[mr_col].diff().dropna().max()
                if dMR_tray_max > 1e-5:
                    print(f"Warning: MR_tray{i} increased over time (max dMR = {dMR_tray_max:.3e})")

            rh_col = f"RH_tray{i}_out_frac"
            if rh_col in result_df.columns:
                max_rh = result_df[rh_col].max()
                if max_rh > 1.0001:
                    print(f"Warning: RH_tray{i}_out_frac exceeded saturation (max = {max_rh:.3f})")

        if "RH_out_frac" in result_df.columns:
            max_rh_out = result_df["RH_out_frac"].max()
            if max_rh_out > 1.0001:
                print(f"Warning: RH_out_frac exceeded saturation (max = {max_rh_out:.3f})")

    if not result_df.empty:
        Q_total_kWh = result_df["Q_heater_step_kJ"].sum() / 3600.0
        total_m_w = m_w_cum
        SEC_kWh_per_kg = Q_total_kWh / total_m_w if total_m_w > 0 else None
        result_df.loc[result_df.index[-1], "SEC_kWh_per_kg"] = SEC_kWh_per_kg

    times_s = result_df["time_s"] if "time_s" in result_df else pd.Series(dtype=float)
    return Phase1Result(times_s=times_s, df=result_df)
