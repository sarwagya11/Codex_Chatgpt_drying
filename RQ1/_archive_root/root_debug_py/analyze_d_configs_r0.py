"""Enumerate and compare all r=0 HRX configurations (D1, D2, D3)."""
from src.rq1.psychro import (
    p_sat_water_Pa, humidity_ratio_from_T_RH,
    dewpoint_from_omega_C, RH_from_T_omega,
    moist_air_enthalpy_kJ_per_kg,
)
from src.rq1.heatpump import compute_heat_pump_cycle, HeatPumpConfig

P_ktm = 86120.0
P_btn = 100460.0
hp_cfg = HeatPumpConfig()
T_set = 45.0
T_cond_sat = 55.0
eps_HRX = 0.70
m_da = 0.078

test_points = [
    ("Early KTM", 10.0, 0.85, 25.0, 0.018, P_ktm),
    ("Mid KTM",   10.0, 0.85, 38.0, 0.014, P_ktm),
    ("Late KTM",  10.0, 0.85, 44.0, 0.009, P_ktm),
    ("Mid BTN",   25.0, 0.80, 38.0, 0.014, P_btn),
    ("Late BTN",  25.0, 0.80, 44.0, 0.009, P_btn),
]

print("=" * 110)
print("ALL r=0 CONFIGURATIONS WITH HRX (Kathmandu + Biratnagar)")
print("=" * 110)
print()
print("HRX: Hot side = ALL exhaust, Cold side = ALL ambient, eps = 0.70")
print()

# ---- Show HRX outlet conditions first ----
print("HRX OUTLET CONDITIONS")
print("-" * 100)
print(f"{'':>12} | T_amb | T_exh | T_amb_h | T_exh_c | omega_amb | omega_exh | exh condensed? | omega_exh_c")
print("-" * 100)

hrx_data = {}
for name, T_amb, RH_amb, T_exh, omega_exh, P in test_points:
    omega_amb = humidity_ratio_from_T_RH(T_amb, RH_amb, P)
    T_amb_h = T_amb + eps_HRX * (T_exh - T_amb)
    T_exh_c = T_exh - eps_HRX * (T_exh - T_amb)
    T_dp_exh = dewpoint_from_omega_C(omega_exh, P)
    if T_exh_c < T_dp_exh:
        omega_exh_c = 0.622 * p_sat_water_Pa(T_exh_c) / (P - p_sat_water_Pa(T_exh_c))
        cond = "YES"
    else:
        omega_exh_c = omega_exh
        cond = "no"
    hrx_data[name] = (T_amb, T_exh, T_amb_h, T_exh_c, omega_amb, omega_exh, omega_exh_c, P)
    print(f"{name:>12} | {T_amb:4.0f}C | {T_exh:4.0f}C | {T_amb_h:6.1f}C | {T_exh_c:6.1f}C | {omega_amb:9.5f} | {omega_exh:9.5f} | {cond:>14} | {omega_exh_c:11.5f}")

print()
print("=" * 110)
print("CONFIGURATION DEFINITIONS")
print("=" * 110)
print()
print("Config A (baseline, no HRX):")
print("  Ambient -> Condenser -> Chamber")
print("  Exhaust -> Expelled")
print("  Evaporator: separate ambient source (outdoor unit, T_evap = T_amb - 10K)")
print()
print("Config D1: HRX + exhaust expelled")
print("  Ambient -> [HRX cold] -> preheated -> Condenser -> Chamber")
print("  Exhaust -> [HRX hot]  -> cooled    -> Expelled")
print("  Evaporator: separate ambient source (same as Config A)")
print()
print("Config D2: HRX + exhaust to evaporator")
print("  Ambient -> [HRX cold] -> preheated -> Condenser -> Chamber")
print("  Exhaust -> [HRX hot]  -> cooled    -> Evaporator -> Expelled")
print("  Evaporator source: cooled exhaust (WARMER than raw ambient)")
print("  Benefit: higher T_evap -> better COP, anti-frost")
print()
print("Config D3: HRX + exhaust to condenser (SWAPPED)")
print("  Ambient -> [HRX cold] -> preheated -> Evaporator -> Expelled")
print("  Exhaust -> [HRX hot]  -> cooled    -> Condenser  -> Chamber")
print("  Chamber gets exhaust air (humidity risk!)")
print("  Evaporator: preheated ambient (very warm source -> high COP)")
print()

# ---- COMPUTE ALL CONFIGS ----
print("=" * 110)
print("RESULTS COMPARISON")
print("=" * 110)
print()
header = (f"{'':>12} | {'Config A':^18} | {'D1 (exh expelled)':^18} | "
          f"{'D2 (exh->evap)':^18} | {'D3 (exh->cond)':^24}")
print(header)
print(f"{'':>12} | {'W_comp  COP':^18} | {'W_comp  COP  sav':^18} | "
      f"{'W_comp  COP  sav':^18} | {'W_comp  COP  sav  RH@45':^24}")
print("-" * 110)

for name in hrx_data:
    T_amb, T_exh, T_amb_h, T_exh_c, omega_amb, omega_exh, omega_exh_c, P = hrx_data[name]

    # --- Config A: no HRX ---
    h_out_A = moist_air_enthalpy_kJ_per_kg(T_set, omega_amb)
    h_in_A = moist_air_enthalpy_kJ_per_kg(T_amb, omega_amb)
    Q_A = max(0.01, m_da * (h_out_A - h_in_A))
    T_evap_A = max(-5, T_amb - 10)
    hp_A = compute_heat_pump_cycle(T_evap_A, T_cond_sat, Q_A, hp_cfg)

    # --- D1: preheated amb -> cond, exh expelled, evap = separate ambient ---
    h_in_D1 = moist_air_enthalpy_kJ_per_kg(T_amb_h, omega_amb)
    Q_D1 = max(0.01, m_da * (h_out_A - h_in_D1))
    hp_D1 = compute_heat_pump_cycle(T_evap_A, T_cond_sat, Q_D1, hp_cfg)
    s1 = (hp_A.W_comp_kW - hp_D1.W_comp_kW) / hp_A.W_comp_kW * 100

    # --- D2: preheated amb -> cond, cooled exh -> evap ---
    T_evap_D2 = max(-5, min(T_exh_c - 10, 15))
    hp_D2 = compute_heat_pump_cycle(T_evap_D2, T_cond_sat, Q_D1, hp_cfg)  # same Q_cond as D1
    s2 = (hp_A.W_comp_kW - hp_D2.W_comp_kW) / hp_A.W_comp_kW * 100

    # --- D3: cooled exh -> cond, preheated amb -> evap ---
    h_out_D3 = moist_air_enthalpy_kJ_per_kg(T_set, omega_exh_c)
    h_in_D3 = moist_air_enthalpy_kJ_per_kg(T_exh_c, omega_exh_c)
    Q_D3 = max(0.01, m_da * (h_out_D3 - h_in_D3))
    T_evap_D3 = max(-5, min(T_amb_h - 10, 15))
    hp_D3 = compute_heat_pump_cycle(T_evap_D3, T_cond_sat, Q_D3, hp_cfg)
    s3 = (hp_A.W_comp_kW - hp_D3.W_comp_kW) / hp_A.W_comp_kW * 100
    RH_D3 = RH_from_T_omega(T_set, omega_exh_c, P)

    print(f"{name:>12} | {hp_A.W_comp_kW:.3f} {hp_A.COP:.2f}       | "
          f"{hp_D1.W_comp_kW:.3f} {hp_D1.COP:.2f} {s1:+5.1f}% | "
          f"{hp_D2.W_comp_kW:.3f} {hp_D2.COP:.2f} {s2:+5.1f}% | "
          f"{hp_D3.W_comp_kW:.3f} {hp_D3.COP:.2f} {s3:+5.1f}% {RH_D3:5.1%}")

print()
print("=" * 110)
print("D2 DETAIL: Why cooled exhaust is a better evaporator source")
print("=" * 110)
print()
print(f"{'':>12} | Evap source   | T_source | T_evap | Frost risk?")
print("-" * 70)
for name in hrx_data:
    T_amb, T_exh, T_amb_h, T_exh_c, omega_amb, omega_exh, omega_exh_c, P = hrx_data[name]
    T_evap_A = max(-5, T_amb - 10)
    T_evap_D2 = max(-5, min(T_exh_c - 10, 15))
    T_coil_A = T_evap_A + 3
    T_coil_D2 = T_evap_D2 + 3
    frost_A = "YES" if T_coil_A < 0 else "no"
    frost_D2 = "YES" if T_coil_D2 < 0 else "no"
    print(f"{name:>12} | Config A: amb  | {T_amb:6.1f}C | {T_evap_A:5.1f}C | {frost_A} (T_coil={T_coil_A:.0f}C)")
    print(f"{'':>12} | D2: cooled exh | {T_exh_c:6.1f}C | {T_evap_D2:5.1f}C | {frost_D2} (T_coil={T_coil_D2:.0f}C)")
    print()

print("=" * 110)
print("D3 DETAIL: Humidity analysis - is exhaust air OK for chamber?")
print("=" * 110)
print()
print(f"{'':>12} | omega_amb  RH@45C | omega_exh_c  RH@45C | Which is drier at 45C?")
print("-" * 85)
for name in hrx_data:
    T_amb, T_exh, T_amb_h, T_exh_c, omega_amb, omega_exh, omega_exh_c, P = hrx_data[name]
    RH_amb_45 = RH_from_T_omega(T_set, omega_amb, P)
    RH_exh_45 = RH_from_T_omega(T_set, omega_exh_c, P)
    winner = "AMBIENT" if RH_amb_45 < RH_exh_45 else "EXHAUST"
    print(f"{name:>12} | {omega_amb:.5f} {RH_amb_45:5.1%}  | {omega_exh_c:.5f}  {RH_exh_45:5.1%}  | {winner}")
