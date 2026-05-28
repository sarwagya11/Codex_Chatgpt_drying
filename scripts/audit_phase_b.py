"""
Phase B audit: are the M1 and M2 LOCO fits reproducible?

A model is only publishable if its claimed parameters are at the *global*
minimum of the LS objective on the given data, not at a local minimum
that happens to be near the chosen P0. We check this by re-fitting the
full-data model from many random starts and asserting the converged
parameter set and RMSE collapse to a single point.

Protocol (uniform across M1 and M2 to keep the comparison apples-to-apples):
  - 1 nominal (literature-prior) start + 49 uniform-random starts in bounds
  - Single-stage NLS on raw PAVA-cleaned MR(t) (matches live model and
    Phase E protocol)
  - Reproducibility = bool(RMSE_range < 1e-4) at the model's own RMSE scale
  - Reports n_at_best (within 1e-4 of best) and per-parameter spread among
    the near-best subset.

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

N_STARTS = 50
SEED = 42
RMSE_TOL = 1e-4


def _verdict(df: pd.DataFrame, p_cols, rmse_tol: float = RMSE_TOL):
    best = df["rmse_full"].min()
    near_best = df[df["rmse_full"] - best < rmse_tol]
    spread = {}
    for col in p_cols:
        vals = near_best[col].values
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        spread[col] = dict(
            mean=mean, std=std,
            rel_spread=float(std / abs(mean)) if mean != 0 else float(std),
        )
    return dict(
        rmse_min=float(best),
        rmse_max=float(df["rmse_full"].max()),
        rmse_range=float(df["rmse_full"].max() - df["rmse_full"].min()),
        n_starts=int(len(df)),
        n_at_best=int(len(near_best)),
        n_failed_to_converge=int((df["rmse_full"] - best >= rmse_tol).sum()),
        fraction_at_best=float(len(near_best) / max(1, len(df))),
        reproducible=bool(df["rmse_full"].max() - best < rmse_tol),
        param_spread=spread,
    )


def main():
    curves = load_curves(TARGETS_CSV, DATA_DIR)
    rng = np.random.default_rng(seed=SEED)
    print(f"Loaded {len(curves)} curves. Running {N_STARTS} starts per model "
          f"(1 nominal + {N_STARTS - 1} random) ...")

    # ---- M1 (single-stage NLS on raw MR; convex by construction) ----
    rows_m1 = []
    starts_m1 = [M1_NOM] + [rng.uniform(M1_LO, M1_HI) for _ in range(N_STARTS - 1)]
    for i, p0 in enumerate(starts_m1):
        try:
            sol = fit_m1(curves, p0)
            rmse_v = rmse_full(curves,
                               lambda c, p: m1_predict(c["t"], c["T_C"], c["RH_pct"],
                                                        c["v_ms"], c["d_mm"], p),
                               sol.x)
            rows_m1.append(dict(
                start_id=i, success=bool(sol.success),
                cost=float(sol.cost), rmse_full=float(rmse_v),
                logK_ref=float(sol.x[0]), Ea_over_R=float(sol.x[1]),
                alpha_RH=float(sol.x[2]), gamma_v=float(sol.x[3]),
                delta_d=float(sol.x[4]),
            ))
        except Exception as exc:
            rows_m1.append(dict(
                start_id=i, success=False, cost=float("nan"),
                rmse_full=float("nan"), logK_ref=float("nan"),
                Ea_over_R=float("nan"), alpha_RH=float("nan"),
                gamma_v=float("nan"), delta_d=float("nan"),
                error=str(exc),
            ))
        if (i + 1) % 10 == 0:
            print(f"  M1 start {i+1:3d}/{N_STARTS}  rmse={rows_m1[-1]['rmse_full']:.6f}")
    df_m1 = pd.DataFrame(rows_m1)
    df_m1.to_csv(OUT_DIR / "phase_b_m1_starts.csv", index=False, float_format="%.8g")

    # ---- M2 (single-stage NLS on raw MR; non-convex) ----
    rows_m2 = []
    starts_m2 = [M2_NOM] + [rng.uniform(M2_LO, M2_HI) for _ in range(N_STARTS - 1)]
    for i, p0 in enumerate(starts_m2):
        try:
            sol = fit_m2_one(curves, p0)
            rmse_v = rmse_full(curves,
                               lambda c, p: m2_predict(c["t"], c["T_C"], c["v_ms"],
                                                        c["RH_pct"], p),
                               sol.x)
            rows_m2.append(dict(
                start_id=i, success=bool(sol.success),
                cost=float(sol.cost), rmse_full=float(rmse_v),
                logA=float(sol.x[0]), Ea_J_per_mol=float(sol.x[1]),
                n0=float(sol.x[2]), n_T=float(sol.x[3]),
                n_v=float(sol.x[4]), b0=float(sol.x[5]),
                b_RH=float(sol.x[6]),
            ))
        except Exception as exc:
            rows_m2.append(dict(
                start_id=i, success=False, cost=float("nan"),
                rmse_full=float("nan"),
                logA=float("nan"), Ea_J_per_mol=float("nan"),
                n0=float("nan"), n_T=float("nan"), n_v=float("nan"),
                b0=float("nan"), b_RH=float("nan"),
                error=str(exc),
            ))
        if (i + 1) % 10 == 0:
            print(f"  M2 start {i+1:3d}/{N_STARTS}  rmse={rows_m2[-1]['rmse_full']:.6f}")
    df_m2 = pd.DataFrame(rows_m2)
    df_m2.to_csv(OUT_DIR / "phase_b_m2_starts.csv", index=False, float_format="%.8g")

    m1_v = _verdict(df_m1.dropna(subset=["rmse_full"]),
                    ["logK_ref", "Ea_over_R", "alpha_RH", "gamma_v", "delta_d"])
    m2_v = _verdict(df_m2.dropna(subset=["rmse_full"]),
                    ["logA", "Ea_J_per_mol", "n0", "n_T", "n_v", "b0", "b_RH"])

    # Recommended multi-start budget for M2 LOCO (Phase C):
    # if X/N starts fail, P(all k fail) = (X/N)^k. We want P_fail <= 1%.
    p_fail_m2 = 1.0 - m2_v["fraction_at_best"]
    if 0.0 < p_fail_m2 < 1.0:
        rec_starts = int(np.ceil(np.log(0.01) / np.log(p_fail_m2)))
    else:
        rec_starts = 1
    rec_starts = max(rec_starts, 1)

    summary = dict(
        n_curves=len(curves),
        n_starts=N_STARTS,
        seed=SEED,
        rmse_tol=RMSE_TOL,
        M1=m1_v,
        M2=m2_v,
        recommended_M2_loco_starts_for_p_fail_le_0_01=rec_starts,
    )
    (OUT_DIR / "phase_b_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 78)
    print("Phase B  multi-start fit reproducibility")
    print("=" * 78)
    for name, v in [("M1", m1_v), ("M2", m2_v)]:
        print(f"\n{name}:  best RMSE = {v['rmse_min']:.6f}  "
              f"max RMSE = {v['rmse_max']:.6f}  "
              f"range = {v['rmse_range']:.2e}  "
              f"reproducible = {v['reproducible']}")
        print(f"  {v['n_starts']} starts; {v['n_at_best']} within {RMSE_TOL:g} of best "
              f"({100 * v['fraction_at_best']:.1f}%)")
    print(f"\nRecommended M2 LOCO multi-start budget for P(fail)<=1%: {rec_starts}")
    print(f"\nWrote {OUT_DIR / 'phase_b_summary.json'}")


if __name__ == "__main__":
    main()
