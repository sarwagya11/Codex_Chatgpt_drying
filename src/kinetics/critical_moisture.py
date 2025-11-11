"""Detection of the critical moisture content from drying experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

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
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError("Inputs must be one-dimensional sequences of floats.")
    return array


def _enforce_strictly_increasing(time: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if time.size <= 1:
        return time, values

    order = np.argsort(time, kind="mergesort")
    time_sorted = time[order]
    values_sorted = values[order]

    dt = np.diff(time_sorted)
    if np.all(dt > 0):
        return time_sorted, values_sorted

    keep = np.ones(time_sorted.size, dtype=bool)
    keep[1:] = dt > 0
    time_filtered = time_sorted[keep]
    values_filtered = values_sorted[keep]
    return time_filtered, values_filtered


def detect_critical_moisture(
    time_min: Sequence[float] | np.ndarray,
    x_db: Sequence[float] | np.ndarray,
    *,
    lowess_frac: float = 0.15,
    lambda_const: float = 5.0,
    acceptance_delta: float = 6.0,
) -> Optional[CriticalMoistureResult]:
    """Detect the critical moisture point using a constrained bilinear fit."""
    lowess_frac = float(np.clip(lowess_frac, 0.05, 0.60))
    lambda_const = float(max(lambda_const, 0.0))
    acceptance_delta = float(max(acceptance_delta, 0.0))
    
    time = _as_float_array(time_min)
    values = _as_float_array(x_db)

    if time.size != values.size:
        raise ValueError("time and x_db must have the same length")

    finite_mask = np.isfinite(time) & np.isfinite(values)
    time = time[finite_mask]
    values = values[finite_mask]

    if time.size < 2:
        return None

    time, values = _enforce_strictly_increasing(time, values)
    if time.size < 2:
        return None

    if time.size >= 3 and lowess_frac > 0:
        smoothed = lowess(values, time, frac=lowess_frac, return_sorted=False)
    else:
        smoothed = values.copy()

    dt = np.diff(time)
    if not np.all(dt > 0):
        positive = dt > 0
        keep = np.ones(time.size, dtype=bool)
        keep[1:] = positive
        time = time[keep]
        values = values[keep]
        smoothed = smoothed[keep]
        dt = np.diff(time)

    if time.size < 2:
        return None

    rate = -(smoothed[1:] - smoothed[:-1]) / dt
    midpoint_time = 0.5 * (time[1:] + time[:-1])
    midpoint_x = 0.5 * (values[1:] + values[:-1])

    positive_mask = rate > 0
    rate = rate[positive_mask]
    midpoint_time = midpoint_time[positive_mask]
    midpoint_x = midpoint_x[positive_mask]

    m = rate.size
    if m == 0:
        return None

    min_leaf = max(8, int(np.ceil(0.08 * m)))
    if m < 2 * min_leaf:
        return None

    candidate_start = min_leaf - 1
    candidate_stop = m - min_leaf
    if candidate_start >= candidate_stop:
        return None

    best_bic = np.inf
    best_params: Optional[tuple[int, float, float, float, float]] = None

    eps = 1e-12

    for k in range(candidate_start, candidate_stop):
        Xc = midpoint_x[k]
        u = midpoint_x - Xc

        left_mask = np.arange(m) <= k
        right_mask = ~left_mask

        r_left = rate[left_mask]
        u_left = u[left_mask]
        r_right = rate[right_mask]
        u_right = u[right_mask]

        if r_left.size == 0 or r_right.size == 0:
            continue

        A = np.zeros((m, 3), dtype=float)
        b = np.concatenate([r_right, r_left])

        n_right = r_right.size
        A[:n_right, 0] = 1.0
        A[:n_right, 1] = u_right
        A[n_right:, 0] = 1.0
        A[n_right:, 2] = u_left

        AtA = A.T @ A
        Atb = A.T @ b
        AtA[1, 1] += lambda_const
        AtA[2, 2] += lambda_const

        try:
            a0, b1, b2 = np.linalg.solve(AtA, Atb)
        except np.linalg.LinAlgError:
            a0, b1, b2 = tuple(np.linalg.pinv(AtA) @ Atb)

            active = [True, True]
        if b1 < 0:
            b1 = 0.0
            active[0] = False
        if b2 < 0:
            b2 = 0.0
            active[1] = False

        if not active[0] and not active[1]:
            # both slopes knocked out → constant rate
            a0 = float(np.mean(b))
            b1 = 0.0
            b2 = 0.0
            p = 1  # intercept only
        elif not all(active):
            cols = [0]
            if active[0]:
                cols.append(1)
            if active[1]:
                cols.append(2)
            A_act = A[:, cols]
            AtA = A_act.T @ A_act
            # ridge only on active slope columns
            if active[0] and active[1]:
                AtA[1, 1] += lambda_const
                AtA[2, 2] += lambda_const
            elif active[0] and not active[1]:
                AtA[1, 1] += lambda_const
            elif active[1] and not active[0]:
                AtA[1, 1] += lambda_const
            Atb = A_act.T @ b
            try:
                theta = np.linalg.solve(AtA, Atb)
            except np.linalg.LinAlgError:
                theta = np.linalg.pinv(AtA) @ Atb
            a0 = float(theta[0])
            if active[0] and active[1]:
                b1, b2 = float(theta[1]), float(theta[2])
                p = 3
            elif active[0] and not active[1]:
                b1, b2 = float(theta[1]), 0.0
                p = 2
            else:
                b1, b2 = 0.0, float(theta[1])
                p = 2
        else:
            p = 3  # intercept + two slopes active


        pred_right = a0 + b1 * u_right
        pred_left = a0 + b2 * u_left
        resid = np.concatenate([r_right - pred_right, r_left - pred_left])
        rss = float(
            np.sum(resid ** 2)
            + lambda_const * ((b1 if active[0] else 0.0) ** 2 + (b2 if active[1] else 0.0) ** 2)
        )
        rss = max(rss, eps)

        p = 1 + int(active[0]) + int(active[1])
        bic = m * np.log(rss / m) + p * np.log(m)

        if bic < best_bic:
            best_bic = bic
            best_params = (k, a0, b1, b2, Xc)

    if best_params is None:
        return None

    k_star, a0_star, b1_star, b2_star, Xc_star = best_params

    A_null = np.column_stack([np.ones(m), midpoint_x])
    AtA_null = A_null.T @ A_null
    Atb_null = A_null.T @ rate
    AtA_null[1, 1] += lambda_const

    try:
        alpha, beta = np.linalg.solve(AtA_null, Atb_null)
    except np.linalg.LinAlgError:
        alpha, beta = tuple(np.linalg.pinv(AtA_null) @ Atb_null)

    resid_null = rate - (alpha + beta * midpoint_x)
    rss0 = float(np.sum(resid_null ** 2) + lambda_const * (beta**2))
    rss0 = max(rss0, eps)
    bic0 = m * np.log(rss0 / m) + 2 * np.log(m)

    delta = bic0 - best_bic

    left_indices = np.arange(0, k_star + 1, dtype=int)
    right_indices = np.arange(k_star + 1, m, dtype=int)

    if delta < acceptance_delta or left_indices.size < min_leaf or right_indices.size < min_leaf:
        return None

    t_split = midpoint_time[k_star]
    result = CriticalMoistureResult(
        t_split=float(t_split),
        Xc=float(Xc_star),
        left_indices=left_indices,
        right_indices=right_indices,
        a0=float(a0_star),
        b1=float(b1_star),
        b2=float(b2_star),
        bic_split=float(best_bic),
        bic_null=float(bic0),
        delta_bic=float(delta),
    )
    return result

