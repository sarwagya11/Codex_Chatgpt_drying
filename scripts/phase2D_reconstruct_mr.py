"""Reconstruct drying curves from predicted Midilli parameters."""  # CHANGE: Updated script header

from __future__ import annotations  # CHANGE: Future annotations retained

import argparse  # CHANGE: CLI parsing import
import json  # CHANGE: Summary parsing
import shutil  # CHANGE: File copying for plots
from pathlib import Path  # CHANGE: Path handling
from typing import Dict, Tuple  # CHANGE: Typing helpers

import numpy as np  # CHANGE: Numerical operations
import pandas as pd  # CHANGE: DataFrame handling

import sys  # CHANGE: Ensure project importability

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # CHANGE: Project root
_SRC_ROOT = _PROJECT_ROOT / "src"  # CHANGE: Source directory
for candidate in (_PROJECT_ROOT, _SRC_ROOT):  # CHANGE: Extend sys.path loop
    candidate_str = str(candidate)  # CHANGE: Convert to string
    if candidate_str not in sys.path:  # CHANGE: Avoid duplicates
        sys.path.insert(0, candidate_str)  # CHANGE: Insert path

from kinetics import load_and_preprocess  # noqa: E402  # CHANGE: Preprocess import
from kinetics.metrics import count_monotonicity_violations  # noqa: E402  # CHANGE: Violation counter
from kinetics.phase2_utils import (  # noqa: E402  # CHANGE: Shared utilities import
    configure_logging,  # CHANGE: Logger factory
    ensure_directory,  # CHANGE: Directory helper
    extract_config_section,  # CHANGE: Config section helper
    load_config,  # CHANGE: Config loader
    midilli_curve,  # CHANGE: Midilli evaluation
    resolve_dataset_path,  # CHANGE: Dataset resolver
)
from kinetics.visualize import plot_mr_reconstruction  # noqa: E402  # CHANGE: Visualization helper

REQUIRED_COLUMNS = {"segment_start_time", "segment_duration", "pred_k", "pred_n", "pred_b"}  # CHANGE: Required columns
DEFAULT_PREDICTIONS_CSV = _PROJECT_ROOT / "outputs" / "phase2" / "predicted_params.csv"  # CHANGE: Default predictions path
DEFAULT_SUMMARY_INDEX = _PROJECT_ROOT / "outputs" / "recursive_split" / "summary_index.json"  # CHANGE: Summary index path
DEFAULT_DATA_ROOT = _PROJECT_ROOT / "data"  # CHANGE: Data root
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "outputs" / "phase2" / "mr_curves"  # CHANGE: Per-dataset curves directory
DEFAULT_RECONSTRUCTED_CSV = _PROJECT_ROOT / "outputs" / "reconstructed_mr.csv"  # CHANGE: Global output path
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"  # CHANGE: Diagnostics directory
DEFAULT_PLOTS_DIR = _PROJECT_ROOT / "outputs" / "plots"  # CHANGE: Plots directory
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"  # CHANGE: Log directory
DEFAULT_LOGGER_NAME = "phase2.phase2D"  # CHANGE: Logger name constant


def parse_args() -> argparse.Namespace:  # CHANGE: CLI parser definition
    parser = argparse.ArgumentParser(  # CHANGE: Parser creation
        description="Rebuild MR(t) curves using predicted Midilli parameters.",  # CHANGE: Description update
    )
    parser.add_argument(  # CHANGE: Predictions CSV argument
        "--predictions-csv",
        type=Path,
        default=DEFAULT_PREDICTIONS_CSV,
        help="CSV produced by phase2C.",
    )
    parser.add_argument(  # CHANGE: Summary index argument
        "--summary-index",
        type=Path,
        default=DEFAULT_SUMMARY_INDEX,
        help="Phase-1 summary index for resolving dataset metadata.",
    )
    parser.add_argument(  # CHANGE: Data root argument
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Directory containing the raw drying datasets.",
    )
    parser.add_argument(  # CHANGE: Per-dataset output directory argument
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for reconstructed curves and per-dataset diagnostics.",
    )
    parser.add_argument(  # CHANGE: Synthetic points argument
        "--synthetic-points",
        type=int,
        default=75,
        help="Points per segment when no ground-truth dataset is available.",
    )
    parser.add_argument(  # CHANGE: Global reconstructed CSV argument
        "--reconstructed-csv",
        type=Path,
        default=DEFAULT_RECONSTRUCTED_CSV,
        help="Path for the aggregated reconstructed MR curves.",
    )
    parser.add_argument(  # CHANGE: Diagnostics directory argument
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for continuity/monotonicity diagnostics.",
    )
    parser.add_argument(  # CHANGE: Plots directory argument
        "--plots-dir",
        type=Path,
        default=DEFAULT_PLOTS_DIR,
        help="Directory for reconstruction plots.",
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


def load_dataset_registry(summary_path: Path, data_root: Path) -> Dict[str, Tuple[Path, float]]:  # CHANGE: Registry helper
    if not summary_path.exists():  # CHANGE: Guard missing summary
        return {}  # CHANGE: Return empty registry
    summary = json.loads(summary_path.read_text())  # CHANGE: Load summary JSON
    default_head_trim = float(summary.get("head_trim_min", 0.0))  # CHANGE: Default head trim
    registry: Dict[str, Tuple[Path, float]] = {}  # CHANGE: Registry container
    for entry in summary.get("datasets", []):  # CHANGE: Iterate datasets
        raw_input = entry.get("input")  # CHANGE: Raw input path
        if raw_input is None:  # CHANGE: Skip missing path
            continue  # CHANGE: Continue loop
        resolved = resolve_dataset_path(raw_input, data_root)  # CHANGE: Resolve dataset
        head_trim = float(entry.get("head_trim_min", default_head_trim))  # CHANGE: Determine head trim
        registry[resolved.name] = (resolved, head_trim)  # CHANGE: Store registry entry
    return registry  # CHANGE: Return registry


def segment_end(row: pd.Series) -> float:  # CHANGE: Segment end helper
    if pd.notna(row.get("segment_end_time")):  # CHANGE: Use provided end time
        return float(row["segment_end_time"])  # CHANGE: Return explicit end
    return float(row["segment_start_time"] + row["segment_duration"])  # CHANGE: Compute fallback


def enforce_continuity(preds: np.ndarray, last_value: float | None) -> Tuple[np.ndarray, float]:  # CHANGE: Continuity enforcement helper
    if last_value is None or not np.isfinite(last_value):  # CHANGE: No adjustment needed
        return preds, preds[-1] if preds.size else float("nan")  # CHANGE: Return as-is
    offset = preds[0] - last_value  # CHANGE: Compute offset
    adjusted = np.clip(preds - offset, 0.0, 1.1)  # CHANGE: Apply offset and clip
    return adjusted, adjusted[-1] if adjusted.size else float("nan")  # CHANGE: Return adjusted preds


def reconstruct_with_actual(
    dataset_name: str,
    rows: pd.DataFrame,
    dataset_path: Path,
    head_trim: float,
) -> Tuple[pd.DataFrame, float, dict]:  # CHANGE: Reconstruction with ground truth
    preprocess = load_and_preprocess(dataset_path, head_trim)  # CHANGE: Load dataset
    time = preprocess.time_min  # CHANGE: Time series
    actual = preprocess.mr_iso  # CHANGE: Actual MR
    predicted = np.full_like(actual, np.nan, dtype=float)  # CHANGE: Predicted array

    rows_sorted = rows.sort_values("segment_start_time")  # CHANGE: Sort segments
    last_mr = None  # CHANGE: Last MR tracker
    discontinuity = 0.0  # CHANGE: Discontinuity accumulator
    monotonic_violations = 0  # CHANGE: Monotonicity counter

    for _, row in rows_sorted.iterrows():  # CHANGE: Iterate segments
        start = float(row["segment_start_time"])  # CHANGE: Start time
        end = segment_end(row)  # CHANGE: End time
        mask = (time >= start) & (time <= end + 1e-9)  # CHANGE: Segment mask
        if not np.any(mask):  # CHANGE: Skip if no points
            continue  # CHANGE: Continue loop
        segment_time = time[mask]  # CHANGE: Segment times
        preds = midilli_curve(segment_time, row["pred_k"], row["pred_n"], row["pred_b"])  # CHANGE: Evaluate Midilli
        preds = np.clip(preds, 0.0, 1.1)  # CHANGE: Clip predictions

        if last_mr is not None:  # CHANGE: Continuity enforcement
            preds, last_mr_candidate = enforce_continuity(preds, last_mr)  # CHANGE: Apply continuity
            discontinuity += abs(preds[0] - last_mr)  # CHANGE: Accumulate discontinuity
            last_mr = last_mr_candidate  # CHANGE: Update last MR
        else:
            last_mr = preds[-1]  # CHANGE: Initialize last MR

        monotonicity = np.diff(preds)  # CHANGE: Differences
        monotonic_violations += int(np.sum(monotonicity > 0))  # CHANGE: Count upward jumps
        predicted[mask] = preds  # CHANGE: Store predictions

    valid = np.isfinite(predicted) & np.isfinite(actual)  # CHANGE: Valid mask
    rmse = np.sqrt(np.mean((predicted[valid] - actual[valid]) ** 2)) if np.any(valid) else float("nan")  # CHANGE: RMSE calculation

    df_out = pd.DataFrame(  # CHANGE: Output DataFrame
        {
            "dataset_name": dataset_name,
            "time_min": time,
            "mr_actual": actual,
            "mr_predicted": predicted,
        }
    )

    diag = {  # CHANGE: Diagnostics payload
        "dataset_name": dataset_name,
        "discontinuity_total": float(discontinuity),
        "monotonicity_violations": int(monotonic_violations),
        "rmse": float(rmse),
    }
    return df_out, rmse, diag  # CHANGE: Return reconstructed data


def reconstruct_synthetic(
    dataset_label: str,
    rows: pd.DataFrame,
    points_per_segment: int,
) -> Tuple[pd.DataFrame, dict]:  # CHANGE: Reconstruction without ground truth
    times: list[np.ndarray] = []  # CHANGE: Time segments
    preds_list: list[np.ndarray] = []  # CHANGE: Prediction segments
    last_mr = None  # CHANGE: Last MR tracker
    discontinuity = 0.0  # CHANGE: Discontinuity accumulator
    monotonic_violations = 0  # CHANGE: Monotonicity counter

    rows_sorted = rows.sort_values("segment_start_time")  # CHANGE: Sort segments
    for _, row in rows_sorted.iterrows():  # CHANGE: Iterate segments
        start = float(row["segment_start_time"])  # CHANGE: Start time
        end = segment_end(row)  # CHANGE: End time
        if not np.isfinite(start) or not np.isfinite(end):  # CHANGE: Guard invalid bounds
            continue  # CHANGE: Continue loop
        segment_times = np.linspace(start, end, max(points_per_segment, 2))  # CHANGE: Segment time grid
        preds = np.clip(midilli_curve(segment_times, row["pred_k"], row["pred_n"], row["pred_b"]), 0.0, 1.1)  # CHANGE: Evaluate Midilli
        if last_mr is not None:  # CHANGE: Continuity enforcement
            preds, last_mr_candidate = enforce_continuity(preds, last_mr)  # CHANGE: Apply continuity
            discontinuity += abs(preds[0] - last_mr)  # CHANGE: Accumulate discontinuity
            last_mr = last_mr_candidate  # CHANGE: Update last MR
        else:
            last_mr = preds[-1]  # CHANGE: Initialize last MR
        monotonic_violations += count_monotonicity_violations(preds, direction="decreasing")  # CHANGE: Count violations
        times.append(segment_times)  # CHANGE: Append times
        preds_list.append(preds)  # CHANGE: Append predictions

    if not times:  # CHANGE: Guard no predictions
        return (
            pd.DataFrame(columns=["dataset_name", "time_min", "mr_actual", "mr_predicted"]),
            {"dataset_name": dataset_label, "discontinuity_total": 0.0, "monotonicity_violations": 0, "rmse": float("nan")},
        )  # CHANGE: Return empty

    time_series = np.concatenate(times)  # CHANGE: Concatenate times
    pred_series = np.concatenate(preds_list)  # CHANGE: Concatenate predictions
    df = pd.DataFrame(  # CHANGE: Output DataFrame
        {
            "dataset_name": dataset_label,
            "time_min": time_series,
            "mr_actual": np.full_like(time_series, np.nan, dtype=float),
            "mr_predicted": pred_series,
        }
    )

    diag = {  # CHANGE: Diagnostics payload
        "dataset_name": dataset_label,
        "discontinuity_total": float(discontinuity),
        "monotonicity_violations": int(monotonic_violations),
        "rmse": float("nan"),
    }
    return df, diag  # CHANGE: Return synthetic reconstruction


def main() -> None:  # CHANGE: Main entrypoint
    args = parse_args()  # CHANGE: Parse CLI args
    config = load_config(args.config)  # CHANGE: Load optional config
    section = extract_config_section(config, "phase2D")  # CHANGE: Phase2D config section

    predictions_path = Path(section.get("predictions_csv", args.predictions_csv))  # CHANGE: Predictions path resolution
    summary_index = Path(section.get("summary_index", args.summary_index))  # CHANGE: Summary path resolution
    data_root = Path(section.get("data_root", args.data_root))  # CHANGE: Data root resolution
    output_dir = Path(section.get("output_dir", args.output_dir))  # CHANGE: Output directory resolution
    synthetic_points = int(section.get("synthetic_points", args.synthetic_points))  # CHANGE: Synthetic points resolution
    reconstructed_csv = Path(section.get("reconstructed_csv", args.reconstructed_csv))  # CHANGE: Global CSV resolution
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))  # CHANGE: Diagnostics directory resolution
    plots_dir = Path(section.get("plots_dir", args.plots_dir))  # CHANGE: Plots directory resolution
    log_dir = Path(section.get("log_dir", args.log_dir))  # CHANGE: Log directory resolution
    log_level = section.get("log_level", args.log_level)  # CHANGE: Log level resolution

    for path in [output_dir, diagnostics_dir, plots_dir, reconstructed_csv.parent]:  # CHANGE: Ensure directories
        ensure_directory(path)  # CHANGE: Create directories
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"  # CHANGE: Log path resolution
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)  # CHANGE: Configure logger

    df = pd.read_csv(predictions_path)  # CHANGE: Load predictions
    missing = REQUIRED_COLUMNS - set(df.columns)  # CHANGE: Required columns check
    if missing:  # CHANGE: Guard missing columns
        raise KeyError("Predictions CSV missing required columns: " + ", ".join(sorted(missing)))  # CHANGE: Error message
    if "segment_end_time" not in df.columns:  # CHANGE: Ensure end time column
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]  # CHANGE: Compute end time

    registry = load_dataset_registry(summary_index, data_root)  # CHANGE: Load registry
    logger.info("Loaded registry for %s datasets", len(registry))  # CHANGE: Log registry size

    metrics_records: list[dict] = []  # CHANGE: Diagnostics records
    curve_frames: list[pd.DataFrame] = []  # CHANGE: Combined curves
    plot_paths: list[Path] = []  # CHANGE: Plot paths

    group_labels = df["dataset_name"].fillna("scenario").astype(str)  # CHANGE: Dataset labels
    grouped = df.groupby(group_labels)  # CHANGE: Group predictions

    for dataset_name, rows in grouped:  # CHANGE: Iterate datasets
        dataset_label = str(dataset_name)  # CHANGE: Normalize label
        registry_entry = registry.get(dataset_label)  # CHANGE: Lookup dataset
        if registry_entry:  # CHANGE: Actual dataset branch
            dataset_path, head_trim = registry_entry  # CHANGE: Unpack registry entry
            curve_df, rmse, diag = reconstruct_with_actual(dataset_label, rows, dataset_path, head_trim)  # CHANGE: Reconstruct actual
        else:  # CHANGE: Synthetic branch
            curve_df, diag = reconstruct_synthetic(dataset_label, rows, synthetic_points)  # CHANGE: Reconstruct synthetic
            rmse = diag.get("rmse", float("nan"))  # CHANGE: RMSE fallback

        curve_path = output_dir / f"{dataset_label}_mr_curve.csv"  # CHANGE: Per-dataset curve path
        curve_df.to_csv(curve_path, index=False, float_format="%.9g")  # CHANGE: Write curve CSV
        logger.info("Saved curve for %s to %s", dataset_label, curve_path)  # CHANGE: Log curve path

        metrics_records.append(diag)  # CHANGE: Append diagnostics
        curve_frames.append(curve_df)  # CHANGE: Append DataFrame

        plot_path = plot_mr_reconstruction(curve_df, dataset_label, plots_dir)  # CHANGE: Generate plot
        plot_paths.append(plot_path)  # CHANGE: Track plot
        logger.debug("Generated plot for %s at %s", dataset_label, plot_path)  # CHANGE: Debug log

    if curve_frames:  # CHANGE: Aggregate curves
        combined_df = pd.concat(curve_frames, ignore_index=True)  # CHANGE: Combine DataFrames
        combined_df.to_csv(reconstructed_csv, index=False, float_format="%.9g")  # CHANGE: Write aggregated CSV
        logger.info("Wrote aggregated reconstruction to %s", reconstructed_csv)  # CHANGE: Log aggregated path
    else:  # CHANGE: No curves branch
        pd.DataFrame(columns=["dataset_name", "time_min", "mr_actual", "mr_predicted"]).to_csv(
            reconstructed_csv, index=False
        )  # CHANGE: Write empty aggregated CSV
        logger.warning("No curves reconstructed; wrote empty aggregated file to %s", reconstructed_csv)  # CHANGE: Warn empty

    diagnostics_df = pd.DataFrame(metrics_records)  # CHANGE: Diagnostics DataFrame
    diagnostics_path = diagnostics_dir / "phase2D_violation_report.csv"  # CHANGE: Diagnostics CSV path
    diagnostics_df.to_csv(diagnostics_path, index=False)  # CHANGE: Write diagnostics
    logger.info("Recorded reconstruction diagnostics to %s", diagnostics_path)  # CHANGE: Log diagnostics

    if plot_paths:  # CHANGE: Canonical plot output
        canonical_plot = plots_dir / "reconstruction_plot.png"  # CHANGE: Canonical plot path
        primary_plot = plot_paths[0]  # CHANGE: Primary plot path
        if primary_plot != canonical_plot:  # CHANGE: Avoid duplicate copy
            shutil.copyfile(primary_plot, canonical_plot)  # CHANGE: Copy plot
        logger.info("Copied representative plot to %s", canonical_plot)  # CHANGE: Log canonical plot
    else:  # CHANGE: No plots branch
        logger.warning("No plots were generated during reconstruction.")  # CHANGE: Warn missing plots


if __name__ == "__main__":  # CHANGE: Script guard
    main()  # CHANGE: Invoke main
