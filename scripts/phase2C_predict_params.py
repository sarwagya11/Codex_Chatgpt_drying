"""Predict Midilli parameters for new drying segments."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from joblib import load

# Ensure project modules are importable when running as a script -----------------
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics.phase2_utils import ALL_FEATURE_COLUMNS, prepare_feature_frame  # noqa: E402

REQUIRED_TIMING_COLUMNS = {"segment_start_time", "segment_duration"}
REQUIRED_RAW_FEATURES = {"T", "RH", "velocity", "thickness", "segment_position"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use trained regressors to predict Midilli parameters.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv",
        help="CSV containing segment descriptors for prediction.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2" / "models",
        help="Directory with trained parameter models (from phase2B).",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "phase2" / "predicted_params.csv",
        help="Destination CSV for predicted parameters.",
    )
    return parser.parse_args()


def load_artifact(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact missing: {path}")
    artifact: Dict[str, Any] = load(path)
    if "model" not in artifact:
        raise KeyError(f"Model artifact at {path} is missing the 'model' entry")
    return artifact


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input_csv)

    missing_timing = REQUIRED_TIMING_COLUMNS - set(df.columns)
    if missing_timing:
        raise KeyError(f"Missing timing columns: {sorted(missing_timing)}")

    missing_features = REQUIRED_RAW_FEATURES - set(df.columns)
    if missing_features:
        raise KeyError(f"Missing required features: {sorted(missing_features)}")

    feature_frame = prepare_feature_frame(df)

    if feature_frame.isnull().any().any():
        print("[WARN] NaNs found in input features — prediction may degrade.")
        df["has_nan_features"] = feature_frame.isnull().any(axis=1)
    else:
        df["has_nan_features"] = False

    models_dir = args.models_dir
    predictions: Dict[str, np.ndarray] = {}

    for target in ("k", "n", "b"):
        artifact_path = models_dir / f"{target}_model.pkl"
        artifact = load_artifact(artifact_path)
        model = artifact["model"]  # type: Any
        model_features = artifact.get("all_feature_columns", ALL_FEATURE_COLUMNS)

        # Check if model expects columns that are missing
        missing_in_X = set(model_features) - set(feature_frame.columns)
        if missing_in_X:
            raise ValueError(
                f"Model for {target} expects missing columns: {sorted(missing_in_X)}"
            )

        X = feature_frame[model_features]
        preds = model.predict(X)

        if not np.all(np.isfinite(preds)):
            raise ValueError(f"Non-finite predictions detected in {target}")

        predictions[f"pred_{target}"] = preds

    for col, values in predictions.items():
        df[col] = np.asarray(values, dtype=float)

    # Ensure segment_end_time is computed if missing
    if "segment_end_time" not in df.columns:
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]

    output_path: Path = args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.9g")
    print(f"[Phase2C] Wrote predictions for {len(df)} segments to {output_path}")


if __name__ == "__main__":
    main()
