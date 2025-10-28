"""Model fitting utilities for the phase-1 drying kinetics pipeline."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

__all__ = [
    "ModelSpec",
    "FitResult",
    "get_model_specs",
    "fit_all_models",
    "_select_best_result",
    "save_fit_artifacts",
]

@dataclass(frozen=True)
class ModelSpec:
    """Description of an empirical drying kinetics model."""

    name: str
    param_names: List[str]
    predict: Callable[[np.ndarray, Dict[str, float]], np.ndarray]
    initializer: Callable[[np.ndarray, np.ndarray], Dict[str, float]]
    bounds: Dict[str, Tuple[float, float]]

    def bounds_array(self) -> np.ndarray:
        """Return lower/upper bounds in parameter order for optimisation."""

        ordered = np.array([self.bounds[name] for name in self.param_names], dtype=float)
        return ordered


@dataclass
class FitResult:
    """Container describing the outcome of fitting a model to MR data."""

    model_name: str
    param_names: List[str]
    params: Dict[str, float]
    stderr: Optional[Dict[str, float]]
    ci95: Optional[Dict[str, Tuple[float, float]]]
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
        for name in self.param_names:
            value = self.params.get(name)
            row[name] = value
            if self.stderr and name in self.stderr:
                row[f"{name}_se"] = self.stderr[name]
            if self.ci95 and name in self.ci95:
                lo, hi = self.ci95[name]
                row[f"{name}_ci_lower"] = lo
                row[f"{name}_ci_upper"] = hi
        return row


if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from .preprocess_phase1 import PreprocessResult

from .models_phase1 import MODEL_SPECS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_model_specs() -> List[ModelSpec]:
    """Return the registered model specifications."""

    return list(MODEL_SPECS)


def fit_all_models(time: np.ndarray, mr_iso: np.ndarray) -> List[FitResult]:
    """Fit all phase-1 models to the supplied data."""

    results: List[FitResult] = []
    for spec in get_model_specs():
        result = _fit_single_model(spec, time, mr_iso)
        results.append(result)
    return results


def _select_best_result(results: Iterable[FitResult]) -> FitResult:
    """Choose the best-fit result using AICc primary, LOO-RMSE tie-breaker."""

    sorted_results = sorted(
        results,
        key=lambda r: (
            _finite_or_inf(r.metrics.get("aicc")),
            _finite_or_inf(r.metrics.get("loo_rmse")),
        ),
    )
    return sorted_results[0]


def _finite_or_inf(value: Optional[float]) -> float:
    if value is None or not math.isfinite(value):
        return float("inf")
    return float(value)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fit_single_model(spec: ModelSpec, time: np.ndarray, mr: np.ndarray) -> FitResult:
    bounds = spec.bounds_array()
    lower = bounds[:, 0]
    upper = bounds[:, 1]

    params0_dict = spec.initializer(time, mr)
    params0 = _param_dict_to_vector(params0_dict, spec.param_names)
    params0 = np.clip(params0, lower, upper)

    def residuals(vector: np.ndarray) -> np.ndarray:
        preds = spec.predict(time, _vector_to_param_dict(vector, spec.param_names))
        return preds - mr

    result = least_squares(
        residuals,
        params0,
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=0.1,
        max_nfev=5000,
    )

    params_vector = result.x
    success = bool(result.success)
    message = str(result.message)

    residual_vec = residuals(params_vector)
    sse = float(np.sum(residual_vec**2))
    n_obs = int(len(time))
    dof = max(n_obs - len(params_vector), 1)
    rmse = float(np.sqrt(sse / n_obs)) if n_obs else float("nan")
    aic, aicc, bic = _information_criteria(sse, n_obs, len(params_vector))

    stderr, ci95 = _parameter_uncertainty(result, sse, dof, spec)
    warnings = _collect_warnings(spec, params_vector, result)

    loo_rmse = _blocked_loo_rmse(spec, time, mr, params_vector, lower, upper)

    metrics = {
        "rmse": rmse,
        "sse": sse,
        "aic": aic,
        "aicc": aicc,
        "bic": bic,
        "loo_rmse": loo_rmse,
        "n_obs": n_obs,
    }

    params_dict = _vector_to_param_dict(params_vector, spec.param_names)

    return FitResult(
        model_name=spec.name,
        param_names=list(spec.param_names),
        params=params_dict,
        stderr=stderr,
        ci95=ci95,
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
) -> tuple[Optional[Dict[str, float]], Optional[Dict[str, Tuple[float, float]]]]:
    if result.jac is None or dof <= 0:
        return None, None

    stderr: Dict[str, float] = {}
    ci95: Dict[str, Tuple[float, float]] = {}

    try:
        jtj = result.jac.T.dot(result.jac)
        cov = np.linalg.inv(jtj) * (sse / dof)
    except np.linalg.LinAlgError:
        return None, None

    for idx, name in enumerate(spec.param_names):
        variance = float(cov[idx, idx]) if cov.size else float("nan")
        if variance < 0:
            variance = float("nan")
        se = float(np.sqrt(variance)) if math.isfinite(variance) else float("nan")
        if not math.isfinite(se):
            stderr[name] = float("nan")
            ci95[name] = (float("nan"), float("nan"))
            continue
        stderr[name] = se
        ci95[name] = (
            float(result.x[idx] - 1.96 * se),
            float(result.x[idx] + 1.96 * se),
        )

    return stderr, ci95


def _collect_warnings(
    spec: ModelSpec, params: np.ndarray, result: least_squares
) -> List[str]:
    warnings: List[str] = []
    if not result.success:
        warnings.append("optimizer_failed")

    tol = 1e-6
    for idx, name in enumerate(spec.param_names):
        lo, hi = spec.bounds[name]
        if abs(params[idx] - lo) <= tol:
            warnings.append(f"param_{name}_at_lower_bound")
        if abs(params[idx] - hi) <= tol:
            warnings.append(f"param_{name}_at_upper_bound")

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
            params0_dict = spec.initializer(time_train, mr_train)
            params0 = np.clip(
                _param_dict_to_vector(params0_dict, spec.param_names), lower, upper
            )
            result = least_squares(
                lambda p: spec.predict(
                    time_train, _vector_to_param_dict(p, spec.param_names)
                )
                - mr_train,
                params0,
                bounds=(lower, upper),
                loss="soft_l1",
                f_scale=0.1,
                max_nfev=3000,
            )
            preds = spec.predict(
                time[block],
                _vector_to_param_dict(result.x, spec.param_names),
            )
        except Exception:  # pragma: no cover - safeguard for numerical issues
            preds = spec.predict(
                time[block], _vector_to_param_dict(params, spec.param_names)
            )

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


def _param_dict_to_vector(params: Dict[str, float], param_names: Sequence[str]) -> np.ndarray:
    return np.array([float(params[name]) for name in param_names], dtype=float)


def _vector_to_param_dict(vector: np.ndarray, param_names: Sequence[str]) -> Dict[str, float]:
    return {name: float(vector[idx]) for idx, name in enumerate(param_names)}


def save_fit_artifacts(
    outdir: Path,
    preprocess: "PreprocessResult",
    results: List[FitResult],
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
        f"{name}={best_result.params.get(name, float('nan')):.4f}"
        for name in best_result.param_names
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
        "best_params": {name: best_result.params.get(name) for name in best_result.param_names},
        "warnings": best_result.warnings,
        "all_models": [r.to_row() for r in results],
        "preprocess": preprocess.to_jsonable(),
    }

    summary_path.write_text(json.dumps(summary, indent=2))
    pd.DataFrame([r.to_row() for r in results]).to_csv(params_path, index=False)
    joblib.dump({r.model_name: r for r in results}, joblib_path)
