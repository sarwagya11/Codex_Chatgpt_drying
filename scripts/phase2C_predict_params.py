"""Predict Midilli parameters for each segment and pre-check continuity."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from joblib import load

import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics.metrics import segment_discontinuities  # noqa: E402
from kinetics.phase2_utils import (  # noqa: E402
    ALL_FEATURE_COLUMNS,
    clip_mr,
    configure_logging,
    ensure_directory,
    extract_config_section,
    load_config,
    midilli_curve,
    prepare_feature_frame,
    inverse_softplus,
)  # noqa: E402

DEFAULT_INPUT_CSV = _PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv"
DEFAULT_MODELS_DIR = _PROJECT_ROOT / "outputs" / "phase2" / "models"
DEFAULT_OUTPUT_PATH = _PROJECT_ROOT / "outputs" / "phase2" / "predicted_params.csv"
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"
DEFAULT_LOGGER_NAME = "phase2.phase2C"

REQUIRED_COLUMNS = {
    "dataset_name",
    "segment_index",
    "segment_start_time",
    "segment_end_time",
    "segment_duration",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use trained models to predict Midilli parameters and continuity gaps.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help="Segment-level dataset produced by phase2A.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help="Directory containing trained parameter models (phase2B).",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Destination CSV for predicted parameters.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for continuity diagnostics.",
    )
    parser.add_argument(
        "--continuity-threshold",
        type=float,
        default=0.02,
        help="Absolute MR gap threshold used to flag continuity violations.",
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
        help="Optional JSON/YAML config file with overrides.",
    )
    return parser.parse_args()


def load_artifact(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact missing: {path}")
    artifact: Dict[str, Any] = load(path)
    if "model" not in artifact:
        raise KeyError(f"Model artifact at {path} is missing the 'model' entry")
    if "all_feature_columns" not in artifact:
        raise KeyError(f"Model artifact at {path} is missing 'all_feature_columns'")
    return artifact


def postprocess_predictions(
    preds_transformed: np.ndarray,
    transform: str,
) -> Tuple[np.ndarray, np.ndarray | None]:
    if transform == "log":
        preds = np.exp(preds_transformed)
        return preds, None
    if transform == "softplus":
        preds_pos = preds_transformed
        preds = inverse_softplus(preds_pos)
        return preds, preds_pos
    return preds_transformed, None


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    section = extract_config_section(config, "phase2C")

    input_path = Path(section.get("input_csv", args.input_csv))
    models_dir = Path(section.get("models_dir", args.models_dir))
    output_path = Path(section.get("output_path", args.output_path))
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))
    continuity_threshold = float(section.get("continuity_threshold", args.continuity_threshold))
    log_dir = Path(section.get("log_dir", args.log_dir))
    log_level = section.get("log_level", args.log_level)

    ensure_directory(output_path.parent)
    ensure_directory(diagnostics_dir)
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)

    df = pd.read_csv(input_path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise KeyError(f"Input dataset missing required columns: {sorted(missing)}")

    features = prepare_feature_frame(df)
    X = features[[col for col in ALL_FEATURE_COLUMNS if col in features.columns]]

    predictions: Dict[str, np.ndarray] = {}

    for target in ("k", "n", "b"):
        artifact_path = models_dir / f"{target}_model.pkl"
        artifact = load_artifact(artifact_path)
        model = artifact["model"]
        model_features = artifact.get("all_feature_columns", [])
        transform = artifact.get("target_transform", "identity")
        pred_column = artifact.get("prediction_column", f"pred_{target}")
        extra_cols = artifact.get("extra_prediction_columns", ())

        missing_features = [col for col in model_features if col not in X.columns]
        if missing_features:
            raise ValueError(
                f"Model for {target} expects missing features: {missing_features}"
            )
        X_model = X[model_features]
        preds_transformed = model.predict(X_model)
        preds, extra = postprocess_predictions(np.asarray(preds_transformed, dtype=float), transform)
        predictions[pred_column] = preds
        if extra is not None and extra_cols:
            predictions[extra_cols[0]] = np.asarray(extra, dtype=float)
        logger.info("Generated predictions for %s", target.upper())

    for column, values in predictions.items():
        df[column] = values

    if "pred_b" not in df.columns and "pred_b_pos" in df.columns:
        df["pred_b"] = inverse_softplus(df["pred_b_pos"].to_numpy(dtype=float))

    if "segment_end_time" not in df.columns or df["segment_end_time"].isna().all():
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]

    start_times = df["segment_start_time"].to_numpy(dtype=float)
    end_times = df["segment_end_time"].to_numpy(dtype=float)
    k_vals = df.get("pred_k").to_numpy(dtype=float)
    n_vals = df.get("pred_n").to_numpy(dtype=float)
    b_vals = df.get("pred_b").to_numpy(dtype=float)

    df["pred_segment_start_MR"] = clip_mr(midilli_curve(start_times, k_vals, n_vals, b_vals))
    df["pred_segment_end_MR"] = clip_mr(midilli_curve(end_times, k_vals, n_vals, b_vals))

    continuity_df = segment_discontinuities(
        df,
        start_col="pred_segment_start_MR",
        end_col="pred_segment_end_MR",
    )
    diagnostics_path = diagnostics_dir / "phase2C_discontinuities.csv"
    if not continuity_df.empty:
        continuity_df.rename(columns={"gap": "pred_continuity_gap"}, inplace=True)
        continuity_df["is_violation"] = (
            continuity_df["pred_continuity_gap"].astype(float).abs() > continuity_threshold
        )
        df = df.merge(
            continuity_df[
                [
                    "dataset_name",
                    "segment_index",
                    "pred_continuity_gap",
                    "prev_segment_end_MR",
                ]
            ],
            on=["dataset_name", "segment_index"],
            how="left",
        )
        df.rename(columns={"prev_segment_end_MR": "prev_pred_end_MR"}, inplace=True)
        continuity_df.to_csv(diagnostics_path, index=False, float_format="%.9g")
        logger.info(
            "Recorded %s continuity checks to %s", len(continuity_df), diagnostics_path
        )
    else:
        pd.DataFrame(
            columns=["dataset_name", "segment_index", "pred_continuity_gap", "is_violation"]
        ).to_csv(diagnostics_path, index=False)
        logger.info("No continuity gaps detected; wrote empty diagnostics to %s", diagnostics_path)
        df["pred_continuity_gap"] = np.nan
        df["prev_pred_end_MR"] = np.nan

    df.to_csv(output_path, index=False, float_format="%.9g")
    logger.info("Wrote predictions for %s segments to %s", len(df), output_path)


if __name__ == "__main__":
    main()
