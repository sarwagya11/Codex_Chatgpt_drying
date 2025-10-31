"""Predict Midilli parameters for new drying segments."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

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


def load_artifact(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact missing: {path}")
    artifact = load(path)
    if "model" not in artifact:
        raise KeyError(f"Model artifact at {path} is missing the 'model' entry")
    return artifact


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input_csv)

    missing_timing = REQUIRED_TIMING_COLUMNS - set(df.columns)
    if missing_timing:
        raise KeyError(
            "Input CSV must include timing columns: " + ", ".join(sorted(missing_timing))
        )

    missing_features = REQUIRED_RAW_FEATURES - set(df.columns)
    if missing_features:
        raise KeyError(
            "Input CSV must include feature columns: " + ", ".join(sorted(missing_features))
        )

    feature_frame = prepare_feature_frame(df)

    models_dir = args.models_dir
    predictions = {}

    for target in ("k", "n", "b"):
        artifact_path = models_dir / f"{target}_model.pkl"
        artifact = load_artifact(artifact_path)
        model = artifact["model"]
        columns = artifact.get("all_feature_columns", ALL_FEATURE_COLUMNS)
        X = feature_frame[columns]
        preds = np.asarray(model.predict(X), dtype=float)
        predictions[f"pred_{target}"] = preds

    for key, values in predictions.items():
        df[key] = values

    if "segment_end_time" not in df.columns:
        df["segment_end_time"] = df["segment_start_time"] + df["segment_duration"]

    output_path: Path = args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Wrote predictions for {len(df)} segments to {output_path}")


if __name__ == "__main__":
    main()
