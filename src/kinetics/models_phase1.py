"""Model definitions and initial-guess helpers for Phase-1 drying kinetics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence

import numpy as np



def _effective_time(t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0:
        return t
    return np.maximum(t - tau, 0.0)


def page_model(t: np.ndarray, k: float, n: float, tau: float = 0.0) -> np.ndarray:
    t_eff = _effective_time(np.asarray(t, dtype=float), tau)
    return np.exp(-k * np.power(t_eff, n))


def midilli_a1_model(t: np.ndarray, k: float, n: float, b: float, tau: float = 0.0) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    t_eff = _effective_time(t, tau)
    return np.exp(-k * np.power(t_eff, n)) + b * t


def page_no_tau(params: Sequence[float], t: np.ndarray) -> np.ndarray:
    k, n = params
    return page_model(t, k, n, tau=0.0)


def page_tau(params: Sequence[float], t: np.ndarray) -> np.ndarray:
    k, n, tau = params
    return page_model(t, k, n, tau=tau)


def midilli_a1_no_tau(params: Sequence[float], t: np.ndarray) -> np.ndarray:
    k, n, b = params
    return midilli_a1_model(t, k, n, b, tau=0.0)


def midilli_a1_tau(params: Sequence[float], t: np.ndarray) -> np.ndarray:
    k, n, b, tau = params
    return midilli_a1_model(t, k, n, b, tau=tau)


MODEL_FUNCS: Dict[str, Callable[[Sequence[float], np.ndarray], np.ndarray]] = {
    "page_no_tau": page_no_tau,
    "page_tau": page_tau,
    "midilli_a1_no_tau": midilli_a1_no_tau,
    "midilli_a1_tau": midilli_a1_tau,
}

MODEL_PARAM_NAMES: Dict[str, List[str]] = {
    "page_no_tau": ["k", "n"],
    "page_tau": ["k", "n", "tau"],
    "midilli_a1_no_tau": ["k", "n", "b"],
    "midilli_a1_tau": ["k", "n", "b", "tau"],
}


@dataclass
class InitialGuess:
    params: np.ndarray
    param_names: List[str]


def _estimate_initial_k(t: np.ndarray, mr_iso: np.ndarray) -> float:
    t = np.asarray(t, dtype=float)
    mr_iso = np.asarray(mr_iso, dtype=float)
    mask = (mr_iso > 0.1) & (mr_iso < 0.99)
    t_filtered = t[mask]
    mr_filtered = mr_iso[mask]
    if t_filtered.size < 2:
        return 0.002

    cutoff = max(3, int(np.ceil(t_filtered.size * 0.3)))
    t_subset = t_filtered[:cutoff]
    mr_subset = mr_filtered[:cutoff]
    if np.any(mr_subset <= 0):
        mr_subset = mr_subset[mr_subset > 0]
        t_subset = t_subset[: mr_subset.size]
    if t_subset.size < 2 or mr_subset.size < 2:
        return 0.002

    try:
        y = -np.log(mr_subset)
        coeffs = np.polyfit(t_subset, y, deg=1)
        slope = coeffs[0]
        if np.isfinite(slope) and slope > 0:
            return float(slope)
    except Exception:
        pass
    return 0.002


def make_initial_guess(func_name: str, t: np.ndarray, mr_iso: np.ndarray) -> InitialGuess:
    func_name = func_name.lower()
    if func_name not in MODEL_PARAM_NAMES:
        raise KeyError(f"Unknown model variant: {func_name}")

    param_names = MODEL_PARAM_NAMES[func_name]
    params = []
    k0 = _estimate_initial_k(t, mr_iso)
    n0 = 1.0
    b0 = 0.0
    tau0 = 0.0

    for name in param_names:
        if name == "k":
            params.append(k0)
        elif name == "n":
            params.append(n0)
        elif name == "b":
            params.append(b0)
        elif name == "tau":
            params.append(tau0)
        else:
            params.append(1.0)

    return InitialGuess(params=np.array(params, dtype=float), param_names=param_names)


__all__ = [
    "MODEL_FUNCS",
    "MODEL_PARAM_NAMES",
    "InitialGuess",
    "make_initial_guess",
    "page_no_tau",
    "page_tau",
    "midilli_a1_no_tau",
    "midilli_a1_tau",
]
