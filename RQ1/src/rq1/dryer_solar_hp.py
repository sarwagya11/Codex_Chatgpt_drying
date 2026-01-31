"""Complete solar-assisted heat pump dryer simulator - ALL 5 CONFIGS.

Integrates:
- Solar thermal collector
- Heat pump thermodynamics (CoolProp)
- Multi-tray drying chamber (10 trays)
- Phase-2 Midilli kinetics

All 5 configurations fully implemented:
- Config A: HP-only (24/7 baseline)
- Config B: Solar + HP series (solar preheat, evap source = ambient)
- Config C: Solar-assisted HP evaporator (evap source = solar-heated)
- Config D: Solar-only (passive, daytime only)
- Config E: Solar cascade (solar preheats air AND boosts evaporator source)

FIXES APPLIED:
- Weather data interpolation: Hourly PVGIS data interpolated to dt_s resolution
- Correct time tracking: Simulation time matches real weather time
- Night operation: Solar configs fall back to HP-only when GHI ≈ 0
- Config D: Limited to 72 hours max (solar-only may not finish)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
# Multi-zone simulation support (NEW)
from rq1.multizone_simulation import (
    simulate_drying_chamber_multizone,
    mix_air_streams,
    ZoneState,
)
# Import from rq1 package
from rq1.config_solar_hp import DryerConfiguration, SimulationConfig
from rq1.heatpump import HeatPumpConfig, compute_heat_pump_cycle, size_heat_pump_for_air_heating
from rq1.solar import SolarCollectorConfig, compute_solar_collector
from rq1.kinetics import compute_dm_w_kinetic_first_order, compute_dm_w_air_capacity
from rq1.psychro import (
    RH_from_T_omega,
    humidity_ratio_from_T_RH,
    moist_air_enthalpy_kJ_per_kg,
    temperature_from_h_omega_C,
    dewpoint_from_omega_C,
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

def load_weather_data(cfg: SimulationConfig) -> pd.DataFrame:
    """Load raw weather data from PVGIS CSV format.
    
    Returns hourly data with time_index representing hours.
    """
    df = pd.read_csv(cfg.ambient.csv_path)
    
    required = ["time_index", "T_amb_C", "RH_amb_pct", "GHI_Wm2"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Weather CSV missing: {missing}")
    
    start = cfg.ambient.start_index
    end = None if cfg.ambient.max_steps is None else start + cfg.ambient.max_steps
    df_subset = df.iloc[start:end].copy().reset_index(drop=True)
    
    if "pressure_Pa" not in df_subset.columns:
        df_subset["pressure_Pa"] = 101325.0
    if "wind_speed_ms" not in df_subset.columns:
        df_subset["wind_speed_ms"] = 1.0
    
    return df_subset


def interpolate_weather_to_timestep(
    weather_df: pd.DataFrame,
    dt_s: float,
    max_simulation_time_s: float,
) -> pd.DataFrame:
    """Interpolate hourly weather data to simulation timestep resolution.
    
    PVGIS data is hourly (time_index 0, 1, 2, ... = hours 0, 1, 2, ...)
    We need values at t = 0, dt_s, 2*dt_s, ... seconds
    
    Parameters
    ----------
    weather_df : pd.DataFrame
        Hourly weather data with 'time_index' in hours
    dt_s : float
        Simulation timestep in seconds (e.g., 60)
    max_simulation_time_s : float
        Maximum simulation duration in seconds
    
    Returns
    -------
    pd.DataFrame
        Interpolated weather with 'time_s' column
    """
    # Hourly time points in seconds
    # time_index is the hour number (0, 1, 2, ...)
    t_hourly_s = weather_df['time_index'].values.astype(float) * 3600.0
    
    # Maximum time available in weather data
    t_max_weather_s = t_hourly_s[-1]
    
    # Limit simulation time to available weather
    actual_max_time_s = min(max_simulation_time_s, t_max_weather_s)
    
    # Fine time points at dt_s resolution
    n_steps = int(actual_max_time_s / dt_s) + 1
    t_fine_s = np.arange(n_steps) * dt_s
    
    # Interpolate each weather variable
    df_interp = pd.DataFrame({
        'time_s': t_fine_s,
        'T_amb_C': np.interp(t_fine_s, t_hourly_s, weather_df['T_amb_C'].values),
        'RH_amb_pct': np.interp(t_fine_s, t_hourly_s, weather_df['RH_amb_pct'].values),
        'GHI_Wm2': np.interp(t_fine_s, t_hourly_s, weather_df['GHI_Wm2'].values),
    })
    
    # Optional columns
    if 'wind_speed_ms' in weather_df.columns:
        df_interp['wind_speed_ms'] = np.interp(
            t_fine_s, t_hourly_s, weather_df['wind_speed_ms'].values
        )
    else:
        df_interp['wind_speed_ms'] = 1.0
    
    if 'pressure_Pa' in weather_df.columns:
        df_interp['pressure_Pa'] = np.interp(
            t_fine_s, t_hourly_s, weather_df['pressure_Pa'].values
        )
    else:
        df_interp['pressure_Pa'] = 101325.0
    
    # Clip RH to valid range after interpolation
    df_interp['RH_amb_pct'] = df_interp['RH_amb_pct'].clip(0, 100)
    
    # Clip GHI to non-negative
    df_interp['GHI_Wm2'] = df_interp['GHI_Wm2'].clip(lower=0)
    
    return df_interp


def prepare_weather_for_simulation(
    cfg: SimulationConfig,
    max_time_override_s: float = None,
) -> pd.DataFrame:
    """Load and interpolate weather data for simulation.
    
    Parameters
    ----------
    cfg : SimulationConfig
        Simulation configuration
    max_time_override_s : float, optional
        Override max simulation time (e.g., for Config D limit)
    
    Returns
    -------
    pd.DataFrame
        Interpolated weather at dt_s resolution
    """
    weather_hourly = load_weather_data(cfg)
    
    max_sim_time = max_time_override_s if max_time_override_s else cfg.max_simulation_time_s
    dt_s = cfg.dryer.dt_s
    
    weather_interp = interpolate_weather_to_timestep(
        weather_hourly, dt_s, max_sim_time
    )
    
    print(f"[WEATHER] Loaded {len(weather_hourly)} hourly points")
    print(f"[WEATHER] Interpolated to {len(weather_interp)} points at dt={dt_s}s")
    print(f"[WEATHER] Time range: 0 to {weather_interp['time_s'].iloc[-1]/3600:.1f} hours")
    
    return weather_interp


# ==============================================================================
# DRYING CHAMBER (Common to all configs)
# ==============================================================================

def simulate_drying_chamber_single_inlet(
    T_to_chamber_C: float,
    omega_to_chamber: float,
    h_to_chamber: float,
    X_trays: List[float],
    MR_trays: List[float],
    cfg: SimulationConfig,
    time_s: float,
    m_da: float,
    dt_s: float,
) -> Tuple[List[float], List[float], List[float], List[float], List[float], List[float]]:
    """Simulate 10-tray drying chamber (common to all configs).
    
    Returns:
        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays_new, MR_trays_new
    """
    n_trays = cfg.dryer.n_trays
    m_p_tray = cfg.dryer.m_p_dry_kg / n_trays
    X_eq_db = cfg.dryer.X_eq_db
    h_fg = cfg.dryer.h_fg_kJ_per_kg
    
    T_air = T_to_chamber_C
    omega_air = omega_to_chamber
    h_air = h_to_chamber
    RH_air = float(RH_from_T_omega(T_air, omega_air))
    
    dm_w_trays = []
    T_tray_out = []
    RH_tray_out = []
    h_tray_out = []
    X_trays_new = []
    MR_trays_new = []
    
    for i in range(n_trays):
        X_j = X_trays[i]
        
        # Kinetics
        dm_w_kin = compute_dm_w_kinetic_first_order(
            X_db=X_j,
            X_eq_db=X_eq_db,
            T_in_C=T_air,
            RH_in_frac=RH_air,
            dt_s=dt_s,
            cfg=cfg.kinetics,  # type: ignore
            m_p_dry_kg=m_p_tray,
            time_s=time_s,
        )

        # Air capacity limit
        dm_w_air_max = compute_dm_w_air_capacity(
            T_in_C=T_air,
            omega_in=omega_air,
            m_da_kg_per_s=m_da,
            dt_s=dt_s,
            cfg=cfg.kinetics,  # type: ignore
            h_fg_kJ_per_kg=h_fg,
        ) if cfg.kinetics.enable_air_limit else float("inf")  # type: ignore
        
        max_removable = max(0.0, (X_j - X_eq_db) * m_p_tray)
        dm_w = min(dm_w_kin, dm_w_air_max, max_removable)
        
        # Update moisture
        dX = dm_w / m_p_tray if m_p_tray > 0 else 0.0
        X_new = max(X_j - dX, X_eq_db)
        MR_new = (X_new - X_eq_db) / (cfg.dryer.X0_db - X_eq_db) if cfg.dryer.X0_db != X_eq_db else 0.0
        
        X_trays_new.append(X_new)
        MR_trays_new.append(MR_new)
        
        # Air state after tray
        m_w_rate = dm_w / dt_s if dt_s > 0 else 0.0
        omega_out = omega_air + m_w_rate / m_da if m_da > 0 else omega_air
        
        Qdot_latent_kW = m_w_rate * h_fg
        h_out = h_air - Qdot_latent_kW / m_da if m_da > 0 else h_air
        
        T_out = float(temperature_from_h_omega_C(h_out, omega_out))
        RH_out = float(RH_from_T_omega(T_out, omega_out))
        
        if RH_out > 1.0:
            T_out = float(dewpoint_from_omega_C(omega_out))
            RH_out = 1.0
            h_out = float(moist_air_enthalpy_kJ_per_kg(T_out, omega_out))
        
        dm_w_trays.append(dm_w)
        T_tray_out.append(T_out)
        RH_tray_out.append(RH_out)
        h_tray_out.append(h_out)
        
        # Cascade to next tray
        T_air = T_out
        omega_air = omega_out
        h_air = h_out
        RH_air = RH_out
    
    return dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays_new, MR_trays_new

def simulate_drying_chamber(
    T_to_chamber_C: float,
    omega_to_chamber: float,
    h_to_chamber: float,
    X_trays: List[float],
    MR_trays: List[float],
    cfg: SimulationConfig,
    time_s: float,
    m_da: float,
    dt_s: float,
) -> tuple:
    """Simulate drying chamber - dispatches to single-inlet or multi-zone."""
    
    # Check if multi-zone is enabled
    if hasattr(cfg.dryer, 'multizone') and cfg.dryer.multizone.enabled:
        # Use multi-zone simulation
        result = simulate_drying_chamber_multizone(
            T_fresh_C=T_to_chamber_C,
            omega_fresh=omega_to_chamber,
            h_fresh=h_to_chamber,
            X_trays=X_trays,
            MR_trays=MR_trays,
            cfg=cfg,
            time_s=time_s,
            m_da_total=m_da,
            dt_s=dt_s,
        )
        return result[:6]  # First 6 elements for compatibility
    else:
        # Use original single-inlet simulation
        return simulate_drying_chamber_single_inlet(
            T_to_chamber_C=T_to_chamber_C,
            omega_to_chamber=omega_to_chamber,
            h_to_chamber=h_to_chamber,
            X_trays=X_trays,
            MR_trays=MR_trays,
            cfg=cfg,
            time_s=time_s,
            m_da=m_da,
            dt_s=dt_s,
        )

# ==============================================================================
# COMMON SETUP FUNCTION
# ==============================================================================

def setup_simulation(cfg: SimulationConfig) -> Tuple[float, float, List[float], List[float]]:
    """Common setup for all configurations.
    
    Returns:
        m_da, dt_s, X_trays, MR_trays
    """
    dt_s = cfg.dryer.dt_s
    n_trays = cfg.dryer.n_trays
    m_p_dry_total = cfg.dryer.m_p_dry_kg
    m_p_tray = m_p_dry_total / n_trays
    
    # Auto-calculate geometry
    if cfg.dryer.tray_area_m2 is None:
        rho_bulk = cfg.dryer.product_apparent_density_kg_per_m3
        thickness = cfg.dryer.product_thickness_m
        tray_area = m_p_tray / (rho_bulk * thickness)
        cfg.dryer.tray_area_m2 = tray_area
    
    # Auto-calculate air flow
    if cfg.dryer.m_da_kg_per_s <= 0:
        v_target = cfg.dryer.target_velocity_m_per_s
        m_da = cfg.dryer.air_density_kg_per_m3 * cfg.dryer.tray_area_m2 * v_target
        cfg.dryer.m_da_kg_per_s = m_da
    else:
        m_da = cfg.dryer.m_da_kg_per_s
    
    # Initialize tray states
    X_trays = [cfg.dryer.X0_db] * n_trays
    MR_trays = [1.0] * n_trays
    
    return m_da, dt_s, X_trays, MR_trays


def create_record(
    time_s: float,
    T_amb_C: float,
    RH_amb_pct: float,
    G_solar: float,
    Q_solar_kW: float,
    T_solar_out_C: float,
    eta_solar: float,
    hp_result,  # Can be None for Config D
    T_to_chamber_C: float,
    omega_to_chamber: float,
    T_tray_out: List[float],
    RH_tray_out: List[float],
    X_trays: List[float],
    MR_trays: List[float],
    dm_w_trays: List[float],
    m_w_cum: float,
    W_comp_cum_kWh: float,
    Q_cond_cum_kWh: float,
    Q_solar_cum_kWh: float,
    cfg: SimulationConfig,
) -> dict:
    """Create a record dict for the results DataFrame."""
    
    n_trays = cfg.dryer.n_trays
    X_avg = sum(X_trays) / n_trays
    MR_global = (X_avg - cfg.dryer.X_eq_db) / (cfg.dryer.X0_db - cfg.dryer.X_eq_db) \
                if cfg.dryer.X0_db != cfg.dryer.X_eq_db else 0.0
    
    # HP values (may be None/zero for Config D)
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
        W_comp_kW = 0.0
        Q_evap_kW = 0.0
        Q_cond_kW = 0.0
        COP = 0.0
        T_evap_C = 0.0
        T_cond_C = T_to_chamber_C
        P_evap_bar = 0.0
        P_cond_bar = 0.0
        m_ref = 0.0
    
    record = {
        "time_s": time_s,
        "time_h": time_s / 3600.0,
        "T_amb_C": T_amb_C,
        "RH_amb_pct": RH_amb_pct,
        "G_solar_Wm2": G_solar,
        "Q_solar_kW": Q_solar_kW,
        "T_solar_out_C": T_solar_out_C,
        "eta_solar": eta_solar,
        "T_evap_C": T_evap_C,
        "T_cond_C": T_cond_C,
        "P_evap_bar": P_evap_bar,
        "P_cond_bar": P_cond_bar,
        "W_comp_kW": W_comp_kW,
        "Q_evap_kW": Q_evap_kW,
        "Q_cond_kW": Q_cond_kW,
        "COP": COP,
        "m_ref_kg_per_s": m_ref,
        "T_to_chamber_C": T_to_chamber_C,
        "RH_to_chamber_frac": RH_from_T_omega(T_to_chamber_C, omega_to_chamber),
        "omega_to_chamber": omega_to_chamber,
        "T_exhaust_C": T_tray_out[-1],
        "RH_exhaust_frac": RH_tray_out[-1],
        "X_db_avg": X_avg,
        "MR_global": MR_global,
        "dm_w_total_kg": sum(dm_w_trays),
        "m_w_cum_kg": m_w_cum,
        "W_comp_cum_kWh": W_comp_cum_kWh,
        "Q_cond_cum_kWh": Q_cond_cum_kWh,
        "Q_solar_cum_kWh": Q_solar_cum_kWh,
    }
    
    # Per-tray data
    for i in range(n_trays):
        record[f"X_tray_{i}"] = X_trays[i]
        record[f"MR_tray_{i}"] = MR_trays[i]
        record[f"T_tray_{i}_out_C"] = T_tray_out[i]
        record[f"RH_tray_{i}_out_frac"] = RH_tray_out[i]
        record[f"dm_w_tray_{i}_kg"] = dm_w_trays[i]
    
    return record


# ==============================================================================
# MAIN DISPATCHER
# ==============================================================================

def run_solar_hp_dryer_simulation(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Main entry point - dispatches to config-specific simulator."""
    
    if cfg.config_type == DryerConfiguration.CONFIG_A:
        return simulate_config_A_HP_only(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_B:
        return simulate_config_B_solar_HP_series(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_C:
        return simulate_config_C_solar_HP_evap(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_D:
        return simulate_config_D_solar_only(cfg)
    elif cfg.config_type == DryerConfiguration.CONFIG_E:
        return simulate_config_E_cascade(cfg)
    else:
        raise ValueError(f"Unknown config: {cfg.config_type}")


# ==============================================================================
# CONFIG A: HP ONLY (Baseline)
# ==============================================================================

def simulate_config_A_HP_only(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config A: Heat pump only, 24/7.
    
    Air path: Ambient → HP Condenser → Chamber
    HP Evaporator source: Ambient air
    
    This is the baseline for comparison.
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    
    # Load and interpolate weather
    weather_df = prepare_weather_for_simulation(cfg)
    
    # Cumulative trackers
    m_w_cum = 0.0
    W_comp_cum_kWh = 0.0
    Q_cond_cum_kWh = 0.0
    Q_solar_cum_kWh = 0.0  # Always 0 for Config A
    
    records = []
    final_msg = "Simulation incomplete"
    
    print(f"[CONFIG A] HP-only, {n_trays} trays, m_da={m_da:.3f} kg/s")
    
    for row in weather_df.itertuples(index=False):
        time_s = row.time_s  # type: ignore
        T_amb_C = row.T_amb_C  # type: ignore
        RH_amb_frac = row.RH_amb_pct / 100.0  # type: ignore
        G_solar = row.GHI_Wm2  # type: ignore  # Not used, but recorded
        
        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))
        
        # Heat pump: heats air from T_amb to T_set
        hp_cfg = HeatPumpConfig(
            eta_isentropic=cfg.heatpump.eta_isentropic,
            superheat_K=cfg.heatpump.superheat_K,
            subcooling_K=cfg.heatpump.subcooling_K,
        )
        
        hp_result = size_heat_pump_for_air_heating(
            T_air_in_C=T_amb_C,
            T_air_out_target_C=cfg.dryer.T_set_C,
            m_air_kg_per_s=m_da,
            T_evap_source_C=T_amb_C,  # Evaporator uses ambient
            cfg=hp_cfg,
        )
        
        T_to_chamber_C = cfg.dryer.T_set_C
        omega_to_chamber = omega_amb
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))
        
        # Drying chamber
        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s
        )
        
        # Cumulative energy
        m_w_step = sum(dm_w_trays)
        m_w_cum += m_w_step
        W_comp_cum_kWh += hp_result.W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += hp_result.Q_cond_kW * dt_s / 3600.0
        
        # Record
        record = create_record(
            time_s=time_s,
            T_amb_C=T_amb_C,
            RH_amb_pct=row.RH_amb_pct,  # type: ignore
            G_solar=G_solar,
            Q_solar_kW=0.0,
            T_solar_out_C=T_amb_C,
            eta_solar=0.0,
            hp_result=hp_result,
            T_to_chamber_C=T_to_chamber_C,
            omega_to_chamber=omega_to_chamber,
            T_tray_out=T_tray_out,
            RH_tray_out=RH_tray_out,
            X_trays=X_trays,
            MR_trays=MR_trays,
            dm_w_trays=dm_w_trays,
            m_w_cum=m_w_cum,
            W_comp_cum_kWh=W_comp_cum_kWh,
            Q_cond_cum_kWh=Q_cond_cum_kWh,
            Q_solar_cum_kWh=Q_solar_cum_kWh,
            cfg=cfg,
        )
        records.append(record)
        
        # Stop criterion: all trays dry
        if all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        
        # Time limit
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"
    
    result_df = pd.DataFrame.from_records(records)
    
    # Calculate SEC
    if m_w_cum > 0:
        SEC_elec = W_comp_cum_kWh / m_w_cum
        result_df.loc[result_df.index[-1], "SEC_elec_kWh_per_kg"] = SEC_elec
    
    return SolarHPDryerResult(
        times_s=result_df["time_s"],
        df=result_df,
        config_type="CONFIG_A",
        converged=all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG B: SOLAR + HP SERIES
# ==============================================================================

def simulate_config_B_solar_HP_series(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config B: Solar preheats air, HP boosts to T_set if needed.
    
    Air path: Ambient → Solar Collector → HP Condenser → Chamber
    HP Evaporator source: Ambient air (separate stream)
    
    Benefits:
    - Solar reduces HP condenser load (smaller ΔT needed)
    - If T_solar >= T_set, HP is bypassed entirely
    - At night, falls back to Config A behavior
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    
    # Load and interpolate weather
    weather_df = prepare_weather_for_simulation(cfg)
    
    # Solar collector config
    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2,
        eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )
    
    # State variables
    T_absorber_prev = None
    m_w_cum = 0.0
    W_comp_cum_kWh = 0.0
    Q_cond_cum_kWh = 0.0
    Q_solar_cum_kWh = 0.0
    
    records = []
    final_msg = "Simulation incomplete"
    
    print(f"[CONFIG B] Solar+HP series, {n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m²")
    
    for row in weather_df.itertuples(index=False):
        time_s = row.time_s  # type: ignore
        T_amb_C = row.T_amb_C  # type: ignore
        RH_amb_frac = row.RH_amb_pct / 100.0  # type: ignore
        G_solar = row.GHI_Wm2  # type: ignore

        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))

        # Solar collector: heats air from T_amb
        solar_state, T_absorber_prev = compute_solar_collector(
            T_in_C=T_amb_C,
            T_amb_C=T_amb_C,
            G_solar_W_per_m2=G_solar,
            m_air_kg_per_s=m_da,
            cfg=solar_cfg,
            dt_s=dt_s,
            T_absorber_prev_C=T_absorber_prev,
        )
        
        T_after_solar = solar_state.T_out_C
        omega_after_solar = omega_amb  # Humidity unchanged through solar collector
        
        # Decide HP operation
        if T_after_solar >= cfg.dryer.T_set_C:
            # Solar sufficient - bypass HP
            hp_result = None
            W_comp_kW = 0.0
            Q_cond_kW = 0.0
            T_to_chamber_C = T_after_solar  # May exceed T_set slightly
        else:
            # HP boosts from T_after_solar to T_set
            hp_cfg = HeatPumpConfig(
                eta_isentropic=cfg.heatpump.eta_isentropic,
                superheat_K=cfg.heatpump.superheat_K,
                subcooling_K=cfg.heatpump.subcooling_K,
            )
            
            hp_result = size_heat_pump_for_air_heating(
                T_air_in_C=T_after_solar,  # Air enters HP already warmed by solar
                T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da,
                T_evap_source_C=T_amb_C,  # Evaporator uses ambient (not solar-heated)
                cfg=hp_cfg,
            )
            
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW
            T_to_chamber_C = cfg.dryer.T_set_C
        
        omega_to_chamber = omega_after_solar
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))
        
        # Drying chamber
        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s
        )
        
        # Cumulative energy
        m_w_step = sum(dm_w_trays)
        m_w_cum += m_w_step
        W_comp_cum_kWh += W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        
        # Record
        record = create_record(
            time_s=time_s,
            T_amb_C=T_amb_C,
            RH_amb_pct=row.RH_amb_pct,  # type: ignore
            G_solar=G_solar,
            Q_solar_kW=solar_state.Q_useful_kW,
            T_solar_out_C=T_after_solar,
            eta_solar=solar_state.eta_collector,
            hp_result=hp_result,
            T_to_chamber_C=T_to_chamber_C,
            omega_to_chamber=omega_to_chamber,
            T_tray_out=T_tray_out,
            RH_tray_out=RH_tray_out,
            X_trays=X_trays,
            MR_trays=MR_trays,
            dm_w_trays=dm_w_trays,
            m_w_cum=m_w_cum,
            W_comp_cum_kWh=W_comp_cum_kWh,
            Q_cond_cum_kWh=Q_cond_cum_kWh,
            Q_solar_cum_kWh=Q_solar_cum_kWh,
            cfg=cfg,
        )
        records.append(record)
        
        # Stop criterion
        if all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"
    
    result_df = pd.DataFrame.from_records(records)
    
    if m_w_cum > 0:
        SEC_elec = W_comp_cum_kWh / m_w_cum
        result_df.loc[result_df.index[-1], "SEC_elec_kWh_per_kg"] = SEC_elec
    
    return SolarHPDryerResult(
        times_s=result_df["time_s"],
        df=result_df,
        config_type="CONFIG_B",
        converged=all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG C: SOLAR-ASSISTED HP EVAPORATOR
# ==============================================================================

def simulate_config_C_solar_HP_evap(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config C: Solar heats evaporator source for higher COP.
    
    Air path: Ambient → HP Condenser → Chamber (same as Config A)
    HP Evaporator source: Solar-heated air (higher T_evap → higher COP)
    
    Benefits:
    - Higher COP due to warmer evaporator source
    - Same heating load as Config A, but less electricity
    - At night, falls back to Config A behavior (evap source = T_amb)
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    
    # Load and interpolate weather
    weather_df = prepare_weather_for_simulation(cfg)
    
    # Solar collector config (used for evaporator source heating)
    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2,
        eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )
    
    # State variables
    T_absorber_prev = None
    m_w_cum = 0.0
    W_comp_cum_kWh = 0.0
    Q_cond_cum_kWh = 0.0
    Q_solar_cum_kWh = 0.0
    
    records = []
    final_msg = "Simulation incomplete"
    
    print(f"[CONFIG C] Solar-assisted HP evaporator, {n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m²")
    
    for row in weather_df.itertuples(index=False):
        time_s = row.time_s  # type: ignore
        T_amb_C = row.T_amb_C  # type: ignore
        RH_amb_frac = row.RH_amb_pct / 100.0  # type: ignore
        G_solar = row.GHI_Wm2  # type: ignore

        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))

        # Solar collector heats air for evaporator source
        solar_state, T_absorber_prev = compute_solar_collector(
            T_in_C=T_amb_C,
            T_amb_C=T_amb_C,
            G_solar_W_per_m2=G_solar,
            m_air_kg_per_s=m_da,  # Assume similar flow for evap source
            cfg=solar_cfg,
            dt_s=dt_s,
            T_absorber_prev_C=T_absorber_prev,
        )
        
        T_evap_source = solar_state.T_out_C  # Solar-heated evaporator source
        
        # Heat pump with warmer evaporator source
        hp_cfg = HeatPumpConfig(
            eta_isentropic=cfg.heatpump.eta_isentropic,
            superheat_K=cfg.heatpump.superheat_K,
            subcooling_K=cfg.heatpump.subcooling_K,
        )
        
        hp_result = size_heat_pump_for_air_heating(
            T_air_in_C=T_amb_C,  # Drying air enters HP condenser at AMBIENT
            T_air_out_target_C=cfg.dryer.T_set_C,
            m_air_kg_per_s=m_da,
            T_evap_source_C=T_evap_source,  # Evaporator uses SOLAR-heated source
            cfg=hp_cfg,
        )
        
        # Higher T_evap_source → Higher COP → Lower W_comp for same Q_cond
        
        T_to_chamber_C = cfg.dryer.T_set_C
        omega_to_chamber = omega_amb
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))
        
        # Drying chamber
        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s
        )
        
        # Cumulative energy
        m_w_step = sum(dm_w_trays)
        m_w_cum += m_w_step
        W_comp_cum_kWh += hp_result.W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += hp_result.Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        
        # Record
        record = create_record(
            time_s=time_s,
            T_amb_C=T_amb_C,
            RH_amb_pct=row.RH_amb_pct,  # type: ignore
            G_solar=G_solar,
            Q_solar_kW=solar_state.Q_useful_kW,
            T_solar_out_C=T_evap_source,
            eta_solar=solar_state.eta_collector,
            hp_result=hp_result,
            T_to_chamber_C=T_to_chamber_C,
            omega_to_chamber=omega_to_chamber,
            T_tray_out=T_tray_out,
            RH_tray_out=RH_tray_out,
            X_trays=X_trays,
            MR_trays=MR_trays,
            dm_w_trays=dm_w_trays,
            m_w_cum=m_w_cum,
            W_comp_cum_kWh=W_comp_cum_kWh,
            Q_cond_cum_kWh=Q_cond_cum_kWh,
            Q_solar_cum_kWh=Q_solar_cum_kWh,
            cfg=cfg,
        )
        records.append(record)
        
        # Stop criterion
        if all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"
    
    result_df = pd.DataFrame.from_records(records)
    
    if m_w_cum > 0:
        SEC_elec = W_comp_cum_kWh / m_w_cum
        result_df.loc[result_df.index[-1], "SEC_elec_kWh_per_kg"] = SEC_elec
    
    return SolarHPDryerResult(
        times_s=result_df["time_s"],
        df=result_df,
        config_type="CONFIG_C",
        converged=all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG D: SOLAR ONLY
# ==============================================================================

def simulate_config_D_solar_only(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config D: Solar only, no heat pump.
    
    Air path: Ambient → Solar Collector → Chamber
    No HP: W_comp = 0 always
    
    Characteristics:
    - 100% renewable operation
    - Variable chamber temperature (depends on irradiance)
    - At night: T_chamber ≈ T_amb (minimal drying)
    - Much longer drying time (may not complete in 72h)
    
    Limited to 72 hours maximum.
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    
    # Config D limit: 72 hours max (3 days)
    CONFIG_D_MAX_TIME_S = 72 * 3600.0
    max_time_s = min(cfg.max_simulation_time_s, CONFIG_D_MAX_TIME_S)
    
    # Load and interpolate weather with Config D limit
    weather_df = prepare_weather_for_simulation(cfg, max_time_override_s=max_time_s)
    
    # Solar collector config
    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2,
        eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )
    
    # State variables
    T_absorber_prev = None
    m_w_cum = 0.0
    W_comp_cum_kWh = 0.0  # Always 0 for Config D
    Q_cond_cum_kWh = 0.0  # Always 0 for Config D
    Q_solar_cum_kWh = 0.0
    
    records = []
    final_msg = "Simulation incomplete"
    
    print(f"[CONFIG D] Solar-only, {n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m²")
    print(f"[WARNING] Config D limited to {max_time_s/3600:.0f}h - may not complete drying")
    
    for row in weather_df.itertuples(index=False):
        time_s = row.time_s  # type: ignore
        T_amb_C = row.T_amb_C  # type: ignore
        RH_amb_frac = row.RH_amb_pct / 100.0  # type: ignore
        G_solar = row.GHI_Wm2  # type: ignore

        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))

        # Solar collector is the ONLY heat source
        solar_state, T_absorber_prev = compute_solar_collector(
            T_in_C=T_amb_C,
            T_amb_C=T_amb_C,
            G_solar_W_per_m2=G_solar,
            m_air_kg_per_s=m_da,
            cfg=solar_cfg,
            dt_s=dt_s,
            T_absorber_prev_C=T_absorber_prev,
        )
        
        # Chamber temperature is whatever solar provides (no HP boost!)
        T_to_chamber_C = solar_state.T_out_C  # Variable, may be < T_set
        omega_to_chamber = omega_amb
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))
        
        # Drying chamber (slower drying when T_to_chamber < T_set)
        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s
        )
        
        # Cumulative energy (no electricity!)
        m_w_step = sum(dm_w_trays)
        m_w_cum += m_w_step
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        
        # Record
        record = create_record(
            time_s=time_s,
            T_amb_C=T_amb_C,
            RH_amb_pct=row.RH_amb_pct,  # type: ignore
            G_solar=G_solar,
            Q_solar_kW=solar_state.Q_useful_kW,
            T_solar_out_C=T_to_chamber_C,
            eta_solar=solar_state.eta_collector,
            hp_result=None,  # No HP
            T_to_chamber_C=T_to_chamber_C,
            omega_to_chamber=omega_to_chamber,
            T_tray_out=T_tray_out,
            RH_tray_out=RH_tray_out,
            X_trays=X_trays,
            MR_trays=MR_trays,
            dm_w_trays=dm_w_trays,
            m_w_cum=m_w_cum,
            W_comp_cum_kWh=W_comp_cum_kWh,
            Q_cond_cum_kWh=Q_cond_cum_kWh,
            Q_solar_cum_kWh=Q_solar_cum_kWh,
            cfg=cfg,
        )
        records.append(record)
        
        # Stop criterion
        if all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        
        if time_s >= max_time_s:
            final_msg = f"Config D time limit ({max_time_s/3600:.0f}h) - may not be fully dry"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"
    
    result_df = pd.DataFrame.from_records(records)
    
    # SEC is technically infinite (0 electricity) but we record 0
    if m_w_cum > 0:
        result_df.loc[result_df.index[-1], "SEC_elec_kWh_per_kg"] = 0.0
    
    return SolarHPDryerResult(
        times_s=result_df["time_s"],
        df=result_df,
        config_type="CONFIG_D",
        converged=all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays),
        final_message=final_msg,
    )


# ==============================================================================
# CONFIG E: SOLAR CASCADE (Your Innovative Design)
# ==============================================================================

def simulate_config_E_cascade(cfg: SimulationConfig) -> SolarHPDryerResult:
    """Config E: Solar cascade - both air preheat AND evaporator boost.
    
    Air path: Ambient → Solar Collector → HP Condenser → Chamber
    HP Evaporator source: Solar-heated air (same collector)
    
    This combines benefits of Config B and Config C:
    - Solar preheats air (reduces HP condenser load like Config B)
    - Solar-heated source for evaporator (higher COP like Config C)
    
    Expected to be the most efficient configuration (lowest SEC).
    At night, falls back to Config A behavior.
    """
    m_da, dt_s, X_trays, MR_trays = setup_simulation(cfg)
    n_trays = cfg.dryer.n_trays
    
    # Load and interpolate weather
    weather_df = prepare_weather_for_simulation(cfg)
    
    # Solar collector config
    solar_cfg = SolarCollectorConfig(
        area_m2=cfg.solar.area_m2,
        eta_optical=cfg.solar.eta_optical,
        U_loss_W_per_m2K=cfg.solar.U_loss_W_per_m2K,
    )
    
    # State variables
    T_absorber_prev = None
    m_w_cum = 0.0
    W_comp_cum_kWh = 0.0
    Q_cond_cum_kWh = 0.0
    Q_solar_cum_kWh = 0.0
    
    records = []
    final_msg = "Simulation incomplete"
    
    print(f"[CONFIG E] Solar cascade (preheat + evap boost), {n_trays} trays, A_solar={cfg.solar.area_m2:.1f}m²")
    
    for row in weather_df.itertuples(index=False):
        time_s = row.time_s  # type: ignore
        T_amb_C = row.T_amb_C  # type: ignore
        RH_amb_frac = row.RH_amb_pct / 100.0  # type: ignore
        G_solar = row.GHI_Wm2  # type: ignore

        omega_amb = float(humidity_ratio_from_T_RH(T_amb_C, RH_amb_frac))

        # Solar collector heats ambient air
        solar_state, T_absorber_prev = compute_solar_collector(
            T_in_C=T_amb_C,
            T_amb_C=T_amb_C,
            G_solar_W_per_m2=G_solar,
            m_air_kg_per_s=m_da,
            cfg=solar_cfg,
            dt_s=dt_s,
            T_absorber_prev_C=T_absorber_prev,
        )
        
        T_after_solar = solar_state.T_out_C
        omega_after_solar = omega_amb
        
        # Decide HP operation
        if T_after_solar >= cfg.dryer.T_set_C:
            # Solar sufficient - bypass HP entirely
            hp_result = None
            W_comp_kW = 0.0
            Q_cond_kW = 0.0
            T_to_chamber_C = T_after_solar
        else:
            # HP boosts from T_after_solar to T_set
            # BOTH benefits:
            # 1. Air enters condenser at T_after_solar (less ΔT needed)
            # 2. Evaporator source is T_after_solar (higher COP)
            hp_cfg = HeatPumpConfig(
                eta_isentropic=cfg.heatpump.eta_isentropic,
                superheat_K=cfg.heatpump.superheat_K,
                subcooling_K=cfg.heatpump.subcooling_K,
            )
            
            hp_result = size_heat_pump_for_air_heating(
                T_air_in_C=T_after_solar,  # Air preheated by solar
                T_air_out_target_C=cfg.dryer.T_set_C,
                m_air_kg_per_s=m_da,
                T_evap_source_C=T_after_solar,  # Evaporator also uses solar-heated source
                cfg=hp_cfg,
            )
            
            W_comp_kW = hp_result.W_comp_kW
            Q_cond_kW = hp_result.Q_cond_kW
            T_to_chamber_C = cfg.dryer.T_set_C
        
        omega_to_chamber = omega_after_solar
        h_to_chamber = float(moist_air_enthalpy_kJ_per_kg(T_to_chamber_C, omega_to_chamber))
        
        # Drying chamber
        dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays, MR_trays = simulate_drying_chamber(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s
        )
        
        # Cumulative energy
        m_w_step = sum(dm_w_trays)
        m_w_cum += m_w_step
        W_comp_cum_kWh += W_comp_kW * dt_s / 3600.0
        Q_cond_cum_kWh += Q_cond_kW * dt_s / 3600.0
        Q_solar_cum_kWh += solar_state.Q_useful_kW * dt_s / 3600.0
        
        # Record
        record = create_record(
            time_s=time_s,
            T_amb_C=T_amb_C,
            RH_amb_pct=row.RH_amb_pct,  # type: ignore
            G_solar=G_solar,
            Q_solar_kW=solar_state.Q_useful_kW,
            T_solar_out_C=T_after_solar,
            eta_solar=solar_state.eta_collector,
            hp_result=hp_result,
            T_to_chamber_C=T_to_chamber_C,
            omega_to_chamber=omega_to_chamber,
            T_tray_out=T_tray_out,
            RH_tray_out=RH_tray_out,
            X_trays=X_trays,
            MR_trays=MR_trays,
            dm_w_trays=dm_w_trays,
            m_w_cum=m_w_cum,
            W_comp_cum_kWh=W_comp_cum_kWh,
            Q_cond_cum_kWh=Q_cond_cum_kWh,
            Q_solar_cum_kWh=Q_solar_cum_kWh,
            cfg=cfg,
        )
        records.append(record)
        
        # Stop criterion
        if all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays):
            final_msg = f"All trays dry at t={time_s/3600:.1f}h"
            break
        
        if time_s >= cfg.max_simulation_time_s:
            final_msg = f"Time limit at t={time_s/3600:.1f}h"
            break
    else:
        final_msg = f"Weather data exhausted at t={time_s/3600:.1f}h"
    
    result_df = pd.DataFrame.from_records(records)
    
    if m_w_cum > 0:
        SEC_elec = W_comp_cum_kWh / m_w_cum
        result_df.loc[result_df.index[-1], "SEC_elec_kWh_per_kg"] = SEC_elec
    
    return SolarHPDryerResult(
        times_s=result_df["time_s"],
        df=result_df,
        config_type="CONFIG_E",
        converged=all(X <= cfg.dryer.X_final_db + 1e-6 for X in X_trays),
        final_message=final_msg,
    )