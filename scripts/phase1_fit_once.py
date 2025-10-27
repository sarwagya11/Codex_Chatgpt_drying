# %%
# Quick-start example for VS Code Interactive Window
# from pathlib import Path
# from scripts.phase1_fit_once import run_pipeline
# run_pipeline(
#     input_path=r"D\\Masters\\RQ5\\Codex_chatgpt\\T_40_v1p1.csv",
#     outdir=Path("outputs/phase1_fits"),
#     head_trim_min=0.0,
# )

# %%
"""Fit Page and Midilli models to a single Phase-1 drying dataset."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List

try:
    _HERE = Path(__file__).resolve()
except NameError:
    _HERE = Path.cwd()

if len(_HERE.parents) >= 2:
    _PROJECT_ROOT = _HERE.parents[1]
else:
    _PROJECT_ROOT = _HERE.parent

_SRC_PATH = _PROJECT_ROOT / "src"
if _SRC_PATH.exists() and str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from kinetics.fitters_phase1 import fit_variant
from kinetics.models_phase1 import MODEL_PARAM_NAMES
from kinetics.preprocess_phase1 import PreprocessResult, preprocess_dataset

MODEL_VARIANTS = [
    "page_no_tau",
    "page_tau",
    "midilli_a1_no_tau",
    "midilli_a1_tau",
]


def run_pipeline(
    input_path: str,
    outdir: Path,
    head_trim_min: float = 0.0,
) -> Dict[str, object]:
    input_path = os.path.abspath(input_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    preprocess = preprocess_dataset(input_path, head_trim_min=head_trim_min)
    fits = []
    for variant in MODEL_VARIANTS:
        result = fit_variant(variant, preprocess.t, preprocess.mr_iso)
        fits.append(result)

    fits_df = _summaries_to_dataframe(fits)
    best = _select_best_model(fits_df)

    dataset_dir = outdir / Path(input_path).stem
    dataset_dir.mkdir(parents=True, exist_ok=True)

    residuals = _save_outputs(
        dataset_dir=dataset_dir,
        preprocess=preprocess,
        fits=fits,
        fits_df=fits_df,
        best=best,
        input_path=input_path,
    )

    master_path = outdir / "phase1_master.csv"
    _update_master_csv(
        master_path=master_path,
        input_path=input_path,
        best_row=best,
        metadata=preprocess.metadata,
    )

    _print_summary(best, preprocess, residuals)

    return {
        "preprocess": preprocess,
        "fits": fits,
        "fits_df": fits_df,
        "best": best,
        "output_dir": dataset_dir,
    }


def _summaries_to_dataframe(fits):
    records: List[Dict[str, object]] = []
    for fit in fits:
        row: Dict[str, object] = {
            "model": fit.func_name,
            "rmse": fit.rmse,
            "sse": fit.sse,
            "aic": fit.aic,
            "aicc": fit.aicc,
            "bic": fit.bic,
            "loo_rmse": fit.loo_rmse,
            "success": fit.success,
            "message": fit.message,
            "n_obs": fit.n_obs,
            "warnings": "; ".join(fit.warnings) if fit.warnings else "",
        }
        for name, value in zip(fit.param_names, fit.params):
            row[f"{name}"] = value
        if fit.stderr is not None:
            for name, se in zip(fit.param_names, fit.stderr):
                row[f"{name}_se"] = se
        if fit.ci95 is not None:
            for idx, name in enumerate(fit.param_names):
                row[f"{name}_ci_lower"] = fit.ci95[idx, 0]
                row[f"{name}_ci_upper"] = fit.ci95[idx, 1]
        records.append(row)
    return pd.DataFrame.from_records(records)


def _select_best_model(fits_df: pd.DataFrame) -> pd.Series:
    df = fits_df.copy()
    df["aicc_sort"] = df["aicc"].replace({np.nan: np.inf})
    df["loo_sort"] = df["loo_rmse"].replace({np.nan: np.inf})
    df.sort_values(["aicc_sort", "loo_sort"], inplace=True)
    return df.iloc[0]


def _save_outputs(dataset_dir: Path, preprocess: PreprocessResult, fits, fits_df, best, input_path: str):
    summary = {
        "input_file": input_path,
        "metadata": preprocess.metadata,
        "best_model": {
            "name": best["model"],
            "metrics": {
                "rmse": best["rmse"],
                "aicc": best["aicc"],
                "bic": best["bic"],
                "loo_rmse": best["loo_rmse"],
            },
            "parameters": {
                name: best.get(name) for name in MODEL_PARAM_NAMES[best["model"]]
            },
            "warnings": best.get("warnings"),
        },
        "all_models": fits_df.to_dict(orient="records"),
    }

    with open(dataset_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=_json_default)

    fits_df.to_csv(dataset_dir / "params.csv", index=False)

    joblib.dump(
        {
            fit.func_name: {
                "params": fit.params,
                "stderr": fit.stderr,
                "ci95": fit.ci95,
                "metrics": {
                    "rmse": fit.rmse,
                    "aicc": fit.aicc,
                    "bic": fit.bic,
                    "loo_rmse": fit.loo_rmse,
                },
            }
            for fit in fits
        },
        dataset_dir / "fit_results.joblib",
    )

    residuals = _make_plots(dataset_dir, preprocess, best)
    return residuals


def _make_plots(dataset_dir: Path, preprocess: PreprocessResult, best: pd.Series):
    t = preprocess.t
    mr_raw = preprocess.mr_raw
    mr_iso = preprocess.mr_iso
    model_name = best["model"]
    params = [best.get(name, np.nan) for name in MODEL_PARAM_NAMES[model_name]]

    from kinetics.models_phase1 import MODEL_FUNCS

    predictions = MODEL_FUNCS[model_name](params, t)
    residuals = mr_iso - predictions

    plt.figure(figsize=(6, 4))
    plt.plot(t, mr_raw, "o", label="MR raw", alpha=0.6)
    plt.plot(t, mr_iso, "-", label="MR iso")
    plt.xlabel("Time (min)")
    plt.ylabel("Moisture ratio")
    plt.legend()
    plt.title("Moisture ratio preprocessing")
    plt.tight_layout()
    plt.savefig(dataset_dir / "mr_preprocessing.png", dpi=300)
    plt.close()

    plt.figure(figsize=(6, 4))
    plt.plot(t, mr_iso, "o", label="MR iso")
    plt.plot(t, predictions, "-", label=f"{model_name} fit")
    annotation_lines = [f"{name} = {best.get(name):.4g}" for name in MODEL_PARAM_NAMES[model_name]]
    annotation = "\n".join(annotation_lines)
    plt.annotate(annotation, xy=(0.05, 0.05), xycoords="axes fraction", fontsize=9,
                 bbox=dict(boxstyle="round", fc="white", alpha=0.7))
    plt.xlabel("Time (min)")
    plt.ylabel("Moisture ratio")
    plt.legend()
    plt.title("Best-fit model")
    plt.tight_layout()
    plt.savefig(dataset_dir / "best_fit.png", dpi=300)
    plt.close()

    plt.figure(figsize=(6, 4))
    plt.axhline(0, color="k", linewidth=0.8)
    plt.plot(t, residuals, "o-")
    plt.xlabel("Time (min)")
    plt.ylabel("Residuals (MR)")
    plt.title("Residuals vs time")
    plt.tight_layout()
    plt.savefig(dataset_dir / "residuals.png", dpi=300)
    plt.close()

    sm.qqplot(residuals, line="s")
    plt.title("Residual QQ plot")
    plt.tight_layout()
    plt.savefig(dataset_dir / "residuals_qq.png", dpi=300)
    plt.close()

    return residuals


def _update_master_csv(master_path: Path, input_path: str, best_row: pd.Series, metadata: Dict[str, object]):
    hints = metadata.get("hints", {}) or {}
    record = {
        "file": os.path.abspath(input_path),
        "model": best_row["model"],
        "k": best_row.get("k"),
        "n": best_row.get("n"),
        "b": best_row.get("b"),
        "tau": best_row.get("tau"),
        "rmse": best_row.get("rmse"),
        "aicc": best_row.get("aicc"),
        "bic": best_row.get("bic"),
        "loo_rmse": best_row.get("loo_rmse"),
        "N": int(best_row.get("n_obs", 0)),
    }
    for key in ["T_C", "v_ms", "RH_pct", "thickness_mm"]:
        record[key] = hints.get(key)

    df = pd.DataFrame([record])
    if master_path.exists():
        df_existing = pd.read_csv(master_path)
        df_combined = pd.concat([df_existing, df], ignore_index=True)
    else:
        df_combined = df
    df_combined.drop_duplicates(subset=["file", "model"], keep="last", inplace=True)
    df_combined.to_csv(master_path, index=False)


def _json_default(obj):
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def _print_summary(best: pd.Series, preprocess: PreprocessResult, residuals: np.ndarray):
    warnings = best.get("warnings")
    warning_text = f" | Warnings: {warnings}" if warnings else ""
    params = ", ".join(
        f"{name}={best.get(name):.4g}" for name in MODEL_PARAM_NAMES[best["model"]]
        if not pd.isna(best.get(name))
    )
    rmse = best.get("rmse")
    aicc = best.get("aicc")
    loo = best.get("loo_rmse")
    print(
        f"Best model: {best['model']} | Params: {params} | RMSE={rmse:.4g} | "
        f"AICc={aicc:.4g} | LOO-RMSE={loo:.4g}{warning_text}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit Phase-1 drying kinetics models to a dataset")
    parser.add_argument("--input", required=True, help="Absolute path to CSV or XLSX dataset")
    parser.add_argument(
        "--outdir",
        default="outputs/phase1_fits",
        help="Directory for fit artifacts",
    )
    parser.add_argument(
        "--head_trim_min",
        type=float,
        default=0.0,
        help="Minutes of head segment to trim before fitting",
    )
    return parser.parse_args()


def _running_interactively() -> bool:
    """Return True when executed inside an IPython / VS Code Interactive session."""

    try:
        from IPython import get_ipython  # type: ignore
    except Exception:
        return False
    shell = get_ipython()
    return shell is not None


def main():
    if len(sys.argv) <= 1 and _running_interactively():
        print(
            "Interactive session detected — call run_pipeline(...) from the first cell "
            "instead of invoking the CLI without arguments."
        )
        return

    args = _parse_args()
    run_pipeline(
        input_path=args.input,
        outdir=Path(args.outdir),
        head_trim_min=args.head_trim_min,
    )


if __name__ == "__main__":
    main()
