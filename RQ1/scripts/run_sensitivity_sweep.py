#!/usr/bin/env python3
"""Reviewer-requested sensitivity and convergence simulations.

F1: eps_cond, eps_evap sweep (0.75, 0.85, 0.95) on Config A + E2 at KTM
    eps_HRX sweep (0.60, 0.70, 0.80) on Config E2 at KTM
F2: dt convergence (30, 60, 120 s) on Config A + E2 at KTM
F3: Taplejung E1/E2/E3 +/- VPD bypass at 10 m^2

Results saved to outputs/reviewer_sensitivity/
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import (
    make_config_A_HP_only,
    make_config_E_HRX_solar,
    make_config_D_HRX,
)
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation
import csv


LOCATION_ELEVATIONS = {"kathmandu": 1350, "biratnagar": 72, "taplejung": 1820}

def get_weather(loc):
    for name in [f"{loc}_pvgis_standard.csv", f"{loc}.csv"]:
        p = PROJECT_ROOT / "data" / "ambient" / name
        if p.exists():
            return p
    raise FileNotFoundError(f"No weather file for {loc}")

def get_phase2():
    p = PROJECT_ROOT / "outputs" / "phase2c_for_chamber.csv"
    return p.parent if p.exists() else None


def _make_A(weather, elev, phase2, r=0.0):
    return make_config_A_HP_only(
        ambient_csv=weather, elevation_m=elev,
        phase2_root=phase2, r_recirc=r,
    )

def _make_E2(weather, elev, phase2, area=10.0, eps_hrx=0.70, vpd=0.0):
    return make_config_E_HRX_solar(
        ambient_csv=weather, solar_area_m2=area, e_variant="E2",
        elevation_m=elev, phase2_root=phase2,
        eps_HRX=eps_hrx, vpd_bypass_thresh=vpd,
    )

def _make_D1(weather, elev, phase2, eps_hrx=0.70):
    return make_config_D_HRX(
        ambient_csv=weather, d_variant="D1",
        elevation_m=elev, phase2_root=phase2,
        eps_HRX=eps_hrx,
    )

def _make_E_variant(weather, elev, phase2, variant, area=10.0, eps_hrx=0.70, vpd=0.0):
    return make_config_E_HRX_solar(
        ambient_csv=weather, solar_area_m2=area, e_variant=variant,
        elevation_m=elev, phase2_root=phase2,
        eps_HRX=eps_hrx, vpd_bypass_thresh=vpd,
    )


def run_and_extract(cfg, label):
    """Run a simulation and return a summary dict."""
    result = run_solar_hp_dryer_simulation(cfg)
    df = result.df
    if df.empty:
        return {"label": label, "SEC": "FAIL", "time_h": "FAIL"}
    final = df.iloc[-1]
    sec_col = "SEC_elec_kWh_per_kg"
    sec = df[sec_col].dropna().iloc[-1] if sec_col in df.columns else None
    return {
        "label": label,
        "SEC": f"{sec:.4f}" if sec else "N/A",
        "time_h": f"{final['time_h']:.1f}",
        "W_comp_kWh": f"{final['W_comp_cum_kWh']:.2f}",
        "W_fan_kWh": f"{final['W_fan_cum_kWh']:.2f}",
        "m_water_kg": f"{final['m_w_cum_kg']:.2f}",
    }


def save_results(rows, filename):
    out_dir = PROJECT_ROOT / "outputs" / "reviewer_sensitivity"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    if not rows:
        print(f"  No results for {filename}")
        return
    keys = rows[0].keys()
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved: {path}")


# ── F1: Effectiveness sensitivity ──────────────────────────────────

def run_F1_eps_sensitivity():
    print("\n" + "="*70)
    print("F1: Effectiveness sensitivity (eps_cond, eps_evap, eps_HRX)")
    print("="*70)

    loc = "kathmandu"
    elev = LOCATION_ELEVATIONS[loc]
    weather = get_weather(loc)
    phase2 = get_phase2()
    results = []

    # F1a: eps_cond sweep on Config A
    for eps_c in [0.75, 0.85, 0.95]:
        label = f"A_KTM_eps_cond={eps_c:.2f}"
        print(f"\n  Running {label}...")
        cfg = _make_A(weather, elev, phase2)
        cfg.heatpump.epsilon_cond = eps_c
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    # F1b: eps_evap sweep on Config A
    for eps_e in [0.75, 0.85, 0.95]:
        label = f"A_KTM_eps_evap={eps_e:.2f}"
        print(f"\n  Running {label}...")
        cfg = _make_A(weather, elev, phase2)
        cfg.heatpump.epsilon_evap = eps_e
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    # F1c: eps_cond sweep on E2
    for eps_c in [0.75, 0.85, 0.95]:
        label = f"E2_KTM_eps_cond={eps_c:.2f}"
        print(f"\n  Running {label}...")
        cfg = _make_E2(weather, elev, phase2)
        cfg.heatpump.epsilon_cond = eps_c
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    # F1d: eps_evap sweep on E2
    for eps_e in [0.75, 0.85, 0.95]:
        label = f"E2_KTM_eps_evap={eps_e:.2f}"
        print(f"\n  Running {label}...")
        cfg = _make_E2(weather, elev, phase2)
        cfg.heatpump.epsilon_evap = eps_e
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    # F1e: eps_HRX sweep on E2
    for eps_h in [0.60, 0.70, 0.80]:
        label = f"E2_KTM_eps_HRX={eps_h:.2f}"
        print(f"\n  Running {label}...")
        cfg = _make_E2(weather, elev, phase2, eps_hrx=eps_h)
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    # F1f: eps_HRX sweep on D1
    for eps_h in [0.60, 0.70, 0.80]:
        label = f"D1_KTM_eps_HRX={eps_h:.2f}"
        print(f"\n  Running {label}...")
        cfg = _make_D1(weather, elev, phase2, eps_hrx=eps_h)
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    save_results(results, "F1_effectiveness_sensitivity.csv")
    return results


# ── F2: Time-step convergence ──────────────────────────────────────

def run_F2_dt_convergence():
    print("\n" + "="*70)
    print("F2: Time-step convergence (dt = 30, 60, 120 s)")
    print("="*70)

    loc = "kathmandu"
    elev = LOCATION_ELEVATIONS[loc]
    weather = get_weather(loc)
    phase2 = get_phase2()
    results = []

    for dt in [30, 60, 120]:
        # Config A
        label = f"A_KTM_dt={dt}s"
        print(f"\n  Running {label}...")
        cfg = _make_A(weather, elev, phase2)
        cfg.dryer.dt_s = float(dt)
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

        # Config E2
        label = f"E2_KTM_dt={dt}s"
        print(f"\n  Running {label}...")
        cfg = _make_E2(weather, elev, phase2)
        cfg.dryer.dt_s = float(dt)
        cfg.max_simulation_time_s = 72 * 3600
        results.append(run_and_extract(cfg, label))

    save_results(results, "F2_timestep_convergence.csv")
    return results


# ── F3: Taplejung E-configs ────────────────────────────────────────

def run_F3_taplejung_E():
    print("\n" + "="*70)
    print("F3: Taplejung E1/E2/E3 +/- VPD bypass")
    print("="*70)

    loc = "taplejung"
    elev = LOCATION_ELEVATIONS[loc]
    weather = get_weather(loc)
    phase2 = get_phase2()
    results = []

    for variant in ["E1", "E2", "E3"]:
        out_dir = PROJECT_ROOT / "outputs" / f"config_{variant}" / loc
        out_dir.mkdir(parents=True, exist_ok=True)

        # Without VPD bypass
        label = f"{variant}_TAP_10m2"
        print(f"\n  Running {label}...")
        cfg = _make_E_variant(weather, elev, phase2, variant)
        cfg.max_simulation_time_s = 72 * 3600
        result_obj = run_solar_hp_dryer_simulation(cfg)
        result_obj.df.to_csv(out_dir / "Ac_10m2_hrx0.70.csv", index=False)
        # Extract summary
        df = result_obj.df
        if not df.empty:
            final = df.iloc[-1]
            sec_col = "SEC_elec_kWh_per_kg"
            sec = df[sec_col].dropna().iloc[-1] if sec_col in df.columns else None
            results.append({
                "label": label,
                "SEC": f"{sec:.4f}" if sec else "N/A",
                "time_h": f"{final['time_h']:.1f}",
                "W_comp_kWh": f"{final['W_comp_cum_kWh']:.2f}",
                "W_fan_kWh": f"{final['W_fan_cum_kWh']:.2f}",
                "m_water_kg": f"{final['m_w_cum_kg']:.2f}",
            })

        # With VPD bypass (E1 and E2 only; E3 does not use VPD bypass)
        if variant in ("E1", "E2"):
            label_vpd = f"{variant}_TAP_10m2_VPD"
            print(f"\n  Running {label_vpd}...")
            cfg_vpd = _make_E_variant(weather, elev, phase2, variant, vpd=0.05)
            cfg_vpd.max_simulation_time_s = 72 * 3600
            result_vpd = run_solar_hp_dryer_simulation(cfg_vpd)
            result_vpd.df.to_csv(out_dir / "Ac_10m2_hrx0.70_vpd0.05.csv", index=False)
            df_v = result_vpd.df
            if not df_v.empty:
                final_v = df_v.iloc[-1]
                sec_v = df_v[sec_col].dropna().iloc[-1] if sec_col in df_v.columns else None
                results.append({
                    "label": label_vpd,
                    "SEC": f"{sec_v:.4f}" if sec_v else "N/A",
                    "time_h": f"{final_v['time_h']:.1f}",
                    "W_comp_kWh": f"{final_v['W_comp_cum_kWh']:.2f}",
                    "W_fan_kWh": f"{final_v['W_fan_cum_kWh']:.2f}",
                    "m_water_kg": f"{final_v['m_w_cum_kg']:.2f}",
                })

    save_results(results, "F3_taplejung_E_configs.csv")
    return results


# ── Main ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--f1", action="store_true", help="Run F1 (effectiveness sensitivity)")
    parser.add_argument("--f2", action="store_true", help="Run F2 (timestep convergence)")
    parser.add_argument("--f3", action="store_true", help="Run F3 (Taplejung E-configs)")
    parser.add_argument("--all", action="store_true", help="Run all")
    args = parser.parse_args()

    run_all = args.all or not (args.f1 or args.f2 or args.f3)

    if args.f1 or run_all:
        run_F1_eps_sensitivity()
    if args.f2 or run_all:
        run_F2_dt_convergence()
    if args.f3 or run_all:
        run_F3_taplejung_E()

    print("\n" + "="*70)
    print("All requested simulations complete.")
    print("Results in: outputs/reviewer_sensitivity/")
    print("="*70)
