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
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, cast

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


_GLOBAL_RNG: Optional[np.random.Generator] = None


@contextmanager
def _scipy_random_state() -> Iterator[None]:
    if _GLOBAL_RNG is None:
        yield
        return
    state = np.random.get_state()
    seed_value = int(_GLOBAL_RNG.integers(0, 2**32 - 1))
    np.random.seed(seed_value)
    try:
        yield
    finally:
        np.random.set_state(state)


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
    monotonic_hardcap: int
    total_gap_budget: float
    time_penalty: float
    lowess_frac_root: float
    max_iter: int
    seed: int
    log_level: str
    probe_better_child: bool
    probe_better_child_passes: int
    lambda_b: float
    page_fallback_eps: float
    midbody_aicc_tolerance: float
    midilli_b_softbound: float
    export_leaves_csv: bool
    no_plots: bool
    candidate_min_spacing: int = 4
    max_allowed_gap_eps: float = 1e-12
    max_allowed_slope_eps: float = 1e-12
    monotonic_eps: float = 5e-6
    lowess_points: int = 5
    iso_rmse_tol: float = 1e-6


@dataclass
class FitStats:
    family: str
    params: Dict[str, float]
    initial_guess: Dict[str, float]
    rss: float
    rmse: float
    aicc: float
    n_obs: int
    saturates_bound: bool
    predictions: np.ndarray
    hit_bounds: Dict[str, bool]
    bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None

    def to_summary(self) -> Dict[str, object]:
        return {
            "family": self.family,
            "params": {key: float(value) for key, value in self.params.items()},
            "initial_guess": {key: float(value) for key, value in self.initial_guess.items()},
            "AICc": float(self.aicc),
            "RMSE": float(self.rmse),
            "n_obs": int(self.n_obs),
            "hit_bounds": {key: bool(value) for key, value in self.hit_bounds.items()},
            "bounds": [bound.tolist() for bound in self.bounds] if self.bounds is not None else None,
        }


@dataclass
class SplitInfo:
    split_index: int
    split_time: float
    raw_gap_pre_shift: float
    post_join_gap_adj: float
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
    right_time_shift_attempted: float


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
                    "post_join_gap_adj": float(self.split.post_join_gap_adj),
                    "raw_gap_pre_shift": float(self.split.raw_gap_pre_shift),
                    # Backward compatibility: emit legacy keys for one release.
                    "slope_gap": float(self.split.slope_gap),
                    "penalized_score": float(self.split.penalized_score),
                    "time_penalty": float(self.split.time_penalty),
                    "delta_aicc": float(self.split.delta_aicc),
                    "rel_improvement": float(self.split.rel_improvement),
                    "mono_violations": int(self.split.violations),
                    "level_shift_applied": float(self.split.level_shift_applied),
                    "right_time_shift_attempted": float(
                        self.split.right_time_shift_attempted
                    ),
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
    guess_left: Dict[str, float]
    aicc_left: float
    rmse_left: float
    hit_bounds_left: Dict[str, bool]
    model_left_reason: str
    model_right: str
    params_right: Dict[str, float]
    guess_right: Dict[str, float]
    aicc_right: float
    rmse_right: float
    hit_bounds_right: Dict[str, bool]
    model_right_reason: str
    aicc_unsplit: float
    delta_aicc: float
    rel_improvement: float
    raw_gap_pre_shift: float
    post_join_gap_adj: float
    slope_gap: float
    slope_residual_after_shift: float
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
    right_time_shift_attempted: float
    k0_left: float
    n0_left: float
    b0_left: float
    k0_right: float
    n0_right: float
    b0_right: float
    k_dist_left: float
    n_dist_left: float
    b_dist_left: float
    k_dist_right: float
    n_dist_right: float
    b_dist_right: float

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
            "guess_left_json": json.dumps(self.guess_left, sort_keys=True),
            "AICc_left": self.aicc_left,
            "RMSE_left": self.rmse_left,
            "hit_bounds_left_json": json.dumps(self.hit_bounds_left, sort_keys=True),
            "model_left_reason": self.model_left_reason,
            "model_right": self.model_right,
            "params_right_json": json.dumps(self.params_right, sort_keys=True),
            "guess_right_json": json.dumps(self.guess_right, sort_keys=True),
            "AICc_right": self.aicc_right,
            "RMSE_right": self.rmse_right,
            "hit_bounds_right_json": json.dumps(self.hit_bounds_right, sort_keys=True),
            "model_right_reason": self.model_right_reason,
            "AICc_unsplit": self.aicc_unsplit,
            "delta_AICc": self.delta_aicc,
            "rel_impr": self.rel_improvement,
            "raw_gap_pre_shift": self.raw_gap_pre_shift,
            "post_join_gap_adj": self.post_join_gap_adj,
            "slope_gap": self.slope_gap,
            "slope_residual_after_shift": self.slope_residual_after_shift,
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
            "right_time_shift_attempted": self.right_time_shift_attempted,
            "k0_left": self.k0_left,
            "n0_left": self.n0_left,
            "b0_left": self.b0_left,
            "k0_right": self.k0_right,
            "n0_right": self.n0_right,
            "b0_right": self.b0_right,
            "k_dist_left": self.k_dist_left,
            "n_dist_left": self.n_dist_left,
            "b_dist_left": self.b_dist_left,
            "k_dist_right": self.k_dist_right,
            "n_dist_right": self.n_dist_right,
            "b_dist_right": self.b_dist_right,
        }


@dataclass
class CandidateMeta:
    node_id: str
    raw_grid: int
    raw_lowess: int
    union: int
    spaced: int
    feasible: int


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
DEFAULT_MIDILLI_SOFT_BOUND = 1e-3

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
SCHEMA_VERSION = "2.1.0"
SCHEMA_NOTES = [
    "2.1.0: Added candidate meta logs, slope residual metrics, runtime reporting, and new CLI guardrails.",
]


def _initial_guess_page(time: np.ndarray, values: np.ndarray) -> Tuple[float, float]:
    clipped = np.clip(values, 1e-6, 0.999999)
    with np.errstate(divide="ignore"):
        transformed = -np.log(clipped)
    mask = np.isfinite(transformed) & np.isfinite(time) & (time > 0)
    if np.count_nonzero(mask) >= 2 and np.all(transformed[mask] > 0):
        log_t = np.log(time[mask])
        log_transformed = np.log(transformed[mask])
        try:
            slope, intercept = np.polyfit(log_t, log_transformed, deg=1)
        except (np.linalg.LinAlgError, ValueError):
            slope, intercept = math.nan, math.nan
        if math.isfinite(slope) and math.isfinite(intercept):
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
        try:
            coef = np.polyfit(time[-tail:], values[-tail:], deg=1)
        except (np.linalg.LinAlgError, ValueError):
            coef = [0.0, 0.0]
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
    guess_payload = {"k0": float(guess[0]), "n0": float(guess[1]), "b0": 0.0}
    try:
        with _scipy_random_state():
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
        initial_guess=guess_payload,
        bounds=PAGE_BOUNDS,
    )


def _fit_midilli(
    time: np.ndarray,
    values: np.ndarray,
    max_iter: int,
    bounds: Tuple[np.ndarray, np.ndarray],
) -> Optional[FitStats]:
    guess = _initial_guess_midilli(time, values, bounds)
    guess_payload = {"k0": float(guess[0]), "n0": float(guess[1]), "b0": float(guess[2])}

    try:
        with _scipy_random_state():
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
        initial_guess=guess_payload,
        bounds=bounds,
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
    if (not is_head) and (not is_tail):
        lb, ub = MIDILLI_BOUNDS_BODY
        ub_relaxed = ub.copy()
        ub_relaxed[1] = 2.40
        mid_bounds = (lb, ub_relaxed)

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

    if (not is_head) and (not is_tail) and cfg.allow_per_segment_model:
        if abs(page.aicc - mid.aicc) <= cfg.midbody_aicc_tolerance:
            return (page, "page_midbody_tie")

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
    lowess_cache: Dict[Tuple[int, int, float], np.ndarray],
) -> Tuple[List[int], CandidateMeta]:
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
    raw_grid = len(grid_indices)
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
        cache_key = (start, end, round(frac_clamped, 6))
        if cache_key in lowess_cache:
            smoothed = lowess_cache[cache_key]
        else:
            smoothed = lowess(residuals, time[start:end], frac=frac_clamped, return_sorted=False)
            lowess_cache[cache_key] = smoothed
        for idx in _find_lowess_extrema(residuals, smoothed):
            candidate = start + idx
            lowess_indices.add(candidate)
    raw_lowess = len(lowess_indices)
    union_candidates = sorted(grid_indices.union(lowess_indices))
    union_count = len(union_candidates)
    clamped_candidates = sorted({int(np.clip(idx, allowed_min, allowed_max)) for idx in union_candidates})
    min_spacing = max(1, int(cfg.candidate_min_spacing))
    spaced_candidates: List[int] = []
    for candidate in clamped_candidates:
        if not spaced_candidates or candidate - spaced_candidates[-1] >= min_spacing:
            spaced_candidates.append(candidate)
    spaced_count = len(spaced_candidates)
    feasible: List[int] = []
    for split_idx in spaced_candidates:
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
    meta = CandidateMeta(
        node_id=node.node_id,
        raw_grid=raw_grid,
        raw_lowess=raw_lowess,
        union=union_count,
        spaced=spaced_count,
        feasible=len(feasible),
    )
    return feasible, meta


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
    right_time_shift: float = 0.0,
) -> np.ndarray:
    left_time = time[start : split_idx + 1]
    right_time = time[split_idx + 1 : end]
    left_pred = _segment_base_predictions(left, left_time)
    right_pred = _segment_base_predictions(right, right_time, right_time_shift)
    if right_pred.size:
        right_pred = right_pred + level_shift
    return np.concatenate([left_pred, right_pred])


def _post_join_gap_after_adjustments(
    left_fit: FitStats,
    right_fit: FitStats,
    split_time: float,
    first_right_time: float,
    right_time_shift: float,
) -> Tuple[float, float, float]:
    vL_split, sL_split = _model_value_and_slope(left_fit, split_time)
    vR_at_split_after_shift, sR_split = _model_value_and_slope(
        right_fit, max(split_time + right_time_shift, 1e-8)
    )
    level_shift = vL_split - vR_at_split_after_shift

    vR_first_after_shift, _ = _model_value_and_slope(
        right_fit, max(first_right_time + right_time_shift, 1e-8)
    )
    post_join_gap = abs(vL_split - (vR_first_after_shift + level_shift))

    slope_gap = abs(sL_split - sR_split)
    return post_join_gap, slope_gap, level_shift


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
    bound = max(cfg.midilli_b_softbound, 0.0)
    excess = max(abs(fit.params.get("b", 0.0)) - bound, 0.0)
    if excess <= 0:
        return 0.0
    return cfg.lambda_b * (excess**2)


def _param_distance_to_bounds(fit: FitStats, param: str) -> float:
    if fit.bounds is None or param not in fit.params:
        return float("nan")
    index_map = {"k": 0, "n": 1, "b": 2}
    idx = index_map.get(param)
    if idx is None:
        return float("nan")
    lower_bounds, upper_bounds = fit.bounds
    if idx >= lower_bounds.size or idx >= upper_bounds.size:
        return float("nan")
    value = fit.params.get(param)
    if value is None:
        return float("nan")
    return float(min(value - float(lower_bounds[idx]), float(upper_bounds[idx]) - value))


def score_candidate(
    node: SegmentNode,
    split_idx: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
    dataset_name: str,
    budget_sum_gaps: float,
    current_best: float,
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
            guess_left=left_stats.initial_guess if left_stats else {},
            aicc_left=left_stats.aicc if left_stats else float("nan"),
            rmse_left=left_stats.rmse if left_stats else float("nan"),
            hit_bounds_left=left_stats.hit_bounds if left_stats else {},
            model_left_reason=left_reason,
            model_right=right_stats.family if right_stats else "",
            params_right=right_stats.params if right_stats else {},
            guess_right=right_stats.initial_guess if right_stats else {},
            aicc_right=right_stats.aicc if right_stats else float("nan"),
            rmse_right=right_stats.rmse if right_stats else float("nan"),
            hit_bounds_right=right_stats.hit_bounds if right_stats else {},
            model_right_reason=right_reason,
            aicc_unsplit=node.fit.aicc,
            delta_aicc=float("nan"),
            rel_improvement=float("nan"),
            raw_gap_pre_shift=float("nan"),
            post_join_gap_adj=float("nan"),
            slope_gap=float("nan"),
            slope_residual_after_shift=float("nan"),
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
            right_time_shift_attempted=float("nan"),
            k0_left=float("nan"),
            n0_left=float("nan"),
            b0_left=float("nan"),
            k0_right=float("nan"),
            n0_right=float("nan"),
            b0_right=float("nan"),
            k_dist_left=float("nan"),
            n_dist_left=float("nan"),
            b_dist_left=float("nan"),
            k_dist_right=float("nan"),
            n_dist_right=float("nan"),
            b_dist_right=float("nan"),
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

    left_guess = left_stats.initial_guess
    right_guess = right_stats.initial_guess
    k0_left = float(left_guess.get("k0", float("nan")))
    n0_left = float(left_guess.get("n0", float("nan")))
    b0_left = float(left_guess.get("b0", float("nan")))
    k0_right = float(right_guess.get("k0", float("nan")))
    n0_right = float(right_guess.get("n0", float("nan")))
    b0_right = float(right_guess.get("b0", float("nan")))

    k_dist_left = _param_distance_to_bounds(left_stats, "k")
    n_dist_left = _param_distance_to_bounds(left_stats, "n")
    b_dist_left = _param_distance_to_bounds(left_stats, "b")
    k_dist_right = _param_distance_to_bounds(right_stats, "k")
    n_dist_right = _param_distance_to_bounds(right_stats, "n")
    b_dist_right = _param_distance_to_bounds(right_stats, "b")

    if base > current_best:
        rejected = True
        reason = "dominated"
        tests.append("dominated")
        record = CandidateRecord(
            file=dataset_name,
            node_id=node.node_id,
            t_split=float(time[split_idx]),
            t_idx=split_idx,
            left_n=left_n,
            right_n=right_n,
            model_left=left_stats.family,
            params_left=left_stats.params,
            guess_left=left_stats.initial_guess,
            aicc_left=left_stats.aicc,
            rmse_left=left_stats.rmse,
            hit_bounds_left=left_stats.hit_bounds,
            model_left_reason=left_reason,
            model_right=right_stats.family,
            params_right=right_stats.params,
            guess_right=right_stats.initial_guess,
            aicc_right=right_stats.aicc,
            rmse_right=right_stats.rmse,
            hit_bounds_right=right_stats.hit_bounds,
            model_right_reason=right_reason,
            aicc_unsplit=node.fit.aicc,
            delta_aicc=delta_aicc,
            rel_improvement=rel_impr,
            raw_gap_pre_shift=float("nan"),
            post_join_gap_adj=float("nan"),
            slope_gap=float("nan"),
            slope_residual_after_shift=float("nan"),
            violations=0,
            time_pen=0.0,
            level_shift_applied=0.0,
            b_pen_left=0.0,
            b_pen_right=0.0,
            base_aicc_sum=base,
            gap_pen=0.0,
            slope_pen=0.0,
            mono_pen=0.0,
            time_pen_comp=0.0,
            b_pen_left_comp=0.0,
            b_pen_right_comp=0.0,
            penalized_score=base,
            rejected_flag=True,
            reject_reason=reason,
            accept_reason=accept_reason,
            tests_fired=tests,
            right_time_shift_attempted=0.0,
            k0_left=k0_left,
            n0_left=n0_left,
            b0_left=b0_left,
            k0_right=k0_right,
            n0_right=n0_right,
            b0_right=b0_right,
            k_dist_left=k_dist_left,
            n_dist_left=n_dist_left,
            b_dist_left=b_dist_left,
            k_dist_right=k_dist_right,
            n_dist_right=n_dist_right,
            b_dist_right=b_dist_right,
        )
        return None, record

    right_time = float(time[split_idx + 1])
    value_left, slope_left = _model_value_and_slope(left_stats, split_time)
    value_right_raw, slope_right_raw = _model_value_and_slope(right_stats, right_time)
    raw_gap_pre_shift = abs(value_left - value_right_raw)

    max_shift = max(right_time - split_time, 0.0)
    right_time_shift_attempted = 0.0
    if math.isfinite(slope_left) and math.isfinite(slope_right_raw) and max_shift > 0.0:
        shift = _solve_time_shift_for_slope_match(
            right_stats, right_time, slope_left, max_shift
        )
        if math.isfinite(shift) and shift != 0.0:
            right_time_shift_attempted = float(np.clip(shift, 0.0, max_shift))

    post_join_gap_adj, slope_gap, level_shift = _post_join_gap_after_adjustments(
        left_stats, right_stats, split_time, right_time, right_time_shift_attempted
    )
    slope_residual_after_shift = abs(
        _segment_slope_at(right_stats, max(right_time + right_time_shift_attempted, 1e-8))
        - slope_left
    )
    time_pen = _time_penalty(split_time, node, time, cfg)
    combined_preds = _combine_predictions(
        left_stats,
        right_stats,
        start,
        split_idx,
        end,
        time,
        level_shift,
        right_time_shift_attempted,
    )
    violations = _count_monotonic_violations(combined_preds, cfg.monotonic_eps)

    if not math.isfinite(base) or not math.isfinite(raw_gap_pre_shift) or not math.isfinite(slope_gap):
        rejected = True
        reason = "nan_metric"
        tests.append("nan_metric")
    if post_join_gap_adj > cfg.max_allowed_gap + cfg.max_allowed_gap_eps:
        rejected = True
        reason = "gap_limit"
        tests.append("gap_limit")
    if slope_gap > cfg.max_allowed_slope_gap + cfg.max_allowed_slope_eps:
        rejected = True
        reason = "slope_limit"
        tests.append("slope_limit")
    if cfg.monotonic_hardcap >= 0 and violations > cfg.monotonic_hardcap:
        rejected = True
        reason = "monotonic_hardcap"
        tests.append("monotonic_hardcap")
    elif cfg.reject_nonmonotone and violations > 0:
        rejected = True
        reason = "nonmonotone"
        tests.append("nonmonotone")
    if rel_impr < cfg.min_rel_improvement:
        rejected = True
        reason = "rel_improvement"
        tests.append("rel_improvement")
    if budget_sum_gaps + post_join_gap_adj > cfg.total_gap_budget + cfg.max_allowed_gap_eps:
        rejected = True
        reason = "gap_budget"
        tests.append("gap_budget")

    b_pen_left = _b_penalty(left_stats, cfg)
    b_pen_right = _b_penalty(right_stats, cfg)

    gap_pen_component = (
        cfg.join_penalty * (post_join_gap_adj**2) if math.isfinite(post_join_gap_adj) else float("nan")
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
        "post_join_gap_adj": post_join_gap_adj,
        "right_time_shift_attempted": right_time_shift_attempted,
        "slope_residual_after_shift": slope_residual_after_shift,
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
            post_join_gap_adj,
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
            right_time_shift_attempted,
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
        guess_left=left_stats.initial_guess,
        aicc_left=left_stats.aicc,
        rmse_left=left_stats.rmse,
        hit_bounds_left=left_stats.hit_bounds,
        model_left_reason=left_reason,
        model_right=right_stats.family,
        params_right=right_stats.params,
        guess_right=right_stats.initial_guess,
        aicc_right=right_stats.aicc,
        rmse_right=right_stats.rmse,
        hit_bounds_right=right_stats.hit_bounds,
        model_right_reason=right_reason,
        aicc_unsplit=node.fit.aicc,
        delta_aicc=delta_aicc,
        rel_improvement=rel_impr,
        raw_gap_pre_shift=raw_gap_pre_shift,
        post_join_gap_adj=post_join_gap_adj,
        slope_gap=slope_gap,
        slope_residual_after_shift=slope_residual_after_shift,
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
        right_time_shift_attempted=right_time_shift_attempted,
        k0_left=k0_left,
        n0_left=n0_left,
        b0_left=b0_left,
        k0_right=k0_right,
        n0_right=n0_right,
        b0_right=b0_right,
        k_dist_left=k_dist_left,
        n_dist_left=n_dist_left,
        b_dist_left=b_dist_left,
        k_dist_right=k_dist_right,
        n_dist_right=n_dist_right,
        b_dist_right=b_dist_right,
        slope_residual_after_shift=slope_residual_after_shift,
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
    n_points = max(residuals_child.size, 1)
    amp_norm = (amplitude / sigma) / math.sqrt(float(n_points))
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
    used_newton = True
    for _ in range(6):
        slope_here = _segment_slope_at(fit, current_time)
        if not math.isfinite(slope_here):
            used_newton = False
            break
        error = slope_here - target_slope
        if abs(error) <= tol:
            break
        step_radius = min(max_shift, max(current_time * 0.5, 1e-6))
        left_time = max(current_time - step_radius, 1e-8)
        right_time = min(current_time + step_radius, base_time + max_shift)
        slope_left = _segment_slope_at(fit, left_time)
        slope_right = _segment_slope_at(fit, right_time)
        denom = right_time - left_time
        if denom <= 0:
            used_newton = False
            break
        slope_prime = (slope_right - slope_left) / denom
        if not math.isfinite(slope_prime) or abs(slope_prime) < 1e-12:
            used_newton = False
            break
        step = error / slope_prime
        proposed_time = current_time - step
        if proposed_time < base_time or proposed_time > base_time + max_shift:
            used_newton = False
            break
        current_time = proposed_time
        delta = current_time - base_time
        if abs(step) <= tol:
            break
    final_time = current_time
    if not used_newton:
        left_shift = 0.0
        right_shift = max_shift
        best_shift = 0.0
        best_error = abs(initial_slope - target_slope)
        slope_left_val = initial_slope
        slope_right_val = _segment_slope_at(fit, base_time + max_shift)
        if not math.isfinite(slope_right_val):
            slope_right_val = slope_left_val
        right_error = abs(slope_right_val - target_slope)
        if right_error < best_error:
            best_error = right_error
            best_shift = max_shift
        for _ in range(8):
            mid_shift = 0.5 * (left_shift + right_shift)
            mid_time = base_time + mid_shift
            slope_mid = _segment_slope_at(fit, mid_time)
            if not math.isfinite(slope_mid):
                break
            error_mid = abs(slope_mid - target_slope)
            if error_mid < best_error:
                best_error = error_mid
                best_shift = mid_shift
            left_error = abs(slope_left_val - target_slope)
            right_error = abs(slope_right_val - target_slope)
            if left_error <= right_error:
                right_shift = mid_shift
                slope_right_val = slope_mid
            else:
                left_shift = mid_shift
                slope_left_val = slope_mid
        final_time = base_time + best_shift
        delta = best_shift
    final_slope = _segment_slope_at(fit, final_time)
    if not math.isfinite(final_slope):
        return 0.0
    if abs(final_slope - target_slope) >= abs(initial_slope - target_slope):
        return 0.0
    return max(0.0, min(delta, max_shift))


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
        "mono_violations_seg": int(_count_monotonic_violations(base_pred, cfg.monotonic_eps)),
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
    candidate_meta: List[CandidateMeta],
    lowess_cache: Dict[Tuple[int, int, float], np.ndarray],
    is_probe: bool = False,
    probe_passes_remaining: int = 0,
) -> None:
    if node.depth >= cfg.max_depth:
        return
    if budget.splits_used >= cfg.max_splits:
        return
    candidates, meta = generate_candidates(node, time, values, cfg, lowess_cache)
    candidate_meta.append(meta)
    if not candidates:
        return
    best_info: Optional[SplitInfo] = None
    best_score = float("inf")
    for idx in candidates:
        info, record = score_candidate(
            node,
            idx,
            time,
            values,
            cache,
            cfg,
            dataset_name,
            budget.sum_gaps,
            best_score,
        )
        candidate_records.append(record)
        if info is not None and info.penalized_score < best_score:
            best_info = info
            best_score = info.penalized_score
    if best_info is None:
        return
    node.split = best_info
    split_idx = best_info.split_index
    right_time_shift = float(best_info.right_time_shift_attempted)
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
    budget.sum_gaps += best_info.post_join_gap_adj
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
    if is_probe and probe_passes_remaining <= 0:
        return

    for idx, child in enumerate(ordered_children):
        if budget.splits_used >= cfg.max_splits:
            break
        if child.depth >= cfg.max_depth:
            continue
        child_probe = cfg.probe_better_child and idx > 0
        if is_probe:
            child_passes = max(probe_passes_remaining - 1, 0)
        else:
            child_passes = cfg.probe_better_child_passes
        if child_probe:
            child_passes = max(child_passes - 1, 0)
        recurse_node(
            child,
            time,
            values,
            cache,
            cfg,
            dataset_name,
            budget,
            candidate_records,
            candidate_meta,
            lowess_cache,
            is_probe=child_probe,
            probe_passes_remaining=child_passes,
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
        "guess_left_json",
        "AICc_left",
        "RMSE_left",
        "hit_bounds_left_json",
        "model_left_reason",
        "model_right",
        "params_right_json",
        "guess_right_json",
        "AICc_right",
        "RMSE_right",
        "hit_bounds_right_json",
        "model_right_reason",
        "AICc_unsplit",
        "delta_AICc",
        "rel_impr",
        "raw_gap_pre_shift",
        "post_join_gap_adj",
        "slope_gap",
        "slope_residual_after_shift",
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
        "right_time_shift_attempted",
        "k0_left",
        "n0_left",
        "b0_left",
        "k0_right",
        "n0_right",
        "b0_right",
        "k_dist_left",
        "n_dist_left",
        "b_dist_left",
        "k_dist_right",
        "n_dist_right",
        "b_dist_right",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_csv_row())


def write_candidate_meta_log(path: Path, records: List[CandidateMeta]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["node_id", "raw_grid", "raw_lowess", "union", "spaced", "feasible"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "node_id": record.node_id,
                    "raw_grid": record.raw_grid,
                    "raw_lowess": record.raw_lowess,
                    "union": record.union,
                    "spaced": record.spaced,
                    "feasible": record.feasible,
                }
            )


def collect_split_metrics(node: SegmentNode) -> List[Tuple[str, float, float, float]]:
    splits: List[Tuple[str, float, float, float]] = []
    if node.split is not None:
        splits.append(
            (
                node.node_id,
                node.split.split_time,
                node.split.post_join_gap_adj,
                node.split.slope_gap,
            )
        )
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
    if cfg.no_plots:
        return {}
    outdir.mkdir(parents=True, exist_ok=True)
    plots: Dict[str, str] = {}

    splits = collect_split_metrics(root)
    leaves = [node for node in gather_nodes(root) if node.is_leaf()]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(time, values, "o", label="Observed", alpha=0.6)
    ax.plot(time, preds, "-", label="Piecewise fit (raw)", linewidth=2)
    if np.any(corrected != preds):
        ax.plot(time, corrected, "--", label="Isotonic fit")
    for node_id, split_time, gap, slope_gap in splits:
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
    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min if y_max > y_min else 1.0
    for leaf in leaves:
        segment_mid = (leaf.start + leaf.end - 1) // 2
        mid_time = float(time[segment_mid])
        mean_val = float(np.mean(values[leaf.start : leaf.end]))
        params = leaf.fit.params
        if leaf.fit.family == "Page":
            label = f"Page(k={params['k']:.3f}, n={params['n']:.3f})\nAICc={leaf.fit.aicc:.2f}"
        else:
            label = (
                f"Mid(k={params['k']:.3f}, n={params['n']:.3f}, b={params.get('b', 0.0):.4f})"
                f"\nAICc={leaf.fit.aicc:.2f}"
            )
        ax.text(
            mid_time,
            mean_val + 0.02 * y_range,
            label,
            fontsize=8,
            ha="center",
            va="bottom",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.6),
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
    for _, split_time, _, _ in splits:
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
    for _, split_time, _, _ in splits:
        ax.axvline(split_time, color="red", linestyle=":", alpha=0.5)
    ax.set_xlabel("Time")
    ax.set_ylabel("Change in prediction")
    ax.set_title("Piecewise prediction differences")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path_mono = outdir / f"{dataset_name}_monotonic.png"
    fig.savefig(path_mono, dpi=200)
    plt.close(fig)
    plots["monotonic"] = str(path_mono)

    split_nodes = [node for node in gather_nodes(root) if node.split is not None]
    for node in split_nodes:
        split = node.split
        split_idx = split.split_index
        left_idx = max(node.start, split_idx - 5)
        right_idx = min(node.end, split_idx + 6)
        window = slice(left_idx, right_idx)
        window_time = time[window]
        window_values = values[window]
        combined = _combine_predictions(
            split.left,
            split.right,
            node.start,
            split_idx,
            node.end,
            time,
            split.level_shift_applied,
            split.right_time_shift_attempted,
        )
        combined = combined + node.offset
        combined_raw = _combine_predictions(
            split.left,
            split.right,
            node.start,
            split_idx,
            node.end,
            time,
            0.0,
            split.right_time_shift_attempted,
        )
        combined_raw = combined_raw + node.offset
        window_pred = combined[window.start - node.start : window.stop - node.start]
        window_raw = combined_raw[window.start - node.start : window.stop - node.start]
        value_left, slope_left = _model_value_and_slope(split.left, split.split_time)
        value_right_shifted, slope_right_shifted = _model_value_and_slope(
            split.right,
            max(split.split_time + split.right_time_shift_attempted, 1e-8),
        )
        value_right_shifted += split.level_shift_applied
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(window_time, window_values, "o", label="Observed", alpha=0.7)
        ax.plot(window_time, window_pred, "-", label="Adjusted join", linewidth=2)
        ax.plot(window_time, window_raw, "--", label="Pre level shift", linewidth=1.5)
        delta = max((window_time[-1] - window_time[0]) * 0.1, 1e-6)
        slope_times = np.array([
            split.split_time - delta,
            split.split_time + delta,
        ])
        left_line = value_left + slope_left * (slope_times - split.split_time)
        right_line = value_right_shifted + slope_right_shifted * (slope_times - split.split_time)
        ax.plot(slope_times, left_line, color="green", linestyle=":", label="Left slope")
        ax.plot(slope_times, right_line, color="purple", linestyle=":", label="Right slope")
        ax.set_title(f"Join neighborhood for node {node.node_id}")
        ax.set_xlabel("Time")
        ax.set_ylabel("Moisture ratio")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path_join = outdir / f"{dataset_name}_join_{node.node_id}.png"
        fig.savefig(path_join, dpi=200)
        plt.close(fig)
        plots[f"join_{node.node_id}"] = str(path_join)

    if leaves:
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        mid_times = [float(time[(leaf.start + leaf.end - 1) // 2]) for leaf in leaves]
        k_vals = [leaf.fit.params.get("k", float("nan")) for leaf in leaves]
        n_vals = [leaf.fit.params.get("n", float("nan")) for leaf in leaves]
        b_vals = [leaf.fit.params.get("b", 0.0) for leaf in leaves]
        axes[0].plot(mid_times, k_vals, "o-", label="k")
        axes[0].set_ylabel("k")
        axes[0].grid(True, alpha=0.3)
        axes[1].plot(mid_times, n_vals, "o-", color="orange", label="n")
        axes[1].set_ylabel("n")
        axes[1].grid(True, alpha=0.3)
        axes[2].plot(mid_times, b_vals, "o-", color="purple", label="b")
        axes[2].set_ylabel("b")
        axes[2].set_xlabel("Time")
        axes[2].grid(True, alpha=0.3)
        for axis in axes:
            axis.legend(loc="best")
        fig.suptitle("Parameter trajectories across leaves")
        fig.tight_layout()
        path_params = outdir / f"{dataset_name}_parameter_trajectory.png"
        fig.savefig(path_params, dpi=200)
        plt.close(fig)
        plots["parameter_trajectory"] = str(path_params)

    return plots

CLI_FIELDS = [
    "data_dir",
    "outdir",
    "max_splits",
    "max_depth",
    "min_points_root",
    "min_points_leaf",
    "candidate_grid_count",
    "candidate_min_spacing",
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
    "midbody_aicc_tolerance",
    "monotonic_hardcap",
    "midilli_b_softbound",
    "probe_better_child_passes",
    "export_leaves_csv",
    "no_plots",
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
    global _GLOBAL_RNG
    if _GLOBAL_RNG is None:
        _GLOBAL_RNG = np.random.default_rng(cfg.seed)
        np.random.seed(cfg.seed)

    logger = logging.getLogger(__name__)
    dataset_start = time.perf_counter()
    result = load_and_preprocess(path)
    time = result.time_min.astype(float)
    values = result.mr_iso.astype(float)
    mask = np.isfinite(time) & np.isfinite(values)
    dropped_nonfinite = int(time.size - int(np.count_nonzero(mask)))
    if dropped_nonfinite:
        logger.warning(
            "Dataset %s dropped %d rows with non-finite entries.", path.name, dropped_nonfinite
        )
        time = time[mask]
        values = values[mask]
    if time.size == 0:
        raise RuntimeError(f"Dataset {path} contains no valid rows after filtering")
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
    candidate_meta_records: List[CandidateMeta] = []
    lowess_cache: Dict[Tuple[int, int, float], np.ndarray] = {}
    budget = BudgetState()
    if time.size >= cfg.min_points_root:
        recurse_node(
            root,
            time,
            values,
            cache,
            cfg,
            path.stem,
            budget,
            candidate_records,
            candidate_meta_records,
            lowess_cache,
            is_probe=False,
            probe_passes_remaining=cfg.probe_better_child_passes,
        )

    for node in gather_nodes(root):
        update_node_diagnostics(node, time, values, cfg)

    preds, corrected, violations, iso_used = reconstruct_predictions(root, time, values, cfg)
    iso_violations = _count_monotonic_violations(corrected, cfg.monotonic_eps)
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
    meta_log_path = dataset_outdir / "candidates_meta.csv"
    write_candidate_meta_log(meta_log_path, candidate_meta_records)

    leaves_csv_path: Optional[Path] = None
    if cfg.export_leaves_csv and leaves:
        leaves_csv_path = dataset_outdir / f"{path.stem}_leaves.csv"
        leaves_csv_path.parent.mkdir(parents=True, exist_ok=True)
        with leaves_csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "start_idx",
                    "end_idx",
                    "t_start",
                    "t_end",
                    "family",
                    "k",
                    "n",
                    "b",
                    "rmse",
                    "aicc",
                    "offset",
                    "right_time_shift_at_boundary",
                ]
            )
            for leaf in leaves:
                writer.writerow(
                    [
                        leaf.start,
                        leaf.end,
                        float(time[leaf.start]),
                        float(time[leaf.end - 1]),
                        leaf.fit.family,
                        float(leaf.fit.params.get("k", float("nan"))),
                        float(leaf.fit.params.get("n", float("nan"))),
                        float(leaf.fit.params.get("b", 0.0)),
                        float(leaf.fit.rmse),
                        float(leaf.fit.aicc),
                        float(leaf.offset),
                        float(leaf.right_time_shift_at_boundary),
                    ]
                )

    config_dict = _config_to_dict(cfg)
    config_digest = hashlib.sha1(json.dumps(config_dict, sort_keys=True).encode("utf-8")).hexdigest()
    version = _get_version()
    runtime_seconds = time.perf_counter() - dataset_start
    status = "insufficient_points" if time.size < cfg.min_points_root else "ok"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "file": str(path),
        "config": config_dict,
        "config_digest": config_digest,
        "version": version,
        "seed": cfg.seed,
        "unsplit": root.fit.to_summary(),
        "nodes": [node.to_dict() for node in gather_nodes(root)],
        "status": status,
        "dropped_rows": dropped_nonfinite,
        "runtime_seconds": runtime_seconds,
        "metrics": {
            "sum_gaps": budget.sum_gaps,
            "violations_total": violations,
            "mono_violations_raw": violations,
            "mono_violations_iso": iso_violations,
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
            "runtime_seconds": runtime_seconds,
        },
        "plots": plots,
        "candidate_log": str(candidate_log_path),
        "candidate_meta_log": str(meta_log_path),
    }
    if leaves_csv_path is not None:
        summary["leaves_csv"] = str(leaves_csv_path)

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
    parser.add_argument("--candidate-grid-count", type=int, default=800, help="Uniform grid candidate count.")
    parser.add_argument(
        "--candidate-min-spacing",
        type=int,
        default=4,
        help="Minimum spacing between consecutive candidate indices before feasibility checks.",
    )
    parser.add_argument("--lowess-frac-min", type=float, default=0.15, help="Minimum LOWESS fraction for candidates.")
    parser.add_argument("--lowess-frac-max", type=float, default=0.60, help="Maximum LOWESS fraction for candidates.")
    parser.add_argument("--min-fraction", type=float, default=0.05, help="Minimum fractional position for splits.")
    parser.add_argument("--max-fraction", type=float, default=0.95, help="Maximum fractional position for splits.")
    parser.add_argument("--min-rel-improvement", type=float, default=0.001, help="Minimum relative AICc improvement required.")
    parser.add_argument(
        "--allow-per-segment-model",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Evaluate Page vs Midilli per segment and choose the lower AICc.",
    )
    parser.add_argument("--join-penalty", type=float, default=8.0, help="Penalty on squared join gaps.")
    parser.add_argument("--slope-penalty", type=float, default=2.0, help="Penalty on squared slope gaps.")
    parser.add_argument("--shape-penalty-mono", type=float, default=8.0, help="Penalty per monotonicity violation.")
    parser.add_argument("--max-allowed-gap", type=float, default=0.02, help="Maximum allowed join gap.")
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
        default=0.005,
        help="Tolerance added when comparing against the maximum allowed slope discontinuity.",
    )
    parser.add_argument("--total-gap-budget", type=float, default=0.08, help="Total allowed sum of join gaps.")
    parser.add_argument("--time-penalty", type=float, default=0.05, help="Penalty weight for split location prior.")
    parser.add_argument("--lowess-frac-root", type=float, default=0.18, help="LOWESS fraction at the root node.")
    parser.add_argument("--max-iter", type=int, default=4000, help="Maximum iterations for curve fitting.")
    parser.add_argument("--seed", type=int, default=1337, help="Deterministic RNG seed.")
    parser.add_argument(
        "--reject-nonmonotone",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Reject splits that produce monotonicity violations.",
    )
    parser.add_argument(
        "--monotonic-hardcap",
        type=int,
        default=0,
        help="Reject splits automatically when violations exceed this count (0 disables).",
    )

    parser.add_argument(
        "--probe-better-child",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recurse into the higher-evidence child before probing the other side.",
    )
    parser.add_argument(
        "--probe-better-child-passes",
        type=int,
        default=1,
        help="Additional recursion levels allowed on the prioritized child before probing siblings.",
    )
    parser.add_argument(
        "--lambda-b",
        type=float,
        default=20.0,
        help="Penalty weight applied when |b| exceeds 1e-3 for Midilli segments.",
    )
    parser.add_argument(
        "--midilli-b-softbound",
        type=float,
        default=DEFAULT_MIDILLI_SOFT_BOUND,
        help="Soft threshold for Midilli b penalty (meters the lambda-b quadratic).",
    )
    parser.add_argument(
        "--page-fallback-eps",
        type=float,
        default=0.2,
        help="AICc tolerance for preferring Page when Midilli hits parameter bounds.",
    )
    parser.add_argument(
        "--midbody-aicc-tolerance",
        type=float,
        default=0.05,
        help="If Page and Midilli AICc differ within this tolerance in mid-body segments, prefer Page.",
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
        default=7,
        help="Number of LOWESS fractions evaluated when selecting candidate smoothing levels.",
    )
    parser.add_argument(
        "--iso-rmse-tol",
        type=float,
        default=1e-6,
        help="Only keep isotonic correction if RMSE improves by at least this tolerance.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level (e.g., INFO, DEBUG).")
    parser.add_argument(
        "--export-leaves-csv",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Export a CSV summarizing fitted leaf segments.",
    )
    parser.add_argument(
        "--no-plots",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Disable matplotlib plot generation (useful for headless runs).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse arguments, emit the resolved configuration as JSON, and exit without processing data.",
    )
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
        candidate_min_spacing=args.candidate_min_spacing,
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
        probe_better_child_passes=args.probe_better_child_passes,
        lambda_b=args.lambda_b,
        midilli_b_softbound=args.midilli_b_softbound,
        page_fallback_eps=args.page_fallback_eps,
        midbody_aicc_tolerance=args.midbody_aicc_tolerance,
        monotonic_hardcap=args.monotonic_hardcap,
        monotonic_eps=args.monotonic_eps,
        lowess_points=args.lowess_points,
        iso_rmse_tol=args.iso_rmse_tol,
        export_leaves_csv=bool(args.export_leaves_csv),
        no_plots=bool(args.no_plots),
    )

    global _GLOBAL_RNG
    _GLOBAL_RNG = np.random.default_rng(cfg.seed)
    np.random.seed(cfg.seed)

    if getattr(args, "dry_run", False):
        print(json.dumps(_config_to_dict(cfg), indent=2))
        return 0

    if not cfg.data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {cfg.data_dir}")
    cfg.outdir.mkdir(parents=True, exist_ok=True)

    csv_paths = sorted(p for p in cfg.data_dir.glob("*.csv") if p.is_file())
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in {cfg.data_dir}")

    summaries = []
    total_start = time.perf_counter()
    for path in csv_paths:
        logging.info("Processing %s", path.name)
        summary = process_dataset(path, cfg)
        summaries.append(summary)
    total_runtime = time.perf_counter() - total_start

    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "schema_notes": SCHEMA_NOTES,
        "config": _config_to_dict(cfg),
        "files": [str(path) for path in csv_paths],
        "summaries": summaries,
        "dataset_runtimes": {
            summary["file"]: float(summary.get("runtime_seconds", 0.0)) for summary in summaries
        },
        "total_runtime_seconds": total_runtime,
    }
    index_path = cfg.outdir / "summary_index.json"
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
