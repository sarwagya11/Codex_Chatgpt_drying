"""
Diagnostic: Check Air Capacity Limiting
========================================

This shows how much the air capacity limit is restricting drying.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "src"))

from rq1.config_solar_hp import KineticsConfig
from rq1.kinetics import compute_dm_w_kinetic_first_order, compute_dm_w_air_capacity
from rq1.psychro import humidity_ratio_from_T_RH

# Default config
cfg = KineticsConfig()

# Chamber conditions
T_in_C = 50.0  # °C
RH_in_pct = 8.0  # %
RH_in_frac = RH_in_pct / 100.0

# Tray parameters
m_p_tray = 1.0  # kg dry mass
X_db = 6.5  # kg water / kg dry
X_eq_db = 0.0
dt_s = 60.0

# Air flow
m_da = 0.1186  # kg/s

# Calculate omega
omega_in = humidity_ratio_from_T_RH(T_in_C, RH_in_frac)

print("="*70)
print("AIR CAPACITY LIMITING DIAGNOSTIC")
print("="*70)

print(f"\nChamber Conditions:")
print(f"  T_in = {T_in_C}°C")
print(f"  RH_in = {RH_in_pct}%")
print(f"  omega_in = {omega_in:.6f} kg water/kg dry air")
print(f"  m_da = {m_da} kg/s")
print(f"  dt = {dt_s} s")

print(f"\nProduct:")
print(f"  m_p_dry = {m_p_tray} kg")
print(f"  X = {X_db} kg/kg")

print("\n" + "="*70)
print("MOISTURE REMOVAL LIMITS")
print("="*70)

# Kinetic limit
dm_w_kin = compute_dm_w_kinetic_first_order(
    X_db=X_db, 
    X_eq_db=X_eq_db, 
    T_in_C=T_in_C, 
    RH_in_frac=RH_in_frac,
    dt_s=dt_s, 
    cfg=cfg, 
    m_p_dry_kg=m_p_tray,
    time_s=0.0,
)

print(f"\n1. KINETIC LIMIT (dm_w_kin):")
print(f"   dm_w_kin = {dm_w_kin:.6f} kg")
print(f"   Rate = {dm_w_kin/dt_s*3600:.3f} kg/hour")

# Air capacity limit
dm_w_air_max = compute_dm_w_air_capacity(
    T_in_C=T_in_C,
    omega_in=omega_in,
    m_da_kg_per_s=m_da,
    dt_s=dt_s,
    cfg=cfg,
    h_fg_kJ_per_kg=2400.0,
)

print(f"\n2. AIR CAPACITY LIMIT (dm_w_air_max):")
print(f"   dm_w_air_max = {dm_w_air_max:.6f} kg")
print(f"   Rate = {dm_w_air_max/dt_s*3600:.3f} kg/hour")

# Product limit
max_removable = max(0.0, (X_db - X_eq_db) * m_p_tray)
print(f"\n3. PRODUCT LIMIT (max_removable):")
print(f"   max_removable = {max_removable:.3f} kg")

# Actual removal
dm_w_actual = min(dm_w_kin, dm_w_air_max, max_removable)

print("\n" + "="*70)
print("ACTUAL REMOVAL")
print("="*70)
print(f"\ndm_w = min(kinetic, air, product)")
print(f"     = min({dm_w_kin:.6f}, {dm_w_air_max:.6f}, {max_removable:.3f})")
print(f"     = {dm_w_actual:.6f} kg")

# Which limit is active?
if dm_w_actual == dm_w_kin:
    limiting = "KINETIC"
elif dm_w_actual == dm_w_air_max:
    limiting = "AIR CAPACITY ← THIS IS THE BOTTLENECK!"
else:
    limiting = "PRODUCT"

print(f"\nLimiting factor: {limiting}")

# Reduction factor
reduction = dm_w_actual / dm_w_kin if dm_w_kin > 0 else 0
print(f"Reduction: {reduction:.1%} of kinetic potential")
print(f"Slowdown: {1/reduction:.1f}× slower than kinetics predicts")

# Drying time estimate
if dm_w_actual > 0:
    steps_to_dry = (X_db - 0.1) / (dm_w_actual / m_p_tray)
    time_hours = steps_to_dry * dt_s / 3600.0
    print(f"\nEstimated drying time: {time_hours:.1f} hours")
else:
    print(f"\nEstimated drying time: INFINITE (dm_w = 0)")

print("\n" + "="*70)
print("AIR CAPACITY SETTINGS")
print("="*70)
print(f"\nenable_air_limit: {cfg.enable_air_limit}")
print(f"RH_out_max_frac: {cfg.RH_out_max_frac}")
print(f"min_domega_drive: {cfg.min_domega_drive}")

if cfg.enable_air_limit:
    print("\n⚠️  AIR LIMITING IS ENABLED!")
    print("This is restricting drying to prevent outlet RH > {:.0%}".format(cfg.RH_out_max_frac))
else:
    print("\n✓ Air limiting is disabled (should use kinetic rate)")

print("\n" + "="*70)