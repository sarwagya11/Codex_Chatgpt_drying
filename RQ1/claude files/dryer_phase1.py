"""Core Phase-1 dryer simulation with recirculation, HP, and solar heating."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from .ambient import load_ambient_series
from .config import SimulationConfig
from .kinetics import compute_dm_w_air_capacity, compute_dm_w_kinetic_first_order
from .heat_pump import compute_HP_heating, select_HP_source
from .solar_collector import compute_solar_heating
from .psychro import (
    RH_from_T_omega,
    humidity_ratio_from_T_RH,
    moist_air_enthalpy_kJ_per_kg,
    temperature_from_h_omega_C,
    dewpoint_from_omega_C,
)

# Specific heat of moist air (approximate)
CP_MA_KJ_PER_KG_K = 1.02


@dataclass
class Phase1Result:
    times_s: pd.Series
    df: pd.DataFrame


def run_phase1_simulation(cfg: SimulationConfig) -> Phase1Result:
    """Run Phase-1 simulation for the given configuration.

    Physics outline (HP+Solar variant):
    * Air mixing: (T_amb, ω_amb) mixed with recirculated exhaust → (T_mix, ω_mix)
    * HP heating: T_mix → T_after_HP (limited by HP capacity and ambient)
    * Solar heating: T_after_HP → T_after_solar (depends on GHI)
    * Optional backup: T_after_solar → T_set (if backup enabled)
    * Multi-tray cascade: air passes through n_trays in series
    * Total dm_w in a step = sum over trays; global X_db is tray-average
    """

    amb_df = load_ambient_series(cfg.ambient)
    dt_s = cfg.dryer.dt_s
    r = cfg.dryer.r_recirc
    T_set_C = cfg.dryer.T_set_C
    X_eq_db = cfg.dryer.X_eq_db
    m_p_dry_total = cfg.dryer.m_p_dry_kg
    n_trays = max(1, min(int(cfg.dryer.n_trays), int(cfg.dryer.max_trays)))
    cfg.dryer.n_trays = n_trays
    m_p_tray = m_p_dry_total / n_trays if n_trays > 0 else m_p_dry_total

    if cfg.dryer.tray_area_m2 is None:
        rho_bulk = cfg.dryer.product_apparent_density_kg_per_m3
        thickness = cfg.dryer.product_thickness_m
        if rho_bulk > 0.0 and thickness > 0.0:
            tray_area = m_p_tray / (rho_bulk * thickness)
            cfg.dryer.tray_area_m2 = tray_area
            print(
                f"[INFO] Tray area set to {cfg.dryer.tray_area_m2:.3f} m² for {n_trays} trays of {m_p_tray:.2f} kg each."
            )

    m_da = cfg.dryer.m_da_kg_per_s
    if m_da <= 0.0 and cfg.dryer.tray_area_m2 is not None and cfg.dryer.air_density_kg_per_m3 > 0.0:
        v_target_ms = 1.1
        m_da = cfg.dryer.air_density_kg_per_m3 * cfg.dryer.tray_area_m2 * v_target_ms
        cfg.dryer.m_da_kg_per_s = m_da
        print(
            f"[INFO] m_da auto-set to {cfg.dryer.m_da_kg_per_s:.3f} kg/s for v = {v_target_ms} m/s over {cfg.dryer.tray_area_m2:.3f} m²"
        )

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

    # Cumulative tracking
    m_w_cum = 0.0
    Q_heater_cum_kJ = 0.0
    Q_HP_cum_kJ = 0.0
    W_HP_cum_kJ = 0.0
    Q_solar_cum_kJ = 0.0
    Q_backup_cum_kJ = 0.0
    m_w_condensed_cum = 0.0

    if (
        cfg.dryer.tray_area_m2 is None
        or cfg.dryer.tray_depth_m is None
        or m_da <= 0
        or cfg.dryer.air_density_kg_per_m3 <= 0
    ):
        raise ValueError(
            "tray_area_m2, tray_depth_m, air_density_kg_per_m3, and m_da_kg_per_s must be set"
        )

    V_tray_m3 = cfg.dryer.tray_area_m2 * cfg.dryer.tray_depth_m
    m_air_in_tray = cfg.dryer.air_density_kg_per_m3 * V_tray_m3
    tau_tray_s = m_air_in_tray / m_da
    print(
        f"[INFO] tau_tray_s = {tau_tray_s:.2f} s computed for volume = {V_tray_m3:.3f} m³"
    )

    # Print heating mode info
    if cfg.heat_pump.enabled:
        print(f"[INFO] Heat pump enabled: Q_nom={cfg.heat_pump.Q_HP_nom_kW} kW, source={cfg.heat_pump.source_mode}")
    if cfg.solar.enabled:
        print(f"[INFO] Solar collector enabled: A_col={cfg.solar.A_col_m2} m²")
    if not cfg.dryer.use_backup_heater:
        print("[INFO] No backup heater - T_in will be variable based on HP+Solar")

    for step_idx, row in enumerate(amb_df.itertuples(index=False)):
        T_amb_C = float(row.T_amb_C)
        RH_amb_frac = float(row.RH_amb_pct) / 100.0
        
        # Get GHI if available
        GHI_Wm2 = float(getattr(row, "GHI_Wm2", 0.0))
        
        omega_f = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))
        h_f = float(moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_f))

        # === MIXING STAGE ===
        omega_mix_raw = float((1 - r) * omega_f + r * omega_e_prev)
        h_mix_raw = float((1 - r) * h_f + r * h_e_prev)
        T_mix_C = float(temperature_from_h_omega_C(h_mix_raw, omega_mix_raw))
        RH_mix_frac = float(RH_from_T_omega(T_mix_C, omega_mix_raw))

        omega_mix = omega_mix_raw
        h_mix = h_mix_raw
        m_w_condensed_step = 0.0
        if RH_mix_frac > 1.0:
            omega_sat = float(humidity_ratio_from_T_RH(T_mix_C, 1.0))
            m_w_condensed_step = max(0.0, omega_mix_raw - omega_sat) * m_da * dt_s
            omega_mix = omega_sat
            h_mix = float(moist_air_enthalpy_kJ_per_kg(T_mix_C, omega_mix))
            RH_mix_frac = 1.0
        m_w_condensed_cum += m_w_condensed_step

        time_s = float(step_idx) * dt_s

        # === HEATING STAGES ===
        
        # Stage 1: Heat Pump
        T_after_HP = T_mix_C
        Q_HP_kW = 0.0
        W_HP_kW = 0.0
        COP_actual = 0.0
        HP_at_capacity = False
        HP_running = False
        HP_source_used = "none"

        if cfg.heat_pump.enabled:
            # Select heat source (ambient or exhaust)
            T_source, HP_source_used = select_HP_source(
                T_amb_C=T_amb_C,
                T_exhaust_C=T_e_prev_C,
                cfg=cfg.heat_pump,
            )
            
            hp_result = compute_HP_heating(
                T_source_C=T_source,
                T_in_C=T_mix_C,
                T_target_C=T_set_C,
                m_da_kg_per_s=m_da,
                dt_s=dt_s,
                cfg=cfg.heat_pump,
            )
            
            T_after_HP = hp_result["T_out_C"]
            Q_HP_kW = hp_result["Q_HP_kW"]
            W_HP_kW = hp_result["W_HP_kW"]
            COP_actual = hp_result["COP_actual"]
            HP_at_capacity = hp_result["HP_at_capacity"]
            HP_running = hp_result["HP_running"]

        # Stage 2: Solar Collector
        T_after_solar = T_after_HP
        Q_solar_kW = 0.0
        eta_collector = 0.0
        solar_active = False

        if cfg.solar.enabled:
            solar_result = compute_solar_heating(
                GHI_Wm2=GHI_Wm2,
                T_in_C=T_after_HP,
                T_amb_C=T_amb_C,
                m_da_kg_per_s=m_da,
                cfg=cfg.solar,
            )
            
            T_after_solar = solar_result["T_out_C"]
            Q_solar_kW = solar_result["Q_solar_kW"]
            eta_collector = solar_result["eta_collector"]
            solar_active = solar_result["solar_active"]

        # Stage 3: Backup Heater (optional)
        Q_backup_kW = 0.0
        
        if cfg.dryer.use_backup_heater:
            # Use backup heater to reach T_set
            T_gap = T_set_C - T_after_solar
            if T_gap > 0:
                Q_backup_kW = m_da * CP_MA_KJ_PER_KG_K * T_gap
                T_in_C = T_set_C
            else:
                T_in_C = T_after_solar
        else:
            # No backup - accept whatever temperature was achieved
            T_in_C = T_after_solar

        # Total heating power (for logging)
        Qdot_total_kW = Q_HP_kW + Q_solar_kW + Q_backup_kW

        omega_in = omega_mix
        h_in = float(moist_air_enthalpy_kJ_per_kg(T_in_C, omega_in))
        RH_in_frac = float(RH_from_T_omega(T_in_C, omega_in))

        T_air_in = T_in_C
        omega_air_in = omega_in
        h_air_in = h_in
        RH_air_in = RH_in_frac

        # Ensure tray state vectors remain aligned with n_trays
        if len(X_trays) < n_trays:
            X_trays.extend([X_db_init] * (n_trays - len(X_trays)))
        elif len(X_trays) > n_trays:
            X_trays = X_trays[:n_trays]

        if len(MR_trays) < n_trays:
            MR_trays.extend([1.0] * (n_trays - len(MR_trays)))
        elif len(MR_trays) > n_trays:
            MR_trays = MR_trays[:n_trays]

        # === MULTI-TRAY CASCADE ===
        dm_w_list: list[float] = []
        T_tray_out_list: list[float] = []
        RH_tray_out_list: list[float] = []
        h_tray_out_list: list[float] = []
        q_air_available_list: list[float | None] = []
        q_needed_latent_list: list[float] = []
        q_deficit_list: list[float | None] = []
        air_limit_flag_list: list[bool] = []

        for i in range(n_trays):
            X_j = X_trays[i]
            air_T = T_air_in
            air_omega = omega_air_in
            air_h = h_air_in
            RH_in_tray = float(RH_from_T_omega(air_T, air_omega))

            dm_w_kin_kg = compute_dm_w_kinetic_first_order(
                X_db=X_j,
                X_eq_db=X_eq_db,
                T_in_C=air_T,
                RH_in_frac=RH_in_tray,
                dt_s=dt_s,
                cfg=cfg.kinetics,
                m_p_dry_kg=m_p_tray,
                time_s=time_s,
            )

            dm_w_air_max_kg = (
                compute_dm_w_air_capacity(
                    T_in_C=air_T,
                    omega_in=air_omega,
                    m_da_kg_per_s=m_da,
                    dt_s=dt_s,
                    cfg=cfg.kinetics,
                    h_fg_kJ_per_kg=h_fg,
                )
                if cfg.kinetics.enable_air_limit
                else float("inf")
            )

            max_removable = max(0.0, (X_j - X_eq_db) * m_p_tray)
            dm_w_tray_kg = min(dm_w_kin_kg, dm_w_air_max_kg, max_removable)

            dX_tray = dm_w_tray_kg / m_p_tray if m_p_tray > 0.0 else 0.0
            X_new = max(X_j - dX_tray, X_eq_db)
            dm_w_actual = max(0.0, (X_j - X_new) * m_p_tray)

            X_trays[i] = X_new

            MR_trays[i] = (
                (X_new - X_eq_db) / (cfg.dryer.X0_db - X_eq_db) if cfg.dryer.X0_db != X_eq_db else 0.0
            )

            m_w_rate_kg_per_s = dm_w_actual / dt_s if dt_s > 0 else 0.0
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
                RH_air_out = min(RH_air_out, 1.0)
                h_air_out = float(moist_air_enthalpy_kJ_per_kg(T_air_out, omega_air_out))

            if tau_tray_s is not None:
                delta_h = h_air_in - h_air_out
                q_air_available_kJ = m_da * delta_h * tau_tray_s
            else:
                q_air_available_kJ = None

            h_fg_diag = 2450.0
            q_needed_latent_kJ = dm_w_actual * h_fg_diag
            q_deficit_kJ = (
                q_needed_latent_kJ - q_air_available_kJ
                if q_air_available_kJ is not None
                else None
            )
            air_energy_insufficient = bool(
                q_deficit_kJ is not None and q_deficit_kJ > 0
            )

            dm_w_list.append(dm_w_actual)
            T_tray_out_list.append(T_air_out)
            RH_tray_out_list.append(RH_air_out)
            h_tray_out_list.append(h_air_out)
            q_air_available_list.append(q_air_available_kJ)
            q_needed_latent_list.append(q_needed_latent_kJ)
            q_deficit_list.append(q_deficit_kJ)
            air_limit_flag_list.append(air_energy_insufficient)

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

        # === CUMULATIVE TRACKING ===
        dm_w_trays_sum = sum(dm_w_list)
        m_w_step = dm_w_trays_sum
        m_w_cum += m_w_step

        # Energy tracking (all in kJ)
        Q_HP_step_kJ = Q_HP_kW * dt_s
        W_HP_step_kJ = W_HP_kW * dt_s
        Q_solar_step_kJ = Q_solar_kW * dt_s
        Q_backup_step_kJ = Q_backup_kW * dt_s
        Q_total_step_kJ = Q_HP_step_kJ + Q_solar_step_kJ + Q_backup_step_kJ

        Q_HP_cum_kJ += Q_HP_step_kJ
        W_HP_cum_kJ += W_HP_step_kJ
        Q_solar_cum_kJ += Q_solar_step_kJ
        Q_backup_cum_kJ += Q_backup_step_kJ
        Q_heater_cum_kJ += Q_total_step_kJ  # Keep for backward compatibility

        X_avg = sum(X_trays) / n_trays if n_trays > 0 else 0.0
        MR_global = (
            (X_avg - X_eq_db) / (cfg.dryer.X0_db - X_eq_db) if cfg.dryer.X0_db != X_eq_db else 0.0
        )

        dm_mismatch = m_w_step - dm_w_trays_sum

        # === BUILD RECORD ===
        record = {
            "time_s": time_s,
            "T_amb_C": T_amb_C,
            "RH_amb_pct": float(row.RH_amb_pct),
            "GHI_Wm2": GHI_Wm2,
            
            # Mixing stage
            "T_mix_C": T_mix_C,
            "RH_mix_frac": RH_mix_frac,
            "omega_mix": omega_mix,
            "h_mix_kJ_per_kg": h_mix,
            
            # HP stage
            "T_after_HP_C": T_after_HP,
            "Q_HP_kW": Q_HP_kW,
            "W_HP_kW": W_HP_kW,
            "COP_actual": COP_actual,
            "HP_at_capacity": HP_at_capacity,
            "HP_running": HP_running,
            "HP_source": HP_source_used,
            
            # Solar stage
            "T_after_solar_C": T_after_solar,
            "Q_solar_kW": Q_solar_kW,
            "eta_collector": eta_collector,
            "solar_active": solar_active,
            
            # Backup/Final inlet
            "Q_backup_kW": Q_backup_kW,
            "T_in_C": T_in_C,
            "RH_in_frac": RH_in_frac,
            "omega_in": omega_in,
            "h_in_kJ_per_kg": h_in,
            
            # Outlet
            "T_out_C": T_out_last,
            "RH_out_frac": RH_out_last,
            "omega_out": omega_out_last,
            "h_out_kJ_per_kg": h_out_last,
            
            # System state
            "r_recirc": r,
            "X_db": X_avg,
            "MR": MR_global,
            "dm_w_kg": m_w_step,
            "m_w_cum_kg": m_w_cum,
            
            # Energy totals
            "Qdot_total_kW": Qdot_total_kW,
            "Q_HP_step_kJ": Q_HP_step_kJ,
            "W_HP_step_kJ": W_HP_step_kJ,
            "Q_solar_step_kJ": Q_solar_step_kJ,
            "Q_backup_step_kJ": Q_backup_step_kJ,
            "Q_HP_cum_kJ": Q_HP_cum_kJ,
            "W_HP_cum_kJ": W_HP_cum_kJ,
            "Q_solar_cum_kJ": Q_solar_cum_kJ,
            "Q_backup_cum_kJ": Q_backup_cum_kJ,
            
            # Backward compatibility
            "Qdot_heater_kW": Qdot_total_kW,
            "Q_heater_step_kJ": Q_total_step_kJ,
            "Q_heater_cum_kJ": Q_heater_cum_kJ,
            
            "tau_tray_s": tau_tray_s,
            "dm_w_trays_sum_minus_total_kg": dm_mismatch,
        }

        # Per-tray data
        for i in range(n_trays):
            record[f"X_tray_{i}"] = X_trays[i]
            record[f"MR_tray{i}"] = MR_trays[i]
            record[f"T_tray{i}_out_C"] = T_tray_out_list[i]
            record[f"RH_tray{i}_out_frac"] = RH_tray_out_list[i]
            record[f"dm_w_tray{i}_kg"] = dm_w_list[i]
            record[f"h_tray{i}_out_kJ_per_kg"] = h_tray_out_list[i]
            record[f"q_air_tray{i}_kJ"] = q_air_available_list[i]
            record[f"q_needed_tray{i}_kJ"] = q_needed_latent_list[i]
            record[f"q_deficit_tray{i}_kJ"] = q_deficit_list[i]
            record[f"air_limit_flag_tray{i}"] = air_limit_flag_list[i]

        record["X_tray_last"] = X_trays[-1]
        record["m_w_condensed_step_kg"] = m_w_condensed_step
        record["m_w_condensed_cum_kg"] = m_w_condensed_cum

        records.append(record)

        # Update recirculation state
        T_e_prev_C = T_out_last
        omega_e_prev = omega_out_last
        h_e_prev = h_out_last

        # === TERMINATION CHECK ===
        MR_threshold = cfg.dryer.MR_termination_threshold
        
        if cfg.dryer.require_all_trays_dried:
            # Strict: all trays must be below threshold
            if all(MR_trays[i] < MR_threshold for i in range(n_trays)):
                print(f"[INFO] All trays dried (MR < {MR_threshold}) at t = {time_s/3600:.2f} h")
                break
        else:
            # Original: check global average
            if all(X <= X_eq_db + 1e-6 for X in X_trays):
                break

    # === POST-PROCESSING ===
    result_df = pd.DataFrame.from_records(records)
    if "tau_tray_s" in result_df.columns:
        result_df["tau_tray_s"] = result_df["tau_tray_s"].astype(float)

    # Debug checks
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

    # === FINAL METRICS ===
    if not result_df.empty:
        total_m_w = m_w_cum
        
        # Electrical energy consumed (HP only, in kWh)
        W_HP_total_kWh = W_HP_cum_kJ / 3600.0
        
        # Thermal energy delivered (in kWh)
        Q_HP_total_kWh = Q_HP_cum_kJ / 3600.0
        Q_solar_total_kWh = Q_solar_cum_kJ / 3600.0
        Q_backup_total_kWh = Q_backup_cum_kJ / 3600.0
        Q_total_kWh = Q_HP_total_kWh + Q_solar_total_kWh + Q_backup_total_kWh
        
        # SEC based on electrical input (main metric for HP systems)
        if total_m_w > 0:
            SEC_elec_kWh_per_kg = W_HP_total_kWh / total_m_w
            SEC_thermal_kWh_per_kg = Q_total_kWh / total_m_w
        else:
            SEC_elec_kWh_per_kg = None
            SEC_thermal_kWh_per_kg = None
        
        # System COP (Q_total / W_elec)
        if W_HP_total_kWh > 0:
            COP_system = Q_total_kWh / W_HP_total_kWh
        else:
            COP_system = None
        
        # Solar fraction
        if Q_total_kWh > 0:
            solar_fraction = Q_solar_total_kWh / Q_total_kWh
        else:
            solar_fraction = 0.0
        
        # HP fraction
        if Q_total_kWh > 0:
            hp_fraction = Q_HP_total_kWh / Q_total_kWh
        else:
            hp_fraction = 0.0
        
        # Store final metrics in last row
        result_df.loc[result_df.index[-1], "SEC_kWh_per_kg"] = SEC_elec_kWh_per_kg
        result_df.loc[result_df.index[-1], "SEC_thermal_kWh_per_kg"] = SEC_thermal_kWh_per_kg
        result_df.loc[result_df.index[-1], "COP_system"] = COP_system
        result_df.loc[result_df.index[-1], "solar_fraction"] = solar_fraction
        result_df.loc[result_df.index[-1], "hp_fraction"] = hp_fraction
        result_df.loc[result_df.index[-1], "W_HP_total_kWh"] = W_HP_total_kWh
        result_df.loc[result_df.index[-1], "Q_HP_total_kWh"] = Q_HP_total_kWh
        result_df.loc[result_df.index[-1], "Q_solar_total_kWh"] = Q_solar_total_kWh
        result_df.loc[result_df.index[-1], "Q_backup_total_kWh"] = Q_backup_total_kWh
        
        # Temperature statistics
        result_df.loc[result_df.index[-1], "T_in_mean_C"] = result_df["T_in_C"].mean()
        result_df.loc[result_df.index[-1], "T_in_min_C"] = result_df["T_in_C"].min()
        result_df.loc[result_df.index[-1], "T_in_max_C"] = result_df["T_in_C"].max()

    times_s = result_df["time_s"] if "time_s" in result_df else pd.Series(dtype=float)
    return Phase1Result(times_s=times_s, df=result_df)
