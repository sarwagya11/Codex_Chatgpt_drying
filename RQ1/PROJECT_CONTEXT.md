# RQ1 — Solar-Assisted Heat-Pump Dryer (SAHPD): Project Context

**Version:** 4.0 (full rewrite, 2026-04-20)
**Scope:** Apple-slice drying in Nepal; ten configurations (A, B, C1, C2, D1, D2, D3, E1, E2, E3); two locations (Kathmandu, Biratnagar) plus Taplejung seasonal; annual and three seasonal TMY splits.
**Status:** Phase 4 in progress. All six physics checks passed on 2026-04-09.

This document is the single canonical description of what the code actually does. It supersedes the earlier v3.x `PROJECT_CONTEXT.md` (which described an older 5-config, T_set = 50°C, 10 kg set-up). Every claim below is pinned to a specific module and function in `src/rq1/`.

---

## 1. Problem Statement

Dry 3.0 kg of apple dry-mass (≈ 22.5 kg fresh at X0 = 6.5 db) from X0 = 6.5 kg-water/kg-dry to X_f = 0.10 kg-water/kg-dry using a heat-pump dryer optionally coupled with a flat-plate solar collector and a counter-flow heat-recovery exchanger (HRX). Compare ten airside-topology variants on energy cost (SEC), drying time, and specific moisture extraction rate (SMER).

Product and operating envelope (in `DryerConfig`, `src/rq1/config_solar_hp.py`):

| Quantity | Value | Source |
|---|---|---|
| Dry mass m_p_dry | 3.0 kg | `DryerConfig.m_p_dry_kg` |
| Trays | 10 | `DryerConfig.n_trays` |
| Initial / target moisture | 6.5 / 0.10 db | `X0_db`, `X_final_db` |
| Target temperature T_set | 45 °C | `DryerConfig.T_set_C` |
| Target air velocity | 1.1 m/s | `DryerConfig.target_velocity_m_s` |
| Product slab thickness | 6 mm | `DryerConfig.product_thickness_m` |
| Sections per tray | 1 (default) | `DryerConfig.n_sections` |
| Timestep | 60 s | `DryerConfig.dt_s` |
| Simulation horizon | ≤ 72 h | `SimulationConfig.max_simulation_time_s` |

Locations (`LOCATION_ELEVATIONS_M` in `scripts/run_solar_hp_configs.py`):

| Location | Elevation | P_atm (computed) |
|---|---|---|
| Kathmandu | 1350 m | ≈ 86.3 kPa |
| Biratnagar | 72 m | ≈ 100.5 kPa |
| Taplejung | 1820 m | ≈ 81.3 kPa |

---

## 2. Configuration Catalogue

Enum `DryerConfiguration` in `src/rq1/config_solar_hp.py` enumerates the ten simulated air-side topologies. Each config has a dedicated simulator in `src/rq1/dryer_solar_hp.py`.

| Code | Name | Air path (condenser stream) | Evaporator source | Recirc |
|------|------|------------------------------|-------------------|--------|
| A  | HP only | (1−r)·Amb + r·Exh → Evap → Cond → Chamber | in-line | r ∈ [0, 1] |
| B  | Solar + HP series | Mix → Evap → Solar → Cond → Chamber | in-line | r ≥ 0 |
| C1 | Solar cascade, mix before solar | Mix → Solar → Cond → Chamber; Evap fed by solar | separate stream (m_evap_stream) | r ≥ 0 (r = 0 typical) |
| C2 | Solar cascade, mix after solar | Solar → Mix → Cond → Chamber; Evap fed by solar | separate stream | r ≥ 0 |
| D1 | HRX + HP, ambient evap | Amb → HRX (cold) → Cond → Chamber; Exh → HRX (hot) → expelled; Evap: ambient | ambient | r = 0 |
| D2 | HRX + HP, mixed evap | Amb → HRX → Cond → Chamber; Evap: cooled-exhaust + ambient make-up | dynamic mix | r = 0 |
| D3 | HRX swapped | Exh → HRX → Cond → Chamber; Amb → HRX → Evap (humidity risk) | HRX-cooled ambient | r = 0 |
| E1 | HRX + Solar + HP, ambient evap | Amb → HRX → Solar → Cond → Chamber; Evap: ambient | ambient | r = 0 |
| E2 | HRX + Solar + HP, mixed evap | Amb → HRX → Solar → Cond → Chamber; Evap: exhaust + ambient make-up | iterative mix | r = 0 |
| E3 | HRX + Solar **after** condenser, solar-priority | Amb → HRX → Cond → Solar → Chamber; HP off when solar alone reaches T_set | exhaust + ambient | r = 0 |

Factories: `make_config_A_HP_only`, `make_config_B_solar_HP_series`, `make_config_C1_solar_cascade_mix_before`, `make_config_C2_solar_cascade_mix_after`, `make_config_D_HRX`, `make_config_E_HRX_solar`.

---

## 3. Governing Physics

### 3.1 Psychrometrics (`src/rq1/psychro.py`)

* Saturation pressure: Tetens, `p_sat(T_C)` → Pa.
* Humidity ratio from dry-bulb + RH: `ω = 0.622 · p_v / (P_atm − p_v)`.
* Moist-air enthalpy (base 0 °C): `h = 1.006·T + ω·(2501 + 1.86·T)` kJ/kg-dry-air (`moist_air_enthalpy_kJ_per_kg`). The constant 2501 is h_fg(0 °C), correct for enthalpy bookkeeping in this reference frame. (Do not confuse with the latent-heat constant `DryerConfig.h_fg_kJ_per_kg` used for water-mass-balance bookkeeping; that one is set to the 45 °C value, 2394.8 kJ/kg.)
* Dry-bulb recovery from (h, ω): `temperature_from_h_omega_C`.
* Dewpoint: `dewpoint_from_omega_C(ω, P)` (inverse Tetens).

### 3.2 Heat-pump cycle (`src/rq1/heatpump.py`)

R134a is used throughout (changed from R410A on 2026-03-23 because R410A is a two-component blend whose saturation envelope complicates simple CoolProp calls, and it is phased down under the Kigali amendment). CoolProp handles refrigerant properties.

* Open-loop sizing (`size_heat_pump_for_air_heating`): T_cond = T_set + 10 K; T_evap = T_source − 10 K; limits T_evap ∈ [T_evap_min, T_evap_max], T_cond ≤ T_cond_max, pressure ratio ≤ 10.
* Closed-loop (r > 0) first-law-enforced path: given the air-side condenser duty, the evaporator duty closes from Q_cond = Q_evap + W_shaft with η_is = 0.75, η_mech = 0.95, superheat 5 K, subcooling 5 K.
* Heat-exchanger effectiveness: ε_cond = 0.85 and ε_evap = 0.85 (`HeatPumpConfig`).
* Evaporator strategy (default): fixed T_evap_target = 5 °C. An opt-in `"onset-tracking"` variant ties T_evap to the mixed-air dewpoint minus 2/3/5 K depending on MR phase; **no thesis run uses it.**

### 3.3 Solar collector (`src/rq1/solar.py`)

Hottel-Whillier-Bliss model with the F_R factor recovered from a UA-based NTU formulation:

```
Q_abs  = A · (τα · G − U_L · (T_in − T_amb))       [W]
F_R    = (m·cp / (U_L·A)) · (1 − exp(− U_L·A·F'/(m·cp)))
Q_out  = F_R · Q_abs                               [W, useful]
T_out  = T_in + Q_out / (m·cp)
```

Defaults in `SolarConfig`: τα = 0.80, U_L = 6.0 W/m²·K, F' = 0.95, area from caller. No thermal inertia (quasi-steady at each timestep); GHI from TMY CSV.

### 3.4 Heat-recovery exchanger (`_compute_HRX` in `dryer_solar_hp.py`)

Counter-flow plate HRX, ε = 0.70 (`DryerConfig.eps_HRX`), sensible-only:

```
Q_HRX      = ε · m·cp_min · (T_exh − T_amb)
T_cold_out = T_amb + Q_HRX / (m·cp_cold)
T_hot_out  = T_exh − Q_HRX / (m·cp_hot)
```

Moisture is assumed impermeable through the plate, so ω is unchanged on both streams across the HRX.

### 3.5 Chamber model (`simulate_drying_chamber` called from each config simulator)

Cross-flow, trays-in-series: air enters at (T_to_chamber, ω_to_chamber), passes Tray 0 → ... → Tray 9, leaving as exhaust. Each tray is divided into `n_sections` along airflow (default 1 for thesis runs). For each tray-section at each dt:

1. Effective drying rate `K_eff` from kinetics (§3.6).
2. Instantaneous water removal `dm_w = K_eff · (X − X_eq) · m_dry · dt`, clipped by
   (a) the local air capacity (ω_sat(T_air) − ω_air)·m_da·dt, and
   (b) `X` not falling below `X_eq` (GAB).
3. Sensible energy balance: latent load h_fg·dm_w cools the air; sensible exchange with product is neglected (thin slab, short dt).
4. Air-state handoff: outlet (T, ω) of section i = inlet of section i+1.

Exhaust (T_exhaust, ω_exhaust) is the last section's outlet. It feeds back to t+dt with a 300 s exponential smoother to represent duct/chamber thermal inertia.

### 3.6 Drying kinetics (`src/rq1/kinetics.py`)

Parametric Midilli fitted to the 13-row `outputs/phase2c_for_chamber.csv` dataset (`_fit_parametric_keff`, log-linear OLS):

```
K_eff(T, RH, v, d) = K_ref · exp(Ea/R · (1/T_ref − 1/T))
                           · exp(−α_RH · RH)
                           · (v / v_ref)^γ_v
                           · (d_ref / d)^δ_d
MR(t) = exp(−(K_eff · t)^n) · exp(−b·t)       (Midilli form)
```

Fitted values at T_ref = 45 °C: K_ref ≈ 1.63e-4 /s, Ea/R = 2711 K, **α_RH = 1.75**, γ_v = 0.442, δ_d = 0.656, R² = 0.90. The runtime path `keff_from_state` always uses this parametric fit (the `alpha_RH` field in `KineticsConfig`, now 1.75, is a dead fallback only reached when `use_knb_table=False`, which never occurs in thesis runs). Validity bounds T ∈ [30, 70] °C and RH ∈ [10, 90] % are enforced.

GAB sorption isotherm (apple) provides X_eq(T, RH); drying stops when X approaches X_eq.

### 3.7 Fan power (`compute_fan_power_kW`)

Quasi-static electrical fan power:

```
W_fan = m_da · (ΔP_evap + ΔP_cond + ΔP_duct + Σ K_bend · 0.5·ρ·v²) / (ρ · η_fan)
```

η_fan = 0.60. Pressure drops: ΔP_evap = ΔP_cond = 80 Pa, ΔP_duct = 50 Pa, K_bend = 2.0 for 180° serpentine turns.

---

## 4. Control Strategies

### 4.1 Recirculation (Configs A, B, C1, C2)

Fixed recirculation ratio r ∈ [0, 1] supplied by the user (`DryerConfig.r_recirc`). Closed-loop (r > 0) mixes exhaust with ambient at the evaporator inlet; open-loop (r = 0) uses ambient only. The previously-documented dynamic recirculation modes (`dynamic-max`, `dynamic-proportional`, `r_max_dynamic`, `recirc_mode`) were deleted on 2026-04-20 (they had been shown to be equivalent to or worse than fixed r = 0.9).

### 4.2 VPD-based condenser-direct bypass (Configs A, B)

When the fraction of VPD "lost" to evaporator dehumidification drops below `cond_penalty_thresh` (typical 0.05), the controller routes exhaust directly to the condenser for a physics-based humidity-accumulation dwell (`compute_humidity_dwell_s`), then switches back when the penalty grows to 3× threshold. Implemented per-step in each simulator; oscillates at ≈ 10-15 min cycle. Minimum dwell 600 s, 3× hysteresis band to avoid chatter.

### 4.3 VPD exhaust bypass (Configs D1, D2, E1, E2)

Same oscillating logic but on the *exhaust* side for HRX-equipped configs: low VPD utilisation bypasses the HRX-ambient path and routes exhaust straight back to the condenser. Controlled by `DryerConfig.vpd_bypass_thresh`, `--vpd-threshold 0.05` on the CLI. **D3 and E3 do not expose a VPD bypass by design** (D3 already routes exhaust through HRX to the condenser stream; E3 uses solar-priority control that preempts any bypass decision).

### 4.4 Iterative evaporator sizing (Configs E2, E3)

`_iterative_evap_sizing` solves the fixed-point problem that arises when the evaporator sees a mix of chamber exhaust and ambient make-up whose ratio depends on the evaporator duty itself. Fallback to the legacy closed-form expression only when the iteration fails (never observed in the thesis runs).

### 4.5 Solar-priority control (Config E3)

E3 places the collector *after* the condenser so the solar gain can finish the temperature lift. If `T_cond_out_if_HP_off + Q_solar/(m·cp) ≥ T_set`, the compressor is switched off for that step; otherwise the HP provides a variable partial lift (T_cond chosen so that the combined cond+solar output equals T_set). Fully implemented in `simulate_config_E3_HRX_solar_after_cond`.

---

## 5. Inputs, Outputs, Runners

### 5.1 Weather

* Annual TMY: `data/ambient/<location>_pvgis_standard.csv` (PVGIS hourly).
* Seasonal splits produced by `scripts/split_seasons.py`: `data/ambient/seasonal/<loc>_<season>.csv` for `autumn_oct_nov`, `winter_dec_jan`, `spring_mar_apr`.
* Each row supplies T_amb_C, RH_amb_pct, GHI_Wm2, time_s.

### 5.2 Core runners

* `scripts/run_solar_hp_configs.py` — single-run CLI (`--config`, `--location`, `--solar-area`, `--recirc-values`, `--vpd-threshold`, `--cond-threshold`, `--weather-file`, `--max-hours`).
* `scripts/run_all_thesis_simulations.py` — master batch (240 jobs: 3 locations × {annual + 3 seasons} × 10 configs × selected VPD variants + E2 area sweep).
* `scripts/make_master_summary.py` — aggregates all config CSVs into `outputs/master_summary.csv`.

### 5.3 Output tree

```
outputs/
  config_<letter>/<location>/<season?>/<filename>.csv
  master_summary.csv
  run_summary.csv            # last runner invocation
  phase2c_for_chamber.csv    # kinetics training data
  plots/…                    # figures
```

Column contract per simulator CSV includes `t_s`, `T_amb_C`, `RH_amb_pct`, `omega_amb`, `T_to_chamber_C`, `omega_to_chamber`, `T_exhaust_C`, `omega_exhaust`, `MR_avg`, `W_comp_kW`, `Q_cond_kW`, `Q_evap_kW`, `Q_solar_kW` (if solar), `Q_HRX_kW` (if HRX), plus config-specific diagnostics (`T_evap_sat`, `cond_penalty_frac`, `vpd_utilisation`, bypass flags).

---

## 6. Validation Status (2026-04-09)

All six first-principles checks on the six representative cases (A_r0, A_r0.9, B_10m2, D2, E2_10m2, E2_10m2_VPD): **PASS**.

1. First law at the HP: |Q_cond − Q_evap − W_shaft| < 1e-6 kW every step.
2. Air-side water balance: Σdm_w(trays) = Σ ρ·(ω_in − ω_out)·V̇·dt, error < 1e-6 kg cumulative.
3. Psychrometric self-consistency: recomputed ω and RH from (T, h) match stored state < 4e-6.
4. Condenser effectiveness: T_to_chamber matches ε-NTU with ε_cond = 0.85 exactly.
5. COP 3.5-4.8 and Carnot efficiency 0.61-0.62 (consistent with η_is = 0.75).
6. No frost / impossible-cycle flags triggered.

All configs reach T_to_chamber = 45 °C, so **differences between configs reduce to energy cost, not drying kinetics**.

---

## 7. Known Model Limitations (paper-level)

These are flagged both here and as IDEA-tagged items in `GAME_PLAN.md` §0.

1. **Quasi-steady solar collector** — no thermal mass, no cloud-cover transient. Over-reacts on minute-scale GHI flicker (the 60 s timestep largely averages this out).
2. **No thermal energy storage** — a solar-only daytime dryer with evening HP-off would need a buffer; mention as retrofit in discussion.
3. **No refrigerant mass inventory / startup transients** — HP treated as instant-on each step, no compressor cycling losses.
4. **No air leakage or infiltration** — chamber treated as a sealed duct.
5. **No product shrinkage** — slab thickness fixed at 6 mm; real apple contracts ~30-40 %.
6. **Sensible-only HRX** — plate is modelled moisture-impermeable; real plate HRX at > 80 % RH exhaust may show minor latent recovery.
7. **No experimental validation of MR(t) or SEC** — no apple drying experiments run yet; all curves are model-derived. Flagged as V2/V4 paper limitations.
8. **Kinetics fit R² = 0.90** — 13 training runs, 5 parameters; extrapolation beyond 30-60 °C, 10-90 % RH, 4-10 mm not recommended.
9. **Electricity-only SEC** — does not include embodied energy of solar collector or HRX.
10. **Single-inlet chamber** — multi-zone / flow-reversal only partially wired (`flow_reversal_interval_min` is exposed, not exercised in thesis runs).

---

## 8. File Map

```
src/rq1/
  config_solar_hp.py    # DryerConfiguration, SimulationConfig, AmbientConfig,
                        # SolarConfig, HeatPumpConfig, DryerConfig, KineticsConfig,
                        # make_config_{A, B, C1, C2, D_HRX, E_HRX_solar}
  dryer_solar_hp.py     # 10 simulate_config_* functions + _compute_HRX,
                        # _evaporator_dehumidify, _iterative_evap_sizing,
                        # compute_cond_penalty_est, compute_vpd_utilization,
                        # compute_humidity_dwell_s, simulate_drying_chamber
  heatpump.py           # compute_heat_pump_cycle, size_heat_pump_for_air_heating
  psychro.py            # p_sat, humidity_ratio_from_T_RH, moist_air_enthalpy_kJ_per_kg,
                        # dewpoint_from_omega_C, temperature_from_h_omega_C
  solar.py              # compute_solar_collector (HWB + F_R NTU)
  kinetics.py           # _fit_parametric_keff, keff_from_state, K_eff_from_T_RH (fallback)
  chamber_geometry.py   # tray layout and cross-section bookkeeping

scripts/
  run_solar_hp_configs.py         # single-run CLI
  run_all_thesis_simulations.py   # 240-job batch
  split_seasons.py                # annual TMY → seasonal splits
  make_master_summary.py          # aggregate all outputs
  verify_energy_balance.py        # §6 validation
  plot_*.py, batch_plot.py        # plotting helpers

outputs/
  master_summary.csv
  phase2c_for_chamber.csv
  config_<X>/<loc>/<season?>/*.csv
  plots/…
```

---

## 9. Revision Log

* 2026-04-20 — v4.0 full rewrite to match current code (10 configs, T_set = 45 °C, m_p_dry = 3.0 kg, R134a, α_RH = 1.75, h_fg at 45 °C, dynamic recirc removed).
* 2026-04-11 — Seasonal KTM E2/E3 runs added.
* 2026-04-09 — Phase 3.5 validation: all six checks passed.
* 2026-04-08 — E2/E3 iterative-evap sizing fix (fixed-point algorithm).
* 2026-03-31 — D2 dynamic ambient compensation.
* 2026-03-23 — Refrigerant R410A → R134a.
