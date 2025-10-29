"""Residual analysis tool to detect split points for piecewise Midilli modelling."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess

# Bootstrap sys.path for interactive usage -----------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.fitters_phase1 import (  # noqa: E402
    FitResult,
    ModelSpec,
    _fit_single_model,
)
from kinetics.models_phase1 import MODEL_SPECS  # noqa: E402

plt.switch_backend("Agg")


@dataclass
class SplitEvaluation:
    """Container summarising metrics for a candidate split."""

    t_split: float
    rmse_left: float
    rmse_right: float
    combined_rmse: float
    n_left: int
    n_right: int


def run_piecewise_split(
    input_path: str | Path,
    outdir: str | Path = "outputs/time_split",
    head_trim_min: float = 0.0,
    min_fraction: float = 0.15,
    max_fraction: float = 0.85,
    min_points: int = 6,
) -> Dict[str, object]:
    """Fit Midilli residuals and identify an optimal time split."""

    input_path = Path(input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    outdir = Path(outdir)
    dataset_outdir = outdir / input_path.stem
    plots_dir = dataset_outdir
    plots_dir.mkdir(parents=True, exist_ok=True)

    preprocess = load_and_preprocess(input_path, head_trim_min=head_trim_min)
    time = preprocess.time_min
    mr = preprocess.mr_iso

    if time.size < max(2 * min_points, 10):
        raise ValueError(
            "Dataset must contain sufficient observations to evaluate splits."
        )

    midilli_spec = _get_midilli_spec()
    full_result = _fit_with_spec(midilli_spec, time, mr)
    predictions = midilli_spec.predict(time, full_result.params)
    residuals = mr - predictions

    smoothed = _smooth_residuals(time, residuals)

    evaluations = list(
        _evaluate_candidates(
            midilli_spec,
            time,
            mr,
            min_fraction=min_fraction,
            max_fraction=max_fraction,
            min_points=min_points,
        )
    )

    if not evaluations:
        raise ValueError("No valid split candidates found. Adjust parameters or dataset.")

    best_eval = min(evaluations, key=lambda item: item.combined_rmse)

    _plot_residuals(
        time,
        residuals,
        smoothed,
        best_eval.t_split,
        plots_dir / "residuals_plot.png",
    )

    summary = {
        "input": str(input_path),
        "t_split": best_eval.t_split,
        "rmse_single": float(full_result.metrics.get("rmse", math.nan)),
        "rmse_left": best_eval.rmse_left,
        "rmse_right": best_eval.rmse_right,
        "rmse_combined": best_eval.combined_rmse,
        "n_left": best_eval.n_left,
        "n_right": best_eval.n_right,
        "head_trim_min": head_trim_min,
    }

    summary_path = dataset_outdir / "split_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    _write_candidates_csv(dataset_outdir / "candidate_splits.csv", evaluations)

    print(
        f"Best split for {input_path.name}: t_split={best_eval.t_split:.3f} min "
        f"(combined RMSE={best_eval.combined_rmse:.5f})"
    )

    return summary


def _get_midilli_spec() -> ModelSpec:
    for spec in MODEL_SPECS:
        if spec.name == "midilli":
            return spec
    raise RuntimeError("Midilli model specification not found.")


def _fit_with_spec(spec: ModelSpec, time: np.ndarray, mr: np.ndarray) -> FitResult:
    time = np.asarray(time, dtype=float)
    mr = np.asarray(mr, dtype=float)
    result = _fit_single_model(spec, time, mr)
    if not isinstance(result, FitResult):
        raise RuntimeError("Midilli fitting did not return a FitResult.")
    return result


def _smooth_residuals(time: np.ndarray, residuals: np.ndarray) -> np.ndarray:
    frac = 0.25 if time.size >= 20 else 0.4
    smoothed = lowess(residuals, time, frac=frac, return_sorted=False)
    return np.asarray(smoothed, dtype=float)


def _evaluate_candidates(
    spec: ModelSpec,
    time: np.ndarray,
    mr: np.ndarray,
    *,
    min_fraction: float,
    max_fraction: float,
    min_points: int,
) -> Iterable[SplitEvaluation]:
    n_obs = time.size
    indices = np.arange(n_obs)

    start_idx = max(int(math.floor(n_obs * min_fraction)), min_points)
    end_idx = min(int(math.ceil(n_obs * max_fraction)), n_obs - min_points)

    if start_idx >= end_idx:
        return

    candidate_indices = np.arange(start_idx, end_idx, dtype=int)
    if candidate_indices.size > 60:
        candidate_indices = np.unique(
            np.linspace(start_idx, end_idx - 1, num=60, dtype=int)
        )

    best_cache: Dict[Tuple[int, int], FitResult] = {}

    for idx in candidate_indices:
        left_mask = indices <= idx
        right_mask = indices > idx
        n_left = int(left_mask.sum())
        n_right = int(right_mask.sum())
        if n_left < min_points or n_right < min_points:
            continue

        time_left = np.asarray(time[left_mask], dtype=float)
        mr_left = np.asarray(mr[left_mask], dtype=float)
        time_right = np.asarray(time[right_mask], dtype=float)
        mr_right = np.asarray(mr[right_mask], dtype=float)

        left_key = (0, idx + 1)
        right_key = (idx + 1, n_obs)

        if left_key not in best_cache:
            left_result = _fit_single_model(spec, time_left, mr_left)
            best_cache[left_key] = left_result
        else:
            left_result = best_cache[left_key]

        if right_key not in best_cache:
            right_result = _fit_single_model(spec, time_right, mr_right)
            best_cache[right_key] = right_result
        else:
            right_result = best_cache[right_key]

        preds_left = spec.predict(time_left, left_result.params)
        preds_right = spec.predict(time_right, right_result.params)

        residual_left = mr_left - preds_left
        residual_right = mr_right - preds_right

        rmse_left = float(np.sqrt(np.mean(residual_left**2)))
        rmse_right = float(np.sqrt(np.mean(residual_right**2)))

        combined_rmse = float(
            np.sqrt(
                (
                    float(np.sum(residual_left**2))
                    + float(np.sum(residual_right**2))
                )
                / (n_left + n_right)
            )
        )

        t_split = float(time[idx])
        yield SplitEvaluation(
            t_split=t_split,
            rmse_left=rmse_left,
            rmse_right=rmse_right,
            combined_rmse=combined_rmse,
            n_left=n_left,
            n_right=n_right,
        )


def _plot_residuals(
    time: np.ndarray,
    residuals: np.ndarray,
    smoothed: np.ndarray,
    t_split: float,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(time, residuals, label="Residuals", alpha=0.6, color="#1f77b4")
    ax.plot(time, smoothed, label="LOWESS", color="#ff7f0e", linewidth=2)
    ax.axvline(t_split, color="#d62728", linestyle="--", label="Best split")
    ax.axhline(0.0, color="black", linewidth=1, alpha=0.3)
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Residual (MR observed - predicted)")
    ax.set_title("Midilli residuals and suggested split")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _write_candidates_csv(path: Path, evaluations: Sequence[SplitEvaluation]) -> None:
    import csv

    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "t_split",
                "rmse_left",
                "rmse_right",
                "rmse_combined",
                "n_left",
                "n_right",
            ]
        )
        for item in evaluations:
            writer.writerow(
                [
                    f"{item.t_split:.6f}",
                    f"{item.rmse_left:.6f}",
                    f"{item.rmse_right:.6f}",
                    f"{item.combined_rmse:.6f}",
                    item.n_left,
                    item.n_right,
                ]
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect residual-based split point for piecewise Midilli fitting.",
    )
    parser.add_argument("--input", required=True, help="Path to the input dataset.")
    parser.add_argument(
        "--outdir",
        default="outputs/time_split",
        help="Base directory for split diagnostics.",
    )
    parser.add_argument(
        "--head_trim_min",
        type=float,
        default=0.0,
        help="Trim early minutes before fitting (consistent with phase-1 pipeline).",
    )
    parser.add_argument(
        "--min_fraction",
        type=float,
        default=0.15,
        help="Minimum fractional index (0-1) eligible for split consideration.",
    )
    parser.add_argument(
        "--max_fraction",
        type=float,
        default=0.85,
        help="Maximum fractional index (0-1) eligible for split consideration.",
    )
    parser.add_argument(
        "--min_points",
        type=int,
        default=6,
        help="Minimum observations per segment when evaluating splits.",
    )

    args = parser.parse_args(argv)

    run_piecewise_split(
        input_path=args.input,
        outdir=args.outdir,
        head_trim_min=args.head_trim_min,
        min_fraction=args.min_fraction,
        max_fraction=args.max_fraction,
        min_points=args.min_points,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
