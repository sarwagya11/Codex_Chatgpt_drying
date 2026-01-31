"""Heat pump module for Phase-1 dryer simulation.

Implements temperature-dependent COP and capacity calculations for
air-source heat pump integration with the drying system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

# Specific heat of moist air (approximate)
CP_MA_KJ_PER_KG_K = 1.02


@dataclass
class HeatPumpConfig:
    """Configuration for heat pump subsystem."""

    enabled: bool = True

    # Nominal capacity and COP at reference conditions
    Q_HP_nom_kW: float = 10.0
    COP_nom: float = 3.33

    # Reference conditions for nominal ratings (EN 14511 standard)
    T_source_nom_C: float = 7.0  # A7/W35 or A7/A35 rating
    T_sink_nom_C: float = 35.0

    # Carnot efficiency factor (typically 0.4-0.6 for real HP)
    eta_carnot: float = 0.50

    # Capacity degradation at low ambient
    T_defrost_C: float = 2.0  # Temperature below which defrost cycles occur
    capacity_degrade_per_C: float = 0.02  # 2% capacity loss per °C below T_source_nom

    # Minimum operating conditions
    T_source_min_C: float = -15.0  # HP shuts off below this
    T_sink_max_C: float = 60.0  # Maximum achievable outlet temperature
    T_lift_max_C: float = 50.0  # Maximum temperature lift

    # Source selection mode
    source_mode: Literal["ambient", "exhaust", "dual"] = "ambient"
    exhaust_recovery_fraction: float = 0.3  # Fraction of exhaust heat recoverable

    # Control parameters
    modulation_min: float = 0.3  # Minimum part-load ratio (30%)
    enable_capacity_limit: bool = True


def compute_carnot_COP(T_source_C: float, T_sink_C: float) -> float:
    """
    Compute ideal Carnot COP for a heat pump.

    COP_carnot = T_sink / (T_sink - T_source)  [temperatures in Kelvin]

    Parameters
    ----------
    T_source_C : float
        Heat source temperature [°C] (evaporator side)
    T_sink_C : float
        Heat sink temperature [°C] (condenser side)

    Returns
    -------
    float
        Ideal Carnot COP (dimensionless)
    """
    T_source_K = T_source_C + 273.15
    T_sink_K = T_sink_C + 273.15

    dT = T_sink_K - T_source_K
    if dT <= 0:
        # No temperature lift needed, COP -> infinity (unrealistic)
        return 20.0  # Cap at high value

    return T_sink_K / dT


def compute_actual_COP(
    T_source_C: float,
    T_sink_C: float,
    cfg: HeatPumpConfig,
) -> float:
    """
    Compute actual COP accounting for real-world inefficiencies.

    COP_actual = eta_carnot * COP_carnot

    With additional penalties for:
    - Defrost cycles at low ambient
    - Part-load operation

    Parameters
    ----------
    T_source_C : float
        Heat source temperature [°C]
    T_sink_C : float
        Heat sink temperature [°C]
    cfg : HeatPumpConfig
        Heat pump configuration

    Returns
    -------
    float
        Actual COP (dimensionless)
    """
    COP_carnot = compute_carnot_COP(T_source_C, T_sink_C)
    COP_actual = cfg.eta_carnot * COP_carnot

    # Defrost penalty at low temperatures
    if T_source_C < cfg.T_defrost_C:
        defrost_penalty = 0.95 - 0.01 * (cfg.T_defrost_C - T_source_C)
        defrost_penalty = max(0.7, defrost_penalty)  # Cap at 30% penalty
        COP_actual *= defrost_penalty

    # Ensure reasonable bounds
    COP_actual = max(1.5, min(6.0, COP_actual))

    return COP_actual


def compute_HP_capacity_kW(
    T_source_C: float,
    T_sink_C: float,
    cfg: HeatPumpConfig,
) -> float:
    """
    Compute temperature-dependent HP heating capacity.

    Capacity degrades at:
    - Low source temperatures (ambient)
    - High sink temperatures (required outlet)

    Parameters
    ----------
    T_source_C : float
        Heat source temperature [°C]
    T_sink_C : float
        Heat sink temperature [°C]
    cfg : HeatPumpConfig
        Heat pump configuration

    Returns
    -------
    float
        Available heating capacity [kW]
    """
    Q_nom = cfg.Q_HP_nom_kW

    # Source temperature degradation
    if T_source_C < cfg.T_source_nom_C:
        dT_source = cfg.T_source_nom_C - T_source_C
        source_factor = 1.0 - cfg.capacity_degrade_per_C * dT_source
        source_factor = max(0.4, source_factor)  # Don't go below 40%
    else:
        # Slight capacity increase at warmer ambient
        dT_source = T_source_C - cfg.T_source_nom_C
        source_factor = 1.0 + 0.005 * dT_source  # 0.5% per °C
        source_factor = min(1.2, source_factor)  # Cap at 20% boost

    # Sink temperature effect (higher T_sink = lower capacity)
    T_lift = T_sink_C - T_source_C
    if T_lift > 30.0:
        lift_penalty = 1.0 - 0.01 * (T_lift - 30.0)
        lift_penalty = max(0.7, lift_penalty)
    else:
        lift_penalty = 1.0

    Q_available = Q_nom * source_factor * lift_penalty

    # Shutdown below minimum source temperature
    if T_source_C < cfg.T_source_min_C:
        Q_available = 0.0

    return max(0.0, Q_available)


def select_HP_source(
    T_amb_C: float,
    T_exhaust_C: float,
    cfg: HeatPumpConfig,
) -> tuple[float, str]:
    """
    Select optimal heat source for dual-source HP.

    Parameters
    ----------
    T_amb_C : float
        Ambient air temperature [°C]
    T_exhaust_C : float
        Dryer exhaust temperature [°C]
    cfg : HeatPumpConfig
        Heat pump configuration

    Returns
    -------
    tuple[float, str]
        Selected source temperature [°C] and source name
    """
    if cfg.source_mode == "ambient":
        return T_amb_C, "ambient"

    if cfg.source_mode == "exhaust":
        # Use exhaust with recovery fraction
        T_source = T_amb_C + cfg.exhaust_recovery_fraction * (T_exhaust_C - T_amb_C)
        return T_source, "exhaust"

    if cfg.source_mode == "dual":
        # Choose better source
        T_exhaust_effective = T_amb_C + cfg.exhaust_recovery_fraction * (T_exhaust_C - T_amb_C)
        if T_exhaust_effective > T_amb_C + 2.0:
            return T_exhaust_effective, "exhaust"
        return T_amb_C, "ambient"

    return T_amb_C, "ambient"


def compute_HP_heating(
    T_source_C: float,
    T_in_C: float,
    T_target_C: float,
    m_da_kg_per_s: float,
    dt_s: float,
    cfg: HeatPumpConfig,
) -> Dict[str, float]:
    """
    Compute heat pump heating for one timestep.

    The HP heats air from T_in_C toward T_target_C, limited by:
    - Available capacity (temperature-dependent)
    - Maximum achievable temperature (T_sink_max_C)
    - Maximum temperature lift

    Parameters
    ----------
    T_source_C : float
        Heat source temperature [°C] (ambient or exhaust)
    T_in_C : float
        Inlet air temperature [°C] (after mixing)
    T_target_C : float
        Target outlet temperature [°C] (T_set)
    m_da_kg_per_s : float
        Dry air mass flow rate [kg/s]
    dt_s : float
        Timestep [s]
    cfg : HeatPumpConfig
        Heat pump configuration

    Returns
    -------
    dict
        Results with keys:
        - Q_HP_kW: Heat delivered [kW]
        - W_HP_kW: Electrical input [kW]
        - COP_actual: Operating COP [-]
        - T_out_C: Outlet temperature [°C]
        - HP_at_capacity: True if capacity-limited
        - HP_running: True if HP is operating
    """
    result = {
        "Q_HP_kW": 0.0,
        "W_HP_kW": 0.0,
        "COP_actual": 0.0,
        "T_out_C": T_in_C,
        "HP_at_capacity": False,
        "HP_running": False,
    }

    if not cfg.enabled:
        return result

    # Check if heating is needed
    dT_needed = T_target_C - T_in_C
    if dT_needed <= 0.0:
        # Already at or above target
        result["T_out_C"] = T_in_C
        return result

    # Compute required heating power
    Q_required_kW = m_da_kg_per_s * CP_MA_KJ_PER_KG_K * dT_needed

    # Determine sink temperature (target outlet)
    T_sink_C = min(T_target_C, cfg.T_sink_max_C)

    # Check temperature lift constraint
    T_lift = T_sink_C - T_source_C
    if T_lift > cfg.T_lift_max_C:
        # Can't achieve full lift, reduce target
        T_sink_C = T_source_C + cfg.T_lift_max_C
        dT_achievable = T_sink_C - T_in_C
        if dT_achievable <= 0:
            return result
        Q_required_kW = m_da_kg_per_s * CP_MA_KJ_PER_KG_K * dT_achievable

    # Compute available capacity at operating conditions
    Q_available_kW = compute_HP_capacity_kW(T_source_C, T_sink_C, cfg)

    if Q_available_kW <= 0.0:
        # HP cannot operate (too cold)
        return result

    # Compute actual COP at operating conditions
    COP_actual = compute_actual_COP(T_source_C, T_sink_C, cfg)

    # Determine actual heat delivery
    if cfg.enable_capacity_limit and Q_required_kW > Q_available_kW:
        Q_HP_kW = Q_available_kW
        HP_at_capacity = True
    else:
        Q_HP_kW = Q_required_kW
        HP_at_capacity = False

    # Check minimum modulation
    if Q_HP_kW < cfg.modulation_min * cfg.Q_HP_nom_kW:
        # Below minimum, HP cycles
        Q_HP_kW = cfg.modulation_min * cfg.Q_HP_nom_kW
        HP_at_capacity = False

    # Compute electrical input
    W_HP_kW = Q_HP_kW / COP_actual

    # Compute outlet temperature
    dT_achieved = Q_HP_kW / (m_da_kg_per_s * CP_MA_KJ_PER_KG_K)
    T_out_C = T_in_C + dT_achieved

    result["Q_HP_kW"] = Q_HP_kW
    result["W_HP_kW"] = W_HP_kW
    result["COP_actual"] = COP_actual
    result["T_out_C"] = T_out_C
    result["HP_at_capacity"] = HP_at_capacity
    result["HP_running"] = True

    return result
