"""Train Phase-2 parameter models with reconstruction-aware selection."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.utils import check_random_state

from .phase2_common import (
    FeaturePreprocessor,
    K_BOUNDS,
    N_BOUNDS,
    B_BOUNDS,
    OFFSET_BOUNDS,
    TSHIFT_BOUNDS,
    apply_bounds,
    build_elasticnet_design,
    build_gbdt_matrix,
    load_raw_timeseries,
    reconstruct_piecewise,
    write_run_meta,
)

try:  # pragma: no cover - optional import
    from sklearn.ensemble import HistGradientBoostingRegressor

    HAVE_HGB = True
except Exception:  # pragma: no cover - fallback if unavailable
    HAVE_HGB = False


LOGGER = logging.getLogger("phase2.train")


DEFAULT_TARGETS_CSV = Path(
    r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\phase2_targets.csv"
)
DEFAULT_RAW_ROOT = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\data")
DEFAULT_OUT_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\models")

BASE_FEATURES = ["T_C", "RH_mid_pct", "v_ms", "thickness_mm"]
TARGET_COLUMNS = [
    "kL",
    "nL",
    "bL",
    "kR",
    "nR",
    "bR",
    "offsetR_at_join",
    "right_time_shift_at_boundary",
]


@dataclass
class TargetSpec:
    name: str
    transform: str
    bound_key: str


TARGET_SPECS: Dict[str, TargetSpec] = {
    "kL": TargetSpec("kL", "log", "k"),
    "nL": TargetSpec("nL", "identity", "n"),
    "bL": TargetSpec("bL", "slog1p", "b"),   # add
    "kR": TargetSpec("kR", "log", "k"),
    "nR": TargetSpec("nR", "identity", "n"),
    "bR": TargetSpec("bR", "slog1p", "b"),   # add
    "offsetR_at_join": TargetSpec("offsetR_at_join", "identity", "offset"),
    "right_time_shift_at_boundary": TargetSpec(
        "right_time_shift_at_boundary", "identity", "tshift"
    ),
}


ELASTICNET_L1 = [0.0, 0.25, 0.5, 0.75, 1.0]
ELASTICNET_ALPHA = np.logspace(-5, 1, 30)

GBDT_MAX_DEPTH = [2, 3, 4, 5]
GBDT_N_ESTIMATORS = [200, 400, 800]
GBDT_LEARNING_RATE = [0.03, 0.07, 0.12]


def _transform_target(values: np.ndarray, spec: TargetSpec) -> np.ndarray:
    if spec.transform == "log":
        return np.log(np.clip(values, 1e-12, None))
    # CHANGE 2: signed log1p for b
    if spec.transform == "slog1p":
        s = np.sign(values)
        return s * np.log1p(np.abs(values))
    return values

def _inverse_target(values: np.ndarray, spec: TargetSpec) -> np.ndarray:
    if spec.transform == "log":
        return np.exp(values)
    # CHANGE 3: inverse of slog1p
    if spec.transform == "slog1p":
        s = np.sign(values)
        return s * (np.expm1(np.abs(values)))
    return values


def _apply_target_bounds(values: np.ndarray, spec: TargetSpec) -> np.ndarray:
    v = apply_bounds(spec.bound_key, values)
    if spec.bound_key == "k":
        v = np.maximum(v, 1e-8)
    return v


def _make_folds(
    df: pd.DataFrame, n_splits: int, seed: int
) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    rng = check_random_state(seed)
    stratify_col = df["T_C"].copy()
    if stratify_col.notna().nunique() >= 2:
        labels = stratify_col.fillna(stratify_col.median()).astype(int)
        counts = labels.value_counts()
        if (counts >= n_splits).all():
            splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
            yield from splitter.split(df, labels)
            return

    splitter = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    yield from splitter.split(df)


def _reconstruct_rmse(
    row: pd.Series,
    predicted: Dict[str, float],
    raw_root: Path,
) -> float | None:
    dataset = row["dataset"]
    try:
        raw_df = load_raw_timeseries(raw_root, dataset)
    except FileNotFoundError:
        LOGGER.warning("Raw dataset %s missing; skipping RMSE computation", dataset)
        return None

    def _pick_value(key: str) -> float:
        value = predicted.get(key)
        if value is None:
            value = row[key]
        if pd.isna(value):
             raise ValueError(f"Missing target '{key}' for dataset {dataset}")
        return float(value)

    t_split = float(row["tR_start"])
    left_params = {
        "k": _pick_value("kL"),
        "n": _pick_value("nL"),
        "b": _pick_value("bL"),
    }
    right_params = {
        "k": _pick_value("kR"),
        "n": _pick_value("nR"),
        "b": _pick_value("bR"),
    }
    offsetR = _pick_value("offsetR_at_join")
    tshift = _pick_value("right_time_shift_at_boundary")

    curves = reconstruct_piecewise(
        raw_df["time_min"].to_numpy(),
        left_params,
        right_params,
        t_split,
        offsetR,
        tshift,
        bool(row.get("famL_is_page", False)),
        bool(row.get("famR_is_page", False)),
        mr_floor=0.0,
    )

    mr_obs = (raw_df["mr_iso"] if "mr_iso" in raw_df.columns else raw_df["mr"]).to_numpy()
    rmse = math.sqrt(mean_squared_error(mr_obs, curves["final"]))
    return rmse


def _evaluate_candidate(
    target: str,
    spec: TargetSpec,
    family: str,
    params: Dict[str, Any],
    df: pd.DataFrame,
    features: pd.DataFrame,
    folds: Iterable[Tuple[np.ndarray, np.ndarray]],
    raw_root: Path,
    seed: int,
) -> Tuple[float, float, float, float]:
    rng = check_random_state(seed)
    recon_scores: List[float] = []
    param_scores: List[float] = []

    for train_idx, val_idx in folds:
        X_train = features.iloc[train_idx]
        X_val = features.iloc[val_idx]
        y_train = df.iloc[train_idx][target].to_numpy(dtype=float)
        y_val = df.iloc[val_idx][target].to_numpy(dtype=float)

        preproc = FeaturePreprocessor(BASE_FEATURES).fit(X_train)
        X_train_proc = preproc.transform(X_train)
        X_val_proc = preproc.transform(X_val)

        y_train_trans = _transform_target(y_train, spec)

        if family == "elasticnet":
            design_train = build_elasticnet_design(X_train_proc)
            design_val = build_elasticnet_design(X_val_proc)
            model = ElasticNet(
                alpha=params["lambda"],
                l1_ratio=params["alpha"],
                fit_intercept=True,
                max_iter=10000,
                random_state=rng.randint(0, 1_000_000),
            )
        elif family == "gbdt" and HAVE_HGB:
            design_train = build_gbdt_matrix(X_train_proc)
            design_val = build_gbdt_matrix(X_val_proc)
            monotone = None
            if target in {"kL", "kR"}:
                # Order: all base features then indicators.
                monotone = [1, -1, 0, 0] + [0] * (design_train.shape[1] - 4)
            model = HistGradientBoostingRegressor(
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                max_iter=params["n_estimators"],
                random_state=rng.randint(0, 1_000_000),
                monotonic_cst=monotone,
            )
        else:
            raise RuntimeError("Gradient boosting backend unavailable")

        model.fit(design_train, y_train_trans)
        y_val_pred = model.predict(design_val)
        y_val_pred = _inverse_target(y_val_pred, spec)
        y_val_pred = _apply_target_bounds(y_val_pred, spec)

        param_rmse = math.sqrt(mean_squared_error(y_val, y_val_pred))
        param_scores.append(param_rmse)

        fold_df = df.iloc[val_idx]
        rmse_per_curve: List[float] = []
        for i, (_, row) in enumerate(fold_df.iterrows()):
            predicted_values = {target: float(y_val_pred[i])}
            rmse = _reconstruct_rmse(row, predicted_values, raw_root)
            if rmse is not None:
                rmse_per_curve.append(rmse)

        if rmse_per_curve:
            recon_scores.append(float(np.mean(rmse_per_curve)))

    recon_mean = float(np.mean(recon_scores)) if recon_scores else float("inf")
    recon_std = float(np.std(recon_scores)) if recon_scores else float("nan")
    param_mean = float(np.mean(param_scores)) if param_scores else float("inf")
    param_std = float(np.std(param_scores)) if param_scores else float("nan")
    return recon_mean, recon_std, param_mean, param_std


def _train_best_model(
    target: str,
    spec: TargetSpec,
    family: str,
    params: Dict[str, Any],
    features: pd.DataFrame,
    y: np.ndarray,
    preproc: FeaturePreprocessor,
    seed: int,
):
    rng = check_random_state(seed)
    X_proc = preproc.transform(features)
    y_trans = _transform_target(y, spec)

    if family == "elasticnet":
        design = build_elasticnet_design(X_proc)
        model = ElasticNet(
            alpha=params["lambda"],
            l1_ratio=params["alpha"],
            fit_intercept=True,
            max_iter=10000,
            random_state=rng.randint(0, 1_000_000),
        )
        model.fit(design, y_trans)
        return model
    elif family == "gbdt" and HAVE_HGB:
        design = build_gbdt_matrix(X_proc)
        monotone = None
        if target in {"kL", "kR"}:
            monotone = [1, -1, 0, 0] + [0] * (design.shape[1] - 4)
        model = HistGradientBoostingRegressor(
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            max_iter=params["n_estimators"],
            random_state=rng.randint(0, 1_000_000),
            monotonic_cst=monotone,
        )
        model.fit(design, y_trans)
        return model

    raise RuntimeError("Unknown family or unavailable backend")


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train Phase-2 parameter models")
    parser.add_argument("--targets-csv", type=Path, default=DEFAULT_TARGETS_CSV)
    parser.add_argument("--raw-data-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    targets_csv: Path = args.targets_csv
    raw_root: Path = args.raw_data_root
    out_dir: Path = args.out_dir

    if not targets_csv.exists():
        raise FileNotFoundError(f"Targets CSV not found: {targets_csv}")
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw data root not found: {raw_root}")

    df = pd.read_csv(targets_csv)
    features = df[BASE_FEATURES].copy()
    cv_folds = min(args.cv_folds, max(2, len(df)))
    folds = list(_make_folds(df, cv_folds, args.seed))
    
    if not HAVE_HGB:
        LOGGER.warning("HistGradientBoostingRegressor unavailable; skipping GBDT candidates")

    preprocessor = FeaturePreprocessor(BASE_FEATURES)
    preprocessor.fit(features)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(preprocessor, out_dir / "preprocessor.joblib")

    meta: Dict[str, Any] = {
        "features": BASE_FEATURES,
        "targets": {},
        "transforms": {name: spec.transform for name, spec in TARGET_SPECS.items()},
        "bounds": {
            "k": list(K_BOUNDS),
            "n": list(N_BOUNDS),
            "b": list(B_BOUNDS),
            "offset": list(OFFSET_BOUNDS),
            "tshift": list(TSHIFT_BOUNDS),
        },
    }
    # CHANGE 9: record model selection criterion
    meta["selection_metric"] = "mean_reconstruction_RMSE (lower is better); tie-breaker: parameter_RMSE"
    
    for target in TARGET_COLUMNS:
        spec = TARGET_SPECS[target]
        best_family = None
        best_params = None
        best_scores = (float("inf"), float("nan"), float("inf"), float("nan"))

        LOGGER.info("Selecting model for %s", target)

        # Elastic Net candidates
        for l1_ratio in ELASTICNET_L1:
            for lam in ELASTICNET_ALPHA:
                params = {"alpha": l1_ratio, "lambda": float(lam)}
                scores = _evaluate_candidate(
                    target,
                    spec,
                    "elasticnet",
                    params,
                    df,
                    features,
                    folds,
                    raw_root,
                    args.seed,
                )
                if scores[0] < best_scores[0] or (
                    math.isclose(scores[0], best_scores[0]) and scores[2] < best_scores[2]
                ):
                    best_family = "elasticnet"
                    best_params = params
                    best_scores = scores

        if HAVE_HGB:
            for depth in GBDT_MAX_DEPTH:
                for n_est in GBDT_N_ESTIMATORS:
                    for lr in GBDT_LEARNING_RATE:
                        params = {
                            "max_depth": depth,
                            "n_estimators": n_est,
                            "learning_rate": lr,
                        }
                        scores = _evaluate_candidate(
                            target,
                            spec,
                            "gbdt",
                            params,
                            df,
                            features,
                            folds,
                            raw_root,
                            args.seed,
                        )
                        if scores[0] < best_scores[0] or (
                            math.isclose(scores[0], best_scores[0]) and scores[2] < best_scores[2]
                        ):
                            best_family = "gbdt"
                            best_params = params
                            best_scores = scores

        if best_family is None or best_params is None:
            raise RuntimeError(f"No valid model found for target {target}")

        LOGGER.info(
            "Selected %s for %s with reconstruction RMSE %.4f", target, best_family, best_scores[0]
        )

        model = _train_best_model(
            target,
            spec,
            best_family,
            best_params,
            features,
            df[target].to_numpy(dtype=float),
            preprocessor,
            args.seed,
        )

        model_path = {
            "kL": "kL.joblib",
            "nL": "nL.joblib",
            "bL": "bL.joblib",
            "kR": "kR.joblib",
            "nR": "nR.joblib",
            "bR": "bR.joblib",
            "offsetR_at_join": "offsetR.joblib",
            "right_time_shift_at_boundary": "join_tshift.joblib",
        }[target]
        joblib.dump(model, out_dir / model_path)

        meta["targets"][target] = {
            "family": best_family,
            "params": best_params,
            "reconstruction_rmse_mean": best_scores[0],
            "reconstruction_rmse_std": best_scores[1],
            "parameter_rmse_mean": best_scores[2],
            "parameter_rmse_std": best_scores[3],
        }

    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    write_run_meta(out_dir, list(sys.argv))


if __name__ == "__main__":
    main()

