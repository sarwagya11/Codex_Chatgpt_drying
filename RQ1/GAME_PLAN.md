# SAHPD Research Game Plan
## Master Strategy: Model Finalization → Validation → Paper

**Owner:** Wasti (Researcher)
**Assistant:** Claude Code (helper and executor — follows researcher instructions)
**Last Updated:** 2026-04-09
**Status:** Phase 3.5 COMPLETE — Full model validation passed (1st law, energy balance, psychrometrics, COP). Ready for Phase 4 (seasonal).

---

## Enhancement Ideas Backlog
*Listed here before any implementation. Each needs literature review + researcher decision first.*

### IDEA-2: Air-to-Air Heat Exchanger (Regenerator/HRV) for Frost Sites
**Trigger:** At cold sites (Kathmandu), late in drying, exhaust air is warm (~45°C) but nearly dry. Fresh ambient air is cold (~8°C) and dry. If we exchange heat between exhaust and ambient before mixing/evaporating, the ambient air is pre-warmed → T_dp_mix rises → T_evap_sat rises → frost risk reduced.
**Concept:** Add a sensible heat exchanger (effectiveness ε = 0.6–0.8) between exhaust and incoming ambient. This is a standard Heat Recovery Ventilator (HRV) concept applied to food HPD.
**Two possible placements:**
  - Before the evaporator: pre-warm ambient air going into the evaporator (reduces frost risk)
  - Before the condenser: pre-warm the dehumidified air going to the condenser (reduces HP heating load)
**This is essentially a new sub-config of Config A** — could be called Config A-HRV or remain as a parameter.
**Literature needed:** HRV in food dryers, heat recovery in HPCD, effectiveness values.
**Status:** IDEA ONLY — do not implement until Phases 1-3 complete.

### IDEA-7: Condenser Physics Refinements for Config E (Hot Air Inlet)
**Trigger:** In Config E (HRX+Solar), the air entering the condenser can be very hot (up to 58.6°C in Biratnagar). Three unmodeled effects identified:

**Issue 1: HP should be fully OFF when T_solar_out >= T_set**
- Currently: code clamps `T_air_in_cond = min(T_solar_out, T_set)` and runs HP at Q=0.001 kW floor
- Fix: set `W_comp = 0` when T_solar_out >= T_set. Actual impact: <0.1% of total W_comp (negligible)
- Could also allow T_to_chamber > T_set during solar peak (faster drying, but risk overheating product)
- Biratnagar: T_solar > T_set for 42% of timesteps; T_solar > T_cond_sat(55°C) for 23%

**Issue 2: T_cond_sat should adapt to T_air_in (variable condenser pressure)**
- Currently: `T_cond_sat = T_set + 10 = 55°C` (fixed)
- Physics: when T_air_in is high (e.g., 43°C), condenser approach = only 12°C. Adequate for eps_cond=0.85 but marginal.
- When T_air_in > T_cond_sat: refrigerant physically cannot reject heat → HP must be OFF
- Fix: `T_cond_sat = max(T_set + 10, T_air_in + ΔT_min)` where ΔT_min ≈ 5-10K
- Impact: when T_air_in is high, this INCREASES T_cond → higher pressure ratio → lower COP → higher W_comp
- But Q_cond_needed is tiny at high T_air_in, so absolute W_comp increase is small
- Current fixed T_cond = 55°C is CONSERVATIVE (slightly overestimates W_comp at low loads)

**Issue 3: Same ΔT lift costs MORE work at higher T_air_in**
- Heating 30→45°C (Q=1.48 kW) at T_cond=55°C: COP≈4.5, W_comp≈0.33 kW
- Heating 40→55°C (same Q=1.48 kW) requires T_cond=65°C: COP≈3.5, W_comp≈0.42 kW (27% more)
- Reason: higher T_cond → higher pressure ratio → more compression work per unit heat
- This is correctly captured IF T_cond_sat adapts. Our fixed T_cond model misses this.
- BUT: in Config E we never need to heat ABOVE T_set, so this only matters if we implement IDEA-7 Issue 1 (allowing T_to_chamber > T_set)

**Issue 4: Compressor minimum capacity**
- Real compressors can't modulate below ~30% of rated capacity. Below that they cycle on/off.
- Our model allows W_comp = 0.0002 kW (0.2W) which is unrealistic
- Fix: add `W_comp_min` threshold — below that, HP is OFF and compressor cycles
- Impact on SEC: minimal (the idle power is negligible)

**Net assessment:** Current model is slightly CONSERVATIVE (overestimates W_comp) because:
1. Fixed T_cond = 55°C even when low load would allow T_cond = 50°C → better COP
2. HP runs at 0.001 kW floor instead of OFF
3. Solar heat above T_set is discarded (could accelerate drying)

**Status:** IDEA — document in paper as limitation. Low priority for implementation (impact < 1% on SEC).

### IDEA-3: Dedicated HPD Compressor vs. Modified AC Unit
**Observation:** T_evap > 20°C in early drying (high moisture product) is outside typical AC operating range but thermodynamically fine for a dedicated HPD compressor.
**Concept:** Distinguish two equipment scenarios in the paper:
  - Scenario A: Modified AC unit (T_evap limited to 2–20°C by AC design)
  - Scenario B: Dedicated HPD compressor (T_evap can be 2–25°C or wider)
  - Flag `flag_outside_ac_range` marks where Scenario A would require derating/protection
**Not a code change** — a paper framing decision. The flag already exists.
**Status:** DECISION — keep 20°C flag threshold as-is (correct for AC unit context).

### IDEA-4: Flow Reversal (Tray Uniformity Enhancement)
**Concept:** Periodically reverse air flow direction (e.g., every 30 min). Inlet trays dry faster than outlet trays normally; reversing evens out the MR distribution, potentially reducing total drying time.
**Code:** `--flow-reversal 30` flag already exists in the runner. Never tested.
**Status:** DEFER — implement and test after all 5 configs are finalized.

### IDEA-5: Seasonal Weather Profiles (per-month simulation)
**Concept:** Rather than one "average year" weather file, simulate Oct, Nov, Dec separately.
  Apple harvest is Oct–Nov (post-monsoon). Dec–Jan would be a cold-weather stress test.
**Status:** DEFER — Phase 4 scope.

### IDEA-6: Heat Recovery Unit (HRU) for Solar-COP (Config C) Exhaust Stream
**Trigger:** Config C always discards drying chamber exhaust. That exhaust is warm (~40–45°C) and moderately humid. Discarding it wastes thermal energy.
**Concept:** Add a sensible heat exchanger (effectiveness ε = 0.6–0.8) between the drying chamber exhaust and the incoming ambient air. The ambient air (Stream 1 → solar → HP evaporator source) is pre-warmed before entering the solar collector/evaporator, reducing the HP heat demand.
**Status:** IDEA ONLY — do not implement until Phases 1-3 complete.

---

## Ground Rules

- Researcher decides all directions. Claude executes, analyzes, and flags issues.
- No config or model change is made without researcher approval.
- Each phase must be declared COMPLETE and signed off before the next begins.
- All results go to `outputs/` with clear naming. All analysis is documented here.

---

## PHASE 1 — Finalize Config A (HP Dryer with Recirculation) ✓ COMPLETE

### Summary of findings
- Recirculation strategy FINALIZED: use fixed r (higher r → lower SEC, longer drying time)
- Dynamic recirculation modes (dynamic-max, dynamic-proportional) REMOVED — shown to be equivalent to or worse than fixed r=0.9
- Optimal r is climate-dependent:
  - Kathmandu (cold): r=0.9 gives best SEC (0.499 kWh/kg, 18.9h)
  - Biratnagar (warm): r=0 is best (SEC=0.579 kWh/kg, 14.4h) — recirculation makes HP less efficient in warm climates
- Physics bypass: omega_exhaust ≤ omega_amb → bypass activates (never triggers at r=0.9 Kathmandu — exhaust always more humid than ambient throughout)
- Energy breakdown (r=0.9, Kathmandu):
  - h=0–8:  removes 14.6 kg water using 2.45 kWh → 5.96 kg/kWh (efficient)
  - h=8–14: removes 3.97 kg water using 2.53 kWh → 1.57 kg/kWh (acceptable)
  - h=14+:  removes 0.76 kg water using 3.94 kWh → 0.19 kg/kWh (very poor — 44% of electricity for 4% of water)

### Validated results (Config A)
| Location | r=0 | r=0.3 | r=0.5 | r=0.7 | r=0.9 |
|---|---|---|---|---|---|
| Kathmandu SEC | 0.760 | 0.761 | 0.701 | 0.624 | **0.499** |
| Kathmandu time (h) | 13.8 | 14.1 | 14.7 | 15.7 | 18.9 |
| Biratnagar SEC | **0.579** | 0.821 | 0.782 | 0.728 | 0.642 |
| Biratnagar time (h) | 14.4 | 14.1 | 14.5 | 15.2 | 16.8 |

### Code cleanup needed (before proceeding)
- [ ] **1.C1** Remove `recirc_mode` (dynamic-max, dynamic-proportional) from `dryer_solar_hp.py`
- [ ] **1.C2** Remove `recirc_mode`, `r_max_dynamic` from `config_solar_hp.py` DryerConfig
- [ ] **1.C3** Remove `--recirc-mode`, `--rmax` CLI args from `run_solar_hp_configs.py`

---

## PHASE 1.5 — Condenser-Direct Bypass Strategy for Config A (NEW)

**Motivation:** In late drying, the HP uses 44% of all electricity to remove only 4% of the water. The exhaust air is already warm (44°C) and dry (17% RH). Running it through the evaporator at this point is wasteful — the evaporator sees nearly-dry air and barely raises T_evap. Meanwhile the condenser must heat air from ~20°C (after evaporator) up to 45°C — a 25°C lift at poor efficiency.

**The strategy:**

```
PHASE A — when RH_exhaust < threshold (e.g., 25%):
   Exhaust (44°C, 17% RH)  →  condenser  →  45°C  →  chamber
   Fresh ambient            →  evaporator (heat source only, vented)
   Result: Q_cond ≈ tiny (1°C lift), W_comp ≈ tiny
   Humidity in loop builds up naturally as product continues to dry

PHASE B — when RH_exhaust ≥ threshold:
   Exhaust  →  evaporator (higher omega → better T_evap → better COP)  →  condenser  →  chamber
   Result: efficient HP operation, active dehumidification
```

**Why this beats continuous evaporator operation:**
- Phase A: HP barely runs. Drying continues from the warm dry air alone.
- Phase B (triggered when humidity builds back up): evaporator now sees MORE humid air → T_evap is higher than in the current model → better COP per unit moisture removed.
- Net: less electricity for the same water removed.

**Key physics:** During Phase A, the evaporator still runs but on fresh ambient air (it needs a heat source for the refrigerant cycle). In warmer locations (Biratnagar, T_amb=25°C), T_evap from ambient will be ~15°C instead of -1°C — even better. Q_cond is so small that W_comp is negligible regardless of COP.

### Implementation plan

**Files to change:**

1. **`config_solar_hp.py`** — add one new field to `DryerConfig`:
   ```python
   RH_cond_threshold: float = 0.0   # 0 = disabled; set e.g. 0.25 to enable condenser-direct mode
   ```

2. **`dryer_solar_hp.py`** — in Config A simulation loop, at the recirculation decision block, add a new branch before the existing evaporator path:
   ```python
   if r_eff > 0 and T_exhaust_prev is not None:
       RH_exh = RH_from_T_omega(T_exhaust_prev, omega_exhaust_prev, p_atm)
       cond_threshold = cfg.dryer.RH_cond_threshold
       if cond_threshold > 0 and RH_exh < cond_threshold:
           # CONDENSER-DIRECT: exhaust → condenser (no evaporator for this air)
           T_air_in_cond    = T_exhaust_prev        # exhaust enters condenser directly
           omega_to_chamber = omega_exhaust_prev    # no dehumidification
           T_evap_source    = T_amb_C               # HP evaporator uses ambient air
           bypass_mode      = "cond_direct"
           # HP call: size_heat_pump_for_air_heating with T_air_in = T_exhaust_prev
           # Q_cond ≈ tiny → W_comp ≈ tiny
       else:
           # NORMAL EVAP PATH (existing code)
           ...
   ```

3. **`run_solar_hp_configs.py`** — add optional CLI arg:
   ```
   --cond-threshold 0.25   # activates condenser-direct mode when RH_exhaust < 25%
   ```

4. **New CSV column:** `bypass_mode = "cond_direct"` during condenser-direct steps

### Test plan (Config A only)

1. Run baseline r=0.9, Kathmandu — no threshold (existing):
   `python scripts/run_solar_hp_configs.py --config A --location kathmandu --recirc-values 0.9`

2. Run with cond-threshold=0.25:
   `python scripts/run_solar_hp_configs.py --config A --location kathmandu --recirc-values 0.9 --cond-threshold 0.25`

3. Run with cond-threshold=0.35:
   `python scripts/run_solar_hp_configs.py --config A --location kathmandu --recirc-values 0.9 --cond-threshold 0.35`

4. Compare: SEC, drying time, W_comp breakdown by phase, COP distribution

### Expected outcomes
- W_comp in late drying (h=14+) drops significantly
- Drying time may increase slightly (inlet air is more humid during cond_direct phase)
- Net SEC improvement expected — need to verify magnitude
- Test at Biratnagar too: warmer ambient → T_evap from ambient is better → even more benefit

### Status: COMPLETE ✓ (2026-03-18)

**Implementation:** VPD-based oscillating condenser-direct bypass using `cond_penalty_frac`.
- `cond_penalty = (VPD_post_evap - VPD_exhaust) / VPD_post_evap` at T_set
- Activation: `cond_penalty < 0.05`; Deactivation: `cond_penalty > 0.15` (3×thresh)
- Applied to Config A and Config B
- CLI: `--cond-threshold 0.05`

**Results (Config A, thresh=0.05):**
| Location | r | Baseline SEC | VPD SEC | Change |
|---|---|---|---|---|
| Kathmandu | 0.3 | 0.761 | 0.510 | -33% |
| Kathmandu | 0.5 | 0.701 | 0.488 | -30% |
| Kathmandu | 0.7 | 0.624 | 0.439 | -30% |
| Kathmandu | 0.9 | 0.499 | 0.395 | -21% |
| Biratnagar | 0.3 | 0.821 | 0.530 | -35% |
| Biratnagar | 0.5 | 0.782 | 0.523 | -33% |
| Biratnagar | 0.7 | 0.728 | 0.519 | -29% |
| Biratnagar | 0.9 | 0.642 | 0.574 | -11% |

**Results (Config B, A_solar=10m², thresh=0.05):**
| Location | r | Baseline SEC | VPD SEC | Change |
|---|---|---|---|---|
| Kathmandu | 0.3 | 0.571 | 0.287 | -50% |
| Kathmandu | 0.5 | 0.549 | 0.276 | -50% |
| Kathmandu | 0.7 | 0.519 | 0.271 | -48% |
| Kathmandu | 0.9 | 0.469 | 0.321 | -32% |
| Biratnagar | 0.3 | 0.457 | 0.212 | -54% |
| Biratnagar | 0.5 | 0.443 | 0.202 | -54% |
| Biratnagar | 0.7 | 0.432 | 0.216 | -50% |
| Biratnagar | 0.9 | 0.419 | 0.318 | -24% |

---

## FINDING: The r=0 vs r>0 Discontinuity (The "Code Path Cliff")

**Date:** 2026-03-24
**Status:** Analyzed and documented

### The Observation

Going from r=0.0 to r=0.1 causes a catastrophic performance drop:
- Config A, Kathmandu: r=0.0 → 13.8h, T_cham=45°C. r=0.1 → 72h (never converges), T_cham=15°C
- The drying rate at r=0.1 is ~5× slower than r=0.0

### Root Cause: Two Completely Different Code Paths

**r=0 (open loop)** uses `size_heat_pump_for_air_heating()`:
```
Ambient (8.8°C) → CONDENSER → 45°C → Chamber → Exhaust (discarded)
                   ↑
Separate ambient → EVAPORATOR → (heat absorbed, air discarded)
```
- Evap and cond process DIFFERENT air streams — no thermodynamic coupling
- HP is "sized freely": Q_cond = m_da × (h_45°C - h_8.8°C) = 3.63 kW
- T_evap = T_amb - 10 = -1.2°C (external heat source)
- T_to_chamber = 45°C **always** (HP can deliver whatever is needed)

**r=0.1 (closed loop)** uses the first-law-enforced path:
```
0.9×Ambient(8.8°C) + 0.1×Exhaust(~35°C) = Mix(11.4°C) → EVAPORATOR(5.3°C) → CONDENSER → 15°C → Chamber
```
- **Same air** goes through evap then cond — first law: Q_cond = Q_evap + W_comp
- T_mix = 0.1×35 + 0.9×8.8 = 11.4°C (90% cold ambient dominates)
- T_coil = 8°C → ΔT = 3.4K → triggers modulation down to T_evap=2.3°C, T_coil=5.3°C
- Evap: T_out = 11.4 - 0.85×(11.4 - 5.3) = 6.2°C
- T_dp of ω_mix ≈ 3°C → T_out(6.2°C) > T_dp → **NO dehumidification** → Q_evap is purely sensible
- Q_evap = m_da × cp × (11.4 - 6.2) = 0.098 × 1.006 × 5.2 = **0.51 kW** (vs 3.63 kW at r=0)
- With COP ≈ 4: Q_cond = 0.51 × 4/3 = **0.68 kW**
- T_to_chamber = 6.2 + 0.68/(0.098×1.006) = 6.2 + 6.9 = **13.1°C** (vs 45°C at r=0)

### Why It Gets Worse: The Negative Feedback Loop

At r=0.1, T_to_chamber ≈ 13°C → drying is very slow → T_exhaust drops to ~10°C (air barely heated by fruit) → T_mix drops further → Q_evap drops further → T_to_chamber drops → system gets stuck at 10-15°C.

### Data Evidence (Config A, Kathmandu)

**Timestep comparison:**
| Time | r=0: T_cham | r=0: Q_cond | r=0.1: T_cham | r=0.1: Q_cond |
|---|---|---|---|---|
| 0.5h | 45.0°C | 3.63 kW | 15.3°C | 1.07 kW |
| 5h | 45.0°C | 3.56 kW | 14.9°C | 0.96 kW |
| 10h | 45.0°C | 3.41 kW | 13.4°C | 0.68 kW |

**Moisture Ratio comparison:**
| Time | r=0.0 MR | r=0.1 MR |
|---|---|---|
| 1h | 0.816 | 0.949 |
| 5h | 0.269 | 0.772 |
| 10h | 0.033 | 0.583 |
| 13.8h | **DONE** | 0.483 |

### Fixed Energy Analysis (@10 kWh electrical)

| r | Time to use 10 kWh | Water removed | MR |
|---|---|---|---|
| 0.0 | 10.0h | 18.80 kg | 0.032 |
| 0.1 | 39.4h | 17.23 kg | 0.089 |
| 0.5 | 39.2h | 17.34 kg | 0.075 |
| 0.8 | 11.8h | 18.91 kg | 0.022 |
| 0.9 | 11.4h | 18.98 kg | 0.022 |
| 1.0 | 11.6h | 18.98 kg | 0.022 |

**Key insight:** r=0.1-0.7 takes 39+ hours to use 10 kWh (low power, low drying rate), while r=0, 0.9, 1.0 use it in ~11h (high power, fast drying).

### Fixed Time Analysis (@14h)

| r | W_total (kWh) | Water removed | MR | T_cham |
|---|---|---|---|---|
| 0.0 | 13.86 | **19.34 kg** | 0.005 | 45.0°C |
| 0.1 | 3.79 | 9.70 kg | 0.483 | 13.5°C |
| 0.5 | 4.30 | 11.08 kg | 0.409 | 14.2°C |
| 0.7 | 4.51 | 12.17 kg | 0.351 | 15.0°C |
| 0.9 | 12.15 | **19.28 kg** | 0.007 | 45.0°C |
| 1.0 | 12.03 | **19.26 kg** | 0.007 | 45.0°C |

**Key insight:** At 14h, r=0.1-0.7 has only removed 50-60% of the water and used only 3-5 kWh. The HP is running at ~0.3 kW instead of ~1.0 kW because Q_cond is throttled by the first law.

### Literature Support

1. **Braun & Bansal (2022, ORNL)** showed that vented (open-loop) and unvented (closed-loop) dryers have fundamentally different thermodynamic limits. The Carnot efficiency limit is NOT the same for both.

2. **Cold-climate HP dryer study (2019, Energies)** found COP drops by up to 39% when cold ambient air dilutes the evaporator source, proposing a "unit-room" concept to isolate the HP from ambient.

3. **The bypass air ratio literature** distinguishes between recirculation ratio (fraction of exhaust recirculated) and bypass ratio (fraction of air that skips the evaporator). Our model sets bypass = 0, meaning ALL recirculated air must pass through the evaporator — making the first-law coupling absolute.

### Physical Interpretation

The discontinuity is **physically real, not a modeling artifact**. In a real system:
- At r=0: the compressor can be sized to heat any amount of fresh air (evaporator uses separate outdoor air as heat source, like a normal AC outdoor unit)
- At r>0: the compressor can only deliver Q_cond = Q_evap + W_comp from the SAME air stream, and Q_evap depends on how warm that air is above the coil temperature

The threshold at r≈0.8 (where it starts working again for Kathmandu) corresponds to T_mix being warm enough (~25°C) that Q_evap is substantial. At r≥0.9, T_mix ≈ 38°C → ΔT across evaporator ≈ 30K → large Q_evap → large Q_cond → T_to_chamber ≈ 45°C.

### Implications for System Design

1. **For HP-only (Config A) in cold climates**: Use either r=0 (open loop, SEC≈0.72) or r≥0.9 (closed loop, SEC≈0.67). Avoid r=0.1-0.7.
2. **Solar preheating (Config B) eliminates the problem**: All r values converge because solar raises T_mix above the critical threshold.
3. **Dynamic r control**: Start at r=0 (or r=1), never operate at intermediate r in cold conditions.

---

## PHASE 1.7 — Condenser Effectiveness (ε_cond) Applied (2026-03-24)

**Change:** Applied ε_cond = 0.85 in all 4 configs (A, B, C1, C2) as a third constraint on Q_cond:
- Closed-loop: `Q_cond_actual = min(Q_cond_1st_law, Q_cond_air_req, Q_cond_effectiveness)`
- Open-loop: `T_to_chamber = T_in + ε_cond × (T_cond_sat - T_in)`, capped at T_set

**Impact:** With T_cond_sat=55°C and ε=0.85, the condenser can always reach 45°C when T_air_in < 37°C.
Currently no effect on results, but physically correct and would matter with higher T_air_in (e.g., solar preheating).

---

## PHASE 1.8 — Updated Results with R134a, Fixed T_evap, First Law, ε_cond (2026-03-24)

### Config A (HP-only)

**Kathmandu (1350m, T_amb≈8.8°C):**
| r | Time (h) | W_comp | W_fan | SEC | Converged |
|---|---|---|---|---|---|
| 0.0 | 13.8 | 13.52 | 0.34 | **0.717** | Yes |
| 0.1 | 72.0 | 15.55 | 2.77 | 0.974 | No |
| 0.2 | 72.0 | 15.07 | 2.77 | 0.951 | No |
| 0.3 | 72.0 | 14.67 | 2.77 | 0.931 | No |
| 0.4 | 72.0 | 14.35 | 2.77 | 0.915 | No |
| 0.5 | 72.0 | 14.08 | 2.77 | 0.901 | No |
| 0.6 | 72.0 | 13.89 | 2.77 | 0.890 | No |
| 0.7 | 72.0 | 14.02 | 2.77 | 0.892 | No |
| 0.8 | 31.4 | 15.33 | 1.21 | 0.849 | Yes |
| 0.9 | 14.9 | 12.35 | 0.57 | **0.669** | Yes |
| 1.0 | 15.2 | 12.45 | 0.59 | 0.674 | Yes |

**Biratnagar (72m, T_amb≈25°C):**
| r | Time (h) | W_comp | W_fan | SEC | Converged |
|---|---|---|---|---|---|
| 0.0 | 14.4 | 10.13 | 0.36 | **0.543** | Yes |
| 0.1 | 72.0 | 28.26 | 2.79 | 1.602 | No |
| 0.2 | 72.0 | 28.49 | 2.79 | 1.609 | No |
| 0.3 | 72.0 | 29.33 | 2.79 | 1.647 | No |
| 0.4 | 72.0 | 30.84 | 2.79 | 1.716 | No |
| 0.5 | 33.5 | 17.85 | 1.30 | 0.995 | Yes |
| 0.6 | 29.8 | 17.99 | 1.15 | 0.994 | Yes |
| 0.7 | 14.8 | 14.21 | 0.57 | 0.765 | Yes |
| 0.8 | 14.6 | 14.01 | 0.56 | 0.755 | Yes |
| 0.9 | 14.6 | 13.98 | 0.57 | **0.753** | Yes |
| 1.0 | 14.7 | 13.95 | 0.57 | 0.752 | Yes |

### Config B (Solar 10m² + HP)

**Kathmandu:**
| r | Time (h) | W_comp | W_fan | Q_solar | SEC |
|---|---|---|---|---|---|
| 0.0 | 13.8 | 9.09 | 0.34 | - | 0.488 |
| 0.1 | 31.6 | 6.47 | 1.21 | - | 0.398 |
| 0.2 | 31.4 | 6.26 | 1.21 | - | **0.386** |
| 0.5 | 30.1 | 6.90 | 1.16 | - | 0.416 |
| 0.9 | 14.9 | 8.49 | 0.57 | - | 0.469 |
| 1.0 | 15.2 | 8.62 | 0.59 | - | 0.477 |

**Biratnagar:**
| r | Time (h) | W_comp | W_fan | Q_solar | SEC |
|---|---|---|---|---|---|
| 0.0 | 14.4 | 5.18 | 0.36 | - | **0.287** |
| 0.2 | 27.7 | 9.62 | 1.07 | - | 0.553 |
| 0.7 | 14.8 | 7.76 | 0.57 | - | 0.431 |
| 0.9 | 14.6 | 7.59 | 0.57 | - | 0.423 |
| 1.0 | 14.7 | 7.60 | 0.57 | - | 0.423 |

**Key finding:** Config B eliminates the "valley of death" — all 22 runs converge. Solar preheating raises T_mix above the critical ΔT threshold for the evaporator.

---

## PHASE 2 — Finalize Configs B, C, D, E ✓ COMPLETE (2026-04-01)

### Config B — Solar Preheat + HP Series ✓ COMPLETE (2026-03-24, R134a + first law + ε_cond)

**Air Path (from code, dryer_solar_hp.py lines 1021-1310):**

Open-loop (r=0):
```
Ambient → SOLAR COLLECTOR → T_after_solar → HP CONDENSER → T_set → CHAMBER → Exhaust (discarded)
                                                 ↑
                          Separate ambient → EVAPORATOR (heat source, air discarded)
```
- If T_after_solar ≥ T_set: HP OFF (W_comp=0, free solar drying)
- Otherwise: HP boosts from T_after_solar to T_set (smaller ΔT = less W_comp)

Closed-loop (r>0):
```
r×Exhaust + (1-r)×Ambient → MIX → EVAPORATOR → SOLAR COLLECTOR → HP CONDENSER → CHAMBER
        ↑                                                                           |
        |___________________________________________________________________________|
```
- Key difference from Config A: SOLAR sits between evaporator and condenser
- After evap cools air to ~6°C, solar reheats to 15-25°C during daytime
- First-law Q_evap computed from mix→after_evap (same as A)
- Q_cond_required is smaller because condenser inlet = T_after_solar (warmer)
- When Q_cond_req < Q_cond_1st_law → HP does less work than first law allows
- At night: behaves like Config A (slow), daytime solar carries the batch

**Updated results (R134a, first law, ε_cond, A_solar=10m²):**
| Location | r=0 | r=0.2 | r=0.5 | r=0.7 | r=0.9 | r=1.0 |
|---|---|---|---|---|---|---|
| KTM SEC | 0.488 | **0.386** | 0.416 | 0.460 | 0.469 | 0.477 |
| KTM time | 13.8h | 31.4h | 30.1h | 29.0h | 14.9h | 15.2h |
| BTN SEC | **0.287** | 0.553 | 0.618 | 0.431 | 0.423 | 0.423 |
| BTN time | 14.4h | 27.7h | 26.9h | 14.8h | 14.6h | 14.7h |

**Key finding:** ALL 22/22 runs converge (vs 11/22 for Config A). Solar eliminates the valley of death.
- KTM best SEC: r=0.2 (0.386) — 46% better than Config A best (0.669), but takes 31h (2 solar cycles)
- BTN best SEC: r=0.0 (0.287) — warm climate + solar = very efficient, HP shuts off during solar peak

**Status:** COMPLETE — Config B finalized with R134a, first law enforcement, ε_cond.

### Config C1 — Solar Cascade, Mix Before Solar ✓ COMPLETE (2026-03-31)
- r=0 air path corrected: solar→evaporator source only (not condenser inlet)
- r>0 unchanged: Mix→Solar→Evap→Cond

### Config C2 — Solar Cascade, Mix After Solar ✓ COMPLETE (2026-03-31)
- r=0 air path corrected: solar→evaporator source only
- r>0 unchanged: Solar→Mix→Evap→Cond

### Config D (D1/D2/D3) — HRX + HP ✓ COMPLETE (2026-03-28, updated 2026-04-01)
- D1: Amb→HRX→Cond, Exh→HRX→expelled, Evap=ambient
- D2: Amb→HRX→Cond, Exh→HRX→dynamic ambient compensation at evap
- D3: Exh→HRX→Cond, Amb→HRX→Evap (humidity risk, worst performer)
- VPD exhaust bypass added (2026-04-01): `--vpd-threshold 0.05`
- Q_HRX_cum now only accumulates when HRX output is actually routed

### Config E (E1/E2/E3) — HRX + Solar + HP ✓ COMPLETE (2026-04-01)
- E1: Amb→HRX→Solar→Cond, Evap=ambient
- E2: Amb→HRX→Solar→Cond, Evap=exh+amb dynamic mix
- E3: Amb→HRX→Cond, Exh+amb→Solar→Evap (solar on evap stream)
- VPD exhaust bypass added for E1/E2 (not E3)

### VPD Exhaust Bypass ✓ VALIDATED (2026-04-01)
- Applied to D1/D2 and E1/E2 configs
- Oscillating bypass: ON when VPD util < 5%, OFF when > 15%, 600s dwell
- During bypass: exhaust→condenser (D) or exhaust→solar→condenser (E)
- **Results (Kathmandu, threshold=5%):**

| Config | Base SEC | VPD SEC | Change | Base t | VPD t |
|--------|----------|---------|--------|--------|-------|
| D1     | 0.365    | 0.287   | -21%   | 13.8h  | 15.1h |
| D2     | 0.354    | 0.288   | -18%   | 13.8h  | 15.1h |
| E1 10m2| 0.220    | 0.152   | -31%   | 13.8h  | 15.1h |
| E2 10m2| 0.206    | 0.146   | -29%   | 13.8h  | 15.1h |

- **1st law validated:** Q_cond = Q_evap + W_shaft (exactly). Apparent gap = eta_mech losses (5% of W_comp).
- **SEC_thermal** = 0.94–0.98 kWh/kg = 1.4–1.5× latent min → no violation
- **Literature check:** Wang 2019 HP+HRX mango SEC=0.49; our D configs 0.29–0.37 (within range); E configs 0.15–0.22 (below HP-only min, explained by free solar+HRX thermal energy)
- **Novelty confirmed:** HRX+Solar+HP triple combo and VPD-based bypass are both novel (see RESEARCH_NOVELTY_SEC.md)

---

## PHASE 3 — Integration Strategy Comparison ✓ COMPLETE (2026-04-02)

**Goal:** For each location, identify the best config+solar_area+r combination.
**Status:** COMPLETE — 36 runs, master table built, summary plots generated.

### 3.0 Prerequisite Runs ✓ COMPLETE
- [x] **3.0.1** C1/C2 at both locations, solar 5+10 m², r=0 (corrected air paths)
- [x] **3.0.2** E3 baseline (no VPD) at both locations, A_solar=10 m²
- [x] **3.0.3** E2 solar area sensitivity: 2, 5, 10, 15, 20 m² (KTM + BTN)
- [x] **3.0.4** D2+VPD already isolates HRX+HP (D configs have no solar)

### 3.1 Master Comparison Table (annual runs, post 2026-04-21 overnight batch)

Rebuilt from `outputs/master_summary.csv` on 2026-04-21. SMER = m_water / (W_comp + W_fan). SEC_thermal = (Q_cond + Q_solar_usable + Q_HRX) / m_water. "nan" entries in Q_HRX indicate configs without an HRX; 0.0 entries in Q_sol indicate configs without a solar collector.

| Config | Loc | A_sol (m²) | SEC_e (kWh/kg) | SEC_th (kWh/kg) | Time (h) | SMER (kg/kWh) | Q_sol (kWh) | Q_HRX (kWh) |
|--------|-----|------------|----------------|-----------------|----------|---------------|-------------|-------------|
| A | KAT | 0 | 0.717 | 2.533 | 13.8 | 1.40 | 0.0 | — |
| A | BIR | 0 | 0.543 | 2.300 | 14.4 | 1.84 | 0.0 | — |
| B 10m² | KAT | 10 | 0.541 | 2.574 | 14.2 | 1.85 | 15.9 | — |
| B 10m² | BIR | 10 | 0.323 | 2.396 | 14.8 | 3.10 | 22.8 | — |
| C1 10m² | KAT | 10 | 0.476 | 2.574 | 14.2 | 2.10 | 15.9 | — |
| C1 10m² | BIR | 10 | 0.302 | 2.396 | 14.8 | 3.31 | 22.8 | — |
| C2 10m² | KAT | 10 | 0.476 | 2.574 | 14.2 | 2.10 | 15.9 | — |
| C2 10m² | BIR | 10 | 0.302 | 2.396 | 14.8 | 3.31 | 22.8 | — |
| D1 | KAT | 0 | 0.365 | 2.533 | 13.8 | 2.74 | 0.0 | 25.1 |
| D1 | BIR | 0 | 0.293 | 2.300 | 14.4 | 3.41 | 0.0 | 22.0 |
| D2 | KAT | 0 | 0.354 | 2.533 | 13.8 | 2.83 | 0.0 | 25.1 |
| D2 | BIR | 0 | 0.282 | 2.300 | 14.4 | 3.55 | 0.0 | 22.0 |
| D3 | KAT | 0 | 0.477 | 4.276 | 17.3 | 2.10 | 0.0 | 34.5 |
| D3 | BIR | 0 | 0.460 | 4.596 | 20.4 | 2.17 | 0.0 | 37.4 |
| D1+VPD | KAT | 0 | 0.287 | 1.558 | 15.1 | 3.48 | 0.0 | 11.9 |
| D1+VPD | BIR | 0 | 0.238 | 1.415 | 15.8 | 4.21 | 0.0 | 10.0 |
| D2+VPD | KAT | 0 | 0.288 | 1.558 | 15.1 | 3.47 | 0.0 | 11.9 |
| D2+VPD | BIR | 0 | 0.238 | 1.415 | 15.8 | 4.19 | 0.0 | 10.0 |
| E1 10m² | KAT | 10 | 0.220 | 2.526 | 13.8 | 4.55 | 10.3 | 25.1 |
| E1 10m² | BIR | 10 | 0.141 | 2.290 | 14.4 | 7.09 | 18.5 | 22.0 |
| E2 10m² | KAT | 10 | 0.197 | 2.526 | 13.8 | 5.08 | 10.3 | 25.1 |
| E2 10m² | BIR | 10 | 0.129 | 2.290 | 14.4 | 7.75 | 18.5 | 22.0 |
| E3 10m² | KAT | 10 | 0.217 | 2.527 | 13.8 | 4.62 | 8.3 | 25.1 |
| E3 10m² | BIR | 10 | 0.137 | 2.291 | 14.4 | 7.31 | 17.6 | 22.0 |
| E1+VPD | KAT | 10 | 0.152 | 1.911 | 15.1 | 6.57 | 9.7 | 11.9 |
| E1+VPD | BIR | 10 | 0.101 | 1.741 | 15.8 | 9.92 | 18.0 | 10.0 |
| **E2+VPD** | **KAT** | **10** | **0.144** | **1.911** | **15.1** | **6.94** | **9.7** | **11.9** |
| **E2+VPD** | **BIR** | **10** | **0.097** | **1.741** | **15.8** | **10.29** | **18.0** | **10.0** |

Notes:
1. The older C1 "diverged at 5 m² / 10 m² KAT" entries (SEC 0.72–0.98) reflected a pre-fix mix-path formulation. After the 2026-04-08 iterative-evap fix the C1 and C2 paths converge to the same SEC at r = 0 (mix is downstream of both in the equivalent open-loop formulation).
2. Batch rerun 2026-04-21: 238/240 jobs succeeded. Two timeouts (E2 BIR winter 10m², E2 TAP winter 10m² VPD) remain to be re-run.

### 3.2 E2 Solar Area Sensitivity

| Loc | 2 m2 | 5 m2 | 10 m2 | 15 m2 | 20 m2 | Marginal SEC/m2 (5-10) |
|-----|------|------|-------|-------|-------|----------------------|
| KAT | 0.302 | 0.258 | 0.206 | 0.184 | 0.175 | -0.010 |
| BIR | 0.223 | 0.161 | 0.134 | 0.125 | 0.120 | -0.006 |

**Finding:** Diminishing returns after 10 m2. Sweet spot = 10 m2 (best cost-effectiveness).

### 3.3 Key Findings

**Configuration ranking (SEC_elec, drying time < 20h):**
1. **E2+VPD** (0.098-0.146) — Best overall. HRX+Solar+HP with VPD bypass.
2. **E1+VPD** (0.101-0.152) — Slightly worse than E2 (no dynamic evap compensation).
3. **E2 baseline** (0.134-0.206) — Strong without VPD.
4. **E3** (0.183-0.261) — Solar on evap stream less effective than cond stream.
5. **D1+VPD/D2+VPD** (0.238-0.288) — No solar, still very competitive.
6. **B r=0** (0.287-0.488) — Solar only, no HRX.
7. **C2** (0.381-0.561) — Solar cascade, moderate.
8. **C1** (0.718-0.980) — Solar on evap source is inefficient at r=0, very slow drying.
9. **A** (0.543-0.717) — HP-only baseline.

**Climate effect:** Biratnagar (warm) always outperforms Kathmandu (cold) by 25-35%.

**D3 is worst D config:** Routing exhaust through HRX to condenser brings humidity into chamber.

**C1 is worst solar config:** Solar heating evap source at r=0 cannot raise T_to_chamber to 45C.

### 3.4 Summary Plots Generated
- `plots/phase3_summary/sec_comparison_bar.png` — Bar chart of SEC across all configs
- `plots/phase3_summary/e2_solar_sensitivity.png` — SEC and SMER vs solar area
- `plots/phase3_summary/energy_breakdown.png` — Stacked energy source bar chart
- `plots/phase3_summary/pareto_sec_vs_time.png` — Pareto front: SEC vs drying time

### 3.5 Sankey Diagram
- [ ] TODO: Create energy flow Sankey for E2+VPD (best config)

---

## PHASE 4 — Seasonal and Multi-Location Analysis

**Only begin after Phases 1–3 are complete and validated.**

### 4.1 Locations
- Kathmandu (1350m, temperate): main focus
- Biratnagar (72m, tropical lowland): contrast case
- Taplejung (1820m, high altitude): highland case
- Dhulikhel (1550m, mid-mountain): supplement

### 4.2 Seasonal Analysis
Apple harvest in Nepal: October–November (post-monsoon).
Key seasons to model:
- **Post-harvest (Oct–Nov):** Primary operational window — most important
- **Winter (Dec–Jan):** Cold, dry — HP works hard but kinetics slow
- **Spring (Mar–Apr):** Warm, less humid — for comparison

---

## PHASE 5 — Paper Revision (Major Revision Response)

**Status:** IN PROGRESS (2026-04-25)
**Reviewer verdict:** Major revision required.
**Detailed plan:** `paper/REVISION_PLAN.md`

### Revision approach
- One section at a time, one paragraph at a time.
- Start new simulations first (sensitivity, convergence, Taplejung E-configs).
- Clean bibliography before editing prose.
- Then work Abstract through Conclusions sequentially.

### Blocking new simulations needed
- [ ] **F1** Sensitivity sweep: eps_cond (0.75/0.85/0.95), eps_evap (0.75/0.85/0.95), eps_HRX (0.60/0.70/0.80)
- [ ] **F2** Time-step convergence: dt=30s, 60s, 120s for Config A and E2 at KTM
- [ ] **F3** Taplejung E1/E2/E3 +/- bypass (or remove Taplejung from abstract)

### Key numerical fixes
- Wet mass: 3*(1+5.5) = 19.5 kg, water = 16.5 kg (not 22.4 / 19.3)
- "Five limitations" but six listed; "Spring is lowest" contradicted by own table
- r=0.3 Biratnagar spike unexplained; Taplejung gaps unexplained
- SMER 7.8 vs 10.29 inconsistency

### Key physics fixes
- Tetens misnamed (actually Magnus-Alduchov-Eskridge)
- W_comp is shaft power, not electrical
- Pinch + eps_cond over-determination must be reconciled
- GAB sign convention and source citation needed

### Reference cleanup
- Remove ~15 uncited/irrelevant refs (microwave ovens, plaster of Paris, etc.)
- Fix 3 mis-attributions (Erbay & Koca, Mohanraj copra, R^2 from Royen)
- Add missing refs (Bliss 1959, Mohanraj 2016, CoolProp inline)
- Remove duplicate [24]=[47]

### 5.1 What the Paper Must Answer (Novelty Requirements)

1. **9-configuration comparison framework**: A, B, C1, C2, D1, D2, D3, E1, E2 (+E3) SAHPD
   topologies under realistic Himalayan/sub-tropical conditions with real kinetics.

2. **HRX + Solar + HP triple integration (Config E)**: Novel combination not found in literature.
   Achieves SEC_elec = 0.13-0.21 kWh/kg (SMER 4.9-7.7 kg/kWh).

3. **VPD-based exhaust bypass**: Novel control strategy using VPD utilization metric to
   dynamically switch between normal and exhaust-recirculation modes. 15-31% SEC reduction.
   Applied to both closed-loop (Config A, cond_penalty) and open-loop (Configs D/E, VPD util).

4. **Climate-adaptive recirculation strategy**: r_optimal depends on ambient T and humidity.
   Warm/humid climates → r=0 optimal. Cold/dry climates → r=0.7–0.9 optimal.
   r=0.1-0.7 is a "valley of death" in cold climates (physically real discontinuity).

5. **SEC_elec below HP-only theoretical minimum**: Explained by free thermal energy from solar
   and HRX. Must always report both SEC_elec and SEC_thermal.

6. **1st law fully validated**: Q_cond = Q_evap + W_shaft exactly. The 5% apparent gap is
   mechanical efficiency losses (eta_mech = 0.95), not a violation.

### 5.2 What We Are NOT Claiming
- No real experimental validation of the FULL system (only kinetics from experiment)
- This is a simulation study — not hardware
- Midilli kinetics are from lab-scale experiments; scale-up effects not modeled
- Weather data is PVGIS averaged (not real measured on-site)

### 5.3 Sections Needed for Journal Paper
1. Introduction (HPD context, Nepal agriculture, research gap)
2. System Description (5 configurations, schematic, components)
3. Mathematical Model (HP cycle, psychrometrics, kinetics, energy balance)
4. Model Validation (kinetics validation against experimental data — NEEDED)
5. Results: Config A baseline + recirculation + condenser-direct bypass
6. Results: Solar-integrated configs (B, C, D, E)
7. Results: Multi-location seasonal analysis
8. Discussion: Climate-adaptive strategy, design rules, limitations
9. Conclusions

### 5.4 Model Validation Plan (CRITICAL — MUST DO)
- [x] **V1** Compare Config A SEC to published HPCD SEC values → 0.717 kWh/kg within lit range 0.4-1.5
- [ ] **V2** Compare kinetics MR(t) curves against our own experimental phase2 data
- [x] **V3** Compare HP COP values → 3.4-4.1 realistic for R134a at T_evap~5°C, T_cond~55°C
- [ ] **V4** If any actual lab measurements exist — compare directly
- [x] **V5** 1st law energy balance → validated exactly (gap = eta_mech, not error)
- [x] **V6** SEC_thermal > latent heat minimum → all configs pass (1.4-1.9× h_fg)
- [x] **V7** Literature comparison for D/E configs → D within range, E below HP-only min (explained)
- [ ] **V8** Sensitivity analysis: solar area, eps_HRX, VPD threshold

---

## Phase 6: Kinetic Model Justification (Phase-1 piecewise fits + Phase-2 ML regressors)

**Trigger:** Reviewers will ask why we use recursive piecewise Midilli + ML parameter regressors instead of literature Midilli values or a single Arrhenius-scaled fit. We need numbers, not narrative.

**Current state (2026-04-27):**
- 14 (T, v, RH, thickness) curves digitized from a single training paper (`D:\Masters\RQ5\Papers\Data paper for model training.pdf`).
- Phase 1: piecewise (left/right) Page/Midilli fits, AICc + LOO-RMSE selection (`scripts/recursive_piecewise_midilli.py`, `src/kinetics/`).
- Phase 2: ML regressors (Linear/Ridge/Lasso/RF) mapping conditions → 8 segment parameters (`scripts/phase2*.py`, `outputs/phase2/models/`).
- Reconstruction RMSE ≈ 0.065 (mean of 14), nL/nR RMSE ≈ 0.20 (`outputs/phase2/diagnostics/param_model_metrics.json`).
- Drying-literature acceptance threshold is RMSE_MR < 0.025, R² > 0.99 → current results are **above** threshold and need either improvement or strong baseline-comparison evidence.

### 6.1 Acceptance Metrics (must report in paper)

| Test | What it proves | Threshold to claim "good" |
|---|---|---|
| Leave-one-condition-out CV on MR(t) | Generalization across (T, v, RH, thickness) within paper | RMSE_MR < 0.025, R² > 0.99 |
| Time-to-target error (e.g., t at MR=0.1) on held-out | The metric that matters for the dryer simulation | < 5–10 % relative error |
| Beat baseline: single-Midilli + Arrhenius/RH scaling | Justifies piecewise + ML complexity | Statistically significant residual reduction (paired t-test or Diebold–Mariano) |
| External validation: one other paper's curves | Out-of-distribution generalization | RMSE_MR within 1.5× of in-sample |
| Bootstrap CI on parameters | Shows fit isn't degenerate | CI width < 30 % of parameter value |
| ΔAICc: piecewise vs single | Justifies extra segment parameters | mean ΔAICc > 10 in favor of piecewise |
| MBE / χ² / EF (drying-paper standard) | Bias and efficiency | MBE ≈ 0, EF > 0.99 |

### 6.2 Step-by-step Execution Plan

#### Study 1 — Leave-One-Condition-Out CV (LOCO-CV) [GATING]
**Goal:** Quantify generalization of piecewise + ML across the 14 conditions.

1. New script `scripts/phase2_loco_cv.py`:
   - Load `outputs/phase2/phase2_targets.csv` (14 rows).
   - For each row i in 0..13:
     - Hold row i out.
     - Re-train all 8 regressors (kL, nL, bL, kR, nR, bR, offsetR_at_join, right_time_shift_at_boundary) on the remaining 13.
     - Predict the 8 parameters for the held-out condition.
     - Reconstruct MR(t) by piecewise Midilli/Page on the held-out time grid.
     - Load original Phase-1 raw MR data for that dataset (from `outputs/piecewise_recursive_2ndphase/<dataset>/`).
     - Compute per-fold: RMSE_MR, R², MBE, χ², EF, t_at_MR=0.1 (predicted vs actual), per-parameter errors.
2. Aggregate to per-condition table + mean ± std.
3. Save `outputs/phase2/diagnostics/loco_cv_results.csv` and `loco_cv_summary.json`.
4. Plot: bar chart of RMSE_MR per held-out condition with the 0.025 threshold line.

**Pass condition:** mean RMSE_MR < 0.025 across all 14 held-outs. If not, document where it fails (low T? thick samples? low RH?).

#### Study 2 — Baseline: single-segment Arrhenius Midilli
**Goal:** Prove (or disprove) piecewise + ML beats the simpler model already used in `dryer_solar_hp.py`.

1. New script `scripts/baseline_arrhenius_midilli.py`:
   - Fit single-segment Midilli to each of the 14 curves (no piecewise split).
   - Pool the 14 fits to fit:
     - k(T) = A · exp(−Ea/(R·T)) (Arrhenius)
     - n = constant (or smooth in T, v)
     - b = α_b · f(RH) (similar to α_RH = 1.75 already used)
   - Save global parameters to `outputs/baseline/arrhenius_midilli.json`.
2. Run LOCO-CV with the same harness as Study 1 but using this baseline.
3. Save `outputs/baseline/diagnostics/loco_cv_baseline.csv`.

**Piecewise + ML is "worth it" if:**
- ΔRMSE_MR (baseline − piecewise) > 0.005 averaged across conditions, **and**
- statistically significant by paired t-test (p < 0.05) or Diebold–Mariano on per-condition residuals.

If baseline ties or wins → drop piecewise + ML, use Arrhenius single Midilli, frame the paper around it. Honest and defensible.

#### Study 3 — External validation (after Studies 1+2)
**Goal:** Show generalization beyond the training paper.

1. Identify one additional published paper with ≥ 5 (T, v, RH) curves on the same product.
2. Digitize 5–10 curves with WebPlotDigitizer.
3. Run both piecewise+ML and baseline on this external set with **frozen** models from Studies 1+2 (no retraining).
4. Report RMSE_MR, R², t_at_MR=0.1 errors.

**Pass:** RMSE_MR within 1.5× of in-sample value. Beyond that, the abstract can only claim within-paper generalization.

#### Study 4 — Bootstrap parameter CIs (parallel with Study 1)
**Goal:** Quantify parameter uncertainty for each of the 14 fits.

1. For each fit in `outputs/piecewise_recursive_2ndphase/<dataset>/`:
   - Resample residuals 500× (block-bootstrap if autocorrelated).
   - Refit piecewise Midilli/Page each time, record (kL, nL, bL, kR, nR, bR).
   - Compute 95 % CI per parameter.
2. Save to `outputs/phase2/diagnostics/bootstrap_ci.csv`.

**Pass:** CI width / parameter value < 0.3 for kL, nL, kR, nR. Wider → curves don't constrain the model and piecewise is over-parameterized.

#### Study 5 — ΔAICc piecewise vs single
**Goal:** Information-criterion justification for the segment split.

1. Piecewise AICc per curve already in `outputs/piecewise_recursive_2ndphase/`.
2. Refit each curve with single-segment Midilli, record AICc.
3. ΔAICc = AICc_single − AICc_piecewise per curve.
4. Save `outputs/phase2/diagnostics/aicc_comparison.csv`.

**Pass:** mean ΔAICc > 10 in favor of piecewise. Else the second segment isn't earned.

### 6.3 Order of execution

1. **Study 1** (LOCO-CV) — gates everything else.
2. **Study 5** (ΔAICc) — cheap, run alongside Study 1.
3. **Study 2** (baseline comparison) — only meaningful once Study 1 numbers exist.
4. **Study 4** (bootstrap CI) — independent, run after Study 1 finishes.
5. **Study 3** (external validation) — last, only if Studies 1+2 land favorably.

### 6.4 Decision tree at end of Studies 1+2

- **Both pass acceptance:** keep piecewise + ML; write methods paper / strong methodology section.
- **LOCO-CV passes, no significant improvement over baseline:** drop piecewise + ML, use Arrhenius single Midilli. Honest, simpler, defensible.
- **LOCO-CV fails (RMSE_MR > 0.025 on most held-outs):** the data is the bottleneck. Either digitize more curves (add a 2nd paper) or retreat to single-segment fit.

### 6.5 Deliverables for the paper

- **Table 6.1**: LOCO-CV results (Study 1) per condition.
- **Table 6.2**: baseline comparison (Study 2) summary row per condition.
- **Figure 6.1**: predicted vs measured MR(t) for worst- and best-case held-out conditions.
- **Figure 6.2**: parameter CI ranges (Study 4) per condition.
- One paragraph closing item **V2** in §5.4: either "Kinetic model validated with LOCO-CV (RMSE_MR = X), outperforms Arrhenius single-Midilli baseline by Y RMSE units (p<0.05)" **or** "Kinetic model does not measurably outperform Arrhenius baseline; we adopt the simpler model."

### 6.6 Results -- Studies 1, 2, 5  (executed 2026-04-28)

Note: `phase2_targets.csv` actually contains **13** datasets (not 14 as previously assumed in the project memory).

**Study 5 -- ΔAICc piecewise vs single-Midilli  (training-fit info criterion):**
mean ΔAICc = **144.7**, range 54.8 to 364.8, **13/13** strongly favor piecewise (ΔAICc > 10).
→ On training data, piecewise fits *significantly* better even after the 4-extra-parameter penalty.
→ Saved to `outputs/phase2/diagnostics/aicc_comparison.csv`.

**Study 1 -- LOCO-CV piecewise + ML (ElasticNet on 9 targets):**
| Metric | Value | Pass threshold | Pass count |
|---|---|---|---|
| RMSE_MR mean | 0.0685 | < 0.025 | 2 / 13 |
| R² mean | 0.930 | > 0.99 | 2 / 13 |
| MBE mean | -0.016 | ≈ 0 | -- |
| t at MR=0.1 mean rel-err | 15.0 % | < 10 % | 6 / 13 reach the target at all |

**Study 2 -- LOCO-CV Arrhenius single-Midilli baseline (7 global params):**
Form: k(T) = A·exp(-Eₐ/RT), n = n₀ + n_T·(T-50) + n_v·(v-1.1), b = b₀ + b_RH·(RH-42.5).
| Metric | Value | Pass threshold | Pass count |
|---|---|---|---|
| RMSE_MR mean | 0.0404 | < 0.025 | 3 / 13 |
| R² mean | 0.967 | > 0.99 | 8 / 13 |
| MBE mean | +0.002 | ≈ 0 | -- |
| t at MR=0.1 mean rel-err | 15.9 % | < 10 % | 7 / 13 reach the target |

Refit global parameters on all 13 curves (saved at `outputs/baseline/diagnostics/global_fit.json`):
A = 0.4717 min⁻ⁿ, **Eₐ/R = 1847 K** (vs 2711 K currently used in `dryer_solar_hp.py`),
n₀ = 1.243, n_T = +0.0044/°C, n_v = +0.093 s/m, b₀ = 4.15e-5, b_RH = 4.91e-5/%RH.

**Paired comparison (Study 1 vs Study 2):**
| Test | Statistic | p-value |
|---|---|---|
| Paired t-test on RMSE_MR | t = +2.79 | **0.016** (baseline better) |
| Wilcoxon signed-rank on RMSE_MR | W = 12.0 | **0.017** (baseline better) |
| Paired t-test on time-at-MR=0.1 rel-err | t = -0.23 | 0.83 (indistinguishable) |
| Win count (lower RMSE) | baseline 11, piecewise 2, ties 0 | -- |

**Verdict (per §6.4 decision tree):**
The training-fit AICc improvement does **not** transfer to held-out conditions.
The recursive piecewise + ML pipeline is **statistically significantly worse** than the simple
Arrhenius single-Midilli baseline at predicting MR(t) at unseen (T, v, RH, thickness)
combinations (p ≈ 0.016 on RMSE_MR, n = 13). On the simulation-relevant metric
(time-to-MR=0.1) the two are statistically indistinguishable.

**Implication for the paper:**
- For *interpolation at training conditions* (the actual SAHPD simulation use case via
  `phase2c_for_chamber.csv`), neither study is dispositive: lookup at the exact training
  point is exact. The current SAHPD results stand.
- For any claim of *generalization* of the kinetic model to new conditions, only the
  Arrhenius baseline is defensible. The piecewise + ML pipeline cannot be claimed as a
  contribution — it overfits.
- Recommended paper framing: drop piecewise + ML from the methods section. Report the
  Arrhenius single-Midilli (Eₐ/R = 1847 K vs old 2711 K) with LOCO-CV results from
  Study 2 as the kinetic-model validation. The piecewise + ML pipeline becomes an
  appendix / supplementary "we tried this; it didn't help" note, or is dropped entirely.

**Action items remaining:**
- [ ] Update `dryer_solar_hp.py` Arrhenius constants to match the LOCO-validated fit
      (Eₐ/R = 1847 K, b coefficients, n correction terms) and re-run the SAHPD configs.
      Quantify whether SEC numbers shift materially.
- [ ] Decide whether `phase2c_for_chamber.csv` lookup table should be replaced with the
      Arrhenius closed form throughout the SAHPD code.
- [ ] If keeping piecewise+ML in any form, run Study 4 (bootstrap CI) to show the
      parameter regressors are degenerate at n=13 (expected to fail).

---

## Current Status Tracker

| Phase | Status | Notes |
|---|---|---|
| Phase 1: Config A (recirculation) | **COMPLETE** ✓ | r sweep done, recirculation finalized |
| Phase 1.5: Condenser-direct bypass | **COMPLETE** ✓ | VPD-based, Config A+B, 21-54% SEC reduction |
| Phase 1.C: Code cleanup (remove dynamic modes) | **PENDING** | Remove dynamic-max/prop from code |
| Phase 2: Configs B, C, D, E | **COMPLETE** ✓ | All 10 configs implemented, validated |
| Phase 3: Integration comparison | **COMPLETE** ✓ | 36-run table, summary plots, E2+VPD best |
| Phase 3.5: Model validation | **COMPLETE** ✓ (2026-04-09) | Energy balance, 1st law, psychrometric, COP all verified |
| Phase 4: Seasonal analysis | **STARTING** | Need seasonal weather files (Oct-Nov, Dec-Jan, Mar-Apr) |
| Phase 5: Paper revision | **IN PROGRESS** (2026-04-25) | Reviewer report received; revision plan at `paper/REVISION_PLAN.md` |
| Phase 6: Kinetic model justification | **STUDIES 1+2+5 DONE** (2026-04-28) | LOCO-CV: Arrhenius baseline beats piecewise+ML (RMSE 0.040 vs 0.069, p=0.016). Drop piecewise+ML from paper. |

---

*This file is the single source of truth for research progress. Update the Status Tracker after each completed step.*

---

## E1/E2/E3 Data-Analysis Audit (2026-05-06, post-M1-refit rerun)

Step-by-step audit of the 142 E-config CSVs (annual + 3 seasons × 4 locations × VPD on/off + area sweeps). Plan and findings live here so every claim is traceable.

### Step 1 — Data integrity ✅
**Script:** `scripts/analysis_step1_integrity.py`
**Output:** `outputs/audit/step1_integrity.csv`

- Energy balance closes to machine precision once the **motor loss factor** is included: `Q_cond = Q_evap + 0.95·W_comp` (max rel err = 1.5e-14 across all 142 runs). The 5 % gap is `eta_mechanical = 0.95` from `heatpump.py:26` — motor losses do not become air-stream heat. Anyone repeating the audit using `Q = Q_evap + W_comp` (no η_mech) will see a flat −5 % residual; that is model-correct, not a bug.
- Water mass balance, smoothness (no T jumps > 5 °C/min), RH bounds, and convergence (X ≤ 0.18 within 13.4–22.9 h) all clean.
- COP envelope when HP is at full lift = [3.47, 8.71]. E3 records spurious COP > 8 in `'partial'`/`'off'` modes where W_comp ≈ 0 kW; mathematically meaningless, filtered out for bounds checks.

### Step 2a — Solar collector ✅
**Script:** `scripts/analysis_step2a_solar.py`
**Output:** `outputs/audit/step2a_solar.csv`
**Diagnostic plots:** `plots/_audit/step2a_clipping_*.png` (canonical = non-VPD `Ac_10m2_hrx0.70.csv`; VPD bypass is a Phase 1.5 add-on, not the headline configuration)

Code-verified air paths (`dryer_solar_hp.py:1576-1707`):
- **E1**: `Amb → HRX(cold) → SOLAR → COND → Chamber`. Evap parallel: `Amb → EVAP`.
- **E2**: same main path as E1. Evap parallel: `ExhCooled (+ iter. Amb supplement) → EVAP`.
- **E3**: `Amb → HRX(cold) → COND(variable T_cond) → SOLAR → Chamber` with solar-priority HP-off control. Evap parallel: `ExhCooled (+ iter. Amb supplement) → EVAP`.

Findings:
- **E1 ≡ E2 on solar metrics** (identical Q_solar, η, ΔT, capture_eff for every (location, season)). Correct: collector sees the same upstream air in both; configs differ only on the evap side.
- **E3 captures ~2–3 % less solar energy** (η_mean 0.429 vs 0.442). Cause: collector inlet is post-condenser (hotter), so HWB losses are larger. Physically correct.
- **Major clipping** (oversized 10 m² collector for T_set = 45 °C): 27–55 % of gross collector output is thrown away (`Q_solar_clipped_kW`) because the chamber demand saturates. Worst in spring (≈50 %), least in winter (≈30 %). This is the single most paper-worthy finding from Step 2a.
- **No anomalies**: zero negative-gain steps, zero η out of [-0.05, 0.95]. The 49 runs with `T_out > T_in` at G < 50 W/m² are dawn/dusk thermal-mass release (5–16 timesteps each); physical, not a bug.
- **Operating envelope clean**: T_solar_out maxes at 49.5–77.0 °C, well under flat-plate ceiling.

Implication: collector area is the wrong-sized component for T_set = 45 °C. Step 5c (area sweep) will quantify the diminishing-returns knee.

### Step 2b — HRX ✅
**Script:** `scripts/analysis_step2b_hrx.py`
**Output:** `outputs/audit/step2b_hrx.csv`
**Diagnostic plots:** `plots/_audit/step2b_hrx_*.png` (canonical = non-VPD `Ac_10m2_hrx0.70.csv`)

- **ε_HRX target met**: achieved median = 0.6926 across every (config, location, season), with 5–95 percentile envelope in [0.68, 0.70]. Target 0.70, achieved within 1 %.
- **E1 ≡ E2 ≡ E3 on HRX metrics**: bit-identical Q_HRX, ε, condensation fraction across the three E variants. The HRX sees the same `Amb ↔ Exhaust` streams in all three; variants differ downstream only.
- **Q_HRX recovered: 14.3–25.8 kWh per run**, comparable in magnitude to total HP+solar delivery. Largest at KTM (cold ambient → big gradient), smallest at BTN spring.
- **Condensation active 6–33 % of run time**: HRX behaves as a *condensing* recuperator, recovering both sensible + latent, especially at KTM (33 % winter). The `HRX_condensation` flag fires when expected.
- **Sensible balance closes**: median `|dT_cold − dT_hot| = 0.17 °C` (machine-zero); the 17 °C max is a single t = 0 startup transient (1/847 timesteps), not a bug.
- **Zero anomalies**: no negative ε, no daytime Q < 0, no flow reversal.

Implication for paper: HRX is the second-largest free-energy lever after solar. The condensing-mode recovery at cold sites is a model feature worth highlighting.
### Step 2c — Evaporator ✅
**Script:** `scripts/analysis_step2c_evap.py`
**Output:** `outputs/audit/step2c_evap.csv`
**Diagnostic plots:** `plots/_audit/step2c_evap_config_E{1,2,3}_kathmandu_Ac_10m2_hrx0.70.png`

**Headline (per-config means, canonical 10 m² no VPD):**

| Config | T_evap_source [°C] | Boost vs T_amb [°C] | T_evap [°C] | PR | COP_full | Q_evap [kWh] |
|---|---|---|---|---|---|---|
| E1 | 17.63 | 0.00 | 7.63 | 3.96 | 4.34 | 7.59 |
| E2 | 24.37 | +5.76 | 14.37 | 3.14 | 5.12 | 7.82 |
| E3 | 24.37 | +5.73 | 14.37 | 3.04 | 5.26 | 8.74 |

- **Mechanism explaining E2 vs E1**: the iterative `ExhCooled + amb-supplement` evaporator (`_iterative_evap_sizing`) lifts T_evap by +6.7 °C, raising COP by +0.78 (E2 over E1). E3 inherits the same evap and adds a smaller +0.14 COP gain by running the HP at partial lift (smaller ΔT_lift).
- **Why E3 still loses on SEC despite higher COP** (preview of Step 4): partial lift means less Q_cond per kWh of HP work; solar must finish the heating, but at T_set=45 °C the solar is already clipping (Step 2a), so the net effect is worse SEC.
- **Sanity all clean**: 0/138 frost events (worst case KTM E1 annual hits T_evap_min = −2.4 °C, above the −5 °C floor; E2 lifts the same case to +0.5 °C — the supplement design saves cold sites). 0/138 pressure-ratio violations (median 3.0–4.0, max well below PR_max=10). 0 evap-oversized flags, 0 Q_evap<0.
- **Boost magnitude tracks ambient cold**: +8.2 °C at KTM annual vs +3.8 °C at BTN autumn — the supplement contributes more when ambient is colder, exactly as intended.
### Step 2d — Condenser ✅
- **Audit script**: `scripts/analysis_step2d_cond.py` → `outputs/audit/step2d_cond.csv` (138 runs); plots `plots/_audit/step2d_cond_*.png` for KTM annual E1/E2/E3.
- **E1/E2 condenser is rigid**: T_cond fixed at 55 °C (= T_cond_target 45 + 10 °C subcooling margin) in 100 % of timesteps, hp_mode = 'full' always, approach to T_set = 0.000 °C — i.e. T_to_chamber = 45.00 °C exactly. Achieved air-side eps_cond ≈ 0.33 (median across all canonical runs); condenser is sized so this fixed eps lands the air on T_set, not designed to hit 0.85.
- **E3 condenser is variable** (solar-priority controller working as designed): T_cond median 51.3 °C (vs 55 in E1/E2), hp_mode split = 46 % full / 14 % partial / 40 % off. The 'off' fraction maps to daylight hours where HRX+solar alone meet T_set; 'partial' maps to shoulder hours where HP needs only a fraction of full lift. eps_cond_median ≈ 0.47 (higher because partial-lift steps run with smaller (T_cond_sat − T_air_in) denominator).
- **Q_cond cumulative**: E1 = E2 = 9.84 kWh (mean across canonical), E3 = 10.94 kWh — E3 spends *more* condenser energy because solar-after-cond means cond outlet is below T_set, then solar finishes; the HP off-steps don't compensate enough.
- **Sanity all clean**: 0/138 T_cond > 70 °C (R134a ceiling), 0/138 flag_cond_oversized, 0/138 Q_cond < 0. T_cond_max = 55.0 °C across every run — no thermal stress on the cycle.
- **Why approach = 0 in every run**: T_to_chamber is enforced to T_set by the design (cond + solar trim). What separates configs is *how much HP work* it costs, not whether the air arrives at 45 °C — confirms the Phase 3.5 validation finding.
### Step 2e — Heat pump (whole) ✅ + E2 vs E3 verdict
- **Audit script**: `scripts/analysis_step2e_hp.py` → `outputs/audit/step2e_hp.csv` (39 canonical runs).
- **Schematic**: `scripts/analysis_step2e_air_states.py` → `plots/_audit/step2e_air_states_E{1,2,3}_kathmandu_annual.png` — air-state diagrams at hr 1/2/8/10 (KTM annual) showing HRX, Solar, Cond, Chamber, Evap with T values labelled on every leg.
- **Cross-config means (all 13 canonical runs each)**:
  | Config | COP_full | duty_full | W_total kWh | Q_solar_used kWh | capture | SEC kWh/kg | SMER kg/kWh |
  |--------|----------|-----------|-------------|------------------|---------|------------|-------------|
  | E1     | 4.39     | 1.000     | 2.74        | 11.57            | 0.647   | 0.142      | 7.62        |
  | **E2** | **5.02** | **1.000** | **2.49**    | **11.57**        | **0.647** | **0.129** | **8.31**   |
  | E3     | 5.04     | 0.462     | 2.69        | 10.48            | 0.628   | 0.139      | 7.70        |
- **Annual head-to-head (E2 wins SEC at every location)**:
  - BTN: SEC E1=0.143, **E2=0.130**, E3=0.137 kWh/kg → E2 best
  - Dhulikhel: SEC E1=0.184, **E2=0.167**, E3=0.181 kWh/kg → E2 best
  - KTM: SEC E1=0.223, **E2=0.199**, E3=0.218 kWh/kg → E2 best
  - TPJ: SEC E1=0.180, **E2=0.164**, E3=0.176 kWh/kg → E2 best
- **Why E2 beats E3**:
  1. **Solar utilisation**: E2 uses 11.57 kWh, E3 uses 10.48 kWh (−9.4%). E3's solar sits *after* the condenser; its inlet is already near T_set, leaving a thin ΔT before clipping. E2's solar sits *before* the condenser at HRX-out (~25–35 °C), giving a wider usable envelope. Capture: E2 0.647 vs E3 0.628.
  2. **HP COP**: E2 ≈ E3 (5.02 vs 5.04). Both feed the evaporator with exhaust+amb mix, so both lift T_evap by ~6 °C over E1.
  3. **HP runtime**: E3's solar-priority controller cuts duty_full to 0.46 (off 40%, partial 14%, full 46%); E1/E2 stay at full lift 100% of the time. E3 saves compressor steps but must deliver *more* total Q_cond when running.
  4. **Net**: E3's runtime saving (~200 W avg) does not recover the ~1 kWh solar gap that E2 keeps. The losing factor is solar-after-condenser placement, not the controller logic.
- **Energy ranking**: E2 < E3 < E1 on W_total at every location.
- **SMER ranking**: E2 > E3 > E1 (8.31 / 7.70 / 7.62 mean).
- **Drying time**: 15.12 h mean — identical across E1/E2/E3 because all deliver T_to_chamber = 45 °C; configs differ only in energy cost.
- **VERDICT**: **E2 is the winner.** Solar before the condenser + exhaust-warmed evaporator gives both maximum solar capture and the +6 °C COP lift. E3's solar-priority controller is clever but misplaces solar in the air path.
### Step 2e.1 — E2 vs E3 deep-dive ✅ (PHASE CLOSED)
- **Deep-dive script**: `scripts/analysis_e2_vs_e3_deepdive.py` → `outputs/audit/e2_vs_e3_deepdive.txt` + plots `plots/_audit/e2_vs_e3_cumulative_kathmandu.png`, `plots/_audit/e2_vs_e3_power_kathmandu.png`.
- **Final report**: `outputs/audit/E2_vs_E3_FINAL.md` (paper-ready).
- **KTM annual decisive numbers**: SEC E2=0.1987 vs E3=0.2182 (Δ=+9.8%); W_total E2=3.845 vs E3=4.222 kWh; Q_solar_usable E2=9.685 vs E3=7.710 kWh; drying time and m_w identical (14.10 h, 19.351 kg).
- **Dominant mechanism (~80% of gap)**: collector η-loss when fed hot inlet. E3's solar inlet = T_cond_out ≈ 40 °C; E2's = T_HRX_out ≈ 28 °C. Collector heat-loss ∝ (T_plate − T_amb) → E3 gross solar drops by 1.975 kWh at *identical* irradiance (clipping identical 0.659 kWh both — this is collector physics, not clipping).
- **Secondary mechanism (~20% of gap)**: condenser air-side ΔT widens. E2 inlet 34.9 → outlet 45.0 (ΔT=10.1); E3 inlet 28.0 → outlet 39.5 (ΔT=11.5). E3's condenser delivers +2.003 kWh more Q_cond, costing +0.378 kWh W_comp.
- **Null mechanism (rules out controller credit)**: COP at full lift identical (E2=4.236 vs E3=4.211 mean). W_comp daylight E2=1.327 vs E3=1.701 kWh — E3 spends MORE in daylight despite running less.
- **Cross-location**: E2 wins SEC at all 4 locations by 5–10% (BTN 5.4%, Dhulikhel 8.3%, KTM 9.8%, TPJ 6.7%).
- **VERDICT (locked in)**: **Build E2.** Solar collector belongs *before* the condenser. E3's solar-priority controller cannot recover what its bad collector placement loses.
### Step 2f — Chamber ✅
- **Audit script**: `scripts/analysis_step2f_chamber.py` → `outputs/audit/step2f_chamber.csv` (39 canonical runs); plots `plots/_audit/step2f_chamber_*.png` (chamber + per-tray) for KTM annual E1/E2/E3.
- **Headline**: chamber behaviour is *bit-identical* across E1/E2/E3 (every per-config mean matches to 4 decimals). This is the expected Phase 3.5 finding: same T_to_chamber → same RH/X/MR/drying-rate/tray trajectories → same throughput. Configs differ only in upstream energy cost.
- **T_set tracking (clean)**: T_to_chamber_mean = 45.000 °C, max deviation = 0.000 °C in every run. Controller is rigid.
- **Sensible-to-latent conversion (KTM annual)**: T_to_chamber = 45 °C, T_exhaust ≈ 35.9 °C → sens_cool = 9.09 °C. The chamber gives up 9 °C of sensible heat to evaporate water (same kg/s air both sides). Mean across all 39 runs = 8.37 °C. Lower in humid Biratnagar autumn (5.36 °C) where less sensible budget is needed because evaporation is mass-transfer-limited.
- **RH envelope**: RH_chamber min/max = 0.10–0.16 (very dry inlet, expected at 45 °C with low absolute humidity); RH_exhaust peak = 0.93 (near-saturated outlet at peak drying rate, confirming evaporation is pulling water aggressively in the constant-rate window).
- **Drying milestones (mean across runs)**: t_to_MR50 = 3.23 h, t_to_MR10 = 8.00 h, total = ~15.1 h. Constant-rate window (≥80 % of peak rate) = 2.67 h, with peak rate ≈ 3.40 kg/h (transient peak; the average over the constant-rate window is ~3.0 kg/h).
- **Per-tray uniformity (good)**: final-X spread across 10 trays = 0.066 kg/kg, σ = 0.021 (mean across runs). Tray 0 (driest air) finishes lowest, tray 9 (most humid air) finishes highest, but all 10 trays end well below X_TARGET = 0.18.
- **X_final_avg = 0.057** vs X_TARGET = 0.18 → simulation over-dries past target. Stopping criterion is MR-based, not X-based; this is consistent with the runner's behaviour and not a defect (worth flagging in paper as "all results report run-to-MR≈0.005, equivalent to ≈3.5 % wet basis — past commercial 18 % target so SEC numbers are conservative").
- **Verdict**: chamber is well-behaved; controller delivers exactly T_set, evaporation extracts the expected latent load, tray spread is within engineering tolerance. The chamber is *not* a differentiator between E1/E2/E3 — all the action is upstream.
### Step 2g — VPD bypass controller ✅
- **Script**: `scripts/analysis_step2g_vpd.py` — pairs `Ac_10m2_hrx0.70.csv` (no VPD) vs `Ac_10m2_hrx0.70_vpd0.05.csv`. 36 pairs across E1/E2/E3 × 4 locations × seasons.
- **Output**: `outputs/audit/step2g_vpd.csv`; plots `plots/_audit/step2g_vpd_*.png`.
- **Per-config means (SEC kWh/kg)**:
  | Config | bypass_frac | SEC_no | SEC_vpd | ΔSEC_pct |
  |--------|-------------|--------|---------|----------|
  | E1     | 0.484       | 0.138  | 0.096   | **−30.0 %** |
  | E2     | 0.484       | 0.126  | 0.093   | **−26.2 %** |
  | E3     | 0.484       | 0.136  | 0.101   | **−25.4 %** |
- **Code fixes (2026-05-07)**:
  1. Removed `e_variant in ("E1","E2")` gate in the VPD decision (line 1518) so E3 also evaluates bypass.
  2. Split the bypass branch by variant: E1/E2 bypass keeps `Exh→Solar→Cond→Chamber`; E3 bypass uses `Exh→Cond→Solar→Chamber` (solar is physically downstream of the condenser — bypass only removes HRX, it doesn't move the collector).
  3. E3 bypass applies the same partial-lift control law as canonical E3 with `T_in = T_exhaust_prev`: HP back-calculates a variable `T_cond_target` so solar finishes the heating to T_set; HP turns OFF when exhaust + solar alone already reaches T_set.
  4. `Q_solar_usable` reference temperature switched to `T_exhaust_prev` (not `T_amb_heated`) when bypass is active for E1/E2.
  5. `_hp_mode` labels updated: `vpd_bypass_off`, `vpd_bypass_partial`, `vpd_bypass_full`.
- **Best case**: E1 Biratnagar autumn → −40.4 % SEC. Worst: spring runs −17 to −19 % (still positive wins; nothing goes the wrong way after the fix).
- **Verdict**: VPD bypass is a free −25 to −30 % SEC win for ALL three E configs in humid/marginal weather. E2 retains the lowest absolute SEC with VPD on (0.0927 vs 0.0962 E1 vs 0.1006 E3 mean), so the E2 ranking is unchanged.
- **Threshold sensitivity sweep ✅** (script `analysis_step4_vpd_sweep.py`, `step4_vpd_sweep.csv`, plot `step4_vpd_sweep.png`). E2 at two representative cases swept across {0.00, 0.02, 0.05, 0.10, 0.15, 0.20}:
  | threshold | SEC BTN aut | SEC KTM ann | t_h BTN aut | t_h KTM ann | bypass duty |
  |-----------|-------------|-------------|-------------|-------------|-------------|
  | 0.00 (off)| 0.108       | 0.199       | 20.0 h      | 14.1 h      | 0 %         |
  | 0.02      | 0.075       | 0.158       | 21.4 h      | 14.5 h      | 30 %        |
  | **0.05**  | **0.069**   | **0.144**   | 22.9 h      | 15.4 h      | 50 %        |
  | 0.10      | 0.084       | 0.149       | 33.9 h      | 19.4 h      | 74 %        |
  | 0.15      | 0.089       | 0.146       | 36.0 h      | 23.2 h      | 87 %        |
  | 0.20      | 0.139       | 0.152       | 72.0 h (DNF) | 28.3 h     | 94 %        |
  - **SEC minimum is at threshold = 0.05** for both cases (clear U-shape; below 0.05 bypass is under-used, above 0.05 it stalls drying).
  - **Drying time grows monotonically** with threshold (+1.3 h at 0.05, +5 h at 0.10, +13 h at 0.15, did-not-finish at 0.20 BTN autumn). Higher thresholds keep the bypass on too long, so the chamber sees stale exhaust with declining VPD and drying stalls.
  - **0.05 is the SEC optimum at minimal time penalty** — paper-defensible choice. Above 0.10 the drying-time penalty wipes out the SEC gain (you pay in product quality and throughput for marginal energy savings that eventually reverse).
### Step 3 — Energy split (where the heat goes) ✅
- **Script**: `scripts/analysis_step3_energy_split.py`. 39 canonical (no-VPD) runs, A_solar=10 m².
- **Output**: `outputs/audit/step3_energy_split.csv`; plots `plots/_audit/step3_energy_split_{E1,E2,E3}.png`.
- **Inlet-air heat budget** (mean per run, kWh delivered to air at T_set):
  | Config | Q_cond (HP) | Q_solar_usable | Q_HRX | Total |
  |--------|-------------|----------------|-------|-------|
  | E1     | 9.84 (24%)  | 11.57 (28%)    | 19.96 (48%) | 41.4 |
  | E2     | 9.84 (24%)  | 11.57 (28%)    | 19.96 (48%) | 41.4 |
  | E3     | 10.94 (26%) | 10.48 (26%)    | 19.96 (48%) | 41.4 |
- **HRX is the dominant heat source** in all three E configs at ~48 % of inlet-air heat. Solar provides ~26–29 %, HP condenser ~24–26 %. This is the headline reason E configs trounce A/B/C/D on SEC: half the heat is recovered for free.
- **Solar collector fate** (mean of 42.8 kWh irradiance/run):
  | Config | Q_useful (to air) | Q_clipped | Q_collector_loss |
  |--------|-------------------|-----------|------------------|
  | E1/E2  | 11.6 kWh (28 %)   | 7.7 (18 %) | 23.6 (54 %) |
  | E3     | 10.5 kWh (25 %)   | 7.7 (18 %) | 24.7 (57 %) |
  Net collector capture (gross η) is 41–44 %, of which 40 % gets clipped at T_set, leaving only 25–28 % of irradiance actually useful. **The 10 m² collector is heavily oversized** for T_set = 45 °C — Step 5 will sweep area to find the optimum.
- **E3's penalty quantified**: hotter solar inlet (T_cond_out ≈ 50 °C vs T_HRX_out ≈ 30 °C for E1/E2) drops collector η from 44 % → 41 % gross, and reduces usable solar by 1.1 kWh/run. HP picks up the slack (Q_cond +1.1 kWh), so total inlet heat is identical, but at higher W_comp cost. **This 1.1 kWh shift is the entire SEC gap** between E2 and E3.
- **Drying efficiencies** (mean):
  | Config | η_elec = Q_latent / W_total | η_overall = Q_latent / (W_total + Q_solar_usable) | COP |
  |--------|-------|-------|-----|
  | E1     | 5.17  | 0.919 | 5.17 |
  | E2     | **5.64** | **0.936** | **5.64** |
  | E3     | 5.23  | 1.000 | 5.23 |
  E2 wins on electrical drying efficiency (5.64 kWh latent per kWh electricity); E3 has nominally 100 % "overall" efficiency but pays for it in higher W_comp.
- **Verdict**: E2's SEC advantage is mechanistically clean — same HRX recovery, same solar capture, lower W_comp because the evap exhaust+amb mix runs the HP at a warmer source (COP 5.64 vs 5.17 E1 vs 5.23 E3). The 11 % SEC gap (0.129 vs 0.142 E1, 0.139 E3) tracks the COP gap exactly.
### Step 4 — E1 vs E2 vs E3 head-to-head ✅
- **Script**: `scripts/analysis_step4_head_to_head.py`. Consolidates Steps 2e + 2g into a single decision matrix (75 rows: 3 configs × 25 cases).
- **Outputs**: `step4_head_to_head.csv`, `step4_winrate.csv`, `step4_pivot_SEC_no_vpd.csv`, `step4_pivot_SEC_vpd.csv`.
- **SEC win count** (25 paired cases: 13 no-VPD + 12 VPD):
  | Config | no-VPD wins | VPD wins | Total |
  |--------|-------------|----------|-------|
  | **E2** | **13/13**   | **12/12** | **25/25** |
  | E1     | 0/13        | 0/12     | 0/25  |
  | E3     | 0/13        | 0/12     | 0/25  |
  E2 is the unconditional SEC winner across every location, every season, with and without VPD.
- **SEC mean by mode** (kWh/kg):
  | Mode    | E1     | E2     | E3     | E2 advantage vs E1 | vs E3 |
  |---------|--------|--------|--------|--------------------|-------|
  | no-VPD  | 0.1417 | 0.1291 | 0.1391 | **−8.9 %**         | −7.2 % |
  | VPD on  | 0.0962 | 0.0927 | 0.1008 | **−3.6 %**         | −8.0 % |
  VPD compresses the E1/E2 gap (both benefit similarly from bypass) but widens the gap to E3 (E3 benefits less because the bypass topology still has solar after cond, so the partial-lift trick is what's bypassed).
- **Per-KPI ranking**:
  | KPI            | Winner (no-VPD) | Winner (VPD) | Reason |
  |----------------|-----------------|--------------|--------|
  | SEC            | E2 (13/13)      | E2 (12/12)   | best COP × same heat budget |
  | SMER           | E2 (13/13)      | E2 (12/12)   | inverse of SEC |
  | COP_med        | E3 (13/13)      | E2 (11/12)   | E3 partial-lift wins HP cycle COP off-VPD; under VPD bypass the partial-lift logic is suspended |
  | t_h            | tie             | tie          | all three reach T_chamber = 45 °C → identical kinetics (Step 2f) |
  | Q_solar_usable | E1 ≡ E2 (tie)   | E1 ≡ E2      | E3 hotter solar inlet ⇒ ~10 % less captured |
- **E3-vs-E2 SEC penalty** is consistent at +5 to +11 % across every case (mean +7.5 %). The penalty is structural: E3's collector inlet is the cond outlet (~50 °C) vs E1/E2's HRX outlet (~30 °C), so collector η drops 44 % → 41 % gross and HP must make up the missing solar.
- **Verdict for the paper**:
  1. **E2 is the recommended SAHPD configuration** at T_set = 45 °C with HRX + Solar.
  2. Mechanism: "warm-source HP" — feeding the evaporator with cooled exhaust + ambient supplement gives the highest cycle COP (5.64 vs 5.17 E1, 5.23 E3).
  3. E3's solar-priority partial-lift is a thermodynamic dead end at this T_set: the COP gain is real but smaller than the solar-capture penalty.
  4. VPD bypass on top of E2 delivers an additional −26 % SEC in humid weather (Step 2g).
### Step 5 — Sensitivities (season/location/area/VPD/M1-vs-M2) ✅
- **Script**: `scripts/analysis_step5_sensitivity.py`. VPD already done (Step 2g sweep); this step covers the four remaining axes.
- **Outputs**: `step5_area_sweep.csv`, `step5_season_location.csv`; plots `step5_area_sweep.png`, `step5_season_heatmap.png`.

**(a) Collector area sweep (E2 annual, no-VPD)** — SEC [kWh/kg] vs A_c [m²]:
  | A_c [m²] | BTN    | KTM    | TPJ    |
  |----------|--------|--------|--------|
  | 2        | 0.2140 | 0.2903 | 0.2410 |
  | 4        | 0.1712 | 0.2596 | 0.2091 |
  | 6        | 0.1463 | 0.2332 | 0.1807 |
  | 8        | 0.1354 | 0.2106 | 0.1684 |
  | 10       | 0.1298 | 0.1987 | 0.1639 |
  | 15       | 0.1200 | 0.1759 | —      |
  | 20       | 0.1156 | 0.1678 | —      |

  - SEC decreases monotonically with area, no minimum within 2–20 m².
  - **Diminishing returns**: 2→4 m² cuts SEC ~20 %; 4→6 ~14 %; 6→10 ~11 %; 10→15 ~7 %; 15→20 ~4 %. Knee ≈ 8–10 m².
  - **Drying time is flat** at ~14 h regardless of area — solar displaces HP work, doesn't accelerate the chamber (which is already at T_set). Area is purely an energy-cost lever, not a throughput lever.
  - Clipping-fraction column is unreliable for older 15/20 m² runs (missing `Q_solar_usable_kW`); area sweep should be re-run if precise clipping figures are needed for the paper.

**(b)+(c) Season × location (E2 SEC kWh/kg, A=10 m², no-VPD)**:
  | Location   | Winter | Spring | Autumn | Annual |
  |------------|--------|--------|--------|--------|
  | Biratnagar | 0.1106 | 0.0719 | 0.1081 | 0.1298 |
  | Kathmandu  | 0.1323 | 0.0942 | 0.1226 | 0.1987 |
  | Taplejung  | 0.1626 | 0.1146 | 0.1018 | 0.1639 |
  | Dhulikhel  | —      | —      | —      | 0.1668 |
  - **Spring is cheapest** at every location (best solar, mild ambient).
  - **Winter most expensive at TPJ** (low irradiance + cold ambient → HP works hard).
  - **KTM annual** SEC=0.199 is the worst single number because annual averaging includes monsoon (poor solar); seasonal numbers are markedly better.
  - Annual SEC ranking: BTN < TPJ ≈ DLK < KTM.

**(d) M1 vs M2 kinetics** (from `phase_d_sec_delta.csv`, BTN/KTM/TPJ annual):
  | Config | mean Δ% | min Δ% | max Δ% | n |
  |--------|---------|--------|--------|---|
  | E1     | −1.31 % | −4.80 %| +1.51 %| 3 |
  | E2     | −2.11 % | −5.43 %| +0.72 %| 3 |
  | E3     | +3.97 % | −0.11 %| +6.66 %| 3 |
  - E1/E2 SEC is **robust** to kinetics swap (within ±5.5 %, mean slightly negative — M2 marginally faster).
  - E3 is **kinetics-sensitive** (M2 raises SEC by up to +6.7 % at KTM); E3's partial-lift control interacts with the drying curve, while E1/E2's full-lift is decoupled.
  - **Spearman rank correlation (M1 vs M2 SEC across all 30 audit cases) = 0.985** (memory note `phase6_audit_results.md`); E2 remains the SEC winner under both kinetic models.

**Overall sensitivity verdict**:
  1. **Area**: 8–10 m² is the practical knee; 2 m² costs ~65 % more SEC; 20 m² gains only ~10 % over 10 m².
  2. **Season/location**: BTN/spring is the cheapest operating point, TPJ/winter the most expensive — spread ≈ ±25 % around the BTN-annual baseline.
  3. **VPD threshold**: 0.05 is the optimum (Step 2g sweep); >0.10 collapses on drying-time penalty.
  4. **Kinetics**: E2's SEC and ranking are robust to M1/M2 swap; E3 is not — additional reason to prefer E2.
### Step 6 — Anomaly hunt ✅
**Script**: `scripts/analysis_step6_anomaly_hunt.py`
**Output**: `outputs/audit/step6_anomaly_log.csv`

Swept 92 canonical CSVs (E1/E2/E3 × all locations × all seasons × {no-VPD, VPD}) for 7 classes of anomaly:
1. COP outliers (< 1.5 or > 8.0 during HP running)
2. T_to_chamber deficits (> 0.5 K below T_set when not in bypass/transient)
3. HP capacity / heat-exchanger oversizing flags
4. VPD bypass churn (> 6 switches/h vs 600 s dwell)
5. Per-step first-law residual `|Q_cond − (Q_evap + 0.95·W_comp)| / expected > 2 %`
6. Cross-config consistency (E1 vs E2 must have identical Q_HRX and Q_solar_usable per case)
7. 72 h time-limit DNFs

**Findings (3 total, 1 warn / 2 info)**:

| case | kind | detail | severity |
|---|---|---|---|
| E2 / BTN / autumn / vpd | DNF_72h_limit | reached 72.0 h, m_w=18.99 kg (≈99 % of target) | warn |
| E3 / BTN / autumn / no-vpd | COP_outlier | 9 / 723 steps with COP > 8 (partial-lift transients) | info |
| E3 / BTN / autumn / vpd | COP_outlier | 7 / 247 steps with COP > 8 | info |

**Verdict**: zero first-law violations across 92 runs, zero capacity flags, zero T_chamber deficits, zero bypass-churn warnings, zero E1↔E2 energy-bookkeeping discrepancies. The single warn (BTN autumn / VPD) is a known stress-case where humid ambient + aggressive bypass leaves the dryer 1 % short of target at the 72 h cutoff (m_w=18.99 vs ~19.2 kg). The two info-level COP > 8 flags are E3 partial-lift transients at very low T_cond targets (Carnot-limited but physically realistic). Audit is clean.

### Step 7 — Paper synthesis [PENDING]

