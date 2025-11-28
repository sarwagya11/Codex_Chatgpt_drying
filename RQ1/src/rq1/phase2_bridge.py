"""Bridge utilities to use Phase-2 Midilli surfaces inside Phase-1 dryer sims."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import joblib
import numpy as np
import pandas as pd

PHASE2_MODELS_ROOT = Path(__file__).resolve().parents[2] / "outputs" / "phase2" / "models"


@dataclass
class Phase2Models:
    preprocessor: Any
    model_kL: Any
    model_nL: Any
    model_bL: Any
    model_kR: Any
    model_nR: Any
    model_bR: Any
    model_offsetR: Any
    model_join_tshift: Any
    meta: Dict[str, Any]
    feature_columns: List[str]


@dataclass
class SegmentParams:
    kL: float
    nL: float
    bL: float
    kR: float
    nR: float
    bR: float
    offsetR: float
    t_split_min: float
    t_shift_R_min: float


# ---------------------------------------------------------------------------
# Helpers mirroring Phase-2 preprocessing
# ---------------------------------------------------------------------------


def _load_meta(models_root: Path) -> Dict[str, Any]:
    for name in ("meta.json", "meta"):
        path = models_root / name
        if path.exists():
            return json.loads(path.read_text())
    raise FileNotFoundError(f"No meta JSON found under {models_root}")


def _extract_feature_columns(meta: Dict[str, Any], preprocessor: Any) -> List[str]:
    for key in ("raw_feature_columns", "features", "feature_columns"):
        cols = meta.get(key)
        if cols:
            return list(cols)
    for attr in ("feature_names", "feature_names_", "feature_names_in_"):
        cols = getattr(preprocessor, attr, None)
        if cols is not None:
            return list(cols)
    return []


def load_phase2_models(models_root: Path | None = None) -> Phase2Models:
    """Load all Phase-2 joblib models and associated metadata into a single struct."""

    root = models_root or PHASE2_MODELS_ROOT
    meta = _load_meta(root)
    preprocessor = joblib.load(root / "preprocessor.joblib")

    model_files = {
        "model_kL": "kL.joblib",
        "model_nL": "nL.joblib",
        "model_bL": "bL.joblib",
        "model_kR": "kR.joblib",
        "model_nR": "nR.joblib",
        "model_bR": "bR.joblib",
        "model_offsetR": "offsetR.joblib",
        "model_join_tshift": "join_tshift.joblib",
    }

    loaded: Dict[str, Any] = {}
    for key, filename in model_files.items():
        path = root / filename
        loaded[key] = joblib.load(path)

    feature_columns = _extract_feature_columns(meta, preprocessor)

    return Phase2Models(
        preprocessor=preprocessor,
        feature_columns=feature_columns,
        meta=meta,
        **loaded,
    )


def build_feature_row(
    T_C: float,
    RH_lo_pct: float,
    RH_hi_pct: float,
    v_ms: float,
    thickness_mm: float,
    models: Phase2Models,
) -> pd.DataFrame:
    """
    Build a single-row DataFrame with columns models.feature_columns.

    Attempts to honour Phase-2 feature naming recorded in metadata.  Any
    missing or unused columns are filled with NaN so the preprocessor can
    impute as trained.
    """

    mid_pct = (RH_lo_pct + RH_hi_pct) / 2.0 if not (np.isnan(RH_lo_pct) or np.isnan(RH_hi_pct)) else np.nan
    base: Dict[str, float] = {
        "T_C": T_C,
        "RH_lo_pct": RH_lo_pct,
        "RH_hi_pct": RH_hi_pct,
        "RH_mid_pct": mid_pct,
        "v_ms": v_ms,
        "thickness_mm": thickness_mm,
    }

    if models.feature_columns:
        data = {col: base.get(col, np.nan) for col in models.feature_columns}
        return pd.DataFrame([data], columns=models.feature_columns)

    return pd.DataFrame([base])


# ---------------------------------------------------------------------------
# Prediction utilities mirroring phase2c_predict behaviour
# ---------------------------------------------------------------------------


def _inverse_transform(values: np.ndarray, transform: str) -> np.ndarray:
    if transform == "log":
        return np.exp(values)
    if transform == "slog1p":
        sign = np.sign(values)
        return sign * np.expm1(np.abs(values))
    return values


def _bound_key_for_target(name: str) -> str | None:
    if name.startswith("k"):
        return "k"
    if name.startswith("n"):
        return "n"
    if name.startswith("b"):
        return "b"
    if name == "offsetR_at_join" or "offset" in name:
        return "offset"
    if "tshift" in name:
        return "tshift"
    return None


def _apply_bounds(values: np.ndarray, bound_key: str | None, meta: Dict[str, Any]) -> np.ndarray:
    bounds_map = meta.get("bounds", {}) if isinstance(meta, dict) else {}
    bounds = bounds_map.get(bound_key)
    if bounds is None:
        defaults = {
            "k": (1e-6, 1.0),
            "n": (0.2, 3.5),
            "b": (-5e-3, 5e-3),
            "offset": (-0.2, 2.0),
            "tshift": (0.0, 600.0),
        }
        bounds = defaults.get(bound_key)
    if bounds is None:
        return values
    lo, hi = bounds
    return np.clip(values, lo, hi)


def _get_family(meta: Dict[str, Any], target: str) -> str:
    return meta.get("targets", {}).get(target, {}).get("family", "elasticnet")


def _get_transform(meta: Dict[str, Any], target: str) -> str:
    return meta.get("transforms", {}).get(target, "identity")


def _build_elasticnet_design(df: pd.DataFrame, base_features: Iterable[str]) -> np.ndarray:
    base = list(base_features)
    for name in base:
        if name not in df.columns:
            raise KeyError(f"Feature '{name}' missing from dataframe")

    inv_T_K = 1.0 / (df["T_C"] + 273.15)
    log_v = np.log(np.clip(df["v_ms"], 1e-6, None))
    RH_frac = df.get("RH_mid_pct", df.get("RH_mid", df.get("RH_mid_frac", np.nan)))
    RH_frac = RH_frac / 100.0 if not isinstance(RH_frac, float) else RH_frac
    inv_RH = 1.0 / np.clip(RH_frac, 1e-6, None)
    thick_sq = df["thickness_mm"] ** 2

    interactions = [
        df["T_C"] * df.get("RH_mid_pct", df["RH_mid_pct"] if "RH_mid_pct" in df.columns else 0),
        df["T_C"] * df["v_ms"],
        df["v_ms"] * df["thickness_mm"],
    ]

    columns: List[np.ndarray] = []
    columns.extend(np.asarray(df[name], dtype=float) for name in base)
    columns.extend(np.asarray(arr, dtype=float) for arr in [inv_T_K, log_v, RH_frac, inv_RH, thick_sq])
    columns.extend(np.asarray(arr, dtype=float) for arr in interactions)

    indicator_cols = [col for col in df.columns if col.endswith("_missing") and col[:-8] in base]
    columns.extend(np.asarray(df[name], dtype=float) for name in indicator_cols)

    return np.column_stack(columns)


def _build_design_matrix(df: pd.DataFrame, family: str, base_features: Iterable[str]) -> np.ndarray:
    if family == "elasticnet":
        return _build_elasticnet_design(df, base_features)
    return df.to_numpy(dtype=float)


def _predict_target(models: Phase2Models, processed: pd.DataFrame, target: str) -> float:
    family = _get_family(models.meta, target)
    transform = _get_transform(models.meta, target)
    design = _build_design_matrix(processed, family, models.feature_columns)
    model_attr = f"model_{target}"
    model = getattr(models, model_attr, None)
    if model is None and target == "offsetR_at_join":
        model = getattr(models, "model_offsetR")
    if model is None:
        model = getattr(models, target)
    pred_trans = np.asarray(model.predict(design), dtype=float)
    pred_real = _inverse_transform(pred_trans, transform)
    bound_key = _bound_key_for_target(target)
    pred_bounded = _apply_bounds(pred_real, bound_key, models.meta)
    return float(np.ravel(pred_bounded)[0])


def predict_segment_params(
    models: Phase2Models,
    T_C: float,
    RH_lo_pct: float,
    RH_hi_pct: float,
    v_ms: float,
    thickness_mm: float,
) -> SegmentParams:
    """
    Use the Phase-2 surfaces to predict Midilli segment parameters and join info.
    """

    features_df = build_feature_row(T_C, RH_lo_pct, RH_hi_pct, v_ms, thickness_mm, models)
    processed = models.preprocessor.transform(features_df)

    kL = _predict_target(models, processed, "kL")
    nL = _predict_target(models, processed, "nL")
    bL = _predict_target(models, processed, "bL")
    kR = _predict_target(models, processed, "kR")
    nR = _predict_target(models, processed, "nR")
    bR = _predict_target(models, processed, "bR")
    offsetR = _predict_target(models, processed, "offsetR_at_join")

    tshift_design = _build_design_matrix(
        processed, _get_family(models.meta, "right_time_shift_at_boundary"), models.feature_columns
    )
    tshift_pred = models.model_join_tshift.predict(tshift_design)
    tshift_arr = np.asarray(tshift_pred, dtype=float)
    if tshift_arr.ndim > 1 and tshift_arr.shape[1] >= 2:
        t_split_min = float(tshift_arr[0, 0])
        t_shift_R_min = float(tshift_arr[0, 1])
    else:
        t_shift_R_min = float(np.ravel(tshift_arr)[0])
        default_split = (
            models.meta.get("t_split_default_min")
            or models.meta.get("t_split_min_mean")
            or models.meta.get("t_split_mean_min")
            or 0.0
        )
        t_split_min = float(default_split)
        if default_split == 0.0:
            warnings.warn("t_split_min defaulting to 0.0; join_tshift model did not provide a split time.")

    return SegmentParams(
        kL=kL,
        nL=nL,
        bL=bL,
        kR=kR,
        nR=nR,
        bR=bR,
        offsetR=offsetR,
        t_split_min=t_split_min,
        t_shift_R_min=t_shift_R_min,
    )


def reconstruct_MR_piecewise_model(seg: SegmentParams, t_min_grid: np.ndarray) -> np.ndarray:
    """
    Reconstruct MR(t) over t_min_grid using the Phase-2 'model' logic.
    """

    t = np.asarray(t_min_grid, dtype=float)
    tau = np.maximum(t - seg.t_shift_R_min, 0.0)

    MR_L = np.exp(-seg.kL * np.power(t, seg.nL)) + seg.bL * t
    MR_R_raw = np.exp(-seg.kR * np.power(tau, seg.nR)) + seg.bR * tau
    MR_R = MR_R_raw + seg.offsetR

    MR_combined = np.where(t <= seg.t_split_min, MR_L, MR_R)
    return MR_combined
