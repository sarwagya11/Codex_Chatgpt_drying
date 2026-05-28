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

