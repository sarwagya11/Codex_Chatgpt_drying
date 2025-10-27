from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
    dataset = PROJECT_ROOT / "T_40_v1p1.csv"
    output_dir = tmp_path / "phase1"

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


def test_cli_execution_modes(tmp_path: Path) -> None:
    dataset = PROJECT_ROOT / "T_40_v1p1.csv"
    dataset_two = PROJECT_ROOT / "T_45_v1p1.csv"

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

    pattern = str(dataset.parent / "T_4*_v1p1.csv")
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
    for stem in (dataset.stem, dataset_two.stem):
        assert (batch_dir / stem / "summary.json").exists()
