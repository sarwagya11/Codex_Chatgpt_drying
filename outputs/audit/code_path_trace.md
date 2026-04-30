# Phase A: Code-path audit — what K_eff does the live sim use?

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
| K_ref          | 1.6344e-04 1/s @ 50 °C, RH=0, v=1.1, d=6 mm |
| Ea/R           | 2711.2 K |
| alpha_RH       | 1.750 |
| gamma_v        | 0.442 |
| delta_d        | 0.656 |
| R²(ln K)       | 0.8977 |

These are the only Arrhenius/RH/v/d numbers consumed by the live sim.

## Dead-constant reads during the sim

| Field                                  | Value | Reads in sim |
| -------------------------------------- | ----- | ------------ |
| `KineticsConfig.Ea_over_R_K` (default) | 3609.0 K | 0 |
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
| Number of K calls    | 2410 |
| Calls with rel_err < 1e-12 | 2410 |
| Max relative error   | 0.000e+00 |

If `n_bit_equal == n_K_calls`, the live sim's K_eff is **exactly** the
M1 parametric model with the params above. There is no other K formula
on the live path.

## Conclusion

The live SAHPD simulation's K_eff is the M1 5-parameter Arrhenius+RH+v+d
log-linear fit, with `Ea/R = 2711 K`
(≈ 22.5 kJ/mol). The 3609 K constant
in `config_solar_hp.py:399` and the 3839 K default in `config.py` are
**inert** — they only feed `get_K_eff_from_state`, which is not on the
live path.

## Artifacts

- `outputs/audit/phase_a_k_log.csv` — every (T,RH,v,d,K_logged,K_recomputed,rel_err) tuple
- `outputs/audit/phase_a_summary.json` — machine-readable summary
