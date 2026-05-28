import pandas as pd
import numpy as np
import sys

def validate_csv(path, label):
    print(f"\n{'='*80}")
    print(f"VALIDATION: {label}")
    print(f"File: {path}")
    print(f"{'='*80}")

    df = pd.read_csv(path)
    errors = []
    warnings = []

    # =========================================================================
    # TEST 1: flow_direction column exists and has valid values
    # =========================================================================
    print("\n--- TEST 1: flow_direction column ---")
    if 'flow_direction' not in df.columns:
        errors.append("FATAL: flow_direction column missing")
        print("  FAIL: column missing")
    else:
        unique_vals = df['flow_direction'].unique()
        print(f"  Unique values: {unique_vals}")
        invalid = set(unique_vals) - {'forward', 'reverse'}
        if invalid:
            errors.append(f"Invalid flow_direction values: {invalid}")
        n_fwd = (df['flow_direction'] == 'forward').sum()
        n_rev = (df['flow_direction'] == 'reverse').sum()
        print(f"  forward: {n_fwd}, reverse: {n_rev}, total: {len(df)}")
        if n_rev == 0:
            errors.append("FATAL: No 'reverse' entries — flow reversal not working")
        if n_fwd == 0:
            errors.append("FATAL: No 'forward' entries — always reversed?")

    # =========================================================================
    # TEST 2: Reversal timing — should switch every 30 min (1800s)
    # =========================================================================
    print("\n--- TEST 2: Reversal timing (every 30 min) ---")
    if 'flow_direction' in df.columns:
        df['expected_dir'] = df['time_s'].apply(
            lambda t: 'reverse' if (int(t / 1800) % 2 == 1) else 'forward'
        )
        mismatches = (df['flow_direction'] != df['expected_dir']).sum()
        print(f"  Mismatches vs expected: {mismatches} / {len(df)}")
        if mismatches > 0:
            bad = df[df['flow_direction'] != df['expected_dir']][['time_s', 'time_h', 'flow_direction', 'expected_dir']].head(10)
            print(f"  First mismatches:\n{bad}")
            errors.append(f"Reversal timing mismatch: {mismatches} rows wrong")

        # Check transition points
        transitions = df[df['flow_direction'] != df['flow_direction'].shift(1)].copy()
        print(f"  Number of transitions: {len(transitions)}")
        if len(transitions) > 1:
            t_transitions = transitions['time_s'].values
            intervals = np.diff(t_transitions)
            print(f"  Transition intervals (s): min={intervals.min()}, max={intervals.max()}, mean={intervals.mean():.0f}")
            # Should be ~1800s (30 min), but with 60s timestep, could be 1740-1860
            if intervals.min() < 1700 or intervals.max() > 1900:
                warnings.append(f"Transition intervals outside [1700, 1900]s range: [{intervals.min()}, {intervals.max()}]")

    # =========================================================================
    # TEST 3: Exhaust temperature correctness
    # T_exhaust should come from the LAST tray visited by air
    # Forward: exhaust = tray 4 (last), Reverse: exhaust = tray 0 (first)
    # =========================================================================
    print("\n--- TEST 3: Exhaust indexing ---")
    if 'flow_direction' in df.columns:
        fwd_rows = df[df['flow_direction'] == 'forward']
        rev_rows = df[df['flow_direction'] == 'reverse']

        # During forward flow, exhaust = T_tray_4_out_C
        # During reverse flow, exhaust = T_tray_0_out_C
        if 'T_tray_4_out_C' in df.columns and 'T_tray_0_out_C' in df.columns:
            if len(fwd_rows) > 0:
                fwd_match = np.allclose(fwd_rows['T_exhaust_C'], fwd_rows['T_tray_4_out_C'], atol=1e-6)
                print(f"  Forward: T_exhaust == T_tray_4_out: {fwd_match}")
                if not fwd_match:
                    diff = (fwd_rows['T_exhaust_C'] - fwd_rows['T_tray_4_out_C']).abs()
                    print(f"    Max diff: {diff.max():.6f}")
                    errors.append("Forward exhaust doesn't match tray 4")

            if len(rev_rows) > 0:
                rev_match = np.allclose(rev_rows['T_exhaust_C'], rev_rows['T_tray_0_out_C'], atol=1e-6)
                print(f"  Reverse: T_exhaust == T_tray_0_out: {rev_match}")
                if not rev_match:
                    diff = (rev_rows['T_exhaust_C'] - rev_rows['T_tray_0_out_C']).abs()
                    print(f"    Max diff: {diff.max():.6f}")
                    errors.append("Reverse exhaust doesn't match tray 0")

        # Same for RH
        if 'RH_tray_4_out_frac' in df.columns and 'RH_tray_0_out_frac' in df.columns:
            if len(fwd_rows) > 0:
                fwd_rh_match = np.allclose(fwd_rows['RH_exhaust_frac'], fwd_rows['RH_tray_4_out_frac'], atol=1e-6)
                print(f"  Forward: RH_exhaust == RH_tray_4_out: {fwd_rh_match}")
                if not fwd_rh_match:
                    errors.append("Forward RH exhaust doesn't match tray 4")
            if len(rev_rows) > 0:
                rev_rh_match = np.allclose(rev_rows['RH_exhaust_frac'], rev_rows['RH_tray_0_out_frac'], atol=1e-6)
                print(f"  Reverse: RH_exhaust == RH_tray_0_out: {rev_rh_match}")
                if not rev_rh_match:
                    errors.append("Reverse RH exhaust doesn't match tray 0")

    # =========================================================================
    # TEST 4: Tray uniformity improvement
    # The WHOLE POINT of flow reversal. Compare tray moisture spread.
    # =========================================================================
    print("\n--- TEST 4: Tray uniformity analysis ---")
    tray_cols = [f'X_tray_{i}' for i in range(5) if f'X_tray_{i}' in df.columns]
    if len(tray_cols) >= 2:
        # At several time snapshots, check spread
        for t_h in [2.0, 4.0, 6.0, 8.0, 10.0]:
            idx = (df['time_h'] - t_h).abs().idxmin()
            row = df.loc[idx]
            vals = [row[c] for c in tray_cols]
            spread = max(vals) - min(vals)
            actual_h = row['time_h']
            print(f"  t={actual_h:.1f}h: X range [{min(vals):.3f}, {max(vals):.3f}], spread={spread:.3f}")

        # Check if trays ALTERNATE which is driest at consecutive reversals
        # At t=15min (forward), tray0 should be driest
        # At t=45min (reverse), tray4 should be driest
        for t_min, expected_driest_label in [(15, "tray0 (forward period)"), (45, "tray4 (reverse period)")]:
            idx = (df['time_h'] - t_min/60).abs().idxmin()
            row = df.loc[idx]
            vals = {c: row[c] for c in tray_cols}
            driest = min(vals, key=vals.get)
            print(f"  t={t_min}min: Driest is {driest} (expected: {expected_driest_label})")

    # =========================================================================
    # TEST 5: Air state continuity at reversal boundaries
    # Check that tray temperatures don't have unphysical discontinuities
    # =========================================================================
    print("\n--- TEST 5: Continuity at reversal boundaries ---")
    if 'flow_direction' in df.columns and len(transitions) > 1:
        # Look at first few transitions
        for tidx in transitions.index[:5]:
            if tidx == 0:
                continue
            prev_row = df.loc[tidx - 1]
            curr_row = df.loc[tidx]
            dT0 = abs(curr_row.get('T_tray_0_out_C', 0) - prev_row.get('T_tray_0_out_C', 0))
            dT4 = abs(curr_row.get('T_tray_4_out_C', 0) - prev_row.get('T_tray_4_out_C', 0))
            dT_exh = abs(curr_row['T_exhaust_C'] - prev_row['T_exhaust_C'])
            t_h = curr_row['time_h']
            direction = curr_row['flow_direction']
            print(f"  t={t_h:.2f}h ({direction}): dT_tray0={dT0:.2f}C, dT_tray4={dT4:.2f}C, dT_exhaust={dT_exh:.2f}C")
            if dT_exh > 20:
                warnings.append(f"Large exhaust T jump at t={t_h:.2f}h: {dT_exh:.1f}C (expected at reversal)")

    # =========================================================================
    # TEST 6: Water balance — total water removed should be ~64 kg
    # =========================================================================
    print("\n--- TEST 6: Water balance ---")
    final = df.iloc[-1]
    m_w_cum = final['m_w_cum_kg']
    X_avg_final = final['X_db_avg']
    print(f"  Final m_w_cum: {m_w_cum:.2f} kg (target ~64 kg)")
    print(f"  Final X_avg: {X_avg_final:.4f} (target <= 0.20)")

    expected_water = 10.0 * (6.5 - 0.20)  # m_dry * (X0 - X_final)
    pct_diff = abs(m_w_cum - expected_water) / expected_water * 100
    print(f"  Expected: {expected_water:.1f} kg, actual: {m_w_cum:.2f} kg, diff: {pct_diff:.1f}%")
    if pct_diff > 5:
        warnings.append(f"Water balance off by {pct_diff:.1f}% (expected {expected_water:.1f}, got {m_w_cum:.2f})")

    # Check each tray's final moisture
    for i in range(5):
        col = f'X_tray_{i}'
        if col in df.columns:
            x_final = final[col]
            print(f"  Tray {i} final X: {x_final:.4f} {'OK' if x_final <= 0.1001 else 'NOT DRY'}")

    # =========================================================================
    # TEST 7: Section-level data consistency
    # =========================================================================
    print("\n--- TEST 7: Section-level consistency ---")
    for i in range(5):
        sec_cols = [f'X_tray_{i}_sec_{j}' for j in range(3)]
        if all(c in df.columns for c in sec_cols):
            avg_col = f'X_tray_{i}'
            if avg_col in df.columns:
                computed_avg = df[sec_cols].mean(axis=1)
                max_diff = (df[avg_col] - computed_avg).abs().max()
                print(f"  Tray {i}: max |X_tray_avg - mean(sections)| = {max_diff:.8f}")
                if max_diff > 1e-6:
                    errors.append(f"Tray {i} average doesn't match section mean (diff={max_diff:.8f})")

    # =========================================================================
    # TEST 8: Bypass mode interaction with flow reversal
    # =========================================================================
    print("\n--- TEST 8: Bypass mode interaction ---")
    if 'bypass_mode' in df.columns:
        modes = df['bypass_mode'].value_counts()
        print(f"  Bypass mode distribution: {dict(modes)}")

        # Check that bypass mode changes are independent of flow direction changes
        if 'flow_direction' in df.columns:
            cross = pd.crosstab(df['flow_direction'], df['bypass_mode'])
            print(f"  Cross-tab (flow_direction x bypass_mode):\n{cross}")

    # =========================================================================
    # TEST 9: Monotonicity of cumulative quantities
    # =========================================================================
    print("\n--- TEST 9: Monotonicity checks ---")
    for col in ['m_w_cum_kg', 'W_comp_cum_kWh', 'W_fan_cum_kWh']:
        if col in df.columns:
            diffs = df[col].diff().dropna()
            n_neg = (diffs < -1e-10).sum()
            print(f"  {col}: {n_neg} negative diffs (should be 0)")
            if n_neg > 0:
                errors.append(f"{col} not monotonically increasing: {n_neg} decreases")

    # =========================================================================
    # TEST 10: Physical bounds
    # =========================================================================
    print("\n--- TEST 10: Physical bounds ---")
    # Temperature bounds
    T_min = df['T_exhaust_C'].min()
    T_max = df['T_to_chamber_C'].max()
    print(f"  T_exhaust range: [{T_min:.1f}, {df['T_exhaust_C'].max():.1f}]C")
    print(f"  T_to_chamber range: [{df['T_to_chamber_C'].min():.1f}, {T_max:.1f}]C")
    if T_min < -10:
        errors.append(f"Unphysical exhaust temperature: {T_min:.1f}C")

    # RH bounds
    rh_max = df['RH_exhaust_frac'].max()
    rh_min = df['RH_exhaust_frac'].min()
    print(f"  RH_exhaust range: [{rh_min:.4f}, {rh_max:.4f}]")
    if rh_max > 1.001:
        errors.append(f"RH > 1: {rh_max:.4f}")
    if rh_min < 0:
        errors.append(f"RH < 0: {rh_min:.4f}")

    # X bounds (no negative moisture)
    for i in range(5):
        col = f'X_tray_{i}'
        if col in df.columns:
            x_min = df[col].min()
            if x_min < -0.001:
                errors.append(f"Negative moisture on tray {i}: {x_min:.6f}")

    # =========================================================================
    # TEST 11: Tray T/RH reversal pattern
    # In forward flow, T_tray_0 should be warmest (closest to inlet)
    # In reverse flow, T_tray_4 should be warmest
    # =========================================================================
    print("\n--- TEST 11: Tray temperature ordering by flow direction ---")
    # Check at t=2h (constant-rate drying, clearest signal)
    for t_h_check in [1.0, 3.0, 5.0]:
        idx = (df['time_h'] - t_h_check).abs().idxmin()
        row = df.loc[idx]
        direction = row.get('flow_direction', 'forward')
        t_vals = [row.get(f'T_tray_{i}_out_C', 0) for i in range(5)]

        if direction == 'forward':
            # Air enters tray 0 first → tray 0 should be warmest exit
            warmest = np.argmax(t_vals)
            coldest = np.argmin(t_vals)
            expected_warmest = 0
            expected_coldest = 4
        else:
            # Air enters tray 4 first → tray 4 should be warmest exit
            warmest = np.argmax(t_vals)
            coldest = np.argmin(t_vals)
            expected_warmest = 4
            expected_coldest = 0

        ok_warm = warmest == expected_warmest
        ok_cold = coldest == expected_coldest
        status = "OK" if (ok_warm and ok_cold) else "CHECK"
        print(f"  t={t_h_check:.0f}h ({direction}): T_out = {[f'{v:.1f}' for v in t_vals]}")
        print(f"    Warmest=tray{warmest} (expect {expected_warmest}), Coldest=tray{coldest} (expect {expected_coldest}) [{status}]")
        if not ok_warm:
            warnings.append(f"At t={t_h_check:.0f}h ({direction}), warmest tray is {warmest} not {expected_warmest}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print(f"\n{'='*80}")
    print(f"SUMMARY: {label}")
    print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
    print(f"  ERRORS: {len(errors)}")
    for e in errors:
        print(f"    [ERROR] {e}")
    print(f"  WARNINGS: {len(warnings)}")
    for w in warnings:
        print(f"    [WARN] {w}")
    print(f"  VERDICT: {'FAIL' if errors else 'PASS' if not warnings else 'PASS (with warnings)'}")
    print(f"{'='*80}")
    return errors, warnings

# Run on both CSVs
e1, w1 = validate_csv(
    r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\validation_test\config_A\kathmandu\baseline_r0.8.csv",
    "Config A (HP-only, r=0.8, flow_reversal=30min)"
)
e2, w2 = validate_csv(
    r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\validation_test\config_B\kathmandu\Ac_10m2_r0.8.csv",
    "Config B (Solar+HP, r=0.8, flow_reversal=30min)"
)

print(f"\n\n{'#'*80}")
print("OVERALL RESULT")
print(f"{'#'*80}")
total_errors = len(e1) + len(e2)
total_warnings = len(w1) + len(w2)
print(f"Total ERRORS: {total_errors}")
print(f"Total WARNINGS: {total_warnings}")
if total_errors == 0:
    print("OVERALL: ALL CRITICAL TESTS PASSED")
else:
    print("OVERALL: FAILURES DETECTED — NEEDS FIX")
