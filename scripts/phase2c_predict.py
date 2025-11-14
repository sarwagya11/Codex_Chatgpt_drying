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
    apply_bounds,
    build_elasticnet_design,
    build_gbdt_matrix,
    reconstruct_piecewise,
    write_run_meta,
)


LOGGER = logging.getLogger("phase2.predict")


DEFAULT_MODELS_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\models")
DEFAULT_OUT_DIR = Path(r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\predict_demo")


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


def _inverse(values: np.ndarray, transform: str) -> np.ndarray:
    if transform == "log":
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
    for target in TARGET_ORDER:
        filename = {
            "kL": "kL.joblib",
            "nL": "nL.joblib",
            "bL": "bL.joblib",
            "kR": "kR.joblib",
            "nR": "nR.joblib",
            "bR": "bR.joblib",
            "offsetR_at_join": "offsetR.joblib",
            "right_time_shift_at_boundary": "join_tshift.joblib",
        }[target]
        model_path = models_dir / filename
        if not model_path.exists():
            raise FileNotFoundError(f"Missing model artifact: {model_path}")
        models[target] = joblib.load(model_path)

    return meta, preprocessor, models


def predict_for_row(
    row: pd.Series,
    preprocessor: FeaturePreprocessor,
    models: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, float]:
    features_df = pd.DataFrame([
        {
            "T_C": row["T_C"],
            "RH_mid_pct": row["RH_mid_pct"],
            "v_ms": row["v_ms"],
            "thickness_mm": row["thickness_mm"],
        }
    ])
    processed = preprocessor.transform(features_df)

    outputs: Dict[str, float] = {}
    for target in TARGET_ORDER:
        family = meta["targets"].get(target, {}).get("family", "elasticnet")
        transform = TRANSFORMS[target]
        if family == "elasticnet":
            design = build_elasticnet_design(processed)
        else:
            design = build_gbdt_matrix(processed)
        model = models[target]
        pred_trans = model.predict(design)
        pred = _inverse(np.asarray(pred_trans), transform)
        pred = _apply_bounds(target, pred)
        outputs[target] = float(pred[0])

    return outputs


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Phase-2 continuity-aware predictor")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--operating-point-csv", type=Path)
    parser.add_argument("--time-grid", type=str, default="0:600:1")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    models_dir: Path = args.models_dir
    ops_csv: Path = args.operating_point_csv
    out_dir: Path = args.out_dir

    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory does not exist: {models_dir}")
    if not ops_csv.exists():
        raise FileNotFoundError(f"Operating point CSV not found: {ops_csv}")

    meta, preprocessor, models = load_models(models_dir)
    time_grid = parse_time_grid(args.time_grid)

    ops_df = pd.read_csv(ops_csv)
    required_cols = {"id", "T_C", "RH_mid_pct", "v_ms", "thickness_mm", "t_split_min"}
    missing = required_cols - set(ops_df.columns)
    if missing:
        raise ValueError(f"Operating point CSV missing columns: {', '.join(sorted(missing))}")
    out_dir.mkdir(parents=True, exist_ok=True)

    for _, row in ops_df.iterrows():
        identifier = row["id"]
        predictions = predict_for_row(row, preprocessor, models, meta)

        curves = reconstruct_piecewise(
            time_grid,
            {"k": predictions["kL"], "n": predictions["nL"], "b": predictions["bL"]},
            {"k": predictions["kR"], "n": predictions["nR"], "b": predictions["bR"]},
            float(row["t_split_min"]),
            predictions["offsetR_at_join"],
            predictions["right_time_shift_at_boundary"],
            False,
            False,
        )

        segment = np.where(time_grid <= row["t_split_min"], "left", "right")
        df = pd.DataFrame(
            {
                "id": identifier,
                "t": curves["time"],
                "MR_pred": curves["final"],
                "segment": segment,
                "MR_L": curves["left"],
                "MR_R_raw": curves["right_raw"],
                "MR_R_shifted": curves["right_shifted"],
                "offsetR": predictions["offsetR_at_join"],
                "tshift": predictions["right_time_shift_at_boundary"],
            }
        )

        csv_path = out_dir / f"{identifier}_prediction.csv"
        df.to_csv(csv_path, index=False)

        plt.figure(figsize=(8, 4.5))
        plt.plot(curves["time"], curves["left"], label="MR_L", linestyle="--")
        plt.plot(curves["time"], curves["right_raw"], label="MR_R_raw", linestyle=":")
        plt.plot(curves["time"], curves["right_shifted"], label="MR_R_shifted", linestyle="-")
        plt.plot(curves["time"], curves["final"], label="MR_pred", linewidth=2)
        plt.axvline(float(row["t_split_min"]), color="black", linestyle="--", alpha=0.5)
        plt.xlabel("Time (min)")
        plt.ylabel("MR")
        plt.title(f"Phase-2 prediction for {identifier}")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / f"{identifier}_prediction.png", dpi=150)
        plt.close()

    write_run_meta(out_dir, list(sys.argv))


if __name__ == "__main__":
    main()

