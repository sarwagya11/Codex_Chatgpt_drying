"""Preprocessing utilities for Phase-1 drying kinetics datasets."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


TIME_CANDIDATES = ("time_min", "t_min", "time")
MR_CANDIDATES = ("mr", "moisture_ratio")
X_CANDIDATES = ("x_db", "x", "moisture", "moisture_content")


@dataclass
class PreprocessResult:
    t: np.ndarray
    mr_raw: np.ndarray
    mr_iso: np.ndarray
    metadata: Dict[str, object]


def _find_column(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    lower_map = {col.lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def _load_dataframe(path: str) -> pd.DataFrame:
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in {".xls", ".xlsx"}:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
    return df


def parse_filename_hints(path: str) -> Dict[str, Optional[float]]:
    """Extract experimental hints from filename tokens.

    Supported hints:
        * Temperature "T_40" -> T_C = 40
        * Velocity "v1p1" -> v_ms = 1.1
        * Relative humidity "RH_35-38%" -> RH_pct = average of range (here 36.5)
        * Thickness "_t_6mm" -> thickness_mm = 6
    """

    basename = os.path.basename(path)
    stem, _ = os.path.splitext(basename)

    hints: Dict[str, Optional[float]] = {
        "T_C": None,
        "v_ms": None,
        "RH_pct": None,
        "thickness_mm": None,
    }

    temp_match = re.search(r"(?i)T[_-]?(\d+(?:\.\d+)?)", stem)
    if temp_match:
        try:
            hints["T_C"] = float(temp_match.group(1))
        except ValueError:
            pass

    vel_match = re.search(r"(?i)v(\d+(?:p\d+)?)", stem)
    if vel_match:
        token = vel_match.group(1).replace("p", ".")
        try:
            hints["v_ms"] = float(token)
        except ValueError:
            pass

    rh_match = re.search(r"(?i)RH[_-]?(\d+(?:\.\d+)?)(?:-(\d+(?:\.\d+)?))?", stem)
    if rh_match:
        try:
            low = float(rh_match.group(1))
            high = float(rh_match.group(2)) if rh_match.group(2) else low
            hints["RH_pct"] = (low + high) / 2.0
        except ValueError:
            pass

    thickness_match = re.search(r"(?i)_t_?(\d+(?:\.\d+)?)(?:mm)?", stem)
    if thickness_match:
        try:
            hints["thickness_mm"] = float(thickness_match.group(1))
        except ValueError:
            pass

    return hints


def preprocess_dataset(
    path: str,
    head_trim_min: float = 0.0,
    isotonic_clip: Tuple[float, float] = (0.0, 1.2),
) -> PreprocessResult:
    """Load and preprocess a Phase-1 drying dataset."""

    df = _load_dataframe(path)
    if df.empty:
        raise ValueError("Dataset is empty")

    time_col = _find_column(df, TIME_CANDIDATES)
    if not time_col:
        raise ValueError("Unable to locate time column; expected one of: " + ", ".join(TIME_CANDIDATES))

    mr_col = _find_column(df, MR_CANDIDATES)
    x_col = _find_column(df, X_CANDIDATES)

    if mr_col is None and x_col is None:
        raise ValueError("Dataset must contain either an MR column or an X/X_db column")

    data = df[[time_col]].copy()
    data.rename(columns={time_col: "time"}, inplace=True)

    flags: List[str] = []
    xe_used = 0.0
    x0_value: Optional[float] = None

    if mr_col is not None:
        mr_series = df[mr_col].astype(float)
    else:
        x_series = df[x_col].astype(float)
        valid_initial = x_series.dropna()
        if valid_initial.empty:
            raise ValueError("Cannot compute MR because X column has no valid values")
        x0_value = float(valid_initial.iloc[0])
        if not math.isfinite(x0_value) or x0_value == 0:
            raise ValueError("Invalid initial moisture content for MR calculation")
        mr_series = x_series / x0_value
        xe_used = 0.0

    data["MR_raw"] = mr_series
    data.replace([np.inf, -np.inf], np.nan, inplace=True)
    data.dropna(subset=["time", "MR_raw"], inplace=True)

    data.sort_values("time", inplace=True)
    data = data[~data["time"].duplicated(keep="first")]

    data["time"] = data["time"].astype(float)
    start_time = float(data["time"].iloc[0])
    data["time"] = data["time"] - start_time

    if head_trim_min > 0:
        data = data[data["time"] >= head_trim_min].copy()
        data["time"] -= data["time"].iloc[0]

    data["MR_raw"] = data["MR_raw"].clip(isotonic_clip[0], isotonic_clip[1])

    if len(data) < 3:
        raise ValueError("Need at least three data points after preprocessing")

    iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
    mr_iso = iso.fit_transform(data["time"], data["MR_raw"])

    metadata = {
        "file_path": os.path.abspath(path),
        "time_column": time_col,
        "mr_column": mr_col,
        "x_column": x_col,
        "X0": x0_value,
        "Xe_used": xe_used,
        "head_trim_min": head_trim_min,
        "clip_range": isotonic_clip,
        "flags": flags,
        "hints": parse_filename_hints(path),
    }

    return PreprocessResult(
        t=data["time"].to_numpy(dtype=float),
        mr_raw=data["MR_raw"].to_numpy(dtype=float),
        mr_iso=mr_iso.astype(float),
        metadata=metadata,
    )


__all__ = [
    "PreprocessResult",
    "parse_filename_hints",
    "preprocess_dataset",
]
