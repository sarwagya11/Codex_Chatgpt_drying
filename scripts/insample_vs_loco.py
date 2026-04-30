"""
In-sample vs LOCO RMSE_MR for M1 and M2.

For each model:
  - In-sample RMSE: refit on all 13 curves, predict each curve, compute RMSE.
  - LOCO RMSE: read from saved per-fold CSVs.

If in-sample << LOCO, the limitation is small-sample extrapolation, not model capacity.
If in-sample ~ LOCO, the model has hit its capacity ceiling and richer models would
not help on this dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV  = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR     = PROJECT_ROOT / "data"
M1_CSV       = PROJECT_ROOT / "outputs" / "m1_loco_cv" / "loco_cv_m1.csv"
M2_CSV       = PROJECT_ROOT / "outputs" / "baseline"   / "diagnostics" / "loco_cv_baseline.csv"
OUT_DIR      = PROJECT_ROOT / "outputs" / "m1_loco_cv"

# --- M1 ---
T_REF_C = 50.0; V_REF = 1.1; D_REF = 6.0
M1_P0 = np.array([np.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])
M1_LO = np.array([np.log(1e-7),     0.0, 0.0,  -3.0, -3.0])
M1_HI = np.array([np.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])

# --- M2 (mirrors baseline_arrhenius_midilli.py) ---
R_GAS = 8.314
M2_P0 = np.array([np.log(0.005), 25_000.0, 1.10, 0.0, 0.0, -1e-4, -5e-6])
M2_LO = np.array([np.log(1e-8), 0.0,     0.5, -0.05, -0.5,  -2e-3, -5e-4])
M2_HI = np.array([np.log(10.0), 200_000.0, 2.5, 0.05,  0.5,   2e-3,  5e-4])
M2_T_REF_C = 50.0; M2_V_REF = 1.1; M2_RH_REF = 42.5


def load_raw_mr(dataset: str) -> Tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(DATA_DIR / f"{dataset}.csv")
    time = df["time_min"].astype(float).to_numpy()
    x = df["X_db"].astype(float).to_numpy()
    mr = np.clip(x / x[0], 0.0, 1.1)
    order = np.argsort(time)
    time_s = time[order]; mr_s = mr[order].astype(float)
    blocks: List[Tuple[float, int]] = []
    for v in mr_s:
        blocks.append((float(v), 1))
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            (a, ca), (b, cb) = blocks[-2], blocks[-1]
            blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
    iso = np.empty_like(mr_s); i = 0
    for value, count in blocks:
        iso[i:i + count] = value; i += count
    return time_s, iso


def m1_predict(t_min, T_C, RH_pct, v_ms, d_mm, p):
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K = T_C + 273.15; T_ref_K = T_REF_C + 273.15
    K = (K_ref * np.exp(EaR * (1.0/T_ref_K - 1.0/T_K))
         * np.exp(-alpha_RH * RH_pct/100.0)
         * (v_ms / V_REF) ** gamma_v
         * (D_REF / d_mm) ** delta_d)
    return np.clip(np.exp(-K * np.maximum(t_min*60.0, 0.0)), 0.0, 1.1)


def m2_predict(t_min, T_C, v_ms, RH_pct, p):
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA); T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = n0 + n_T * (T_C - M2_T_REF_C) + n_v * (v_ms - M2_V_REF)
    n = max(0.2, min(2.5, n))
    b = b0 + b_RH * (RH_pct - M2_RH_REF)
    safe = np.maximum(t_min, 0.0)
    return np.clip(np.exp(-k * np.power(safe, n)) + b * safe, 0.0, 1.1)


def fit_m1(curves):
    def res(p):
        out = []
        for c in curves:
            out.append(m1_predict(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p) - c["mr"])
        return np.concatenate(out)
    return least_squares(res, M1_P0, bounds=(M1_LO, M1_HI), method="trf",
                         max_nfev=20_000, xtol=1e-12, ftol=1e-12).x


def fit_m2(curves):
    def res(p):
        out = []
        for c in curves:
            out.append(m2_predict(c["t"], c["T_C"], c["v_ms"], c["RH_pct"], p) - c["mr"])
        return np.concatenate(out)
    return least_squares(res, M2_P0, bounds=(M2_LO, M2_HI), method="trf",
                         max_nfev=20_000, xtol=1e-12, ftol=1e-12).x


def rmse(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.sqrt(np.mean((a[m] - b[m])**2)))


def main():
    df = pd.read_csv(TARGETS_CSV)
    curves = []
    for _, r in df.iterrows():
        t, mr = load_raw_mr(str(r["dataset"]))
        curves.append(dict(dataset=str(r["dataset"]), t=t, mr=mr,
                           T_C=float(r["T_C"]), v_ms=float(r["v_ms"]),
                           d_mm=float(r["thickness_mm"]),
                           RH_pct=float(r["RH_mid_pct"])))

    p_m1 = fit_m1(curves)
    p_m2 = fit_m2(curves)

    rows = []
    for c in curves:
        m1_in = m1_predict(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p_m1)
        m2_in = m2_predict(c["t"], c["T_C"], c["v_ms"], c["RH_pct"], p_m2)
        rows.append(dict(
            dataset=c["dataset"],
            m1_insample_rmse=rmse(c["mr"], m1_in),
            m2_insample_rmse=rmse(c["mr"], m2_in),
        ))
    insample = pd.DataFrame(rows)

    m1_loco = pd.read_csv(M1_CSV)[["dataset", "rmse_mr"]].rename(columns={"rmse_mr": "m1_loco_rmse"})
    m2_loco = pd.read_csv(M2_CSV)[["dataset", "rmse_mr"]].rename(columns={"rmse_mr": "m2_loco_rmse"})

    merged = insample.merge(m1_loco, on="dataset").merge(m2_loco, on="dataset")
    merged["m1_gap"] = merged["m1_loco_rmse"] - merged["m1_insample_rmse"]
    merged["m2_gap"] = merged["m2_loco_rmse"] - merged["m2_insample_rmse"]

    merged.to_csv(OUT_DIR / "insample_vs_loco.csv", index=False, float_format="%.6g")

    print("=" * 92)
    print(f"{'dataset':30s}  {'M1_in':>7s}  {'M1_loco':>8s}  {'gap':>7s}    {'M2_in':>7s}  {'M2_loco':>8s}  {'gap':>7s}")
    print("=" * 92)
    for _, r in merged.iterrows():
        print(f"{r['dataset']:30s}  {r['m1_insample_rmse']:7.4f}  {r['m1_loco_rmse']:8.4f}  "
              f"{r['m1_gap']:+7.4f}    {r['m2_insample_rmse']:7.4f}  {r['m2_loco_rmse']:8.4f}  "
              f"{r['m2_gap']:+7.4f}")
    print("-" * 92)
    print(f"{'MEAN':30s}  {merged['m1_insample_rmse'].mean():7.4f}  "
          f"{merged['m1_loco_rmse'].mean():8.4f}  {merged['m1_gap'].mean():+7.4f}    "
          f"{merged['m2_insample_rmse'].mean():7.4f}  {merged['m2_loco_rmse'].mean():8.4f}  "
          f"{merged['m2_gap'].mean():+7.4f}")
    print()
    print("Interpretation:")
    print(f"  Small in-sample / large LOCO  =>  small-sample extrapolation penalty (more data would help).")
    print(f"  In-sample ~ LOCO              =>  model-capacity ceiling on this dataset.")


if __name__ == "__main__":
    main()
