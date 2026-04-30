"""
Phase 6 -- Compare Study 1 (piecewise + ML) vs Study 2 (Arrhenius single Midilli).

Paired tests on per-condition RMSE_MR and time-to-MR=0.1 errors.
Also computes delta-AICc piecewise vs single from existing tree_summary.json files
(Study 5 -- nearly free since the recursive fitter already saved 'unsplit' fits).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIECEWISE_CSV = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics" / "loco_cv_results.csv"
BASELINE_CSV  = PROJECT_ROOT / "outputs" / "baseline" / "diagnostics" / "loco_cv_baseline.csv"
TREE_DIR      = PROJECT_ROOT / "outputs" / "piecewise_recursive_2ndphase"
OUT_DIR       = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics"


def main() -> None:
    pw = pd.read_csv(PIECEWISE_CSV)
    bl = pd.read_csv(BASELINE_CSV)

    # Align by dataset name
    merged = pw[["dataset", "rmse_mr", "r2", "mbe", "t_at_MR0p1_rel_err"]].rename(
        columns=lambda c: c if c == "dataset" else f"pw_{c}"
    ).merge(
        bl[["dataset", "rmse_mr", "r2", "mbe", "t_at_MR0p1_rel_err"]].rename(
            columns=lambda c: c if c == "dataset" else f"bl_{c}"
        ),
        on="dataset",
    )
    merged["delta_rmse"] = merged["pw_rmse_mr"] - merged["bl_rmse_mr"]
    merged["delta_t_relerr"] = merged["pw_t_at_MR0p1_rel_err"] - merged["bl_t_at_MR0p1_rel_err"]

    # Paired t-test on RMSE diffs (n=13, normality is roughly OK for RMSE)
    rmse_t = stats.ttest_rel(merged["pw_rmse_mr"], merged["bl_rmse_mr"], nan_policy="omit")
    # Wilcoxon signed-rank (nonparametric, more robust at n=13)
    rmse_w = stats.wilcoxon(merged["pw_rmse_mr"], merged["bl_rmse_mr"], zero_method="wilcox")

    # Time-to-target -- only on rows where both are finite
    finite = merged.dropna(subset=["pw_t_at_MR0p1_rel_err", "bl_t_at_MR0p1_rel_err"])
    if len(finite) >= 3:
        t_t = stats.ttest_rel(finite["pw_t_at_MR0p1_rel_err"], finite["bl_t_at_MR0p1_rel_err"])
        t_w = stats.wilcoxon(finite["pw_t_at_MR0p1_rel_err"], finite["bl_t_at_MR0p1_rel_err"],
                             zero_method="wilcox")
    else:
        t_t = t_w = None

    # Counts of where each model "wins" (lower RMSE)
    pw_wins = int((merged["delta_rmse"] < 0).sum())
    bl_wins = int((merged["delta_rmse"] > 0).sum())

    # ---- Study 5: delta-AICc piecewise vs single ----
    aicc_rows = []
    for ds_dir in sorted(TREE_DIR.iterdir()):
        if not ds_dir.is_dir():
            continue
        summary = ds_dir / "tree_summary.json"
        if not summary.exists():
            continue
        payload = json.loads(summary.read_text())
        unsplit = payload.get("unsplit", {})
        unsplit_aicc = float(unsplit.get("AICc", float("nan")))
        # piecewise total AICc -- node 0's children sum (post-split): use node[0].score_components base
        # The training logs report delta_AICc_total which is exactly unsplit - sum-of-children.
        # We can read it directly from the metrics block.
        delta_total = float(payload.get("metrics", {}).get("delta_AICc_total", float("nan")))
        # piecewise_aicc = unsplit - delta (since delta = unsplit - piecewise -> piecewise = unsplit - delta)
        # But the code defines delta as positive when split is better, sign of "improvement", so
        # piecewise_aicc = unsplit_aicc - delta_total.
        piecewise_aicc = unsplit_aicc - delta_total
        aicc_rows.append(dict(
            dataset=ds_dir.name,
            unsplit_AICc=unsplit_aicc,
            piecewise_AICc=piecewise_aicc,
            delta_AICc=delta_total,  # positive = piecewise better
        ))
    aicc_df = pd.DataFrame(aicc_rows)
    aicc_df.to_csv(OUT_DIR / "aicc_comparison.csv", index=False, float_format="%.4f")

    # ---- Print and save ----
    summary = {
        "n_folds": int(len(merged)),
        "rmse_mr": {
            "piecewise_mean": float(merged["pw_rmse_mr"].mean()),
            "baseline_mean":  float(merged["bl_rmse_mr"].mean()),
            "delta_mean":     float(merged["delta_rmse"].mean()),
            "paired_t_p":     float(rmse_t.pvalue),
            "paired_t_stat":  float(rmse_t.statistic),
            "wilcoxon_p":     float(rmse_w.pvalue),
            "wilcoxon_stat":  float(rmse_w.statistic),
            "piecewise_wins_count": pw_wins,
            "baseline_wins_count":  bl_wins,
        },
        "t_at_MR0p1_rel_err": {
            "piecewise_mean": float(merged["pw_t_at_MR0p1_rel_err"].mean(skipna=True)),
            "baseline_mean":  float(merged["bl_t_at_MR0p1_rel_err"].mean(skipna=True)),
            "n_finite_pairs": int(len(finite)),
            "paired_t_p":     float(t_t.pvalue) if t_t else None,
            "wilcoxon_p":     float(t_w.pvalue) if t_w else None,
        },
        "aicc": {
            "delta_mean":  float(aicc_df["delta_AICc"].mean()),
            "delta_min":   float(aicc_df["delta_AICc"].min()),
            "delta_max":   float(aicc_df["delta_AICc"].max()),
            "n_piecewise_better": int((aicc_df["delta_AICc"] > 10).sum()),
            "n_total":     int(len(aicc_df)),
            "interpretation": "delta>10 favours piecewise on training fit (information criterion).",
        },
    }
    (OUT_DIR / "phase6_comparison_summary.json").write_text(json.dumps(summary, indent=2))
    merged.to_csv(OUT_DIR / "phase6_paired_comparison.csv", index=False, float_format="%.6g")

    print("=" * 78)
    print(f"Phase 6 paired comparison  (n={len(merged)} held-out conditions)")
    print("=" * 78)
    print(f"\nRMSE_MR (lower is better)")
    print(f"  Piecewise + ML  mean = {merged['pw_rmse_mr'].mean():.4f}")
    print(f"  Arrhenius base  mean = {merged['bl_rmse_mr'].mean():.4f}")
    print(f"  Delta (pw - bl) mean = {merged['delta_rmse'].mean():+.4f}  "
          f"(positive => baseline is better)")
    print(f"  Paired t-test      : t={rmse_t.statistic:+.3f}  p={rmse_t.pvalue:.4g}")
    print(f"  Wilcoxon signed-rk : W={rmse_w.statistic:.1f}  p={rmse_w.pvalue:.4g}")
    print(f"  Win count          : piecewise wins {pw_wins}, baseline wins {bl_wins}, "
          f"ties {len(merged) - pw_wins - bl_wins}")
    print(f"\nTime-at-MR=0.1 relative error (lower is better)  "
          f"[n_finite_pairs = {len(finite)}]")
    print(f"  Piecewise + ML  mean = {merged['pw_t_at_MR0p1_rel_err'].mean(skipna=True):.3f}")
    print(f"  Arrhenius base  mean = {merged['bl_t_at_MR0p1_rel_err'].mean(skipna=True):.3f}")
    if t_t is not None:
        print(f"  Paired t-test      : t={t_t.statistic:+.3f}  p={t_t.pvalue:.4g}")
        print(f"  Wilcoxon signed-rk : W={t_w.statistic:.1f}  p={t_w.pvalue:.4g}")
    print(f"\nAICc piecewise vs single-Midilli (training-fit info criterion)")
    print(f"  delta_AICc mean = {aicc_df['delta_AICc'].mean():.1f}  "
          f"min = {aicc_df['delta_AICc'].min():.1f}  "
          f"max = {aicc_df['delta_AICc'].max():.1f}")
    print(f"  Piecewise strongly preferred (delta>10) on {(aicc_df['delta_AICc'] > 10).sum()}/{len(aicc_df)}")
    print(f"\nOutputs:")
    print(f"  {OUT_DIR / 'phase6_paired_comparison.csv'}")
    print(f"  {OUT_DIR / 'phase6_comparison_summary.json'}")
    print(f"  {OUT_DIR / 'aicc_comparison.csv'}")


if __name__ == "__main__":
    main()
