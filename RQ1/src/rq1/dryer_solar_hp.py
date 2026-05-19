"""Solar-assisted heat pump dryer simulator - 4 CONFIGS (A, B, C1, C2).

Integrates:
- Solar thermal collector (Hottel-Whillier-Bliss model)
- Heat pump thermodynamics (CoolProp)
- Multi-tray drying chamber (10 trays in series)
- Phase-2 Midilli kinetics

Configurations:
- Config A:  HP-only (24/7 baseline)
- Config B:  Solar + HP series (solar preheats air, HP boosts to T_set)
- Config C1: Solar cascade, mix BEFORE solar ([r×Exh+(1-r)×Amb] → Solar → Evap → Cond)
- Config C2: Solar cascade, mix AFTER solar  (Amb → Solar → [Mix+r×Exh] → Evap → Cond)

Key Features:
- Weather data interpolation from hourly to simulation timestep
- Proper time tracking matching real weather conditions
- Night operation fallback to HP-only for solar configs
- VPD condenser-direct bypass strategy (all configs with r > 0)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd

from rq1.config_solar_hp import DryerConfiguration, SimulationConfig
from rq1.heatpump import HeatPumpConfig, size_heat_pump_for_air_heating, compute_heat_pump_cycle, compute_hp_COP
from rq1.solar import SolarCollectorConfig, compute_solar_collector
from rq1.kinetics import compute_dm_w_kinetic_first_order, compute_dm_w_air_capacity, gab_equilibrium_moisture
from rq1.psychro import (
    RH_from_T_omega,
    humidity_ratio_from_T_RH,
    moist_air_enthalpy_kJ_per_kg,
    temperature_from_h_omega_C,
    dewpoint_from_omega_C,
    p_sat_water_Pa,
)


@dataclass
class SolarHPDryerResult:
    """Results from solar-HP dryer simulation."""
    times_s: pd.Series
    df: pd.DataFrame
    config_type: str
    converged: bool
    final_message: str


# ==============================================================================
# WEATHER DATA HANDLING
# ==============================================================================

def load_weather_data_raw(cfg: SimulationConfig) -> pd.DataFrame:
    """Load raw hourly weather data from PVGIS CSV format."""
    df = pd.read_csv(cfg.ambient.csv_path)
    
    required = ["time_index", "T_amb_C", "RH_amb_pct", "GHI_Wm2"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Weather CSV missing columns: {missing}")
    
    start = cfg.ambient.start_index
    end = None if cfg.ambient.max_steps is None else start + cfg.ambient.max_steps
    df_subset = df.iloc[start:end].copy().reset_index(drop=True)
    
    if "pressure_Pa" not in df_subset.columns:
        df_subset["pressure_Pa"] = 101325.0
    if "wind_speed_ms" not in df_subset.columns:
        df_subset["wind_speed_ms"] = 1.0
    
    return df_subset


def interpolate_weather_to_timestep(
    weather_hourly: pd.DataFrame,
    dt_s: float,
    max_simulation_time_s: float,
) -> pd.DataFrame:
    """Interpolate hourly weather data to simulation timestep resolution.
    
    PVGIS data is hourly (time_index 0, 1, 2, ... represents hours 0, 1, 2, ...)
    This function creates data at t = 0, dt_s, 2*dt_s, ... seconds
    """
    # Convert hourly time_index to seconds
    t_hourly_s = weather_hourly['time_index'].values.astype(float) * 3600.0
    
    # Maximum time available in weather data
    t_max_weather_s = t_hourly_s[-1]
    
    # Limit simulation time to available weather
    actual_max_time_s = min(max_simulation_time_s, t_max_weather_s)
    
    # Create fine time grid at dt_s resolution
    n_steps = int(actual_max_time_s / dt_s) + 1
    t_fine_s = np.arange(n_steps) * dt_s
    
    # Interpolate each weather variable
    df_interp = pd.DataFrame({
        'time_s': t_fine_s,
        'T_amb_C': np.interp(t_fine_s, t_hourly_s, weather_hourly['T_amb_C'].values),
        'RH_amb_pct': np.interp(t_fine_s, t_hourly_s, weather_hourly['RH_amb_pct'].values),
        'GHI_Wm2': np.interp(t_fine_s, t_hourly_s, weather_hourly['GHI_Wm2'].values),
    })
    
    # Clip to valid ranges
    df_interp['RH_amb_pct'] = df_interp['RH_amb_pct'].clip(0, 100)
    df_interp['GHI_Wm2'] = df_interp['GHI_Wm2'].clip(lower=0)
    
    return df_interp


def prepare_weather_for_simulation(
    cfg: SimulationConfig,
    max_time_override_s: Optional[float] = None,
) -> pd.DataFrame:
    """Load and interpolate weather data for simulation."""
    weather_hourly = load_weather_data_raw(cfg)
    
    max_sim_time = max_time_override_s if max_time_override_s else cfg.max_simulation_time_s
    dt_s = cfg.dryer.dt_s
    
    weather_interp = interpolate_weather_to_timestep(weather_hourly, dt_s, max_sim_time)
    
    print(f"[WEATHER] Loaded {len(weather_hourly)} hourly data points")
    print(f"[WEATHER] Interpolated to {len(weather_interp)} points at dt={dt_s}s")
    print(f"[WEATHER] Simulation time range: 0 to {weather_interp['time_s'].iloc[-1]/3600:.1f} hours")
    
    return weather_interp


# ==============================================================================
# DRYING CHAMBER SIMULATION
# ==============================================================================

def simulate_drying_chamber(
    T_to_chamber_C: float,
    omega_to_chamber: float,
    h_to_chamber: float,
    X_trays: List[List[float]],
    MR_trays: List[List[float]],
    cfg: SimulationConfig,
    time_s: float,
    m_da: float,
    dt_s: float,
    reverse_flow: bool = False,
) -> Tuple[List[float], List[float], List[float], List[float], List[List[float]], List[List[float]]]:
    """Simulate multi-tray drying chamber with series airflow and per-section discretization.

    Parameters
    ----------
    X_trays, MR_trays : List[List[float]]
        Shape (n_trays, n_sections).
    reverse_flow : bool
        If True, air visits trays in reverse order (last→first).
        Results are always indexed by physical tray position.

    Returns
    -------
    dm_w_trays : List[float]          — total water removed per tray
    T_tray_out : List[float]          — air T after last section of each tray
    RH_tray_out : List[float]         — air RH after last section of each tray
    h_tray_out : List[float]          — air enthalpy after last section of each tray
    X_trays_new : List[List[float]]   — updated moisture per section
    MR_trays_new : List[List[float]]  — updated MR per section
    """
    n_trays = cfg.dryer.n_trays
    m_p_tray = cfg.dryer.m_p_dry_kg / n_trays
    h_fg = cfg.dryer.h_fg_kJ_per_kg
    p_atm = cfg.ambient.default_pressure_Pa

    T_air = T_to_chamber_C
    omega_air = omega_to_chamber
    h_air = h_to_chamber
    RH_air = float(RH_from_T_omega(T_air, omega_air, p_atm))

    tray_order = list(range(n_trays - 1, -1, -1)) if reverse_flow else list(range(n_trays))

    # Pre-allocate (results indexed by physical tray position)
    dm_w_trays = [0.0] * n_trays
    T_tray_out = [0.0] * n_trays
    RH_tray_out = [0.0] * n_trays
    h_tray_out = [0.0] * n_trays
    X_trays_new: List[Optional[List[float]]] = [None] * n_trays
    MR_trays_new: List[Optional[List[float]]] = [None] * n_trays

    for i in tray_order:
        n_sec = len(X_trays[i])
        m_p_section = m_p_tray / n_sec
        X_sec_new = []
        MR_sec_new = []
        dm_w_tray_total = 0.0

        for j in range(n_sec):
            X_j = X_trays[i][j]

            # Dynamic equilibrium moisture from GAB isotherm
            X_eq_local = gab_equilibrium_moisture(T_air, RH_air)

            dm_w_kin = compute_dm_w_kinetic_first_order(
                X_db=X_j, X_eq_db=X_eq_local, T_in_C=T_air, RH_in_frac=RH_air,
                dt_s=dt_s, cfg=cfg.kinetics, m_p_dry_kg=m_p_section, time_s=time_s,
            )

            if cfg.kinetics.enable_air_limit:
                dm_w_air_max = compute_dm_w_air_capacity(
                    T_in_C=T_air, omega_in=omega_air, m_da_kg_per_s=m_da,
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

            # Update air state for next section / next tray
            m_w_rate = dm_w / dt_s if dt_s > 0 else 0.0
            d_omega = m_w_rate / m_da if m_da > 0 else 0.0
            omega_out = omega_air + d_omega

            # Near-constant-enthalpy humidification (ASHRAE)
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


# ==============================================================================
# COMMON SETUP
# ==============================================================================

def setup_simulation(cfg: SimulationConfig) -> Tuple[float, float, List[List[float]], List[List[float]]]:
    """Initialize simulation parameters.

    Returns
    -------
    m_da : float
    dt_s : float
    X_trays : List[List[float]]   — shape (n_trays, n_sections)
    MR_trays : List[List[float]]  — shape (n_trays, n_sections)
    """
    dt_s = cfg.dryer.dt_s
    n_trays = cfg.dryer.n_trays
    n_sec = cfg.dryer.n_sections
    m_p_dry_total = cfg.dryer.m_p_dry_kg
    m_p_tray = m_p_dry_total / n_trays

    if cfg.dryer.loading_density_kg_m2 <= 0:
        cfg.dryer.loading_density_kg_m2 = (
            cfg.dryer.product_apparent_density_kg_per_m3 * cfg.dryer.product_thickness_m
        )

    if cfg.dryer.tray_area_m2 is None:
        m_fresh_tray = m_p_tray * (1 + cfg.dryer.X0_db)
        tray_area = m_fresh_tray / cfg.dryer.loading_density_kg_m2
        cfg.dryer.tray_area_m2 = tray_area
        tray_side = tray_area ** 0.5
        cfg.dryer.tray_length_m = tray_side
        cfg.dryer.tray_width_m = tray_side

    if cfg.dryer.m_da_kg_per_s <= 0:
        A_cross = cfg.dryer.tray_width_m * cfg.dryer.air_gap_m
        m_da = cfg.dryer.air_density_kg_per_m3 * A_cross * cfg.dryer.target_velocity_m_s
        cfg.dryer.m_da_kg_per_s = m_da
    else:
        m_da = cfg.dryer.m_da_kg_per_s

    X_trays = [[cfg.dryer.X0_db] * n_sec for _ in range(n_trays)]
    MR_trays = [[1.0] * n_sec for _ in range(n_trays)]

    return m_da, dt_s, X_trays, MR_trays


def compute_fan_power_kW(cfg: SimulationConfig) -> float:
    """Compute fan electrical power [kW] from pressure drop model."""
    return cfg.compute_pressure_drop_and_fan_power()["W_fan_kW"]


def create_record(
    time_s, T_amb_C, RH_amb_pct, G_solar, Q_solar_kW, T_solar_out_C, eta_solar,
    hp_result, T_to_chamber_C, omega_to_chamber,
    T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
    m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
    W_fan_kW: float = 0.0,
    W_fan_cum_kWh: float = 0.0,
    W_elec_kW: float = 0.0,
    W_elec_cum_kWh: float = 0.0,
    bypass_mode: str = "none",
    flow_direction: str = "forward",
) -> dict:
    """Create a record dictionary for results DataFrame.

    Parameters
    ----------
    X_trays, MR_trays : List[List[float]]
        Shape (n_trays, n_sections).
    bypass_mode : str
        "evap", "bypass", or "none"
    flow_direction : str
        "forward" or "reverse"
    """
    n_trays = cfg.dryer.n_trays
    n_sec = cfg.dryer.n_sections

    # Exhaust = last tray visited by air
    exhaust_idx = 0 if flow_direction == "reverse" else (n_trays - 1)

    # Average across ALL sections for global X_avg
    all_X = [x for tray in X_trays for x in tray]
    X_avg = sum(all_X) / len(all_X)

    # Use GAB X_eq at inlet conditions for global MR reporting
    p_atm = cfg.ambient.default_pressure_Pa
    RH_in = float(RH_from_T_omega(T_to_chamber_C, omega_to_chamber, p_atm))
    X_eq_report = gab_equilibrium_moisture(T_to_chamber_C, RH_in)
    MR_global = (X_avg - X_eq_report) / (cfg.dryer.X0_db - X_eq_report) if cfg.dryer.X0_db != X_eq_report else 0.0

    if hp_result is not None:
        W_comp_kW = hp_result.W_comp_kW
        Q_evap_kW = hp_result.Q_evap_kW
        Q_cond_kW = hp_result.Q_cond_kW
        COP = hp_result.COP
        T_evap_C = hp_result.T_evap_C
        T_cond_C = hp_result.T_cond_C
        P_evap_bar = hp_result.P_evap_Pa / 1e5
        P_cond_bar = hp_result.P_cond_Pa / 1e5
        m_ref = hp_result.m_ref_kg_per_s
    else:
        W_comp_kW = Q_evap_kW = Q_cond_kW = COP = 0.0
        T_evap_C = 0.0
        T_cond_C = T_to_chamber_C
        P_evap_bar = P_cond_bar = m_ref = 0.0

    record = {
        "time_s": time_s, "time_h": time_s / 3600.0,
        "T_amb_C": T_amb_C, "RH_amb_pct": RH_amb_pct, "G_solar_Wm2": G_solar,
        "Q_solar_kW": Q_solar_kW, "T_solar_out_C": T_solar_out_C, "eta_solar": eta_solar,
        "T_evap_C": T_evap_C, "T_cond_C": T_cond_C,
        "P_evap_bar": P_evap_bar, "P_cond_bar": P_cond_bar,
        "W_comp_kW": W_comp_kW, "Q_evap_kW": Q_evap_kW, "Q_cond_kW": Q_cond_kW,
        "COP": COP, "m_ref_kg_per_s": m_ref,
        "T_to_chamber_C": T_to_chamber_C,
        "RH_to_chamber_frac": float(RH_from_T_omega(T_to_chamber_C, omega_to_chamber, p_atm)),
        "omega_to_chamber": omega_to_chamber,
        "T_exhaust_C": T_tray_out[exhaust_idx], "RH_exhaust_frac": RH_tray_out[exhaust_idx],
        "X_db_avg": X_avg, "MR_global": MR_global,
        "dm_w_total_kg": sum(dm_w_trays), "m_w_cum_kg": m_w_cum,
        "W_comp_cum_kWh": W_comp_cum_kWh, "Q_cond_cum_kWh": Q_cond_cum_kWh,
        "Q_solar_cum_kWh": Q_solar_cum_kWh,
        "W_fan_kW": W_fan_kW,
        "W_fan_cum_kWh": W_fan_cum_kWh,
        "W_elec_kW": W_elec_kW,
        "W_elec_cum_kWh": W_elec_cum_kWh,
        "bypass_mode": bypass_mode,
        "flow_direction": flow_direction,
    }

    # Per-tray averages (backward compatible)
    for i in range(n_trays):
        record[f"X_tray_{i}"] = sum(X_trays[i]) / len(X_trays[i])
        record[f"MR_tray_{i}"] = sum(MR_trays[i]) / len(MR_trays[i])
        record[f"T_tray_{i}_out_C"] = T_tray_out[i]
        record[f"RH_tray_{i}_out_frac"] = RH_tray_out[i]
        record[f"dm_w_tray_{i}_kg"] = dm_w_trays[i]

    # Per-section columns (only when n_sections > 1)
    if n_sec > 1:
        for i in range(n_trays):
            for j in range(n_sec):
                record[f"X_tray_{i}_sec_{j}"] = X_trays[i][j]
                record[f"MR_tray_{i}_sec_{j}"] = MR_trays[i][j]

    return record


# ==============================================================================
# MAIN DISPATCHER
# ==============================================================================

def run_solar_hp_dryer_simulation(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Main entry point - dispatches to configuration-specific simulator."""
    if cfg.config_type == DryerConfiguration.CONFIG_0:
        return simulate_config_0_electric(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_A:
        return simulate_config_A_HP_only(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_B:
        return simulate_config_B_solar_HP_series(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_C1:
        return simulate_config_C1_mix_before_solar(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_C2:
        return simulate_config_C2_mix_after_solar(cfg)
    elif cfg.config_type in (DryerConfiguration.CONFIG_D1,
                             DryerConfiguration.CONFIG_D2,
                             DryerConfiguration.CONFIG_D3):
        return simulate_config_D_HRX(cfg)
    elif cfg.config_type in (DryerConfiguration.CONFIG_E1,
                             DryerConfiguration.CONFIG_E2,
                             DryerConfiguration.CONFIG_E3):
        return simulate_config_E_HRX_solar(cfg)
    else:
        raise ValueError(f"Unknown configuration: {cfg.config_type}")


# ==============================================================================
# ADAPTIVE RECIRCULATION RATIO
# ==============================================================================

def compute_optimal_recirc_ratio(
    omega_exhaust: float,
    omega_amb: float,
    r_max: float,
    T_evap_min_C: float = 2.0,
    T_evap_max_C: float = 20.0,
    p_atm_Pa: float = 101325.0,
) -> tuple:
    """Find r in [0, r_max] maximizing COP.

    With fixed T_evap_target, higher r means more Q_evap (higher T_mix).
    The T_evap_sat is fixed and independent of r, so the only constraint
    is the hard stop (T_evap_sat >= T_cond), which never triggers with
    fixed T_evap=5 C and T_cond~55 C.  The omega_exhaust <= omega_amb
    bypass case is handled in the main simulation loop.

    Returns
    -------
    (r_optimal, mode)
        mode: 'recirc_max' — always returns r_max
    """
    return r_max, "recirc_max"


# ==============================================================================
# CONDENSER-PENALTY ESTIMATOR (VPD-based bypass criterion)
# ==============================================================================

def compute_cond_penalty_est(
    omega_exhaust: float,
    omega_amb: float,
    r: float,
    T_set_C: float,
    epsilon_evap: float,
    T_evap_target_C: float = 5.0,
    p_atm_Pa: float = 101325.0,
) -> float:
    """Estimate condenser penalty fraction without running the evaporator.

    cond_penalty = (VPD_post_evap - VPD_exhaust_at_Tset) / VPD_post_evap

    When this is small (<5%), the evaporator barely improves drying potential
    and condenser-direct mode saves compressor energy.

    Returns
    -------
    float
        cond_penalty_frac in [0, 1].  0 = evap adds nothing; 1 = exhaust is saturated.
    """
    # Mixed air humidity at the evaporator inlet
    omega_mix = r * omega_exhaust + (1.0 - r) * omega_amb

    # Fixed evap coil temperature from design T_evap + approach
    T_evap_coil = T_evap_target_C + 3.0

    # Saturated humidity ratio at evap coil surface
    omega_sat_coil = humidity_ratio_from_T_RH(T_evap_coil, 1.0, p_atm_Pa)

    # Estimate post-evap omega (effectiveness model)
    omega_after_evap = omega_mix - epsilon_evap * max(0.0, omega_mix - omega_sat_coil)

    # VPD at T_set for both streams (fair comparison at chamber temperature)
    P_sat_Tset = p_sat_water_Pa(T_set_C)
    p_v_post_evap = omega_after_evap * p_atm_Pa / (0.622 + omega_after_evap)
    p_v_exhaust   = omega_exhaust   * p_atm_Pa / (0.622 + omega_exhaust)

    VPD_post_evap = max(0.0, P_sat_Tset - p_v_post_evap)
    VPD_exhaust   = max(0.0, P_sat_Tset - p_v_exhaust)

    if VPD_post_evap < 1e-3:
        return 1.0   # both saturated; no benefit from evap either

    return max(0.0, min(1.0, (VPD_post_evap - VPD_exhaust) / VPD_post_evap))


def compute_humidity_dwell_s(
    omega_exhaust: float,
    omega_amb: float,
    r: float,
    T_set_C: float,
    epsilon_evap: float,
    cond_penalty_now: float,
    target_penalty: float,
    dm_w_total_prev: float,
    m_da: float,
    dt_s: float,
    T_evap_target_C: float = 5.0,
    p_atm_Pa: float = 101325.0,
    tau_min_s: float = 300.0,
    tau_max_s: float = 7200.0,
) -> float:
    """Compute physics-based minimum dwell time from humidity accumulation rate.

    Estimates how long it takes for the exhaust humidity to change enough
    to cross the target cond_penalty threshold, given the current drying rate.

    τ = Δ(cond_penalty) / |d(cond_penalty)/dt|

    where d(cond_penalty)/dt is estimated from the finite-difference sensitivity
    d(cond_penalty)/d(omega_exhaust) × d(omega_exhaust)/dt.

    Parameters
    ----------
    cond_penalty_now : current cond_penalty_frac value
    target_penalty : the threshold to cross (thresh for evap→cond, 3×thresh for cond→evap)
    dm_w_total_prev : total water removed by chamber in previous timestep [kg]
    m_da : dry air mass flow rate [kg/s]
    dt_s : timestep [s]
    tau_min_s : absolute minimum dwell time (compressor protection) [s]
    tau_max_s : absolute maximum dwell time (prevent lock-in) [s]

    Returns
    -------
    float : dwell time in seconds, clamped to [tau_min_s, tau_max_s]
    """
    # Rate of omega change: d(omega)/dt = dm_w / (m_da × dt_s) [per second]
    if m_da <= 0 or dt_s <= 0 or dm_w_total_prev <= 0:
        return tau_max_s

    d_omega_dt = dm_w_total_prev / (m_da * dt_s)  # kg_water/kg_da per second

    # Sensitivity: d(cond_penalty)/d(omega_exhaust) via finite difference
    d_omega = max(1e-5, omega_exhaust * 0.01)  # 1% perturbation
    cp_plus = compute_cond_penalty_est(
        omega_exhaust + d_omega, omega_amb, r, T_set_C,
        epsilon_evap, T_evap_target_C, p_atm_Pa,
    )
    cp_minus = compute_cond_penalty_est(
        max(1e-6, omega_exhaust - d_omega), omega_amb, r, T_set_C,
        epsilon_evap, T_evap_target_C, p_atm_Pa,
    )
    d_cp_d_omega = (cp_plus - cp_minus) / (2.0 * d_omega)

    # Rate of penalty change
    d_cp_dt = abs(d_cp_d_omega * d_omega_dt)

    if d_cp_dt < 1e-10:
        return tau_max_s

    # Time to cross the threshold
    delta_penalty = abs(target_penalty - cond_penalty_now)
    tau = delta_penalty / d_cp_dt

    return max(tau_min_s, min(tau_max_s, tau))


def compute_vpd_utilization(
    omega_exhaust: float,
    omega_amb: float,
    T_set_C: float,
    p_atm_Pa: float = 101325.0,
) -> float:
    """Fraction of inlet VPD consumed by drying (0 = air unused, 1 = fully saturated).

    VPD_in  = P_sat(T_set) - p_v(omega_amb)     (fresh air at T_set)
    VPD_exh = P_sat(T_set) - p_v(omega_exhaust)  (exhaust at T_set)
    utilization = (VPD_in - VPD_exh) / VPD_in = 1 - VPD_exh/VPD_in

    High utilization → air is picking up lots of moisture (early drying).
    Low utilization  → air passes through nearly unchanged (late drying).
    """
    P_sat_Tset = p_sat_water_Pa(T_set_C)
    p_v_amb = omega_amb * p_atm_Pa / (0.622 + omega_amb)
    p_v_exh = omega_exhaust * p_atm_Pa / (0.622 + omega_exhaust)

    VPD_in  = max(0.0, P_sat_Tset - p_v_amb)
    VPD_exh = max(0.0, P_sat_Tset - p_v_exh)

    if VPD_in < 1e-3:
        return 1.0  # ambient is saturated at T_set — can't dry

    return max(0.0, min(1.0, 1.0 - VPD_exh / VPD_in))


# ==============================================================================
# EVAPORATOR DEHUMIDIFICATION MODEL
# ==============================================================================

def _evaporator_dehumidify(
    T_air_in_C: float,
    omega_in: float,
    T_evap_coil_C: float,
    epsilon_evap: float,
    p_atm_Pa: float = 101325.0,
) -> tuple[float, float, float]:
    """Model air-side evaporator: sensible cooling + dehumidification.

    Parameters
    ----------
    T_air_in_C : float
        Mixed air temperature entering evaporator [°C]
    omega_in : float
        Humidity ratio of incoming air [kg/kg_da]
    T_evap_coil_C : float
        Evaporator coil surface temperature [°C]
    epsilon_evap : float
        Evaporator heat exchanger effectiveness [0..1]

    Returns
    -------
    (T_out_C, omega_out, h_out_kJ_per_kg)
    """
    # Guard: if air is already at or below coil temperature, no cooling occurs
    if T_air_in_C <= T_evap_coil_C:
        h_out = float(moist_air_enthalpy_kJ_per_kg(T_air_in_C, omega_in))
        return T_air_in_C, omega_in, h_out

    # Sensible cooling via effectiveness
    T_out = T_air_in_C - epsilon_evap * (T_air_in_C - T_evap_coil_C)

    # Dewpoint of incoming air
    T_dp = dewpoint_from_omega_C(omega_in, p_total_Pa=p_atm_Pa)

    if T_out < T_dp:
        # Air cooled below its dewpoint → exits saturated at T_out
        omega_out = humidity_ratio_from_T_RH(T_out, 1.0, p_atm_Pa)
        omega_out = min(omega_out, omega_in)  # Can only remove moisture
    else:
        # No condensation
        omega_out = omega_in

    h_out = float(moist_air_enthalpy_kJ_per_kg(T_out, omega_out))
    return T_out, omega_out, h_out


# ==============================================================================
# CONFIG A: HP ONLY (closed-loop HPCD with tuneable recirculation)
# ==============================================================================

def simulate_config_A_HP_only(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config A: HP-only open-loop baseline.

    Air path: Ambient -> Condenser -> Chamber -> Exhaust (vented).
    Evaporator runs on ambient as the cycle heat source (parallel branch).
    No recirculation, no solar, no HRX. Canonical "Mode A" baseline in fruit
    and vegetable HP-drying literature (Sun et al. 2025; Mujumdar and Chou 2021).

    Recirculation (r > 0) was removed 2026-05-13: the single-stream design
    creates a cold-attractor bistability without an active humidity lever, so
    fixed-r operation does not represent a real machine. Recirculation is
    addressed in Configs D and E via HRX.
    """
    if cfg.dryer.r_recirc != 0.0:
        raise ValueError(
            f"Config A is open-loop only. Got r_recirc={cfg.dryer.r_recirc}. "
            f"For recirculation, use Config D or E (HRX-based)."
        )

    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa

    m_w_cum = W_comp_cum_kWh = Q_cond_cum_kWh = Q_solar_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    print(f"[CONFIG A] open-loop HP, {n_trays} trays, m_da={m_da:.4f} kg/s, "
          f"P_atm={p_atm/1000:.1f}kPa, rho={cfg.dryer.air_density_kg_per_m3:.3f}kg/m³")

    hp_cfg = HeatPumpConfig(
        refrigerant=cfg.heatpump.refrigerant,
        eta_isentropic=cfg.heatpump.eta_isentropic,
        eta_mechanical=cfg.heatpump.eta_mechanical,
        superheat_K=cfg.heatpump.superheat_K,
        subcooling_K=cfg.heatpump.subcooling_K,
        epsilon_evap=cfg.heatpump.epsilon_evap,
        epsilon_cond=cfg.heatpump.epsilon_cond,
        T_evap_min_C=cfg.heatpump.T_evap_min_C,
        T_evap_max_C=cfg.heatpump.T_evap_max_C,
        T_cond_min_C=cfg.heatpump.T_cond_min_C,
        T_cond_max_C=cfg.heatpump.T_cond_max_C,
        COP_min=cfg.heatpump.COP_min,
        pressure_ratio_max=cfg.heatpump.pressure_ratio_max,
        Q_cond_max_kW=cfg.heatpump.Q_cond_max_kW,
        Q_evap_max_kW=cfg.heatpump.Q_evap_max_kW,
        DT_evap_approach=cfg.heatpump.DT_evap_approach,
    )

    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))

        T_air_in_cond = T_amb_C
        omega_to_chamber = omega_amb
        T_evap_source = T_amb_C

        hp_result = size_heat_pump_for_air_heating(
            T_air_in_C=T_air_in_cond,
            T_air_out_target_C=cfg.dryer.T_set_C,
            m_air_kg_per_s=m_da,
            T_evap_source_C=T_evap_source,
            cfg=hp_cfg,
            omega_in=omega_to_chamber,
        )
        _T_cond_sat_ol = cfg.dryer.T_set_C + 10.0
        T_to_chamber_C = T_air_in_cond + hp_cfg.epsilon_cond * (_T_cond_sat_ol - T_air_in_cond)
        T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        reverse_flow = (int(time_s / reversal_s) % 2 == 1) if reversal_s > 0 else False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = (
            simulate_drying_chamber(
                T_to_chamber_C, omega_to_chamber, h_to_chamber,
                X_trays, MR_trays, cfg, time_s, m_da, dt_s,
                reverse_flow=reverse_flow,
            )
        )

        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exhaust_prev = T_tray_out[exhaust_idx]
        omega_exhaust_prev = float(humidity_ratio_from_T_RH(
            T_exhaust_prev, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))

        m_w_cum += sum(dm_w_trays)
        W_comp_cum_kWh += hp_result.W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += hp_result.Q_cond_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar, 0.0, T_amb_C, 0.0,
            hp_result, T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            bypass_mode="none",
            flow_direction=flow_direction,
        )
        record["T_dp_mix_C"]        = 0.0
        record["T_evap_coil_C_dyn"] = 0.0
        record["r_recirc_actual"]   = 0.0
        record["RH_exhaust_pct"]    = 0.0
        record["cond_penalty_frac"] = 0.0
        record["humidity_dwell_s"]  = 0.0
        record["T_mix_C"]        = T_amb_C
        record["omega_mix"]      = omega_amb
        record["T_after_evap_C"] = T_amb_C
        _T_evap_rec = hp_result.T_evap_C
        record["flag_frost_risk"]       = int(_T_evap_rec < 2.0)
        record["flag_outside_ac_range"] = int(_T_evap_rec < 2.0 or _T_evap_rec > 20.0)
        record["flag_impossible_cycle"] = 0
        record["flag_hp_at_capacity"]   = int(hp_result.flag_hp_at_capacity)
        record["flag_evap_oversized"]   = int(hp_result.flag_evap_oversized)
        record["flag_cond_oversized"]   = int(hp_result.flag_cond_oversized)
        _p_v_exh = omega_exhaust_prev * p_atm / (0.622 + omega_exhaust_prev)
        _p_v_amb = omega_amb * p_atm / (0.622 + omega_amb)
        record["VPD_exhaust_Pa"] = max(0.0, p_sat_water_Pa(T_exhaust_prev) - _p_v_exh)
        record["VPD_ambient_Pa"] = max(0.0, p_sat_water_Pa(T_amb_C) - _p_v_amb)
        record["T_to_chamber_deficit_C"] = cfg.dryer.T_set_C - T_to_chamber_C
        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_comp_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df, config_type="CONFIG_A",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG 0: Electric resistance baseline (no HP, no solar)
# ==============================================================================

def simulate_config_0_electric(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config 0: Electric resistance heater open-loop baseline.

    Air path: Ambient -> Electric heater (Q = m_da * cp * (T_set - T_amb))
              -> Chamber -> Exhaust (vented).

    Most basic reference point: what a simple thermostat-controlled resistance
    tray dryer would consume on the same product, weather and chamber as the
    HP configurations. SEC = (W_elec_cum + W_fan_cum) / m_w_cum.
    """
    if cfg.dryer.r_recirc != 0.0:
        raise ValueError(
            f"Config 0 is open-loop only. Got r_recirc={cfg.dryer.r_recirc}."
        )

    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa
    CP_AIR = 1.006  # kJ/(kg·K) dry-air approx; ω-correction is sub-1%

    W_elec_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    m_w_cum = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    print(f"[CONFIG 0] electric resistance, {n_trays} trays, m_da={m_da:.4f} kg/s, "
          f"P_atm={p_atm/1000:.1f}kPa, T_set={cfg.dryer.T_set_C}°C")

    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))

        T_to_chamber_C = cfg.dryer.T_set_C
        omega_to_chamber = omega_amb
        Q_heat_kW = max(0.0, m_da * CP_AIR * (T_to_chamber_C - T_amb_C))
        W_elec_kW = Q_heat_kW  # resistance heating, eta = 1

        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        reverse_flow = (int(time_s / reversal_s) % 2 == 1) if reversal_s > 0 else False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = (
            simulate_drying_chamber(
                T_to_chamber_C, omega_to_chamber, h_to_chamber,
                X_trays, MR_trays, cfg, time_s, m_da, dt_s,
                reverse_flow=reverse_flow,
            )
        )

        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exhaust_prev = T_tray_out[exhaust_idx]
        omega_exhaust_prev = float(humidity_ratio_from_T_RH(
            T_exhaust_prev, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))

        m_w_cum += sum(dm_w_trays)
        W_elec_cum_kWh += W_elec_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar, 0.0, T_amb_C, 0.0,
            None,  # hp_result = None (no HP)
            T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, 0.0, 0.0, 0.0, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            W_elec_kW=W_elec_kW, W_elec_cum_kWh=W_elec_cum_kWh,
            bypass_mode="electric",
            flow_direction=flow_direction,
        )
        # Electric-only: most HP/closed-loop fields are zero/placeholder
        record["Q_heat_kW"]         = Q_heat_kW
        record["T_dp_mix_C"]        = 0.0
        record["T_evap_coil_C_dyn"] = 0.0
        record["r_recirc_actual"]   = 0.0
        record["RH_exhaust_pct"]    = 0.0
        record["cond_penalty_frac"] = 0.0
        record["humidity_dwell_s"]  = 0.0
        record["T_mix_C"]        = T_amb_C
        record["omega_mix"]      = omega_amb
        record["T_after_evap_C"] = T_amb_C
        record["flag_frost_risk"]       = 0
        record["flag_outside_ac_range"] = 0
        record["flag_impossible_cycle"] = 0
        record["flag_hp_at_capacity"]   = 0
        record["flag_evap_oversized"]   = 0
        record["flag_cond_oversized"]   = 0
        _p_v_exh = omega_exhaust_prev * p_atm / (0.622 + omega_exhaust_prev)
        _p_v_amb = omega_amb * p_atm / (0.622 + omega_amb)
        record["VPD_exhaust_Pa"] = max(0.0, p_sat_water_Pa(T_exhaust_prev) - _p_v_exh)
        record["VPD_ambient_Pa"] = max(0.0, p_sat_water_Pa(T_amb_C) - _p_v_amb)
        record["T_to_chamber_deficit_C"] = 0.0
        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    # SEC for Config 0: electric resistance heat + fan, no compressor
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_elec_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df, config_type="CONFIG_0",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )


# ==============================================================================
# HRX HELPER (Config D)
# ==============================================================================

def _compute_HRX(
    T_exhaust_C: float,
    omega_exhaust: float,
    T_amb_C: float,
    omega_amb: float,
    eps_HRX: float,
    p_atm_Pa: float,
) -> tuple:
    """Compute heat recovery exchanger outlet conditions.

    Counter-flow plate HRX: sensible heat only through wall.
    Hot side = exhaust, cold side = ambient.

    Returns
    -------
    (T_amb_heated, T_exh_cooled, omega_amb_out, omega_exh_out, Q_HRX_kW, condensation)
    """
    T_amb_heated = T_amb_C + eps_HRX * (T_exhaust_C - T_amb_C)
    T_exh_cooled = T_exhaust_C - eps_HRX * (T_exhaust_C - T_amb_C)

    # Ambient side: no moisture change (sensible only, no condensation on cold side)
    omega_amb_out = omega_amb

    # Exhaust side: check if cooled below dewpoint -> condensation
    T_dp_exhaust = dewpoint_from_omega_C(omega_exhaust, p_atm_Pa)
    if T_exh_cooled < T_dp_exhaust:
        omega_exh_out = humidity_ratio_from_T_RH(T_exh_cooled, 1.0, p_atm_Pa)
        omega_exh_out = min(omega_exh_out, omega_exhaust)  # can only remove moisture
        condensation = True
    else:
        omega_exh_out = omega_exhaust
        condensation = False

    # Q_HRX from air-side enthalpy change (ambient stream)
    h_amb_in = float(moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_amb))
    h_amb_out = float(moist_air_enthalpy_kJ_per_kg(T_amb_heated, omega_amb_out))
    # Q_HRX needs mass flow but we don't know it here — caller multiplies by m_da
    # Return per-unit-mass enthalpy gain instead
    dh_HRX = h_amb_out - h_amb_in  # kJ/kg_da

    return T_amb_heated, T_exh_cooled, omega_amb_out, omega_exh_out, dh_HRX, condensation


# ==============================================================================
# CONFIG D: HRX + HP (r=0 only)
# ==============================================================================

def simulate_config_D_HRX(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config D: Heat Recovery Exchanger + HP, open-loop (r=0).

    Three variants (set via cfg.dryer.d_variant):
      D1: Amb -> [HRX cold] -> preheated -> Cond -> Chamber
          Exh -> [HRX hot]  -> cooled    -> Expelled
          Evap: separate ambient source (outdoor unit)

      D2: Amb -> [HRX cold] -> preheated -> Cond -> Chamber
          Exh -> [HRX hot]  -> cooled    -> mixed w/ ambient -> Evap -> Expelled
          Evap source: 50/50 mix of cooled exhaust + ambient (infinite reservoir)

      D3: Exh -> [HRX hot]  -> cooled    -> Cond -> Chamber
          Amb -> [HRX cold] -> preheated -> Evap -> Expelled
          Evap source: preheated ambient (warm source, high COP)
          WARNING: chamber gets exhaust air (humidity risk!)
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa

    d_variant = cfg.dryer.d_variant
    eps_HRX = cfg.dryer.eps_HRX

    m_w_cum = W_comp_cum_kWh = Q_cond_cum_kWh = Q_solar_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    Q_HRX_cum_kWh = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    # Previous-step exhaust state
    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    _tau_s = 300.0
    _alpha = dt_s / (_tau_s + dt_s)

    hp_cfg = HeatPumpConfig(
        refrigerant=cfg.heatpump.refrigerant,
        eta_isentropic=cfg.heatpump.eta_isentropic,
        eta_mechanical=cfg.heatpump.eta_mechanical,
        superheat_K=cfg.heatpump.superheat_K,
        subcooling_K=cfg.heatpump.subcooling_K,
        epsilon_evap=cfg.heatpump.epsilon_evap,
        epsilon_cond=cfg.heatpump.epsilon_cond,
        T_evap_min_C=cfg.heatpump.T_evap_min_C,
        T_evap_max_C=cfg.heatpump.T_evap_max_C,
        T_cond_min_C=cfg.heatpump.T_cond_min_C,
        T_cond_max_C=cfg.heatpump.T_cond_max_C,
        COP_min=cfg.heatpump.COP_min,
        pressure_ratio_max=cfg.heatpump.pressure_ratio_max,
        Q_cond_max_kW=cfg.heatpump.Q_cond_max_kW,
        Q_evap_max_kW=cfg.heatpump.Q_evap_max_kW,
        DT_evap_approach=cfg.heatpump.DT_evap_approach,
    )

    # VPD-based exhaust bypass state
    _vpd_thresh = cfg.dryer.vpd_bypass_thresh
    _vpd_bypass_active = False
    _vpd_utilization = 1.0
    _vpd_last_switch_s = -1e9
    _vpd_dwell_s = 600.0  # minimum dwell between mode switches [s]

    _vpd_mode_str = f", vpd_bypass={_vpd_thresh:.2f}" if _vpd_thresh > 0 else ""
    print(f"[CONFIG {d_variant}] HRX + HP, r=0 (open-loop), eps_HRX={eps_HRX:.2f}{_vpd_mode_str}, "
          f"{n_trays} trays, m_da={m_da:.4f} kg/s, "
          f"P_atm={p_atm/1000:.1f}kPa, rho={cfg.dryer.air_density_kg_per_m3:.3f}kg/m3")

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))

        bypass_mode = "none"

        # ----- 0. VPD BYPASS DECISION (D1/D2 only) -----
        if (_vpd_thresh > 0 and d_variant in ("D1", "D2")
                and T_exhaust_prev is not None and omega_exhaust_prev is not None):
            _vpd_utilization = compute_vpd_utilization(
                omega_exhaust_prev, omega_amb, cfg.dryer.T_set_C, p_atm,
            )
            _dwell_ok = (time_s - _vpd_last_switch_s) >= _vpd_dwell_s
            if _vpd_bypass_active:
                # Currently bypassing — switch back when utilization rises
                if _vpd_utilization > _vpd_thresh * 3.0 and _dwell_ok:
                    _vpd_bypass_active = False
                    _vpd_last_switch_s = time_s
            else:
                # Normal mode — switch to bypass when utilization drops
                if _vpd_utilization < _vpd_thresh and _dwell_ok:
                    _vpd_bypass_active = True
                    _vpd_last_switch_s = time_s

        # ----- 1. HRX COMPUTATION -----
        # Use previous exhaust state; at t=0 use a reasonable estimate
        if T_exhaust_prev is None:
            T_exh_est = cfg.dryer.T_set_C - 5.0
            omega_exh_est = omega_amb + 0.002
        else:
            T_exh_est = T_exhaust_prev
            omega_exh_est = omega_exhaust_prev

        T_amb_heated, T_exh_cooled, omega_amb_hrx, omega_exh_cooled, dh_HRX, hrx_condensation = (
            _compute_HRX(T_exh_est, omega_exh_est, T_amb_C, omega_amb, eps_HRX, p_atm)
        )
        Q_HRX_kW = m_da * dh_HRX

        # ----- 2. ROUTING PER D VARIANT (or bypass) -----
        if _vpd_bypass_active and T_exhaust_prev is not None:
            # EXHAUST BYPASS: warm exhaust → condenser directly (tiny Q_cond)
            T_air_in_cond = T_exhaust_prev
            omega_to_chamber = omega_exhaust_prev
            T_evap_source = T_amb_C
            bypass_mode = "exhaust_bypass"

        elif d_variant == "D1":
            T_air_in_cond = T_amb_heated
            omega_to_chamber = omega_amb_hrx
            T_evap_source = T_amb_C

        elif d_variant == "D2":
            T_air_in_cond = T_amb_heated
            omega_to_chamber = omega_amb_hrx
            T_evap_source = T_exh_cooled
            _cp_air = 1.006
            _T_evap_coil = T_exh_cooled - 10.0
            _Q_exh_avail = m_da * _cp_air * hp_cfg.epsilon_evap * max(0.0, T_exh_cooled - _T_evap_coil)
            _hp_trial = size_heat_pump_for_air_heating(
                T_air_in_C=T_air_in_cond,
                T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da,
                T_evap_source_C=T_exh_cooled,
                cfg=hp_cfg,
                omega_in=omega_to_chamber,
            )
            if _hp_trial.Q_evap_kW > _Q_exh_avail and T_amb_C > _T_evap_coil:
                _Q_deficit = _hp_trial.Q_evap_kW - _Q_exh_avail
                _m_amb_extra = _Q_deficit / (_cp_air * (T_amb_C - _T_evap_coil))
                T_evap_source = (
                    (m_da * T_exh_cooled + _m_amb_extra * T_amb_C)
                    / (m_da + _m_amb_extra)
                )

        elif d_variant == "D3":
            T_air_in_cond = T_exh_cooled
            omega_to_chamber = omega_exh_cooled
            T_evap_source = T_amb_heated

        # ----- 3. HP CONDENSER (open-loop: size_heat_pump_for_air_heating) -----
        hp_result = size_heat_pump_for_air_heating(
            T_air_in_C=T_air_in_cond,
            T_air_out_target_C=cfg.dryer.T_set_C,
            m_air_kg_per_s=m_da,
            T_evap_source_C=T_evap_source,
            cfg=hp_cfg,
            omega_in=omega_to_chamber,
        )

        # Apply condenser effectiveness
        _T_cond_sat_ol = cfg.dryer.T_set_C + 10.0
        T_to_chamber_C = T_air_in_cond + hp_cfg.epsilon_cond * (_T_cond_sat_ol - T_air_in_cond)
        T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        # ----- 4. DRYING CHAMBER -----
        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        if reversal_s > 0:
            reverse_flow = (int(time_s / reversal_s) % 2 == 1)
        else:
            reverse_flow = False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = (
            simulate_drying_chamber(
                T_to_chamber_C, omega_to_chamber, h_to_chamber,
                X_trays, MR_trays, cfg, time_s, m_da, dt_s,
                reverse_flow=reverse_flow,
            )
        )

        # ----- 5. SAVE exhaust for next step -----
        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exh_raw = T_tray_out[exhaust_idx]
        omega_exh_raw = float(humidity_ratio_from_T_RH(
            T_exh_raw, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))
        if T_exhaust_prev is not None:
            T_exhaust_prev = _alpha * T_exh_raw + (1.0 - _alpha) * T_exhaust_prev
            omega_exhaust_prev = _alpha * omega_exh_raw + (1.0 - _alpha) * omega_exhaust_prev
        else:
            T_exhaust_prev = T_exh_raw
            omega_exhaust_prev = omega_exh_raw

        # ----- 6. ACCUMULATE & RECORD -----
        m_w_cum += sum(dm_w_trays)
        W_comp_cum_kWh += hp_result.W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += hp_result.Q_cond_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0
        # Only count HRX heat when it's actually used (not during bypass)
        if not _vpd_bypass_active:
            Q_HRX_cum_kWh += max(0, Q_HRX_kW) * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar, 0.0, T_amb_C, 0.0,
            hp_result, T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            bypass_mode=bypass_mode,
            flow_direction=flow_direction,
        )
        # HRX-specific columns
        record["T_amb_heated_C"] = T_amb_heated
        record["T_exh_cooled_C"] = T_exh_cooled
        record["omega_exh_cooled"] = omega_exh_cooled
        record["Q_HRX_kW"] = Q_HRX_kW
        record["Q_HRX_cum_kWh"] = Q_HRX_cum_kWh
        record["HRX_condensation"] = int(hrx_condensation)
        record["T_to_chamber_deficit_C"] = cfg.dryer.T_set_C - T_to_chamber_C
        record["vpd_utilization"] = _vpd_utilization
        record["vpd_bypass_active"] = int(_vpd_bypass_active)
        # Flags
        record["flag_hp_at_capacity"] = int(hp_result is not None and hp_result.flag_hp_at_capacity)
        record["flag_evap_oversized"] = int(hp_result is not None and hp_result.flag_evap_oversized)
        record["flag_cond_oversized"] = int(hp_result is not None and hp_result.flag_cond_oversized)

        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_comp_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df,
        config_type=f"CONFIG_{d_variant}",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )



# ==============================================================================
# CONFIG E: HRX + SOLAR + HP (r=0 only)
# ==============================================================================


def _iterative_evap_sizing(
    T_exh_cooled: float,
    T_amb_C: float,
    m_da: float,
    T_air_in_cond: float,
    T_cond_target: float,
    hp_cfg: "HeatPumpConfig",
    omega_to_chamber: float,
    max_iter: int = 5,
    tol: float = 0.05,
) -> tuple[float, float]:
    """Iteratively solve for T_evap_source with dynamic ambient supplement.

    The evaporator coil temperature is always T_evap_source - 10 K (approach),
    so Q_avail = (m_da + m_amb) * cp * eps * 10.  When exhaust alone can't
    supply Q_evap, ambient air is mixed in.  Changing the mix changes
    T_evap_source → COP → Q_evap, creating a circular dependency resolved
    by iteration.

    Returns (T_evap_source, m_amb_extra).
    """
    _cp = 1.006
    _eps = hp_cfg.epsilon_evap
    _Q_per_kg = _cp * _eps * 10.0  # kW per (kg/s) of air through evaporator

    T_evap_source = T_exh_cooled
    m_amb_extra = 0.0

    for _ in range(max_iter):
        hp_trial = size_heat_pump_for_air_heating(
            T_air_in_C=T_air_in_cond,
            T_air_out_target_C=T_cond_target,
            m_air_kg_per_s=m_da,
            T_evap_source_C=T_evap_source,
            cfg=hp_cfg,
            omega_in=omega_to_chamber,
        )
        Q_evap_needed = hp_trial.Q_evap_kW
        Q_avail = (m_da + m_amb_extra) * _Q_per_kg

        if Q_evap_needed <= Q_avail:
            break  # sufficient

        # Need more air mass
        m_total_needed = Q_evap_needed / _Q_per_kg
        m_amb_extra = max(0.0, m_total_needed - m_da)

        if m_amb_extra < 1e-6:
            break

        T_new = (m_da * T_exh_cooled + m_amb_extra * T_amb_C) / (m_da + m_amb_extra)
        if abs(T_new - T_evap_source) < tol:
            T_evap_source = T_new
            break
        T_evap_source = T_new

    return T_evap_source, m_amb_extra


def simulate_config_E_HRX_solar(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config E: HRX + Solar + HP, open-loop (r=0).

    Three variants (set via cfg.dryer.d_variant):
      E1: Amb -> HRX -> Solar -> Cond -> Chamber
          Evap = ambient air (separate stream, like D1)
      E2: Amb -> HRX -> Solar -> Cond -> Chamber
          Evap = cooled exhaust (post-HRX) + ambient supplement
      E3: Amb -> HRX -> Cond (variable T_cond) -> Solar -> Chamber
          Evap = cooled exhaust (post-HRX) + ambient supplement
          Solar-priority: HP OFF when solar alone reaches T_set,
          otherwise HP provides partial lift, solar finishes.
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa

    e_variant = cfg.dryer.d_variant  # "E1" or "E2"
    eps_HRX = cfg.dryer.eps_HRX

    m_w_cum = W_comp_cum_kWh = Q_cond_cum_kWh = Q_solar_cum_kWh = 0.0
    Q_solar_usable_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    Q_HRX_cum_kWh = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    # Previous-step exhaust state
    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    _tau_s = 300.0
    _alpha = dt_s / (_tau_s + dt_s)

    # Solar collector config
    solar_cfg = SolarCollectorConfig(area_m2=cfg.solar.area_m2)
    T_absorber_prev: Optional[float] = None

    hp_cfg = HeatPumpConfig(
        refrigerant=cfg.heatpump.refrigerant,
        eta_isentropic=cfg.heatpump.eta_isentropic,
        eta_mechanical=cfg.heatpump.eta_mechanical,
        superheat_K=cfg.heatpump.superheat_K,
        subcooling_K=cfg.heatpump.subcooling_K,
        epsilon_evap=cfg.heatpump.epsilon_evap,
        epsilon_cond=cfg.heatpump.epsilon_cond,
        T_evap_min_C=cfg.heatpump.T_evap_min_C,
        T_evap_max_C=cfg.heatpump.T_evap_max_C,
        T_cond_min_C=cfg.heatpump.T_cond_min_C,
        T_cond_max_C=cfg.heatpump.T_cond_max_C,
        COP_min=cfg.heatpump.COP_min,
        pressure_ratio_max=cfg.heatpump.pressure_ratio_max,
        Q_cond_max_kW=cfg.heatpump.Q_cond_max_kW,
        Q_evap_max_kW=cfg.heatpump.Q_evap_max_kW,
        DT_evap_approach=cfg.heatpump.DT_evap_approach,
    )

    # VPD-based exhaust bypass state
    _vpd_thresh = cfg.dryer.vpd_bypass_thresh
    _vpd_bypass_active = False
    _vpd_utilization = 1.0
    _vpd_last_switch_s = -1e9
    _vpd_dwell_s = 600.0

    _vpd_mode_str = f", vpd_bypass={_vpd_thresh:.2f}" if _vpd_thresh > 0 else ""
    print(f"[CONFIG {e_variant}] HRX + Solar + HP, r=0, eps_HRX={eps_HRX:.2f}, "
          f"A_solar={cfg.solar.area_m2:.1f}m2{_vpd_mode_str}, "
          f"{n_trays} trays, m_da={m_da:.4f} kg/s, "
          f"P_atm={p_atm/1000:.1f}kPa, rho={cfg.dryer.air_density_kg_per_m3:.3f}kg/m3")

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))

        bypass_mode = "none"

        # ----- 0. VPD BYPASS DECISION (E1/E2/E3) -----
        if (_vpd_thresh > 0
                and T_exhaust_prev is not None and omega_exhaust_prev is not None):
            _vpd_utilization = compute_vpd_utilization(
                omega_exhaust_prev, omega_amb, cfg.dryer.T_set_C, p_atm,
            )
            _dwell_ok = (time_s - _vpd_last_switch_s) >= _vpd_dwell_s
            if _vpd_bypass_active:
                if _vpd_utilization > _vpd_thresh * 3.0 and _dwell_ok:
                    _vpd_bypass_active = False
                    _vpd_last_switch_s = time_s
            else:
                if _vpd_utilization < _vpd_thresh and _dwell_ok:
                    _vpd_bypass_active = True
                    _vpd_last_switch_s = time_s

        # ----- 1. HRX COMPUTATION -----
        if T_exhaust_prev is None:
            T_exh_est = cfg.dryer.T_set_C - 5.0
            omega_exh_est = omega_amb + 0.002
        else:
            T_exh_est = T_exhaust_prev
            omega_exh_est = omega_exhaust_prev

        T_amb_heated, T_exh_cooled, omega_amb_hrx, omega_exh_cooled, dh_HRX, hrx_condensation = (
            _compute_HRX(T_exh_est, omega_exh_est, T_amb_C, omega_amb, eps_HRX, p_atm)
        )
        Q_HRX_kW = m_da * dh_HRX

        # ----- 2. SOLAR COLLECTOR + ROUTING PER E VARIANT -----
        omega_to_chamber = omega_amb_hrx  # = omega_amb (no moisture change on cold side)

        # Audit trail variables (set in each code path below)
        _T_solar_in = T_amb_heated   # default; overridden per path
        _T_air_in_cond = T_amb_heated
        _T_cond_out = T_amb_heated
        _T_evap_source = T_amb_C
        _T_cond_target = cfg.dryer.T_set_C
        _hp_mode = "full"

        if (_vpd_bypass_active and T_exhaust_prev is not None
                and e_variant in ("E1", "E2")):
            # E1/E2 BYPASS: Exh → Solar → Cond → Chamber (HRX skipped, topology preserved)
            solar_state, T_absorber_prev = compute_solar_collector(
                T_in_C=T_exhaust_prev, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
                m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s,
                T_absorber_prev_C=T_absorber_prev,
            )
            T_after_solar = solar_state.T_out_C
            T_air_in_cond = min(T_after_solar, cfg.dryer.T_set_C)
            omega_to_chamber = omega_exhaust_prev
            T_evap_source = T_amb_C
            bypass_mode = "exhaust_bypass"
            # Audit trail
            _T_solar_in = T_exhaust_prev
            _T_air_in_cond = T_air_in_cond
            _T_evap_source = T_evap_source
            _T_cond_target = cfg.dryer.T_set_C
            # mode label: HP idles when solar from exhaust already saturates at T_set
            _hp_mode = "vpd_bypass_off" if T_after_solar >= cfg.dryer.T_set_C - 0.05 else "vpd_bypass_full"

        elif (_vpd_bypass_active and T_exhaust_prev is not None
                and e_variant == "E3"):
            # E3 BYPASS: Exh → Cond → Solar → Chamber (solar still AFTER cond,
            # because the collector is physically downstream of the condenser).
            # Apply E3 partial-lift control with T_in = T_exhaust_prev.
            omega_to_chamber = omega_exhaust_prev
            T_evap_source = T_amb_C
            bypass_mode = "exhaust_bypass"

            _cp_e3 = 1.006
            from math import exp as _exp
            _F_prime = 0.90
            _UA_e3 = solar_cfg.area_m2 * solar_cfg.U_loss_W_per_m2K / 1000.0
            _C_min_e3 = m_da * _cp_e3
            if _C_min_e3 > 0 and _UA_e3 > 0:
                _NTU_e3 = _UA_e3 * _F_prime / _C_min_e3
                _F_R_e3 = (_C_min_e3 / _UA_e3) * (1.0 - _exp(-_NTU_e3))
            else:
                _F_R_e3 = 0.0
            _alpha_e3 = (_F_R_e3 * solar_cfg.eta_optical * max(G_solar, 0)
                         * solar_cfg.area_m2 / (m_da * _cp_e3 * 1000))
            _beta_e3 = (_F_R_e3 * solar_cfg.U_loss_W_per_m2K
                        * solar_cfg.area_m2 / (m_da * _cp_e3 * 1000))
            _solar_dt_bypass = (_alpha_e3 - _beta_e3 * (T_exhaust_prev - T_amb_C)
                                if _beta_e3 < 1.0 else 0.0)

            if (T_exhaust_prev + _solar_dt_bypass) >= cfg.dryer.T_set_C and G_solar > 10:
                # HP OFF: exhaust + solar alone already reaches T_set
                solar_state, T_absorber_prev = compute_solar_collector(
                    T_in_C=T_exhaust_prev, T_amb_C=T_amb_C,
                    G_solar_W_per_m2=G_solar, m_air_kg_per_s=m_da,
                    cfg=solar_cfg, dt_s=dt_s,
                    T_absorber_prev_C=T_absorber_prev,
                )
                T_after_solar = solar_state.T_out_C
                hp_result = size_heat_pump_for_air_heating(
                    T_air_in_C=T_exhaust_prev,
                    T_air_out_target_C=T_exhaust_prev,
                    m_air_kg_per_s=m_da, T_evap_source_C=T_evap_source,
                    cfg=hp_cfg, omega_in=omega_to_chamber,
                )
                T_to_chamber_C = min(T_after_solar, cfg.dryer.T_set_C)
                _T_solar_in = T_exhaust_prev
                _T_air_in_cond = T_exhaust_prev
                _T_cond_out = T_exhaust_prev
                _T_evap_source = T_evap_source
                _T_cond_target = T_exhaust_prev
                _hp_mode = "vpd_bypass_off"
            else:
                # HP partial lift, solar finishes
                if G_solar > 10 and _beta_e3 < 1.0:
                    _T_cond_target = ((cfg.dryer.T_set_C - _alpha_e3
                                       - _beta_e3 * T_amb_C) / (1.0 - _beta_e3))
                    _T_cond_target = max(T_exhaust_prev,
                                         min(_T_cond_target, cfg.dryer.T_set_C))
                else:
                    _T_cond_target = cfg.dryer.T_set_C  # night: full HP

                hp_result = size_heat_pump_for_air_heating(
                    T_air_in_C=T_exhaust_prev,
                    T_air_out_target_C=_T_cond_target,
                    m_air_kg_per_s=m_da, T_evap_source_C=T_evap_source,
                    cfg=hp_cfg, omega_in=omega_to_chamber,
                )

                _T_cond_sat_e3 = _T_cond_target + 10.0
                T_cond_out = (T_exhaust_prev + hp_cfg.epsilon_cond
                              * (_T_cond_sat_e3 - T_exhaust_prev))
                T_cond_out = min(T_cond_out, _T_cond_target)

                solar_state, T_absorber_prev = compute_solar_collector(
                    T_in_C=T_cond_out, T_amb_C=T_amb_C,
                    G_solar_W_per_m2=G_solar, m_air_kg_per_s=m_da,
                    cfg=solar_cfg, dt_s=dt_s,
                    T_absorber_prev_C=T_absorber_prev,
                )
                T_after_solar = solar_state.T_out_C
                T_to_chamber_C = min(T_after_solar, cfg.dryer.T_set_C)
                _T_solar_in = T_cond_out
                _T_air_in_cond = T_exhaust_prev
                _T_cond_out = T_cond_out
                _T_evap_source = T_evap_source
                _T_cond_target = _T_cond_target
                _hp_mode = ("vpd_bypass_partial"
                            if _T_cond_target < cfg.dryer.T_set_C
                            else "vpd_bypass_full")

            Q_solar_kW = solar_state.Q_useful_kW
            eta_solar = solar_state.eta_collector
            h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(
                T_to_chamber_C, omega_to_chamber))

        elif e_variant in ("E1", "E2"):
            # E1/E2: Solar between HRX and condenser (heats condenser inlet)
            solar_state, T_absorber_prev = compute_solar_collector(
                T_in_C=T_amb_heated, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
                m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s,
                T_absorber_prev_C=T_absorber_prev,
            )
            T_after_solar = solar_state.T_out_C
            T_air_in_cond = min(T_after_solar, cfg.dryer.T_set_C)

            if e_variant == "E1":
                # E1: ambient air at evaporator (like D1)
                T_evap_source = T_amb_C
            else:  # E2
                # E2: cooled exhaust + iterative ambient supplement
                T_evap_source, _m_amb_extra = _iterative_evap_sizing(
                    T_exh_cooled, T_amb_C, m_da,
                    T_air_in_cond, cfg.dryer.T_set_C,
                    hp_cfg, omega_to_chamber,
                )
            # Audit trail
            _T_solar_in = T_amb_heated
            _T_air_in_cond = T_air_in_cond
            _T_evap_source = T_evap_source
            _T_cond_target = cfg.dryer.T_set_C
            _hp_mode = "full"

        elif e_variant == "E3":
            # E3: Solar AFTER condenser (Amb → HRX → Cond → Solar → Chamber)
            # Evap: cooled exhaust first, dynamically add ambient if needed

            # Back-calculate HP contribution using Hottel-Whillier-Bliss:
            #   T_out = T_in + F_R*[eta*G*A - U_L*A*(T_in - T_amb)] / (m*cp)
            #   Want T_out = T_set, solve for T_in (= condenser outlet):
            #   T_in = (T_set - alpha - beta*T_amb) / (1 - beta)
            _cp_e3 = 1.006  # kJ/kg·K
            # Compute actual F_R from NTU-effectiveness (matches solar.py)
            from math import exp as _exp
            _F_prime = 0.90
            _UA_e3 = solar_cfg.area_m2 * solar_cfg.U_loss_W_per_m2K / 1000.0
            _C_min_e3 = m_da * _cp_e3
            if _C_min_e3 > 0 and _UA_e3 > 0:
                _NTU_e3 = _UA_e3 * _F_prime / _C_min_e3
                _F_R_e3 = (_C_min_e3 / _UA_e3) * (1.0 - _exp(-_NTU_e3))
            else:
                _F_R_e3 = 0.0
            _alpha_e3 = (_F_R_e3 * solar_cfg.eta_optical * max(G_solar, 0)
                         * solar_cfg.area_m2 / (m_da * _cp_e3 * 1000))
            _beta_e3 = (_F_R_e3 * solar_cfg.U_loss_W_per_m2K
                        * solar_cfg.area_m2 / (m_da * _cp_e3 * 1000))

            # Check bypass: can solar alone (from HRX output) reach T_set?
            _solar_dt_bypass = (_alpha_e3 - _beta_e3 * (T_amb_heated - T_amb_C)
                                if _beta_e3 < 1.0 else 0.0)

            if (T_amb_heated + _solar_dt_bypass) >= cfg.dryer.T_set_C and G_solar > 10:
                # --- HP OFF: solar alone from HRX output reaches T_set ---
                T_evap_source = T_exh_cooled  # doesn't matter (HP off)
                solar_state, T_absorber_prev = compute_solar_collector(
                    T_in_C=T_amb_heated, T_amb_C=T_amb_C,
                    G_solar_W_per_m2=G_solar, m_air_kg_per_s=m_da,
                    cfg=solar_cfg, dt_s=dt_s,
                    T_absorber_prev_C=T_absorber_prev,
                )
                T_after_solar = solar_state.T_out_C

                # Minimal HP call (no heating needed)
                hp_result = size_heat_pump_for_air_heating(
                    T_air_in_C=T_amb_heated,
                    T_air_out_target_C=T_amb_heated,
                    m_air_kg_per_s=m_da,
                    T_evap_source_C=T_evap_source,
                    cfg=hp_cfg, omega_in=omega_to_chamber,
                )
                T_to_chamber_C = min(T_after_solar, cfg.dryer.T_set_C)
                # Audit trail
                _T_solar_in = T_amb_heated
                _T_air_in_cond = T_amb_heated
                _T_cond_out = T_amb_heated  # condenser bypassed
                _T_evap_source = T_evap_source
                _T_cond_target = T_amb_heated
                _hp_mode = "off"

            else:
                # --- HP ON: partial lift, solar finishes ---
                if G_solar > 10 and _beta_e3 < 1.0:
                    _T_cond_target = ((cfg.dryer.T_set_C - _alpha_e3
                                       - _beta_e3 * T_amb_C) / (1.0 - _beta_e3))
                    _T_cond_target = max(T_amb_heated,
                                         min(_T_cond_target, cfg.dryer.T_set_C))
                else:
                    _T_cond_target = cfg.dryer.T_set_C  # night: full HP

                # Dynamic evaporator: exhaust + iterative ambient supplement
                T_evap_source, _m_amb_extra = _iterative_evap_sizing(
                    T_exh_cooled, T_amb_C, m_da,
                    T_amb_heated, _T_cond_target,
                    hp_cfg, omega_to_chamber,
                )

                # HP heats from T_HRX_out → _T_cond_target (variable, ≤ T_set)
                hp_result = size_heat_pump_for_air_heating(
                    T_air_in_C=T_amb_heated,
                    T_air_out_target_C=_T_cond_target,
                    m_air_kg_per_s=m_da,
                    T_evap_source_C=T_evap_source,
                    cfg=hp_cfg, omega_in=omega_to_chamber,
                )

                # Condenser effectiveness (variable T_cond_sat)
                _T_cond_sat_e3 = _T_cond_target + 10.0
                T_cond_out = (T_amb_heated + hp_cfg.epsilon_cond
                              * (_T_cond_sat_e3 - T_amb_heated))
                T_cond_out = min(T_cond_out, _T_cond_target)

                # Solar heats from condenser output → chamber
                solar_state, T_absorber_prev = compute_solar_collector(
                    T_in_C=T_cond_out, T_amb_C=T_amb_C,
                    G_solar_W_per_m2=G_solar, m_air_kg_per_s=m_da,
                    cfg=solar_cfg, dt_s=dt_s,
                    T_absorber_prev_C=T_absorber_prev,
                )
                T_after_solar = solar_state.T_out_C
                T_to_chamber_C = min(T_after_solar, cfg.dryer.T_set_C)
                # Audit trail
                _T_solar_in = T_cond_out
                _T_air_in_cond = T_amb_heated
                _T_cond_out = T_cond_out
                _T_evap_source = T_evap_source
                _T_cond_target = _T_cond_target
                _hp_mode = "partial" if _T_cond_target < cfg.dryer.T_set_C else "full"

            Q_solar_kW = solar_state.Q_useful_kW
            eta_solar = solar_state.eta_collector
            h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(
                T_to_chamber_C, omega_to_chamber))

        # --- Common HP + condenser for E1/E2 (incl. their bypass).
        # E3 (canonical and bypass) handles HP/cond inside its own branch above.
        if e_variant in ("E1", "E2"):
            Q_solar_kW = solar_state.Q_useful_kW
            eta_solar = solar_state.eta_collector

            hp_result = size_heat_pump_for_air_heating(
                T_air_in_C=T_air_in_cond,
                T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da,
                T_evap_source_C=T_evap_source,
                cfg=hp_cfg,
                omega_in=omega_to_chamber,
            )

            _T_cond_sat_ol = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            T_to_chamber_C = T_air_in_cond + hp_cfg.epsilon_cond * (_T_cond_sat_ol - T_air_in_cond)
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)
            _T_cond_out = T_to_chamber_C  # for E1/E2, condenser outlet = chamber inlet
            h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        # --- Usable solar (clipped at T_set demand) for all E variants ---
        _cp_air_usable = 1.006
        if e_variant in ("E1", "E2"):
            # Solar sits between collector inlet and condenser inlet. Usable =
            # enthalpy actually delivered to the cond inlet (T_air_in_cond).
            # Inlet ref is HRX output normally, exhaust during VPD bypass.
            _solar_inlet_ref = (T_exhaust_prev if _vpd_bypass_active
                                and T_exhaust_prev is not None else T_amb_heated)
            Q_solar_usable_kW = (
                m_da * _cp_air_usable
                * max(T_air_in_cond - _solar_inlet_ref, 0.0)
            )
        else:
            # E3: solar targets T_set after the condenser. Usable =
            # enthalpy delivered from T_cond_out to T_to_chamber_C (capped at T_set).
            Q_solar_usable_kW = (
                m_da * _cp_air_usable
                * max(T_to_chamber_C - _T_cond_out, 0.0)
            )

        # ----- 5. DRYING CHAMBER -----
        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        if reversal_s > 0:
            reverse_flow = (int(time_s / reversal_s) % 2 == 1)
        else:
            reverse_flow = False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = (
            simulate_drying_chamber(
                T_to_chamber_C, omega_to_chamber, h_to_chamber,
                X_trays, MR_trays, cfg, time_s, m_da, dt_s,
                reverse_flow=reverse_flow,
            )
        )

        # ----- 6. SAVE exhaust for next step -----
        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exh_raw = T_tray_out[exhaust_idx]
        omega_exh_raw = float(humidity_ratio_from_T_RH(
            T_exh_raw, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))
        if T_exhaust_prev is not None:
            T_exhaust_prev = _alpha * T_exh_raw + (1.0 - _alpha) * T_exhaust_prev
            omega_exhaust_prev = _alpha * omega_exh_raw + (1.0 - _alpha) * omega_exhaust_prev
        else:
            T_exhaust_prev = T_exh_raw
            omega_exhaust_prev = omega_exh_raw

        # ----- 7. ACCUMULATE & RECORD -----
        m_w_cum += sum(dm_w_trays)
        W_comp_cum_kWh += hp_result.W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += hp_result.Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += Q_solar_kW * dt_s / 3600.0
        Q_solar_usable_cum_kWh += Q_solar_usable_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0
        # Only count HRX heat when it's actually used (not during bypass)
        if not _vpd_bypass_active:
            Q_HRX_cum_kWh += max(0, Q_HRX_kW) * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar,
            Q_solar_kW, T_after_solar, eta_solar,
            hp_result, T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            bypass_mode=bypass_mode,
            flow_direction=flow_direction,
        )
        # HRX-specific columns
        record["T_amb_heated_C"] = T_amb_heated
        record["T_exh_cooled_C"] = T_exh_cooled
        record["omega_exh_cooled"] = omega_exh_cooled
        record["Q_HRX_kW"] = Q_HRX_kW
        record["Q_HRX_cum_kWh"] = Q_HRX_cum_kWh
        record["HRX_condensation"] = int(hrx_condensation)
        # Usable solar (clipped at T_set demand) — see E2/E3 clipping analysis
        record["Q_solar_usable_kW"] = Q_solar_usable_kW
        record["Q_solar_usable_cum_kWh"] = Q_solar_usable_cum_kWh
        record["Q_solar_clipped_kW"] = max(0.0, Q_solar_kW - Q_solar_usable_kW)
        record["T_to_chamber_deficit_C"] = cfg.dryer.T_set_C - T_to_chamber_C
        record["vpd_utilization"] = _vpd_utilization
        record["vpd_bypass_active"] = int(_vpd_bypass_active)
        # Audit trail columns
        record["T_solar_in_C"] = _T_solar_in
        record["T_air_in_cond_C"] = _T_air_in_cond
        record["T_cond_out_C"] = _T_cond_out
        record["T_evap_source_C"] = _T_evap_source
        record["T_cond_target_C"] = _T_cond_target
        record["omega_amb"] = omega_amb
        record["omega_exhaust"] = omega_exhaust_prev if omega_exhaust_prev is not None else omega_amb
        record["hp_mode"] = _hp_mode
        # Flags
        record["flag_hp_at_capacity"] = int(hp_result is not None and hp_result.flag_hp_at_capacity)
        record["flag_evap_oversized"] = int(hp_result is not None and hp_result.flag_evap_oversized)
        record["flag_cond_oversized"] = int(hp_result is not None and hp_result.flag_cond_oversized)

        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_comp_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df,
        config_type=f"CONFIG_{e_variant}",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG B: SOLAR + HP SERIES
# ==============================================================================

def simulate_config_B_solar_HP_series(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config B: Solar preheats air, HP boosts to T_set if needed.

    Supports evaporator bypass (same logic as Config A).
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa

    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2, eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )

    T_absorber_prev = None
    m_w_cum = W_comp_cum_kWh = Q_cond_cum_kWh = Q_solar_cum_kWh = 0.0
    Q_solar_wasted_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    # Bug fix: pass ALL heatpump fields
    hp_cfg = HeatPumpConfig(
        refrigerant=cfg.heatpump.refrigerant,
        eta_isentropic=cfg.heatpump.eta_isentropic,
        eta_mechanical=cfg.heatpump.eta_mechanical,
        superheat_K=cfg.heatpump.superheat_K,
        subcooling_K=cfg.heatpump.subcooling_K,
        epsilon_evap=cfg.heatpump.epsilon_evap,
        epsilon_cond=cfg.heatpump.epsilon_cond,
        T_evap_min_C=cfg.heatpump.T_evap_min_C,
        T_evap_max_C=cfg.heatpump.T_evap_max_C,
        T_cond_min_C=cfg.heatpump.T_cond_min_C,
        T_cond_max_C=cfg.heatpump.T_cond_max_C,
        COP_min=cfg.heatpump.COP_min,
        pressure_ratio_max=cfg.heatpump.pressure_ratio_max,
        Q_cond_max_kW=cfg.heatpump.Q_cond_max_kW,
        Q_evap_max_kW=cfg.heatpump.Q_evap_max_kW,
        DT_evap_approach=cfg.heatpump.DT_evap_approach,
    )

    r = cfg.dryer.r_recirc

    # Previous-step exhaust state — start as None so t=0 runs open-loop and
    # recirculation begins smoothly from t=1 using actual chamber exhaust.
    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    # Condenser-direct bypass state (VPD-based oscillating)
    _cond_bypass_active = False
    _cond_penalty_frac = 1.0  # start high so bypass doesn't activate on step 0
    _last_mode_switch_s = -1e9  # timestamp of last VPD mode switch
    _humidity_dwell_s = 300.0   # current computed dwell (updated each step)
    _dm_w_total_prev = 0.0     # total water removed in previous timestep [kg]

    T_cond_C_hp = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K  # fixed for flags

    _tau_s = 300.0
    _alpha = dt_s / (_tau_s + dt_s)

    mode = f"closed-loop, r={r:.2f}" if r > 0 else "open-loop"
    print(f"[CONFIG B] Solar+HP series ({mode}), {n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m2, "
          f"P_atm={p_atm/1000:.1f}kPa")

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))
        h_amb = float(moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_amb))

        bypass_mode = "none"
        # Per-step tracking variables (updated in recirc+evap path)
        T_dp_mix = 0.0
        T_evap_coil_dyn = 0.0
        r_recirc_actual = 0.0
        RH_exh_prev_pct = 0.0
        T_evap_sat = None      # set only in recirc+evap path → triggers direct HP call
        T_evap_source = T_amb_C  # fallback for open-loop and bypass paths
        _flag_impossible = False
        # Air state tracking for psychrometric chart (defaults = open-loop)
        T_mix_val = T_amb_C
        omega_mix_val = omega_amb
        T_after_evap_val = T_amb_C

        # Fixed recirculation ratio (dynamic modes removed 2026-04-20)
        r_eff = r

        # ---- Update condenser-direct bypass state (VPD-based oscillating) ----
        _cond_thresh = cfg.dryer.cond_penalty_thresh
        if _cond_thresh > 0.0 and omega_exhaust_prev is not None and r_eff > 0:
            _cond_penalty_frac = compute_cond_penalty_est(
                omega_exhaust=omega_exhaust_prev,
                omega_amb=omega_amb,
                r=r_eff,
                T_set_C=cfg.dryer.T_set_C,
                epsilon_evap=hp_cfg.epsilon_evap,
                T_evap_target_C=cfg.heatpump.T_evap_target_C,
                p_atm_Pa=p_atm,
            )
            # Compute physics-based dwell from humidity accumulation rate
            if _cond_bypass_active:
                _target_penalty = _cond_thresh * 3.0
            else:
                _target_penalty = _cond_thresh
            _humidity_dwell_s = compute_humidity_dwell_s(
                omega_exhaust=omega_exhaust_prev,
                omega_amb=omega_amb,
                r=r_eff,
                T_set_C=cfg.dryer.T_set_C,
                epsilon_evap=hp_cfg.epsilon_evap,
                T_evap_target_C=cfg.heatpump.T_evap_target_C,
                cond_penalty_now=_cond_penalty_frac,
                target_penalty=_target_penalty,
                dm_w_total_prev=_dm_w_total_prev,
                m_da=m_da,
                dt_s=dt_s,
                p_atm_Pa=p_atm,
            )
            _dwell_ok = (time_s - _last_mode_switch_s) >= _humidity_dwell_s
            if _cond_bypass_active:
                if _cond_penalty_frac > _cond_thresh * 3.0 and _dwell_ok:
                    _cond_bypass_active = False
                    _last_mode_switch_s = time_s
            else:
                if _cond_penalty_frac < _cond_thresh and _dwell_ok:
                    _cond_bypass_active = True
                    _last_mode_switch_s = time_s
        if omega_exhaust_prev is not None and T_exhaust_prev is not None:
            RH_exh_prev_pct = float(RH_from_T_omega(T_exhaust_prev, omega_exhaust_prev, p_atm)) * 100.0

        # ----- 1. MIXING + EVAPORATOR (closed-loop) or DIRECT (open-loop) -----
        if r_eff > 0 and T_exhaust_prev is not None:
            if _cond_bypass_active and _cond_thresh > 0.0:
                # ---- CONDENSER-DIRECT MODE ----
                # Exhaust warm+dry → condenser directly (tiny Q_cond).
                # Solar runs on ambient → evaporator heat source.
                T_air_to_solar     = T_amb_C              # solar runs on ambient air
                omega_to_chamber   = omega_exhaust_prev   # closed loop (humidity carries over)
                T_air_in_cond_direct = T_exhaust_prev     # exhaust bypasses solar → condenser
                bypass_mode        = "cond_direct"
                # T_evap_sat stays None → size_heat_pump_for_air_heating
                T_mix_val = T_exhaust_prev
                omega_mix_val = omega_exhaust_prev
                T_after_evap_val = T_exhaust_prev
            else:
                # Closed-loop: mix exhaust with ambient at ratio r_eff
                h_exh = float(moist_air_enthalpy_kJ_per_kg(T_exhaust_prev, omega_exhaust_prev))
                omega_mix = r_eff * omega_exhaust_prev + (1.0 - r_eff) * omega_amb
                h_mix = r_eff * h_exh + (1.0 - r_eff) * h_amb
                T_mix = float(temperature_from_h_omega_C(h_mix, omega_mix))

                # Saturation clamp: if mix is supersaturated, excess condenses as fog
                omega_sat_mix = float(humidity_ratio_from_T_RH(T_mix, 1.0, p_atm))
                if omega_mix > omega_sat_mix:
                    omega_mix = omega_sat_mix

                # Fixed T_evap with modulation: lower T_evap if T_mix is near coil
                _min_dt_evap = 5.0
                T_evap_sat      = cfg.heatpump.T_evap_target_C
                T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach
                if T_mix - T_evap_coil_dyn < _min_dt_evap:
                    T_evap_coil_dyn = T_mix - _min_dt_evap
                    T_evap_sat = T_evap_coil_dyn - hp_cfg.DT_evap_approach
                    T_evap_sat = max(T_evap_sat, hp_cfg.T_evap_min_C)
                    T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach
                # Hard stop: impossible cycle guard
                if T_evap_sat >= T_cond_C_hp:
                    _flag_impossible = True
                    T_air_to_solar = T_mix
                    omega_to_chamber = omega_mix
                    T_evap_source = T_amb_C
                    T_evap_sat = None
                    bypass_mode = "bypass"
                    T_mix_val = T_mix
                    omega_mix_val = omega_mix
                    T_after_evap_val = T_mix
                else:
                    r_recirc_actual = r_eff
                    T_after_evap, omega_after_evap, _ = _evaporator_dehumidify(
                        T_air_in_C=T_mix, omega_in=omega_mix,
                        T_evap_coil_C=T_evap_coil_dyn, epsilon_evap=hp_cfg.epsilon_evap,
                        p_atm_Pa=p_atm,
                    )
                    T_air_to_solar = T_after_evap
                    omega_to_chamber = omega_after_evap
                    bypass_mode = "evap"
                    T_mix_val = T_mix
                    omega_mix_val = omega_mix
                    T_after_evap_val = T_after_evap
        else:
            T_air_to_solar = T_amb_C
            omega_to_chamber = omega_amb

        # ----- 2. SOLAR COLLECTOR preheats air -----
        solar_state, T_absorber_prev = compute_solar_collector(
            T_in_C=T_air_to_solar, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
            m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s, T_absorber_prev_C=T_absorber_prev,
        )
        T_after_solar = solar_state.T_out_C

        # In cond-direct mode: exhaust bypasses solar, solar output is evap source
        if bypass_mode == "cond_direct":
            T_evap_source = T_after_solar   # solar-heated ambient → evap heat source
            T_hp_air_in = T_air_in_cond_direct  # warm exhaust → condenser
        else:
            T_hp_air_in = T_after_solar     # normal: solar output → condenser

        # ----- 3. HP CONDENSER boosts to T_set (if needed) -----
        Q_solar_wasted_kW = 0.0
        if bypass_mode != "cond_direct" and T_after_solar >= cfg.dryer.T_set_C:
            # Solar alone overshoots T_set: clamp delivered air to T_set.
            # The energy above T_set is dumped (modeled damper/bypass), tracked
            # as Q_solar_wasted_kW so collector output (Q_solar_useful) and
            # delivered heat can be reconciled.
            hp_result = None
            W_comp_kW = Q_cond_kW = 0.0
            T_to_chamber_C = cfg.dryer.T_set_C
            h_after_solar = float(moist_air_enthalpy_kJ_per_kg(T_after_solar, omega_to_chamber))
            h_at_set      = float(moist_air_enthalpy_kJ_per_kg(cfg.dryer.T_set_C, omega_to_chamber))
            Q_solar_wasted_kW = max(0.0, m_da * (h_after_solar - h_at_set))
        elif T_evap_sat is not None:
            # Recirc+evap path: enforce HP first law (Q_cond = W_comp + Q_evap_air)
            h_before_evap = float(moist_air_enthalpy_kJ_per_kg(T_mix, omega_mix_val))
            h_after_evap  = float(moist_air_enthalpy_kJ_per_kg(T_after_evap_val, omega_to_chamber))
            Q_evap_air_kW = max(0.0, m_da * (h_before_evap - h_after_evap))

            T_cond_C_cycle = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            COP_now = compute_hp_COP(T_evap_sat, T_cond_C_cycle, hp_cfg)

            eta_m = hp_cfg.eta_mechanical
            if COP_now > eta_m:
                Q_cond_1st_kW = Q_evap_air_kW * COP_now / (COP_now - eta_m)
            else:
                Q_cond_1st_kW = Q_evap_air_kW

            h_in_cond     = float(moist_air_enthalpy_kJ_per_kg(T_hp_air_in, omega_to_chamber))
            h_out_cond    = float(moist_air_enthalpy_kJ_per_kg(cfg.dryer.T_set_C, omega_to_chamber))
            Q_cond_kW_req = max(0.001, m_da * (h_out_cond - h_in_cond))

            # Condenser effectiveness limit
            T_out_cond_eff = T_hp_air_in + hp_cfg.epsilon_cond * (T_cond_C_cycle - T_hp_air_in)
            h_out_cond_eff = float(moist_air_enthalpy_kJ_per_kg(T_out_cond_eff, omega_to_chamber))
            Q_cond_eff_kW  = max(0.001, m_da * (h_out_cond_eff - h_in_cond))

            Q_cond_actual_kW = min(Q_cond_1st_kW, Q_cond_kW_req, Q_cond_eff_kW)

            hp_result = compute_heat_pump_cycle(
                T_evap_C=T_evap_sat,
                T_cond_C=T_cond_C_cycle,
                Q_cond_target_kW=Q_cond_actual_kW,
                cfg=hp_cfg,
            )
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW

            # T_to_chamber from enthalpy balance
            h_to_cham = h_in_cond + hp_result.Q_cond_kW / m_da
            T_to_chamber_C = float(temperature_from_h_omega_C(h_to_cham, omega_to_chamber))
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)
        else:
            # Open-loop, bypass, or cond-direct path
            hp_result = size_heat_pump_for_air_heating(
                T_air_in_C=T_hp_air_in, T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da, T_evap_source_C=T_evap_source, cfg=hp_cfg,
                omega_in=omega_to_chamber,
            )
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW
            # Apply condenser effectiveness
            _T_cond_sat_ol = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            T_to_chamber_C = T_hp_air_in + hp_cfg.epsilon_cond * (_T_cond_sat_ol - T_hp_air_in)
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)

        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        # ----- 4. DRYING CHAMBER -----
        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        if reversal_s > 0:
            reverse_flow = (int(time_s / reversal_s) % 2 == 1)
        else:
            reverse_flow = False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s,
            reverse_flow=reverse_flow,
        )

        # ----- 5. SAVE exhaust for next step's mixing -----
        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exh_raw = T_tray_out[exhaust_idx]
        omega_exh_raw = float(humidity_ratio_from_T_RH(
            T_exh_raw, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))
        if T_exhaust_prev is not None:
            T_exhaust_prev = _alpha * T_exh_raw + (1.0 - _alpha) * T_exhaust_prev
            omega_exhaust_prev = _alpha * omega_exh_raw + (1.0 - _alpha) * omega_exhaust_prev
        else:
            T_exhaust_prev = T_exh_raw
            omega_exhaust_prev = omega_exh_raw

        # ----- 6. ACCUMULATE & RECORD -----
        _dm_w_total_prev = sum(dm_w_trays)  # save for humidity dwell calc
        m_w_cum += _dm_w_total_prev
        W_comp_cum_kWh += W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        Q_solar_wasted_cum_kWh += Q_solar_wasted_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar,
            solar_state.Q_useful_kW, T_after_solar, solar_state.eta_collector,
            hp_result, T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            bypass_mode=bypass_mode,
            flow_direction=flow_direction,
        )
        record["Q_solar_wasted_kW"]      = Q_solar_wasted_kW
        record["Q_solar_wasted_cum_kWh"] = Q_solar_wasted_cum_kWh
        record["T_mix_C"]           = T_mix_val
        record["omega_mix"]         = omega_mix_val
        record["T_after_evap_C"]    = T_after_evap_val
        record["T_dp_mix_C"]        = T_dp_mix
        record["T_evap_coil_C_dyn"] = T_evap_coil_dyn
        record["r_recirc_actual"]   = r_recirc_actual
        record["RH_exhaust_pct"]    = RH_exh_prev_pct
        record["cond_penalty_frac"] = _cond_penalty_frac
        record["humidity_dwell_s"]  = _humidity_dwell_s
        # Use T_evap_sat from evap path when HP condenser is off (hp_result is None)
        _T_evap_rec = hp_result.T_evap_C if hp_result is not None else (T_evap_sat if T_evap_sat is not None else 0.0)
        record["flag_frost_risk"]       = int(_T_evap_rec < 2.0)
        record["flag_outside_ac_range"] = int(_T_evap_rec < 2.0 or _T_evap_rec > 20.0)
        record["flag_impossible_cycle"] = int(_flag_impossible)
        record["flag_hp_at_capacity"]   = int(hp_result is not None and hp_result.flag_hp_at_capacity)
        record["flag_evap_oversized"]   = int(hp_result is not None and hp_result.flag_evap_oversized)
        record["flag_cond_oversized"]   = int(hp_result is not None and hp_result.flag_cond_oversized)
        _p_v_exh = (omega_exhaust_prev * p_atm / (0.622 + omega_exhaust_prev)) if omega_exhaust_prev is not None else 0.0
        _p_v_amb = omega_amb * p_atm / (0.622 + omega_amb)
        record["VPD_exhaust_Pa"] = max(0.0, p_sat_water_Pa(T_exhaust_prev) - _p_v_exh) if T_exhaust_prev is not None else 0.0
        record["VPD_ambient_Pa"] = max(0.0, p_sat_water_Pa(T_amb_C) - _p_v_amb)
        record["T_to_chamber_deficit_C"] = cfg.dryer.T_set_C - T_to_chamber_C
        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_comp_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df, config_type="CONFIG_B",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG C1: SOLAR CASCADE — MIX BEFORE SOLAR
# ==============================================================================

def simulate_config_C1_mix_before_solar(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config C1: Solar cascade — recirculated exhaust mixes BEFORE solar collector.

    Air path: [r×Exhaust + (1-r)×Ambient] → Solar → Evap → Cond → Chamber
    For r=0: Ambient → Solar → Cond → Chamber (identical to C2 open-loop)

    VPD condenser-direct bypass (when cond_penalty_thresh > 0):
      When exhaust is nearly as dry as post-evap air (CPF < threshold),
      route exhaust directly to condenser (tiny Q_cond) and run evaporator
      on solar-heated ambient air as heat source.
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa

    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2, eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )

    T_absorber_prev = None
    m_w_cum = W_comp_cum_kWh = Q_cond_cum_kWh = Q_solar_cum_kWh = 0.0
    Q_solar_wasted_cum_kWh = 0.0
    Q_solar_to_evap_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    hp_cfg = HeatPumpConfig(
        refrigerant=cfg.heatpump.refrigerant,
        eta_isentropic=cfg.heatpump.eta_isentropic,
        eta_mechanical=cfg.heatpump.eta_mechanical,
        superheat_K=cfg.heatpump.superheat_K,
        subcooling_K=cfg.heatpump.subcooling_K,
        epsilon_evap=cfg.heatpump.epsilon_evap,
        epsilon_cond=cfg.heatpump.epsilon_cond,
        T_evap_min_C=cfg.heatpump.T_evap_min_C,
        T_evap_max_C=cfg.heatpump.T_evap_max_C,
        T_cond_min_C=cfg.heatpump.T_cond_min_C,
        T_cond_max_C=cfg.heatpump.T_cond_max_C,
        COP_min=cfg.heatpump.COP_min,
        pressure_ratio_max=cfg.heatpump.pressure_ratio_max,
        Q_cond_max_kW=cfg.heatpump.Q_cond_max_kW,
        Q_evap_max_kW=cfg.heatpump.Q_evap_max_kW,
        DT_evap_approach=cfg.heatpump.DT_evap_approach,
    )

    r = cfg.dryer.r_recirc

    # Exhaust tracking for recirculation
    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    _tau_s = 300.0
    _alpha = dt_s / (_tau_s + dt_s)
    T_cond_C_hp = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K

    # Condenser-direct bypass state (VPD-based oscillating)
    _cond_bypass_active = False
    _cond_penalty_frac = 1.0
    _last_mode_switch_s = -1e9
    _humidity_dwell_s = 300.0
    _dm_w_total_prev = 0.0

    mode = f"closed-loop, r={r:.2f}" if r > 0 else "open-loop"
    print(f"[CONFIG C1] Solar cascade, mix BEFORE solar ({mode}), "
          f"{n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m2, P_atm={p_atm/1000:.1f}kPa")

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))
        h_amb = float(moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_amb))

        bypass_mode = "none"
        T_dp_mix = 0.0
        T_evap_coil_dyn = 0.0
        r_recirc_actual = 0.0
        RH_exh_prev_pct = 0.0
        T_evap_sat = None
        T_evap_source = T_amb_C
        _flag_impossible = False
        # Air state tracking for psychrometric chart (defaults = open-loop)
        T_mix_val = T_amb_C
        omega_mix_val = omega_amb
        T_after_evap_val = T_amb_C

        # ---- Update condenser-direct bypass state (VPD-based oscillating) ----
        _cond_thresh = cfg.dryer.cond_penalty_thresh
        if _cond_thresh > 0.0 and omega_exhaust_prev is not None and r > 0:
            _cond_penalty_frac = compute_cond_penalty_est(
                omega_exhaust=omega_exhaust_prev, omega_amb=omega_amb, r=r,
                T_set_C=cfg.dryer.T_set_C,
                epsilon_evap=hp_cfg.epsilon_evap, T_evap_target_C=cfg.heatpump.T_evap_target_C,
                p_atm_Pa=p_atm,
            )
            if _cond_bypass_active:
                _target_penalty = _cond_thresh * 3.0
            else:
                _target_penalty = _cond_thresh
            _humidity_dwell_s = compute_humidity_dwell_s(
                omega_exhaust=omega_exhaust_prev, omega_amb=omega_amb, r=r,
                T_set_C=cfg.dryer.T_set_C,
                epsilon_evap=hp_cfg.epsilon_evap, T_evap_target_C=cfg.heatpump.T_evap_target_C,
                cond_penalty_now=_cond_penalty_frac,
                target_penalty=_target_penalty, dm_w_total_prev=_dm_w_total_prev,
                m_da=m_da, dt_s=dt_s, p_atm_Pa=p_atm,
            )
            _dwell_ok = (time_s - _last_mode_switch_s) >= _humidity_dwell_s
            if _cond_bypass_active:
                if _cond_penalty_frac > _cond_thresh * 3.0 and _dwell_ok:
                    _cond_bypass_active = False
                    _last_mode_switch_s = time_s
            else:
                if _cond_penalty_frac < _cond_thresh and _dwell_ok:
                    _cond_bypass_active = True
                    _last_mode_switch_s = time_s
        if omega_exhaust_prev is not None and T_exhaust_prev is not None:
            RH_exh_prev_pct = float(RH_from_T_omega(T_exhaust_prev, omega_exhaust_prev, p_atm)) * 100.0

        # ----- 1. MIXING (before solar) + SOLAR COLLECTOR -----
        if r > 0 and T_exhaust_prev is not None:
            if _cond_bypass_active and _cond_thresh > 0.0:
                # ---- CONDENSER-DIRECT MODE ----
                # Exhaust → condenser directly (tiny Q_cond).
                # Solar collector runs on pure ambient → evaporator heat source.
                solar_state, T_absorber_prev = compute_solar_collector(
                    T_in_C=T_amb_C, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
                    m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s,
                    T_absorber_prev_C=T_absorber_prev,
                )
                T_after_solar = solar_state.T_out_C
                T_air_in_HP = T_exhaust_prev
                omega_to_chamber = omega_exhaust_prev
                T_evap_source = T_after_solar
                bypass_mode = "cond_direct"
                T_mix_val = T_exhaust_prev
                omega_mix_val = omega_exhaust_prev
                T_after_evap_val = T_exhaust_prev
            else:
                # ---- NORMAL PATH: mix exhaust+ambient BEFORE solar ----
                h_exh = float(moist_air_enthalpy_kJ_per_kg(T_exhaust_prev, omega_exhaust_prev))
                omega_mix = r * omega_exhaust_prev + (1.0 - r) * omega_amb
                h_mix = r * h_exh + (1.0 - r) * h_amb
                T_mix = float(temperature_from_h_omega_C(h_mix, omega_mix))

                # Saturation clamp: if mix is supersaturated, excess condenses as fog
                omega_sat_mix = float(humidity_ratio_from_T_RH(T_mix, 1.0, p_atm))
                if omega_mix > omega_sat_mix:
                    omega_mix = omega_sat_mix

                # Solar collector processes the MIX (warmer inlet → lower η)
                solar_state, T_absorber_prev = compute_solar_collector(
                    T_in_C=T_mix, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
                    m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s,
                    T_absorber_prev_C=T_absorber_prev,
                )
                T_after_solar = solar_state.T_out_C
                # Solar doesn't change humidity ratio
                omega_after_solar = omega_mix

                # Fixed T_evap with modulation: lower T_evap if air is near coil
                _min_dt_evap = 5.0
                T_evap_sat      = cfg.heatpump.T_evap_target_C
                T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach
                if T_after_solar - T_evap_coil_dyn < _min_dt_evap:
                    T_evap_coil_dyn = T_after_solar - _min_dt_evap
                    T_evap_sat = T_evap_coil_dyn - hp_cfg.DT_evap_approach
                    T_evap_sat = max(T_evap_sat, hp_cfg.T_evap_min_C)
                    T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach

                if T_evap_sat >= T_cond_C_hp:
                    _flag_impossible = True
                    T_air_in_HP = T_after_solar
                    omega_to_chamber = omega_after_solar
                    T_evap_source = T_after_solar
                    T_evap_sat = None
                    bypass_mode = "bypass"
                    T_mix_val = T_mix
                    omega_mix_val = omega_mix
                    T_after_evap_val = T_after_solar
                else:
                    r_recirc_actual = r
                    T_after_evap, omega_after_evap, _ = _evaporator_dehumidify(
                        T_air_in_C=T_after_solar, omega_in=omega_after_solar,
                        T_evap_coil_C=T_evap_coil_dyn, epsilon_evap=hp_cfg.epsilon_evap,
                        p_atm_Pa=p_atm,
                    )
                    T_air_in_HP = T_after_evap
                    omega_to_chamber = omega_after_evap
                    bypass_mode = "evap"
                    T_mix_val = T_mix
                    omega_mix_val = omega_mix
                    T_after_evap_val = T_after_evap
        else:
            # Open-loop (r=0): Amb → Solar → Evap (inline dehumid) → Cond → Chamber
            solar_state, T_absorber_prev = compute_solar_collector(
                T_in_C=T_amb_C, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
                m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s,
                T_absorber_prev_C=T_absorber_prev,
            )
            T_after_solar = solar_state.T_out_C
            omega_after_solar = omega_amb  # solar is sensible-only

            # Inline evaporator on the solar-heated air
            _min_dt_evap = 5.0
            T_evap_sat      = cfg.heatpump.T_evap_target_C
            T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach
            if T_after_solar - T_evap_coil_dyn < _min_dt_evap:
                T_evap_coil_dyn = T_after_solar - _min_dt_evap
                T_evap_sat = T_evap_coil_dyn - hp_cfg.DT_evap_approach
                T_evap_sat = max(T_evap_sat, hp_cfg.T_evap_min_C)
                T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach

            if T_evap_sat >= T_cond_C_hp:
                # Impossible cycle — fall back to open-loop sizing
                _flag_impossible = True
                T_air_in_HP = T_after_solar
                omega_to_chamber = omega_after_solar
                T_evap_source = T_after_solar
                T_evap_sat = None
                bypass_mode = "bypass"
            else:
                T_after_evap, omega_after_evap, _ = _evaporator_dehumidify(
                    T_air_in_C=T_after_solar, omega_in=omega_after_solar,
                    T_evap_coil_C=T_evap_coil_dyn, epsilon_evap=hp_cfg.epsilon_evap,
                    p_atm_Pa=p_atm,
                )
                T_air_in_HP = T_after_evap          # cooled/dehumid air → condenser
                omega_to_chamber = omega_after_evap  # dehumidified
                bypass_mode = "evap"
                T_mix_val = T_after_solar
                omega_mix_val = omega_after_solar
                T_after_evap_val = T_after_evap

        # ----- 2. HP CONDENSER heats to T_set (if needed) -----
        Q_solar_wasted_kW = 0.0
        Q_solar_to_evap_kW = 0.0
        if bypass_mode == "cond_direct":
            # Solar feeds the evap side only (parallel to chamber stream).
            Q_solar_to_evap_kW = solar_state.Q_useful_kW
        if T_air_in_HP >= cfg.dryer.T_set_C:
            hp_result = None
            W_comp_kW = Q_cond_kW = 0.0
            T_to_chamber_C = cfg.dryer.T_set_C
            # Chamber air is clamped to T_set: anything above is dumped.
            h_in   = float(moist_air_enthalpy_kJ_per_kg(T_air_in_HP, omega_to_chamber))
            h_set  = float(moist_air_enthalpy_kJ_per_kg(cfg.dryer.T_set_C, omega_to_chamber))
            Q_solar_wasted_kW = max(0.0, m_da * (h_in - h_set))
        elif T_evap_sat is not None:
            # Recirc+evap path: enforce HP first law
            # In C1, evaporator processes solar output (T_after_solar, omega_after_solar)
            h_before_evap = float(moist_air_enthalpy_kJ_per_kg(T_after_solar, omega_after_solar))
            h_after_evap  = float(moist_air_enthalpy_kJ_per_kg(T_air_in_HP, omega_to_chamber))
            Q_evap_air_kW = max(0.0, m_da * (h_before_evap - h_after_evap))

            T_cond_C_cycle = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            COP_now = compute_hp_COP(T_evap_sat, T_cond_C_cycle, hp_cfg)

            eta_m = hp_cfg.eta_mechanical
            if COP_now > eta_m:
                Q_cond_1st_kW = Q_evap_air_kW * COP_now / (COP_now - eta_m)
            else:
                Q_cond_1st_kW = Q_evap_air_kW

            h_in_cond     = float(moist_air_enthalpy_kJ_per_kg(T_air_in_HP, omega_to_chamber))
            h_out_cond    = float(moist_air_enthalpy_kJ_per_kg(cfg.dryer.T_set_C, omega_to_chamber))
            Q_cond_kW_req = max(0.001, m_da * (h_out_cond - h_in_cond))

            # Condenser effectiveness limit
            T_out_cond_eff = T_air_in_HP + hp_cfg.epsilon_cond * (T_cond_C_cycle - T_air_in_HP)
            h_out_cond_eff = float(moist_air_enthalpy_kJ_per_kg(T_out_cond_eff, omega_to_chamber))
            Q_cond_eff_kW  = max(0.001, m_da * (h_out_cond_eff - h_in_cond))

            Q_cond_actual_kW = min(Q_cond_1st_kW, Q_cond_kW_req, Q_cond_eff_kW)

            hp_result = compute_heat_pump_cycle(
                T_evap_C=T_evap_sat,
                T_cond_C=T_cond_C_cycle,
                Q_cond_target_kW=Q_cond_actual_kW, cfg=hp_cfg,
            )
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW

            h_to_cham = h_in_cond + hp_result.Q_cond_kW / m_da
            T_to_chamber_C = float(temperature_from_h_omega_C(h_to_cham, omega_to_chamber))
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)
        else:
            hp_result = size_heat_pump_for_air_heating(
                T_air_in_C=T_air_in_HP, T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da, T_evap_source_C=T_evap_source, cfg=hp_cfg,
                omega_in=omega_to_chamber,
            )
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW
            # Apply condenser effectiveness
            _T_cond_sat_ol = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            T_to_chamber_C = T_air_in_HP + hp_cfg.epsilon_cond * (_T_cond_sat_ol - T_air_in_HP)
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)

        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        # ----- 3. DRYING CHAMBER -----
        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        if reversal_s > 0:
            reverse_flow = (int(time_s / reversal_s) % 2 == 1)
        else:
            reverse_flow = False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s,
            reverse_flow=reverse_flow,
        )

        # ----- 4. SAVE exhaust for next step -----
        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exh_raw = T_tray_out[exhaust_idx]
        omega_exh_raw = float(humidity_ratio_from_T_RH(
            T_exh_raw, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))
        if T_exhaust_prev is not None:
            T_exhaust_prev = _alpha * T_exh_raw + (1.0 - _alpha) * T_exhaust_prev
            omega_exhaust_prev = _alpha * omega_exh_raw + (1.0 - _alpha) * omega_exhaust_prev
        else:
            T_exhaust_prev = T_exh_raw
            omega_exhaust_prev = omega_exh_raw

        # ----- 5. ACCUMULATE & RECORD -----
        _dm_w_total_prev = sum(dm_w_trays)
        m_w_cum += _dm_w_total_prev
        W_comp_cum_kWh += W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        Q_solar_wasted_cum_kWh += Q_solar_wasted_kW * dt_s / 3600.0
        Q_solar_to_evap_cum_kWh += Q_solar_to_evap_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar,
            solar_state.Q_useful_kW, T_after_solar, solar_state.eta_collector,
            hp_result, T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            bypass_mode=bypass_mode,
            flow_direction=flow_direction,
        )
        record["Q_solar_wasted_kW"]       = Q_solar_wasted_kW
        record["Q_solar_wasted_cum_kWh"]  = Q_solar_wasted_cum_kWh
        record["Q_solar_to_evap_kW"]      = Q_solar_to_evap_kW
        record["Q_solar_to_evap_cum_kWh"] = Q_solar_to_evap_cum_kWh
        record["T_mix_C"]           = T_mix_val
        record["omega_mix"]         = omega_mix_val
        record["T_after_evap_C"]    = T_after_evap_val
        record["T_dp_mix_C"]        = T_dp_mix
        record["T_evap_coil_C_dyn"] = T_evap_coil_dyn
        record["r_recirc_actual"]   = r_recirc_actual
        record["RH_exhaust_pct"]    = RH_exh_prev_pct
        record["cond_penalty_frac"] = _cond_penalty_frac
        record["humidity_dwell_s"]  = _humidity_dwell_s
        _T_evap_rec = hp_result.T_evap_C if hp_result is not None else (T_evap_sat if T_evap_sat is not None else 0.0)
        record["flag_frost_risk"]       = int(_T_evap_rec < 2.0)
        record["flag_outside_ac_range"] = int(_T_evap_rec < 2.0 or _T_evap_rec > 20.0)
        record["flag_impossible_cycle"] = int(_flag_impossible)
        record["flag_hp_at_capacity"]   = int(hp_result is not None and hp_result.flag_hp_at_capacity)
        record["flag_evap_oversized"]   = int(hp_result is not None and hp_result.flag_evap_oversized)
        record["flag_cond_oversized"]   = int(hp_result is not None and hp_result.flag_cond_oversized)
        _p_v_exh = (omega_exhaust_prev * p_atm / (0.622 + omega_exhaust_prev)) if omega_exhaust_prev is not None else 0.0
        _p_v_amb = omega_amb * p_atm / (0.622 + omega_amb)
        record["VPD_exhaust_Pa"] = max(0.0, p_sat_water_Pa(T_exhaust_prev) - _p_v_exh) if T_exhaust_prev is not None else 0.0
        record["VPD_ambient_Pa"] = max(0.0, p_sat_water_Pa(T_amb_C) - _p_v_amb)
        record["T_to_chamber_deficit_C"] = cfg.dryer.T_set_C - T_to_chamber_C
        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_comp_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df, config_type="CONFIG_C1",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG C2: SOLAR CASCADE — MIX AFTER SOLAR
# ==============================================================================

def simulate_config_C2_mix_after_solar(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config C2: Solar cascade — recirculated exhaust mixes AFTER solar collector.

    Air paths (code-true):
      r > 0 (normal): Ambient → Solar → MIX(+ r·Exhaust) → Evap → Cond → Chamber
        Solar is inline on the chamber air stream.
      r = 0 (open-loop): Ambient → Cond → Chamber  (chamber stream)
                         Ambient → Solar → T_evap_source  (parallel, evap-side only)
        At r=0 the solar collector heats a PARALLEL stream used only as the
        refrigerant evaporator's heat source (boosts COP); it does not pass
        through the chamber air path. Q_solar_to_evap_cum_kWh tracks this.

    The solar collector always sees fresh ambient air, preserving its
    efficiency. Exhaust is mixed with the solar outlet before the HP at r>0.

    VPD condenser-direct bypass (when cond_penalty_thresh > 0):
      When exhaust is nearly as dry as post-evap air (CPF < threshold),
      route exhaust directly to condenser (tiny Q_cond) and run evaporator
      on solar-heated ambient air as heat source.
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    weather_df = prepare_weather_for_simulation(cfg)
    p_atm = cfg.ambient.default_pressure_Pa

    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2, eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )

    T_absorber_prev = None
    m_w_cum = W_comp_cum_kWh = Q_cond_cum_kWh = Q_solar_cum_kWh = 0.0
    Q_solar_wasted_cum_kWh = 0.0
    Q_solar_to_evap_cum_kWh = 0.0
    W_fan_cum_kWh = 0.0
    W_fan_kW = compute_fan_power_kW(cfg)
    records = []
    final_msg = "Simulation incomplete"

    hp_cfg = HeatPumpConfig(
        refrigerant=cfg.heatpump.refrigerant,
        eta_isentropic=cfg.heatpump.eta_isentropic,
        eta_mechanical=cfg.heatpump.eta_mechanical,
        superheat_K=cfg.heatpump.superheat_K,
        subcooling_K=cfg.heatpump.subcooling_K,
        epsilon_evap=cfg.heatpump.epsilon_evap,
        epsilon_cond=cfg.heatpump.epsilon_cond,
        T_evap_min_C=cfg.heatpump.T_evap_min_C,
        T_evap_max_C=cfg.heatpump.T_evap_max_C,
        T_cond_min_C=cfg.heatpump.T_cond_min_C,
        T_cond_max_C=cfg.heatpump.T_cond_max_C,
        COP_min=cfg.heatpump.COP_min,
        pressure_ratio_max=cfg.heatpump.pressure_ratio_max,
        Q_cond_max_kW=cfg.heatpump.Q_cond_max_kW,
        Q_evap_max_kW=cfg.heatpump.Q_evap_max_kW,
        DT_evap_approach=cfg.heatpump.DT_evap_approach,
    )

    r = cfg.dryer.r_recirc

    # Exhaust tracking for recirculation
    T_exhaust_prev: Optional[float] = None
    omega_exhaust_prev: Optional[float] = None

    _tau_s = 300.0
    _alpha = dt_s / (_tau_s + dt_s)
    T_cond_C_hp = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K

    # Condenser-direct bypass state (VPD-based oscillating)
    _cond_bypass_active = False
    _cond_penalty_frac = 1.0
    _last_mode_switch_s = -1e9
    _humidity_dwell_s = 300.0
    _dm_w_total_prev = 0.0

    mode = f"closed-loop, r={r:.2f}" if r > 0 else "open-loop"
    print(f"[CONFIG C2] Solar cascade, mix AFTER solar ({mode}), "
          f"{n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m2, P_atm={p_atm/1000:.1f}kPa")

    for row in weather_df.itertuples(index=False):
        time_s = row.time_s
        T_amb_C = row.T_amb_C
        RH_amb_frac = row.RH_amb_pct / 100.0
        G_solar = row.GHI_Wm2
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac, p_atm))
        h_amb = float(moist_air_enthalpy_kJ_per_kg(T_amb_C, omega_amb))

        # ----- 1. Solar collector (always fresh ambient air) -----
        solar_state, T_absorber_prev = compute_solar_collector(
            T_in_C=T_amb_C, T_amb_C=T_amb_C, G_solar_W_per_m2=G_solar,
            m_air_kg_per_s=m_da, cfg=solar_cfg, dt_s=dt_s, T_absorber_prev_C=T_absorber_prev,
        )
        T_after_solar = solar_state.T_out_C

        bypass_mode = "none"
        T_dp_mix = 0.0
        T_evap_coil_dyn = 0.0
        r_recirc_actual = 0.0
        RH_exh_prev_pct = 0.0
        T_evap_sat = None
        T_evap_source = T_after_solar
        _flag_impossible = False
        # Air state tracking for psychrometric chart (defaults = open-loop)
        T_mix_val = T_amb_C
        omega_mix_val = omega_amb
        T_after_evap_val = T_amb_C

        # ---- Update condenser-direct bypass state (VPD-based oscillating) ----
        _cond_thresh = cfg.dryer.cond_penalty_thresh
        if _cond_thresh > 0.0 and omega_exhaust_prev is not None and r > 0:
            _cond_penalty_frac = compute_cond_penalty_est(
                omega_exhaust=omega_exhaust_prev, omega_amb=omega_amb, r=r,
                T_set_C=cfg.dryer.T_set_C,
                epsilon_evap=hp_cfg.epsilon_evap, T_evap_target_C=cfg.heatpump.T_evap_target_C,
                p_atm_Pa=p_atm,
            )
            if _cond_bypass_active:
                _target_penalty = _cond_thresh * 3.0
            else:
                _target_penalty = _cond_thresh
            _humidity_dwell_s = compute_humidity_dwell_s(
                omega_exhaust=omega_exhaust_prev, omega_amb=omega_amb, r=r,
                T_set_C=cfg.dryer.T_set_C,
                epsilon_evap=hp_cfg.epsilon_evap, T_evap_target_C=cfg.heatpump.T_evap_target_C,
                cond_penalty_now=_cond_penalty_frac,
                target_penalty=_target_penalty, dm_w_total_prev=_dm_w_total_prev,
                m_da=m_da, dt_s=dt_s, p_atm_Pa=p_atm,
            )
            _dwell_ok = (time_s - _last_mode_switch_s) >= _humidity_dwell_s
            if _cond_bypass_active:
                if _cond_penalty_frac > _cond_thresh * 3.0 and _dwell_ok:
                    _cond_bypass_active = False
                    _last_mode_switch_s = time_s
            else:
                if _cond_penalty_frac < _cond_thresh and _dwell_ok:
                    _cond_bypass_active = True
                    _last_mode_switch_s = time_s
        if omega_exhaust_prev is not None and T_exhaust_prev is not None:
            RH_exh_prev_pct = float(RH_from_T_omega(T_exhaust_prev, omega_exhaust_prev, p_atm)) * 100.0

        # ----- 2. Mixing (after solar) + bypass decision -----
        if r > 0 and T_exhaust_prev is not None:
            if _cond_bypass_active and _cond_thresh > 0.0:
                # ---- CONDENSER-DIRECT MODE ----
                # Exhaust → condenser directly (tiny Q_cond).
                # Evaporator on solar-heated ambient air (heat source only).
                T_air_in_HP = T_exhaust_prev
                omega_to_chamber = omega_exhaust_prev
                T_evap_source = T_after_solar
                bypass_mode = "cond_direct"
                T_mix_val = T_exhaust_prev
                omega_mix_val = omega_exhaust_prev
                T_after_evap_val = T_exhaust_prev
            else:
                # Solar doesn't change humidity ratio
                omega_solar = omega_amb
                # Mix solar output with exhaust at ratio r
                h_solar = float(moist_air_enthalpy_kJ_per_kg(T_after_solar, omega_solar))
                h_exh = float(moist_air_enthalpy_kJ_per_kg(T_exhaust_prev, omega_exhaust_prev))
                omega_mix = r * omega_exhaust_prev + (1.0 - r) * omega_solar
                h_mix = r * h_exh + (1.0 - r) * h_solar
                T_mix = float(temperature_from_h_omega_C(h_mix, omega_mix))

                # Saturation clamp: if mix is supersaturated, excess condenses as fog
                omega_sat_mix = float(humidity_ratio_from_T_RH(T_mix, 1.0, p_atm))
                if omega_mix > omega_sat_mix:
                    omega_mix = omega_sat_mix

                # Fixed T_evap with modulation: lower T_evap if T_mix is near coil
                _min_dt_evap = 5.0
                T_evap_sat      = cfg.heatpump.T_evap_target_C
                T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach
                if T_mix - T_evap_coil_dyn < _min_dt_evap:
                    T_evap_coil_dyn = T_mix - _min_dt_evap
                    T_evap_sat = T_evap_coil_dyn - hp_cfg.DT_evap_approach
                    T_evap_sat = max(T_evap_sat, hp_cfg.T_evap_min_C)
                    T_evap_coil_dyn = T_evap_sat + hp_cfg.DT_evap_approach

                if T_evap_sat >= T_cond_C_hp:
                    _flag_impossible = True
                    T_air_in_HP = T_mix
                    omega_to_chamber = omega_mix
                    T_evap_source = T_after_solar
                    T_evap_sat = None
                    bypass_mode = "bypass"
                    T_mix_val = T_mix
                    omega_mix_val = omega_mix
                    T_after_evap_val = T_mix
                else:
                    r_recirc_actual = r
                    T_after_evap, omega_after_evap, _ = _evaporator_dehumidify(
                        T_air_in_C=T_mix, omega_in=omega_mix,
                        T_evap_coil_C=T_evap_coil_dyn, epsilon_evap=hp_cfg.epsilon_evap,
                        p_atm_Pa=p_atm,
                    )
                    T_air_in_HP = T_after_evap
                    omega_to_chamber = omega_after_evap
                    bypass_mode = "evap"
                    T_mix_val = T_mix
                    omega_mix_val = omega_mix
                    T_after_evap_val = T_after_evap
        else:
            # Open-loop (r=0): solar heats evap source only, condenser gets ambient
            T_air_in_HP = T_amb_C              # condenser heats fresh ambient
            omega_to_chamber = omega_amb
            T_evap_source = T_after_solar      # solar boosts evap source for better COP

        # ----- 3. HP condenser heats to T_set (if needed) -----
        Q_solar_wasted_kW = 0.0
        Q_solar_to_evap_kW = 0.0
        # At r=0 the chamber stream is Amb→Cond→Chamber and solar feeds only
        # the evap-side heat source. In cond_direct mode (r>0 bypass) the
        # same parallel topology applies.
        if (r <= 0.0) or (bypass_mode == "cond_direct"):
            Q_solar_to_evap_kW = solar_state.Q_useful_kW
        if T_air_in_HP >= cfg.dryer.T_set_C:
            hp_result = None
            W_comp_kW = Q_cond_kW = 0.0
            T_to_chamber_C = cfg.dryer.T_set_C
            # Chamber air clamped to T_set: excess (typically solar in r>0 evap path) dumped.
            h_in   = float(moist_air_enthalpy_kJ_per_kg(T_air_in_HP, omega_to_chamber))
            h_set  = float(moist_air_enthalpy_kJ_per_kg(cfg.dryer.T_set_C, omega_to_chamber))
            Q_solar_wasted_kW = max(0.0, m_da * (h_in - h_set))
        elif T_evap_sat is not None:
            # Recirc+evap path: enforce HP first law
            # In C2, evaporator processes mix (T_mix, omega_mix → T_after_evap, omega_after_evap)
            h_before_evap = float(moist_air_enthalpy_kJ_per_kg(T_mix, omega_mix_val))
            h_after_evap  = float(moist_air_enthalpy_kJ_per_kg(T_air_in_HP, omega_to_chamber))
            Q_evap_air_kW = max(0.0, m_da * (h_before_evap - h_after_evap))

            T_cond_C_cycle = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            COP_now = compute_hp_COP(T_evap_sat, T_cond_C_cycle, hp_cfg)

            eta_m = hp_cfg.eta_mechanical
            if COP_now > eta_m:
                Q_cond_1st_kW = Q_evap_air_kW * COP_now / (COP_now - eta_m)
            else:
                Q_cond_1st_kW = Q_evap_air_kW

            h_in_cond     = float(moist_air_enthalpy_kJ_per_kg(T_air_in_HP, omega_to_chamber))
            h_out_cond    = float(moist_air_enthalpy_kJ_per_kg(cfg.dryer.T_set_C, omega_to_chamber))
            Q_cond_kW_req = max(0.001, m_da * (h_out_cond - h_in_cond))

            # Condenser effectiveness limit
            T_out_cond_eff = T_air_in_HP + hp_cfg.epsilon_cond * (T_cond_C_cycle - T_air_in_HP)
            h_out_cond_eff = float(moist_air_enthalpy_kJ_per_kg(T_out_cond_eff, omega_to_chamber))
            Q_cond_eff_kW  = max(0.001, m_da * (h_out_cond_eff - h_in_cond))

            Q_cond_actual_kW = min(Q_cond_1st_kW, Q_cond_kW_req, Q_cond_eff_kW)

            hp_result = compute_heat_pump_cycle(
                T_evap_C=T_evap_sat,
                T_cond_C=T_cond_C_cycle,
                Q_cond_target_kW=Q_cond_actual_kW, cfg=hp_cfg,
            )
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW

            h_to_cham = h_in_cond + hp_result.Q_cond_kW / m_da
            T_to_chamber_C = float(temperature_from_h_omega_C(h_to_cham, omega_to_chamber))
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)
        else:
            hp_result = size_heat_pump_for_air_heating(
                T_air_in_C=T_air_in_HP, T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da, T_evap_source_C=T_evap_source, cfg=hp_cfg,
                omega_in=omega_to_chamber,
            )
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW
            # Apply condenser effectiveness
            _T_cond_sat_ol = cfg.dryer.T_set_C + cfg.heatpump.T_approach_cond_K
            T_to_chamber_C = T_air_in_HP + hp_cfg.epsilon_cond * (_T_cond_sat_ol - T_air_in_HP)
            T_to_chamber_C = min(T_to_chamber_C, cfg.dryer.T_set_C)

        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))

        # ----- 4. Drying chamber -----
        reversal_s = cfg.dryer.flow_reversal_interval_min * 60.0
        if reversal_s > 0:
            reverse_flow = (int(time_s / reversal_s) % 2 == 1)
        else:
            reverse_flow = False
        flow_direction = "reverse" if reverse_flow else "forward"

        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s,
            reverse_flow=reverse_flow,
        )

        # ----- 5. Save exhaust for next step -----
        exhaust_idx = 0 if reverse_flow else (n_trays - 1)
        T_exh_raw = T_tray_out[exhaust_idx]
        omega_exh_raw = float(humidity_ratio_from_T_RH(
            T_exh_raw, min(RH_tray_out[exhaust_idx], 1.0), p_atm,
        ))
        if T_exhaust_prev is not None:
            T_exhaust_prev = _alpha * T_exh_raw + (1.0 - _alpha) * T_exhaust_prev
            omega_exhaust_prev = _alpha * omega_exh_raw + (1.0 - _alpha) * omega_exhaust_prev
        else:
            T_exhaust_prev = T_exh_raw
            omega_exhaust_prev = omega_exh_raw

        # ----- 6. Accumulate & record -----
        _dm_w_total_prev = sum(dm_w_trays)
        m_w_cum += _dm_w_total_prev
        W_comp_cum_kWh += W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        Q_solar_wasted_cum_kWh += Q_solar_wasted_kW * dt_s / 3600.0
        Q_solar_to_evap_cum_kWh += Q_solar_to_evap_kW * dt_s / 3600.0
        W_fan_cum_kWh += W_fan_kW * dt_s / 3600.0

        record = create_record(
            time_s, T_amb_C, row.RH_amb_pct, G_solar,
            solar_state.Q_useful_kW, T_after_solar, solar_state.eta_collector,
            hp_result, T_to_chamber_C, omega_to_chamber,
            T_tray_out, RH_tray_out, X_trays, MR_trays, dm_w_trays,
            m_w_cum, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh, cfg,
            W_fan_kW=W_fan_kW, W_fan_cum_kWh=W_fan_cum_kWh,
            bypass_mode=bypass_mode,
            flow_direction=flow_direction,
        )
        record["Q_solar_wasted_kW"]       = Q_solar_wasted_kW
        record["Q_solar_wasted_cum_kWh"]  = Q_solar_wasted_cum_kWh
        record["Q_solar_to_evap_kW"]      = Q_solar_to_evap_kW
        record["Q_solar_to_evap_cum_kWh"] = Q_solar_to_evap_cum_kWh
        record["T_mix_C"]           = T_mix_val
        record["omega_mix"]         = omega_mix_val
        record["T_after_evap_C"]    = T_after_evap_val
        record["T_dp_mix_C"]        = T_dp_mix
        record["T_evap_coil_C_dyn"] = T_evap_coil_dyn
        record["r_recirc_actual"]   = r_recirc_actual
        record["RH_exhaust_pct"]    = RH_exh_prev_pct
        record["cond_penalty_frac"] = _cond_penalty_frac
        record["humidity_dwell_s"]  = _humidity_dwell_s
        _T_evap_rec = hp_result.T_evap_C if hp_result is not None else (T_evap_sat if T_evap_sat is not None else 0.0)
        record["flag_frost_risk"]       = int(_T_evap_rec < 2.0)
        record["flag_outside_ac_range"] = int(_T_evap_rec < 2.0 or _T_evap_rec > 20.0)
        record["flag_impossible_cycle"] = int(_flag_impossible)
        record["flag_hp_at_capacity"]   = int(hp_result is not None and hp_result.flag_hp_at_capacity)
        record["flag_evap_oversized"]   = int(hp_result is not None and hp_result.flag_evap_oversized)
        record["flag_cond_oversized"]   = int(hp_result is not None and hp_result.flag_cond_oversized)
        _p_v_exh = (omega_exhaust_prev * p_atm / (0.622 + omega_exhaust_prev)) if omega_exhaust_prev is not None else 0.0
        _p_v_amb = omega_amb * p_atm / (0.622 + omega_amb)
        record["VPD_exhaust_Pa"] = max(0.0, p_sat_water_Pa(T_exhaust_prev) - _p_v_exh) if T_exhaust_prev is not None else 0.0
        record["VPD_ambient_Pa"] = max(0.0, p_sat_water_Pa(T_amb_C) - _p_v_amb)
        record["T_to_chamber_deficit_C"] = cfg.dryer.T_set_C - T_to_chamber_C
        records.append(record)

        if all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit reached at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"

    result_df = pd.DataFrame.from_records(records)
    result_df["SEC_elec_kWh_per_kg"] = (
        (result_df["W_comp_cum_kWh"] + result_df["W_fan_cum_kWh"])
        / result_df["m_w_cum_kg"].replace(0, float("nan"))
    )
    result_df["SMER_kg_per_kWh"] = 1.0 / result_df["SEC_elec_kWh_per_kg"]

    return SolarHPDryerResult(
        times_s=result_df["time_s"], df=result_df, config_type="CONFIG_C2",
        converged=all(x <= cfg.dryer.X_final_db + 1e-6 for tray in X_trays for x in tray),
        final_message=final_msg,
    )
