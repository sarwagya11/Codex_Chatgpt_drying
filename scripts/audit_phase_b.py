"""
Phase B audit: are the M1 and M2 LOCO fits reproducible?

A model is only publishable if its claimed parameters are at the *global*
minimum of the LS objective on the given data, not at a local minimum
that happens to be near the chosen P0. We check this by re-fitting the
full-data model from many random starts and asserting the converged
parameter set and RMSE collapse to a single point.

For each of M1 and M2:
  - sample 10 random starting points uniformly in the parameter bounds
  - fit on all 13 curves
  - record converged parameters and RMSE_MR
  - flag as 'reproducible' if all converged RMSEs lie within 1e-4 of the
    minimum and the parameter spread is below a tolerance.

Outputs:
  outputs/audit/phase_b_m1_starts.csv
  outputs/audit/phase_b_m2_starts.csv
  outputs/audit/phase_b_summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from _kinetics_common import (
    M1_HI, M1_LO, M1_NOM,
    M2_HI, M2_LO, M2_NOM,
    fit_m1, fit_m2_one, load_curves, m1_predict, m2_predict, rmse_full,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    curves = load_curves(TARGETS_CSV, DATA_DIR)
    rng = np.random.default_rng(seed=42)
    n_starts = 10

    # ---- M1 ----
    rows_m1 = []
    starts_m1 = [M1_NOM] + [rng.uniform(M1_LO, M1_HI) for _ in range(n_starts - 1)]
    for i, p0 in enumerate(starts_m1):
        sol = fit_m1(curves, p0)
        rmse_v = rmse_full(curves,
                           lambda c, p: m1_predict(c["t"], c["T_C"], c["RH_pct"],
                                                    c["v_ms"], c["d_mm"], p),
                           sol.x)
        rows_m1.append(dict(
            start_id=i,
            success=bool(sol.success),
            cost=float(sol.cost),
            rmse_full=rmse_v,
            logK_ref=float(sol.x[0]),
            Ea_over_R=float(sol.x[1]),
            alpha_RH=float(sol.x[2]),
            gamma_v=float(sol.x[3]),
            delta_d=float(sol.x[4]),
        ))
    df_m1 = pd.DataFrame(rows_m1)
    df_m1.to_csv(OUT_DIR / "phase_b_m1_starts.csv", index=False, float_format="%.8g")

    # ---- M2 ----
    rows_m2 = []
    starts_m2 = [M2_NOM] + [rng.uniform(M2_LO, M2_HI) for _ in range(n_starts - 1)]
    for i, p0 in enumerate(starts_m2):
        sol = fit_m2_one(curves, p0)
        rmse_v = rmse_full(curves,
                           lambda c, p: m2_predict(c["t"], c["T_C"], c["v_ms"],
                                                    c["RH_pct"], p),
                           sol.x)
        rows_m2.append(dict(
            start_id=i,
            success=bool(sol.success),
            cost=float(sol.cost),
            rmse_full=rmse_v,
            logA=float(sol.x[0]),
            Ea_J_per_mol=float(sol.x[1]),
            n0=float(sol.x[2]),
            n_T=float(sol.x[3]),
            n_v=float(sol.x[4]),
            b0=float(sol.x[5]),
            b_RH=float(sol.x[6]),
        ))
    df_m2 = pd.DataFrame(rows_m2)
    df_m2.to_csv(OUT_DIR / "phase_b_m2_starts.csv", index=False, float_format="%.8g")

    # ---- Reproducibility verdict ----
    def verdict(df, p_cols, rmse_tol=1e-4):
        best = df["rmse_full"].min()
        near_best = df[df["rmse_full"] - best < rmse_tol]
        param_spread = {}
        for col in p_cols:
            vals = near_best[col].values
            mean = float(np.mean(vals))
            std = float(np.std(vals))
            param_spread[col] = dict(
                mean=mean, std=std,
                rel_spread=float(std / abs(mean)) if mean != 0 else float(std),
            )
        rmse_range = float(df["rmse_full"].max() - df["rmse_full"].min())
        return dict(
            rmse_min=float(best),
            rmse_max=float(df["rmse_full"].max()),
            rmse_range=rmse_range,
            n_starts=int(len(df)),
            n_at_best=int(len(near_best)),
            reproducible=bool(rmse_range < rmse_tol),
            param_spread=param_spread,
        )

    m1_v = verdict(df_m1, ["logK_ref", "Ea_over_R", "alpha_RH", "gamma_v", "delta_d"])
    m2_v = verdict(df_m2, ["logA", "Ea_J_per_mol", "n0", "n_T", "n_v", "b0", "b_RH"])

    summary = dict(
        n_curves=len(curves),
        n_starts=n_starts,
        seed=42,
        M1=m1_v,
        M2=m2_v,
    )
    (OUT_DIR / "phase_b_summary.json").write_text(json.dumps(summary, indent=2))

    print("=" * 78)
    print("Phase B - multi-start LOCO-fit reproducibility")
    print("=" * 78)
    for name, v, df in [("M1", m1_v, df_m1), ("M2", m2_v, df_m2)]:
        print(f"\n{name}:  best RMSE = {v['rmse_min']:.6f}  "
              f"max RMSE = {v['rmse_max']:.6f}  "
              f"range = {v['rmse_range']:.2e}  "
              f"reproducible = {v['reproducible']}")
        print(f"  {df.shape[0]} starts; {v['n_at_best']} converged within 1e-4 of best")

    print(f"\nWrote {OUT_DIR / 'phase_b_summary.json'}")


if __name__ == "__main__":
    main()
