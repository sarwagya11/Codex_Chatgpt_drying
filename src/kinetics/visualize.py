from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def plot_mr_reconstruction(
    df: pd.DataFrame,
    dataset_name: str,
    output_dir: Path,
    *,
    show_splits: bool = True,
    annotate_violations: bool = True,
) -> Path:
    """
    Plot MR_actual vs MR_predicted for a given dataset.
    Optionally mark split boundaries and monotonicity violations.
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    time = df["time_min"].astype(float).to_numpy()
    mr_pred_series = df["mr_predicted"].astype(float)
    mr_pred = mr_pred_series.to_numpy()

    mr_actual: np.ndarray | None = None
    if "mr_actual" in df.columns:
        _actual_series = df["mr_actual"]
        has_actual = _actual_series.notna().any()
        if has_actual:
            mr_actual = _actual_series.astype(float).to_numpy()

    ax.plot(time, mr_pred, label="Predicted MR", linewidth=2)
    if mr_actual is not None:
        ax.plot(time, mr_actual, label="Actual MR", linestyle="--", alpha=0.7)

    if show_splits:
        # Identify drop in time => new segment
        time_diff = np.diff(time)
        split_times = time[1:][time_diff < 0]
        for t in split_times:
            ax.axvline(t, color="gray", linestyle=":", alpha=0.5)

    if annotate_violations:
        mr_diff = np.diff(mr_pred)
        violation_mask = mr_diff > 0
        violation_times = time[1:][violation_mask]
        violation_vals = mr_pred[1:][violation_mask]
        ax.scatter(violation_times, violation_vals, color="red", label="Upward jumps", zorder=3)

    ax.set_title(f"MR Curve – {dataset_name}")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Moisture Ratio")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend()

    output_dir.mkdir(parents=True, exist_ok=True)
    outpath = output_dir / f"{dataset_name}_mr_plot.png"
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    return outpath
