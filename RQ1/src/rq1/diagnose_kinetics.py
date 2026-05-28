"""
Diagnostic: Check K_eff calculation
====================================

This script tests the kinetics calculation to see what K_eff values
are being produced for typical chamber conditions.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import KineticsConfig
from rq1.kinetics import keff_from_state, K_eff_from_T_RH

# Create default kinetics config
cfg = KineticsConfig()

print("="*70)
print("KINETICS DIAGNOSTICS")
print("="*70)

print("\nConfiguration:")
print(f"  mode: {cfg.mode}")
print(f"  phase2_models_root: {cfg.phase2_models_root}")
print(f"  use_knb_table: {cfg.use_knb_table}")
print(f"  K_ref_1_per_s: {cfg.K_ref_1_per_s}")
print(f"  k_eff_min: {cfg.k_eff_min}")
print(f"  k_eff_max: {cfg.k_eff_max}")

print("\n" + "="*70)
print("TEST: Chamber inlet conditions (T=50°C, RH=8%)")
print("="*70)

# Typical chamber inlet: 50°C, 8% RH
T_in_C = 50.0
RH_in_frac = 0.08

print(f"\nInput: T = {T_in_C}°C, RH = {RH_in_frac:.2%}")

# Method 1: keff_from_state (uses phase2 or fallback)
k_eff_1 = keff_from_state(T_in_C, RH_in_frac, cfg)
print(f"\nMethod 1 (keff_from_state): K_eff = {k_eff_1:.6e} s⁻¹")

# Method 2: K_eff_from_T_RH (simple formula)
k_eff_2 = K_eff_from_T_RH(T_in_C, RH_in_frac, cfg)
print(f"Method 2 (K_eff_from_T_RH): K_eff = {k_eff_2:.6e} s⁻¹")

# Calculate drying rate
m_p_tray = 1.0  # kg dry mass per tray
X_db = 6.5  # Initial moisture
X_eq_db = 0.0
dt_s = 60.0

dX_per_step_1 = k_eff_1 * (X_db - X_eq_db) * dt_s
dX_per_step_2 = k_eff_2 * (X_db - X_eq_db) * dt_s

print("\n" + "="*70)
print("DRYING RATE ESTIMATE")
print("="*70)
print(f"\nFor tray with X = {X_db} kg/kg, dt = {dt_s}s:")
print(f"  Method 1: dX = {dX_per_step_1:.6f} kg/kg per step")
print(f"  Method 2: dX = {dX_per_step_2:.6f} kg/kg per step")

# Estimate time to dry from 6.5 to 0.1
X_target = 0.1
steps_needed_1 = (X_db - X_target) / dX_per_step_1 if dX_per_step_1 > 0 else float('inf')
steps_needed_2 = (X_db - X_target) / dX_per_step_2 if dX_per_step_2 > 0 else float('inf')

time_hours_1 = steps_needed_1 * dt_s / 3600.0
time_hours_2 = steps_needed_2 * dt_s / 3600.0

print(f"\nEstimated time to dry (6.5 → 0.1):")
print(f"  Method 1: {time_hours_1:.1f} hours")
print(f"  Method 2: {time_hours_2:.1f} hours")

print("\n" + "="*70)
print("EXPECTED VS ACTUAL")
print("="*70)
print(f"\nYour baseline result: 15.7 hours")
print(f"Current result:       24.3 hours")
print(f"\nRatio: {24.3 / 15.7:.2f}× slower")
print(f"K_eff should be: {k_eff_1 * (24.3 / 15.7):.6e} s⁻¹ to match baseline")

# Test with different RH values
print("\n" + "="*70)
print("K_eff vs RH (at T=50°C)")
print("="*70)
print(f"\n{'RH %':>6} | {'K_eff (s⁻¹)':>15} | {'Time (h)':>10}")
print("-"*40)

for rh_pct in [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95]:
    rh_frac = rh_pct / 100.0
    k = keff_from_state(T_in_C, rh_frac, cfg)
    dX = k * (X_db - X_eq_db) * dt_s
    if dX > 0:
        time_h = (X_db - X_target) / dX * dt_s / 3600.0
    else:
        time_h = float('inf')
    print(f"{rh_pct:>6} | {k:>15.6e} | {time_h:>10.1f}")

print("\n" + "="*70)