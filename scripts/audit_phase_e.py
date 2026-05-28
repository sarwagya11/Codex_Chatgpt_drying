"""
Phase E audit: parameter uncertainty + literature comparison.

For both M1 and M2:
  1. Refit the full-data model using the shared NLS-on-raw-MR protocol
     (`_kinetics_common.fit_m1` / `fit_m2_one`), so the Phase E covariance
     matrix is taken at the same point as the LOCO comparison and the
     Phase B reproducibility study.
  2. Compute parameter covariance from the LS Jacobian:
        Cov ~ sigma2 * (J^T J)^{-1},   sigma2 = SS_res / (N - p)
     and report standard errors, 95% CIs, and a profile-likelihood SE for
     Ea (Jacobian SE collapses under logA<->Ea collinearity for M2).
  3. Convert the M1 Ea/R uncertainty into Ea (J/mol) and compare to
     published apple-drying activation energies.
  4. Sample n_draws parameter draws from a multivariate normal centred at
     the LS estimate and propagate to K_eff at the design point
     (T=45 C, RH=15%, v=1.1, d=6 mm). Reject any draw that violates the
     fit bounds and resample until the requested number of valid draws is
     obtained, so K_eff statistics never include physically impossible
     parameters. RH=15% is below the M1/M2 calibration range (RH_min=22%
     in the 13-curve dataset); this is reported in the summary so the
     extrapolation is explicit.

Outputs:
  outputs/audit/phase_e_param_ci.csv
  outputs/audit/phase_e_summary.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from _kinetics_common import (
    M1_HI, M1_LO, M1_NOM,
    M2_HI, M2_LO, M2_NOM,
    R_GAS, RH_REF, T_REF_C, V_REF, D_REF,
    fit_m1, fit_m2_one, load_curves, m1_predict, m2_predict,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR    = PROJECT_ROOT / "data"
OUT_DIR     = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M1_NAMES = ["logK_ref", "Ea_over_R_K", "alpha_RH", "gamma_v", "delta_d"]
M2_NAMES = ["logA", "Ea_J_per_mol", "n0", "n_T", "n_v", "b0", "b_RH"]

# Design point (single fixed condition used for K_eff propagation).
# RH=15% is below the calibration range RH in [22, 65]% (see phase2_targets);
# this is intentional (corresponds to in-chamber RH after condenser drying)
# but the summary records the extrapolation explicitly.
DESIGN_T_C = 45.0
DESIGN_RH_PCT = 15.0
DESIGN_V_MS = 1.1
DESIGN_D_MM = 6.0

# Literature: apple-drying activation energies (kJ/mol)
LIT_APPLE = [
    ("Sacilik & Elicin 2006",        19.96, "thin-layer apple, Midilli"),
    ("Wang et al. 2007",             24.23, "thin-layer apple, Page"),
    ("Doymaz 2010",                  30.93, "thin-layer apple, Midilli"),
    ("Meisami-asl et al. 2010",      29.26, "thin-layer apple slices"),
    ("Tzempelikos et al. 2014",      27.10, "convective apple drying"),
    ("Kaleta & Gornicki 2010",       22.70, "thin-layer apple, Page"),
]


# ---------------------------------------------------------------------------
# Residuals and predict-fn dispatch (Phase E owns its own residual stack
# because we need direct access to the Jacobian; the shared module wraps
# the call inside its own least_squares).
# ---------------------------------------------------------------------------

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


def _refit_with_jac(curves, predict_fn, p_init, lo, hi):
    """Refit at p_init (already at the global optimum from Phase B/C) just
    to recover the LS Jacobian for covariance estimation."""
    def res(p):
        return _residuals(curves, predict_fn, p)
    sol = least_squares(res, p_init, bounds=(lo, hi), method="trf",
                        max_nfev=20_000, xtol=1e-12, ftol=1e-12)
    J = sol.jac
    r = sol.fun
    n_obs = len(r)
    n_par = len(sol.x)
    sigma2 = float((r @ r) / max(n_obs - n_par, 1))
    JTJ = J.T @ J
    cov = sigma2 * np.linalg.pinv(JTJ, rcond=1e-15)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    return sol.x, cov, se, sigma2, n_obs


def _profile_se_ea(curves, predict_fn, p_hat, lo, hi, idx_ea, n_obs, n_par):
    """Profile-likelihood SE for the Ea parameter.

    Refit the other parameters with Ea fixed at p_hat[idx]+/-delta. Find
    delta such that (SS - SS_min) crosses chi2(1, 0.05) = 3.84 * sigma2.
    """
    SS_min = float(np.sum(_residuals(curves, predict_fn, p_hat) ** 2))
    sigma2 = SS_min / max(n_obs - n_par, 1)
    target = SS_min + 3.84 * sigma2
    base = abs(p_hat[idx_ea]) if p_hat[idx_ea] != 0 else 1.0

    def ss_at(ea_val):
        if not (lo[idx_ea] <= ea_val <= hi[idx_ea]):
            return float("inf")
        mask = np.ones(len(p_hat), dtype=bool); mask[idx_ea] = False
        p0 = p_hat.copy()
        p_lo = lo[mask]; p_hi = hi[mask]

        def res_partial(pf):
            p_full = np.empty(len(p_hat))
            p_full[mask] = pf
            p_full[idx_ea] = ea_val
            return _residuals(curves, predict_fn, p_full)
        try:
            sol = least_squares(res_partial, p0[mask], bounds=(p_lo, p_hi),
                                method="trf", max_nfev=10_000,
                                xtol=1e-10, ftol=1e-10)
            return float(np.sum(sol.fun ** 2))
        except Exception:
            return float("inf")

    deltas: list[float] = []
    for sign in (+1, -1):
        lo_d = 0.0
        hi_d = 1.5 * base
        for _ in range(40):
            if ss_at(p_hat[idx_ea] + sign * hi_d) >= target:
                break
            hi_d *= 1.5
        for _ in range(60):
            mid = 0.5 * (lo_d + hi_d)
            if ss_at(p_hat[idx_ea] + sign * mid) >= target:
                hi_d = mid
            else:
                lo_d = mid
            if hi_d - lo_d < 1e-3 * base:
                break
        deltas.append(0.5 * (lo_d + hi_d))
    d_plus, d_minus = deltas
    return float(d_plus), float(d_minus)


# ---------------------------------------------------------------------------
# K_eff at design point (NOT MR, this is the rate constant in 1/s)
# ---------------------------------------------------------------------------

def _K_M1_at(T_C, RH_pct, v_ms, d_mm, p):
    """M1 first-order rate constant (1/s) at the design point."""
    logK_ref, EaR, alpha_RH, gamma_v, delta_d = p
    K_ref = np.exp(logK_ref)
    T_K = T_C + 273.15
    T_ref_K = T_REF_C + 273.15
    return float(K_ref * np.exp(EaR * (1.0 / T_ref_K - 1.0 / T_K))
                 * np.exp(-alpha_RH * RH_pct / 100.0)
                 * (v_ms / V_REF) ** gamma_v
                 * (D_REF / d_mm) ** delta_d)


def _K_M2_at(T_C, v_ms, RH_pct, p, t_min: float = 60.0):
    """M2 instantaneous Midilli K-equivalent at t=60 min (mid-curve), 1/s.

    Midilli is MR = exp(-k * t^n) + b * t (in minutes); the local first-order
    equivalent rate is d(-ln MR)/dt ~ k * n * t^(n-1) at the chosen t.
    """
    logA, Ea, n0, n_T, n_v, b0, b_RH = p
    A = np.exp(logA)
    T_K = T_C + 273.15
    k = A * np.exp(-Ea / (R_GAS * T_K))
    n = max(0.2, min(2.5, n0 + n_T * (T_C - T_REF_C) + n_v * (v_ms - V_REF)))
    return float(k * n * t_min ** (n - 1) / 60.0)


# ---------------------------------------------------------------------------
# Bounds-respecting Monte Carlo (rejection sampling)
# ---------------------------------------------------------------------------

def _mc_draws_bounded(p_hat: np.ndarray, cov: np.ndarray, lo: np.ndarray,
                      hi: np.ndarray, n: int, rng: np.random.Generator,
                      max_oversample: int = 50) -> Tuple[np.ndarray, dict]:
    """Sample n parameter vectors from N(p_hat, cov), rejecting any draw
    that falls outside [lo, hi] in any component. Returns the draws and a
    diagnostic dict with the rejection rate.
    """
    accepted: list[np.ndarray] = []
    n_total = 0
    n_attempted_max = n * max_oversample
    while len(accepted) < n and n_total < n_attempted_max:
        batch = max(n - len(accepted), 1) * 4
        try:
            cand = rng.multivariate_normal(p_hat, cov, size=batch)
        except np.linalg.LinAlgError:
            return np.array([p_hat] * n), dict(
                n_drawn=0, n_accepted=0, fraction_accepted=float("nan"),
                fallback="cov_not_psd",
            )
        n_total += batch
        for row in cand:
            if np.all(row >= lo) and np.all(row <= hi):
                accepted.append(row)
                if len(accepted) >= n:
                    break
    if len(accepted) < n:
        # Pad by repeating the truncated draws; record degenerate diagnostic.
        if accepted:
            rep = np.array(accepted)
            extra = rep[rng.integers(0, len(rep), size=n - len(rep))]
            arr = np.vstack([rep, extra])
        else:
            arr = np.array([p_hat] * n)
        return arr, dict(
            n_drawn=int(n_total),
            n_accepted=int(len(accepted)),
            fraction_accepted=float(len(accepted) / max(n_total, 1)),
            fallback="oversample_exhausted",
        )
    return np.array(accepted[:n]), dict(
        n_drawn=int(n_total),
        n_accepted=int(n),
        fraction_accepted=float(n / max(n_total, 1)),
        fallback=None,
    )


def main():
    curves = load_curves(TARGETS_CSV, DATA_DIR)

    # ---- M1 fit + covariance (single start; M1 is convex) ----
    sol_m1 = fit_m1(curves, M1_NOM)
    p_m1, cov_m1, se_m1, sig2_m1, n1 = _refit_with_jac(
        curves, m1_predict, sol_m1.x, M1_LO, M1_HI)
    EaR_m1 = float(p_m1[1])
    EaR_se_m1 = float(se_m1[1])
    Ea_kJ_m1 = EaR_m1 * R_GAS / 1000.0
    Ea_kJ_se_m1 = EaR_se_m1 * R_GAS / 1000.0
    d_p_m1, d_m_m1 = _profile_se_ea(curves, m1_predict, p_m1, M1_LO, M1_HI,
                                     idx_ea=1, n_obs=n1, n_par=len(p_m1))
    EaR_prof_m1 = (d_p_m1 + d_m_m1) / 2.0
    Ea_kJ_prof_m1 = EaR_prof_m1 * R_GAS / 1000.0

    # ---- M2 fit + covariance (single start at literature prior; Phase B
    # confirmed this start reaches the global optimum) ----
    sol_m2 = fit_m2_one(curves, M2_NOM)
    p_m2, cov_m2, se_m2, sig2_m2, n2 = _refit_with_jac(
        curves, m2_predict, sol_m2.x, M2_LO, M2_HI)
    Ea_J_m2 = float(p_m2[1])
    Ea_J_se_m2 = float(se_m2[1])
    Ea_kJ_m2 = Ea_J_m2 / 1000.0
    Ea_kJ_se_m2 = Ea_J_se_m2 / 1000.0
    EaR_m2 = Ea_J_m2 / R_GAS
    d_p_m2, d_m_m2 = _profile_se_ea(curves, m2_predict, p_m2, M2_LO, M2_HI,
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

    # ---- Monte-Carlo K_eff at design point with bounds rejection ----
    rng = np.random.default_rng(seed=7)
    n_draws = 200
    m1_draws, mc_diag_m1 = _mc_draws_bounded(p_m1, cov_m1, M1_LO, M1_HI,
                                              n_draws, rng)
    K_m1_at_design = np.array([
        _K_M1_at(DESIGN_T_C, DESIGN_RH_PCT, DESIGN_V_MS, DESIGN_D_MM, pp)
        for pp in m1_draws
    ])
    m2_draws, mc_diag_m2 = _mc_draws_bounded(p_m2, cov_m2, M2_LO, M2_HI,
                                              n_draws, rng)
    K_m2_at_design = np.array([
        _K_M2_at(DESIGN_T_C, DESIGN_V_MS, DESIGN_RH_PCT, pp) for pp in m2_draws
    ])

    def _pct(arr, p):
        return float(np.percentile(arr, p))

    # ---- Calibration ranges (for the RH extrapolation note) ----
    targets = pd.read_csv(TARGETS_CSV)
    rh_min = float(targets["RH_mid_pct"].min())
    rh_max = float(targets["RH_mid_pct"].max())
    T_min = float(targets["T_C"].min())
    T_max = float(targets["T_C"].max())
    v_min = float(targets["v_ms"].min())
    v_max = float(targets["v_ms"].max())
    d_min = float(targets["thickness_mm"].min())
    d_max = float(targets["thickness_mm"].max())

    summary = dict(
        design_point=dict(
            T_C=DESIGN_T_C, RH_pct=DESIGN_RH_PCT,
            v_ms=DESIGN_V_MS, d_mm=DESIGN_D_MM,
            calibration_range=dict(
                T_C=[T_min, T_max], RH_pct=[rh_min, rh_max],
                v_ms=[v_min, v_max], d_mm=[d_min, d_max],
            ),
            extrapolation_flags=dict(
                RH_below_min=bool(DESIGN_RH_PCT < rh_min),
                RH_above_max=bool(DESIGN_RH_PCT > rh_max),
            ),
            extrapolation_note=(
                f"Design RH={DESIGN_RH_PCT:.0f}% is below the calibration "
                f"minimum RH={rh_min:.0f}% (range {rh_min:.0f}-{rh_max:.0f}%). "
                f"K_eff is extrapolated linearly in RH via the alpha_RH (M1) "
                f"and b0+b_RH (M2) terms; treat the design-point K_eff as "
                f"indicative, not observation-validated."
            ),
        ),
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
            mc_draws=dict(
                n_requested=int(n_draws),
                n_drawn=int(mc_diag_m1["n_drawn"]),
                n_accepted=int(mc_diag_m1["n_accepted"]),
                fraction_accepted=float(mc_diag_m1["fraction_accepted"]),
                fallback=mc_diag_m1["fallback"],
            ),
            K_at_design=dict(
                mean=float(np.mean(K_m1_at_design)),
                std=float(np.std(K_m1_at_design)),
                p2p5=_pct(K_m1_at_design, 2.5),
                p97p5=_pct(K_m1_at_design, 97.5),
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
            mc_draws=dict(
                n_requested=int(n_draws),
                n_drawn=int(mc_diag_m2["n_drawn"]),
                n_accepted=int(mc_diag_m2["n_accepted"]),
                fraction_accepted=float(mc_diag_m2["fraction_accepted"]),
                fallback=mc_diag_m2["fallback"],
            ),
            K_at_design=dict(
                mean=float(np.mean(K_m2_at_design)),
                std=float(np.std(K_m2_at_design)),
                p2p5=_pct(K_m2_at_design, 2.5),
                p97p5=_pct(K_m2_at_design, 97.5),
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
          f"(profile 95%CI {Ea_kJ_m1 - Ea_kJ_prof_m1:.2f} to "
          f"{Ea_kJ_m1 + Ea_kJ_prof_m1:.2f}; Jac SE {Ea_kJ_se_m1:.2f})")
    print(f"M2: Ea = {Ea_kJ_m2:.2f} kJ/mol  "
          f"(profile 95%CI {Ea_kJ_m2 - Ea_kJ_prof_m2:.2f} to "
          f"{Ea_kJ_m2 + Ea_kJ_prof_m2:.2f}; Jac SE "
          f"{Ea_kJ_se_m2*1000:.2e} J/mol -> ~0 from logA-Ea collinearity)")
    print(f"\nLiterature apple Ea range: "
          f"{min(v for _, v, _ in LIT_APPLE):.2f} to "
          f"{max(v for _, v, _ in LIT_APPLE):.2f} kJ/mol")
    for label, Ea_lit, src in LIT_APPLE:
        print(f"  {label:30s} {Ea_lit:5.2f} kJ/mol  ({src})")

    print(f"\nMC draws (bounds-respecting, n={n_draws}):")
    print(f"  M1: drew {mc_diag_m1['n_drawn']}, accepted "
          f"{mc_diag_m1['n_accepted']} "
          f"({100 * mc_diag_m1['fraction_accepted']:.1f}%)"
          + (f"  [{mc_diag_m1['fallback']}]" if mc_diag_m1["fallback"] else ""))
    print(f"  M2: drew {mc_diag_m2['n_drawn']}, accepted "
          f"{mc_diag_m2['n_accepted']} "
          f"({100 * mc_diag_m2['fraction_accepted']:.1f}%)"
          + (f"  [{mc_diag_m2['fallback']}]" if mc_diag_m2["fallback"] else ""))

    print(f"\nK_eff at design point "
          f"(T={DESIGN_T_C} C, RH={DESIGN_RH_PCT:.0f}% [extrapolated; "
          f"calibration min RH={rh_min:.0f}%], v={DESIGN_V_MS}, "
          f"d={DESIGN_D_MM} mm):")
    print(f"  M1: {summary['M1']['K_at_design']['mean']:.4e} +/- "
          f"{summary['M1']['K_at_design']['std']:.4e} 1/s   "
          f"(t63 = {summary['M1']['K_at_design']['t63_min_mean']:.1f} min)")
    print(f"  M2: {summary['M2']['K_at_design']['mean']:.4e} +/- "
          f"{summary['M2']['K_at_design']['std']:.4e} 1/s   "
          f"(t63 = {summary['M2']['K_at_design']['t63_min_mean']:.1f} min)")

    print(f"\nWrote {OUT_DIR / 'phase_e_param_ci.csv'}")
    print(f"      {OUT_DIR / 'phase_e_summary.json'}")


if __name__ == "__main__":
    main()
