#!/usr/bin/env python3
"""
Energy Balance Checker for SAHPD Simulation CSVs
Per-timestep mathematical verification of:

  HP CYCLE      ? Q_cond = Q_evap + W_compxeta_mech, COP, R134a pressures
  PSYCHRO       ? omega consistency, exhaust RH <= 1.0
  DEWPOINT      ? T_evap_coil = T_dp_mix - 5K, T_evap_sat clamped
  TRAY PHYSICS  ? T decreases / RH increases along airflow; X non-increasing over time
  MASS BALANCE  ? sum dm_w_tray_i = dm_w_total; m_w_cum accumulation
  ENERGY ACCUM  ? W_comp_cum and Q_cond_cum accumulate correctly from instantaneous values
  SANITY        ? T_to_chamber ~ T_set, T_exhaust < T_supply, COP range

Usage:
    python checkenergy.py outputs/config_A/kathmandu/baseline_r0.0.csv
    python checkenergy.py outputs/config_A/kathmandu/baseline_r0.7.csv --verbose
    python checkenergy.py outputs/config_B/kathmandu/Ac_10m2_r0.0.csv --p-atm 86123
    python checkenergy.py outputs/config_A/kathmandu/baseline_r0.0.csv --t-set 45 --eta-mech 0.95
"""

import argparse
import sys
import numpy as np
import pandas as pd
from pathlib import Path

try:
    import CoolProp.CoolProp as CP
    COOLPROP_AVAILABLE = True
except ImportError:
    COOLPROP_AVAILABLE = False


# -----------------------------------------------------------------------------
# Standalone psychrometric helpers (no project dependency)
# -----------------------------------------------------------------------------

def sat_pressure_Pa(T_C):
    """Water vapour saturation pressure [Pa] via Magnus formula."""
    T_C = np.asarray(T_C, dtype=float)
    return 610.78 * np.exp(17.27 * T_C / (T_C + 237.3))


def omega_from_T_RH(T_C, RH_frac, P_atm_Pa):
    """Humidity ratio [kg_w/kg_da]."""
    P_ws = sat_pressure_Pa(T_C)
    P_w = RH_frac * P_ws
    return 0.622 * P_w / (P_atm_Pa - P_w)


def dewpoint_C(omega, P_atm_Pa):
    """Dewpoint [ degC] from humidity ratio."""
    P_w = np.maximum(omega * P_atm_Pa / (0.622 + omega), 1e-6)
    ln_r = np.log(P_w / 610.78)
    return 237.3 * ln_r / (17.27 - ln_r)


def moist_enthalpy_kJ(T_C, omega):
    """Moist air specific enthalpy [kJ/kg_da]."""
    return 1.006 * T_C + omega * (2501.0 + 1.86 * T_C)


def infer_P_atm(df) -> float:
    """
    Infer atmospheric pressure from omega_to_chamber + T_to_chamber + RH_to_chamber.
    Formula:  omega = 0.622 x RH x P_ws / (P - RH x P_ws)
          =>  P = RH x P_ws x (0.622/omega + 1)
    """
    sample = df[df['omega_to_chamber'] > 0.001].head(20)
    if sample.empty:
        return 101325.0
    T = sample['T_to_chamber_C'].values
    RH = sample['RH_to_chamber_frac'].values
    omega = sample['omega_to_chamber'].values
    P_ws = sat_pressure_Pa(T)
    P_w = RH * P_ws
    P_vals = P_w * (0.622 / omega + 1.0)
    return float(np.median(P_vals))


def infer_eta_mech(df) -> float:
    """
    Infer eta_mechanical from Q_cond, Q_evap, W_comp.
    First law of HP (refrigerant side):  Q_cond = Q_evap + W_ref
    W_ref = W_comp x eta_mech  =>  eta_mech = (Q_cond - Q_evap) / W_comp
    """
    mask = df['W_comp_kW'] > 0.01
    if not mask.any():
        return 0.95
    eta_vals = (df.loc[mask, 'Q_cond_kW'] - df.loc[mask, 'Q_evap_kW']) / df.loc[mask, 'W_comp_kW']
    return float(np.median(eta_vals))


# -----------------------------------------------------------------------------
# Check result container
# -----------------------------------------------------------------------------

class Check:
    """Accumulates pass/fail results for a single named check."""

    def __init__(self, name: str, desc: str):
        self.name = name
        self.desc = desc
        self.n_pass = 0
        self.n_fail = 0
        self.max_err = 0.0
        self.failures: list[tuple] = []   # (row_idx, time_h, message, error)
        self.skipped = False
        self.skip_reason = ""

    # -- recording ----------------------------------------------------------

    def ok(self, err: float = 0.0):
        self.n_pass += 1
        self.max_err = max(self.max_err, abs(err))

    def fail(self, idx: int, t_h: float, msg: str, err: float = 0.0):
        self.n_fail += 1
        self.max_err = max(self.max_err, abs(err))
        self.failures.append((idx, t_h, msg, err))

    def skip(self, reason: str = ""):
        self.skipped = True
        self.skip_reason = reason

    # -- accessors ----------------------------------------------------------

    @property
    def n_total(self):
        return self.n_pass + self.n_fail

    @property
    def passed(self):
        return (not self.skipped) and self.n_fail == 0

    def status_str(self) -> str:
        if self.skipped:
            return f"SKIP  {self.skip_reason[:50]}"
        tag = "PASS" if self.n_fail == 0 else "FAIL"
        return f"{tag}  {self.n_pass}/{self.n_total} steps  max_err={self.max_err:.5g}"


# -----------------------------------------------------------------------------
# Check functions
# -----------------------------------------------------------------------------

# -- HP Cycle -----------------------------------------------------------------

def chk_hp_first_law(df: pd.DataFrame, eta_mech: float, tol_pct: float = 1.0) -> Check:
    """
    FIRST LAW of HP: Q_cond = Q_evap + W_comp x eta_mech
    (mechanical losses leave the system; refrigerant receives only eta_mech fraction)
    """
    c = Check("HP_FIRST_LAW", f"Q_cond = Q_evap + W_compxeta_mech={eta_mech:.4f}  tol={tol_pct}%")
    mask = df['W_comp_kW'] > 0.01
    if not mask.any():
        c.skip("HP not running")
        return c

    for idx, row in df[mask].iterrows():
        expected = row['Q_evap_kW'] + row['W_comp_kW'] * eta_mech
        err_pct = abs(row['Q_cond_kW'] - expected) / max(row['Q_cond_kW'], 1e-6) * 100
        if err_pct > tol_pct:
            c.fail(idx, row['time_h'],
                   f"Q_cond={row['Q_cond_kW']:.4f} kW  expected={expected:.4f} kW  err={err_pct:.2f}%",
                   err_pct)
        else:
            c.ok(err_pct)
    return c


def chk_cop(df: pd.DataFrame, tol: float = 0.005) -> Check:
    """COP column must equal Q_cond / W_comp exactly."""
    c = Check("COP_VERIFY", f"COP_col = Q_cond / W_comp  tol={tol}")
    mask = df['W_comp_kW'] > 0.01
    if not mask.any():
        c.skip("HP not running")
        return c

    for idx, row in df[mask].iterrows():
        cop_calc = row['Q_cond_kW'] / row['W_comp_kW']
        err = abs(row['COP'] - cop_calc)
        if err > tol:
            c.fail(idx, row['time_h'],
                   f"COP_col={row['COP']:.5f}  COP_calc={cop_calc:.5f}  diff={err:.5f}", err)
        else:
            c.ok(err)
    return c


def chk_r410a_pressures(df: pd.DataFrame, tol_pct: float = 0.5):
    """P_evap and P_cond in CSV must match CoolProp R134a saturation curve."""
    if not COOLPROP_AVAILABLE:
        ce = Check("R134a_P_EVAP", "CoolProp R134a check"); ce.skip("CoolProp not installed")
        cc = Check("R134a_P_COND", "CoolProp R134a check"); cc.skip("CoolProp not installed")
        return ce, cc

    ce = Check("R134a_P_EVAP", f"P_evap matches CoolProp(T_evap, R134a)  tol={tol_pct}%")
    cc = Check("R134a_P_COND", f"P_cond matches CoolProp(T_cond, R134a)  tol={tol_pct}%")
    mask = df['W_comp_kW'] > 0.01
    if not mask.any():
        ce.skip("HP not running"); cc.skip("HP not running")
        return ce, cc

    for idx, row in df[mask].iterrows():
        # Evaporator
        P_e_calc = CP.PropsSI('P', 'T', row['T_evap_C'] + 273.15, 'Q', 0, 'R134a') / 1e5
        err_e = abs(P_e_calc - row['P_evap_bar']) / max(row['P_evap_bar'], 1e-6) * 100
        if err_e > tol_pct:
            ce.fail(idx, row['time_h'],
                    f"T_evap={row['T_evap_C']:.2f} degC  P_csv={row['P_evap_bar']:.4f}bar  P_calc={P_e_calc:.4f}bar  err={err_e:.3f}%",
                    err_e)
        else:
            ce.ok(err_e)

        # Condenser
        P_c_calc = CP.PropsSI('P', 'T', row['T_cond_C'] + 273.15, 'Q', 0, 'R134a') / 1e5
        err_c = abs(P_c_calc - row['P_cond_bar']) / max(row['P_cond_bar'], 1e-6) * 100
        if err_c > tol_pct:
            cc.fail(idx, row['time_h'],
                    f"T_cond={row['T_cond_C']:.2f} degC  P_csv={row['P_cond_bar']:.4f}bar  P_calc={P_c_calc:.4f}bar  err={err_c:.3f}%",
                    err_c)
        else:
            cc.ok(err_c)

    return ce, cc


# -- Psychrometrics ------------------------------------------------------------

def chk_psychro_omega(df: pd.DataFrame, P_atm: float, tol: float = 5e-4) -> Check:
    """omega_to_chamber must match psychro formula from T_to_chamber + RH_to_chamber + P_atm."""
    c = Check("PSYCHRO_OMEGA", f"omega_to_chamber = f(T, RH, P_atm={P_atm:.0f} Pa)  tol={tol:.1e}")
    for idx, row in df.iterrows():
        omega_calc = omega_from_T_RH(row['T_to_chamber_C'], row['RH_to_chamber_frac'], P_atm)
        err = abs(row['omega_to_chamber'] - omega_calc)
        if err > tol:
            c.fail(idx, row['time_h'],
                   f"omega_csv={row['omega_to_chamber']:.6f}  omega_calc={omega_calc:.6f}  diff={err:.2e} kg/kg",
                   err)
        else:
            c.ok(err)
    return c


def chk_exhaust_rh(df: pd.DataFrame, tol: float = 0.005) -> Check:
    """Exhaust RH must never exceed 1.0 (no supersaturation in air leaving dryer)."""
    c = Check("EXHAUST_RH_MAX", "RH_exhaust <= 1.0 (no supersaturation)")
    for idx, row in df.iterrows():
        rh = row['RH_exhaust_frac']
        if rh > 1.0 + tol:
            c.fail(idx, row['time_h'], f"RH_exhaust={rh:.5f} > 1.0", rh - 1.0)
        else:
            c.ok()
    return c


# -- Fixed T_evap with Modulation -----------------------------------------------

def chk_dewpoint_evap(df: pd.DataFrame,
                      DT_sub: float = 5.0, DT_app: float = 3.0,
                      T_min: float = -5.0, T_max: float = 20.0,
                      T_evap_target: float = 5.0,
                      min_dt_evap: float = 5.0,
                      tol_K: float = 0.5):
    """
    Fixed T_evap model with modulation:
      T_evap_sat = T_evap_target (default 5°C)
      T_coil = T_evap_sat + DT_app (default 8°C)
      If T_mix - T_coil < min_dt_evap: modulate T_evap down (min T_evap_min)
    """
    needed = {'T_evap_coil_C_dyn', 'T_evap_C', 'r_recirc_actual', 'T_mix_C'}
    c_coil = Check("EVAP_COIL_T", f"T_coil = T_evap + {DT_app}K  tol={tol_K}K")
    c_sat  = Check("EVAP_SAT_T",  f"T_evap in [{T_min}, {T_evap_target}]°C with modulation  tol={tol_K}K")

    if not needed.issubset(df.columns):
        missing = needed - set(df.columns)
        c_coil.skip(f"Missing cols: {missing}")
        c_sat.skip(f"Missing cols: {missing}")
        return c_coil, c_sat

    mask = (df['r_recirc_actual'] > 0.0) & (df['bypass_mode'] == 'evap') & (df['W_comp_kW'] > 0.01)
    rows = df[mask]
    if rows.empty:
        c_coil.skip("No recirc 'evap' mode rows with HP running")
        c_sat.skip("No recirc 'evap' mode rows with HP running")
        return c_coil, c_sat

    for idx, row in rows.iterrows():
        T_coil_csv = row['T_evap_coil_C_dyn']
        T_sat_csv = row['T_evap_C']

        # Coil = T_evap + DT_approach
        err_coil = abs(T_coil_csv - (T_sat_csv + DT_app))
        if err_coil > tol_K:
            c_coil.fail(idx, row['time_h'],
                        f"T_coil={T_coil_csv:.3f}  T_evap+DT_app={T_sat_csv + DT_app:.3f}  err={err_coil:.3f}K",
                        err_coil)
        else:
            c_coil.ok(err_coil)

        # T_evap_sat should be in [T_min, T_evap_target]
        if T_sat_csv < T_min - tol_K or T_sat_csv > T_evap_target + tol_K:
            c_sat.fail(idx, row['time_h'],
                       f"T_evap={T_sat_csv:.3f} outside [{T_min}, {T_evap_target}]°C",
                       max(T_sat_csv - T_evap_target, T_min - T_sat_csv))
        else:
            c_sat.ok(0.0)

    return c_coil, c_sat


# -- Tray Physics --------------------------------------------------------------

def chk_tray_T_monotone(df: pd.DataFrame, n_trays: int = 10, tol_K: float = 0.05) -> Check:
    """
    Air temperature must decrease monotonically as air flows through the trays.
    Forward flow:  T_inlet > T_tray_0_out > T_tray_1_out > ... > T_tray_9_out
    Reverse flow:  T_inlet > T_tray_9_out > T_tray_8_out > ... > T_tray_0_out
    """
    c = Check("TRAY_T_MONO", f"T decreases along airflow through all {n_trays} trays  tol={tol_K}K")
    T_cols_all = [f'T_tray_{i}_out_C' for i in range(n_trays)]

    for idx, row in df.iterrows():
        direction = str(row.get('flow_direction', 'forward'))
        if direction == 'forward':
            T_seq = [row['T_to_chamber_C']] + [row[c] for c in T_cols_all]
        else:
            T_seq = [row['T_to_chamber_C']] + [row[f'T_tray_{i}_out_C'] for i in range(n_trays-1, -1, -1)]

        viols = []
        max_v = 0.0
        for i in range(len(T_seq) - 1):
            delta = T_seq[i+1] - T_seq[i]   # should be <= 0
            if delta > tol_K:
                label = T_cols_all[i] if direction == 'forward' else T_cols_all[n_trays-1-i]
                viols.append(f"{label}: +{delta:.3f}K")
                max_v = max(max_v, delta)

        if viols:
            c.fail(idx, row['time_h'], "  |  ".join(viols), max_v)
        else:
            c.ok()
    return c


def chk_tray_RH_monotone(df: pd.DataFrame, n_trays: int = 10, tol: float = 0.005) -> Check:
    """
    RH must increase as air flows through the trays (air gains moisture from product).
    Forward flow:  RH_inlet < RH_tray_0_out < RH_tray_1_out < ...
    """
    c = Check("TRAY_RH_MONO", f"RH increases along airflow through all {n_trays} trays  tol={tol}")
    RH_cols_all = [f'RH_tray_{i}_out_frac' for i in range(n_trays)]

    for idx, row in df.iterrows():
        direction = str(row.get('flow_direction', 'forward'))
        if direction == 'forward':
            RH_seq = [row['RH_to_chamber_frac']] + [row[c] for c in RH_cols_all]
        else:
            RH_seq = [row['RH_to_chamber_frac']] + [row[f'RH_tray_{i}_out_frac'] for i in range(n_trays-1, -1, -1)]

        viols = []
        max_v = 0.0
        for i in range(len(RH_seq) - 1):
            delta = RH_seq[i] - RH_seq[i+1]   # should be <= 0 (RH increases)
            if delta > tol:
                label = RH_cols_all[i] if direction == 'forward' else RH_cols_all[n_trays-1-i]
                viols.append(f"{label}: fell by {delta:.4f}")
                max_v = max(max_v, delta)

        if viols:
            c.fail(idx, row['time_h'], "  |  ".join(viols), max_v)
        else:
            c.ok()
    return c


def chk_X_monotone_time(df: pd.DataFrame, n_trays: int = 10) -> Check:
    """
    Moisture content X_tray_i must never increase over time
    (product can only lose moisture, not gain it).
    """
    c = Check("X_MONO_TIME", "X_tray_i non-increasing over time for all trays")
    times = df['time_h'].values
    for i in range(n_trays):
        col = f'X_tray_{i}'
        if col not in df.columns:
            continue
        X = df[col].values
        for t_idx in range(1, len(X)):
            delta = X[t_idx] - X[t_idx - 1]
            if delta > 1e-3:
                c.fail(t_idx, times[t_idx],
                       f"{col}: X={X[t_idx]:.7f} > X_prev={X[t_idx-1]:.7f}  ?={delta:.2e}",
                       delta)
            else:
                c.ok(0.0)
    return c


# -- Mass Balance --------------------------------------------------------------

def chk_dm_sum(df: pd.DataFrame, n_trays: int = 10, tol_pct: float = 1.0) -> Check:
    """
    dm_w_total must equal the sum of per-tray water removals.
    dm_w_total [kg/step] = sum_{i=0}^{9} dm_w_tray_i
    """
    c = Check("MASS_BAL_TRAY", f"dm_w_total = sum dm_w_tray_i  tol={tol_pct}%")
    dm_cols = [f'dm_w_tray_{i}_kg' for i in range(n_trays) if f'dm_w_tray_{i}_kg' in df.columns]

    for idx, row in df.iterrows():
        dm_total = row['dm_w_total_kg']
        dm_sum   = sum(row[c_] for c_ in dm_cols)
        denom    = max(abs(dm_total), abs(dm_sum), 1e-10)
        err_pct  = abs(dm_total - dm_sum) / denom * 100
        if err_pct > tol_pct:
            c.fail(idx, row['time_h'],
                   f"dm_total={dm_total:.7f} kg  sumtray={dm_sum:.7f} kg  err={err_pct:.2f}%",
                   err_pct)
        else:
            c.ok(err_pct)
    return c


def chk_mw_cum(df: pd.DataFrame, tol_kg: float = 1e-4) -> Check:
    """
    Cumulative water mass must grow by exactly dm_w_total each step.
    m_w_cum[t] = m_w_cum[t-1] + dm_w_total[t]
    """
    c = Check("MW_CUM_ACCUM", f"m_w_cum[t] = m_w_cum[t-1] + dm_w_total[t]  tol={tol_kg} kg")
    for i in range(1, len(df)):
        expected = df['m_w_cum_kg'].iloc[i-1] + df['dm_w_total_kg'].iloc[i]
        got      = df['m_w_cum_kg'].iloc[i]
        err      = abs(got - expected)
        if err > tol_kg:
            c.fail(i, df['time_h'].iloc[i],
                   f"m_w_cum={got:.6f}  expected={expected:.6f}  diff={err:.2e} kg", err)
        else:
            c.ok(err)
    return c


# -- Energy Accumulation -------------------------------------------------------

def chk_wcomp_cum(df: pd.DataFrame, tol_kWh: float = 1e-5) -> Check:
    """
    W_comp_cum must integrate W_comp x dt/3600.
    W_comp_cum[t] = W_comp_cum[t-1] + W_comp[t] x (dt_s / 3600)
    """
    c = Check("WCOMP_CUM", f"W_comp_cum[t] = W_comp_cum[t-1] + W_compxdt/3600  tol={tol_kWh} kWh")
    for i in range(1, len(df)):
        dt_h     = (df['time_s'].iloc[i] - df['time_s'].iloc[i-1]) / 3600.0
        expected = df['W_comp_cum_kWh'].iloc[i-1] + df['W_comp_kW'].iloc[i] * dt_h
        got      = df['W_comp_cum_kWh'].iloc[i]
        err      = abs(got - expected)
        if err > tol_kWh:
            c.fail(i, df['time_h'].iloc[i],
                   f"W_comp_cum={got:.6f}  expected={expected:.6f}  diff={err:.2e} kWh", err)
        else:
            c.ok(err)
    return c


def chk_qcond_cum(df: pd.DataFrame, tol_kWh: float = 1e-5) -> Check:
    """
    Q_cond_cum must integrate Q_cond_kW x dt/3600.
    Q_cond_cum[t] = Q_cond_cum[t-1] + Q_cond_kW[t] x (dt_s / 3600)
    """
    c = Check("QCOND_CUM", f"Q_cond_cum[t] = Q_cond_cum[t-1] + Q_condxdt/3600  tol={tol_kWh} kWh")
    for i in range(1, len(df)):
        dt_h     = (df['time_s'].iloc[i] - df['time_s'].iloc[i-1]) / 3600.0
        expected = df['Q_cond_cum_kWh'].iloc[i-1] + df['Q_cond_kW'].iloc[i] * dt_h
        got      = df['Q_cond_cum_kWh'].iloc[i]
        err      = abs(got - expected)
        if err > tol_kWh:
            c.fail(i, df['time_h'].iloc[i],
                   f"Q_cond_cum={got:.6f}  expected={expected:.6f}  diff={err:.2e} kWh", err)
        else:
            c.ok(err)
    return c


# -- Sanity Checks -------------------------------------------------------------

def chk_T_to_chamber(df: pd.DataFrame, T_set: float = 45.0, tol_K: float = 0.5) -> Check:
    """
    When HP is running (non-bypass), supply air to chamber must be ~ T_set.
    Large deviations indicate a control error.
    """
    c = Check("T_SUPPLY_SET", f"T_to_chamber ~ {T_set} degC when HP on (non-bypass)  tol={tol_K}K")
    # HP is actively heating in both 'none' (open-loop) and 'evap' (recirc) modes
    mask = (df['W_comp_kW'] > 0.01) & (df['bypass_mode'].isin(['none', 'evap']))
    if not mask.any():
        c.skip("No HP-on non-bypass rows")
        return c
    for idx, row in df[mask].iterrows():
        err = abs(row['T_to_chamber_C'] - T_set)
        if err > tol_K:
            c.fail(idx, row['time_h'],
                   f"T_supply={row['T_to_chamber_C']:.3f} degC  T_set={T_set} degC  diff={err:.3f}K", err)
        else:
            c.ok(err)
    return c


def chk_T_exhaust_lt_supply(df: pd.DataFrame, tol_K: float = 0.1) -> Check:
    """
    Exhaust air must be cooler than supply air (dryer consumes enthalpy to evaporate moisture;
    the wet-bulb temperature at the exit is always below the dry-bulb inlet temperature).
    """
    c = Check("T_EXH_LT_SUP", "T_exhaust < T_to_chamber (dryer cools supply air)")
    for idx, row in df.iterrows():
        delta = row['T_exhaust_C'] - row['T_to_chamber_C']
        if delta > tol_K:
            c.fail(idx, row['time_h'],
                   f"T_exhaust={row['T_exhaust_C']:.3f} degC > T_supply={row['T_to_chamber_C']:.3f} degC  ?T=+{delta:.3f}K",
                   delta)
        else:
            c.ok()
    return c


def chk_cop_range(df: pd.DataFrame, COP_min: float = 1.5, COP_max: float = 50.0) -> Check:
    """COP must be in a physically plausible range for a vapour-compression HP.

    Upper bound is 50 to accommodate Config C/E (solar-assisted evaporator):
    when T_evap approaches T_cond (small temperature lift), COP can legitimately
    reach 40+ (e.g., T_evap=50C, T_cond=55C => Carnot COP = 328/5 = 65.6).
    The old bug (T_evap > T_cond) gave COP > 200 and is still caught.
    """
    c = Check("COP_RANGE", f"COP in [{COP_min}, {COP_max}] when HP running")
    mask = df['W_comp_kW'] > 0.01
    if not mask.any():
        c.skip("HP not running")
        return c
    for idx, row in df[mask].iterrows():
        cop = row['COP']
        if cop < COP_min or cop > COP_max:
            c.fail(idx, row['time_h'],
                   f"COP={cop:.4f} outside [{COP_min}, {COP_max}]",
                   max(COP_min - cop, cop - COP_max, 0))
        else:
            c.ok()
    return c


def chk_pressure_ratio(df: pd.DataFrame, PR_max: float = 8.0) -> Check:
    """Pressure ratio P_cond / P_evap must not exceed HP compressor design limit."""
    c = Check("PRESS_RATIO", f"P_cond/P_evap <= {PR_max}")
    mask = df['W_comp_kW'] > 0.01
    if not mask.any():
        c.skip("HP not running")
        return c
    for idx, row in df[mask].iterrows():
        PR = row['P_cond_bar'] / max(row['P_evap_bar'], 1e-6)
        if PR > PR_max:
            c.fail(idx, row['time_h'],
                   f"PR={PR:.3f} (P_cond={row['P_cond_bar']:.3f} / P_evap={row['P_evap_bar']:.3f} bar)", PR)
        else:
            c.ok(0.0)
    return c


# -----------------------------------------------------------------------------
# Run all checks and print report
# -----------------------------------------------------------------------------

CATEGORIES = {
    "HP_FIRST_LAW": "HP Cycle",
    "COP_VERIFY":   "HP Cycle",
    "R134a_P_EVAP": "HP Cycle",
    "R134a_P_COND": "HP Cycle",
    "PSYCHRO_OMEGA":"Psychrometrics",
    "EXHAUST_RH_MAX":"Psychrometrics",
    "EVAP_COIL_T":  "Dewpoint Physics",
    "EVAP_SAT_T":   "Dewpoint Physics",
    "TRAY_T_MONO":  "Tray Physics",
    "TRAY_RH_MONO": "Tray Physics",
    "X_MONO_TIME":  "Tray Physics",
    "MASS_BAL_TRAY":"Mass Balance",
    "MW_CUM_ACCUM": "Mass Balance",
    "WCOMP_CUM":    "Energy Accum.",
    "QCOND_CUM":    "Energy Accum.",
    "T_SUPPLY_SET": "Sanity",
    "T_EXH_LT_SUP": "Sanity",
    "COP_RANGE":    "Sanity",
    "PRESS_RATIO":  "Sanity",
}

W = 70  # line width


def run_checks(csv_path: Path,
               verbose: bool = False,
               P_atm_Pa: float = None,
               eta_mech: float = None,
               T_set: float = 45.0,
               n_trays: int = 10) -> list[Check]:

    print(f"\n{'='*W}")
    print(f"  SAHPD ENERGY BALANCE CHECKER")
    print(f"  File : {csv_path.name}")
    print(f"  Path : {csv_path.parent}")
    print(f"{'='*W}\n")

    df = pd.read_csv(csv_path)
    n_rows = len(df)
    n_cols = len(df.columns)
    print(f"  Loaded  : {n_rows} timesteps x {n_cols} columns")

    # Infer parameters
    P_atm = P_atm_Pa or infer_P_atm(df)
    eta   = eta_mech or infer_eta_mech(df)

    dt_s = df['time_s'].diff().median() if len(df) > 1 else 60.0
    print(f"  P_atm   : {P_atm:.0f} Pa  ({P_atm/1e5:.4f} bar)  [{'given' if P_atm_Pa else 'inferred'}]")
    print(f"  eta_mech  : {eta:.5f}  [{'given' if eta_mech else 'inferred'}]")
    print(f"  T_set   : {T_set} degC")
    print(f"  dt      : {dt_s:.0f} s")
    print(f"  n_trays : {n_trays}\n")

    # -- collect all checks ------------------------------------------------

    checks: list[Check] = []

    # HP Cycle
    checks.append(chk_hp_first_law(df, eta))
    checks.append(chk_cop(df))
    ce, cc = chk_r410a_pressures(df)
    checks += [ce, cc]

    # Psychrometrics
    checks.append(chk_psychro_omega(df, P_atm))
    checks.append(chk_exhaust_rh(df))

    # Dewpoint-driven T_evap
    c_coil, c_sat = chk_dewpoint_evap(df)
    checks += [c_coil, c_sat]

    # Tray physics
    checks.append(chk_tray_T_monotone(df, n_trays))
    checks.append(chk_tray_RH_monotone(df, n_trays))
    checks.append(chk_X_monotone_time(df, n_trays))

    # Mass balance
    checks.append(chk_dm_sum(df, n_trays))
    checks.append(chk_mw_cum(df))

    # Energy accumulation
    checks.append(chk_wcomp_cum(df))
    checks.append(chk_qcond_cum(df))

    # Sanity
    checks.append(chk_T_to_chamber(df, T_set))
    checks.append(chk_T_exhaust_lt_supply(df))
    checks.append(chk_cop_range(df))
    checks.append(chk_pressure_ratio(df))

    # -- print results table -----------------------------------------------

    print(f"{'-'*W}")
    print(f"  {'CATEGORY':<18} {'CHECK':<22} {'RESULT'}")
    print(f"{'-'*W}")

    for chk in checks:
        cat = CATEGORIES.get(chk.name, "Other")
        print(f"  {cat:<18} {chk.name:<22} {chk.status_str()}")

    # -- summary -----------------------------------------------------------

    n_pass = sum(1 for x in checks if x.passed)
    n_fail = sum(1 for x in checks if x.n_fail > 0)
    n_skip = sum(1 for x in checks if x.skipped)

    print(f"{'-'*W}")
    overall = "ALL PASS [OK]" if n_fail == 0 else f"{n_fail} CHECK(S) FAILED [FAIL]"
    print(f"\n  SUMMARY  {n_pass} PASS  |  {n_fail} FAIL  |  {n_skip} SKIP    ->  {overall}\n")

    # -- verbose failure details -------------------------------------------

    if verbose:
        failed = [x for x in checks if x.n_fail > 0]
        if not failed:
            print("  No failures to detail.\n")
        else:
            print(f"{'-'*W}")
            print(f"  FAILURE DETAILS (first 10 per check)")
            print(f"{'-'*W}")
            for chk in failed:
                print(f"\n  [{chk.name}]  {chk.desc}")
                for i, (idx, t, msg, _) in enumerate(chk.failures):
                    if i >= 10:
                        print(f"    ... +{len(chk.failures)-10} more failures")
                        break
                    print(f"    row {idx:>5}  t={t:>7.3f}h  {msg}")
            print()

    return checks


# -----------------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Per-timestep energy balance checker for SAHPD simulation CSVs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('csv_file', help='Path to simulation CSV')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed failure info (first 10 per check)')
    parser.add_argument('--p-atm', type=float, default=None,
                        metavar='Pa',
                        help='Atmospheric pressure [Pa] (default: inferred from data)')
    parser.add_argument('--eta-mech', type=float, default=None,
                        metavar='FLOAT',
                        help='Compressor mechanical efficiency (default: inferred from data)')
    parser.add_argument('--t-set', type=float, default=45.0,
                        metavar='DEG_C',
                        help='Dryer set-point temperature [ degC] (default: 45.0)')
    parser.add_argument('--n-trays', type=int, default=10,
                        help='Number of trays (default: 10)')
    args = parser.parse_args()

    path = Path(args.csv_file)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    results = run_checks(
        csv_path=path,
        verbose=args.verbose,
        P_atm_Pa=args.p_atm,
        eta_mech=args.eta_mech,
        T_set=args.t_set,
        n_trays=args.n_trays,
    )

    n_fail = sum(1 for x in results if x.n_fail > 0)
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == '__main__':
    main()
