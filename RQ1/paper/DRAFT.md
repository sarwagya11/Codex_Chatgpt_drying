# [Title placeholder, ~12 words: climate-scaling + topology comparison framing]

**Authors:** Sarwagya [..], [supervisors]
**Affiliation:** [..]
**Corresponding author:** sarwagya160@gmail.com

> Journal target: Renewable Energy (Elsevier). Word budget 5600. Refs ≤ 50, numbered IEEE.
> Style anchor: Kuan et al. 2019, Renewable Energy 143:214-225 [ledger #12].
> Voice: passive, simulation-only. No em-dashes. Each unverified figure tagged `[VERIFY: ledger #N]`.

---

## Highlights (3-5 bullets, ≤ 85 chars each) — defer until §5 stable

- [placeholder]

## Abstract (≤ 250 words) — defer until §5 stable

[placeholder]

## Keywords (6) — defer

solar-assisted heat pump dryer; heat-recovery exchanger; apple drying; Nepal; specific energy consumption; topology comparison

---

## 1. Introduction (~1050 words, 4 paragraphs)

### Paragraph 1 — Nepalese horticulture and the case for apple drying (~250 w)

Apple is the principal commercial winter-fruit species of Nepal's mid- and high-hill belts, grown on terraced orchards distant from cold-chain infrastructure; nationally, the winter-fruits group (apple, pear, walnut) accounts for roughly 0.15 Mt of the 1.53 Mt annual fruit harvest, with apple as the dominant species [MoALD 2024, ledger #35], and a recent in-country dryer trial on apple has been reported [Aacharya et al. 2024, ledger #9]. Best practice for thin-layer apple drying lies in a narrow 40 to 55 °C window: above the upper end the colour and aroma fractions degrade, and below it the drying time grows uneconomically [Royen et al. 2020, ledger #40]. A controlled-temperature electrical dryer is therefore preferred over open-sun or biomass-fired alternatives. The combination of an absent rural cold chain, post-harvest losses of order 20 to 35 % across handling and storage in Nepali fruits and vegetables [GC and Ghimire 2019, ledger #60], and the thermolabile profile of the apple flesh makes a heat-pump-based dryer the natural backbone of any year-round dryer installation, and the necessity of adopting HPD technology in Nepal follows directly from this combination. Drying demand at this temperature window is not confined to apple: large cardamom, the principal Nepali spice export, is cured at 45 to 55 °C in direct-fire bhatti kilns that consume around 2.5 kg of fuelwood per kg of dry product [Kattel et al. 2020, ledger #61; Ranjan et al. 2018, ledger #62], illustrating the broader national demand for controlled mid-temperature drying. The Nepalese annual global horizontal irradiance ranges from 1614 kWh/m²·yr in the eastern Terai to 1949 kWh/m²·yr in the trans-Himalayan rain shadow, with Kathmandu at 1753 kWh/m²·yr [ESMAP 2017, ledger #30], strong on annual integral but with pronounced monsoon and microclimatic variability. Hybrid systems combining solar collectors, heat-recovery exchangers, and heat pumps together with simpler standalone configurations are evaluated in this study.

### Paragraph 2 — Solar-assisted heat-pump drying with heat-recovery exchange: prior work and the inherited-kinetics gap (~430 w)

Heat-pump drying (HPD) substitutes a vapor-compression cycle for the resistance heater of a conventional hot-air dryer. In closed-loop variants the evaporator additionally dehumidifies and cools the recirculated chamber exhaust while the condenser reheats the same airstream before re-admission, recycling latent heat that would otherwise be vented; in open-loop variants the condenser heats either ambient air or HRX-pre-warmed ambient air on its way to the chamber, and the evaporator draws either a parallel ambient stream or the cooled exhaust as its source [Çolak and Hepbaşlı 2009, ledger #39; Minea 2013a, ledger #32]. The present work studies the open-loop case throughout (Section 4). Aktaş et al. measured apple drying under HP operation at a chamber temperature of 45 °C with slabs of 5 mm thickness and obtained an effective diffusivity of 2.36 × 10⁻⁸ m²/s, more than twice that of a solar-dryer comparator operated in parallel under the same product geometry, illustrating the apple-drying acceleration accessible from heat-pump conditioning of the inlet air [Aktaş et al. 2015, VERIFY: PDF needed; cited diffusivity is for 45 °C, 5 mm slab]. Reported HPD performance for fruits and vegetables falls in the range SMER 0.2-4 kg/kWh and drying-air temperature 40-70 °C, the lower end of which is well-suited to thermolabile products whose colour and aroma fractions degrade above the upper end of this window [Minea 2013b, ledger #33; Loemba et al. 2023, ledger #59; Zhu et al. 2025, ledger #47]. In solar-assisted heat-pump drying (SAHPD), a solar air or PV/T collector supplies sensible pre-heat that reduces the condenser-side load and raises the system-level coefficient of performance (Q_solar + Q_cond per unit compressor work), and a sensible heat-recovery exchanger (HRX) coupled between the dryer exhaust and the inlet air is a natural further efficiency step since it recovers exhaust enthalpy that would otherwise be vented and reduces the evaporator load. Mortezapour et al. demonstrated a PV/T-coupled SAHPD for saffron in Iran at 40-60 °C with a 33% reduction in specific energy consumption against the HP-only baseline and a system SMER of 1.16 kg/kWh [ledger #34]. Yahya and Fudholi compared open-sun and SAHPD modes for cassava in Indonesia and raised SMER from 0.38 to 0.47 kg/kWh at a refrigerant-cycle COP of 3.23-3.47 [ledger #16]. Rulazi et al. evaluated an SAHPD for tomato and carrot at the Nelson Mandela African Institution in Tanzania, reaching COP 3.4, SMER 1.33 kg/kWh and payback periods of 2.6-3.0 years [ledger #46]. Kuan et al. provided one of the few continental-cold-climate evaluations, simulating an SAHPD for banana in Almaty that shortened drying time from 35 to 21 h with SMER 0.6 kg/kWh and COP 2.72, and quantified the contribution of an exhaust-side heat-recovery unit at 12.9% additional energy saving over the SAHPD-only configuration [ledger #12]. Qiu et al. integrated a heat-recovery unit and a thermal storage tank into an SAHPD and reported a 40.5% system-level energy saving relative to the solar-plus-HP baseline [ledger #17], and Ismaeel and Yumrutaş extended the combination to a full Solar + HP + TES + HRU configuration for wheat drying with annual HRU savings of 21.4% and a heat-pump COP of 5.55 [ledger #5]. The solar-plus-HP-plus-HRX combination is therefore not novel in itself, and the studies reviewed above are uniformly single-site, single-configuration evaluations; a separate methodological observation is that the apple drying kinetics, where applicable, are typically inherited as a single-temperature Arrhenius or Midilli fit drawn from one experimental source and the resulting parameter uncertainty is rarely propagated into the simulated specific energy consumption, even within the calibration band of the inherited fit, despite apple thin-layer datasets reported under matched conditions exhibiting non-trivial dispersion in the temperature, velocity and humidity dependence of the drying-rate constant [Royen et al. 2020, ledger #40; Sharabiani et al. 2021, ledger #21].

### Paragraph 3 — Gap statement (~180 w)

Three gaps emerge from the literature reviewed above. First, to the authors' knowledge no peer-reviewed evaluation of HP-based drying (including solar-assisted and HRU-based variants) has been reported for Nepal; the closest in-country journal contribution couples a flat-plate solar collector to a biomass gasifier for chilli and banana at Kathmandu [Mishra et al. 2017, VERIFY: PDF needed], leaving the vapor-compression option untested in a national context whose annual irradiance varies by more than 20% between the eastern Terai and the trans-Himalayan rain shadow. Second, the SAHPD literature is dominated by single-site, single-season evaluations; where climate variability is examined at all it is by simulating successive months at one location, as in the four-season Almaty study of Kuan et al. [ledger #12], and no peer-reviewed evaluation has reported matched-set-point specific energy consumption across more than one site to expose the elevation- and humidity-dependence of the resulting performance. Third, the prior topology comparisons that do exist vary only a single design axis at a single site. The joint effect of where the solar collector is integrated into the air loop, combined with whether an exhaust-side heat-recovery exchanger is present, has not been reported under a matched drying-air set point, a matched product load and a multi-site climate envelope.

### Paragraph 4 — Objectives, contributions, roadmap (~225 w)

Against this backdrop, this study has been undertaken to first check the performance of HPD, SAHPD, and SAHPD+HRU configurations under Nepali climate, and on that basis to identify the best placement of the solar collector within heat-pump-based and heat-pump-plus-heat-recovery-exchanger-based drying configurations for apple drying. The heat-recovery exchanger, where present, is consistently coupled to the dryer exhaust to recover sensible enthalpy before venting, while the solar collector is repositioned across the plausible integration points on the conditioning side of the air loop; the resulting twelve dryer simulators (Section 4.3, Table 1) cover both the open-loop (r = 0) and closed-loop (r > 0) operating modes where both are physically meaningful, so that the configurations are distinguished by their air-loop topology (where the solar collector, the HRX, and the exhaust stream connect into the air loop) together with a single per-(configuration, site) recirculation fraction selected by an explicit Stage-1 screen (Section 4.4). A common drying-air set point of 45 °C and a fresh apple load of 22.5 kg are imposed across every configuration, and four Nepali sites at 72 to 3440 m elevation (Biratnagar in the tropical Terai, Kathmandu in the sub-tropical mid-hill capital, Jomsom in the temperate trans-Himalayan rain shadow in Mustang, and Namche in the sub-alpine Solukhumbu) are simulated under site-specific PVGIS-SARAH3 typical-meteorological-year hourly weather [PVGIS-JRC 2024, ledger #63]; the four sites traverse Nepal's tropical Terai, sub-tropical mid-hill, temperate trans-Himalayan and sub-alpine climate bands, so that the SEC ranking exposed by the simulation is robust against the country's ambient-humidity and ambient-irradiance envelope. Annual and calendar-quarter (Q1-Q4) subsets are retained to expose the winter-irradiance and pre-monsoon humidity sensitivity of each configuration; the monsoon quarter (Q3, July to September) is reported with the caveat that field-practice apple drying in Nepal is typically suspended in that window. The contributions of this work are: a side-by-side ranking of the solar-placement variants under a five-parameter drying-rate law calibrated on the apple thin-layer dataset of Royen et al. [ledger #40], with the fit protocol, calibration band, and parameter uncertainty bounds reported in §3.4 and §5.6; a quantification of how the energy advantage of solar pre-conditioning varies across Nepal's tropical Terai, sub-tropical mid-hill, temperate trans-Himalayan and sub-alpine climate bands; and a design recommendation, transferable across the 72 to 3440 m climate envelope, that nominates a preferred topology and a collector-area range for apple drying at the 45 °C set point characteristic of Nepali installations.


---

## 2. System description (~400 w)

The Nepalese horticultural belt spans tropical Terai sites near 70 m elevation, temperate mid-hills near 1500 m, and sub-alpine highlands beyond 1800 m, with monsoon-period overcast and winter ambient temperatures near or below 10 °C at the upper three sites in the PVGIS TMY record (Kathmandu, Dhulikhel, Taplejung; §4.2). A solar-only dryer cannot maintain a controlled chamber set-point through these periods, and a vapor-compression heat pump has therefore been adopted as the year-round backbone of the system simulated in this work. Once the heat pump is in place, the chamber exhaust still leaves carrying useful enthalpy at the set-point temperature; a sensible-only air-to-air heat-recovery exchanger (HRX) is therefore coupled to that exhaust, both to pre-heat the incoming ambient stream before it reaches the condenser and to deliver a warmer source stream to the evaporator. The HRX consequently reduces the lift the compressor must provide on the main air path and raises the coefficient of performance on the evaporator side at the same time, which together motivate it as the second core component of the system. A flat-plate solar air collector is then added in series on the chamber-side air path so that solar gain, when available, supplies a further share of the heat duty that would otherwise fall on the compressor. The integrated system simulated in this work is the combination of these three components (heat pump, HRX, solar collector) coupled to the drying chamber. The mathematical model of each subsystem is developed in §3; the dryer configurations that differ in how the three components are wired together, together with the simulation matrix used to evaluate them, are laid out in §4.

## 3. Mathematical model (~1200 w)

The model is decomposed into four subsystems that are treated separately: the vapor-compression heat-pump cycle, the flat-plate solar air collector, the heat-recovery exchanger, and the drying chamber with its kinetic model. A common psychrometric layer carries the air state between components, and the integrated simulator advances all subsystems on a fixed timestep dt = 60 s. The mathematical model is developed under the following assumptions; the numerical values of all constants used in this section are collected in Table 2.

### 3.1 Modeling assumptions

*Air loop and numerical scheme.*
- (i) All air-side processes within a single timestep are quasi-steady; transients are resolved between timesteps only.
- (ii) The site total pressure p_atm is set by the deployment-site elevation.
- (iii) Air flows axially through the solar collector and horizontally over the trays in the drying chamber; no transverse air-side gradient is resolved within a single tray.
- (iv) The air velocity over the trays is held at 1.1 m/s, matching the reference state of the kinetic dataset (Section 3.4).
- (v) The drying-chamber and air-duct walls are adiabatic; heat losses through the enclosure are ignored.
- (vi) The drying chamber is treated as a one-dimensional series of well-mixed tray-level control volumes; the air state within a single tray is uniform and the per-tray humidity-ratio rise propagates to the next tray downstream.
- (vii) Blower count is configuration-dependent. The electric-resistance baseline (Config 0) and the closed-loop variants in which the evaporator sits inline on the recirculating main loop (A at r > 0, B1_closed, B2_closed, C1 at r > 0) carry a single chamber blower. The open-loop heat-pump configurations with a parallel evaporator source stream (A at r = 0, B1_open, B2_open, C1 at r = 0, D1, D2, E1, E2, E3) carry two blowers: a main chamber blower on the conditioning path and a second blower on the evaporator source stream. Where two blowers are present they are mechanically independent and their per-step shaft powers are summed into the total fan power W_fan (Section 3.10).

*Refrigerant cycle.*
- (viii) The refrigerant-cycle energy balance retains only enthalpy changes; kinetic-energy, potential-energy, and chemical contributions are neglected, as is standard for vapor-compression analysis.
- (ix) Compression of refrigerant vapour is represented by an isentropic efficiency η_is = 0.75 and a mechanical efficiency η_mech = 0.90.
- (x) The expansion valve is isenthalpic, h_4 = h_3.
- (xi) The compressor-suction superheat and the condenser-outlet subcooling are both 5 K, following the ASHRAE Handbook Refrigeration convention [ledger #ASHRAE-Refrig].
- (xii) R134a is the working fluid; all refrigerant properties are evaluated from CoolProp at every timestep, with no working-fluid property tabulation assumed in advance. The operating envelope is enforced as a soft clip on T_evap ≥ −5 °C (frost limit on the air-side of the evaporator coil), T_cond ≤ 70 °C (mechanical and lubricant limit), and pressure ratio P_cond/P_evap ≤ 10 (single-stage compression-ratio limit); any timestep that crosses one of these is reported as an out-of-envelope flag but is not capped on the cycle solution.
- (xiii) The cycle represents an inverter-driven compressor and an electronic expansion valve that together modulate the refrigerant mass flow rate to track the air-side condenser duty. The compressor is sized off-line against a 1-ton-air-conditioning rating (Table 2); timesteps that exceed the rated capacity are flagged but not capped.

*Solar air collector.*
- (xiv) The optical and radiation properties of the flat-plate solar collector (absorptance, emittance, transmittance, overall loss coefficient, plate-efficiency factor) are held fixed at their datasheet values for every hour of the TMY record (Table 2); no angle-of-incidence, plate-temperature, or wind-speed corrections are applied. The collector aperture area A_c is a design variable.
- (xv) The collector is modeled by the lumped Hottel-Whillier-Bliss formulation [ledger #DuffieBeckman]; all values and relevant constants are listed in Table 2.

*Heat-recovery exchanger.*
- (xvi) The HRX is a sensible counter-flow plate exchanger of fixed effectiveness (Table 2). Cold-side condensation is neglected since the cold side is being heated from ambient, which lies well below its own dewpoint at every site and season; condensation cannot occur on a surface that is being warmed.
- (xvi-b) Hot-side condensation is admitted only when the cooled-exhaust temperature crosses the local dewpoint, in which case the cooled stream is taken as saturated at its outlet temperature and the corresponding latent transfer is reported alongside the sensible duty.

*Chamber, kinetics, and product.*
- (xvii) The dry-air and water-vapor specific heats and the reference latent heats are taken as constants (Table 2); the saturation latent heat at 45 °C closes the chamber humidification balance.
- (xviii) The kinetic equilibrium moisture content is taken as X_eq = 0 in the per-step moisture update; the local-relative-humidity dependence of the drying rate enters through the rate constant itself (Eq. 22, §3.4), not through the equilibrium term.
- (xix) The product is treated as apple slices of fixed thickness and apparent density (Table 2).
- (xx) Sensible heating of the product (less than 2 % of the cumulative latent load over a full batch) is neglected; the product temperature is set equal to the local tray-air dry-bulb temperature, which is also the variable controlled and reported in the thin-layer dataset of Royen et al. [ledger #40].

**Table 2.** Fixed model constants used in §3.

| Property | Symbol | Value | Unit |
|---|---|---|---|
| Compressor isentropic efficiency | η_is | 0.75 | – |
| Compressor mechanical efficiency | η_mech | 0.90 | – |
| Compressor-suction superheat | ΔT_sh | 5 | K |
| Condenser-outlet subcooling | ΔT_sc | 5 | K |
| Condenser air-side effectiveness | ε_cond | 0.85 | – |
| Evaporator air-side effectiveness | ε_evap | 0.85 | – |
| Condenser pinch temperature difference | ΔT_pinch,cond | 10 | K |
| Evaporator pinch temperature difference | ΔT_pinch,evap | 10 | K |
| Condenser rated capacity | Q_cond,max | 4.0 | kW |
| Evaporator rated capacity | Q_evap,max | 3.5 | kW |
| Collector optical efficiency | η_opt | 0.75 | – |
| Collector incidence-angle modifier | K_θ | 1 | – |
| Collector overall loss coefficient | U_L | 5.0 | W/(m²·K) |
| Collector plate-efficiency factor | F′ | 0.90 | – |
| Collector absorber-plate heat capacity | C_p | 10 | kJ/K |
| Collector tilt angle (PVGIS POA request) | β | 45 | ° |
| Collector azimuth (true south) | γ | 0 | ° |
| HRX sensible effectiveness | ε_HRX | 0.70 | – |
| Number of trays in chamber | n_trays | 10 | – |
| Chamber set-point temperature | T_set | 45 | °C |
| Superficial air velocity over trays | v | 1.1 | m/s |
| Apple slice thickness | d | 6 | mm |
| Apple slice apparent density [Rodriguez-Ramirez et al. 2012, J Food Sci 77(12):R146] | ρ_s | 750 | kg/m³ |
| Tray topology | – | parallel | – |
| Inter-tray air gap | h_gap | 15 | mm |
| Tray frame thickness | h_frame | 20 | mm |
| Chamber inlet plenum loss coefficient | K_plenum,in | 0.5 | – |
| Chamber outlet plenum loss coefficient | K_plenum,out | 1.0 | – |
| Evaporator-air pinch approach | ΔT_evap,approach | 3 | K |
| Dry-solid product mass | m_p,dry | 3 | kg |
| Initial moisture content (dry basis) | X_0 | 6.5 | kg water / kg dry |
| Kinetic reference temperature | T_ref | 50 (323.15) | °C (K) |
| Kinetic reference velocity | v_ref | 1.1 | m/s |
| Kinetic reference thickness | d_ref | 6 | mm |
| Fan electromechanical efficiency | η_fan | 0.60 | – |
| Condenser pressure drop | ΔP_cond | 60 | Pa |
| Evaporator pressure drop | ΔP_evap | 90 | Pa |
| HRX per-side pressure drop | ΔP_HRX,side | 150 | Pa |
| Collector pressure drop | ΔP_solar | 40 | Pa |
| Duct pressure drop | ΔP_duct | 60 | Pa |
| Electric-resistance heater efficiency | η_elec | 1.00 | – |
| Dry-air specific heat | c_p,da | 1.006 | kJ/(kg·K) |
| Water-vapor specific heat | c_p,v | 1.86 | kJ/(kg·K) |
| Liquid-water specific heat | c_p,w | 4.186 | kJ/(kg·K) |
| Latent heat of vaporisation at 0 °C | h_fg,0 | 2501 | kJ/kg |
| Latent heat of vaporisation at 45 °C | h_fg | 2394.8 | kJ/kg |

### 3.2 Heat-pump cycle

The cycle is closed in four refrigerant states, indexed in the direction of refrigerant flow; the constants used below are listed in Table 2.

State 1 (compressor suction). The evaporation pressure is fixed by the saturation curve at the assigned evaporation temperature, and the suction state is set ΔT_sh above saturation:
- P_evap = P_sat(T_evap),   T_1 = T_evap + ΔT_sh,                                                    (1)
with h_1 and s_1 obtained from CoolProp at (T_1, P_evap).

State 2 (compressor discharge). With P_cond = P_sat(T_cond), the isentropic discharge enthalpy is h_2s = h(P_cond, s_1) and the actual discharge enthalpy follows from the isentropic efficiency:
- h_2 = h_1 + (h_2s − h_1) / η_is.                                                                   (2)

State 3 (condenser outlet). The condenser-outlet liquid is subcooled by ΔT_sc:
- T_3 = T_cond − ΔT_sc,    h_3 = h(T_3, P_cond).                                                     (3)

State 4 (expansion-valve outlet). The expansion is isenthalpic:
- h_4 = h_3.                                                                                         (4)

The per-kilogram cycle duties on the refrigerant side are
- q_cond = h_2 − h_3,    q_evap = h_1 − h_4.                                                         (5)

The refrigerant mass flow rate is given by the air-side condenser duty Q_cond,target that the cycle must deliver to lift the condenser-inlet air to the chamber set point:
- ṁ_ref = Q_cond,target / q_cond,                                                                    (6)
- Q_cond,target = ṁ_da · [ h_a(T_set, ω_in) − h_a(T_cond,in, ω_in) ],                                (7)
with the moist-air specific enthalpy h_a defined in §3.6. All ten configurations reported in this work operate open-loop, so the humidity ratio across the condenser is unchanged.

The condenser heating capacity and the evaporator cooling capacity are given by
- Q_cond = ṁ_ref · q_cond,    Q_evap = ṁ_ref · q_evap.                                               (8)

The compressor power consumption is given by
- W_comp = ṁ_ref · (h_2 − h_1) / η_mech.                                                             (9)

The cycle coefficient of performance is defined by
- COP = Q_cond / W_comp.                                                                             (10)

Each refrigerant-to-air coil is closed by a sensible effectiveness applied between the coil-side air state and the refrigerant saturation state:
- T_air,cond,out = T_air,cond,in + ε_cond · ( T_cond − T_air,cond,in ),                              (11)
- T_air,evap,out = T_air,evap,in − ε_evap · ( T_air,evap,in − T_evap ),                              (12)
and the refrigerant-side saturation temperatures are set by the pinches
- T_cond = T_air,cond,out + ΔT_pinch,cond,                                                           (13)
- T_evap = T_air,evap,in − ΔT_pinch,evap.                                                            (14)

For the conditioning-side condenser, T_air,cond,out is additionally constrained to the chamber set point T_set under nominal sizing, so Eqs. (11)-(14) collapse to a one-shot algebraic update.

### 3.3 Solar air collector

The collector energy balance and the absorber-plate transient are written as:

- Absorbed solar power: Q_abs = A_c · η_opt · K_θ · G. (15)
- Convective-radiative loss to ambient: Q_loss = A_c · U_L · (T_in − T_amb). (16)
- Air-side number of transfer units and heat-removal factor:
  NTU = (A_c · U_L · F′) / (ṁ_da · c_p,da), (17)
  F_R = (ṁ_da · c_p,da) / (A_c · U_L) · [ 1 − exp(−NTU) ]. (18)
- Useful gain and air-side outlet temperature:
  Q_useful = max( 0, F_R · (Q_abs − Q_loss) ), (19)
  T_out = T_in + Q_useful / (ṁ_da · c_p,da), (20)
  with Q_useful = 0 and T_out = T_in whenever G < 10 W/m² (cut-in).

The absorber plate stores heat and lags step changes in G(t); this is captured by a first-order relaxation of the plate temperature T_p (°C) between timesteps, with time constant τ = C_p / (A_c · U_L) and relaxation factor α = dt / (τ + dt), giving τ on the order of a few minutes for the baseline geometry:
- T_p(t + dt) = T_p(t) + α · ( T_p,ss − T_p(t) ), (21)

with T_p,ss (°C) the steady-state plate temperature consistent with the current G and T_in. The humidity ratio is unchanged across the collector, ω_out = ω_in.

### 3.4 Drying kinetics

The kinetic model is a five-parameter Arrhenius-humidity-velocity-thickness rate law applied per tray and per timestep. The five parameters were obtained once, off-line, by single-stage nonlinear least squares against the thin-layer apple-drying dataset of Royen et al. [ledger #40], spanning 40-50 °C, 0.6-1.1 m/s, and 4-10 mm slab thickness, with 1573 moisture-ratio observations after pool-adjacent-violators isotonic cleaning.

#### 3.4.1 Rate law

The Arrhenius temperature dependence and the multiplicative power-law modifiers in relative humidity, air velocity, and slice thickness follow the dependency structure established in the apple thin-layer modelling literature [Royen et al. 2020, ledger #40; Midilli et al. 2002, ledger #Midilli2002, VERIFY ledger ID; Sharabiani et al. 2021, ledger #21]; in the present work the four variables (T, RH, v, d) are fit simultaneously by a single closed-form rate law:

- K(T, RH, v, d) = K_ref · exp[ (Ea / R) · ( 1/T_ref − 1/T ) ] · exp(−α_RH · RH) · (v / v_ref)^γ_v · (d_ref / d)^δ_d, (22)

evaluated at the local chamber-air temperature T (K), local relative humidity RH (fraction), local superficial velocity v (m/s), and slice thickness d (m), with the reference state (T_ref, v_ref, d_ref) from Table 2. The five fitted parameters of Eq. (22) are summarised below.

| Term | Symbol | Physical meaning |
|---|---|---|
| Reference rate constant | K_ref | Rate constant at the reference state (T_ref, RH = 0, v_ref, d_ref). |
| Arrhenius activation-temperature ratio | Ea/R | Temperature sensitivity of the rate. |
| Humidity attenuation coefficient | α_RH | Negative-exponential coefficient that attenuates the rate as local RH rises. |
| Velocity exponent | γ_v | Power-law exponent on v/v_ref. |
| Thickness exponent | δ_d | Power-law exponent on d_ref/d. |

The first-order moisture update per tray and per timestep is
- X_new = max( X_old − K · ( X_old − X_eq ) · dt, X_eq ), X_eq = 0, (23)

with X (kg water / kg dry solid) the local tray-average moisture on dry basis. The max-operator floor prevents non-physical undershoot at large K · dt and is a numerical safeguard rather than a model assumption.

#### 3.4.2 Air-side capacity gate

The kinetic update of Eq. (23) can request more water than the chamber air can carry at the local mass flow and saturation limit. The per-step removal is therefore capped by the moist-air capacity. With ρ_s the apparent density (Table 2), A_tray the per-tray air-contact area, and d the slice thickness, the kinetic increment expressed as a water-mass removal per tray is

- Δm_w,kin = ρ_s · A_tray · d · ( X_old − X_new ). (24)

The maximum admissible humidity-ratio rise across the tray bank, Δω_max, is obtained by bisection on the saturation constraint

- RH( T_out, ω_in + Δω_max ) ≤ RH_out,max = 1.0, (25)

where RH_out,max is the chamber-air saturation limit (condensation in the chamber air is not modeled). The corresponding air-capacity removal is

- Δm_w,air = ṁ_da · Δω_max · dt, (26)

and the per-tray cap is

- Δm_w = min( Δm_w,kin, Δm_w,air / n_trays ). (27)

Equations (24)-(27) are applied tray by tray, so the outlet of tray j is the inlet of tray j+1. Per tray, the humidity ratio is updated by

- ω_out = ω_in + Δm_w / ( ṁ_da · dt ), (28)

and the air enthalpy is closed by the ASHRAE near-constant-enthalpy humidification with the sensible enthalpy of the makeup liquid water at the tray-inlet temperature T_in (°C) added explicitly,

- h_out = h_in + Δω · c_p,w · T_in. (29)

The tray-outlet temperature is recovered from Eq. (38).

#### 3.4.3 Fit procedure

The five parameters of Eq. (22) are obtained by single-stage nonlinear least squares on the 1573 cleaned moisture-ratio observations of the Royen et al. dataset [ledger #40], with the reference state fixed at T_ref = 50 °C, v_ref = 1.1 m/s, and d_ref = 6 mm (the upper edge of the calibration band in T and v, and the central thickness). The form of Eq. (22) is chosen for its compatibility with the per-step first-order moisture update of Eq. (23) at the tray level and for the physical interpretation of each of its five parameters as a separate operator-controllable knob in T, RH, v, and d. The fitted parameter values, their confidence intervals, and the comparison against the published apple-drying activation-energy band are reported in Section 5.

### 3.5 Heat-recovery exchanger

The HRX is treated as a sensible counter-flow plate exchanger of fixed effectiveness ε_HRX (Table 2), with equal capacity rates on both sides and no cold-side condensation. The two outlet temperatures follow from the effectiveness definition,

- T_amb,heated = T_amb + ε_HRX · ( T_exh − T_amb ), (30)
- T_exh,cooled = T_exh − ε_HRX · ( T_exh − T_amb ), (31)

evaluated at the current ambient and chamber-exhaust states. The ambient (cold) side carries no moisture change, ω_amb,out = ω_amb, since wall condensation can occur only on a surface cooled below the local dewpoint and the cold-side wall is always warmer than the cold-side air. On the exhaust (hot) side the cooled-exhaust temperature is compared against the exhaust dewpoint T_dp(ω_exh), obtained by bisection of ω = ω_sat(T_dp, p_atm). When T_exh,cooled < T_dp(ω_exh) the cooled stream is taken as saturated at its temperature and the corresponding humidity ratio is

- ω_exh,out = min( ω_sat(T_exh,cooled, p_atm), ω_exh ), (32)

so that moisture can only be removed from the hot stream; otherwise ω_exh,out = ω_exh and no latent transfer is recorded. The latent heat released by hot-side condensation is carried on the moist-air enthalpy of Eq. (37) and therefore enters the absolute HRX duty
- Q_HRX = ṁ_da · [ h_a(T_amb,heated, ω_amb) − h_a(T_amb, ω_amb) ], (33)

reported alongside the cycle duties; the effectiveness ε_HRX of Eqs. (30)-(31) is therefore strictly a sensible-side definition, and the cold-side enthalpy gain that closes the energy balance includes both the sensible rise and, when applicable, the latent release from the hot stream.

### 3.6 Air properties at component inlet and outlet

The saturation vapor pressure of water is taken from the Tetens correlation [Tetens 1930, ledger #Tetens1930] with T in °C,

- p_sat(T) = 610.94 · exp[ 17.625 · T / ( T + 243.04 ) ] Pa. (34)

The humidity ratio and the relative humidity are exchanged through

- ω(T, RH) = 0.62198 · RH · p_sat(T) / [ p_atm − RH · p_sat(T) ], (35)
- RH(T, ω) = [ ω · p_atm / ( 0.62198 + ω ) ] / p_sat(T). (36)

The moist-air specific enthalpy on a per-kilogram-dry-air basis is

- h_a(T, ω) = c_p,da · T + ω · ( h_fg,0 + c_p,v · T ), (37)

with c_p,da, c_p,v, and h_fg,0 from Table 2. The inversion used when an air state is known by its enthalpy and humidity ratio is

- T( h, ω ) = ( h − ω · h_fg,0 ) / ( c_p,da + ω · c_p,v ). (38)

### 3.7 Variable-T_cond control

In configurations B2 and E3 the solar collector sits downstream of the condenser, so the collector inlet equals the condenser air-outlet, T_solar,in = T_cond,air,out. The upstream condenser-inlet temperature T_cond,air,in differs between the two: T_cond,air,in = T_amb in B2 and T_cond,air,in = T_HRX,cold-out in E3. The heat pump and collector share the lift to T_set in series, and the share is set at every timestep by

- ΔT_solar,target = T_set − T_solar,in, (39)
- α_solar = min( 1, max( 0, Q_useful / ( ṁ_da · c_p,da · ΔT_solar,target ) ) ), (40)

where α_solar is the collector's fractional share of the total lift, ΔT_solar,target is the temperature rise across the collector required to reach T_set, and Q_useful follows from Eqs. (15)-(19) at the local T_solar,in and G(t). The condenser air-outlet target is

- T_cond,air,out = T_set − α_solar · ΔT_solar,target, (41)

so the heat pump lifts the air from T_cond,air,in up to that target and the collector finishes the rest. When α_solar = 1 the chamber demand is met by the collector alone and the heat pump is switched off for the timestep (solar-priority cutoff); when α_solar = 0 the cycle reduces to fixed-T_cond operation. The refrigerant-side T_cond follows from Eqs. (11)-(14), which lowers the compression ratio when solar gain is available. Configurations A, B1, C1, D1, D2, E1, and E2 operate at fixed T_cond and do not use this branch.

### 3.8 Iterative evaporator sizing (B1_open, B2_open, D2, E2, E3)

In configurations B1_open, B2_open, D2, E2, and E3 the evaporator source stream is the chamber exhaust (B1_open, B2_open) or the cooled exhaust leaving the HRX hot side (D2, E2, E3). The mass flow on the evaporator side is therefore fixed at the main-loop dry-air mass flow ṁ_da, but the evaporator duty Q_evap (Eq. 8) generally requires more capacity than the exhaust stream alone can supply, particularly during the constant-rate drying period when the exhaust dewpoint is near the chamber set point. A second ambient stream of mass flow ṁ_amb,extra is therefore mixed into the evaporator inlet to make up the shortfall; ṁ_amb,extra is found at every timestep by a fixed-point iteration on the evaporator energy balance because the mixing changes T_evap,source, which changes the heat-pump COP, which changes Q_evap, creating a circular dependency that a single closed-form pass cannot resolve. An earlier closed-form supplement was retained for D2 through 2026-05-29 and replaced by the iterative routine after a Namche Q1 A/B cell exposed an unbounded supplement whenever T_amb approached the evaporator-coil temperature.

- Initial guess: ṁ_amb,extra,0 = 0.                                                                  (42)
- Mixed evaporator inlet state at iteration k:
  T_evap,in,k = ( ṁ_da · T_exh,cooled + ṁ_amb,extra,k · T_amb ) / ( ṁ_da + ṁ_amb,extra,k ),         (43)
  ω_evap,in,k = ( ṁ_da · ω_exh,cooled + ṁ_amb,extra,k · ω_amb ) / ( ṁ_da + ṁ_amb,extra,k ).         (44)
- Evaporator outlet temperature from Eq. (12) at T_evap = T_evap,in,k − ΔT_pinch,evap:
  T_evap,out,k = T_evap,in,k − ε_evap · ( T_evap,in,k − T_evap ).                                   (45)
- The shortfall in evaporator duty is
  ΔQ_k = Q_evap,target − ( ṁ_da + ṁ_amb,extra,k ) · c_p,da · ( T_evap,in,k − T_evap,out,k ),        (46)
- and the next-iterate makeup flow is obtained by Newton update on ṁ_amb,extra against ΔQ.         (47)

The iteration is terminated when |ΔQ_k| < 1 W or after 20 iterations. The second-blower fan power is then incremented at every timestep by ṁ_amb,extra · Δp / (ρ · η_fan) (Section 3.10).

### 3.9 Electric-resistance baseline (Configuration 0)

Configuration 0 is a pure electric-resistance dryer used as the energy-cost anchor. The chamber demand is supplied by a resistance heater upstream of the chamber inlet,

- Q_heater = ṁ_da · c_p,da · ( T_set − T_amb ), (48)
- W_elec = Q_heater / η_elec,    η_elec = 1.00. (49)

The fan power follows Section 3.10 with the single-blower variant.

### 3.10 Fan power and pressure drop

The path-summed pressure drop ΔP_j on each blower combines the per-component values in Table 2 with the plenum losses of the parallel-tray chamber geometry (Section 3.7). The chamber air enters a low-velocity plenum, splits across ten parallel tray channels of 15 mm air gap (Section 3.7, Table 2), and recombines in a second plenum on the downstream face; the channel-face area ratio is A_channel / A_plenum ≈ 0.1, so the inlet contraction is treated as a sharp area change (K_plenum,in = 0.5, sudden contraction asymptote at small area ratio) and the outlet expansion as a sudden dump into the downstream plenum (K_plenum,out = 1.0). The per-blower plenum loss is therefore (K_plenum,in + K_plenum,out) · q_channel = 1.5 · q_channel, with q_channel = ½ · ρ_air · v_channel² evaluated at the tray-channel superficial velocity (v = 1.1 m/s, Table 2) and at the chamber set-point density ρ_air(T_set). The shaft power of blower j follows the standard fan-affinity relation,

- W_fan,j = ( ṁ_da,j / ρ_air ) · ΔP_j / η_fan, (50)

and the total fan-power input is

- W_fan = W_fan,main + W_fan,evap. (51)

Configuration 0 carries the main blower only.

### 3.11 Specific energy consumption

The integrated electrical input to the air loop is the time integral of the compressor shaft power (Eq. 9), the two-blower fan power (Eq. 51), and the resistance-heater electrical power (Eq. 49, Configuration 0 only),
- W_total(t) = ∫_0^t [ W_comp(τ) + W_fan(τ) + W_elec(τ) ] dτ.                                       (52)

The cumulative mass of water removed from the product is m_w(t) = m_p,dry · ( X_0 − X̄(t) ), with X̄ the tray-averaged moisture on dry basis. The specific energy consumption is then
- SEC(t) = W_total(t) / m_w(t)   [kWh / kg water],                                                  (53)

and the specific moisture extraction rate is the reciprocal expressed in mass-per-energy units,
- SMER(t) = m_w(t) / W_total(t)   [kg water / kWh].                                                 (54)

SEC is the principal performance metric reported in Section 5; SMER is reported alongside where the literature comparator uses that convention.

### 3.12 Initial conditions

Each batch starts at t = 0 with X(j) = X_0 on every tray, T_chamber and T_p,solar set to T_amb at the start hour, and the cumulative integrals W_total and m_w at zero. The refrigerant cycle is seeded from Eqs. (13)-(14) at the t = 0 air states and re-seeds from the previous step thereafter; no warm-up transient is excluded from the SEC integration of Eq. (52).

## 4. Simulation setup (~1100 w)

### 4.1 Implementation and numerical scheme

The model is implemented in Python 3.11. Refrigerant-side state points for R134a are evaluated from CoolProp [ledger #CoolProp] at every timestep; psychrometric properties of moist air use the ideal-gas formulation of Eqs. (34)-(38) with the IAPWS-IF97 latent heat at 45 °C (Table 2). The coupled subsystem equations are integrated with an explicit Euler scheme at dt = 60 s, well below the slowest characteristic time of any subsystem (collector thermal time constant of a few minutes; chamber air residence on the order of seconds; the refrigerant cycle is quasi-steady within a step). Within each timestep the refrigerant cycle of Eqs. (1)-(14) is solved to closure of the first-law balance Q_cond = Q_evap + W_comp; the global water-mass balance Σ Δm_w = ṁ_da · ( ω_exh − ω_amb ) · t_run is checked at the end of every run as a numerical consistency test, and both balances close to numerical precision in every configuration considered. A batch is terminated when the slowest tray reaches X_f = 0.20 (kg water per kg dry solid), or when the simulation time exceeds 72 h.

### 4.2 Sites and weather data

Hourly ambient temperature, relative humidity, global horizontal irradiance, plane-of-array irradiance, surface pressure, and 10 m wind speed are drawn from the PVGIS-SARAH3 typical-meteorological-year (TMY) record at four Nepalese sites that bracket the climate envelope of the country: Biratnagar (26.46° N, 87.28° E, 72 m a.s.l., tropical Terai), Kathmandu (27.70° N, 85.33° E, 1350 m, sub-tropical mid-hill capital), Jomsom (28.78° N, 83.72° E, 2700 m, temperate trans-Himalayan rain shadow in Mustang), and Namche (27.81° N, 86.71° E, 3440 m, sub-alpine Solukhumbu). The four sites span 3368 m of elevation and cover ambient drybulb conditions from below 0 °C at Namche in January to above 30 °C at Biratnagar in May [VERIFY: PVGIS-SARAH3 TMY per-site hourly range]. The local atmospheric pressure used in the psychrometric closures of Eqs. (35)-(36) is recomputed from site elevation through the standard-atmosphere relation. The plane-of-array irradiance feeding the collector model of Eq. (15) is requested from PVGIS at slope 45° and azimuth 0° (true south, matching the dominant rooftop and ground-mount orientation across the four sites); the incidence-angle modifier K_θ inside the collector model is consequently fixed at unity to avoid double-counting the angle-of-incidence correction already applied inside the PVGIS-SARAH3 POA pipeline. The hourly TMY is consumed in full by the Stage-2 every-5-day production grid (Section 4.4); seasonal slices used in Section 5 are produced downstream of the matrix by binning the single-batch SECs into the four calendar quarters Q1 to Q4.

### 4.3 Dryer configurations

Twelve dryer simulators are implemented in this work, grouped into seven topology families (0, A, B1, B2, C1, D, E) with explicit open- and closed-loop variants where both modes are physically meaningful. The recirculation fraction r ∈ [0, 1) is the dry-mass-flow share of chamber exhaust that is re-mixed into the loop; r = 0 is fully open (single pass through the chamber) and r > 0 closes the loop by feeding back a fraction of the exhaust. Configuration 0 is a pure electric-resistance baseline used to anchor the energy-saving claims of the heat-pump configurations on a common drying schedule. Configuration A is the heat-pump-only reference and contains no solar collector and no HRX; in the open mode (r = 0) it is sized as Amb → Cond → Chamber with the evaporator on a parallel ambient stream, and in the closed mode (r > 0) it collapses into a single loop in which the recirculated exhaust mixes with ambient and the mixture passes inline through the evaporator (which doubles as dehumidifier) before the condenser. Configurations B1 and B2 add a solar collector to the heat-pump baseline at two junctions on the chamber-side air loop, upstream of the condenser (B1) or downstream of it (B2), and each is implemented in an explicit open variant (B1_open, B2_open) and a closed variant (B1_closed, B2_closed); the open variants run the evaporator on the chamber exhaust with iterative ambient supplement when the exhaust enthalpy is insufficient (the same fixed-point routine used by E2 and E3, Section 3.8), and the closed variants form a single recirculating loop in which evaporator dehumidification is inline. Configuration C1 places the solar collector on the evaporator-source stream rather than the chamber stream; the r = 0 mode is an open cascade in which the main chamber stream still runs Amb → Cond → Chamber and the solar-heated parallel stream feeds the evaporator alone, and the r > 0 mode is a closed loop in which ambient is first solar-heated, then mixed with the recirculated exhaust, then passes through the evaporator and condenser to the chamber. Configurations D1 and D2 add an HRX on the chamber exhaust without a collector and differ in whether the cooled exhaust is vented (D1) or routed to the evaporator with iterative ambient supplement (D2, same fixed-point routine as B1_open, B2_open, E2, E3; Section 3.8). Configurations E1, E2, and E3 combine all three components: E1 vents the cooled exhaust and places the solar collector upstream of the condenser; E2 reuses the cooled exhaust as the evaporator source with the solar collector still upstream of the condenser; and E3 reuses the cooled exhaust at the evaporator and places the solar collector downstream of the condenser under a solar-priority control law in which the heat pump shuts off whenever the HRX outlet plus the solar gain alone delivers the set-point. Table 1 lists the code-verified air paths for every simulator and mode. The reference integrated configuration E2 is shown in Fig. 1 and the solar-priority variant E3 in Fig. 2 [VERIFY: figures pending].

**Table 1.** Code-verified air paths for the twelve simulators evaluated, one row per (config, r-mode) pair. "Amb" = site ambient air; "Cond" = heat-pump condenser; "Evap" = heat-pump evaporator; "HRX-cold"/"HRX-hot" = cold-side and hot-side of the heat-recovery exchanger; "Exh" = chamber exhaust; "Exh_cooled" = cooled exhaust leaving HRX-hot; "Mix" = mass-weighted blend of the recirculated exhaust and the inflowing ambient stream (mix ratio set by r).

| Config       | r        | Main (chamber-side) path                                                | Evaporator source                                   | HP control                       | Components                |
|--------------|----------|-------------------------------------------------------------------------|-----------------------------------------------------|----------------------------------|---------------------------|
| 0            | —        | Amb → Electric heater → Chamber                                         | —                                                   | —                                | Electric resistance only  |
| A            | r = 0    | Amb → Cond → Chamber                                                    | Amb (parallel)                                      | Fixed T_cond                     | HP                        |
| A            | r > 0    | Mix(r·Exh + Amb) → Evap → Cond → Chamber (single loop, inline evap)     | Inline on main loop                                 | Fixed T_cond, first-law sized    | HP                        |
| B1_open      | r = 0    | Amb → Solar → Cond → Chamber                                            | Exh (+ iterative Amb supplement)                    | Fixed T_cond                     | Solar + HP                |
| B2_open      | r = 0    | Amb → Cond(var T_cond) → Solar → Chamber                                | Exh (+ iterative Amb supplement)                    | Variable T_cond, solar-priority  | Solar + HP                |
| B1_closed    | r > 0    | Mix(r·Exh + Amb) → Evap → Solar → Cond → Chamber                        | Inline on main loop                                 | Fixed T_cond, first-law sized    | Solar + HP                |
| B2_closed    | r > 0    | Mix(r·Exh + Amb) → Evap → Cond(var T_cond) → Solar → Chamber            | Inline on main loop                                 | Variable T_cond, solar-priority  | Solar + HP                |
| C1           | r = 0    | Amb → Cond → Chamber                                                    | Amb → Solar → Evap (parallel)                       | Fixed T_cond                     | Solar + HP                |
| C1           | r > 0    | Amb → Solar → Mix(+ r·Exh) → Evap → Cond → Chamber                      | Inline on main loop                                 | Fixed T_cond, first-law sized    | Solar + HP                |
| D1           | r = 0    | Amb → HRX-cold → Cond → Chamber; Exh → HRX-hot → vent                   | Amb (parallel)                                      | Fixed T_cond                     | HRX + HP                  |
| D2           | r = 0    | Amb → HRX-cold → Cond → Chamber; Exh → HRX-hot → Exh_cooled             | Exh_cooled (+ iterative Amb supplement)             | Fixed T_cond                     | HRX + HP                  |
| E1           | r = 0    | Amb → HRX-cold → Solar → Cond → Chamber; Exh → HRX-hot → vent           | Amb (parallel)                                      | Fixed T_cond                     | Solar + HRX + HP          |
| **E2**       | r = 0    | Amb → HRX-cold → Solar → Cond → Chamber; Exh → HRX-hot → Exh_cooled     | Exh_cooled (+ iterative Amb supplement)             | Fixed T_cond                     | Solar + HRX + HP (Fig. 1) |
| **E3**       | r = 0    | Amb → HRX-cold → Cond → Solar → Chamber; Exh → HRX-hot → Exh_cooled     | Exh_cooled (+ iterative Amb supplement)             | Variable T_cond, solar-priority  | Solar + HRX + HP (Fig. 2) |

A common drying-air set-point, fresh load, and tray geometry are imposed across all twelve simulators in Table 1; the fixed chamber and product parameters are collected in Table 2. The HRX effectiveness ε_HRX = 0.70 and the heat-pump cycle parameters are also held constant across the configurations that contain those components.

### 4.4 Simulation matrix

The matrix is built at daily granularity in two stages: a Stage-1 r-screening sweep that picks a per-site recirculation fraction r* for each closed-loop-capable configuration, and a Stage-2 production sweep that evaluates every configuration at its chosen r* over a year-round every-5-day batch grid. For both stages a single batch is one independent run starting from the first weather row at or after 08:45 NPT on the nominal calendar date and integrating for up to 24 simulated hours; the last two calendar days of each year are dropped (no 24 h forward weather window in the source PVGIS file), and a batch terminates when the slowest tray reaches X_f = 0.20 (kg water per kg dry solid) or at the 24 h cap, whichever comes first.

Stage 1, the r-screening sweep, runs 1,056 single-batch simulations enumerated in `outputs/quarterly/screening_batch_starts.csv`. Four r-accepting configurations (A, C1, B1_closed, B2_closed) are evaluated at 4 sites × 12 calendar days per site (one mid-month day per calendar month, sampling the full annual climate range while keeping the screen tractable) × six recirculation fractions r ∈ {0, 0.3, 0.5, 0.7, 0.8, 0.9}. The closed-loop variants B1_closed and B2_closed skip r = 0 because the closed-loop topology collapses at zero recirculation, leaving 5 r-values for those two configurations and 6 for A and C1; the screen therefore totals 4 · 12 · (2 · 6 + 2 · 5) = 1,056 single-batch SECs. For each (configuration, site) pair the per-r SEC is averaged over the 12 screening days, and the recirculation fraction r* that minimises the screen-mean SEC is selected as the per-site production value; ties within 1 % of the minimum are broken in favour of the smaller r-value (lower fan power and shorter mixing length). The r* table is written to `outputs/quarterly/r_star_by_config_site.csv` by `scripts/pick_r_star.py` and passed to Stage 2 through the `--r-star-csv` flag of `scripts/run_quarterly_sweep.py`.

Stage 2, the production sweep at fixed r*, runs 5,328 single-batch simulations enumerated in `outputs/quarterly/production_batch_starts.csv`. The eleven heat-pump-bearing configurations of Table 1 are evaluated at 4 sites × 74 calendar days per site (every fifth day of the year, starting from 1 January, with the last two days of Q4 dropped for the same 24 h forward-window reason as above) × one recirculation fraction per (configuration, site): r = r* for the four r-accepting configurations (A, C1, B1_closed, B2_closed) and r = 0 for the seven remaining open-loop variants (B1_open, B2_open, D1, D2, E1, E2, E3). The collector area is fixed at the baseline A_c = 10 m² for every solar-bearing configuration except E2, which is additionally swept at the same r and the same 74 batches per site over A_c ∈ {2, 4, 6, 8, 10, 12, 15, 20} m², contributing 7 extra collector-area runs on top of the A_c = 10 m² baseline. The Stage-2 workload is therefore (11 + 7) · 4 · 74 = 5,328 single-batch simulations; the E2 area sweep is independent of r* because the E2 evaporator inherits the cooled-exhaust source from the HRX hot side rather than from a recirculated chamber stream (Section 3.8). The resistance-only baseline (Config 0) is run separately as an analytical anchor at each site and is not part of the sweep output. Across the two stages the matrix delivers 6,384 simulator-batch records, with wall times of approximately 3 h for Stage 1 and 15 h for Stage 2 on the reference workstation.

The Stage-2 every-5-day grain places approximately 18 batches per (configuration, site, calendar quarter). Under the empirical SEC standard deviation σ ≈ 0.08 kWh kg⁻¹ measured on the corresponding Stage-1 SEC distribution at A_c = 10 m², the resulting one-sigma uncertainty on a quarterly-mean SEC is σ/√n ≈ 0.019 kWh kg⁻¹. This is comfortably below the typical cross-family SEC delta (0.05 to 0.30 kWh kg⁻¹ across the HP, HP + Solar, HP + HRX, and HP + HRX + Solar families; Section 5.1) and below the headline E2-vs-E3 gap at fixed site (about 0.02 to 0.05 kWh kg⁻¹; Section 5.2). Close-pair calls within a single family at a fixed site (E1 vs E2 or D1 vs D2, for example) sit at or below the per-quarter resolution and are flagged in the relevant Section 5 subsections as requiring a finer-grain follow-up.

The seasonal slicing reported in Section 5 is performed downstream of the matrix by aggregating the Stage-2 daily batches into calendar quarters (Q1 = Jan to Mar, Q2 = Apr to Jun, Q3 = Jul to Sep, Q4 = Oct to Dec); the Q3 mean is reported with the caveat that the principal apple-harvest and small-scale drying calendar in Nepal sits in Q4 (autumn harvest) and Q1 to Q2 (winter and spring storage and pre-monsoon drying), and field practice in the monsoon Q3 window is typically suspended at all four sites. The full-year mean is reported alongside the four quarterly means for completeness.

## 5. Results and discussion (~1500 w)

### 5.1 Cross-family topology ranking

Fig. 3 reports the SEC of the nine HP-bearing configurations and the resistive baseline at the four sites under the annual TMY and four 60-day seasonal windows, all at T_set = 45 °C, A_c = 10 m², r = 0. Configurations are grouped by heating-component family and sorted by ascending annual-mean SEC within each family; Config 0 is shown on a separate colour scale below.

![Fig. 3. Cross-family SEC heatmap. Configurations are grouped by heating-component family. Yellow = lower (better) SEC; dark blue = higher SEC. Config 0 is shown on a separate scale below.](../outputs/paperplots/fig3_topology_ranking_heatmap.png)

Averaged across the four sites, the family ranking under the annual TMY is Electric ≫ HP > HP + Solar > HP + HRX > HP + HRX + Solar. Table 3 reports the family-mean annual SEC and the reduction relative to the HP-only baseline.

**Table 3.** Family-mean annual SEC and reduction relative to HP-only (Config A). Each family mean is averaged across its member configurations and across the four sites.

| Family | Member configs | Mean annual SEC (kWh kg⁻¹) | Reduction vs HP-only |
|---|---|---|---|
| Electric resistance | 0 | 1.93 | — |
| HP | A | 0.55 | reference |
| HP + Solar | B1, B2, C1 | 0.37 | 33 % |
| HP + HRX | D1, D2 | 0.32 | 41 % |
| HP + HRX + Solar | E1, E2, E3 | 0.19 | 65 % |

The combined HP + HRX + Solar saving (0.36 kWh kg⁻¹) is 88 % of the sum of the individual HRX and Solar savings (0.23 + 0.18 = 0.41 kWh kg⁻¹). The two components therefore interact sub-additively: HRX and solar both reduce the same gross heat-supply duty on the HP, so once one is in place the load available for the other to offload is smaller.

Kathmandu carries the highest annual SEC at every family, ranging from 1.3 × the Biratnagar value (HP + HRX) to 1.7 × (HP + Solar). Dhulikhel and Taplejung fall between Biratnagar and Kathmandu. Within each site, winter is the highest-SEC season at every family; for the HP + HRX + Solar family the seasonal range is 0.078-0.137 kWh kg⁻¹ at Biratnagar and 0.109-0.196 kWh kg⁻¹ at Taplejung.

Drying time is 14.4 h (range 14.2-14.6 h) at every configuration in Fig. 3, with the chamber inlet pinned at T_set across all topologies. The SEC differences in Fig. 3 are therefore differences in electrical work per kilogram of removed water at fixed residence time. The Table 5 set-point sweep below isolates the additional dependence of drying time on T_set and confirms that the topology-driven SEC ranking is preserved when the schedule itself is shortened (Section 5.2.1).

### 5.2 Solar-collector placement: chamber stream vs evaporator stream, pre-condenser vs post-condenser

The three solar-bearing single-component variants (B1, B2, C1) and the two solar-bearing E variants (E2, E3) share the same Hottel-Whillier-Bliss collector (Section 4.2) and the same baseline area A_c = 10 m². They differ only in where the heated air is delivered: the chamber-supply stream upstream of the condenser (B1, E2), the chamber-supply stream downstream of the condenser (B2, E3), or a parallel stream that supplies only the refrigerant evaporator (C1). Table 4 isolates the chamber-stream-vs-evaporator-stream choice (B1 vs C1) at fixed condenser placement; Fig. 4 isolates the pre-condenser-vs-post-condenser choice within the chamber stream (B1 vs B2 and E2 vs E3). Config A is included in Table 4 as the no-solar reference.

**Table 4.** Solar on the chamber stream (B1) vs solar on the evaporator stream (C1), with Config A as no-solar reference. Annual baseline, A_c = 10 m², r = 0. Q_solar, Q_cond, Q_evap, W_comp are cumulative over the drying batch (kWh); T_evap, T_cond, COP are energy-weighted means over the HP-on interval.

| Config | Site | Q_solar (kWh) | η_solar | Q_cond (kWh) | Q_evap (kWh) | W_comp (kWh) | T_evap (°C) | T_cond (°C) | COP | SEC (kWh kg⁻¹) |
|---|---|---|---|---|---|---|---|---|---|---|
| A  | Biratnagar | —    | —     | 36.4 | 27.7 | 8.75 |  8.5 | 55.0 | 4.16 | 0.485 |
| A  | Kathmandu  | —    | —     | 41.9 | 29.7 | 12.22| -0.3 | 55.0 | 3.43 | 0.664 |
| A  | Dhulikhel  | —    | —     | 36.5 | 26.9 | 9.68 |  4.2 | 55.0 | 3.78 | 0.533 |
| A  | Taplejung  | —    | —     | 35.6 | 26.0 | 9.60 |  3.5 | 55.0 | 3.71 | 0.528 |
| B1 | Biratnagar | 21.9 | 0.513 | 17.2 | 13.1 | 4.16 |  8.3 | 55.0 | 4.14 | 0.246 |
| B1 | Kathmandu  | 15.2 | 0.501 | 26.5 | 18.7 | 7.74 | -0.4 | 55.0 | 3.42 | 0.431 |
| B1 | Dhulikhel  | 14.8 | 0.505 | 21.5 | 15.9 | 5.70 |  4.3 | 55.0 | 3.78 | 0.326 |
| B1 | Taplejung  | 16.1 | 0.498 | 20.1 | 14.6 | 5.47 |  3.0 | 55.0 | 3.67 | 0.313 |
| C1 | Biratnagar | 21.9 | 0.513 | 36.4 | 30.8 | 5.61 | 17.4 | 55.0 | 6.50 | 0.321 |
| C1 | Kathmandu  | 15.2 | 0.501 | 41.9 | 32.7 | 9.19 |  8.8 | 55.0 | 4.56 | 0.506 |
| C1 | Dhulikhel  | 14.8 | 0.505 | 36.5 | 29.4 | 7.12 | 12.9 | 55.0 | 5.13 | 0.400 |
| C1 | Taplejung  | 16.1 | 0.498 | 35.6 | 28.8 | 6.84 | 11.6 | 55.0 | 5.21 | 0.384 |

B1 and C1 collect the same solar input at every site (identical Q_solar and η_solar in each row of Table 4), because the collector inlet is ambient air in both topologies. Their heat-pump duty diverges. In B1 the solar collector and the condenser sit in series on the chamber supply, so the solar lift reduces the residual temperature lift required of the condenser one-for-one: Q_cond is depressed by an amount close to Q_solar (Biratnagar 36.4 → 17.2 kWh; Kathmandu 41.9 → 26.5 kWh) at fixed T_cond = 55 °C. The cycle COP stays at the Config-A level because T_evap is unchanged, and W_comp drops in proportion to Q_cond. In C1 the solar stream is parallel to the chamber path and only warms the refrigerant evaporator; T_evap rises by 6-12 K relative to Config A and the COP rises from 3.4-4.2 to 4.6-6.5, but the condenser still has to lift the full ambient air to T_set, so Q_cond is unchanged from Config A. The net result is that B1 delivers a larger W_comp reduction than C1 at the same Q_solar at every site: 0.246 < 0.321 kWh kg⁻¹ at Biratnagar, 0.431 < 0.506 at Kathmandu, 0.326 < 0.400 at Dhulikhel, and 0.313 < 0.384 at Taplejung. Crediting solar against the condenser duty therefore outperforms crediting solar against the evaporator-side COP whenever the collector can supply useful heat at the chamber-air pressure level. The same ordering, solar-on-chamber-stream above solar-on-evaporator-stream, has been reported for parallel-versus-series air-source solar-assisted heat-pump configurations in [Vega and Cuevas, 2020, *Appl. Therm. Eng.* 166:114650].

![Fig. 4. Solar-collector placement penalty when the collector is moved from upstream of the condenser (B1, E2; blue) to downstream of the condenser (B2, E3; orange) at A_c = 10 m², T_set = 45 °C, r = 0, annual TMY. Panels (a, b) show cumulative solar capture; panels (c, d) show SEC. Percentages above the bar pairs are the post-cond minus pre-cond change relative to the pre-cond bar.](../outputs/paperplots/fig4_placement_pre_vs_post.png)

Fig. 4 reports the placement penalty. When the collector is moved from upstream of the condenser (B1, E2) to downstream of the condenser (B2, E3), the collector inlet is no longer ambient air but the warmer condenser-outlet air, and the Hottel-Whillier-Bliss heat-loss term (U_L · (T_pl − T_amb)) grows. Panels (a, b) show the consequence on cumulative solar capture: Q_solar drops at every site, by 8.8 to 39.6 % in the single-component family (B1 → B2) and by 4.7 to 18.1 % in the HP + HRX + Solar family (E2 → E3); the drop is largest at the coldest, lowest-irradiance site (Kathmandu) because the heat-loss penalty bites hardest where the temperature difference between the post-condenser plate and the ambient surround is largest. The post-condenser variants compensate for the lost solar gain by lowering T_cond below the 55 °C set point under solar-priority control (B2 T_cond falls to 52.6 °C at Kathmandu, E3 falls to 53.8 °C), and the resulting cycle-COP gain (B2 4.31 vs B1 4.14; E3 4.57 vs E2 4.49 at Biratnagar) raises the heat-pump efficiency by 3 to 7 %. That COP gain does not recover the additional condenser duty that solar no longer offsets, however, and panels (c, d) show that SEC rises monotonically at every site for the post-condenser placement: by 5.9 to 15.4 % across sites in the single-component family and by 5.9 to 10.2 % in the HP + HRX + Solar family. The penalty is again largest at Kathmandu, the worst-case climate site (Section 5.3).

Across both placement choices, the design rule is the same: place the solar collector so that it sees the coldest available chamber-supply air (here, ambient) and so that its delivered heat directly substitutes for condenser duty rather than only raising the evaporator-side heat source. This rule selects B1 over both C1 and B2 in the single-component solar family and selects E2 over E3 in the HP + HRX + Solar family. The combined HRX + pre-condenser solar topology E2 is the configuration retained for the seasonal, climate, and area-sweep analyses that follow.

#### 5.2.1 Set-point sensitivity

The 45 °C baseline sits at the upper edge of the kinetic dataset (40–50 °C in-distribution; Section 3.1, Section 4.1). To test whether the E2 advantage and the placement penalty against E3 are robust below and above the baseline, the two HP + HRX + Solar variants are re-run at T_set ∈ {40, 50, 55} °C at all four sites under the annual TMY (A_c = 10 m², r = 0). T_set = 40 °C is at the lower edge of the kinetic dataset and 50 °C is at the upper edge (both in-distribution); 55 °C is reported as a +5 K extrapolation outside the dataset, and T_set ≥ 60 °C is not run. The condenser saturation temperature T_cond is constrained to the 70 °C upper bound of the cycle model (Section 3.2); the largest value reached anywhere in the sweep is 65 °C (E2 at T_set = 55 °C, fixed-T_cond control), so the entire set-point sweep stays inside the calibrated refrigerant-cycle envelope. The full per-cell numerical record (32 rows: 2 configs × 4 sites × 4 T_set values, with cumulative Q_solar, η_solar, Q_cond, W_comp, T_evap, T_cond, COP, and SEC) is provided as a supplementary file (`outputs/T_sweep_summary.csv`); the principal SEC story is summarised in Fig. 5.

![Fig. 5. Set-point sensitivity of pre-cond (E2, solid lines, circles) vs post-cond (E3, dashed lines, squares) at A_c = 10 m², r = 0, annual TMY. Each colour is one of the four Nepali sites. Panel (a) shows the SEC trajectory across T_set ∈ {40, 45, 50, 55} °C; the shaded band at T_set > 50 °C marks the +5 K kinetic extrapolation. Panel (b) shows the relative E2-over-E3 SEC advantage at each site, expressed as the percentage by which E3 SEC exceeds E2 SEC at the same site and T_set.](../outputs/paperplots/fig5_tset_sweep.png)

Raising T_set from 40 °C to 55 °C shortens the batch by ~42 % (Biratnagar 17.4 → 10.1 h; Kathmandu 17.0 → 10.4 h) because the higher chamber temperature accelerates the M1 thin-layer kinetics. Two trends are visible in panel (a). E2 is essentially flat or slightly improving up to 50 °C at the warmest site (Biratnagar 0.155 → 0.145 → 0.144 → 0.151 kWh kg⁻¹ across T_set 40 → 45 → 50 → 55 °C, with a shallow minimum at 50 °C) and rises modestly at the colder, lower-irradiance sites (Kathmandu 0.213 → 0.241; Dhulikhel 0.183 → 0.207; Taplejung 0.187 → 0.200 across 40 → 55 °C): the cycle COP drops with the larger refrigerant lift, but the shorter batch keeps the cumulative fan-and-compressor work nearly flat. E3 rises monotonically at every site (Biratnagar 0.160 → 0.168; Kathmandu 0.229 → 0.284) because the post-condenser collector inlet temperature tracks T_cond and the Hottel-Whillier-Bliss heat-loss term grows accordingly: at Kathmandu the cumulative Q_solar collapses from 9.9 to 5.6 kWh (a 43 % loss) over T_set 40 → 55 °C, while at Biratnagar it falls from 18.8 to 14.6 kWh (a 22 % loss).

Panel (b) makes the placement-penalty trend explicit: the E2-over-E3 ranking holds at every (site, T_set) cell, and the gap widens monotonically with T_set at every site, ranging from 3.8 % at the warmest, sunniest cell (Biratnagar, 40 °C) to 17.7 % at the worst-case cell (Kathmandu, 55 °C). The pre-condenser placement is therefore not a fortuitous winner at the 45 °C baseline; it becomes more advantageous as the operating temperature rises, because the E3 solar-collector inlet warms in lockstep with T_set while the E2 collector inlet (downstream of the HRX cold side and ambient) does not.

### 5.3 Climate scaling across the four Nepali sites

Fig. 3 shows that the SEC of every HP-bearing configuration is sensitive to the site, with the rank Biratnagar (lowest SEC) < Dhulikhel ≈ Taplejung < Kathmandu (highest SEC) holding at every family. This section decomposes that pattern into the three climate drivers that the model is sensitive to: the annual-mean ambient temperature (sets the condenser lift required of the heat pump), the annual-mean ambient relative humidity (sets the moisture-handling load at the chamber inlet), and the global horizontal irradiance (sets the upper bound on the solar contribution at fixed collector area).

**Table 6.** Annual climate at the four PVGIS-SARAH3 TMY sites used in the matrix. T_amb and RH are hourly means over 8760 hours; GHI_daytime is averaged over the 4445–4960 hourly samples with G > 5 W m⁻²; GHI_annual is the annual integrated horizontal irradiance.

| Site | Elevation (m) | P_atm (kPa) | T_amb annual mean (°C) | RH annual mean (%) | GHI daytime mean (W m⁻²) | GHI annual (kWh m⁻²) |
|---|---|---|---|---|---|---|
| Biratnagar |   72 | 100.5 | 24.4 | 72.5 | 391 | 1663 |
| Kathmandu  | 1350 |  86.1 | 15.7 | 79.6 | 378 | 1595 |
| Dhulikhel  | 1550 |  83.7 | 17.8 | 74.7 | 387 | 1633 |
| Taplejung  | 1820 |  81.0 | 16.9 | 79.3 | 358 | 1519 |

Biratnagar is the warmest, driest, and most-irradiated site; Kathmandu pairs the coldest annual mean (15.7 °C) with the highest relative humidity (79.6 %) at near-median irradiance; Dhulikhel sits between Biratnagar and Kathmandu on all three drivers; Taplejung is the highest-elevation site and has the lowest annual irradiance (1519 kWh m⁻², 9 % below Biratnagar). Taplejung's annual mean of 16.9 °C sits above Kathmandu's 15.7 °C despite the 470 m higher elevation; this is a PVGIS-SARAH3 TMY characteristic of the Taplejung grid cell (a sheltered valley microclimate in the eastern Mahabharat range) rather than a coordinate error, and it is the proximate reason the SEC ranking in Table 7 below is not monotonic in elevation.

**Table 7.** Annual baseline SEC (kWh kg⁻¹) for the ten configurations at the four sites, A_c = 10 m², T_set = 45 °C, r = 0. Numbers identical to the "Annual" column of Fig. 3. The Kathmandu / Biratnagar column reports the ratio of the worst- to the best-irradiated site in the matrix and serves as a single-number index of climate sensitivity for each configuration.

| Family | Config | Biratnagar | Kathmandu | Dhulikhel | Taplejung | Kathmandu / Biratnagar |
|---|---|---|---|---|---|---|
| Electric | 0  | 1.872 | 2.155 | 1.874 | 1.831 | 1.15 |
| HP | A  | 0.485 | 0.664 | 0.533 | 0.528 | 1.37 |
| HP + Solar | B1 | 0.246 | 0.431 | 0.326 | 0.313 | 1.75 |
| HP + Solar | B2 | 0.270 | 0.497 | 0.371 | 0.353 | 1.84 |
| HP + Solar | C1 | 0.321 | 0.506 | 0.400 | 0.384 | 1.58 |
| HP + HRX | D1 | 0.293 | 0.369 | 0.320 | 0.318 | 1.26 |
| HP + HRX | D2 | 0.282 | 0.384 | 0.314 | 0.316 | 1.36 |
| HP + HRX + Solar | E1 | 0.153 | 0.231 | 0.195 | 0.195 | 1.51 |
| HP + HRX + Solar | E2 | 0.145 | 0.215 | 0.184 | 0.186 | 1.49 |
| HP + HRX + Solar | E3 | 0.153 | 0.237 | 0.201 | 0.200 | 1.55 |

Three patterns are read directly from Table 7. First, the electric-resistance baseline (Config 0) has the lowest climate sensitivity (Kathmandu / Biratnagar = 1.15) because the resistive heater absorbs the same enthalpy gap from ambient to T_set at unit electrical efficiency at every site, and the only sensitivity is to the moisture load through inlet RH and the resulting batch length. Second, configurations that contain a heat pump but no recuperation (Config A) show a 37 % Kathmandu penalty, driven by the cold-ambient lift that pushes the cycle COP down (Section 5.2: KTM T_evap = −0.3 °C, COP = 3.43; BTN T_evap = 8.5 °C, COP = 4.16 in the same Table 4). Third, the climate sensitivity is largest in the HP + Solar single-component family (B1, B2, C1 at 58-84 % Kathmandu penalty), because these configurations bank on solar gain that is itself depressed at the cold, humid, lower-irradiance site (Kathmandu Q_solar in Table 4 is 15.2 kWh vs Biratnagar 21.9 kWh, a 30 % loss at the same collector area).

Adding the HRX to a heat-pump topology systematically dampens climate sensitivity: D1 and D2 each carry a 26-36 % Kathmandu penalty, smaller than the 37 % Config-A penalty and far smaller than the B-family penalty. The HRX recovers latent heat from the exhaust, which is most valuable when the ambient is cold and humid; this is why the HRX-bearing families have the flattest site-to-site SEC profile. The HP + HRX + Solar family (E1, E2, E3) sits between the HRX-only and Solar-only families on climate sensitivity (49-55 % Kathmandu penalty), since the HRX recovers the largest fraction of the load and only the residual is exposed to the site-dependent solar gain.

The mechanism that produces Kathmandu as the worst-case site at every HP-bearing family is therefore the coincidence of three penalties: a colder ambient that lowers cycle COP, a higher relative humidity that raises the latent fraction of the chamber heating duty, and an irradiance that, while not the lowest in the matrix, is paired with the coldest collector inlet so that the heat-loss term of the Hottel-Whillier-Bliss collector still cuts into the solar contribution. Taplejung, the highest-elevation site, has the lowest GHI in the matrix (1519 kWh m⁻²) but a warmer annual mean than Kathmandu, so its solar-bearing SEC sits below Kathmandu (E2 SEC 0.186 vs 0.215 kWh kg⁻¹). The site ranking is therefore not aligned with elevation alone; it is driven by the joint behaviour of T_amb, RH, and the available irradiance.

### 5.4 Collector-area sweep and the diminishing-returns knee

The 10 m² baseline used throughout Sections 5.1–5.3 fixes the collector area but does not justify it. Fig. 6 reports the SEC of the preferred topology E2 over the area sweep A_c ∈ {2, 4, 6, 8, 10, 12, 15} m² at the four sites under the annual TMY (r = 0, T_set = 45 °C). The 56-row underlying dataset is included in the matrix summary as block = "solar_sweep" (Section 4.4).

![Fig. 6. Collector-area sweep for E2 at the four Nepali sites. Panel (a) plots SEC against A_c; the dotted vertical line marks the 10 m² baseline used in Sections 5.1–5.3. Panel (b) reports each site's fractional SEC reduction relative to the A_c = 2 m² floor, normalised to the maximum reduction realised at A_c = 15 m². The dashed horizontal lines at 80 % and 90 % visualise the knee.](../outputs/paperplots/fig6_area_sweep.png)

Panel (a) shows the expected diminishing-returns shape at every site: SEC falls steeply between 2 and 6 m², flattens between 6 and 10 m², and approaches a per-site asymptote between 10 and 15 m². The total SEC reduction over the sweep is 0.091 kWh kg⁻¹ at Biratnagar (0.228 → 0.137), 0.116 at Kathmandu (0.314 → 0.197), 0.099 at Dhulikhel (0.271 → 0.173), and 0.085 at Taplejung (0.265 → 0.179); the cold, humid Kathmandu profile responds the most in absolute terms because it starts from the highest SEC, but its asymptote remains the highest of the four sites. Panel (b) normalises each site to its own A_c = 15 m² ceiling and shows that the 10 m² baseline captures 85 to 92 % of the maximum SEC reduction available within the swept range across the four sites (Biratnagar 91 %, Kathmandu 85 %, Dhulikhel 88 %, Taplejung 92 %). Going from 10 m² to 15 m² adds 50 % more collector area for an additional 6 to 10 percentage points of reduction; going from 10 m² to 12 m² adds 20 % more area for an additional 4 to 6 points. The marginal benefit at the baseline is ~0.002 kWh kg⁻¹ per m² of additional collector at Biratnagar and Taplejung and ~0.004 kWh kg⁻¹ per m² at Kathmandu and Dhulikhel; this is roughly an order of magnitude lower than the 0.02 to 0.04 kWh kg⁻¹ per m² returned by the first 2 m² of collector at the same sites. The 10 m² value adopted as the baseline in this work is therefore close to, but on the diminishing-returns side of, the per-site knee at all four sites: the inflection point on each curve sits between 6 and 10 m² for the three lower-irradiance sites and between 4 and 8 m² for Biratnagar. A practical installation at any of these four sites would therefore size the collector in the 8 to 12 m² range; pushing further into the 12 to 15 m² range yields a small additional SEC saving that an economic optimisation, not attempted in this work, would have to weigh against the marginal capital cost of the larger collector.

### 5.5 Comparison with published SAHPD performance

The configuration matrix returns absolute SMER values for E2 of 6.91, 4.65, 5.44, and 5.38 kg kWh⁻¹ at Biratnagar, Kathmandu, Dhulikhel, and Taplejung respectively (reciprocals of the Table 7 SEC values). These sit above the experimental SAHPD band of 0.47 to 2.71 kg kWh⁻¹ in Table 8 but inside the modelled-SAHPD band that includes Ismaeel and Yumrutaş (2020), who report SMER 9.25 kg kWh⁻¹ for an analytical SAHPD + TES + HRU configuration on wheat under matched-T_set conditions. A like-for-like comparison with the experimental literature therefore has to be made at the level of the percentage contribution of each heating component rather than on absolute SMER.

**Table 8.** Published SAHPD and HP-dryer performance benchmarks alongside the present-work E2 baseline at the four Nepali sites. SMER, COP and saving figures are reproduced from the cited sources; the HRX/HRU and solar columns report the saving claimed in each study relative to the indicated baseline within that same study. "n/r" indicates the measure was not reported. All cited entries are traceable to PDFs catalogued in the literature ledger (`paper/_archive/LIT_REVIEW_LEDGER.md`).

| Study | Product | Climate / site | Topology | COP | SMER (kg kWh⁻¹) | HRX/HRU saving | Solar saving | Cited baseline for saving |
|---|---|---|---|---|---|---|---|---|
| Hawlader et al. (2006, 2008) | Green beans | Singapore, tropical | Solar evap-collector (DX) | 7.0 sim / 5.0 exp | 0.65 | – | – | – |
| Mortezapour et al. (2012) | Saffron stigmas | Tehran, Iran (semi-arid) | Hybrid PV/T + HP, 40-60 °C | n/r | 1.16 | – | 33 % | HP-only at same T_set |
| Yahya, Fudholi et al. (2016) | Cassava | Indonesia, tropical | SAHPD vs solar-dryer, 40-45 °C | 3.23-3.47 | 0.47 (SAHPD) vs 0.38 (SD) | – | 24 % SMER uplift | Solar dryer (not HP-only) |
| Qiu et al. (2016) | Radish / pepper / mushroom | China | SAHPD + HR + TES | 3.21-3.49 | n/r | combined with solar gain | 40.5 % | SAHPD without HR + TES |
| Kuan et al. (2019) | Banana | Almaty, Kazakhstan (continental cold) | SAHPD + HRU, R134a | 2.72 | 0.60 | 12.9 % | – | SAHPD without HRU |
| Ismaeel and Yumrutaş (2020) | Wheat | Şanlıurfa, Turkey (semi-arid; analytical) | SAHPD + TES + HRU, 100 m² coll | 5.55 | 9.25 (yr-5 periodic) | 21.4 % | – | SAHPD + TES without HRU |
| Rulazi et al. (2023) | Tomato / carrot | Tanzania, NM-AIST | SAHPD, novel design | 3.40 | 1.33 | – | n/r | – |
| Aacharya et al. (2024) | Apple | Dhulikhel, Nepal (1550 m) | Solar-only, double-pass + counter-flow HRX | – | n/r | n/r | – | (solar-only, no HP) |
| Abdullah et al. (2025) | Pandan herbs | Malaysia, tropical | Dual-condenser SAHPD + hot-water solar | 6.53 | 2.71 | – | n/r | – |
| **Present work, E2** | **Apple slice (5 mm)** | **Biratnagar, Nepal (72 m, sub-tropical)** | **Solar + HP + HRX (pre-cond), r = 0** | **4.49** | **6.91** | **41.1 %** | **50.5 %** | **B1 (HRX); D1 (solar)** |
| **Present work, E2** | **Apple slice (5 mm)** | **Kathmandu, Nepal (1350 m, temperate)** | **Solar + HP + HRX (pre-cond), r = 0** | **3.82** | **4.65** | **50.1 %** | **41.7 %** | **B1 (HRX); D1 (solar)** |
| **Present work, E2** | **Apple slice (5 mm)** | **Dhulikhel, Nepal (1550 m, temperate)** | **Solar + HP + HRX (pre-cond), r = 0** | **4.11** | **5.44** | **43.6 %** | **42.5 %** | **B1 (HRX); D1 (solar)** |
| **Present work, E2** | **Apple slice (5 mm)** | **Taplejung, Nepal (1820 m, temperate)** | **Solar + HP + HRX (pre-cond), r = 0** | **4.01** | **5.38** | **40.6 %** | **41.5 %** | **B1 (HRX); D1 (solar)** |

The three reasons the simulated SMER sits above the experimental envelope (0.47 to 2.71 kg kWh⁻¹) are structural, not accidental. First, the digital twin enforces a closed first-law balance at every step (Q_cond = Q_evap + W_comp, verified in Section 3.10) and assumes adiabatic chamber and duct walls, so none of the cycle work is lost to envelope conduction, radiation, or door-opening events that an experimental rig necessarily incurs. Second, the kinetic law (Section 3.5) is a thin-layer Midilli model calibrated on individual 4 to 10 mm slabs in an instrumented duct; it returns the drying rate of a single slab fully exposed to the inlet conditions and does not include a tray-coverage factor, a slab-to-slab shadowing penalty, or the dead-volume effect of a real tray rack. Both idealisations inflate moisture-extraction-per-unit-energy relative to what an integrated prototype would measure. Third, the published studies in Table 8 mix denominator conventions: some report SMER on compressor-plus-fan electricity (the convention adopted here, following Mortezapour et al. and Kuan et al.), others on the total parasitic load including chamber, control, and auxiliary heaters, and the Ismaeel and Yumrutaş analytical model excludes the thermal-storage maintenance load from the denominator — the reason their SMER (9.25 kg kWh⁻¹) sits above this work despite a higher-irradiance climate. A factor-of-two spread across the published band is therefore explained as much by the boundary of the energy denominator and the modelling-vs-experimental gap as by the underlying technology. With these three corrections in mind, the absolute SMER reported here should be read as an upper-bound performance envelope under idealised operation; experimental prototypes targeting the same topology at the same sites should be expected to land in the 1.5 to 3.0 kg kWh⁻¹ range once envelope losses, tray-coverage and parasitic loads are included.

The component-level savings are the more transferable comparison and lie above the published envelope at all four sites. The HRX contribution (E2 vs B1, the same topology with the HRX removed) is 40.6 to 50.1 % across the four sites, with the largest value at Kathmandu where the cold, humid ambient produces the highest exhaust-to-ambient enthalpy gap and therefore the most latent heat for the HRX to recover. Kuan et al. (2019) report a 12.9 % HRU saving in a banana SAHPD at Almaty (continental dry climate) and Ismaeel and Yumrutaş (2020) report 21.4 % for wheat at Şanlıurfa (semi-arid, with thermal storage); the higher value here is consistent with the joint effect of an ε_HRX = 0.70 module (Table 2) and a latent-rich exhaust at all four Nepali sites (ambient RH 72.5 to 79.6 %, Table 6), where the recovered enthalpy includes a larger latent share than at the comparator sites. The solar contribution (E2 vs D1, the same topology with the solar collector removed) is 41.5 to 50.5 %, bracketing the 33 % saving reported by Mortezapour et al. (2012) for a PV/T SAHPD on saffron in Tehran (HP-only baseline at the same T_set) and the 40.5 % saving reported by Qiu et al. (2016) for an HR + TES SAHPD on radish, pepper and mushroom (SAHPD-without-HR-TES baseline); the comparison brackets the present work above and below but the cited baselines differ, so the alignment is qualitative rather than quantitative. The mechanism-level comparison therefore confirms that this work's headline E2 SEC of 0.145 to 0.215 kWh kg⁻¹ across Nepal is anchored to component contributions that sit within or just above the published envelope; the absolute SMER inflation is a property of the idealised simulator, not of the topology choice itself. A direct geographic anchor is Aacharya et al. (2024), who report a solar-only apple dryer with a counter-flow plate HRX operating at Dhulikhel (1550 m, one of the four sites studied here) with a collector efficiency of 89 % and a drying rate of 107 g h⁻¹ m⁻² of tray area; their study does not report SEC or SMER on a comparable basis and is solar-only (no heat pump), so a direct numerical comparison is not feasible, but their Dhulikhel collector efficiency provides an upper-bound experimental anchor for the HWB collector parameters used here at the same site.

### 5.6 Seasonal breakdown

The annual baseline reported in Table 7 is a single batch starting at the first hour of the TMY (January 1, 00:00) and therefore reflects the coldest part of the year at each site. To resolve how the preferred topology behaves across the practical drying calendar, the simulator is re-run with each of the four two-month seasonal weather slices generated by `split_seasons.py` (autumn, October–November; winter, December–January; spring, March–April; summer, May–June). The monsoon months (July to September) are excluded by design: ambient relative humidity routinely exceeds 90 % during this window at all four sites and outdoor drying operations would be impractical irrespective of the dryer topology used. The four seasonal slices therefore represent the drying window over which the E2 topology is expected to operate. Fig. 7 reports E2 SEC and cumulative solar capture by season at all four sites; the underlying numbers are reproduced in Table 9.

![Fig. 7. Seasonal breakdown of E2 at the four Nepali sites at A_c = 10 m², T_set = 45 °C, r = 0. Panel (a) plots SEC by season with the annual Jan-1-start baseline marked as a dotted line at each site. Panel (b) plots cumulative solar capture Q_solar by season.](../outputs/paperplots/fig7_seasonal.png)

**Table 9.** E2 specific energy consumption (kWh kg⁻¹) and cumulative solar capture Q_solar (kWh) by site and season; A_c = 10 m², T_set = 45 °C, r = 0. The "Max / Min" column reports the ratio of the worst- to best-season SEC at each site and serves as a single-number index of seasonal sensitivity.

| Site | Autumn SEC | Winter SEC | Spring SEC | Summer SEC | Annual SEC (Table 7) | Max / Min |
|---|---|---|---|---|---|---|
| Biratnagar | 0.116 | 0.126 | 0.094 | 0.078 | 0.145 | 1.62 |
| Kathmandu  | 0.138 | 0.156 | 0.118 | 0.118 | 0.215 | 1.32 |
| Dhulikhel  | 0.116 | 0.152 | 0.113 | 0.103 | 0.184 | 1.48 |
| Taplejung  | 0.121 | 0.184 | 0.139 | 0.109 | 0.186 | 1.69 |
| Site | Autumn Q_sol | Winter Q_sol | Spring Q_sol | Summer Q_sol | – | Max / Min |
| Biratnagar | 20.4 | 16.7 | 29.8 | 30.1 | – | 1.80 |
| Kathmandu  | 20.6 | 17.3 | 27.6 | 25.8 | – | 1.59 |
| Dhulikhel  | 23.8 | 18.3 | 28.4 | 25.1 | – | 1.55 |
| Taplejung  | 24.1 | 14.1 | 24.0 | 28.0 | – | 1.98 |

Three patterns are read directly from Table 9 and Fig. 7. First, winter is the worst-SEC season at every site, with Taplejung winter (0.184 kWh kg⁻¹) the highest seasonal SEC observed anywhere in the matrix. The winter penalty has two reinforcing drivers: the coldest seasonal ambient reduces the evaporator inlet enthalpy and forces a lower T_evap and lower cycle COP (Section 5.2), and the lowest seasonal irradiance reduces solar capture, raising the share of the load that the compressor must service. Taplejung winter exemplifies the joint penalty: Q_solar drops to 14.1 kWh (50 % below its summer value) while the compressor must supply 2.58 kWh of electrical input, the highest single-batch compressor load anywhere in the E2 seasonal matrix. Second, summer is the best-SEC season at three of the four sites, with the largest absolute reduction at Biratnagar (0.078 kWh kg⁻¹, SMER 12.8 kg kWh⁻¹) where the combination of warmer ambient and high-irradiance long days drives the compressor load down to 0.50 kWh and the solar capture up to 30.1 kWh. Spring SEC at Taplejung (0.139 kWh kg⁻¹) sits between its summer and winter values; for the high-elevation site spring and summer SEC differ by only 0.030 kWh kg⁻¹ because solar capture rebounds faster than the ambient temperature. Third, the seasonal SEC swing (max / min ratio) is largest at Taplejung (1.69), followed by Biratnagar (1.62), Dhulikhel (1.48) and Kathmandu (1.32). Kathmandu has the highest absolute SEC in every season but the smallest swing because all four of its seasonal samples share a cold high-RH profile: ambient never warms enough to materially raise the evaporator COP, and irradiance never drops enough to lose the solar share entirely. Taplejung shows the inverse pattern: high-elevation winter is severe but high-elevation summer recovers strongly because the post-monsoon-shoulder atmosphere has high transmittance and the collector heat-loss term U_L benefits from the lower ambient.

A practical implication is that the E2 topology is robust to seasonal variation when judged against the published SAHPD envelope: its worst-season SEC (0.184 kWh kg⁻¹, Taplejung winter) corresponds to SMER 5.43 kg kWh⁻¹, still above the experimental band reported in Table 8 (0.47 to 2.71 kg kWh⁻¹) and well above the electric-resistance baseline at any site or season. The annual baseline in Table 7 is more conservative than every seasonal value because it samples the coldest hour of the year as the start of its 14-hour batch; consequently the headline E2 SEC of 0.145 to 0.215 kWh kg⁻¹ across Nepal used in Sections 5.1 to 5.5 over-states the energy cost a year-round operator would observe by 15 to 40 % depending on site. Operators concerned with a single fixed sizing decision should treat the Table 7 annual values as a worst-case shoulder and the Table 9 seasonal values as the actual operating distribution.

### 5.7 Kinetic-model sensitivity

All SEC results in Sections 5.1 to 5.6 rest on a single drying-kinetics law (M1, the live first-order law refit on the laboratory thin-layer dataset; Section 4.5). M1 is a deliberately compact functional form that absorbs temperature, air velocity, relative humidity and slice thickness into a single rate coefficient K. To test whether the topology ranking depends on this functional choice, the simulator is re-run with an independent alternative kinetic law (M2): a piecewise Midilli surrogate fit on the same laboratory dataset under a global LOCO-CV protocol, with a fixed Arrhenius pre-exponent and a time-varying exponent n(T, v). M2 is converted to an instantaneous first-order-equivalent K_eff(t) via K_eff = k · n · t_min^(n−1) and substituted into the same discretisation kernel as M1 (`scripts/audit_phase_d.py`, monkey-patching `compute_dm_w_kinetic_first_order`). The matrix is re-run for the nine HP-bearing configurations of Table 1 at each of the four sites under A_c = 10 m², T_set = 45 °C and r = 0, yielding 72 simulations (36 per kinetic model) summarised in Table 11. Configuration 0 is excluded because its energy balance has no refrigerant cycle and the kinetic law enters only through batch length.

**Table 11.** SEC under M1 (live, headline values used throughout the paper) and M2 (Midilli surrogate, sensitivity bracket) at the four Nepali sites; A_c = 10 m², T_set = 45 °C, r = 0. The "rel. Δ" column is 100 · (SEC_M2 − SEC_M1) / SEC_M1. Source: `outputs/audit/phase_d_sec_summary.csv`, `phase_d_sec_delta.csv`.

| Config | Site | SEC_M1 | SEC_M2 | rel. Δ (%) |
|---|---|---|---|---|
| A  | Biratnagar | 0.4846 | 0.4451 | −8.2 |
| A  | Kathmandu  | 0.6642 | 0.6347 | −4.4 |
| A  | Dhulikhel  | 0.5325 | 0.4991 | −6.3 |
| A  | Taplejung  | 0.5278 | 0.5069 | −4.0 |
| B1 | Biratnagar | 0.2458 | 0.2055 | −16.4 |
| B1 | Kathmandu  | 0.4312 | 0.4011 | −7.0 |
| B1 | Dhulikhel  | 0.3257 | 0.2916 | −10.5 |
| B1 | Taplejung  | 0.3135 | 0.2919 | −6.9 |
| B2 | Biratnagar | 0.2697 | 0.2291 | −15.1 |
| B2 | Kathmandu  | 0.4975 | 0.4673 | −6.1 |
| B2 | Dhulikhel  | 0.3708 | 0.3365 | −9.3 |
| B2 | Taplejung  | 0.3526 | 0.3309 | −6.1 |
| C1 | Biratnagar | 0.3210 | 0.2809 | −12.5 |
| C1 | Kathmandu  | 0.5063 | 0.4764 | −5.9 |
| C1 | Dhulikhel  | 0.3998 | 0.3659 | −8.5 |
| C1 | Taplejung  | 0.3843 | 0.3630 | −5.6 |
| D1 | Biratnagar | 0.2929 | 0.2770 | −5.4 |
| D1 | Kathmandu  | 0.3685 | 0.3567 | −3.2 |
| D1 | Dhulikhel  | 0.3202 | 0.3063 | −4.3 |
| D1 | Taplejung  | 0.3176 | 0.3084 | −2.9 |
| D2 | Biratnagar | 0.2822 | 0.2686 | −4.8 |
| D2 | Kathmandu  | 0.3835 | 0.3752 | −2.2 |
| D2 | Dhulikhel  | 0.3142 | 0.3028 | −3.6 |
| D2 | Taplejung  | 0.3158 | 0.3087 | −2.2 |
| E1 | Biratnagar | 0.1528 | 0.1335 | −12.6 |
| E1 | Kathmandu  | 0.2310 | 0.2170 | −6.0 |
| E1 | Dhulikhel  | 0.1953 | 0.1788 | −8.5 |
| E1 | Taplejung  | 0.1953 | 0.1835 | −6.0 |
| **E2** | **Biratnagar** | **0.1448** | **0.1270** | **−12.2** |
| **E2** | **Kathmandu**  | **0.2150** | **0.2021** | **−6.0** |
| **E2** | **Dhulikhel**  | **0.1840** | **0.1688** | **−8.3** |
| **E2** | **Taplejung**  | **0.1860** | **0.1748** | **−6.0** |
| E3 | Biratnagar | 0.1534 | 0.1358 | −11.5 |
| E3 | Kathmandu  | 0.2369 | 0.2246 | −5.2 |
| E3 | Dhulikhel  | 0.2010 | 0.1862 | −7.4 |
| E3 | Taplejung  | 0.2004 | 0.1892 | −5.6 |

Three results from Table 11 govern how the rest of the paper should be read. First, M2 is systematically below M1 at every config × site (36 of 36 cases negative, mean rel. Δ = −7.1 %, median = −6.1 %, range −2.2 % to −16.4 %), which means M1 is the conservative kinetic choice: every SEC value reported in Tables 4 to 9 over-states the energy cost relative to the M2 surrogate. The largest M1−M2 gap is B1 at Biratnagar (−16.4 %), where the chamber-inlet RH drops to the low-30 % band that the two laws fit somewhat differently (M1's exp(−α_RH · RH) factor with α_RH = 1.266 falls faster with humidity than the Midilli b·t drift term in M2). The smallest swings are D1 and D2 (rel. Δ between −2.2 % and −5.4 %), the two pure-HRX configurations whose chamber inlet RH stays inside the kinetic calibration band of 35 to 55 %. The E-family swings sit in the middle of the distribution (−5.2 % to −12.6 %), with E1 at Biratnagar (−12.6 %) marking the upper bound and E2 at Biratnagar (−12.2 %) close behind. Second, the topology ranking is preserved across both kinetic laws: E2 is the best configuration at every site under both M1 and M2, the E-family always occupies the three best positions, and the only rank flips occur deep in the HRX-only band (Spearman ρ = 1.000 at Biratnagar and Kathmandu, 0.983 at Taplejung and 0.950 at Dhulikhel; three flipped pairs out of 144 pairwise comparisons across all four sites, all of them at the D1 ⇄ D2, B1 ⇄ D2 and B1 ⇄ D1 boundary). The selection of E2 as the preferred topology is therefore robust to the kinetic-law choice within the family of laws calibrated on the same laboratory dataset. Third, the E2-over-E3 gap is slightly wider under M2 (mean 9.1 % across the four sites, range 6.9 to 11.1 %) than under M1 (mean 8.3 %, range 5.9 to 10.2 %), so the pre-cond / post-cond placement story in Section 5.2 is if anything understated by the headline M1 numbers; the same conclusion holds for the B1-versus-C1 comparison, where C1 sits 17 to 31 % above B1 under M1 (mean 23 %) and 19 to 37 % above B1 under M2 (mean 26 %). The Table 7 headline SEC values reported in this paper should therefore be read as the upper bound on a band whose lower edge sits about 2 to 16 % below depending on configuration, and the cross-family and pre-cond-vs-post-cond rankings are stable across both kinetic laws.

### 5.8 Model validation summary

The simulator's internal consistency is checked by `scripts/verify_energy_balance.py`, which traces the air path component-by-component, recomputes each enthalpy step from the logged temperatures and humidities, and compares the recomputed cumulative energies against the corresponding logged cumulative integrals. The checks are run on the E2 baseline (A_c = 10 m², T_set = 45 °C, r = 0) at all four sites and are summarised in Table 10. The same script also verifies the refrigerant first law at every timestep (Q_cond_kW = Q_evap_kW + W_comp_kW · η_mech with η_mech = 0.90) and the temperature monotonicity along the air path (T_amb < T_HRX_out < T_solar_out and T_air_in_cond < T_cond_out).

**Table 10.** Energy-balance verification of the E2 baseline at the four Nepali sites; m_da reconstructed from the configuration, η_mech = 0.90, h_fg = 2450 kJ kg⁻¹. "Max" denotes the per-timestep worst case over the 14-hour batch; "Cum" is the absolute difference between the logged cumulative integral and the trapezoidal recomputation from the instantaneous columns. SEC is the published Table 7 value cross-checked against W_elec / m_w computed from the final-row totals.

| Site | HRX Max\|err\| | Solar Max\|err\| | Q_cond_air / Q_cond_ref | First-law Max\|err\| | Cum W_comp drift | Cum Q_cond drift | SEC (computed) | SEC (Table 7) |
|---|---|---|---|---|---|---|---|---|
| Biratnagar | 1.67 % | 0.00 % | 0.984 | < 1×10⁻⁴ % | 0.000000 kWh | 0.000000 kWh | 0.145 | 0.145 |
| Kathmandu  | 1.40 % | 0.00 % | 0.987 | < 1×10⁻⁴ % | 0.000000 kWh | 0.000000 kWh | 0.215 | 0.215 |
| Dhulikhel  | 1.81 % | 0.00 % | 0.984 | < 1×10⁻⁴ % | 0.000000 kWh | 0.000000 kWh | 0.184 | 0.184 |
| Taplejung  | 1.59 % | 0.00 % | 0.986 | < 1×10⁻⁴ % | 0.000000 kWh | 0.000000 kWh | 0.186 | 0.186 |

Three results follow from Table 10. First, the refrigerant first law closes exactly at every timestep at every site: the maximum per-timestep residual on Q_cond − (Q_evap + W_comp · η_mech) is below 10⁻⁴ % of Q_cond, and the mechanical losses W_comp · (1 − η_mech) = 0.187 to 0.320 kWh per batch are fully accounted as a separate term in the global energy book-keeping. Second, the condenser air-side / refrigerant-side ratio settles in the band 0.984 to 0.987 at every site, i.e. close to unity to within 1.6 %; the 0.3 to 1.5 % residual is a pure dry-air cp approximation (the script benchmarks m_da · cp · ΔT against the enthalpy-based Q_cond), not a model defect. Third, the cumulative energy integrals (W_comp_cum_kWh, Q_solar_cum_kWh, Q_cond_cum_kWh) reproduce their trapezoidal recomputations from the instantaneous columns to better than 1 µWh at every site, which means the SEC values reported in Sections 5.1 to 5.6 are arithmetically reproducible from the published per-timestep CSVs without recourse to any internal summation. The cross-checked SEC matches the published Table 7 entries to the third decimal at every site. The solar-collector check is exact by construction because Q_solar_kW is itself defined as m_da · cp · (T_solar_out − T_solar_in); it is retained as a sanity guard that solar capture is being routed to and from the correct nodes. The HRX residual (1.4 to 1.8 % of the instantaneous Q_HRX) likewise reflects the dry-air cp approximation against the enthalpy-based logged value and is the largest discrepancy in the validation suite; it falls below 0.01 % when accumulated over the batch because the residual sign-changes between humid and dry timesteps and cancels in the integral. The same checks were re-run for E3 at Biratnagar and Kathmandu and pass with the additional E3-only diagnostic that the partial-HP back-calculation lands T_to_chamber on T_set to within ±10⁻³ K at every timestep where the HP runs in partial-lift mode (105 timesteps at Biratnagar, 229 at Kathmandu), confirming that the implicit solve for the partial-mode condensing temperature converges exactly. Together these checks verify that the published SEC, COP and SMER values are internally consistent with the underlying model and that the differences between configurations and between sites cannot be attributed to logging artefacts.

## 6. Conclusions (~300 w) — defer

---

## Nomenclature

[defer]

## CRediT author statement

[defer]

## Declaration of competing interests

The authors declare no competing interests.

## Declaration of generative AI

[Required by Renewable Energy: state tool, scope, and that authors take full responsibility. Draft on submission.]

## References (IEEE numbered, ≤ 50)

[defer; build from ledger row tags during revision pass]
