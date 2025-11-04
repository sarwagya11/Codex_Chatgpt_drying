"""Train regressors for Midilli parameters using engineered features."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.model_selection import KFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Ensure project modules are importable when running as a script -----------------
import sys
import importlib.util

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics.phase2_utils import (  # noqa: E402
    ALL_FEATURE_COLUMNS,
    RAW_FEATURE_COLUMNS,
    inverse_signed_log1p,
    prepare_feature_frame,
    signed_log1p,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit regression models for Midilli parameters.",
    )
    parser.add_argument(
        "--segments-csv",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv",
        help="Segment-level dataset produced by phase2A.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2",
        help="Base directory for saved models and metrics.",
    )
    parser.add_argument(
        "--min-folds",
        type=int,
        default=3,
        help="Minimum number of cross-validation folds when possible.",
    )
    return parser.parse_args()


def make_estimators() -> Dict[str, Pipeline]:
    base_steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
    estimators: Dict[str, Pipeline] = {
        "LinearRegression": Pipeline(base_steps + [("model", LinearRegression())]),
        "Ridge": Pipeline(base_steps + [("model", Ridge(alpha=1.0))]),
        "Lasso": Pipeline(
            base_steps + [("model", Lasso(alpha=1e-3, max_iter=5000, random_state=42))]
        ),
        "RandomForest": Pipeline(
            base_steps
            + [
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=300,
                        random_state=42,
                        n_jobs=-1,
                        min_samples_leaf=2,
                    ),
                )
            ]
        ),
    }

    if importlib.util.find_spec("xgboost") is not None:  # Optional dependency
        from xgboost import XGBRegressor  # type: ignore

        estimators["XGBoost"] = Pipeline(
            base_steps
            + [
                (
                    "model",
                    XGBRegressor(
                        n_estimators=500,
                        learning_rate=0.05,
                        max_depth=4,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        objective="reg:squarederror",
                        random_state=42,
                    ),
                )
            ]
        )

    return estimators


def evaluate_models(
    X: pd.DataFrame,
    y: np.ndarray,
    estimators: Dict[str, Pipeline],
    *,
    min_folds: int,
    target: str,
    use_transform: bool,
) -> Tuple[str, Dict[str, dict]]:
    n_samples = len(X)
    cv_folds = min(max(min_folds, 2), n_samples) if n_samples >= 2 else 0

    results: Dict[str, dict] = {}
    best_model_name = None
    best_score = np.inf

    for name, pipeline in estimators.items():
        if use_transform:
            regressor = TransformedTargetRegressor(
                regressor=pipeline,
                func=signed_log1p,
                inverse_func=inverse_signed_log1p,
                check_inverse=False,
            )
        else:
            regressor = pipeline

        metrics = {
            "parameter": target,
            "model": name,
            "n_samples": n_samples,
            "cv_folds": cv_folds,
            "mean_rmse": np.nan,
            "std_rmse": np.nan,
            "mean_r2": np.nan,
            "std_r2": np.nan,
        }

        if cv_folds >= 2:
            cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
            scores = cross_validate(
                regressor,
                X,
                y,
                scoring={
                    "neg_root_mean_squared_error": "neg_root_mean_squared_error",
                    "r2": "r2",
                },
                cv=cv,
                n_jobs=-1,
                error_score="raise",
            )
            rmse = -scores["test_neg_root_mean_squared_error"]
            r2 = scores["test_r2"]
            metrics.update(
                {
                    "mean_rmse": float(rmse.mean()),
                    "std_rmse": float(rmse.std(ddof=0)),
                    "mean_r2": float(r2.mean()),
                    "std_r2": float(r2.std(ddof=0)),
                }
            )
            score = metrics["mean_rmse"]
        else:
            score = np.nan

        results[name] = {
            "metrics": metrics,
            "estimator": regressor,
        }

        if np.isnan(score):
            if best_model_name is None:
                best_model_name = name
        elif score < best_score:
            best_score = score
            best_model_name = name

    assert best_model_name is not None
    return best_model_name, results


def main() -> None:
    args = parse_args()
    segments_path: Path = args.segments_csv
    if not segments_path.exists():
        raise FileNotFoundError(f"Segments CSV not found: {segments_path}")

    df = pd.read_csv(segments_path)
    feature_frame = prepare_feature_frame(df)

    models_dir = args.output_dir / "models"
    metrics_dir = args.output_dir / "metrics"
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    estimators = make_estimators()
    metrics_records: list[dict] = []

    for target in ("k", "n", "b"):
        if target not in df.columns:
            raise KeyError(f"Target column '{target}' missing from segments dataset")

        y = pd.to_numeric(df[target], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(y)
        X = feature_frame.loc[mask, ALL_FEATURE_COLUMNS]
        y_valid = y[mask]

        use_transform = target == "b"

        print(f"\n[Phase2B] Training regressors for {target.upper()}...")

        best_name, results = evaluate_models(
            X,
            y_valid,
            estimators,
            min_folds=args.min_folds,
            target=target,
            use_transform=use_transform,
        )

        for name, payload in results.items():
            metrics = payload["metrics"]
            metrics["is_best"] = name == best_name
            metrics_records.append(metrics)

        final_model = results[best_name]["estimator"]
        final_model.fit(X, y_valid)

        artifact = {
            "model": final_model,
            "raw_feature_columns": RAW_FEATURE_COLUMNS,
            "all_feature_columns": ALL_FEATURE_COLUMNS,
            "target": target,
            "target_transform": "signed_log1p" if use_transform else "identity",
        }

        model_path = models_dir / f"{target}_model.pkl"
        dump(artifact, model_path)
        print(f"[Phase2B] Saved best model for {target.upper()} to {model_path}")

    metrics_df = pd.DataFrame(metrics_records)
    metrics_path = metrics_dir / "model_performance.csv"
    metrics_df.sort_values(["parameter", "mean_rmse"], inplace=True)
    metrics_df.to_csv(metrics_path, index=False)
    print(f"[Phase2B] Wrote CV metrics to {metrics_path}")


if __name__ == "__main__":
    main()
