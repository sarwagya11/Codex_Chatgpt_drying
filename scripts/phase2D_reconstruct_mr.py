"""Reconstruct drying curves from predicted Midilli parameters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

# Ensure project modules are importable when running as a script -----------------
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.phase2_utils import midilli_curve, resolve_dataset_path  # noqa: E402


REQUIRED_COLUMNS = {"segment_start_time", "segment_duration", "pred_k", "pred_n", "pred_b"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild MR(t) curves using predicted Midilli parameters.",
    )
    parser.add_argument(
        "--predictions-csv",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2" / "predicted_params.csv",
        help="CSV produced by phase2C.",
    )
    parser.add_argument(
        "--summary-index",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "recursive_split" / "summary_index.json",
        help="Phase-1 summary index for resolving dataset metadata.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=_PROJECT_ROOT / "data",
        help="Directory containing the raw drying datasets.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2" / "mr_curves_comparison",
        help="Directory for reconstructed curves and metrics.",
    )
    parser.add_argument(
        "--synthetic-points",
        type=int,
        default=75,
        help="Points per segment when no ground-truth dataset is available.",
    )
    return parser.parse_args()


def load_dataset_registry(summary_path: Path, data_root: Path) -> Dict[str, Tuple[Path, float]]:
    if not summary_path.exists():
        return {}

    summary = json.loads(summary_path.read_text())
    default_head_trim = float(summary.get("head_trim_min", 0.0))
    registry: Dict[str, Tuple[Path, float]] = {}

    for entry in summary.get("datasets", []):
        raw_input = entry.get("input")
        if raw_input is None:
            continue
        resolved = resolve_dataset_path(raw_input, data_root)
        head_trim = float(entry.get("head_trim_min", default_head_trim))
        registry[resolved.name] = (resolved, head_trim)

    return registry


def segment_end(row: pd.Series) -> float:
    if pd.notna(row.get("segment_end_time")):
        return float(row["segment_end_time"])
    return float(row["segment_start_time"] + row["segment_duration"])


def reconstruct_with_actual(
    dataset_name: str,
    rows: pd.DataFrame,
    dataset_path: Path,
    head_trim: float,
) -> Tuple[pd.DataFrame, float]:
    preprocess = load_and_preprocess(dataset_path, head_trim)
    time = preprocess.time_min
    actual = preprocess.mr_iso
    predicted = np.full_like(actual, np.nan, dtype=float)

    rows_sorted = rows.sort_values("segment_start_time")
    for _, row in rows_sorted.iterrows():
        start = float(row["segment_start_time"])
        end = segment_end(row)
        mask = (time >= start) & (time <= end + 1e-9)
        if not np.any(mask):
            continue
        segment_time = time[mask]
        preds = midilli_curve(segment_time, row["pred_k"], row["pred_n"], row["pred_b"])
        predicted[mask] = np.clip(preds, 0.0, 1.1)

    curve = pd.DataFrame(
        {
            "dataset_name": dataset_name,
            "time_min": time,
            "mr_actual": actual,
            "mr_predicted": predicted,
        }
    )
    valid = np.isfinite(predicted) & np.isfinite(actual)
    rmse = (
        float(np.sqrt(np.mean((predicted[valid] - actual[valid]) ** 2)))
        if np.any(valid)
        else float("nan")
    )
    return curve, rmse


def reconstruct_synthetic(
    dataset_label: str,
    rows: pd.DataFrame,
    points_per_segment: int,
) -> pd.DataFrame:
    times: list[np.ndarray] = []
    preds: list[np.ndarray] = []

    rows_sorted = rows.sort_values("segment_start_time")
    for idx, (_, row) in enumerate(rows_sorted.iterrows()):
        start = float(row["segment_start_time"])
        end = segment_end(row)
        if not np.isfinite(start) or not np.isfinite(end):
            continue
        n_points = max(points_per_segment, 2)
        segment_times = np.linspace(start, end, n_points)
        if idx > 0 and times:
            segment_times = segment_times[1:]
        times.append(segment_times)
        preds.append(
            np.clip(
                midilli_curve(segment_times, row["pred_k"], row["pred_n"], row["pred_b"]),
                0.0,
                1.1,
            )
        )

    if not times:
        return pd.DataFrame(columns=["dataset_name", "time_min", "mr_actual", "mr_predicted"])

    time_series = np.concatenate(times)
    pred_series = np.concatenate(preds)
    return pd.DataFrame(
        {
            "dataset_name": dataset_label,
            "time_min": time_series,
            "mr_actual": np.full_like(time_series, np.nan, dtype=float),
            "mr_predicted": pred_series,
        }
    )


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.predictions_csv)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise KeyError(
            "Predictions CSV missing required columns: " + ", ".join(sorted(missing))
        )

    if "segment_end_time" not in df.columns:
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]

    registry = load_dataset_registry(args.summary_index, args.data_root)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_records: list[dict] = []

    if "dataset_name" in df.columns:
        group_labels = df["dataset_name"].fillna("scenario").astype(str)
    else:
        group_labels = pd.Series(["scenario"] * len(df), index=df.index)

    grouped = df.groupby(group_labels)

    for dataset_name, rows in grouped:
        dataset_label = dataset_name if isinstance(dataset_name, str) else str(dataset_name)
        registry_entry = registry.get(dataset_label)

        if registry_entry is not None:
            dataset_path, head_trim = registry_entry
            curve_df, rmse = reconstruct_with_actual(dataset_label, rows, dataset_path, head_trim)
        else:
            curve_df = reconstruct_synthetic(dataset_label, rows, args.synthetic_points)
            rmse = float("nan")

        curve_path = output_dir / f"{dataset_label}_mr_curve.csv"
        curve_df.to_csv(curve_path, index=False)
        metrics_records.append({"dataset_name": dataset_label, "rmse": rmse})
        print(f"Saved reconstructed curve for {dataset_label} to {curve_path}")

    metrics_df = pd.DataFrame(metrics_records)
    metrics_path = output_dir / "mr_reconstruction_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"Wrote RMSE summary to {metrics_path}")


if __name__ == "__main__":
    main()
