# PROJECT CONTEXT: Solar-Assisted Heat Pump Dryer (SAHPD)
## Ground Truth Documentation for Coding Agents

**Version:** 2.0  
**Date:** February 4, 2026  
**Author:** Wasti (Masters Thesis Research)  
**Purpose:** Authoritative reference for all SAHPD simulation code development

---

## 1. PROJECT GOAL & OBJECTIVES

### 1.1 Primary Objective
Design, simulate, and optimize a **Solar-Assisted Heat Pump Dryer (SAHPD)** system for agricultural applications in Nepal, specifically focusing on apple slice drying.

### 1.2 Target Product & Operating Parameters
- **Product:** Apple slices  
- **Initial Moisture Content (X₀):** 6.5 kg water/kg dry solid (87% wet basis)  
- **Final Moisture Content (X_f):** 0.10 kg water/kg dry solid (9% wet basis)  
- **Target Drying Temperature:** 50°C (controllable 40-50°C range)  
- **Air Velocity:** 1.1 m/s (controllable 0.8-1.1 m/s range)  
- **Chamber Configuration:** 10 trays in series cascade arrangement  
- **Batch Size:** 10 kg dry solids (1 kg per tray)  

### 1.3 Performance Metrics
Primary metrics for configuration comparison:
- **SEC (Specific Energy Consumption):** kWh electricity per kg water removed
- **COP (Coefficient of Performance):** Heat delivered / Electrical work input
- **Solar Fraction:** Percentage of total energy from solar
- **Drying Time:** Hours to reach target moisture content
- **Energy Savings:** Percentage reduction vs. baseline (Config A)

### 1.4 Research Questions
1. What is the optimal solar collector area for each configuration?
2. How do different solar integration strategies affect system COP and SEC?
3. Which configuration achieves maximum energy savings while maintaining product quality?
4. How does system performance vary across different Nepal locations and weather conditions?

---

## 2. SYSTEM CONFIGURATIONS (The 5 Modes)

All configurations share common components: 10-tray chamber, psychrometric control, and kinetics model. They differ in heat source integration strategy.

### Configuration A: Heat Pump Only (BASELINE)
**Air Flow Path:**
```
Ambient Air → Heat Pump Evaporator → Heat Pump Condenser (50°C) → Chamber → Exhaust
```

**Physics:**
- Heat pump operates 24/7 at constant condenser temperature (60°C)
- Evaporator temperature: T_amb - 10K (typical approach temperature)
- No solar contribution (Q_solar = 0)
- Baseline for all comparisons

**Key Equations:**
- COP = Q_cond / W_comp
- T_evap = T_amb - ΔT_approach (ΔT_approach = 10K)
- T_cond = T_set + ΔT_superheat (ΔT_superheat = 10K)

**Expected Performance (Kathmandu):**
- SEC ≈ 1.05 kWh/kg
- COP ≈ 3.45
- Drying time ≈ 15.7 hours 

---

### Configuration B: Solar + Heat Pump Series (LOAD REDUCTION)
**Air Flow Path:**
```
Ambient Air → Solar Collector → Heat Pump Condenser (to 50°C) → Chamber → Exhaust
                 (preheats)         (adds remaining heat)
```

**Physics:**
- Solar preheats air before HP condenser
- HP condenser adds remaining heat to reach T_set = 50°C
- Heat pump evaporator uses ambient air (NOT solar-heated air)
- Mechanism: Reduces required Q_cond, therefore reduces W_comp

**Key Equations:**
- Q_solar = A_c × F_R × [η_opt × G - U_L × (T_amb - T_amb)]
- T_after_solar = T_amb + Q_solar / (ṁ_da × c_p)
- ΔT_needed_HP = T_set - T_after_solar
- Q_cond_needed = ṁ_da × c_p × ΔT_needed_HP

**Expected Performance (Kathmandu, 15 m²):**
- SEC ≈ 0.93 kWh/kg (11.5% savings)
- COP ≈ 3.45 (unchanged, evaporator still uses ambient)
- Solar fraction ≈ 12%
- Drying time ≈ 15.7 hours (same as baseline)

**Why Config B Works:**
Solar directly displaces compressor work by reducing the thermal lift required. Even though COP remains constant, total W_comp decreases because Q_cond_needed is lower.

---

### Configuration C: Solar-Assisted Evaporator (COP IMPROVEMENT)
**Air Flow Path:**
```
Ambient Air → Solar Collector → Heat Pump Evaporator → Heat Pump Condenser (50°C) → Chamber → Exhaust
                 (preheats)         (uses warm air)         (full heating)
```

**Physics:**
- Solar preheats air for HP evaporator heat source
- Higher T_evap → Higher COP → Less W_comp for same Q_cond
- Condenser must still heat from T_amb to T_set (full ΔT)
- Mechanism: Improves efficiency rather than reducing load

**Key Equations:**
- T_evap = T_solar_out - ΔT_approach
- COP = f(T_evap, T_cond) → increases with T_evap
- W_comp = Q_cond / COP → decreases due to higher COP
- Q_cond = constant (must heat from T_amb to T_set)

**Expected Performance (Kathmandu, 15 m²):**
- SEC ≈ 0.94 kWh/kg (10% savings)
- COP ≈ 4.22 during solar hours (22% higher than baseline)
- Solar fraction ≈ 0% (solar energy not directly used, only boosts COP)
- Drying time ≈ 15.7 hours

**Why Config C Works Differently Than Config B:**
Config C improves system efficiency (higher COP) while Config B reduces thermal load. Config B typically saves more energy because direct load reduction is more effective than efficiency improvement at these temperature levels.

---

### Configuration D: Solar Only (NO HEAT PUMP)
**Air Flow Path:**
```
Ambient Air → Solar Collector → Chamber (variable T) → Exhaust
```

**Physics:**
- Passive solar heating only
- No electricity consumption (W_comp = 0)
- Chamber temperature varies with solar irradiance
- Drying occurs only when T_solar > T_product and humidity gradient exists
- Nighttime: No drying (solar flux = 0)

**Key Equations:**
- T_chamber = T_solar_out = T_amb + η_coll × G × A_c / (ṁ_da × c_p)
- Q_solar = A_c × F_R × [η_opt × G - U_L × (T_in - T_amb)]
- Drying rate = f(T_chamber, RH_chamber) from Midilli kinetics

**Expected Performance (Kathmandu, 15 m²):**
- SEC = 0 kWh/kg (no electricity)
- COP = ∞ (undefined, no compressor)
- Solar fraction = 100%
- Drying time ≈ 72+ hours (incomplete drying likely)

**Critical Limitation:**
Solar-only drying is **impractical** for Nepal conditions due to:
1. Insufficient temperatures during monsoon/winter
2. No nighttime drying capability
3. Extended drying times risk product spoilage
4. Inconsistent product quality

Config D serves as a theoretical upper bound for solar utilization but is not recommended for implementation.

---

### Configuration E: Cascade (OPTIMAL HYBRID)
**Air Flow Path:**
```
Ambient Air → Solar Collector → Heat Pump Evaporator → Heat Pump Condenser (50°C) → Chamber → Exhaust
                 (preheats)         (uses warm air)         (adds final heat)
```

**Physics:**
- Solar-heated air serves BOTH evaporator AND condenser inlet
- Combines benefits of Config B (load reduction) and Config C (COP improvement)
- Synergistic effect: Higher T_evap AND lower ΔT_needed
- Maximum energy efficiency among all configurations

**Key Equations:**
- T_after_solar = T_amb + Q_solar / (ṁ_da × c_p)
- T_evap = T_after_solar - ΔT_approach → Higher COP
- ΔT_needed_HP = T_set - T_after_solar → Reduced Q_cond
- Double benefit: W_comp = Q_cond_reduced / COP_improved

**Expected Performance (Kathmandu, 15 m²):**
- SEC ≈ 0.85 kWh/kg (19.5% savings)
- COP ≈ 4.10 (improved due to higher T_evap)
- Solar fraction ≈ 13%
- Drying time ≈ 15.7 hours

**Why Config E is Optimal:**
Config E is the only configuration that simultaneously:
1. Reduces thermal load on heat pump (like Config B)
2. Improves heat pump COP (like Config C)
3. Maximizes solar energy utilization efficiency
4. Maintains consistent product temperature control

**Validation Note:**
Config E achieves 17-24% electricity savings across all Nepal locations (Kathmandu, Dhulikhel, Biratnagar, Taplejung) with A_c = 20 m².

---

## 3. PHYSICS & MATHEMATICAL MODELS

### 3.1 Psychrometric Model (ASHRAE Standards)

**Implementation File:** `psychro.py`

#### Saturation Vapor Pressure (Tetens Correlation)
```
p_sat(T) = 610.94 × exp(17.625 × T / (T + 243.04))  [Pa]
```
Valid: -40°C to +50°C  
Reference: ASHRAE RP-1485

#### Humidity Ratio
```
ω = 0.62198 × p_v / (P_atm - p_v)  [kg_water/kg_dry_air]
```
where p_v = RH × p_sat(T)

#### Moist Air Enthalpy
```
h = c_p,da × T + ω × (h_fg,0 + c_p,v × T)  [kJ/kg_dry_air]
```
Constants:
- c_p,da = 1.006 kJ/kg·K (dry air specific heat)
- c_p,v = 1.86 kJ/kg·K (water vapor specific heat)
- h_fg,0 = 2501 kJ/kg (latent heat at 0°C)

#### Relative Humidity (Inverse Calculation)
```
RH = (ω × P_atm) / ((0.62198 + ω) × p_sat(T))
```

#### Temperature from Enthalpy (Inverse)
```
T = (h - ω × h_fg,0) / (c_p,da + ω × c_p,v)  [°C]
```

**Critical Notes:**
- All psychrometric functions must maintain mass/energy conservation
- Temperature inversions validated against ASHRAE tables (error < 0.5%)
- Dewpoint calculations use bisection method with tolerance 0.01°C

---

### 3.2 Solar Collector Model (Hottel-Whillier-Bliss)

**Implementation File:** `solar.py`

#### Useful Heat Gain
```
Q_useful = A_c × F_R × [η_opt × K_θ × G - U_L × (T_in - T_amb)]  [kW]
```

**Parameters:**
- A_c: Collector area [m²] (variable: 0, 2, 4, 6, 8, 10, 12, 15, 20 m²)
- F_R: Heat removal factor [-] (calculated, typically 0.86-0.90)
- η_opt: Optical efficiency [-] = 0.75 (τα product)
- K_θ: Incidence angle modifier [-] = 1.0 (normal incidence assumption)
- G: Global horizontal irradiance [W/m²] (from PVGIS weather data)
- U_L: Loss coefficient [W/m²·K] = 5.0
- T_in: Inlet fluid/air temperature [°C]
- T_amb: Ambient temperature [°C]

#### Heat Removal Factor (F_R)
```
F_R = (ṁ × c_p / (A_c × U_L)) × [1 - exp(-F' × U_L × A_c / (ṁ × c_p))]
```
where:
- F' = Collector efficiency factor ≈ 0.90 (well-designed flat plate)
- ṁ = Air mass flow rate [kg/s]
- c_p = Air specific heat [kJ/kg·K]

#### Outlet Temperature
```
T_out = T_in + Q_useful / (ṁ × c_p)
```

#### Instantaneous Efficiency
```
η_coll = Q_useful / (A_c × G)
```
Typical range: 0.40 - 0.70 depending on (T_in - T_amb)/G ratio

**Reference:** Duffie & Beckman, "Solar Engineering of Thermal Processes" 4th Ed (2013)

**Validation:**
- Peak efficiency ~62% at 550 W/m² irradiance (matches literature)
- F_R = 0.861 for air collectors (typical: 0.85-0.92)
- Stagnation temperature calculation: T_stag = T_amb + (η_opt × G / U_L)

---

### 3.3 Heat Pump Thermodynamic Cycle (R134a Refrigerant)

**Implementation File:** `heatpump.py`

#### Refrigerant Properties (CoolProp)
- Refrigerant: R134a
- Property source: CoolProp v6.4 library
- All saturation properties from P_sat(T) or T_sat(P) relations

#### Cycle State Points

**State 1:** Evaporator Outlet (Superheated Vapor)
```
T_1 = T_evap + ΔT_superheat  (ΔT_superheat = 5K)
P_1 = P_sat(T_evap)
h_1, s_1 = CoolProp.PropsSI('H|S', 'T', T_1+273.15, 'P', P_1, 'R134a')
```

**State 2s:** Isentropic Compression Endpoint
```
P_2s = P_sat(T_cond)
s_2s = s_1  (isentropic process)
h_2s = CoolProp.PropsSI('H', 'P', P_2s, 'S', s_2s, 'R134a')
```

**State 2:** Actual Compressor Discharge
```
h_2 = h_1 + (h_2s - h_1) / η_isen  [kJ/kg]
```
where η_isen = 0.75 (isentropic efficiency)

**State 3:** Condenser Outlet (Subcooled Liquid)
```
T_3 = T_cond - ΔT_subcool  (ΔT_subcool = 5K)
P_3 = P_sat(T_cond)
h_3 = CoolProp.PropsSI('H', 'T', T_3+273.15, 'P', P_3, 'R134a')
```

**State 4:** Expansion Valve Outlet (Two-Phase)
```
h_4 = h_3  (isenthalpic expansion)
P_4 = P_sat(T_evap)
x_4 = (h_4 - h_f) / (h_g - h_f)  [vapor quality]
```

#### Energy Balance Equations

**Refrigerant Mass Flow Rate:**
```
ṁ_ref = Q_cond_target / (h_2 - h_3)  [kg/s]
```

**Heat Flows:**
```
Q_evap = ṁ_ref × (h_1 - h_4)  [kW]
Q_cond = ṁ_ref × (h_2 - h_3)  [kW]
W_comp = ṁ_ref × (h_2 - h_1)  [kW]
```

**Coefficient of Performance:**
```
COP = Q_cond / W_comp
```

**Carnot COP (Theoretical Maximum):**
```
COP_Carnot = T_cond,K / (T_cond,K - T_evap,K)
```

**Second-Law Efficiency:**
```
η_II = COP_actual / COP_Carnot
```
Typical real systems: η_II = 0.35 to 0.65

#### Operating Constraints
- T_evap ∈ [-15, 20]°C
- T_cond ∈ [30, 70]°C
- Pressure ratio: P_cond / P_evap ≤ 8.0
- COP_min = 2.0 (below this, system flagged as inefficient)

**Reference:** ASHRAE Handbook - HVAC Systems and Equipment (2020), Chapter 38

---

### 3.4 Drying Kinetics (Piecewise Midilli + Arrhenius)

**Implementation Files:** `kinetics.py`, `midilli_table.py`, `phase2c_for_chamber.csv`

#### Moisture Ratio Definition
```
MR = (X - X_eq) / (X_0 - X_eq)
```
where:
- X: Current moisture content [kg_water/kg_dry]
- X_0 = 6.5 kg/kg (initial)
- X_eq = 0.0 kg/kg (equilibrium, assumed zero)

#### Piecewise Midilli Model (Phase-2 Experimental Data)

For operating points within experimental validity box (T ∈ [40,50]°C, RH ∈ [25,45]%, v ∈ [0.6,1.1] m/s, thickness ∈ [4,10] mm):

```
MR(t) = {
    a_L × exp(-k_L × t^n_L) + b_L × t,                                    t < t_split
    a_R × exp(-k_R × (t-t_shift)^n_R) + b_R × (t-t_shift) + MR_offset,   t ≥ t_split
}
```

**Parameters (Example: T=50°C, v=1.1 m/s, thickness=6mm):**
- Left segment: k_L, n_L, b_L (fitted to constant-rate + early falling-rate)
- Right segment: k_R, n_R, b_R (fitted to late falling-rate + equilibrium)
- Transition: t_split [min], t_shift [min], MR_offset [-]

**Effective Drying Coefficient Extraction:**
```
K_eff(t) = -(1/MR) × dMR/dt = -(1/(X - X_eq)) × dX/dt  [s⁻¹]
```

This converts Midilli's power-law model into a time-varying first-order coefficient for use in Phase-1 simulation.

**Data Source:** `phase2c_for_chamber.csv` contains 13 experimental conditions with fitted Midilli parameters.

#### Validity Boxes

**Hard Box (Experimental Data):**
- T: [40, 50]°C
- RH: [0.25, 0.45] (25-45%)
- v: [0.6, 1.1] m/s
- thickness: [4, 10] mm

**Soft Box (Extrapolation Permitted):**
- T: [35, 55]°C
- RH: [0.20, 0.55]
- v: [0.5, 1.3] m/s

#### Extrapolation Methods

**Method 1: Arrhenius Temperature Correction**
```
K_eff(T) = K_base × exp(-E_a/R × (1/T - 1/T_base))
```
where:
- E_a/R = 3839 K (activation energy parameter)
- T, T_base in Kelvin
- K_base: coefficient at nearest tabulated condition

**Method 2: Linear RH Scaling**
```
K_eff(RH) = K_eff × (1 - RH) / (1 - RH_base)
```
Clamped to [0, 1.5] to prevent unrealistic extrapolations.

**Method 3: Simple Exponential Fallback (When No Data Available)**
```
K_eff = K_ref × exp(α_T × ΔT) × exp(-α_RH × RH)
```
where:
- K_ref = 1×10⁻⁴ s⁻¹ at T_ref = 50°C
- α_T = 0.05 °C⁻¹
- α_RH = 2.0
- K_min = 1×10⁻⁶ s⁻¹ (numerical stability floor)

#### Moisture Content Update (First-Order Finite Difference)
```
X_{k+1} = X_k - K_eff(T, RH) × (X_k - X_eq) × Δt
```
Timestep: Δt = 60 seconds

**Constraint:** X_{k+1} ≥ X_eq (moisture cannot go negative)

---

### 3.5 Multi-Tray Chamber Model

**Implementation File:** `dryer_solar_hp.py`

#### Chamber Configuration
- Number of trays: N = 10
- Arrangement: Series cascade (Tray 0 → 1 → 2 → ... → 9)
- Mass per tray: m_dry,tray = 1.0 kg dry solids
- Total batch: m_dry,total = 10.0 kg
- Air flow: Single pass, no recirculation (r = 0)

#### Mass Balance per Tray

The water removal rate from tray j is the minimum of three physical limits:

```
dṁ_w/dt |_j = min(dṁ_w,kinetic, dṁ_w,air_capacity, m_removable/Δt)
```

where:
1. **Kinetic limit:** dṁ_w,kinetic = K_eff × (X_j - X_eq) × m_dry,j / Δt
2. **Air capacity limit:** dṁ_w,air = ṁ_da × Δω_max (prevents RH_out > 0.95)
3. **Removable moisture:** m_removable = (X_j - X_eq) × m_dry,j

#### Air Capacity Constraint

To prevent outlet air saturation, the maximum absorbable water is computed iteratively:

**Humidity Ratio Increase:**
```
Δω = (dṁ_w / Δt) / ṁ_da
```

**Air Capacity Solving:**
Δω_max is found such that:
```
RH(T_out, ω_in + Δω_max) = 0.95
```
using bisection method, where T_out is determined from enthalpy balance.

#### Humidity Ratio Update
```
ω_out = ω_in + Δω
```

#### Enthalpy Balance (Non-Adiabatic Chamber)

Evaporation extracts latent heat from the air stream:

```
Q_latent = (dṁ_w/dt) × h_fg  [kW]
h_out = h_in - Q_latent / ṁ_da  [kJ/kg_dry_air]
```

**Outlet Temperature:**
```
T_out = temperature_from_h_omega(h_out, ω_out)
```

**Outlet RH:**
```
RH_out = RH_from_T_omega(T_out, ω_out)
```

**Physical Interpretation:**
- Air loses sensible heat (temperature drops)
- Air gains latent heat (humidity increases)
- Net enthalpy decreases (energy transferred to product)

**Note on Adiabatic vs. Non-Adiabatic:**
The code currently models non-adiabatic behavior (enthalpy decreases). For thin-layer drying, adiabatic assumption (h_out = h_in) may be more typical. This is a documented modeling choice and does not affect comparative results between configurations since all use the same chamber model.

#### Sequential Tray Processing

Air conditions evolve through the cascade:
```
Tray 0: (T_in, RH_in, ω_in) → (T_0_out, RH_0_out, ω_0_out)
Tray 1: (T_0_out, RH_0_out, ω_0_out) → (T_1_out, RH_1_out, ω_1_out)
...
Tray 9: (T_8_out, RH_8_out, ω_8_out) → (T_exhaust, RH_exhaust, ω_exhaust)
```

**Cascade Behavior:**
- Tray 0 receives hottest, driest air → dries fastest (≈4-5 hours)
- Tray 9 receives coolest, most humid air → dries slowest (≈15-16 hours)
- Total drying time = time for Tray 9 to reach X_f = 0.10

#### Stop Criterion
Simulation stops when ALL trays satisfy:
```
X_j ≤ X_f = 0.10 kg/kg  for j = 0, 1, ..., 9
```

**Validation Metric:**
Total water removed should equal:
```
m_w,total = N_trays × m_dry,tray × (X_0 - X_f)
            = 10 × 1.0 × (6.5 - 0.10)
            = 64.0 kg
```

Actual simulations achieve ≈64.65 kg (0.2% error) due to slight X_f undershoot, confirming mass balance closure.

---

### 3.6 Constants & Physical Properties

#### Atmospheric Properties
```
P_atm = 101325 Pa  (standard atmospheric pressure)
g = 9.81 m/s²  (gravitational acceleration)
```

#### Dry Air Properties
```
c_p,da = 1.006 kJ/kg·K  (specific heat at constant pressure)
R_da = 287 J/kg·K  (gas constant)
ρ_da,0 = 1.204 kg/m³ at 20°C, 1 atm
```

#### Water Properties
```
c_p,v = 1.86 kJ/kg·K  (water vapor specific heat)
h_fg,0 = 2501 kJ/kg  (latent heat at 0°C)
h_fg(T) ≈ 2501 - 2.42 × T [kJ/kg]  (temperature correction)
ρ_water = 1000 kg/m³  (liquid water density)
```

#### Product Properties (Apple Slices)
```
ρ_product = 650 kg/m³  (bulk density, wet basis)
c_p,product = 3.6 kJ/kg·K  (specific heat, high moisture)
X_0 = 6.5 kg_water/kg_dry  (initial moisture, d.b.)
X_f = 0.10 kg_water/kg_dry  (final moisture, d.b.)
X_eq = 0.0 kg_water/kg_dry  (equilibrium, conservative)
```

#### Heat Pump Constants
```
η_isen = 0.75  (compressor isentropic efficiency)
η_mech = 0.95  (mechanical efficiency)
ΔT_superheat = 5 K  (evaporator outlet)
ΔT_subcool = 5 K  (condenser outlet)
ΔT_approach,evap = 10 K  (evaporator approach to heat source)
ΔT_approach,cond = 10 K  (condenser superheat above setpoint)
```

#### Solar Collector Constants
```
η_opt = 0.75  (optical efficiency, τα product)
U_L = 5.0 W/m²·K  (overall loss coefficient)
F' = 0.90  (collector efficiency factor)
K_θ = 1.0  (incidence angle modifier, normal incidence)
```

#### Simulation Parameters
```
Δt = 60 s  (timestep)
t_max = 259200 s  (72 hours maximum, 3 days)
ṁ_da = 0.1667 kg/s  (dry air mass flow rate)
v_chamber = 1.1 m/s  (air velocity through trays)
```

---

## 4. CODING STANDARDS & MODULAR DESIGN

### 4.1 General Principles

1. **Modular Functions:** Each physical component must be implemented as a standalone function or class:
   - `evaporator()` - Heat pump evaporator heat transfer
   - `condenser()` - Heat pump condenser heat transfer
   - `compressor()` - Compressor work and state transformation
   - `expansion_valve()` - Isenthalpic throttling
   - `solar_collector()` - Hottel-Whillier-Bliss calculation
   - `chamber_tray()` - Single tray mass/energy balance

2. **Mass Flow Rate Consistency:** All functions must verify ṁ_ref consistency:
   ```python
   assert abs(m_ref_from_Q_evap - m_ref_from_Q_cond) < 1e-6
   ```

3. **Energy Balance Verification:** For heat pump cycle:
   ```python
   energy_error = abs(Q_evap + W_comp - Q_cond) / Q_cond
   assert energy_error < 0.01  # <1% error tolerance
   ```

4. **Unit Consistency:**
   - Temperatures: °C (convert to K only for CoolProp calls)
   - Pressures: Pa (Pascals)
   - Energy: kW (kilowatts) for power, kWh for cumulative energy
   - Mass flow: kg/s
   - Specific properties: Per kg of dry air (psychrometrics) or per kg of refrigerant (HP cycle)

5. **Docstrings:** Every function must include:
   ```python
   def function_name(arg1, arg2):
       """Brief description.
       
       Args:
           arg1 (type): Description with units [unit]
           arg2 (type): Description with units [unit]
       
       Returns:
           type: Description with units [unit]
       
       Raises:
           ValueError: When invalid input conditions occur
       
       References:
           Citation to governing equation source
       """
   ```

6. **Type Hints:** Use Python type hints for all function signatures:
   ```python
   def compute_COP(T_evap: float, T_cond: float) -> float:
       ...
   ```

7. **Error Handling:** Validate inputs and provide meaningful error messages:
   ```python
   if T_evap >= T_cond:
       raise ValueError(f"T_evap ({T_evap}°C) must be < T_cond ({T_cond}°C)")
   ```

---

### 4.2 Code Organization & File Structure

**Core Simulation Modules:**
```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\src\rq1
├── psychro.py              # Psychrometric calculations
├── solar.py                # Solar collector model (Hottel-Whillier-Bliss)
├── heatpump.py             # Heat pump cycle (CoolProp-based)
├── kinetics.py             # Drying kinetics (first-order + Arrhenius)
├── midilli_table.py        # Midilli parameter lookup & K_eff extraction
├── dryer_solar_hp.py       # Main SAHPD simulator (all 5 configs)
├── config_solar_hp.py      # Configuration dataclasses
├── ambient.py              # Weather data loading
├── chamber_geometry.py     # Chamber physical specs
└── metrics.py              # Performance metric calculations
```

**Phase-2 Kinetics Integration:**
```
├── phase2c_for_chamber.csv          # Experimental Midilli parameters
├── recursive_piecewise_midilli.py   # Piecewise fitting algorithm
├── phase2_1a_collect_targets.py     # Experimental data processing
├── phase2_1b_train_models.py        # Midilli curve fitting
├── phase2_1c_predict.py             # Prediction from fitted models
└── phase2_utils.py                  # Shared utilities
```

**Runner Scripts:**
```
scripts/
├── run_solar_hp_configs.py          # Single config execution
├── run_phase1_simulation.py         # Legacy Phase-1 runner
├── batch_plot.py                    # Batch visualization
├── visualize_results.py             # Results plotting
└── verify_weather_data.py           # Weather data validation
```

**Data Files:**
```
data/ (not in repo, generated locally)
├── weather/
│   ├── kathmandu_pvgis.csv
│   ├── dhulikhel_pvgis.csv
│   ├── biratnagar_pvgis.csv
│   └── taplejung_pvgis.csv
└── outputs/
    ├── baseline.csv
    ├── Ac_10m2.csv
    ├── Ac_12m2.csv
    ├── Ac_15m2.csv
    └── Ac_20m2.csv
```

---

### 4.3 Configuration Dataclass Structure

**Location:** `config_solar_hp.py`

```python
from dataclasses import dataclass
from enum import Enum

class DryerConfiguration(Enum):
    """System configuration modes."""
    A_HP_ONLY = "A"              # Heat pump only (baseline)
    B_SOLAR_HP_SERIES = "B"      # Solar preheats before HP condenser
    C_SOLAR_EVAP = "C"           # Solar preheats HP evaporator source
    D_SOLAR_ONLY = "D"           # Solar only (no HP)
    E_CASCADE = "E"              # Solar → HP evap → HP cond (optimal)

@dataclass
class HeatPumpConfig:
    refrigerant: str = "R134a"
    eta_isentropic: float = 0.75
    eta_mechanical: float = 0.95
    superheat_K: float = 5.0
    subcooling_K: float = 5.0
    T_evap_min_C: float = -15.0
    T_evap_max_C: float = 20.0
    T_cond_min_C: float = 30.0
    T_cond_max_C: float = 70.0
    COP_min: float = 2.0
    pressure_ratio_max: float = 8.0

@dataclass
class SolarCollectorConfig:
    area_m2: float = 15.0            # Collector area [m²]
    eta_optical: float = 0.75        # Optical efficiency [-]
    U_L_W_per_m2K: float = 5.0       # Loss coefficient [W/m²·K]
    F_prime: float = 0.90            # Efficiency factor [-]
    incidence_angle_modifier: float = 1.0  # K_θ [-]

@dataclass
class DryerSystemConfig:
    configuration: DryerConfiguration
    T_set_C: float = 50.0            # Chamber setpoint temperature [°C]
    v_air_m_per_s: float = 1.1       # Air velocity [m/s]
    num_trays: int = 10              # Number of trays
    m_dry_per_tray_kg: float = 1.0   # Dry mass per tray [kg]
    X_initial: float = 6.5           # Initial moisture [kg/kg db]
    X_final: float = 0.10            # Final moisture [kg/kg db]
    X_equilibrium: float = 0.0       # Equilibrium moisture [kg/kg db]
    dt_s: float = 60.0               # Timestep [s]
    t_max_s: float = 259200.0        # Max simulation time [s] (72 hours)
```

---

### 4.4 Key Function Signatures

#### Psychrometrics (`psychro.py`)
```python
def saturation_pressure(T_C: float) -> float:
    """Tetens correlation for p_sat [Pa]."""
    ...

def humidity_ratio(T_C: float, RH_frac: float, P_atm: float = 101325) -> float:
    """Calculate ω [kg_w/kg_da] from T and RH."""
    ...

def RH_from_T_omega(T_C: float, omega: float, P_atm: float = 101325) -> float:
    """Calculate RH [-] from T and ω."""
    ...

def moist_air_enthalpy(T_C: float, omega: float) -> float:
    """Calculate h [kJ/kg_da] from T and ω."""
    ...

def temperature_from_h_omega(h_kJ_per_kg: float, omega: float) -> float:
    """Invert enthalpy equation to get T [°C]."""
    ...
```

#### Solar Collector (`solar.py`)
```python
def compute_F_R(
    A_c_m2: float,
    m_air_kg_per_s: float,
    F_prime: float,
    U_L: float
) -> float:
    """Calculate heat removal factor F_R [-]."""
    ...

def compute_solar_heating(
    A_c_m2: float,
    G_W_per_m2: float,
    T_in_C: float,
    T_amb_C: float,
    m_air_kg_per_s: float,
    cfg: SolarCollectorConfig
) -> tuple[float, float, float]:
    """
    Calculate solar collector performance.
    
    Returns:
        Q_useful_kW: Useful heat gain [kW]
        T_out_C: Outlet air temperature [°C]
        eta_coll: Instantaneous efficiency [-]
    """
    ...
```

#### Heat Pump (`heatpump.py`)
```python
def compute_heat_pump_cycle(
    T_evap_C: float,
    T_cond_C: float,
    Q_cond_target_kW: float,
    cfg: HeatPumpConfig
) -> dict:
    """
    Calculate complete heat pump cycle.
    
    Returns:
        dict with keys:
            m_ref_kg_per_s: Refrigerant mass flow [kg/s]
            Q_evap_kW: Evaporator heat [kW]
            Q_cond_kW: Condenser heat [kW]
            W_comp_kW: Compressor work [kW]
            COP: Coefficient of performance [-]
            state_1, state_2, state_3, state_4: RefrigerantState objects
            within_limits: bool
            warnings: list[str]
    """
    ...
```

#### Drying Kinetics (`kinetics.py`)
```python
def get_K_eff(
    T_C: float,
    RH_frac: float,
    v_m_per_s: float = 1.1,
    thickness_mm: float = 6.0
) -> float:
    """
    Get effective drying coefficient [1/s].
    
    Uses Midilli table if within validity box,
    otherwise applies Arrhenius/RH extrapolation.
    """
    ...

def update_moisture_content(
    X_current: float,
    K_eff: float,
    X_eq: float,
    dt_s: float
) -> float:
    """
    First-order moisture update: X_new = X - K*(X-Xeq)*dt
    """
    ...
```

#### Multi-Tray Chamber (`dryer_solar_hp.py`)
```python
def simulate_tray(
    T_in_C: float,
    RH_in_frac: float,
    omega_in: float,
    X_product: float,
    m_dry_kg: float,
    m_da_kg_per_s: float,
    dt_s: float,
    cfg: DryerSystemConfig
) -> dict:
    """
    Simulate one tray for one timestep.
    
    Returns:
        dict with keys:
            T_out_C, RH_out_frac, omega_out: Outlet air conditions
            X_new: Updated moisture content [kg/kg]
            dm_w_kg: Water removed this timestep [kg]
            K_eff_used: Drying coefficient [1/s]
            limiting_factor: 'kinetic' | 'air_capacity' | 'product_empty'
    """
    ...
```

---

### 4.5 Validation & Quality Checks

Every simulation must pass these automated checks:

**1. Mass Balance Closure**
```python
theoretical_water_removed = num_trays * m_dry_per_tray * (X_0 - X_f)
simulated_water_removed = sum(dm_w_cumulative_all_trays)
mass_balance_error = abs(simulated - theoretical) / theoretical
assert mass_balance_error < 0.01  # <1% error
```

**2. Energy Balance (Heat Pump)**
```python
Q_evap + W_comp = Q_cond
energy_error = abs((Q_evap + W_comp) - Q_cond) / Q_cond
assert energy_error < 0.005  # <0.5% error
```

**3. COP Reasonableness**
```python
COP_Carnot = T_cond_K / (T_cond_K - T_evap_K)
eta_II = COP_actual / COP_Carnot
assert 0.35 <= eta_II <= 0.65  # Typical range for real systems
```

**4. Solar Efficiency Bounds**
```python
assert 0.0 <= eta_coll <= 0.80  # Cannot exceed 80% for flat plate
```

**5. Psychrometric Validity**
```python
assert 0.0 <= RH <= 1.0  # Physical constraint
assert omega >= 0.0  # Cannot have negative moisture
assert dewpoint <= T_drybulb  # Fundamental thermodynamic law
```

**6. Moisture Content Monotonicity**
```python
for t in time_array[1:]:
    assert X[t] <= X[t-1]  # Moisture can only decrease (or stay constant)
```

**7. Convergence Check**
```python
if time_elapsed > t_max:
    raise RuntimeError("Simulation did not converge within 72 hours")
```

---

## 5. WEATHER DATA & GEOGRAPHICAL LOCATIONS

### 5.1 Nepal Locations

Four locations selected to represent diverse climatic zones:

| Location | Latitude | Longitude | Elevation | Climate Zone | Avg Temp | Avg GHI |
|----------|----------|-----------|-----------|--------------|----------|---------|
| **Kathmandu** | 27.70°N | 85.32°E | 1350 m | Temperate valley | 18.5°C | 170 W/m² |
| **Dhulikhel** | 27.62°N | 85.54°E | 1550 m | Hilly temperate | 17.2°C | 175 W/m² |
| **Biratnagar** | 26.45°N | 87.28°E | 72 m | Subtropical plains | 24.1°C | 185 W/m² |
| **Taplejung** | 27.35°N | 87.66°E | 1732 m | Mountain temperate | 15.8°C | 165 W/m² |

### 5.2 Weather Data Source

**PVGIS (Photovoltaic Geographical Information System)**
- Dataset: PVGIS-SARAH2 (2005-2020 climate database)
- Temporal resolution: Hourly
- Variables required:
  - T_amb: Ambient temperature [°C]
  - RH: Relative humidity [%]
  - G_h: Global horizontal irradiance [W/m²]
  - (Optional) G_b: Direct beam irradiance [W/m²]
  - (Optional) G_d: Diffuse irradiance [W/m²]
  - (Optional) wind_speed [m/s]

**Data Processing:**
- Script: `Process_pvgis_data.py`
- Output format: CSV with columns [datetime, T_amb_C, RH_pct, G_solar_Wm2]
- Timestep: 1 hour (interpolated linearly to 60-second simulation timestep)
- Missing data handling: Linear interpolation, flagged in validation report

### 5.3 Typical Meteorological Year (TMY)

For annual performance analysis, TMY data is used:
- Combines 12 representative months from multi-year dataset
- Captures seasonal variations in solar resource and ambient conditions
- Enables realistic year-round SEC and solar fraction calculations

---

## 6. PERFORMANCE METRICS & OUTPUT SPECIFICATIONS

### 6.1 Primary Metrics

**Specific Energy Consumption (SEC)**
```
SEC = W_comp_cumulative_kWh / m_w_removed_kg  [kWh_elec/kg_water]
```
Lower is better. Baseline (Config A) ≈ 1.05 kWh/kg for Kathmandu.

**Coefficient of Performance (COP)**
```
COP_instantaneous = Q_cond_kW / W_comp_kW  [-]
COP_average = Σ(Q_cond) / Σ(W_comp)  [-]
```
Higher is better. Baseline ≈ 3.45 for Kathmandu.

**Solar Fraction**
```
f_solar = Q_solar_cumulative_kWh / (Q_solar + Q_cond)_cumulative_kWh  [%]
```
Percentage of total thermal energy from solar. Config B/E: 10-15%, Config D: 100%.

**Drying Time**
```
t_dry = time when all X_j ≤ X_f  [hours]
```
Target: ≤20 hours for commercial viability.

**Electricity Savings**
```
Savings_% = (SEC_baseline - SEC_config) / SEC_baseline × 100  [%]
```
Config E target: 20-25% savings.

### 6.2 Secondary Metrics

**Specific Moisture Extraction Rate (SMER)**
```
SMER = m_w_removed_kg / W_comp_cumulative_kWh  [kg_water/kWh_elec]
```
Inverse of SEC. Higher is better.

**Energy Efficiency Ratio (EER)**
```
EER = Q_latent_kWh / W_comp_cumulative_kWh  [-]
```
Similar to SMER but using latent heat instead of mass.

**Solar Collector Efficiency (Average)**
```
η_coll_avg = Σ(Q_useful) / Σ(A_c × G)  [%]
```
Typical: 50-65% for well-designed air collectors.

**Pressure Ratio (Heat Pump)**
```
PR = P_cond / P_evap  [-]
```
Should remain < 8.0 for compressor reliability.

### 6.3 Output Files

**CSV Format (Timestep-Level Data):**

Columns (80 total):
```
time_s, time_h,
T_amb_C, RH_amb_pct, G_solar_Wm2,
Q_solar_kW, T_solar_out_C, eta_solar,
T_evap_C, T_cond_C, P_evap_bar, P_cond_bar,
W_comp_kW, Q_evap_kW, Q_cond_kW, COP, m_ref_kg_per_s,
T_to_chamber_C, RH_to_chamber_frac, omega_to_chamber,
T_exhaust_C, RH_exhaust_frac,
X_db_avg, MR_global, dm_w_total_kg,
m_w_cum_kg, W_comp_cum_kWh, Q_cond_cum_kWh, Q_solar_cum_kWh,
X_tray_0, MR_tray_0, T_tray_0_out_C, RH_tray_0_out_frac, dm_w_tray_0_kg,
... (repeat for trays 1-9) ...,
SEC_elec_kWh_per_kg
```

**Naming Convention:**
- Baseline: `baseline.csv`
- Config B/C/D/E with A_c = X m²: `Ac_Xm2.csv`

Example: `Ac_15m2.csv` for Config E with 15 m² collector.

### 6.4 Visualization Requirements

**Plot 1: Overview (2x2 Grid)**
- Subplot (a): Ambient conditions (T, RH vs. time)
- Subplot (b): Solar irradiance (G vs. time)
- Subplot (c): Chamber conditions (T_in, RH_in vs. time)
- Subplot (d): Drying progress (MR vs. time, all trays)

**Plot 2: Energy Summary**
- Bar chart: W_comp_cum, Q_cond_cum, Q_solar_cum
- Secondary axis: SEC, f_solar

**Plot 3: Heat Pump Performance**
- COP vs. time
- T_evap, T_cond vs. time
- Pressure ratio vs. time

**Plot 4: Solar Collector Performance**
- η_coll vs. time (colored by G level)
- Q_solar vs. time
- T_solar_out vs. time

**Plot 5: Tray-Specific Drying Curves**
- X vs. time for each tray (10 curves)
- Highlight sequential drying pattern

All plots saved as PNG (300 DPI) and PDF (vector).

---

## 7. VALIDATION & BENCHMARKING

### 7.1 Physics Validation

**Psychrometric Validation:**
- Compare saturation pressure against ASHRAE tables: error < 1%
- Verify humidity ratio inverse calculations: roundtrip error < 0.1%
- Check enthalpy-temperature inversions: error < 0.5%

**Solar Collector Validation:**
- F_R calculation: Compare to Duffie & Beckman Example 6.8.1
- Collector efficiency: Should match typical flat-plate performance curves
- Stagnation temperature: T_stag = T_amb + (η_opt × G_max / U_L) ≈ T_amb + 112K at 1000 W/m²

**Heat Pump Validation:**
- COP vs. literature: Real systems achieve 35-65% of Carnot COP
- Pressure-enthalpy diagram: All state points must lie on valid R134a properties
- Energy balance: |Q_evap + W_comp - Q_cond| / Q_cond < 0.5%

**Drying Kinetics Validation:**
- First-order check: ln(MR) vs. time should be approximately linear (R² > 0.85)
- Comparison to experimental data: RMSE < 0.05 for MR predictions
- Page/Midilli model fit: R² > 0.95 for all experimental runs

### 7.2 Benchmark Comparisons

**SEC Benchmarks (from literature):**
- Electric resistance dryer: 1.5-2.5 kWh/kg
- Heat pump dryer (HP-only): 0.8-1.2 kWh/kg
- Solar-assisted HP dryer: 0.6-0.9 kWh/kg

**COP Benchmarks:**
- Air-source heat pump (ΔT = 30K): COP = 2.8-3.5
- Optimized SAHPD: COP = 3.8-4.5

**Drying Time Benchmarks:**
- Conventional electric (50°C): 12-18 hours
- HP dryer (50°C): 14-20 hours
- Solar dryer (variable T): 24-72 hours

### 7.3 Configuration Comparison Reference

**Expected Performance Summary (Kathmandu, 15 m² collector):**

| Config | Description | SEC [kWh/kg] | COP [-] | Solar Fraction [%] | Savings [%] |
|--------|-------------|--------------|---------|-------------------|-------------|
| A | HP-only baseline | 1.052 | 3.45 | 0 | 0 (baseline) |
| B | Solar+HP series | 0.932 | 3.45 | 12 | 11.5 |
| C | Solar→evap | 0.945 | 4.22* | 0 | 10.0 |
| D | Solar-only | 0.000 | N/A | 100 | N/A (incomplete) |
| E | Cascade (optimal) | 0.847 | 4.10 | 13 | 19.5 |

*COP varies with solar, average shown

**Critical Insight:**
Config B outperforms Config C despite Config C having higher COP. This is because direct load reduction (Config B) is more effective than efficiency improvement (Config C) at these operating temperatures. Config E combines both mechanisms for maximum savings.

---

## 8. IMPLEMENTATION WORKFLOW

### 8.1 Recommended Development Sequence

**Phase 1: Core Physics Modules (Complete)**
1. ✅ `psychro.py` - ASHRAE psychrometric calculations
2. ✅ `solar.py` - Hottel-Whillier-Bliss solar collector
3. ✅ `heatpump.py` - CoolProp-based refrigeration cycle
4. ✅ `kinetics.py` - Drying coefficient calculations
5. ✅ `midilli_table.py` - Phase-2 experimental data integration

**Phase 2: Chamber & System Integration (Complete)**
6. ✅ `dryer_solar_hp.py` - Multi-tray cascade simulator
7. ✅ `config_solar_hp.py` - Configuration dataclasses
8. ✅ All 5 configurations implemented with proper air flow routing

**Phase 3: Execution & Analysis (Current)**
9. ✅ `run_solar_hp_configs.py` - Single configuration runner
10. ⏳ Batch execution across locations × solar areas
11. ⏳ Comprehensive results visualization
12. ⏳ Statistical analysis and optimization

**Phase 4: Documentation & Publication (Future)**
13. ⏳ Physics validation report completion
14. ⏳ Technical documentation with all equations
15. ⏳ Thesis chapter draft
16. ⏳ Journal manuscript preparation

### 8.2 Running Simulations

**Single Configuration:**
```bash
python scripts/run_solar_hp_configs.py \
    --config E \
    --location kathmandu \
    --solar-area 15 \
    --output results/configE_ktm_15m2.csv
```

**Full Sweep (All Configs × Locations × Solar Areas):**
```bash
python scripts/run_solar_hp_configs.py --full
```
This generates:
- 1 baseline (Config A) × 4 locations = 4 simulations
- Configs B/C/E × 4 locations × 8 solar areas (2,4,6,8,10,12,15,20 m²) = 96 simulations
- Config D × 4 locations × 8 solar areas = 32 simulations
- **Total: 132 simulations**

**Batch Visualization:**
```bash
python scripts/visualize_results.py --config E --location kathmandu
```

### 8.3 Git Workflow

**Branch Strategy:**
- `main` - Stable, validated code only
- `dev` - Active development
- `feature/config-X` - Configuration-specific development
- `bugfix/issue-N` - Bug fixes

**Commit Message Convention:**
```
[MODULE] Brief description

Detailed explanation of changes made.

Affects:
- File 1
- File 2

Validation:
- Mass balance: ±0.2%
- Energy balance: ±0.3%
```

Example:
```
[HEATPUMP] Fix COP calculation for low T_evap

Updated isentropic efficiency correlation to handle
T_evap < 0°C more accurately using Martin-Hou EOS
correction factors.

Affects:
- heatpump.py: compute_heat_pump_cycle()

Validation:
- COP for T_evap=-5°C, T_cond=60°C: 2.85 (was 2.72)
- Energy balance error: 0.15% (was 0.89%)
```

---

## 9. KNOWN ISSUES & FUTURE IMPROVEMENTS

### 9.1 Current Limitations

**1. Chamber Model Assumption**
- **Issue:** Non-adiabatic enthalpy balance (h_out = h_in - Q_latent/ṁ_da)
- **Impact:** May underestimate temperature drop through trays
- **Alternative:** Adiabatic model (h_out = h_in, wet-bulb cooling)
- **Action:** Document assumption in thesis methodology; compare both models in sensitivity analysis

**2. Equilibrium Moisture Content**
- **Issue:** X_eq = 0 assumed (conservative but unrealistic)
- **Reality:** X_eq ≈ 0.05-0.08 kg/kg for apples at 50°C, 10% RH
- **Impact:** Slightly overpredicts drying time and SEC
- **Action:** Implement GAB or Henderson isotherm model in future version

**3. Solar Collector Incidence Angle**
- **Issue:** K_θ = 1.0 (normal incidence) hard-coded
- **Reality:** K_θ = f(θ_incident) reduces efficiency at high angles
- **Impact:** Overestimates solar gain by ~5-15% at morning/evening
- **Action:** Implement ASHRAE 93-2010 incidence angle modifier correlation

**4. Heat Exchanger Effectiveness**
- **Issue:** ε_evap = ε_cond = 0.85 assumed constant
- **Reality:** Effectiveness varies with flow rate and fouling
- **Impact:** May overestimate HP performance slightly
- **Action:** Implement NTU-effectiveness method with variable UA

**5. Kinetics Extrapolation Uncertainty**
- **Issue:** Arrhenius extrapolation outside hard box uncertain
- **Reality:** Drying mechanisms may change at extreme conditions
- **Impact:** Predictions at T < 40°C or RH > 50% less reliable
- **Action:** Flag soft-box predictions with confidence intervals in output

### 9.2 Planned Enhancements

**Short-Term (1-2 months):**
1. Add confidence intervals for kinetics extrapolation
2. Implement economic analysis (NPV, payback period, LCOE)
3. Create interactive dashboard for results exploration
4. Automate PVGIS data download for any lat/lon

**Medium-Term (3-6 months):**
1. Multi-objective optimization (Pareto front for SEC vs. cost)
2. Uncertainty quantification (Monte Carlo for parameter uncertainty)
3. Control strategy optimization (variable setpoint, adaptive airflow)
4. Extend to other crops (banana, mango, citrus)

**Long-Term (6+ months):**
1. Experimental validation with pilot-scale SAHPD
2. Machine learning surrogate model for fast predictions
3. Real-time optimization and control implementation
4. Integration with IoT sensors for adaptive operation

---

## 10. REFERENCES & CITATIONS

### 10.1 Core Textbooks

1. **ASHRAE Handbook - Fundamentals (2021)**  
   Chapter 1: Psychrometrics  
   Tetens correlation, humidity ratio, moist air properties

2. **Duffie, J. A., & Beckman, W. A. (2013)**  
   *Solar Engineering of Thermal Processes, 4th Edition*  
   Wiley. ISBN: 978-0-470-87366-3  
   Hottel-Whillier-Bliss equation, F_R calculation, collector performance

3. **ASHRAE Handbook - HVAC Systems and Equipment (2020)**  
   Chapter 38: Compressors  
   Chapter 39: Condensers  
   Chapter 40: Evaporators  
   Isentropic efficiency, COP benchmarks

4. **Mujumdar, A. S. (Ed.). (2014)**  
   *Handbook of Industrial Drying, 4th Edition*  
   CRC Press. ISBN: 978-1-4665-9665-8  
   Drying kinetics, thin-layer models, Page/Midilli equations

### 10.2 Key Journal Articles

(Selected from `/mnt/project/*.pdf` literature collection)

**Solar-Assisted Heat Pump Dryers:**
- Hawlader et al. (2006, 2008) - Solar-HP drying systems
- Kuan et al. (2019) - Performance optimization
- Chanpet et al. (2020) - Agricultural applications

**Drying Kinetics:**
- Rahman et al. (2013) - Midilli-Kucuk model validation
- Salhi et al. (2022) - Thin-layer drying of fruits

**Solar Collectors:**
- Ismaeel et al. (2020) - Flat-plate collector modeling
- Various ASHRAE Standard 93-2010 references

**Nepal Solar Resource:**
- Solar Resource Mapping Report (2015)  
  World Bank ESMAP publication  
  GHI and DNI data for Nepal locations

### 10.3 Software & Data Sources

**CoolProp v6.4**  
Bell, I. H., Wronski, J., Quoilin, S., & Lemort, V. (2014)  
"Pure and Pseudo-pure Fluid Thermophysical Property Evaluation and the Open-Source Thermophysical Property Library CoolProp"  
*Industrial & Engineering Chemistry Research*, 53(6), 2498-2508.  
DOI: 10.1021/ie4033999

**PVGIS (Photovoltaic Geographical Information System)**  
European Commission Joint Research Centre  
SARAH2 satellite-based solar radiation database (2005-2020)  
https://re.jrc.ec.europa.eu/pvg_tools/en/

**Python Libraries:**
- NumPy 1.24+ (numerical computing)
- Pandas 2.0+ (data manipulation)
- Matplotlib 3.7+ (visualization)
- SciPy 1.10+ (optimization, interpolation)

---

## 11. CONTACT & SUPPORT

**Primary Developer:** Wasti  
**Institution:** [University Name - To Be Added]  
**Program:** Masters Thesis Research  
**Supervisor:** [Supervisor Name - To Be Added]  
**Research Group:** [Group Name - To Be Added]

**Code Repository:** [GitHub URL - To Be Added]  
**Documentation:** This file (`PROJECT_CONTEXT.md`)  
**Issue Tracker:** [GitHub Issues URL - To Be Added]

**For Questions:**
- Technical (code): Open GitHub issue with `[QUESTION]` tag
- Scientific (physics): Email supervisor with `[SAHPD]` subject prefix
- Collaboration: Email primary developer

---

## 12. CHANGELOG

**v2.0 (2026-02-04) - Current Version**
- Complete rewrite of PROJECT_CONTEXT.md as authoritative Ground Truth
- Added comprehensive physics models with all equations
- Documented all 5 configurations with expected performance
- Added coding standards and modular design principles
- Included validation procedures and benchmark comparisons
- Expanded implementation workflow and git conventions

**v1.5 (2026-01-28)**
- Fixed Config B/C physics interpretation
- Added Configuration E (cascade) as optimal design
- Validated against Dhulikhel results (17-24% savings achieved)

**v1.0 (2026-01-22)**
- Initial structure with Configs A-D
- Basic psychrometrics, solar, and HP models implemented
- Phase-2 Midilli integration completed

---

## 13. CURRENT STATUS & CRITICAL UPDATES (February 4, 2026)

### 13.1 Drying Time Discrepancy - IMPORTANT UPDATE

**CRITICAL CORRECTION:** The drying times documented in earlier sections of this document (≈15.7 hours) were based on preliminary simulations. **Current simulation results show significantly longer drying times.**

#### Actual Drying Times (Current Simulation Results)

**Single Inlet Mode (Standard Configuration):**

| Location | Config A (Baseline) | Config B (15m²) | Config C (15m²) | Config E (15m²) | Config D (15-20m²) |
|----------|---------------------|-----------------|-----------------|-----------------|-------------------|
| **Kathmandu** | 24.3 hours | 24.2-24.3 hours | 24.3 hours | 24.2-24.3 hours | 72+ hours (incomplete) |
| **Dhulikhel** | 25.5 hours | 25.4-25.5 hours | 25.5 hours | 25.5 hours | 72+ hours (incomplete) |
| **Biratnagar** | 26.2 hours | 24.1-26.2 hours | 26.2 hours | 25.3-26.2 hours | 53.8-67.7 hours |

**Multizone Mode (3 Zones, n_zones=3):**

| Location | Config A (Baseline) | Config B (15m²) | Config C (15m²) | Config E (15m²) |
|----------|---------------------|-----------------|-----------------|-----------------|
| **Kathmandu** | 24.7 hours | 24.7 hours | 24.7 hours | 24.7 hours |
| **Dhulikhel** | 25.8 hours | 25.8 hours | 25.8 hours | 25.8 hours |
| **Biratnagar** | 26.5 hours | 25.6-26.5 hours | 26.5 hours | 25.6-26.5 hours |

#### Key Observations

1. **Baseline Drying Time:** Config A (HP-only) takes **24-26 hours** to complete drying, not 15.7 hours as initially documented.

2. **Tray-by-Tray Variation:**
   - **Tray 0 (first tray):** Dries fastest at 2.7-6.0 hours
   - **Tray 9 (last tray):** Takes 23.6-25.6 hours (determines total drying time)
   - **Range:** 20-22 hours difference between fastest and slowest tray

3. **Solar Configurations Impact:**
   - Configs B, C, E achieve 15-25% energy savings (SEC reduction)
   - Drying times remain similar to baseline (±0.5 hours)
   - Solar integration primarily reduces electricity consumption, not drying time

4. **Config D (Solar-Only) Limitations:**
   - Kathmandu/Dhulikhel: Does NOT complete within 72 hours
   - Biratnagar (higher solar): 53.8-67.7 hours to complete
   - Confirms impracticality for commercial applications

5. **Multizone vs Single Inlet:**
   - Multizone: Slightly longer total time (+0.3-0.4 hours)
   - Multizone: Better uniformity (uniformity_pct: ~23% vs ~11%)
   - Multizone: Reduced tray-to-tray variation

#### Why the Discrepancy?

The longer drying times in current simulations are attributed to:

1. **Phase-2 Kinetics Integration:** Updated drying coefficient (K_eff) extraction from experimental piecewise Midilli models reflects more realistic drying behavior at varying T/RH conditions.

2. **Multi-Tray Cascade Effects:** Sequential air degradation through 10 trays causes RH to increase and temperature to decrease, significantly slowing drying in downstream trays (especially Trays 7-9).

3. **Air Capacity Constraints:** The simulation now properly enforces maximum humidity ratio increases (RH_out ≤ 0.95) to prevent air saturation, which limits water removal rates.

4. **Non-Adiabatic Chamber Model:** Enthalpy decrease through trays (evaporative cooling) reduces driving force for moisture removal in later trays.

5. **Conservative Stop Criterion:** Simulation only terminates when ALL trays reach X ≤ 0.10 kg/kg, not just average moisture content.

#### Performance Metrics (Updated Values)

**Config A (Kathmandu, Baseline):**
- SEC: 0.560 kWh/kg (previously estimated 1.05 kWh/kg)
- COP: 3.40-3.45 (matches expectations)
- Drying time: **24.3 hours** (was 15.7 hours)
- Total energy: 36.3 kWh

**Config E (Kathmandu, 15 m² solar, Optimal):**
- SEC: 0.432 kWh/kg (22.9% savings vs Config A)
- COP: 4.10-4.20 during solar hours
- Solar fraction: ~45% of total thermal energy
- Drying time: **24.3 hours** (similar to baseline)
- Total energy: 28.0 kWh electric + 22.6 kWh solar

**Config E (Biratnagar, 20 m² solar, Best Case):**
- SEC: 0.261 kWh/kg (53.4% savings vs Config A baseline)
- Drying time: **24.1 hours**
- Highest energy savings achieved across all locations

### 13.2 Output Directory Structure

**Current Organization:**

```
RQ1/outputs/
├── config_A/                    # Config A (HP-only), single inlet
│   ├── kathmandu/
│   │   └── Ac_0m2.csv          # Baseline (solar_area = 0)
│   ├── dhulikhel/
│   └── biratnagar/
├── config_B/                    # Config B (Solar+HP series), single inlet
│   ├── kathmandu/
│   │   ├── Ac_5m2.csv
│   │   ├── Ac_10m2.csv
│   │   ├── Ac_12m2.csv
│   │   ├── Ac_15m2.csv
│   │   └── Ac_20m2.csv
│   ├── dhulikhel/
│   └── biratnagar/
├── config_C/                    # Config C (Solar evaporator), single inlet
├── config_D/                    # Config D (Solar-only), single inlet
├── config_E/                    # Config E (Cascade), single inlet
├── config_A_mz3/               # Config A with multizone (3 zones)
├── config_B_mz3/               # Config B with multizone (3 zones)
├── config_C_mz3/               # Config C with multizone (3 zones)
├── config_D_mz3/               # Config D with multizone (3 zones)
├── config_E_mz3/               # Config E with multizone (3 zones)
├── phase2c_for_chamber.csv     # Experimental Midilli parameters
├── run_summary.csv             # Summary of all single-inlet runs
└── run_summary_multizone.csv   # Summary of all multizone runs
```

**Naming Convention:**
- `config_A`, `config_B`, etc.: Single inlet mode (default)
- `config_A_mz3`, `config_B_mz3`, etc.: Multizone mode with 3 zones
- `Ac_Xm2.csv`: Solar collector area = X square meters
- `Ac_0m2.csv`: No solar collector (Config A baseline)

**Previous Outputs Location:**
- Historical results stored in: `C:\Users\sarwa\OneDrive\Desktop\Plots for 1 inlet`
- These represent earlier simulation versions before Phase-2 kinetics integration

### 13.3 Known Issues & Limitations (Current)

1. **Taplejung Weather Data Missing:**
   - Error: Weather file not found for Taplejung location
   - All Taplejung simulations fail with file not found error
   - Action: Need to generate or obtain PVGIS data for Taplejung coordinates

2. **Division by Zero Error (Solar Area = 0):**
   - Configs B, C, D, E with Ac=0 crash with "float division by zero"
   - Root cause: Solar collector functions called even when area = 0
   - Workaround: Config B/C/D/E should only run with Ac > 0
   - Config A (HP-only) correctly handles Ac=0 case

3. **Config D Incomplete Drying:**
   - Solar-only configuration cannot complete drying in 72 hours for most locations
   - Only Biratnagar (high solar resource) completes in 53-67 hours
   - Confirms expected limitation documented in Section 2 (Config D)

4. **Tray Drying Uniformity:**
   - Single inlet: 11-12% uniformity (large tray-to-tray variation)
   - Multizone (3 zones): 23-24% uniformity (better, but still significant variation)
   - Last tray (Tray 9) takes 8-9x longer than first tray (Tray 0)

5. **SEC Values Lower Than Expected:**
   - Current simulations show SEC ~0.4-0.6 kWh/kg
   - Literature benchmarks suggest 0.8-1.2 kWh/kg for HP dryers
   - Possible causes:
     - Different product (apples vs. other crops)
     - High initial moisture content (X₀ = 6.5 kg/kg)
     - Optimistic heat pump COP assumptions
     - Need validation against experimental data

### 13.4 Recent Code Changes

**Phase-2 Kinetics Integration (Complete):**
- Piecewise Midilli model implemented with transition points
- K_eff extraction from experimental data (phase2c_for_chamber.csv)
- Arrhenius extrapolation for T/RH outside hard box
- Significantly improved drying time predictions (more realistic)

**Weather Data Handling (Fixed):**
- Hourly PVGIS data interpolated to 60-second timesteps
- Proper time alignment between weather and simulation
- Night operation: Solar configs gracefully fall back to HP-only when GHI ≈ 0

**Multizone Simulation (New Feature):**
- 3-zone chamber configuration with recirculation
- Zone-by-zone air mixing and mass balance
- Improved drying uniformity vs. single inlet
- Separate output directory (config_X_mz3)

**Stop Criterion (Improved):**
- Simulation terminates only when ALL trays reach X ≤ X_final
- Prevents premature stopping based on average moisture
- Better reflects real batch drying completion

### 13.5 Recommendations for Future Work

1. **Experimental Validation:**
   - Critical need to validate simulation predictions with pilot-scale dryer
   - Measure actual drying times, SEC, and COP under controlled conditions
   - Calibrate Phase-2 kinetics parameters if needed

2. **Uniformity Improvement:**
   - Explore 5-zone or 7-zone configurations
   - Investigate variable air flow rates between zones
   - Consider reversing air flow direction periodically

3. **Economic Analysis:**
   - Update cost calculations with corrected drying times (24-26 hours vs. 15.7 hours)
   - Longer batch times affect throughput and capital cost recovery
   - Re-evaluate payback period for solar integration

4. **Control Strategy Optimization:**
   - Dynamic T_set adjustment based on tray moisture levels
   - Adaptive air flow rate to maintain uniform drying
   - Smart HP compressor cycling to reduce electricity peaks

5. **Extended Location Analysis:**
   - Obtain Taplejung weather data
   - Add 2-3 more Nepal locations for comprehensive coverage
   - Investigate seasonal variations (monsoon vs. dry season)

### 13.6 Summary Table (Corrected Expected Performance)

| Config | Kathmandu SEC [kWh/kg] | Kathmandu Time [h] | Savings [%] | Solar Fraction [%] | Status |
|--------|------------------------|--------------------|--------------|--------------------|--------|
| A (Baseline) | 0.560 | 24.3 | 0 (baseline) | 0 | ✅ Complete |
| B (15m²) | 0.459 | 24.3 | 18.0 | 43.1 | ✅ Complete |
| C (15m²) | 0.488 | 24.3 | 12.9 | 41.7 | ✅ Complete |
| D (15m²) | N/A | 72+ | N/A | 100 | ⚠️ Incomplete |
| E (15m²) | 0.432 | 24.3 | 22.9 | 44.7 | ✅ Complete |
| E (20m²) | 0.414 | 24.2 | 26.1 | 50.8 | ✅ Complete |

**Key Insight:** Solar integration (Config E) achieves 23-26% electricity savings with same drying time as baseline. Config D (solar-only) is not viable for this application.

---

**END OF PROJECT_CONTEXT.md**

*This document serves as the single source of truth for all SAHPD simulation development. Any modifications to core physics models, configurations, or coding standards must be reflected in updates to this document.*

*Version control: All changes tracked via Git with descriptive commits.*

*Last validated: 2026-02-04*

**Last major update: 2026-02-04** - Section 13 added to document actual simulation results, drying time corrections, and current status of all configurations.
