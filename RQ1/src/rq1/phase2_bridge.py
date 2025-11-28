"""Bridge utilities connecting Phase-2 Midilli parameter surfaces to downstream sims."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import sys

import joblib
import numpy as np
import pandas as pd

# -------------------------------------------------------------------
# Path setup: compute repo root and add <repo>/src so we can import
# phase2_common (FeaturePreprocessor, design builders, etc.).
#
# This file lives at:
#   <repo>/RQ1/src/rq1/phase2_bridge.py
#
# So:
#   parents[0] -> .../rq1
#   parents[1] -> .../RQ1/src
#   parents[2] -> .../RQ1
#   parents[3] -> <repo> (Codex_Chatgpt_drying)
# -------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _PROJECT_ROOT / "src"
_SCRIPTS_ROOT = _PROJECT_ROOT / "scripts"

for _path in (str(_SRC_ROOT), str(_SCRIPTS_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from phase2_common import (  # type: ignore[import]
    FeaturePreprocessor,  # imported so joblib can unpickle; may look unused
    build_elasticnet_design,
    build_gbdt_matrix,
)

DEFAULT_PHASE2_MODELS_ROOT = _PROJECT_ROOT / "outputs" / "phase2" / "models"


@dataclass
class MidilliSurfaces:
    preprocessor: Any
    model_kL: Any
    model_nL: Any
    model_bL: Any
    model_kR: Any
    model_nR: Any
    model_bR: Any
    model_offsetR: Any
    model_tshiftR: Any
    meta: dict


@dataclass
class MidilliParams:
    kL: float
    nL: float
    bL: float
    kR: float
    nR: float
    bR: float
    offsetR_at_join: float
    right_time_shift_at_boundary_min: float
    t_split_min: float


_SURFACES: Optional[MidilliSurfaces] = None


def load_midilli_surfaces(models_root: Path | None = None) -> MidilliSurfaces:
    """
    Load Phase-2 Midilli surfaces (preprocessor + regressors + meta.json).
    Cache the result so we only hit disk once.
    """
    global _SURFACES
    if _SURFACES is not None:
        return _SURFACES

    root = models_root or DEFAULT_PHASE2_MODELS_ROOT

    preprocessor = joblib.load(root / "preprocessor.joblib")
    model_kL = joblib.load(root / "kL.joblib")
    model_nL = joblib.load(root / "nL.joblib")
    model_bL = joblib.load(root / "bL.joblib")
    model_kR = joblib.load(root / "kR.joblib")
    model_nR = joblib.load(root / "nR.joblib")
    model_bR = joblib.load(root / "bR.joblib")
    model_offsetR = joblib.load(root / "offsetR.joblib")
    model_tshiftR = joblib.load(root / "join_tshift.joblib")

    meta_path = root / "meta.json"
    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    _SURFACES = MidilliSurfaces(
        preprocessor=preprocessor,
        model_kL=model_kL,
        model_nL=model_nL,
        model_bL=model_bL,
        model_kR=model_kR,
        model_nR=model_nR,
        model_bR=model_bR,
        model_offsetR=model_offsetR,
        model_tshiftR=model_tshiftR,
        meta=meta,
    )
    return _SURFACES


def _predict_single_target(
    model: Any,
    target_name: str,
    X_proc: pd.DataFrame,
    targets_meta: dict,
) -> float:
    """
    Predict a single Midilli target (kL, nL, ...) using the same design logic
    as in Phase-2 training.

    - If family == 'elasticnet': use build_elasticnet_design(X_proc)
    - If family == 'gbdt':      use build_gbdt_matrix(X_proc)
    - Else:                     fall back to plain numpy array.
    """
    meta = targets_meta.get(target_name, {})
    family = meta.get("family", "elasticnet")

    if family == "elasticnet":
        X_design = build_elasticnet_design(X_proc)
    elif family == "gbdt":
        X_design = build_gbdt_matrix(X_proc)
    else:
        X_design = X_proc.to_numpy(dtype=float)

    y_pred = model.predict(X_design)
    return float(y_pred[0])


def predict_midilli_params_for_operating_point(
    T_C: float,
    v_ms: float,
    thickness_mm: float,
    RH_mid_pct: float,
    t_split_min: float,
    models_root: Path | None = None,
) -> MidilliParams:
    """
    Use Phase-2 surfaces to predict Midilli parameters for a single operating point.

    Inputs must match Phase-2 feature columns (T_C, v_ms, thickness_mm, RH_mid_pct).
    `t_split_min` is supplied by the caller; it is not predicted here.
    """
    surfaces = load_midilli_surfaces(models_root)

    row = pd.DataFrame(
        [
            {
                "T_C": T_C,
                "v_ms": v_ms,
                "thickness_mm": thickness_mm,
                "RH_mid_pct": RH_mid_pct,
            }
        ]
    )

    # First stage: feature preprocessing
    X_proc = surfaces.preprocessor.transform(row)

    # If the preprocessor returns a numpy array, wrap it into a DataFrame
    # with output columns from the preprocessor (Phase-2 stores these).
    if isinstance(X_proc, np.ndarray):
        cols = getattr(surfaces.preprocessor, "output_columns_", None)
        if cols is None:
            raise RuntimeError("Preprocessor did not expose output_columns_.")
        X_proc = pd.DataFrame(X_proc, columns=cols)

    targets_meta = surfaces.meta.get("targets", {})

    kL = _predict_single_target(surfaces.model_kL, "kL", X_proc, targets_meta)
    nL = _predict_single_target(surfaces.model_nL, "nL", X_proc, targets_meta)
    bL = _predict_single_target(surfaces.model_bL, "bL", X_proc, targets_meta)
    kR = _predict_single_target(surfaces.model_kR, "kR", X_proc, targets_meta)
    nR = _predict_single_target(surfaces.model_nR, "nR", X_proc, targets_meta)
    bR = _predict_single_target(surfaces.model_bR, "bR", X_proc, targets_meta)
    offsetR = _predict_single_target(surfaces.model_offsetR, "offsetR", X_proc, targets_meta)
    tshiftR = _predict_single_target(surfaces.model_tshiftR, "tshiftR", X_proc, targets_meta)

    return MidilliParams(
        kL=kL,
        nL=nL,
        bL=bL,
        kR=kR,
        nR=nR,
        bR=bR,
        offsetR_at_join=offsetR,
        right_time_shift_at_boundary_min=tshiftR,
        t_split_min=t_split_min,
    )


def _midilli_curve(t_min: np.ndarray, k: float, n: float, b: float) -> np.ndarray:
    """
    Standard Midilli MR curve:
        MR(t) = exp(-k * t^n) + b * t
    where t is in minutes.
    """
    t = np.asarray(t_min, dtype=float)
    t = np.clip(t, 0.0, None)
    return np.exp(-k * np.power(t, n)) + b * t


def evaluate_piecewise_midilli_MR(
    t_s: np.ndarray,
    params: MidilliParams,
    mr_floor: float = 0.0,
) -> np.ndarray:
    """
    Evaluate the piecewise Midilli MR(t) for an array of times in seconds.

    Global time axis logic mirrors src/phase2c_predict.py:
    - Left segment uses (kL, nL, bL) from t=0 up to t_split_min.
    - Right segment uses (kR, nR, bR) with a time shift and a vertical offset.
    - Right segment becomes active after t_split_min + right_time_shift_at_boundary_min.
    """
    t_min = np.asarray(t_s, dtype=float) / 60.0

    kL = params.kL
    nL = params.nL
    bL = params.bL
    kR = params.kR
    nR = params.nR
    bR = params.bR
    offsetR = params.offsetR_at_join
    tshift = params.right_time_shift_at_boundary_min
    t_split = params.t_split_min

    # Left segment
    tL = np.clip(t_min, 0.0, t_split)
    MR_L = _midilli_curve(tL, kL, nL, bL)

    # Right segment: local time starts at join_time_right_min
    join_time_right_min = t_split + tshift
    tR_local = np.maximum(0.0, t_min - join_time_right_min)
    MR_R_raw = _midilli_curve(tR_local, kR, nR, bR)
    MR_R_shifted = MR_R_raw + offsetR

    mask_left = t_min <= t_split
    MR = np.where(mask_left, MR_L, MR_R_shifted)

    if mr_floor > 0.0:
        MR = np.maximum(MR, mr_floor)

    return MR


def evaluate_piecewise_midilli_Xdb(
    t_s: np.ndarray,
    params: MidilliParams,
    X0_db: float,
    X_eq_db: float,
    mr_floor: float = 0.0,
) -> np.ndarray:
    """
    Convert MR(t) into dry-basis moisture content X_db(t):
        X_db(t) = X_eq_db + MR(t) * (X0_db - X_eq_db)
    """
    MR = evaluate_piecewise_midilli_MR(t_s, params, mr_floor=mr_floor)
    return X_eq_db + MR * (X0_db - X_eq_db)

