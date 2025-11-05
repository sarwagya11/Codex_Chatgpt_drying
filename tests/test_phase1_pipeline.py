from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from scripts.phase1_fit_once import run_pipeline  # noqa: E402


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_run_pipeline_creates_artifacts(tmp_path: Path) -> None:
    dataset = PROJECT_ROOT / "data" / "T_40_v1p1.csv"  # CHANGE: Use data directory
    output_dir = tmp_path / "phase1_out" / "_test_run"

    summary = run_pipeline(dataset, outdir=output_dir)
    dataset_dir = output_dir / dataset.stem
    plots_dir = dataset_dir / "plots"

    assert (dataset_dir / "summary.json").exists()
    assert (dataset_dir / "params.csv").exists()
    assert (dataset_dir / "fit_results.joblib").exists()
    assert (plots_dir / "01_mr_raw_vs_iso.png").exists()
    assert (plots_dir / "02_fit_best.png").exists()
    assert (plots_dir / "03_residuals_best.png").exists()
    assert (plots_dir / "04_qq_best.png").exists()

    summary_data = _read_json(dataset_dir / "summary.json")
    assert summary_data["best_model"] == summary["best_model"]
    master = output_dir / "phase1_master.csv"
    assert master.exists()
    master_df = pd.read_csv(master)
    matching = master_df[
        (master_df["file"] == dataset.name) & (master_df["model"] == summary["best_model"])
    ]
    assert not matching.empty


def test_cli_execution_modes(tmp_path: Path) -> None:
    dataset = PROJECT_ROOT / "data" / "T_40_v1p1.csv"  # CHANGE: Use data directory
    dataset_two = PROJECT_ROOT / "data" / "T_45_v1p1.csv"  # CHANGE: Use data directory

    once_dir = tmp_path / "cli_once"
    batch_dir = tmp_path / "cli_batch"

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "scripts.phase1_fit_once",
            "--input",
            str(dataset),
            "--outdir",
            str(once_dir),
        ],
        cwd=PROJECT_ROOT,
    )

    assert (once_dir / dataset.stem / "summary.json").exists()

    pattern = str((PROJECT_ROOT / "data") / "T_4*_v1p1.csv")  # CHANGE: Batch glob uses data directory
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "scripts.phase1_fit_all",
            "--glob",
            pattern,
            "--outdir",
            str(batch_dir),
        ],
        cwd=PROJECT_ROOT,
    )

    master = batch_dir / "phase1_master.csv"
    assert master.exists()
    master_df = pd.read_csv(master)
    for ds in (dataset, dataset_two):
        assert (batch_dir / ds.stem / "summary.json").exists()
        assert (master_df["file"] == ds.name).any()
