"""Drying kinetics utilities for Phase-1 simulations."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .config import KineticsConfig
from .knb_table import KNBTable
from .midilli_table import (
    evaluate_piecewise_midilli_MR,
    load_midilli_surfaces,
    predict_midilli_params_for_operating_point,
    build_keff_table_from_phase2,
)

from .psychro import (
    RH_from_T_omega,
    humidity_ratio_from_T_RH,
    moist_air_enthalpy_kJ_per_kg,
    temperature_from_h_omega_C,
)

# Cache for Midilli parameter tables
_knb_cache: Dict[Path, KNBTable] = {}
_KEFF_TABLE_DF: Optional[pd.DataFrame] = None


@dataclass
class MidilliCurve:
    t_min: np.ndarray
    MR: np.ndarray


def get_keff_table(cfg: KineticsConfig) -> pd.DataFrame:
    """
    Return a cached K_eff table derived from Phase-2 Midilli parameters.

    Uses cfg.phase2_models_root as the root containing phase2c_for_chamber.csv.
    """

    global _KEFF_TABLE_DF
    if _KEFF_TABLE_DF is not None:
        return _KEFF_TABLE_DF

    if cfg.phase2_models_root is None:
        raise ValueError("phase2_models_root must be set in KineticsConfig to build K_eff table.")

    _KEFF_TABLE_DF = build_keff_table_from_phase2(
        models_root=cfg.phase2_models_root,
        X0_db=cfg.X0_db_ref,
        X_eq_db=cfg.X_eq_db_ref,
    )
    return _KEFF_TABLE_DF


def K_eff_from_T_RH(
    T_in_C: float,
    RH_in_frac: float,
    cfg: KineticsConfig,
) -> float:
    """
    Return effective first-order drying coefficient K_eff [1/s].

    If cfg.use_knb_table and cfg.phase2_models_root is set, interpolate K_eff
    from the Phase-2-derived table as a function of (T_C, RH_pct, v_ms, thickness_mm).

    Otherwise, fall back to the existing simple exponential law in T and RH.
    """

    if cfg.use_knb_table and cfg.phase2_models_root is not None:
        table = get_keff_table(cfg)
        if table.empty:
            warnings.warn("K_eff table is empty; falling back to simple law.")
        else:
            RH_pct = RH_in_frac * 100.0
            v_ms = cfg.v_ms_ref
            thickness_mm = cfg.thickness_mm_ref

            features = table[["T_C", "RH_mid_pct", "v_ms", "thickness_mm"]].to_numpy()
            targets = np.array([T_in_C, RH_pct, v_ms, thickness_mm])
            diffs = features - targets
            distances = np.sum(diffs ** 2, axis=1)
            idx = int(np.argmin(distances))
            row = table.iloc[idx]
            K_eff = float(row["K_eff_1_per_s"])
            if K_eff > 0:
                return K_eff

    K_ref = cfg.K_ref_1_per_s
    dT = T_in_C - cfg.T_ref_C
    K_T = K_ref * math.exp(cfg.alpha_T_per_C * dT)
    f_RH = math.exp(-cfg.alpha_RH * RH_in_frac)
    K_eff = max(cfg.K_min_1_per_s, K_T * f_RH)
    return K_eff


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

    # Make sure models are loaded once
    load_midilli_surfaces(kin_cfg.phase2_models_root)

    # Use the mid-RH between RH_lo and RH_hi as the operating RH for the bridge
    RH_mid_pct = 0.5 * (kin_cfg.RH_lo_pct_ref + kin_cfg.RH_hi_pct_ref)

    params = predict_midilli_params_for_operating_point(
        T_C=kin_cfg.T_C_ref,
        v_ms=kin_cfg.v_ms_ref,
        thickness_mm=kin_cfg.thickness_mm_ref,
        RH_mid_pct=RH_mid_pct,
        t_split_min=kin_cfg.t_split_min_ref,
        models_root=kin_cfg.phase2_models_root,
    )

    # Global time grid in seconds, then convert to minutes for the MidilliCurve struct
    t_s_grid = np.arange(0.0, total_time_s + dt_s, dt_s)
    MR_grid = evaluate_piecewise_midilli_MR(t_s_grid, params)

    return MidilliCurve(t_min=t_s_grid / 60.0, MR=MR_grid)



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
    Compute maximum water mass [kg] that the air can take in this step such that
    the outlet RH (after adiabatic cooling) does not exceed cfg.RH_out_max_frac.
    """

    if m_da_kg_per_s <= 0.0 or dt_s <= 0.0:
        return 0.0

    h_in = moist_air_enthalpy_kJ_per_kg(T_in_C, omega_in)

    RH_max = cfg.RH_out_max_frac
    if RH_max <= 0.0 or RH_max >= 1.0:
        return float("inf")

    omega_sat_in = humidity_ratio_from_T_RH(T_in_C, 1.0)
    domega_hi = max(omega_sat_in - omega_in, cfg.min_domega_drive)
    if domega_hi <= 0:
        return 0.0

    def RH_out_for_domega(domega: float) -> float:
        omega_out = omega_in + domega
        if omega_out <= 0.0:
            return 0.0
        T_out_C = temperature_from_h_omega_C(h_in, omega_out)
        return RH_from_T_omega(T_out_C, omega_out)

    RH_hi = RH_out_for_domega(domega_hi)
    if RH_hi <= RH_max:
        m_w_rate_air_max = m_da_kg_per_s * domega_hi
        return max(0.0, m_w_rate_air_max * dt_s)

    lo, hi = 0.0, domega_hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        RH_mid = RH_out_for_domega(mid)
        if RH_mid > RH_max:
            hi = mid
        else:
            lo = mid
    domega_max = max(lo, cfg.min_domega_drive)
    m_w_rate_air_max = m_da_kg_per_s * domega_max
    dm_w_air_max = max(0.0, m_w_rate_air_max * dt_s)
    return dm_w_air_max
