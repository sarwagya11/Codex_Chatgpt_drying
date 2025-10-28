"""Run the phase-1 drying kinetics pipeline on a single dataset."""

# %% Quick-start (VS Code Interactive)
# from scripts.phase1_fit_once import run_pipeline
# run_pipeline(
#     r"D:\Masters\RQ5\Codex_chatgpt\T_40_v1p1.csv",
#     r"D:\Masters\RQ5\Codex_chatgpt\phase1_out",
# )

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

# Bootstrap sys.path for interactive usage -----------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.fitters_phase1 import (  # noqa: E402
    FitResult,
    ModelSpec,
    _select_best_result,
    fit_all_models,
    save_fit_artifacts,
)
from kinetics.models_phase1 import MODEL_SPECS  # noqa: E402
from kinetics.preprocess_phase1 import (  # noqa: E402
    PreprocessResult,
    save_preprocess_artifacts,
)


def run_pipeline(
    input_path: str | Path,
    outdir: str | Path = "phase1_out",
    head_trim_min: float = 0.0,
) -> Dict[str, object]:
    """Execute the full preprocessing + fitting workflow for one dataset."""

    input_path = Path(input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    outdir = Path(outdir)
    dataset_outdir = outdir / input_path.stem
    plots_dir = dataset_outdir / "plots"

    preprocess = load_and_preprocess(input_path, head_trim_min=head_trim_min)
    save_preprocess_artifacts(preprocess, plots_dir, "01_mr_raw_vs_iso")

    results: List[FitResult] = fit_all_models(preprocess.time_min, preprocess.mr_iso)
    best: FitResult = _select_best_result(results)
    best_spec: ModelSpec = next(spec for spec in MODEL_SPECS if spec.name == best.model_name)
    best_params: Dict[str, float] = {
        name: float(best.params[name]) for name in best_spec.param_names
    }
    best_predictions = best_spec.predict(preprocess.time_min, best_params)
    best_residuals = best_predictions - preprocess.mr_iso

    save_fit_artifacts(
        dataset_outdir,
        preprocess,
        results,
        best,
        best_predictions,
        best_residuals,
    )

    _write_master_rows(outdir / "phase1_master.csv", preprocess, results)

    summary = {
        "input": str(input_path),
        "output_dir": str(dataset_outdir.resolve()),
        "best_model": best.model_name,
        "best_metrics": {
            key: best.metrics.get(key)
            for key in ["rmse", "aicc", "bic", "loo_rmse", "sse", "n_obs"]
        },
        "best_params": {name: best.params.get(name) for name in best.param_names},
        "warnings": best.warnings,
    }

    aicc = best.metrics.get("aicc")
    loo_rmse = best.metrics.get("loo_rmse")
    summary_line = f"Best model for {input_path.name}: {best.model_name}"
    if aicc is not None and loo_rmse is not None:
        summary_line += f" (AICc={aicc:.3f}, LOO-RMSE={loo_rmse:.4f})"
    if best.warnings:
        summary_line += f" | warnings: {'; '.join(best.warnings)}"
    print(summary_line)

    return summary


def _write_master_rows(
    master_path: Path, preprocess: PreprocessResult, results: List[FitResult]
) -> None:
    import pandas as pd

    master_path.parent.mkdir(parents=True, exist_ok=True)
    hints = preprocess.metadata.get("hints", {})

    rows: List[Dict[str, object]] = []
    for result in results:
        row = {
            "file": preprocess.source_path.name,
            "model": result.model_name,
            "rmse": result.metrics.get("rmse"),
            "sse": result.metrics.get("sse"),
            "aic": result.metrics.get("aic"),
            "aicc": result.metrics.get("aicc"),
            "bic": result.metrics.get("bic"),
            "loo_rmse": result.metrics.get("loo_rmse"),
            "N": result.metrics.get("n_obs"),
            "T_C": hints.get("T_C"),
            "T_K": hints.get("T_K"),
            "v_ms": hints.get("v_ms"),
            "RH_pct": hints.get("RH_pct"),
            "RH_frac": hints.get("RH_frac"),
            "thickness_mm": hints.get("thickness_mm"),
        }
        for name in result.param_names:
            row[name] = result.params.get(name)
        rows.append(row)

    new_df = pd.DataFrame(rows)

    if master_path.exists():
        master_df = pd.read_csv(master_path)
        master_df = master_df[
            ~(
                (master_df["file"] == preprocess.source_path.name)
                & master_df["model"].isin(new_df["model"])
            )
        ]
        master_df = pd.concat([master_df, new_df], ignore_index=True)
    else:
        master_df = new_df

    master_df.to_csv(master_path, index=False)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run phase-1 drying kinetics on one dataset.")
    parser.add_argument("--input", required=True, help="Path to the input CSV/XLSX dataset.")
    parser.add_argument(
        "--outdir",
        default="phase1_out",
        help="Directory for phase-1 outputs.",
    )
    parser.add_argument(
        "--head_trim_min",
        type=float,
        default=0.0,
        help="Trim leading minutes before fitting.",
    )

    args = parser.parse_args(argv)
    run_pipeline(args.input, outdir=args.outdir, head_trim_min=args.head_trim_min)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
