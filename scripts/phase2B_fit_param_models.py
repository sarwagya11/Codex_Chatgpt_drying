"""Train regressors for Midilli parameters using engineered features."""  # CHANGE: Updated script header

from __future__ import annotations  # CHANGE: Future annotations retained

import argparse  # CHANGE: CLI parsing import
from pathlib import Path  # CHANGE: Path handling
from typing import Dict  # CHANGE: Typing helper

import numpy as np  # CHANGE: Numerical operations
import pandas as pd  # CHANGE: DataFrame handling
from joblib import dump  # CHANGE: Model persistence
from sklearn.base import clone  # CHANGE: Estimator cloning
from sklearn.model_selection import KFold, cross_validate  # CHANGE: CV utilities
from sklearn.compose import TransformedTargetRegressor  # CHANGE: Target transform

import sys  # CHANGE: Ensure project importability

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # CHANGE: Project root
_SRC_ROOT = _PROJECT_ROOT / "src"  # CHANGE: Source directory
for candidate in (_PROJECT_ROOT, _SRC_ROOT):  # CHANGE: Extend sys.path loop
    candidate_str = str(candidate)  # CHANGE: Convert to string
    if candidate_str not in sys.path:  # CHANGE: Avoid duplicates
        sys.path.insert(0, candidate_str)  # CHANGE: Insert path

from kinetics.metrics import (  # noqa: E402  # CHANGE: Metrics utilities
    compute_rmse,  # CHANGE: RMSE calculation
    count_monotonicity_violations,  # CHANGE: Monotonicity counter
)
from kinetics.models_phase2 import (  # noqa: E402  # CHANGE: Shared model utilities
    make_baseline_estimators,  # CHANGE: Estimator factory
)
from kinetics.phase2_utils import (  # noqa: E402  # CHANGE: Shared utilities import
    ALL_FEATURE_COLUMNS,  # CHANGE: Feature columns
    RAW_FEATURE_COLUMNS,  # CHANGE: Raw features
    configure_logging,  # CHANGE: Logger factory
    ensure_directory,  # CHANGE: Directory helper
    extract_config_section,  # CHANGE: Config section helper
    load_config,  # CHANGE: Config loader
    prepare_feature_frame,  # CHANGE: Feature engineering
    signed_log1p,  # CHANGE: Target transform function
    inverse_signed_log1p,  # CHANGE: Inverse transform function
)

DEFAULT_SEGMENTS_CSV = _PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv"  # CHANGE: Default input path
DEFAULT_MODELS_DIR = _PROJECT_ROOT / "outputs" / "phase2" / "models"  # CHANGE: Models directory
DEFAULT_METRICS_PATH = _PROJECT_ROOT / "outputs" / "model_performance.csv"  # CHANGE: Metrics file path
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"  # CHANGE: Log directory
DEFAULT_LOGGER_NAME = "phase2.phase2B"  # CHANGE: Logger name constant


def parse_args() -> argparse.Namespace:  # CHANGE: CLI parser definition
    parser = argparse.ArgumentParser(  # CHANGE: Parser creation
        description="Fit regression models for Midilli parameters.",  # CHANGE: Description update
    )
    parser.add_argument(  # CHANGE: Segments dataset argument
        "--segments-csv",
        type=Path,
        default=DEFAULT_SEGMENTS_CSV,
        help="Segment-level dataset produced by phase2A.",
    )
    parser.add_argument(  # CHANGE: Models directory argument
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help="Directory to store trained parameter models.",
    )
    parser.add_argument(  # CHANGE: Metrics output argument
        "--metrics-path",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="Path to write consolidated performance metrics.",
    )
    parser.add_argument(  # CHANGE: Minimum folds argument
        "--min-folds",
        type=int,
        default=3,
        help="Minimum number of cross-validation folds when possible.",
    )
    parser.add_argument(  # CHANGE: Smoothness penalty argument
        "--smoothness-alpha",
        type=float,
        default=0.1,
        help="Penalty weight for monotonicity violations during model selection.",
    )
    parser.add_argument(  # CHANGE: Config path argument
        "--config",
        type=Path,
        default=None,
        help="Optional JSON/YAML config file with overrides.",
    )
    parser.add_argument(  # CHANGE: Log level argument
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (e.g., INFO, DEBUG).",
    )
    parser.add_argument(  # CHANGE: Log directory argument
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for log files.",
    )
    return parser.parse_args()  # CHANGE: Return parsed args


def evaluate_estimators(
    X: pd.DataFrame,
    y: np.ndarray,
    *,
    estimators: Dict[str, object],
    min_folds: int,
    smoothness_alpha: float,
    target: str,
    order_index: np.ndarray,
    logger,
) -> tuple[str, dict[str, dict[str, object]]]:  # CHANGE: Evaluation helper signature
    results: dict[str, dict[str, object]] = {}  # CHANGE: Results container
    best_name = None  # CHANGE: Best estimator tracker
    best_score = np.inf  # CHANGE: Best score tracker

    if order_index.size == 0:  # CHANGE: Fallback ordering
        order_index = np.arange(len(X))  # CHANGE: Default order

    for name, pipeline in estimators.items():  # CHANGE: Iterate estimators
        logger.debug("Evaluating estimator %s for target %s", name, target)  # CHANGE: Debug log
        estimator = pipeline  # CHANGE: Default estimator
        if target == "b":  # CHANGE: Apply signed log transform for b
            estimator = TransformedTargetRegressor(
                regressor=pipeline,
                func=signed_log1p,
                inverse_func=inverse_signed_log1p,
                check_inverse=False,
            )  # CHANGE: Transform target

        n_samples = len(X)  # CHANGE: Sample count
        cv_folds = min(max(min_folds, 2), n_samples) if n_samples >= 2 else 0  # CHANGE: Fold calculation
        metrics = {
            "parameter": target,
            "model_name": name,
            "n_samples": n_samples,
            "cv_folds": cv_folds,
            "mean_rmse": float("nan"),
            "std_rmse": float("nan"),
            "mean_r2": float("nan"),
            "std_r2": float("nan"),
            "train_rmse": float("nan"),
            "monotonicity_violations": 0,
            "penalty": 0.0,
        }  # CHANGE: Metrics skeleton

        if cv_folds >= 2:  # CHANGE: Cross-validation branch
            cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)  # CHANGE: KFold setup
            scores = cross_validate(
                estimator,
                X,
                y,
                scoring={
                    "neg_root_mean_squared_error": "neg_root_mean_squared_error",
                    "r2": "r2",
                },
                cv=cv,
                n_jobs=-1,
                return_estimator=False,
                error_score="raise",
            )  # CHANGE: Perform CV
            rmse = -scores["test_neg_root_mean_squared_error"]  # CHANGE: RMSE extraction
            r2 = scores["test_r2"]  # CHANGE: R2 extraction
            metrics.update(
                {
                    "mean_rmse": float(rmse.mean()),
                    "std_rmse": float(rmse.std(ddof=0)),
                    "mean_r2": float(r2.mean()),
                    "std_r2": float(r2.std(ddof=0)),
                }
            )  # CHANGE: Update metrics

        fitted = clone(estimator).fit(X, y)  # CHANGE: Fit cloned estimator
        preds = fitted.predict(X)  # CHANGE: Predictions on training data
        metrics["train_rmse"] = compute_rmse(y, preds)  # CHANGE: Train RMSE

        sorted_preds = preds[order_index]  # CHANGE: Order predictions
        violations = count_monotonicity_violations(sorted_preds, direction="decreasing")  # CHANGE: Monotonic violations
        metrics["monotonicity_violations"] = int(violations)  # CHANGE: Record violations
        metrics["penalty"] = float(smoothness_alpha * violations)  # CHANGE: Penalty term

        score_base = metrics["mean_rmse"] if np.isfinite(metrics["mean_rmse"]) else metrics["train_rmse"]  # CHANGE: Base score
        score = float(score_base + metrics["penalty"])  # CHANGE: Apply penalty
        logger.debug(
            "Estimator %s: score=%s, mean_rmse=%s, penalty=%s",
            name,
            score,
            metrics["mean_rmse"],
            metrics["penalty"],
        )  # CHANGE: Debug log

        results[name] = {"metrics": metrics, "estimator": fitted}  # CHANGE: Store result

        if np.isnan(score):  # CHANGE: Handle NaN score
            if best_name is None:  # CHANGE: Default fallback
                best_name = name  # CHANGE: Set best estimator
        elif score < best_score:  # CHANGE: Compare scores
            best_score = score  # CHANGE: Update best score
            best_name = name  # CHANGE: Update best estimator

    assert best_name is not None  # CHANGE: Ensure best estimator found
    return best_name, results  # CHANGE: Return evaluation outcome


def main() -> None:  # CHANGE: Main entrypoint
    args = parse_args()  # CHANGE: Parse CLI args
    config = load_config(args.config)  # CHANGE: Load optional config
    section = extract_config_section(config, "phase2B")  # CHANGE: Phase2B config section

    segments_path = Path(section.get("segments_csv", args.segments_csv))  # CHANGE: Segments path resolution
    models_dir = Path(section.get("models_dir", args.models_dir))  # CHANGE: Models directory resolution
    metrics_path = Path(section.get("metrics_path", args.metrics_path))  # CHANGE: Metrics path resolution
    min_folds = int(section.get("min_folds", args.min_folds))  # CHANGE: Minimum folds resolution
    smoothness_alpha = float(section.get("smoothness_alpha", args.smoothness_alpha))  # CHANGE: Penalty resolution
    log_dir = Path(section.get("log_dir", args.log_dir))  # CHANGE: Log directory resolution
    log_level = section.get("log_level", args.log_level)  # CHANGE: Log level resolution

    if not segments_path.exists():  # CHANGE: Validate segments file
        raise FileNotFoundError(f"Segments CSV not found: {segments_path}")  # CHANGE: Error message

    ensure_directory(models_dir)  # CHANGE: Ensure models directory
    ensure_directory(metrics_path.parent)  # CHANGE: Ensure metrics directory
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"  # CHANGE: Log path resolution
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)  # CHANGE: Configure logger

    df = pd.read_csv(segments_path)  # CHANGE: Load segments dataset
    missing_features = [col for col in RAW_FEATURE_COLUMNS if col not in df.columns]  # CHANGE: Validate features
    if missing_features:  # CHANGE: Missing features guard
        raise KeyError("Segments dataset missing required columns: " + ", ".join(missing_features))  # CHANGE: Error message

    feature_frame = prepare_feature_frame(df)  # CHANGE: Build feature frame

    estimators = make_baseline_estimators()  # CHANGE: Instantiate estimators
    metrics_records: list[dict[str, object]] = []  # CHANGE: Metrics list

    for target in ("k", "n", "b"):  # CHANGE: Iterate targets
        if target not in df.columns:  # CHANGE: Guard missing target
            raise KeyError(f"Target column '{target}' missing from segments dataset")  # CHANGE: Error

        y = pd.to_numeric(df[target], errors="coerce").to_numpy(dtype=float)  # CHANGE: Target vector
        mask = np.isfinite(y)  # CHANGE: Finite mask
        X = feature_frame.loc[mask, ALL_FEATURE_COLUMNS]  # CHANGE: Filtered features
        y_valid = y[mask]  # CHANGE: Filtered target

        if len(X) == 0:  # CHANGE: Guard empty training set
            logger.warning("No valid samples for %s; skipping training", target.upper())  # CHANGE: Warning log
            continue  # CHANGE: Skip target

        subset_df = df.loc[mask].copy()  # CHANGE: Subset for ordering
        ordered_subset = subset_df.sort_values(["dataset_name", "segment_start_time"]).index.to_numpy()  # CHANGE: Ordered subset
        order_index = X.index.get_indexer(ordered_subset)  # CHANGE: Position mapping
        order_index = order_index[order_index >= 0]  # CHANGE: Filter valid indices
        order_index = order_index.astype(int, copy=False)  # CHANGE: Ensure integer dtype

        logger.info("Training regressors for %s with %s samples", target.upper(), len(X))  # CHANGE: Info log

        best_name, results = evaluate_estimators(
            X,
            y_valid,
            estimators=estimators,
            min_folds=min_folds,
            smoothness_alpha=smoothness_alpha,
            target=target,
            order_index=order_index,
            logger=logger,
        )  # CHANGE: Evaluate estimators

        for name, payload in results.items():  # CHANGE: Collect metrics
            metrics = dict(payload["metrics"])  # CHANGE: Copy metrics
            metrics["is_best"] = name == best_name  # CHANGE: Flag best model
            metrics_records.append(metrics)  # CHANGE: Append metrics

        final_model = results[best_name]["estimator"]  # CHANGE: Retrieve best estimator
        final_model.fit(X, y_valid)  # CHANGE: Fit on full data

        artifact = {  # CHANGE: Model artifact payload
            "model": final_model,
            "raw_feature_columns": RAW_FEATURE_COLUMNS,
            "all_feature_columns": ALL_FEATURE_COLUMNS,
            "target": target,
            "smoothness_alpha": smoothness_alpha,
        }

        model_path = models_dir / f"{target}_model.pkl"  # CHANGE: Model path
        dump(artifact, model_path)  # CHANGE: Persist model
        logger.info("Saved best model %s for %s to %s", best_name, target.upper(), model_path)  # CHANGE: Log save

    metrics_df = pd.DataFrame(metrics_records)  # CHANGE: Metrics DataFrame
    metrics_df.sort_values(["parameter", "mean_rmse"], inplace=True)  # CHANGE: Sort metrics
    metrics_df.to_csv(metrics_path, index=False)  # CHANGE: Write metrics CSV
    logger.info("Wrote consolidated metrics to %s", metrics_path)  # CHANGE: Log metrics path


if __name__ == "__main__":  # CHANGE: Script guard
    main()  # CHANGE: Invoke main
