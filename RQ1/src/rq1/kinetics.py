"""Drying kinetics utilities for Phase-1 simulations."""

from __future__ import annotations

import math
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


def _inside_valid_box(T_in_C: float, RH_in_frac: float, cfg: KineticsConfig) -> bool:
    """Return True if (T, RH) are inside the Phase-2 validity box."""

    T_min = cfg.T_min_valid_C
    T_max = cfg.T_max_valid_C
    RH_min = getattr(cfg, "RH_min_valid_frac", cfg.RH_min_valid_frac)
    RH_max = getattr(cfg, "RH_max_valid_frac", cfg.RH_max_valid_frac)

    return T_min <= T_in_C <= T_max and RH_min <= RH_in_frac <= RH_max


def _nearest_keff_row(T_in_C: float, RH_in_frac: float, cfg: KineticsConfig) -> Optional[pd.Series]:
    """Return nearest-neighbour row from Phase-2-derived K_eff table if available."""

    if not cfg.use_knb_table or cfg.phase2_models_root is None:
        return None

    table = get_keff_table(cfg)
    if table.empty:
        return None

    RH_pct = RH_in_frac * 100.0
    dist2 = (table["T_C"] - T_in_C) ** 2 + (table["RH_mid_pct"] - RH_pct) ** 2
    idx = int(np.argmin(dist2.to_numpy()))
    return table.iloc[idx]


def K_eff_from_T_RH(
    T_in_C: float,
    RH_in_frac: float,
    cfg: KineticsConfig,
) -> float:
    """
    Return effective first-order drying coefficient K_eff [1/s] using the
    simple Arrhenius-like exponential temperature dependency and RH scaling
    used as a guardrail outside the Phase-2 validity box.
    """

    K_ref = cfg.K_ref_1_per_s
    dT = T_in_C - cfg.T_ref_C
    K_T = K_ref * math.exp(cfg.alpha_T_per_C * dT)
    f_RH = math.exp(-cfg.alpha_RH * RH_in_frac)
    K_eff = max(cfg.K_min_1_per_s, K_T * f_RH)
    return K_eff


def keff_from_state(T_in_C: float, RH_in_frac: float, cfg: KineticsConfig) -> float:
    """Return k_eff using table inside validity box and guardrail outside."""

    row = _nearest_keff_row(T_in_C, RH_in_frac, cfg)
    if row is not None:
        base_K = float(row["K_eff_1_per_s"])
        if base_K <= 0.0:
            base_K = cfg.K_min_1_per_s
        T_base_C = float(row["T_C"])
        RH_base_frac = float(row["RH_mid_pct"]) / 100.0

        if _inside_valid_box(T_in_C, RH_in_frac, cfg):
            return max(cfg.K_min_1_per_s, base_K)

        K_guard, _ = get_K_eff_from_state(
            base_K_1_per_s=base_K,
            T_in_C=T_in_C,
            RH_in_frac=RH_in_frac,
            cfg=cfg,
            T_base_C=T_base_C,
            RH_base_frac=RH_base_frac,
        )
        return max(cfg.K_min_1_per_s, K_guard)

    return K_eff_from_T_RH(T_in_C, RH_in_frac, cfg)


def get_K_eff_from_state(
    base_K_1_per_s: float,
    T_in_C: float,
    RH_in_frac: float,
    cfg: KineticsConfig,
    T_base_C: float | None = None,
    RH_base_frac: float | None = None,
) -> tuple[float, dict]:
    """
    Adjust a base kinetic coefficient using temperature/RH guardrails.

    Returns (K_eff, flags_dict) capturing whether the operating point is inside
    the strict and soft validity boxes.
    """

    if T_base_C is None:
        T_base_C = cfg.T_C_ref
    if RH_base_frac is None:
        RH_base_frac = 0.5 * (cfg.RH_lo_pct_ref + cfg.RH_hi_pct_ref) / 100.0

    T_min = cfg.T_min_valid_C
    T_max = cfg.T_max_valid_C
    T_soft_min = cfg.T_soft_min_C
    T_soft_max = cfg.T_soft_max_C

    RH_min = getattr(cfg, "RH_min_valid_frac", cfg.RH_min_valid_pct / 100.0)
    RH_max = getattr(cfg, "RH_max_valid_frac", cfg.RH_max_valid_pct / 100.0)
    RH_soft_min = cfg.RH_soft_min_pct / 100.0
    RH_soft_max = cfg.RH_soft_max_pct / 100.0

    inside_T_box = T_min <= T_in_C <= T_max
    inside_RH_box = RH_min <= RH_in_frac <= RH_max
    inside_T_soft = T_soft_min <= T_in_C <= T_soft_max
    inside_RH_soft = RH_soft_min <= RH_in_frac <= RH_soft_max

    K_eff = base_K_1_per_s

    T_in_K = T_in_C + 273.15
    T_base_K = T_base_C + 273.15
    Ea_over_R = cfg.Ea_over_R_K
    if Ea_over_R is not None and inside_T_soft:
        K_eff *= math.exp(-Ea_over_R * (1.0 / T_in_K - 1.0 / T_base_K))

    RH_eff = min(max(RH_in_frac, RH_soft_min), RH_soft_max)
    RH_eff = min(max(RH_eff, RH_min), RH_max)
    denom = 1.0 - RH_base_frac
    if denom > 1e-6:
        scale_RH = (1.0 - RH_eff) / denom
        scale_RH = min(scale_RH, cfg.max_RH_scale)
        scale_RH = max(scale_RH, 0.0)
        K_eff *= scale_RH

    flags = {
        "inside_T_box": inside_T_box,
        "inside_RH_box": inside_RH_box,
        "inside_T_soft": inside_T_soft,
        "inside_RH_soft": inside_RH_soft,
    }

    return K_eff, flags


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
    time_s: float | None = None,
) -> float:
    """
    Compute kinetic water removal (kg) over dt_s using the first-order model.

    The effective K depends on both temperature and inlet RH. Midilli hooks are in
    place via KNB tables, but the drying update still follows a first-order form.
    """

    RH_in_frac = max(0.0, min(1.0, RH_in_frac))
    k_eff = keff_from_state(T_in_C=T_in_C, RH_in_frac=RH_in_frac, cfg=cfg)

    X_db_new = X_db - k_eff * (X_db - X_eq_db) * dt_s
    X_db_new = max(X_db_new, X_eq_db)

    dX = max(0.0, X_db - X_db_new)
    dm_w_kin = max(0.0, m_p_dry_kg * dX)

    if cfg.debug_keff:
        counter = getattr(compute_dm_w_kinetic_first_order, "_debug_counter", 0) + 1
        compute_dm_w_kinetic_first_order._debug_counter = counter
        inside_T_box = cfg.T_min_valid_C <= T_in_C <= cfg.T_max_valid_C
        inside_RH_box = cfg.RH_min_valid_frac <= RH_in_frac <= cfg.RH_max_valid_frac
        should_log = counter % 60 == 0 or (time_s is not None and time_s % 3600 == 0)
        if should_log:
            print(
                f"[keff debug] t={time_s}, T={T_in_C:.2f}C, RH={RH_in_frac:.3f}, "
                f"K_eff={k_eff:.4e}, inside_T_box={inside_T_box}, inside_RH_box={inside_RH_box}"
            )

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
    h_fg_kJ_per_kg: float,
) -> float:
    """
    Compute maximum water mass [kg] that the air can take in this step such that
    the outlet RH (after latent-heat-adjusted cooling) does not exceed
    cfg.RH_out_max_frac.
    """

    if m_da_kg_per_s <= 0.0 or dt_s <= 0.0:
        return 0.0

    RH_max = cfg.RH_out_max_frac
    if RH_max <= 0.0 or RH_max >= 1.0:
        return float("inf")

    h_in = moist_air_enthalpy_kJ_per_kg(T_in_C, omega_in)
    omega_sat_in = humidity_ratio_from_T_RH(T_in_C, 1.0)
    domega_hi = max(omega_sat_in - omega_in, cfg.min_domega_drive)
    if domega_hi <= 0:
        return 0.0

    def RH_out_for_domega(domega: float) -> float:
        omega_out = omega_in + domega
        if omega_out <= 0.0:
            return 0.0
        m_w_rate_kg_per_s = m_da_kg_per_s * domega
        h_out = h_in - m_w_rate_kg_per_s * h_fg_kJ_per_kg / m_da_kg_per_s
        T_out_C = temperature_from_h_omega_C(h_out, omega_out)
        # Avoid extreme negative temperatures that can overflow Tetens correlation.
        if T_out_C < -60.0:
            T_out_C = -60.0
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
    domega_max = max(lo, 0.0)
    m_w_rate_air_max = m_da_kg_per_s * domega_max
    dm_w_air_max = max(0.0, m_w_rate_air_max * dt_s)
    return dm_w_air_max
