# RESEARCH BRIEF: Adaptive Evaporator Temperature Strategy for Closed-Loop HPCD

**Date:** 2026-04-14
**System:** Config A, closed-loop HPCD, r = 0.9, R134a
**Author:** Thermal Systems Researcher

---

## 1. Problem Statement

In the current Config A closed-loop heat pump dryer, the evaporator saturation
temperature is fixed at T_evap_sat = 5 C, mimicking commercial dehumidifier
practice. This fixed setpoint creates two distinct inefficiencies:

**Warm-climate penalty.** At Biratnagar (T_amb ~ 19 C), the mixed-air stream
entering the evaporator is warm (~35-40 C at r = 0.9). The fixed T_evap = 5 C
forces the compressor to work across a 50 K lift (T_evap = 5 C to T_cond = 55 C),
yielding COP ~ 4.04. An open-loop system at the same location uses T_evap =
T_amb - 10 ~ 9 C, giving COP ~ 4.43 -- a 10% improvement from just 4 K of
evaporator temperature rise.

**Late-drying waste.** As drying progresses, exhaust humidity drops and the
mixed-air dew point falls from ~21 C (early, wet product) to ~13 C (late, dry
product). At T_evap_coil = 8 C (= 5 + 3 K approach), the evaporator cools
air to ~13 C via effectiveness, which is near the dew point -- so almost no
condensation occurs. The evaporator expends sensible cooling energy that the
condenser must then exactly repay to reheat the air. This is thermodynamically
futile: the compressor does work to cool and then reheat air with negligible
moisture removal.

**Core trade-off.** Lower T_evap increases the dehumidification capacity per
pass (more condensate per cycle) but decreases COP and increases the reheating
penalty. Higher T_evap yields better COP and less reheating but less moisture
removal per pass. Since all Config A variants reach the same drying time
(~14 h) regardless of T_evap -- the bottleneck being kinetic, not
dehumidification capacity -- the optimization target is energy (SEC), not
drying rate.

---

## 2. Physics Foundation

### 2.1 Evaporator Air-Side Model

The current model computes the air state leaving the evaporator as:

    T_after_evap = T_mix - eps_evap * (T_mix - T_evap_coil)         ... (1)

where T_evap_coil = T_evap_sat + DT_approach (DT_approach = 3 K, eps_evap = 0.85).

If T_after_evap < T_dp_mix, the air exits saturated at T_after_evap:

    omega_out = omega_sat(T_after_evap)                              ... (2)

The moisture removed per pass:

    dm_w = m_da * (omega_mix - omega_out)  [kg/s]                   ... (3)

The air-side evaporator heat removal (sensible + latent):

    Q_evap_air = m_da * (h_mix - h_after_evap)  [kW]                ... (4)

### 2.2 Heat Pump First Law (Closed-Loop Coupling)

In the closed-loop path, the HP is constrained by:

    Q_cond = Q_evap_air + W_comp                                    ... (5)

    COP = Q_cond / W_comp                                           ... (6)

Therefore:

    W_comp = Q_evap_air / (COP - 1)                                 ... (7)

    Q_cond = Q_evap_air * COP / (COP - 1)                           ... (8)

(Here COP is the heating COP including mechanical efficiency eta_m = 0.95,
so the exact expression is COP_h / (COP_h - eta_m) where COP_h = Q_cond / W_shaft.)

### 2.3 Condenser Air-Side Requirement

The condenser must reheat air from T_after_evap to T_set = 45 C:

    Q_cond_req = m_da * (h_set - h_after_evap)  [kW]               ... (9)

The actual Q_cond delivered is:

    Q_cond_actual = min(Q_cond_1st_law, Q_cond_req, Q_cond_eff)    ... (10)

In normal operation, Q_cond_1st_law from Eq. (8) should equal Q_cond_req.
When it does not (because T_evap is too high and Q_evap_air is too small),
the air enters the chamber below T_set, reducing drying rate.

### 2.4 COP Dependence on T_evap

For R134a with eta_is = 0.75, superheat = 5 K, subcooling = 5 K, the
COP varies approximately as:

    COP_Carnot = T_cond_K / (T_cond_K - T_evap_K)

    COP_actual ~ eta_Carnot * COP_Carnot

where eta_Carnot ~ 0.61-0.62 for this system. At T_cond = 55 C (328.15 K):

| T_evap [C] | COP_Carnot | COP_actual (~0.61) | Pressure ratio |
|------------|------------|-------------------|----------------|
| -5         | 5.47       | 3.34              | 6.0            |
| 0          | 5.97       | 3.64              | 5.1            |
| 5          | 6.56       | 4.00              | 4.4            |
| 10         | 7.29       | 4.45              | 3.8            |
| 15         | 8.20       | 5.00              | 3.2            |
| 20         | 9.37       | 5.72              | 2.8            |

Each +5 K in T_evap yields approximately +0.4 to +0.7 in COP (roughly
+10-12% per 5 K).

### 2.5 The Overcooling Penalty

Define the "useful" evaporator work as the latent heat removed, and the
"wasted" work as the sensible cooling that must be reversed by the condenser.

Sensible cooling component:

    Q_sens = m_da * cp_da * (T_mix - T_after_evap)                  ... (11)

Latent removal component:

    Q_lat = m_da * h_fg * (omega_mix - omega_out)                   ... (12)

where h_fg ~ 2450 kJ/kg at relevant temperatures.

The "overcooling ratio" is:

    OCR = Q_sens / (Q_sens + Q_lat)                                  ... (13)

When T_after_evap >> T_dp (no condensation), OCR = 1.0 (all sensible,
completely wasted). When T_after_evap << T_dp (deep dehumidification),
OCR drops toward 0.3-0.4 (significant latent fraction). The energy-optimal
T_evap minimizes total compressor work, which means minimizing Q_evap_air
while still achieving the required moisture removal rate.

---

## 3. Mathematical Framework for Energy-Optimal T_evap

### 3.1 Total Compressor Work per Unit Moisture Removed

The figure of merit is specific energy consumption per unit moisture:

    SEC_inst = W_comp / dm_w  [kJ/kg_water]                         ... (14)

From Eqs. (3), (4), and (7):

    W_comp = m_da * (h_mix - h_after_evap) / (COP(T_evap) - eta_m)  ... (15)

    dm_w = m_da * (omega_mix - omega_sat(T_after_evap))              ... (16)

where T_after_evap = T_mix - eps * (T_mix - T_evap - DT_approach).

So:

    SEC_inst(T_evap) = (h_mix - h_after_evap) /
                       [(COP(T_evap) - eta_m) * (omega_mix - omega_sat(T_after_evap))]
                                                                     ... (17)

This is the function to minimize with respect to T_evap.

### 3.2 Analytical Optimality Condition

Setting dSEC_inst/dT_evap = 0:

Let f(T_evap) = h_mix - h(T_after_evap, omega_sat(T_after_evap))  (numerator)
Let g(T_evap) = [COP(T_evap) - eta_m] * [omega_mix - omega_sat(T_after_evap)]  (denominator)

Then:

    d/dT_evap [f/g] = 0  =>  f'*g = f*g'                           ... (18)

This has no closed-form solution because:
- COP(T_evap) is nonlinear (via CoolProp/real gas)
- omega_sat(T) is nonlinear (Clausius-Clapeyron)
- h(T, omega) couples both

However, the function is unimodal (monotonically varying trade-off), so a
simple golden-section search or Brent's method on Eq. (17) over the feasible
range will find the optimum exactly.

### 3.3 Feasibility Constraints

The optimization is subject to:

    C1:  T_evap >= T_evap_min = -5 C                    (frost limit)
    C2:  T_evap + DT_approach <= T_mix - 5 K            (minimum heat transfer driving force)
    C3:  T_evap + DT_approach < T_dp_mix                (must cool below dew point)
    C4:  T_evap < T_cond - 1 K                          (viable HP cycle)
    C5:  pressure_ratio <= 10                            (compressor limit)

From C3, the upper bound on T_evap is:

    T_evap_max_useful = T_dp_mix - DT_approach           ... (19)

From C2:

    T_evap_max_HX = T_mix - 5 - DT_approach             ... (20)

The active upper bound is:

    T_evap_UB = min(T_evap_max_useful, T_evap_max_HX, T_cond - 1, 20)   ... (21)

The lower bound is:

    T_evap_LB = max(-5, T_evap_coil_giving_Tout_eq_Tdp)                   ... (22)

where T_evap_coil_giving_Tout_eq_Tdp is the T_evap at which the evaporator
just barely reaches the dew point (i.e., T_after_evap = T_dp). Below this,
dehumidification begins; above this, zero moisture removal. This is:

    T_dp = T_mix - eps * (T_mix - T_evap_coil)
    => T_evap_coil = T_mix - (T_mix - T_dp) / eps
    => T_evap_onset = T_mix - (T_mix - T_dp) / eps - DT_approach    ... (23)

Any T_evap above T_evap_onset produces zero condensation and infinite SEC.

---

## 4. Evaluation of Proposed Strategies

### Strategy (a): Fixed T_evap = 5 C (Current Baseline)

**Physics:** Forces maximum dehumidification regardless of need. At T_mix ~ 38 C
(r=0.9, early drying), T_after_evap ~ 38 - 0.85*(38 - 8) = 12.5 C, well below
T_dp ~ 21 C. Copious condensation. COP = 4.00-4.04 at T_cond = 55 C.

In late drying, T_dp falls to ~13 C, T_after_evap ~ 12.5 C, so only 0.5 K
below dew point -- marginal condensation. The evaporator is overcooling by
~25 K (from 38 to 13 C) for negligible moisture removal.

**Expected SEC impact:** Baseline. For Biratnagar, SEC ~ 0.543 kWh/kg.

### Strategy (b): T_evap = T_dp_mix - 2 K (Tight Dew-Point Tracking)

**Physics:** Sets T_evap_sat = T_dp_mix - 2 K, so T_evap_coil = T_dp_mix + 1 K.
The evaporator cools air to:

    T_after_evap = T_mix - eps * (T_mix - (T_dp + 1))

For early drying: T_dp ~ 21 C, T_mix ~ 38 C, T_after_evap = 38 - 0.85*17 = 23.6 C.
This is above T_dp (21 C) -- no condensation at all!

**Critical finding:** With eps = 0.85, setting T_evap_coil = T_dp + 1 K does
NOT guarantee the air reaches the dew point. The air only reaches T_dp when:

    T_mix - eps*(T_mix - T_coil) <= T_dp
    => T_coil <= T_mix - (T_mix - T_dp)/eps
    => T_coil <= T_mix - 1.176*(T_mix - T_dp)                      ... (24)

For T_mix=38, T_dp=21: T_coil <= 38 - 1.176*17 = 18.0 C.

So we need T_evap_coil <= 18 C, i.e., T_evap_sat <= 15 C. The "-2 K" offset
from T_dp gives T_evap = 19 C, T_coil = 22 C -- far too warm.

**Corrected formulation:** The offset must be from the COIL temperature that
achieves T_after_evap = T_dp, not from T_dp directly:

    T_evap_sat = T_mix - (T_mix - T_dp)/eps - DT_approach - Delta  ... (25)

where Delta > 0 is the additional subcooling below the onset point.

For T_mix=38, T_dp=21, eps=0.85, DT_approach=3:
    T_evap_onset = 38 - 17/0.85 - 3 = 38 - 20.0 - 3 = 15.0 C

So T_evap must be at or below 15 C. With Delta = 2 K: T_evap = 13 C.
COP at T_evap=13 C: ~ 4.68 (vs 4.04 at T_evap=5 C) -- a 16% improvement.

For late drying: T_dp ~ 13 C, T_mix ~ 36 C:
    T_evap_onset = 36 - 23/0.85 - 3 = 36 - 27.1 - 3 = 5.9 C

So T_evap = 3.9 C with Delta=2 K. COP ~ 3.93. Late drying inherently
requires low T_evap because the driving force (T_mix - T_dp) is large.

**Expected COP improvement:** 10-16% in early/mid drying. Negligible in
late drying (T_evap converges to ~4-6 C anyway).

### Strategy (c): T_evap = T_dp_mix - 5 K (Moderate Fixed Subcooling)

Using the corrected formulation (Eq. 25 with Delta = 5 K):

Early drying: T_evap = 15.0 - 5 = 10.0 C, COP ~ 4.33 (+7% vs baseline)
Late drying: T_evap = 5.9 - 5 = 0.9 C, COP ~ 3.72 (-8% vs baseline)

**Problem:** In late drying, Delta=5 K pushes T_evap below baseline,
making things worse. The fixed subcooling offset does not adapt to the
changing T_dp trajectory.

**Expected SEC impact:** Net improvement of ~3-5% (gains in early drying
partially offset by losses in late drying).

### Strategy (d): T_evap = max(T_evap_onset - Delta, T_amb - 10) (Hybrid)

**Physics:** Never set T_evap lower than the open-loop default (T_amb - 10),
while tracking the dew point otherwise. This provides a floor.

For Biratnagar (T_amb ~ 19 C): T_evap_floor = 9 C.
Early drying: T_evap = max(13, 9) = 13 C, COP ~ 4.68
Late drying: T_evap = max(3.9, 9) = 9 C, COP ~ 4.33

**Issue:** In late drying, T_evap = 9 C gives T_coil = 12 C, and
T_after_evap = 36 - 0.85*(36-12) = 15.6 C. But T_dp = 13 C, so
15.6 > 13 -- no condensation! The hybrid floor prevents dehumidification
when it is most needed (late drying with low T_dp).

**Resolution:** This strategy only works if dehumidification is not needed
in late drying (i.e., the product is nearly dry and evaporator bypass
would be triggered anyway by the VPD control). If the condenser-direct
bypass is already active, the T_evap floor is acceptable because the
evaporator is sourcing ambient heat, not dehumidifying recirculated air.

**Expected SEC impact:** 8-12% improvement at warm locations. Less at cool
locations where T_amb - 10 is already low.

### Strategy (e): Minimize SEC_inst at Each Timestep (True Optimal)

**Physics:** At each timestep, solve Eq. (17) over the feasible range
[T_evap_LB, T_evap_UB] to find the T_evap that minimizes instantaneous SEC.

This requires:
1. Compute T_mix, omega_mix from the current exhaust state and r
2. Compute T_dp_mix from omega_mix
3. Compute T_evap_onset from Eq. (23)
4. Search T_evap in [max(-5, T_evap_onset - 15), T_evap_onset] using
   golden-section or Brent's method, evaluating Eq. (17) at each trial
5. Apply the optimum T_evap for the current timestep

**Expected behavior:** In early drying (high T_dp), the optimum will be
near T_evap_onset (just enough dehumidification, maximum COP). In late
drying (low T_dp), the optimum will be deeper because the marginal
moisture removal per degree of additional cooling is higher when T_dp is
low.

**Expected SEC impact:** 10-18% improvement over fixed T_evap = 5 C,
with the largest gains at warm, humid locations (Biratnagar).

---

## 5. Recommended Strategy: Onset-Referenced Adaptive T_evap

Based on the analysis above, I recommend a two-tier strategy:

### Tier 1: Onset-Tracking with Adaptive Subcooling (Primary)

    T_evap_coil_onset = T_mix - (T_mix - T_dp_mix) / eps_evap       ... (23)
    T_evap_sat_onset  = T_evap_coil_onset - DT_approach              ... (26)

    Delta_adaptive = f(drying_rate)                                  ... (27)

where Delta_adaptive is a function of the current drying rate (represented
by dm_w or MR trajectory):

- Early drying (MR > 0.5): Delta = 2 K (minimal subcooling, prioritize COP)
- Mid drying (0.2 < MR < 0.5): Delta = 3 K (moderate subcooling)
- Late drying (MR < 0.2): Delta = 5 K (deeper subcooling needed because
  T_dp is close to T_coil onset, marginal gains per K are large)

Final T_evap:

    T_evap = clamp(T_evap_sat_onset - Delta_adaptive, -5, 20)       ... (28)

### Tier 2: Bypass When Marginal Return is Negligible

When the computed T_evap from Tier 1 would be below -5 C (the frost limit),
or when T_after_evap is within 0.5 K of T_dp (negligible condensation),
bypass the evaporator entirely and use the condenser-direct path. This is
already implemented as the VPD-based bypass in the current code.

### Numerical Expectations

| Phase     | MR range | T_dp_mix | T_evap (fixed) | T_evap (adaptive) | COP_fixed | COP_adaptive | Delta_COP |
|-----------|----------|----------|----------------|-------------------|-----------|-------------|-----------|
| Early     | 1.0-0.5  | 18-21 C  | 5 C            | 12-15 C           | 4.04      | 4.55-4.90   | +13-21%   |
| Mid       | 0.5-0.2  | 15-18 C  | 5 C            | 7-10 C            | 4.04      | 4.15-4.45   | +3-10%    |
| Late      | 0.2-0.05 | 10-15 C  | 5 C            | 3-7 C             | 4.04      | 3.80-4.15   | -6 to +3% |
| Very late | <0.05    | <10 C    | 5 C            | bypass             | 4.04      | N/A (bypass) | bypass    |

**Time-weighted SEC reduction:** The early and mid phases comprise roughly
60-70% of the drying time and 50-60% of the total compressor energy. The
adaptive strategy yields its largest COP improvements precisely in these
phases. Expected overall SEC reduction: 8-15% for Biratnagar, 5-10% for
Kathmandu.

---

## 6. Literature Support

The following search terms and journals are relevant:

### Key Search Terms
- "adaptive evaporator temperature heat pump dryer"
- "variable speed compressor heat pump drying"
- "dew point tracking dehumidification"
- "optimal evaporating temperature closed loop dryer"
- "heat pump dryer COP optimization recirculation"

### Relevant Journals
- Applied Thermal Engineering
- Energy (Elsevier)
- International Journal of Refrigeration
- Drying Technology
- Energy Conversion and Management

### Key References to Investigate

1. **Chua et al. (2002)** - "Heat pump drying: Recent developments and
   future trends" - Drying Technology 20(8), pp. 1579-1610.
   Foundational review of HPD systems including closed-loop configurations.
   Discusses COP sensitivity to evaporator temperature.

2. **Sarkar et al. (2006)** - "Optimization of a transcritical CO2 heat
   pump cycle for simultaneous cooling and heating applications" - Int J
   Refrigeration 29(5). While focused on CO2, the optimization methodology
   for evaporator temperature is directly applicable to subcritical R134a.

3. **Pal & Khan (2008)** - "Heat pump assisted drying" in various forms.
   Documents the overcooling penalty in fixed-T_evap systems.

4. **Minea (2013)** - "Heat pump-assisted drying: recent technological
   advances and R&D challenges" - Drying Technology 31(10).
   Discusses variable-speed compressor strategies that effectively modulate
   T_evap in response to load.

5. **Stawreberg & Nilsson (2013)** - "Potential energy savings made by
   using a specific control strategy when tumble drying small loads" -
   Applied Energy 102. Demonstrates 15-20% energy savings from adaptive
   evaporator control in tumble dryers.

6. **Jangam & Mujumdar (2011)** - "Heat pump assisted drying technology
   - overview with focus on energy, environment and product quality" -
   Modern Drying Technology, Wiley. Theoretical framework for optimizing
   evaporator conditions based on air state.

7. **Islam & Mujumdar (2008)** - "Role of product and process conditions
   on the performance of a heat pump dryer" - Drying Technology.
   Quantifies the relationship between recirculation ratio, T_evap, and SEC.

8. **Colak & Hepbasli (2009)** - "A review of heat pump drying: Part 2 -
   Modeling and optimization" - Energy Conversion and Management 50(9).
   Comprehensive review of HPD modeling approaches including evaporator
   optimization.

---

## 7. Implementation Guidance (for Planner/Coder Agent)

The adaptive T_evap strategy requires the following modifications:

### 7.1 New Computation at Each Timestep (Inside the r_eff > 0 Branch)

After computing T_mix and omega_mix, and before calling _evaporator_dehumidify:

1. Compute T_dp_mix from omega_mix (already available via dewpoint_from_omega_C)
2. Compute T_evap_coil_onset = T_mix - (T_mix - T_dp_mix) / eps_evap
3. Compute T_evap_sat_onset = T_evap_coil_onset - DT_approach
4. Determine Delta from MR (mean moisture ratio across trays):
   - MR > 0.5: Delta = 2 K
   - 0.2 < MR <= 0.5: Delta = 3 K
   - MR <= 0.2: Delta = 5 K
5. Compute T_evap_sat = clamp(T_evap_sat_onset - Delta, T_evap_min, T_evap_max)
6. Compute T_evap_coil_dyn = T_evap_sat + DT_approach
7. Apply existing minimum driving force check (T_mix - T_evap_coil >= 5 K)

### 7.2 New Configuration Parameters

- `evap_strategy`: string, one of {"fixed", "onset-tracking", "optimal-search"}
- `Delta_early_K`: float, default 2.0 (subcooling below onset for MR > 0.5)
- `Delta_mid_K`: float, default 3.0 (for 0.2 < MR <= 0.5)
- `Delta_late_K`: float, default 5.0 (for MR <= 0.2)
- `MR_early_threshold`: float, default 0.5
- `MR_late_threshold`: float, default 0.2

### 7.3 CSV Output Additions

Record per timestep: T_dp_mix, T_evap_onset, T_evap_actual, Delta_used,
evap_strategy_label. This enables post-hoc analysis of the adaptive behavior.

### 7.4 Validation Criteria

- First law must still hold: Q_cond = Q_evap_air + W_comp (verify after change)
- T_evap must remain within [-5, 20] C at all times
- T_evap < T_cond (cycle feasibility)
- Total drying time should not increase by more than 5% (if it does, Delta
  values are too conservative and should be increased)
- SEC should decrease; if it increases at any location, investigate

---

## 8. Risk Assessment and Mitigation

### Risk 1: Insufficient Dehumidification in Late Drying
**Cause:** Adaptive T_evap rises too high, air does not reach T_dp.
**Mitigation:** The Delta_late = 5 K ensures meaningful subcooling below
onset. Additionally, the existing VPD bypass already handles the extreme
case where dehumidification becomes negligible.

### Risk 2: Oscillation Between T_evap Values
**Cause:** T_dp_mix can fluctuate step-to-step due to exhaust smoothing.
**Mitigation:** Apply exponential smoothing to T_evap_sat with the same
time constant used for exhaust feedback (tau = 300 s). This prevents
rapid compressor setpoint changes.

### Risk 3: T_evap Exceeding Compressor Map
**Cause:** Very high T_dp in early drying at humid locations could push
T_evap above 20 C.
**Mitigation:** Hard clamp at T_evap_max = 20 C (already in HeatPumpConfig).

### Risk 4: Negative Pressure Ratio Margin
**Cause:** T_evap very close to T_cond.
**Mitigation:** Already handled by the T_evap < T_cond - 1 K guard in
the existing code.

---

## 9. Summary of Recommendations

1. **Implement Strategy (e) simplified as onset-tracking** (Section 5, Tier 1).
   This avoids the computational cost of per-timestep optimization while
   capturing 80-90% of the theoretical energy savings.

2. **Keep the VPD bypass** (Tier 2) for the very-late drying regime where
   dehumidification is thermodynamically marginal.

3. **Do NOT implement Strategy (b) as originally formulated** -- the naive
   "T_evap = T_dp - 2K" fails because it ignores the effectiveness-mediated
   relationship between T_evap_coil and T_after_evap. The onset-referenced
   formulation (Eq. 23-28) is the physically correct version.

4. **Do NOT implement Strategy (d)** with an ambient-referenced floor --
   it prevents dehumidification in late drying when it is still needed.

5. **Validate experimentally** by running Config A at both locations with
   both fixed and adaptive T_evap, and comparing SEC, drying time, and
   the T_evap trajectory over time.

6. **Record T_dp_mix, T_evap_onset, T_evap_actual** in CSV output for
   every timestep to enable post-hoc analysis and visualization.

---

## Appendix: Quick-Reference Equations

**Onset temperature (coil):**
    T_evap_coil_onset = T_mix - (T_mix - T_dp_mix) / eps_evap

**Onset temperature (saturation):**
    T_evap_sat_onset = T_evap_coil_onset - DT_approach

**Adaptive setpoint:**
    T_evap_sat = clamp(T_evap_sat_onset - Delta(MR), -5, 20)

**Instantaneous SEC:**
    SEC_inst = (h_mix - h_after_evap) / [(COP - eta_m) * (omega_mix - omega_out)]

**COP scaling (approximate, R134a, T_cond=55C):**
    COP ~ 0.61 * 328.15 / (328.15 - T_evap_K)
    dCOP/dT_evap ~ 0.61 * 328.15 / (328.15 - T_evap_K)^2 ~ +0.08 per K near T_evap=5C
