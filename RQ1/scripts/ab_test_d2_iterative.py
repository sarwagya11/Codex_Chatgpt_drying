"""A/B test: D2 closed-form vs iterative evaporator supplement.

Runs Config D2 at three cells (Namche Q1 cold, Biratnagar Q3 humid monsoon,
Kathmandu Q2 mild) under the legacy closed-form ambient-supplement (the path
that has shipped through 2026-05-29) and under the fixed-point
_iterative_evap_sizing routine used by B1_open, B2_open, E2, E3.

Reports SEC, drying time, total compressor and fan energy, and the
m_amb_extra trajectory stats for each cell. Use the per-cell SEC delta to
decide whether the iterative path is worth shipping as the new D2 default.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rq1.config_solar_hp import make_config_D_HRX
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation

AMBIENT_DIR = ROOT / "data" / "ambient"

CELLS = [
    # label,                 csv,                                       elev,  start_idx (hr)
    ("namche_q1_jan15",      "namche_pvgis_standard_poa45.csv",         3440, 345),
    ("biratnagar_q3_jul15",  "biratnagar_pvgis_standard_poa45.csv",     72,   4689),
    ("kathmandu_q2_apr15",   "kathmandu_pvgis_standard_poa45.csv",      1350, 2505),
]


def _run(cell, use_iterative: bool):
    label, csv_name, elev, start_idx = cell
    cfg = make_config_D_HRX(
        ambient_csv=AMBIENT_DIR / csv_name,
        d_variant="D2",
        elevation_m=elev,
        display_geometry=False,
    )
    cfg.ambient.start_index = start_idx
    cfg.ambient.max_steps = 25
    cfg.dryer.use_iterative_evap_for_d2 = use_iterative
    return run_solar_hp_dryer_simulation(cfg)


def _summary(result):
    df = result.df
    sec = float(df["SEC_elec_kWh_per_kg"].iloc[-1])
    t_h = float(df["time_s"].iloc[-1]) / 3600.0
    w_comp = float(df["W_comp_cum_kWh"].iloc[-1])
    w_fan = float(df["W_fan_cum_kWh"].iloc[-1])
    m_amb = df["m_amb_extra_kg_per_s"]
    active = m_amb[m_amb > 0]
    return {
        "SEC": sec,
        "t_h": t_h,
        "W_comp_kWh": w_comp,
        "W_fan_kWh": w_fan,
        "max_m_amb": float(m_amb.max()),
        "mean_m_amb_active": float(active.mean()) if len(active) else 0.0,
        "frac_steps_active": float((m_amb > 0).mean()),
        "converged": bool(result.converged),
    }


def main() -> int:
    header = (
        f"{'cell':<22} {'mode':<11} {'SEC':>8} {'t_h':>6} {'W_comp':>8} "
        f"{'W_fan':>7} {'max_mamb':>10} {'avg_mamb':>10} {'frac':>6} {'conv':>5}"
    )
    print("=" * len(header))
    print(header)
    print("=" * len(header))

    deltas = []
    for cell in CELLS:
        per_mode = {}
        for mode in ("closed", "iterative"):
            res = _run(cell, use_iterative=(mode == "iterative"))
            s = _summary(res)
            per_mode[mode] = s
            print(
                f"{cell[0]:<22} {mode:<11} {s['SEC']:>8.4f} {s['t_h']:>6.2f} "
                f"{s['W_comp_kWh']:>8.4f} {s['W_fan_kWh']:>7.4f} "
                f"{s['max_m_amb']:>10.5f} {s['mean_m_amb_active']:>10.5f} "
                f"{s['frac_steps_active']:>6.1%} {str(s['converged']):>5}"
            )
        d_sec = per_mode["iterative"]["SEC"] - per_mode["closed"]["SEC"]
        d_t = per_mode["iterative"]["t_h"] - per_mode["closed"]["t_h"]
        sec_c = per_mode["closed"]["SEC"]
        d_pct = d_sec / sec_c * 100.0 if sec_c else 0.0
        deltas.append((cell[0], d_sec, d_pct, d_t))
        print(
            f"{cell[0]:<22} {'D(it-cl)':<11} {d_sec:>+8.4f} {d_t:>+6.2f}  "
            f"({d_pct:+.2f}% SEC)"
        )
        print("-" * len(header))

    print("\nVERDICT")
    print("-------")
    thresh_kwh = 0.019  # quarterly-mean SEC resolution from S4.4
    for lbl, d_sec, d_pct, d_t in deltas:
        flag = "MATERIAL" if abs(d_sec) > thresh_kwh else "below noise"
        print(f"  {lbl:<22} |Delta SEC| = {abs(d_sec):.4f} kWh/kg  ({flag})")
    print(f"\nThreshold: |Delta SEC| > {thresh_kwh} kWh/kg (quarterly resolution from S4.4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
