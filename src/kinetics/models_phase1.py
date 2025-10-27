"""Model definitions for phase-1 drying kinetics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

import numpy as np


ArrayLike = Sequence[float]


@dataclass(frozen=True)
class ModelSpec:
    """Description of an empirical drying kinetics model."""

    name: str
    param_names: Sequence[str]
    bounds: Sequence[tuple[float, float]]
    predict: Callable[[np.ndarray, np.ndarray], np.ndarray]
    initializer: Callable[[np.ndarray, np.ndarray], np.ndarray]

    def clip(self, params: np.ndarray) -> np.ndarray:
        params = np.asarray(params, dtype=float)
        clipped = params.copy()
        for idx, (lo, hi) in enumerate(self.bounds):
            clipped[idx] = np.clip(clipped[idx], lo, hi)
        return clipped


# ---------------------------------------------------------------------------
# Base functions
# ---------------------------------------------------------------------------

def _page(time: np.ndarray, params: np.ndarray) -> np.ndarray:
    k, n = params[:2]
    return np.exp(-k * np.power(time, n))


def _page_shift(time: np.ndarray, params: np.ndarray) -> np.ndarray:
    k, n, tau = params[:3]
    shifted = np.maximum(time - tau, 0.0)
    return np.exp(-k * np.power(shifted, n))


def _midilli(time: np.ndarray, params: np.ndarray) -> np.ndarray:
    k, n, b = params[:3]
    return np.exp(-k * np.power(time, n)) + b * time


def _midilli_shift(time: np.ndarray, params: np.ndarray) -> np.ndarray:
    k, n, b, tau = params[:4]
    shifted = np.maximum(time - tau, 0.0)
    return np.exp(-k * np.power(shifted, n)) + b * shifted


# ---------------------------------------------------------------------------
# Initialisation heuristics
# ---------------------------------------------------------------------------

def _shared_initial_guess(time: np.ndarray, mr: np.ndarray) -> tuple[float, float]:
    mask = (time > 0) & (mr > 0) & (mr < 0.999)
    if mask.sum() >= 2:
        x = np.log(time[mask])
        y = np.log(-np.log(np.clip(mr[mask], 1e-6, 1 - 1e-6)))
        slope, intercept = _linear_regression(x, y)
        n0 = float(np.clip(slope, 0.2, 2.5))
        k0 = float(np.clip(np.exp(intercept), 1e-6, 1.0))
        return k0, n0
    return 0.01, 1.0


def _linear_regression(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size == 0:
        return 1.0, 0.0
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    denom = float(((x - x_mean) ** 2).sum())
    if denom == 0:
        return 1.0, y_mean - x_mean
    slope = float(((x - x_mean) * (y - y_mean)).sum() / denom)
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _page_initializer(time: np.ndarray, mr: np.ndarray) -> np.ndarray:
    k0, n0 = _shared_initial_guess(time, mr)
    return np.array([k0, n0], dtype=float)


def _page_shift_initializer(time: np.ndarray, mr: np.ndarray) -> np.ndarray:
    k0, n0 = _shared_initial_guess(time, mr)
    tau_guess = float(_first_time_below_threshold(time, mr, 0.98))
    tau_guess = np.clip(tau_guess, 0.0, 10.0)
    return np.array([k0, n0, tau_guess], dtype=float)


def _midilli_initializer(time: np.ndarray, mr: np.ndarray) -> np.ndarray:
    k0, n0 = _shared_initial_guess(time, mr)
    slope_guess = _tail_slope(time, mr)
    b0 = float(np.clip(slope_guess, -0.01, 0.0))
    return np.array([k0, n0, b0], dtype=float)


def _midilli_shift_initializer(time: np.ndarray, mr: np.ndarray) -> np.ndarray:
    k0, n0 = _shared_initial_guess(time, mr)
    tau_guess = float(_first_time_below_threshold(time, mr, 0.98))
    tau_guess = np.clip(tau_guess, 0.0, 10.0)
    b0 = float(np.clip(_tail_slope(time, mr), -0.01, 0.0))
    return np.array([k0, n0, b0, tau_guess], dtype=float)


def _tail_slope(time: np.ndarray, mr: np.ndarray) -> float:
    if len(time) < 4:
        return -1e-3
    tail = min(6, len(time) // 2)
    x = time[-tail:]
    y = mr[-tail:]
    slope, _ = _linear_regression(x, y)
    return float(min(slope, 0.0))


def _first_time_below_threshold(time: np.ndarray, mr: np.ndarray, threshold: float) -> float:
    mask = mr < threshold
    if np.any(mask):
        idx = int(np.argmax(mask))
        return float(time[idx])
    return 0.0


MODEL_SPECS: List[ModelSpec] = [
    ModelSpec(
        name="page",
        param_names=("k", "n"),
        bounds=((1e-6, 1.0), (0.2, 2.5)),
        predict=lambda t, p: np.clip(_page(t, p), 0.0, 1.1),
        initializer=_page_initializer,
    ),
    ModelSpec(
        name="page_shift",
        param_names=("k", "n", "tau"),
        bounds=((1e-6, 1.0), (0.2, 2.5), (0.0, 10.0)),
        predict=lambda t, p: np.clip(_page_shift(t, p), 0.0, 1.1),
        initializer=_page_shift_initializer,
    ),
    ModelSpec(
        name="midilli",
        param_names=("k", "n", "b"),
        bounds=((1e-6, 1.0), (0.2, 2.5), (-0.01, 0.0)),
        predict=lambda t, p: np.clip(_midilli(t, p), 0.0, 1.1),
        initializer=_midilli_initializer,
    ),
    ModelSpec(
        name="midilli_shift",
        param_names=("k", "n", "b", "tau"),
        bounds=((1e-6, 1.0), (0.2, 2.5), (-0.01, 0.0), (0.0, 10.0)),
        predict=lambda t, p: np.clip(_midilli_shift(t, p), 0.0, 1.1),
        initializer=_midilli_shift_initializer,
    ),
]

__all__ = ["ModelSpec", "MODEL_SPECS"]
