"""
Shared kinetic-model utilities used by:
  - baseline_arrhenius_midilli.py  (M2 baseline + LOCO-CV)
  - m1_loco_cv.py                  (M1 LOCO-CV)
  - audit_phase_b.py               (multi-start reproducibility)
  - audit_phase_c.py               (unified LOCO + bootstrap)
  - audit_phase_e.py               (parameter uncertainty)

Centralises:
  - PAVA monotonic preprocessing
  - 13-curve loader (joins phase2_targets.csv with raw data CSVs)
  - M1 (5-parameter first-order Arrhenius+RH+v+d) predictor + fitter
  - M2 (7-parameter Arrhenius+Midilli) predictor + fitter (with multi-start)
  - rmse / time-to-MR / paired bootstrap helpers

Importing scripts assume `scripts/` is on sys.path, which is automatic when
running via `python scripts/<name>.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.optimize import least_squares


# ---------------------------------------------------------------------------
# Reference constants (must match across all consumers; do not change without
# also updating outputs/audit/METHODOLOGY.md and outputs/baseline/diagnostics)
# ---------------------------------------------------------------------------
T_REF_C: float = 50.0
V_REF: float = 1.1
D_REF: float = 6.0
RH_REF: float = 42.5
R_GAS: float = 8.314  # J/mol/K


# ---------------------------------------------------------------------------
# M1: 5-parameter first-order Arrhenius+RH+v+d (live SAHPD path)
# Parameters: [logK_ref, Ea_over_R, alpha_RH, gamma_v, delta_d]
# ---------------------------------------------------------------------------
M1_LO = np.array([np.log(1e-7),     0.0,   0.0, -3.0, -3.0])
M1_HI = np.array([np.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])
M1_NOM = np.array([np.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])


# ---------------------------------------------------------------------------
# M2: 7-parameter Arrhenius+Midilli (paper-baseline)
# Parameters: [logA, Ea_J_per_mol, n0, n_T, n_v, b0, b_RH]
# ---------------------------------------------------------------------------
M2_LO = np.array([np.log(1e-8),     0.0, 0.5, -0.05, -0.5, -2e-3, -5e-4])
M2_HI = np.array([np.log(10.0), 200_000.0, 2.5,  0.05,  0.5,  2e-3,  5e-4])
M2_NOM = np.array([np.log(0.005), 25_000.0, 1.10, 0.0, 0.0, -1e-4, -5e-6])


# ===========================================================================
# Preprocessing
# ===========================================================================
def pava(mr_s: np.ndarray) -> np.ndarray:
    """Pool-Adjacent-Violators: monotone-decreasing isotonic regression.

    Used to clean raw MR(t) curves before fitting (handles measurement noise
    that produces brief upticks).
    """
    blocks: List = []
    for v in mr_s:
        blocks.append((float(v), 1))
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            (a, ca), (b, cb) = blocks[-2], blocks[-1]
            blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
    iso = np.empty_like(mr_s)
    i = 0
    for value, count in blocks:
        iso[i:i + count] = value
        i += count
    return iso


def load_curves(targets_csv: Path, data_dir: Path) -> List[Dict]:
    """Load all 13 thin-layer drying curves listed in `targets_csv`.

    Each entry contains:
      dataset, t (min), mr (PAVA-cleaned), T_C, v_ms, d_mm, RH_pct
    """
    df = pd.read_csv(targets_csv)
    out: List[Dict] = []
    for _, r in df.iterrows():
        raw = pd.read_csv(data_dir / f"{r['dataset']}.csv")
        time = raw["time_min"].astype(float).to_numpy()
        x = raw["X_db"].astype(float).to_numpy()
        order = np.argsort(time)
        time_s = time[order]
        mr_raw = np.clip(x[order] / x[order][0], 0.0, 1.1).astype(float)
        out.append(dict(
            dataset=str(r["dataset"]),
            t=time_s,
            mr=pava(mr_raw),
            T_C=float(r["T_C"]),
            v_ms=float(r["v_ms"]),
            d_mm=float(r["thickness_mm"]),
            RH_pct=float(r["RH_mid_pct"]),
        ))
    return out


# ===========================================================================
# M1 predictor + fitter
# ===========================================================================
def m1_predict(t_min, T_C, RH_pct, v_ms, d_mm, p) -> np.ndarray:
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K = T_C + 273.15
    T_ref_K = T_REF_C + 273.15
    K = (K_ref
         * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
         * np.exp(-alpha_RH * RH_pct / 100.0)
         * (v_ms / V_REF) ** gamma_v
         * (D_REF / d_mm) ** delta_d)
    return np.clip(np.exp(-K * np.maximum(t_min * 60.0, 0.0)), 0.0, 1.1)


def fit_m1(curves: List[Dict], p0: Optional[np.ndarray] = None):
    """OLS log-linear fit for M1 (convex; one start is enough)."""
    if p0 is None:
        p0 = M1_NOM

    def res(p):
        return np.concatenate([
            m1_predict(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p)
            - c["mr"]
            for c in curves
        ])
    return least_squares(res, p0, bounds=(M1_LO, M1_HI), method="trf",
                         max_nfev=20_000, xtol=1e-12, ftol=1e-12)


# ===========================================================================
# M2 predictor + fitter (with multi-start to escape local minima)
# ===========================================================================
def m2_predict(t_min, T_C, v_ms, RH_pct, p) -> np.ndarray:
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA)
    T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = n0 + n_T * (T_C - T_REF_C) + n_v * (v_ms - V_REF)
    n = max(0.2, min(2.5, n))
    b = b0 + b_RH * (RH_pct - RH_REF)
    safe = np.maximum(t_min, 0.0)
    return np.clip(np.exp(-k * np.power(safe, n)) + b * safe, 0.0, 1.1)


def fit_m2_one(curves: List[Dict], p0: np.ndarray):
    """Single-start M2 least-squares fit. Returns scipy OptimizeResult."""
    def res(p):
        return np.concatenate([
            m2_predict(c["t"], c["T_C"], c["v_ms"], c["RH_pct"], p) - c["mr"]
            for c in curves
        ])
    return least_squares(res, p0, bounds=(M2_LO, M2_HI), method="trf",
                         max_nfev=20_000, xtol=1e-12, ftol=1e-12)


def fit_m2_multistart(
    curves: List[Dict],
    n_starts: int = 5,
    seed: int = 0,
) -> np.ndarray:
    """Multi-start M2 fit. Phase B audit (2026-04-29) showed ~30% of random
    starts get trapped at local minima where b0 saturates the lower bound;
    multi-start with the literature-prior nominal as start 0 reliably finds
    the global minimum.

    Returns the parameter vector with the lowest LS cost.
    """
    rng = np.random.default_rng(seed)
    starts = [M2_NOM] + [rng.uniform(M2_LO, M2_HI) for _ in range(n_starts - 1)]
    best_x: Optional[np.ndarray] = None
    best_cost: float = np.inf
    for p0 in starts:
        try:
            sol = fit_m2_one(curves, p0)
            if float(sol.cost) < best_cost:
                best_cost = float(sol.cost)
                best_x = sol.x
        except Exception:
            continue
    if best_x is None:
        raise RuntimeError("All M2 multi-start fits failed")
    return best_x


# ===========================================================================
# Metrics
# ===========================================================================
def rmse(a: np.ndarray, b: np.ndarray) -> float:
    """RMSE on the finite intersection of two arrays."""
    m = np.isfinite(a) & np.isfinite(b)
    if not np.any(m):
        return float("nan")
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def rmse_full(
    curves: List[Dict],
    predict_fn: Callable[[Dict, np.ndarray], np.ndarray],
    p: np.ndarray,
) -> float:
    """Pooled RMSE across all curves under predict_fn(curve, p)."""
    preds = [predict_fn(c, p) for c in curves]
    truths = [c["mr"] for c in curves]
    a = np.concatenate(preds)
    b = np.concatenate(truths)
    return rmse(a, b)


def metrics_mr(actual: np.ndarray, pred: np.ndarray, n_params: int = 7) -> Dict:
    """Standard fit-quality block: rmse, r2, mbe, chi2_red, ef."""
    mask = np.isfinite(actual) & np.isfinite(pred)
    a = actual[mask]
    p = pred[mask]
    if a.size == 0:
        return dict(rmse=float("nan"), r2=float("nan"), mbe=float("nan"),
                    chi2_red=float("nan"), ef=float("nan"))
    res = a - p
    sse = float(np.sum(res * res))
    sst = float(np.sum((a - a.mean()) ** 2))
    rmse_v = float(np.sqrt(sse / a.size))
    r2 = 1.0 - sse / sst if sst > 0 else float("nan")
    mbe = float(np.mean(res))
    dof = max(a.size - n_params, 1)
    return dict(rmse=rmse_v, r2=r2, mbe=mbe, chi2_red=sse / dof, ef=r2)


def time_at_mr(time_min: np.ndarray, mr: np.ndarray, target: float = 0.1) -> float:
    """Linear interpolation of the time at which MR first crosses `target`."""
    if mr[0] < target:
        return float(time_min[0])
    if mr[-1] > target:
        return float("nan")
    for i in range(1, len(mr)):
        if mr[i] <= target:
            t1, t2 = time_min[i - 1], time_min[i]
            m1, m2 = mr[i - 1], mr[i]
            if m1 == m2:
                return float(t1)
            return float(t1 + (target - m1) * (t2 - t1) / (m2 - m1))
    return float("nan")


def paired_bootstrap(diff_vec: np.ndarray, n_boot: int = 5000, seed: int = 1) -> Dict:
    """Paired bootstrap on a per-curve difference vector.

    Returns mean of differences with 95% CI on the bootstrap distribution
    of the mean. Uses with-replacement sampling at the curve level.
    """
    rng = np.random.default_rng(seed)
    n = len(diff_vec)
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[b] = diff_vec[idx].mean()
    return dict(
        mean=float(diff_vec.mean()),
        ci95_lo=float(np.percentile(means, 2.5)),
        ci95_hi=float(np.percentile(means, 97.5)),
        boot_se=float(means.std()),
    )
