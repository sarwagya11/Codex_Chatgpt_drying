"""Phase-2.1 predictor using Midilli/Page parameter models."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys

from .phase2_common import (
    FeaturePreprocessor,
    apply_bounds,
    build_elasticnet_design,
    build_gbdt_matrix,
    load_raw_timeseries,
    reconstruct_two_segment_continuous,
    write_run_meta,
)

LOGGER = logging.getLogger("phase2_1.predict")

DEFAULT_MODELS_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2.1\models")
DEFAULT_OPS_CSV = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2.1\ops_from_targets.csv")
DEFAULT_OUT_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2.1\predict")

TARGET_ORDER = ["kL", "nL", "bL", "kR", "nR", "bR"]


def _as_bool(x) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, float)):
        return bool(int(x))
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "t", "y", "yes")
    return False


# ---------- helpers: use recorded transforms ----------
def _inverse(values: np.ndarray, transform: str) -> np.ndarray:
    if transform == "log":
        return np.exp(values)
    if transform == "slog1p":
        s = np.sign(values)
        return s * (np.expm1(np.abs(values)))
    return values


def _get_transform(meta: Dict[str, Any], target: str) -> str:
    return meta.get("transforms", {}).get(target, "identity")


def _apply_bounds_for(name: str, values: np.ndarray) -> np.ndarray:
    if name.startswith("k"):
        return apply_bounds("k", values)
    if name.startswith("n"):
        return apply_bounds("n", values)
    if name.startswith("b"):
        return apply_bounds("b", values)
    return values


# -----------------------------------------------------------------
def parse_time_grid(spec: str) -> np.ndarray:
    parts = spec.split(":")
    if len(parts) != 3:
        raise ValueError("Time grid must be 'start:end:step'")
    start, end, step = map(float, parts)
    if step <= 0:
        raise ValueError("Time grid step must be positive")
    count = int(np.floor((end - start) / step)) + 1
    return start + step * np.arange(count)


def load_models(models_dir: Path):
    meta = json.loads((models_dir / "meta.json").read_text())
    preprocessor = joblib.load(models_dir / "preprocessor.joblib")

    models = {}
    filenames = {
        "kL": "kL.joblib",
        "nL": "nL.joblib",
        "bL": "bL.joblib",
        "kR": "kR.joblib",
        "nR": "nR.joblib",
        "bR": "bR.joblib",
    }
    for target, fname in filenames.items():
        path = models_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing model artifact: {path}")
        models[target] = joblib.load(path)

    return meta, preprocessor, models


def predict_for_row(
    row: pd.Series,
    preprocessor: FeaturePreprocessor,
    models: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, float]:
    features_df = pd.DataFrame(
        [
            {
                "T_C": row["T_C"],
                "RH_mid_pct": row["RH_mid_pct"],
                "v_ms": row["v_ms"],
                "thickness_mm": row["thickness_mm"],
            }
        ]
    )
    processed = preprocessor.transform(features_df)

    outputs: Dict[str, float] = {}
    for target in TARGET_ORDER:
        family = meta["targets"].get(target, {}).get("family", "elasticnet")
        transform = _get_transform(meta, target)
        design = (
            build_elasticnet_design(processed)
            if family == "elasticnet"
            else build_gbdt_matrix(processed)
        )
        pred_trans = models[target].predict(design)
        pred = _inverse(np.asarray(pred_trans, dtype=float), transform)
        pred = _apply_bounds_for(target, pred)
        outputs[target] = float(pred[0])
    return outputs


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Phase-2.1 predictor")
    parser.add_argument("--t-source", choices=["tL_end", "tR_start"], default="tL_end")
    parser.add_argument(
        "--auto-page-eps",
        type=float,
        default=1e-6,
        help="If |b| ≤ eps on a side, force Page (b=0, is_page=True).",
    )
    parser.add_argument(
        "--force-continuity",
        action="store_true",
        help="Unused placeholder to mirror Phase-2 CLI options.",
    )
    parser.add_argument("--mr-floor", type=float, default=0.03)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--operating-point-csv", type=Path, default=DEFAULT_OPS_CSV)
    parser.add_argument("--time-grid", type=str, default="0:600:1")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--raw-root", type=Path, help="Folder with raw dataset CSVs for overlay")
    parser.add_argument("--xeq-db", type=float, default=0.0, help="Equilibrium moisture (dry-basis)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if not args.models_dir.exists():
        raise FileNotFoundError(f"Models directory does not exist: {args.models_dir}")
    if not args.operating_point_csv.exists():
        raise FileNotFoundError(f"Operating point CSV not found: {args.operating_point_csv}")

    meta, preproc, models = load_models(args.models_dir)
    time_grid = parse_time_grid(args.time_grid)
    ops_df = pd.read_csv(args.operating_point_csv)

    base_cols = {
        "dataset",
        "T_C",
        "RH_mid_pct",
        "v_ms",
        "thickness_mm",
        "tL_end",
        "tR_start",
        "famL_is_page",
        "famR_is_page",
    }
    missing = base_cols - set(ops_df.columns)
    if missing:
        raise ValueError(f"Operating point CSV missing columns: {', '.join(sorted(missing))}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for _, row in ops_df.iterrows():
        identifier = row["dataset"]
        predictions = predict_for_row(row, preproc, models, meta)

        join_col = "tL_end" if args.t_source == "tL_end" else "tR_start"
        t_split = float(row[join_col])

        kL = float(predictions["kL"])
        nL = float(predictions["nL"])
        bL = float(predictions["bL"])
        kR = float(predictions["kR"])
        nR = float(predictions["nR"])
        bR = float(predictions["bR"])

        famL_is_page = _as_bool(row.get("famL_is_page", False)) or abs(bL) <= args.auto_page_eps
        famR_is_page = _as_bool(row.get("famR_is_page", False)) or abs(bR) <= args.auto_page_eps
        if famL_is_page:
            bL = 0.0
        if famR_is_page:
            bR = 0.0

        curves = reconstruct_two_segment_continuous(
            time_grid,
            {"k": kL, "n": nL, "b": bL},
            {"k": kR, "n": nR, "b": bR},
            t_split,
            is_page_left=famL_is_page,
            is_page_right=famR_is_page,
            mr_floor=float(args.mr_floor),
        )
        mr_pred = np.asarray(curves["final"], dtype=float)

        observed = None
        if args.raw_root and args.raw_root.exists():
            try:
                raw_df = load_raw_timeseries(args.raw_root, identifier, xeq_db=float(args.xeq_db))
                observed = raw_df
            except Exception:
                observed = None

        if observed is not None:
            mr_obs = np.interp(time_grid, observed["time_min"], observed["mr"], left=np.nan, right=np.nan)
        else:
            mr_obs = np.full_like(time_grid, np.nan, dtype=float)

        pred_df = pd.DataFrame(
            {
                "time_min": time_grid,
                "MR_obs": mr_obs,
                "MR_pred": mr_pred,
                "t_split": t_split,
            }
        )
        pred_df.to_csv(args.out_dir / f"{identifier}_prediction.csv", index=False)

        plt.figure(figsize=(8, 4.5))
        if observed is not None:
            plt.scatter(observed["time_min"], observed["mr"], s=10, alpha=0.6, label="Observed MR")
        plt.plot(time_grid, mr_pred, linewidth=2, label="MR_pred (Phase-2.1)")
        plt.axvline(x=t_split, linestyle="--", linewidth=1, color="k", label="Split time")
        plt.xlabel("Time (min)")
        plt.ylabel("MR")
        plt.title(f"Phase-2.1 prediction for {identifier}")
        plt.legend(loc="best")
        plt.tight_layout()
        plt.savefig(args.out_dir / f"{identifier}_prediction.png", dpi=150)
        plt.close()

    write_run_meta(args.out_dir, list(sys.argv))


if __name__ == "__main__":
    main()
