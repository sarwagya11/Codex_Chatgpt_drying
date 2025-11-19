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


def load_raw_timeseries(raw_root: Path, dataset_stem: str, xeq_db: float = 0.0) -> pd.DataFrame:
    """
    Expect a CSV per dataset with columns:
      time_min, X_db  (dry-basis moisture content)
    MR = (X_db - Xeq)/(X0 - Xeq); for Xeq=0 -> MR = X_db / X0.
    """
    csv = (raw_root / f"{dataset_stem}.csv")
    df = pd.read_csv(csv)
    if "X_db" not in df.columns or "time_min" not in df.columns:
        raise ValueError(f"{csv} must contain time_min and X_db")
    x0 = float(df["X_db"].iloc[0])
    mr = (df["X_db"].to_numpy() - xeq_db) / max(x0 - xeq_db, 1e-12)
    out = df.copy()
    out["mr"] = np.clip(mr, 0.0, 1.1)
    return out



# ---------------------------------------------------------------------------
# Curve reconstruction helpers
# ---------------------------------------------------------------------------


# Bounds used everywhere
K_BOUNDS = (1e-6, 1.0)
N_BOUNDS = (0.2, 3.5)
B_BOUNDS = (-5e-3, 5e-3)
OFFSET_BOUNDS = (-0.2, 0.2)
TSHIFT_BOUNDS = (0.0, 600.0)


def apply_bounds(kind: str, x: np.ndarray) -> np.ndarray:
    lo, hi = {
        "k": K_BOUNDS,
        "n": N_BOUNDS,
        "b": B_BOUNDS,
        "offset": OFFSET_BOUNDS,
        "tshift": TSHIFT_BOUNDS,
    }[kind]
    return np.clip(x, lo, hi)


def _midilli_curve(t: np.ndarray, k: float, n: float, b: float, is_page: bool) -> np.ndarray:
    # Page: MR = exp(-k * t^n), Midilli: exp(-k * t^n) + b * t
    base = np.exp(-k * np.power(np.maximum(t, 0.0), n))
    return base if is_page else (base + b * np.maximum(t, 0.0))


def reconstruct_piecewise(
    time_arr: np.ndarray,
    left: dict,
    right: dict,
    t_split: float,
    offsetR_at_join: float,
    tshift_right: float,
    is_page_left: bool = False,
    is_page_right: bool = False,
    mr_floor: float = 0.0,
) -> dict:
    time_arr = np.asarray(time_arr, dtype=float)

    # Left is evaluated on absolute time.
    MR_L = _midilli_curve(time_arr, left["k"], left["n"], left["b"], is_page_left)

    # Right is a local-time model. Its local time at the boundary is:
    # right_t(t=t_split) = max(0, 0 + tshift_right) = tshift_right
    # and for general t: right_t = max(0, (t - t_split) + tshift_right).
    right_t = np.clip(time_arr - float(t_split) + float(tshift_right), a_min=0.0, a_max=None)
    MR_R_raw = _midilli_curve(right_t, right["k"], right["n"], right["b"], is_page_right)
    MR_R_shifted = MR_R_raw + float(offsetR_at_join)

    # Compose final piecewise curve (left governs up to the split)
    right_mask = time_arr >= float(t_split)
    MR_final = MR_L.copy()
    if right_mask.any():
        rseg = np.minimum.accumulate(MR_R_shifted[right_mask])
        MR_final[right_mask] = rseg
    if mr_floor > 0:
        MR_final = np.maximum(MR_final, mr_floor)

    return {
        "time": time_arr,
        "left": MR_L,
        "right_raw": MR_R_raw,
        "right_shifted": MR_R_shifted,
        "final": MR_final,
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

