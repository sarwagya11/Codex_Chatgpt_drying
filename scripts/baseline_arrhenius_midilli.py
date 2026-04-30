"""
Phase 6 / Study 2 -- Arrhenius single-segment Midilli baseline + LOCO-CV.

Model:
  MR(t) = exp(-k(T) * t^n) + b * t
  k(T) = A * exp(-Ea / (R * T_K))         (Arrhenius)
  n    = n0 + n_T * (T - 50) + n_v * (v - 1.1)
  b    = b0 + b_RH * (RH - 42.5)

Training:
  Pool all 13 raw curves, fit (A, Ea, n0, n_T, n_v, b0, b_RH) globally using
  multi-start least-squares (5 starts: literature-prior nominal + 4 random).
  Phase B audit (2026-04-29) showed ~30% of random starts get trapped at local
  minima where b0 saturates the lower bound; multi-start guarantees the
  global minimum.

LOCO-CV:
  For each held-out condition, refit globally on the remaining 12 curves
  (5-start best-of), evaluate predicted MR(t) on the held-out raw time grid,
  score same metrics as Study 1.

Outputs:
  outputs/baseline/diagnostics/loco_cv_baseline.csv
  outputs/baseline/diagnostics/loco_cv_baseline_summary.json
  outputs/baseline/diagnostics/global_fit.json    (full-data fit for reference)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from _kinetics_common import (
    R_GAS, RH_REF, T_REF_C, V_REF,
    fit_m2_multistart, load_curves, m2_predict, metrics_mr, time_at_mr,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "outputs" / "baseline" / "diagnostics"
PRED_DIR = OUT_DIR / "loco_cv_predictions"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)

    curves: List[Dict] = load_curves(TARGETS_CSV, DATA_DIR)

    # Reference fit on all data (multi-start best-of-5)
    p_full = fit_m2_multistart(curves, n_starts=5, seed=0)
    full_meta = {
        "logA": float(p_full[0]),
        "A_per_min_n": float(np.exp(p_full[0])),
        "Ea_J_per_mol": float(p_full[1]),
        "Ea_over_R": float(p_full[1] / R_GAS),
        "n0": float(p_full[2]),
        "n_T": float(p_full[3]),
        "n_v": float(p_full[4]),
        "b0": float(p_full[5]),
        "b_RH": float(p_full[6]),
        "T_ref_C": T_REF_C,
        "v_ref_ms": V_REF,
        "RH_ref_pct": RH_REF,
    }
    (OUT_DIR / "global_fit.json").write_text(json.dumps(full_meta, indent=2))

    rows = []
    for i, target in enumerate(curves):
        train = [c for j, c in enumerate(curves) if j != i]
        p_loco = fit_m2_multistart(train, n_starts=5, seed=i + 1)
        mr_pred = m2_predict(target["t"], target["T_C"], target["v_ms"],
                             target["RH_pct"], p_loco)
        m = metrics_mr(target["mr"], mr_pred)
        t_actual = time_at_mr(target["t"], target["mr"], 0.1)
        t_pred = time_at_mr(target["t"], mr_pred, 0.1)
        if np.isfinite(t_actual) and np.isfinite(t_pred) and t_actual > 0:
            t_rel = abs(t_pred - t_actual) / t_actual
        else:
            t_rel = float("nan")

        pd.DataFrame({
            "time_min": target["t"], "mr_actual": target["mr"], "mr_pred": mr_pred,
        }).to_csv(PRED_DIR / f"{target['dataset']}_pred_vs_actual.csv",
                  index=False, float_format="%.9g")

        print(f"[{i+1:2d}/{len(curves)}] {target['dataset']:30s} "
              f"RMSE={m['rmse']:.4f} R2={m['r2']:.4f} "
              f"MBE={m['mbe']:+.4f} t10%_relerr={t_rel:.3f}")

        rows.append(dict(
            dataset=target["dataset"], rmse_mr=m["rmse"], r2=m["r2"], mbe=m["mbe"],
            chi2_red=m["chi2_red"], ef=m["ef"],
            t_at_MR0p1_actual=t_actual, t_at_MR0p1_pred=t_pred,
            t_at_MR0p1_rel_err=t_rel,
            n_obs=int(np.sum(np.isfinite(target["mr"]))),
        ))

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "loco_cv_baseline.csv", index=False, float_format="%.9g")

    summary = {
        "n_folds": len(rows),
        "rmse_mr_mean": float(np.nanmean(out["rmse_mr"])),
        "rmse_mr_std": float(np.nanstd(out["rmse_mr"])),
        "rmse_mr_max": float(np.nanmax(out["rmse_mr"])),
        "r2_mean": float(np.nanmean(out["r2"])),
        "r2_min": float(np.nanmin(out["r2"])),
        "mbe_mean": float(np.nanmean(out["mbe"])),
        "ef_mean": float(np.nanmean(out["ef"])),
        "t_at_MR0p1_rel_err_mean": float(np.nanmean(out["t_at_MR0p1_rel_err"])),
        "t_at_MR0p1_rel_err_max": float(np.nanmax(out["t_at_MR0p1_rel_err"])),
        "n_pass_rmse_lt_0p025": int(np.sum(out["rmse_mr"] < 0.025)),
        "n_pass_r2_gt_0p99": int(np.sum(out["r2"] > 0.99)),
        "global_fit": full_meta,
    }
    (OUT_DIR / "loco_cv_baseline_summary.json").write_text(json.dumps(summary, indent=2))

    print()
    print("=" * 70)
    print(f"Arrhenius single-Midilli baseline LOCO-CV  (n={summary['n_folds']})")
    print("=" * 70)
    print(f"RMSE_MR  mean={summary['rmse_mr_mean']:.4f}  "
          f"std={summary['rmse_mr_std']:.4f}  max={summary['rmse_mr_max']:.4f}")
    print(f"R^2      mean={summary['r2_mean']:.4f}  min={summary['r2_min']:.4f}")
    print(f"MBE      mean={summary['mbe_mean']:+.4f}")
    print(f"t@MR=0.1 mean rel-err={summary['t_at_MR0p1_rel_err_mean']:.3f}  "
          f"max={summary['t_at_MR0p1_rel_err_max']:.3f}")
    print(f"Folds passing RMSE<0.025 : {summary['n_pass_rmse_lt_0p025']}/{summary['n_folds']}")
    print(f"Folds passing R^2>0.99   : {summary['n_pass_r2_gt_0p99']}/{summary['n_folds']}")
    print(f"\nGlobal fit (full data, 5-start best-of):")
    print(f"  Ea/R = {full_meta['Ea_over_R']:.1f} K")
    print(f"  A    = {full_meta['A_per_min_n']:.4g} min^-n")
    print(f"  n0={full_meta['n0']:.3f}  n_T={full_meta['n_T']:.4f}  "
          f"n_v={full_meta['n_v']:.4f}")
    print(f"  b0={full_meta['b0']:.4g}  b_RH={full_meta['b_RH']:.4g}")
    print(f"\nResults : {OUT_DIR / 'loco_cv_baseline.csv'}")
    print(f"Summary : {OUT_DIR / 'loco_cv_baseline_summary.json'}")


if __name__ == "__main__":
    main()
