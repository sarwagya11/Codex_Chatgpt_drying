"""
Phase 6 / Study 2 -- Arrhenius single-segment Midilli baseline + LOCO-CV.

Model:
  MR(t) = exp(-k(T) * t^n) + b * t
  k(T) = A * exp(-Ea / (R * T_K))         (Arrhenius)
  n    = n0 + n_T * (T - 50) + n_v * (v - 1.1)
  b    = b0 + b_RH * (RH - 42.5)

Training:
  Pool all 13 raw curves, fit (A, Ea, n0, n_T, n_v, b0, b_RH) globally with
  least-squares on stacked MR(t) residuals.

LOCO-CV:
  For each held-out condition, refit globally on the remaining 12 curves,
  evaluate the predicted MR(t) on the held-out raw time grid, score same
  metrics as Study 1.

Outputs:
  outputs/baseline/diagnostics/loco_cv_baseline.csv
  outputs/baseline/diagnostics/loco_cv_baseline_summary.json
  outputs/baseline/diagnostics/global_fit.json    (full-data fit for reference)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "outputs" / "baseline" / "diagnostics"
PRED_DIR = OUT_DIR / "loco_cv_predictions"

R_GAS = 8.314  # J/mol/K

# Reference centring (matches median of dataset)
T_REF_C = 50.0
V_REF = 1.1
RH_REF = 42.5

# Param vector layout: [logA, Ea, n0, n_T, n_v, b0, b_RH]
P0 = np.array([np.log(0.005), 25_000.0, 1.10, 0.0, 0.0, -1e-4, -5e-6])
P_LO = np.array([np.log(1e-8), 0.0,     0.5, -0.05, -0.5,  -2e-3, -5e-4])
P_HI = np.array([np.log(10.0), 200_000.0, 2.5, 0.05,  0.5,   2e-3,  5e-4])


def load_raw_mr(dataset: str) -> Tuple[np.ndarray, np.ndarray]:
    path = DATA_DIR / f"{dataset}.csv"
    df = pd.read_csv(path)
    time = df["time_min"].astype(float).to_numpy()
    x = df["X_db"].astype(float).to_numpy()
    mr = np.clip(x / x[0], 0.0, 1.1)
    order = np.argsort(time)
    time_s = time[order]
    mr_s = mr[order].astype(float)
    # Pool-adjacent-violators monotone decreasing
    blocks: List[Tuple[float, int]] = []
    for v in mr_s:
        blocks.append((float(v), 1))
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            (a, ca), (b, cb) = blocks[-2], blocks[-1]
            blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
    iso = np.empty_like(mr_s)
    i = 0
    for value, count in blocks:
        iso[i:i + count] = value
        i += count
    return time_s, iso


def predict_mr(
    t: np.ndarray, T_C: float, v_ms: float, RH_pct: float, p: np.ndarray
) -> np.ndarray:
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA)
    T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = n0 + n_T * (T_C - T_REF_C) + n_v * (v_ms - V_REF)
    n = max(0.2, min(2.5, n))
    b = b0 + b_RH * (RH_pct - RH_REF)
    safe_t = np.maximum(t, 0.0)
    return np.clip(np.exp(-k * np.power(safe_t, n)) + b * safe_t, 0.0, 1.1)


def fit_global(curves: List[Dict]) -> np.ndarray:
    """Least-squares fit of (logA, Ea, n0, n_T, n_v, b0, b_RH) over pooled curves."""

    def residuals(p):
        out = []
        for c in curves:
            mr_p = predict_mr(c["t"], c["T_C"], c["v_ms"], c["RH_pct"], p)
            out.append(mr_p - c["mr"])
        return np.concatenate(out)

    res = least_squares(
        residuals, P0, bounds=(P_LO, P_HI),
        method="trf", max_nfev=20000, xtol=1e-12, ftol=1e-12,
    )
    return res.x


def metrics_mr(actual: np.ndarray, pred: np.ndarray, n_params: int = 7) -> Dict[str, float]:
    mask = np.isfinite(actual) & np.isfinite(pred)
    a = actual[mask]
    p = pred[mask]
    if a.size == 0:
        return dict(rmse=float("nan"), r2=float("nan"), mbe=float("nan"),
                    chi2_red=float("nan"), ef=float("nan"))
    res = a - p
    sse = float(np.sum(res * res))
    sst = float(np.sum((a - a.mean()) ** 2))
    rmse = float(np.sqrt(sse / a.size))
    r2 = 1.0 - sse / sst if sst > 0 else float("nan")
    mbe = float(np.mean(res))
    dof = max(a.size - n_params, 1)
    chi2_red = sse / dof
    return dict(rmse=rmse, r2=r2, mbe=mbe, chi2_red=chi2_red, ef=r2)


def time_at_mr(time_min: np.ndarray, mr: np.ndarray, target: float = 0.1) -> float:
    if mr[0] < target:
        return float(time_min[0])
    if mr[-1] > target:
        return float("nan")
    for i in range(1, len(mr)):
        if mr[i] <= target:
            t1, t2 = time_min[i - 1], time_min[i]
            m1, m2 = mr[i - 1], mr[i]
            if m1 == m2:
                return float(t1)
            return float(t1 + (target - m1) * (t2 - t1) / (m2 - m1))
    return float("nan")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(TARGETS_CSV)
    df = df.copy()

    # Cache raw curves
    curves: List[Dict] = []
    for _, row in df.iterrows():
        ds = str(row["dataset"])
        t, mr = load_raw_mr(ds)
        curves.append(dict(
            dataset=ds, t=t, mr=mr,
            T_C=float(row["T_C"]), v_ms=float(row["v_ms"]),
            RH_pct=float(row["RH_mid_pct"]),
        ))

    # Reference fit on all data (for paper / sanity)
    p_full = fit_global(curves)
    full_meta = {
        "logA": float(p_full[0]), "A_per_min_n": float(np.exp(p_full[0])),
        "Ea_J_per_mol": float(p_full[1]),
        "Ea_over_R": float(p_full[1] / R_GAS),
        "n0": float(p_full[2]), "n_T": float(p_full[3]), "n_v": float(p_full[4]),
        "b0": float(p_full[5]), "b_RH": float(p_full[6]),
        "T_ref_C": T_REF_C, "v_ref_ms": V_REF, "RH_ref_pct": RH_REF,
    }
    (OUT_DIR / "global_fit.json").write_text(json.dumps(full_meta, indent=2))

    # LOCO-CV
    rows = []
    for i, target in enumerate(curves):
        train = [c for j, c in enumerate(curves) if j != i]
        p_loco = fit_global(train)
        mr_pred = predict_mr(target["t"], target["T_C"], target["v_ms"], target["RH_pct"], p_loco)
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

        print(f"[{i+1:2d}/{len(curves)}] {target['dataset']:30s} RMSE={m['rmse']:.4f} "
              f"R2={m['r2']:.4f} MBE={m['mbe']:+.4f} t10%_relerr={t_rel:.3f}")

        rows.append(dict(
            dataset=target["dataset"], rmse_mr=m["rmse"], r2=m["r2"], mbe=m["mbe"],
            chi2_red=m["chi2_red"], ef=m["ef"],
            t_at_MR0p1_actual=t_actual, t_at_MR0p1_pred=t_pred, t_at_MR0p1_rel_err=t_rel,
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
    print(f"RMSE_MR  mean={summary['rmse_mr_mean']:.4f}  std={summary['rmse_mr_std']:.4f}  max={summary['rmse_mr_max']:.4f}")
    print(f"R^2      mean={summary['r2_mean']:.4f}  min={summary['r2_min']:.4f}")
    print(f"MBE      mean={summary['mbe_mean']:+.4f}")
    print(f"t@MR=0.1 mean rel-err={summary['t_at_MR0p1_rel_err_mean']:.3f}  max={summary['t_at_MR0p1_rel_err_max']:.3f}")
    print(f"Folds passing RMSE<0.025 : {summary['n_pass_rmse_lt_0p025']}/{summary['n_folds']}")
    print(f"Folds passing R^2>0.99   : {summary['n_pass_r2_gt_0p99']}/{summary['n_folds']}")
    print(f"\nGlobal fit (full data):")
    print(f"  Ea/R = {full_meta['Ea_over_R']:.1f} K   (was 2711 K in dryer_solar_hp.py)")
    print(f"  A    = {full_meta['A_per_min_n']:.4g} min^-n")
    print(f"  n0={full_meta['n0']:.3f}  n_T={full_meta['n_T']:.4f}  n_v={full_meta['n_v']:.4f}")
    print(f"  b0={full_meta['b0']:.4g}  b_RH={full_meta['b_RH']:.4g}")
    print(f"\nResults : {OUT_DIR / 'loco_cv_baseline.csv'}")
    print(f"Summary : {OUT_DIR / 'loco_cv_baseline_summary.json'}")


if __name__ == "__main__":
    main()
