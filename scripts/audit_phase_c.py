"""
Phase C audit: unified LOCO + bootstrap CIs.

Goals:
  1. Re-run LOCO for M1 and M2 using one shared preprocessing/metrics module
     (verifies that earlier M1 and M2 numbers in MEMORY are reproducible).
  2. For M2, use 5-start best-of within each fold to guarantee the global
     minimum (Phase B showed M2 has local minima for some random P0).
  3. Pull M3 LOCO numbers from the existing CSV (recursive piecewise + ML
     pipeline; refitting is too expensive for this audit).
  4. Compute paired bootstrap 95% CIs on RMSE_MR differences:
        M1 - M2,  M2 - M3,  M1 - M3
     Use 5000 resamples with replacement at the per-curve level.
  5. Save:
        outputs/audit/phase_c_loco_results.csv  (per-fold M1, M2 RMSE)
        outputs/audit/phase_c_bootstrap.json     (means + 95% CIs)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from _kinetics_common import (
    M1_NOM,
    fit_m1, fit_m2_multistart, load_curves, m1_predict, m2_predict,
    paired_bootstrap, rmse,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV  = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR     = PROJECT_ROOT / "data"
M3_CSV       = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics" / "loco_cv_results.csv"
OUT_DIR      = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_loco(curves):
    rows = []
    for k, held in enumerate(curves):
        train = [c for j, c in enumerate(curves) if j != k]
        # M1: single start (convex)
        p_m1 = fit_m1(train, M1_NOM).x
        m1_pred = m1_predict(held["t"], held["T_C"], held["RH_pct"],
                             held["v_ms"], held["d_mm"], p_m1)
        m1_rmse = rmse(held["mr"], m1_pred)
        # M2: multi-start best-of (5)
        p_m2 = fit_m2_multistart(train, n_starts=5, seed=k)
        m2_pred = m2_predict(held["t"], held["T_C"], held["v_ms"],
                             held["RH_pct"], p_m2)
        m2_rmse = rmse(held["mr"], m2_pred)
        rows.append(dict(dataset=held["dataset"],
                         m1_loco_rmse=m1_rmse, m2_loco_rmse=m2_rmse))
        print(f"  fold {k+1:2d}/{len(curves)}  {held['dataset']:30s}  "
              f"M1={m1_rmse:.4f}  M2={m2_rmse:.4f}")
    return pd.DataFrame(rows)


def main():
    curves = load_curves(TARGETS_CSV, DATA_DIR)
    print(f"Loaded {len(curves)} curves.")

    print("\nRunning unified LOCO (M1 single-start, M2 5-start best-of)...")
    df = run_loco(curves)

    # Pull M3 from the existing CSV
    m3 = pd.read_csv(M3_CSV)[["dataset", "rmse_mr"]].rename(
        columns={"rmse_mr": "m3_loco_rmse"})
    merged = df.merge(m3, on="dataset", how="left")
    merged.to_csv(OUT_DIR / "phase_c_loco_results.csv",
                  index=False, float_format="%.6g")

    diff_m1_m2 = (merged["m1_loco_rmse"] - merged["m2_loco_rmse"]).to_numpy()
    diff_m2_m3 = (merged["m2_loco_rmse"] - merged["m3_loco_rmse"]).to_numpy()
    diff_m1_m3 = (merged["m1_loco_rmse"] - merged["m3_loco_rmse"]).to_numpy()

    boot = dict(
        n_curves=int(len(merged)),
        n_boot=5000,
        means=dict(
            m1=float(merged["m1_loco_rmse"].mean()),
            m2=float(merged["m2_loco_rmse"].mean()),
            m3=float(merged["m3_loco_rmse"].mean()),
        ),
        diffs=dict(
            m1_minus_m2=paired_bootstrap(diff_m1_m2),
            m2_minus_m3=paired_bootstrap(diff_m2_m3),
            m1_minus_m3=paired_bootstrap(diff_m1_m3),
        ),
        paired_t=dict(
            m1_vs_m2={"t": float(stats.ttest_rel(merged["m1_loco_rmse"], merged["m2_loco_rmse"]).statistic),
                       "p": float(stats.ttest_rel(merged["m1_loco_rmse"], merged["m2_loco_rmse"]).pvalue)},
            m2_vs_m3={"t": float(stats.ttest_rel(merged["m2_loco_rmse"], merged["m3_loco_rmse"]).statistic),
                       "p": float(stats.ttest_rel(merged["m2_loco_rmse"], merged["m3_loco_rmse"]).pvalue)},
            m1_vs_m3={"t": float(stats.ttest_rel(merged["m1_loco_rmse"], merged["m3_loco_rmse"]).statistic),
                       "p": float(stats.ttest_rel(merged["m1_loco_rmse"], merged["m3_loco_rmse"]).pvalue)},
        ),
    )
    (OUT_DIR / "phase_c_bootstrap.json").write_text(json.dumps(boot, indent=2))

    print("\n" + "=" * 78)
    print(f"Phase C  (unified LOCO + paired bootstrap, n={len(merged)})")
    print("=" * 78)
    print(f"  Mean RMSE  M1 = {boot['means']['m1']:.4f}   "
          f"M2 = {boot['means']['m2']:.4f}   "
          f"M3 = {boot['means']['m3']:.4f}")
    for label, key in [("M1 - M2", "m1_minus_m2"),
                       ("M2 - M3", "m2_minus_m3"),
                       ("M1 - M3", "m1_minus_m3")]:
        d = boot["diffs"][key]
        print(f"  {label}: mean = {d['mean']:+.4f}  "
              f"95% CI [{d['ci95_lo']:+.4f}, {d['ci95_hi']:+.4f}]")
    print(f"\nSaved {OUT_DIR / 'phase_c_loco_results.csv'}")
    print(f"      {OUT_DIR / 'phase_c_bootstrap.json'}")


if __name__ == "__main__":
    main()
