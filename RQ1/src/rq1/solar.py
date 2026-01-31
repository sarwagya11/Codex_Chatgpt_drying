"""Solar thermal flat-plate collector model.

Implements first-principles heat transfer model with:
- Optical efficiency (absorption, transmission, reflection)
- Thermal losses (convection, radiation, conduction)
- Incidence angle modifier
- Ambient conditions integration

References:
- Duffie & Beckman, "Solar Engineering of Thermal Processes" (2013)
- ASHRAE 93-2010 (Standard test method for solar collectors)
- Hottel-Whillier-Bliss equation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class SolarCollectorConfig:
    """Configuration for flat-plate solar collector."""
    
    # Collector geometry
    area_m2: float = 10.0  # Collector area [m²]
    
    # Optical properties
    eta_optical: float = 0.75  # Optical efficiency (τα product)
    # Typical values:
    #   - Flat-plate, single glass: 0.75-0.80
    #   - Flat-plate, double glass: 0.70-0.75
    #   - Evacuated tube: 0.65-0.70
    
    # Thermal loss coefficients
    U_loss_W_per_m2K: float = 5.0  # Overall heat loss coefficient [W/m²·K]
    # Typical values:
    #   - Flat-plate, single glass: 4-6 W/m²·K
    #   - Flat-plate, double glass: 3-4 W/m²·K
    #   - Evacuated tube: 1-2 W/m²·K
    
    # Incidence angle modifier
    K_theta: float = 1.0  # Incidence angle modifier (1.0 = normal incidence)
    # For tilted collectors, K_theta varies with sun angle
    # Simplification: Use 1.0 for now (assumes good tracking or optimal tilt)
    
    # Heat capacity effects (thermal inertia)
    C_collector_kJ_per_K: float = 10.0  # Heat capacity of collector [kJ/K]
    # Typical: 5-15 kJ/K for 10 m² collector
    
    # Flow configuration
    flow_rate_kg_per_s: float | None = None  # Air mass flow rate [kg/s]
    # If None, use same as dryer air flow
    
    # Performance limits
    T_stagnation_max_C: float = 150.0  # Maximum stagnation temperature [°C]
    T_min_useful_C: float = 5.0  # Minimum useful outlet temperature above ambient


@dataclass
class SolarCollectorState:
    """State variables for solar collector at one timestep."""
    
    # Inputs
    T_in_C: float  # Inlet air temperature [°C]
    T_amb_C: float  # Ambient temperature [°C]
    G_solar_W_per_m2: float  # Solar irradiance [W/m²]
    m_air_kg_per_s: float  # Air mass flow rate [kg/s]
    
    # Outputs
    T_out_C: float  # Outlet air temperature [°C]
    Q_useful_kW: float  # Useful heat gained [kW]
    Q_loss_kW: float  # Thermal losses [kW]
    eta_collector: float  # Instantaneous collector efficiency
    
    # Diagnostics
    T_absorber_avg_C: float  # Average absorber plate temperature [°C]
    is_stagnant: bool  # True if no flow (stagnation condition)
    useful: bool  # True if Q_useful > 0


def compute_solar_collector(
    T_in_C: float,
    T_amb_C: float,
    G_solar_W_per_m2: float,
    m_air_kg_per_s: float,
    cfg: SolarCollectorConfig,
    dt_s: float = 60.0,
    T_absorber_prev_C: float | None = None,
) -> Tuple[SolarCollectorState, float]:
    """Compute solar collector performance for one timestep.
    
    Uses Hottel-Whillier-Bliss equation for flat-plate collectors.
    
    Parameters
    ----------
    T_in_C : float
        Inlet air temperature [°C]
    T_amb_C : float
        Ambient temperature [°C]
    G_solar_W_per_m2 : float
        Solar irradiance on collector surface [W/m²]
    m_air_kg_per_s : float
        Air mass flow rate [kg/s]
    cfg : SolarCollectorConfig
        Collector configuration
    dt_s : float
        Timestep [s] (for thermal inertia calculation)
    T_absorber_prev_C : float, optional
        Absorber temperature from previous timestep (for thermal inertia)
    
    Returns
    -------
    state : SolarCollectorState
        Collector state at this timestep
    T_absorber_out_C : float
        Updated absorber temperature (for next timestep)
    """
    # Air specific heat
    cp_air = 1.006  # kJ/kg·K
    
    # Check for stagnation (no flow)
    is_stagnant = m_air_kg_per_s <= 0.0 or G_solar_W_per_m2 <= 0.0
    
    if is_stagnant or G_solar_W_per_m2 < 10.0:
        # No useful heat, collector cools to ambient
        T_out_C = T_in_C
        Q_useful_kW = 0.0
        Q_loss_kW = 0.0
        eta_collector = 0.0
        T_absorber_avg_C = T_amb_C
        useful = False
        
        state = SolarCollectorState(
            T_in_C=T_in_C,
            T_amb_C=T_amb_C,
            G_solar_W_per_m2=G_solar_W_per_m2,
            m_air_kg_per_s=m_air_kg_per_s,
            T_out_C=T_out_C,
            Q_useful_kW=Q_useful_kW,
            Q_loss_kW=Q_loss_kW,
            eta_collector=eta_collector,
            T_absorber_avg_C=T_absorber_avg_C,
            is_stagnant=is_stagnant,
            useful=useful,
        )
        
        return state, T_amb_C
    
    # === Steady-state collector model (Hottel-Whillier-Bliss) ===
    
    # Collector heat removal factor F_R
    # F_R relates actual useful gain to ideal useful gain at inlet temperature
    # Typical values: 0.85-0.95 for well-designed collectors
    
    # For air collectors, F_R depends on mass flow rate and collector design
    # Simplified correlation: F_R = 1 - exp(-A * U * F' / (m * cp))
    # where F' is collector efficiency factor (~0.9)
    
    F_prime = 0.90  # Collector efficiency factor
    UA = cfg.area_m2 * cfg.U_loss_W_per_m2K / 1000.0  # kW/K
    C_min = m_air_kg_per_s * cp_air  # kW/K
    
    if C_min > 0 and UA > 0:
        NTU = UA * F_prime / C_min  # Number of Transfer Units
        F_R = (C_min / UA) * (1.0 - math.exp(-NTU))  # CORRECTED FORMULA
    else:
        F_R = 0.0
    # Useful heat gain (Hottel-Whillier-Bliss equation)
    # Q_u = A * F_R * [η_optical * G - U_L * (T_in - T_amb)]
    
    Q_absorbed_kW = cfg.area_m2 * cfg.eta_optical * cfg.K_theta * G_solar_W_per_m2 / 1000.0
    Q_loss_kW = cfg.area_m2 * cfg.U_loss_W_per_m2K * (T_in_C - T_amb_C) / 1000.0
    
    Q_useful_kW = F_R * (Q_absorbed_kW - Q_loss_kW)
    Q_useful_kW = max(0.0, Q_useful_kW)  # Cannot be negative
    
    # Outlet temperature
    if m_air_kg_per_s > 0 and Q_useful_kW > 0:
        delta_T = Q_useful_kW / (m_air_kg_per_s * cp_air)
        T_out_C = T_in_C + delta_T
    else:
        T_out_C = T_in_C
    
    # Average absorber plate temperature (for diagnostics)
    # Approximation: T_absorber ≈ (T_in + T_out) / 2 + some elevation due to resistance
    T_fluid_avg = (T_in_C + T_out_C) / 2.0
    
    # Temperature rise of absorber above fluid (depends on U_L and F')
    if cfg.U_loss_W_per_m2K > 0 and F_prime > 0:
        delta_T_absorber = (Q_absorbed_kW / cfg.area_m2 * 1000.0) / (cfg.U_loss_W_per_m2K) - (T_fluid_avg - T_amb_C)
    else:
        delta_T_absorber = 0.0
    
    T_absorber_avg_C = T_fluid_avg + delta_T_absorber
    
    # Apply thermal inertia if previous temperature available
    if T_absorber_prev_C is not None and cfg.C_collector_kJ_per_K > 0:
        # Exponential relaxation toward new steady-state temperature
        tau_thermal_s = cfg.C_collector_kJ_per_K / (cfg.area_m2 * cfg.U_loss_W_per_m2K / 1000.0)
        alpha = dt_s / (tau_thermal_s + dt_s)
        T_absorber_avg_C = (1 - alpha) * T_absorber_prev_C + alpha * T_absorber_avg_C
    
    # Collector efficiency
    if G_solar_W_per_m2 > 0:
        eta_collector = Q_useful_kW / (cfg.area_m2 * G_solar_W_per_m2 / 1000.0)
    else:
        eta_collector = 0.0
    
    # Check if useful
    useful = Q_useful_kW > 0.01 and (T_out_C - T_amb_C) > cfg.T_min_useful_C
    
    # Check stagnation temperature limit
    if T_absorber_avg_C > cfg.T_stagnation_max_C:
        T_absorber_avg_C = cfg.T_stagnation_max_C
        # In reality, this would require flow increase or shading
    
    state = SolarCollectorState(
        T_in_C=T_in_C,
        T_amb_C=T_amb_C,
        G_solar_W_per_m2=G_solar_W_per_m2,
        m_air_kg_per_s=m_air_kg_per_s,
        T_out_C=T_out_C,
        Q_useful_kW=Q_useful_kW,
        Q_loss_kW=Q_loss_kW,
        eta_collector=eta_collector,
        T_absorber_avg_C=T_absorber_avg_C,
        is_stagnant=is_stagnant,
        useful=useful,
    )
    
    return state, T_absorber_avg_C


def compute_stagnation_temperature(
    T_amb_C: float,
    G_solar_W_per_m2: float,
    cfg: SolarCollectorConfig,
) -> float:
    """Compute stagnation (no-flow) temperature of collector.
    
    At stagnation: Q_absorbed = Q_loss
    η_optical * G = U_L * (T_stag - T_amb)
    T_stag = T_amb + (η_optical * G) / U_L
    
    This is the maximum temperature the collector can reach.
    """
    if cfg.U_loss_W_per_m2K <= 0:
        return cfg.T_stagnation_max_C
    
    T_stag = T_amb_C + (cfg.eta_optical * cfg.K_theta * G_solar_W_per_m2) / cfg.U_loss_W_per_m2K
    
    return min(T_stag, cfg.T_stagnation_max_C)


def size_collector_for_target_temperature(
    T_in_C: float,
    T_out_target_C: float,
    T_amb_C: float,
    G_solar_W_per_m2: float,
    m_air_kg_per_s: float,
    cfg: SolarCollectorConfig,
) -> float:
    """Determine required collector area to achieve target outlet temperature.
    
    Returns required area [m²], or 0 if target is unachievable.
    """
    cp_air = 1.006  # kJ/kg·K
    
    if G_solar_W_per_m2 < 100.0:
        return 0.0  # Insufficient solar
    
    # Required heat
    Q_required_kW = m_air_kg_per_s * cp_air * (T_out_target_C - T_in_C)
    
    if Q_required_kW <= 0:
        return 0.0
    
    # Check if achievable (stagnation temperature must exceed target)
    T_stag = T_amb_C + (cfg.eta_optical * G_solar_W_per_m2) / cfg.U_loss_W_per_m2K
    if T_stag < T_out_target_C:
        return 0.0  # Physically impossible with this irradiance
    
    # Iteratively solve for required area
    # (This is complex because F_R depends on area)
    # Use bisection search
    
    A_min, A_max = 0.0, 100.0  # Search range [m²]
    
    for _ in range(30):
        A_test = 0.5 * (A_min + A_max)
        cfg_test = SolarCollectorConfig(
            area_m2=A_test,
            eta_optical=cfg.eta_optical,
            U_loss_W_per_m2K=cfg.U_loss_W_per_m2K,
            K_theta=cfg.K_theta,
        )
        
        state, _ = compute_solar_collector(
            T_in_C, T_amb_C, G_solar_W_per_m2, m_air_kg_per_s, cfg_test
        )
        
        if abs(state.T_out_C - T_out_target_C) < 0.1:
            return A_test
        
        if state.T_out_C < T_out_target_C:
            A_min = A_test
        else:
            A_max = A_test
    
    return 0.5 * (A_min + A_max)


if __name__ == "__main__":
    print("=== Solar Collector Model Test ===\n")
    
    cfg = SolarCollectorConfig(
        area_m2=10.0,
        eta_optical=0.75,
        U_loss_W_per_m2K=5.0,
    )
    
    # Test case: T_in = 20°C, T_amb = 15°C, G = 800 W/m², m = 0.5 kg/s
    state, T_absorber = compute_solar_collector(
        T_in_C=20.0,
        T_amb_C=15.0,
        G_solar_W_per_m2=800.0,
        m_air_kg_per_s=0.5,
        cfg=cfg,
    )
    
    print(f"Inlet air:      T = {state.T_in_C:.1f}°C")
    print(f"Outlet air:     T = {state.T_out_C:.1f}°C")
    print(f"Temperature rise: ΔT = {state.T_out_C - state.T_in_C:.1f}°C")
    print()
    
    print(f"Solar irradiance: G = {state.G_solar_W_per_m2:.0f} W/m²")
    print(f"Useful heat:      Q = {state.Q_useful_kW:.2f} kW")
    print(f"Thermal losses:   Q_loss = {state.Q_loss_kW:.2f} kW")
    print(f"Collector efficiency: η = {state.eta_collector:.3f}")
    print()
    
    print(f"Absorber temperature: {state.T_absorber_avg_C:.1f}°C")
    print(f"Useful heat available: {state.useful}")
    print()
    
    # Stagnation temperature
    T_stag = compute_stagnation_temperature(15.0, 800.0, cfg)
    print(f"Stagnation temperature (no flow): {T_stag:.1f}°C")
    print()
    
    # Required area for target temperature
    A_req = size_collector_for_target_temperature(
        T_in_C=20.0,
        T_out_target_C=50.0,
        T_amb_C=15.0,
        G_solar_W_per_m2=800.0,
        m_air_kg_per_s=0.5,
        cfg=cfg,
    )
    print(f"Area required for T_out = 50°C: {A_req:.1f} m²")
