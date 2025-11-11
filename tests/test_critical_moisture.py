import importlib.util
import sys
from pathlib import Path

import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "kinetics" / "critical_moisture.py"

spec = importlib.util.spec_from_file_location("critical_moisture", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)

detect_critical_moisture = module.detect_critical_moisture


def _generate_piecewise_series():
    rng = np.random.default_rng(2024)
    base_values = np.linspace(0.68, 0.02, 220)
    midpoints = 0.5 * (base_values[:-1] + base_values[1:])
    split_threshold = 0.35

    rates = np.where(midpoints > split_threshold, 0.006, 0.006 - 0.045 * (midpoints - split_threshold))
    rates = np.clip(rates, 1e-4, None)

    dt = -(base_values[1:] - base_values[:-1]) / rates
    dt *= rng.uniform(0.95, 1.05, size=dt.size)

    time = np.concatenate([[0.0], np.cumsum(dt)])
    time = np.insert(time, 70, time[70])

    values = np.insert(base_values, 70, base_values[70])
    values += rng.normal(0.0, 1e-4, size=values.size)

    order = np.argsort(time)
    time_sorted = time[order]
    values_sorted = values[order]

    keep = np.ones(time_sorted.size, dtype=bool)
    keep[1:] = np.diff(time_sorted) > 0
    inc_time = time_sorted[keep]
    inc_values = values_sorted[keep]

    smoothed = lowess(inc_values, inc_time, frac=0.15, return_sorted=False)
    rate = -(smoothed[1:] - smoothed[:-1]) / np.diff(inc_time)
    mid_time = 0.5 * (inc_time[1:] + inc_time[:-1])
    mid_value = 0.5 * (inc_values[1:] + inc_values[:-1])

    positive = rate > 0
    mid_time = mid_time[positive]
    mid_value = mid_value[positive]

    idx = int(np.flatnonzero(mid_value <= 0.076)[0])
    t_crit = float(mid_time[idx])
    x_crit = float(mid_value[idx])

    return time, values, t_crit, x_crit


def test_detects_critical_moisture_point():
    time, values, t_crit, x_crit = _generate_piecewise_series()
    result = detect_critical_moisture(time, values)
    assert result is not None

    assert abs(result.t_split - t_crit) < 1e-6
    assert abs(result.Xc - x_crit) < 1e-6

    assert result.left_indices.size >= 8
    assert result.right_indices.size >= 8
    assert result.delta_bic >= 50.0
    assert result.b2 <= 0.0
    assert abs(result.b1) < 0.005


def test_returns_none_when_no_split_needed():
    rng = np.random.default_rng(2025)
    time = np.cumsum(rng.uniform(0.5, 1.0, size=120))
    x0 = 0.55
    rate = 0.01
    values = x0 - rate * time + rng.normal(0.0, 2e-4, size=time.size)

    result = detect_critical_moisture(time, values)
    assert result is None
