"""Phase 2 pipeline integration and unit tests."""  # CHANGE: Added new test module

from __future__ import annotations  # CHANGE: Future annotations retained

import json  # CHANGE: JSON handling for summary
import os  # CHANGE: Environment manipulation
import subprocess  # CHANGE: Subprocess for script execution
import sys  # CHANGE: Access to Python executable
from pathlib import Path  # CHANGE: Path handling

import numpy as np  # CHANGE: Numerical assertions
import pandas as pd  # CHANGE: DataFrame operations
import pytest  # CHANGE: Pytest utilities

from kinetics.metrics import continuity_gap, segment_discontinuities  # CHANGE: Metrics imports
from kinetics.models_phase2 import make_baseline_estimators  # CHANGE: Model utilities import
from kinetics.phase2_utils import prepare_feature_frame  # CHANGE: Feature engineering import

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # CHANGE: Project root constant
SCRIPTS_DIR = PROJECT_ROOT / "scripts"  # CHANGE: Scripts directory constant
OUTPUTS_DIR = PROJECT_ROOT / "outputs"  # CHANGE: Outputs directory constant


def _pythonpath_env() -> dict[str, str]:  # CHANGE: Helper to extend PYTHONPATH
    env = os.environ.copy()  # CHANGE: Copy environment
    src_path = PROJECT_ROOT / "src"  # CHANGE: Source path
    paths = [str(PROJECT_ROOT), str(src_path)]  # CHANGE: Paths to include
    existing = env.get("PYTHONPATH")  # CHANGE: Existing PYTHONPATH
    if existing:  # CHANGE: Append existing path
        paths.append(existing)  # CHANGE: Append existing
    env["PYTHONPATH"] = os.pathsep.join(paths)  # CHANGE: Update PYTHONPATH
    return env  # CHANGE: Return environment


def test_metrics_utilities_behaviour() -> None:  # CHANGE: Unit test for metrics utilities
    start_gap = continuity_gap(0.5, 0.5, normalize=True)  # CHANGE: Compute normalized gap
    assert start_gap == pytest.approx(0.0)  # CHANGE: Assert zero gap

    df = pd.DataFrame(  # CHANGE: Build sample segment frame
        {
            "dataset_name": ["sample", "sample"],
            "segment_start_time": [0.0, 5.0],
            "segment_start_MR": [0.9, 0.5],
            "segment_end_MR": [0.5, 0.3],
        }
    )
    discontinuities = segment_discontinuities(df)  # CHANGE: Compute discontinuities
    assert len(discontinuities) == 1  # CHANGE: Expect single discontinuity row
    assert discontinuities.iloc[0]["gap"] == pytest.approx(0.0)  # CHANGE: Expect zero gap

    estimators = make_baseline_estimators()  # CHANGE: Retrieve estimators
    assert "Linear" in estimators  # CHANGE: Ensure baseline model present


def test_prepare_feature_frame_numeric_conversion() -> None:  # CHANGE: Unit test for feature engineering
    df = pd.DataFrame(  # CHANGE: Build raw segment data
        {
            "T": [50],
            "RH": [30],
            "velocity": [1.2],
            "thickness": [6.0],
            "segment_position": [0],
            "segment_duration": [3.0],
        }
    )
    features = prepare_feature_frame(df)  # CHANGE: Generate features
    assert set(features.columns).issuperset({"inv_thickness_sq", "T_RH_ratio", "temp_vel"})  # CHANGE: Check engineered columns


@pytest.mark.integration  # CHANGE: Mark integration test
def test_phase2_pipeline_end_to_end(tmp_path: Path) -> None:  # CHANGE: Integration test for Phase 2 scripts
    data_dir = tmp_path / "data"  # CHANGE: Temp data directory
    diagnostics_dir = tmp_path / "diagnostics"  # CHANGE: Temp diagnostics directory
    logs_dir = tmp_path / "logs"  # CHANGE: Temp logs directory
    models_dir = tmp_path / "models"  # CHANGE: Temp models directory
    plots_dir = tmp_path / "plots"  # CHANGE: Temp plots directory
    outputs_dir = tmp_path / "outputs"  # CHANGE: Temp outputs directory
    for directory in [data_dir, diagnostics_dir, logs_dir, models_dir, plots_dir, outputs_dir]:  # CHANGE: Create directories
        directory.mkdir(parents=True, exist_ok=True)  # CHANGE: Ensure directory exists

    dataset_path = data_dir / "synthetic_dataset.csv"  # CHANGE: Synthetic dataset path
    dataset_df = pd.DataFrame(  # CHANGE: Build synthetic dataset
        {
            "time_min": np.arange(0.0, 7.0, 1.0),
            "MR": np.linspace(1.0, 0.4, 7),
            "T_C": [50.0] * 7,
            "RH_pct": [25.0] * 7,
            "v_ms": [1.0] * 7,
            "thickness_mm": [5.0] * 7,
        }
    )
    dataset_df.to_csv(dataset_path, index=False)  # CHANGE: Persist synthetic dataset

    summary_path = tmp_path / "summary_index.json"  # CHANGE: Summary index path
    summary_payload = {  # CHANGE: Summary content
        "head_trim_min": 0.0,
        "datasets": [
            {
                "input": str(dataset_path),
                "head_trim_min": 0.0,
                "tree": {
                    "children": [
                        {
                            "t_start": 0.0,
                            "t_end": 3.0,
                            "n_obs": 4,
                            "rmse": 0.01,
                            "aicc": 10.0,
                            "params": {"k": 0.5, "n": 1.0, "b": 0.01},
                        },
                        {
                            "t_start": 3.0,
                            "t_end": 6.0,
                            "n_obs": 4,
                            "rmse": 0.02,
                            "aicc": 12.0,
                            "params": {"k": 0.45, "n": 0.95, "b": 0.008},
                        },
                    ]
                },
            }
        ],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2))  # CHANGE: Write summary JSON

    segments_csv = outputs_dir / "segments.csv"  # CHANGE: Phase2A output path
    env = _pythonpath_env()  # CHANGE: Build environment

    subprocess.run(  # CHANGE: Execute phase2A script
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase2A_prepare_dataset.py"),
            "--summary-index",
            str(summary_path),
            "--data-root",
            str(data_dir),
            "--output-path",
            str(segments_csv),
            "--diagnostics-dir",
            str(diagnostics_dir),
            "--log-dir",
            str(logs_dir),
        ],
        check=True,
        env=env,
    )
    assert segments_csv.exists()  # CHANGE: Verify phase2A output

    metrics_path = outputs_dir / "model_performance.csv"  # CHANGE: Phase2B metrics path
    subprocess.run(  # CHANGE: Execute phase2B script
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase2B_fit_param_models.py"),
            "--segments-csv",
            str(segments_csv),
            "--models-dir",
            str(models_dir),
            "--metrics-path",
            str(metrics_path),
            "--min-folds",
            "2",
            "--smoothness-alpha",
            "0.0",
            "--log-dir",
            str(logs_dir),
        ],
        check=True,
        env=env,
    )
    assert metrics_path.exists()  # CHANGE: Verify metrics output

    predictions_csv = outputs_dir / "predicted_params.csv"  # CHANGE: Phase2C output path
    subprocess.run(  # CHANGE: Execute phase2C script
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase2C_predict_params.py"),
            "--input-csv",
            str(segments_csv),
            "--models-dir",
            str(models_dir),
            "--output-path",
            str(predictions_csv),
            "--diagnostics-dir",
            str(diagnostics_dir),
            "--log-dir",
            str(logs_dir),
        ],
        check=True,
        env=env,
    )
    assert predictions_csv.exists()  # CHANGE: Verify predictions output

    reconstructed_csv = outputs_dir / "reconstructed.csv"  # CHANGE: Phase2D aggregated output path
    subprocess.run(  # CHANGE: Execute phase2D script
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase2D_reconstruct_mr.py"),
            "--predictions-csv",
            str(predictions_csv),
            "--summary-index",
            str(summary_path),
            "--data-root",
            str(data_dir),
            "--output-dir",
            str(outputs_dir / "mr_curves"),
            "--reconstructed-csv",
            str(reconstructed_csv),
            "--diagnostics-dir",
            str(diagnostics_dir),
            "--plots-dir",
            str(plots_dir),
            "--log-dir",
            str(logs_dir),
        ],
        check=True,
        env=env,
    )
    assert reconstructed_csv.exists()  # CHANGE: Verify aggregated reconstruction

    continuity_path = diagnostics_dir / "phase2C_discontinuities.csv"  # CHANGE: Continuity diagnostics path
    assert continuity_path.exists()  # CHANGE: Diagnostics existence assertion
    continuity_df = pd.read_csv(continuity_path)  # CHANGE: Load diagnostics
    if not continuity_df.empty:  # CHANGE: Conditional check
        assert not continuity_df["is_violation"].fillna(False).any()  # CHANGE: Ensure no violations flagged

    violation_path = diagnostics_dir / "phase2D_violation_report.csv"  # CHANGE: Phase2D diagnostics path
    assert violation_path.exists()  # CHANGE: Ensure diagnostics file generated

    plots_file = plots_dir / "reconstruction_plot.png"  # CHANGE: Canonical plot path
    assert plots_file.exists()  # CHANGE: Ensure plot generated

    summary_output_dir = OUTPUTS_DIR / "tests"  # CHANGE: Outputs/tests directory
    summary_output_dir.mkdir(parents=True, exist_ok=True)  # CHANGE: Ensure summary directory
    summary_payload = {  # CHANGE: Summary payload
        "segments": int(pd.read_csv(segments_csv).shape[0]),
        "metrics_rows": int(pd.read_csv(metrics_path).shape[0]),
        "has_continuity_violations": bool(
            continuity_df["is_violation"].fillna(False).any() if not continuity_df.empty else False
        ),
    }
    (summary_output_dir / "test_summary.json").write_text(json.dumps(summary_payload, indent=2))  # CHANGE: Persist summary
