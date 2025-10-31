"""Utilities for the phase-2 drying-parameter modelling workflow."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from typing import Iterable

import numpy as np
import pandas as pd

RAW_FEATURE_COLUMNS: list[str] = [
    "T",
    "RH",
    "velocity",
    "thickness",
    "segment_position",
    "segment_duration",
]
"""Columns expected to be present in the raw segment datasets."""

ENGINEERED_FEATURE_COLUMNS: list[str] = [
    "inv_thickness_sq",
    "T_RH_ratio",
    "temp_vel",
]
"""Derived features computed from the raw drying-condition inputs."""

ALL_FEATURE_COLUMNS: list[str] = RAW_FEATURE_COLUMNS + ENGINEERED_FEATURE_COLUMNS
"""Full set of model features (raw + engineered)."""


def resolve_dataset_path(raw_path: str | Path, data_root: Path) -> Path:
    """Resolve a dataset path that may contain platform-specific prefixes.

    Parameters
    ----------
    raw_path:
        Path stored in the summary index. On Windows this is typically an
        absolute ``D:\\`` path which will not exist on other systems.
    data_root:
        Directory containing the local data files.

    Returns
    -------
    Path
        Resolved path pointing at a file under ``data_root`` when necessary.

    Raises
    ------
    FileNotFoundError
        If the resolved file does not exist.
    """

    candidate = Path(raw_path)
    if candidate.exists():
        return candidate

    windows_path = PureWindowsPath(str(raw_path))
    name = windows_path.name
    if not name:
        name = Path(str(raw_path)).name

    possibilities: list[Path] = []
    if name:
        possibilities.append(data_root / name)

    parent = windows_path.parent
    if str(parent) not in {"", "."}:
        possibilities.append(data_root / parent.name / name)

    for option in possibilities:
        if option.exists():
            return option

    if possibilities:
        return possibilities[0]

    raise FileNotFoundError(f"Could not resolve dataset path from {raw_path!r}")


def prepare_feature_frame(raw_segments: pd.DataFrame) -> pd.DataFrame:
    """Return a design matrix with engineered features for modelling.

    The input must contain the columns listed in :data:`RAW_FEATURE_COLUMNS`.
    Missing values are coerced to ``NaN`` so downstream pipelines can impute
    them consistently.
    """

    missing = [col for col in RAW_FEATURE_COLUMNS if col not in raw_segments.columns]
    if missing:
        raise KeyError(
            "Missing required columns for feature engineering: " + ", ".join(missing)
        )

    features = pd.DataFrame(index=raw_segments.index)
    for column in RAW_FEATURE_COLUMNS:
        features[column] = pd.to_numeric(raw_segments[column], errors="coerce")

    thickness = features["thickness"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv_sq = np.where(thickness != 0, 1.0 / np.square(thickness), np.nan)
    features["inv_thickness_sq"] = inv_sq

    rh = features["RH"].to_numpy(dtype=float)
    temperature = features["T"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(rh != 0, temperature / rh, np.nan)
    features["T_RH_ratio"] = ratio

    velocity = features["velocity"].to_numpy(dtype=float)
    features["temp_vel"] = temperature * velocity

    return features


def signed_log1p(values: Iterable[float] | np.ndarray) -> np.ndarray:
    """Apply a sign-preserving ``log1p`` transform used for the Midilli ``b`` term."""

    arr = np.asarray(values, dtype=float)
    return np.sign(arr) * np.log1p(np.abs(arr))


def inverse_signed_log1p(values: Iterable[float] | np.ndarray) -> np.ndarray:
    """Inverse of :func:`signed_log1p`."""

    arr = np.asarray(values, dtype=float)
    return np.sign(arr) * np.expm1(np.abs(arr))


def midilli_curve(time: Iterable[float] | np.ndarray, k: float, n: float, b: float) -> np.ndarray:
    """Evaluate the Midilli model for given parameters."""

    t = np.asarray(time, dtype=float)
    return np.exp(-k * np.power(t, n)) + b * t
