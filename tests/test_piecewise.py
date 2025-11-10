import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from recursive_piecewise_midilli import (  # noqa: E402
    BudgetState,
    Config,
    DEFAULT_MIDILLI_SOFT_BOUND,
    FitCache,
    SegmentNode,
    compute_unsplit_fit,
    midilli_model,
    page_model,
    reconstruct_predictions,
    recurse_node,
    select_best_model,
)


def make_config(**overrides: object) -> Config:
    params = dict(
        data_dir=ROOT,
        outdir=ROOT,
        max_splits=3,
        max_depth=3,
        min_points_root=24,
        min_points_leaf=12,
        candidate_grid_count=80,
        lowess_frac_min=0.10,
        lowess_frac_max=0.35,
        min_fraction=0.05,
        max_fraction=0.95,
        min_rel_improvement=0.001,
        allow_per_segment_model=True,
        join_penalty=6.0,
        slope_penalty=2.0,
        shape_penalty_mono=8.0,
        max_allowed_gap=0.08,
        max_allowed_slope_gap=0.01,
        reject_nonmonotone=False,
        monotonic_hardcap=overrides.get("monotonic_hardcap", 0),
        total_gap_budget=0.5,
        time_penalty=0.05,
        lowess_frac_root=0.18,
        max_iter=4000,
        seed=1337,
        log_level="INFO",
        probe_better_child=True,
        probe_better_child_passes=overrides.get("probe_better_child_passes", 1),
        lambda_b=overrides.get("lambda_b", 20.0),
        midilli_b_softbound=overrides.get("midilli_b_softbound", DEFAULT_MIDILLI_SOFT_BOUND),
        page_fallback_eps=overrides.get("page_fallback_eps", 0.2),
        midbody_aicc_tolerance=overrides.get("midbody_aicc_tolerance", 0.05),
        monotonic_eps=5e-6,
        lowess_points=5,
        iso_rmse_tol=overrides.get("iso_rmse_tol", 1e-6),
        export_leaves_csv=False,
        no_plots=True,
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


def test_gap_limit_rejection():
    time = np.linspace(0.1, 10.0, 80)
    left = midilli_model(time[:40], 0.02, 1.1, -4e-4)
    right = midilli_model(time[40:], 0.025, 1.0, -3e-4) + 0.04
    values = np.concatenate([left, right])
    cfg = make_config(max_allowed_gap=5e-4, total_gap_budget=1.0)
    root, _, _ = build_tree(time, values, cfg)
    assert root.split is None


def test_gap_budget_limits_multiple_splits():
    time = np.linspace(0.1, 12.0, 90)
    seg1 = midilli_model(time[:30], 0.02, 1.15, -4e-4)
    seg2 = midilli_model(time[30:60], 0.028, 1.05, -3e-4) + 0.03
    seg3 = midilli_model(time[60:], 0.017, 1.2, -2e-4) + 0.06
    values = np.concatenate([seg1, seg2, seg3])

    rich_cfg = make_config(total_gap_budget=1.0)
    rich_root, rich_budget, _ = build_tree(time, values, rich_cfg)
    assert rich_root.split is not None
    assert rich_budget.splits_used >= 2

    tight_cfg = make_config(total_gap_budget=0.05)
    tight_root, tight_budget, _ = build_tree(time, values, tight_cfg)
    assert tight_root.split is not None
    assert tight_budget.splits_used == 1


def test_isotonic_threshold_respected():
    time = np.linspace(0.1, 8.0, 80)
    baseline = np.exp(-0.02 * np.power(time, 1.1))
    # introduce a gentle hump to encourage isotonic correction
    values = baseline.copy()
    values[30:35] += 0.01

    cfg = make_config(iso_rmse_tol=1e-6)
    cache = FitCache()
    root_fit = compute_unsplit_fit(0, time.size, time, values, cache, cfg)
    assert root_fit is not None
    root = SegmentNode(node_id="0", start=0, end=time.size, depth=0, fit=root_fit)
    preds, corrected, _, iso_used = reconstruct_predictions(root, time, values, cfg)
    rmse_raw = math.sqrt(np.mean((preds - values) ** 2))
    rmse_iso = math.sqrt(np.mean((corrected - values) ** 2))
    assert iso_used == (rmse_iso <= rmse_raw + cfg.iso_rmse_tol)

    cfg_loose = make_config(iso_rmse_tol=0.05)
    preds2, corrected2, _, iso_used2 = reconstruct_predictions(root, time, values, cfg_loose)
    rmse_raw2 = math.sqrt(np.mean((preds2 - values) ** 2))
    rmse_iso2 = math.sqrt(np.mean((corrected2 - values) ** 2))
    assert not iso_used2
    assert rmse_iso2 > rmse_raw2 + cfg_loose.iso_rmse_tol - 1e-9


def test_probe_better_child_priority():
    time = np.linspace(0.1, 9.0, 90)
    left_primary = np.concatenate(
        [
            midilli_model(time[:25], 0.02, 1.05, -4e-4),
            midilli_model(time[25:45], 0.03, 1.1, -3e-4) + 0.025,
        ]
    )
    right_segment = midilli_model(time[45:], 0.028, 1.0, -2e-4) + 0.05
    values = np.concatenate([left_primary, right_segment])

    cfg_probe = make_config(probe_better_child_passes=1)
    root_probe, _, _ = build_tree(time, values, cfg_probe)
    assert root_probe.split is not None
    left_child, right_child = root_probe.children
    assert left_child.children  # prioritized child should continue splitting
    assert not right_child.children  # probe child stops after evaluation

    cfg_all = make_config(probe_better_child=False)
    root_all, _, _ = build_tree(time, values, cfg_all)
    assert root_all.split is not None
    left_all, right_all = root_all.children
    assert left_all.children and right_all.children


def test_head_tail_model_preference():
    time = np.linspace(0.1, 12.0, 120)
    base = page_model(time, 0.02, 1.1)
    tail = midilli_model(time[-20:], 0.028, 1.0, -4e-4)
    values = base.copy()
    values[-20:] = tail

    cache = FitCache()
    cfg = make_config(min_points_root=20, min_points_leaf=10)

    head_result = select_best_model(0, 20, time, values, cache, cfg)
    assert head_result is not None
    head_fit, reason_head = head_result
    assert head_fit.family == "Page"
    assert reason_head.startswith("page")

    tail_start = 100
    tail_result = select_best_model(tail_start, 120, time, values, cache, cfg)
    assert tail_result is not None
    tail_fit, reason_tail = tail_result
    assert tail_fit.family == "Midilli"
    assert "midilli" in reason_tail
