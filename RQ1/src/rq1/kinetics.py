"""Drying kinetics utilities for Phase-1 simulations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import NearestNDInterpolator

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
_KEFF_INTERP: Optional[Tuple] = None  # (linear_interp, nearest_interp, avg_df)
_PARAMETRIC_PARAMS: Optional[Dict] = None  # Fitted parametric K_eff model


@dataclass
class MidilliCurve:
    t_min: np.ndarray
    MR: np.ndarray


# ==============================================================================
# GAB SORPTION ISOTHERM
# ==============================================================================
# Parameters for apple desorption from Kaymak-Ertekin & Gedik (2004),
# Maroulis et al. (1988), Mbarek & Mihoubi (2019).
# Fitted to 28 experimental points across 30-60C, RMSE = 0.005 kg/kg db.

_GAB_R = 8.314       # Universal gas constant [J/(mol*K)]
_GAB_Xm0 = 3.141e-3  # Monolayer pre-exponential [kg/kg db]
_GAB_dH_xm = 8057.0  # Monolayer enthalpy [J/mol]
_GAB_C0 = 4.923e-3   # Guggenheim pre-exponential [-]
_GAB_dHc = 17241.0    # Guggenheim enthalpy [J/mol]
_GAB_K0 = 0.9904      # Multilayer pre-exponential [-]
_GAB_dHk = -0.8       # Multilayer enthalpy [J/mol] (K ~ constant)


def gab_equilibrium_moisture(T_C: float, RH_frac: float) -> float:
    """GAB sorption isotherm: equilibrium moisture for apple [kg/kg db].

    X_eq = (Xm * C * K * aw) / ((1 - K*aw) * (1 - K*aw + C*K*aw))

    where aw = RH (fraction), and Xm, C, K are temperature-dependent.
    """
    if RH_frac <= 0.0:
        return 0.0
    aw = min(RH_frac, 0.95)  # Clamp to avoid singularity at aw=1/K

    T_K = T_C + 273.15
    Xm = _GAB_Xm0 * math.exp(_GAB_dH_xm / (_GAB_R * T_K))
    C = _GAB_C0 * math.exp(_GAB_dHc / (_GAB_R * T_K))
    K = _GAB_K0 * math.exp(_GAB_dHk / (_GAB_R * T_K))

    denom = (1.0 - K * aw) * (1.0 - K * aw + C * K * aw)
    if denom <= 0.0:
        return Xm  # Fallback: return monolayer moisture
    return Xm * C * K * aw / denom


def get_keff_table(cfg: KineticsConfig) -> pd.DataFrame:
    """
    Return a cached K_eff table derived from Phase-2 Midilli parameters.

    Uses cfg.phase2_models_root as the root containing phase2c_for_chamber.csv.
    """

    global _KEFF_TABLE_DF, _KEFF_INTERP, _PARAMETRIC_PARAMS
    if _KEFF_TABLE_DF is not None:
        return _KEFF_TABLE_DF

    if cfg.phase2_models_root is None:
        raise ValueError("phase2_models_root must be set in KineticsConfig to build K_eff table.")

    _KEFF_INTERP = None  # Clear interpolator when table is rebuilt
    _PARAMETRIC_PARAMS = None  # Clear parametric model when table is rebuilt
    _KEFF_TABLE_DF = build_keff_table_from_phase2(
        models_root=cfg.phase2_models_root,
        X0_db=cfg.X0_db_ref,
        X_eq_db=cfg.X_eq_db_ref,
    )
    return _KEFF_TABLE_DF


# ---------------------------------------------------------------------------
# M1 fit reference state and parameter bounds.
# These constants MUST match scripts/_kinetics_common.py:T_REF_C/V_REF/D_REF/
# M1_LO/M1_HI/M1_NOM so that the live simulation and the audit pipeline
# (Phases A-F) operate on byte-equal parameter vectors.
# ---------------------------------------------------------------------------
_M1_T_REF_C = 50.0
_M1_V_REF = 1.1
_M1_D_REF = 6.0
_M1_LO = np.array([math.log(1e-7),     0.0,   0.0, -3.0, -3.0])
_M1_HI = np.array([math.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])
_M1_NOM = np.array([math.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])


def _pava_monotone(mr: np.ndarray) -> np.ndarray:
    """Pool-Adjacent-Violators isotonic regression (monotone decreasing).

    Cleans noise-driven up-ticks in MR(t) before fitting. Algorithm matches
    scripts/_kinetics_common.py:pava() byte-for-byte.
    """
    blocks = []
    for v in mr:
        blocks.append((float(v), 1))
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            (a, ca), (b, cb) = blocks[-2], blocks[-1]
            blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
    iso = np.empty_like(mr)
    i = 0
    for value, count in blocks:
        iso[i:i + count] = value
        i += count
    return iso


def _load_raw_curves_for_m1_fit(targets_csv: Path, data_dir: Path):
    """Load all 13 thin-layer curves listed in targets_csv with PAVA cleaning.

    Mirrors scripts/_kinetics_common.py:load_curves() exactly.
    """
    df = pd.read_csv(targets_csv)
    out = []
    for _, r in df.iterrows():
        raw = pd.read_csv(data_dir / f"{r['dataset']}.csv")
        time = raw["time_min"].astype(float).to_numpy()
        x = raw["X_db"].astype(float).to_numpy()
        order = np.argsort(time)
        time_s = time[order]
        mr_raw = np.clip(x[order] / x[order][0], 0.0, 1.1).astype(float)
        # RH read from raw CSV (single source of truth, matches Royen Table 1).
        # phase2_targets.RH_mid_pct was filled with literature default 42.5 for
        # stems without an RH token, mislabeling the four thickness-sweep runs.
        rh_pct = float(raw["RH_pct"].iloc[0])
        out.append(dict(
            dataset=str(r["dataset"]),
            t=time_s,
            mr=_pava_monotone(mr_raw),
            T_C=float(r["T_C"]),
            v_ms=float(r["v_ms"]),
            d_mm=float(r["thickness_mm"]),
            RH_pct=rh_pct,
        ))
    return out


def _m1_predict_mr(t_min, T_C, RH_pct, v_ms, d_mm, p):
    """M1 first-order Arrhenius+RH+v+d MR(t) prediction. Matches Phase E."""
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = math.exp(logK_ref)
    T_K = T_C + 273.15
    T_ref_K = _M1_T_REF_C + 273.15
    K = (K_ref
         * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
         * np.exp(-alpha_RH * RH_pct / 100.0)
         * (v_ms / _M1_V_REF) ** gamma_v
         * (_M1_D_REF / d_mm) ** delta_d)
    return np.clip(np.exp(-K * np.maximum(t_min * 60.0, 0.0)), 0.0, 1.1)


def _fit_parametric_keff(cfg: KineticsConfig) -> Optional[Dict]:
    """Fit M1 K_eff(T, RH, v, d) by single-stage NLS on raw MR(t) curves.

    Five-parameter first-order Arrhenius with RH, velocity, and thickness
    corrections:
        K = K_ref * exp((Ea/R)(1/T_ref - 1/T)) * exp(-alpha * RH/100)
              * (v/v_ref)^gamma * (d_ref/d)^delta
        MR(t) = exp(-K * t_seconds)

    Fitted by scipy.optimize.least_squares on PAVA-cleaned MR(t) data from
    all 13 thin-layer drying curves simultaneously. Reference state is
    fixed at T_ref=50C, v_ref=1.1 m/s, d_ref=6 mm to match the audit
    pipeline (scripts/_kinetics_common.py and audit Phases A-F).

    Returns a dict of physical parameters plus fit diagnostics. Falls back
    to the legacy two-stage log-linear OLS if the raw-data path is not
    locatable, and labels the result accordingly via `fit_protocol`.
    """
    global _PARAMETRIC_PARAMS
    if _PARAMETRIC_PARAMS is not None:
        return _PARAMETRIC_PARAMS

    if cfg.phase2_models_root is None:
        return None

    # Locate raw curves and Phase-2 targets CSV from phase2_models_root.
    # Layout: <project>/data/<dataset>.csv and
    #         <project>/outputs/phase2/phase2_targets.csv
    # phase2_models_root is typically <project>/RQ1/outputs.
    project_root = cfg.phase2_models_root.parent.parent
    targets_csv = project_root / "outputs" / "phase2" / "phase2_targets.csv"
    data_dir = project_root / "data"

    use_nls = targets_csv.exists() and data_dir.exists()
    if use_nls:
        try:
            curves = _load_raw_curves_for_m1_fit(targets_csv, data_dir)
        except Exception as exc:
            print(f"[kinetics] raw-curve load failed ({exc}); falling back to OLS")
            use_nls = False
    if use_nls and len(curves) < 3:
        use_nls = False

    if use_nls:
        # Single-stage NLS on raw MR(t) - matches Phase E protocol.
        from scipy.optimize import least_squares

        def res(p):
            return np.concatenate([
                _m1_predict_mr(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p)
                - c["mr"]
                for c in curves
            ])

        sol = least_squares(res, _M1_NOM, bounds=(_M1_LO, _M1_HI),
                            method="trf", max_nfev=20_000,
                            xtol=1e-12, ftol=1e-12)
        beta = sol.x
        n_obs = sum(len(c["t"]) for c in curves)
        n_par = len(beta)
        SS_res = float(np.sum(sol.fun ** 2))
        sigma2_mr = SS_res / max(n_obs - n_par, 1)
        rmse_mr = float(math.sqrt(SS_res / n_obs))

        params = {
            "K_ref": math.exp(beta[0]),
            "Ea_over_R": float(beta[1]),
            "alpha_RH": float(beta[2]),
            "gamma_v": float(beta[3]),
            "delta_d": float(beta[4]),
            "T_ref_K": _M1_T_REF_C + 273.15,
            "v_ref": _M1_V_REF,
            "d_ref": _M1_D_REF,
            "fit_protocol": "single-stage NLS on raw MR(t)",
            "n_curves": len(curves),
            "n_obs": int(n_obs),
            "sigma2_mr": float(sigma2_mr),
            "RMSE_mr": rmse_mr,
        }
    else:
        # Legacy fallback: two-stage log-linear OLS on K-summary table.
        # Kept so simulations can still run if the raw-data path is missing,
        # but emits a warning so the user notices the protocol downgrade.
        table = get_keff_table(cfg)
        if table.empty or len(table) < 3:
            return None
        T_ref_K_legacy = cfg.T_ref_C + 273.15
        T_K = table["T_C"].values + 273.15
        RH_frac = table["RH_mid_pct"].values / 100.0
        v = table["v_ms"].values
        d = table["thickness_mm"].values
        K_data = table["K_eff_1_per_s"].values
        y = np.log(K_data)
        X = np.column_stack([
            np.ones(len(table)),
            1.0 / T_ref_K_legacy - 1.0 / T_K,
            RH_frac,
            np.log(v / cfg.v_ms),
            np.log(cfg.thickness_mm / d),
        ])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        SS_res = float(np.sum((y - X @ beta) ** 2))
        SS_tot = float(np.sum((y - np.mean(y)) ** 2))
        R2 = 1.0 - SS_res / SS_tot if SS_tot > 0 else 0.0
        params = {
            "K_ref": math.exp(beta[0]),
            "Ea_over_R": float(beta[1]),
            "alpha_RH": float(-beta[2]),
            "gamma_v": float(beta[3]),
            "delta_d": float(beta[4]),
            "T_ref_K": T_ref_K_legacy,
            "v_ref": cfg.v_ms,
            "d_ref": cfg.thickness_mm,
            "fit_protocol": "two-stage log-linear OLS on K-summary (LEGACY)",
            "n_curves": int(len(table)),
            "n_obs": int(len(table)),
            "R2_log_K": R2,
            "RMSE_log_K": float(math.sqrt(SS_res / len(table))),
        }
        print("[kinetics] WARNING: raw-curve path missing, using legacy OLS fit")

    # Print fit summary
    print(f"\n{'='*70}")
    print(f"PARAMETRIC K_eff MODEL  ({params['fit_protocol']})")
    print(f"{'='*70}")
    print(f"  K_ref    = {params['K_ref']:.4e} 1/s  (at T={params['T_ref_K']-273.15:.1f}C, "
          f"RH=0%, v={params['v_ref']}, d={params['d_ref']}mm)")
    print(f"  Ea/R     = {params['Ea_over_R']:.0f} K   "
          f"(Ea = {params['Ea_over_R']*8.314/1000.0:.2f} kJ/mol)")
    print(f"  alpha_RH = {params['alpha_RH']:.3f}")
    print(f"  gamma_v  = {params['gamma_v']:.3f}")
    print(f"  delta_d  = {params['delta_d']:.3f}")
    if "RMSE_mr" in params:
        print(f"  RMSE(MR)   = {params['RMSE_mr']:.5f}   "
              f"sigma2 = {params['sigma2_mr']:.4e}")
        print(f"  n_curves = {params['n_curves']}, n_obs = {params['n_obs']}")
    else:
        print(f"  R2(ln K)   = {params['R2_log_K']:.4f}")
        print(f"  RMSE(ln K) = {params['RMSE_log_K']:.4f}")
        print(f"  n_points = {params['n_obs']}")
    print(f"{'='*70}\n")

    _PARAMETRIC_PARAMS = params
    return params


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
    """Return K_eff using parametric model fitted from all Phase-2 experiments.

    K_eff(T, RH, v, d) = K_ref * exp(Ea/R * (1/T_ref - 1/T))
                               * exp(-alpha * RH)
                               * (v/v_ref)^gamma
                               * (d_ref/d)^delta
    """
    if cfg.use_knb_table and cfg.phase2_models_root is not None:
        params = _fit_parametric_keff(cfg)
        if params is not None:
            T_K = T_in_C + 273.15
            ln_K = (
                math.log(params["K_ref"])
                + params["Ea_over_R"] * (1.0 / params["T_ref_K"] - 1.0 / T_K)
                - params["alpha_RH"] * RH_in_frac
                + params["gamma_v"] * math.log(cfg.v_ms / params["v_ref"])
                + params["delta_d"] * math.log(params["d_ref"] / cfg.thickness_mm)
            )
            return max(cfg.K_min_1_per_s, math.exp(ln_K))

    # Fallback: Arrhenius + RH scaling from config parameters
    return K_eff_from_T_RH(T_in_C, RH_in_frac, cfg)


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
    if cfg.debug_keff:
        print(f"[Keff LOG] t={time_s:.0f}s | T={T_in_C:.1f}°C | RH={RH_in_frac:.2f} | Keff={k_eff:.5e} s^-1")

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
    p_atm_Pa: float = 101325.0,
) -> float:
    """
    Compute maximum water mass [kg] that the air can take in this step such that
    the outlet RH (after latent-heat-adjusted cooling) does not exceed
    cfg.RH_out_max_frac.

    p_atm_Pa must match the pressure used when computing omega_in (e.g. 86120 Pa
    at Kathmandu).  Using the wrong pressure here causes the RH back-calculation
    to return an artificially high value, forcing dm_air_max = 0 at high altitude.
    """

    if m_da_kg_per_s <= 0.0 or dt_s <= 0.0:
        return 0.0

    RH_max = cfg.RH_out_max_frac
    if RH_max <= 0.0 or RH_max > 1.0:
        return float("inf")

    h_in = moist_air_enthalpy_kJ_per_kg(T_in_C, omega_in)
    omega_sat_in = humidity_ratio_from_T_RH(T_in_C, 1.0, p_atm_Pa)
    domega_hi = max(omega_sat_in - omega_in, cfg.min_domega_drive)
    if domega_hi <= 0:
        return 0.0

    def RH_out_for_domega(domega: float) -> float:
        omega_out = omega_in + domega
        if omega_out <= 0.0:
            return 0.0
        # Correct: constant-enthalpy humidification + liquid water correction
        h_out = h_in + domega * 4.186 * T_in_C
        T_out_C = temperature_from_h_omega_C(h_out, omega_out)
        # Avoid extreme negative temperatures that can overflow Tetens correlation.
        if T_out_C < -60.0:
            T_out_C = -60.0
        return RH_from_T_omega(T_out_C, omega_out, p_atm_Pa)

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
