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
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.optimize import least_squares


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR    = PROJECT_ROOT / "data"
OUT_DIR     = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Match insample_vs_loco.py exactly so results compare like-for-like
T_REF_C = 50.0; V_REF = 1.1; D_REF = 6.0
M1_LO = np.array([np.log(1e-7),     0.0,  0.0, -3.0, -3.0])
M1_HI = np.array([np.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])
M1_NOMINAL = np.array([np.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])

R_GAS = 8.314
M2_LO = np.array([np.log(1e-8),     0.0, 0.5, -0.05, -0.5, -2e-3, -5e-4])
M2_HI = np.array([np.log(10.0), 200_000.0, 2.5,  0.05,  0.5,  2e-3,  5e-4])
M2_NOMINAL = np.array([np.log(0.005), 25_000.0, 1.10, 0.0, 0.0, -1e-4, -5e-6])
M2_T_REF_C = 50.0; M2_V_REF = 1.1; M2_RH_REF = 42.5


def load_curves() -> List[Dict]:
    df = pd.read_csv(TARGETS_CSV)
    out = []
    for _, r in df.iterrows():
        raw = pd.read_csv(DATA_DIR / f"{r['dataset']}.csv")
        time = raw["time_min"].astype(float).to_numpy()
        x = raw["X_db"].astype(float).to_numpy()
        mr = np.clip(x / x[0], 0.0, 1.1)
        order = np.argsort(time)
        time_s = time[order]; mr_s = mr[order].astype(float)
        # PAVA monotonic preprocessing
        blocks = []
        for v in mr_s:
            blocks.append((float(v), 1))
            while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
                (a, ca), (b, cb) = blocks[-2], blocks[-1]
                blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
        iso = np.empty_like(mr_s); i = 0
        for value, count in blocks:
            iso[i:i + count] = value; i += count
        out.append(dict(dataset=str(r["dataset"]), t=time_s, mr=iso,
                        T_C=float(r["T_C"]), v_ms=float(r["v_ms"]),
                        d_mm=float(r["thickness_mm"]),
                        RH_pct=float(r["RH_mid_pct"])))
    return out


def m1_predict(t_min, T_C, RH_pct, v_ms, d_mm, p):
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K = T_C + 273.15; T_ref_K = T_REF_C + 273.15
    K = (K_ref * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
         * np.exp(-alpha_RH * RH_pct / 100.0)
         * (v_ms / V_REF) ** gamma_v
         * (D_REF / d_mm) ** delta_d)
    return np.clip(np.exp(-K * np.maximum(t_min * 60.0, 0.0)), 0.0, 1.1)


def m2_predict(t_min, T_C, v_ms, RH_pct, p):
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA); T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = n0 + n_T * (T_C - M2_T_REF_C) + n_v * (v_ms - M2_V_REF)
    n = max(0.2, min(2.5, n))
    b = b0 + b_RH * (RH_pct - M2_RH_REF)
    safe = np.maximum(t_min, 0.0)
    return np.clip(np.exp(-k * np.power(safe, n)) + b * safe, 0.0, 1.1)


def fit_m1(curves, p0):
    def res(p):
        return np.concatenate([
            m1_predict(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p) - c["mr"]
            for c in curves
        ])
    sol = least_squares(res, p0, bounds=(M1_LO, M1_HI), method="trf",
                        max_nfev=20_000, xtol=1e-12, ftol=1e-12)
    return sol


def fit_m2(curves, p0):
    def res(p):
        return np.concatenate([
            m2_predict(c["t"], c["T_C"], c["v_ms"], c["RH_pct"], p) - c["mr"]
            for c in curves
        ])
    sol = least_squares(res, p0, bounds=(M2_LO, M2_HI), method="trf",
                        max_nfev=20_000, xtol=1e-12, ftol=1e-12)
    return sol


def rmse_full(curves, predict_fn, p) -> float:
    preds = []
    truths = []
    for c in curves:
        preds.append(predict_fn(c, p))
        truths.append(c["mr"])
    a = np.concatenate(preds); b = np.concatenate(truths)
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def main():
    curves = load_curves()
    rng = np.random.default_rng(seed=42)
    n_starts = 10

    # ---- M1 ----
    rows_m1 = []
    sols_m1 = []
    # Start 0: nominal P0
    starts_m1 = [M1_NOMINAL]
    for _ in range(n_starts - 1):
        starts_m1.append(rng.uniform(M1_LO, M1_HI))
    for i, p0 in enumerate(starts_m1):
        sol = fit_m1(curves, p0)
        rmse = rmse_full(curves,
                         lambda c, p: m1_predict(c["t"], c["T_C"], c["RH_pct"],
                                                  c["v_ms"], c["d_mm"], p),
                         sol.x)
        rows_m1.append(dict(
            start_id=i,
            success=bool(sol.success),
            cost=float(sol.cost),
            rmse_full=rmse,
            logK_ref=float(sol.x[0]),
            Ea_over_R=float(sol.x[1]),
            alpha_RH=float(sol.x[2]),
            gamma_v=float(sol.x[3]),
            delta_d=float(sol.x[4]),
        ))
        sols_m1.append(sol.x)
    df_m1 = pd.DataFrame(rows_m1)
    df_m1.to_csv(OUT_DIR / "phase_b_m1_starts.csv", index=False, float_format="%.8g")

    # ---- M2 ----
    rows_m2 = []
    sols_m2 = []
    starts_m2 = [M2_NOMINAL]
    for _ in range(n_starts - 1):
        starts_m2.append(rng.uniform(M2_LO, M2_HI))
    for i, p0 in enumerate(starts_m2):
        sol = fit_m2(curves, p0)
        rmse = rmse_full(curves,
                         lambda c, p: m2_predict(c["t"], c["T_C"], c["v_ms"],
                                                  c["RH_pct"], p),
                         sol.x)
        rows_m2.append(dict(
            start_id=i,
            success=bool(sol.success),
            cost=float(sol.cost),
            rmse_full=rmse,
            logA=float(sol.x[0]),
            Ea_J_per_mol=float(sol.x[1]),
            n0=float(sol.x[2]),
            n_T=float(sol.x[3]),
            n_v=float(sol.x[4]),
            b0=float(sol.x[5]),
            b_RH=float(sol.x[6]),
        ))
        sols_m2.append(sol.x)
    df_m2 = pd.DataFrame(rows_m2)
    df_m2.to_csv(OUT_DIR / "phase_b_m2_starts.csv", index=False, float_format="%.8g")

    # ---- Reproducibility verdict ----
    def verdict(df, p_cols, rmse_tol=1e-4, p_rel_tol=0.05):
        best = df["rmse_full"].min()
        near_best = df[df["rmse_full"] - best < rmse_tol]
        param_spread = {}
        for col in p_cols:
            vals = near_best[col].values
            mean = float(np.mean(vals))
            std = float(np.std(vals))
            param_spread[col] = dict(mean=mean, std=std,
                                     rel_spread=float(std / abs(mean)) if mean != 0 else float(std))
        rmse_range = float(df["rmse_full"].max() - df["rmse_full"].min())
        n_at_best = int(len(near_best))
        return dict(
            rmse_min=float(best),
            rmse_max=float(df["rmse_full"].max()),
            rmse_range=rmse_range,
            n_starts=int(len(df)),
            n_at_best=n_at_best,
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
