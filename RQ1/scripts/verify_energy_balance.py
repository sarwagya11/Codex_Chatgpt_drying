"""Energy balance verification for E2 and E3 configs.

Traces the air path component-by-component and checks:
1. HRX: Q_HRX = m_da * cp * (T_amb_heated - T_amb)
2. Solar: Q_solar = m_da * cp * (T_solar_out - T_solar_in)
3. Condenser: Q_cond_air = m_da * cp * (T_cond_out - T_air_in_cond)
4. First law: Q_cond = Q_evap + W_comp
5. Chamber: energy in - energy out accounts for latent heat of drying
6. Temperature monotonicity along air path
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def verify_config(csv_path: Path, config_name: str, m_da: float, cp: float = 1.006):
    """Run all energy balance checks on a simulation CSV.

    Parameters
    ----------
    csv_path : Path
        Path to simulation output CSV.
    config_name : str
        "E2" or "E3" — determines expected air path order.
    m_da : float
        Dry air mass flow rate [kg/s].
    cp : float
        Specific heat of air [kJ/kg·K].
    """
    df = pd.read_csv(csv_path)
    dt_s = df["time_s"].diff().median()
    n = len(df)

    print(f"\n{'='*72}")
    print(f"ENERGY BALANCE VERIFICATION: {config_name}")
    print(f"File: {csv_path.name}")
    print(f"Timesteps: {n}, dt={dt_s:.0f}s, m_da={m_da:.4f} kg/s")
    print(f"{'='*72}")

    errors = []

    # ── 1. HRX CHECK ──────────────────────────────────────────────────────
    print(f"\n--- 1. HRX (Amb -> preheated) ---")
    Q_hrx_expected = m_da * cp * (df["T_amb_heated_C"] - df["T_amb_C"])
    Q_hrx_logged = df["Q_HRX_kW"]
    hrx_err = Q_hrx_expected - Q_hrx_logged
    print(f"  dT_HRX mean: {(df['T_amb_heated_C'] - df['T_amb_C']).mean():.2f} K")
    print(f"  Q_HRX expected (m*cp*dT): mean={Q_hrx_expected.mean():.4f} kW")
    print(f"  Q_HRX logged:             mean={Q_hrx_logged.mean():.4f} kW")
    print(f"  Error: mean={hrx_err.mean():.6f} kW, max|err|={hrx_err.abs().max():.6f} kW")
    # Note: Q_HRX is computed from enthalpy (includes humidity effects),
    # cp*dT is a dry-air approximation — small difference is expected.
    pct_err = (hrx_err / Q_hrx_logged.replace(0, np.nan)).dropna()
    if pct_err.abs().max() > 0.10:
        errors.append(f"HRX: max error {pct_err.abs().max()*100:.1f}% > 10%")
        print(f"  [WARN] Max relative error: {pct_err.abs().max()*100:.1f}%")
    else:
        print(f"  [OK] Max relative error: {pct_err.abs().max()*100:.2f}%")

    # ── 2. SOLAR CHECK ────────────────────────────────────────────────────
    print(f"\n--- 2. Solar Collector (T_solar_in -> T_solar_out) ---")
    Q_solar_expected = m_da * cp * (df["T_solar_out_C"] - df["T_solar_in_C"])
    Q_solar_logged = df["Q_solar_kW"]
    solar_err = Q_solar_expected - Q_solar_logged
    print(f"  T_solar_in mean:  {df['T_solar_in_C'].mean():.2f} C")
    print(f"  T_solar_out mean: {df['T_solar_out_C'].mean():.2f} C")
    print(f"  dT_solar mean:    {(df['T_solar_out_C'] - df['T_solar_in_C']).mean():.2f} K")
    print(f"  Q_solar expected (m*cp*dT): mean={Q_solar_expected.mean():.4f} kW")
    print(f"  Q_solar logged:             mean={Q_solar_logged.mean():.4f} kW")
    print(f"  Error: mean={solar_err.mean():.6f} kW, max|err|={solar_err.abs().max():.6f} kW")
    mask_solar = Q_solar_logged > 0.01
    if mask_solar.any():
        pct_s = ((solar_err[mask_solar]) / Q_solar_logged[mask_solar])
        print(f"  [{'WARN' if pct_s.abs().max()>0.10 else 'OK'}] "
              f"Max relative error (Q>0.01): {pct_s.abs().max()*100:.2f}%")
        if pct_s.abs().max() > 0.10:
            errors.append(f"Solar: max error {pct_s.abs().max()*100:.1f}% > 10%")

    # ── 3. CONDENSER AIR-SIDE CHECK ───────────────────────────────────────
    print(f"\n--- 3. Condenser air-side (T_air_in_cond -> T_cond_out) ---")
    Q_cond_air = m_da * cp * (df["T_cond_out_C"] - df["T_air_in_cond_C"])
    Q_cond_logged = df["Q_cond_kW"]
    cond_air_err = Q_cond_air - Q_cond_logged
    print(f"  T_air_in_cond mean: {df['T_air_in_cond_C'].mean():.2f} C")
    print(f"  T_cond_out mean:    {df['T_cond_out_C'].mean():.2f} C")
    print(f"  dT_cond mean:       {(df['T_cond_out_C'] - df['T_air_in_cond_C']).mean():.2f} K")
    print(f"  Q_cond air (m*cp*dT): mean={Q_cond_air.mean():.4f} kW")
    print(f"  Q_cond HP logged:     mean={Q_cond_logged.mean():.4f} kW")
    print(f"  Difference:           mean={cond_air_err.mean():.4f} kW")
    # Q_cond from HP is the REFRIGERANT side heat rejection.
    # Q_cond_air is what the AIR actually absorbs.
    # They differ because: (a) condenser effectiveness < 1, (b) HP model uses
    # enthalpy-based Q while we approximate with cp*dT.
    # The air absorbs LESS than what the refrigerant rejects (rest is lost).
    # So Q_cond_air <= Q_cond_logged is expected.
    mask_cond = Q_cond_logged > 0.01
    if mask_cond.any():
        ratio = Q_cond_air[mask_cond] / Q_cond_logged[mask_cond]
        print(f"  Q_air/Q_ref ratio: mean={ratio.mean():.4f}, "
              f"min={ratio.min():.4f}, max={ratio.max():.4f}")
        # With epsilon_cond=0.85, expect ratio around 0.85
        if ratio.mean() < 0.5 or ratio.mean() > 1.1:
            errors.append(f"Condenser: air/ref ratio {ratio.mean():.3f} outside [0.5, 1.1]")
            print(f"  [WARN] Ratio outside expected range")
        else:
            print(f"  [OK] Ratio consistent with condenser effectiveness")

    # ── 4. FIRST LAW: Q_cond = Q_evap + W_comp * eta_mech ───────────────
    # The refrigerant first law is Q_cond = Q_evap + W_shaft
    # where W_shaft = W_comp * eta_mechanical
    # So: Q_cond - Q_evap - W_comp * eta_mech = 0
    eta_mech = 0.90  # from HeatPumpConfig default (config_solar_hp.py:114)
    print(f"\n--- 4. First Law: Q_cond = Q_evap + W_comp * eta_mech ---")
    first_law_lhs = df["Q_cond_kW"]
    first_law_rhs = df["Q_evap_kW"] + df["W_comp_kW"] * eta_mech
    fl_err = first_law_lhs - first_law_rhs
    print(f"  Q_cond mean:                    {first_law_lhs.mean():.4f} kW")
    print(f"  Q_evap + W_comp*eta_mech mean:  {first_law_rhs.mean():.4f} kW")
    print(f"  Error: mean={fl_err.mean():.6f} kW, max|err|={fl_err.abs().max():.6f} kW")
    mask_fl = first_law_lhs > 0.01
    if mask_fl.any():
        pct_fl = (fl_err[mask_fl] / first_law_lhs[mask_fl])
        max_fl = pct_fl.abs().max()
        print(f"  [{'FAIL' if max_fl > 0.01 else 'OK'}] "
              f"Max relative error: {max_fl*100:.4f}%")
        if max_fl > 0.01:
            errors.append(f"First law: max error {max_fl*100:.4f}% > 1%")

    # ── 5. TEMPERATURE MONOTONICITY (air path order) ──────────────────────
    print(f"\n--- 5. Temperature Path Monotonicity ---")
    if config_name in ("E1", "E2"):
        # E2: Amb → HRX → Solar → Cond → Chamber
        # Each step should heat (or at least not cool) the air
        # Exception: night when G=0, solar adds nothing
        checks = [
            ("Amb -> HRX", "T_amb_C", "T_amb_heated_C"),
            ("HRX -> Solar", "T_amb_heated_C", "T_solar_out_C"),
            ("Solar -> Cond in (clamped)", "T_solar_out_C", "T_air_in_cond_C"),
            ("Cond in -> Cond out", "T_air_in_cond_C", "T_cond_out_C"),
        ]
    else:  # E3
        # E3: Amb → HRX → Cond → Solar → Chamber
        checks = [
            ("Amb -> HRX", "T_amb_C", "T_amb_heated_C"),
            ("HRX -> Cond in", "T_amb_heated_C", "T_air_in_cond_C"),
            ("Cond in -> Cond out", "T_air_in_cond_C", "T_cond_out_C"),
            ("Cond out -> Solar", "T_cond_out_C", "T_solar_out_C"),
        ]

    for label, col_in, col_out in checks:
        dT = df[col_out] - df[col_in]
        n_decrease = (dT < -0.1).sum()
        print(f"  {label}: mean dT={dT.mean():+.2f} K, "
              f"min={dT.min():+.2f}, violations(dT<-0.1)={n_decrease}/{n}")
        if "clamped" in label.lower():
            # E1/E2: min(T_solar_out, T_set) intentionally clamps — not a bug
            if n_decrease > 0:
                print(f"    (Expected: T_solar_out clamped to T_set when solar "
                      f"exceeds target — IDEA-7 documented behavior)")
        elif n_decrease > 0 and "Solar" in label:
            # Solar can have dT<0 at night or very low irradiance — OK
            night_mask = df["G_solar_Wm2"] < 10
            day_violations = ((dT < -0.1) & ~night_mask).sum()
            print(f"    (night timesteps: {night_mask.sum()}, "
                  f"daytime violations: {day_violations})")
            if day_violations > 0:
                errors.append(f"{label}: {day_violations} daytime temperature drops")
        elif n_decrease > 0:
            errors.append(f"{label}: {n_decrease} temperature drops")

    # Check final: T_to_chamber should not exceed T_set (45°C)
    over_tset = (df["T_to_chamber_C"] > df["T_cond_target_C"].max() + 0.5).sum()
    print(f"  T_to_chamber > T_set+0.5: {over_tset} timesteps")
    if over_tset > 0:
        errors.append(f"T_to_chamber exceeds T_set: {over_tset} timesteps")

    # ── 6. CHAMBER ENERGY BALANCE ─────────────────────────────────────────
    print(f"\n--- 6. Chamber Energy Balance ---")
    # Energy in: m_da * h_to_chamber (per timestep)
    # Energy out: m_da * h_exhaust + latent heat removed
    # h_fg ~ 2450 kJ/kg at 45°C
    h_fg = 2450.0  # kJ/kg latent heat of vaporization at ~45°C
    # Approximate: Q_in_air = m_da * cp * T_to_chamber
    #              Q_out_air = m_da * cp * T_exhaust
    #              Q_drying = dm_w * h_fg / dt_s (kW)
    Q_in = m_da * cp * df["T_to_chamber_C"]
    Q_out = m_da * cp * df["T_exhaust_C"]
    Q_sensible_drop = Q_in - Q_out  # should be positive (air cools)
    Q_drying = df["dm_w_total_kg"] * h_fg / dt_s  # kW
    # Also account for humidity increase in air (latent energy carried by exhaust)
    # This is a simplified check — full enthalpy would be more precise
    chamber_balance = Q_sensible_drop - Q_drying
    print(f"  Q_air_in (m*cp*T_in):  mean={Q_in.mean():.2f} kW")
    print(f"  Q_air_out (m*cp*T_ex): mean={Q_out.mean():.2f} kW")
    print(f"  Q_sensible_drop:       mean={Q_sensible_drop.mean():.4f} kW")
    print(f"  Q_drying (dm_w*h_fg):  mean={Q_drying.mean():.4f} kW")
    print(f"  Residual (sens - lat): mean={chamber_balance.mean():.4f} kW")
    print(f"  Note: Residual includes sensible heating of product + humidity")
    print(f"        transport (not pure energy conservation check)")

    # ── 7. HP MODE DISTRIBUTION (E3 specific) ─────────────────────────────
    if "hp_mode" in df.columns:
        print(f"\n--- 7. HP Mode Distribution ---")
        modes = df["hp_mode"].value_counts()
        for mode, count in modes.items():
            pct = 100 * count / n
            if mode == "off":
                avg_w = 0.0
            else:
                avg_w = df.loc[df["hp_mode"] == mode, "W_comp_kW"].mean()
            print(f"  {mode:>12}: {count:>5} ({pct:5.1f}%)  "
                  f"avg W_comp={avg_w:.3f} kW")

    # ── 8. E3-SPECIFIC: SOLAR BACK-CALCULATION CHECK ─────────────────────
    if config_name == "E3":
        print(f"\n--- 8. E3 Back-Calculation Accuracy ---")
        # When HP is partial, check: T_solar_out should be close to T_set
        partial = df[df["hp_mode"] == "partial"]
        if len(partial) > 0:
            target_miss = partial["T_to_chamber_C"] - 45.0  # T_set
            print(f"  Partial-HP timesteps: {len(partial)}")
            print(f"  T_to_chamber vs T_set: "
                  f"mean={target_miss.mean():+.3f} K, "
                  f"min={target_miss.min():+.3f}, max={target_miss.max():+.3f}")
            if target_miss.abs().max() > 2.0:
                errors.append(f"E3 back-calc: max miss {target_miss.abs().max():.2f} K > 2K")
                print(f"  [WARN] Some timesteps miss target by > 2K")
            else:
                print(f"  [OK] All within 2K of target")

        # When HP is off, check: solar output should reach T_set
        hp_off = df[df["hp_mode"] == "off"]
        if len(hp_off) > 0:
            off_miss = hp_off["T_solar_out_C"] - 45.0
            print(f"  HP-OFF timesteps: {len(hp_off)}")
            print(f"  T_solar_out vs T_set: "
                  f"mean={off_miss.mean():+.3f} K, "
                  f"min={off_miss.min():+.3f}, max={off_miss.max():+.3f}")

    # ── 9. CUMULATIVE ENERGY CROSS-CHECK ──────────────────────────────────
    print(f"\n--- 9. Cumulative Energy Cross-Check ---")
    final = df.iloc[-1]
    welec = final["W_comp_cum_kWh"] + final["W_fan_cum_kWh"]
    mw = final["m_w_cum_kg"]
    sec = welec / mw if mw > 0 else 999

    # Recompute cumulatives from instantaneous values
    W_comp_recomp = (df["W_comp_kW"] * dt_s / 3600).sum()
    Q_solar_recomp = (df["Q_solar_kW"] * dt_s / 3600).sum()
    Q_cond_recomp = (df["Q_cond_kW"] * dt_s / 3600).sum()

    print(f"  W_comp_cum:  logged={final['W_comp_cum_kWh']:.4f}, "
          f"recomputed={W_comp_recomp:.4f}, "
          f"diff={final['W_comp_cum_kWh']-W_comp_recomp:.6f} kWh")
    print(f"  Q_solar_cum: logged={final['Q_solar_cum_kWh']:.4f}, "
          f"recomputed={Q_solar_recomp:.4f}, "
          f"diff={final['Q_solar_cum_kWh']-Q_solar_recomp:.6f} kWh")
    print(f"  Q_cond_cum:  logged={final['Q_cond_cum_kWh']:.4f}, "
          f"recomputed={Q_cond_recomp:.4f}, "
          f"diff={final['Q_cond_cum_kWh']-Q_cond_recomp:.6f} kWh")
    print(f"  SEC: {sec:.3f} kWh/kg  (W_elec={welec:.2f}, m_w={mw:.2f})")

    cum_err = abs(final['W_comp_cum_kWh'] - W_comp_recomp)
    if cum_err > 0.01:
        errors.append(f"Cumulative W_comp drift: {cum_err:.4f} kWh")

    # ── 10. GLOBAL ENERGY ACCOUNTING ──────────────────────────────────────
    print(f"\n--- 10. Global Energy Accounting ---")
    Q_solar_total = final.get("Q_solar_cum_kWh", 0)
    Q_cond_total = final["Q_cond_cum_kWh"]
    Q_hrx_total = final.get("Q_HRX_cum_kWh", 0)
    W_comp_total = final["W_comp_cum_kWh"]
    W_fan_total = final["W_fan_cum_kWh"]
    Q_evap_total = (df["Q_evap_kW"] * dt_s / 3600).sum()
    Q_latent = mw * 2450 / 3600  # kWh (approximate latent heat for all water)

    print(f"  Electrical inputs:")
    print(f"    W_comp:  {W_comp_total:.2f} kWh")
    print(f"    W_fan:   {W_fan_total:.2f} kWh")
    print(f"  Thermal inputs:")
    print(f"    Q_solar: {Q_solar_total:.2f} kWh")
    print(f"    Q_HRX:   {Q_hrx_total:.2f} kWh (recovered, not external)")
    print(f"    Q_evap:  {Q_evap_total:.2f} kWh (absorbed from evap source)")
    print(f"    Q_cond:  {Q_cond_total:.2f} kWh (= Q_evap + W_comp)")
    print(f"  Useful output:")
    print(f"    Q_latent (m_w * h_fg): {Q_latent:.2f} kWh")
    print(f"  First law check (refrigerant: Q_cond = Q_evap + W_shaft):")
    W_shaft_total = W_comp_total * eta_mech
    print(f"    Q_evap + W_shaft = {Q_evap_total + W_shaft_total:.2f} kWh")
    print(f"    Q_cond =           {Q_cond_total:.2f} kWh")
    fl_cum_err = abs((Q_evap_total + W_shaft_total) - Q_cond_total)
    print(f"    Difference:        {fl_cum_err:.4f} kWh "
          f"({'OK' if fl_cum_err < 0.01 else 'WARN'})")
    print(f"    Mech losses (W_comp*(1-eta)): {W_comp_total*(1-eta_mech):.4f} kWh")
    if fl_cum_err > 0.01:
        errors.append(f"Cumulative first law error: {fl_cum_err:.4f} kWh")

    # ── SUMMARY ───────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    if errors:
        print(f"RESULT: {len(errors)} ISSUE(S) FOUND")
        for e in errors:
            print(f"  - {e}")
    else:
        print("RESULT: ALL CHECKS PASSED")
    print(f"{'='*72}\n")

    return errors


def get_m_da(csv_path: Path) -> float:
    """Extract m_da from the simulation by back-computing from Q_cond and temperatures."""
    df = pd.read_csv(csv_path)
    # Use a row where HP is running (Q_cond > 0.1)
    mask = df["Q_cond_kW"] > 0.1
    if not mask.any():
        return 0.08  # fallback
    row = df[mask].iloc[0]
    dT = row["T_cond_out_C"] - row["T_air_in_cond_C"]
    if abs(dT) < 0.1:
        return 0.08
    # Q_cond_air ~ m_da * cp * dT (approximate — condenser effectiveness means
    # Q_cond_air < Q_cond_ref, but for m_da estimation this is close enough)
    # Better: read from config. For now use known value.
    return 0.08  # Will be overridden below


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify energy balance for E configs")
    parser.add_argument("--config", type=str, choices=["E1", "E2", "E3"], default=None)
    parser.add_argument("--location", type=str, default="kathmandu")
    parser.add_argument("--solar-area", type=float, default=10.0)
    args = parser.parse_args()

    OUTPUTS = PROJECT_ROOT / "outputs"

    # Get m_da by constructing config with correct elevation
    from rq1.config_solar_hp import (SimulationConfig, AmbientConfig,
                                      DryerConfig, SolarConfig, KineticsConfig)

    loc_elevations = {"kathmandu": 1350, "biratnagar": 72,
                      "dhulikhel": 1550, "taplejung": 1820}
    elev = loc_elevations.get(args.location, 0)

    # Use a dummy weather file — we only need geometry/m_da
    # Need a valid csv_path even though we won't read weather data
    _dummy_csv = PROJECT_ROOT / "data" / "weather" / "kathmandu_tmy.csv"
    _dummy_cfg = SimulationConfig(
        ambient=AmbientConfig(csv_path=_dummy_csv, elevation_m=elev),
        dryer=DryerConfig(T_set_C=45.0, m_p_dry_kg=3.0, n_trays=10,
                          target_velocity_m_s=1.1),
        display_geometry=False,
    )
    m_da = _dummy_cfg.dryer.m_da_kg_per_s
    print(f"m_da for {args.location} (elev={elev}m): {m_da:.4f} kg/s")

    configs_to_check = [args.config] if args.config else ["E2", "E3"]
    loc = args.location
    area = args.solar_area

    all_errors = {}
    for cfg_name in configs_to_check:
        csv_file = OUTPUTS / f"config_{cfg_name}/{loc}/Ac_{area:.0f}m2_hrx0.70.csv"
        if not csv_file.exists():
            print(f"\n[SKIP] {csv_file} not found")
            continue
        errs = verify_config(csv_file, cfg_name, m_da)
        all_errors[cfg_name] = errs

    # Final summary
    print(f"\n{'#'*72}")
    print(f"FINAL SUMMARY")
    print(f"{'#'*72}")
    for cfg_name, errs in all_errors.items():
        status = "PASS" if not errs else f"FAIL ({len(errs)} issues)"
        print(f"  {cfg_name}: {status}")
