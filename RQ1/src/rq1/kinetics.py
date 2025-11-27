"""Simple first-order drying kinetics for Phase-1 simulations."""

import math

from .config import KineticsConfig

# Default parameters for first-order drying coefficient
K_REF = 1e-4  # 1/s
T_REF = 50.0  # °C
ALPHA = 0.05  # 1/°C


def K_eff_from_T_C(T_in_C: float, cfg: KineticsConfig) -> float:
    """Return an effective drying rate coefficient K [1/s] as a function of inlet temperature."""
    if not cfg.use_simple_K:
        # Placeholder for future Midilli/KNB integration
        raise NotImplementedError("Non-simple kinetics not implemented in Phase-1.")
    delta_T = T_in_C - T_REF
    return K_REF * math.exp(ALPHA * delta_T)


def update_X_db_first_order(
    X_db: float,
    X_eq_db: float,
    T_in_C: float,
    dt_s: float,
    cfg: KineticsConfig,
) -> float:
    """
    First-order moisture update:
    X_{k+1} = X_k - K(T_in) * (X_k - X_eq) * dt
    """
    K_eff = K_eff_from_T_C(T_in_C, cfg)
    X_new = X_db - K_eff * (X_db - X_eq_db) * dt_s
    return max(X_new, X_eq_db)


# Future extension note:
# If cfg.use_knb_table is enabled and cfg.knb_csv_path provided, the module can be extended
# to instantiate a KNBTable and derive an effective K from Midilli parameters (k, n, b)
# based on operating conditions. That logic is deferred until Phase-2.
