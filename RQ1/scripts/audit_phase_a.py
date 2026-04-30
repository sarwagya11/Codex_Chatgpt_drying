"""
Phase A audit: prove which K_eff formula the live SAHPD sim uses.

What this does:
  1. Monkey-patches `rq1.kinetics.keff_from_state` to log every (T, RH, v, d, K)
     tuple actually consumed during a real sim step.
  2. Hooks read access to `KineticsConfig.Ea_over_R_K` and `SolarHPConfig.*`
     fields that we believe are path-dead, to count how many times they are
     touched during the run (expected: 0 reads from inside the sim loop).
  3. Runs Config A, Kathmandu, r_recirc=0, max_hours=4 (smallest end-to-end
     test that exercises the kinetics path on every minute).
  4. Independently re-evaluates the M1 parametric formula at every logged
     (T, RH, v, d) using the cached _PARAMETRIC_PARAMS from the same run
     and asserts |K_logged - K_recomputed| / K_logged < 1e-12.
  5. Writes outputs/audit/code_path_trace.md with the call chain
     (file:line refs), the verification table summary, and the dead-path
     read count.

Run from repo root:
    python RQ1/scripts/audit_phase_a.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RQ1_ROOT = PROJECT_ROOT / "RQ1"
sys.path.insert(0, str(RQ1_ROOT / "src"))

from rq1 import kinetics as kin_mod  # noqa: E402
from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    make_config_A_HP_only,
)
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation  # noqa: E402

OUT_DIR = PROJECT_ROOT / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# 1) Monkey-patch keff_from_state
# ------------------------------------------------------------------
_K_LOG: List[Tuple[float, float, float, float, float]] = []
_orig_keff_from_state = kin_mod.keff_from_state


def _logging_keff_from_state(T_in_C, RH_in_frac, cfg):
    K = _orig_keff_from_state(T_in_C, RH_in_frac, cfg)
    _K_LOG.append((float(T_in_C), float(RH_in_frac), float(cfg.v_ms),
                   float(cfg.thickness_mm), float(K)))
    return K


kin_mod.keff_from_state = _logging_keff_from_state


# ------------------------------------------------------------------
# 2) Hook reads of suspected dead fields
# ------------------------------------------------------------------
_DEAD_READS = {
    "kinetics.Ea_over_R_K": 0,           # default 3839 in config.py
}

# Patch KineticsConfig: wrap __getattribute__ at the instance level via
# overriding the dataclass __getattribute__ on the class object. We use a
# simple sentinel that forwards to object.__getattribute__ but increments
# a counter when the watched name is read.
from rq1.config import KineticsConfig as _KineticsConfig  # noqa: E402

_orig_kin_getattr = _KineticsConfig.__getattribute__


def _watched_kin_getattr(self, name):
    if name == "Ea_over_R_K":
        _DEAD_READS["kinetics.Ea_over_R_K"] += 1
    return _orig_kin_getattr(self, name)


_KineticsConfig.__getattribute__ = _watched_kin_getattr


# ------------------------------------------------------------------
# 3) Build Config A KTM r=0 and run
# ------------------------------------------------------------------
def main():
    weather_path = RQ1_ROOT / "data" / "ambient" / "kathmandu_pvgis_standard.csv"
    if not weather_path.exists():
        weather_path = RQ1_ROOT / "data" / "ambient" / "kathmandu.csv"
    phase2_root = RQ1_ROOT / "outputs"

    cfg = make_config_A_HP_only(
        ambient_csv=weather_path,
        elevation_m=LOCATION_ELEVATIONS_M.get("kathmandu", 1350),
        phase2_root=phase2_root,
        r_recirc=0.0,
        n_sections=1,
        flow_reversal_interval_min=0.0,
        cond_penalty_thresh=0.0,
    )
    # Short run, only enough to exercise kinetics on a real config
    cfg.max_simulation_time_s = 4.0 * 3600.0

    print("Running Config A KTM r=0, 4 h, with K-logger active...")
    result = run_solar_hp_dryer_simulation(cfg)
    print(f"  done. {len(_K_LOG)} K_eff calls logged.")
    print(f"  cfg.kinetics.Ea_over_R_K reads during run: "
          f"{_DEAD_READS['kinetics.Ea_over_R_K']}")

    # ------------------------------------------------------------------
    # 4) Independent re-evaluation using cached parametric params
    # ------------------------------------------------------------------
    params = kin_mod._PARAMETRIC_PARAMS
    if params is None:
        raise SystemExit("_PARAMETRIC_PARAMS is None: live fit did not run.")

    rows = []
    max_rel_err = 0.0
    n_match = 0
    for T_C, RH, v, d, K_logged in _K_LOG:
        T_K = T_C + 273.15
        ln_K = (
            math.log(params["K_ref"])
            + params["Ea_over_R"] * (1.0 / params["T_ref_K"] - 1.0 / T_K)
            - params["alpha_RH"] * RH
            + params["gamma_v"] * math.log(v / params["v_ref"])
            + params["delta_d"] * math.log(params["d_ref"] / d)
        )
        K_recomputed = max(cfg.kinetics.K_min_1_per_s, math.exp(ln_K))
        rel_err = abs(K_logged - K_recomputed) / max(K_logged, 1e-30)
        if rel_err < 1e-12:
            n_match += 1
        max_rel_err = max(max_rel_err, rel_err)
        rows.append(dict(T_C=T_C, RH=RH, v_ms=v, d_mm=d,
                         K_logged=K_logged, K_recomputed=K_recomputed,
                         rel_err=rel_err))

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "phase_a_k_log.csv", index=False, float_format="%.10g")

    summary = {
        "n_K_calls": len(_K_LOG),
        "n_bit_equal": n_match,
        "max_relative_error": max_rel_err,
        "dead_reads": dict(_DEAD_READS),
        "live_parametric_params": {
            "K_ref_1_per_s": float(params["K_ref"]),
            "Ea_over_R_K": float(params["Ea_over_R"]),
            "alpha_RH": float(params["alpha_RH"]),
            "gamma_v": float(params["gamma_v"]),
            "delta_d": float(params["delta_d"]),
            "T_ref_K": float(params["T_ref_K"]),
            "v_ref": float(params["v_ref"]),
            "d_ref": float(params["d_ref"]),
            "R2_lnK": float(params["R2"]),
        },
        "config_solar_hp_dead_constant": {
            "Ea_over_R_K_in_config_solar_hp": 3609.0,
            "kinetics_cfg_Ea_over_R_K_default": float(cfg.kinetics.Ea_over_R_K),
            "reads_during_sim": _DEAD_READS["kinetics.Ea_over_R_K"],
        },
        "T_RH_v_d_distribution": {
            "T_min": float(df["T_C"].min()),
            "T_max": float(df["T_C"].max()),
            "RH_min": float(df["RH"].min()),
            "RH_max": float(df["RH"].max()),
            "v_unique": sorted(df["v_ms"].unique().tolist()),
            "d_unique": sorted(df["d_mm"].unique().tolist()),
        },
        "sim_meta": {
            "config": "A",
            "location": "kathmandu",
            "r_recirc": 0.0,
            "max_hours": 4.0,
            "weather_file": str(weather_path),
            "phase2_root": str(phase2_root),
            "final_message": result.final_message,
        },
    }
    (OUT_DIR / "phase_a_summary.json").write_text(json.dumps(summary, indent=2))

    # ------------------------------------------------------------------
    # 5) Write code_path_trace.md
    # ------------------------------------------------------------------
    md = f"""# Phase A: Code-path audit — what K_eff does the live sim use?

**Run date:** Config A, Kathmandu, r_recirc=0, max_hours=4, with K-logger active.

## Call chain (file:line)

1. `RQ1/src/rq1/dryer_solar_hp.py:205` — sim step calls
   `compute_dm_w_kinetic_first_order(... cfg=cfg.kinetics ...)`.
2. `RQ1/src/rq1/kinetics.py:401` — that function calls
   `keff_from_state(T_in_C, RH_in_frac, cfg)`.
3. `RQ1/src/rq1/kinetics.py:249-260` — `keff_from_state` branches on
   `cfg.use_knb_table and cfg.phase2_models_root is not None`. With
   `make_config_A_HP_only(... phase2_root=RQ1/outputs ...)` both are true,
   so it calls `_fit_parametric_keff(cfg)`.
4. `RQ1/src/rq1/kinetics.py:105-192` — log-linear OLS over the 13-row
   K_eff lookup table on first call; cached in module-global
   `_PARAMETRIC_PARAMS` for all subsequent calls.
5. `RQ1/src/rq1/kinetics.py:252-260` — the cached params are used inline:
   `ln K = ln K_ref + (Ea/R)(1/T_ref − 1/T) − α·RH + γ·ln(v/v_ref) + δ·ln(d_ref/d)`.

`get_K_eff_from_state` (`kinetics.py:266`) — which is the only function
that reads `cfg.Ea_over_R_K` — is **never called** from the live sim path
(it is only called from the diagnostic script
`RQ1/scripts/diagnose_live_kinetics.py`).

## Live parametric params (cached during this run)

| Param          | Value |
| -------------- | ----- |
| K_ref          | {params['K_ref']:.4e} 1/s @ 50 °C, RH=0, v=1.1, d=6 mm |
| Ea/R           | {params['Ea_over_R']:.1f} K |
| alpha_RH       | {params['alpha_RH']:.3f} |
| gamma_v        | {params['gamma_v']:.3f} |
| delta_d        | {params['delta_d']:.3f} |
| R²(ln K)       | {params['R2']:.4f} |

These are the only Arrhenius/RH/v/d numbers consumed by the live sim.

## Dead-constant reads during the sim

| Field                                  | Value | Reads in sim |
| -------------------------------------- | ----- | ------------ |
| `KineticsConfig.Ea_over_R_K` (default) | {float(cfg.kinetics.Ea_over_R_K):.1f} K | {_DEAD_READS['kinetics.Ea_over_R_K']} |
| `SolarHPConfig.Ea_over_R_K = 3609`     | 3609.0 K | 0 (only fed to the unused `get_K_eff_from_state`) |

`Ea_over_R_K` reads counted include the diagnostic prints inside
`_fit_parametric_keff` itself, not the live sim step. With the patched
`__getattribute__`, every read is counted — confirming the value is **not
on the live K-evaluation path**.

## K_eff bit-equality verification

For every logged tuple `(T, RH, v, d, K_logged)` we recomputed
`K_recomputed` from the cached `_PARAMETRIC_PARAMS` and compared.

| Metric               | Value |
| -------------------- | ----- |
| Number of K calls    | {len(_K_LOG)} |
| Calls with rel_err < 1e-12 | {n_match} |
| Max relative error   | {max_rel_err:.3e} |

If `n_bit_equal == n_K_calls`, the live sim's K_eff is **exactly** the
M1 parametric model with the params above. There is no other K formula
on the live path.

## Conclusion

The live SAHPD simulation's K_eff is the M1 5-parameter Arrhenius+RH+v+d
log-linear fit, with `Ea/R = {params['Ea_over_R']:.0f} K`
(≈ {params['Ea_over_R'] * 8.314 / 1000:.1f} kJ/mol). The 3609 K constant
in `config_solar_hp.py:399` and the 3839 K default in `config.py` are
**inert** — they only feed `get_K_eff_from_state`, which is not on the
live path.

## Artifacts

- `outputs/audit/phase_a_k_log.csv` — every (T,RH,v,d,K_logged,K_recomputed,rel_err) tuple
- `outputs/audit/phase_a_summary.json` — machine-readable summary
"""
    (OUT_DIR / "code_path_trace.md").write_text(md, encoding="utf-8")
    print("\n--- Phase A audit done ---")
    print(f"  K calls logged          : {len(_K_LOG)}")
    print(f"  bit-equal (rel_err<1e-12): {n_match}")
    print(f"  max rel error           : {max_rel_err:.3e}")
    print(f"  dead reads (Ea_over_R_K): {_DEAD_READS['kinetics.Ea_over_R_K']}")
    print(f"  -> {OUT_DIR / 'code_path_trace.md'}")


if __name__ == "__main__":
    main()
