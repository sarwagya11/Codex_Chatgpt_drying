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
