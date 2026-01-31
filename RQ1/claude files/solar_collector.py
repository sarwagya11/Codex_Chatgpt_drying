"""Solar collector module for Phase-1 dryer simulation.

Implements flat-plate solar collector heating using the Hottel-Whillier-Bliss
equation for integration with the HP+Solar drying system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

# Specific heat of moist air (approximate)
CP_MA_KJ_PER_KG_K = 1.02


@dataclass
class SolarCollectorConfig:
    """Configuration for flat-plate solar collector subsystem."""

    enabled: bool = True

    # Collector geometry
    A_col_m2: float = 10.0  # Collector area [m²]

    # Optical and thermal properties (typical flat-plate values)
    eta_optical: float = 0.75  # Optical efficiency (tau*alpha product)
    U_loss_W_per_m2K: float = 6.0  # Overall heat loss coefficient [W/(m²·K)]

    # Flow and operation
    collector_tilt_deg: float = 27.0  # Tilt angle (typically ~latitude)
    GHI_threshold_W_per_m2: float = 50.0  # Minimum GHI for operation

    # Temperature limits
    T_stagnation_C: float = 120.0  # Maximum collector temperature (no flow)
    T_fluid_max_C: float = 80.0  # Maximum outlet temperature

    # Incidence angle modifier (IAM) coefficients
    # IAM = 1 - b0 * (1/cos(theta) - 1)
    b0_IAM: float = 0.1  # First-order IAM coefficient

    # Heat removal factor (for air-based collectors)
    F_R: float = 0.85  # Heat removal factor (0.8-0.95 for good design)


def compute_incidence_angle_modifier(
    zenith_angle_deg: float,
    cfg: SolarCollectorConfig,
) -> float:
    """
    Compute incidence angle modifier for non-normal solar incidence.

    Parameters
    ----------
    zenith_angle_deg : float
        Solar zenith angle [degrees]
    cfg : SolarCollectorConfig
        Collector configuration

    Returns
    -------
    float
        IAM factor (0 to 1)
    """
    import math

    # For simplicity, assume effective incidence angle = zenith angle
    # (valid for horizontal or optimally tilted collectors)
    theta_rad = math.radians(min(zenith_angle_deg, 85.0))  # Cap at 85°

    cos_theta = math.cos(theta_rad)
    if cos_theta <= 0.1:
        return 0.0

    IAM = 1.0 - cfg.b0_IAM * (1.0 / cos_theta - 1.0)
    return max(0.0, min(1.0, IAM))


def compute_solar_useful_gain_kW(
    GHI_Wm2: float,
    T_in_C: float,
    T_amb_C: float,
    cfg: SolarCollectorConfig,
) -> float:
    """
    Compute useful solar heat gain using Hottel-Whillier-Bliss equation.

    Q_u = A_col * F_R * [η_opt * G - U_L * (T_in - T_amb)]

    Parameters
    ----------
    GHI_Wm2 : float
        Global horizontal irradiance [W/m²]
    T_in_C : float
        Collector inlet temperature [°C]
    T_amb_C : float
        Ambient temperature [°C]
    cfg : SolarCollectorConfig
        Collector configuration

    Returns
    -------
    float
        Useful heat gain [kW]
    """
    if GHI_Wm2 < cfg.GHI_threshold_W_per_m2:
        return 0.0

    # Absorbed solar radiation (with optical efficiency)
    S_Wm2 = cfg.eta_optical * GHI_Wm2

    # Thermal losses (proportional to temperature difference)
    dT = T_in_C - T_amb_C
    Q_loss_Wm2 = cfg.U_loss_W_per_m2K * max(0.0, dT)

    # Net useful gain per unit area
    Q_useful_Wm2 = S_Wm2 - Q_loss_Wm2

    # Apply heat removal factor and collector area
    Q_u_W = cfg.A_col_m2 * cfg.F_R * Q_useful_Wm2

    # Convert to kW and ensure non-negative
    Q_u_kW = max(0.0, Q_u_W / 1000.0)

    return Q_u_kW


def compute_collector_efficiency(
    GHI_Wm2: float,
    T_in_C: float,
    T_amb_C: float,
    cfg: SolarCollectorConfig,
) -> float:
    """
    Compute instantaneous collector efficiency.

    η = F_R * [η_opt - U_L * (T_in - T_amb) / G]

    Parameters
    ----------
    GHI_Wm2 : float
        Global horizontal irradiance [W/m²]
    T_in_C : float
        Collector inlet temperature [°C]
    T_amb_C : float
        Ambient temperature [°C]
    cfg : SolarCollectorConfig
        Collector configuration

    Returns
    -------
    float
        Collector efficiency (0 to 1)
    """
    if GHI_Wm2 < cfg.GHI_threshold_W_per_m2:
        return 0.0

    dT = T_in_C - T_amb_C
    reduced_temp = dT / GHI_Wm2  # Reduced temperature difference

    eta = cfg.F_R * (cfg.eta_optical - cfg.U_loss_W_per_m2K * reduced_temp)

    return max(0.0, min(1.0, eta))


def compute_solar_heating(
    GHI_Wm2: float,
    T_in_C: float,
    T_amb_C: float,
    m_da_kg_per_s: float,
    cfg: SolarCollectorConfig,
) -> Dict[str, float]:
    """
    Compute solar collector heating for one timestep.

    Parameters
    ----------
    GHI_Wm2 : float
        Global horizontal irradiance [W/m²]
    T_in_C : float
        Inlet air temperature [°C] (after HP)
    T_amb_C : float
        Ambient temperature [°C]
    m_da_kg_per_s : float
        Dry air mass flow rate [kg/s]
    cfg : SolarCollectorConfig
        Collector configuration

    Returns
    -------
    dict
        Results with keys:
        - Q_solar_kW: Heat delivered [kW]
        - T_out_C: Outlet temperature [°C]
        - eta_collector: Instantaneous efficiency [-]
        - solar_active: True if collector is providing heat
    """
    result = {
        "Q_solar_kW": 0.0,
        "T_out_C": T_in_C,
        "eta_collector": 0.0,
        "solar_active": False,
    }

    if not cfg.enabled:
        return result

    if GHI_Wm2 < cfg.GHI_threshold_W_per_m2:
        return result

    # Compute useful heat gain
    Q_solar_kW = compute_solar_useful_gain_kW(GHI_Wm2, T_in_C, T_amb_C, cfg)

    if Q_solar_kW <= 0.0:
        return result

    # Compute outlet temperature
    if m_da_kg_per_s > 0.0:
        dT = Q_solar_kW / (m_da_kg_per_s * CP_MA_KJ_PER_KG_K)
        T_out_C = T_in_C + dT

        # Limit to maximum fluid temperature
        if T_out_C > cfg.T_fluid_max_C:
            T_out_C = cfg.T_fluid_max_C
            Q_solar_kW = m_da_kg_per_s * CP_MA_KJ_PER_KG_K * (T_out_C - T_in_C)
    else:
        T_out_C = T_in_C
        Q_solar_kW = 0.0

    # Compute efficiency
    eta = compute_collector_efficiency(GHI_Wm2, T_in_C, T_amb_C, cfg)

    result["Q_solar_kW"] = Q_solar_kW
    result["T_out_C"] = T_out_C
    result["eta_collector"] = eta
    result["solar_active"] = Q_solar_kW > 0.0

    return result


def estimate_daily_solar_gain_kWh(
    GHI_hourly_Wm2: list[float],
    T_amb_hourly_C: list[float],
    T_in_avg_C: float,
    cfg: SolarCollectorConfig,
) -> float:
    """
    Estimate daily solar heat gain for preliminary sizing.

    Parameters
    ----------
    GHI_hourly_Wm2 : list[float]
        Hourly GHI values for one day [W/m²]
    T_amb_hourly_C : list[float]
        Hourly ambient temperatures [°C]
    T_in_avg_C : float
        Average collector inlet temperature [°C]
    cfg : SolarCollectorConfig
        Collector configuration

    Returns
    -------
    float
        Estimated daily useful heat [kWh]
    """
    Q_daily_kWh = 0.0

    for GHI, T_amb in zip(GHI_hourly_Wm2, T_amb_hourly_C):
        Q_hourly = compute_solar_useful_gain_kW(GHI, T_in_avg_C, T_amb, cfg)
        Q_daily_kWh += Q_hourly  # 1 hour timestep

    return Q_daily_kWh
