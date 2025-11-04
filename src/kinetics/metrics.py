"""Metrics and diagnostics for drying kinetics predictions."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def count_monotonicity_violations(y: np.ndarray, *, direction: str = "decreasing") -> int:
    """
    Count monotonicity violations in a 1D sequence.
    If direction='decreasing', counts where y[i+1] > y[i].
    """
    if len(y) < 2:
        return 0
    y = np.asarray(y)
    if direction == "decreasing":
        return int(np.sum(y[1:] > y[:-1]))
    elif direction == "increasing":
        return int(np.sum(y[1:] < y[:-1]))
    else:
        raise ValueError(f"Unknown monotonic direction: {direction}")


def continuity_gap(
    start_value: Optional[float], end_value: Optional[float], normalize: bool = True
) -> float:
    """
    Compute absolute difference between segment end and next start.
    If normalize=True, returns gap / (start + end) to scale near [0, 1].
    Returns NaN if inputs are invalid.
    """
    if start_value is None or end_value is None:
        return float("nan")
    if not np.isfinite(start_value) or not np.isfinite(end_value):
        return float("nan")
    
    gap = abs(start_value - end_value)
    if normalize:
        denom = start_value + end_value
        return gap / denom if denom != 0 else 0.0
    return gap



def compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute root mean squared error between prediction and ground truth."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if not np.any(mask):
        return float("nan")
    return float(np.sqrt(np.mean((y_true[mask] - y_pred[mask]) ** 2)))


def check_time_monotonicity(time: np.ndarray) -> bool:
    """Return True if time is strictly increasing."""
    time = np.asarray(time)
    return bool(np.all(np.diff(time) > 0))


def segment_discontinuities(
    df: pd.DataFrame,
    *,
    dataset_col: str = "dataset_name",
    start_col: str = "segment_start_MR",
    end_col: str = "segment_end_MR"
) -> pd.DataFrame:
    """
    Compute per-dataset continuity gap between consecutive segments.
    Returns DataFrame with columns: dataset_name, seg_index, start, end, gap.
    Assumes segments are sorted by segment_start_time.
    """
    results = []
    for name, group in df.groupby(dataset_col):
        group = group.sort_values("segment_start_time")
        prev_end = None
        for i, row in enumerate(group.itertuples()):
            start = getattr(row, start_col, None)
            end = getattr(row, end_col, None)
            if prev_end is not None:
                gap = continuity_gap(start, prev_end)
                results.append({
                    "dataset_name": name,
                    "segment_index": i,
                    "segment_start_MR": start,
                    "prev_segment_end_MR": prev_end,
                    "gap": gap,
                })
            prev_end = end
    return pd.DataFrame(results)
