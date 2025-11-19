"""Continuity-aware predictor using Phase-2 models."""

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
    FeaturePreprocessor,  # required for joblib loading
    OFFSET_BOUNDS,
    TSHIFT_BOUNDS,
    _midilli_curve,
    apply_bounds,
    build_elasticnet_design,
    build_gbdt_matrix,
    reconstruct_piecewise,
    write_run_meta,
)

LOGGER = logging.getLogger("phase2.predict")

DEFAULT_MODELS_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\models")
DEFAULT_OUT_DIR    = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\predict_demo")

TARGET_ORDER = [
    "kL","nL","bL",
    "kR","nR","bR",
    "offsetR_at_join","right_time_shift_at_boundary",
]

# ---------- helpers: use Phase-2B’s recorded transforms ----------
def _inverse(values: np.ndarray, transform: str) -> np.ndarray:
    if transform == "log":
        return np.exp(values)
    if transform == "slog1p":
        s = np.sign(values)
        return s * (np.expm1(np.abs(values)))
    return values  # identity

def _get_transform(meta: Dict[str, Any], target: str) -> str:
    # Phase-2B wrote this map in meta["transforms"]
    return meta.get("transforms", {}).get(target, "identity")

def _apply_bounds_for(name: str, values: np.ndarray) -> np.ndarray:
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
        "kL":"kL.joblib","nL":"nL.joblib","bL":"bL.joblib",
        "kR":"kR.joblib","nR":"nR.joblib","bR":"bR.joblib",
        "offsetR_at_join":"offsetR.joblib",
        "right_time_shift_at_boundary":"join_tshift.joblib",
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
    features_df = pd.DataFrame([{
        "T_C": row["T_C"],
        "RH_mid_pct": row["RH_mid_pct"],
        "v_ms": row["v_ms"],
        "thickness_mm": row["thickness_mm"],
    }])
    processed = preprocessor.transform(features_df)

    outputs: Dict[str, float] = {}
    for target in TARGET_ORDER:
        family    = meta["targets"].get(target, {}).get("family", "elasticnet")
        transform = _get_transform(meta, target)
        design = (build_elasticnet_design(processed)
                  if family == "elasticnet" else
                  build_gbdt_matrix(processed))
        pred_trans = models[target].predict(design)
        pred = _inverse(np.asarray(pred_trans, dtype=float), transform)
        pred = _apply_bounds_for(target, pred)
        outputs[target] = float(pred[0])
    return outputs

def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Phase-2 continuity-aware predictor")
    parser.add_argument("--t-source", choices=["tL_end", "t_split_min"], default="tL_end")
    parser.add_argument(
        "--auto-page-eps",
        type=float,
        default=1e-6,
        help="If |b| ≤ eps on a side, force Page (b=0, is_page=True).",
    )
    parser.add_argument("--force-continuity", action="store_true",
                        help="Solve tshift so MR_right(t_split)=MR_left(t_split); offset≈0")
    parser.add_argument("--mr-floor", type=float, default=0.03)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--operating-point-csv", type=Path)
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
    base_cols = {"id","T_C","RH_mid_pct","v_ms","thickness_mm"}
    join_col  = "tL_end" if args.t_source == "tL_end" else "t_split_min"
    missing = (base_cols | {join_col}) - set(ops_df.columns)
    if missing:
        raise ValueError(f"Operating point CSV missing columns: {', '.join(sorted(missing))}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for _, row in ops_df.iterrows():
        identifier = row["id"]
        predictions = predict_for_row(row, preproc, models, meta)

        t_split = float(row[join_col])

        # Current parameter predictions + Page/Midilli selection
        kL = float(predictions["kL"])
        nL = float(predictions["nL"])
        bL = float(predictions["bL"])
        kR = float(predictions["kR"])
        nR = float(predictions["nR"])
        bR = float(predictions["bR"])

        is_page_L = bool(row.get("famL_is_page", False)) or abs(bL) <= args.auto_page_eps
        is_page_R = bool(row.get("famR_is_page", False)) or abs(bR) <= args.auto_page_eps
        if is_page_L:
            bL = 0.0
        if is_page_R:
            bR = 0.0

        offsetR = float(predictions["offsetR_at_join"])
        tshift = float(predictions["right_time_shift_at_boundary"])

        if args.force_continuity:
            mr_target = float(_midilli_curve(np.array([t_split]), kL, nL, bL, is_page_L)[0])
            lo, hi = 0.0, TSHIFT_BOUNDS[1]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                mr_mid = float(_midilli_curve(np.array([mid]), kR, nR, bR, is_page_R)[0])
                if mr_mid > mr_target:
                    lo = mid
                else:
                    hi = mid
            tshift = float(hi)
            offsetR = 0.0

        tshift_used = float(np.clip(tshift, *TSHIFT_BOUNDS))

        mr_left_at_join = float(
            _midilli_curve(
                np.array([t_split]),
                kL,
                nL,
                float(bL),
                is_page_L,
            )[0]
        )

        mr_right_raw_at_join = float(
            _midilli_curve(
                np.array([tshift_used]),
                kR,
                nR,
                float(bR),
                is_page_R,
            )[0]
        )

        if args.force_continuity:
            offset_used = 0.0
        else:
            offset_cont = mr_left_at_join - mr_right_raw_at_join
            offset_used = float(np.clip(offset_cont, *OFFSET_BOUNDS))

        print(
            f"{identifier}: join MR_L={mr_left_at_join:.6f}  "
            f"MR_R_raw@tshift={mr_right_raw_at_join:.6f}  "
            f"offset_used={offset_used:.6f}  tshift_used={tshift_used:.6f}"
        )

        curves = reconstruct_piecewise(
            time_grid,
            {"k": float(predictions["kL"]), "n": float(predictions["nL"]), "b": bL},
            {"k": float(predictions["kR"]), "n": float(predictions["nR"]), "b": bR},
            t_split,
            offset_used,
            tshift_used,
            is_page_left=is_page_L,
            is_page_right=is_page_R,
            mr_floor=float(args.mr_floor),
        )
        observed = None
        if args.raw_root and (args.raw_root.exists()):
            from .phase2_common import load_raw_timeseries

            try:
                raw_df = load_raw_timeseries(args.raw_root, identifier, xeq_db=float(args.xeq_db))
                observed = raw_df
            except Exception:
                observed = None

        segment = np.where(curves["time"] <= t_split, "left", "right")
        df = pd.DataFrame(
            {
                "id": identifier,
                "t": curves["time"],
                "segment": segment,
                "MR_L": curves["left"],
                "MR_R_raw": curves["right_raw"],
                "MR_R_shifted": curves["right_shifted"],
                "MR_pred": curves["final"],
                "offsetR": offset_used,
                "tshift": tshift_used,
                "t_split": t_split,
            }
        )
        df.to_csv(args.out_dir / f"{identifier}_prediction.csv", index=False)

        # Plot
        plt.figure(figsize=(8, 4.5))
        if observed is not None:
            plt.scatter(
                observed["time_min"], observed["mr"], s=10, alpha=0.6, label="Observed MR"
            )

        plt.plot(curves["time"], curves["left"],         "--", label="MR_L")
        plt.plot(curves["time"], curves["right_raw"],    ":",  label="MR_R_raw")
        plt.plot(curves["time"], curves["right_shifted"],     label="MR_R_shifted")
        plt.plot(curves["time"], curves["final"],        linewidth=2, label="MR_pred")

        join_idx = np.searchsorted(time_grid, t_split, side="left")
        plt.scatter([t_split],[curves["left"][join_idx]], s=25, label="Join target (left)")
        plt.scatter([t_split],[curves["right_shifted"][join_idx]], s=35, marker="x", label="Right@join after shift")

        plt.xlabel("Time (min)"); plt.ylabel("MR")
        plt.title(f"Phase-2 prediction for {identifier}")
        plt.legend(loc="best"); plt.tight_layout()
        plt.savefig(args.out_dir / f"{identifier}_prediction.png", dpi=150)
        plt.close()

    write_run_meta(args.out_dir, list(sys.argv))

if __name__ == "__main__":
    main()
