"""Model wrappers and training utilities for Phase 2 parameter regressors."""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional, Tuple
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge, Lasso, LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.compose import TransformedTargetRegressor
from sklearn.model_selection import cross_val_score

# CHANGE: Optional import for monotonic regressors
try:
    from sklearn.isotonic import IsotonicRegression
    HAVE_ISOTONIC = True
except ImportError:
    HAVE_ISOTONIC = False


def make_baseline_estimators() -> dict[str, Pipeline]:
    """Return dictionary of standard ML regressors with preprocessing."""
    base = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
    return {
        "Linear": Pipeline(base + [("model", LinearRegression())]),
        "Ridge": Pipeline(base + [("model", Ridge(alpha=1.0))]),
        "Lasso": Pipeline(base + [("model", Lasso(alpha=1e-3, max_iter=5000))]),
        "RF": Pipeline(base + [("model", RandomForestRegressor(n_estimators=300, random_state=42))]),
    }


def wrap_with_log_transform(
    pipeline: BaseEstimator,
    target_name: str,
    signed: bool = False,
) -> BaseEstimator:
    """Wrap estimator to apply log/signed-log transform to target."""
    def signed_log1p(x):
        return np.sign(x) * np.log1p(np.abs(x))

    def inverse_signed_log1p(x):
        return np.sign(x) * (np.expm1(np.abs(x)))

    if target_name == "b" or signed:
        return TransformedTargetRegressor(
            regressor=pipeline,
            func=signed_log1p,
            inverse_func=inverse_signed_log1p,
            check_inverse=False,
        )
    return pipeline


def train_and_evaluate(
    estimator: BaseEstimator,
    X: pd.DataFrame,
    y: np.ndarray,
    cv: int = 5,
    scoring: str = "neg_root_mean_squared_error",
) -> float:
    """Train estimator and return mean CV score."""
    scores = cross_val_score(estimator, X, y, cv=cv, scoring=scoring, n_jobs=-1)
    return float(-np.mean(scores))


def fit_monotonic_regressor_1d(X: np.ndarray, y: np.ndarray) -> Optional[IsotonicRegression]:
    """Fit 1D monotonic regressor if available (fallback for bivariate modeling)."""
    if not HAVE_ISOTONIC:
        return None
    if X.shape[1] != 1:
        return None
    return IsotonicRegression(out_of_bounds="clip").fit(X.ravel(), y)


def count_monotonic_violations(y_pred: np.ndarray) -> int:
    """Return number of upward violations (non-decreasing)."""
    return int(np.sum(np.diff(y_pred) > 0))


def soft_penalty_monotonic_loss(y_pred: np.ndarray, alpha: float = 1.0) -> float:
    """Add penalty proportional to number of increasing steps."""
    violations = np.diff(y_pred) > 0
    return alpha * float(np.sum(violations))


def add_violation_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    """Return violation and continuity diagnostics."""
    return {
        "monotonic_violations": count_monotonic_violations(y_pred),
        "max_up_jump": float(np.max(np.diff(y_pred)[np.diff(y_pred) > 0])) if np.any(np.diff(y_pred) > 0) else 0.0,
        "min_value": float(np.min(y_pred)),
    }
