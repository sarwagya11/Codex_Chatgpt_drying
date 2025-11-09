"""Utilities for the phase-2 drying-parameter modelling workflow."""  # CHANGE: Module docstring retained

from __future__ import annotations  # CHANGE: Future annotations retained

import json  # CHANGE: Import for config loading
import logging  # CHANGE: Import for centralized logging
from logging import Logger  # CHANGE: Explicit logger type
from pathlib import Path, PureWindowsPath  # CHANGE: Path handling
from typing import Any, Dict, Iterable, MutableMapping  # CHANGE: Typing helpers

import numpy as np  # CHANGE: Numerical ops retained
import pandas as pd  # CHANGE: DataFrame ops retained

try:  # CHANGE: Optional YAML config support
    import yaml  # type: ignore  # CHANGE: Optional dependency import
    HAVE_YAML = True  # CHANGE: Flag for YAML availability
except ImportError:  # CHANGE: Handle missing dependency
    HAVE_YAML = False  # CHANGE: YAML unavailable fallback

BASE_FEATURE_COLUMNS: list[str] = [
    "T",
    "RH",
    "velocity",
    "thickness",
    "segment_duration",
    "segment_position",
]
"""Core feature columns required for parameter modelling."""

OPTIONAL_FEATURE_COLUMNS: list[str] = [
    "segment_mid_time",
    "join_gap",
    "left_slope",
    "right_slope",
    "resid_rms_segment",
    "lowess_curvature",
    "lowess_amplitude",
    "is_root",
    "is_leaf",
    "min_points_constraint_hit",
]
"""Auxiliary structural features populated when available."""

ENGINEERED_FEATURE_COLUMNS: list[str] = [
    "inv_thickness_sq",
    "T_RH_ratio",
    "temp_vel",
]
"""Derived interactions computed from the physical drying conditions."""

ALL_FEATURE_COLUMNS: list[str] = (
    BASE_FEATURE_COLUMNS + OPTIONAL_FEATURE_COLUMNS + ENGINEERED_FEATURE_COLUMNS
)
"""Full set of model features (raw + optional + engineered)."""


def load_config(config_path: Path | None) -> Dict[str, Any]:  # CHANGE: Config loader helper
    """Load a JSON/YAML configuration file when provided."""  # CHANGE: Docstring
    if config_path is None:  # CHANGE: No config specified
        return {}  # CHANGE: Return empty dict
    path = Path(config_path)  # CHANGE: Ensure Path instance
    if not path.exists():  # CHANGE: Guard missing file
        raise FileNotFoundError(f"Config file not found: {path}")  # CHANGE: Error message
    suffix = path.suffix.lower()  # CHANGE: Determine format
    if suffix in {".json", ""}:  # CHANGE: JSON support
        return json.loads(path.read_text())  # CHANGE: Parse JSON
    if suffix in {".yml", ".yaml"}:  # CHANGE: YAML support branch
        if not HAVE_YAML:  # CHANGE: Require PyYAML
            raise RuntimeError("YAML config requested but PyYAML is not installed.")  # CHANGE: Error
        return yaml.safe_load(path.read_text()) or {}  # type: ignore[arg-type]  # CHANGE: Parse YAML
    raise ValueError(f"Unsupported config format: {suffix}")  # CHANGE: Unsupported suffix


def extract_config_section(config: Dict[str, Any], section: str) -> Dict[str, Any]:  # CHANGE: Section helper
    """Return a subsection of the configuration dictionary."""  # CHANGE: Docstring
    value = config.get(section, {})  # CHANGE: Fetch section
    if isinstance(value, MutableMapping):  # CHANGE: Ensure mapping
        return dict(value)  # CHANGE: Return copy
    return {}  # CHANGE: Fallback empty dict


def normalize_log_level(level: str | int) -> int:  # CHANGE: Normalize logging level
    """Convert various log-level representations to ``logging`` constants."""  # CHANGE: Docstring
    if isinstance(level, int):  # CHANGE: Already integer
        return level  # CHANGE: Return as-is
    if isinstance(level, str):  # CHANGE: String input
        value = level.strip().upper()  # CHANGE: Normalize string
        return getattr(logging, value, logging.INFO)  # CHANGE: Lookup constant
    return logging.INFO  # CHANGE: Default fallback


def configure_logging(
    name: str,
    *,
    log_path: Path | None = None,
    level: str | int = "INFO",
    propagate: bool = False,
) -> Logger:  # CHANGE: Centralized logger factory
    """Create or update a module-level logger with stream/file handlers."""  # CHANGE: Docstring
    logger = logging.getLogger(name)  # CHANGE: Acquire logger
    logger.setLevel(normalize_log_level(level))  # CHANGE: Apply level
    logger.propagate = propagate  # CHANGE: Control propagation

    if not logger.handlers:  # CHANGE: Avoid duplicate handlers
        stream_handler = logging.StreamHandler()  # CHANGE: Console handler
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )  # CHANGE: Formatter for console
        logger.addHandler(stream_handler)  # CHANGE: Attach handler

    if log_path is not None:  # CHANGE: Optional file logging
        path = Path(log_path)  # CHANGE: Ensure Path
        path.parent.mkdir(parents=True, exist_ok=True)  # CHANGE: Create directory
        existing_files = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]  # CHANGE: Inspect
        for handler in existing_files:  # CHANGE: Remove stale handlers
            logger.removeHandler(handler)  # CHANGE: Detach previous file handler
        file_handler = logging.FileHandler(path)  # CHANGE: New file handler
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )  # CHANGE: File format
        logger.addHandler(file_handler)  # CHANGE: Attach file handler

    return logger  # CHANGE: Return configured logger


def ensure_directory(path: Path) -> Path:  # CHANGE: Directory helper
    """Ensure the directory exists and return it."""  # CHANGE: Docstring
    directory = Path(path)  # CHANGE: Cast to Path
    directory.mkdir(parents=True, exist_ok=True)  # CHANGE: Create directory
    return directory  # CHANGE: Return path


def resolve_dataset_path(raw_path: str | Path, data_root: Path) -> Path:  # CHANGE: Existing helper retained
    """Resolve a dataset path that may contain platform-specific prefixes."""  # CHANGE: Docstring retained

    candidate = Path(raw_path)  # CHANGE: Convert to Path
    if candidate.exists():  # CHANGE: Prefer existing path
        return candidate  # CHANGE: Return as-is

    windows_path = PureWindowsPath(str(raw_path))  # CHANGE: Windows compatibility
    name = windows_path.name  # CHANGE: Extract file name
    if not name:  # CHANGE: Guard empty name
        name = Path(str(raw_path)).name  # CHANGE: Fallback extraction

    possibilities: list[Path] = []  # CHANGE: Candidate list
    if name:  # CHANGE: Non-empty name guard
        possibilities.append(data_root / name)  # CHANGE: Candidate with root

    parent = windows_path.parent  # CHANGE: Parent path
    if str(parent) not in {"", "."}:  # CHANGE: Non-trivial parent
        possibilities.append(data_root / parent.name / name)  # CHANGE: Another candidate

    for option in possibilities:  # CHANGE: Iterate possibilities
        if option.exists():  # CHANGE: Check existence
            return option  # CHANGE: Return resolved path

    if possibilities:  # CHANGE: If candidates existed
        return possibilities[0]  # CHANGE: Return first as fallback

    raise FileNotFoundError(f"Could not resolve dataset path from {raw_path!r}")  # CHANGE: Error


def prepare_feature_frame(raw_segments: pd.DataFrame) -> pd.DataFrame:
    """Return a design matrix with engineered features for modelling."""

    missing = [col for col in BASE_FEATURE_COLUMNS if col not in raw_segments.columns]
    if missing:
        raise KeyError(
            "Missing required columns for feature engineering: " + ", ".join(sorted(missing))
        )

    features = pd.DataFrame(index=raw_segments.index)
    for column in BASE_FEATURE_COLUMNS:
        features[column] = pd.to_numeric(raw_segments[column], errors="coerce")

    for column in OPTIONAL_FEATURE_COLUMNS:
        if column in raw_segments.columns:
            values = pd.to_numeric(raw_segments[column], errors="coerce")
        else:
            values = pd.Series(0.0, index=raw_segments.index, dtype=float)
        if column in {"is_root", "is_leaf", "min_points_constraint_hit"}:
            values = values.fillna(0.0).astype(float)
        features[column] = values

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


def signed_log1p(values: Iterable[float] | np.ndarray) -> np.ndarray:  # CHANGE: Signed log transform retained
    """Apply a sign-preserving ``log1p`` transform used for the Midilli ``b`` term."""  # CHANGE: Docstring retained

    arr = np.asarray(values, dtype=float)  # CHANGE: Convert to ndarray
    return np.sign(arr) * np.log1p(np.abs(arr))  # CHANGE: Compute transform


def inverse_signed_log1p(values: Iterable[float] | np.ndarray) -> np.ndarray:  # CHANGE: Inverse transform retained
    """Inverse of :func:`signed_log1p`."""  # CHANGE: Docstring retained

    arr = np.asarray(values, dtype=float)  # CHANGE: Convert to ndarray
    return np.sign(arr) * np.expm1(np.abs(arr))  # CHANGE: Invert transform


def midilli_curve(time: Iterable[float] | np.ndarray, k: float, n: float, b: float) -> np.ndarray:  # CHANGE: Midilli curve retained
    """Evaluate the Midilli model for given parameters."""  # CHANGE: Docstring retained

    t = np.asarray(time, dtype=float)  # CHANGE: Convert to ndarray
    return np.exp(-k * np.power(t, n)) + b * t  # CHANGE: Evaluate curve


def midilli_derivative(time: Iterable[float] | np.ndarray, k: float, n: float, b: float) -> np.ndarray:
    """Return the derivative of the Midilli model with respect to time."""

    t = np.asarray(time, dtype=float)
    safe_time = np.maximum(t, 1e-12)
    base = np.exp(-k * np.power(safe_time, n))
    derivative = -k * n * np.power(safe_time, n - 1.0) * base + b
    derivative = np.where(t <= 0.0, b, derivative)
    return derivative


def softplus(values: Iterable[float] | np.ndarray) -> np.ndarray:
    """Numerically stable softplus transform."""

    arr = np.asarray(values, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        positive_mask = arr > 20
        result = np.where(positive_mask, arr, np.log1p(np.exp(arr)))
    return result


def inverse_softplus(values: Iterable[float] | np.ndarray) -> np.ndarray:
    """Inverse of :func:`softplus` for positive inputs."""

    arr = np.asarray(values, dtype=float)
    arr = np.maximum(arr, 1e-12)
    with np.errstate(over="ignore", invalid="ignore"):
        large = arr > 20
        inverse = np.where(large, arr + np.log1p(-np.exp(-arr)), np.log(np.expm1(arr)))
    return inverse


def clip_mr(values: Iterable[float] | np.ndarray, *, low: float = 0.0, high: float = 1.1) -> np.ndarray:
    """Clip moisture-ratio values into the physically valid range."""

    arr = np.asarray(values, dtype=float)
    return np.clip(arr, low, high)
