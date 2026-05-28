"""Print the K_eff parametric fit that the live SAHPD simulation actually consumes.

Builds a minimal KineticsConfig pointing at outputs/phase2c_for_chamber.csv
(via phase2_models_root) and calls the same _fit_parametric_keff that runs
at sim startup. Prints fitted Ea/R, K_ref, alpha_RH, gamma_v, delta_d alongside
the LOCO-CV baseline numbers from outputs/baseline/diagnostics/global_fit.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RQ1_ROOT = PROJECT_ROOT / "RQ1"
sys.path.insert(0, str(RQ1_ROOT / "src"))

from rq1.config import KineticsConfig
from rq1.kinetics import _fit_parametric_keff, get_keff_table


def main() -> None:
    phase2_root = RQ1_ROOT / "outputs"
    if not (phase2_root / "phase2c_for_chamber.csv").exists():
        raise SystemExit(f"phase2c_for_chamber.csv not found under {phase2_root}")

    cfg = KineticsConfig(
        phase2_models_root=phase2_root,
        T_C_ref=50.0,
        v_ms=1.1,
        thickness_mm=6.0,
        use_knb_table=True,
    )

    table = get_keff_table(cfg)
    print(f"K_eff table loaded with {len(table)} rows.")
    print(table[["T_C", "RH_mid_pct", "v_ms", "thickness_mm", "K_eff_1_per_s"]])

    params = _fit_parametric_keff(cfg)
    if params is None:
        raise SystemExit("Parametric fit returned None.")

    print("\n=== LIVE SIM PARAMETRIC FIT ===")
    print(f"  K_ref     = {params['K_ref']:.4e} 1/s")
    print(f"  Ea/R      = {params['Ea_over_R']:.1f} K")
    print(f"  alpha_RH  = {params['alpha_RH']:.3f}")
    print(f"  gamma_v   = {params['gamma_v']:.3f}")
    print(f"  delta_d   = {params['delta_d']:.3f}")
    print(f"  R^2 (lnK) = {params['R2']:.4f}")

    baseline_path = PROJECT_ROOT / "outputs" / "baseline" / "diagnostics" / "global_fit.json"
    if baseline_path.exists():
        bl = json.loads(baseline_path.read_text())
        print("\n=== LOCO-CV ARRHENIUS-MIDILLI BASELINE (full-data fit) ===")
        print(f"  A         = {bl['A_per_min_n']:.4e} min^-n")
        print(f"  Ea/R      = {bl['Ea_over_R']:.1f} K")
        print(f"  n0        = {bl['n0']:.3f}")
        print(f"  n_T       = {bl['n_T']:.4f} per K")
        print(f"  n_v       = {bl['n_v']:.3f} per m/s")
        print(f"  b0        = {bl['b0']:.4e}")
        print(f"  b_RH      = {bl['b_RH']:.4e}")
    else:
        print(f"\n(baseline JSON not found at {baseline_path})")

    # Ea_over_R_K constant in config_solar_hp.py was removed 2026-04-30:
    # Phase A audit (outputs/audit/phase_a_summary.json) confirmed it had
    # zero reads during a live 4 h Config A run, and the only consumer
    # (kinetics.get_K_eff_from_state) was deleted in the same change.


if __name__ == "__main__":
    main()
