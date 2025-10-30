"""Recursive residual-based Midilli splitter supporting up to two split points."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess

# Ensure project modules are importable when running as a script -----------------
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.fitters_phase1 import FitResult, ModelSpec, _fit_single_model  # noqa: E402
from kinetics.models_phase1 import MODEL_SPECS  # noqa: E402


plt.switch_backend("Agg")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SegmentNode:
    """Representation of a segment in the recursive split tree."""

    t_start: float
    t_end: float
    n_obs: int
    rmse: float
    aicc: float
    params: Dict[str, float]
    split_time: Optional[float] = None
    combined_rmse: Optional[float] = None
    combined_aicc: Optional[float] = None
    children: List["SegmentNode"] = field(default_factory=list)

    def is_leaf(self) -> bool:
        return not self.children

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "t_start": self.t_start,
            "t_end": self.t_end,
            "n_obs": self.n_obs,
            "rmse": self.rmse,
            "aicc": self.aicc,
            "params": self.params,
        }
        if self.split_time is not None:
            payload.update(
                {
                    "t_split": self.split_time,
                    "combined_rmse": self.combined_rmse,
                    "combined_aicc": self.combined_aicc,
                }
            )
        if self.children:
            payload["children"] = [child.to_dict() for child in self.children]
        return payload


@dataclass(frozen=True)
class CandidateEvaluation:
    """Summary of a candidate split evaluation."""

    index: int
    t_split: float
    left_result: FitResult
    right_result: FitResult
    combined_rmse: float
    combined_aicc: float


# ---------------------------------------------------------------------------
# Core recursive algorithm
# ---------------------------------------------------------------------------


def recursive_split_segment(
    spec: ModelSpec,
    time: np.ndarray,
    mr: np.ndarray,
    *,
    depth: int,
    max_depth: int,
    remaining_splits: int,
    min_points: int,
    min_fraction: float,
    max_fraction: float,
    improvement_threshold: float,
    log_prefix: str = "",
) -> Tuple[SegmentNode, int, np.ndarray, np.ndarray]:
    """Recursively split a segment using residual diagnostics.

    Returns a tuple of (segment_node, splits_used, residuals, smoothed_residuals).
    """

    time = np.asarray(time, dtype=float)
    mr = np.asarray(mr, dtype=float)

    fit = _fit_with_spec(spec, time, mr)
    preds = spec.predict(time, fit.params)
    residuals = mr - preds
    smoothed = _smooth_residuals(time, residuals)

    node = SegmentNode(
        t_start=float(time[0]),
        t_end=float(time[-1]),
        n_obs=int(time.size),
        rmse=float(fit.metrics.get("rmse", math.nan)),
        aicc=float(fit.metrics.get("aicc", math.nan)),
        params={name: float(value) for name, value in fit.params.items()},
    )

    if depth >= max_depth or remaining_splits <= 0:
        return node, 0, residuals, smoothed

    candidates = list(
        _generate_candidates(
            spec,
            time,
            mr,
            smoothed,
            min_points=min_points,
            min_fraction=min_fraction,
            max_fraction=max_fraction,
        )
    )

    if not candidates:
        return node, 0, residuals, smoothed

    baseline_rmse = node.rmse
    baseline_aicc = node.aicc

    best_candidate: Optional[CandidateEvaluation] = None
    best_priority: Tuple[float, float] | None = None

    for cand in candidates:
        improvement = _relative_improvement(baseline_rmse, cand.combined_rmse)
        if improvement < improvement_threshold:
            continue
        if not math.isfinite(baseline_aicc) or not math.isfinite(cand.combined_aicc):
            continue
        if cand.combined_aicc >= baseline_aicc:
            continue

        priority = (cand.combined_aicc, cand.combined_rmse)
        if best_priority is None or priority < best_priority:
            best_priority = priority
            best_candidate = cand

    if best_candidate is None:
        return node, 0, residuals, smoothed

    node.split_time = best_candidate.t_split
    node.combined_rmse = best_candidate.combined_rmse
    node.combined_aicc = best_candidate.combined_aicc

    if log_prefix:
        print(
            f"{log_prefix}Split at {best_candidate.t_split:.3f} min "
            f"(ΔRMSE={baseline_rmse - best_candidate.combined_rmse:.5f}, "
            f"ΔAICc={baseline_aicc - best_candidate.combined_aicc:.3f})"
        )
    else:
        print(
            f"Split at {best_candidate.t_split:.3f} min "
            f"(ΔRMSE={baseline_rmse - best_candidate.combined_rmse:.5f}, "
            f"ΔAICc={baseline_aicc - best_candidate.combined_aicc:.3f})"
        )

    splits_used_total = 1
    remaining_after_current = remaining_splits - 1

    left_time = time[: best_candidate.index + 1]
    left_mr = mr[: best_candidate.index + 1]
    right_time = time[best_candidate.index + 1 :]
    right_mr = mr[best_candidate.index + 1 :]

    # Prioritise the branch with higher RMSE for further splitting.
    left_priority = best_candidate.left_result.metrics.get("rmse", float("inf"))
    right_priority = best_candidate.right_result.metrics.get("rmse", float("inf"))

    branches = [
        ("left", left_time, left_mr, left_priority, best_candidate.left_result),
        ("right", right_time, right_mr, right_priority, best_candidate.right_result),
    ]
    branches.sort(key=lambda item: item[3], reverse=True)

    child_nodes: Dict[str, SegmentNode] = {}

    splits_remaining = remaining_after_current

    for name, seg_time, seg_mr, _, _ in branches:
        if splits_remaining <= 0:
            node_child, used, _, _ = recursive_split_segment(
                spec,
                seg_time,
                seg_mr,
                depth=depth + 1,
                max_depth=max_depth,
                remaining_splits=0,
                min_points=min_points,
                min_fraction=min_fraction,
                max_fraction=max_fraction,
                improvement_threshold=improvement_threshold,
                log_prefix=f"{log_prefix}{name}> ",
            )
        else:
            node_child, used, _, _ = recursive_split_segment(
                spec,
                seg_time,
                seg_mr,
                depth=depth + 1,
                max_depth=max_depth,
                remaining_splits=splits_remaining,
                min_points=min_points,
                min_fraction=min_fraction,
                max_fraction=max_fraction,
                improvement_threshold=improvement_threshold,
                log_prefix=f"{log_prefix}{name}> ",
            )
            splits_remaining = max(splits_remaining - used, 0)
            splits_used_total += used
        child_nodes[name] = node_child

    # Maintain left/right ordering in children list.
    node.children = [child_nodes["left"], child_nodes["right"]]

    return node, splits_used_total, residuals, smoothed


def _generate_candidates(
    spec: ModelSpec,
    time: np.ndarray,
    mr: np.ndarray,
    smoothed: np.ndarray,
    *,
    min_points: int,
    min_fraction: float,
    max_fraction: float,
) -> Iterable[CandidateEvaluation]:
    n_obs = time.size
    if n_obs < (2 * min_points):
        return []

    indices = np.arange(n_obs)
    start_idx = max(int(math.floor(n_obs * min_fraction)), min_points)
    end_idx = min(int(math.ceil(n_obs * max_fraction)), n_obs - min_points)

    if start_idx >= end_idx:
        return []

    candidate_indices = _lowess_candidate_indices(
        smoothed,
        start_idx=start_idx,
        end_idx=end_idx,
    )
    if not candidate_indices:
        candidate_indices = list(range(start_idx, end_idx))

    cache: Dict[Tuple[int, int], FitResult] = {}

    for idx in candidate_indices:
        left_mask = indices <= idx
        right_mask = indices > idx
        n_left = int(left_mask.sum())
        n_right = int(right_mask.sum())
        if n_left < min_points or n_right < min_points:
            continue

        left_key = (0, idx + 1)
        right_key = (idx + 1, n_obs)

        if left_key not in cache:
            left_result = _fit_single_model(spec, time[left_mask], mr[left_mask])
            cache[left_key] = left_result
        else:
            left_result = cache[left_key]

        if right_key not in cache:
            right_result = _fit_single_model(spec, time[right_mask], mr[right_mask])
            cache[right_key] = right_result
        else:
            right_result = cache[right_key]

        combined_rmse, combined_aicc = _combine_metrics(left_result, right_result)

        yield CandidateEvaluation(
            index=int(idx),
            t_split=float(time[idx]),
            left_result=left_result,
            right_result=right_result,
            combined_rmse=combined_rmse,
            combined_aicc=combined_aicc,
        )


def _lowess_candidate_indices(
    smoothed: np.ndarray,
    *,
    start_idx: int,
    end_idx: int,
    max_candidates: int = 40,
) -> List[int]:
    if smoothed.size < 3:
        return []

    magnitudes = np.abs(smoothed)
    candidate_set: set[int] = set()

    for idx in range(start_idx, end_idx):
        if idx <= 0 or idx >= smoothed.size - 1:
            continue
        left_mag = magnitudes[idx - 1]
        right_mag = magnitudes[idx + 1]
        center_mag = magnitudes[idx]
        if center_mag >= left_mag and center_mag >= right_mag:
            candidate_set.add(idx)

    if not candidate_set:
        return []

    sorted_candidates = sorted(
        candidate_set,
        key=lambda i: magnitudes[i],
        reverse=True,
    )

    return sorted_candidates[:max_candidates]


def _combine_metrics(left: FitResult, right: FitResult) -> Tuple[float, float]:
    n_left = left.metrics.get("n_obs", 0) or 0
    n_right = right.metrics.get("n_obs", 0) or 0
    if not n_left or not n_right:
        return float("inf"), float("inf")

    sse_left = left.metrics.get("sse", float("inf"))
    sse_right = right.metrics.get("sse", float("inf"))
    if not math.isfinite(sse_left) or not math.isfinite(sse_right):
        return float("inf"), float("inf")

    combined_rmse = math.sqrt((sse_left + sse_right) / (n_left + n_right))

    aicc_left = left.metrics.get("aicc", float("inf"))
    aicc_right = right.metrics.get("aicc", float("inf"))
    combined_aicc = float(aicc_left + aicc_right)

    return combined_rmse, combined_aicc


def _relative_improvement(baseline: float, candidate: float) -> float:
    if not math.isfinite(baseline) or baseline == 0:
        return 0.0
    if not math.isfinite(candidate):
        return 0.0
    return (baseline - candidate) / baseline


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


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
    if time.size == 0:
        return np.array([], dtype=float)
    frac = 0.25 if time.size >= 20 else 0.4
    smoothed = lowess(residuals, time, frac=frac, return_sorted=False)
    return np.asarray(smoothed, dtype=float)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _collect_split_times(node: SegmentNode) -> List[float]:
    splits: List[float] = []
    if node.split_time is not None:
        splits.append(node.split_time)
    for child in node.children:
        splits.extend(_collect_split_times(child))
    return splits


def _collect_leaf_segments(node: SegmentNode) -> List[SegmentNode]:
    if node.is_leaf():
        return [node]
    leaves: List[SegmentNode] = []
    for child in node.children:
        leaves.extend(_collect_leaf_segments(child))
    return leaves


def _plot_dataset_residuals(
    time: np.ndarray,
    residuals: np.ndarray,
    smoothed: np.ndarray,
    split_times: Sequence[float],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(time, residuals, alpha=0.6, label="Residuals", color="#1f77b4")
    ax.plot(time, smoothed, label="LOWESS", color="#ff7f0e", linewidth=2)
    for split in sorted(split_times):
        ax.axvline(split, color="#d62728", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.axhline(0.0, color="black", linewidth=1, alpha=0.3)
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Residual (MR observed - predicted)")
    ax.set_title("Recursive Midilli residual analysis")
    if split_times:
        ax.legend()
    else:
        ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _write_leaf_csv(path: Path, leaves: Sequence[SegmentNode]) -> None:
    import csv

    if not leaves:
        return

    param_names = sorted({name for leaf in leaves for name in leaf.params})

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        header = [
            "segment",
            "t_start",
            "t_end",
            "n_obs",
            "rmse",
            "aicc",
        ] + param_names
        writer.writerow(header)

        for idx, leaf in enumerate(leaves, start=1):
            row = [
                idx,
                f"{leaf.t_start:.6f}",
                f"{leaf.t_end:.6f}",
                leaf.n_obs,
                f"{leaf.rmse:.6f}",
                f"{leaf.aicc:.6f}",
            ]
            for name in param_names:
                value = leaf.params.get(name, float("nan"))
                row.append(f"{value:.8g}" if math.isfinite(value) else "")
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_recursive_split(
    input_path: Path,
    outdir: Path,
    *,
    head_trim_min: float,
    min_fraction: float,
    max_fraction: float,
    min_points: int,
    improvement_threshold: float,
    max_depth: int,
    max_splits: int,
) -> Dict[str, object]:
    preprocess = load_and_preprocess(input_path, head_trim_min=head_trim_min)
    time = preprocess.time_min
    mr = preprocess.mr_iso

    if time.size < max(2 * min_points, 10):
        raise ValueError("Dataset must contain sufficient observations to evaluate splits.")

    spec = _get_midilli_spec()

    root_node, splits_used, residuals, smoothed = recursive_split_segment(
        spec,
        time,
        mr,
        depth=0,
        max_depth=max_depth,
        remaining_splits=max_splits,
        min_points=min_points,
        min_fraction=min_fraction,
        max_fraction=max_fraction,
        improvement_threshold=improvement_threshold,
    )

    dataset_outdir = outdir / input_path.stem
    dataset_outdir.mkdir(parents=True, exist_ok=True)

    split_times = _collect_split_times(root_node)
    _plot_dataset_residuals(
        time,
        residuals,
        smoothed,
        split_times,
        dataset_outdir / "residuals_recursive.png",
    )

    leaves = _collect_leaf_segments(root_node)
    _write_leaf_csv(dataset_outdir / "segments.csv", leaves)

    summary = {
        "input": str(input_path),
        "head_trim_min": head_trim_min,
        "max_depth": max_depth,
        "max_splits": max_splits,
        "splits_used": splits_used,
        "tree": root_node.to_dict(),
    }

    summary_path = dataset_outdir / "recursive_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recursive residual analysis for Midilli model with up to two splits.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing CSV datasets to analyse.",
    )
    parser.add_argument(
        "--outdir",
        default="outputs/recursive_split",
        help="Output directory for diagnostics.",
    )
    parser.add_argument(
        "--head_trim_min",
        type=float,
        default=0.0,
        help="Trim early minutes before fitting (consistent with preprocessing).",
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
    parser.add_argument(
        "--improvement_threshold",
        type=float,
        default=0.05,
        help="Relative RMSE improvement required to accept a split (e.g. 0.05 = 5%%).",
    )
    parser.add_argument(
        "--max_depth",
        type=int,
        default=2,
        help="Maximum recursion depth for splitting (root depth is 0).",
    )
    parser.add_argument(
        "--max_splits",
        type=int,
        default=2,
        help="Maximum number of split points permitted across the dataset.",
    )

    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    csv_paths = sorted(p for p in data_dir.glob("*.csv") if p.is_file())
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    summaries = []
    for path in csv_paths:
        print(f"Processing {path.name}...")
        summary = run_recursive_split(
            path,
            outdir,
            head_trim_min=args.head_trim_min,
            min_fraction=args.min_fraction,
            max_fraction=args.max_fraction,
            min_points=args.min_points,
            improvement_threshold=args.improvement_threshold,
            max_depth=args.max_depth,
            max_splits=args.max_splits,
        )
        summaries.append(summary)

    index_path = outdir / "summary_index.json"
    index_payload = {
        "data_dir": str(data_dir),
        "head_trim_min": args.head_trim_min,
        "datasets": summaries,
    }
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
