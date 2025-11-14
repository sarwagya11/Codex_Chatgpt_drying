"""Shared utilities for the Phase-2 pipeline.

This module intentionally lives alongside the Phase-2 CLI entry points
so that the command line interfaces can import helpers without touching
legacy implementations that may exist elsewhere in the repository.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def _safe_version(import_name: str) -> Optional[str]:
    """Return a module's ``__version__`` if available."""

    try:
        module = __import__(import_name)
    except Exception:  # pragma: no cover - defensive programming
        return None

    return getattr(module, "__version__", None)


def write_run_meta(out_dir: Path, argv: List[str]) -> None:
    """Persist run metadata alongside CLI artefacts.

    Parameters
    ----------
    out_dir:
        Directory that will receive the ``run_meta.json`` file.  The directory
        is created if it does not already exist.
    argv:
        Raw command line arguments (``sys.argv``) for provenance tracking.
    """

    out_dir.mkdir(parents=True, exist_ok=True)

    meta: Dict[str, Any] = {
        "args": argv,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "package_versions": {
            "numpy": _safe_version("numpy"),
            "pandas": _safe_version("pandas"),
            "scikit-learn": _safe_version("sklearn"),
            "xgboost": _safe_version("xgboost"),
            "lightgbm": _safe_version("lightgbm"),
        },
    }

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:  # pragma: no cover - git may be unavailable
        git_hash = None
    else:
        git_hash = completed.stdout.strip() if completed.returncode == 0 else None

    meta["git_hash"] = git_hash

    run_meta_path = out_dir / "run_meta.json"
    run_meta_path.write_text(json.dumps(meta, indent=2))


# ---------------------------------------------------------------------------
# Dataset parsing helpers
# ---------------------------------------------------------------------------


@dataclass
class ParsedStem:
    dataset: str
    T_C: float
    v_ms: float
    thickness_mm: float
    RH_lo_pct: float
    RH_hi_pct: float
    RH_mid_pct: float


def _parse_temperature(stem: str) -> Optional[float]:
    import re

    match = re.search(r"(?i)t[_]?([0-9]{2,3})", stem)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_velocity(stem: str) -> Optional[float]:
    import re

    match = re.search(r"(?i)v([0-9]+(?:p[0-9]+)?)", stem)
    if match:
        body = match.group(1).replace("p", ".")
        try:
            return float(body)
        except ValueError:
            return None
    return None


def _parse_thickness(stem: str) -> Optional[float]:
    import re

    match = re.search(r"(?i)t[_]?([0-9]+(?:p[0-9]+)?)mm", stem)
    if match:
        body = match.group(1).replace("p", ".")
        try:
            return float(body)
        except ValueError:
            return None
    return None


def _parse_rh(stem: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    lower = stem.lower()
    if "rh" not in lower:
        return (None, None, None)

    for token in lower.split("_"):
        if token.startswith("rh") and "-" in token and token.endswith("%"):
            body = token[2:-1]
            try:
                lo_str, hi_str = body.split("-")
                lo = float(lo_str)
                hi = float(hi_str)
            except Exception:
                break
            mid = (lo + hi) / 2.0
            return (lo, hi, mid)

    return (None, None, None)


def parse_dataset_stem(stem: str) -> Dict[str, Any]:
    """Parse environmental covariates encoded in a dataset folder name."""

    stem = stem.strip()
    if not stem:
        raise ValueError("Dataset stem must be a non-empty string")

    T_C = _parse_temperature(stem)
    v_ms = _parse_velocity(stem)
    thickness = _parse_thickness(stem)
    RH_lo, RH_hi, RH_mid = _parse_rh(stem)

    return {
        "dataset": stem,
        "T_C": float(T_C) if T_C is not None else math.nan,
        "v_ms": float(v_ms) if v_ms is not None else math.nan,
        "thickness_mm": float(thickness) if thickness is not None else math.nan,
        "RH_lo_pct": float(RH_lo) if RH_lo is not None else math.nan,
        "RH_hi_pct": float(RH_hi) if RH_hi is not None else math.nan,
        "RH_mid_pct": float(RH_mid) if RH_mid is not None else math.nan,
    }


# ---------------------------------------------------------------------------
# Raw data loading
# ---------------------------------------------------------------------------


REQUIRED_RAW_COLUMNS = ("time_min", "mr")


def load_raw_timeseries(raw_dir: Path, stem: str) -> pd.DataFrame:
    """Load the observed MR curve for ``stem``.

    Parameters
    ----------
    raw_dir:
        Directory containing ``<stem>.csv`` files.
    stem:
        Dataset identifier (without extension).
    """

    csv_path = raw_dir / f"{stem}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Raw data CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    missing = [col for col in REQUIRED_RAW_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Raw CSV {csv_path} missing required columns: {', '.join(missing)}"
        )

    return df[list(REQUIRED_RAW_COLUMNS)].copy()


# ---------------------------------------------------------------------------
# Curve reconstruction helpers
# ---------------------------------------------------------------------------


def _midilli_curve(t: np.ndarray, k: float, n: float, b: float, is_page: bool) -> np.ndarray:
    """Evaluate the Midilli (or Page when ``is_page``) curve."""

    if is_page:
        b = 0.0
    return np.exp(-(k * np.power(t, n))) + b * t


def _clip_bounds(value: np.ndarray, lower: float, upper: float) -> np.ndarray:
    return np.clip(value, lower, upper)


K_BOUNDS = (1e-6, 1e-1)
N_BOUNDS = (0.4, 2.2)
B_BOUNDS = (-5e-3, 5e-3)
OFFSET_BOUNDS = (-0.05, 0.05)
TSHIFT_BOUNDS = (-45.0, 45.0)


def apply_bounds(name: str, values: np.ndarray) -> np.ndarray:
    """Apply parameter bounds defined for Phase-2 targets."""

    bounds_map = {
        "k": K_BOUNDS,
        "n": N_BOUNDS,
        "b": B_BOUNDS,
        "offset": OFFSET_BOUNDS,
        "tshift": TSHIFT_BOUNDS,
    }

    if name not in bounds_map:
        return values

    lower, upper = bounds_map[name]
    return np.clip(values, lower, upper)


def reconstruct_piecewise(
    time_min: Iterable[float],
    left_params: Mapping[str, float],
    right_params: Mapping[str, float],
    t_split: float,
    offset_right: float,
    tshift_right: float,
    is_page_left: bool,
    is_page_right: bool,
) -> Dict[str, np.ndarray]:
    """Rebuild a piecewise Midilli/Page curve with continuity guards.

    Returns a dictionary containing the left curve, the raw right curve, the
    level-shifted right curve, and the final guarded prediction.
    """

    time_arr = np.asarray(list(time_min), dtype=float)
    if time_arr.ndim != 1:
        raise ValueError("time_min must be one-dimensional")

    left_t = np.clip(time_arr, a_min=0.0, a_max=None)
    right_t = np.clip(time_arr - t_split + tshift_right, a_min=0.0, a_max=None)

    kL = float(left_params["k"])
    nL = float(left_params["n"])
    bL = float(left_params["b"])
    kR = float(right_params["k"])
    nR = float(right_params["n"])
    bR = float(right_params["b"])

    left_curve = _midilli_curve(left_t, kL, nL, bL, is_page_left)
    right_raw = _midilli_curve(right_t, kR, nR, bR, is_page_right)
    right_shifted = right_raw + offset_right

    final = left_curve.copy()
    right_mask = time_arr >= t_split
    if right_mask.any():
        join_idx = np.searchsorted(time_arr, t_split, side="left")
        join_value = left_curve[join_idx - 1] if join_idx > 0 else left_curve[0]
        guarded_right = right_shifted[right_mask]
        guarded_right = np.minimum(guarded_right, join_value)
        guarded_right = np.minimum.accumulate(guarded_right)
        final[right_mask] = guarded_right

    final = np.maximum(final, 0.0)

    return {
        "time": time_arr,
        "left": left_curve,
        "right_raw": right_raw,
        "right_shifted": right_shifted,
        "final": final,
    }


# ---------------------------------------------------------------------------
# Feature preprocessing
# ---------------------------------------------------------------------------


class FeaturePreprocessor:
    """Median-impute numeric features and add missing indicators."""

    def __init__(self, feature_names: Iterable[str]):
        self.feature_names = list(feature_names)
        self.medians_: Dict[str, float] = {}
        self.output_columns_: List[str] = []

    def fit(self, X: pd.DataFrame) -> "FeaturePreprocessor":
        medians: Dict[str, float] = {}
        for name in self.feature_names:
            series = X[name]
            med = float(series.median(skipna=True)) if not series.dropna().empty else 0.0
            medians[name] = med
        self.medians_ = medians
        self.output_columns_ = []
        for name in self.feature_names:
            self.output_columns_.append(name)
            self.output_columns_.append(f"{name}_missing")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self.medians_:
            raise RuntimeError("FeaturePreprocessor must be fitted before transform().")

        data: MutableMapping[str, Any] = {}
        for name in self.feature_names:
            series = X[name].astype(float)
            missing = series.isna().astype(float)
            filled = series.fillna(self.medians_[name])
            data[name] = filled
            data[f"{name}_missing"] = missing
        return pd.DataFrame(data, index=X.index)

    def fit_transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return self.fit(X).transform(X)

    def get_feature_names_out(self) -> List[str]:
        if not self.output_columns_:
            raise RuntimeError("FeaturePreprocessor has not been fitted yet")
        return list(self.output_columns_)


def build_elasticnet_design(df: pd.DataFrame) -> np.ndarray:
    """Construct the polynomial feature matrix for Elastic Net models."""

    required = ["T_C", "RH_mid_pct", "v_ms", "thickness_mm"]
    for name in required:
        if name not in df.columns:
            raise KeyError(f"Feature '{name}' missing from dataframe")

    interactions = {
        "T_C*RH_mid_pct": df["T_C"] * df["RH_mid_pct"],
        "T_C*v_ms": df["T_C"] * df["v_ms"],
        "v_ms*thickness_mm": df["v_ms"] * df["thickness_mm"],
    }

    columns: List[np.ndarray] = [df[name].to_numpy(dtype=float) for name in required]
    columns.extend(arr.to_numpy(dtype=float) for arr in interactions.values())

    # Add missing indicators at the end to keep them available to the model.
    indicator_cols = [
        col for col in df.columns if col.endswith("_missing") and col[:-8] in required
    ]
    columns.extend(df[name].to_numpy(dtype=float) for name in indicator_cols)

    return np.column_stack(columns)


def build_gbdt_matrix(df: pd.DataFrame) -> np.ndarray:
    """Return the design matrix for gradient boosting models."""

    return df.to_numpy(dtype=float)

