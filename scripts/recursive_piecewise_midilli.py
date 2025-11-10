"""Recursive piecewise Page/Midilli splitter with continuity and monotonicity controls."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, cast

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from statsmodels.nonparametric.smoothers_lowess import lowess


def clamp01(value: float) -> float:
    if math.isfinite(value):
        return float(np.clip(value, 0.0, 1.0))
    return 0.0

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402


plt.switch_backend("Agg")


@dataclass
class Config:
    data_dir: Path
    outdir: Path
    max_splits: int
    max_depth: int
    min_points_root: int  # Recommended to be at least twice min_points_leaf.
    min_points_leaf: int
    candidate_grid_count: int
    lowess_frac_min: float
    lowess_frac_max: float
    min_fraction: float
    max_fraction: float
    min_rel_improvement: float
    allow_per_segment_model: bool
    join_penalty: float
    slope_penalty: float
    shape_penalty_mono: float
    max_allowed_gap: float
    max_allowed_slope_gap: float
    reject_nonmonotone: bool
    total_gap_budget: float
    time_penalty: float
    lowess_frac_root: float
    max_iter: int
    seed: int
    log_level: str
    probe_better_child: bool
    lambda_b: float
    page_fallback_eps: float
    max_allowed_gap_eps: float = 1e-12
    max_allowed_slope_eps: float = 1e-12
    monotonic_eps: float = 5e-4
    lowess_points: int = 5
    iso_rmse_tol: float = 1e-6


@dataclass
class FitStats:
    family: str
    params: Dict[str, float]
    rss: float
    rmse: float
    aicc: float
    n_obs: int
    saturates_bound: bool
    predictions: np.ndarray
    hit_bounds: Dict[str, bool]

    def to_summary(self) -> Dict[str, object]:
        return {
            "family": self.family,
            "params": {key: float(value) for key, value in self.params.items()},
            "AICc": float(self.aicc),
            "RMSE": float(self.rmse),
            "n_obs": int(self.n_obs),
            "hit_bounds": {key: bool(value) for key, value in self.hit_bounds.items()},
        }


@dataclass
class SplitInfo:
    split_index: int
    split_time: float
    raw_gap_pre_shift: float
    post_shift_gap: float
    slope_gap: float
    penalized_score: float
    time_penalty: float
    level_shift_applied: float
    score_components: Dict[str, float]
    left: FitStats
    right: FitStats
    delta_aicc: float
    rel_improvement: float
    violations: int
    accept_reason: str
    left_reason: str
    right_reason: str
    b_penalty_left: float
    b_penalty_right: float


@dataclass
class Evidence:
    delta_aicc: float
    runs_p_value: float
    residual_amplitude: float
    slope_sign_changes: int
    score: float


@dataclass
class SegmentNode:
    node_id: str
    start: int
    end: int
    depth: int
    fit: FitStats
    split: Optional[SplitInfo] = None
    children: List["SegmentNode"] = field(default_factory=list)
    evidence: Optional[Evidence] = None
    offset: float = 0.0
    right_time_shift_at_boundary: float = 0.0
    diagnostics: Dict[str, float] = field(default_factory=dict)

    def is_leaf(self) -> bool:
        return not self.children

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "node_id": self.node_id,
            "start_idx": self.start,
            "end_idx": self.end,
            "depth": self.depth,
            "family": self.fit.family,
            "params": {key: float(value) for key, value in self.fit.params.items()},
            "n_obs": int(self.fit.n_obs),
            "hit_bounds": {key: bool(val) for key, val in self.fit.hit_bounds.items()},
            "rmse_seg": float(self.fit.rmse),
            "lowess_amp": float(self.diagnostics.get("lowess_amp", 0.0)),
            "lowess_curv": float(self.diagnostics.get("lowess_curv", 0.0)),
            "left_slope": float(self.diagnostics.get("left_slope", 0.0)),
            "right_slope": float(self.diagnostics.get("right_slope", 0.0)),
            "offset": float(self.offset),
        }
        if abs(self.right_time_shift_at_boundary) > 0.0:
            payload["right_time_shift_at_boundary"] = float(self.right_time_shift_at_boundary)
        if self.split is not None:
            payload.update(
                {
                    "t_split": float(self.split.split_time),
                    "post_shift_gap": float(self.split.post_shift_gap),
                    "raw_gap_pre_shift": float(self.split.raw_gap_pre_shift),
                    # Backward compatibility: emit legacy keys for one release.
                    "slope_gap": float(self.split.slope_gap),
                    "penalized_score": float(self.split.penalized_score),
                    "time_penalty": float(self.split.time_penalty),
                    "delta_aicc": float(self.split.delta_aicc),
                    "rel_improvement": float(self.split.rel_improvement),
                    "mono_violations": int(self.split.violations),
                    "level_shift_applied": float(self.split.level_shift_applied),
                    "accept_reason": self.split.accept_reason,
                    "score_components": {
                        key: float(value) for key, value in self.split.score_components.items()
                    },
                    "left": {
                        **self.split.left.to_summary(),
                        "selection_reason": self.split.left_reason,
                    },
                    "right": {
                        **self.split.right.to_summary(),
                        "selection_reason": self.split.right_reason,
                    },
                    "children": [child.node_id for child in self.children],
                }
            )
        if self.evidence is not None:
            payload["evidence"] = {
                "delta_aicc": float(self.evidence.delta_aicc),
                "runs_p_value": float(self.evidence.runs_p_value),
                "residual_amplitude": float(self.evidence.residual_amplitude),
                "slope_sign_changes": int(self.evidence.slope_sign_changes),
                "score": float(self.evidence.score),
            }
        return payload


@dataclass
class CandidateRecord:
    file: str
    node_id: str
    t_split: float
    t_idx: int
    left_n: int
    right_n: int
    model_left: str
    params_left: Dict[str, float]
    aicc_left: float
    rmse_left: float
    hit_bounds_left: Dict[str, bool]
    model_left_reason: str
    model_right: str
    params_right: Dict[str, float]
    aicc_right: float
    rmse_right: float
    hit_bounds_right: Dict[str, bool]
    model_right_reason: str
    aicc_unsplit: float
    delta_aicc: float
    rel_improvement: float
    raw_gap_pre_shift: float
    post_shift_gap: float
    slope_gap: float
    violations: int
    time_pen: float
    level_shift_applied: float
    b_pen_left: float
    b_pen_right: float
    base_aicc_sum: float
    gap_pen: float
    slope_pen: float
    mono_pen: float
    time_pen_comp: float
    b_pen_left_comp: float
    b_pen_right_comp: float
    penalized_score: float
    rejected_flag: bool
    reject_reason: str
    accept_reason: str
    tests_fired: List[str]

    def to_csv_row(self) -> Dict[str, object]:
        return {
            "file": self.file,
            "node_id": self.node_id,
            "t_split": self.t_split,
            "t_idx": self.t_idx,
            "left_n": self.left_n,
            "right_n": self.right_n,
            "model_left": self.model_left,
            "params_left_json": json.dumps(self.params_left, sort_keys=True),
            "AICc_left": self.aicc_left,
            "RMSE_left": self.rmse_left,
            "hit_bounds_left_json": json.dumps(self.hit_bounds_left, sort_keys=True),
            "model_left_reason": self.model_left_reason,
            "model_right": self.model_right,
            "params_right_json": json.dumps(self.params_right, sort_keys=True),
            "AICc_right": self.aicc_right,
            "RMSE_right": self.rmse_right,
            "hit_bounds_right_json": json.dumps(self.hit_bounds_right, sort_keys=True),
            "model_right_reason": self.model_right_reason,
            "AICc_unsplit": self.aicc_unsplit,
            "delta_AICc": self.delta_aicc,
            "rel_impr": self.rel_improvement,
            "raw_gap_pre_shift": self.raw_gap_pre_shift,
            "post_shift_gap": self.post_shift_gap,
            # Backward compatibility: emit legacy keys for one release.
            "slope_gap": self.slope_gap,
            "violations": self.violations,
            "time_pen": self.time_pen,
            "level_shift_applied": self.level_shift_applied,
            "b_pen_left": self.b_pen_left,
            "b_pen_right": self.b_pen_right,
            "base_aicc_sum": self.base_aicc_sum,
            "gap_pen": self.gap_pen,
            "slope_pen": self.slope_pen,
            "mono_pen": self.mono_pen,
            "time_pen_comp": self.time_pen_comp,
            "b_pen_left_comp": self.b_pen_left_comp,
            "b_pen_right_comp": self.b_pen_right_comp,
            "penalized_score": self.penalized_score,
            "rejected_flag": self.rejected_flag,
            "reject_reason": self.reject_reason,
            "accept_reason": self.accept_reason,
            "tests_fired_json": json.dumps(self.tests_fired, sort_keys=True),
        }


class FitCache:
    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, int, int, str], FitStats] = {}

    def get(self, family: str, start: int, end: int, tag: str) -> Optional[FitStats]:
        return self._cache.get((family, start, end, tag))

    def put(self, family: str, start: int, end: int, tag: str, stats: FitStats) -> None:
        self._cache[(family, start, end, tag)] = stats

@dataclass
class BudgetState:
    sum_gaps: float = 0.0
    splits_used: int = 0
    levels_splits: Dict[int, int] = field(default_factory=dict)


def page_model(time: np.ndarray, k: float, n: float) -> np.ndarray:
    return np.exp(-k * np.power(time, n))


def page_derivative(time: np.ndarray, k: float, n: float) -> np.ndarray:
    safe_time = np.maximum(time, 1e-12)
    base = np.exp(-k * np.power(safe_time, n))
    derivative = -k * n * np.power(safe_time, n - 1.0) * base
    derivative = np.where(time <= 0.0, 0.0, derivative)
    return derivative


def midilli_model(time: np.ndarray, k: float, n: float, b: float) -> np.ndarray:
    return np.exp(-k * np.power(time, n)) + b * time


def midilli_derivative(time: np.ndarray, k: float, n: float, b: float) -> np.ndarray:
    return page_derivative(time, k, n) + b


PAGE_BOUNDS = (np.array([1e-8, 0.10]), np.array([1.0, 3.00]))

MIDILLI_BOUNDS_BODY = (np.array([1e-8, 0.60, -2e-3]), np.array([2e-1, 2.20, 0.0]))
MIDILLI_BOUNDS_TAIL = (np.array([1e-8, 0.70, -6e-4]), np.array([6e-2, 2.30, 0.0]))

# Keep, but this now works in tandem with MIDILLI_BOUNDS_* and the b-penalty
MIDILLI_SOFT_BOUND = 1e-3

# === Segment classifiers ===
TAIL_FRAC = 0.20          # rightmost fraction of timeline qualifies as tail
TAIL_MR_MAX = 0.20        # or MR small enough to be considered tail
HEAD_FRAC = 0.35          # early zone where Page is preferred but not forced


def _is_tail(start: int, end: int, time: np.ndarray, values: np.ndarray) -> bool:
    t_end = float(time[end - 1])
    t_max = float(time[-1])
    return (t_end >= (1.0 - TAIL_FRAC) * t_max) or (float(values[end - 1]) <= TAIL_MR_MAX)


def _is_head(start: int, end: int, time: np.ndarray) -> bool:
    t_end = float(time[end - 1])
    t_max = float(time[-1])
    return t_end <= HEAD_FRAC * t_max
SCHEMA_VERSION = "2.0.0"


def _initial_guess_page(time: np.ndarray, values: np.ndarray) -> Tuple[float, float]:
    clipped = np.clip(values, 1e-6, 0.999999)
    with np.errstate(divide="ignore"):
        transformed = -np.log(clipped)
    mask = np.isfinite(transformed) & np.isfinite(time) & (time > 0)
    if np.count_nonzero(mask) >= 2 and np.all(transformed[mask] > 0):
        log_t = np.log(time[mask])
        log_transformed = np.log(transformed[mask])
        slope, intercept = np.polyfit(log_t, log_transformed, deg=1)
        n_guess = float(np.clip(slope, PAGE_BOUNDS[0][1], PAGE_BOUNDS[1][1]))
        k_guess = float(np.clip(math.exp(intercept), PAGE_BOUNDS[0][0], PAGE_BOUNDS[1][0]))
        if math.isfinite(k_guess) and math.isfinite(n_guess):
            return k_guess, n_guess
    return 0.05, 1.0


def _initial_guess_midilli(
    time: np.ndarray, values: np.ndarray, bounds: Tuple[np.ndarray, np.ndarray]
) -> Tuple[float, float, float]:
    k_guess, n_guess = _initial_guess_page(time, values)
    if time.size >= 3:
        tail = min(5, time.size)
        coef = np.polyfit(time[-tail:], values[-tail:], deg=1)
        b_guess = float(np.clip(coef[0], bounds[0][2], bounds[1][2]))
    else:
        b_guess = 0.0
    k_guess = float(np.clip(k_guess, bounds[0][0], bounds[1][0]))
    n_guess = float(np.clip(n_guess, bounds[0][1], bounds[1][1]))
    return k_guess, n_guess, b_guess


# Note: AICc computed from MSE=RSS/n (constant-variance Gaussian), used only for relative comparisons across candidates.
def _compute_aicc(n_obs: int, rss: float, k_params: int) -> float:
    if n_obs <= k_params + 1:
        return float("inf")
    if rss <= 0:
        rss = 1e-12
    mse = rss / n_obs
    aic = n_obs * math.log(mse) + 2 * k_params
    correction = (2 * k_params * (k_params + 1)) / (n_obs - k_params - 1)
    return aic + correction


def _fit_page(time: np.ndarray, values: np.ndarray, max_iter: int) -> Optional[FitStats]:
    guess = _initial_guess_page(time, values)
    try:
        params, _ = curve_fit(
            lambda t, k, n: page_model(t, k, n),
            time,
            values,
            p0=guess,
            bounds=PAGE_BOUNDS,
            maxfev=max_iter,
        )
    except Exception:  # pragma: no cover - scipy raises runtime errors
        return None
    params = np.clip(params, PAGE_BOUNDS[0], PAGE_BOUNDS[1])
    k = float(params[0])
    n = float(params[1])
    predictions = page_model(time, k, n)
    residuals = values - predictions
    rss = float(np.dot(residuals, residuals))
    rmse = math.sqrt(max(rss, 0.0) / time.size)
    aicc = _compute_aicc(time.size, rss, 2)
    hit_bounds = {
        "k": bool(
            abs(k - PAGE_BOUNDS[0][0]) <= 1e-8 or abs(k - PAGE_BOUNDS[1][0]) <= 1e-8
        ),
        "n": bool(
            abs(n - PAGE_BOUNDS[0][1]) <= 1e-8 or abs(n - PAGE_BOUNDS[1][1]) <= 1e-8
        ),
        "b": False,
    }
    return FitStats(
        family="Page",
        params={"k": k, "n": n, "b": 0.0},
        rss=rss,
        rmse=rmse,
        aicc=aicc,
        n_obs=time.size,
        saturates_bound=any(hit_bounds.values()),
        predictions=predictions,
        hit_bounds=hit_bounds,
    )


def _fit_midilli(
    time: np.ndarray,
    values: np.ndarray,
    max_iter: int,
    bounds: Tuple[np.ndarray, np.ndarray],
) -> Optional[FitStats]:
    guess = _initial_guess_midilli(time, values, bounds)

    try:
        params, _ = curve_fit(
            lambda t, k, n, b: midilli_model(t, k, n, b),
            time,
            values,
            p0=guess,
            bounds=bounds,
            maxfev=max_iter,
        )
    except Exception:  # pragma: no cover - scipy raises runtime errors
        return None
    params = np.clip(params, bounds[0], bounds[1])
    k = float(params[0])
    n = float(params[1])
    b = float(params[2])
    predictions = midilli_model(time, k, n, b)
    residuals = values - predictions
    rss = float(np.dot(residuals, residuals))
    rmse = math.sqrt(max(rss, 0.0) / time.size)
    aicc = _compute_aicc(time.size, rss, 3)
    hit_bounds = {
        "k": bool(abs(k - bounds[0][0]) <= 1e-8 or abs(k - bounds[1][0]) <= 1e-8),
        "n": bool(abs(n - bounds[0][1]) <= 1e-8 or abs(n - bounds[1][1]) <= 1e-8),
        "b": bool(abs(b - bounds[0][2]) <= 1e-8 or abs(b - bounds[1][2]) <= 1e-8),
    }
    saturates = any(hit_bounds.values())
    return FitStats(
        family="Midilli",
        params={"k": k, "n": n, "b": b},
        rss=rss,
        rmse=rmse,
        aicc=aicc,
        n_obs=time.size,
        saturates_bound=saturates,
        predictions=predictions,
        hit_bounds=hit_bounds,
    )


def fit_segment(
    family: str,
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    max_iter: int,
    bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None,
) -> Optional[FitStats]:
    if family == "Page":
        tag = "page"
    elif family == "Midilli":
        if bounds is None or bounds is MIDILLI_BOUNDS_BODY:
            tag = "mid_body"
        elif bounds is MIDILLI_BOUNDS_TAIL:
            tag = "mid_tail"
        else:
            if bounds is not None and all(
                np.array_equal(b, candidate)
                for b, candidate in zip(bounds, MIDILLI_BOUNDS_BODY)
            ):
                tag = "mid_body"
            elif bounds is not None and all(
                np.array_equal(b, candidate)
                for b, candidate in zip(bounds, MIDILLI_BOUNDS_TAIL)
            ):
                tag = "mid_tail"
            else:
                raise ValueError("Unrecognized bounds for Midilli fit cache tag")
    else:
        raise ValueError(f"Unsupported family '{family}' for fit cache")

    cached = cache.get(family, start, end, tag)
    if cached is not None:
        return cached

    segment_time = time[start:end]
    segment_values = values[start:end]
    if family == "Page":
        stats = _fit_page(segment_time, segment_values, max_iter)
    else:
        use_bounds = bounds if bounds is not None else MIDILLI_BOUNDS_BODY
        stats = _fit_midilli(segment_time, segment_values, max_iter, use_bounds)
    if stats is not None:
        cache.put(family, start, end, tag, stats)
    return stats


def select_best_model(
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
) -> Optional[Tuple[FitStats, str]]:
    is_tail = _is_tail(start, end, time, values)
    is_head = _is_head(start, end, time)

    mid_bounds = MIDILLI_BOUNDS_TAIL if is_tail else MIDILLI_BOUNDS_BODY

    page = fit_segment("Page", start, end, time, values, cache, cfg.max_iter)
    mid = fit_segment(
        "Midilli",
        start,
        end,
        time,
        values,
        cache,
        cfg.max_iter,
        bounds=mid_bounds,
    )

    if page is None and mid is None:
        return None
    if page is None:
        return (cast(FitStats,mid),"midilli_only")
    if mid is None:
        return (page, "page_only")

    if is_head and cfg.allow_per_segment_model:
        if page.aicc <= mid.aicc + cfg.page_fallback_eps:
            return (page, "page_head_preferred")

    if is_tail and cfg.allow_per_segment_model:
        if mid.aicc <= page.aicc + cfg.page_fallback_eps:
            return (mid, "midilli_tail_preferred")

    fallback_trigger = mid.saturates_bound or mid.hit_bounds.get("b", False)
    if fallback_trigger and page.aicc <= mid.aicc + cfg.page_fallback_eps:
        return (page, "page_fallback")

    if cfg.allow_per_segment_model and page.aicc < mid.aicc - 1e-9:
        return (page, "page")

    return (mid, "midilli")


def select_model_with_fallback(
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
) -> Optional[Tuple[FitStats, str]]:
    result = select_best_model(start, end, time, values, cache, cfg)
    if result is not None:
        return result
    fallback = fit_segment("Page", start, end, time, values, cache, cfg.max_iter)
    if fallback is None:
        return None
    return fallback, "page_fallback_only"


def compute_unsplit_fit(
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
) -> Optional[FitStats]:
    result = select_model_with_fallback(start, end, time, values, cache, cfg)
    if result is None:
        return None
    return result[0]


def _find_lowess_extrema(residuals: np.ndarray, smooth: np.ndarray) -> List[int]:
    if smooth.size < 3:
        return []
    diff = np.diff(smooth)
    signs = np.sign(diff)
    sign_change = np.diff(signs)
    indices = np.where(sign_change != 0)[0] + 1
    return indices.tolist()


def generate_candidates(
    node: SegmentNode,
    time: np.ndarray,
    values: np.ndarray,
    cfg: Config,
) -> List[int]:
    start = node.start
    end = node.end
    length = end - start
    if length < cfg.min_points_leaf * 2:
        return []
    allowed_min = start + cfg.min_points_leaf - 1
    allowed_max = end - cfg.min_points_leaf - 1
    if allowed_min > allowed_max:
        return []
    grid = np.linspace(allowed_min, allowed_max, cfg.candidate_grid_count)
    grid_indices = {int(round(idx)) for idx in grid}
    grid_indices = {idx for idx in grid_indices if allowed_min <= idx <= allowed_max}
    segment_time = time[start:end]
    base_pred = _segment_base_predictions(
        node.fit, segment_time, node.right_time_shift_at_boundary
    )
    if base_pred.size:
        base_pred = base_pred + node.offset
    residuals = values[start:end] - base_pred
    if node.depth == 0:
        fractions = [cfg.lowess_frac_root]
    else:
        fractions = np.linspace(cfg.lowess_frac_min, cfg.lowess_frac_max, cfg.lowess_points).tolist()
    lowess_indices: set[int] = set()
    for frac in fractions:
        frac_clamped = float(np.clip(frac, 0.01, 0.99))
        smoothed = lowess(residuals, time[start:end], frac=frac_clamped, return_sorted=False)
        for idx in _find_lowess_extrema(residuals, smoothed):
            candidate = start + idx
            if allowed_min <= candidate <= allowed_max:
                lowess_indices.add(candidate)
    candidates = sorted(grid_indices.union(lowess_indices))
    feasible: List[int] = []
    for split_idx in candidates:
        left_len = split_idx - start + 1
        right_len = end - (split_idx + 1)
        if left_len < cfg.min_points_leaf or right_len < cfg.min_points_leaf:
            logging.getLogger(__name__).debug(
                "Candidate %s-%d rejected: insufficient points (L=%d R=%d)",
                node.node_id,
                split_idx,
                left_len,
                right_len,
            )
            continue
        fraction = (split_idx - start + 1) / length
        if fraction < cfg.min_fraction or fraction > cfg.max_fraction:
            logging.getLogger(__name__).debug(
                "Candidate %s-%d rejected: fraction %.3f outside bounds", node.node_id, split_idx, fraction
            )
            continue
        feasible.append(split_idx)
    return feasible


def _model_value_and_slope(fit: FitStats, time_value: float) -> Tuple[float, float]:
    if fit.family == "Page":
        k = fit.params["k"]
        n = fit.params["n"]
        value = float(page_model(np.array([time_value]), k, n)[0])
        slope = float(page_derivative(np.array([time_value]), k, n)[0])
        return value, slope
    k = fit.params["k"]
    n = fit.params["n"]
    b = fit.params.get("b", 0.0)
    value = float(midilli_model(np.array([time_value]), k, n, b)[0])
    slope = float(midilli_derivative(np.array([time_value]), k, n, b)[0])
    return value, slope


def _segment_base_predictions(
    fit: FitStats, segment_time: np.ndarray, first_point_time_shift: float = 0.0
) -> np.ndarray:
    if first_point_time_shift != 0.0 and segment_time.size:
        adjusted_time = np.array(segment_time, copy=True)
        adjusted_time[0] = max(float(adjusted_time[0]) + first_point_time_shift, 0.0)
    else:
        adjusted_time = segment_time
    if fit.family == "Page":
        return page_model(adjusted_time, fit.params["k"], fit.params["n"])
    return midilli_model(
        adjusted_time, fit.params["k"], fit.params["n"], fit.params.get("b", 0.0)
    )


def _combine_predictions(
    left: FitStats,
    right: FitStats,
    start: int,
    split_idx: int,
    end: int,
    time: np.ndarray,
    level_shift: float = 0.0,
) -> np.ndarray:
    left_time = time[start : split_idx + 1]
    right_time = time[split_idx + 1 : end]
    left_pred = _segment_base_predictions(left, left_time)
    right_pred = _segment_base_predictions(right, right_time)
    if right_pred.size:
        right_pred = right_pred + level_shift
    return np.concatenate([left_pred, right_pred])


def _count_monotonic_violations(predictions: np.ndarray, eps: float) -> int:
    diffs = np.diff(predictions)
    return int(np.sum(diffs > eps))


def isotonic_pav(y: np.ndarray, nonincreasing: bool = True) -> np.ndarray:
    """Project ``y`` onto the space of monotone sequences via PAV."""

    if y.ndim != 1:
        raise ValueError("isotonic_pav expects a 1D array")
    if y.size == 0:
        return y.copy()

    def _pav_non_decreasing(values: np.ndarray) -> np.ndarray:
        block_values: List[float] = []
        block_lengths: List[int] = []
        for value in values:
            block_values.append(float(value))
            block_lengths.append(1)
            while len(block_values) >= 2 and block_values[-2] > block_values[-1]:
                total = block_lengths[-2] + block_lengths[-1]
                merged = (
                    block_values[-2] * block_lengths[-2]
                    + block_values[-1] * block_lengths[-1]
                ) / total
                block_values[-2] = merged
                block_lengths[-2] = total
                block_values.pop()
                block_lengths.pop()
        result = np.empty(values.size, dtype=float)
        idx = 0
        for value, length in zip(block_values, block_lengths):
            result[idx : idx + length] = value
            idx += length
        return result

    if nonincreasing:
        return -_pav_non_decreasing(-y.astype(float))
    return _pav_non_decreasing(y.astype(float))


def _time_penalty(split_time: float, node: SegmentNode, time: np.ndarray, cfg: Config) -> float:
    t_min = float(time[node.start])
    t_max = float(time[node.end - 1])
    if t_max <= t_min:
        return 0.0
    t_mid = 0.5 * (t_min + t_max)
    scale = 0.5 * (t_max - t_min)
    if scale <= 0:
        return 0.0
    x = (split_time - t_mid) / scale
    return cfg.time_penalty * (x**2)


def _b_penalty(fit: FitStats, cfg: Config) -> float:
    if fit.family != "Midilli" or cfg.lambda_b <= 0:
        return 0.0
    excess = max(abs(fit.params.get("b", 0.0)) - MIDILLI_SOFT_BOUND, 0.0)
    if excess <= 0:
        return 0.0
    return cfg.lambda_b * (excess**2)


def score_candidate(
    node: SegmentNode,
    split_idx: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
    dataset_name: str,
    budget_sum_gaps: float,
) -> Tuple[Optional[SplitInfo], CandidateRecord]:
    start = node.start
    end = node.end
    left_result = select_model_with_fallback(start, split_idx + 1, time, values, cache, cfg)
    right_result = select_model_with_fallback(split_idx + 1, end, time, values, cache, cfg)
    left_stats = left_result[0] if left_result is not None else None
    right_stats = right_result[0] if right_result is not None else None
    left_reason = left_result[1] if left_result is not None else ""
    right_reason = right_result[1] if right_result is not None else ""
    left_n = split_idx - start + 1
    right_n = end - (split_idx + 1)
    split_time = float(time[split_idx])
    tests: List[str] = []
    rejected = False
    reason = ""
    accept_reason = ""

    if left_stats is None or right_stats is None:
        rejected = True
        reason = "fit_failure"
        tests.append("fit_failure")
        record = CandidateRecord(
            file=dataset_name,
            node_id=node.node_id,
            t_split=split_time,
            t_idx=split_idx,
            left_n=left_n,
            right_n=right_n,
            model_left=left_stats.family if left_stats else "",
            params_left=left_stats.params if left_stats else {},
            aicc_left=left_stats.aicc if left_stats else float("nan"),
            rmse_left=left_stats.rmse if left_stats else float("nan"),
            hit_bounds_left=left_stats.hit_bounds if left_stats else {},
            model_left_reason=left_reason,
            model_right=right_stats.family if right_stats else "",
            params_right=right_stats.params if right_stats else {},
            aicc_right=right_stats.aicc if right_stats else float("nan"),
            rmse_right=right_stats.rmse if right_stats else float("nan"),
            hit_bounds_right=right_stats.hit_bounds if right_stats else {},
            model_right_reason=right_reason,
            aicc_unsplit=node.fit.aicc,
            delta_aicc=float("nan"),
            rel_improvement=float("nan"),
            raw_gap_pre_shift=float("nan"),
            post_shift_gap=float("nan"),
            slope_gap=float("nan"),
            violations=0,
            time_pen=0.0,
            level_shift_applied=0.0,
            b_pen_left=0.0,
            b_pen_right=0.0,
            base_aicc_sum=float("nan"),
            gap_pen=float("nan"),
            slope_pen=float("nan"),
            mono_pen=float("nan"),
            time_pen_comp=float("nan"),
            b_pen_left_comp=float("nan"),
            b_pen_right_comp=float("nan"),
            penalized_score=float("nan"),
            rejected_flag=rejected,
            reject_reason=reason,
            accept_reason=accept_reason,
            tests_fired=tests,
        )
        return None, record

    if left_reason.startswith("page_fallback"):
        tests.append("page_fallback_left")
    if right_reason.startswith("page_fallback"):
        tests.append("page_fallback_right")

    base = left_stats.aicc + right_stats.aicc
    delta_aicc = node.fit.aicc - base
    denom = max(abs(node.fit.aicc), 1e-9)
    rel_impr = (node.fit.aicc - base) / denom

    value_left, slope_left = _model_value_and_slope(left_stats, split_time)
    right_time = float(time[split_idx + 1])
    value_right, slope_right = _model_value_and_slope(right_stats, right_time)
    raw_gap_pre_shift = abs(value_left - value_right)
    level_shift = value_left - value_right
    post_shift_gap = abs(value_left - (value_right + level_shift))
    slope_gap = abs(slope_left - slope_right)
    time_pen = _time_penalty(split_time, node, time, cfg)
    combined_preds = _combine_predictions(
        left_stats, right_stats, start, split_idx, end, time, level_shift
    )
    violations = _count_monotonic_violations(combined_preds, cfg.monotonic_eps)

    if not math.isfinite(base) or not math.isfinite(raw_gap_pre_shift) or not math.isfinite(slope_gap):
        rejected = True
        reason = "nan_metric"
        tests.append("nan_metric")
    if raw_gap_pre_shift > cfg.max_allowed_gap + cfg.max_allowed_gap_eps:
        rejected = True
        reason = "gap_limit"
        tests.append("gap_limit")
    if slope_gap > cfg.max_allowed_slope_gap + cfg.max_allowed_slope_eps:
        rejected = True
        reason = "slope_limit"
        tests.append("slope_limit")
    if cfg.reject_nonmonotone and violations > 0:
        rejected = True
        reason = "nonmonotone"
        tests.append("nonmonotone")
    if rel_impr < cfg.min_rel_improvement:
        rejected = True
        reason = "rel_improvement"
        tests.append("rel_improvement")
    if budget_sum_gaps + raw_gap_pre_shift > cfg.total_gap_budget + cfg.max_allowed_gap_eps:
        rejected = True
        reason = "gap_budget"
        tests.append("gap_budget")

    b_pen_left = _b_penalty(left_stats, cfg)
    b_pen_right = _b_penalty(right_stats, cfg)

    gap_pen_component = (
        cfg.join_penalty * (raw_gap_pre_shift**2) if math.isfinite(raw_gap_pre_shift) else float("nan")
    )
    slope_pen_component = (
        cfg.slope_penalty * (slope_gap**2) if math.isfinite(slope_gap) else float("nan")
    )
    mono_pen_component = cfg.shape_penalty_mono * violations
    score_components = {
        "base": base,
        "gap_pen": gap_pen_component,
        "slope_pen": slope_pen_component,
        "time_pen": time_pen,
        "mono_pen": mono_pen_component,
        "b_pen_left": b_pen_left,
        "b_pen_right": b_pen_right,
        "raw_gap_pre_shift": raw_gap_pre_shift,
        # Backward compatibility: emit legacy key for one release.
        "raw_gap": raw_gap_pre_shift,
    }

    score = base + gap_pen_component + slope_pen_component
    score += mono_pen_component + time_pen + b_pen_left + b_pen_right

    if not rejected and not math.isfinite(score):
        rejected = True
        reason = "nan_score"
        tests.append("nan_score")

    split_info = None
    if not rejected:
        tests.append("accepted")
        accept_reason = "best_penalized_score"
        split_info = SplitInfo(
            split_idx,
            split_time,
            raw_gap_pre_shift,
            post_shift_gap,
            slope_gap,
            score,
            time_pen,
            level_shift,
            score_components,
            left_stats,
            right_stats,
            delta_aicc,
            rel_impr,
            violations,
            accept_reason,
            left_reason,
            right_reason,
            b_pen_left,
            b_pen_right,
        )
    else:
        if not tests:
            tests.append("rejected")

    record = CandidateRecord(
        file=dataset_name,
        node_id=node.node_id,
        t_split=split_time,
        t_idx=split_idx,
        left_n=left_n,
        right_n=right_n,
        model_left=left_stats.family,
        params_left=left_stats.params,
        aicc_left=left_stats.aicc,
        rmse_left=left_stats.rmse,
        hit_bounds_left=left_stats.hit_bounds,
        model_left_reason=left_reason,
        model_right=right_stats.family,
        params_right=right_stats.params,
        aicc_right=right_stats.aicc,
        rmse_right=right_stats.rmse,
        hit_bounds_right=right_stats.hit_bounds,
        model_right_reason=right_reason,
        aicc_unsplit=node.fit.aicc,
        delta_aicc=delta_aicc,
        rel_improvement=rel_impr,
        raw_gap_pre_shift=raw_gap_pre_shift,
        post_shift_gap=post_shift_gap,
        slope_gap=slope_gap,
        violations=violations,
        time_pen=time_pen,
        level_shift_applied=level_shift,
        b_pen_left=b_pen_left,
        b_pen_right=b_pen_right,
        base_aicc_sum=score_components["base"],
        gap_pen=score_components["gap_pen"],
        slope_pen=score_components["slope_pen"],
        mono_pen=score_components["mono_pen"],
        time_pen_comp=score_components["time_pen"],
        b_pen_left_comp=score_components["b_pen_left"],
        b_pen_right_comp=score_components["b_pen_right"],
        penalized_score=score,
        rejected_flag=rejected,
        reject_reason=reason,
        accept_reason=accept_reason,
        tests_fired=tests,
    )
    return split_info, record


def _runs_test(residuals: np.ndarray) -> Tuple[float, float]:
    signs = np.sign(residuals)
    signs = signs[signs != 0]
    n = signs.size
    if n < 2:
        return float("nan"), float("nan")
    n_pos = int(np.sum(signs > 0))
    n_neg = int(np.sum(signs < 0))
    if n_pos == 0 or n_neg == 0:
        return 0.0, float("inf")
    runs = 1 + int(np.sum(signs[:-1] != signs[1:]))
    expected = (2 * n_pos * n_neg) / n + 1
    variance = (2 * n_pos * n_neg * (2 * n_pos * n_neg - n_pos - n_neg)) / (n**2 * (n - 1))
    if variance <= 0:
        return float("nan"), float("nan")
    z = (runs - expected) / math.sqrt(variance)
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return float(p_value), float(z)


def _residual_lowess_amplitude(time: np.ndarray, residuals: np.ndarray, frac: float) -> float:
    if residuals.size < 2:
        return 0.0
    smoothed = lowess(residuals, time, frac=float(np.clip(frac, 0.01, 0.99)), return_sorted=False)
    return float(np.nanmax(smoothed) - np.nanmin(smoothed))


def _lowess_curvature(time: np.ndarray, residuals: np.ndarray, frac: float) -> float:
    if residuals.size < 3:
        return 0.0
    smoothed = lowess(residuals, time, frac=float(np.clip(frac, 0.01, 0.99)), return_sorted=False)
    if smoothed.size < 3:
        return 0.0
    second_diff = np.diff(smoothed, n=2)
    if second_diff.size == 0:
        return 0.0
    return float(np.nanmax(np.abs(second_diff)))


def _slope_sign_changes(residuals: np.ndarray) -> int:
    if residuals.size < 3:
        return 0
    diff = np.diff(residuals)
    signs = np.sign(diff)
    changes = np.sum(signs[1:] * signs[:-1] < 0)
    return int(changes)


def compute_child_evidence(
    child: SegmentNode,
    parent: SegmentNode,
    time: np.ndarray,
    values: np.ndarray,
    cfg: Config,
) -> Evidence:
    child_slice = slice(child.start, child.end)
    child_time = time[child_slice]
    parent_base = _segment_base_predictions(parent.fit, child_time)
    if parent_base.size:
        parent_base = parent_base + parent.offset
    parent_k = 2 if parent.fit.family == "Page" else 3
    residuals_parent = values[child_slice] - parent_base

    child_base = _segment_base_predictions(
        child.fit, child_time, child.right_time_shift_at_boundary
    )
    if child_base.size:
        child_base = child_base + child.offset
    residuals_child = values[child_slice] - child_base
    rss_parent = float(np.dot(residuals_parent, residuals_parent))
    rss_child = float(np.dot(residuals_child, residuals_child))
    aicc_parent = _compute_aicc(child.fit.n_obs, rss_parent, parent_k)
    delta = aicc_parent - child.fit.aicc
    runs_p, _ = _runs_test(residuals_child)
    amplitude = _residual_lowess_amplitude(time[child_slice], residuals_child, cfg.lowess_frac_root)
    sigma = max(float(np.std(residuals_child)), 1e-8)
    amp_norm = amplitude / sigma
    slope_changes = _slope_sign_changes(residuals_child)
    score = float(delta - 0.5 * amp_norm - 0.25 * slope_changes - (1.0 - clamp01(runs_p)))
    return Evidence(delta, runs_p, amplitude, slope_changes, score)


def _segment_boundary_slopes(fit: FitStats, segment_time: np.ndarray) -> Tuple[float, float]:
    if segment_time.size == 0:
        return 0.0, 0.0
    left_t = float(segment_time[0])
    right_t = float(segment_time[-1])
    if fit.family == "Page":
        left_val = float(page_derivative(np.array([left_t]), fit.params["k"], fit.params["n"])[0])
        right_val = float(page_derivative(np.array([right_t]), fit.params["k"], fit.params["n"])[0])
    else:
        left_val = float(
            midilli_derivative(
                np.array([left_t]),
                fit.params["k"],
                fit.params["n"],
                fit.params.get("b", 0.0),
            )[0]
        )
        right_val = float(
            midilli_derivative(
                np.array([right_t]),
                fit.params["k"],
                fit.params["n"],
                fit.params.get("b", 0.0),
            )[0]
        )
    return left_val, right_val


def _segment_slope_at(fit: FitStats, time_value: float) -> float:
    if fit.family == "Page":
        return float(
            page_derivative(np.array([time_value]), fit.params["k"], fit.params["n"])[0]
        )
    return float(
        midilli_derivative(
            np.array([time_value]),
            fit.params["k"],
            fit.params["n"],
            fit.params.get("b", 0.0),
        )[0]
    )


def _solve_time_shift_for_slope_match(
    fit: FitStats, base_time: float, target_slope: float, max_shift: float
) -> float:
    base_time = float(max(base_time, 1e-8))
    max_shift = float(max(max_shift, 0.0))
    if max_shift <= 0.0:
        return 0.0
    initial_slope = _segment_slope_at(fit, base_time)
    if not math.isfinite(initial_slope) or not math.isfinite(target_slope):
        return 0.0
    if abs(initial_slope - target_slope) <= 1e-12:
        return 0.0
    delta = 0.0
    current_time = base_time
    tol = 1e-8 + 1e-3 * abs(target_slope)
    for _ in range(6):
        slope_here = _segment_slope_at(fit, current_time)
        if not math.isfinite(slope_here):
            return 0.0
        error = slope_here - target_slope
        if abs(error) <= tol:
            break
        step_radius = min(max_shift, max(current_time * 0.5, 1e-6))
        left_time = max(current_time - step_radius, 1e-8)
        right_time = current_time + step_radius
        slope_left = _segment_slope_at(fit, left_time)
        slope_right = _segment_slope_at(fit, right_time)
        denom = right_time - left_time
        if denom <= 0:
            break
        slope_prime = (slope_right - slope_left) / denom
        if not math.isfinite(slope_prime) or abs(slope_prime) < 1e-12:
            break
        step = error / slope_prime
        delta -= step
        delta = float(np.clip(delta, -max_shift, max_shift))
        current_time = base_time + delta
        if current_time <= 0.0:
            current_time = max(1e-8, base_time - max_shift)
            delta = current_time - base_time
        if abs(step) <= tol:
            break
    final_time = base_time + delta
    final_slope = _segment_slope_at(fit, final_time)
    if not math.isfinite(final_slope):
        return 0.0
    if abs(final_slope - target_slope) >= abs(initial_slope - target_slope):
        return 0.0
    return delta


def update_node_diagnostics(node: SegmentNode, time: np.ndarray, values: np.ndarray, cfg: Config) -> None:
    segment_time = time[node.start : node.end]
    base_pred = _segment_base_predictions(
        node.fit, segment_time, node.right_time_shift_at_boundary
    )
    if base_pred.size:
        base_pred = base_pred + node.offset
    residuals = values[node.start : node.end] - base_pred
    amp = _residual_lowess_amplitude(segment_time, residuals, cfg.lowess_frac_root)
    curv = _lowess_curvature(segment_time, residuals, cfg.lowess_frac_root)
    left_slope, right_slope = _segment_boundary_slopes(node.fit, segment_time)
    node.diagnostics = {
        "lowess_amp": amp,
        "lowess_curv": curv,
        "left_slope": left_slope,
        "right_slope": right_slope,
    }


def recurse_node(
    node: SegmentNode,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
    dataset_name: str,
    budget: BudgetState,
    candidate_records: List[CandidateRecord],
    is_probe: bool = False,
) -> None:
    if node.depth >= cfg.max_depth:
        return
    if budget.splits_used >= cfg.max_splits:
        return
    candidates = generate_candidates(node, time, values, cfg)
    if not candidates:
        return
    best_info: Optional[SplitInfo] = None
    best_score = float("inf")
    for idx in candidates:
        info, record = score_candidate(node, idx, time, values, cache, cfg, dataset_name, budget.sum_gaps)
        candidate_records.append(record)
        if info is not None and info.penalized_score < best_score:
            best_info = info
            best_score = info.penalized_score
    if best_info is None:
        return
    node.split = best_info
    right_time_shift = 0.0
    split_idx = best_info.split_index
    right_idx = split_idx + 1
    if right_idx < node.end:
        left_time = float(time[split_idx])
        right_time = float(time[right_idx])
        slope_left = _segment_slope_at(best_info.left, left_time)
        slope_right = _segment_slope_at(best_info.right, right_time)
        slope_gap = abs(slope_left - slope_right)
        slope_tol = max(cfg.max_allowed_slope_gap, cfg.max_allowed_slope_eps)
        if (
            math.isfinite(slope_left)
            and math.isfinite(slope_right)
            and slope_gap <= slope_tol
        ):
            max_shift = max(right_time - left_time, 0.0)
            if max_shift > 0.0 and slope_gap > cfg.max_allowed_slope_eps:
                shift = _solve_time_shift_for_slope_match(
                    best_info.right, right_time, slope_left, max_shift
                )
                if shift != 0.0:
                    right_time_shift = shift
    left_node = SegmentNode(
        node_id=f"{node.node_id}L",
        start=node.start,
        end=split_idx + 1,
        depth=node.depth + 1,
        fit=best_info.left,
        offset=node.offset,
    )
    right_node = SegmentNode(
        node_id=f"{node.node_id}R",
        start=split_idx + 1,
        end=node.end,
        depth=node.depth + 1,
        fit=best_info.right,
        offset=node.offset + best_info.level_shift_applied,
        right_time_shift_at_boundary=right_time_shift,
    )
    node.children = [left_node, right_node]
    budget.sum_gaps += best_info.raw_gap_pre_shift
    budget.splits_used += 1
    budget.levels_splits[node.depth] = budget.levels_splits.get(node.depth, 0) + 1
    left_node.evidence = compute_child_evidence(left_node, node, time, values, cfg)
    right_node.evidence = compute_child_evidence(right_node, node, time, values, cfg)

    update_node_diagnostics(left_node, time, values, cfg)
    update_node_diagnostics(right_node, time, values, cfg)

    if cfg.probe_better_child:
        def _evidence_key(child: SegmentNode) -> float:
            ev = child.evidence
            if ev is None:
                return float("-inf")
            return float(ev.score)

        ordered_children = sorted(node.children, key=_evidence_key, reverse=True)
    else:
        ordered_children = list(node.children)
    if is_probe:
        return

    for idx, child in enumerate(ordered_children):
        if budget.splits_used >= cfg.max_splits:
            break
        if child.depth >= cfg.max_depth:
            continue
        child_probe = cfg.probe_better_child and idx > 0
        recurse_node(
            child,
            time,
            values,
            cache,
            cfg,
            dataset_name,
            budget,
            candidate_records,
            is_probe=child_probe,
        )


def reconstruct_predictions(
    node: SegmentNode, time: np.ndarray, values: np.ndarray, cfg: Config
) -> Tuple[np.ndarray, np.ndarray, int, bool]:
    preds = np.zeros_like(time, dtype=float)

    def _assign(segment: SegmentNode) -> None:
        segment_time = time[segment.start:segment.end]
        base = _segment_base_predictions(
            segment.fit, segment_time, segment.right_time_shift_at_boundary
        )
        if base.size:
            base = base + segment.offset
        preds[segment.start:segment.end] = base
        for child in segment.children:
            _assign(child)

    _assign(node)

    # Count violations on raw preds (for diagnostics)
    violations = _count_monotonic_violations(preds, cfg.monotonic_eps)

    # Candidate isotonic correction
    iso = isotonic_pav(preds, nonincreasing=True)

    rmse_raw = float(np.sqrt(np.mean((preds - values) ** 2)))
    rmse_iso = float(np.sqrt(np.mean((iso - values) ** 2)))
    use_iso = rmse_iso <= rmse_raw + cfg.iso_rmse_tol

    corrected = iso if use_iso else preds
    return preds, corrected, violations, use_iso



def gather_nodes(node: SegmentNode) -> List[SegmentNode]:
    nodes = [node]
    for child in node.children:
        nodes.extend(gather_nodes(child))
    return nodes


def write_candidate_log(path: Path, records: List[CandidateRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file",
        "node_id",
        "t_split",
        "t_idx",
        "left_n",
        "right_n",
        "model_left",
        "params_left_json",
        "AICc_left",
        "RMSE_left",
        "hit_bounds_left_json",
        "model_left_reason",
        "model_right",
        "params_right_json",
        "AICc_right",
        "RMSE_right",
        "hit_bounds_right_json",
        "model_right_reason",
        "AICc_unsplit",
        "delta_AICc",
        "rel_impr",
        "raw_gap_pre_shift",
        "post_shift_gap",
        # Backward compatibility: emit legacy columns for one release.
        "slope_gap",
        "violations",
        "time_pen",
        "level_shift_applied",
        "b_pen_left",
        "b_pen_right",
        "base_aicc_sum",
        "gap_pen",
        "slope_pen",
        "mono_pen",
        "time_pen_comp",
        "b_pen_left_comp",
        "b_pen_right_comp",
        "penalized_score",
        "rejected_flag",
        "reject_reason",
        "accept_reason",
        "tests_fired_json",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_csv_row())


def collect_split_metrics(node: SegmentNode) -> List[Tuple[float, float, float]]:
    splits: List[Tuple[float, float, float]] = []
    if node.split is not None:
        splits.append((node.split.split_time, node.split.post_shift_gap, node.split.slope_gap))
        for child in node.children:
            splits.extend(collect_split_metrics(child))
    return splits


def create_plots(
    outdir: Path,
    dataset_name: str,
    time: np.ndarray,
    values: np.ndarray,
    preds: np.ndarray,
    corrected: np.ndarray,
    root: SegmentNode,
    cfg: Config,
) -> Dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    plots: Dict[str, str] = {}

    splits = collect_split_metrics(root)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(time, values, "o", label="Observed", alpha=0.6)
    ax.plot(time, preds, "-", label="Piecewise fit (raw)", linewidth=2)
    if np.any(corrected != preds):
        ax.plot(time, corrected, "--", label="Isotonic fit")
    for split_time, gap, slope_gap in splits:
        ax.axvline(split_time, color="red", linestyle="--", alpha=0.6)
        ax.text(
            split_time,
            ax.get_ylim()[0],
            f"post_gap={gap:.4f}\nslope={slope_gap:.5f}",
            rotation=90,
            va="bottom",
            ha="right",
            fontsize=8,
            color="red",
        )
    ax.set_xlabel("Time")
    ax.set_ylabel("Moisture ratio")
    ax.set_title(f"Piecewise fit for {dataset_name}")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path_fit = outdir / f"{dataset_name}_fit.png"
    fig.savefig(path_fit, dpi=200)
    plt.close(fig)
    plots["fit"] = str(path_fit)

    residuals = values - preds
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(time, residuals, "o", label="Residuals", alpha=0.6)
    smooth = lowess(residuals, time, frac=float(np.clip(cfg.lowess_frac_root, 0.01, 0.99)), return_sorted=False)
    ax.plot(time, smooth, "-", label="LOWESS")
    for split_time, _, _ in splits:
        ax.axvline(split_time, color="red", linestyle=":", alpha=0.5)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xlabel("Time")
    ax.set_ylabel("Residual")
    ax.set_title("Residual diagnostics")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path_resid = outdir / f"{dataset_name}_residuals.png"
    fig.savefig(path_resid, dpi=200)
    plt.close(fig)
    plots["residuals"] = str(path_resid)

    diffs = np.diff(preds)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(time[1:], diffs, "-", label="Δŷ")
    ax.axhline(0.0, color="black", linewidth=1)
    for split_time, _, _ in splits:
        ax.axvline(split_time, color="red", linestyle=":", alpha=0.5)
    ax.set_xlabel("Time")
    ax.set_ylabel("Forward difference")
    ax.set_title("Monotonicity diagnostics")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path_mono = outdir / f"{dataset_name}_monotonic.png"
    fig.savefig(path_mono, dpi=200)
    plt.close(fig)
    plots["monotonic"] = str(path_mono)

    return plots

CLI_FIELDS = [
    "data_dir",
    "outdir",
    "max_splits",
    "max_depth",
    "min_points_root",
    "min_points_leaf",
    "candidate_grid_count",
    "lowess_frac_min",
    "lowess_frac_max",
    "min_fraction",
    "max_fraction",
    "min_rel_improvement",
    "allow_per_segment_model",
    "join_penalty",
    "slope_penalty",
    "shape_penalty_mono",
    "max_allowed_gap",
    "max_allowed_slope_gap",
    "max_allowed_gap_eps",
    "max_allowed_slope_eps",
    "reject_nonmonotone",
    "total_gap_budget",
    "time_penalty",
    "lowess_frac_root",
    "monotonic_eps",
    "lowess_points",
    "iso_rmse_tol",
    "max_iter",
    "seed",
    "probe_better_child",
    "lambda_b",
    "page_fallback_eps",
    "log_level",
]


def _config_to_dict(cfg: Config) -> Dict[str, object]:
    payload: Dict[str, object] = {}
    for field_name in CLI_FIELDS:
        value = getattr(cfg, field_name)
        if isinstance(value, Path):
            payload[field_name] = str(value)
        else:
            payload[field_name] = value
    return payload


def _get_version() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            cwd=_PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def process_dataset(path: Path, cfg: Config) -> Dict[str, object]:
    logger = logging.getLogger(__name__)
    result = load_and_preprocess(path)
    time = result.time_min.astype(float)
    values = result.mr_iso.astype(float)
    if time.size < cfg.min_points_root:
        logger.warning(
            "Dataset %s has only %d points (< min_points_root=%d); recursion disabled.",
            path.name,
            time.size,
            cfg.min_points_root,
        )
    cache = FitCache()
    root_fit = compute_unsplit_fit(0, time.size, time, values, cache, cfg)
    if root_fit is None:
        raise RuntimeError(f"Unable to fit baseline model for {path}")
    root = SegmentNode(node_id="0", start=0, end=time.size, depth=0, fit=root_fit)
    candidate_records: List[CandidateRecord] = []
    budget = BudgetState()
    if time.size >= cfg.min_points_root:
        recurse_node(root, time, values, cache, cfg, path.stem, budget, candidate_records)

    for node in gather_nodes(root):
        update_node_diagnostics(node, time, values, cfg)

    preds, corrected, violations, iso_used = reconstruct_predictions(root, time, values, cfg)
    rmse_raw = float(np.sqrt(np.mean((preds - values) ** 2)))
    rmse_corrected = float(np.sqrt(np.mean((corrected - values) ** 2)))
    leaves = [node for node in gather_nodes(root) if node.is_leaf()]
    leaf_aicc = sum(leaf.fit.aicc for leaf in leaves)
    delta_total = root.fit.aicc - leaf_aicc
    rel_total = (root.fit.aicc - leaf_aicc) / max(abs(root.fit.aicc), 1e-9)
    correction_mag = float(np.max(np.abs(corrected - preds)))

    dataset_outdir = cfg.outdir / path.stem
    plots = create_plots(dataset_outdir / "plots", path.stem, time, values, preds, corrected, root, cfg)
    candidate_log_path = dataset_outdir / "candidate_log.csv"
    write_candidate_log(candidate_log_path, candidate_records)

    config_dict = _config_to_dict(cfg)
    config_digest = hashlib.sha1(json.dumps(config_dict, sort_keys=True).encode("utf-8")).hexdigest()
    version = _get_version()

    summary = {
        "schema_version": SCHEMA_VERSION,
        "file": str(path),
        "config": config_dict,
        "config_digest": config_digest,
        "version": version,
        "seed": cfg.seed,
        "unsplit": root.fit.to_summary(),
        "nodes": [node.to_dict() for node in gather_nodes(root)],
        "metrics": {
            "sum_gaps": budget.sum_gaps,
            "violations_total": violations,
            "delta_AICc_total": delta_total,
            "rel_impr_total": rel_total,
            "correction_magnitude": correction_mag,
            "rmse_raw": rmse_raw,
            "rmse_corrected": rmse_corrected,
            "rmse_gain": float(rmse_raw - rmse_corrected),
            "isotonic_used": bool(iso_used),
            "splits_used": budget.splits_used,
            "n_leaves": len(leaves),
            "levels_splits": {str(depth): count for depth, count in budget.levels_splits.items()},
        },
        "plots": plots,
        "candidate_log": str(candidate_log_path),
    }

    summary_path = dataset_outdir / "tree_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    # Leave duplicate argument definitions as hard errors to expose configuration issues.
    parser = argparse.ArgumentParser(
        description="Recursive piecewise Page/Midilli splitter with continuity and monotonicity controls."
    )
    parser.add_argument("--data-dir", default="data", help="Directory containing input CSV files.")
    parser.add_argument("--outdir", default="outputs/piecewise_recursive", help="Directory to store outputs.")
    parser.add_argument("--max-splits", type=int, default=2, help="Maximum number of splits across the tree.")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum recursion depth (root depth is 0).")
    parser.add_argument(
        "--min-points-root",
        type=int,
        default=30,
        help="Minimum points required at the root segment (must be at least twice the leaf requirement).",
    )
    parser.add_argument(
        "--min-points-leaf",
        type=int,
        default=15,
        help="Minimum points required for child segments; root defaults satisfy >= 2x this value.",
    )
    parser.add_argument("--candidate-grid-count", type=int, default=400, help="Uniform grid candidate count.")
    parser.add_argument("--lowess-frac-min", type=float, default=0.10, help="Minimum LOWESS fraction for candidates.")
    parser.add_argument("--lowess-frac-max", type=float, default=0.30, help="Maximum LOWESS fraction for candidates.")
    parser.add_argument("--min-fraction", type=float, default=0.05, help="Minimum fractional position for splits.")
    parser.add_argument("--max-fraction", type=float, default=0.95, help="Maximum fractional position for splits.")
    parser.add_argument("--min-rel-improvement", type=float, default=0.002, help="Minimum relative AICc improvement required.")
    parser.add_argument(
        "--allow-per-segment-model",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Evaluate Page vs Midilli per segment and choose the lower AICc.",
    )
    parser.add_argument("--join-penalty", type=float, default=8.0, help="Penalty on squared join gaps.")
    parser.add_argument("--slope-penalty", type=float, default=2.0, help="Penalty on squared slope gaps.")
    parser.add_argument("--shape-penalty-mono", type=float, default=8.0, help="Penalty per monotonicity violation.")
    parser.add_argument("--max-allowed-gap", type=float, default=0.01, help="Maximum allowed join gap.")
    parser.add_argument(
        "--max-allowed-slope-gap", type=float, default=0.003, help="Maximum allowed slope discontinuity."
    )
    parser.add_argument(
        "--max-allowed-gap-eps",
        type=float,
        default=1e-12,
        help="Tolerance added when comparing against the maximum allowed join gap.",
    )
    parser.add_argument(
        "--max-allowed-slope-eps",
        type=float,
        default=1e-12,
        help="Tolerance added when comparing against the maximum allowed slope discontinuity.",
    )
    parser.add_argument("--total-gap-budget", type=float, default=0.05, help="Total allowed sum of join gaps.")
    parser.add_argument("--time-penalty", type=float, default=0.05, help="Penalty weight for split location prior.")
    parser.add_argument("--lowess-frac-root", type=float, default=0.18, help="LOWESS fraction at the root node.")
    parser.add_argument("--max-iter", type=int, default=4000, help="Maximum iterations for curve fitting.")
    parser.add_argument("--seed", type=int, default=1337, help="Deterministic RNG seed.")
    parser.add_argument(
        "--reject-nonmonotone",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reject splits that produce monotonicity violations.",
    )
    
    parser.add_argument(
        "--probe-better-child",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recurse into the higher-evidence child before probing the other side.",
    )
    parser.add_argument(
        "--lambda-b",
        type=float,
        default=20.0,
        help="Penalty weight applied when |b| exceeds 1e-3 for Midilli segments.",
    )
    parser.add_argument(
        "--page-fallback-eps",
        type=float,
        default=0.2,
        help="AICc tolerance for preferring Page when Midilli hits parameter bounds.",
    )
    parser.add_argument(
        "--monotonic-eps",
        type=float,
        default=5e-6,
        help="Numerical tolerance used when checking for monotonicity violations.",
    )
    parser.add_argument(
        "--lowess-points",
        type=int,
        default=5,
        help="Number of LOWESS fractions evaluated when selecting candidate smoothing levels.",
    )
    parser.add_argument(
        "--iso-rmse-tol",
        type=float,
        default=1e-6,
        help="Only keep isotonic correction if RMSE improves by at least this tolerance.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level (e.g., INFO, DEBUG).")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(levelname)s:%(message)s")

    cfg = Config(
        data_dir=Path(args.data_dir).expanduser().resolve(),
        outdir=Path(args.outdir).expanduser().resolve(),
        max_splits=args.max_splits,
        max_depth=args.max_depth,
        min_points_root=args.min_points_root,
        min_points_leaf=args.min_points_leaf,
        candidate_grid_count=args.candidate_grid_count,
        lowess_frac_min=args.lowess_frac_min,
        lowess_frac_max=args.lowess_frac_max,
        min_fraction=args.min_fraction,
        max_fraction=args.max_fraction,
        min_rel_improvement=args.min_rel_improvement,
        allow_per_segment_model=bool(args.allow_per_segment_model),
        join_penalty=args.join_penalty,
        slope_penalty=args.slope_penalty,
        shape_penalty_mono=args.shape_penalty_mono,
        max_allowed_gap=args.max_allowed_gap,
        max_allowed_slope_gap=args.max_allowed_slope_gap,
        max_allowed_gap_eps=args.max_allowed_gap_eps,
        max_allowed_slope_eps=args.max_allowed_slope_eps,
        reject_nonmonotone=bool(args.reject_nonmonotone),
        total_gap_budget=args.total_gap_budget,
        time_penalty=args.time_penalty,
        lowess_frac_root=args.lowess_frac_root,
        max_iter=args.max_iter,
        seed=args.seed,
        log_level=str(args.log_level),
        probe_better_child=bool(args.probe_better_child),
        lambda_b=args.lambda_b,
        page_fallback_eps=args.page_fallback_eps,
        monotonic_eps=args.monotonic_eps,
        lowess_points=args.lowess_points,
        iso_rmse_tol=args.iso_rmse_tol,
    )

    np.random.seed(cfg.seed)

    if not cfg.data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {cfg.data_dir}")
    cfg.outdir.mkdir(parents=True, exist_ok=True)

    csv_paths = sorted(p for p in cfg.data_dir.glob("*.csv") if p.is_file())
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in {cfg.data_dir}")

    summaries = []
    for path in csv_paths:
        logging.info("Processing %s", path.name)
        summary = process_dataset(path, cfg)
        summaries.append(summary)

    index_payload = {
        "config": _config_to_dict(cfg),
        "files": [str(path) for path in csv_paths],
        "summaries": summaries,
    }
    index_path = cfg.outdir / "summary_index.json"
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
