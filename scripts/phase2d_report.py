"""Diagnostics and acceptance checks for Phase-2 models."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import joblib
import matplotlib.pyplot as plt
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

try:  # pragma: no cover - optional dependency
    from sklearn.ensemble import HistGradientBoostingRegressor

    HAVE_HGB = True
except Exception:  # pragma: no cover - gracefully degrade
    HAVE_HGB = False


LOGGER = logging.getLogger("phase2.report")


DEFAULT_PHASE1_ROOT = Path(
    r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\piecewise_recursive_2ndphase"
)
DEFAULT_MODELS_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\models")
DEFAULT_TARGETS_CSV = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\phase2_targets.csv")
DEFAULT_OUT_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\diagnostics")
DEFAULT_RAW_ROOT = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\data")

BASE_FEATURES = ["T_C", "RH_mid_pct", "v_ms", "thickness_mm"]
TARGET_ORDER = [
    "kL",
    "nL",
    "bL",
    "kR",
    "nR",
    "bR",
    "offsetR_at_join",
    "right_time_shift_at_boundary",
]

TRANSFORMS = {
    "kL": "log",
    "nL": "log",
    "bL": "identity",
    "kR": "log",
    "nR": "log",
    "bR": "identity",
    "offsetR_at_join": "identity",
    "right_time_shift_at_boundary": "identity",
}


def _transform(values: np.ndarray, name: str) -> np.ndarray:
    if TRANSFORMS[name] == "log":
        return np.log(np.clip(values, 1e-12, None))
    return values


def _inverse(values: np.ndarray, name: str) -> np.ndarray:
    if TRANSFORMS[name] == "log":
        return np.exp(values)
    return values


def _apply_bounds(name: str, values: np.ndarray) -> np.ndarray:
    if name.startswith("k"):
        return apply_bounds("k", values)
    if name.startswith("n"):
        return apply_bounds("n", values)
    if name.startswith("b"):
        return apply_bounds("b", values)
    if name == "offsetR_at_join":
        return apply_bounds("offset", values)
    if name == "right_time_shift_at_boundary":
        return apply_bounds("tshift", values)
    return values


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


def load_phase1_metrics(phase1_root: Path) -> List[float]:
    values: List[float] = []
    for dataset_dir in sorted(p for p in phase1_root.iterdir() if p.is_dir()):
        summary_path = dataset_dir / "tree_summary.json"
        if not summary_path.exists():
            continue
        try:
            metrics = json.loads(summary_path.read_text()).get("metrics", {})
        except json.JSONDecodeError:
            continue
        value = metrics.get("rmse_total_corrected")
        if value is not None:
            values.append(float(value))
    return values


def load_models(models_dir: Path):
    meta = json.loads((models_dir / "meta.json").read_text())
    preprocessor = joblib.load(models_dir / "preprocessor.joblib")
    return meta, preprocessor


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Phase-2 diagnostics and acceptance gate")
    parser.add_argument("--phase1-root", type=Path, default=DEFAULT_PHASE1_ROOT)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--targets-csv", type=Path, default=DEFAULT_TARGETS_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--raw-data-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if not args.models_dir.exists():
        raise FileNotFoundError(f"Models directory not found: {args.models_dir}")
    if not args.targets_csv.exists():
        raise FileNotFoundError(f"Targets CSV not found: {args.targets_csv}")
    if not args.raw_data_root.exists():
        raise FileNotFoundError(f"Raw data root not found: {args.raw_data_root}")

    if not HAVE_HGB:
        LOGGER.warning("HistGradientBoostingRegressor unavailable; diagnostics will skip GBDT models")

    meta, saved_preprocessor = load_models(args.models_dir)
    df = pd.read_csv(args.targets_csv)
    features = df[BASE_FEATURES].copy()

    folds = list(_make_folds(df, args.cv_folds, args.seed))
    if not folds:
        raise RuntimeError("No folds produced for diagnostics")

    predictions = {name: np.zeros(len(df)) for name in TARGET_ORDER}
    recon_rmse: List[float] = []
    join_jumps: List[float] = []
    curve_cache: Dict[str, Dict[str, Any]] = {}

    for fold_id, (train_idx, val_idx) in enumerate(folds, 1):
        LOGGER.info("Processing fold %d/%d", fold_id, len(folds))
        X_train = features.iloc[train_idx]
        X_val = features.iloc[val_idx]
        preproc = FeaturePreprocessor(BASE_FEATURES).fit(X_train)
        X_train_proc = preproc.transform(X_train)
        X_val_proc = preproc.transform(X_val)

        for target in TARGET_ORDER:
            family = meta["targets"].get(target, {}).get("family", "elasticnet")
            params = meta["targets"].get(target, {}).get("params", {})

            y_train = df.iloc[train_idx][target].to_numpy(dtype=float)
            y_val = df.iloc[val_idx][target].to_numpy(dtype=float)
            y_train_trans = _transform(y_train, target)

            if family == "elasticnet":
                design_train = build_elasticnet_design(X_train_proc)
                design_val = build_elasticnet_design(X_val_proc)
                estimator = ElasticNet(
                    alpha=params["lambda"],
                    l1_ratio=params["alpha"],
                    fit_intercept=True,
                    max_iter=10000,
                    random_state=args.seed + fold_id,
                )
            else:
                if not HAVE_HGB:
                    raise RuntimeError("GBDT models requested but HistGradientBoosting missing")
                design_train = build_gbdt_matrix(X_train_proc)
                design_val = build_gbdt_matrix(X_val_proc)
                monotone = None
                if target in {"kL", "kR"}:
                    monotone = [1, -1, 0, 0] + [0] * (design_train.shape[1] - 4)
                estimator = HistGradientBoostingRegressor(
                    max_depth=params["max_depth"],
                    learning_rate=params["learning_rate"],
                    max_iter=params["n_estimators"],
                    random_state=args.seed + fold_id,
                    monotonic_cst=monotone,
                )

            estimator.fit(design_train, y_train_trans)
            pred = estimator.predict(design_val)
            pred = _inverse(pred, target)
            pred = _apply_bounds(target, pred)
            predictions[target][val_idx] = pred

        for position, idx in enumerate(val_idx):
            row = df.iloc[idx]
            dataset = row["dataset"]
            try:
                raw = load_raw_timeseries(args.raw_data_root, dataset)
            except FileNotFoundError:
                LOGGER.warning("Raw data missing for %s; skipping diagnostics", dataset)
                continue

            pred_values = {name: predictions[name][idx] for name in TARGET_ORDER}
            join_time = float(row["tL_end"]) if "tL_end" in row else float(row["tR_start"])
            curves = reconstruct_piecewise(
                raw["time_min"].to_numpy(),
                {"k": pred_values["kL"], "n": pred_values["nL"], "b": pred_values["bL"]},
                {"k": pred_values["kR"], "n": pred_values["nR"], "b": pred_values["bR"]},
                join_time,
                pred_values["offsetR_at_join"],
                pred_values["right_time_shift_at_boundary"],
                bool(row.get("famL_is_page", False)),
                bool(row.get("famR_is_page", False)),
            )

            rmse = math.sqrt(mean_squared_error(raw["mr"].to_numpy(), curves["final"]))
            recon_rmse.append(rmse)

            time_arr = curves["time"]
            join_idx = np.searchsorted(time_arr, join_time, side="left")
            left_value = curves["left"][join_idx - 1 if join_idx > 0 else 0]
            right_value = curves["right_shifted"][join_idx if join_idx < len(time_arr) else -1]
            join_jumps.append(right_value - left_value)

            curve_cache[dataset] = {
                "time": time_arr,
                "observed": raw["mr"].to_numpy(),
                "predicted": curves["final"],
                "residual": raw["mr"].to_numpy() - curves["final"],
                "join_time": join_time,
            }

    metrics = {
        "reconstruction_rmse": {
            "mean": float(np.mean(recon_rmse)) if recon_rmse else float("nan"),
            "std": float(np.std(recon_rmse)) if recon_rmse else float("nan"),
        },
        "parameter_rmse": {
            name: float(np.sqrt(mean_squared_error(df[name], predictions[name])))
            for name in TARGET_ORDER
        },
        "bounds": {
            "k": list(K_BOUNDS),
            "n": list(N_BOUNDS),
            "b": list(B_BOUNDS),
            "offset": list(OFFSET_BOUNDS),
            "tshift": list(TSHIFT_BOUNDS),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "param_model_metrics.json").write_text(json.dumps(metrics, indent=2))

    selected_datasets = list(curve_cache.keys())[:6]
    for dataset in selected_datasets:
        payload = curve_cache[dataset]
        fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        axes[0].plot(payload["time"], payload["observed"], label="Observed")
        axes[0].plot(payload["time"], payload["predicted"], label="Reconstructed")
        axes[0].axvline(payload["join_time"], color="black", linestyle="--", alpha=0.5)
        axes[0].set_ylabel("MR")
        axes[0].legend()
        axes[0].set_title(f"Dataset {dataset}")

        axes[1].plot(payload["time"], payload["residual"], color="tab:red")
        axes[1].axhline(0.0, color="black", linewidth=1)
        axes[1].set_xlabel("Time (min)")
        axes[1].set_ylabel("Residual (MR)")
        axes[1].axvline(payload["join_time"], color="black", linestyle="--", alpha=0.5)
        fig.tight_layout()
        fig.savefig(out_dir / f"{dataset}_diagnostic.png", dpi=150)
        plt.close(fig)

    phase1_metrics = load_phase1_metrics(args.phase1_root)
    threshold = float(np.quantile(phase1_metrics, 0.75)) if phase1_metrics else float("inf")
    mean_recon = metrics["reconstruction_rmse"]["mean"]
    positive_jumps = [jump for jump in join_jumps if jump > 0.01]
    jump_ratio = (len(positive_jumps) / len(join_jumps)) if join_jumps else 0.0

    failures: List[str] = []
    if phase1_metrics and mean_recon > threshold:
        failures.append(
            f"Mean reconstruction RMSE {mean_recon:.4f} exceeds 0.75-quantile {threshold:.4f}"
        )
    if jump_ratio > 0.10:
        failures.append(
            f"{jump_ratio*100:.1f}% of curves show >0.01 MR positive jump before guard"
        )

    if failures:
        (out_dir / "acceptance_failures.txt").write_text("\n".join(failures))
        write_run_meta(out_dir, list(sys.argv))
        LOGGER.error("Acceptance checks failed:\n%s", "\n".join(failures))
        sys.exit(2)

    write_run_meta(out_dir, list(sys.argv))
    LOGGER.info("Diagnostics completed successfully")


if __name__ == "__main__":
    main()

