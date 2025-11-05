"""Predict Midilli parameters for new drying segments."""  # CHANGE: Updated script header

from __future__ import annotations  # CHANGE: Future annotations retained

import argparse  # CHANGE: CLI parsing import
from pathlib import Path  # CHANGE: Path handling
from typing import Any, Dict  # CHANGE: Typing helpers

import numpy as np  # CHANGE: Numerical operations
import pandas as pd  # CHANGE: DataFrame handling
from joblib import load  # CHANGE: Model loading

import sys  # CHANGE: Ensure project importability

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # CHANGE: Project root
_SRC_ROOT = _PROJECT_ROOT / "src"  # CHANGE: Source directory
for candidate in (_PROJECT_ROOT, _SRC_ROOT):  # CHANGE: Extend sys.path loop
    candidate_str = str(candidate)  # CHANGE: Convert to string
    if candidate_str not in sys.path:  # CHANGE: Avoid duplicates
        sys.path.insert(0, candidate_str)  # CHANGE: Insert path

from kinetics.metrics import segment_discontinuities  # noqa: E402  # CHANGE: Continuity diagnostics
from kinetics.phase2_utils import (  # noqa: E402  # CHANGE: Shared utilities import
    ALL_FEATURE_COLUMNS,  # CHANGE: Feature columns
    configure_logging,  # CHANGE: Logger factory
    ensure_directory,  # CHANGE: Directory helper
    extract_config_section,  # CHANGE: Config section helper
    load_config,  # CHANGE: Config loader
    midilli_curve,  # CHANGE: Midilli evaluation
    prepare_feature_frame,  # CHANGE: Feature engineering
)  # CHANGE: Utilities import

DEFAULT_INPUT_CSV = _PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv"  # CHANGE: Default dataset path
DEFAULT_MODELS_DIR = _PROJECT_ROOT / "outputs" / "phase2" / "models"  # CHANGE: Models directory
DEFAULT_OUTPUT_PATH = _PROJECT_ROOT / "outputs" / "phase2" / "predicted_params.csv"  # CHANGE: Output path
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"  # CHANGE: Diagnostics directory
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"  # CHANGE: Log directory
DEFAULT_LOGGER_NAME = "phase2.phase2C"  # CHANGE: Logger name constant

REQUIRED_TIMING_COLUMNS = {"segment_start_time", "segment_duration"}  # CHANGE: Timing requirements
REQUIRED_RAW_FEATURES = {"T", "RH", "velocity", "thickness", "segment_position"}  # CHANGE: Feature requirements
BOUNDARY_COLUMNS = {"segment_start_MR", "segment_end_MR"}  # CHANGE: Boundary requirements


def parse_args() -> argparse.Namespace:  # CHANGE: CLI parser definition
    parser = argparse.ArgumentParser(  # CHANGE: Parser creation
        description="Use trained regressors to predict Midilli parameters.",  # CHANGE: Description update
    )
    parser.add_argument(  # CHANGE: Input CSV argument
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help="CSV containing segment descriptors for prediction.",
    )
    parser.add_argument(  # CHANGE: Models directory argument
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help="Directory with trained parameter models (from phase2B).",
    )
    parser.add_argument(  # CHANGE: Output path argument
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Destination CSV for predicted parameters.",
    )
    parser.add_argument(  # CHANGE: Diagnostics directory argument
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for continuity diagnostics.",
    )
    parser.add_argument(  # CHANGE: Continuity threshold argument
        "--continuity-threshold",
        type=float,
        default=0.02,
        help="Normalized gap threshold to flag discontinuities.",
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


def load_artifact(path: Path) -> Dict[str, Any]:  # CHANGE: Artifact loader helper
    if not path.exists():  # CHANGE: Guard missing file
        raise FileNotFoundError(f"Model artifact missing: {path}")  # CHANGE: Error message
    artifact: Dict[str, Any] = load(path)  # CHANGE: Load artifact
    if "model" not in artifact:  # CHANGE: Validate contents
        raise KeyError(f"Model artifact at {path} is missing the 'model' entry")  # CHANGE: Error message
    return artifact  # CHANGE: Return artifact


def main() -> None:  # CHANGE: Main entrypoint
    args = parse_args()  # CHANGE: Parse CLI args
    config = load_config(args.config)  # CHANGE: Load optional config
    section = extract_config_section(config, "phase2C")  # CHANGE: Phase2C config section

    input_path = Path(section.get("input_csv", args.input_csv))  # CHANGE: Input path resolution
    models_dir = Path(section.get("models_dir", args.models_dir))  # CHANGE: Models directory resolution
    output_path = Path(section.get("output_path", args.output_path))  # CHANGE: Output path resolution
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))  # CHANGE: Diagnostics directory resolution
    continuity_threshold = float(section.get("continuity_threshold", args.continuity_threshold))  # CHANGE: Threshold resolution
    log_dir = Path(section.get("log_dir", args.log_dir))  # CHANGE: Log directory resolution
    log_level = section.get("log_level", args.log_level)  # CHANGE: Log level resolution

    ensure_directory(output_path.parent)  # CHANGE: Ensure output directory
    ensure_directory(diagnostics_dir)  # CHANGE: Ensure diagnostics directory
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"  # CHANGE: Log path resolution
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)  # CHANGE: Configure logger

    df = pd.read_csv(input_path)  # CHANGE: Load input dataset
    logger.info("Loaded %s segments for prediction from %s", len(df), input_path)  # CHANGE: Log load

    missing_timing = REQUIRED_TIMING_COLUMNS - set(df.columns)  # CHANGE: Timing validation
    if missing_timing:  # CHANGE: Guard missing timing
        raise KeyError(f"Missing timing columns: {sorted(missing_timing)}")  # CHANGE: Error message

    missing_features = REQUIRED_RAW_FEATURES - set(df.columns)  # CHANGE: Feature validation
    if missing_features:  # CHANGE: Guard missing features
        raise KeyError(f"Missing required features: {sorted(missing_features)}")  # CHANGE: Error message

    missing_boundaries = BOUNDARY_COLUMNS - set(df.columns)  # CHANGE: Boundary validation
    if missing_boundaries:  # CHANGE: Guard missing MR boundaries
        raise KeyError(f"Missing MR boundary columns: {sorted(missing_boundaries)}")  # CHANGE: Error message

    feature_frame = prepare_feature_frame(df)  # CHANGE: Build feature frame

    if feature_frame.isnull().any().any():  # CHANGE: Feature NaN check
        logger.warning("NaNs found in input features — prediction quality may degrade.")  # CHANGE: Warning log
        df["has_nan_features"] = feature_frame.isnull().any(axis=1)  # CHANGE: Flag NaNs
    else:  # CHANGE: No NaNs branch
        df["has_nan_features"] = False  # CHANGE: Flag default

    predictions: Dict[str, np.ndarray] = {}  # CHANGE: Predictions container

    for target in ("k", "n", "b"):  # CHANGE: Iterate targets
        artifact_path = models_dir / f"{target}_model.pkl"  # CHANGE: Artifact path
        artifact = load_artifact(artifact_path)  # CHANGE: Load artifact
        model = artifact["model"]  # CHANGE: Extract model
        model_features = artifact.get("all_feature_columns", ALL_FEATURE_COLUMNS)  # CHANGE: Feature list

        missing_in_X = set(model_features) - set(feature_frame.columns)  # CHANGE: Feature expectation check
        if missing_in_X:  # CHANGE: Guard missing columns
            raise ValueError(
                f"Model for {target} expects missing columns: {sorted(missing_in_X)}"
            )  # CHANGE: Error message

        X = feature_frame[model_features]  # CHANGE: Feature subset
        preds = model.predict(X)  # type: ignore[call-arg]  # CHANGE: Generate predictions

        if not np.all(np.isfinite(preds)):  # CHANGE: Finite guard
            raise ValueError(f"Non-finite predictions detected in {target}")  # CHANGE: Error message

        predictions[f"pred_{target}"] = np.asarray(preds, dtype=float)  # CHANGE: Store predictions
        logger.info("Generated predictions for %s", target.upper())  # CHANGE: Log prediction

    for col, values in predictions.items():  # CHANGE: Attach predictions to DataFrame
        df[col] = values  # CHANGE: Assign column

    if "segment_end_time" not in df.columns:  # CHANGE: Ensure end time column
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]  # CHANGE: Compute end time

    start_times = df["segment_start_time"].to_numpy(dtype=float)  # CHANGE: Start time array
    end_times = df["segment_end_time"].to_numpy(dtype=float)  # CHANGE: End time array
    k_vals = df["pred_k"].to_numpy(dtype=float)  # CHANGE: Predicted k array
    n_vals = df["pred_n"].to_numpy(dtype=float)  # CHANGE: Predicted n array
    b_vals = df["pred_b"].to_numpy(dtype=float)  # CHANGE: Predicted b array

    df["pred_segment_start_MR"] = midilli_curve(start_times, k_vals, n_vals, b_vals)  # CHANGE: Predicted start MR
    df["pred_segment_end_MR"] = midilli_curve(end_times, k_vals, n_vals, b_vals)  # CHANGE: Predicted end MR

    continuity_df = segment_discontinuities(
        df,
        start_col="pred_segment_start_MR",
        end_col="pred_segment_end_MR",
    )  # CHANGE: Compute continuity diagnostics
    if not continuity_df.empty:  # CHANGE: Annotate violations
        continuity_df.rename(columns={"gap": "continuity_gap"}, inplace=True)  # CHANGE: Rename column
        continuity_df["is_violation"] = continuity_df["continuity_gap"].astype(float) > continuity_threshold  # CHANGE: Flag
        diagnostics_path = diagnostics_dir / "phase2C_discontinuities.csv"  # CHANGE: Diagnostics path
        continuity_df.to_csv(diagnostics_path, index=False)  # CHANGE: Write diagnostics
        logger.info(
            "Recorded %s continuity checks to %s", len(continuity_df), diagnostics_path
        )  # CHANGE: Log diagnostics
    else:  # CHANGE: No continuity records
        diagnostics_path = diagnostics_dir / "phase2C_discontinuities.csv"  # CHANGE: Diagnostics path fallback
        pd.DataFrame(columns=["dataset_name", "segment_index", "continuity_gap", "is_violation"]).to_csv(
            diagnostics_path, index=False
        )  # CHANGE: Write empty diagnostics
        logger.info("No continuity gaps detected; wrote empty diagnostics to %s", diagnostics_path)  # CHANGE: Log empty

    df.to_csv(output_path, index=False, float_format="%.9g")  # CHANGE: Write predictions CSV
    logger.info("Wrote predictions for %s segments to %s", len(df), output_path)  # CHANGE: Log output


if __name__ == "__main__":  # CHANGE: Script guard
    main()  # CHANGE: Invoke main
