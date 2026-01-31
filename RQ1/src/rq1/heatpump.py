"""Heat pump thermodynamic cycle using CoolProp library.

Matches the syntax and structure from your existing code.
Uses CP.PropsSI() for all property calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

try:
    import CoolProp.CoolProp as CP
    COOLPROP_AVAILABLE = True
except ImportError:
    COOLPROP_AVAILABLE = False
    print("[WARNING] CoolProp not available. Heat pump simulations will fail.")


@dataclass
class HeatPumpConfig:
    """Configuration parameters for heat pump simulation."""
    
    refrigerant: str = "R134a"
    eta_isentropic: float = 0.75  # Compressor isentropic efficiency
    eta_mechanical: float = 0.95  # Mechanical efficiency
    superheat_K: float = 5.0  # Evaporator outlet superheat
    subcooling_K: float = 5.0  # Condenser outlet subcooling
    
    # Safety limits
    T_evap_min_C: float = -15.0
    T_evap_max_C: float = 20.0
    T_cond_min_C: float = 30.0
    T_cond_max_C: float = 70.0
    
    # Performance limits
    COP_min: float = 2.0
    pressure_ratio_max: float = 8.0
    
    # Heat exchanger effectiveness
    epsilon_evap: float = 0.85
    epsilon_cond: float = 0.85


@dataclass
class RefrigerantState:
    """Thermodynamic state at a given point."""
    
    T_C: float
    P_Pa: float
    h_kJ_per_kg: float
    s_kJ_per_kgK: float
    rho_kg_per_m3: float
    quality: float | None = None
    phase: str = "unknown"


@dataclass
class HeatPumpCycleResult:
    """Results from heat pump cycle calculation."""
    
    state_1: RefrigerantState
    state_2: RefrigerantState
    state_2s: RefrigerantState
    state_3: RefrigerantState
    state_4: RefrigerantState
    
    m_ref_kg_per_s: float
    Q_evap_kW: float
    Q_cond_kW: float
    W_comp_kW: float
    COP: float
    pressure_ratio: float
    
    T_evap_C: float
    T_cond_C: float
    P_evap_Pa: float
    P_cond_Pa: float
    
    within_limits: bool
    warning: str | None = None


def compute_heat_pump_cycle(
    T_evap_C: float,
    T_cond_C: float,
    Q_cond_target_kW: float,
    cfg: HeatPumpConfig,
) -> HeatPumpCycleResult:
    """Compute complete heat pump cycle using CoolProp.
    
    Parameters
    ----------
    T_evap_C : float
        Evaporating temperature [°C]
    T_cond_C : float
        Condensing temperature [°C]
    Q_cond_target_kW : float
        Target condenser heat delivery [kW]
    cfg : HeatPumpConfig
        Configuration parameters
    
    Returns
    -------
    HeatPumpCycleResult
        Complete cycle with all state points
    """
    if not COOLPROP_AVAILABLE:
        raise ImportError("CoolProp is required for heat pump simulations")
    
    fluid = cfg.refrigerant
    
    # Check limits
    within_limits = True
    warning = None
    
    if T_evap_C < cfg.T_evap_min_C or T_evap_C > cfg.T_evap_max_C:
        within_limits = False
        warning = f"T_evap={T_evap_C:.1f}°C outside limits"
    
    if T_cond_C < cfg.T_cond_min_C or T_cond_C > cfg.T_cond_max_C:
        within_limits = False
        warning = f"T_cond={T_cond_C:.1f}°C outside limits"
    
    # Convert to Kelvin for CoolProp
    T_evap_K = T_evap_C + 273.15
    T_cond_K = T_cond_C + 273.15
    
    # Saturation pressures
    P_evap = CP.PropsSI('P', 'T', T_evap_K, 'Q', 0, fluid)  # [Pa]
    P_cond = CP.PropsSI('P', 'T', T_cond_K, 'Q', 0, fluid)  # [Pa]
    
    pressure_ratio = P_cond / P_evap
    if pressure_ratio > cfg.pressure_ratio_max:
        within_limits = False
        warning = f"Pressure ratio {pressure_ratio:.2f} exceeds {cfg.pressure_ratio_max}"
    
    # ===== STATE 1: Evaporator outlet (superheated vapor) =====
    T_1_K = T_evap_K + cfg.superheat_K
    P_1 = P_evap
    
    h_1 = CP.PropsSI('H', 'T', T_1_K, 'P', P_1, fluid) / 1000.0  # Convert J/kg to kJ/kg
    s_1 = CP.PropsSI('S', 'T', T_1_K, 'P', P_1, fluid) / 1000.0  # Convert J/kg·K to kJ/kg·K
    rho_1 = CP.PropsSI('D', 'T', T_1_K, 'P', P_1, fluid)
    
    state_1 = RefrigerantState(
        T_C=T_1_K - 273.15,
        P_Pa=P_1,
        h_kJ_per_kg=h_1,
        s_kJ_per_kgK=s_1,
        rho_kg_per_m3=rho_1,
        quality=None,
        phase="vapor"
    )
    
    # ===== STATE 2s: Isentropic compression endpoint =====
    P_2s = P_cond
    s_2s = s_1
    
    h_2s = CP.PropsSI('H', 'P', P_2s, 'S', s_2s * 1000.0, fluid) / 1000.0  # kJ/kg
    T_2s_K = CP.PropsSI('T', 'P', P_2s, 'S', s_2s * 1000.0, fluid)
    rho_2s = CP.PropsSI('D', 'P', P_2s, 'S', s_2s * 1000.0, fluid)
    
    state_2s = RefrigerantState(
        T_C=T_2s_K - 273.15,
        P_Pa=P_2s,
        h_kJ_per_kg=h_2s,
        s_kJ_per_kgK=s_2s,
        rho_kg_per_m3=rho_2s,
        quality=None,
        phase="vapor"
    )
    
    # ===== STATE 2: Actual compressor outlet =====
    h_2 = h_1 + (h_2s - h_1) / cfg.eta_isentropic
    P_2 = P_cond
    
    T_2_K = CP.PropsSI('T', 'P', P_2, 'H', h_2 * 1000.0, fluid)
    s_2 = CP.PropsSI('S', 'P', P_2, 'H', h_2 * 1000.0, fluid) / 1000.0
    rho_2 = CP.PropsSI('D', 'P', P_2, 'H', h_2 * 1000.0, fluid)
    
    state_2 = RefrigerantState(
        T_C=T_2_K - 273.15,
        P_Pa=P_2,
        h_kJ_per_kg=h_2,
        s_kJ_per_kgK=s_2,
        rho_kg_per_m3=rho_2,
        quality=None,
        phase="vapor"
    )
    
    # ===== STATE 3: Condenser outlet (subcooled liquid) =====
    T_3_K = T_cond_K - cfg.subcooling_K
    P_3 = P_cond
    
    h_3 = CP.PropsSI('H', 'T', T_3_K, 'P', P_3, fluid) / 1000.0  # kJ/kg
    s_3 = CP.PropsSI('S', 'T', T_3_K, 'P', P_3, fluid) / 1000.0
    rho_3 = CP.PropsSI('D', 'T', T_3_K, 'P', P_3, fluid)
    
    state_3 = RefrigerantState(
        T_C=T_3_K - 273.15,
        P_Pa=P_3,
        h_kJ_per_kg=h_3,
        s_kJ_per_kgK=s_3,
        rho_kg_per_m3=rho_3,
        quality=None,
        phase="liquid"
    )
    
    # ===== STATE 4: Expansion valve outlet (two-phase) =====
    # Isenthalpic expansion
    h_4 = h_3
    P_4 = P_evap
    T_4_K = T_evap_K
    
    # Calculate quality
    h_f = CP.PropsSI('H', 'T', T_4_K, 'Q', 0, fluid) / 1000.0  # Saturated liquid
    h_g = CP.PropsSI('H', 'T', T_4_K, 'Q', 1, fluid) / 1000.0  # Saturated vapor
    
    if h_g > h_f:
        quality_4 = (h_4 - h_f) / (h_g - h_f)
    else:
        quality_4 = 0.0
    
    quality_4 = max(0.0, min(1.0, quality_4))
    
    s_4 = CP.PropsSI('S', 'P', P_4, 'Q', quality_4, fluid) / 1000.0
    rho_4 = CP.PropsSI('D', 'P', P_4, 'Q', quality_4, fluid)
    
    state_4 = RefrigerantState(
        T_C=T_4_K - 273.15,
        P_Pa=P_4,
        h_kJ_per_kg=h_4,
        s_kJ_per_kgK=s_4,
        rho_kg_per_m3=rho_4,
        quality=quality_4,
        phase="two-phase"
    )
    
    # ===== Energy flows =====
    # Refrigerant mass flow rate
    Q_cond_per_kg = h_2 - h_3
    
    if Q_cond_per_kg > 0:
        m_ref = Q_cond_target_kW / Q_cond_per_kg
    else:
        m_ref = 0.0
    
    Q_evap_kW = m_ref * (h_1 - h_4)
    W_comp_kW = m_ref * (h_2 - h_1)
    Q_cond_kW = m_ref * (h_2 - h_3)
    
    # COP
    if W_comp_kW > 0:
        COP = Q_cond_kW / W_comp_kW
    else:
        COP = 0.0
    
    if COP < cfg.COP_min:
        within_limits = False
        if warning:
            warning += f"; COP={COP:.2f} below min"
        else:
            warning = f"COP={COP:.2f} below minimum {cfg.COP_min}"
    
    return HeatPumpCycleResult(
        state_1=state_1,
        state_2=state_2,
        state_2s=state_2s,
        state_3=state_3,
        state_4=state_4,
        m_ref_kg_per_s=m_ref,
        Q_evap_kW=Q_evap_kW,
        Q_cond_kW=Q_cond_kW,
        W_comp_kW=W_comp_kW,
        COP=COP,
        pressure_ratio=pressure_ratio,
        T_evap_C=T_evap_C,
        T_cond_C=T_cond_C,
        P_evap_Pa=P_evap,
        P_cond_Pa=P_cond,
        within_limits=within_limits,
        warning=warning,
    )


def size_heat_pump_for_air_heating(
    T_air_in_C: float,
    T_air_out_target_C: float,
    m_air_kg_per_s: float,
    T_evap_source_C: float,
    cfg: HeatPumpConfig,
) -> HeatPumpCycleResult:
    """Size heat pump to heat air from T_in to T_out.
    
    Parameters
    ----------
    T_air_in_C : float
        Air inlet temperature at condenser [°C]
    T_air_out_target_C : float
        Target air outlet temperature [°C]
    m_air_kg_per_s : float
        Air mass flow rate [kg/s]
    T_evap_source_C : float
        Temperature of evaporator heat source [°C]
    cfg : HeatPumpConfig
        Heat pump configuration
    
    Returns
    -------
    HeatPumpCycleResult
        Sized heat pump cycle
    """
    # Heat required
    cp_air = 1.006  # kJ/kg·K
    Q_cond_target_kW = m_air_kg_per_s * cp_air * (T_air_out_target_C - T_air_in_C)
    
    if Q_cond_target_kW <= 0:
        Q_cond_target_kW = 0.001  # Minimum to avoid errors
    
    # Evaporator temperature (approach temperature ~10 K)
    T_evap_C = T_evap_source_C - 10.0
    
    # Condenser temperature (pinch ~10 K above air outlet)
    T_cond_C = T_air_out_target_C + 10.0
    
    # Compute cycle
    return compute_heat_pump_cycle(T_evap_C, T_cond_C, Q_cond_target_kW, cfg)


if __name__ == "__main__":
    print("=== CoolProp Heat Pump Model Test ===\n")
    
    if not COOLPROP_AVAILABLE:
        print("ERROR: CoolProp not installed!")
        print("Install with: pip install CoolProp")
        exit(1)
    
    cfg = HeatPumpConfig()
    
    # Test case
    result = compute_heat_pump_cycle(
        T_evap_C=5.0,
        T_cond_C=55.0,
        Q_cond_target_kW=10.0,
        cfg=cfg,
    )
    
    print(f"Evaporator: T = {result.T_evap_C:.1f}°C, P = {result.P_evap_Pa/1e5:.2f} bar")
    print(f"Condenser:  T = {result.T_cond_C:.1f}°C, P = {result.P_cond_Pa/1e5:.2f} bar")
    print(f"Pressure ratio: {result.pressure_ratio:.2f}")
    print()
    
    print(f"State 1: T = {result.state_1.T_C:.1f}°C, h = {result.state_1.h_kJ_per_kg:.1f} kJ/kg")
    print(f"State 2: T = {result.state_2.T_C:.1f}°C, h = {result.state_2.h_kJ_per_kg:.1f} kJ/kg")
    print(f"State 3: T = {result.state_3.T_C:.1f}°C, h = {result.state_3.h_kJ_per_kg:.1f} kJ/kg")
    print(f"State 4: T = {result.state_4.T_C:.1f}°C, h = {result.state_4.h_kJ_per_kg:.1f} kJ/kg, x = {result.state_4.quality:.3f}")
    print()
    
    print(f"m_ref:  {result.m_ref_kg_per_s:.4f} kg/s")
    print(f"Q_evap: {result.Q_evap_kW:.2f} kW")
    print(f"W_comp: {result.W_comp_kW:.2f} kW")
    print(f"Q_cond: {result.Q_cond_kW:.2f} kW")
    print(f"COP:    {result.COP:.2f}")
    print()
    
    print(f"Within limits: {result.within_limits}")
    if result.warning:
        print(f"Warning: {result.warning}")
