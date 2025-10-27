"""Fitting helpers for Phase-1 drying kinetics models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from scipy.optimize import least_squares

from .models_phase1 import MODEL_FUNCS, MODEL_PARAM_NAMES, InitialGuess, make_initial_guess

# Physical parameter bounds
LOWER_BOUNDS = {
    "k": 1e-9,
    "n": 0.2,
    "b": -1e-3,
    "tau": 0.0,
}
UPPER_BOUNDS = {
    "k": 10.0,
    "n": 3.0,
    "b": 0.0,
    "tau": 30.0,
}


@dataclass
class FitResult:
    func_name: str
    params: np.ndarray
    param_names: List[str]
    success: bool
    message: str
    sse: float
    rmse: float
    aic: float
    aicc: float
    bic: float
    loo_rmse: float
    stderr: np.ndarray
    ci95: np.ndarray
    warnings: List[str]
    n_obs: int


def _build_bounds(param_names: List[str]) -> np.ndarray:
    lower = [LOWER_BOUNDS.get(name, -np.inf) for name in param_names]
    upper = [UPPER_BOUNDS.get(name, np.inf) for name in param_names]
    return np.array(lower, dtype=float), np.array(upper, dtype=float)


def _compute_statistics(residuals: np.ndarray, n_params: int) -> Dict[str, float]:
    n = residuals.size
    sse = float(np.sum(residuals ** 2))
    rmse = float(np.sqrt(sse / n)) if n > 0 else np.nan
    aic = np.nan
    bic = np.nan
    aicc = np.nan
    if n > 0 and sse > 0:
        # Akaike Information Criterion
        aic = n * np.log(sse / n) + 2 * n_params
        # Bayesian Information Criterion
        bic = n * np.log(sse / n) + n_params * np.log(n)
        # Small-sample corrected AIC (AICc)
        if n - n_params - 1 > 0:
            aicc = aic + (2 * n_params * (n_params + 1)) / (n - n_params - 1)
    return {"sse": sse, "rmse": rmse, "aic": aic, "aicc": aicc, "bic": bic}


def _parameter_uncertainty(jac: np.ndarray, residuals: np.ndarray, n_params: int) -> np.ndarray:
    n = residuals.size
    if jac is None or jac.size == 0 or n <= n_params:
        return np.full(n_params, np.nan)
    jt_j = jac.T @ jac
    try:
        cond = np.linalg.cond(jt_j)
        if not np.isfinite(cond) or cond > 1e12:
            raise np.linalg.LinAlgError("Ill-conditioned Jacobian")
        sigma2 = np.sum(residuals ** 2) / (n - n_params)
        cov = sigma2 * np.linalg.inv(jt_j)
        stderr = np.sqrt(np.diag(cov))
        return stderr
    except np.linalg.LinAlgError:
        return np.full(n_params, np.nan)


def _blocked_loo_rmse(
    func_name: str,
    param_names: List[str],
    t: np.ndarray,
    mr: np.ndarray,
    bounds,
    loss: str,
) -> float:
    n = t.size
    n_blocks = min(5, n)
    if n_blocks <= 1:
        return np.nan

    indices = np.array_split(np.arange(n), n_blocks)
    rmses = []
    for block in indices:
        if block.size == 0:
            continue
        mask = np.ones(n, dtype=bool)
        mask[block] = False
        if mask.sum() < len(param_names):
            continue
        t_train, mr_train = t[mask], mr[mask]
        t_val, mr_val = t[~mask], mr[~mask]
        try:
            init = make_initial_guess(func_name, t_train, mr_train)
            if bounds is not None:
                lower, upper = bounds
            else:
                lower, upper = _build_bounds(param_names)
            result = least_squares(
                lambda p: MODEL_FUNCS[func_name](p, t_train) - mr_train,
                init.params,
                bounds=(lower, upper),
                loss=loss,
                f_scale=0.1,
                max_nfev=2000,
            )
            pred = MODEL_FUNCS[func_name](result.x, t_val)
            residuals = pred - mr_val
            rmse = np.sqrt(np.mean(residuals ** 2))
            if np.isfinite(rmse):
                rmses.append(rmse)
        except Exception:
            continue
    if not rmses:
        return np.nan
    return float(np.mean(rmses))


def fit_variant(
    func_name: str,
    t: np.ndarray,
    mr_iso: np.ndarray,
    bounds: Optional[Dict[str, tuple]] = None,
    robust_loss: str = "soft_l1",
) -> FitResult:
    if func_name not in MODEL_FUNCS:
        raise KeyError(f"Unknown model variant: {func_name}")

    param_names = MODEL_PARAM_NAMES[func_name]
    init = make_initial_guess(func_name, t, mr_iso)

    lower, upper = _build_bounds(param_names)
    if bounds:
        custom_lower = list(lower)
        custom_upper = list(upper)
        for idx, name in enumerate(param_names):
            if name in bounds:
                lo, hi = bounds[name]
                if lo is not None:
                    custom_lower[idx] = max(custom_lower[idx], lo)
                if hi is not None:
                    custom_upper[idx] = min(custom_upper[idx], hi)
        lower = np.array(custom_lower, dtype=float)
        upper = np.array(custom_upper, dtype=float)

    residual_fun = lambda p: MODEL_FUNCS[func_name](p, t) - mr_iso

    res = least_squares(
        residual_fun,
        init.params,
        bounds=(lower, upper),
        loss=robust_loss,
        f_scale=0.1,
        max_nfev=5000,
    )

    residuals = residual_fun(res.x)
    stats = _compute_statistics(residuals, len(param_names))

    stderr = _parameter_uncertainty(res.jac, residuals, len(param_names))
    ci95 = np.column_stack(
        (
            res.x - 1.96 * stderr,
            res.x + 1.96 * stderr,
        )
    ) if np.all(np.isfinite(stderr)) else np.full((len(param_names), 2), np.nan)

    warnings: List[str] = []
    if not res.success:
        warnings.append(res.message)
    if not np.all(np.isfinite(stderr)):
        warnings.append("Jacobian ill-conditioned; parameter SE unavailable")

    loo_rmse = _blocked_loo_rmse(
        func_name,
        param_names,
        res.x,
        t,
        mr_iso,
        (lower, upper),
        robust_loss,
    )

    return FitResult(
        func_name=func_name,
        params=res.x,
        param_names=param_names,
        success=res.success,
        message=res.message,
        sse=stats["sse"],
        rmse=stats["rmse"],
        aic=stats["aic"],
        aicc=stats["aicc"],
        bic=stats["bic"],
        loo_rmse=loo_rmse,
        stderr=stderr,
        ci95=ci95,
        warnings=warnings,
        n_obs=t.size,
    )


__all__ = ["fit_variant", "FitResult"]
