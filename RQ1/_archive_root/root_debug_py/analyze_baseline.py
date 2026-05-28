"""Comprehensive analysis of baseline_r0.8.csv"""
import pandas as pd
import numpy as np

csv_path = r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_A\kathmandu\baseline_r0.8.csv"
df = pd.read_csv(csv_path)

print("=" * 80)
print("ANALYSIS OF baseline_r0.8.csv")
print(f"Total rows: {len(df)}, time range: {df['time_h'].min():.4f} - {df['time_h'].max():.4f} h")
print(f"Timestep: {df['time_s'].diff().dropna().median():.0f} s = {df['time_h'].diff().dropna().median()*60:.2f} min")
print("=" * 80)

# ─────────────────────────────────────────────────────────────────────────────
# 1. TIME MARKERS: when does each tray first reach X <= 0.10?
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("1. TIME MARKERS  (first time X <= 0.10)")
print("=" * 80)

tray_cols = [f"X_tray_{i}" for i in range(5)]
for col in tray_cols:
    mask = df[col] <= 0.10
    if mask.any():
        idx = mask.idxmax()
        print(f"  {col:15s}  reaches X<=0.10 at time_h = {df.loc[idx, 'time_h']:.4f}  (X = {df.loc[idx, col]:.6f})")
    else:
        print(f"  {col:15s}  NEVER reaches X<=0.10  (final X = {df[col].iloc[-1]:.6f})")

print()
sec_cols = ["X_tray_0_sec_0", "X_tray_0_sec_2", "X_tray_4_sec_0", "X_tray_4_sec_2"]
for col in sec_cols:
    if col not in df.columns:
        print(f"  {col:25s}  COLUMN NOT FOUND")
        continue
    mask = df[col] <= 0.10
    if mask.any():
        idx = mask.idxmax()
        print(f"  {col:25s}  reaches X<=0.10 at time_h = {df.loc[idx, 'time_h']:.4f}  (X = {df.loc[idx, col]:.6f})")
    else:
        print(f"  {col:25s}  NEVER reaches X<=0.10  (final X = {df[col].iloc[-1]:.6f})")

# ─────────────────────────────────────────────────────────────────────────────
# 2. BYPASS TRANSITION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("2. BYPASS TRANSITION")
print("=" * 80)

modes = df['bypass_mode'].values
transitions = []
for i in range(1, len(modes)):
    if modes[i] != modes[i - 1]:
        transitions.append((df['time_h'].iloc[i], modes[i - 1], modes[i]))

print(f"  Total number of mode transitions: {len(transitions)}")
if transitions:
    first_to_bypass = [(t, f, to) for t, f, to in transitions if to == 'bypass']
    if first_to_bypass:
        t0, fr, to = first_to_bypass[0]
        print(f"  First switch to 'bypass': time_h = {t0:.4f}  (from '{fr}')")
    else:
        print(f"  No switch to 'bypass' found")

    # Check for chattering
    if len(transitions) > 2:
        print(f"  WARNING: {len(transitions)} transitions detected - CHATTERING present!")
    else:
        print(f"  No chattering (clean transition)")

    print("\n  All transitions:")
    for i, (t, fr, to) in enumerate(transitions):
        print(f"    [{i}] time_h={t:.4f}: '{fr}' -> '{to}'")
else:
    print("  No transitions found (mode is constant)")

# ─────────────────────────────────────────────────────────────────────────────
# 3. HP TRANSITION SPIKE (6-8h window)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("3. HP TRANSITION SPIKE (6-8h window)")
print("=" * 80)

def get_nearest_row(t_target):
    idx = (df['time_h'] - t_target).abs().idxmin()
    return df.loc[idx]

probe_times = [6.0, 6.5, 7.0, 7.5, 8.0]
print(f"\n  {'time_h':>8s}  {'W_comp_kW':>11s}  {'Q_cond_kW':>11s}  {'COP':>8s}  {'T_evap_C':>10s}")
print("  " + "-" * 60)
for t in probe_times:
    r = get_nearest_row(t)
    print(f"  {r['time_h']:8.4f}  {r['W_comp_kW']:11.4f}  {r['Q_cond_kW']:11.4f}  {r['COP']:8.4f}  {r['T_evap_C']:10.4f}")

window = df[(df['time_h'] >= 6.0) & (df['time_h'] <= 8.0)]
print(f"\n  W_comp_kW in 6-8h window:  min = {window['W_comp_kW'].min():.4f},  max = {window['W_comp_kW'].max():.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. TEMPERATURE PROFILES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("4. TEMPERATURE PROFILES")
print("=" * 80)

t_probes = [0.5, 2.0, 4.0, 6.0, 8.0, 10.0, 13.0]
print(f"\n  {'time_h':>8s}  {'T_exhaust_C':>12s}  {'T_to_chamber':>13s}  {'T_tray0_out':>12s}  {'T_tray4_out':>12s}")
print("  " + "-" * 68)
for t in t_probes:
    r = get_nearest_row(t)
    t0out = r.get('T_tray_0_out_C', float('nan'))
    t4out = r.get('T_tray_4_out_C', float('nan'))
    print(f"  {r['time_h']:8.4f}  {r['T_exhaust_C']:12.4f}  {r['T_to_chamber_C']:13.4f}  {t0out:12.4f}  {t4out:12.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. RH PROFILES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("5. RH PROFILES")
print("=" * 80)

print(f"\n  {'time_h':>8s}  {'RH_exhaust':>11s}  {'RH_to_chamb':>12s}")
print("  " + "-" * 38)
for t in t_probes:
    r = get_nearest_row(t)
    print(f"  {r['time_h']:8.4f}  {r['RH_exhaust_frac']:11.6f}  {r['RH_to_chamber_frac']:12.6f}")

max_rh_idx = df['RH_to_chamber_frac'].idxmax()
print(f"\n  Chamber inlet RH max: {df.loc[max_rh_idx, 'RH_to_chamber_frac']:.6f} at time_h = {df.loc[max_rh_idx, 'time_h']:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. ENERGY CHECK
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("6. ENERGY CHECK")
print("=" * 80)

last = df.iloc[-1]
W_comp_cum = last['W_comp_cum_kWh']
W_fan_cum  = last['W_fan_cum_kWh']
Q_cond_cum = last['Q_cond_cum_kWh']
m_w_cum    = last['m_w_cum_kg']

print(f"  W_comp_cum_kWh (end)  = {W_comp_cum:.4f}")
print(f"  W_fan_cum_kWh  (end)  = {W_fan_cum:.4f}")
print(f"  Q_cond_cum_kWh (end)  = {Q_cond_cum:.4f}")
print(f"  m_w_cum_kg     (end)  = {m_w_cum:.4f}")

if m_w_cum > 0:
    SEC = (W_comp_cum + W_fan_cum) / m_w_cum
    print(f"\n  SEC = (W_comp + W_fan) / m_w_cum = {SEC:.4f} kWh/kg")
else:
    print(f"\n  SEC: cannot compute (m_w_cum = 0)")

if W_comp_cum > 0:
    ratio = Q_cond_cum / W_comp_cum
    print(f"  Q_cond_cum / W_comp_cum = {ratio:.4f}  (should approximate COP)")
else:
    print(f"  Q_cond_cum / W_comp_cum: cannot compute")

# Latent heat check
# m_water * 2400 kJ/kg / 3600 = theoretical minimum kWh
latent_min_kWh = m_w_cum * 2400.0 / 3600.0
print(f"\n  Latent heat check:")
print(f"    m_water_removed = {m_w_cum:.4f} kg")
print(f"    Theoretical minimum energy = m_w * 2400 / 3600 = {latent_min_kWh:.4f} kWh")
print(f"    Actual condenser energy     = {Q_cond_cum:.4f} kWh")
print(f"    Actual total electrical     = {W_comp_cum + W_fan_cum:.4f} kWh")
if latent_min_kWh > 0:
    print(f"    Q_cond / latent_min        = {Q_cond_cum / latent_min_kWh:.4f}")
    print(f"    (W_comp+W_fan) / latent_min = {(W_comp_cum + W_fan_cum) / latent_min_kWh:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. DRYING RATE
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("7. DRYING RATE")
print("=" * 80)

dr_times = [0.5, 2.0, 4.0, 6.0, 8.0, 10.0]
print(f"\n  {'time_h':>8s}  {'dm_w_total_kg':>14s}  {'X_db_avg':>10s}")
print("  " + "-" * 38)
for t in dr_times:
    r = get_nearest_row(t)
    print(f"  {r['time_h']:8.4f}  {r['dm_w_total_kg']:14.6f}  {r['X_db_avg']:10.6f}")

# Identify constant-rate period
# Look at dm_w_total_kg over time and find where it's roughly constant
# Group into 0.5h bins and compute mean dm_w
df_copy = df.copy()
df_copy['time_bin'] = (df_copy['time_h'] * 2).round() / 2  # 0.5h bins
bin_means = df_copy.groupby('time_bin')['dm_w_total_kg'].mean()

print(f"\n  dm_w_total_kg averaged in 0.5h bins:")
print(f"  {'time_bin':>8s}  {'mean dm_w':>12s}")
print("  " + "-" * 24)
for tb, dm in bin_means.items():
    print(f"  {tb:8.1f}  {dm:12.6f}")

# Find the constant rate period: where dm_w varies by less than 10% of the max
max_dm = bin_means.max()
threshold = 0.10 * max_dm
# Find consecutive bins within threshold of max
const_rate_bins = bin_means[bin_means >= max_dm - threshold]
if len(const_rate_bins) > 0:
    t_start_cr = const_rate_bins.index.min()
    t_end_cr = const_rate_bins.index.max()
    print(f"\n  Constant-rate period (dm_w within 10% of max {max_dm:.6f}):")
    print(f"    Approximate range: {t_start_cr:.1f} h  to  {t_end_cr:.1f} h")
else:
    print(f"\n  No clear constant-rate period found")

# ─────────────────────────────────────────────────────────────────────────────
# 8. SECTION ASYMMETRY AT t=4h
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("8. SECTION ASYMMETRY AT t=4h")
print("=" * 80)

r4 = get_nearest_row(4.0)
print(f"\n  Nearest row: time_h = {r4['time_h']:.4f}")
print(f"\n  {'Tray':>6s}  {'X_sec_0':>10s}  {'X_sec_2':>10s}  {'sec2/sec0':>10s}")
print("  " + "-" * 42)
for i in range(5):
    sec0_col = f"X_tray_{i}_sec_0"
    sec2_col = f"X_tray_{i}_sec_2"
    if sec0_col in df.columns and sec2_col in df.columns:
        s0 = r4[sec0_col]
        s2 = r4[sec2_col]
        ratio = s2 / s0 if s0 != 0 else float('inf')
        print(f"  Tray {i}  {s0:10.6f}  {s2:10.6f}  {ratio:10.6f}")
    else:
        print(f"  Tray {i}  columns not found")

print("\n" + "=" * 80)
print("END OF ANALYSIS")
print("=" * 80)
