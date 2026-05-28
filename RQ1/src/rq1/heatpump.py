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
    
    refrigerant: str = "R134a"         # Standard heat-pump dryer refrigerant
    eta_isentropic: float = 0.75  # Compressor isentropic efficiency
    eta_mechanical: float = 0.90  # Mechanical efficiency
    superheat_K: float = 5.0  # Evaporator outlet superheat
    subcooling_K: float = 5.0  # Condenser outlet subcooling

    # Safety limits
    # T_evap_min_C = -5.0 → R134a anti-frost (sat P @ -5°C = 2.4 bar, safe)
    # T_cond_max_C = 70.0 → R134a critical temp = 101°C; P_cond @ 70°C ≈ 21 bar (safe)
    T_evap_min_C: float = -5.0
    T_evap_max_C: float = 20.0
    T_cond_min_C: float = 30.0
    T_cond_max_C: float = 70.0

    # Performance limits
    COP_min: float = 2.0
    pressure_ratio_max: float = 10.0

    # Reference thresholds for flagging — 1-ton AC in HP dryer mode [kW]
    # NOT used to cap any values; only used to set feasibility flags in results
    Q_cond_max_kW: float = 4.0   # 1-ton AC condenser reference
    Q_evap_max_kW: float = 3.5   # 1-ton AC evaporator reference (Q_cond - W_comp typical)
    
    # Heat exchanger effectiveness
    epsilon_evap: float = 0.85
    epsilon_cond: float = 0.85

    # Evaporator coil approach temperature [K]
    # Coil surface = T_evap_sat + DT_evap_approach (refrigerant-to-surface resistance)
    DT_evap_approach:   float = 3.0


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
    T_evap_coil_C: float = 0.0   # Evaporator coil surface temperature [°C] (for record output)
    P_evap_Pa: float = 0.0
    P_cond_Pa: float = 0.0

    flag_hp_at_capacity: bool = False  # True when Q_cond exceeds Q_cond_max_kW reference (4 kW / 1-ton AC)
    flag_evap_oversized: bool = False  # True when Q_evap exceeds 1-ton AC evaporator reference
    flag_cond_oversized: bool = False  # True when Q_cond exceeds 1-ton AC condenser reference
    within_limits: bool = True
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
    W_comp_kW = m_ref * (h_2 - h_1) / cfg.eta_mechanical
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
        T_evap_coil_C=T_evap_C + cfg.DT_evap_approach,
        P_evap_Pa=P_evap,
        P_cond_Pa=P_cond,
        flag_hp_at_capacity=(Q_cond_target_kW > cfg.Q_cond_max_kW),
        flag_evap_oversized=(Q_evap_kW > cfg.Q_evap_max_kW),
        flag_cond_oversized=(Q_cond_kW > cfg.Q_cond_max_kW),
        within_limits=within_limits,
        warning=warning,
    )


def compute_hp_COP(T_evap_C: float, T_cond_C: float, cfg: HeatPumpConfig) -> float:
    """Return HP COP for given evaporator/condenser temperatures.

    COP depends only on T_evap, T_cond, and config — not on Q_cond_target.
    Uses a unit-load cycle (Q_cond=1 kW) to avoid computing a full sized cycle.
    """
    result = compute_heat_pump_cycle(T_evap_C, T_cond_C, 1.0, cfg)
    return result.COP


def size_heat_pump_for_air_heating(
    T_air_in_C: float,
    T_air_out_target_C: float,
    m_air_kg_per_s: float,
    T_evap_source_C: float,
    cfg: HeatPumpConfig,
    omega_in: float | None = None,
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
    omega_in : float, optional
        Humidity ratio of condenser inlet air [kg/kg_da].  When provided the
        heat load is computed from moist-air enthalpy difference (more
        accurate than cp·ΔT).

    Returns
    -------
    HeatPumpCycleResult
        Sized heat pump cycle
    """
    # Heat required
    if omega_in is not None:
        # Moist-air enthalpy method (accounts for humidity)
        # h = cp_da*T + omega*(h_fg + cp_v*T)  with cp_da=1.006, h_fg=2501, cp_v=1.86
        h_in  = 1.006 * T_air_in_C + omega_in * (2501.0 + 1.86 * T_air_in_C)
        h_out = 1.006 * T_air_out_target_C + omega_in * (2501.0 + 1.86 * T_air_out_target_C)
        Q_cond_target_kW = m_air_kg_per_s * (h_out - h_in)
    else:
        cp_air = 1.006  # kJ/kg·K
        Q_cond_target_kW = m_air_kg_per_s * cp_air * (T_air_out_target_C - T_air_in_C)
    
    if Q_cond_target_kW <= 0:
        Q_cond_target_kW = 0.001  # Minimum to avoid errors
    
    # Condenser temperature (pinch ~10 K above air outlet)
    T_cond_C = T_air_out_target_C + 10.0

    # Evaporator temperature (approach ~10 K below source — no clamping, flags added by caller)
    T_evap_C = T_evap_source_C - 10.0

    # Hard stop: T_evap must be strictly below T_cond for a valid refrigeration cycle.
    # Occurs in Config C when solar area is very large (T_solar_out >> T_set).
    # Minimum 1 K lift maintained so CoolProp does not crash.
    if T_evap_C >= T_cond_C:
        T_evap_C = T_cond_C - 1.0

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
