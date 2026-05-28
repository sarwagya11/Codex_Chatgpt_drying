# SAHPD RQ1 Paper — Consolidated Section Notes

_Merged from prior 00–05 section markdowns on 2026-05-19. Originals archived in `_archive/`. Treat as reference, not the active draft._

---


<!-- ===== 00_framework.md ===== -->

# Paper Framework

## Target journal

**Primary: Energy Conversion and Management (Elsevier).**
IF ~10 (2024), acceptance rate ~18%, word target 7,000-9,000, ~5-8 figures, ~40-70 refs.
Scope fit: hybrid-energy systems, comparative modelling, thermal storage, solar integration.
Typical section pattern for SAHPD modelling papers: Introduction, System description,
Mathematical model, Simulation setup, Results and discussion, Conclusions.

**Backup 1: Applied Thermal Engineering.**
IF ~6.4, broader component scope, easier acceptance, same IMRaD layout.

**Backup 2: Drying Technology.**
IF ~3.2. Use only if reviewer feedback pushes the paper toward kinetics over system comparison.

## Paper structure (working)

1. **Introduction** (~1,000 words)
   1.1 Context (apple post-harvest losses in Nepal, grid electricity cost, solar potential)
   1.2 Heat pump drying overview
   1.3 Solar-assisted heat pump dryers: state of the art
   1.4 Literature gap
   1.5 Contribution of this work

2. **System description** (~1,200 words, 3-4 figures)
   2.1 Reference configuration (Config A, HP-only)
   2.2 Solar-assisted variants (B, C1, C2)
   2.3 Heat-recovery variants (D1, D2) — D3 excluded
   2.4 Combined variants (E1, E2, E3)
   2.5 VPD bypass control

3. **Mathematical model** (~1,800 words, heavy equations)
   3.1 Vapour-compression cycle (R134a, CoolProp, eta_is = 0.75)
   3.2 Solar collector (Hottel-Whillier-Bliss)
   3.3 Counter-flow HRX (eps-NTU)
   3.4 Drying kinetics (parametric Midilli with alpha_RH)
   3.5 GAB sorption isotherm
   3.6 Psychrometrics and control
   3.7 First-law enforcement and validation

4. **Simulation setup** (~700 words, 1 figure, 1 table)
   4.1 Sites and TMY data (Kathmandu, Biratnagar, Taplejung)
   4.2 Operating inputs (T_set, batch, trays, v_air)
   4.3 Model validation (water balance, energy balance, COP realism)

5. **Results and discussion** (~2,500 words, 5-6 figures, 3-4 tables)
   5.1 Baseline (A) and site sensitivity
   5.2 Solar integration (B, C1, C2)
   5.3 Heat recovery (D1, D2)
   5.4 VPD bypass as an independent control lever
   5.5 Combined systems (E1, E2, E3) and area sensitivity
   5.6 Synthesis: Pareto of SEC vs. capital complexity

6. **Conclusions** (~500 words)
   Quantified headline numbers + limitations + future work

7. **References** (~50-60 entries, pulled from RESEARCH_*.md)

## Contribution claim

Three specific claims that a reviewer will test:

1. **Systematic comparative scope.** Ten air-path topologies compared under one
   validated thermodynamic model, one kinetic model, and one TMY dataset, at three
   Nepalese sites. Prior work reports individual configurations, not a directly
   comparable set.

2. **HRX + solar + VPD bypass combination.** Annual SEC reaches 0.097 kWh/kg at
   Biratnagar with E2 + VPD (A_c = 10 m^2), below every value in the SEC survey
   in RESEARCH_NOVELTY_SEC.md. The novelty is the combination rather than any
   single component; the paper must frame it this way.

3. **Site-dependence mapping.** The closed-loop recirculation crossover (SEC
   benefit at Kathmandu, penalty at Biratnagar) is explicitly traced to the
   interaction between fixed T_evap and ambient climate; this guides geographic
   configuration choice.

## Writing conventions

- SI units throughout. kWh/kg for SEC. Absolute units in tables.
- Refrigerant: R134a (switched from R410A 2026-03-23).
- Configuration labels: Config A, Config B, Config C1, Config C2, Config D1,
  Config D2, Config E1, Config E2, Config E3. Never Config D3.
- Cite the validation note (2026-04-09, six-configuration first-law check) once
  in Section 4.3.
- Objective tone. Do not write "negative result" or similar framing. State
  magnitudes and direction, let the reader judge.
- Figures: SEC bar by site and config; recirculation sweep; collector area
  sweep; Pareto scatter. Diagrams of the ten air paths go in §2.

## Deliverable order

1. 00_framework.md (this file)
2. 01_literature_review.md (Introduction §1.2-1.5 + the supporting lit review paragraphs)
3. 02_system_description.md
4. 03_mathematical_model.md
5. 04_simulation_setup.md
6. 05_results.md (condensed from thesis Results_Discussion_v3.docx)
7. 06_conclusions.md
8. 07_references.bib

---


<!-- ===== 01_literature_review.md ===== -->

# 1. Introduction and Literature Review

_Phase C draft (2026-05-05). All citations verified against `LIT_REVIEW_LEDGER.md`. Target journal: Energy Conversion and Management._

## 1.1  Fruit drying in Nepal

Nepal produced approximately 1.53 Mt of fruit on 139,478 ha of productive area in fiscal year 2079/80 (2022/23), with apple yielding about 52,800 t over 6,200 ha of productive area at a national average of 8.5 t/ha (MoALD, 2024). Production is distributed across three agro-climatic belts: subtropical Tarai, temperate mid-hills, and high-hill apple-growing districts at altitudes above 1,800 m. Nepal also has a substantial solar resource, with long-term mean global horizontal irradiation of approximately 1,614 kWh/m²/year at Biratnagar in the eastern Tarai, 1,753 kWh/m²/year at Kathmandu, and 1,949 kWh/m²/year at Jomsom in the high-hill rain-shadow zone (ESMAP, 2017). Combined with the perishability of fresh fruit and the seasonality of harvest, this resource profile motivates electrified drying technologies that can use solar gain when available and recover sensible enthalpy from the exhaust at other times. The present study uses apple slices as the model crop, building directly on the two recent Nepali fruit-drying studies (Aacharya et al., 2024; Adhikari et al., 2025), but the air-path topologies and the thermodynamic model considered here are crop-agnostic and apply equally to other Nepali fruit and vegetable products.

## 1.2  Drying kinetics for apple slices

Specific energy consumption and chamber sizing for any dryer ultimately ride on the kinetic model used to translate inlet air state into a moisture-removal rate. For apples, the dominant convention in the literature is a Midilli–Kucuk thin-layer form with Arrhenius temperature dependence and empirical corrections for relative humidity, air velocity, and slab thickness; this family has been fitted to apple slices across cultivars and dryer geometries spanning 40–80 °C and 0.5–2.75 m/s (Sacilik and Elicin, 2006; Kaleta and Górnicki, 2010; Meisami-asl et al., 2010; Doymaz, 2010). The directly verifiable activation energies for Arrhenius-type effective-diffusivity models on convectively dried apple slices cluster between roughly 14 and 23 kJ/mol. Doymaz (2010) reports 14.47, 18.93 and 22.06 kJ/mol for citric-acid-treated, blanched and untreated Amasya red apple at 55–75 °C; Kaya et al. (2007), cited within Doymaz (2010), report 19.95–22.62 kJ/mol for red delicious apple. Velić et al. (2004) report effective diffusivities of 1.7–4.4 × 10⁻⁹ m²/s for Jonagold apple at 60 °C with airflow velocities varying from 0.64 to 2.75 m/s, but their experimental design holds temperature constant and therefore does not yield an Arrhenius activation energy. Reported values shift markedly higher when the heat-transfer mode itself changes (Sharabiani et al., 2021, 122–125 kJ/mol for microwave drying), so microwave and infrared studies are not directly comparable to the convective regime considered here.

The pooled training set used in the present work was reconstructed by digitising the 13 published moisture-ratio curves of Royen et al. (2020), since the underlying tabulated data were not made publicly available by the original authors. Curves span 40, 45 and 50 °C; air velocity 0.6, 0.85 and 1.1 m/s; slice thickness 4, 6, 8, 10 and 12 mm; and inlet relative humidity 25–28%, 35–38% and 40–45%, totalling 1573 PAVA-cleaned MR(t) observations across the 13 conditions.

Three candidate models were compared under leave-one-condition-out cross-validation (LOCO-CV, n=13). M1 is the operational five-parameter first-order Arrhenius form (K_ref, E_a/R, alpha_RH, gamma_v, delta_d), fitted by single-stage non-linear least squares directly on raw MR(t). M2 is a seven-parameter Arrhenius+Midilli baseline mirroring Sacilik and Elicin (2006) and Doymaz (2010). M3 is a recursive piecewise + ElasticNet machine-learning pipeline. LOCO RMSE_MR was 0.053, 0.040 and 0.069 for M1, M2 and M3 respectively. A 5000-resample paired bootstrap places M1 − M2 at +0.012 (95% CI [−0.002, +0.022]); the interval crosses zero, so the simpler operational model is statistically indistinguishable from the published Midilli baseline on held-out conditions, and both significantly beat the ML pipeline (M1 − M3 = −0.016 [−0.033, −0.000]; M2 − M3 = −0.028 [−0.048, −0.009]).

M1's profile-likelihood interval for the activation energy is E_a = 31.08 kJ/mol, 95% CI [28.6, 33.6] kJ/mol. This sits above the verified apple-specific convective-drying Arrhenius range cited above (14.47–22.62 kJ/mol); the discrepancy with the apple-specific upper bound is consistent with the lower-temperature convective regime of the present dataset (40–50 °C versus 40–80 °C in the cited studies) and with our explicit RH and velocity dependencies, which absorb temperature-correlated variance that an Arrhenius-only fit would attribute to E_a. Calibration relative humidity spans 26–42% and the design point at 15% RH is a modest extrapolation. Configuration ranking is essentially preserved when SEC is recomputed under M2 (Spearman rho = 0.985 across 30 configuration-site pairs); ranks differ on 11/30 pairs and SEC magnitudes shift by −32% to +15%, with the largest shift on Configuration C1 at the Taplejung site. M1 is therefore retained as the operational kinetic model and M2 is reported as the sensitivity bracket.

## 1.3  Heat-pump drying: principle, performance envelope and limits

A heat-pump dryer (HPD) couples a vapour-compression refrigeration cycle to the dryer air loop so that the condenser supplies the sensible heat needed to raise the air to the drying temperature, while the evaporator simultaneously dehumidifies the exhaust by condensing water out of it. Because the evaporator-side latent recovery is reused as condenser-side sensible gain, the resulting specific moisture extraction rate (SMER) and coefficient of performance (COP) are typically several times higher than for an electrically heated open-loop dryer; the principle and its early industrial development are reviewed in detail by Çolak and Hepbaşlı (2009) and by Minea (2011, 2013a). The same low-temperature operation (typically 35–60 °C) preserves heat-sensitive constituents in fruit and vegetable products, which is why the technique has been studied extensively for agricultural drying since the 1990s (Prasertsan and Saen-saby, 1998; Chua et al., 2002; Minea, 2013b).

Reported performance numbers for vapour-compression HPDs on agro-food products span an SMER range of approximately 0.4–4 kg/kWh and a COP range of approximately 2.5–4.5 (Prasertsan and Saen-saby, 1998, SMER 0.572 kg/kWh on banana; Minea, 2013b, SMER 1–4 kg/kWh across agro-food and wood; Yahya et al., 2016, 0.38–0.47 kg/kWh on cassava; Singh et al., 2020, drying rate 0.205 kg/(kg·min) on banana chips with R1234yf; Yahya et al., 2023, SMER 0.44 kg/kWh and SEC 4.69 kWh/kg on paddy). The spread is driven mainly by ambient state, condenser-side temperature lift, and whether the air loop is open, closed, or partially recirculated.

Three operational limits are repeatedly identified in the same body of work: COP falls as the condenser-side lift grows, evaporator frosting can become a constraint at low ambient temperature, and the achievable drying rate is capped by the moisture content of the inlet air whenever it has not been dehumidified. These three limits are what motivate the air-path and source-side modifications reviewed in §1.4, where solar gain, thermal storage, and heat recovery are added on top of an otherwise conventional HPD cycle.

## 1.4  Solar-assisted heat-pump dryers: topology landscape

Each of the three HPD limits identified above has been addressed in the literature by a different family of modifications, and the resulting solar-assisted heat-pump dryer (SAHPD) field is mature enough to support several comprehensive reviews (Daghigh et al., 2010; Mohanraj et al., 2018; Zou et al., 2023; Zhu et al., 2025). The integration patterns reported in these reviews differ in where the solar gain enters the air loop, whether the solar collector also acts as the evaporator heat source, and whether thermal storage or downstream heat recovery is added on top. The present subsection summarises the patterns most relevant to the configurations compared in this paper; the verified performance numbers for each cited work appear in Table 1.

The earliest and still most-cited family places an air-type solar collector upstream of the heat-pump condenser, so that solar gain reduces the condenser-side lift required from the compressor (Hawlader et al., 2003; Şevik, 2013; Rahman et al., 2013). Şevik (2013) reported air-collector efficiencies of 60–78% on a PV-supplied dryer drying carrot at 50 °C, while Rahman et al. (2013) used a coupled FORTRAN model to identify a payback period near four years for an evaporator-collector + air-collector layout. A second family routes the solar gain through the evaporator side, either by using the collector as a direct-expansion evaporator or by elevating the source-side temperature for the heat pump. Hawlader and Jahangeer (2006) and Hawlader, Rahman and Jahangeer (2008), working at NUS Singapore, reported evaporator-collector efficiencies of 0.80–0.86, an upper-bound COP of 7.0 in simulation (5.0 experimental), and an SMER of 0.65 kg/kWh on green beans; Amin and Hawlader (2013) summarised the same Singapore platform and reported COPs as high as 8.0 with R134a evaporator-collectors, with the caveat that these are tropical-climate values.

A third family addresses the inlet-humidity ceiling by adding thermal energy storage and downstream heat recovery to extend operating hours and to recycle exhaust enthalpy. Qiu et al. (2016) reported a combined HR + TES SAHPD with a COP of 3.21–3.49, a 40.5% reduction in input energy versus a baseline SAHPD, and crop-dependent paybacks of two to six years for radish, pepper and mushroom. Ismaeel and Yumrutaş (2020), using a periodic analytical model with a 100 m² collector and a 300 m³ tank, reported a fifth-year SMER of 9.25 kg/kWh, a heat-pump COP of 5.55, and a 21.4% annual energy saving when an HRU was added on top of the TES. Mortezapour et al. (2012) demonstrated a hybrid PV/T + heat-pump dryer for saffron with a 33% reduction in energy demand and an SMER of 1.16 kg/kWh.

A fourth, more recent set of variants targets the heat-pump cycle itself rather than the air path. Yu et al. (2024) integrated an ejector with a solar evaporator-coupled heat-pump dryer and reported a 28.7% improvement in moisture extraction rate and a 54.3% improvement in exergy efficiency over the conventional HPD baseline (SMER 1.40 kg/kWh). Abdullah et al. (2025) used a dual-condenser SAHPD with hot-water solar coupling on pandan herbs and reported a COP of 6.53 and an SMER of 2.71 kg/kWh, with the solar-driven hot-water side preheating one of the two condensers. Tang et al. (2025) reported a multistage SAHPD for tomato with 85.1% solar contribution in spring and autumn and an SMER of 40.7 kg/kWh, illustrating the upper end of what the literature currently claims.

Reported headline metrics for fruit and vegetable SAHPDs cluster broadly around COPs of 2.7–6.5 and SMERs of 0.4–2.7 kg/kWh once the multistage and tropical evaporator-collector outliers are set aside (Yahya et al., 2016, 2023; Singh et al., 2020; Kuan et al., 2019; Rulazi et al., 2023). Solar contribution and payback are highly site-dependent: continental-cold (Kuan et al., 2019) and high-altitude (Li et al., 2021) studies report comparatively lower solar fractions and slower paybacks than tropical or subtropical sites, which directly motivates the three-altitude scope of the present work. None of the cited studies, however, performs a like-for-like comparison of more than three or four topology variants under a single thermodynamic model, and none reports a humidity-aware bypass control on top of a solar + HRX air loop; that combined gap is the subject of subsection 1.5 and the contribution stated in subsection 1.7.

## 1.5  Heat-recovery exchangers and humidity-aware control

Two further air-loop modifications are repeatedly considered in the SAHPD literature, each addressing a different one of the HPD limits identified in §1.3: an exhaust-to-inlet heat-recovery exchanger (HRX), which raises the inlet temperature without increasing condenser duty, and a control strategy that throttles or bypasses recirculation when the recirculated air becomes too humid to drive further moisture removal. The two modifications interact, because an HRX placed across the chamber exhaust both recovers sensible enthalpy and shifts the humidity state of the air actually entering the heat-pump section.

For the HRX itself, a counter-flow plate geometry with an effectiveness near 0.70 is the most common fabrication choice, since the effectiveness-NTU relation for counter-flow with balanced capacity rates predicts that the area required to push effectiveness beyond about 0.75 grows non-linearly (Shah and Sekulić, 2003). Ismaeel and Yumrutaş (2020) demonstrated this trade-off quantitatively on a wheat SAHPD with thermal storage: adding a heat-recovery unit on top of the baseline TES tank produced a 21.4% annual energy saving, with the unit's restoring efficiency reported at up to 41.7% across the simulated year. Aacharya et al. (2024), working in Nepal at the Kathmandu University–Lund University platform, integrated a low-emissivity-coated double-pass collector with a counter-flow plate exchanger on an apple solar dryer and reported a collector efficiency of 89% and a payback period of 1.61 years; the apple drying rate increased from 78 g/(h·m²) on open sun and 50–84 g/(h·m²) with flat or v-corrugated collectors to 107 g/(h·m²) with the low-emissivity coated collector. Adhikari et al. (2025) followed up the same platform with an ANSYS Fluent CFD study and smoke-flow validation, raising the chamber uniformity index from 0.569 in the baseline geometry to 0.728 in their best variant; this provides Nepal-specific evidence that air-side heterogeneity inside the drying chamber is non-trivial even before any HRX or heat pump is added.

For control, recirculation-throttling and bypass strategies are an active research thread on the heat-pump side, and three groups of approaches are visible in the literature. The first group treats the bypass air ratio (BAR) and recirculation ratio as static design variables to be optimised offline against drying time and energy use; Loemba et al. (2023), reviewing closed-type air-source heat-pump dryers, report that the specific moisture extraction rate is maximised at BAR ≈ 0.4 and declines once that fraction is exceeded, with the system response otherwise dominated by drying-air temperature rather than by the bypass setting itself. The second group applies fixed-setpoint control on either temperature or chamber humidity ratio. Wang et al. (2026), working on a high-temperature heat-pump dryer for bamboo, used a bypass-airflow strategy with a fixed humidity-ratio trigger and reported a 36.5% reduction in input energy, a 60.4% increase in SMER, and a 57.5% reduction in SEC relative to a no-bypass baseline. The third and most recent group applies fuzzy or adaptive multi-energy control across the solar, heat-pump and storage subsystems jointly. Kang et al. (2024) report a fuzzy self-adaptive controller on a solar + heat-pump + phase-change-storage kelp dryer with a 40 ± 2 °C temperature setpoint and a 30 ± 5% RH setpoint, holding chamber temperature deviation within ±2 °C (versus ±5 °C under their original PLC logic) and reducing total electrical energy by up to 43.0% in solar-plus-heat-pump mode and 16.4% in heat-storage-plus-heat-pump mode. The use of vapour pressure deficit (VPD) as the explicit bypass-trigger variable is standard practice in controlled-environment agriculture and post-harvest storage but is, to the authors' knowledge, not yet reported as the control variable on a SAHPD in the literature reviewed here; it is treated in the present work as a procedural rather than a thermodynamic novelty, since the underlying physics (raising VPD by reducing the recirculation fraction whenever the chamber air saturates the kinetic driving force) is already implicit in the dehumidification arguments of Çolak and Hepbaşlı (2009) and Minea (2013a) and in the bypass-ratio results of Wang et al. (2026) and Loemba et al. (2023). Balaraman et al. (2025) provide an exergy-accounting framework for energy-recovery ventilator integration on HPDs that is useful for benchmarking but is not adopted as the headline metric in the present work.

## 1.6  Prior Nepali work and the gap this paper addresses

Within the body of literature reviewed in §1.4 and §1.5, only two peer-reviewed studies report fruit drying on a Nepali test platform, and both are products of the Kathmandu University–Lund University collaboration at Dhulikhel. Aacharya et al. (2024) instrumented a solar dryer fitted with double-pass flat, v-corrugated and low-emissivity coated collectors and a counter-flow plate heat exchanger, dried apple slices over the February–April 2023 season, and reported the drying-rate and payback figures already cited in §1.5. Adhikari et al. (2025) extended the same platform with an ANSYS Fluent CFD study of the chamber, validated by smoke-flow visualisation. Both studies are solar-only with sensible heat recovery; neither incorporates a vapour-compression heat pump, neither sweeps multiple air-path topologies under a single thermodynamic model, and neither addresses humidity-aware control of the recirculation fraction. Both Nepali studies are also single-season campaigns; no peer-reviewed Nepali study, to the authors' knowledge, reports seasonal performance of a solar dryer or solar-assisted heat-pump dryer across multiple seasons of the same year and site.

No peer-reviewed Nepali study, to the authors' knowledge, reports a heat-pump dryer of any kind, solar-assisted or otherwise, and no study from any country (Nepali or otherwise) compares the ten air-path topologies considered here under a single first-law-consistent model with a humidity-triggered exhaust bypass. The combination of three distinct Nepali altitude regimes (subtropical Biratnagar at 72 m, mid-hill Kathmandu at 1,350 m and high-hill Taplejung at 1,820 m) with a unified topology sweep and a VPD-based bypass control therefore defines the gap addressed by the present work.

## 1.7  Aim and contribution

Building on the gaps identified in §1.4–§1.6, the aim of the present work is to compare ten solar-assisted heat-pump dryer air-path topologies for apple-slice drying at 45 °C under a single first-law-consistent thermodynamic model, evaluated at three Nepali altitudes (Biratnagar at 72 m, Kathmandu at 1,350 m and Taplejung at 1,820 m) and across four seasons at each site. The ten configurations span a heat-pump-only baseline (A), series solar-assisted variants (B, C1, C2), heat-recovery exchanger variants without solar (D1, D2, D3) and combined HRX-plus-solar variants (E1, E2, E3); their air paths and topology rationale are detailed in §3. The same R-134a vapour-compression cycle, the same counter-flow plate HRX with effectiveness 0.70, the same Royen-derived apple-slice kinetic model (§1.2) and the same vapour-pressure-deficit triggered exhaust bypass control are applied uniformly across all ten configurations, so that differences in specific energy consumption and drying time are attributable to topology rather than to component-level choices. The contributions of the paper are therefore: (i) a unified ten-topology comparison under a procedurally identical thermodynamic model; (ii) a VPD-based bypass control on the recirculation loop, applied here for the first time on a SAHPD; and (iii) Nepal-specific seasonal SEC and SMER envelopes at three altitudes that bracket the country's fruit-growing belts.

---


<!-- ===== 02_system_description.md ===== -->

# 2. System description

_All ten air-path topologies share the same drying chamber, the same R134a vapour-compression cycle, the same flat-plate solar air collector model, the same counter-flow plate heat-recovery exchanger (HRX) where applicable, and the same VPD-triggered exhaust bypass valve. They differ only in how the four thermodynamic blocks (ambient inlet, solar collector, condenser, evaporator) and the optional HRX are connected. This section describes the topology of each variant. Component-level equations, refrigerant-side relations, and the kinetic and psychrometric submodels are deferred to §3._

[Figure 2.1: Master schematic of the reference dryer (Config A). Shows the drying chamber with ten loaded trays, the R134a heat-pump loop with condenser on the supply side and evaporator on the return side, the ambient inlet, the chamber exhaust port, the VPD-triggered exhaust bypass valve, and the recirculation duct. All other configurations are obtained by inserting or rerouting the solar collector and/or the HRX into this base topology.]

## 2.1 Reference configuration (Config A, HP-only)

Config A is the heat-pump-only reference against which the nine variants are benchmarked. Ambient air enters the system, passes through the condenser where it is heated to the chamber set-point T_set = 45 °C, traverses the loaded chamber, picks up moisture from the apple slices, and is partly recirculated and partly discharged. At the open-loop limit (recirculation fraction r = 0) the evaporator runs on an independent ambient draw and is decoupled from the heating stream. At r > 0 the recirculated exhaust is mixed with fresh ambient and routed first through the evaporator (where it is dehumidified and cooled) and then through the condenser (where it is reheated to T_set). The first-law constraint Q_cond = Q_evap + W_comp is enforced on every time step, and the compressor speed is sized so that the condenser-side air leaves at exactly T_set.

## 2.2 Solar-assisted variants (Configs B, C1, C2)

Three configurations introduce a flat-plate solar air collector of area A_c (the baseline value used throughout the paper is A_c = 10 m²) into the heating side of the system.

**Config B** places the collector in series with the condenser on the supply line. At r = 0 the path is Amb → Sol → Cond → Cham → Exh → Discharge, with the evaporator running on a parallel ambient draw. At r > 0 the recirculated exhaust is mixed with ambient, passes through the evaporator, then the collector, then the condenser. B is the most direct analogue of Hawlader (2003) and Şevik (2013).

**Config C1** is a solar cascade with the evaporator placed _inline_ between collector and condenser. The path at r = 0 is Amb → Sol → Evap → Cond → Cham → Exh → Discharge. The collector preheat is therefore partially undone by the dehumidifying evaporator before the condenser reheats the stream. This topology is included deliberately to quantify the thermal penalty of running the evaporator inline, a configuration that appears in some commercial schematics but has rarely been benchmarked against the parallel-evaporator alternative.

**Config C2** is a solar cascade with mixing _after_ the collector. At r = 0 the topology splits into two parallel streams: a heating path Amb → Cond → Cham → Exh → Discharge and a separate cooling path Sol → Evap → Discharge. At r > 0 the collector feeds the recirculation mix node so that solar heat is delivered to the evaporator inlet rather than to the condenser supply. The r = 0 case must be drawn with two clearly separate paths; the source-code behaviour is the authoritative reference for this configuration.

[Figure 2.2: Block-diagram grid of the nine non-reference air paths (B, C1, C2, D1, D2, D3, E1, E2, E3). Each panel uses the same icon set; arrows indicate flow direction; recirculation paths (where applicable) are drawn dashed.]

## 2.3 Heat-recovery variants (Configs D1, D2, D3)

Three configurations introduce a counter-flow plate HRX with effectiveness ε = 0.70 between the chamber exhaust and the ambient inlet. All three are open-loop (r = 0 by design) and have no solar collector.

**Config D1** routes ambient air through the cold side of the HRX, then through the condenser, then into the chamber. The exhaust passes through the hot side of the HRX and is then expelled. The evaporator runs on a separate ambient draw.

**Config D2** uses the same heating-side path as D1, but the evaporator is fed by the exhaust leaving the HRX hot side. A dynamic ambient supplement is added to the evaporator inlet so that the evaporator load matches the condenser duty under the first-law constraint.

**Config D3** is included as an inversion test: the chamber exhaust is sent to the cold side of the HRX, then to the condenser and into the chamber, while the ambient draw is sent to the hot side and then to the evaporator. This routing recovers latent heat into the supply but also recycles humid air back into the chamber, and is reported here mainly to demonstrate that the resulting humidity penalty is observable in the SEC results.

## 2.4 Combined variants (Configs E1, E2, E3)

The E group combines HRX heat recovery with solar preheat. All three are r = 0 by design; the open-loop, HRX-equipped supply removes most of the energy benefit of recirculation and would also raise the chamber humidity unnecessarily.

**Config E1** places ambient air through the HRX cold side, then the collector, then the condenser, then the chamber. The chamber exhaust passes through the HRX hot side and is discharged. The evaporator runs on an independent ambient draw, so dehumidification is fully decoupled from the heating stream.

**Config E2** uses the same heating-side path as E1, but the chamber exhaust is split: one portion gives heat back through the HRX hot side and is discharged, and the second portion is mixed with an ambient supplement and fed to the evaporator. The supplement mass flow is solved by a fixed-point iteration so that the evaporator load matches the condenser duty exactly. The recovered exhaust raises the evaporator inlet temperature and humidity, which raises COP. E2 is the best-performing topology in the present study.

**Config E3** moves the collector _downstream_ of the condenser: ambient → HRX cold side → condenser → collector → chamber. A solar-priority control overlay is applied. If the post-collector air alone reaches T_set, the heat pump is switched off and the collector finishes the temperature lift. Otherwise the heat pump runs at a variable condenser temperature chosen so that the post-collector stream meets T_set exactly, and the collector tops up the residual lift. The exhaust-side handling is identical to E2 (split between HRX recovery and evaporator supply with iterative ambient supplement).

## 2.5 VPD-triggered exhaust bypass control

A single control overlay is applied uniformly to all ten configurations: a VPD-triggered exhaust bypass valve. Vapour-pressure deficit (VPD) at the chamber outlet is monitored on every time step. When VPD falls below a threshold of 0.05 kPa (set so that mass-transfer driving force, not heat input, becomes the limiting resistance), the bypass opens and a portion of the recirculated stream is dumped to ambient and replaced with fresh dry intake. The valve uses 3× hysteresis (it must clear 3 × 0.05 = 0.15 kPa before closing) and a 600 s dwell time to suppress oscillation. The same trigger logic and the same threshold are used across all ten configs so that the bypass effect can be compared cleanly with the topology effect.

[Figure 2.3: VPD-bypass control logic. State diagram with two states (bypass closed / bypass open); transitions labelled with the VPD threshold, hysteresis multiplier, and dwell timer. A second panel shows a representative chamber-outlet VPD trace over a single batch with the bypass open/closed regions shaded.]

The bypass valve is the only active control element shared by all ten configurations. Compressor speed (sized to deliver T_set at the condenser outlet), evaporator-side ambient supplement (D2, E2, E3), and the solar-priority HP on/off switch (E3 only) are configuration-specific control elements and are described together with the topology of the relevant variant above.

---


<!-- ===== 02_airpaths_for_drawio.md ===== -->

# Air-path reference for draw.io diagrams (Configs B, C, E)

_Verified against `RQ1/src/rq1/dryer_solar_hp.py` on 2026-04-30 and consistent with `air_paths_verified.md`. Use these chains as the source of truth when drawing the topology figures._

Convention used below:
- `Amb` = ambient inlet
- `HRX_c` / `HRX_h` = HRX cold side (gains heat) / hot side (gives heat)
- `Sol` = solar air collector
- `Cond` = HP condenser (heating side)
- `Evap` = HP evaporator (cooling/dehumidifying side)
- `Cham` = drying chamber
- `Exh` = chamber exhaust
- `Mix(a + b)` = adiabatic mixing junction
- `r` = recirculation fraction (0 = full open loop; D/E configs are r = 0 by design)
- "→ Discharge" = stream leaves the system

---

## Config A — HP-only reference (no solar, no HRX)

**r = 0 (open loop)**

- Heating stream: `Amb → Cond → Cham → Exh → Discharge`
- Evaporator side: `Amb (independent draw) → Evap → Discharge` (parallel; not coupled to the heating stream at r = 0)

**r > 0 (closed/partial loop)**

- Single loop: `Mix(Amb + r·Exh) → Evap → Cond → Cham → Exh splitter:`
  - r·Exh routed back to Mix
  - (1 − r)·Exh discharged

**Comment for figure:** A is the HP-only reference. The evaporator is parallel at r = 0 and inline (after the mix node) at r > 0. All other configurations are obtained by inserting Sol and/or HRX into this base topology.

---

## Config D1 — HRX only, ambient evaporator

(All D configs are r = 0 by design.)

- Heating stream: `Amb → HRX_c → Cond → Cham → Exh → HRX_h → Discharge`
- Evaporator stream: `Amb (independent draw) → Evap → Discharge`

**Comment for figure:** counter-flow HRX with ε ≈ 0.70 between chamber exhaust and ambient inlet; evaporator decoupled on a separate ambient draw.

---

## Config D2 — HRX only, exhaust-supplied evaporator

- Heating stream: `Amb → HRX_c → Cond → Cham → Exh → HRX_h → Mix(+ Amb_supplement) → Evap → Discharge`
- The ambient supplement at the evaporator inlet is sized dynamically so the evaporator load matches the condenser duty under the first-law constraint.

**Comment for figure:** identical heating-side path to D1; the only visual difference is that the post-HRX exhaust feeds the evaporator (with an ambient supplement mix node) instead of being expelled. Mark the dynamic mix node.

---

## Config D3 — HRX swapped (inversion test)

- Heating stream: `Exh → HRX_c → Cond → Cham` (chamber exhaust enters the cold side, then heated by the condenser, then back to the chamber)
- Evaporator stream: `Amb → HRX_h → Evap → Discharge`

**Comment for figure:** D3 inverts the HRX routing. The chamber sees recycled humid air on the supply, which raises chamber humidity and degrades drying. Included as an inversion test to demonstrate the humidity penalty in the SEC results; not a serious operating candidate.

---

## Config B — Solar + HP series on the heating stream

**r = 0 (open loop)**

- Heating stream: `Amb → Sol → Cond → Cham → Exh → Discharge`
- Evaporator side: `Amb (independent draw) → Evap → Discharge` (parallel; not coupled to the heating stream at r = 0)

**r > 0 (closed/partial loop)**

- Single loop: `Mix(Amb + r·Exh) → Evap → Sol → Cond → Cham → Exh splitter:`
  - r·Exh routed back to Mix
  - (1 − r)·Exh discharged

**Comment for figure:** B is "solar in series with the condenser, on the heating stream". Most directly comparable to Hawlader 2003 / Şevik 2013.

---

## Config C1 — Solar cascade, mix BEFORE solar (inline evap)

**r = 0 (open loop, single inline stream)**

- `Amb → Sol → Evap → Cond → Cham → Exh → Discharge`
- The evap sits inline between solar and condenser, so solar preheat is partially undone by the dehumidifying evaporator before the condenser reheats.

**r > 0 (closed/partial loop)**

- `Mix(Amb + r·Exh) → Sol → Evap → Cond → Cham → Exh splitter`

**Comment for figure:** C1 deliberately puts the evaporator inline. The thermal penalty (solar gain wasted on the cooling step) is the design trade-off being illustrated.

---

## Config C2 — Solar cascade, mix AFTER solar (parallel paths at r = 0)

> ⚠ The code and the docstring disagree at r = 0. The figure must follow the **code**, not the docstring. See `air_paths_verified.md`.

**r = 0 (open loop, two parallel paths) — code-true**

- Heating path: `Amb → Cond → Cham → Exh → Discharge` (no solar in the main path)
- Cooling path: `Sol → Evap → Discharge` (solar feeds the evaporator side, separate stream)

**r > 0 (closed/partial loop) — solar feeds the recirculation mix**

- `Sol → Mix(Sol-heated air + r·Exh) → Evap → Cond → Cham → Exh splitter`

**Comment for figure:** the r = 0 case must be drawn with two clearly separate paths; do **not** draw a Sol→Cond connection at r = 0 even though the docstring suggests it. Add a footnote in the figure caption acknowledging the topology change between r = 0 and r > 0.

---

## Config E1 — HRX + Solar on the condenser stream, ambient evaporator

(All E configs are r = 0 by design; D/E paths are open-loop with VPD-triggered exhaust bypass on top.)

- Heating stream: `Amb → HRX_c → Sol → Cond → Cham → Exh → HRX_h → Discharge`
- Evaporator stream: `Amb (independent draw) → Evap → Discharge`

**Comment for figure:** counter-flow HRX with ε ≈ 0.70; solar preheat sits between HRX and condenser; evaporator runs on ambient, so dehumidification is decoupled from the heating loop.

---

## Config E2 — HRX + Solar on the condenser stream, exhaust-supplied evaporator

- Heating stream: `Amb → HRX_c → Sol → Cond → Cham → Exh splitter:`
  - portion 1 → `HRX_h → Discharge` (gives heat back to the cold side)
  - portion 2 → `Mix(Exh + Amb_supplement) → Evap → Discharge`
- The ambient supplement mass flow feeding the evaporator mix is solved by the fixed-point iteration in `_iterative_evap_sizing()`, so the evaporator load matches the condenser duty under the first-law constraint.

**Comment for figure:** the key visual difference from E1 is that the evaporator now sees a recovered (warmer, more humid) inlet stream, raising COP. Mark the iterative mix node clearly. This is the best-performing topology in the present study.

---

## Config E3 — HRX + Solar AFTER condenser, exhaust-supplied evaporator, solar-priority control

- Heating stream: `Amb → HRX_c → Cond → Sol → Cham → Exh splitter:`
  - portion 1 → `HRX_h → Discharge`
  - portion 2 → `Mix(Exh + Amb_supplement) → Evap → Discharge`

**Solar-priority control overlay (must be shown on the figure or in the caption):**
1. If `HRX_c → Sol` outlet alone reaches T_set, HP is **OFF**. Solar finishes the lift.
2. Otherwise, HP runs at a variable T_cond chosen so that the post-solar stream meets T_set. Solar tops up; HP only provides the residual lift.

**Comment for figure:** key difference from E2 is solar AFTER the condenser, not before. This lets solar opportunistically replace HP duty when irradiance is high. Worth a small inset on the figure showing the control logic switch.

---

## Notes for all figures

- Use the same icon set across all 10 figures so the reader can compare topologies at a glance.
- Mark r = 0 vs r > 0 paths in different stroke styles when both are shown on one figure (e.g., solid for r = 0 open loop, dashed for the recirculation overlay).
- Show direction arrows on every segment.
- Label all heat exchangers with the duty name (Q_sol, Q_cond, Q_evap, Q_HRX) so §3 can refer back to the same labels.
- VPD-bypass exhaust valve is the same on all 10 configs; draw it on the master schematic only and reference it in the others.

---


<!-- ===== 03_mathematical_model.md ===== -->

# 3. Mathematical model

_All ten configurations share the same component-level model. Only the connectivity (described in §2) and a small number of configuration-specific control rules differ. Refrigerant properties are evaluated through CoolProp; moist-air properties from a Tetens-based psychrometric library; the drying kinetics from the parametric M1 model fitted on 13 thin-layer apple-drying curves (§3.4)._

## 3.1 Vapour-compression cycle

The heat pump uses R134a as the working fluid. Each time step solves the four state points of a single-stage cycle with fixed superheat ΔT_sh = 5 K at the evaporator outlet and fixed sub-cooling ΔT_sc = 5 K at the condenser outlet. Compressor isentropic efficiency η_is = 0.75 and mechanical efficiency η_m = 0.95 are held constant.

State 1 (evaporator outlet, superheated vapour):
T₁ = T_evap + ΔT_sh, P₁ = P_sat(T_evap), h₁ = h(T₁, P₁) [Eq. 3.1]

State 2s (isentropic compression endpoint):
P_2s = P_sat(T_cond), s_2s = s₁, h_2s = h(P_2s, s_2s) [Eq. 3.2]

State 2 (actual compressor outlet):
h₂ = h₁ + (h_2s − h₁) / η_is [Eq. 3.3]

State 3 (condenser outlet, sub-cooled liquid):
T₃ = T_cond − ΔT_sc, h₃ = h(T₃, P_cond) [Eq. 3.4]

State 4 (expansion-valve outlet, two-phase):
h₄ = h₃ (isenthalpic), x₄ = (h₄ − h_f) / (h_g − h_f) [Eq. 3.5]

The refrigerant mass flow is sized to the air-side condenser duty Q_cond_target:
m_ref = Q_cond_target / (h₂ − h₃) [Eq. 3.6]

Energy flows and COP follow:
Q_evap = m_ref (h₁ − h₄), W_comp = m_ref (h₂ − h₁) / η_m, COP = Q_cond / W_comp [Eq. 3.7]

Operating envelope: −5 °C ≤ T_evap ≤ 20 °C, 30 °C ≤ T_cond ≤ 70 °C, pressure ratio ≤ 10. Cases that fall outside are flagged but not clipped, so unphysical operating points are visible in the results.

For sizing, the condenser pinch is fixed at +10 K above the air-outlet target and the evaporator approach at −10 K below the heat-source temperature. T_evap ≥ T_cond is treated as a hard fault and a 1 K minimum lift is enforced so CoolProp does not return a degenerate cycle.

## 3.2 Solar air collector

The flat-plate solar air collector is modelled with the Hottel-Whillier-Bliss steady-state form. Useful gain per time step is

Q_useful = A_c · F_R · [η_o · K_θ · G − U_L · (T_in − T_amb)] [Eq. 3.8]

with collector area A_c (baseline 10 m²), optical efficiency η_o = 0.75 (transmittance-absorptance product), incidence-angle modifier K_θ = 1.0 (assumes a south-tilted reference orientation), and overall loss coefficient U_L = 5 W m⁻² K⁻¹. The heat-removal factor F_R follows the standard ε-NTU form for an air collector,

F_R = (C_min / UA) · [1 − exp(−UA · F′ / C_min)] [Eq. 3.9]

with collector efficiency factor F′ = 0.90 and capacity rate C_min = ṁ_air c_p,air. The outlet air temperature is

T_out = T_in + Q_useful / (ṁ_air c_p,air) [Eq. 3.10]

Stagnation (ṁ_air = 0 or G < 10 W m⁻²) collapses Eq. 3.8 to zero useful gain. Absorber-plate temperature is tracked with first-order thermal inertia (C_collector = 10 kJ K⁻¹) so that abrupt irradiance steps do not produce instantaneous outlet-temperature jumps:

T_abs(t+Δt) = (1 − α) T_abs(t) + α T_abs,ss, α = Δt / (τ + Δt), τ = C_collector / (A_c U_L / 1000) [Eq. 3.11]

A stagnation cap of T_abs ≤ 150 °C is enforced as a numerical safeguard.

## 3.3 Counter-flow heat-recovery exchanger (HRX)

Configurations D1, D2, D3, E1, E2, and E3 include a flat-plate counter-flow air-to-air HRX between the chamber exhaust and the ambient inlet. The HRX is modelled as a single-effectiveness device with ε_HRX = 0.70 (consistent with commercial polymer-plate units of comparable size). For air streams of equal mass flow,

T_amb,heated = T_amb + ε_HRX (T_exhaust − T_amb) [Eq. 3.12]
T_exh,cooled = T_exhaust − ε_HRX (T_exhaust − T_amb) [Eq. 3.13]

with the cold-side outlet humidity ratio held equal to the cold-side inlet (no mass transfer across the HRX plates is modelled; condensate that forms on the hot side is removed but does not cross to the cold side).

## 3.4 Drying kinetics (M1 parametric Arrhenius model)

The drying-chamber moisture content evolves through a first-order kinetic law,

dX/dt = −K_eff(T, RH, v, d) · (X − X_eq) [Eq. 3.14]

discretised on each time step as

X(t+Δt) = X(t) − K_eff (X(t) − X_eq) Δt, X(t+Δt) ≥ X_eq [Eq. 3.15]

The effective rate constant K_eff is the M1 parametric form fitted by single-stage non-linear least squares to thirteen PAVA-cleaned thin-layer apple-drying MR(t) curves drawn from the project's experimental dataset:

K_eff(T, RH, v, d) = K_ref · exp[(E_a/R)(1/T_ref − 1/T)] · exp(−α_RH · RH/100) · (v / v_ref)^γ_v · (d_ref / d)^δ_d [Eq. 3.16]

with reference state T_ref = 50 °C, v_ref = 1.1 m s⁻¹, d_ref = 6 mm, and fitted parameters
- K_ref = 2.097 × 10⁻⁴ s⁻¹
- E_a/R = 3738 K (E_a = 31.08 kJ mol⁻¹, profile 95 % CI [28.56, 33.60] kJ mol⁻¹)
- α_RH = 1.965
- γ_v = 0.401
- δ_d = 0.589

Fit residual RMSE on MR is 0.04685 across all thirteen curves (n_obs = 386). The activation-energy CI overlaps the published apple-specific convective range cited in §1.2 (14.47–22.62 kJ mol⁻¹) at its lower end; the upper end of our CI exceeds that range and is consistent with the broader 12–83 kJ mol⁻¹ envelope reported by Erbay & Icier (2010) across 41 food products. A leave-one-curve-out cross-validation (LOCO-CV, n = 13) returned mean RMSE_MR = 0.0528 for M1, 0.0404 for an Arrhenius+Midilli alternative (M2), and 0.0685 for a piecewise-linear ElasticNet baseline (M3). M1 and M2 differ within their bootstrap confidence interval; both significantly outperform M3. M1 is used as the operational kinetic model and M2 is used as the sensitivity bracket in §5.

## 3.5 GAB sorption isotherm

Equilibrium moisture content X_eq at chamber temperature T and relative humidity RH (water activity a_w = RH) follows the three-parameter GAB form,

X_eq = (X_m C K a_w) / [(1 − K a_w)(1 − K a_w + C K a_w)] [Eq. 3.17]

with temperature-dependent parameters

X_m(T) = X_{m,0} exp(ΔH_xm / R T), C(T) = C_0 exp(ΔH_C / R T), K(T) = K_0 exp(ΔH_K / R T) [Eq. 3.18]

The constants (X_{m,0} = 3.141 × 10⁻³ kg kg⁻¹ db, ΔH_xm = 8 057 J mol⁻¹, C_0 = 4.923 × 10⁻³, ΔH_C = 17 241 J mol⁻¹, K_0 = 0.9904, ΔH_K ≈ 0 J mol⁻¹) were taken from a pooled dataset for apple desorption (Kaymak-Ertekin & Gedik 2004; Maroulis et al. 1988; Mbarek & Mihoubi 2019), giving an RMSE of 0.005 kg kg⁻¹ db across 28 experimental points spanning 30–60 °C. To prevent a singularity as a_w → 1/K, the water activity is clamped at 0.95 within the simulation.

## 3.6 Psychrometrics and moist-air enthalpy

Saturation vapour pressure follows the Tetens correlation (over liquid water for T ≥ 0 °C, over ice otherwise). Humidity ratio, relative humidity, and dew-point temperature are computed at the local atmospheric pressure of each site (Biratnagar 100 460 Pa; Kathmandu 86 120 Pa; Taplejung 81 000 Pa), so the psychrometric chart shifts correctly with altitude.

Moist-air specific enthalpy is

h = c_{p,da} T + ω (h_{fg,0} + c_{p,v} T) [Eq. 3.19]

with c_{p,da} = 1.006 kJ kg⁻¹ K⁻¹, c_{p,v} = 1.86 kJ kg⁻¹ K⁻¹, and h_{fg,0} = 2 501 kJ kg⁻¹. Adiabatic mix nodes (Mix(a + b) in §2) are solved by mass-and-enthalpy balance:

ṁ_mix h_mix = ṁ_a h_a + ṁ_b h_b, ṁ_mix ω_mix = ṁ_a ω_a + ṁ_b ω_b [Eq. 3.20]

A constant-enthalpy humidification with a small liquid-water enthalpy correction (h_out = h_in + Δω · 4.186 · T_in_C) is used inside the chamber so the energy released when liquid water enters the air stream is accounted for; this correction was added after the 2026-04-09 first-law audit revealed that ignoring it produced a Q_cond − (Q_evap + W_comp) imbalance of order 10⁻³.

The chamber-outlet RH is bounded by RH_out,max (configurable, default 0.95) so that the air is never asked to pick up more moisture than it can carry; the kinetic step (§3.4) and the air-capacity step are taken as a minimum and the simulation reports both.

## 3.7 Configuration-specific control overlays

Three configurations apply additional control rules on top of the shared component model:

- **Iterative evaporator-supply sizing (D2, E2, E3).** The ambient supplement that is mixed with the recovered exhaust before the evaporator is solved by a fixed-point iteration so that Q_evap matches Q_cond − W_comp under the first-law constraint at the current operating point; convergence tolerance is 10⁻³ on mass-flow ratio.
- **Solar-priority HP control (E3 only).** If the post-collector air alone reaches T_set = 45 °C (i.e. Q_HRX + Q_solar already covers the chamber duty), the heat pump is switched off for that time step and the collector is allowed to finish the temperature lift. Otherwise the heat pump runs at a variable T_cond chosen so that the post-collector stream exits at exactly T_set, and the collector tops up the residual lift.
- **VPD-triggered exhaust bypass (all ten configs).** As described in §2.5, the bypass valve opens when the chamber-outlet vapour-pressure deficit drops below 0.05 kPa, and closes after a 3× hysteresis margin (0.15 kPa) and a 600 s dwell timer. The same threshold and timing are used uniformly across the ten topologies.

## 3.8 First-law enforcement and validation

The condenser-side air-heating duty is taken as the binding constraint on every time step:

Q_cond_target = ṁ_air (h_air,out_set − h_air,in) [Eq. 3.21]

with h_air,in evaluated at the actual condenser inlet (which depends on the topology) and h_air,out_set evaluated at T_set with the inlet humidity ratio. The compressor speed (and hence m_ref) is sized to deliver Q_cond_target exactly. Q_evap is then computed from Eq. 3.7 and matched to the evaporator-side air capacity by either (i) the parallel ambient draw (A r=0, B r=0, D1, E1), (ii) the dynamic ambient supplement (D2), or (iii) the iterative supplement (E2, E3). At every time step the first-law residual

ε_FL = Q_cond − (Q_evap + W_comp) [Eq. 3.22]

is logged. The 2026-04-09 model-validation pass (Configs A, B, D1, D2, E1, E2 across all three sites) returned |ε_FL| < 10⁻⁶ kW on every time step, alongside |Σ dm_w − m_w_cum| < 10⁻⁶ kg for the water mass balance and |ω_calc − ω_psychro| < 4 × 10⁻⁶ for the psychrometric consistency check. COP values were 3.5–4.8 with Carnot efficiency 0.61–0.62 across configurations, consistent with η_is = 0.75 and the operating envelope of §3.1, and no frost or impossible-cycle flags were raised.

---


<!-- ===== 04_simulation_setup.md ===== -->

# 4. Simulation setup

## 4.1 Sites and weather data

The ten topologies are run at three Nepali sites chosen to span the altitude band over which apple cultivation and post-harvest drying are economically relevant:

- **Biratnagar** (26.45 °N, 87.27 °E, 72 m a.s.l., P_atm ≈ 100 460 Pa): hot, humid Terai lowland; high baseline ambient enthalpy reduces the marginal value of the heat pump.
- **Kathmandu** (27.71 °N, 85.32 °E, 1 350 m a.s.l., P_atm ≈ 86 120 Pa): temperate mid-hill capital; the bulk of the country's apple processing infrastructure sits at this altitude band.
- **Taplejung** (27.35 °N, 87.67 °E, 1 820 m a.s.l., P_atm ≈ 81 000 Pa): cooler mid-hill apple-growing region in eastern Nepal; lower baseline temperature and lower atmospheric pressure relative to Biratnagar.

Hourly weather data (dry-bulb temperature T_amb, relative humidity RH_amb, global horizontal irradiance GHI, diffuse irradiance, direct-normal irradiance, wind speed, surface pressure) for each site are drawn from the PVGIS-SARAH3 typical-meteorological-year (TMY) database for the period 2011–2023. Each TMY file contains 8 760 hourly records and is the standard PVGIS comma-separated export with no further smoothing or imputation. The simulation linearly interpolates the hourly TMY values onto the 60-second internal time step (§4.2).

The site-specific atmospheric pressure is used both in the psychrometric calculations (§3.6) and in the moist-air density that sets the air mass flow at constant volumetric flow. At T_set = 45 °C, the resulting air densities are 1.100 kg m⁻³ (Biratnagar), 0.937 kg m⁻³ (Kathmandu), and 0.891 kg m⁻³ (Taplejung).

[Figure 4.1: Annual TMY profiles for the three sites: monthly-mean T_amb, RH_amb, and GHI. Each panel shows three traces (one per site) so the altitude effect is visible at a glance.]

## 4.2 Operating inputs

A single operating-point specification is used across all configurations and all sites so that differences in SEC are attributable to the topology and to the climate, not to the product loading.

| Symbol | Value | Description |
|---|---|---|
| T_set | 45 °C | Chamber set-point air temperature |
| ΔT_tol | ±2 K | Set-point tolerance band |
| m_p,dry | 3.0 kg | Dry mass of apple load per batch (≈ 22.5 kg fresh at X₀ = 6.5) |
| N_trays | 10 | Stacked trays per batch |
| d | 6 mm | Apple-slice thickness (M1 kinetic reference) |
| v_air | 1.1 m s⁻¹ | Superficial air velocity past the trays (M1 kinetic reference) |
| X₀ | 6.5 kg kg⁻¹ db | Initial moisture content (apple, mid-ripeness) |
| X_target | 0.10 kg kg⁻¹ db | Target final moisture content |
| X_eq | 0.0 kg kg⁻¹ db | Equilibrium moisture for the kinetic floor (conservative) |
| A_c | 10 m² | Baseline solar-collector area (B, C1, C2, E1, E2, E3) |
| ε_HRX | 0.70 | HRX effectiveness (D1, D2, D3, E1, E2, E3) |
| VPD_thr | 0.05 kPa | VPD-bypass trigger (all configs) |
| Δt | 60 s | Internal simulation time step |
| Refrigerant | R134a | Working fluid (η_is = 0.75, η_m = 0.95) |

The 3.0 kg dry / 22.5 kg fresh batch is sized so that the steady-state condenser duty in the reference configuration (Config A) is close to 4 kW, matching the rated capacity of a commercial 1-ton-AC heat-pump core; this keeps the simulation within an off-the-shelf hardware envelope. The 60 s time step is short enough that the slowest control transient (the 600 s VPD-bypass dwell, §2.5) is resolved with an order-of-magnitude margin while keeping a full annual sweep tractable.

All batches start with the chamber pre-soaked at ambient. The simulation terminates when the bulk-average dry-basis moisture content X_db crosses X_target from above; the elapsed simulation time becomes the drying time t_dry. Specific energy consumption is reported as

SEC = ∫₀^{t_dry} (W_comp + W_fan) dt / m_w,removed [kWh kg⁻¹] (Eq. 4.1)

with m_w,removed = m_p,dry (X₀ − X_target) ≈ 19.2 kg per batch. W_comp is the compressor shaft power scaled by the motor efficiency η_m = 0.95 (§3.1) and W_fan is the supply-fan electrical draw computed from the air-side pressure drop and a fan efficiency η_fan = 0.60 (§3.6). Standby and control-electronics losses are not modelled. The figure of merit reported in §5 is therefore the electrical SEC at the system battery limit, which is the comparable basis to the SAHPD literature reviewed in §1.

## 4.3 Model validation

The full first-law and mass-balance audit was carried out on 9 April 2026 across six representative configurations (A, B, D1, D2, E1, E2) at all three sites. Three checks were applied at every internal time step of every run:

1. **First law on the refrigerant cycle.** ε_FL = Q_cond − (Q_evap + W_comp) [Eq. 3.22]. Maximum absolute residual across the audit set: |ε_FL| < 10⁻⁶ kW.
2. **Water mass balance on the chamber.** |Σ dm_w − m_w_cum| < 10⁻⁶ kg, where dm_w is the per-step kinetic withdrawal (§3.4) and m_w_cum is the cumulative integration of the chamber-outlet humidity-ratio gain.
3. **Psychrometric consistency.** |ω_state − ω_psychro(T, RH)| < 4 × 10⁻⁶ kg kg⁻¹ at every state node.

In addition, the condenser-effectiveness model (§3.1) was checked against the air-side energy balance: the supply-air outlet T_to_chamber matches the effectiveness prediction at numerical precision. Heat-pump COP ranged from 3.5 to 4.8 across the six configurations and three sites, with Carnot efficiency 0.61–0.62, consistent with the η_is = 0.75 and η_m = 0.95 assumptions in §3.1. No frost flags (T_evap < −5 °C) and no impossible-cycle flags (T_evap ≥ T_cond) were raised in any of the audited runs.

The kinetic submodel (§3.4) was independently validated by leave-one-curve-out cross-validation on the thirteen thin-layer apple-drying curves used to fit M1. The cross-validated RMSE on dimensionless moisture ratio was 0.0528 for M1, 0.0404 for the Arrhenius-Midilli alternative (M2), and 0.0685 for the piecewise-linear ElasticNet baseline (M3); the M1–M2 difference is not significant at the 95 % bootstrap CI, while both M1 and M2 are significantly more accurate than M3. M1 is used as the operational kinetic model in §5 and M2 as the sensitivity bracket; M3 is reported only as a reference baseline.

Because each topology is exposed to the same T_set, the same chamber loading, and the same kinetic model, every configuration reaches the same drying time within numerical precision when fed with the same TMY hour. The dispersion in SEC across configurations and sites reported in §5 is therefore driven entirely by the electrical compressor duty W_comp and not by differences in residence time or moisture endpoint.

---


<!-- ===== 05_results.md ===== -->

# 5. Results

## 5.1 Headline results across eight topologies and three sites

The electrical specific energy consumption (SEC, Eq. 4.1) was computed for each (configuration, site) pair under the two kinetic models retained in §3.4: M1 (parametric Arrhenius–Midilli, operational) and M2 (Arrhenius–Midilli, sensitivity). All forty-eight runs converged to the target moisture content X_target = 0.10 kg kg⁻¹ (dry basis) and satisfied the first-law, water-mass, and psychrometric residual checks reported in §4.3.

| Config | Biratnagar (M1 / M2) | Kathmandu (M1 / M2) | Taplejung (M1 / M2) |
|---|---|---|---|
| A (HP only)              | 0.555 / 0.571 | 0.730 / 0.796 | 0.578 / 0.632 |
| B (solar+HP series)      | 0.299 / 0.314 | 0.502 / 0.567 | 0.357 / 0.410 |
| C1 (solar→evap cascade)  | 0.937 / 0.888 | 0.770 / 0.713 | 0.925 / 0.626 |
| C2 (mix-after-solar)     | 0.393 / 0.409 | 0.574 / 0.640 | 0.436 / 0.490 |
| D1 (HRX, amb evap)       | 0.241 / 0.241 | 0.292 / 0.297 | 0.252 / 0.258 |
| D2 (HRX, exh evap)       | 0.241 / 0.240 | 0.293 / 0.298 | 0.254 / 0.259 |
| E1 (HRX+solar, amb evap) | 0.100 / 0.095 | 0.153 / 0.156 | 0.133 / 0.132 |
| **E2 (HRX+solar, exh evap)** | **0.096 / 0.091** | **0.144 / 0.146** | **0.128 / 0.126** |

_Table 5.1. Electrical SEC [kWh kg⁻¹ water] for the eight engineering-viable topologies at three sites under the M1 (operational) and M2 (sensitivity) kinetic models. Bold values denote the per-column minimum; the bold row identifies the global optimum. Configurations D3 (HRX-inverted) and E3 (solar post-condenser) are mis-routed variants retained only as mechanism-inversion tests and are discussed in §5.4 and §5.5, respectively._

[Figure 5.1: 8 × 3 SEC heatmap (M1) with the M2 bracket annotated per cell. Colour scale is viridis, log-stretched between 0.09 and 1.0 kWh kg⁻¹.]

Three features of Table 5.1 frame the remainder of §5. First, configuration E2 attains the global SEC minimum at every site, with M1 values of 0.096, 0.144, and 0.128 kWh kg⁻¹ at Biratnagar, Kathmandu, and Taplejung, respectively; the closest competitor (E1) trails by 4–6 % at each site. Second, the four heat-recovery configurations (D1, D2, E1, E2) cluster below 0.30 kWh kg⁻¹, whereas the HP-only baseline (A) and the solar-cascade variants (B, C2) occupy the 0.30–0.80 band. Configuration C1 exceeds 0.45 kWh kg⁻¹ at all sites because ambient air enters the evaporator upstream of the condenser, which drives the refrigerant cycle into its low-temperature clip band during cold nights at Taplejung; this mechanism is examined in §5.3. Third, the M1–M2 bracket remains within 5 % across the heat-recovery family but widens to 32 % at C1-Taplejung. Because the leave-one-curve-out cross-validation in §4.3 placed M1 and M2 in a statistical tie, the bracket should be interpreted as the kinetic-sensitivity envelope: rankings are robust where it is narrow and fragile where it is wide.

The subsequent sections unpack the table in physical layers, namely the bare HP baseline and the recirculation valley (§5.2), the role of solar pre-heat (§5.3), passive heat recovery through the HRX (§5.4), the VPD-bypass control lever as a topology-independent axis (§5.4b), and the combined HRX–solar topologies that yield the headline numbers (§5.5). The SEC–solar-area Pareto and the synthesis statement close the chapter in §5.6.

## 5.2 Heat-pump-only baseline (configuration A, open-loop)

Configuration A, an open-loop heat-pump dryer in which ambient air is drawn in, reheated by the condenser, passed through the chamber, and exhausted to atmosphere, was examined first to quantify the irreducible electrical demand in the absence of solar pre-heat or exhaust recovery. This topology corresponds to the canonical "Mode A" baseline reported in the fruit and vegetable heat-pump-drying literature (Sun et al., 2025; Mujumdar and Chou, 2021). Bypass-air-ratio (BAR) control of partial recirculation is well-established for tumble-dryer geometries (Mancini et al., 2022; Shi et al., 2026) but was not re-tested here because the present study targets the bulk-product cabinet geometry and the recirculation question is addressed through the heat-recovery configurations of §5.4–§5.5.

Drying-window means of the ambient drivers and compressor-on means of the cycle variables were computed from the per-step simulator output for each run. Means denoted "drying-window" are arithmetic averages over the full converged window; "compressor-on" means are restricted to time steps with W_comp > 0.01 kW. Cumulative totals were taken at the final time step.

Ambient drivers and HP-cycle response at the three sites are reported in Table 5.2.1. The condenser-leaving temperature is held at 55 °C by the controller (45 °C chamber set-point plus the 10 K cond-side approach defined in §3.1). The ambient VPD entry is the drying-window-averaged ambient vapour-pressure deficit, p_sat(T_amb) − p_v,amb.

| Block | Quantity | Biratnagar (72 m) | Kathmandu (1350 m) | Taplejung (1820 m) |
|---|---|---|---|---|
| **Ambient** | T_amb (drying-window mean) | 18.8 °C | 9.8 °C | 13.6 °C |
| | RH_amb (mean) | 63.8 % | 83.8 % | 60.8 % |
| | VPD_amb (mean) | 822 Pa | 199 Pa | 611 Pa |
| | GHI (mean over window) | 276 W m⁻² | 208 W m⁻² | 220 W m⁻² |
| **HP cycle** | T_evap (compressor-on mean) | 8.77 °C | -0.24 °C | 3.57 °C |
| | T_cond (compressor-on mean) | 55.00 °C | 55.00 °C | 55.00 °C |
| | ΔT_lift (T_cond − T_evap) | 46.23 K | 55.24 K | 51.43 K |
| | COP (compressor-on mean) | 4.42 | 3.62 | 3.92 |
| | W_comp (compressor-on mean) | 0.702 kW | 0.977 kW | 0.760 kW |
| | Q_cond (compressor-on mean) | 3.077 kW | 3.536 kW | 2.977 kW |
| **Totals** | Drying time t_dry | 14.73 h | 14.10 h | 14.25 h |
| | W_comp + W_fan cumulative | 10.72 kWh | 14.16 kWh | 11.19 kWh |
| | Q_cond cumulative | 45.39 kWh | 49.92 kWh | 42.47 kWh |
| | Water removed m_w | 19.33 kg | 19.35 kg | 19.35 kg |
| | **SEC (M1)** | **0.555 kWh kg⁻¹** | **0.730 kWh kg⁻¹** | **0.578 kWh kg⁻¹** |

_Table 5.2.1. Configuration A at r = 0: ambient drivers and HP-cycle statistics. All cycle means are taken over rows in which the compressor is operating; ambient means are taken over the full drying window._

[Figure 5.2b: Six-panel time series of (a) T_amb, (b) VPD_amb, (c) Q_cond, (d) COP, (e) bulk-average moisture content X_db, and (f) cumulative W_comp at each site over the drying window.]

The drying time is nearly site-invariant (14.1–14.7 h) because the condenser-effectiveness controller (§3.6) regulates the chamber-supply temperature to 45 °C ± 2 K at every time step. The kinetic clock (Eq. 3.16) is therefore driven by T_chamber and ω_chamber, both of which are decoupled from site once the controller is in regulation; the residual 4 % spread originates in the second-order influence of ambient absolute humidity on ω_chamber, which is slightly higher at Biratnagar (8.54 g kg⁻¹) than at Kathmandu (7.38) or Taplejung (7.31).

Panel (b) of Figure 5.2b shows that the ambient VPD at Biratnagar rises sharply during the middle of the drying window, reaching above 1400 Pa at the third-quartile point of the run before falling back to ~700 Pa near completion. This behaviour reflects the diurnal cycle that falls within the simulated window: the start time is set so that drying spans morning through afternoon, with T_amb climbing from ~16 °C at start to ~23 °C at midday and falling to ~18 °C by the end, while RH_amb drops from ~80 % to ~47 % over the same interval. The non-linear dependence of p_sat on T_amb amplifies the temperature swing into the prominent VPD peak. The corresponding swing at Taplejung is smaller (peak ~792 Pa) because the air there warms by only 3 K within the window, and at Kathmandu the peak (~309 Pa) is suppressed by the persistently high relative humidity.

The 9 K spread in ΔT_lift across sites follows directly from ambient temperature. Because the condenser-leaving temperature is fixed at 55 °C and the evaporator settles approximately 10 K below T_amb (the design approach used in §3.1), the lift is ΔT_lift ≈ 65 K − T_amb. The compressor-on T_evap values of 8.77, −0.24, and 3.57 °C agree with the predicted T_amb − 10 K to within 0.5 K at all three sites. The polytropic compressor model (Eq. 3.4) returns COPs of 4.42, 3.62, and 3.92, against Carnot reference values of 7.10, 5.94, and 6.39 at the observed lifts. The actual-to-Carnot ratios (0.622, 0.609, 0.614) agree to within 2 %, confirming that the refrigerant cycle operates at a uniform isentropic efficiency across sites and that the inter-site COP spread is attributable entirely to the Carnot lift rather than to any second-order effect of pressure or pressure-ratio.

The condenser duty (3.08, 3.54, and 2.98 kW) is the air-side sensible load ṁ_air · c_p · (T_to_chamber − T_amb). Volumetric flow is fixed at 0.18 m³ s⁻¹ (§3.6), so ṁ_air scales with site air density (1.100, 0.937, and 0.891 kg m⁻³). The product ρ · ΔT_sensible (28.8, 33.0, 28.0 in arbitrary units) reproduces the measured Q_cond ratios to within 0.5 %. Kathmandu therefore has the largest condenser duty despite its lowest density, because its 35 K sensible lift more than compensates. The corresponding compressor power, W_comp = Q_cond / COP, evaluates to 0.697, 0.978, and 0.760 kW, matching the tabulated means to within 1 %.

The Biratnagar–Taplejung SEC near-tie (0.555 versus 0.578 kWh kg⁻¹, a 4 % gap) arises because the two sites exchange penalties of similar magnitude. Biratnagar has the higher chamber-supply humidity (mean 8.54 g kg⁻¹), which depresses the kinetic-rate constant through the α_RH = 1.97 humidity factor in Eq. 3.16 and lengthens the drying time to 14.73 h. Taplejung is drier (7.31 g kg⁻¹) and finishes earlier (14.25 h), but its lower ambient temperature inflates ΔT_lift by 5.2 K and depresses the cycle COP from 4.42 to 3.92. The net cumulative compressor work, equal to the time-average power multiplied by t_dry, is 10.72 kWh at Biratnagar and 11.19 kWh at Taplejung, leaving the integrated electrical demand within 4 % of each other. The Kathmandu penalty, by contrast, is not a partial cancellation but a stacking of two adverse effects: the 35 K sensible lift combines with the depressed COP (3.62) to raise the integrated compressor demand to 14.16 kWh, a 32 % premium over Biratnagar. The headroom available to the lift-reducing (solar) and enthalpy-recovering (HRX) mechanisms developed in §5.3–§5.5 is therefore largest at Kathmandu.

In summary, the open-loop HP topology requires 0.555–0.730 kWh kg⁻¹ across the three sites and serves as the reference against which all subsequent configurations are benchmarked.

## 5.3 Solar pre-heat: three ways to add a 10 m² collector to Config A

This section drops a 10 m² flat-plate collector (η_optical = 0.75, U_L = 5 W m⁻² K⁻¹, §3.2) into the air path in three different positions and reports what changes. The only difference between B, C1, C2 and the A baseline is where the collector sits relative to the evaporator and condenser. Numbers come from `outputs/config_{B,C1,C2}/{site}/Ac_10m2.csv`; A-baseline numbers are reproduced from Table 5.2.1 for direct comparison.

### 5.3.1 Headline comparison

[Figure 5.3a: SEC at three sites for Configs A, B, C1, C2 (10 m² collector, r = 0).]

| Quantity | A (HP only) | B (solar→cond) | C1 (cascade, mix-before) | C2 (mix-after-solar) |
|---|---|---|---|---|
| **Biratnagar :  SEC** | 0.555 | **0.299 (-46 %)** | 0.937 (+69 %) | 0.393 (-29 %) |
| t_dry [h] | 14.7 | 14.7 | 29.3 | 14.7 |
| W_comp + W_fan [kWh] | 10.72 | 5.78 | 18.10 | 7.60 |
| Q_cond cum. [kWh] | 45.4 | 23.6 | 70.1 | 45.4 |
| Q_solar cum. [kWh] | 0 | 22.8 | 32.1 | 22.8 |
| T_evap mean [°C] | 8.77 | 8.78 | 4.79 | **22.13** |
| COP (compressor-on mean) | 4.42 | 4.42 | 4.03 | **7.69** |
| **Kathmandu :  SEC** | 0.730 | **0.502 (-31 %)** | 0.770 (+5 %) | 0.574 (-21 %) |
| t_dry [h] | 14.1 | 14.1 | 33.0 | 14.1 |
| W_comp + W_fan [kWh] | 14.16 | 9.74 | 14.88 | 11.14 |
| Q_cond cum. [kWh] | 49.9 | 33.8 | 54.8 | 49.9 |
| Q_solar cum. [kWh] | 0 | 15.9 | 34.6 | 15.9 |
| T_evap mean [°C] | -0.24 | -0.24 | 1.91 | **11.12** |
| COP (compressor-on mean) | 3.62 | 3.62 | 3.80 | **5.02** |
| **Taplejung :  SEC** | 0.578 | **0.357 (-38 %)** | 0.925 (+60 %) | 0.436 (-25 %) |
| t_dry [h] | 14.25 | 14.25 | 53.4 | 14.25 |
| W_comp + W_fan [kWh] | 11.19 | 6.90 | 18.43 | 8.47 |
| Q_cond cum. [kWh] | 42.5 | 25.4 | 67.6 | 42.5 |
| Q_solar cum. [kWh] | 0 | 16.8 | 41.0 | 16.8 |
| T_evap mean [°C] | 3.57 | 3.56 | 2.57 | **16.19** |
| COP (compressor-on mean) | 3.92 | 3.92 | 3.85 | **6.17** |

_Table 5.3.1. Solar configs B, C1, C2 vs A baseline at three sites, 10 m² collector, r = 0. Δ-SEC in bold/parentheses is the percentage change relative to A at the same site. Bold COP/T_evap entries highlight which mechanism each topology activates._

The table makes the three mechanisms visible at a glance:

- **Config B** keeps t_dry identical to A at every site and reduces SEC by 31–46 %. Q_solar appears directly as a *reduction in Q_cond*: BTN drops 45.4 → 23.6 kWh (-21.8, matched by the 22.8 kWh of Q_solar within 5 %), KTM drops 49.9 → 33.8 (-16.1 vs 15.9 Q_solar), TPJ drops 42.5 → 25.4 (-17.1 vs 16.8). T_evap and COP are unchanged because the evaporator still draws ambient air. Solar enthalpy is substituting one-for-one for condenser duty.
- **Config C2** also keeps t_dry identical to A and reduces SEC by 21–29 %, but the mechanism is completely different. Q_cond is identical to A's (45.4 / 49.9 / 42.5 kWh, three significant figures); the collector is feeding the *evaporator* side, raising T_evap from 8.77 → 22.13 °C (BTN), -0.24 → 11.12 (KTM), 3.57 → 16.19 (TPJ). The Carnot lift collapses and COP jumps from 4.42 → 7.69 (BTN), 3.62 → 5.02 (KTM), 3.92 → 6.17 (TPJ). C2 reduces compressor work by raising COP, not by replacing thermal duty.
- **Config C1** does the worst thing: it puts the collector *and* the evaporator in series before the condenser, which dehumidifies air that did not need dehumidifying and stretches drying time by 2.0 × (BTN), 2.3 × (KTM), 3.7 × (TPJ). SEC explodes at BTN and TPJ (+69 %, +60 %) and barely loses to A at KTM (+5 %). The diagnostic of why TPJ is so much worse than BTN and KTM occupies §5.3.4 in full.

### 5.3.2 Config B: solar substitutes for condenser duty

[Figure 5.3b: Config B (r = 0, A_c = 10 m²) four-panel time series at three sites: Q_solar(t), Q_cond(t), COP(t), and the bulk-average drying curve X_db(t).]

Panel (a) of Figure 5.3b shows the solar thermal delivery: a diurnal bell-curve at every site, with peak Q_solar of 5.5 kW (BTN), 4.5 kW (KTM), 4.7 kW (TPJ) around solar noon and zero at night. Panel (b) shows the matching condenser duty: when Q_solar is high, Q_cond drops to near zero :  the controller dispatches the cheaper energy source. When Q_solar is zero (night, dawn, dusk), Q_cond rises to its full ambient-only value, identical to the Config A trace at the same site. Panel (c) confirms that COP is unchanged from A: the heat-pump cycle operates on the same ambient evaporator stream, so T_evap and the Carnot ratio are inherited. Panel (d) shows the drying curves are nearly identical to A (within 4 % on t_dry) because T_to_chamber is held at 45 °C throughout: solar reduces the *cost* of heating but not the *quality* of the supply air.

This is the textbook "solar offsets HP duty" topology. The SEC reduction equals the solar share of the total heating energy (Q_solar / (Q_solar + Q_cond) ≈ 0.49, 0.32, 0.40 at BTN, KTM, TPJ), modulated by the COP. The reason BTN benefits most is that its higher GHI (276 vs 208 vs 220 W m⁻² mean over the drying window) lets the collector deliver more energy per hour while the dryer is running.

### 5.3.3 Config C2: solar boosts COP via the evaporator side

[Figure 5.3d: T_evap(t) and COP(t) for Config A (dotted) vs Config C2 (solid) at three sites.]

In C2 at r = 0, the air-path-verified topology (see [air_paths_verified.md]) routes ambient air to the condenser and the solar-collector output to the evaporator. The cycle now draws heat from a stream that is 13–18 K warmer than ambient (panel a of Figure 5.3d, solid vs dotted at each site). The refrigerant T_evap settles at the new source temperature minus the 10-K approach: 22.1 °C (BTN), 11.1 (KTM), 16.2 (TPJ), each 13–14 K above the A baseline. The Carnot lift T_cond − T_evap drops by the same amount, so COP rises in inverse proportion.

The SEC reductions (-29 % BTN, -21 % KTM, -25 % TPJ) are smaller than B's (-46 %, -31 %, -38 %) at the same Q_solar because the COP boost is multiplicative on Q_cond, not substitutive. C2 still pays the full ambient-to-45 °C lift on the condenser side; it just runs the compressor at a better operating point. At BTN, C2 saves W_comp from 10.4 kWh to 7.2 kWh (-31 %), of which roughly 3.2 kWh is the COP-boost contribution and the remainder is fan-share rounding. At sites with lower ambient T (KTM, TPJ), the absolute COP gain is larger but Q_cond stays large, so the percentage saving is moderated.

C2 is *less* SEC-efficient than B at all three sites, but it has one practical advantage hidden in Table 5.3.1: T_evap stays well above the frost floor (-5 °C) at every site, including Kathmandu where Config A's T_evap dips into negative territory (-0.24 °C mean, min -1.5 °C). C2 is therefore the topology to reach for if frost robustness is a higher priority than peak SEC, especially in cold-shoulder seasons.

### 5.3.4 Config C1: the inline-evaporator penalty

C1 routes the collector-heated air through the evaporator *before* the condenser. At r = 0 the chamber receives ambient air that has been warmed by the collector, cooled and dehumidified by the evaporator, then re-heated by the condenser. The dehumidification step is the trap: at r = 0 the ambient air entering the evaporator is not loaded with chamber-released water, so the evaporator's only function is to extract a small amount of moisture from a clean stream that already had a usable VPD. The exit air is colder than the inlet (by typically 8–15 K), which the condenser must claw back. The net effect is a higher cumulative Q_cond (Table 5.3.1: 70.1 / 54.8 / 67.6 kWh, all *higher* than A's 45.4 / 49.9 / 42.5) and a much longer drying time.

At BTN (29.3 h) and KTM (33.0 h) the loop still reaches T_to_chamber = 45 °C for ~30 % and ~20 % of the run respectively (Figure 5.3a) so X_target is eventually reached. At Taplejung the picture is different.

[Figure 5.3c: C1 at Taplejung over the full 53.4-h drying window. Top panel: T_amb, T_after_solar, T_after_evap, T_to_chamber, vs the 45 °C set-point. Bottom panel: refrigerant T_evap with the -5 °C frost floor; shaded red bands show steps where the frost-protection flag was raised; GHI is overlaid (scaled / 100) so day/night cycles are visible.]

The C1-TPJ pathology is fully visible in Figure 5.3c:

- **T_to_chamber sits below 43 °C for 42.4 h out of 53.4 h (79 % of the drying window).** The supply air never reaches the set-point; the chamber is being "kept warm" rather than actively dried.
- **The 24 °C deficit between T_to_chamber and the 45 °C set-point** (Table 5.3.1 column: mean T_to_chamber_deficit_C is 24.08) is driven by the refrigerant cycle clipping at its frost floor. T_evap dips to -3.77 °C during cold nights, the flag_frost_risk register fires in 1230 of 3205 steps (38 %), and the controller throttles Q_cond to keep T_evap above -5 °C.
- **Day vs night split.** During solar daytime (G > 50 W m⁻², 1279 steps): T_amb = 12.9 °C, T_evap = 4.8 °C, T_to_chamber = 35.3 °C :  the cycle works but is sub-optimal. During night (G ≤ 5 W m⁻², 1734 steps): T_amb = 9.0 °C, T_evap = 0.9 °C, T_to_chamber = 11.2 °C :  the chamber is essentially cold-air-soaked.
- **Kinetic consequence.** M1's α_RH = 1.97 means the drying rate is hyper-sensitive to chamber RH. A T_to_chamber of 11 °C combined with whatever supply ω the evaporator allows pushes the chamber RH close to saturation; the M1 rate constant collapses by an order of magnitude, and the bulk moisture barely moves. The 53.4-h drying time is the integral of those near-stalled nights between productive daytime windows.

The same mechanism is present at Biratnagar and Kathmandu but at lower severity because (i) ambient temperatures stay further above the frost floor (BTN never triggers the flag; KTM does for 45 % of steps but the daytime windows are longer per cycle), and (ii) BTN-KTM nights are warmer in absolute terms. The Taplejung night ambient hovers around 5–10 °C, which sits exactly at the boundary where the inline evaporator drops T_evap into the protection band.

This is also why the M1-vs-M2 bracket on C1 at Taplejung is the widest in Table 5.1 (M1: 0.925, M2: 0.626, a 32 % gap). M2 has α_RH = 1.59 (less sensitive to chamber RH than M1's 1.97), so the long cold nights cost M2 less in kinetic time. The M1 number is the conservative one, and Table 5.1 ranks topologies by M1; on M2 the C1-TPJ penalty is half what M1 reports. C1-TPJ is therefore flagged as the entry in §5 where the M1-vs-M2 disagreement is large enough to matter for design decisions. The headline statement in §5.6 will report C1 as "dominated at all sites but with the largest kinetic-model uncertainty" rather than as a clean ranking.

### 5.3.5 Synthesis for §5.3

For an r = 0 single-pass topology with a 10 m² collector:

1. **Putting the collector in series with the condenser (B) is the dominant solar strategy.** SEC drops by 31–46 % at every site, t_dry is unchanged, and the mechanism is a direct substitution of free solar enthalpy for compressor-driven enthalpy.
2. **Putting the collector on the evaporator side (C2) is a second-best lever that buys frost-tolerance.** SEC drops by 21–29 %, less than B, but T_evap stays comfortably above the frost floor at every site.
3. **Putting the collector and evaporator in series on the supply path (C1) is the *only* solar topology that loses to the bare HP baseline** (at BTN and TPJ). The inline evaporator dehumidifies air that did not need dehumidifying and drags T_evap toward the frost floor, especially at cold-night-prone sites. The mechanism is real, reproducible, and clean in the simulation; it is also a textbook example of why "more components ≠ better topology" in this design space.

§5.4 next: passive heat recovery via the HRX (D1, D2, D3), which is the second free-energy lever and the partner that combines with B in the §5.5 Config E family to produce the headline SEC numbers in Table 5.1.

## 5.4 Passive heat recovery: the HRX family (D1, D2, D3)

The collector adds free enthalpy from the *outside* of the dryer; the HRX adds free enthalpy from the *inside*, by extracting heat from the chamber exhaust before it leaves. Configs D1, D2, D3 use the same air-to-air HRX (ε_HRX = 0.70, §3.3) but route the four legs (ambient-cold, ambient-hot, exhaust-hot, exhaust-cold) in three different ways. All three D variants are run at r = 0 so the HRX is the only added component versus the A baseline. Numbers are drawn from `outputs/config_D{1,2,3}/{site}/hrx_eps0.70.csv` (VPD-bypass disabled) and `…/hrx_eps0.70_vpd0.05.csv` (VPD-bypass at 0.05 kPa threshold). The VPD-on column previews §5.4b; the headline ranking in §5.1 is the VPD-on column for D1/D2 and the (irrelevant) VPD-off column for D3.

### 5.4.1 Headline comparison: HRX without bypass vs HRX with bypass

[Figure 5.4a: SEC at three sites for A r = 0, D1, D1 + VPD, D2, D2 + VPD, D3.]

| Quantity | A r=0 | D1 | D1 + VPD | D2 | D2 + VPD | D3 |
|---|---|---|---|---|---|---|
| **Biratnagar :  SEC** | 0.555 | 0.297 (-46 %) | **0.241 (-57 %)** | 0.285 (-49 %) | **0.241 (-57 %)** | 0.474 (-15 %) |
| t_dry [h] | 14.7 | 14.7 | 16.2 | 14.7 | 16.2 | 21.1 |
| W_comp + W_fan [kWh] | 10.72 | 5.74 | 4.64 | 5.50 | 4.66 | 9.14 |
| Q_cond cum. [kWh] | 45.4 | 22.8 | 17.6 | 22.8 | 17.6 | 52.9 |
| Q_HRX cum. [kWh] | 0 | 22.6 | 10.5 | 22.6 | 10.5 | 39.2 |
| T_evap mean [°C] | 8.77 | 8.77 | n/a | **13.33** | n/a | **23.05** |
| COP (compressor-on mean) | 4.42 | 4.42 | n/a | **4.99** | n/a | **6.67** |
| ω_to_chamber mean [g kg⁻¹] | 8.54 | 8.54 | 10.92 | 8.54 | 10.92 | **19.24** |
| HRX_condensation flags | 0 | 154 | 0 (bypass disabled) | 154 | 0 | 1266 |
| **Kathmandu :  SEC** | 0.730 | 0.369 (-49 %) | **0.292 (-60 %)** | 0.357 (-51 %) | **0.293 (-60 %)** | 0.488 (-33 %) |
| t_dry [h] | 14.1 | 14.1 | 15.4 | 14.1 | 15.4 | 17.8 |
| W_comp + W_fan [kWh] | 14.16 | 7.15 | 5.64 | 6.92 | 5.66 | 9.41 |
| Q_cond cum. [kWh] | 49.9 | 24.1 | 18.5 | 24.1 | 18.5 | 49.4 |
| Q_HRX cum. [kWh] | 0 | 25.8 | 12.6 | 25.8 | 12.6 | 35.8 |
| T_evap mean [°C] | -0.24 | -0.24 | n/a | **3.71** | n/a | **19.19** |
| COP (compressor-on mean) | 3.62 | 3.62 | n/a | **3.95** | n/a | **5.92** |
| **Taplejung :  SEC** | 0.578 | 0.314 (-46 %) | **0.252 (-56 %)** | 0.302 (-48 %) | **0.254 (-56 %)** | 0.450 (-22 %) |
| t_dry [h] | 14.25 | 14.25 | 15.57 | 14.25 | 15.57 | 19.5 |
| W_comp + W_fan [kWh] | 11.19 | 6.08 | 4.87 | 5.85 | 4.90 | 8.68 |
| Q_cond cum. [kWh] | 42.5 | 21.9 | 16.9 | 21.9 | 16.9 | 46.5 |
| Q_HRX cum. [kWh] | 0 | 20.6 | 9.1 | 20.6 | 9.1 | 32.8 |
| T_evap mean [°C] | 3.57 | 3.57 | n/a | **8.25** | n/a | **20.49** |
| COP (compressor-on mean) | 3.92 | 3.92 | n/a | **4.38** | n/a | **6.16** |

_Table 5.4.1. HRX variants D1, D2, D3 at three sites versus the A baseline, ε_HRX = 0.70, r = 0. The "D1 + VPD" and "D2 + VPD" columns use the cond-penalty exhaust bypass at threshold 0.05 (see §5.4b). D3's VPD-on file is identical to its VPD-off file because the bypass cannot fire when exhaust is already routed to the heating side, so only one column is reported. Δ-SEC in parentheses is relative to A at the same site._

Reading the table top-to-bottom for the headline mechanisms:

- **D1 (HRX only, ambient-fed evaporator)** lowers SEC by 46–49 % vs A simply by recovering exhaust enthalpy on the supply-side ambient leg of the HRX. Q_HRX is 20.6–25.8 kWh per batch, almost exactly cancelling the same magnitude of Q_cond reduction (45.4 → 22.8 BTN, 49.9 → 24.1 KTM, 42.5 → 21.9 TPJ). T_evap, COP, and ω_to_chamber are identical to A's because the evaporator still sees ambient air and the cold leg of the HRX is the ambient supply, not the chamber supply.
- **D2 (HRX + exhaust-supplied evaporator)** adds a second lever on top of D1: the cold (exhaust-side) leg of the HRX feeds into the evaporator inlet rather than being expelled. The evaporator now sees a stream that is 4–5 K warmer than ambient (Figure 5.4b, left panel) and the cycle's Carnot lift drops. COP rises from 4.42 to 4.99 (BTN), 3.62 to 3.95 (KTM), 3.92 to 4.38 (TPJ). The SEC improvement over D1 is small (1–4 %) because D1 already captured most of the available exhaust enthalpy on the supply side; D2 is squeezing a second pass out of the same exhaust stream.
- **D3 (HRX swapped)** is the inversion test: exhaust is routed to the *hot* side of the HRX, so the chamber receives exhaust air directly through the condenser. ω_to_chamber jumps from 8.5 g kg⁻¹ (A) to 19.2 g kg⁻¹ (D3-BTN), a 2.3 × increase. The chamber's drying potential collapses: t_dry stretches from 14.7 h to 21.1 h at BTN, 17.8 h at KTM, 19.5 h at TPJ. T_evap also rises to ~20 °C and COP looks excellent (6.7 BTN), but those gains are illusory because they come at the price of much longer drying time. Q_HRX is enormous (32.8–39.2 kWh) yet wasted: the recovered heat goes back into the chamber as humidity, not as drying capacity. D3 is reported as the worst HRX variant precisely because it shows how easy it is to wire the same component the wrong way round.

### 5.4.2 D1 vs D2: where the second lever helps

Figure 5.4b at Biratnagar shows D2 at work. The left panel plots refrigerant T_evap for A, D1, and D2 over the drying window; A and D1 trace each other almost exactly (both sit at the ambient-minus-10-K curve), while D2 sits 4–5 K higher because the evaporator now sees the exhaust-side-cooled HRX outlet rather than ambient. The right panel plots COP: A and D1 overlay; D2 sits ~13 % higher (4.99 vs 4.42).

The "second lever" is most useful at sites where T_evap was sitting at or below the frost floor in A: at Kathmandu the A-baseline T_evap of -0.24 °C lifts to 3.71 °C in D2, comfortably above the -5 °C floor. Frost-flag activity (not shown in Table 5.4.1 to keep the table compact) drops from 0 / 4 / 0 steps in A (BTN/KTM/TPJ) to 0 / 0 / 0 in D2 across all three sites. D2 therefore *fixes* a hidden frost-margin issue that A had at Kathmandu, in addition to delivering its small SEC gain.

The trade-off D2 imposes is a small increase in fan power. The exhaust-side HRX leg has more pressure drop than the open ambient draw in D1, so W_fan rises from 0.49 kWh (D1-BTN) to 0.70 kWh (D2-BTN). At the headline level this is absorbed into the W_comp gain, but it is the reason D2 looks identical to D1 once VPD-bypass is added (the bypass dumps the exhaust leg through most of the run, so the D2 evaporator-side gain is annulled).

### 5.4.3 D3: an HRX wired the wrong way round

[Figure 5.4c: ω_to_chamber over the drying window at the three sites for A, D1, D3.]

Figure 5.4c plots the supply-air absolute humidity ω_to_chamber at the three sites. The A and D1 traces are essentially the same: both supply ω equals ambient ω, around 7–9 g kg⁻¹. The D3 trace is dramatically higher: 19.2 g kg⁻¹ at Biratnagar, 15.1 at Kathmandu, 18.9 at Taplejung. This is the smoking gun.

The mechanism is that D3's hot-side feed to the HRX is the chamber exhaust, which is by construction loaded with the water the chamber just released. The HRX cools this stream against the cold-side ambient, condensing some of its moisture (HRX_condensation flag fires in 1067–1266 of the steps in D3 vs. 149–279 in D1/D2, Table 5.4.1), but the warm-side outlet, which is now what the condenser draws and what the chamber sees, still carries far more moisture than the ambient air that A and D1 are pulling from. The chamber's vapour-pressure deficit therefore collapses.

Quantitatively, with M1 kinetics (Eq. 3.16, α_RH = 1.97), the drying-rate constant k_eff drops as (1 - RH_chamber)^1.97. Substituting the table numbers (RH_chamber mean of 48.3 / 41.3 / 45.3 % for D3 BTN/KTM/TPJ vs 33.6 / 32.2 / 31.4 % for D1) gives a kinetic-rate ratio D3 / D1 of 0.74, 0.83, 0.76 at the three sites. The actual t_dry ratios from the table are 21.1 / 14.7 = 1.44 (BTN), 17.8 / 14.1 = 1.26 (KTM), 19.5 / 14.25 = 1.37 (TPJ); the reciprocal of the kinetic ratios (1.35, 1.20, 1.32) matches within 6 %. The drying-time penalty is therefore not a numerical artefact: it is exactly what M1 predicts when the chamber supply is run at twice the ambient absolute humidity.

D3 is interesting as a teaching example for the §5.6 synthesis: it has the *largest* Q_HRX of any topology in §5 (39 kWh BTN, 36 KTM, 33 TPJ :  more than D1/D2 by ~ 15 kWh), yet delivers the *worst* SEC in the D family. Heat-recovery effectiveness is not the right figure of merit; the right figure of merit is the SEC, and SEC includes the cost of the longer drying time that humid supply air imposes.

### 5.4.4 Synthesis for §5.4

1. **D1 is the simplest passive heat-recovery topology and already cuts SEC nearly in half** at every site (-46 / -49 / -46 %). The mechanism is a direct Q_HRX → ΔQ_cond substitution on the supply side, with no change to t_dry or to COP.
2. **D2 layers a small COP boost on top of D1** by routing the cold-side HRX exit through the evaporator. The headline SEC gain over D1 is 1–4 %, but the hidden value is frost-margin: D2 keeps the refrigerant cycle out of the -5 °C clip band at Kathmandu, which D1 sits right next to.
3. **D3 is a deliberate misdirection of the same HRX**, exposing the fact that "recovering more heat" is a trap if the recovered stream carries the water you are trying to remove. D3 has the largest Q_HRX in the §5 study (39 kWh BTN) and the worst SEC in the D family (0.474 BTN), a 4-pt lesson against optimising for HRX duty alone.
4. **VPD-bypass turns D1 and D2 into equally good topologies** at SEC 0.241–0.293 across the three sites. The bypass mechanism is the §5.4b headline lever and is described in detail there; for the present section it is enough to note that D1 + VPD and D2 + VPD converge to the same SEC because the bypass dumps the exhaust most of the time and erases the D2-specific evaporator-side gain.

The HRX family closes the gap to the headline SEC range (0.10–0.15) within a factor of 2. The remaining factor is closed in §5.5 by combining the HRX with the solar collector of §5.3 (Configs E1, E2, E3); §5.4b first formalises the VPD-bypass control lever, which applies independently to every recirculating-exhaust topology and is the reason the D and E configurations beat the open-loop B numbers despite having the same first-law structure.


---

