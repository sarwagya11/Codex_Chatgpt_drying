"""Analyze where to place solar collector in Design C (HRX + HP dryer)."""
import numpy as np
from src.rq1.psychro import (
    p_sat_water_Pa, humidity_ratio_from_T_RH,
    dewpoint_from_omega_C, RH_from_T_omega,
    moist_air_enthalpy_kJ_per_kg,
)
from src.rq1.heatpump import compute_heat_pump_cycle, HeatPumpConfig

P_atm = 86120.0
hp_cfg = HeatPumpConfig()
T_set = 45.0
T_cond_sat = 55.0
eps_HRX = 0.70
eps_evap = 0.85
T_evap_sat = 5.0
T_coil = T_evap_sat + 3.0
m_da = 0.078
cp = 1.02

T_amb = 10.0
RH_amb = 0.85
T_exh = 38.0
omega_exh = 0.014
omega_amb = humidity_ratio_from_T_RH(T_amb, RH_amb, P_atm)
r = 0.5
m_fresh = (1 - r) * m_da

# Design C baseline (no solar)
T_fresh_hrx = T_amb + eps_HRX * (T_exh - T_amb)
T_mix = r * T_exh + (1 - r) * T_fresh_hrx
omega_mix = r * omega_exh + (1 - r) * omega_amb
T_after_evap = T_mix - eps_evap * (T_mix - T_coil)
T_dp_mix = dewpoint_from_omega_C(omega_mix, P_atm)
if T_after_evap < T_dp_mix:
    omega_ae = 0.622 * p_sat_water_Pa(T_after_evap) / (P_atm - p_sat_water_Pa(T_after_evap))
else:
    omega_ae = omega_mix

h_ae = moist_air_enthalpy_kJ_per_kg(T_after_evap, omega_ae)
h_tgt = moist_air_enthalpy_kJ_per_kg(T_set, omega_ae)
Q_cond_base = m_da * (h_tgt - h_ae)

print("WHERE TO PUT SOLAR IN DESIGN C")
print("=" * 100)
print()
print(f"Conditions: T_amb=10C, T_exh=38C, r=0.5, eps_HRX=0.7")
print(f"  T_fresh_after_HRX = {T_fresh_hrx:.1f}C")
print(f"  T_mix = {T_mix:.1f}C")
print(f"  T_after_evap = {T_after_evap:.1f}C")
print(f"  Q_cond_needed (no solar) = {Q_cond_base:.3f} kW")
print()

# Solar collector output at different inlet temperatures
A_solar = 10.0
G = 500.0
eta_0 = 0.75
U_L = 5.0

print("SOLAR COLLECTOR EFFICIENCY AT EACH POSITION")
print(f"A={A_solar}m2, G={G}W/m2, eta_0={eta_0}, U_L={U_L}W/m2/K")
print("-" * 90)
print(f"{'Position':>25} | T_in_solar | Q_useful kW | Collector eff | Notes")
print("-" * 90)

positions = [
    ("S1: before HRX", T_amb, "Best eff, but solar+HRX compete for same DT"),
    ("S2: after HRX, pre-mix", T_fresh_hrx, "Good eff, but heats air going into evap"),
    ("S3: after mix, pre-evap", T_mix, "Evap will cool this back down"),
    ("S4: after evap, pre-cond", T_after_evap, "Cold air = best eff + direct benefit"),
]

solar_results = {}
for label, T_in, note in positions:
    Q_useful = A_solar * (G * eta_0 - U_L * (T_in - T_amb)) / 1000.0
    Q_useful = max(0, Q_useful)
    eff = Q_useful * 1000 / (A_solar * G)
    solar_results[label] = Q_useful
    print(f"{label:>25} | {T_in:9.1f}C | {Q_useful:10.3f}  | {eff:12.1%}  | {note}")

print()
print("WHAT HAPPENS TO SOLAR ENERGY AT EACH POSITION")
print("-" * 90)

# S3: Solar before evaporator
Q_s3 = solar_results["S3: after mix, pre-evap"]
T_mix_s3 = T_mix + Q_s3 / (m_da * cp)
T_ae_s3 = T_mix_s3 - eps_evap * (T_mix_s3 - T_coil)
print(f"S3: Solar adds {Q_s3:.2f}kW before evap. T_mix goes {T_mix:.1f} -> {T_mix_s3:.1f}C")
print(f"    Evaporator cools to {T_ae_s3:.1f}C (vs {T_after_evap:.1f}C without solar)")
print(f"    Evap absorbs {eps_evap*100:.0f}% of extra heat. Only {(1-eps_evap)*100:.0f}% of solar reaches condenser inlet.")
print(f"    Net T rise at cond inlet from solar: {T_ae_s3 - T_after_evap:.1f}C")
print()

# S4: Solar after evaporator
Q_s4 = solar_results["S4: after evap, pre-cond"]
T_before_cond_s4 = T_after_evap + Q_s4 / (m_da * cp)
print(f"S4: Solar adds {Q_s4:.2f}kW after evap. T goes {T_after_evap:.1f} -> {T_before_cond_s4:.1f}C")
print(f"    100% of solar reaches condenser inlet. No evap interference.")
print(f"    Net T rise at cond inlet from solar: {T_before_cond_s4 - T_after_evap:.1f}C")
print()

# Compare W_comp
h_ae_s3 = moist_air_enthalpy_kJ_per_kg(T_ae_s3, omega_ae)
Q_cond_s3 = max(0.01, m_da * (h_tgt - h_ae_s3))
hp_s3 = compute_heat_pump_cycle(T_evap_sat, T_cond_sat, Q_cond_s3, hp_cfg)

h_s4 = moist_air_enthalpy_kJ_per_kg(T_before_cond_s4, omega_ae)
Q_cond_s4 = max(0.01, m_da * (h_tgt - h_s4))
hp_s4 = compute_heat_pump_cycle(T_evap_sat, T_cond_sat, max(0.01, Q_cond_s4), hp_cfg)

hp_base = compute_heat_pump_cycle(T_evap_sat, T_cond_sat, max(0.01, Q_cond_base), hp_cfg)

print("COMPRESSOR POWER COMPARISON")
print("-" * 70)
print(f"  No solar:         Q_cond={Q_cond_base:.3f}kW  W_comp={hp_base.W_comp_kW:.3f}kW")
print(f"  S3 (pre-evap):    Q_cond={Q_cond_s3:.3f}kW  W_comp={hp_s3.W_comp_kW:.3f}kW  (saved {hp_base.W_comp_kW-hp_s3.W_comp_kW:.3f}kW)")
print(f"  S4 (post-evap):   Q_cond={Q_cond_s4:.3f}kW  W_comp={hp_s4.W_comp_kW:.3f}kW  (saved {hp_base.W_comp_kW-hp_s4.W_comp_kW:.3f}kW)")
print()
if hp_s3.W_comp_kW > 0.001:
    print(f"  S4 saves {(hp_s3.W_comp_kW-hp_s4.W_comp_kW)/hp_s3.W_comp_kW*100:.0f}% more W_comp than S3")
print()

print("WHY S4 WINS - THREE REASONS")
print("=" * 70)
print(f"1. COLLECTOR EFFICIENCY: Air at evap outlet is coldest ({T_after_evap:.1f}C).")
print("   Cold inlet = minimal heat loss = max Q_useful from collector.")
print()
print("2. DIRECT DISPLACEMENT: Every watt of solar directly reduces Q_cond.")
print("   At S3, evaporator absorbs 85% of solar heat back out.")
print()
print("3. DEHUMIDIFICATION PRESERVED: Evaporator sees same T_mix with or")
print("   without solar. At S3, warmer air = less dehumidification.")
print()

# Across multiple r values
print("=" * 100)
print("DESIGN C + S4 ACROSS RECIRCULATION RATIOS (KTM, mid-drying)")
print("=" * 100)
print(f"{'r':>5} | T_mix  | T_aft_evap | Q_solar kW | T_aft_solar | Q_cond kW | W_comp kW | vs Config A")
print("-" * 100)

for r_val in [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]:
    if r_val < 1.0:
        T_fh = T_amb + eps_HRX * (T_exh - T_amb)
    else:
        T_fh = T_exh  # irrelevant at r=1
    T_m = r_val * T_exh + (1 - r_val) * T_fh
    om = r_val * omega_exh + (1 - r_val) * omega_amb

    T_ae_r = T_m - eps_evap * (T_m - T_coil)
    T_dp_r = dewpoint_from_omega_C(om, P_atm)
    if T_ae_r < T_dp_r:
        om_ae = 0.622 * p_sat_water_Pa(T_ae_r) / (P_atm - p_sat_water_Pa(T_ae_r))
    else:
        om_ae = om

    # Solar at S4
    Q_sol = A_solar * (G * eta_0 - U_L * (T_ae_r - T_amb)) / 1000.0
    Q_sol = max(0, Q_sol)
    T_after_sol = T_ae_r + Q_sol / (m_da * cp)
    T_after_sol = min(T_after_sol, T_set)

    h_as = moist_air_enthalpy_kJ_per_kg(T_after_sol, om_ae)
    h_t = moist_air_enthalpy_kJ_per_kg(T_set, om_ae)
    Qc = max(0.01, m_da * (h_t - h_as))
    hp_r = compute_heat_pump_cycle(T_evap_sat, T_cond_sat, Qc, hp_cfg)

    # Config A baseline (no HRX, no solar)
    T_m_nohrx = r_val * T_exh + (1 - r_val) * T_amb
    T_ae_nohrx = T_m_nohrx - eps_evap * (T_m_nohrx - T_coil)
    om_nohrx = r_val * omega_exh + (1 - r_val) * omega_amb
    T_dp_nohrx = dewpoint_from_omega_C(om_nohrx, P_atm)
    if T_ae_nohrx < T_dp_nohrx:
        om_ae_nohrx = 0.622 * p_sat_water_Pa(T_ae_nohrx) / (P_atm - p_sat_water_Pa(T_ae_nohrx))
    else:
        om_ae_nohrx = om_nohrx
    h_nohrx = moist_air_enthalpy_kJ_per_kg(T_ae_nohrx, om_ae_nohrx)
    h_t_nohrx = moist_air_enthalpy_kJ_per_kg(T_set, om_ae_nohrx)
    Qc_nohrx = max(0.01, m_da * (h_t_nohrx - h_nohrx))
    hp_nohrx = compute_heat_pump_cycle(T_evap_sat, T_cond_sat, Qc_nohrx, hp_cfg)

    saving = (hp_nohrx.W_comp_kW - hp_r.W_comp_kW) / hp_nohrx.W_comp_kW * 100
    print(f"{r_val:5.1f} | {T_m:5.1f}C | {T_ae_r:9.1f}C | {Q_sol:9.3f}  | {T_after_sol:10.1f}C | {Qc:9.3f} | {hp_r.W_comp_kW:9.3f} | {saving:+.0f}%")

print()
print("RECOMMENDED CONFIG D AIR PATH:")
print("  Ambient -> [HRX cold] -> Mix(r*exhaust) -> [Evaporator] -> [SOLAR] -> [Condenser] -> Chamber")
print("  Exhaust: r recirculated, (1-r) -> [HRX hot] -> expelled")
