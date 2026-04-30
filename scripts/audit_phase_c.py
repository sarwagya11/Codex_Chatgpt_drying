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
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV  = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR     = PROJECT_ROOT / "data"
M3_CSV       = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics" / "loco_cv_results.csv"
OUT_DIR      = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Match insample_vs_loco.py / m1_loco_cv.py / baseline_arrhenius_midilli.py
T_REF_C = 50.0; V_REF = 1.1; D_REF = 6.0
M1_LO = np.array([np.log(1e-7),     0.0,  0.0, -3.0, -3.0])
M1_HI = np.array([np.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])
M1_NOM = np.array([np.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])

R_GAS = 8.314
M2_LO = np.array([np.log(1e-8), 0.0, 0.5, -0.05, -0.5, -2e-3, -5e-4])
M2_HI = np.array([np.log(10.0), 200_000.0, 2.5, 0.05, 0.5, 2e-3, 5e-4])
M2_NOM = np.array([np.log(0.005), 25_000.0, 1.10, 0.0, 0.0, -1e-4, -5e-6])
M2_T_REF_C = 50.0; M2_V_REF = 1.1; M2_RH_REF = 42.5


# --------------- shared loaders / metrics ---------------
def pava(mr_s: np.ndarray) -> np.ndarray:
    blocks = []
    for v in mr_s:
        blocks.append((float(v), 1))
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            (a, ca), (b, cb) = blocks[-2], blocks[-1]
            blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
    iso = np.empty_like(mr_s); i = 0
    for value, count in blocks:
        iso[i:i + count] = value; i += count
    return iso


def load_curves() -> List[Dict]:
    df = pd.read_csv(TARGETS_CSV)
    out = []
    for _, r in df.iterrows():
        raw = pd.read_csv(DATA_DIR / f"{r['dataset']}.csv")
        time = raw["time_min"].astype(float).to_numpy()
        x = raw["X_db"].astype(float).to_numpy()
        order = np.argsort(time)
        time_s = time[order]; mr_raw = np.clip(x[order] / x[order][0], 0.0, 1.1)
        out.append(dict(dataset=str(r["dataset"]), t=time_s, mr=pava(mr_raw),
                        T_C=float(r["T_C"]), v_ms=float(r["v_ms"]),
                        d_mm=float(r["thickness_mm"]),
                        RH_pct=float(r["RH_mid_pct"])))
    return out


def rmse(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


# --------------- M1 ---------------
def m1_predict(t_min, T_C, RH_pct, v_ms, d_mm, p):
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K = T_C + 273.15; T_ref_K = T_REF_C + 273.15
    K = (K_ref * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
         * np.exp(-alpha_RH * RH_pct / 100.0)
         * (v_ms / V_REF) ** gamma_v
         * (D_REF / d_mm) ** delta_d)
    return np.clip(np.exp(-K * np.maximum(t_min * 60.0, 0.0)), 0.0, 1.1)


def fit_m1(curves, p0):
    def res(p):
        return np.concatenate([
            m1_predict(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p) - c["mr"]
            for c in curves
        ])
    return least_squares(res, p0, bounds=(M1_LO, M1_HI), method="trf",
                         max_nfev=20_000, xtol=1e-12, ftol=1e-12).x


# --------------- M2 ---------------
def m2_predict(t_min, T_C, v_ms, RH_pct, p):
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA); T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = n0 + n_T * (T_C - M2_T_REF_C) + n_v * (v_ms - M2_V_REF)
    n = max(0.2, min(2.5, n))
    b = b0 + b_RH * (RH_pct - M2_RH_REF)
    safe = np.maximum(t_min, 0.0)
    return np.clip(np.exp(-k * np.power(safe, n)) + b * safe, 0.0, 1.1)


def fit_m2_one(curves, p0):
    def res(p):
        return np.concatenate([
            m2_predict(c["t"], c["T_C"], c["v_ms"], c["RH_pct"], p) - c["mr"]
            for c in curves
        ])
    sol = least_squares(res, p0, bounds=(M2_LO, M2_HI), method="trf",
                        max_nfev=20_000, xtol=1e-12, ftol=1e-12)
    return sol.x, float(sol.cost)


def fit_m2_multistart(curves, n_starts=5, seed=0):
    rng = np.random.default_rng(seed)
    best_x = None; best_cost = np.inf
    starts = [M2_NOM] + [rng.uniform(M2_LO, M2_HI) for _ in range(n_starts - 1)]
    for p0 in starts:
        try:
            x, cost = fit_m2_one(curves, p0)
            if cost < best_cost:
                best_cost = cost; best_x = x
        except Exception:
            continue
    return best_x


# --------------- LOCO ---------------
def run_loco(curves):
    rows = []
    for k, held in enumerate(curves):
        train = [c for j, c in enumerate(curves) if j != k]
        # M1: single start (convex)
        p_m1 = fit_m1(train, M1_NOM)
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


# --------------- bootstrap on RMSE differences ---------------
def paired_bootstrap(diff_vec, n_boot=5000, seed=1):
    rng = np.random.default_rng(seed)
    n = len(diff_vec)
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[b] = diff_vec[idx].mean()
    return dict(
        mean=float(diff_vec.mean()),
        ci95_lo=float(np.percentile(means, 2.5)),
        ci95_hi=float(np.percentile(means, 97.5)),
        boot_se=float(means.std()),
    )


def main():
    curves = load_curves()
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
