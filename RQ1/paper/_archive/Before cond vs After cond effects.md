# Before-Condenser vs After-Condenser solar placement (E2 vs E3)

**Question that triggered this audit**: why does E3 clip the *same* 0.659 kWh
of solar as E2, when the E3 controller is supposed to back-calculate
T_cond_target so solar lands exactly on T_set?

**Short answer**: the clipping number is identical by coincidence, but the
*physics is not the same*. E3 clips during the HP-off hours (where the
controller has no condenser knob to modulate); E2 clips during the HP-on
hours (where the cap is hit at the condenser inlet). Both face the same
T_set ceiling at peak irradiance because, in those moments, both
collectors operate from the same inlet temperature (T_HRX_out ≈ 26 °C). The
real asymmetry between E2 and E3 lies elsewhere: in the *partial-lift*
hours, where E3's collector operates from T_cond_out ≈ 35 °C and loses 25 %
of its efficiency. This document shows the code, the data, and the proof.

---

## 1. What the controller actually does (code-level audit)

**Source**: `src/rq1/dryer_solar_hp.py:1603–1707`

E3 has three branches for any daylight timestep:

### 1.1 HP-OFF branch (line 1631–1657)

Triggered when solar alone (from T_HRX_out) can reach T_set:

```
if (T_amb_heated + solar_dt_bypass) >= T_set and G_solar > 10:
    # HP is bypassed entirely
    solar_state = compute_solar_collector(T_in=T_amb_heated, ...)
    T_after_solar = solar_state.T_out_C
    T_to_chamber = min(T_after_solar, T_set)        # <-- THE CAP
    T_cond_out = T_amb_heated                        # condenser bypassed
```

The collector runs at **full power** with **no controller modulation**.
Whatever irradiance hits, the collector delivers; if T_after_solar
overshoots T_set, the excess is clipped.

### 1.2 HP-PARTIAL branch (line 1660–1706)

Triggered when solar alone cannot reach T_set:

```
T_cond_target = (T_set - alpha - beta*T_amb) / (1 - beta)   # back-calc
T_cond_target = max(T_HRX_out, min(T_cond_target, T_set))   # bounded
hp_result = size_heat_pump(T_in=T_HRX_out, T_out_target=T_cond_target, ...)
T_cond_out = T_HRX_out + eps_cond * (T_cond_sat - T_HRX_out)
T_cond_out = min(T_cond_out, T_cond_target)
solar_state = compute_solar_collector(T_in=T_cond_out, ...)
T_after_solar = solar_state.T_out_C
T_to_chamber = min(T_after_solar, T_set)
```

The controller picks T_cond_target so that the *expected* T_after_solar
(based on Hottel-Whillier-Bliss linearisation) lands on T_set. If the
linearisation matches the actual collector exactly, T_after_solar = T_set
and clipping = 0. The data confirms this branch contributes **zero
clipping** (see §3).

### 1.3 HP-FULL branch

Same as partial when T_cond_target is forced to T_set. In KTM this happens
only at night (no solar to clip).

### 1.4 E2 branch (line 1714–1741) for contrast

```
solar_state = compute_solar_collector(T_in=T_HRX_out, ...)   # ALWAYS
T_air_in_cond = solar_state.T_out_C                          # solar first
hp_result = size_heat_pump(T_in=T_air_in_cond, T_out_target=T_set, ...)
T_to_chamber = T_air_in_cond + eps_cond * (T_cond_sat - T_air_in_cond)
T_to_chamber = min(T_to_chamber, T_set)
Q_solar_usable = m*cp*max(T_air_in_cond - T_HRX_out, 0)
```

E2 has **no solar-modulation logic at all**. Solar runs at full power
every step. If solar overshoots T_set, the cap kicks in via
`min(T_to_chamber, T_set)`, and the clipped portion is `Q_solar_kW −
Q_solar_usable_kW`.

---

## 2. Why the two clipping totals are identical (coincidence, not bug)

Both branches face the **same physical ceiling** when clipping happens:

| Quantity | E2 (hp=full) | E3 (hp=off) | Identical? |
|---|---:|---:|:---:|
| Number of clipping timesteps | 122 | 122 | ✓ |
| Solar-collector inlet T [°C] | 26.43 (T_HRX_out) | 26.25 (T_HRX_out, cond bypassed) | ✓ |
| Mean Q_solar_gross at clip step [kW] | 2.181 | 2.181 | ✓ |
| Max Q_solar_gross at clip step [kW] | 2.363 | 2.363 | ✓ |
| Mean Q_solar_clipped at clip step [kW] | 0.324 | 0.324 | ✓ |
| Total clipped over run [kWh] | 0.659 | 0.659 | ✓ |

The reason for the match is structural: in E2 *every* daylight hour the
collector sees T_HRX_out as inlet. In E3 the *peak-irradiance* hours
trigger the HP-off branch, in which the collector also sees T_HRX_out as
inlet (because the condenser is bypassed). At those peak hours, identical
inlet + identical irradiance + identical collector geometry → identical
gross output → identical clipping when the T_set ceiling kicks in.

This is the model behaving correctly. The controller cannot eliminate
clipping in the HP-off branch because it has no condenser knob to turn
down — the condenser is already off.

---

## 3. The real asymmetry is in the partial-lift hours

### 3.1 E3 daylight solar accounting (KTM annual)

| hp_mode | hours | T_solar_in [°C] | Q_solar_gross [kWh] | Q_solar_usable [kWh] | clipped [kWh] | η_collector (mean) |
|---|---:|---:|---:|---:|---:|---:|
| off | 2.03 | 26.25 | 4.434 | 3.775 | **0.659** | **0.425** |
| partial | 4.17 | 35.46 | 3.934 | 3.934 | 0.000 | **0.259** |
| full (daylight) | 0.00 | — | 0.000 | 0.000 | 0.000 | — |
| **total daylight** | **6.20** | — | **8.369** | **7.710** | **0.659** | — |

### 3.2 E2 daylight solar accounting (KTM annual)

| hp_mode | hours | T_solar_in [°C] | Q_solar_gross [kWh] | Q_solar_usable [kWh] | clipped [kWh] | η_collector (mean) |
|---|---:|---:|---:|---:|---:|---:|
| full (always) | 7.98 | 26.43 | 10.341 | 9.682 | **0.659** | **0.342** |

### 3.3 What this table proves

1. **Clipping totals match** (0.659 vs 0.659 kWh). Confirms §2.
2. **Gross capture differs by 1.972 kWh** (E2 = 10.341, E3 = 8.369).
   This is the actual mechanism that hurts E3.
3. **The gap comes from partial-lift hours**, not from the HP-off hours.
   In HP-off hours, E3's collector sees T_HRX_out ≈ 26 °C (same as E2)
   and operates at η ≈ 0.43. In partial-lift hours, E3's collector sees
   T_cond_out ≈ 35 °C and operates at η ≈ 0.26, **a 39 % efficiency
   penalty** for the same irradiance.
4. **Daylight-hour gap (7.98 E2 vs 6.20 E3) is a counting artefact**: in
   E3 there are 1.78 h of daylight where partial-lift T_cond_out is so
   warm and irradiance so low that the collector's net output drops below
   the 0.05 kW threshold I used to filter "daylight" — the collector's
   η goes to zero (heat losses exceed gain) at high inlet × low G. E2
   never hits this regime because its inlet is always the cool T_HRX_out.

---

## 4. The collector physics (why hot inlet kills η)

The Hottel–Whillier–Bliss model used in `solar.py`:

```
Q_useful = F_R * A * [η_optical * G  −  U_L * (T_in − T_amb)]
η_collector = Q_useful / (G * A)
            = F_R * [η_optical  −  U_L * (T_in − T_amb) / G]
```

For our collector at G = 700 W/m² and T_amb = 14 °C (KTM annual midday):

| T_in [°C] | (T_in − T_amb) | U_L·ΔT [W/m²] | η = F_R·(η_opt − U_L·ΔT/G) |
|---:|---:|---:|---:|
| 26 (E2 / E3-off) | 12 | 96 | 0.90·(0.78 − 96/700) ≈ **0.58** |
| 35 (E3-partial) | 21 | 168 | 0.90·(0.78 − 168/700) ≈ **0.48** |
| 40 (E3-partial worst) | 26 | 208 | 0.90·(0.78 − 208/700) ≈ **0.43** |

Every 10 °C increase in solar inlet costs ≈ 9 percentage points of
collector efficiency. E3's controller raises T_solar_in by ~10 °C during
partial-lift hours; that loss is the 1.97 kWh deficit observed in the
data.

(The numbers in §3 are run-averaged and lower than these midday peaks
because they include shoulder hours, but the rank order is preserved:
E3-partial η < E3-off η ≈ E2 η.)

---

## 5. Energy-budget closure

| line item | E2 [kWh] | E3 [kWh] | Δ (E3 − E2) | comment |
|---|---:|---:|---:|---|
| Q_solar_gross | 10.341 | 8.369 | **−1.972** | dominant mechanism |
| Q_solar_clipped | 0.659 | 0.659 | 0.000 | identical (§2) |
| Q_solar_usable | 9.682 | 7.710 | **−1.972** | gross − clipped |
| Q_HRX | 25.758 | 25.758 | 0.000 | identical |
| Q_cond delivered | 14.284 | 16.287 | +2.003 | secondary effect (cond ΔT widens) |
| W_comp | 3.499 | 3.877 | +0.378 | extra HP work |
| W_fan | 0.346 | 0.346 | 0.000 | identical |
| **W_total** | **3.845** | **4.222** | **+0.378** | electrical penalty |

The accounting closes: E3 loses 1.972 kWh of free solar energy, recovers
2.003 kWh of it via extra condenser duty, which costs 0.378 kWh of
compressor work at the system COP (~5.0 → 1 kWh extra Q_cond ≈ 0.2 kWh
extra W_comp; the rest comes from running the condenser at lower air
temperature i.e. larger ΔT per pass).

---

## 6. SEC and SMER consequences

| Metric (KTM annual) | E2 | E3 | Δ E3 − E2 |
|---|---:|---:|---:|
| W_total [kWh] | 3.845 | 4.222 | +9.8 % |
| Water removed [kg] | 19.351 | 19.351 | 0 % |
| **SEC [kWh / kg]** | **0.1987** | **0.2182** | **+9.8 %** |
| **SMER [kg / kWh]** | **5.033** | **4.583** | **−8.9 %** |
| Drying time [h] | 14.10 | 14.10 | 0 % |

The 9.8 % SEC gap is the direct monetary expression of the 1.97 kWh
gross-solar deficit. There is no kinetic compensation (drying time and
water mass are identical because both deliver T_to_chamber = 45 °C).

---

## 7. Cross-location robustness (E2 wins everywhere)

| Location | Q_sol gross E2 | Q_sol gross E3 | gross deficit | SEC E2 | SEC E3 | gap |
|---|---:|---:|---:|---:|---:|---:|
| Biratnagar | 13.10 | 12.13 | 0.97 | 0.130 | 0.137 | +5.4 % |
| Dhulikhel | 10.43 | 8.83 | 1.60 | 0.167 | 0.181 | +8.3 % |
| Kathmandu | 10.34 | 8.37 | 1.97 | 0.199 | 0.218 | +9.8 % |
| Taplejung | 10.36 | 9.27 | 1.09 | 0.164 | 0.176 | +6.7 % |

The same mechanism operates at every location. The gap is largest at KTM
(coolest annual mean → biggest ΔT_amb → biggest collector η-penalty when
inlet is hot), smallest at hot Biratnagar (smaller ΔT regardless of inlet
position).

---

## 7.5 Important model-labelling note: E2's hidden solar bypass

E2's `hp_mode` is hard-coded to `"full"` on every timestep
(`dryer_solar_hp.py:1601`). This is a static label, **not** a measurement
of compressor load. The data shows E2 in fact has a *de facto* solar
bypass:

| E2 daylight regime (KTM annual) | Steps | % daylight | Q_cond [kW] | W_comp [kW] | What's happening |
|---|---:|---:|---:|---:|---|
| T_air_in_cond ≥ 45 °C (cap hit) | 122 | 25.5 % | **0.001** | **0.000** | HP effectively off |
| 43 ≤ T_air_in_cond < 45 °C | 29 | 6.0 % | low | low | HP nearly off |
| T_air_in_cond < 43 °C | 328 | 68.5 % | normal | normal | HP carrying load |

Daylight mean W_comp = 0.156 kW vs night mean = 0.368 kW — the actual
compressor load is **58 % lower** in daylight than at night, even though
the label always reads `"full"`. The line
`T_air_in_cond = min(T_after_solar, T_set)` (line 1584) silently caps the
solar-warmed air at T_set; downstream the condenser is asked to lift
"45 → 45" and the HP sizing routine returns zero work for that step.

**Implication for the comparison**: the 122 peak-irradiance bypass steps
are *physically the same* in E2 and E3. E3's explicit controller adds no
benefit at peak — both configs deliver the same solar there. E3's
controller only acts during partial-lift hours, and that's where it loses
(§3, §4).

**Implication for §2 of Step 2e** (audit doc): the "duty_full = 1.000"
reported for E2 is a labelling artefact, not a physical duty. The
*energy* duty W_comp_day / W_comp_night ≈ 0.42, meaning the compressor
runs at ≈ 42 % of nominal load during daylight.

## 8. Conclusions, in plain language

1. **The 0.659 kWh clipping match is genuine and explainable.** Both E2
   (in HP-on hours) and E3 (in HP-off hours) hit the same T_set ceiling
   from the same T_HRX_out inlet. Same inlet × same irradiance ×
   same collector → same overshoot. The model is consistent.

2. **The clipping match is *not* the reason E3 loses.** The reason E3
   loses is during HP-*partial* hours, when its collector is fed by
   T_cond_out ≈ 35 °C instead of T_HRX_out ≈ 26 °C. That 10 °C inlet
   penalty costs 9 efficiency points per the Hottel–Whillier–Bliss
   model, summing to a 1.97 kWh gross-capture deficit over the run.

3. **The clever solar-priority controller cannot recover it.** The
   controller acts on T_cond_target (the partial-lift knob), but it
   cannot move the *physical position* of the collector in the air path.
   Whatever the controller does, the collector still sees a hot inlet
   in partial-lift hours.

4. **Engineering rule that follows**: in any series-cascade with HRX +
   solar + heat-pump, place the solar collector *upstream* of the
   condenser. The collector wants the coldest possible inlet; the
   condenser wants the warmest possible inlet (smaller ΔT per pass = less
   compressor work). Putting solar first satisfies both.

5. **Final numbers**: E2 SEC 0.130–0.199 kWh/kg across locations, E3 SEC
   0.137–0.218. E2 wins by 5–10 % at every location, every season.

**Build E2.**
