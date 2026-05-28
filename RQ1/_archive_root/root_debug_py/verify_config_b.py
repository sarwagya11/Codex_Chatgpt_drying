import pandas as pd
import numpy as np

files = {
    "r=0": r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_B\biratnagar\Ac_10m2.csv",
    "r=0.5": r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_B\biratnagar\Ac_10m2_r0.5.csv",
    "r=0.7": r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_B\biratnagar\Ac_10m2_r0.7.csv",
    "r=0.9": r"D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_B\biratnagar\Ac_10m2_r0.9.csv",
}

for label, fpath in files.items():
    print(f"\n{'='*70}")
    print(f"  CONFIG B BIRATNAGAR  {label}")
    print(f"{'='*70}")
    df = pd.read_csv(fpath)
    n_total = len(df)

    # Identify HP-on steps: W_comp > 0
    hp_on = df[df["W_comp_kW"] > 0.001].copy()
    hp_off = df[df["W_comp_kW"] <= 0.001].copy()
    n_hp_on = len(hp_on)
    n_hp_off = len(hp_off)
    print(f"Total rows: {n_total}, HP-on: {n_hp_on}, HP-off: {n_hp_off}")
    print(f"Time range: {df['time_h'].iloc[0]:.2f} - {df['time_h'].iloc[-1]:.2f} h")

    # ===== CHECK 1: Energy Balance Q_cond = Q_evap + W_comp =====
    print(f"\n--- CHECK 1: Energy Balance (Q_cond = Q_evap + W_comp) ---")
    hp_on["eb_sum"] = hp_on["Q_evap_kW"] + hp_on["W_comp_kW"]
    hp_on["eb_err_pct"] = (hp_on["Q_cond_kW"] - hp_on["eb_sum"]) / hp_on["Q_cond_kW"] * 100
    max_eb_err = hp_on["eb_err_pct"].abs().max()
    mean_eb_err = hp_on["eb_err_pct"].abs().mean()
    worst_idx = hp_on["eb_err_pct"].abs().idxmax()
    print(f"  Max |error|: {max_eb_err:.6f}%  (at row {worst_idx}, t={df.loc[worst_idx,'time_h']:.3f}h)")
    print(f"  Mean |error|: {mean_eb_err:.6f}%")
    if max_eb_err < 1.0:
        print(f"  RESULT: PASS (< 1% tolerance)")
    else:
        print(f"  RESULT: FAIL (> 1% tolerance)")

    # Show worst-case row details
    w = df.loc[worst_idx]
    print(f"  Worst row detail: Q_cond={w['Q_cond_kW']:.6f}, Q_evap={w['Q_evap_kW']:.6f}, W_comp={w['W_comp_kW']:.6f}, sum={w['Q_evap_kW']+w['W_comp_kW']:.6f}")

    # ===== CHECK 2: COP = Q_cond / W_comp =====
    print(f"\n--- CHECK 2: COP Consistency ---")
    hp_on["cop_calc"] = hp_on["Q_cond_kW"] / hp_on["W_comp_kW"]
    hp_on["cop_err_pct"] = (hp_on["COP"] - hp_on["cop_calc"]) / hp_on["cop_calc"] * 100
    max_cop_err = hp_on["cop_err_pct"].abs().max()
    print(f"  Max |COP reported - COP calc| / COP calc: {max_cop_err:.8f}%")
    if max_cop_err < 0.01:
        print(f"  RESULT: PASS (< 0.01%)")
    else:
        print(f"  RESULT: FAIL")

    # COP vs Carnot
    print(f"\n--- CHECK 2b: COP < COP_Carnot ---")
    hp_on["T_cond_K"] = hp_on["T_cond_C"] + 273.15
    hp_on["T_evap_K"] = hp_on["T_evap_C"] + 273.15
    hp_on["COP_Carnot"] = hp_on["T_cond_K"] / (hp_on["T_cond_K"] - hp_on["T_evap_K"])
    hp_on["COP_ratio"] = hp_on["COP"] / hp_on["COP_Carnot"]
    violations = hp_on[hp_on["COP"] >= hp_on["COP_Carnot"]]
    max_ratio = hp_on["COP_ratio"].max()
    min_ratio = hp_on["COP_ratio"].min()
    print(f"  COP/COP_Carnot range: {min_ratio:.4f} - {max_ratio:.4f}")
    print(f"  Carnot violations: {len(violations)} / {n_hp_on} steps")
    # Show COP range
    print(f"  COP range: {hp_on['COP'].min():.3f} - {hp_on['COP'].max():.3f}")
    print(f"  COP_Carnot range: {hp_on['COP_Carnot'].min():.3f} - {hp_on['COP_Carnot'].max():.3f}")
    if len(violations) == 0:
        print(f"  RESULT: PASS")
    else:
        print(f"  RESULT: FAIL")

    # ===== CHECK 3: m_ref range =====
    print(f"\n--- CHECK 3: m_ref Physical Reasonableness ---")
    m_ref_min = hp_on["m_ref_kg_per_s"].min()
    m_ref_max = hp_on["m_ref_kg_per_s"].max()
    m_ref_mean = hp_on["m_ref_kg_per_s"].mean()
    print(f"  m_ref range: {m_ref_min:.6f} - {m_ref_max:.6f} kg/s")
    print(f"  m_ref mean:  {m_ref_mean:.6f} kg/s")
    print(f"  Expected range for 1-ton R410A: 0.010 - 0.025 kg/s")
    if 0.005 <= m_ref_min and m_ref_max <= 0.035:
        print(f"  RESULT: PASS (within reasonable bounds)")
    else:
        print(f"  RESULT: WARNING - outside typical range")

    # ===== CHECK 4: COP trend and T_evap correlation =====
    print(f"\n--- CHECK 4: COP Trend Analysis ---")
    first10 = hp_on.head(10)
    last10 = hp_on.tail(10)
    print(f"  First 10 HP-on: COP mean={first10['COP'].mean():.3f}, T_evap mean={first10['T_evap_C'].mean():.2f}C")
    print(f"  Last 10 HP-on:  COP mean={last10['COP'].mean():.3f}, T_evap mean={last10['T_evap_C'].mean():.2f}C")
    corr = hp_on["COP"].corr(hp_on["T_evap_C"])
    print(f"  Pearson correlation COP vs T_evap: {corr:.4f}")
    if corr > 0.8:
        print(f"  RESULT: PASS - strong positive correlation")
    elif corr > 0.5:
        print(f"  RESULT: PASS - moderate positive correlation")
    else:
        print(f"  RESULT: WARNING - weak or negative correlation ({corr:.4f})")

    # ===== CHECK 5: m_ref spike after HP restart =====
    print(f"\n--- CHECK 5: m_ref Spike After HP Restart ---")
    df["hp_on_flag"] = (df["W_comp_kW"] > 0.001).astype(int)
    df["hp_transition"] = df["hp_on_flag"].diff()
    restart_indices = df[df["hp_transition"] == 1].index.tolist()
    shutoff_indices = df[df["hp_transition"] == -1].index.tolist()

    print(f"  HP shutoffs: {len(shutoff_indices)}, HP restarts: {len(restart_indices)}")

    if len(restart_indices) > 0 and len(shutoff_indices) > 0:
        for ri in restart_indices[:3]:
            preceding_shutoffs = [s for s in shutoff_indices if s < ri]
            if preceding_shutoffs:
                shutoff_pt = preceding_shutoffs[-1]
                # Get 10 rows before shutdown and 10 rows after restart
                before_range = range(max(0, shutoff_pt - 10), shutoff_pt)
                after_range = range(ri, min(ri + 10, len(df)))
                before_hp = df.loc[list(before_range)]
                before_hp = before_hp[before_hp["W_comp_kW"] > 0.001]
                after_hp = df.loc[list(after_range)]
                after_hp = after_hp[after_hp["W_comp_kW"] > 0.001]

                if len(before_hp) > 0 and len(after_hp) > 0:
                    print(f"\n  Restart at row {ri} (t={df.loc[ri,'time_h']:.2f}h), shutdown was at row {shutoff_pt} (t={df.loc[shutoff_pt,'time_h']:.2f}h):")
                    print(f"    HP-off duration: {(df.loc[ri,'time_h'] - df.loc[shutoff_pt,'time_h']):.2f} h")
                    print(f"    BEFORE HP-off ({len(before_hp)} rows):")
                    print(f"      T_evap mean={before_hp['T_evap_C'].mean():.2f}C, Q_cond mean={before_hp['Q_cond_kW'].mean():.4f}kW")
                    print(f"      m_ref mean={before_hp['m_ref_kg_per_s'].mean():.6f} kg/s, COP mean={before_hp['COP'].mean():.3f}")
                    print(f"    AFTER HP restart ({len(after_hp)} rows):")
                    print(f"      T_evap mean={after_hp['T_evap_C'].mean():.2f}C, Q_cond mean={after_hp['Q_cond_kW'].mean():.4f}kW")
                    print(f"      m_ref mean={after_hp['m_ref_kg_per_s'].mean():.6f} kg/s, COP mean={after_hp['COP'].mean():.3f}")

                    # Enthalpy difference proxy
                    before_h_diff = (before_hp["Q_cond_kW"] / before_hp["m_ref_kg_per_s"]).mean()
                    after_h_diff = (after_hp["Q_cond_kW"] / after_hp["m_ref_kg_per_s"]).mean()
                    print(f"    h2-h3 proxy BEFORE: {before_h_diff:.2f} kJ/kg")
                    print(f"    h2-h3 proxy AFTER:  {after_h_diff:.2f} kJ/kg")

                    # Show row-by-row around restart
                    print(f"    Row-by-row around restart:")
                    for idx in range(max(0, ri-3), min(ri+5, len(df))):
                        row = df.loc[idx]
                        print(f"      [{idx}] t={row['time_h']:.3f}h W={row['W_comp_kW']:.4f} Q_c={row['Q_cond_kW']:.4f} m_ref={row['m_ref_kg_per_s']:.6f} T_evap={row['T_evap_C']:.2f} COP={row['COP']:.3f}")
    else:
        print(f"  No HP restart transitions found")

    # ===== CHECK 6: Second-law constraints =====
    print(f"\n--- CHECK 6: Second-Law Constraints ---")
    c6a = (hp_on["T_evap_C"] < hp_on["T_cond_C"]).all()
    c6b = (hp_on["W_comp_kW"] > 0).all()
    c6c = (hp_on["Q_evap_kW"] > 0).all()
    c6d = (hp_on["Q_cond_kW"] > hp_on["Q_evap_kW"]).all()
    print(f"  T_evap < T_cond: {c6a}")
    print(f"  W_comp > 0:      {c6b}")
    print(f"  Q_evap > 0:      {c6c}")
    print(f"  Q_cond > Q_evap: {c6d}")
    if c6a and c6b and c6c and c6d:
        print(f"  RESULT: PASS")
    else:
        print(f"  RESULT: FAIL")
        if not c6d:
            bad = hp_on[hp_on["Q_cond_kW"] <= hp_on["Q_evap_kW"]]
            print(f"    Q_cond <= Q_evap at {len(bad)} steps")

    # ===== CHECK 7: HP-off period =====
    print(f"\n--- CHECK 7: HP-off Period (Config B Solar Excess) ---")
    if n_hp_off > 0:
        hp_off_wcomp_max = hp_off["W_comp_kW"].max()
        hp_off_qcond_max = hp_off["Q_cond_kW"].max()
        hp_off_cop_vals = hp_off["COP"].unique()
        print(f"  HP-off rows: {n_hp_off}")
        print(f"  Max W_comp during HP-off: {hp_off_wcomp_max:.8f} kW")
        print(f"  Max Q_cond during HP-off: {hp_off_qcond_max:.8f} kW")
        print(f"  COP values during HP-off: {hp_off_cop_vals[:10]}")
        print(f"  T_to_chamber during HP-off: min={hp_off['T_to_chamber_C'].min():.2f}, max={hp_off['T_to_chamber_C'].max():.2f}")

        # Show transition into HP-off
        if len(shutoff_indices) > 0:
            si = shutoff_indices[0]
            print(f"\n  First HP shutoff at row {si} (t={df.loc[si,'time_h']:.2f}h):")
            for idx in range(max(0, si-2), min(si+3, len(df))):
                row = df.loc[idx]
                print(f"    [{idx}] t={row['time_h']:.3f}h W={row['W_comp_kW']:.4f} Q_c={row['Q_cond_kW']:.4f} Q_sol={row['Q_solar_kW']:.4f} T_solar={row['T_solar_out_C']:.2f} T_chamber={row['T_to_chamber_C']:.2f}")

        if hp_off_wcomp_max < 0.001 and hp_off_qcond_max < 0.001:
            print(f"  RESULT: PASS")
        else:
            print(f"  RESULT: FAIL - nonzero HP values during HP-off")
    else:
        print(f"  No HP-off period (HP always on)")
        print(f"  RESULT: N/A")

    # Cleanup
    df.drop(columns=["hp_on_flag", "hp_transition"], inplace=True)

    # ===== SAMPLE HAND CALCULATION =====
    print(f"\n--- SAMPLE HAND CALCULATION (first HP-on step) ---")
    s = hp_on.iloc[0]
    print(f"  Row index: {hp_on.index[0]}")
    print(f"  T_evap={s['T_evap_C']:.4f}C, T_cond={s['T_cond_C']:.1f}C")
    print(f"  W_comp={s['W_comp_kW']:.6f} kW")
    print(f"  Q_evap={s['Q_evap_kW']:.6f} kW")
    print(f"  Q_cond={s['Q_cond_kW']:.6f} kW")
    print(f"  COP={s['COP']:.6f}")
    print(f"  m_ref={s['m_ref_kg_per_s']:.8f} kg/s")
    print(f"  Check: Q_evap+W_comp = {s['Q_evap_kW']+s['W_comp_kW']:.6f} vs Q_cond = {s['Q_cond_kW']:.6f}")
    print(f"  Check: Q_cond/W_comp = {s['Q_cond_kW']/s['W_comp_kW']:.6f} vs COP = {s['COP']:.6f}")
    print(f"  h2-h3 = Q_cond/m_ref = {s['Q_cond_kW']/s['m_ref_kg_per_s']:.2f} kJ/kg")
    print(f"  h1-h4 = Q_evap/m_ref = {s['Q_evap_kW']/s['m_ref_kg_per_s']:.2f} kJ/kg")
    cop_carnot = (s["T_cond_C"]+273.15) / ((s["T_cond_C"]+273.15) - (s["T_evap_C"]+273.15))
    print(f"  COP_Carnot = {cop_carnot:.3f}, COP/COP_Carnot = {s['COP']/cop_carnot:.4f}")

print(f"\n{'='*70}")
print(f"  VERIFICATION COMPLETE")
print(f"{'='*70}")
