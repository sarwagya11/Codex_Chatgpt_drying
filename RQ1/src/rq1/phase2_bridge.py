"""Bridge utilities connecting Phase-2 Midilli parameter surfaces to downstream sims."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

# Repo root: .../Codex_Chatgpt_drying
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _PROJECT_ROOT /"RQ1"/ "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from phase2_common import (  # type: ignore
    FeaturePreprocessor,
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


def _predict_single_target(
    model: Any,
    target_name: str,
    X_proc: pd.DataFrame,
    targets_meta: dict,
) -> float:
    """Predict a single target using the Phase-2 design logic."""

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


def load_midilli_surfaces(models_root: Path | None = None) -> MidilliSurfaces:
    """Load Phase-2 Midilli surfaces and cache them."""
    print(_PROJECT_ROOT)
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


def predict_midilli_params_for_operating_point(
    T_C: float,
    v_ms: float,
    thickness_mm: float,
    RH_mid_pct: float,
    t_split_min: float,
    models_root: Path | None = None,
) -> MidilliParams:
    """Predict Midilli parameters for a single operating point."""

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

    X_proc = surfaces.preprocessor.transform(row)

    targets_meta = surfaces.meta.get("targets", {})

    kL = _predict_single_target(surfaces.model_kL, "kL", X_proc, targets_meta)
    nL = _predict_single_target(surfaces.model_nL, "nL", X_proc, targets_meta)
    bL = _predict_single_target(surfaces.model_bL, "bL", X_proc, targets_meta)
    kR = _predict_single_target(surfaces.model_kR, "kR", X_proc, targets_meta)
    nR = _predict_single_target(surfaces.model_nR, "nR", X_proc, targets_meta)
    bR = _predict_single_target(surfaces.model_bR, "bR", X_proc, targets_meta)
    offsetR = _predict_single_target(
        surfaces.model_offsetR, "offsetR", X_proc, targets_meta
    )
    tshiftR = _predict_single_target(
        surfaces.model_tshiftR, "tshiftR", X_proc, targets_meta
    )

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
    """Standard Midilli MR curve."""

    t = np.asarray(t_min, dtype=float)
    return np.exp(-k * np.power(t, n)) + b * t


def evaluate_piecewise_midilli_MR(
    t_s: np.ndarray,
    params: MidilliParams,
    mr_floor: float = 0.0,
) -> np.ndarray:
    """Evaluate piecewise Midilli MR(t) on a global time axis."""

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

    tL = np.clip(t_min, 0.0, t_split)
    MR_L = _midilli_curve(tL, kL, nL, bL)

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
    """Map MR(t) to dry-basis moisture content X_db(t)."""

    MR = evaluate_piecewise_midilli_MR(t_s, params, mr_floor=mr_floor)
    return X_eq_db + MR * (X0_db - X_eq_db)
