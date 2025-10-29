"""Run the phase-1 drying kinetics pipeline on a single dataset."""

from __future__ import annotations

# ── standard libs
import argparse
import sys
from pathlib import Path
from typing import Dict, List

# ── make local 'src' importable (for Interactive/VSCode use)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for _cand in (_PROJECT_ROOT, _SRC_ROOT):
    _s = str(_cand)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ── local package imports (after sys.path bootstrap)
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
    load_and_preprocess,
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

    # 1) preprocess
    preprocess: PreprocessResult = load_and_preprocess(
        input_path, head_trim_min=head_trim_min
    )
    save_preprocess_artifacts(preprocess, plots_dir, "01_mr_raw_vs_iso")

    # 2) fit all model variants
    results: List[FitResult] = fit_all_models(
        preprocess.time_min, preprocess.mr_iso
    )
    best: FitResult = _select_best_result(results)

    # 3) best model predictions + residuals
    best_spec: ModelSpec = next(
        spec for spec in MODEL_SPECS if spec.name == best.model_name
    )
    best_params: Dict[str, float] = {
        name: float(best.params[name]) for name in best_spec.param_names
    }
    best_predictions = best_spec.predict(preprocess.time_min, best_params)
    best_residuals = preprocess.mr_iso - best_predictions  # residual = data - fit

    # 4) artifacts
    save_fit_artifacts(
        dataset_outdir,
        preprocess,
        results,
        best,
        best_predictions,
        best_residuals,
    )

    # 5) master CSV (append/replace rows for this file)
_write_master_rows(outdir / "phase1_master.csv", preprocess, results)

# 6) concise console summary
aicc = best.metrics.get("aicc")
loo = best.metrics.get("loo_rmse")
line = f"Best model for {input_path.name}: {best.model_name}"
if aicc is not None and loo is not None:
    line += f" (AICc={aicc:.3f}, LOO-RMSE={loo:.4f})"
if best.warnings:
    line += f" | warnings: {'; '.join(best.warnings)}"
print(line)

summary = {
    "input": str(input_path),
    "output_dir": str(dataset_outdir.resolve()),
    "best_model": best.model_name,
    "best_metrics": {
        k: best.metrics.get(k)
        for k in ["rmse", "aicc", "bic", "loo_rmse", "sse", "n_obs"]
    },
    "best_params": {
        n: best.params.get(n) for n in best.param_names
    },
    "warnings": best.warnings,
}

return summary

def _write_master_rows(
    master_path: Path, preprocess: PreprocessResult, results: List[FitResult]
) -> None:
    import pandas as pd  # local import to keep top-level light

    master_path.parent.mkdir(parents=True, exist_ok=True)
    hints = preprocess.metadata.get("hints", {}) or {}

    rows: List[Dict[str, object]] = []
    for res in results:
        row = {
            "file": preprocess.source_path.name,
            "model": res.model_name,
            "rmse": res.metrics.get("rmse"),
            "sse": res.metrics.get("sse"),
            "aic": res.metrics.get("aic"),
            "aicc": res.metrics.get("aicc"),
            "bic": res.metrics.get("bic"),
            "loo_rmse": res.metrics.get("loo_rmse"),
            "N": res.metrics.get("n_obs"),
            "T_C": hints.get("T_C"),
            "T_K": hints.get("T_K"),
            "v_ms": hints.get("v_ms"),
            "RH_pct": hints.get("RH_pct"),
            "RH_frac": hints.get("RH_frac"),
            "thickness_mm": hints.get("thickness_mm"),
        }
        for name in res.param_names:
             row[name] = res.params.get(name)
            
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

if __name__ == "__main__":  # CLI entry point
    raise SystemExit(main())


# %% Quick-start (VS Code Interactive)
# Adjust paths as needed, then click "Run Cell" on this block only.
#from scripts.phase1_fit_once import run_pipeline

#run_pipeline(
 #   input_path=r"D:\Masters\RQ5\Codex_chatgpt\T_40_v1p1.csv",
 #   outdir=r"D:\Masters\RQ5\Codex_chatgpt\phase1_out",
 #   head_trim_min=0.0,
#)
