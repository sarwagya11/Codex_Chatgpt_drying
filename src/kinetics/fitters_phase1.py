"""Model fitting utilities for the phase-1 drying kinetics pipeline."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .models_phase1 import MODEL_SPECS, ModelSpec


@dataclass
class FitResult:
    """Container describing the outcome of fitting a model to MR data."""

    model_name: str
    params: Dict[str, float]
    param_stderr: Dict[str, float]
    param_ci_lower: Dict[str, float]
    param_ci_upper: Dict[str, float]
    metrics: Dict[str, float]
    success: bool
    message: str
    warnings: List[str] = field(default_factory=list)

    def to_row(self) -> Dict[str, object]:
        row = {
            "model": self.model_name,
            "rmse": self.metrics.get("rmse"),
            "sse": self.metrics.get("sse"),
            "aic": self.metrics.get("aic"),
            "aicc": self.metrics.get("aicc"),
            "bic": self.metrics.get("bic"),
            "loo_rmse": self.metrics.get("loo_rmse"),
            "success": self.success,
            "message": self.message,
            "n_obs": self.metrics.get("n_obs"),
            "warnings": " | ".join(self.warnings) if self.warnings else "",
        }
        for name, value in self.params.items():
            row[name] = value
            row[f"{name}_se"] = self.param_stderr.get(name)
            row[f"{name}_ci_lower"] = self.param_ci_lower.get(name)
            row[f"{name}_ci_upper"] = self.param_ci_upper.get(name)
        return row


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fit_all_models(time: np.ndarray, mr_iso: np.ndarray) -> List[FitResult]:
    """Fit all phase-1 models to the supplied data."""

    results: List[FitResult] = []
    for spec in MODEL_SPECS:
        result = _fit_single_model(spec, time, mr_iso)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fit_single_model(spec: ModelSpec, time: np.ndarray, mr: np.ndarray) -> FitResult:
    bounds = np.array(spec.bounds, dtype=float)
    lower = bounds[:, 0]
    upper = bounds[:, 1]

    x0 = spec.initializer(time, mr)
    x0 = np.clip(x0, lower, upper)

    def residuals(params: np.ndarray) -> np.ndarray:
        preds = spec.predict(time, params)
        return preds - mr

    result = least_squares(
        residuals,
        x0,
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=0.1,
        max_nfev=5000,
    )

    params = result.x
    success = bool(result.success)
    message = str(result.message)

    residual_vec = residuals(params)
    sse = float(np.sum(residual_vec**2))
    n_obs = int(len(time))
    dof = max(n_obs - len(params), 1)
    rmse = float(np.sqrt(sse / n_obs)) if n_obs else float("nan")
    aic, aicc, bic = _information_criteria(sse, n_obs, len(params))

    stderr, ci_lower, ci_upper = _parameter_uncertainty(result, sse, dof, spec)
    warnings = _collect_warnings(spec, params, result)

    loo_rmse = _blocked_loo_rmse(spec, time, mr, params, lower, upper)

    metrics = {
        "rmse": rmse,
        "sse": sse,
        "aic": aic,
        "aicc": aicc,
        "bic": bic,
        "loo_rmse": loo_rmse,
        "n_obs": n_obs,
    }

    return FitResult(
        model_name=spec.name,
        params={name: float(value) for name, value in zip(spec.param_names, params)},
        param_stderr=stderr,
        param_ci_lower=ci_lower,
        param_ci_upper=ci_upper,
        metrics=metrics,
        success=success,
        message=message,
        warnings=warnings,
    )


def _information_criteria(sse: float, n_obs: int, n_params: int) -> tuple[float, float, float]:
    if n_obs == 0:
        return float("nan"), float("nan"), float("nan")
    mse = sse / max(n_obs, 1)
    mse = max(mse, 1e-12)
    aic = n_obs * math.log(mse) + 2 * n_params
    if n_obs - n_params - 1 <= 0:
        aicc = float("inf")
    else:
        aicc = aic + (2 * n_params * (n_params + 1)) / (n_obs - n_params - 1)
    bic = n_obs * math.log(mse) + math.log(n_obs) * n_params
    return float(aic), float(aicc), float(bic)


def _parameter_uncertainty(
    result: least_squares,
    sse: float,
    dof: int,
    spec: ModelSpec,
) -> tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    stderr: Dict[str, float] = {}
    ci_lower: Dict[str, float] = {}
    ci_upper: Dict[str, float] = {}

    if result.jac is None or dof <= 0:
        for name in spec.param_names:
            stderr[name] = float("nan")
            ci_lower[name] = float("nan")
            ci_upper[name] = float("nan")
        return stderr, ci_lower, ci_upper

    try:
        jtj = result.jac.T.dot(result.jac)
        cov = np.linalg.inv(jtj) * (sse / dof)
        for idx, name in enumerate(spec.param_names):
            variance = float(cov[idx, idx]) if cov.size else float("nan")
            if variance < 0:
                variance = float("nan")
            se = float(np.sqrt(variance)) if math.isfinite(variance) else float("nan")
            stderr[name] = se
            if math.isfinite(se):
                ci_lower[name] = float(result.x[idx] - 1.96 * se)
                ci_upper[name] = float(result.x[idx] + 1.96 * se)
            else:
                ci_lower[name] = float("nan")
                ci_upper[name] = float("nan")
    except np.linalg.LinAlgError:
        for name in spec.param_names:
            stderr[name] = float("nan")
            ci_lower[name] = float("nan")
            ci_upper[name] = float("nan")

    return stderr, ci_lower, ci_upper


def _collect_warnings(
    spec: ModelSpec, params: np.ndarray, result: least_squares
) -> List[str]:
    warnings: List[str] = []
    if not result.success:
        warnings.append("optimizer_failed")

    tol = 1e-6
    for idx, (lo, hi) in enumerate(spec.bounds):
        if abs(params[idx] - lo) <= tol:
            warnings.append(f"param_{spec.param_names[idx]}_at_lower_bound")
        if abs(params[idx] - hi) <= tol:
            warnings.append(f"param_{spec.param_names[idx]}_at_upper_bound")

    return warnings


def _blocked_loo_rmse(
    spec: ModelSpec,
    time: np.ndarray,
    mr: np.ndarray,
    params: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    n_obs = len(time)
    if n_obs <= len(params) + 2:
        return float("nan")

    indices = _make_blocks(n_obs)
    errors: List[float] = []
    for block in indices:
        mask = np.ones(n_obs, dtype=bool)
        mask[block] = False
        if mask.sum() <= len(params):
            continue
        time_train = time[mask]
        mr_train = mr[mask]

        try:
            params0 = np.clip(spec.initializer(time_train, mr_train), lower, upper)
            result = least_squares(
                lambda p: spec.predict(time_train, p) - mr_train,
                params0,
                bounds=(lower, upper),
                loss="soft_l1",
                f_scale=0.1,
                max_nfev=3000,
            )
            preds = spec.predict(time[block], result.x)
        except Exception:  # pragma: no cover - safeguard for numerical issues
            preds = spec.predict(time[block], params)

        block_errors = mr[block] - preds
        errors.extend(block_errors.tolist())

    if not errors:
        return float("nan")
    return float(np.sqrt(np.mean(np.square(errors))))


def _make_blocks(n_obs: int) -> List[np.ndarray]:
    num_blocks = int(np.clip(n_obs // 8, 3, 10))
    if num_blocks <= 0:
        num_blocks = 3
    indices = np.array_split(np.arange(n_obs), num_blocks)
    return [idx for idx in indices if idx.size > 0]


def save_fit_artifacts(
    outdir: Path,
    preprocess: "PreprocessResult",
    results: Sequence[FitResult],
    best_result: FitResult,
    best_predictions: np.ndarray,
    best_residuals: np.ndarray,
) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    from matplotlib import pyplot as plt
    from scipy import stats

    plots_dir = outdir / "plots"
    plots_dir.mkdir(exist_ok=True)

    # 02_fit_best.png
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(preprocess.time_min, preprocess.mr_iso, "o", label="MR iso", alpha=0.7)
    ax.plot(
        preprocess.time_min,
        best_predictions,
        "-",
        label=f"Best fit: {best_result.model_name}",
        linewidth=2,
    )
    param_text = ", ".join(
        f"{name}={best_result.params.get(name, float('nan')):.4f}" for name in best_result.params
    )
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Moisture ratio")
    ax.set_title(f"Best-fit overlay ({param_text})")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "02_fit_best.png", dpi=200)
    plt.close(fig)

    # 03_residuals_best.png
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(0.0, color="black", linewidth=1, linestyle="--")
    ax.plot(
        preprocess.time_min,
        best_residuals,
        "o",
        label="Residuals",
    )
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Residual (pred - MR)")
    ax.set_title("Residuals vs time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plots_dir / "03_residuals_best.png", dpi=200)
    plt.close(fig)

    # 04_qq_best.png
    fig, ax = plt.subplots(figsize=(5, 5))
    stats.probplot(best_residuals, dist="norm", plot=ax)
    ax.set_title("Residual QQ plot")
    fig.tight_layout()
    fig.savefig(plots_dir / "04_qq_best.png", dpi=200)
    plt.close(fig)

    # summary.json and params.csv
    summary_path = outdir / "summary.json"
    params_path = outdir / "params.csv"
    joblib_path = outdir / "fit_results.joblib"

    summary = {
        "best_model": best_result.model_name,
        "best_metrics": {
            k: v
            for k, v in best_result.metrics.items()
            if k in {"rmse", "sse", "aic", "aicc", "bic", "loo_rmse", "n_obs"}
        },
        "best_params": best_result.params,
        "warnings": best_result.warnings,
        "all_models": [r.to_row() for r in results],
        "preprocess": preprocess.to_jsonable(),
    }

    summary_path.write_text(json.dumps(summary, indent=2))
    pd.DataFrame([r.to_row() for r in results]).to_csv(params_path, index=False)
    joblib.dump({r.model_name: r for r in results}, joblib_path)
