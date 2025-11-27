"""Basic psychrometric relationships for 0–60 °C air."""

from __future__ import annotations

import math

P_ATM_PA = 101_325.0
CP_DA_KJ_PER_KG_K = 1.006
CP_VAP_KJ_PER_KG_K = 1.86
H_FG0_KJ_PER_KG = 2501.0


def p_sat_water_Pa(T_C: float) -> float:
    """Return saturation vapor pressure of water in Pa using Tetens correlation."""
    return 610.94 * math.exp(17.625 * T_C / (T_C + 243.04))


def humidity_ratio_from_T_RH(T_C: float, RH_frac: float, p_total_Pa: float = P_ATM_PA) -> float:
    """Compute humidity ratio omega from temperature and relative humidity fraction."""
    p_sat = p_sat_water_Pa(T_C)
    p_v = RH_frac * p_sat
    return 0.62198 * p_v / (p_total_Pa - p_v)


def RH_from_T_omega(T_C: float, omega: float, p_total_Pa: float = P_ATM_PA) -> float:
    """Compute relative humidity fraction from temperature and humidity ratio."""
    p_v = omega * p_total_Pa / (0.62198 + omega)
    return p_v / p_sat_water_Pa(T_C)


def moist_air_enthalpy_kJ_per_kg(T_C: float, omega: float) -> float:
    """Specific enthalpy of moist air in kJ/kg based on standard HVAC formula."""
    return CP_DA_KJ_PER_KG_K * T_C + omega * (H_FG0_KJ_PER_KG + CP_VAP_KJ_PER_KG_K * T_C)


def temperature_from_h_omega_C(h_kJ_per_kg: float, omega: float) -> float:
    """Invert moist air enthalpy to solve for temperature (°C)."""
    denominator = CP_DA_KJ_PER_KG_K + omega * CP_VAP_KJ_PER_KG_K
    if denominator == 0:
        raise ValueError("Denominator for temperature inversion is zero.")
    return (h_kJ_per_kg - omega * H_FG0_KJ_PER_KG) / denominator

def dewpoint_from_omega_C(
    omega: float,
    p_total_Pa: float = P_ATM_PA,
    T_min_C: float = -20.0,
    T_max_C: float = 60.0,
    max_iter: int = 40,
) -> float:
    """
    Compute the dewpoint temperature [°C] for a given humidity ratio omega
    at total pressure p_total_Pa.

    Definition: T_dp such that air at T_dp is saturated (RH = 1) and has
    the given humidity ratio omega.

    We solve for T in:
        omega = humidity_ratio_from_T_RH(T, RH=1.0)

    using a simple bisection in [T_min_C, T_max_C].
    """
    # If omega is extremely small or negative, return something cold.
    if omega <= 0.0:
        return T_min_C

    lo = T_min_C
    hi = T_max_C

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        omega_mid = humidity_ratio_from_T_RH(mid, 1.0, p_total_Pa)
        if omega_mid > omega:
            hi = mid
        else:
            lo = mid

    return 0.5 * (lo + hi)



if __name__ == "__main__":
    T_test = 30.0
    RH_test = 0.5
    omega = humidity_ratio_from_T_RH(T_test, RH_test)
    RH_back = RH_from_T_omega(T_test, omega)
    h = moist_air_enthalpy_kJ_per_kg(T_test, omega)
    T_back = temperature_from_h_omega_C(h, omega)
    print(f"omega={omega:.4f} kg/kg, RH back={RH_back:.3f}, T back={T_back:.2f} C")
