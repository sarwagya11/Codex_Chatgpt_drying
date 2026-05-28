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
