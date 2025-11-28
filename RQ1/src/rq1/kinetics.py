"""Drying kinetics utilities for Phase-1 simulations."""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from .config import KineticsConfig
from .knb_table import KNBTable
from .phase2_bridge import (
    MidilliCurve,
    load_phase2_models,
    predict_segment_params,
    reconstruct_MR_piecewise_model,
)
from .psychro import humidity_ratio_from_T_RH

# Cache for Midilli parameter tables
_knb_cache: Dict[Path, KNBTable] = {}


@dataclass
class MidilliCurve:
    t_min: np.ndarray
    MR: np.ndarray


def K_eff_from_T_RH(T_in_C: float, RH_in_frac: float, cfg: KineticsConfig) -> float:
    """
    Effective drying rate coefficient K [1/s] as a function of inlet air temperature and RH.

    Base model (temperature dependence):
        K_T = K_ref * exp(alpha_T * (T_in_C - T_ref))

    Humidity factor (slows drying as RH increases):
        f_RH = exp(-alpha_RH * RH_in_frac)

    so:
        K_eff = K_T * f_RH
    """
    delta_T = T_in_C - cfg.T_ref_C
    K_T = cfg.K_ref_1_per_s * math.exp(cfg.alpha_T_per_C * delta_T)
    f_RH = math.exp(-cfg.alpha_RH * RH_in_frac)
    return K_T * f_RH


def get_knb_table(cfg: KineticsConfig) -> Optional[KNBTable]:
    """Load and cache KNBTable if configured."""

    if not cfg.knb_csv_path:
        return None

    path = cfg.knb_csv_path
    table = _knb_cache.get(path)
    if table is None:
        table = KNBTable(path)
        _knb_cache[path] = table
    return table


def get_midilli_params_for_state(
    T_in_C: float, RH_in_frac: float, cfg: KineticsConfig
) -> Optional[Tuple[float, float, float]]:
    """
    For model_type='midilli', look up (k, n, b) from KNBTable using (T, RH, v, thickness).

    Returns (k, n, b) or None if lookup is not available.
    """

    if cfg.model_type != "midilli" or not cfg.use_knb_table:
        return None

    table = get_knb_table(cfg)
    if table is None:
        return None

    return table.get_knb_nearest(
        T_C=T_in_C, RH_pct=RH_in_frac * 100.0, v_ms=cfg.v_ms, thickness_mm=cfg.thickness_mm
    )


def update_X_db_first_order(
    X_db: float,
    X_eq_db: float,
    T_in_C: float,
    RH_in_frac: float,
    dt_s: float,
    cfg: KineticsConfig,
    K_eff_override: Optional[float] = None,
) -> float:
    """
    First-order moisture update:

    X_{k+1} = X_k - K(T_in, RH_in) * (X_k - X_eq) * dt
    """

    K_eff = K_eff_override if K_eff_override is not None else K_eff_from_T_RH(T_in_C, RH_in_frac, cfg)
    X_new = X_db - K_eff * (X_db - X_eq_db) * dt_s
    return max(X_new, X_eq_db)


def compute_dm_w_kinetic_first_order(
    X_db: float,
    X_eq_db: float,
    T_in_C: float,
    RH_in_frac: float,
    dt_s: float,
    cfg: KineticsConfig,
    m_p_dry_kg: float,
) -> float:
    """
    Compute kinetic water removal (kg) over dt_s using the first-order model.

    The effective K depends on both temperature and inlet RH. Midilli hooks are in
    place via KNB tables, but the drying update still follows a first-order form.
    """

    K_eff_override: Optional[float] = None
    if cfg.model_type == "midilli":
        midilli_params = get_midilli_params_for_state(T_in_C, RH_in_frac, cfg)
        if midilli_params is not None:
            k_midilli, _, _ = midilli_params
            # Placeholder: Midilli integration will refine this mapping later.
            K_eff_override = max(cfg.K_ref_1_per_s, k_midilli)
        else:
            warnings.warn(
                "Midilli model selected but no KNB table available; falling back to simple kinetics.",
                RuntimeWarning,
            )

    X_db_new = update_X_db_first_order(
        X_db=X_db,
        X_eq_db=X_eq_db,
        T_in_C=T_in_C,
        RH_in_frac=RH_in_frac,
        dt_s=dt_s,
        cfg=cfg,
        K_eff_override=K_eff_override,
    )

    dX = max(0.0, X_db - X_db_new)
    dm_w_kin = max(0.0, m_p_dry_kg * dX)
    return dm_w_kin


def precompute_midilli_curve_from_phase2(
    kin_cfg: KineticsConfig,
    total_time_s: float,
    dt_s: float,
) -> MidilliCurve:
    """
    Precompute MR(t) over [0, total_time_s] using Phase-2 Midilli surfaces.
    """

    models = load_phase2_models(kin_cfg.phase2_models_root)
    seg = predict_segment_params(
        models=models,
        T_C=kin_cfg.T_C_ref,
        RH_lo_pct=kin_cfg.RH_lo_pct_ref,
        RH_hi_pct=kin_cfg.RH_hi_pct_ref,
        v_ms=kin_cfg.v_ms_ref,
        thickness_mm=kin_cfg.thickness_mm_ref,
    )

    t_min_grid = np.arange(0.0, total_time_s + dt_s, dt_s) / 60.0
    MR_grid = reconstruct_MR_piecewise_model(seg, t_min_grid)
    return MidilliCurve(t_min=t_min_grid, MR=MR_grid)


def X_db_from_MR(
    MR: float,
    X0_db: float,
    X_eq_db: float,
) -> float:
    return X_eq_db + MR * (X0_db - X_eq_db)


def update_X_db_phase2_midilli(
    time_s: float,
    curve: MidilliCurve,
    X0_db: float,
    X_eq_db: float,
) -> float:
    """
    Given current physical time and a precomputed MR(t) curve, return X_db(time).
    """

    time_min = time_s / 60.0
    MR_current = float(np.interp(time_min, curve.t_min, curve.MR))
    X_db = X_db_from_MR(MR_current, X0_db, X_eq_db)
    return max(X_db, X_eq_db)


def compute_dm_w_air_capacity(
    T_in_C: float,
    omega_in: float,
    m_da_kg_per_s: float,
    dt_s: float,
    cfg: KineticsConfig,
) -> float:
    """
    Compute maximum water mass [kg] that the air can take in this step based on inlet conditions.
    """

    omega_sat = humidity_ratio_from_T_RH(T_in_C, RH_frac=1.0)
    omega_out_max = min(omega_sat * cfg.RH_out_max_frac, omega_sat)
    domega_max = max(omega_out_max - omega_in, cfg.min_domega_drive)
    m_w_rate_air_max = m_da_kg_per_s * domega_max
    dm_w_air_max = max(0.0, m_w_rate_air_max * dt_s)
    return dm_w_air_max
