"""
Phase C audit: unified LOCO + bootstrap CIs.

Goals:
  1. Re-run LOCO for M1 and M2 using the shared preprocessing/metrics module
     (verifies that earlier numbers are reproducible).
  2. Apply the same multi-start best-of policy to BOTH M1 and M2 inside each
     fold, so the comparison is procedurally apples-to-apples. M1 is convex
     so multi-start is a no-op for its parameter values; the loss budget is
     trivial and the protocol consistency matters more than the runtime.
     Multi-start budget for M2 is read from phase_b_summary.json
     (`recommended_M2_loco_starts_for_p_fail_le_0_01`).
  3. M3 LOCO numbers come from `outputs/phase2/diagnostics/loco_cv_results.csv`
     produced by `scripts/phase2_loco_cv.py`. Re-run that script before this
     audit to refresh M3 (it logs its run-time inside `loco_cv_summary.json`).
  4. Compute paired bootstrap 95% CIs on RMSE_MR differences:
        M1 - M2,  M2 - M3,  M1 - M3
     Use 5000 resamples with replacement at the per-curve level.
  5. Save:
        outputs/audit/phase_c_loco_results.csv  (per-fold M1, M2, M3 RMSE)
        outputs/audit/phase_c_bootstrap.json     (means + 95% CIs)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from _kinetics_common import (
    fit_m1, fit_m2_multistart, load_curves, m1_predict, m2_predict, M1_NOM,
    paired_bootstrap, rmse,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV  = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR     = PROJECT_ROOT / "data"
M3_CSV       = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics" / "loco_cv_results.csv"
M3_SUMMARY   = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics" / "loco_cv_summary.json"
PHASE_B_JSON = PROJECT_ROOT / "outputs" / "audit" / "phase_b_summary.json"
OUT_DIR      = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_M2_STARTS = 5
M1_STARTS = 5  # nominal + 4 random; M1 is convex, this is for protocol symmetry


def _read_m2_starts() -> int:
    if PHASE_B_JSON.exists():
        try:
            data = json.loads(PHASE_B_JSON.read_text())
            return int(data.get("recommended_M2_loco_starts_for_p_fail_le_0_01",
                                DEFAULT_M2_STARTS))
        except Exception:
            pass
    return DEFAULT_M2_STARTS


def _fit_m1_multistart(train_curves, n_starts: int, seed: int):
    """Multi-start M1 fit (convex; selects lowest-cost solution)."""
    from _kinetics_common import M1_HI, M1_LO, M1_NOM as _NOM
    rng = np.random.default_rng(seed)
    starts = [_NOM] + [rng.uniform(M1_LO, M1_HI) for _ in range(n_starts - 1)]
    best = None
    best_cost = np.inf
    for p0 in starts:
        try:
            sol = fit_m1(train_curves, p0)
            if float(sol.cost) < best_cost:
                best_cost = float(sol.cost)
                best = sol.x
        except Exception:
            continue
    if best is None:
        raise RuntimeError("All M1 multi-start fits failed")
    return best


def run_loco(curves, n_m1_starts: int, n_m2_starts: int):
    rows = []
    for k, held in enumerate(curves):
        train = [c for j, c in enumerate(curves) if j != k]
        p_m1 = _fit_m1_multistart(train, n_starts=n_m1_starts, seed=k)
        m1_pred = m1_predict(held["t"], held["T_C"], held["RH_pct"],
                             held["v_ms"], held["d_mm"], p_m1)
        m1_rmse = rmse(held["mr"], m1_pred)
        p_m2 = fit_m2_multistart(train, n_starts=n_m2_starts, seed=k)
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

    n_m2_starts = _read_m2_starts()
    print(f"\nLOCO protocol: M1 multi-start n={M1_STARTS} (convex, no-op for params), "
          f"M2 multi-start n={n_m2_starts}  (read from Phase B summary)")
    df = run_loco(curves, n_m1_starts=M1_STARTS, n_m2_starts=n_m2_starts)

    # Pull M3 LOCO numbers (refit timestamp comes from M3_SUMMARY).
    m3_meta = {}
    if M3_SUMMARY.exists():
        try:
            m3_meta = json.loads(M3_SUMMARY.read_text())
        except Exception:
            pass
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
        protocol=dict(
            m1_loco_starts=int(M1_STARTS),
            m2_loco_starts=int(n_m2_starts),
            m3_source=str(M3_CSV.relative_to(PROJECT_ROOT)),
            m3_refit_timestamp=m3_meta.get("run_meta", {}).get("timestamp"),
            m3_n_curves=m3_meta.get("n", None),
        ),
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
