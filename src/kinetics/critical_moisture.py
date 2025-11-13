"""Detection of the critical moisture content from drying experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess


@dataclass
class CriticalMoistureResult:
    """Summary of the detected drying split."""
    t_split: float
    Xc: float
    left_indices: np.ndarray
    right_indices: np.ndarray
    a0: float
    b1: float
    b2: float
    bic_split: float
    bic_null: float
    delta_bic: float


def _as_float_array(values: Sequence[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Inputs must be one-dimensional sequences of floats.")
    return arr


def _enforce_strictly_increasing(time: np.ndarray, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if time.size <= 1:
        return time, values
    order = np.argsort(time, kind="mergesort")
    t = time[order]
    v = values[order]
    dt = np.diff(t)
    if np.all(dt > 0):
        return t, v
    keep = np.ones(t.size, dtype=bool)
    keep[1:] = dt > 0
    return t[keep], v[keep]


def detect_critical_moisture(
    time_min: Sequence[float] | np.ndarray,
    x_db: Sequence[float] | np.ndarray,
    *,
    lowess_frac: float = 0.15,
    lambda_const: float = 5.0,
    acceptance_delta: float = 6.0,
    debug: bool = False,
) -> Optional[CriticalMoistureResult]:
    """Detect the critical moisture point using a constrained bilinear fit on drying rate."""
    # guards
    lowess_frac = float(np.clip(lowess_frac, 0.05, 0.60))
    lambda_const = float(max(lambda_const, 0.0))
    acceptance_delta = float(max(acceptance_delta, 0.0))

    time = _as_float_array(time_min)
    values = _as_float_array(x_db)
    if time.size != values.size:
        raise ValueError("time and x_db must have the same length")

    mask = np.isfinite(time) & np.isfinite(values)
    time = time[mask]
    values = values[mask]
    if time.size < 2:
        if debug: print("[detect] abort: <2 samples after finite filter")
        return None

    time, values = _enforce_strictly_increasing(time, values)
    if time.size < 2:
        if debug: print("[detect] abort: <2 samples after enforcing increasing time")
        return None

    smoothed = (
        lowess(values, time, frac=lowess_frac, return_sorted=False)
        if (time.size >= 3 and lowess_frac > 0)
        else values.copy()
    )

    dt = np.diff(time)
    if not np.all(dt > 0):
        pos = dt > 0
        keep = np.ones(time.size, dtype=bool)
        keep[1:] = pos
        time = time[keep]
        values = values[keep]
        smoothed = smoothed[keep]
        dt = np.diff(time)
    if time.size < 2:
        if debug: print("[detect] abort: <2 samples after dt>0 filter")
        return None

    # finite-difference drying rate (positive)
    rate = -(smoothed[1:] - smoothed[:-1]) / dt
    midpoint_time = 0.5 * (time[1:] + time[:-1])
    midpoint_x = 0.5 * (values[1:] + values[:-1])

    pos_mask = rate > 0
    rate = rate[pos_mask]
    midpoint_time = midpoint_time[pos_mask]
    midpoint_x = midpoint_x[pos_mask]

    # ---- EARLY-WINDOW GATE (choose an early fraction, e.g., 0.30 = first 30% of run) ----
    early_frac = 0.35  # adjust once; 0.25–0.35 is typical for end-of-constant-rate
    max_t = time[-1] * early_frac
    keep_early = midpoint_time <= max_t

    rate = rate[keep_early]
    midpoint_time = midpoint_time[keep_early]
    midpoint_x = midpoint_x[keep_early]

    m = rate.size
    if m == 0:
        if debug: print("[detect] abort: m=0 after positivity filter")
        return None

    min_leaf = max(8, int(np.ceil(0.08 * m)))
    if m < 2 * min_leaf:
        if debug: print(f"[detect] abort: m={m} < 2*min_leaf={2*min_leaf}")
        return None

    start = min_leaf - 1
    stop = m - min_leaf
    if start >= stop:
        if debug: print(f"[detect] abort: empty candidate window [{start},{stop})")
        return None

    best_bic = np.inf
    best_params: Optional[tuple[int, float, float, float, float]] = None
    eps = 1e-12

    for k in range(start, stop):
        Xc = midpoint_x[k]
        u = midpoint_x - Xc

        left_mask = (np.arange(m) <= k)
        right_mask = ~left_mask

        r_left, u_left = rate[left_mask], u[left_mask]
        r_right, u_right = rate[right_mask], u[right_mask]
        if r_left.size == 0 or r_right.size == 0:
            continue

        # design matrix: intercept shared; slope right uses u_right; slope left uses u_left
        n_right = r_right.size
        A = np.zeros((m, 3), dtype=float)
        b = np.concatenate([r_right, r_left])

        A[:n_right, 0] = 1.0
        A[:n_right, 1] = u_right
        A[n_right:, 0] = 1.0
        A[n_right:, 2] = u_left

        # initial ridge solve on both slopes
        AtA = A.T @ A
        Atb = A.T @ b
        AtA[1, 1] += lambda_const
        AtA[2, 2] += lambda_const
        try:
            a0, b1, b2 = np.linalg.solve(AtA, Atb)
        except np.linalg.LinAlgError:
            a0, b1, b2 = tuple(np.linalg.pinv(AtA) @ Atb)

        # enforce nonnegativity of slopes (rates must decay with X)
        active = [True, True]
        if b1 < 0.0:
            b1 = 0.0
            active[0] = False
        if b2 < 0.0:
            b2 = 0.0
            active[1] = False

        if not active[0] and not active[1]:
            # constant rate segment
            a0 = float(np.mean(b))
            b1 = 0.0
            b2 = 0.0
        elif not all(active):
            cols = [0]
            if active[0]:
                cols.append(1)
            if active[1]:
                cols.append(2)
            A_act = A[:, cols]
            AtA_act = A_act.T @ A_act
            # ridge only on active slope columns
            if active[0] and active[1]:
                AtA_act[1, 1] += lambda_const
                AtA_act[2, 2] += lambda_const
            else:
                AtA_act[1, 1] += lambda_const
            Atb_act = A_act.T @ b
            try:
                theta = np.linalg.solve(AtA_act, Atb_act)
            except np.linalg.LinAlgError:
                theta = np.linalg.pinv(AtA_act) @ Atb_act
            a0 = float(theta[0])
            if active[0] and active[1]:
                b1, b2 = float(theta[1]), float(theta[2])
            elif active[0] and not active[1]:
                b1, b2 = float(theta[1]), 0.0
            else:
                b1, b2 = 0.0, float(theta[1])

        # residuals and BIC with ridge penalty on active slopes only
        pred_right = a0 + b1 * u_right
        pred_left = a0 + b2 * u_left
        resid = np.concatenate([r_right - pred_right, r_left - pred_left])
        ridge_pen = ((b1 if active[0] else 0.0) ** 2 + (b2 if active[1] else 0.0) ** 2)
        rss = float(np.sum(resid ** 2) + lambda_const * ridge_pen)
        rss = max(rss, eps)

        p = 1 + int(active[0]) + int(active[1])  # intercept + active slopes
        bic = m * np.log(rss / m) + p * np.log(m)

        if bic < best_bic:
            best_bic = bic
            best_params = (k, a0, b1, b2, Xc)

    if best_params is None:
        if debug: print("[detect] abort: no solvable candidate produced a finite BIC")
        return None

    k_star, a0_star, b1_star, b2_star, Xc_star = best_params

    # null (no split): single ridge linear in X
    A0 = np.column_stack([np.ones(m), midpoint_x])
    AtA0 = A0.T @ A0
    Atb0 = A0.T @ rate
    AtA0[1, 1] += lambda_const
    try:
        alpha, beta = np.linalg.solve(AtA0, Atb0)
    except np.linalg.LinAlgError:
        alpha, beta = tuple(np.linalg.pinv(AtA0) @ Atb0)

    resid0 = rate - (alpha + beta * midpoint_x)
    rss0 = float(np.sum(resid0 ** 2) + lambda_const * (beta ** 2))
    rss0 = max(rss0, eps)
    bic0 = m * np.log(rss0 / m) + 2 * np.log(m)

    delta = bic0 - best_bic

    left_idx = np.arange(0, k_star + 1, dtype=int)
    right_idx = np.arange(k_star + 1, m, dtype=int)
    if debug:
        print(f"[detect] m={m}  min_leaf={min_leaf}  cand=[{start},{stop})")
        print(f"[detect] best t≈{midpoint_time[k_star]:.3f}  Xc≈{Xc_star:.6f}  ΔBIC={delta:.2f}  "
              f"left={left_idx.size}  right={right_idx.size}")
    if delta < acceptance_delta or left_idx.size < min_leaf or right_idx.size < min_leaf:
        if debug:
            reasons = []
            if delta < acceptance_delta: reasons.append(f"ΔBIC {delta:.2f} < {acceptance_delta:.2f}")
            if left_idx.size < min_leaf: reasons.append(f"left {left_idx.size} < {min_leaf}")
            if right_idx.size < min_leaf: reasons.append(f"right {right_idx.size} < {min_leaf}")
            print("[detect] reject best split: " + " | ".join(reasons))
        return None

    t_split = float(midpoint_time[k_star])
    return CriticalMoistureResult(
        t_split=t_split,
        Xc=float(Xc_star),
        left_indices=left_idx,
        right_indices=right_idx,
        a0=float(a0_star),
        b1=float(b1_star),
        b2=float(b2_star),
        bic_split=float(best_bic),
        bic_null=float(bic0),
        delta_bic=float(delta),
    )
