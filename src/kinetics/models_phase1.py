"""Model definitions for phase-1 drying kinetics."""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from .fitters_phase1 import ModelSpec


# ---------------------------------------------------------------------------
# Base functions
# ---------------------------------------------------------------------------

def _page(time: np.ndarray, params: Dict[str, float]) -> np.ndarray:
    k = float(params["k"])
    n = float(params["n"])
    return np.exp(-k * np.power(time, n))


def _page_shift(time: np.ndarray, params: Dict[str, float]) -> np.ndarray:
    k = float(params["k"])
    n = float(params["n"])
    tau = float(params["tau"])
    shifted = np.maximum(time - tau, 0.0)
    return np.exp(-k * np.power(shifted, n))


def _midilli(time: np.ndarray, params: Dict[str, float]) -> np.ndarray:
    k = float(params["k"])
    n = float(params["n"])
    b = float(params["b"])
    return np.exp(-k * np.power(time, n)) + b * time


def _midilli_shift(time: np.ndarray, params: Dict[str, float]) -> np.ndarray:
    k = float(params["k"])
    n = float(params["n"])
    b = float(params["b"])
    tau = float(params["tau"])
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


def _page_initializer(time: np.ndarray, mr: np.ndarray) -> Dict[str, float]:
    k0, n0 = _shared_initial_guess(time, mr)
    return {"k": k0, "n": n0}


def _page_shift_initializer(time: np.ndarray, mr: np.ndarray) -> Dict[str, float]:
    k0, n0 = _shared_initial_guess(time, mr)
    tau_guess = float(_first_time_below_threshold(time, mr, 0.98))
    tau_guess = float(np.clip(tau_guess, 0.0, 10.0))
    return {"k": k0, "n": n0, "tau": tau_guess}


def _midilli_initializer(time: np.ndarray, mr: np.ndarray) -> Dict[str, float]:
    k0, n0 = _shared_initial_guess(time, mr)
    slope_guess = _tail_slope(time, mr)
    b0 = float(np.clip(slope_guess, -0.01, 0.0))
    return {"k": k0, "n": n0, "b": b0}


def _midilli_shift_initializer(time: np.ndarray, mr: np.ndarray) -> Dict[str, float]:
    k0, n0 = _shared_initial_guess(time, mr)
    tau_guess = float(_first_time_below_threshold(time, mr, 0.98))
    tau_guess = float(np.clip(tau_guess, 0.0, 10.0))
    b0 = float(np.clip(_tail_slope(time, mr), -0.01, 0.0))
    return {"k": k0, "n": n0, "b": b0, "tau": tau_guess}


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
        param_names=["k", "n"],
        predict=lambda t, p: np.clip(_page(t, p), 0.0, 1.1),
        initializer=_page_initializer,
        bounds={"k": (1e-6, 1.0), "n": (0.2, 2.5)},
    ),
    ModelSpec(
        name="page_shift",
        param_names=["k", "n", "tau"],
        predict=lambda t, p: np.clip(_page_shift(t, p), 0.0, 1.1),
        initializer=_page_shift_initializer,
        bounds={"k": (1e-6, 1.0), "n": (0.2, 2.5), "tau": (0.0, 10.0)},
    ),
    ModelSpec(
        name="midilli",
        param_names=["k", "n", "b"],
        predict=lambda t, p: np.clip(_midilli(t, p), 0.0, 1.1),
        initializer=_midilli_initializer,
        bounds={"k": (1e-6, 1.0), "n": (0.2, 2.5), "b": (-0.01, 0.0)},
    ),
    ModelSpec(
        name="midilli_shift",
        param_names=["k", "n", "b", "tau"],
        predict=lambda t, p: np.clip(_midilli_shift(t, p), 0.0, 1.1),
        initializer=_midilli_shift_initializer,
        bounds={
            "k": (1e-6, 1.0),
            "n": (0.2, 2.5),
            "b": (-0.01, 0.0),
            "tau": (0.0, 10.0),
        },
    ),
]

__all__ = ["MODEL_SPECS"]
