"""
Multi-Zone Drying Chamber Simulation Module
============================================

This module provides the simulation functions for multi-zone drying
with fresh air injection at zone boundaries.

NEW FILE - Add this to your rq1/ folder as: multizone_simulation.py

The key physics:
1. Air is split at the inlet and distributed to multiple zones
2. At zone boundaries, upstream exhaust MIXES with fresh injected air
3. Each zone processes its trays with the mixed air conditions
4. Mixing uses mass-weighted averaging (perfect mixing assumption)

Author: Wasti (SAHPD Thesis)
Date: January 2026
"""

from __future__ import annotations

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

# Import psychrometric functions from your existing module
from rq1.psychro import (
    RH_from_T_omega,
    temperature_from_h_omega_C,
    dewpoint_from_omega_C,
    moist_air_enthalpy_kJ_per_kg,
)

# Import kinetics functions from your existing module
from rq1.kinetics import (
    compute_dm_w_kinetic_first_order,
    compute_dm_w_air_capacity,
)

# Import chamber geometry classes
from rq1.chamber_geometry import ZoneConfig, MultiZoneConfig, ChamberGeometry


# =============================================================================
# AIR MIXING FUNCTION
# =============================================================================

def mix_air_streams(
    m1: float, T1: float, omega1: float, h1: float,
    m2: float, T2: float, omega2: float, h2: float,
    mixing_efficiency: float = 1.0
) -> Tuple[float, float, float, float, float]:
    """
    Mix two air streams using mass-weighted averaging.
    
    This implements the perfect mixing assumption, which is justified by:
    - Turbulent flow regime (Re ≈ 7000)
    - Adequate mixing length in the chamber
    - Standard practice in lumped-parameter dryer models
    
    The mixing equations are:
    
        ω_mix = (ṁ₁ × ω₁ + ṁ₂ × ω₂) / (ṁ₁ + ṁ₂)
        h_mix = (ṁ₁ × h₁ + ṁ₂ × h₂) / (ṁ₁ + ṁ₂)
        T_mix = f(h_mix, ω_mix)  [from psychrometrics]
    
    Parameters:
        m1: Mass flow rate of stream 1 [kg/s]
        T1: Temperature of stream 1 [°C]
        omega1: Humidity ratio of stream 1 [kg water/kg dry air]
        h1: Enthalpy of stream 1 [kJ/kg dry air]
        m2: Mass flow rate of stream 2 [kg/s]
        T2: Temperature of stream 2 [°C]
        omega2: Humidity ratio of stream 2 [kg water/kg dry air]
        h2: Enthalpy of stream 2 [kJ/kg dry air]
        mixing_efficiency: Mixing efficiency (1.0 = perfect mixing)
                          Values < 1.0 represent partial mixing
    
    Returns:
        Tuple of (m_mix, T_mix, omega_mix, h_mix, RH_mix):
            m_mix: Combined mass flow rate [kg/s]
            T_mix: Mixed temperature [°C]
            omega_mix: Mixed humidity ratio [kg/kg]
            h_mix: Mixed enthalpy [kJ/kg]
            RH_mix: Mixed relative humidity [fraction]
    
    Physical interpretation:
        Stream 1 is typically the upstream exhaust (humid, cooler)
        Stream 2 is typically the fresh injection (dry, hot)
        The mixed stream has intermediate properties
    """
    
    m_total = m1 + m2
    
    # Handle edge case of zero flow
    if m_total <= 1e-10:
        return (0.0, T1, omega1, h1, 0.0)
    
    # Mass-weighted mixing (perfect mixing equations)
    # These are exact for ideal gas mixtures
    omega_mix = (m1 * omega1 + m2 * omega2) / m_total
    h_mix = (m1 * h1 + m2 * h2) / m_total
    
    # For partial mixing (efficiency < 1.0), we could model non-uniformity
    # However, for time-averaged drying, the average values are sufficient
    # The mixing_efficiency parameter is included for sensitivity analysis
    if mixing_efficiency < 1.0:
        # Partial mixing: mixture properties move partially toward perfect mix
        # omega_partial = omega1 + efficiency * (omega_perfect - omega1)
        # This is a simplified model; actual partial mixing is more complex
        omega_weighted = (m1 * omega1 + m2 * omega2) / m_total
        h_weighted = (m1 * h1 + m2 * h2) / m_total
        
        # Dominant stream properties (for partial mixing model)
        if m1 >= m2:
            omega_dominant, h_dominant = omega1, h1
        else:
            omega_dominant, h_dominant = omega2, h2
        
        omega_mix = omega_dominant + mixing_efficiency * (omega_weighted - omega_dominant)
        h_mix = h_dominant + mixing_efficiency * (h_weighted - h_dominant)
    
    # Calculate temperature from enthalpy and humidity ratio
    # Using psychrometric relationship: h = cp_a*T + omega*(hg + cp_v*T)
    T_mix = float(temperature_from_h_omega_C(h_mix, omega_mix))
    
    # Calculate relative humidity at mixed conditions
    RH_mix = float(RH_from_T_omega(T_mix, omega_mix))
    
    # Clamp RH to physical limits
    RH_mix = max(0.0, min(1.0, RH_mix))
    
    return (m_total, T_mix, omega_mix, h_mix, RH_mix)


# =============================================================================
# ZONE STATE TRACKING
# =============================================================================

@dataclass
class ZoneState:
    """State of air at zone inlet and outlet.
    
    Used for tracking and diagnostics.
    """
    zone_name: str
    
    # Inlet conditions (after mixing)
    T_inlet_C: float
    RH_inlet_frac: float
    omega_inlet: float
    h_inlet: float
    m_da_inlet: float  # Mass flow through this zone
    
    # Outlet conditions (after passing through trays)
    T_outlet_C: float
    RH_outlet_frac: float
    omega_outlet: float
    h_outlet: float
    
    # Zone performance
    dm_w_zone_kg: float  # Total water removed in this zone
    n_trays: int


# =============================================================================
# MULTI-ZONE CHAMBER SIMULATION
# =============================================================================

def simulate_drying_chamber_multizone(
    T_fresh_C: float,
    omega_fresh: float,
    h_fresh: float,
    X_trays: List[float],
    MR_trays: List[float],
    cfg,  # SimulationConfig - using duck typing to avoid circular imports
    time_s: float,
    m_da_total: float,
    dt_s: float,
) -> Tuple[List[float], List[float], List[float], List[float], 
           List[float], List[float], Optional[List[ZoneState]]]:
    """
    Simulate multi-zone drying chamber with fresh air injection.
    
    This function implements the multi-zone design where:
    1. Total air flow is split into fractions directed to each zone
    2. Each zone receives: (upstream exhaust) + (fresh injection)
    3. Mixed air passes through the zone's trays in series
    4. Zone exhaust becomes input for next zone's mixing
    
    The air flow pattern:
    
        Heat Pump Output (T_fresh, ω_fresh)
              │
              ├──── 40% ────► Zone A (Trays 0-3) ──┐
              │                                     │ Exhaust A
              ├──── 30% ────► MIXING ◄─────────────┘
              │                  │
              │                  └──► Zone B (Trays 4-6) ──┐
              │                                             │ Exhaust B
              └──── 30% ────► MIXING ◄─────────────────────┘
                                 │
                                 └──► Zone C (Trays 7-9)
                                              │
                                              ▼
                                         EXHAUST
    
    Parameters:
        T_fresh_C: Temperature of fresh air from heat pump condenser [°C]
        omega_fresh: Humidity ratio of fresh air [kg water/kg dry air]
        h_fresh: Enthalpy of fresh air [kJ/kg dry air]
        X_trays: Current moisture content of each tray [kg water/kg dry solid]
        MR_trays: Current moisture ratio of each tray [-]
        cfg: SimulationConfig object containing all configuration
        time_s: Current simulation time [s]
        m_da_total: Total dry air mass flow rate [kg/s]
        dt_s: Time step [s]
    
    Returns:
        Tuple containing:
            dm_w_trays: Water removed from each tray [kg]
            T_tray_out: Air temperature after each tray [°C]
            RH_tray_out: Air RH after each tray [fraction]
            h_tray_out: Air enthalpy after each tray [kJ/kg]
            X_trays_new: Updated moisture content of each tray [kg/kg db]
            MR_trays_new: Updated moisture ratio of each tray [-]
            zone_states: Optional list of ZoneState for diagnostics
    """
    
    # Get configuration parameters
    n_trays = cfg.dryer.n_trays
    m_p_tray = cfg.dryer.m_p_dry_kg / n_trays  # Dry mass per tray
    X_eq_db = cfg.dryer.X_eq_db
    h_fg = cfg.dryer.h_fg_kJ_per_kg
    
    # Get zone configuration
    zones = cfg.dryer.multizone.zones
    mixing_eff = cfg.dryer.multizone.mixing_efficiency
    
    # Initialize output lists (will be reordered at end)
    dm_w_list = []
    T_out_list = []
    RH_out_list = []
    h_out_list = []
    X_new_list = []
    MR_new_list = []
    zone_states = []
    
    # Track upstream exhaust for mixing
    # For first zone, there is no upstream (only fresh air)
    m_upstream = 0.0
    T_upstream = T_fresh_C
    omega_upstream = omega_fresh
    h_upstream = h_fresh
    
    # Process each zone in sequence
    for zone in zones:
        
        # Calculate fresh air flow to this zone
        m_fresh_zone = m_da_total * zone.flow_fraction
        
        # =====================================================================
        # MIX UPSTREAM EXHAUST WITH FRESH INJECTION
        # =====================================================================
        if zone.receives_upstream_exhaust and m_upstream > 0:
            # Mix upstream exhaust with fresh injection
            m_zone, T_zone, omega_zone, h_zone, RH_zone = mix_air_streams(
                m1=m_upstream,
                T1=T_upstream,
                omega1=omega_upstream,
                h1=h_upstream,
                m2=m_fresh_zone,
                T2=T_fresh_C,
                omega2=omega_fresh,
                h2=h_fresh,
                mixing_efficiency=mixing_eff
            )
        else:
            # First zone - only fresh air, no mixing
            m_zone = m_fresh_zone
            T_zone = T_fresh_C
            omega_zone = omega_fresh
            h_zone = h_fresh
            RH_zone = float(RH_from_T_omega(T_zone, omega_zone))
        
        # Store inlet conditions for diagnostics
        T_inlet = T_zone
        RH_inlet = RH_zone
        omega_inlet = omega_zone
        h_inlet = h_zone
        
        # =====================================================================
        # PROCESS TRAYS IN THIS ZONE (air flows through in series)
        # =====================================================================
        T_air = T_zone
        omega_air = omega_zone
        h_air = h_zone
        RH_air = RH_zone
        dm_w_zone_total = 0.0
        
        for i in zone.tray_indices:
            X_j = X_trays[i]
            
            # -----------------------------------------------------------------
            # DRYING KINETICS: Calculate mass transfer rate
            # -----------------------------------------------------------------
            dm_w_kin = compute_dm_w_kinetic_first_order(
                X_db=X_j,
                X_eq_db=X_eq_db,
                T_in_C=T_air,
                RH_in_frac=RH_air,
                dt_s=dt_s,
                cfg=cfg.kinetics,
                m_p_dry_kg=m_p_tray,
                time_s=time_s,
            )
            
            # -----------------------------------------------------------------
            # AIR CAPACITY LIMIT: Maximum water the air can carry
            # -----------------------------------------------------------------
            if cfg.kinetics.enable_air_limit:
                dm_w_air_max = compute_dm_w_air_capacity(
                    T_in_C=T_air,
                    omega_in=omega_air,
                    m_da_kg_per_s=m_zone,  # Use zone flow rate
                    dt_s=dt_s,
                    cfg=cfg.kinetics,
                    h_fg_kJ_per_kg=h_fg,
                )
            else:
                dm_w_air_max = float("inf")
            
            # -----------------------------------------------------------------
            # ACTUAL WATER REMOVAL: Minimum of kinetics, air limit, available
            # -----------------------------------------------------------------
            max_removable = max(0.0, (X_j - X_eq_db) * m_p_tray)
            dm_w = min(dm_w_kin, dm_w_air_max, max_removable)
            dm_w_zone_total += dm_w
            
            # -----------------------------------------------------------------
            # UPDATE MOISTURE CONTENT
            # -----------------------------------------------------------------
            dX = dm_w / m_p_tray if m_p_tray > 0 else 0.0
            X_new = max(X_j - dX, X_eq_db)
            
            # Calculate moisture ratio
            if cfg.dryer.X0_db != X_eq_db:
                MR_new = (X_new - X_eq_db) / (cfg.dryer.X0_db - X_eq_db)
            else:
                MR_new = 0.0
            
            X_new_list.append(X_new)
            MR_new_list.append(MR_new)
            
            # -----------------------------------------------------------------
            # UPDATE AIR STATE AFTER TRAY
            # -----------------------------------------------------------------
            # Mass rate of water evaporation
            m_w_rate = dm_w / dt_s if dt_s > 0 else 0.0
            
            # New humidity ratio (water added to air)
            omega_out = omega_air + m_w_rate / m_zone if m_zone > 0 else omega_air
            
            # Enthalpy change (latent heat absorbed from air)
            # Using non-adiabatic model: sensible heat provides latent heat
            Qdot_latent_kW = m_w_rate * h_fg
            h_out = h_air - Qdot_latent_kW / m_zone if m_zone > 0 else h_air
            
            # Temperature from psychrometrics
            T_out = float(temperature_from_h_omega_C(h_out, omega_out))
            RH_out = float(RH_from_T_omega(T_out, omega_out))
            
            # Saturation check - air cannot exceed 100% RH
            if RH_out > 1.0:
                T_out = float(dewpoint_from_omega_C(omega_out))
                RH_out = 1.0
                h_out = float(moist_air_enthalpy_kJ_per_kg(T_out, omega_out))
            
            # Store results
            dm_w_list.append(dm_w)
            T_out_list.append(T_out)
            RH_out_list.append(RH_out)
            h_out_list.append(h_out)
            
            # Cascade air state to next tray
            T_air = T_out
            omega_air = omega_out
            h_air = h_out
            RH_air = RH_out
        
        # =====================================================================
        # STORE ZONE STATE FOR DIAGNOSTICS
        # =====================================================================
        zone_states.append(ZoneState(
            zone_name=zone.name,
            T_inlet_C=T_inlet,
            RH_inlet_frac=RH_inlet,
            omega_inlet=omega_inlet,
            h_inlet=h_inlet,
            m_da_inlet=m_zone,
            T_outlet_C=T_air,
            RH_outlet_frac=RH_air,
            omega_outlet=omega_air,
            h_outlet=h_air,
            dm_w_zone_kg=dm_w_zone_total,
            n_trays=len(zone.tray_indices),
        ))
        
        # =====================================================================
        # THIS ZONE'S EXHAUST BECOMES NEXT ZONE'S UPSTREAM
        # =====================================================================
        m_upstream = m_zone
        T_upstream = T_air
        omega_upstream = omega_air
        h_upstream = h_air
    
    # =========================================================================
    # REORDER OUTPUTS TO MATCH TRAY INDICES
    # =========================================================================
    # The outputs are currently in zone-order, need to reorder by tray index
    
    dm_w_ordered = [0.0] * n_trays
    T_out_ordered = [0.0] * n_trays
    RH_out_ordered = [0.0] * n_trays
    h_out_ordered = [0.0] * n_trays
    X_ordered = [0.0] * n_trays
    MR_ordered = [0.0] * n_trays
    
    idx = 0
    for zone in zones:
        for tray_i in zone.tray_indices:
            dm_w_ordered[tray_i] = dm_w_list[idx]
            T_out_ordered[tray_i] = T_out_list[idx]
            RH_out_ordered[tray_i] = RH_out_list[idx]
            h_out_ordered[tray_i] = h_out_list[idx]
            X_ordered[tray_i] = X_new_list[idx]
            MR_ordered[tray_i] = MR_new_list[idx]
            idx += 1
    
    return (dm_w_ordered, T_out_ordered, RH_out_ordered, h_out_ordered,
            X_ordered, MR_ordered, zone_states)


# =============================================================================
# WRAPPER FUNCTION FOR BACKWARD COMPATIBILITY
# =============================================================================

def simulate_drying_chamber_dispatch(
    T_to_chamber_C: float,
    omega_to_chamber: float,
    h_to_chamber: float,
    X_trays: List[float],
    MR_trays: List[float],
    cfg,  # SimulationConfig
    time_s: float,
    m_da: float,
    dt_s: float,
    return_zone_states: bool = False,
) -> tuple:
    """
    Dispatch to single-inlet or multi-zone simulation based on config.
    
    This wrapper function checks if multi-zone is enabled and routes
    to the appropriate simulation function.
    
    Parameters:
        Same as simulate_drying_chamber_multizone
        return_zone_states: If True, return zone states as 7th element
    
    Returns:
        (dm_w_trays, T_tray_out, RH_tray_out, h_tray_out, X_trays_new, MR_trays_new)
        If return_zone_states=True, also returns zone_states as 7th element
    """
    
    # Check if multi-zone is enabled
    if hasattr(cfg.dryer, 'multizone') and cfg.dryer.multizone.enabled:
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
        
        if return_zone_states:
            return result  # All 7 elements
        else:
            return result[:6]  # First 6 elements only
    
    else:
        # Fall back to original single-inlet simulation
        # This maintains backward compatibility
        from dryer_solar_hp import simulate_drying_chamber_single_inlet
        return simulate_drying_chamber_single_inlet(
            T_to_chamber_C, omega_to_chamber, h_to_chamber,
            X_trays, MR_trays, cfg, time_s, m_da, dt_s
        )


# =============================================================================
# DIAGNOSTIC UTILITIES
# =============================================================================

def print_zone_diagnostics(zone_states: List[ZoneState], time_h: float):
    """Print diagnostic information for all zones.
    
    Parameters:
        zone_states: List of ZoneState objects
        time_h: Current simulation time in hours
    """
    
    print(f"\n=== Zone Diagnostics at t = {time_h:.2f} h ===")
    print("-" * 70)
    
    for zs in zone_states:
        print(f"\n{zs.zone_name} ({zs.n_trays} trays):")
        print(f"  Inlet:  T={zs.T_inlet_C:.1f}°C, RH={zs.RH_inlet_frac*100:.1f}%, "
              f"ω={zs.omega_inlet*1000:.2f} g/kg")
        print(f"  Outlet: T={zs.T_outlet_C:.1f}°C, RH={zs.RH_outlet_frac*100:.1f}%, "
              f"ω={zs.omega_outlet*1000:.2f} g/kg")
        print(f"  Flow:   {zs.m_da_inlet:.4f} kg/s = {zs.m_da_inlet*3600:.1f} kg/h")
        print(f"  Water removed: {zs.dm_w_zone_kg*1000:.2f} g")


def calculate_uniformity_metrics(
    drying_times_h: List[float]
) -> Dict[str, float]:
    """Calculate uniformity metrics from tray drying times.
    
    Parameters:
        drying_times_h: List of drying times for each tray [hours]
    
    Returns:
        Dictionary with uniformity metrics:
            - t_min: Minimum drying time
            - t_max: Maximum drying time
            - t_mean: Mean drying time
            - t_range: Range (max - min)
            - t_std: Standard deviation
            - uniformity_pct: Uniformity percentage (100% = perfect)
    """
    import statistics
    
    t_min = min(drying_times_h)
    t_max = max(drying_times_h)
    t_mean = statistics.mean(drying_times_h)
    t_range = t_max - t_min
    t_std = statistics.stdev(drying_times_h) if len(drying_times_h) > 1 else 0.0
    
    # Uniformity: 100% means all trays finish at same time
    # Lower range = higher uniformity
    uniformity_pct = 100.0 * (1.0 - t_range / t_max) if t_max > 0 else 100.0
    
    return {
        't_min': t_min,
        't_max': t_max,
        't_mean': t_mean,
        't_range': t_range,
        't_std': t_std,
        'uniformity_pct': uniformity_pct,
    }


# =============================================================================
# MAIN - TESTING
# =============================================================================

if __name__ == "__main__":
    print("Multi-Zone Simulation Module")
    print("="*50)
    print("\nThis module provides:")
    print("  - mix_air_streams(): Air mixing calculations")
    print("  - simulate_drying_chamber_multizone(): Multi-zone simulation")
    print("  - simulate_drying_chamber_dispatch(): Auto-routing wrapper")
    print("  - print_zone_diagnostics(): Zone state printing")
    print("  - calculate_uniformity_metrics(): Uniformity analysis")
    print("\nTo use in your simulation:")
    print("  1. Enable multi-zone in config: cfg.dryer.multizone.enabled = True")
    print("  2. The simulation will automatically use multi-zone logic")
