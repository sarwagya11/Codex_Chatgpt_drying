"""
Phase D audit: SEC robustness across kinetic models, FULL sweep.

Runs all 9 configs (A, B1, C1, D1, D2, D3, E1, E2, E3) at all 3
locations (biratnagar, kathmandu, taplejung) at r=0 (open-loop) under
both M1 (live) and M2 (Arrhenius+Midilli, full-data fit) and reports
the SEC delta. Total: 9 x 3 x 2 = 54 simulations.

If SEC numbers are insensitive to the kinetic-model choice, the SEC
results in MEMORY are robust to that choice.

For M2 we monkey-patch `rq1.dryer_solar_hp.compute_dm_w_kinetic_first_order`
to compute an instantaneous Midilli-equivalent K_eff(t,T,v,RH) and apply
the standard first-order discretisation `dX = -K*(X-X_eq)*dt`. The
section drying clock is the simulation `time_s` (all sections start at
X0 simultaneously).

Outputs:
  outputs/audit/phase_d_sec_summary.csv
  outputs/audit/phase_d_sec_delta.csv
  outputs/audit/phase_d_summary.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RQ1_ROOT = PROJECT_ROOT / "RQ1"
sys.path.insert(0, str(RQ1_ROOT / "src"))

from rq1 import dryer_solar_hp as dryer_mod  # noqa: E402
from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    make_config_A_HP_only,
    make_config_B1_solar_before_cond,
    make_config_B2_solar_after_cond,
    make_config_C1_solar_on_evap_source,
    make_config_D_HRX,
    make_config_E_HRX_solar,
)
from rq1.kinetics import compute_dm_w_kinetic_first_order as _orig_kin  # noqa: E402


OUT_DIR = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# --- M2 params (full-data LOCO global fit) ---
M2_FIT = json.loads(
    (PROJECT_ROOT / "outputs" / "baseline" / "diagnostics" / "global_fit.json")
    .read_text()
)
R_GAS = 8.314


def _m2_keff_instantaneous(t_s: float, T_C: float, v_ms: float, RH_pct: float) -> float:
    """Instantaneous first-order-equivalent K from Midilli derivative.

    Midilli: MR(t_min) = exp(-k * t_min^n) + b * t_min
        k(T)   = A * exp(-Ea / (R*T_K))                        [min^-n]
        n(T,v) = n0 + n_T*(T-T_ref) + n_v*(v-v_ref)
        b(RH)  = b0 + b_RH*(RH-RH_ref)
    Treat dMR/dt = -K_eff(t) * MR (ignoring the +b drift, which is tiny).
    Then K_eff_min = k * n * t_min^(n-1).  Convert to 1/s by dividing by 60.
    """
    A_per_min_n = M2_FIT["A_per_min_n"]
    Ea_J_per_mol = M2_FIT["Ea_J_per_mol"]
    n0 = M2_FIT["n0"]; n_T = M2_FIT["n_T"]; n_v = M2_FIT["n_v"]
    T_ref = M2_FIT["T_ref_C"]; v_ref = M2_FIT["v_ref_ms"]
    T_K = T_C + 273.15
    k_per_min_n = A_per_min_n * math.exp(-Ea_J_per_mol / (R_GAS * T_K))
    n = n0 + n_T * (T_C - T_ref) + n_v * (v_ms - v_ref)
    n = max(0.2, min(2.5, n))
    t_min = max(t_s / 60.0, 1e-3)  # avoid t^(n-1) explosion at t=0
    K_per_min = k_per_min_n * n * (t_min ** (n - 1.0))
    return max(1e-8, K_per_min / 60.0)


def m2_kin_replacement(X_db, X_eq_db, T_in_C, RH_in_frac, dt_s, cfg,
                       m_p_dry_kg, time_s=None):
    K_eff = _m2_keff_instantaneous(
        t_s=float(time_s or 0.0),
        T_C=float(T_in_C),
        v_ms=float(cfg.v_ms),
        RH_pct=float(RH_in_frac) * 100.0,
    )
    K_eff = max(cfg.K_min_1_per_s, K_eff)
    X_db_new = X_db - K_eff * (X_db - X_eq_db) * dt_s
    X_db_new = max(X_db_new, X_eq_db)
    return max(0.0, m_p_dry_kg * max(0.0, X_db - X_db_new))


def use_m1():
    dryer_mod.compute_dm_w_kinetic_first_order = _orig_kin


def use_m2():
    dryer_mod.compute_dm_w_kinetic_first_order = m2_kin_replacement


# --- run helpers ---
def build_cfg(config_letter, location):
    weather = RQ1_ROOT / "data" / "ambient" / f"{location}_pvgis_standard.csv"
    elev = LOCATION_ELEVATIONS_M.get(location, 0)
    phase2_root = RQ1_ROOT / "outputs"
    common = dict(ambient_csv=weather, elevation_m=elev,
                  phase2_root=phase2_root)
    if config_letter == "A":
        cfg = make_config_A_HP_only(
            r_recirc=0.0, n_sections=1,
            flow_reversal_interval_min=0.0, cond_penalty_thresh=0.0,
            **common)
    elif config_letter == "B1":
        cfg = make_config_B1_solar_before_cond(
            solar_area_m2=10.0, r_recirc=0.0, n_sections=1,
            flow_reversal_interval_min=0.0, cond_penalty_thresh=0.0,
            **common)
    elif config_letter == "B2":
        cfg = make_config_B2_solar_after_cond(
            solar_area_m2=10.0, n_sections=1,
            flow_reversal_interval_min=0.0,
            **common)
    elif config_letter == "C1":
        cfg = make_config_C1_solar_on_evap_source(
            solar_area_m2=10.0, r_recirc=0.0, n_sections=1,
            flow_reversal_interval_min=0.0, cond_penalty_thresh=0.0,
            **common)
    elif config_letter in ("D1", "D2", "D3"):
        cfg = make_config_D_HRX(
            d_variant=config_letter, eps_HRX=0.70,
            vpd_bypass_thresh=0.0, **common)
    elif config_letter in ("E1", "E2", "E3"):
        cfg = make_config_E_HRX_solar(
            solar_area_m2=10.0, e_variant=config_letter,
            eps_HRX=0.70, vpd_bypass_thresh=0.0, **common)
    else:
        raise ValueError(f"unknown config {config_letter}")
    cfg.max_simulation_time_s = 72.0 * 3600.0
    return cfg


def extract_sec(result):
    df = result.df
    if df.empty:
        return None
    last = df.iloc[-1]
    sec = None
    if "SEC_elec_kWh_per_kg" in df.columns:
        col = df["SEC_elec_kWh_per_kg"].dropna()
        if not col.empty:
            sec = float(col.iloc[-1])
    return dict(
        SEC=sec,
        m_w_cum_kg=float(last["m_w_cum_kg"]),
        time_h=float(last["time_h"]),
        W_comp_cum_kWh=float(last["W_comp_cum_kWh"]),
        W_fan_cum_kWh=float(last["W_fan_cum_kWh"]),
        Q_solar_cum_kWh=float(last.get("Q_solar_cum_kWh", 0.0)),
    )


def main():
    configs = ["A", "B1", "B2", "C1", "D1", "D2", "D3", "E1", "E2", "E3"]
    locations = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
    runs = [(c, l) for c in configs for l in locations]
    rows = []
    for cfg_letter, loc in runs:
        for tag, switch in [("M1", use_m1), ("M2", use_m2)]:
            switch()
            print(f"\n=== Config {cfg_letter}, {loc}, kinetics={tag} ===")
            cfg = build_cfg(cfg_letter, loc)
            result = dryer_mod.run_solar_hp_dryer_simulation(cfg)
            metrics = extract_sec(result)
            if metrics is None:
                print(f"  EMPTY result!")
                continue
            metrics.update(dict(config=cfg_letter, location=loc, model=tag))
            rows.append(metrics)
            print(f"  SEC={metrics['SEC']}  t={metrics['time_h']:.1f}h  "
                  f"m_w={metrics['m_w_cum_kg']:.2f} kg  "
                  f"W_comp={metrics['W_comp_cum_kWh']:.2f} kWh")
    use_m1()  # restore default

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "phase_d_sec_summary.csv", index=False, float_format="%.6g")

    # Compute SEC delta per (config, location)
    pivot = df.pivot_table(index=["config", "location"], columns="model",
                           values="SEC")
    pivot["SEC_delta_M2_minus_M1"] = pivot["M2"] - pivot["M1"]
    pivot["SEC_rel_delta_pct"] = 100.0 * (pivot["M2"] - pivot["M1"]) / pivot["M1"]
    pivot.to_csv(OUT_DIR / "phase_d_sec_delta.csv", float_format="%.6g")

    summary = dict(
        runs=rows,
        sec_delta=pivot.reset_index().to_dict(orient="records"),
    )
    (OUT_DIR / "phase_d_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 78)
    print("Phase D SEC summary  (kWh/kg)")
    print("=" * 78)
    print(pivot.to_string(float_format=lambda v: f"{v:7.4f}"))
    print(f"\nSaved {OUT_DIR / 'phase_d_sec_summary.csv'}")
    print(f"      {OUT_DIR / 'phase_d_sec_delta.csv'}")


if __name__ == "__main__":
    main()
