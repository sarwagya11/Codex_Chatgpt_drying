"""
Phase E audit: parameter uncertainty + literature comparison.

For both M1 and M2:
  1. Refit the full-data model.
  2. Compute parameter covariance from the LS Jacobian:
        Cov ~ sigma2 * (J^T J)^{-1},   sigma2 = SS_res / (N - p)
     and report standard errors and 95% CIs.
  3. Convert the M1 Ea/R uncertainty into Ea (J/mol) and compare to
     published apple-drying activation energies.
  4. Sample 200 parameter draws from a multivariate normal centred at
     the LS estimate and propagate to K_eff at the design point
     (T=45 C, RH=15%, v=1.1, d=6 mm). Report mean +/- SD of K_eff and
     the implied first-order drying time t63 = 1/K_eff.

Outputs:
  outputs/audit/phase_e_param_ci.csv
  outputs/audit/phase_e_summary.json
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

R_GAS = 8.314

# M1
T_REF_C = 50.0; V_REF = 1.1; D_REF = 6.0
M1_LO = np.array([np.log(1e-7),     0.0,  0.0, -3.0, -3.0])
M1_HI = np.array([np.log(1e-2), 50_000.0, 10.0,  3.0,  3.0])
M1_NOM = np.array([np.log(1.9e-4), 2711.0, 1.75, 0.44, 0.66])
M1_NAMES = ["logK_ref", "Ea_over_R_K", "alpha_RH", "gamma_v", "delta_d"]

# M2
M2_LO = np.array([np.log(1e-8), 0.0, 0.5, -0.05, -0.5, -2e-3, -5e-4])
M2_HI = np.array([np.log(10.0), 200_000.0, 2.5, 0.05, 0.5, 2e-3, 5e-4])
M2_NOM = np.array([np.log(0.005), 25_000.0, 1.10, 0.0, 0.0, -1e-4, -5e-6])
M2_NAMES = ["logA", "Ea_J_per_mol", "n0", "n_T", "n_v", "b0", "b_RH"]
M2_T_REF_C = 50.0; M2_V_REF = 1.1; M2_RH_REF = 42.5

# Literature: apple-drying activation energies (kJ/mol)
LIT_APPLE = [
    # (label, Ea_kJ_per_mol, source)
    ("Sacilik & Elicin 2006",        19.96, "thin-layer apple, Midilli"),
    ("Wang et al. 2007",             24.23, "thin-layer apple, Page"),
    ("Doymaz 2010",                  30.93, "thin-layer apple, Midilli"),
    ("Meisami-asl et al. 2010",      29.26, "thin-layer apple slices"),
    ("Tzempelikos et al. 2014",      27.10, "convective apple drying"),
    ("Kaleta & Gornicki 2010",       22.70, "thin-layer apple, Page"),
]


def pava(mr_s):
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


def load_curves():
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


def _residuals(curves, predict_fn, p):
    out = []
    for c in curves:
        if predict_fn is m1_predict:
            out.append(predict_fn(c["t"], c["T_C"], c["RH_pct"],
                                  c["v_ms"], c["d_mm"], p) - c["mr"])
        else:
            out.append(predict_fn(c["t"], c["T_C"], c["v_ms"],
                                  c["RH_pct"], p) - c["mr"])
    return np.concatenate(out)


def fit_with_jac(curves, predict_fn, p0, lo, hi):
    def res(p):
        return _residuals(curves, predict_fn, p)
    sol = least_squares(res, p0, bounds=(lo, hi), method="trf",
                        max_nfev=20_000, xtol=1e-12, ftol=1e-12)
    J = sol.jac
    r = sol.fun
    n_obs = len(r); n_par = len(sol.x)
    sigma2 = float((r @ r) / max(n_obs - n_par, 1))
    JTJ = J.T @ J
    # Use SVD-based pseudo-inverse with strict rcond so we don't zero out
    # small but real eigenvalues that carry the Ea/logA correlation.
    cov = sigma2 * np.linalg.pinv(JTJ, rcond=1e-15)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    return sol.x, cov, se, sigma2, n_obs


def profile_se_ea(curves, predict_fn, p_hat, lo, hi, idx_ea, n_obs, n_par):
    """Profile-likelihood SE for the Ea parameter.

    Refit the other parameters with Ea fixed at p_hat[idx]+/-delta. Find
    delta such that (SS - SS_min) crosses chi2(1, 0.05) = 3.84 * sigma2.
    Returns +/- delta as the symmetric SE-equivalent.
    """
    SS_min = float(np.sum(_residuals(curves, predict_fn, p_hat) ** 2))
    sigma2 = SS_min / max(n_obs - n_par, 1)
    target = SS_min + 3.84 * sigma2

    # Search range: 0.1 * |p_hat[idx_ea]| up to 1.5 * |p_hat[idx_ea]|
    base = abs(p_hat[idx_ea]) if p_hat[idx_ea] != 0 else 1.0

    def ss_at(ea_val):
        if not (lo[idx_ea] <= ea_val <= hi[idx_ea]):
            return float("inf")
        mask = np.ones(len(p_hat), dtype=bool); mask[idx_ea] = False
        p0 = p_hat.copy()
        p_lo = lo[mask]; p_hi = hi[mask]

        def res_partial(pf):
            p_full = np.empty(len(p_hat)); p_full[mask] = pf; p_full[idx_ea] = ea_val
            return _residuals(curves, predict_fn, p_full)
        try:
            sol = least_squares(res_partial, p0[mask], bounds=(p_lo, p_hi),
                                method="trf", max_nfev=10_000, xtol=1e-10, ftol=1e-10)
            return float(np.sum(sol.fun ** 2))
        except Exception:
            return float("inf")

    # Bracket search: scan up first
    for sign in (+1, -1):
        lo_d = 0.0; hi_d = 1.5 * base
        # ensure hi crosses
        for _ in range(40):
            if ss_at(p_hat[idx_ea] + sign * hi_d) >= target:
                break
            hi_d *= 1.5
        # bisection
        for _ in range(60):
            mid = 0.5 * (lo_d + hi_d)
            if ss_at(p_hat[idx_ea] + sign * mid) >= target:
                hi_d = mid
            else:
                lo_d = mid
            if hi_d - lo_d < 1e-3 * base:
                break
        if sign == +1:
            d_plus = 0.5 * (lo_d + hi_d)
        else:
            d_minus = 0.5 * (lo_d + hi_d)
    return float(d_plus), float(d_minus)


def design_point_K_M1(p):
    """K at T=45 C, RH=15%, v=1.1, d=6 mm, units 1/s."""
    return float(m1_predict(np.array([1.0]), 45.0, 15.0, 1.1, 6.0, p)[0])  # unused
    # The function above wraps with exp(-K*t); we want K directly:


def K_M1_at(T_C, RH_pct, v_ms, d_mm, p):
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K = T_C + 273.15; T_ref_K = T_REF_C + 273.15
    return float(K_ref * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
                 * np.exp(-alpha_RH * RH_pct / 100.0)
                 * (v_ms / V_REF) ** gamma_v
                 * (D_REF / d_mm) ** delta_d)


def K_M2_at(T_C, v_ms, RH_pct, p, t_min=60.0):
    """Instantaneous Midilli K-equivalent at t=60 min (mid-curve)."""
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA); T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = max(0.2, min(2.5, n0 + n_T * (T_C - M2_T_REF_C) + n_v * (v_ms - M2_V_REF)))
    return float(k * n * t_min ** (n - 1) / 60.0)  # 1/s


def main():
    curves = load_curves()

    # ---- M1 fit + covariance ----
    p_m1, cov_m1, se_m1, sig2_m1, n1 = fit_with_jac(curves, m1_predict, M1_NOM, M1_LO, M1_HI)
    EaR_m1 = float(p_m1[1])
    EaR_se_m1 = float(se_m1[1])
    Ea_kJ_m1 = EaR_m1 * R_GAS / 1000.0
    Ea_kJ_se_m1 = EaR_se_m1 * R_GAS / 1000.0
    # Profile SE for M1 Ea/R
    d_p_m1, d_m_m1 = profile_se_ea(curves, m1_predict, p_m1, M1_LO, M1_HI,
                                    idx_ea=1, n_obs=n1, n_par=len(p_m1))
    EaR_prof_m1 = (d_p_m1 + d_m_m1) / 2.0
    Ea_kJ_prof_m1 = EaR_prof_m1 * R_GAS / 1000.0

    # ---- M2 fit + covariance ----
    p_m2, cov_m2, se_m2, sig2_m2, n2 = fit_with_jac(curves, m2_predict, M2_NOM, M2_LO, M2_HI)
    Ea_J_m2 = float(p_m2[1])
    Ea_J_se_m2 = float(se_m2[1])
    Ea_kJ_m2 = Ea_J_m2 / 1000.0
    Ea_kJ_se_m2 = Ea_J_se_m2 / 1000.0
    EaR_m2 = Ea_J_m2 / R_GAS
    EaR_se_m2 = Ea_J_se_m2 / R_GAS
    # Profile SE for M2 Ea (J/mol) - the Jacobian-based SE collapses to ~0
    # because of logA<->Ea collinearity, so profile likelihood is the
    # correct way to characterise its uncertainty.
    d_p_m2, d_m_m2 = profile_se_ea(curves, m2_predict, p_m2, M2_LO, M2_HI,
                                    idx_ea=1, n_obs=n2, n_par=len(p_m2))
    Ea_J_prof_m2 = (d_p_m2 + d_m_m2) / 2.0
    Ea_kJ_prof_m2 = Ea_J_prof_m2 / 1000.0

    # ---- Param CI table ----
    ci_rows = []
    for name, est, se in zip(M1_NAMES, p_m1, se_m1):
        ci_rows.append(dict(model="M1", param=name, estimate=float(est),
                            se=float(se), ci95_lo=float(est - 1.96 * se),
                            ci95_hi=float(est + 1.96 * se)))
    for name, est, se in zip(M2_NAMES, p_m2, se_m2):
        ci_rows.append(dict(model="M2", param=name, estimate=float(est),
                            se=float(se), ci95_lo=float(est - 1.96 * se),
                            ci95_hi=float(est + 1.96 * se)))
    pd.DataFrame(ci_rows).to_csv(OUT_DIR / "phase_e_param_ci.csv",
                                  index=False, float_format="%.6g")

    # ---- Monte-Carlo K_eff at design point ----
    rng = np.random.default_rng(seed=7)
    n_draws = 200
    # M1
    try:
        m1_draws = rng.multivariate_normal(p_m1, cov_m1, size=n_draws)
    except np.linalg.LinAlgError:
        m1_draws = np.array([p_m1] * n_draws)
    K_m1_at_design = np.array([K_M1_at(45.0, 15.0, 1.1, 6.0, pp) for pp in m1_draws])
    # M2 at the same design point (RH 15%) at t=60 min
    try:
        m2_draws = rng.multivariate_normal(p_m2, cov_m2, size=n_draws)
    except np.linalg.LinAlgError:
        m2_draws = np.array([p_m2] * n_draws)
    K_m2_at_design = np.array([K_M2_at(45.0, 1.1, 15.0, pp) for pp in m2_draws])

    def pct(arr, p):
        return float(np.percentile(arr, p))

    summary = dict(
        M1=dict(
            n_obs=int(n1),
            n_par=len(p_m1),
            sigma2=float(sig2_m1),
            params={n: float(v) for n, v in zip(M1_NAMES, p_m1)},
            standard_errors={n: float(s) for n, s in zip(M1_NAMES, se_m1)},
            Ea_kJ_per_mol=float(Ea_kJ_m1),
            Ea_kJ_per_mol_se_jac=float(Ea_kJ_se_m1),
            Ea_kJ_per_mol_se_profile=float(Ea_kJ_prof_m1),
            Ea_kJ_per_mol_95CI_profile=[float(Ea_kJ_m1 - Ea_kJ_prof_m1),
                                         float(Ea_kJ_m1 + Ea_kJ_prof_m1)],
            Ea_over_R_K=float(EaR_m1),
            Ea_over_R_K_95CI_profile=[float(EaR_m1 - EaR_prof_m1),
                                       float(EaR_m1 + EaR_prof_m1)],
            K_at_design_T45_RH15_v1p1_d6mm=dict(
                mean=float(np.mean(K_m1_at_design)),
                std=float(np.std(K_m1_at_design)),
                p2p5=pct(K_m1_at_design, 2.5),
                p97p5=pct(K_m1_at_design, 97.5),
                t63_min_mean=float(1.0 / np.mean(K_m1_at_design) / 60.0),
            ),
        ),
        M2=dict(
            n_obs=int(n2),
            n_par=len(p_m2),
            sigma2=float(sig2_m2),
            params={n: float(v) for n, v in zip(M2_NAMES, p_m2)},
            standard_errors={n: float(s) for n, s in zip(M2_NAMES, se_m2)},
            Ea_kJ_per_mol=float(Ea_kJ_m2),
            Ea_kJ_per_mol_se_jac=float(Ea_kJ_se_m2),
            Ea_kJ_per_mol_se_profile=float(Ea_kJ_prof_m2),
            Ea_kJ_per_mol_95CI_profile=[float(Ea_kJ_m2 - Ea_kJ_prof_m2),
                                         float(Ea_kJ_m2 + Ea_kJ_prof_m2)],
            Ea_over_R_K=float(EaR_m2),
            Ea_over_R_K_95CI_profile=[float((Ea_J_m2 - Ea_J_prof_m2) / R_GAS),
                                       float((Ea_J_m2 + Ea_J_prof_m2) / R_GAS)],
            K_at_design_T45_RH15_v1p1_t60min=dict(
                mean=float(np.mean(K_m2_at_design)),
                std=float(np.std(K_m2_at_design)),
                p2p5=pct(K_m2_at_design, 2.5),
                p97p5=pct(K_m2_at_design, 97.5),
                t63_min_mean=float(1.0 / np.mean(K_m2_at_design) / 60.0),
            ),
        ),
        literature_apple_Ea_kJ_per_mol=[
            dict(label=l, Ea_kJ_per_mol=v, source=s) for l, v, s in LIT_APPLE
        ],
        literature_range_kJ_per_mol=[
            float(min(v for _, v, _ in LIT_APPLE)),
            float(max(v for _, v, _ in LIT_APPLE)),
        ],
    )
    (OUT_DIR / "phase_e_summary.json").write_text(json.dumps(summary, indent=2))

    # ---- Print ----
    print("=" * 78)
    print("Phase E - parameter uncertainty + literature comparison")
    print("=" * 78)
    print(f"\nM1: Ea = {Ea_kJ_m1:.2f} kJ/mol  "
          f"(profile 95%CI {Ea_kJ_m1 - Ea_kJ_prof_m1:.2f} to {Ea_kJ_m1 + Ea_kJ_prof_m1:.2f}; "
          f"Jac SE {Ea_kJ_se_m1:.2f})")
    print(f"M2: Ea = {Ea_kJ_m2:.2f} kJ/mol  "
          f"(profile 95%CI {Ea_kJ_m2 - Ea_kJ_prof_m2:.2f} to {Ea_kJ_m2 + Ea_kJ_prof_m2:.2f}; "
          f"Jac SE {Ea_kJ_se_m2*1000:.2e} J/mol -> ~0 from logA-Ea collinearity)")
    print(f"\nLiterature apple Ea range: "
          f"{min(v for _, v, _ in LIT_APPLE):.2f} to {max(v for _, v, _ in LIT_APPLE):.2f} kJ/mol")
    for label, Ea_lit, src in LIT_APPLE:
        print(f"  {label:30s} {Ea_lit:5.2f} kJ/mol  ({src})")

    print(f"\nK_eff at design point (T=45 C, RH=15%, v=1.1, d=6 mm):")
    print(f"  M1: {summary['M1']['K_at_design_T45_RH15_v1p1_d6mm']['mean']:.4e} +/- "
          f"{summary['M1']['K_at_design_T45_RH15_v1p1_d6mm']['std']:.4e} 1/s   "
          f"(t63 = {summary['M1']['K_at_design_T45_RH15_v1p1_d6mm']['t63_min_mean']:.1f} min)")
    print(f"  M2: {summary['M2']['K_at_design_T45_RH15_v1p1_t60min']['mean']:.4e} +/- "
          f"{summary['M2']['K_at_design_T45_RH15_v1p1_t60min']['std']:.4e} 1/s   "
          f"(t63 = {summary['M2']['K_at_design_T45_RH15_v1p1_t60min']['t63_min_mean']:.1f} min)")

    print(f"\nWrote {OUT_DIR / 'phase_e_param_ci.csv'}")
    print(f"      {OUT_DIR / 'phase_e_summary.json'}")


if __name__ == "__main__":
    main()
