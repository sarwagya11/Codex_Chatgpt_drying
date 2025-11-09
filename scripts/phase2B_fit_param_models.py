"""Train regression models for Midilli parameters from segment features."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold

import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics.phase2_utils import (  # noqa: E402
    ALL_FEATURE_COLUMNS,
    configure_logging,
    ensure_directory,
    extract_config_section,
    load_config,
    prepare_feature_frame,
    softplus,
    inverse_softplus,
)

DEFAULT_SEGMENTS_CSV = _PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv"
DEFAULT_MODELS_DIR = _PROJECT_ROOT / "outputs" / "phase2" / "models"
DEFAULT_METRICS_PATH = _PROJECT_ROOT / "outputs" / "phase2" / "model_performance.csv"
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"
DEFAULT_LOGGER_NAME = "phase2.phase2B"

REQUIRED_TARGET_COLUMNS = {"k", "n", "b"}


@dataclass
class TargetSpec:
    name: str
    column: str
    transform: str
    pred_column: str
    extra_outputs: Tuple[str, ...] = ()

    def forward(self, values: np.ndarray) -> np.ndarray:
        if self.transform == "log":
            clipped = np.clip(values, 1e-12, None)
            return np.log(clipped)
        if self.transform == "softplus":
            return softplus(values)
        return values

    def inverse(self, values: np.ndarray) -> np.ndarray:
        if self.transform == "log":
            return np.exp(values)
        if self.transform == "softplus":
            return inverse_softplus(values)
        return values


TARGET_SPECS: Dict[str, TargetSpec] = {
    "k": TargetSpec(name="k", column="k", transform="log", pred_column="pred_k"),
    "n": TargetSpec(name="n", column="n", transform="identity", pred_column="pred_n"),
    "b": TargetSpec(
        name="b",
        column="b",
        transform="softplus",
        pred_column="pred_b",
        extra_outputs=("pred_b_pos",),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit regression models to Midilli parameters.",
    )
    parser.add_argument(
        "--segments-csv",
        type=Path,
        default=DEFAULT_SEGMENTS_CSV,
        help="Segment-level dataset produced by phase2A.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help="Directory to store trained models.",
    )
    parser.add_argument(
        "--metrics-path",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="Path to write aggregate model metrics.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for diagnostics CSV outputs.",
    )
    parser.add_argument(
        "--min-folds",
        type=int,
        default=3,
        help="Minimum number of group-aware folds for cross-validation.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for log files.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (e.g., INFO, DEBUG).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON/YAML config file providing overrides.",
    )
    return parser.parse_args()


def make_estimator() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_depth=3,
        learning_rate=0.05,
        max_iter=400,
        l2_regularization=0.0,
        random_state=42,
    )


def evaluate_cv(
    estimator: HistGradientBoostingRegressor,
    X: pd.DataFrame,
    y_transformed: np.ndarray,
    spec: TargetSpec,
    groups: np.ndarray,
    min_folds: int,
) -> Tuple[List[Dict[str, float]], int]:
    unique_groups = np.unique(groups)
    n_groups = unique_groups.size
    n_splits = min(n_groups, max(min_folds, 2)) if n_groups >= 2 else 0
    if n_splits < 2:
        return [], 0

    gkf = GroupKFold(n_splits=n_splits)
    fold_metrics: List[Dict[str, float]] = []
    for fold_index, (train_idx, test_idx) in enumerate(gkf.split(X, y_transformed, groups)):
        model = make_estimator()
        model.fit(X.iloc[train_idx], y_transformed[train_idx])
        preds_transformed = model.predict(X.iloc[test_idx])
        preds = spec.inverse(np.asarray(preds_transformed, dtype=float))
        truth = spec.inverse(y_transformed[test_idx])
        rmse = mean_squared_error(truth, preds, squared=False)
        mae = mean_absolute_error(truth, preds)
        fold_metrics.append({
            "fold": fold_index,
            "rmse": float(rmse),
            "mae": float(mae),
        })
    return fold_metrics, n_splits


def fit_and_record(
    df: pd.DataFrame,
    features: pd.DataFrame,
    spec: TargetSpec,
    models_dir: Path,
    min_folds: int,
    groups: np.ndarray,
    logger,
) -> Tuple[Dict[str, Any], pd.Series, Dict[str, Any], pd.DataFrame]:
    y_raw = df[spec.column].to_numpy(dtype=float)
    y_transformed = spec.forward(y_raw)

    estimator = make_estimator()
    estimator.fit(features, y_transformed)
    preds_transformed = estimator.predict(features)
    preds_main = spec.inverse(np.asarray(preds_transformed, dtype=float))

    extra_outputs: Dict[str, np.ndarray] = {}
    if "pred_b_pos" in spec.extra_outputs:
        extra_outputs["pred_b_pos"] = np.asarray(preds_transformed, dtype=float)

    train_rmse = float(mean_squared_error(spec.inverse(y_transformed), preds_main, squared=False))
    train_mae = float(mean_absolute_error(spec.inverse(y_transformed), preds_main))

    fold_metrics, n_splits = evaluate_cv(estimator, features, y_transformed, spec, groups, min_folds)
    if fold_metrics:
        cv_rmse = [fold["rmse"] for fold in fold_metrics]
        cv_mae = [fold["mae"] for fold in fold_metrics]
        cv_summary = {
            "mean_rmse": float(np.mean(cv_rmse)),
            "std_rmse": float(np.std(cv_rmse, ddof=0)),
            "mean_mae": float(np.mean(cv_mae)),
            "std_mae": float(np.std(cv_mae, ddof=0)),
        }
    else:
        cv_summary = {
            "mean_rmse": float("nan"),
            "std_rmse": float("nan"),
            "mean_mae": float("nan"),
            "std_mae": float("nan"),
        }

    artifact = {
        "model": estimator,
        "all_feature_columns": list(features.columns),
        "target": spec.name,
        "target_transform": spec.transform,
        "prediction_column": spec.pred_column,
        "extra_prediction_columns": spec.extra_outputs,
    }

    artifact_path = ensure_directory(models_dir) / f"{spec.name}_model.pkl"
    dump(artifact, artifact_path)
    logger.info("Saved %s model to %s", spec.name, artifact_path)

    metrics_record = {
        "parameter": spec.name,
        "n_segments": int(len(df)),
        "train_rmse": train_rmse,
        "train_mae": train_mae,
        "cv_folds": n_splits,
        **cv_summary,
    }

    predictions = pd.Series(preds_main, index=df.index, name=spec.pred_column)
    feature_importances = getattr(estimator, "feature_importances_", None)
    importance_df = pd.DataFrame()
    if feature_importances is not None:
        importance_df = pd.DataFrame(
            {
                "parameter": spec.name,
                "feature": features.columns,
                "importance": feature_importances,
            }
        )

    return metrics_record, predictions, extra_outputs, importance_df


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    section = extract_config_section(config, "phase2B")

    segments_path = Path(section.get("segments_csv", args.segments_csv))
    models_dir = Path(section.get("models_dir", args.models_dir))
    metrics_path = Path(section.get("metrics_path", args.metrics_path))
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))
    min_folds = int(section.get("min_folds", args.min_folds))
    log_dir = Path(section.get("log_dir", args.log_dir))
    log_level = section.get("log_level", args.log_level)

    ensure_directory(models_dir)
    ensure_directory(metrics_path.parent)
    ensure_directory(diagnostics_dir)
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)

    df = pd.read_csv(segments_path)
    missing_targets = REQUIRED_TARGET_COLUMNS - set(df.columns)
    if missing_targets:
        raise KeyError(f"Missing target columns in segments dataset: {sorted(missing_targets)}")

    features = prepare_feature_frame(df)
    feature_columns = [col for col in ALL_FEATURE_COLUMNS if col in features.columns]
    features = features[feature_columns]
    groups = df["dataset_name"].astype(str).to_numpy()

    metrics: List[Dict[str, Any]] = []
    predictions_frame = df[["dataset_name", "segment_index"]].copy()
    feature_importances_list: List[pd.DataFrame] = []
    residual_records: List[Dict[str, Any]] = []

    for spec in TARGET_SPECS.values():
        metrics_record, predictions, extra_outputs, importance_df = fit_and_record(
            df,
            features,
            spec,
            models_dir,
            min_folds,
            groups,
            logger,
        )
        metrics.append(metrics_record)
        predictions_frame[spec.pred_column] = predictions
        if "pred_b_pos" in extra_outputs:
            predictions_frame["pred_b_pos"] = extra_outputs["pred_b_pos"]
        if not importance_df.empty:
            feature_importances_list.append(importance_df)

        preds = predictions.to_numpy(dtype=float)
        if spec.name == "b" and "pred_b_pos" in predictions_frame.columns:
            preds = spec.inverse(predictions_frame["pred_b_pos"].to_numpy(dtype=float))
        truth = df[spec.column].to_numpy(dtype=float)
        residuals = preds - truth
        residuals_df = pd.DataFrame(
            {
                "dataset_name": df["dataset_name"],
                "residual": residuals,
            }
        )
        grouped = residuals_df.groupby("dataset_name")
        for dataset_name, group in grouped:
            residual_records.append(
                {
                    "dataset_name": dataset_name,
                    "parameter": spec.name,
                    "rmse": float(np.sqrt(np.mean(group["residual"] ** 2))),
                    "mae": float(np.mean(np.abs(group["residual"]))),
                    "n_segments": int(group.shape[0]),
                }
            )

    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(metrics_path, index=False, float_format="%.9g")

    predictions_path = diagnostics_dir / "phase2B_training_predictions.csv"
    predictions_frame.to_csv(predictions_path, index=False, float_format="%.9g")

    residuals_df = pd.DataFrame(residual_records)
    residuals_path = diagnostics_dir / "phase2B_residuals_by_dataset.csv"
    residuals_df.to_csv(residuals_path, index=False, float_format="%.9g")

    if feature_importances_list:
        feature_importances_df = pd.concat(feature_importances_list, ignore_index=True)
        importances_path = diagnostics_dir / "phase2B_feature_importances.csv"
        feature_importances_df.to_csv(importances_path, index=False, float_format="%.9g")

    logger.info("Metrics written to %s", metrics_path)
    logger.info("Predictions written to %s", predictions_path)
    logger.info("Residual diagnostics written to %s", residuals_path)


if __name__ == "__main__":
    main()
