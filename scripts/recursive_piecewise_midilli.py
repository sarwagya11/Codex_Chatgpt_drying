"""Recursive residual-based Midilli splitter supporting up to two split points."""

from __future__ import annotations

import argparse
import json
import logging
import math
from contextlib import contextmanager
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
import kinetics.fitters_phase1 as fitters_phase1  # noqa: E402
from kinetics.fitters_phase1 import FitResult, ModelSpec, _fit_single_model  # noqa: E402
from kinetics.models_phase1 import MODEL_SPECS  # noqa: E402


plt.switch_backend("Agg")


logger = logging.getLogger(__name__)


@contextmanager
def _temporary_max_iter(max_iter: int):
    original = fitters_phase1.least_squares

    def _patched_least_squares(*args, **kwargs):
        if max_iter is not None and max_iter > 0:
            candidate = kwargs.get("max_nfev")
            if candidate is None:
                kwargs["max_nfev"] = max_iter
            else:
                kwargs["max_nfev"] = min(int(candidate), max_iter)
        return original(*args, **kwargs)

    fitters_phase1.least_squares = _patched_least_squares  # type: ignore[assignment]
    try:
        yield
    finally:
        fitters_phase1.least_squares = original  # type: ignore[assignment]


def _safe_float(value: Optional[float | int | np.floating]) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


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
    model_type: str
    baseline_aicc: Optional[float] = None
    split_time: Optional[float] = None
    combined_rmse: Optional[float] = None
    combined_aicc: Optional[float] = None
    penalized_score: Optional[float] = None
    join_gap: Optional[float] = None
    delta_rmse: Optional[float] = None
    delta_aicc: Optional[float] = None
    residual_r2: Optional[float] = None
    index_start: Optional[int] = None
    index_end: Optional[int] = None
    candidate_metrics: List[Dict[str, float]] = field(default_factory=list)
    children: List["SegmentNode"] = field(default_factory=list)

    def is_leaf(self) -> bool:
        return not self.children

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "t_start": self.t_start,
            "t_end": self.t_end,
            "n_obs": self.n_obs,
            "rmse": _safe_float(self.rmse),
            "aicc": _safe_float(self.aicc),
            "model_type": self.model_type,
        }
        payload["params"] = {
            key: _safe_float(value) if isinstance(value, (int, float)) else value
            for key, value in self.params.items()
        }
        baseline = _safe_float(self.baseline_aicc)
        if baseline is not None:
            payload["baseline_aicc"] = baseline
        residual_r2 = _safe_float(self.residual_r2)
        if residual_r2 is not None:
            payload["residual_r2"] = residual_r2
        if self.index_start is not None:
            payload["index_start"] = self.index_start
        if self.index_end is not None:
            payload["index_end"] = self.index_end
        if self.split_time is not None:
            payload.update(
                {
                    "t_split": self.split_time,
                    "combined_rmse": _safe_float(self.combined_rmse),
                    "combined_aicc": _safe_float(self.combined_aicc),
                    "penalized_score": _safe_float(self.penalized_score),
                    "join_gap": _safe_float(self.join_gap),
                    "delta_rmse": _safe_float(self.delta_rmse),
                    "delta_aicc": _safe_float(self.delta_aicc),
                }
            )
        if self.children:
            payload["children"] = [child.to_dict() for child in self.children]
        if self.candidate_metrics:
            cleaned: List[Dict[str, object]] = []
            for entry in self.candidate_metrics:
                cleaned_entry = {
                    key: (_safe_float(value) if isinstance(value, float) else value)
                    for key, value in entry.items()
                }
                cleaned.append(cleaned_entry)
            payload["candidates"] = cleaned
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
    join_gap: float
    penalized_score: float


@dataclass(frozen=True)
class SplitConfig:
    max_depth: int
    join_penalty: float
    max_allowed_gap: float
    candidate_grid_count: int
    probe_better_child: bool
    min_fraction: float
    max_fraction: float
    min_points_root: int
    min_points_leaf: int
    improvement_threshold: float
    lowess_frac_min: float
    lowess_frac_max: float
    max_iter: int


# ---------------------------------------------------------------------------
# Core recursive algorithm
# ---------------------------------------------------------------------------


def recursive_split_segment(
    spec: ModelSpec,
    time: np.ndarray,
    mr: np.ndarray,
    indices: np.ndarray,
    *,
    depth: int,
    remaining_splits: int,
    config: SplitConfig,
    log_prefix: str = "",
) -> Tuple[SegmentNode, int, np.ndarray, np.ndarray]:
    """Recursively split a segment using residual diagnostics.

    Returns a tuple of (segment_node, splits_used, residuals, smoothed_residuals).
    """

    time = np.asarray(time, dtype=float)
    mr = np.asarray(mr, dtype=float)

    try:
        fit = _fit_with_spec(spec, time, mr, max_iter=config.max_iter)
    except Exception as exc:
        raise RuntimeError(f"Failed to fit segment at depth {depth}: {exc}") from exc
    preds = spec.predict(time, fit.params)
    residuals = mr - preds
    smoothed = _smooth_residuals(
        time,
        residuals,
        lowess_frac_min=config.lowess_frac_min,
        lowess_frac_max=config.lowess_frac_max,
    )

    residual_r2 = _residual_r2(residuals, smoothed)

    min_points = _min_points_for_depth(
        depth,
        root_min=config.min_points_root,
        leaf_min=config.min_points_leaf,
    )

    rmse_val = _safe_float(fit.metrics.get("rmse"))
    aicc_val = _safe_float(fit.metrics.get("aicc"))
    if rmse_val is None or aicc_val is None:
        raise RuntimeError("Fit did not provide finite RMSE/AICc metrics")

    params: Dict[str, float] = {}
    for name, value in fit.params.items():
        numeric = _safe_float(
            value if isinstance(value, (int, float, np.floating)) else None
        )
        if numeric is None:
            raise RuntimeError("Fit returned non-finite parameter value")
        params[name] = float(numeric)

    node = SegmentNode(
        t_start=float(time[0]),
        t_end=float(time[-1]),
        n_obs=int(time.size),
        rmse=rmse_val,
        aicc=aicc_val,
        params=params,
        model_type=spec.name,
        baseline_aicc=aicc_val,
        residual_r2=residual_r2,
        index_start=int(indices[0]) if indices.size else None,
        index_end=int(indices[-1]) if indices.size else None,
    )

    if depth >= config.max_depth or remaining_splits <= 0:
        return node, 0, residuals, smoothed

    candidates = list(
        _generate_candidates(
            spec,
            time,
            mr,
            smoothed,
            min_points=min_points,
            min_fraction=config.min_fraction,
            max_fraction=config.max_fraction,
            candidate_grid_count=config.candidate_grid_count,
            max_iter=config.max_iter,
            join_penalty=config.join_penalty,
            max_allowed_gap=config.max_allowed_gap,
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
        delta_rmse = baseline_rmse - cand.combined_rmse
        delta_aicc = baseline_aicc - cand.combined_aicc
        candidate_payload: Dict[str, float] = {
            "t_split": float(cand.t_split),
            "delta_rmse": float(delta_rmse),
            "delta_aicc": float(delta_aicc),
            "rel_improvement": float(improvement),
            "join_gap": float(cand.join_gap),
            "penalized_score": float(cand.penalized_score),
            "combined_rmse": float(cand.combined_rmse),
            "combined_aicc": float(cand.combined_aicc),
        }
        node.candidate_metrics.append(candidate_payload)
        logger.debug(
            "%sCAND t=%.3f | ΔRMSE=%.4f ΔAICc=%.2f gap=%.4f score=%.2f",
            log_prefix,
            cand.t_split,
            delta_rmse,
            delta_aicc,
            cand.join_gap,
            cand.penalized_score,
        )

        if improvement < config.improvement_threshold:
            continue
        if not math.isfinite(baseline_aicc) or not math.isfinite(cand.penalized_score):
            continue
        if cand.combined_aicc >= baseline_aicc:
            continue

        priority = (cand.penalized_score, cand.combined_rmse)
        if best_priority is None or priority < best_priority:
            best_priority = priority
            best_candidate = cand

    if best_candidate is None:
        return node, 0, residuals, smoothed

    node.split_time = best_candidate.t_split
    node.combined_rmse = best_candidate.combined_rmse
    node.combined_aicc = best_candidate.combined_aicc
    node.penalized_score = best_candidate.penalized_score
    node.join_gap = best_candidate.join_gap
    node.delta_rmse = baseline_rmse - best_candidate.combined_rmse
    node.delta_aicc = baseline_aicc - best_candidate.combined_aicc

    if node.delta_aicc is not None and node.delta_aicc < -1e-9:
        raise AssertionError("Combined AICc must improve after split")
    if node.join_gap is not None and node.join_gap > config.max_allowed_gap + 1e-12:
        raise AssertionError("Accepted split exceeds max allowed join gap")
    if node.delta_rmse is not None:
        rel_improvement = _relative_improvement(baseline_rmse, best_candidate.combined_rmse)
        if rel_improvement < config.improvement_threshold - 1e-12:
            raise AssertionError("Accepted split fails minimum relative improvement")

    logger.info(
        "%sACCEPT split@t=%.3f | ΔRMSE=%.4f ΔAICc=%.2f gap=%.4f score=%.2f",
        log_prefix,
        best_candidate.t_split,
        node.delta_rmse if node.delta_rmse is not None else float("nan"),
        node.delta_aicc if node.delta_aicc is not None else float("nan"),
        node.join_gap if node.join_gap is not None else float("nan"),
        node.penalized_score if node.penalized_score is not None else float("nan"),
    )

    if log_prefix:
        logger.debug(
            "%sSplit accepted at %.3f", log_prefix, best_candidate.t_split
        )

    splits_used_total = 1
    remaining_after_current = remaining_splits - 1

    left_time = time[: best_candidate.index + 1]
    left_mr = mr[: best_candidate.index + 1]
    left_indices = indices[: best_candidate.index + 1]
    right_time = time[best_candidate.index + 1 :]
    right_mr = mr[best_candidate.index + 1 :]
    right_indices = indices[best_candidate.index + 1 :]

    # Prioritise the branch with higher RMSE for further splitting.
    left_priority = best_candidate.left_result.metrics.get("rmse", float("inf"))
    right_priority = best_candidate.right_result.metrics.get("rmse", float("inf"))

    branches = [
        (
            "left",
            left_time,
            left_mr,
            left_indices,
            left_priority,
            best_candidate.left_result,
        ),
        (
            "right",
            right_time,
            right_mr,
            right_indices,
            right_priority,
            best_candidate.right_result,
        ),
    ]
    branches.sort(key=lambda item: item[4], reverse=True)

    child_nodes: Dict[str, SegmentNode] = {}

    splits_remaining = remaining_after_current

    for idx, (name, seg_time, seg_mr, seg_indices, _, _) in enumerate(branches):
        if idx == 0:
            allowed = splits_remaining
        else:
            if not config.probe_better_child or splits_remaining <= 0:
                allowed = 0
            else:
                allowed = min(1, splits_remaining)

        node_child, used, _, _ = recursive_split_segment(
            spec,
            seg_time,
            seg_mr,
            seg_indices,
            depth=depth + 1,
            remaining_splits=allowed,
            config=config,
            log_prefix=f"{log_prefix}{name}> ",
        )
        splits_used_total += used
        splits_remaining = max(splits_remaining - used, 0)
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
    candidate_grid_count: int,
    max_iter: int,
    join_penalty: float,
    max_allowed_gap: float,
) -> Iterable[CandidateEvaluation]:
    n_obs = time.size
    if n_obs < (2 * min_points):
        return []

    index_array = np.arange(n_obs)
    start_idx = max(int(math.floor(n_obs * min_fraction)), min_points)
    end_idx = min(int(math.ceil(n_obs * max_fraction)), n_obs - min_points)

    if start_idx >= end_idx:
        return []

    lowess_candidates = _lowess_candidate_indices(
        smoothed,
        start_idx=start_idx,
        end_idx=end_idx,
    )

    grid_candidates: List[int] = []
    if candidate_grid_count > 0 and end_idx > start_idx:
        grid_candidates = np.linspace(
            start_idx,
            end_idx - 1,
            num=min(candidate_grid_count, max(end_idx - start_idx, 1)),
            dtype=int,
        ).tolist()

    candidate_indices = sorted(set(lowess_candidates + grid_candidates))
    if not candidate_indices:
        candidate_indices = list(range(start_idx, end_idx))

    cache: Dict[Tuple[int, int], FitResult] = {}

    for idx in candidate_indices:
        left_mask = index_array <= idx
        right_mask = index_array > idx
        n_left = int(left_mask.sum())
        n_right = int(right_mask.sum())
        if n_left < min_points or n_right < min_points:
            continue

        left_key = (0, idx + 1)
        right_key = (idx + 1, n_obs)

        if left_key not in cache:
            try:
                left_result = _fit_with_spec(
                    spec, time[left_mask], mr[left_mask], max_iter=max_iter
                )
            except Exception as exc:
                logger.debug("Skipping candidate at %s due to left fit failure: %s", idx, exc)
                continue
            cache[left_key] = left_result
        else:
            left_result = cache[left_key]

        if right_key not in cache:
            try:
                right_result = _fit_with_spec(
                    spec, time[right_mask], mr[right_mask], max_iter=max_iter
                )
            except Exception as exc:
                logger.debug("Skipping candidate at %s due to right fit failure: %s", idx, exc)
                continue
            cache[right_key] = right_result
        else:
            right_result = cache[right_key]

        combined_rmse, combined_aicc = _combine_metrics(left_result, right_result)

        if not math.isfinite(combined_rmse) or not math.isfinite(combined_aicc):
            continue

        y_left = spec.predict(np.array([time[idx]]), left_result.params)[0]
        y_right = spec.predict(np.array([time[idx + 1]]), right_result.params)[0]
        gap = float(abs(y_left - y_right))
        if gap > max_allowed_gap:
            continue

        penalized_score = float(combined_aicc + join_penalty * (gap**2))

        yield CandidateEvaluation(
            index=int(idx),
            t_split=float(time[idx]),
            left_result=left_result,
            right_result=right_result,
            combined_rmse=combined_rmse,
            combined_aicc=combined_aicc,
            join_gap=gap,
            penalized_score=penalized_score,
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
    return _get_spec_by_name("midilli")


def _get_spec_by_name(name: str) -> ModelSpec:
    for spec in MODEL_SPECS:
        if spec.name == name:
            return spec
    raise RuntimeError(f"Model specification not found: {name}")


def _fit_with_spec(
    spec: ModelSpec, time: np.ndarray, mr: np.ndarray, *, max_iter: int
) -> FitResult:
    time = np.asarray(time, dtype=float)
    mr = np.asarray(mr, dtype=float)
    with _temporary_max_iter(max_iter):
        result = _fit_single_model(spec, time, mr)
    if not isinstance(result, FitResult):
        raise RuntimeError("Model fitting did not return a FitResult.")
    if not result.success:
        raise RuntimeError(result.message)

    metrics = result.metrics or {}
    rmse = _safe_float(metrics.get("rmse"))
    aicc = _safe_float(metrics.get("aicc"))
    if rmse is None or aicc is None:
        raise RuntimeError("Invalid metrics (rmse/aicc) from fit")

    for warning in result.warnings:
        if warning.endswith("_at_lower_bound") or warning.endswith("_at_upper_bound"):
            raise RuntimeError(f"Fit saturated parameter bounds: {warning}")

    for value in result.params.values():
        numeric = _safe_float(
            value if isinstance(value, (int, float, np.floating)) else None
        )
        if numeric is None:
            raise RuntimeError("Fit returned non-finite parameter value")

    return result


def _smooth_residuals(
    time: np.ndarray,
    residuals: np.ndarray,
    *,
    lowess_frac_min: float,
    lowess_frac_max: float,
) -> np.ndarray:
    if time.size == 0:
        return np.array([], dtype=float)
    frac = float(np.clip(10.0 / max(time.size, 1), lowess_frac_min, lowess_frac_max))
    smoothed = lowess(residuals, time, frac=frac, return_sorted=False)
    return np.asarray(smoothed, dtype=float)


def _residual_r2(residuals: np.ndarray, smoothed: np.ndarray) -> float:
    if residuals.size == 0:
        return float("nan")
    residuals = np.asarray(residuals, dtype=float)
    smoothed = np.asarray(smoothed, dtype=float)
    if residuals.size <= 1:
        return float("nan")
    total_var = float(np.var(residuals, ddof=1))
    if total_var <= 0:
        return float("nan")
    error_var = float(np.var(residuals - smoothed, ddof=1))
    return float(1.0 - (error_var / total_var))


def _min_points_for_depth(depth: int, *, root_min: int, leaf_min: int) -> int:
    if depth <= 0:
        return max(root_min, leaf_min)
    return max(leaf_min, root_min + 2 * depth)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _collect_split_details(node: SegmentNode) -> List[Dict[str, float]]:
    details: List[Dict[str, float]] = []
    if node.split_time is not None:
        detail: Dict[str, float] = {"t_split": float(node.split_time)}
        if node.delta_aicc is not None:
            detail["delta_aicc"] = float(node.delta_aicc)
        if node.delta_rmse is not None:
            detail["delta_rmse"] = float(node.delta_rmse)
        if node.join_gap is not None:
            detail["join_gap"] = float(node.join_gap)
        if node.penalized_score is not None:
            detail["penalized_score"] = float(node.penalized_score)
        details.append(detail)
    for child in node.children:
        details.extend(_collect_split_details(child))
    return details


def _collect_split_times(node: SegmentNode) -> List[float]:
    return [detail["t_split"] for detail in _collect_split_details(node)]


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
    split_details: Sequence[Dict[str, float]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(time, residuals, alpha=0.6, label="Residuals", color="#1f77b4")
    ax.plot(time, smoothed, label="LOWESS", color="#ff7f0e", linewidth=2)
    y_min, y_max = ax.get_ylim()
    span = y_max - y_min if y_max > y_min else 1.0
    for detail in sorted(split_details, key=lambda d: d["t_split"]):
        split = detail["t_split"]
        ax.axvline(split, color="#d62728", linestyle="--", linewidth=1.5, alpha=0.8)
        delta_aicc = detail.get("delta_aicc")
        join_gap = detail.get("join_gap")
        delta_aicc_str = (
            f"{delta_aicc:.2f}" if isinstance(delta_aicc, (int, float)) and math.isfinite(delta_aicc) else "nan"
        )
        gap_str = (
            f"{join_gap:.4f}" if isinstance(join_gap, (int, float)) and math.isfinite(join_gap) else "nan"
        )
        label = (
            f"ΔAICc={delta_aicc_str}\n"
            f"gap={gap_str}"
        )
        ax.text(
            split,
            y_max - 0.05 * span,
            label,
            rotation=90,
            va="top",
            ha="center",
            fontsize=8,
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
        )
    ax.axhline(0.0, color="black", linewidth=1, alpha=0.3)
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Residual (MR observed - predicted)")
    ax.set_title("Recursive residual analysis")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _plot_dataset_fit(
    time: np.ndarray,
    mr: np.ndarray,
    predictions: np.ndarray,
    split_details: Sequence[Dict[str, float]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(time, mr, "o", label="Observed MR", alpha=0.7)
    ax.plot(time, predictions, "-", label="Piecewise fit", linewidth=2)
    y_min, y_max = ax.get_ylim()
    span = y_max - y_min if y_max > y_min else 1.0
    for detail in sorted(split_details, key=lambda d: d["t_split"]):
        split = detail["t_split"]
        ax.axvline(split, color="#d62728", linestyle="--", linewidth=1.2, alpha=0.8)
        delta_aicc = detail.get("delta_aicc")
        join_gap = detail.get("join_gap")
        delta_aicc_str = (
            f"{delta_aicc:.2f}" if isinstance(delta_aicc, (int, float)) and math.isfinite(delta_aicc) else "nan"
        )
        gap_str = (
            f"{join_gap:.4f}" if isinstance(join_gap, (int, float)) and math.isfinite(join_gap) else "nan"
        )
        ax.text(
            split,
            y_max - 0.05 * span,
            f"ΔAICc={delta_aicc_str}\n"
            f"gap={gap_str}",
            rotation=90,
            va="top",
            ha="center",
            fontsize=8,
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
        )
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Moisture ratio (MR)")
    ax.set_title("Observed vs. piecewise model predictions")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _piecewise_predictions(time: np.ndarray, root: SegmentNode) -> np.ndarray:
    predictions = np.full_like(time, fill_value=np.nan, dtype=float)
    leaves = sorted(
        _collect_leaf_segments(root),
        key=lambda node: node.index_start if node.index_start is not None else -1,
    )
    for leaf in leaves:
        if leaf.index_start is None or leaf.index_end is None:
            continue
        start = int(leaf.index_start)
        end = int(leaf.index_end) + 1
        if start < 0 or end > time.size:
            continue
        spec = _get_spec_by_name(leaf.model_type)
        segment_time = time[start:end]
        predictions[start:end] = spec.predict(segment_time, leaf.params)
    return predictions


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
    min_points_root: int,
    min_points_leaf: int,
    min_rel_improvement: float,
    max_depth: int,
    max_splits: int,
    join_penalty: float,
    max_allowed_gap: float,
    candidate_grid_count: int,
    probe_better_child: bool,
    lowess_frac_min: float,
    lowess_frac_max: float,
    try_page_at_root: bool,
    max_iter: int,
) -> Dict[str, object]:
    preprocess = load_and_preprocess(input_path, head_trim_min=head_trim_min)
    time = preprocess.time_min
    mr = preprocess.mr_iso

    if time.size < max(2 * min_points_root, 10):
        raise ValueError("Dataset must contain sufficient observations to evaluate splits.")

    available_specs = [_get_midilli_spec()]
    if try_page_at_root:
        try:
            available_specs.append(_get_spec_by_name("page"))
        except RuntimeError:
            logger.warning("Page model specification not found; using Midilli only")

    root_scores: Dict[str, float] = {}
    best_spec: Optional[ModelSpec] = None
    best_score = float("inf")
    for candidate_spec in available_specs:
        try:
            fit = _fit_with_spec(candidate_spec, time, mr, max_iter=max_iter)
        except Exception as exc:
            logger.debug(
                "Skipping root spec %s due to fit failure: %s", candidate_spec.name, exc
            )
            continue
        aicc = float(fit.metrics.get("aicc", float("inf")))
        root_scores[candidate_spec.name] = aicc
        if math.isfinite(aicc) and aicc < best_score:
            best_score = aicc
            best_spec = candidate_spec

    if best_spec is None:
        raise RuntimeError("Unable to obtain a valid root model fit.")

    if try_page_at_root and root_scores:
        best_name = min(root_scores.items(), key=lambda item: item[1])[0]
        if best_name != best_spec.name:
            raise AssertionError("Root model selection failed to choose best AICc")

    config = SplitConfig(
        max_depth=max_depth,
        join_penalty=join_penalty,
        max_allowed_gap=max_allowed_gap,
        candidate_grid_count=candidate_grid_count,
        probe_better_child=probe_better_child,
        min_fraction=min_fraction,
        max_fraction=max_fraction,
        min_points_root=min_points_root,
        min_points_leaf=min_points_leaf,
        improvement_threshold=min_rel_improvement,
        lowess_frac_min=lowess_frac_min,
        lowess_frac_max=lowess_frac_max,
        max_iter=max_iter,
    )

    indices = np.arange(time.size)

    root_node, splits_used, residuals, smoothed = recursive_split_segment(
        best_spec,
        time,
        mr,
        indices,
        depth=0,
        remaining_splits=max_splits,
        config=config,
    )

    dataset_outdir = outdir / input_path.stem
    dataset_outdir.mkdir(parents=True, exist_ok=True)

    split_details = _collect_split_details(root_node)
    _plot_dataset_residuals(
        time,
        residuals,
        smoothed,
        split_details,
        dataset_outdir / "residuals_recursive.png",
    )

    predictions = _piecewise_predictions(time, root_node)
    _plot_dataset_fit(
        time,
        mr,
        predictions,
        split_details,
        dataset_outdir / "mr_vs_pred.png",
    )

    leaves = _collect_leaf_segments(root_node)
    for leaf in leaves:
        if leaf.n_obs < min_points_leaf:
            raise AssertionError("Leaf segment shorter than min_points_leaf")

    total_join_gap = sum(
        float(detail["join_gap"])
        for detail in split_details
        if isinstance(detail.get("join_gap"), (int, float))
        and math.isfinite(detail["join_gap"])
    )
    gap_limit = 0.05 * max(len(leaves), 1)
    if total_join_gap > gap_limit + 1e-12:
        raise AssertionError("Total join gap exceeds allowed budget for dataset")

    _write_leaf_csv(dataset_outdir / "segments.csv", leaves)

    summary = {
        "input": str(input_path),
        "head_trim_min": head_trim_min,
        "max_depth": max_depth,
        "max_splits": max_splits,
        "splits_used": splits_used,
        "join_penalty": join_penalty,
        "max_allowed_gap": max_allowed_gap,
        "candidate_grid_count": candidate_grid_count,
        "probe_better_child": probe_better_child,
        "lowess_frac_min": lowess_frac_min,
        "lowess_frac_max": lowess_frac_max,
        "min_points_root": min_points_root,
        "min_points_leaf": min_points_leaf,
        "min_rel_improvement": min_rel_improvement,
        "max_iter": max_iter,
        "root_model": best_spec.name,
        "root_model_scores": root_scores,
        "total_join_gap": total_join_gap,
        "join_gap_limit": gap_limit,
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
        "--min-points-root",
        dest="min_points_root",
        type=int,
        default=16,
        help="Minimum observations required at the root segment.",
    )
    parser.add_argument(
        "--min-points-leaf",
        dest="min_points_leaf",
        type=int,
        default=12,
        help="Minimum observations permitted for any leaf segment.",
    )
    parser.add_argument(
        "--min-rel-improvement",
        dest="min_rel_improvement",
        type=float,
        default=0.05,
        help="Relative RMSE improvement required to accept a split (e.g. 0.05 = 5%%).",
    )
    parser.add_argument(
        "--improvement_threshold",
        type=float,
        help=argparse.SUPPRESS,
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
    parser.add_argument(
        "--join-penalty",
        type=float,
        default=50.0,
        help="Penalty multiplier applied to squared join gaps when ranking splits.",
    )
    parser.add_argument(
        "--max-allowed-gap",
        dest="max_allowed_gap",
        type=float,
        default=0.03,
        help="Maximum permitted MR discontinuity at split joins.",
    )
    parser.add_argument(
        "--candidate-grid-count",
        type=int,
        default=10,
        help="Number of evenly spaced grid candidates to union with LOWESS peaks.",
    )
    parser.add_argument(
        "--probe-better-child",
        dest="probe_better_child",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow a one-pass recursion on the lower-RMSE child after splitting.",
    )
    parser.add_argument(
        "--lowess-frac-min",
        dest="lowess_frac_min",
        type=float,
        default=0.15,
        help="Minimum LOWESS smoothing fraction for residual diagnostics.",
    )
    parser.add_argument(
        "--lowess-frac-max",
        dest="lowess_frac_max",
        type=float,
        default=0.35,
        help="Maximum LOWESS smoothing fraction for residual diagnostics.",
    )
    parser.add_argument(
        "--try-page-at-root",
        dest="try_page_at_root",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Probe both Page and Midilli models at the root and select the better AICc.",
    )
    parser.add_argument(
        "--max-iter",
        dest="max_iter",
        type=int,
        default=2000,
        help="Maximum solver iterations for each model fit (applied to least squares).",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Logging level (e.g. DEBUG, INFO, WARNING).",
    )

    args = parser.parse_args(argv)

    if args.improvement_threshold is not None:
        args.min_rel_improvement = args.improvement_threshold

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s:%(message)s",
    )

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
            min_points_root=args.min_points_root,
            min_points_leaf=args.min_points_leaf,
            min_rel_improvement=args.min_rel_improvement,
            max_depth=args.max_depth,
            max_splits=args.max_splits,
            join_penalty=args.join_penalty,
            max_allowed_gap=args.max_allowed_gap,
            candidate_grid_count=args.candidate_grid_count,
            probe_better_child=args.probe_better_child,
            lowess_frac_min=args.lowess_frac_min,
            lowess_frac_max=args.lowess_frac_max,
            try_page_at_root=args.try_page_at_root,
            max_iter=args.max_iter,
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
