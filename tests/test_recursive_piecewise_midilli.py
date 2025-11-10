import math
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from recursive_piecewise_midilli import (  # noqa: E402
    BudgetState,
    Config,
    FitCache,
    FitStats,
    SegmentNode,
    compute_unsplit_fit,
    midilli_model,
    reconstruct_predictions,
    recurse_node,
)


def make_config(**overrides) -> Config:
    params = dict(
        data_dir=ROOT,
        outdir=ROOT,
        max_splits=2,
        max_depth=2,
        min_points_root=12,
        min_points_leaf=8,
        candidate_grid_count=overrides.get("candidate_grid_count", 60),
        lowess_frac_min=0.10,
        lowess_frac_max=0.30,
        min_fraction=0.05,
        max_fraction=0.95,
        min_rel_improvement=0.02,
        allow_per_segment_model=overrides.get("allow_per_segment_model", True),
        join_penalty=10.0,
        slope_penalty=2.0,
        shape_penalty_mono=50.0,
        max_allowed_gap=0.02,
        max_allowed_slope_gap=5e-4,
        reject_nonmonotone=True,
        total_gap_budget=0.05,
        time_penalty=0.5,
        lowess_frac_root=0.20,
        max_iter=4000,
        seed=1337,
        log_level="INFO",
        probe_better_child=overrides.get("probe_better_child", True),
        lambda_b=overrides.get("lambda_b", 50.0),
        page_fallback_eps=overrides.get("page_fallback_eps", 2.0),
    )
    params.update(overrides)
    return Config(**params)


def build_tree(time: np.ndarray, values: np.ndarray, cfg: Config):
    cache = FitCache()
    root_fit = compute_unsplit_fit(0, time.size, time, values, cache, cfg)
    assert root_fit is not None
    root = SegmentNode(node_id="0", start=0, end=time.size, depth=0, fit=root_fit)
    budget = BudgetState()
    candidate_records = []
    recurse_node(root, time, values, cache, cfg, "synthetic", budget, candidate_records)
    return root, budget, candidate_records


def midilli_curve(time: np.ndarray, k: float, n: float, b: float) -> np.ndarray:
    return np.exp(-k * np.power(time, n)) + b * time


@pytest.fixture
def base_time() -> np.ndarray:
    return np.linspace(0.1, 8.0, 80)


def test_single_split_recovery(base_time: np.ndarray):
    split_idx_true = 40
    left = midilli_curve(base_time[: split_idx_true + 1], 0.015, 1.2, -4e-4)
    right = midilli_curve(base_time[split_idx_true + 1 :], 0.025, 1.1, -3e-4)
    values = np.concatenate([left, right])
    cfg = make_config()
    root, budget, _ = build_tree(base_time, values, cfg)
    assert root.split is not None
    assert abs(root.split.split_index - split_idx_true) <= 3
    assert root.split.raw_gap <= cfg.max_allowed_gap + 1e-6
    assert root.split.rel_improvement >= cfg.min_rel_improvement - 1e-6
    assert math.isclose(budget.sum_gaps, root.split.raw_gap, rel_tol=1e-6, abs_tol=1e-6)


def test_no_split_for_page_curve(base_time: np.ndarray):
    values = np.exp(-0.02 * np.power(base_time, 1.1))
    cfg = make_config()
    root, _, _ = build_tree(base_time, values, cfg)
    assert root.split is None


def test_slope_discontinuity_rejected(base_time: np.ndarray):
    split_idx_true = 35
    left = midilli_curve(base_time[: split_idx_true + 1], 0.02, 1.0, -4e-4)
    # Introduce slope jump via positive b term on the right
    right = midilli_curve(base_time[split_idx_true + 1 :], 0.02, 1.0, 3e-3)
    values = np.concatenate([left, right])
    cfg = make_config()
    root, _, _ = build_tree(base_time, values, cfg)
    assert root.split is None

    relaxed_cfg = make_config(max_allowed_slope_gap=0.1, total_gap_budget=1.0)
    relaxed_root, _, _ = build_tree(base_time, values, relaxed_cfg)
    assert relaxed_root.split is not None


def test_grid_jitter_stability(base_time: np.ndarray):
    split_idx_true = 30
    left = midilli_curve(base_time[: split_idx_true + 1], 0.018, 1.3, -5e-4)
    right = midilli_curve(base_time[split_idx_true + 1 :], 0.028, 1.1, -2e-4)
    values = np.concatenate([left, right])

    cfg_base = make_config(candidate_grid_count=60)
    root_base, _, _ = build_tree(base_time, values, cfg_base)
    assert root_base.split is not None

    cfg_jitter = make_config(candidate_grid_count=66)
    root_jitter, _, _ = build_tree(base_time, values, cfg_jitter)
    assert root_jitter.split is not None
    assert root_base.split.split_index == root_jitter.split.split_index

    preds, _, _ = reconstruct_predictions(root_base, base_time, cfg_base)
    assert preds.shape == base_time.shape


def test_reconstruct_predictions_enforces_monotone_tail(base_time: np.ndarray):
    cfg = make_config(alpha_iso=0.1)

    params = {"k": 0.02, "n": 1.1, "b": 0.0}
    base_preds = midilli_model(base_time, params["k"], params["n"], params["b"])

    root_fit = FitStats(
        family="Midilli",
        params=params,
        rss=0.0,
        rmse=0.0,
        aicc=0.0,
        n_obs=base_time.size,
        saturates_bound=False,
        predictions=base_preds,
        hit_bounds={},
    )

    tail_start = base_time.size - 8
    tail_params = {"k": params["k"], "n": params["n"], "b": params["b"]}
    tail_preds = midilli_model(base_time[tail_start:], tail_params["k"], tail_params["n"], tail_params["b"])
    tail_fit = FitStats(
        family="Midilli",
        params=tail_params,
        rss=0.0,
        rmse=0.0,
        aicc=0.0,
        n_obs=base_time.size - tail_start,
        saturates_bound=False,
        predictions=tail_preds,
        hit_bounds={},
    )

    tail_node = SegmentNode(
        node_id="tail",
        start=tail_start,
        end=base_time.size,
        depth=1,
        fit=tail_fit,
        children=[],
        offset=0.12,
    )

    root = SegmentNode(
        node_id="root",
        start=0,
        end=base_time.size,
        depth=0,
        fit=root_fit,
        children=[tail_node],
    )

    preds, corrected, violations = reconstruct_predictions(root, base_time, cfg)
    assert violations > 0
    assert np.any(np.diff(preds[tail_start - 1 : tail_start + 2]) > cfg.monotonic_eps)

    diffs = np.diff(corrected)
    assert np.all(diffs <= cfg.monotonic_eps + 1e-12)
    assert np.all(corrected[:-1] >= corrected[1:] - cfg.monotonic_eps)
