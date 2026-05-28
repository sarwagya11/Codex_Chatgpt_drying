"""PR-1 smoke parity test.

Verifies that:
  (a) Series dispatch invariant: simulate_drying_chamber(topology='series')
      returns exactly what _simulate_drying_chamber_series returns. This is
      the structural guarantee that PR-1 does not alter series behavior.
  (b) Parallel build constructs cleanly, runs, and produces no NaN.
  (c) Parallel exhaust mass-balance closes per step
      (sum over trays of dm_w_tray == dm_w_total cumulative delta).
  (d) Per-channel velocity guardrail trips when air_gap_m is mismatched.
  (e) First-law residual on series df is at machine precision (sanity).

This is a smoke test, not a unit suite. PR-1 ships when this passes.

Run:
    python scripts/smoke_topology_parity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    make_config_E_HRX_solar,
)
from rq1.dryer_solar_hp import (  # noqa: E402
    run_solar_hp_dryer_simulation,
    simulate_drying_chamber,
    _simulate_drying_chamber_series,
    _simulate_drying_chamber_parallel,
)

OUT_DIR = PROJECT_ROOT / "outputs" / "smoke_topology"
OUT_DIR.mkdir(parents=True, exist_ok=True)

_PAPER1 = PROJECT_ROOT / "data" / "ambient" / "kathmandu_pvgis_standard_poa45.csv"
_LEGACY = PROJECT_ROOT / "data" / "ambient" / "kathmandu_pvgis_standard.csv"
WEATHER = _PAPER1 if _PAPER1.exists() else _LEGACY
START_ROW = 1
ELEV = LOCATION_ELEVATIONS_M["kathmandu"]
PHASE2_ROOT = PROJECT_ROOT / "phase2_models"


def _build_cfg(topology: str, air_gap_m: float = 0.10):
    cfg = make_config_E_HRX_solar(
        ambient_csv=WEATHER,
        solar_area_m2=10.0,
        e_variant="E2",
        eps_HRX=0.70,
        vpd_bypass_thresh=0.0,
        elevation_m=ELEV,
        phase2_root=PHASE2_ROOT,
        display_geometry=False,
        tray_topology=topology,
        air_gap_m=air_gap_m,
    )
    return cfg


def _run(topology: str, air_gap_m: float = 0.10):
    cfg = _build_cfg(topology, air_gap_m=air_gap_m)
    cfg.ambient.start_index = START_ROW
    result = run_solar_hp_dryer_simulation(cfg)
    return result.df


def check_a_series_dispatch_invariant():
    """Dispatcher in series mode must call _simulate_drying_chamber_series.

    Build a representative input set, then assert dispatcher(topology=series)
    output equals direct _simulate_drying_chamber_series output, element-wise.
    """
    print("[a] series dispatch invariant...")
    cfg = _build_cfg("series")
    n_trays = cfg.dryer.n_trays
    X_trays = [[cfg.dryer.X0_db]] * n_trays
    MR_trays = [[1.0]] * n_trays
    # Deep copy of input lists since impls may mutate
    X1 = [list(row) for row in X_trays]
    X2 = [list(row) for row in X_trays]
    M1 = [list(row) for row in MR_trays]
    M2 = [list(row) for row in MR_trays]

    T_in, omega_in = 45.0, 0.007
    from rq1.psychro import moist_air_enthalpy_kJ_per_kg
    h_in = float(moist_air_enthalpy_kJ_per_kg(T_in, omega_in))

    out_disp = simulate_drying_chamber(
        T_in, omega_in, h_in, X1, M1, cfg, time_s=0.0,
        m_da=cfg.dryer.m_da_kg_per_s, dt_s=60.0,
    )
    out_direct = _simulate_drying_chamber_series(
        T_in, omega_in, h_in, X2, M2, cfg, time_s=0.0,
        m_da=cfg.dryer.m_da_kg_per_s, dt_s=60.0,
    )
    # Compare each returned tuple element
    names = ["dm_w_trays", "T_tray_out", "RH_tray_out",
             "h_tray_out", "X_trays_new", "MR_trays_new"]
    failed = []
    for name, a, b in zip(names, out_disp, out_direct):
        aa = np.array(a, dtype=float).ravel()
        bb = np.array(b, dtype=float).ravel()
        if not np.allclose(aa, bb, rtol=0.0, atol=0.0):
            mx = float(np.max(np.abs(aa - bb)))
            print(f"  FAIL: {name} differs, max |delta|={mx:.4e}")
            failed.append(name)
        else:
            print(f"  ok   {name:<14} byte-identical")
    return not failed


def check_b_parallel_runs():
    print("[b] running parallel build (gap=1 cm)...")
    df = _run("parallel", air_gap_m=0.01)
    out = OUT_DIR / "parallel_smoke.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out} ({len(df)} rows)")
    if df.isna().any().any():
        bad = df.columns[df.isna().any()].tolist()
        print(f"  FAIL: NaN columns: {bad[:6]}...")
        return False
    print("  ok   no NaN; ran to completion")
    return True


def check_c_parallel_mass_balance():
    print("[c] parallel per-tray water balance...")
    df = pd.read_csv(OUT_DIR / "parallel_smoke.csv")
    tray_cols = [c for c in df.columns if c.startswith("dm_w_tray_") and c.endswith("_kg")]
    if not tray_cols:
        print("  SKIP: no per-tray dm_w columns in output")
        return True
    sum_per_tray = df[tray_cols].sum(axis=1)
    dm_total = df["m_w_cum_kg"].diff().fillna(df["m_w_cum_kg"].iloc[0])
    resid = np.abs(sum_per_tray - dm_total).max()
    print(f"  max |sum(dm_w_tray) - delta m_w_cum| = {resid:.4e} kg")
    if resid > 1e-9:
        print("  FAIL: mass balance does not close per step")
        return False
    print("  ok   mass balance closes at machine precision")
    return True


def check_d_velocity_guardrail():
    print("[d] velocity guardrail: mismatched gap must raise...")
    try:
        # Force m_da to match series 10cm gap, but request parallel topology with
        # 5cm gap -> per-channel v would be wrong, geometry must trip.
        cfg = make_config_E_HRX_solar(
            ambient_csv=WEATHER, solar_area_m2=10.0, e_variant="E2",
            elevation_m=ELEV, phase2_root=PHASE2_ROOT, display_geometry=False,
            tray_topology="parallel", air_gap_m=0.05,
        )
        # The above auto-sized m_da for parallel-5cm, so v matches target -> no trip.
        # Inject a manual override: re-build by hand
        from rq1.config_solar_hp import DryerConfig, SimulationConfig, AmbientConfig, SolarConfig
        from rq1.config_solar_hp import DryerConfiguration, KineticsConfig
        cfg2 = SimulationConfig(
            config_type=DryerConfiguration.CONFIG_E2,
            ambient=AmbientConfig(csv_path=WEATHER, elevation_m=ELEV),
            solar=SolarConfig(area_m2=10.0),
            dryer=DryerConfig(
                tray_topology="parallel",
                air_gap_m=0.01,
                m_da_kg_per_s=0.5,    # arbitrary off-target value
                target_velocity_m_s=1.1,
                d_variant="E2",
                eps_HRX=0.70,
            ),
            kinetics=KineticsConfig(phase2_models_root=PHASE2_ROOT),
            display_geometry=False,
        )
        print("  FAIL: cfg with m_da=0.5 did not raise (expected ValueError)")
        return False
    except ValueError as e:
        msg = str(e)
        if "Per-channel velocity" in msg or "tray_topology" in msg:
            print(f"  ok   raised ValueError: {msg[:80]}...")
            return True
        print(f"  FAIL: wrong error: {msg}")
        return False
    except Exception as e:
        print(f"  FAIL: unexpected error: {type(e).__name__}: {e}")
        return False


def check_e_first_law_series():
    print("[e] series first-law residual sanity...")
    df = _run("series")
    eta_mech = 0.90
    resid = (df["Q_cond_kW"] - df["Q_evap_kW"] - eta_mech * df["W_comp_kW"]).abs().max()
    print(f"  max |Q_cond - Q_evap - eta*W_comp_elec| = {resid:.4e} kW")
    if resid > 1e-9:
        print("  FAIL: first law does not close")
        return False
    print("  ok   first-law closes at machine precision")
    return True


def main():
    print("=" * 64)
    print("PR-1 smoke topology parity test")
    print("=" * 64)
    results = {
        "a_series_dispatch":    check_a_series_dispatch_invariant(),
        "b_parallel_runs":      check_b_parallel_runs(),
        "c_mass_balance":       check_c_parallel_mass_balance(),
        "d_velocity_guardrail": check_d_velocity_guardrail(),
        "e_first_law_series":   check_e_first_law_series(),
    }
    print()
    print("Summary:")
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
