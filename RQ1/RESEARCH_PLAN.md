# RESEARCH PLAN: Literature Review on Heat Pump Dryer Modeling and Recirculation Ratio Effects

**Date:** 2026-03-23
**Author:** Wasti (Masters Thesis Research)
**Status:** Comprehensive Literature Review
**Relevance:** Directly supports RQ1 -- SAHPD system simulation validation and optimization

---

## 1. Problem Statement

This research plan addresses two interrelated questions critical to our SAHPD simulation:

1. **How do other researchers model heat pumps in drying applications?** We need to benchmark our CoolProp-based, first-law-enforced vapor compression cycle model against the state of the art to identify what we are doing correctly, what we might be missing, and what improvements to consider.

2. **What does the literature say about the effect of recirculation ratio on HP dryer performance?** We observe a "valley of death" at intermediate recirculation ratios (r = 0.3--0.7) in cold climates (Kathmandu, T_amb ~ 8.8 C), where the system cannot reach T_set = 45 C because the mixed air temperature is too close to the evaporator coil temperature, yielding insufficient Q_evap. We need to understand whether this phenomenon is reported in the literature and how others address it.

### System Under Investigation

- R134a refrigerant, fixed T_evap = 5 C (modulated to -5 C when T_mix approaches T_coil)
- First law enforced: Q_cond = Q_evap + W_comp x eta_mech
- Config A: Closed-loop HPCD with tunable recirculation ratio r in [0, 1]
- Problem manifests at r = 0.3--0.7: T_mix ~ 10--15 C, T_coil = 8 C, DeltaT ~ 2--7 K
- At r >= 0.9: system works well (SEC ~ 0.67 kWh/kg)
- At r = 0: open-loop, SEC ~ 0.72 kWh/kg

---

## 2. TOPIC 1: How Heat Pumps Are Modeled in Drying Applications

### 2.1 Vapor Compression Cycle Modeling Approaches

The literature reveals three tiers of heat pump modeling sophistication:

**Tier 1 -- Fixed or Carnot-Based COP (Simplest)**

Many early and some recent studies use a fixed COP or a Carnot-fraction approach:

- COP = eta_Carnot x T_cond / (T_cond - T_evap)
- Typical eta_Carnot = 0.4--0.6 for practical systems
- This approach decouples the refrigerant cycle from the air-side calculations entirely
- Used extensively in TRNSYS-based simulations where the heat pump is treated as a "black box" component (Type941)

*Reference:* Braun and Bansal (2022), "Carnot Analysis of Heat Pump Drying: Ideal Efficiency and Dry Time," ORNL report. They showed that the traditional Carnot efficiency limit does not apply directly to dryers because both the hot and cold reservoir temperatures are floating -- neither is fixed by ambient conditions. They defined new efficiency and dry time limits for ideal HPDs for both closed-cycle (unvented) and open-cycle (vented) configurations. ([OSTI Report](https://www.osti.gov/servlets/purl/1885306))

**Tier 2 -- Lumped Thermodynamic Cycle (What We Do)**

Our approach falls in this category: we solve the full vapor compression cycle using CoolProp for R134a properties at discrete state points (evaporator inlet/outlet, compressor outlet, condenser outlet, expansion valve outlet). This is similar to:

- Sarkar, Bhattacharyya, and Ram Gopal (2006), "Transcritical CO2 Heat Pump Dryer: Part 1. Mathematical Model and Simulation," *Drying Technology*, 24(12). They developed a mathematical model accounting for detailed heat and mass transfer and pressure drop phenomena in each component, with heat exchangers divided into infinitesimal segments. They used this to study COP, moisture extraction rate, and SMER variation with operating parameters. ([Taylor & Francis](https://www.tandfonline.com/doi/abs/10.1080/07373930601030903))

- Goncalves et al. (2023), "A Python-based code for modeling the thermodynamics of the vapor compression cycle applied to residential heat pumps." They developed a Python + CoolProp model for vapor compression cycles with features including refrigerant selection, heat exchanger sizing, and design parameter specification. ([ResearchGate](https://www.researchgate.net/publication/374861550_A_Python-based_code_for_modeling_the_thermodynamics_of_the_vapor_compression_cycle_applied_to_residential_heat_pumps))

- Pal and Khan (2008), "Design of Heat Pump Clothes Dryer." Used thermodynamic cycle analysis with REFPROP for refrigerant properties. ([ResearchGate](https://www.researchgate.net/publication/280446701_The_Design_of_Heat_Pump_Clothes_Dryer))

**Tier 3 -- Segment-by-Segment Heat Exchanger Models (Most Detailed)**

The most sophisticated models divide heat exchangers into many small segments:

- ORNL Heat Pump Clothes Dryer Model (Jackson et al., Purdue): A physics-based, quasi-steady-state model with segment-to-segment fin-and-tube condenser modeling using epsilon-NTU within each segment. Used REFPROP 9.1 for refrigerant properties with optional lookup tables for speed. The model was calibrated against prototype experimental data. ([Purdue/ORNL](https://web.ornl.gov/~jacksonwl/hpdm/PurdueHPCD_v1.pdf))

- Recent R290 closed-cycle simulation (2025) used a reverse enthalpy marching mechanism coupled with particle swarm optimization (PSO) for quasi-steady-state solution of the coupled air-refrigerant system. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1359431125022033))

**Assessment of Our Approach:** Our Tier 2 model is appropriate for system-level analysis. We use CoolProp (equivalent to REFPROP for our purposes) and solve the full thermodynamic cycle. We do NOT use a fixed COP. However, we use simple energy-balance heat exchangers rather than segment-by-segment NTU-effectiveness models. This is a reasonable simplification for parametric studies comparing configurations, though it may underpredict transient effects.

### 2.2 Evaporator Modeling

The literature shows three main approaches for evaporator modeling in HP dryers:

**a) NTU-Effectiveness Method (epsilon-NTU)**

- Used by ORNL HPCD model: segment-to-segment approach with epsilon-NTU within each segment
- Perera and Rahman (1997) provided calculation steps for evaporator sizing using epsilon-NTU
- Preferred when detailed heat exchanger geometry is known (fin pitch, tube diameter, number of rows)

*Reference:* Pal and Khan (2008), "Calculation Steps for the Design of Different Components of Heat Pump Dryers Under Constant Drying Rate Condition." The algorithm uses epsilon-NTU for finned heat exchangers to determine air-side and refrigerant-side heat transfer coefficients. ([ResearchGate](https://www.researchgate.net/publication/263346671_Calculation_Steps_for_the_Design_of_Different_Components_of_Heat_Pump_Dryers_Under_Constant_Drying_Rate_Condition))

**b) Contact Factor / Bypass Factor Approach**

- Chou and Chua (1994, 2001, 2002) used a "contact factor" to characterize evaporator performance
- The bypass factor (BF) = 1 - contact factor represents the fraction of air that passes through the coil without being cooled to the coil surface temperature
- Simpler than epsilon-NTU but captures the essential physics of partial dehumidification

*Reference:* Chou S.K. and Chua K.J. (1994), "Performance of a Heat-Pump Assisted Dryer," *International Journal of Energy Research*, 18(6). Used psychrometric process modeling with contact factor. ([Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1002/er.4440180605))

*Reference:* Chua K.J., Chou S.K., Ho J.C., and Hawlader M.N.A. (2002), "Heat pump drying: Recent developments and future trends," *Drying Technology*. Comprehensive review of psychrometric modeling approaches. ([ResearchGate](https://www.researchgate.net/publication/238135948_Heat_pump_drying_Recent_developments_and_future_trends))

**c) Simple Energy Balance (What We Use)**

- Q_evap = m_dot_air x (h_in - h_out)
- We use an effectiveness parameter (epsilon) to determine T_after_evap
- Dehumidification occurs when T_after_evap < T_dew_point of entering air
- This is equivalent to a contact factor approach with the contact factor = epsilon

**Assessment of Our Approach:** Our effectiveness-based approach is equivalent to the contact factor method used by Chou, Chua, and Hawlader. It is simpler than segment-by-segment NTU but captures the essential physics. The key difference is that we use a fixed effectiveness parameter rather than calculating it from heat exchanger geometry. This is acceptable for parametric studies but would need refinement for detailed equipment sizing.

### 2.3 Condenser Modeling

Similar approaches are used for condenser modeling as for the evaporator:

- ORNL model: segment-by-segment with de-superheating, condensing, and subcooling zones treated separately
- Most food drying studies: simple energy balance Q_cond = m_dot_air x c_p x (T_out - T_in)
- Some studies model the condenser as a constant-temperature heat source

**Assessment:** Our simple energy balance approach for the condenser is consistent with the majority of food-drying HP studies. The ORNL segment-by-segment approach is more appropriate for equipment design but not necessary for our system-level comparison of configurations.

### 2.4 First Law Enforcement

**Critical finding:** Most studies enforce the first law implicitly through their cycle calculation (computing each state point around the cycle), but few explicitly state that they verify Q_cond = Q_evap + W_comp.

- Braun and Bansal (2022) explicitly define Q_h = Q_c + W as the fundamental energy balance
- The ORNL HPCD model enforces it through the segment-by-segment calculation, where refrigerant-side and air-side energy balances are solved simultaneously
- Sarkar et al. (2006) enforce it through their detailed cycle model

**Our approach is sound:** We explicitly enforce Q_cond = Q_evap + W_comp x eta_mech and have verified it to 0.000000% error. This is actually MORE rigorous than many published studies that assume it holds without explicit verification. The consequence -- that T_to_chamber may float below T_set when the HP is first-law limited -- is a physically correct result that many models avoid by simply assuming the HP can always reach T_set.

### 2.5 Refrigerants Used in HP Dryer Simulations

Based on the literature survey:

| Refrigerant | Usage Frequency | Key Properties | References |
|---|---|---|---|
| R134a | Most common | GWP=1430, T_crit=101 C, well-characterized | Majority of studies |
| R290 (Propane) | Rising rapidly | GWP=0, T_crit=97 C, flammable, charge <150g | 2025 R290 optimization study |
| R410A | Common in HVAC | GWP=2088, higher pressures | Used in some SAHPD studies |
| CO2 (R744) | Niche/research | GWP=1, transcritical cycle, very high pressure | Sarkar et al. (2006) |
| R407C | Older systems | GWP=1774, zeotropic mixture | Some older studies |
| R450A | Drop-in for R134a | GWP=605, lower environmental impact | Evaluating as R134a replacement |
| Zeotropic mixtures | Emerging | R744/R290/R32 ternary mixtures | 2024 experimental study |

*Key reference:* R290 vs R134a comparison showed R290 achieves COP of 4.03 vs 3.80 for R134a (6% improvement), with SMER almost identical at 1.70 vs 1.69 kg/kWh. R290 charge can be reduced to 50% of R134a charge. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S135943112502201X))

*CO2 vs R134a:* Transcritical CO2 system achieved 15% greater SMER and 13.5% reduction in drying time compared to R134a. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0140700719302269))

**Assessment:** Our choice of R134a is well-supported by the literature as the most widely used and best-characterized refrigerant for HP dryer simulations. For future work, R290 would be the natural transition given environmental regulations (R134a phase-down).

### 2.6 Air-Side / Refrigerant-Side Coupling

The literature shows two main approaches:

**a) Sequential/Decoupled (What We Do)**

- Calculate air-side conditions first (mixing, evaporator air outlet)
- Use air-side Q_evap to determine refrigerant-side conditions
- Calculate compressor work from refrigerant state points
- Enforce Q_cond = Q_evap + W_comp to find condenser air outlet
- Most common in food drying studies

**b) Iterative/Simultaneous**

- Solve air and refrigerant sides simultaneously using Newton-Raphson or similar
- Required when heat exchanger performance depends on both fluid states
- Used in the ORNL model and the recent R290 PSO-based model
- More accurate for transient analysis and detailed equipment sizing

*Reference:* The R290 closed-cycle study (2025) notes that "dryers and heat pumps are both complex thermodynamic systems, and systems integrating them are much more complex than each component separately." The process is described as "nonlinearly strong-coupling and large-delaying." ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1359431125022033))

**Assessment:** Our sequential approach is adequate for our quasi-steady-state, time-stepping simulation. It is the most common approach in the food drying HP literature. The iterative approach would be needed if we modeled heat exchanger geometry in detail.

### 2.7 Compressor Modeling: Variable vs Fixed Speed

The literature shows a clear trend toward variable-speed (inverter-driven) compressor modeling:

- **Fixed-speed models** (older studies): Compressor operates at full capacity or is off. Simple on/off control. This is what our model assumes implicitly (we size the HP for the required load at each timestep).

- **Variable-speed models** (recent studies): Compressor frequency is a control variable. Higher frequency = higher capacity but lower COP. This allows matching capacity to load, which is critical for efficient operation during the falling-rate drying period when the moisture extraction rate decreases.

*Reference:* Study on effects of compressor speed on a heat pump dryer system with auxiliary solar source (2024). Higher compressor frequency leads to higher moisture extraction but increases energy consumption. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0960148124007043))

*Reference:* Simultaneous control of drying temperature and superheat for a closed-loop heat pump dryer. Application of variable speed compressor and electronic expansion valve can control drying temperature and maintain suitable evaporating temperature. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1359431115010480))

**Assessment:** Our model implicitly assumes the compressor can be sized to match any load, which is equivalent to a perfectly modulating variable-speed compressor. This is a reasonable idealization for comparing configurations but overpredicts performance at very low or very high loads where real compressors have reduced efficiency. For practical implementation, we should note that the component feasibility flags we already track (flag_hp_at_capacity, flag_evap_oversized, flag_cond_oversized) partially address this.

### 2.8 Simulation Tools Used

| Tool | Usage | Strengths | References |
|---|---|---|---|
| EES | Very common | Built-in thermodynamic properties, implicit solver | Braun & Bansal (2022); many HP studies |
| TRNSYS | Common for solar-HP | Transient simulation, solar component library | SAHPD optimization studies |
| MATLAB | Common | Flexible, good for optimization | Various HP dryer studies |
| Python + CoolProp | Growing | Open-source, CoolProp = free REFPROP alternative | Goncalves et al. (2023); Our model |
| REFPROP (NIST) | Gold standard | Most accurate refrigerant properties | ORNL HPCD model |
| Modelica/Dymola | Emerging | Object-oriented, component-based | Some European studies |
| CFD (ANSYS/OpenFOAM) | Rare for system-level | Used for airflow in drying chamber | Complementary studies |

**Assessment:** Our Python + CoolProp approach is modern, open-source, and increasingly common. CoolProp accuracy is comparable to REFPROP for standard refrigerants like R134a. The main alternative we might consider is EES for its implicit equation solving capability.

---

## 3. TOPIC 2: Effects of Recirculation Ratio in HP Dryers

### 3.1 Literature on Recirculation Ratio Effects

**a) General Finding: Higher Recirculation is More Energy-Efficient**

The literature consistently shows that higher recirculation ratios improve energy efficiency but can increase drying time:

*Reference:* Experimental investigation of the efficiency of heat pump drying system with full air recirculation. Found that closed-loop heat pump-assisted drying reduced energy demand by up to 84%, but drying time increased by up to 69% compared to open-loop drying. ([Academia.edu](https://www.academia.edu/43308636/EXPERIMENTAL_INVESTIGATION_OF_THE_EFFICIENCY_OF_HEAT_PUMP_DRYING_SYSTEM_WITH_FULL_AIR_RECIRCULATION))

*Reference:* Effect of air recirculation and heat pump on mass transfer and energy parameters in drying of kiwifruit slices. By increasing recirculation air ratio (RAR) successively during drying, substantial energy savings can be achieved with only marginal extension of drying duration. ([IDEAS/RePEc](https://ideas.repec.org/a/eee/energy/v170y2019icp149-158.html))

**b) Partial Recirculation is More Efficient Than Full Recirculation**

This aligns with our findings that r = 0.7--0.9 outperforms r = 1.0:

*Reference:* The partial air recirculation of the heat pump system was much more efficient than that of full air recirculation. This is because at r = 1.0, the humidity builds up in the closed loop, raising the equilibrium moisture content X_eq and reducing the drying driving force.

*Reference:* Comparative assessment of closed-loop heat pump dryer operating in three modes -- closed, open, and partially open cycles at T_dry = 40 C. The highest average COP of 2.50 was observed in the closed system. ([Akademi Baru](https://www.akademiabaru.com/doc/ARFMTSV66_N2_P136_144.pdf))

**c) Optimal Recirculation Ratio**

The literature generally finds optimal recirculation ratios in the range r = 0.6--0.9, but this is highly dependent on ambient conditions:

- In warm, humid climates: r ~ 0.7--0.9 is optimal (warm exhaust air provides good heat source)
- In cold, dry climates: r = 0 (open loop) or r > 0.9 may be better (cold ambient air at intermediate r creates the "valley of death" we observe)

### 3.2 The "Valley of Death" at Intermediate Recirculation Ratios

**This is our key finding -- and it appears to be under-reported in the literature.**

Our model shows that at r = 0.3--0.7 in cold climates (T_amb = 8.8 C):

- T_mix = r x T_exhaust + (1-r) x T_amb ~ 10--20 C (depending on how cold the exhaust is)
- T_coil = T_evap_sat + DT_approach = 5 + 3 = 8 C
- DeltaT = T_mix - T_coil ~ 2--12 K
- Q_evap ~ m_dot_air x c_p x epsilon x DeltaT -- very small
- Q_cond = Q_evap + W_comp -- insufficient to heat air to T_set
- Negative feedback loop: low Q_cond -> low T_chamber -> low T_exhaust -> low T_mix -> even lower Q_evap

**Literature support for this phenomenon:**

*Reference:* Performance Analysis of Heat Pump Dryer with Unit-Room in Cold Climate Regions (2019), *Energies*, 12(16), 3125. This study directly addresses our problem. They proposed a "unit-room" concept where ambient air is mixed with return air in a controlled ratio to avoid the direct influence of cold ambient air on evaporator performance. Key finding: "Drying in low ambient temperatures could decrease the drying temperature in the drying chamber and increase energy consumption with highly decreased energy efficiency." They found an optimal bypass factor (BF) under certain ambient temperatures corresponding to maximum SMER, and the COP of their system increased by up to 39.56% compared to closed-loop systems. ([MDPI](https://www.mdpi.com/1996-1073/12/16/3125))

*Reference:* Effects of Component Arrangement and Ambient and Drying Conditions on the Performance of Heat Pump Dryers. Found that the recirculation air ratio substantially affects system performance, while the evaporator bypass air ratio shows insignificant effect. The effect of ambient temperature on COP was slight only when the dryer operated in closed-loop mode (r ~ 1), but significant for partially open loops. ([ResearchGate](https://www.researchgate.net/publication/233099187_Effects_of_Component_Arrangement_and_Ambient_and_Drying_Conditions_on_the_Performance_of_Heat_Pump_Dryers))

*Reference:* Study on the performance of heat pump drying system under the synergistic effect of humidity enthalpy enhancement and solar heat storage under low temperature working conditions (2024). Addresses the specific challenge of HP dryer operation in cold, low-enthalpy conditions. Solar heat storage is proposed as a solution to bridge the performance gap. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1359431124002941))

### 3.3 Minimum Temperature Difference Across Evaporator

The literature identifies minimum approach temperatures for heat pump evaporators:

- Typical minimum pinch point DeltaT: 5--10 K for practical heat exchangers
- At DeltaT < 5 K, heat transfer rate drops dramatically and heat exchanger surface area becomes impractically large
- Our model modulates T_evap_sat down to -5 C when T_mix - T_coil < 5 K, which is physically correct behavior

**Our hard stop condition** (T_evap_sat >= T_cond_C_hp -> bypass to open-loop) is a thermodynamic constraint that is rarely discussed in the literature because most studies do not push the system to these extreme conditions.

### 3.4 Open-Loop vs Closed-Loop Comparison

The literature confirms our finding that both extremes (r = 0 and r ~ 1) perform well, while intermediate values can be problematic:

*Reference:* Carnot analysis (Braun & Bansal, 2022) found that "efficiency and dry time are generally more favorable for the vented system [open-loop], and the vented system performs similarly to unvented [closed-loop] as the ambient humidity approaches 100%." This is consistent with our finding that open-loop (r = 0) gives reasonable SEC (0.72 kWh/kg) while the optimum closed-loop (r >= 0.9) gives slightly better SEC (0.67 kWh/kg).

*Reference:* Closed-loop systems achieve SMER of 2.15--2.27 kg/kWh with COP of 5.2--5.8 in controlled conditions. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0360544221020673))

### 3.5 Solar Preheating as a Solution to the Cold-Climate Problem

The literature strongly supports using solar preheating to address cold-climate HP dryer performance:

*Reference:* Review of solar assisted heat pump technology for drying applications (2023), *Energy*, 283. Comprehensive review showing that SAHPD systems combine the advantages of solar drying (free energy) and heat pump drying (weather independence, dehumidification). R134a is the most widely used refrigerant. Integration of TES and SAHP can improve overall efficiency by up to 35% and reduce drying time by 20--40%. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0360544223026099))

*Reference:* Experimental study on effects of compressor speed on a heat pump dryer system with auxiliary solar source (2024). Direct evidence that solar preheating raises the evaporator source temperature, improving COP. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0960148124007043))

*Reference:* Solar-heat pump combined drying with phase change heat storage (2024). Multi-energy self-adaptive control strategy for combined solar-HP drying in low-temperature conditions. ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0960148124009352))

**This directly supports our Config B and C1/C2 approaches:** Solar preheating raises T_mix above the critical threshold, enabling effective evaporator operation even at intermediate recirculation ratios in cold climates.

### 3.6 Auxiliary/Supplementary Heating

The literature confirms the use of auxiliary electric heating to bridge performance gaps:

- Standard practice in HVAC heat pumps: auxiliary electric strip heaters activate when outdoor temperature drops below ~-1 C (30 F)
- In HP dryers, some designs include supplementary electric heaters for startup or cold-weather operation
- The COP penalty of auxiliary electric heating (COP = 1.0) means it should be minimized

**Implication for our model:** We could consider adding an auxiliary electric heater mode for intermediate r values in cold climates, but this would increase SEC. Solar preheating (our Config B/C) is a thermodynamically superior solution.

### 3.7 Reported SEC Values

| System | r Value | SEC (kWh/kg) | COP | Reference |
|---|---|---|---|---|
| Closed-loop HPD | ~1.0 | 0.5--0.7 | 3.5--4.5 | Multiple sources |
| Open-loop HPD | 0 | 0.8--1.2 | 2.5--3.5 | Multiple sources |
| SAHPD (solar + HP) | varies | 0.3--0.6 | 4.0--6.0 | Review papers |
| Conventional hot air | -- | 2.5--5.0 | ~1.0 | Baseline |
| **Our model (Config A, KTM)** | **0.0** | **0.717** | **~3.5** | **This work** |
| **Our model (Config A, KTM)** | **0.9** | **0.669** | **~4.0** | **This work** |
| **Our model (Config A, BTN)** | **0.0** | **0.543** | **~3.5** | **This work** |

**Assessment:** Our SEC values fall within the expected range reported in the literature. The improvement from r = 0 to r = 0.9 (about 7% in Kathmandu) is modest compared to some literature reports, likely because our first-law enforcement prevents overestimation of HP performance that occurs in models with implicit energy balance.

---

## 4. Synthesis: What Are We Doing Correctly?

### 4.1 Strengths of Our Approach

1. **First-law enforcement is rigorous and rare.** Most studies assume Q_cond = Q_evap + W_comp holds implicitly. We verify it explicitly to machine precision. This is a genuine contribution.

2. **CoolProp-based thermodynamic cycle** is state-of-the-art for open-source HP modeling. Our approach matches or exceeds the sophistication of most food-drying HP studies.

3. **Fixed T_evap with modulation** is realistic. Real AC/HP units operate at a target evaporating temperature and modulate when conditions demand it. This is more physically accurate than the dewpoint-driven approach we previously used.

4. **The "valley of death" observation** at intermediate r in cold climates is a genuine physical phenomenon that is under-reported in the literature. The unit-room study (MDPI, 2019) is one of few papers that directly addresses this.

5. **Component feasibility flags** represent practical engineering awareness that most simulation studies lack.

6. **Tunable recirculation ratio** as a continuous parameter (rather than just open/closed) is a more sophisticated treatment than most studies, which typically compare only fully open vs fully closed.

### 4.2 What We Might Be Missing or Doing Differently

1. **Bypass air ratio (BAR) as separate from recirculation ratio (r).** Some studies distinguish between the fraction of air that bypasses the evaporator (BAR) and the fraction recirculated from the chamber (r). In our model, all recirculated air passes through the evaporator. Introducing a BAR could improve performance at high r by allowing some warm air to bypass the evaporator and mix with the dehumidified stream. The literature shows that a maximal SMER and minimal total energy consumption exist at an optimal BAR.

2. **Dynamic recirculation ratio control.** The literature suggests increasing r progressively during drying (start with lower r when the product is very wet and increase r as drying progresses). We currently use a fixed r throughout the drying cycle.

3. **Variable-speed compressor effects.** Our model implicitly assumes perfect capacity matching. Real systems with fixed-speed compressors would cycle on/off, and variable-speed systems have efficiency maps that depend on speed. This could affect our predictions at low loads (late in the falling-rate period).

4. **Subcooling and superheat optimization.** Some advanced HP dryer models optimize the degree of subcooling at the condenser outlet and superheat at the evaporator outlet. Our model uses fixed subcooling/superheat values.

5. **Heat exchanger approach temperature as a function of flow rate.** Our effectiveness parameter is fixed. In reality, effectiveness depends on the NTU, which changes with air flow rate. At low flow rates (high r with partial bypassing), the effectiveness would increase.

6. **Thermal mass of the drying product.** Some studies account for the sensible heat required to warm the product from initial temperature to drying temperature, especially during the startup period. This is more important for dense products.

### 4.3 Modeling Improvements to Consider

**Priority 1 (High Impact, Moderate Effort):**
- Implement dynamic r(t) control: start at r = 0 or r = 1 (depending on climate) and adjust based on exhaust humidity
- Add evaporator bypass ratio as a separate control parameter

**Priority 2 (Medium Impact, Moderate Effort):**
- Implement a variable-speed compressor model with COP = f(speed, T_evap, T_cond)
- Add a startup/transient model for the first 30--60 minutes of drying

**Priority 3 (Lower Impact, Higher Effort):**
- Implement NTU-effectiveness heat exchanger models with flow-rate-dependent effectiveness
- Add subcooling/superheat optimization

### 4.4 What the Literature Says About Our Recirculation Problem

The literature confirms our observations:

1. **The phenomenon is real and physical.** Cold ambient air mixing with exhaust at intermediate r creates a mixed stream too close to the evaporator coil temperature for effective heat transfer.

2. **The solution is one of three approaches:**
   a. **Avoid intermediate r in cold climates** -- use r = 0 or r >= 0.9
   b. **Use solar preheating** to raise T_mix above the critical threshold (our Config B/C approach)
   c. **Use a unit-room concept** where the HP itself warms the air before it enters the system (the HPDU approach from the cold-climate study)

3. **Dynamic r control could help:** Start with r = 0 (open loop) until the exhaust reaches a sufficiently warm temperature, then progressively increase r. This avoids the cold-start problem.

4. **The COP is relatively insensitive to ambient temperature in fully closed systems** (r ~ 1) because the evaporator source is the warm exhaust air, not the cold ambient. This explains why r >= 0.9 works even in Kathmandu's cold conditions.

---

## 5. Recommendations for Implementation

### 5.1 For the Current Simulation (Config A)

The recirculation ratio control logic should incorporate temperature-based switching:

- If T_amb < 15 C and 0.1 < r < 0.85: the system is likely in the "valley of death"
- Physical solution: either reduce r to 0 (open loop) or increase r to >= 0.9
- This can be framed as a hysteresis band: if T_mix - T_coil < DeltaT_min (e.g., 7 K), switch to r = 0 or r = 1

### 5.2 For Solar-Assisted Configurations (Config B, C1, C2)

Solar preheating is the thermodynamically correct solution to the cold-climate intermediate-r problem:

- Q_solar raises T_after_solar above T_amb, increasing T_mix
- This increases DeltaT across the evaporator, enabling effective heat pump operation
- The required solar collector area can be estimated from: A_c = Q_needed / (F_R x (eta_opt x G - U_L x DeltaT))
- Where Q_needed = m_dot_air x c_p x (T_min_mix_target - T_mix_without_solar)

### 5.3 For Future Research Directions

1. **Investigate R290 as replacement for R134a** -- the literature shows comparable or better performance with zero GWP
2. **Consider transcritical CO2 cycle** for high-temperature drying applications (T_set > 60 C)
3. **Implement phase-change thermal energy storage (PCM)** to buffer solar intermittency
4. **Validate against experimental data** -- the literature emphasizes that simulation models must be calibrated against prototype measurements

---

## 6. Key References (Organized by Topic)

### Heat Pump Dryer Modeling
1. Braun, J.E. and Bansal, P.K. (2022). "Carnot Analysis of Heat Pump Drying: Ideal Efficiency and Dry Time." ORNL. [Link](https://www.osti.gov/servlets/purl/1885306)
2. Sarkar, J., Bhattacharyya, S., and Ram Gopal, M. (2006). "Transcritical CO2 Heat Pump Dryer: Part 1. Mathematical Model and Simulation." *Drying Technology*, 24(12). [Link](https://www.tandfonline.com/doi/abs/10.1080/07373930601030903)
3. Goncalves et al. (2023). "A Python-based code for modeling the thermodynamics of the vapor compression cycle applied to residential heat pumps." [Link](https://www.researchgate.net/publication/374861550)
4. ORNL Heat Pump Clothes Dryer Model. Jackson et al. [Link](https://web.ornl.gov/~jacksonwl/hpdm/PurdueHPCD_v1.pdf)
5. Minea, V. (2012). "Drying heat pumps -- Part I: System integration." *International Journal of Refrigeration*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0140700712003337)
6. Minea, V. (2012). "Drying heat pumps -- Part II: Agro-food, biological and wood products." *International Journal of Refrigeration*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0140700712003349)
7. Minea, V. (2015). "Overview of Heat Pump-Assisted Drying Systems -- Part I." *Drying Technology*, 33(5). [Link](https://www.tandfonline.com/doi/abs/10.1080/07373937.2014.952377)

### Evaporator/Condenser Modeling
8. Chou, S.K. and Chua, K.J. (1994). "Performance of a Heat-Pump Assisted Dryer." *Int. J. Energy Research*, 18(6). [Link](https://onlinelibrary.wiley.com/doi/abs/10.1002/er.4440180605)
9. Chua, K.J., Chou, S.K., Ho, J.C., and Hawlader, M.N.A. (2002). "Heat pump drying: Recent developments and future trends." *Drying Technology*. [Link](https://www.researchgate.net/publication/238135948)
10. Pal, U.S. and Khan, M.K. (2008). "Calculation Steps for the Design of Different Components of Heat Pump Dryers." [Link](https://www.researchgate.net/publication/263346671)

### Recirculation and Bypass Ratio
11. Performance Analysis of Heat Pump Dryer with Unit-Room in Cold Climate Regions (2019). *Energies*, 12(16), 3125. [Link](https://www.mdpi.com/1996-1073/12/16/3125)
12. Heat pump dryer bypass air ratio evaluation study (2022). *Applied Thermal Engineering*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S1359431122009310)
13. Heat pump assisted drying of agricultural produce -- an overview. *J. Food Engineering*. [Link](https://pmc.ncbi.nlm.nih.gov/articles/PMC3550864/)

### Refrigerant Comparison
14. R290 vs R134a optimization study (2025). *Applied Thermal Engineering*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S135943112502201X)
15. CO2 vs R134a comparative study (2019). *International Journal of Refrigeration*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0140700719302269)
16. R450A as drop-in replacement for R134a (2021). *International Journal of Refrigeration*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0140700721001195)

### Solar-Assisted Heat Pump Dryers
17. Review of solar assisted heat pump technology for drying applications (2023). *Energy*, 283. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0360544223026099)
18. Solar-heat pump combined drying with PCM storage (2024). *Renewable Energy*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0960148124009352)
19. Compressor speed effects on HP dryer with auxiliary solar source (2024). *Renewable Energy*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0960148124007043)
20. HP drying under low temperature with solar heat storage (2024). *Applied Thermal Engineering*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S1359431124002941)

### Exergy Analysis
21. Exergy analysis of convective HP dryer with membrane ERV (2025). *Entropy*, 27(2), 197. [Link](https://www.mdpi.com/1099-4300/27/2/197)
22. Second-law analysis to improve energy efficiency of HP dryers. Purdue. [Link](https://docs.lib.purdue.edu/cgi/viewcontent.cgi?article=2705&context=iracc)

### Nepal-Specific and Developing Country Applications
23. RM Agro Tech (Nepal). "Revolutionizing Food Drying in Nepal: The Power of Heat Pump Food Dryers." [Link](https://www.rmagrotech.com.np/blogs/revolutionizing-food-drying-in-nepal-the-power-of-heat-pump-food-dryers)
24. Review of solar assisted heat pump drying systems for agricultural and marine products. *Renewable and Sustainable Energy Reviews*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S1364032110001152)

### Open-Loop vs Closed-Loop Performance
25. Process simulation and analysis of a closed-loop heat pump clothes dryer. *Applied Thermal Engineering*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S1359431121009765)
26. Assessment of an energy efficient closed loop heat pump dryer. *Energy*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0360544221020673)
27. Comparative Assessment of Closed Loop Heat Pump Dryer. *ARFMTS*. [Link](https://www.akademiabaru.com/doc/ARFMTSV66_N2_P136_144.pdf)

### Variable Speed and Control
28. Simultaneous control of drying temperature and superheat for closed-loop HP dryer. *Applied Thermal Engineering*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S1359431115010480)
29. R290 closed-cycle HP tumble dryer simulation with PSO optimization (2025). *Applied Thermal Engineering*. [Link](https://www.sciencedirect.com/science/article/abs/pii/S1359431125022033)

---

## 7. Conclusions

### What we are doing well:
- First-law enforcement is rigorous and distinguishes our model
- CoolProp-based cycle analysis is state-of-the-art for system-level studies
- Fixed T_evap with modulation is realistic
- The recirculation ratio as a continuous parameter is more sophisticated than binary open/closed
- Our SEC values (0.54--0.72 kWh/kg) are within the expected literature range

### What we should highlight in the thesis:
- The "valley of death" at intermediate r in cold climates is a genuine, under-reported phenomenon
- First-law enforcement prevents the common error of overestimating HP performance
- Solar preheating (Config B/C) is the thermodynamically correct solution to cold-climate HP dryer limitations

### What we should consider adding:
- Dynamic r(t) control strategy
- Evaporator bypass ratio as an independent parameter
- Discussion of R290 as future refrigerant replacement
- Comparison of our SEC values against the literature benchmark table

---

*Document generated: 2026-03-23*
*Next update: After Config B/C simulation results are available*
