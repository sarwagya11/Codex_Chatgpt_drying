"""
Phase 6 / Study 7 -- M1 (live SAHPD K_eff) LOCO-CV harness.

Model M1, exactly the form used at runtime by `_fit_parametric_keff` in
RQ1/src/rq1/kinetics.py:
    MR(t) = exp(-K * t)
    K(T, RH, v, d) = K_ref * exp((Ea/R) * (1/T_ref - 1/T_K))
                            * exp(-alpha_RH * RH_frac)
                            * (v / v_ref) ** gamma_v
                            * (d_ref / d) ** delta_d

Difference vs the live fit: the live `_fit_parametric_keff` does a log-linear
OLS on per-curve K_eff values (one number per curve, n=13). For an honest
LOCO-CV comparison with M2 (Arrhenius + Midilli) we have to fit the same
parametric K formula directly on raw MR(t) residuals so the residual space
matches across models.

Parameters: [logK_ref, Ea_over_R_K, alpha_RH, gamma_v, delta_d]   (5 params)

Reference values (centroid of the dataset, also matches live sim defaults):
    T_ref = 50 degC,  v_ref = 1.1 m/s,  d_ref = 6 mm

LOCO-CV: hold out one of the 13 conditions, refit on the remaining 12 with
nonlinear least-squares on stacked MR(t) residuals (PAVA-monotonised, same
preprocessing as M2), score on the held-out raw curve, repeat.

Outputs:
    outputs/m1_loco_cv/loco_cv_m1.csv
    outputs/m1_loco_cv/loco_cv_m1_summary.json
    outputs/m1_loco_cv/global_fit_m1.json    (full-data fit, for reference)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV  = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR     = PROJECT_ROOT / "data"
OUT_DIR      = PROJECT_ROOT / "outputs" / "m1_loco_cv"
PRED_DIR     = OUT_DIR / "loco_cv_predictions"

M2_CSV       = PROJECT_ROOT / "outputs" / "baseline" / "diagnostics" / "loco_cv_baseline.csv"
M3_CSV       = PROJECT_ROOT / "outputs" / "phase2"   / "diagnostics" / "loco_cv_results.csv"

# Reference values
T_REF_C = 50.0
V_REF   = 1.1
D_REF   = 6.0

# Param vector layout: [logK_ref, Ea_over_R_K, alpha_RH, gamma_v, delta_d]
P0  = np.array([np.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])
LO  = np.array([np.log(1e-7),     0.0, 0.0,  -3.0, -3.0])
HI  = np.array([np.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])


def load_raw_mr(dataset: str) -> Tuple[np.ndarray, np.ndarray]:
    """Same preprocessing as the M2 harness: time-sort + PAVA monotone."""
    path = DATA_DIR / f"{dataset}.csv"
    df = pd.read_csv(path)
    time = df["time_min"].astype(float).to_numpy()
    x    = df["X_db"].astype(float).to_numpy()
    mr = np.clip(x / x[0], 0.0, 1.1)
    order = np.argsort(time)
    time_s = time[order]
    mr_s = mr[order].astype(float)
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


def K_of(T_C: float, RH_pct: float, v_ms: float, d_mm: float, p: np.ndarray) -> float:
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K     = T_C + 273.15
    T_ref_K = T_REF_C + 273.15
    RH_frac = RH_pct / 100.0
    K = (
        K_ref
        * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
        * np.exp(-alpha_RH * RH_frac)
        * (v_ms / V_REF) ** gamma_v
        * (D_REF / d_mm) ** delta_d
    )
    return float(K)


def predict_mr(
    t_min: np.ndarray, T_C: float, RH_pct: float, v_ms: float, d_mm: float, p: np.ndarray
) -> np.ndarray:
    """Predict MR(t) for first-order model.  t supplied in minutes (raw curves
    use min); converted to seconds because K is in 1/s."""
    K = K_of(T_C, RH_pct, v_ms, d_mm, p)
    safe_t_s = np.maximum(t_min * 60.0, 0.0)
    return np.clip(np.exp(-K * safe_t_s), 0.0, 1.1)


def fit_global(curves: List[Dict]) -> np.ndarray:
    def residuals(p):
        out = []
        for c in curves:
            mr_p = predict_mr(c["t"], c["T_C"], c["RH_pct"], c["v_ms"], c["d_mm"], p)
            out.append(mr_p - c["mr"])
        return np.concatenate(out)

    res = least_squares(
        residuals, P0, bounds=(LO, HI),
        method="trf", max_nfev=20_000, xtol=1e-12, ftol=1e-12,
    )
    return res.x


def metrics_mr(actual: np.ndarray, pred: np.ndarray, n_params: int = 5) -> Dict[str, float]:
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


def paired_compare(label: str, m1: pd.Series, other: pd.Series) -> Dict[str, float]:
    finite = m1.notna() & other.notna()
    a = m1[finite].to_numpy()
    b = other[finite].to_numpy()
    if len(a) < 3:
        return dict(label=label, n=int(len(a)))
    t = stats.ttest_rel(a, b)
    w = stats.wilcoxon(a, b, zero_method="wilcox")
    delta = a - b
    return dict(
        label=label, n=int(len(a)),
        m1_mean=float(a.mean()), other_mean=float(b.mean()),
        delta_mean=float(delta.mean()),
        t_stat=float(t.statistic), t_p=float(t.pvalue),
        wilcoxon_W=float(w.statistic), wilcoxon_p=float(w.pvalue),
        m1_wins=int((delta < 0).sum()),
        other_wins=int((delta > 0).sum()),
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(TARGETS_CSV)

    curves: List[Dict] = []
    for _, row in df.iterrows():
        ds = str(row["dataset"])
        t, mr = load_raw_mr(ds)
        curves.append(dict(
            dataset=ds, t=t, mr=mr,
            T_C=float(row["T_C"]),
            v_ms=float(row["v_ms"]),
            d_mm=float(row["thickness_mm"]),
            RH_pct=float(row["RH_mid_pct"]),
        ))

    # --- Reference fit on all data (sanity vs the live `_fit_parametric_keff`)
    p_full = fit_global(curves)
    full_meta = {
        "logK_ref":   float(p_full[0]),
        "K_ref_1_per_s": float(np.exp(p_full[0])),
        "Ea_over_R_K":   float(p_full[1]),
        "alpha_RH":      float(p_full[2]),
        "gamma_v":       float(p_full[3]),
        "delta_d":       float(p_full[4]),
        "T_ref_C": T_REF_C, "v_ref_ms": V_REF, "d_ref_mm": D_REF,
        "objective": "least_squares on stacked MR(t) residuals across all 13 curves",
    }
    (OUT_DIR / "global_fit_m1.json").write_text(json.dumps(full_meta, indent=2))

    # --- LOCO-CV
    rows: List[Dict] = []
    for i, target in enumerate(curves):
        train = [c for j, c in enumerate(curves) if j != i]
        p_loco = fit_global(train)
        mr_pred = predict_mr(
            target["t"], target["T_C"], target["RH_pct"],
            target["v_ms"], target["d_mm"], p_loco,
        )
        m = metrics_mr(target["mr"], mr_pred)
        t_actual = time_at_mr(target["t"], target["mr"], 0.1)
        t_pred   = time_at_mr(target["t"], mr_pred,    0.1)
        if np.isfinite(t_actual) and np.isfinite(t_pred) and t_actual > 0:
            t_rel = abs(t_pred - t_actual) / t_actual
        else:
            t_rel = float("nan")

        pd.DataFrame({
            "time_min": target["t"], "mr_actual": target["mr"], "mr_pred": mr_pred,
        }).to_csv(PRED_DIR / f"{target['dataset']}_pred_vs_actual.csv",
                  index=False, float_format="%.9g")

        print(f"[{i+1:2d}/{len(curves)}] {target['dataset']:30s} "
              f"RMSE={m['rmse']:.4f}  R2={m['r2']:.4f}  MBE={m['mbe']:+.4f}  "
              f"t10%_relerr={t_rel:.3f}")

        rows.append(dict(
            dataset=target["dataset"], rmse_mr=m["rmse"], r2=m["r2"], mbe=m["mbe"],
            chi2_red=m["chi2_red"], ef=m["ef"],
            t_at_MR0p1_actual=t_actual, t_at_MR0p1_pred=t_pred,
            t_at_MR0p1_rel_err=t_rel,
            n_obs=int(np.sum(np.isfinite(target["mr"]))),
        ))

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "loco_cv_m1.csv", index=False, float_format="%.9g")

    summary = {
        "model": "M1 (5-param first-order Arrhenius+RH+v+d K_eff)",
        "n_folds": len(rows),
        "n_params": 5,
        "rmse_mr_mean": float(np.nanmean(out["rmse_mr"])),
        "rmse_mr_std":  float(np.nanstd(out["rmse_mr"])),
        "rmse_mr_max":  float(np.nanmax(out["rmse_mr"])),
        "r2_mean":      float(np.nanmean(out["r2"])),
        "r2_min":       float(np.nanmin(out["r2"])),
        "mbe_mean":     float(np.nanmean(out["mbe"])),
        "ef_mean":      float(np.nanmean(out["ef"])),
        "t_at_MR0p1_rel_err_mean": float(np.nanmean(out["t_at_MR0p1_rel_err"])),
        "t_at_MR0p1_rel_err_max":  float(np.nanmax(out["t_at_MR0p1_rel_err"])),
        "n_pass_rmse_lt_0p025": int(np.sum(out["rmse_mr"] < 0.025)),
        "n_pass_r2_gt_0p99":    int(np.sum(out["r2"] > 0.99)),
        "global_fit": full_meta,
    }

    # --- Paired comparisons vs M2 and M3 if those LOCO files exist
    paired = {}
    if M2_CSV.exists():
        m2 = pd.read_csv(M2_CSV)[["dataset", "rmse_mr", "t_at_MR0p1_rel_err"]].rename(
            columns={"rmse_mr": "m2_rmse", "t_at_MR0p1_rel_err": "m2_t_relerr"})
        merged_m2 = out.merge(m2, on="dataset")
        paired["m1_vs_m2_rmse"] = paired_compare(
            "M1 vs M2 (RMSE_MR)", merged_m2["rmse_mr"], merged_m2["m2_rmse"])
        paired["m1_vs_m2_t10pct"] = paired_compare(
            "M1 vs M2 (t@MR=0.1 rel-err)",
            merged_m2["t_at_MR0p1_rel_err"], merged_m2["m2_t_relerr"])
    if M3_CSV.exists():
        m3 = pd.read_csv(M3_CSV)[["dataset", "rmse_mr", "t_at_MR0p1_rel_err"]].rename(
            columns={"rmse_mr": "m3_rmse", "t_at_MR0p1_rel_err": "m3_t_relerr"})
        merged_m3 = out.merge(m3, on="dataset")
        paired["m1_vs_m3_rmse"] = paired_compare(
            "M1 vs M3 (RMSE_MR)", merged_m3["rmse_mr"], merged_m3["m3_rmse"])
        paired["m1_vs_m3_t10pct"] = paired_compare(
            "M1 vs M3 (t@MR=0.1 rel-err)",
            merged_m3["t_at_MR0p1_rel_err"], merged_m3["m3_t_relerr"])
    summary["paired"] = paired

    (OUT_DIR / "loco_cv_m1_summary.json").write_text(json.dumps(summary, indent=2))

    print()
    print("=" * 72)
    print(f"M1 LOCO-CV  (n={summary['n_folds']}, p={summary['n_params']})")
    print("=" * 72)
    print(f"RMSE_MR  mean={summary['rmse_mr_mean']:.4f}  std={summary['rmse_mr_std']:.4f}  max={summary['rmse_mr_max']:.4f}")
    print(f"R^2      mean={summary['r2_mean']:.4f}  min={summary['r2_min']:.4f}")
    print(f"MBE      mean={summary['mbe_mean']:+.4f}")
    print(f"t@MR=0.1 mean rel-err={summary['t_at_MR0p1_rel_err_mean']:.3f}  "
          f"max={summary['t_at_MR0p1_rel_err_max']:.3f}")
    print(f"Folds passing RMSE<0.025 : {summary['n_pass_rmse_lt_0p025']}/{summary['n_folds']}")
    print(f"Folds passing R^2>0.99   : {summary['n_pass_r2_gt_0p99']}/{summary['n_folds']}")
    print()
    print("Global fit (full data):")
    print(f"  K_ref    = {full_meta['K_ref_1_per_s']:.4e} 1/s   (T_ref=50C, RH=0%, v_ref=1.1, d_ref=6mm)")
    print(f"  Ea/R     = {full_meta['Ea_over_R_K']:.1f} K")
    print(f"  alpha_RH = {full_meta['alpha_RH']:.3f}")
    print(f"  gamma_v  = {full_meta['gamma_v']:.3f}")
    print(f"  delta_d  = {full_meta['delta_d']:.3f}")

    if paired:
        print()
        print("=" * 72)
        print("Paired comparisons")
        print("=" * 72)
        for key, p in paired.items():
            if "t_p" not in p:
                print(f"  {p['label']:35s}  n={p['n']}  (insufficient finite pairs)")
                continue
            print(
                f"  {p['label']:35s}  "
                f"M1 mean={p['m1_mean']:.4f}  other mean={p['other_mean']:.4f}  "
                f"delta={p['delta_mean']:+.4f}  "
                f"t-p={p['t_p']:.4g}  W-p={p['wilcoxon_p']:.4g}  "
                f"M1 wins {p['m1_wins']}/{p['n']}"
            )

    print()
    print("Outputs:")
    print(f"  {OUT_DIR / 'loco_cv_m1.csv'}")
    print(f"  {OUT_DIR / 'loco_cv_m1_summary.json'}")
    print(f"  {OUT_DIR / 'global_fit_m1.json'}")


if __name__ == "__main__":
    main()
