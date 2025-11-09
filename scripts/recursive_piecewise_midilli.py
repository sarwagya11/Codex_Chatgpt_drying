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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from statsmodels.nonparametric.smoothers_lowess import lowess

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
    min_points_root: int
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
    max_allowed_gap_eps: float = 1e-12
    max_allowed_slope_eps: float = 1e-12
    monotonic_eps: float = 5e-6
    alpha_iso: float = 1e-3
    lowess_points: int = 5


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

    def to_summary(self) -> Dict[str, object]:
        return {
            "family": self.family,
            "params": {key: float(value) for key, value in self.params.items()},
            "AICc": float(self.aicc),
            "RMSE": float(self.rmse),
        }


@dataclass
class SplitInfo:
    split_index: int
    split_time: float
    gap: float
    slope_gap: float
    penalized_score: float
    time_penalty: float
    score_components: Dict[str, float]
    left: FitStats
    right: FitStats
    delta_aicc: float
    rel_improvement: float
    violations: int


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

    def is_leaf(self) -> bool:
        return not self.children

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "node_id": self.node_id,
            "start_idx": self.start,
            "end_idx": self.end,
            "depth": self.depth,
            "unsplit": self.fit.to_summary(),
        }
        if self.split is not None:
            payload.update(
                {
                    "t_split": float(self.split.split_time),
                    "gap": float(self.split.gap),
                    "slope_gap": float(self.split.slope_gap),
                    "penalized_score": float(self.split.penalized_score),
                    "time_penalty": float(self.split.time_penalty),
                    "delta_aicc": float(self.split.delta_aicc),
                    "rel_improvement": float(self.split.rel_improvement),
                    "violations": int(self.split.violations),
                    "score_components": {
                        key: float(value) for key, value in self.split.score_components.items()
                    },
                    "left": self.split.left.to_summary(),
                    "right": self.split.right.to_summary(),
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
    model_right: str
    params_right: Dict[str, float]
    aicc_right: float
    rmse_right: float
    aicc_unsplit: float
    delta_aicc: float
    rel_improvement: float
    gap: float
    slope_gap: float
    violations: int
    time_pen: float
    penalized_score: float
    rejected_flag: bool
    reject_reason: str
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
            "model_right": self.model_right,
            "params_right_json": json.dumps(self.params_right, sort_keys=True),
            "AICc_right": self.aicc_right,
            "RMSE_right": self.rmse_right,
            "AICc_unsplit": self.aicc_unsplit,
            "delta_AICc": self.delta_aicc,
            "rel_impr": self.rel_improvement,
            "gap": self.gap,
            "slope_gap": self.slope_gap,
            "violations": self.violations,
            "time_pen": self.time_pen,
            "penalized_score": self.penalized_score,
            "rejected_flag": self.rejected_flag,
            "reject_reason": self.reject_reason,
            "tests_fired_json": json.dumps(self.tests_fired, sort_keys=True),
        }


class FitCache:
    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, int, int], FitStats] = {}

    def get(self, family: str, start: int, end: int) -> Optional[FitStats]:
        return self._cache.get((family, start, end))

    def store(self, family: str, start: int, end: int, stats: FitStats) -> None:
        self._cache[(family, start, end)] = stats


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


PAGE_BOUNDS = (np.array([1e-8, 0.1]), np.array([10.0, 3.0]))
MIDILLI_BOUNDS = (np.array([1e-8, 0.1, -5e-3]), np.array([10.0, 3.0, 5e-3]))
MIDILLI_SOFT_BOUND = 1e-3


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


def _initial_guess_midilli(time: np.ndarray, values: np.ndarray) -> Tuple[float, float, float]:
    k_guess, n_guess = _initial_guess_page(time, values)
    if time.size >= 3:
        tail = min(5, time.size)
        coef = np.polyfit(time[-tail:], values[-tail:], deg=1)
        b_guess = float(np.clip(coef[0], MIDILLI_BOUNDS[0][2], MIDILLI_BOUNDS[1][2]))
    else:
        b_guess = 0.0
    return k_guess, n_guess, b_guess


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
    predictions = page_model(time, params[0], params[1])
    residuals = values - predictions
    rss = float(np.dot(residuals, residuals))
    rmse = math.sqrt(max(rss, 0.0) / time.size)
    aicc = _compute_aicc(time.size, rss, 2)
    return FitStats(
        family="Page",
        params={"k": float(params[0]), "n": float(params[1])},
        rss=rss,
        rmse=rmse,
        aicc=aicc,
        n_obs=time.size,
        saturates_bound=False,
        predictions=predictions,
    )


def _fit_midilli(time: np.ndarray, values: np.ndarray, max_iter: int) -> Optional[FitStats]:
    guess = _initial_guess_midilli(time, values)
    penalty_scale = math.sqrt(time.size)

    try:
        params, _ = curve_fit(
            lambda t, k, n, b: midilli_model(t, k, n, b),
            time,
            values,
            p0=guess,
            bounds=MIDILLI_BOUNDS,
            maxfev=max_iter,
        )
    except Exception:  # pragma: no cover - scipy raises runtime errors
        return None

    predictions = midilli_model(time, params[0], params[1], params[2])
    residuals = values - predictions
    rss = float(np.dot(residuals, residuals))
    soft_excess = max(abs(params[2]) - MIDILLI_SOFT_BOUND, 0.0)
    if soft_excess > 0:
        rss += penalty_scale * (soft_excess**2)
    rmse = math.sqrt(max(rss, 0.0) / time.size)
    aicc = _compute_aicc(time.size, rss, 3)
    saturates = bool(
        abs(params[2] - MIDILLI_BOUNDS[0][2]) <= 1e-6
        or abs(params[2] - MIDILLI_BOUNDS[1][2]) <= 1e-6
    )
    return FitStats(
        family="Midilli",
        params={"k": float(params[0]), "n": float(params[1]), "b": float(params[2])},
        rss=rss,
        rmse=rmse,
        aicc=aicc,
        n_obs=time.size,
        saturates_bound=saturates,
        predictions=predictions,
    )


def fit_segment(
    family: str,
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    max_iter: int,
) -> Optional[FitStats]:
    cached = cache.get(family, start, end)
    if cached is not None:
        return cached

    segment_time = time[start:end]
    segment_values = values[start:end]
    if family == "Page":
        stats = _fit_page(segment_time, segment_values, max_iter)
    else:
        stats = _fit_midilli(segment_time, segment_values, max_iter)
    if stats is not None:
        cache.store(family, start, end, stats)
    return stats


def select_best_model(
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
) -> Optional[FitStats]:
    candidates: List[FitStats] = []
    midilli = fit_segment("Midilli", start, end, time, values, cache, cfg.max_iter)
    if midilli is not None:
        candidates.append(midilli)
        if midilli.saturates_bound:
            page = fit_segment("Page", start, end, time, values, cache, cfg.max_iter)
            if page is not None:
                candidates.append(page)
    if cfg.allow_per_segment_model:
        page = fit_segment("Page", start, end, time, values, cache, cfg.max_iter)
        if page is not None and all(stat.family != "Page" for stat in candidates):
            candidates.append(page)
    if not candidates:
        return None
    best = min(candidates, key=lambda item: item.aicc)
    return best


def select_model_with_fallback(
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
) -> Optional[FitStats]:
    stats = select_best_model(start, end, time, values, cache, cfg)
    if stats is not None:
        return stats
    return fit_segment("Page", start, end, time, values, cache, cfg.max_iter)


def compute_unsplit_fit(
    start: int,
    end: int,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
) -> Optional[FitStats]:
    return select_model_with_fallback(start, end, time, values, cache, cfg)


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
    residuals = values[start:end] - node.fit.predictions
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


def _combine_predictions(
    left: FitStats,
    right: FitStats,
    start: int,
    split_idx: int,
    end: int,
    time: np.ndarray,
) -> np.ndarray:
    left_time = time[start : split_idx + 1]
    right_time = time[split_idx + 1 : end]
    if left.family == "Page":
        left_pred = page_model(left_time, left.params["k"], left.params["n"])
    else:
        left_pred = midilli_model(
            left_time, left.params["k"], left.params["n"], left.params.get("b", 0.0)
        )
    if right.family == "Page":
        right_pred = page_model(right_time, right.params["k"], right.params["n"])
    else:
        right_pred = midilli_model(
            right_time, right.params["k"], right.params["n"], right.params.get("b", 0.0)
        )
    return np.concatenate([left_pred, right_pred])


def _count_monotonic_violations(predictions: np.ndarray, eps: float) -> int:
    diffs = np.diff(predictions)
    return int(np.sum(diffs > eps))


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
    left_stats = select_model_with_fallback(start, split_idx + 1, time, values, cache, cfg)
    right_stats = select_model_with_fallback(split_idx + 1, end, time, values, cache, cfg)
    left_n = split_idx - start + 1
    right_n = end - (split_idx + 1)
    split_time = float(time[split_idx])
    tests: List[str] = []
    rejected = False
    reason = ""

    if left_stats is None or right_stats is None:
        rejected = True
        reason = "fit_failure"
        tests.append("fit_failure")
        record = CandidateRecord(
            dataset_name,
            node.node_id,
            split_time,
            split_idx,
            left_n,
            right_n,
            left_stats.family if left_stats else "",
            left_stats.params if left_stats else {},
            left_stats.aicc if left_stats else float("nan"),
            left_stats.rmse if left_stats else float("nan"),
            right_stats.family if right_stats else "",
            right_stats.params if right_stats else {},
            right_stats.aicc if right_stats else float("nan"),
            right_stats.rmse if right_stats else float("nan"),
            node.fit.aicc,
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            0,
            0.0,
            float("nan"),
            rejected,
            reason,
            tests,
        )
        return None, record

    base = left_stats.aicc + right_stats.aicc
    delta_aicc = node.fit.aicc - base
    denom = max(abs(node.fit.aicc), 1e-9)
    rel_impr = (node.fit.aicc - base) / denom

    value_left, slope_left = _model_value_and_slope(left_stats, split_time)
    right_time = float(time[split_idx + 1])
    value_right, slope_right = _model_value_and_slope(right_stats, right_time)
    gap = abs(value_left - value_right)
    slope_gap = abs(slope_left - slope_right)
    time_pen = _time_penalty(split_time, node, time, cfg)
    combined_preds = _combine_predictions(left_stats, right_stats, start, split_idx, end, time)
    violations = _count_monotonic_violations(combined_preds, cfg.monotonic_eps)

    if not math.isfinite(base) or not math.isfinite(gap) or not math.isfinite(slope_gap):
        rejected = True
        reason = "nan_metric"
        tests.append("nan_metric")
    if gap > cfg.max_allowed_gap + cfg.max_allowed_gap_eps:
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
    if budget_sum_gaps + gap > cfg.total_gap_budget + cfg.max_allowed_gap_eps:
        rejected = True
        reason = "gap_budget"
        tests.append("gap_budget")

    score = base + cfg.join_penalty * (gap**2) + cfg.slope_penalty * (slope_gap**2)
    score += cfg.shape_penalty_mono * violations + time_pen

    if not rejected and not math.isfinite(score):
        rejected = True
        reason = "nan_score"
        tests.append("nan_score")

    split_info = None
    if not rejected:
        tests.append("accepted")
        split_info = SplitInfo(
            split_idx,
            split_time,
            gap,
            slope_gap,
            score,
            time_pen,
            {
                "base": base,
                "gap_pen": cfg.join_penalty * (gap**2),
                "slope_pen": cfg.slope_penalty * (slope_gap**2),
                "time_pen": time_pen,
                "mono_pen": cfg.shape_penalty_mono * violations,
            },
            left_stats,
            right_stats,
            delta_aicc,
            rel_impr,
            violations,
        )
    else:
        if not tests:
            tests.append("rejected")

    record = CandidateRecord(
        dataset_name,
        node.node_id,
        split_time,
        split_idx,
        left_n,
        right_n,
        left_stats.family,
        left_stats.params,
        left_stats.aicc,
        left_stats.rmse,
        right_stats.family,
        right_stats.params,
        right_stats.aicc,
        right_stats.rmse,
        node.fit.aicc,
        delta_aicc,
        rel_impr,
        gap,
        slope_gap,
        violations,
        time_pen,
        score,
        rejected,
        reason,
        tests,
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
    if residuals.size == 0:
        return 0.0
    smoothed = lowess(residuals, time, frac=float(np.clip(frac, 0.01, 0.99)), return_sorted=False)
    return float(np.nanmax(smoothed) - np.nanmin(smoothed))


def _slope_sign_changes(residuals: np.ndarray) -> int:
    if residuals.size < 3:
        return 0
    diff = np.diff(residuals)
    signs = np.sign(diff)
    changes = np.sum(signs[1:] * signs[:-1] < 0)
    return int(changes)


def compute_child_evidence(
    child: SegmentNode,
    parent_fit: FitStats,
    time: np.ndarray,
    values: np.ndarray,
    cfg: Config,
) -> Evidence:
    child_slice = slice(child.start, child.end)
    child_time = time[child_slice]
    if parent_fit.family == "Page":
        parent_segment_pred = page_model(child_time, parent_fit.params["k"], parent_fit.params["n"])
        parent_k = 2
    else:
        parent_segment_pred = midilli_model(
            child_time,
            parent_fit.params["k"],
            parent_fit.params["n"],
            parent_fit.params.get("b", 0.0),
        )
        parent_k = 3
    residuals_parent = values[child_slice] - parent_segment_pred
    residuals_child = values[child_slice] - child.fit.predictions
    rss_parent = float(np.dot(residuals_parent, residuals_parent))
    rss_child = float(np.dot(residuals_child, residuals_child))
    aicc_parent = _compute_aicc(child.fit.n_obs, rss_parent, parent_k)
    delta = aicc_parent - child.fit.aicc
    runs_p, _ = _runs_test(residuals_child)
    amplitude = _residual_lowess_amplitude(time[child_slice], residuals_child, cfg.lowess_frac_root)
    slope_changes = _slope_sign_changes(residuals_child)
    runs_component = 1.0 - float(np.clip(runs_p, 0.0, 1.0)) if math.isfinite(runs_p) else 1.0
    score = float(delta - amplitude - slope_changes - runs_component)
    return Evidence(delta, runs_p, amplitude, slope_changes, score)


def recurse_node(
    node: SegmentNode,
    time: np.ndarray,
    values: np.ndarray,
    cache: FitCache,
    cfg: Config,
    dataset_name: str,
    budget: BudgetState,
    candidate_records: List[CandidateRecord],
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
    left_node = SegmentNode(
        node_id=f"{node.node_id}L",
        start=node.start,
        end=best_info.split_index + 1,
        depth=node.depth + 1,
        fit=best_info.left,
    )
    right_node = SegmentNode(
        node_id=f"{node.node_id}R",
        start=best_info.split_index + 1,
        end=node.end,
        depth=node.depth + 1,
        fit=best_info.right,
    )
    node.children = [left_node, right_node]
    budget.sum_gaps += best_info.gap
    budget.splits_used += 1
    budget.levels_splits[node.depth] = budget.levels_splits.get(node.depth, 0) + 1
    left_node.evidence = compute_child_evidence(left_node, node.fit, time, values, cfg)
    right_node.evidence = compute_child_evidence(right_node, node.fit, time, values, cfg)

    if cfg.probe_better_child:
        def _evidence_key(child: SegmentNode) -> Tuple[float, float, float]:
            ev = child.evidence
            if ev is None:
                return (float("-inf"), float("-inf"), float("-inf"))
            return (
                float(ev.score),
                float(ev.delta_aicc),
                -float(ev.residual_amplitude + ev.slope_sign_changes),
            )

        ordered_children = sorted(node.children, key=_evidence_key, reverse=True)
    else:
        ordered_children = list(node.children)
    for child in ordered_children:
        if budget.splits_used >= cfg.max_splits:
            break
        if child.depth >= cfg.max_depth:
            continue
        recurse_node(child, time, values, cache, cfg, dataset_name, budget, candidate_records)


def reconstruct_predictions(node: SegmentNode, time: np.ndarray, cfg: Config) -> Tuple[np.ndarray, np.ndarray, int]:
    preds = np.zeros_like(time, dtype=float)

    def _assign(segment: SegmentNode) -> None:
        segment_time = time[segment.start : segment.end]
        if segment.fit.family == "Page":
            preds[segment.start : segment.end] = page_model(
                segment_time, segment.fit.params["k"], segment.fit.params["n"]
            )
        else:
            preds[segment.start : segment.end] = midilli_model(
                segment_time,
                segment.fit.params["k"],
                segment.fit.params["n"],
                segment.fit.params.get("b", 0.0),
            )
        for child in segment.children:
            _assign(child)

    _assign(node)
    violations = _count_monotonic_violations(preds, cfg.monotonic_eps)
    corrected = preds.copy()
    for idx in range(1, corrected.size):
        if corrected[idx] > corrected[idx - 1]:
            diff = corrected[idx] - corrected[idx - 1]
            corrected[idx] = corrected[idx - 1] - cfg.alpha_iso * diff
    return preds, corrected, violations


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
        "model_right",
        "params_right_json",
        "AICc_right",
        "RMSE_right",
        "AICc_unsplit",
        "delta_AICc",
        "rel_impr",
        "gap",
        "slope_gap",
        "violations",
        "time_pen",
        "penalized_score",
        "rejected_flag",
        "reject_reason",
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
        splits.append((node.split.split_time, node.split.gap, node.split.slope_gap))
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
    ax.plot(time, preds, "-", label="Piecewise fit", linewidth=2)
    if np.any(corrected != preds):
        ax.plot(time, corrected, "--", label="Isotonic adj.")
    for split_time, gap, slope_gap in splits:
        ax.axvline(split_time, color="red", linestyle="--", alpha=0.6)
        ax.text(
            split_time,
            ax.get_ylim()[0],
            f"gap={gap:.4f}\nslope={slope_gap:.5f}",
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
    "reject_nonmonotone",
    "total_gap_budget",
    "time_penalty",
    "lowess_frac_root",
    "max_iter",
    "seed",
    "probe_better_child",
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

    preds, corrected, violations = reconstruct_predictions(root, time, cfg)
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
    parser = argparse.ArgumentParser(
        description="Recursive piecewise Page/Midilli splitter with continuity penalties.",
        conflict_handler="resolve",
    )
    parser.add_argument("--data-dir", default="data", help="Directory containing input CSV files.")
    parser.add_argument("--outdir", default="outputs", help="Directory to store outputs.")
    parser.add_argument("--max-splits", type=int, default=2, help="Maximum number of splits across the tree.")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum recursion depth (root depth is 0).")
    parser.add_argument("--min-points-root", type=int, default=12, help="Minimum points required at the root segment.")
    parser.add_argument("--min-points-leaf", type=int, default=8, help="Minimum points required for child segments.")
    parser.add_argument("--candidate-grid-count", type=int, default=60, help="Uniform grid candidate count.")
    parser.add_argument("--lowess-frac-min", type=float, default=0.10, help="Minimum LOWESS fraction for candidates.")
    parser.add_argument("--lowess-frac-max", type=float, default=0.30, help="Maximum LOWESS fraction for candidates.")
    parser.add_argument("--min-fraction", type=float, default=0.05, help="Minimum fractional position for splits.")
    parser.add_argument("--max-fraction", type=float, default=0.95, help="Maximum fractional position for splits.")
    parser.add_argument("--min-rel-improvement", type=float, default=0.02, help="Minimum relative AICc improvement required.")
    parser.add_argument(
        "--allow-per-segment-model",
        action="store_true",
        help="Evaluate Page vs Midilli per segment and choose the lower AICc.",
    )
    parser.add_argument("--join-penalty", type=float, default=10.0, help="Penalty on squared join gaps.")
    parser.add_argument("--slope-penalty", type=float, default=2.0, help="Penalty on squared slope gaps.")
    parser.add_argument("--shape-penalty-mono", type=float, default=50.0, help="Penalty per monotonicity violation.")
    parser.add_argument("--max-allowed-gap", type=float, default=0.02, help="Maximum allowed join gap.")
    parser.add_argument(
        "--max-allowed-slope-gap", type=float, default=5e-4, help="Maximum allowed slope discontinuity."
    )
    parser.add_argument(
        "--reject-nonmonotone",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reject splits that produce monotonicity violations.",
    )
    parser.add_argument("--total-gap-budget", type=float, default=0.05, help="Total allowed sum of join gaps.")
    parser.add_argument("--time-penalty", type=float, default=0.5, help="Penalty weight for split location prior.")
    parser.add_argument("--lowess-frac-root", type=float, default=0.20, help="LOWESS fraction at the root node.")
    parser.add_argument("--max-iter", type=int, default=4000, help="Maximum iterations for curve fitting.")
    parser.add_argument("--seed", type=int, default=1337, help="Deterministic RNG seed.")
    parser.add_argument(
        "--probe-better-child",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recurse into the higher-evidence child before probing the other side.",
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
        reject_nonmonotone=bool(args.reject_nonmonotone),
        total_gap_budget=args.total_gap_budget,
        time_penalty=args.time_penalty,
        lowess_frac_root=args.lowess_frac_root,
        max_iter=args.max_iter,
        seed=args.seed,
        log_level=str(args.log_level),
        probe_better_child=bool(args.probe_better_child),
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
