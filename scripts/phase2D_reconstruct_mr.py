"""Reconstruct MR(t) curves from predicted Midilli parameters."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.phase2_utils import (  # noqa: E402
    clip_mr,
    configure_logging,
    ensure_directory,
    extract_config_section,
    load_config,
    midilli_curve,
    resolve_dataset_path,
    inverse_softplus,
)
from kinetics.visualize import plot_mr_reconstruction  # noqa: E402

DEFAULT_PREDICTIONS_CSV = _PROJECT_ROOT / "outputs" / "phase2" / "predicted_params.csv"
DEFAULT_SUMMARY_INDEX = _PROJECT_ROOT / "outputs" / "recursive_midilli" / "summary_index.json"
DEFAULT_DATA_ROOT = _PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "outputs" / "phase2" / "mr_curves"
DEFAULT_RECONSTRUCTED_CSV = _PROJECT_ROOT / "outputs" / "reconstructed_mr.csv"
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"
DEFAULT_PLOTS_DIR = _PROJECT_ROOT / "outputs" / "plots"
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"
DEFAULT_LOGGER_NAME = "phase2.phase2D"

REQUIRED_COLUMNS = {"dataset_name", "segment_index", "segment_start_time", "segment_duration", "pred_k", "pred_n"}


@dataclass
class DatasetInfo:
    path: Path
    head_trim: float


@dataclass
class ReconstructionResult:
    dataset_name: str
    dataframe: pd.DataFrame
    discontinuity_total: float
    monotonicity_violations: int
    segments_skipped: int
    rmse: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild MR(t) curves using predicted Midilli parameters.",
    )
    parser.add_argument(
        "--predictions-csv",
        type=Path,
        default=DEFAULT_PREDICTIONS_CSV,
        help="CSV produced by phase2C.",
    )
    parser.add_argument(
        "--summary-index",
        type=Path,
        default=DEFAULT_SUMMARY_INDEX,
        help="summary_index.json mapping datasets to raw files.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Directory containing the raw drying datasets.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for per-dataset reconstructed curves.",
    )
    parser.add_argument(
        "--reconstructed-csv",
        type=Path,
        default=DEFAULT_RECONSTRUCTED_CSV,
        help="Path for aggregated reconstructed MR curves.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for diagnostics outputs.",
    )
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=DEFAULT_PLOTS_DIR,
        help="Directory for reconstruction plots.",
    )
    parser.add_argument(
        "--synthetic-points",
        type=int,
        default=75,
        help="Number of synthetic points per segment when ground truth is unavailable.",
    )
    parser.add_argument(
        "--disable-isotonic",
        action="store_true",
        help="Disable isotonic post-processing of predicted curves.",
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


def load_summary_index(summary_path: Path, data_root: Path) -> Dict[str, DatasetInfo]:
    if not summary_path.exists():
        return {}
    payload = json.loads(summary_path.read_text())
    registry: Dict[str, DatasetInfo] = {}
    if isinstance(payload.get("datasets"), list):
        default_trim = float(payload.get("head_trim_min", 0.0))
        for entry in payload["datasets"]:
            raw_input = entry.get("input")
            if not raw_input:
                continue
            resolved = resolve_dataset_path(raw_input, data_root)
            head_trim = float(entry.get("head_trim_min", default_trim))
            registry[Path(raw_input).stem] = DatasetInfo(resolved, head_trim)
    elif isinstance(payload.get("summaries"), list):
        for entry in payload["summaries"]:
            raw_input = entry.get("file")
            if not raw_input:
                continue
            resolved = resolve_dataset_path(raw_input, data_root)
            head_trim = float(entry.get("head_trim_min", 0.0))
            registry[Path(raw_input).stem] = DatasetInfo(resolved, head_trim)
    return registry


def resolve_dataset(info: pd.Series, registry: Dict[str, DatasetInfo], data_root: Path) -> DatasetInfo | None:
    source_path = info.get("source_path")
    if isinstance(source_path, str) and source_path:
        try:
            resolved = resolve_dataset_path(source_path, data_root)
            key = Path(source_path).stem
            head_trim = registry.get(key, DatasetInfo(resolved, 0.0)).head_trim
            return DatasetInfo(resolved, head_trim)
        except FileNotFoundError:
            pass
    dataset_name = info.get("dataset_name")
    if isinstance(dataset_name, str):
        key = Path(dataset_name).stem
        if key in registry:
            return registry[key]
        try:
            resolved = resolve_dataset_path(f"{dataset_name}.csv", data_root)
            return DatasetInfo(resolved, 0.0)
        except FileNotFoundError:
            return None
    return None


def segment_end(row: pd.Series) -> float:
    if pd.notna(row.get("segment_end_time")):
        return float(row["segment_end_time"])
    return float(row["segment_start_time"] + row["segment_duration"])


def evaluate_segment(
    times: np.ndarray,
    params: Tuple[float, float, float],
    prev_end: float | None,
) -> Tuple[np.ndarray, float, float, int]:
    preds = clip_mr(midilli_curve(times, *params))
    discontinuity = 0.0
    if prev_end is not None and preds.size:
        offset = preds[0] - prev_end
        preds = clip_mr(preds - offset)
        discontinuity = abs(preds[0] - prev_end)
    violations = int(np.sum(np.diff(preds) > 0)) if preds.size >= 2 else 0
    end_value = preds[-1] if preds.size else (prev_end if prev_end is not None else float("nan"))
    return preds, end_value, discontinuity, violations


def reconstruct_with_actual(
    dataset_name: str,
    rows: pd.DataFrame,
    dataset_info: DatasetInfo,
    apply_isotonic: bool,
) -> ReconstructionResult:
    preprocess = load_and_preprocess(dataset_info.path, dataset_info.head_trim)
    time = preprocess.time_min.astype(float)
    actual = preprocess.mr_iso.astype(float)

    predicted = np.full_like(actual, np.nan, dtype=float)
    rows_sorted = rows.sort_values("segment_start_time")
    prev_end = None
    discontinuity_total = 0.0
    monotonicity = 0
    segments_skipped = 0

    for _, row in rows_sorted.iterrows():
        start = float(row["segment_start_time"])
        end = segment_end(row)
        mask = (time >= start) & (time <= end + 1e-9)
        if not np.any(mask):
            segments_skipped += 1
            continue
        segment_time = time[mask]
        params = (float(row["pred_k"]), float(row["pred_n"]), float(row["pred_b"]))
        preds, prev_end, discontinuity, violations = evaluate_segment(segment_time, params, prev_end)
        predicted[mask] = preds
        discontinuity_total += discontinuity
        monotonicity += violations

    if apply_isotonic and np.isfinite(predicted).sum() >= 2:
        valid_mask = np.isfinite(predicted)
        iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
        fitted = iso.fit(time[valid_mask], predicted[valid_mask])
        predicted_iso = predicted.copy()
        predicted_iso[valid_mask] = fitted.predict(time[valid_mask])
    else:
        predicted_iso = predicted.copy()

    valid = np.isfinite(predicted_iso) & np.isfinite(actual)
    rmse = float(np.sqrt(np.mean((predicted_iso[valid] - actual[valid]) ** 2))) if np.any(valid) else float("nan")

    df_out = pd.DataFrame(
        {
            "dataset_name": dataset_name,
            "time_min": time,
            "mr_actual": actual,
            "mr_predicted": predicted,
            "mr_predicted_iso": predicted_iso,
        }
    )

    return ReconstructionResult(
        dataset_name=dataset_name,
        dataframe=df_out,
        discontinuity_total=float(discontinuity_total),
        monotonicity_violations=int(monotonicity),
        segments_skipped=segments_skipped,
        rmse=rmse,
    )


def reconstruct_synthetic(
    dataset_name: str,
    rows: pd.DataFrame,
    synthetic_points: int,
    apply_isotonic: bool,
) -> ReconstructionResult:
    rows_sorted = rows.sort_values("segment_start_time")
    time_values: List[float] = []
    predicted_values: List[float] = []
    prev_end = None
    discontinuity_total = 0.0
    monotonicity = 0

    for idx, row in rows_sorted.iterrows():
        start = float(row["segment_start_time"])
        end = segment_end(row)
        if end < start:
            end = start
        count = max(synthetic_points, 2)
        segment_time = np.linspace(start, end, count)
        if time_values and len(segment_time) > 1 and np.isclose(segment_time[0], time_values[-1]):
            segment_time = segment_time[1:]
        params = (float(row["pred_k"]), float(row["pred_n"]), float(row["pred_b"]))
        preds, prev_end, discontinuity, violations = evaluate_segment(segment_time, params, prev_end)
        time_values.extend(segment_time.tolist())
        predicted_values.extend(preds.tolist())
        discontinuity_total += discontinuity
        monotonicity += violations

    time_array = np.asarray(time_values, dtype=float)
    predicted = np.asarray(predicted_values, dtype=float)

    if apply_isotonic and predicted.size >= 2:
        iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
        predicted_iso = iso.fit(time_array, predicted).predict(time_array)
    else:
        predicted_iso = predicted.copy()

    df_out = pd.DataFrame(
        {
            "dataset_name": dataset_name,
            "time_min": time_array,
            "mr_actual": np.full_like(time_array, np.nan, dtype=float),
            "mr_predicted": predicted,
            "mr_predicted_iso": predicted_iso,
        }
    )

    return ReconstructionResult(
        dataset_name=dataset_name,
        dataframe=df_out,
        discontinuity_total=float(discontinuity_total),
        monotonicity_violations=int(monotonicity),
        segments_skipped=0,
        rmse=float("nan"),
    )


def ensure_pred_b(df: pd.DataFrame) -> pd.DataFrame:
    if "pred_b" in df.columns:
        return df
    if "pred_b_pos" in df.columns:
        df = df.copy()
        df["pred_b"] = inverse_softplus(df["pred_b_pos"].to_numpy(dtype=float))
    else:
        raise KeyError("Predictions CSV is missing both 'pred_b' and 'pred_b_pos' columns.")
    return df


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    section = extract_config_section(config, "phase2D")

    predictions_path = Path(section.get("predictions_csv", args.predictions_csv))
    summary_index_path = Path(section.get("summary_index", args.summary_index))
    data_root = Path(section.get("data_root", args.data_root))
    output_dir = Path(section.get("output_dir", args.output_dir))
    reconstructed_csv = Path(section.get("reconstructed_csv", args.reconstructed_csv))
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))
    plots_dir = Path(section.get("plots_dir", args.plots_dir))
    synthetic_points = int(section.get("synthetic_points", args.synthetic_points))
    apply_isotonic = not bool(section.get("disable_isotonic", args.disable_isotonic))
    log_dir = Path(section.get("log_dir", args.log_dir))
    log_level = section.get("log_level", args.log_level)

    ensure_directory(output_dir)
    ensure_directory(reconstructed_csv.parent)
    ensure_directory(diagnostics_dir)
    ensure_directory(plots_dir)
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)

    df = pd.read_csv(predictions_path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise KeyError(f"Predictions CSV missing required columns: {sorted(missing)}")
    df = ensure_pred_b(df)
    if "segment_end_time" not in df.columns or df["segment_end_time"].isna().all():
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]

    registry = load_summary_index(summary_index_path, data_root)

    results: List[ReconstructionResult] = []
    plots_generated: List[Path] = []
    segment_counts = df.groupby("dataset_name").size()

    for dataset_name_raw, group in df.groupby("dataset_name"):
        dataset_name = str(dataset_name_raw)
        group = group.sort_values("segment_start_time")
        info = resolve_dataset(group.iloc[0], registry, data_root)
        if info is not None and info.path.exists():
            result = reconstruct_with_actual(dataset_name, group, info, apply_isotonic)
        else:
            logger.warning(
                "No ground truth found for %s; generating synthetic timeline.", dataset_name
            )
            result = reconstruct_synthetic(dataset_name, group, synthetic_points, apply_isotonic)
        results.append(result)

        curve_path = output_dir / f"{dataset_name}_mr_curve.csv"
        result.dataframe.to_csv(curve_path, index=False, float_format="%.9g")
        plot_path = plot_mr_reconstruction(result.dataframe, dataset_name, plots_dir)
        plots_generated.append(plot_path)
        logger.info("Wrote reconstructed curve for %s to %s", dataset_name, curve_path)

    if not results:
        raise RuntimeError("No datasets were reconstructed.")

    combined = pd.concat([res.dataframe for res in results], ignore_index=True)
    combined.to_csv(reconstructed_csv, index=False, float_format="%.9g")

    diagnostics = pd.DataFrame(
        {
            "dataset_name": [res.dataset_name for res in results],
            "segment_count": [int(segment_counts.get(res.dataset_name, 0)) for res in results],
            "segments_skipped": [res.segments_skipped for res in results],
            "discontinuity_total": [res.discontinuity_total for res in results],
            "monotonicity_violations": [res.monotonicity_violations for res in results],
            "rmse": [res.rmse for res in results],
        }
    )
    diagnostics_path = diagnostics_dir / "phase2D_violation_report.csv"
    diagnostics.to_csv(diagnostics_path, index=False, float_format="%.9g")

    if plots_generated:
        canonical = plots_dir / "reconstruction_plot.png"
        canonical.write_bytes(Path(plots_generated[0]).read_bytes())

    logger.info("Aggregated MR curves written to %s", reconstructed_csv)
    logger.info("Diagnostics written to %s", diagnostics_path)


if __name__ == "__main__":
    main()
