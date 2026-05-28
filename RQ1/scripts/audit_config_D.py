"""Exhaustive Config D audit: D1 vs D2, paper-headline (vpd-on).


Component-by-component physics check + mass flow accounting at one
representative case (KTM annual) and one stress case (BTN summer).

Checks:
  1. Mass-flow architecture and per-component flow rates.
  2. HRX effectiveness back-out (T_amb_heated formula vs logged) and Q_HRX.
  3. Condenser air-side energy balance.
  4. Evaporator source temperature and ambient mix-in (D2 only).
  5. Heat-pump first law on shaft work (Q_cond = Q_evap + W_shaft).
  6. Water mass balance (sum of dm_w == m_w_cum).
  7. Frost margin (T_evap vs T_evap_min_C).
  8. HRX condensation events and water-mass attribution.
  9. Fan share of W_elec and per-step W_elec consistency.
 10. Time-series sanity: T_evap, COP, ω_to_chamber over ambient cycle.
"""
from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    make_config_D_HRX,
)


def load_cfg(loc: str, weather: str = "annual"):
    if weather == "annual":
        amb = ROOT / "data" / "ambient" / f"{loc}_pvgis_standard.csv"
    else:
        amb = ROOT / "data" / "ambient" / "seasonal" / f"{loc}_{weather}.csv"
    return make_config_D_HRX(
        d_variant="D1", eps_HRX=0.70, vpd_bypass_thresh=0.05,
        ambient_csv=amb, elevation_m=LOCATION_ELEVATIONS_M.get(loc, 0),
        phase2_root=ROOT / "outputs",
    )


def audit_case(label: str, csv: Path, cfg):
    print(f"\n{'='*78}\n{label}\nFile: {csv.relative_to(ROOT)}\n{'='*78}")
    d = pd.read_csv(csv)
    last = d.iloc[-1]
    n = len(d)
    dt_s = float(np.median(np.diff(d["time_s"].values)))
    cp = 1.006  # kJ/kg-K dry air sensible
    eps_HRX = cfg.dryer.eps_HRX
    m_da = cfg.dryer.m_da_kg_per_s

    # 1. Mass flow architecture
    print("\n[1] Mass-flow architecture")
    print(f"    m_da (dry air): {m_da:.4f} kg/s = {m_da*3600:.1f} kg/h")
    print(f"    rho_air         : {cfg.dryer.air_density_kg_per_m3:.4f} kg/m³")
    print(f"    A_cross       : {cfg.dryer.tray_width_m*cfg.dryer.air_gap_m:.4f} m²"
          f"  (tray_width {cfg.dryer.tray_width_m:.3f} × air_gap {cfg.dryer.air_gap_m:.3f})")
    v = m_da / (cfg.dryer.air_density_kg_per_m3 * cfg.dryer.tray_width_m * cfg.dryer.air_gap_m)
    print(f"    v_air (recomp): {v:.3f} m/s  (target {cfg.dryer.target_velocity_m_s:.2f})")
    print(f"    Per-component m_da:")
    print(f"      HRX cold (Amb→preheated): {m_da:.4f} kg/s")
    print(f"      Condenser (air side)   : {m_da:.4f} kg/s")
    print(f"      Chamber (10 trays)     : {m_da:.4f} kg/s")
    print(f"      Exhaust → HRX hot      : {m_da:.4f} kg/s")
    if "D2" in label:
        # D2 evaporator may have ambient supplement (L1140-1156)
        print(f"      Evap source (D2)       : {m_da:.4f} kg/s base + ambient supp. if Q_exh insufficient")
    else:
        print(f"      Evap source (D1)       : separate outdoor coil (refrigerant-side only)")

    # 2. HRX effectiveness back-out
    print("\n[2] HRX effectiveness check")
    # T_amb_heated = T_amb + eps * (T_exh - T_amb) → eps = (T_amb_heated - T_amb)/(T_exh - T_amb)
    drv = d["T_exhaust_C"] - d["T_amb_C"]
    valid = drv.abs() > 0.5
    eps_back = ((d["T_amb_heated_C"] - d["T_amb_C"]) / drv).where(valid)
    print(f"    eps_HRX configured: {eps_HRX:.3f}")
    print(f"    eps_HRX back-out  : mean={eps_back.mean():.4f}  std={eps_back.std():.4f}"
          f"  (rows with |ΔT|>0.5K: {valid.sum()}/{n})")
    # Q_HRX consistency: Q_HRX_kW ≈ m_da * cp * (T_amb_heated - T_amb)  (sensible part only)
    Q_HRX_sensible = m_da * cp * (d["T_amb_heated_C"] - d["T_amb_C"])
    res = (d["Q_HRX_kW"] - Q_HRX_sensible).abs()
    print(f"    Q_HRX sensible match: mean|Δ|={res.mean():.3e} kW, max|Δ|={res.max():.3e} kW"
          f"  (full enthalpy method includes latent if condensation)")
    cond_steps = int(d.get("HRX_condensation", pd.Series([0]*n)).sum())
    print(f"    HRX condensation events: {cond_steps}/{n} steps")
    print(f"    Q_HRX_cum: {last['Q_HRX_cum_kWh']:.3f} kWh (only counted when bypass inactive)")

    # 3. Condenser air-side balance
    print("\n[3] Condenser air-side energy balance")
    # T_to_chamber depends on bypass mode; in normal D1/D2 mode, supply is T_amb_heated
    Q_cond_air = m_da * cp * (d["T_to_chamber_C"] - d["T_amb_heated_C"])
    # Q_cond_kW logged is refrigerant-side cond duty; air-side should match within eps_cond clip.
    nominal = (d["bypass_mode"] == "none") if "bypass_mode" in d.columns else pd.Series([True]*n)
    qres = (d["Q_cond_kW"] - Q_cond_air).where(nominal)
    print(f"    Normal-mode rows: {int(nominal.sum())}/{n}")
    print(f"    Q_cond air-side mean (normal): {Q_cond_air.where(nominal).mean():.3f} kW")
    print(f"    Q_cond refrig (logged) mean : {d['Q_cond_kW'].where(nominal).mean():.3f} kW")
    print(f"    Q_cond residual (refrig-air): mean={qres.mean():.4f} kW, max|Δ|={qres.abs().max():.4f} kW")

    # 4. Evap source (D2)
    if "D2" in label:
        print("\n[4] Evaporator source (D2): cooled-exhaust + ambient mix-in")
        # No direct T_evap_source column logged for D2; back out via instantaneous T_evap = source - DT_approach
        # T_evap_C is refrigerant evap; source ≈ T_evap_C + DT_evap_approach (default 10K)
        DT = cfg.heatpump.DT_evap_approach
        T_src_back = d["T_evap_C"] + DT
        print(f"    DT_evap_approach: {DT:.1f} K")
        print(f"    T_exh_cooled mean: {d['T_exh_cooled_C'].mean():.2f} °C")
        print(f"    T_evap_source (back-out): mean={T_src_back.mean():.2f} °C  vs T_exh_cooled mean {d['T_exh_cooled_C'].mean():.2f} °C")
        # Cases where T_src > T_exh_cooled => ambient was mixed in to boost source
        mix_in = (T_src_back - d['T_exh_cooled_C']) > 0.5
        print(f"    Steps with ambient mix-in (T_src > T_exh_cooled+0.5K): {int(mix_in.sum())}/{n}")

    # 5. HP first law (shaft work)
    print("\n[5] HP first law on refrigerant (shaft)")
    eta_m = cfg.heatpump.eta_mechanical
    W_shaft = d["W_comp_kW"] * eta_m
    res_inst = d["Q_cond_kW"] - (d["Q_evap_kW"] + W_shaft)
    print(f"    eta_mechanical: {eta_m:.3f}")
    print(f"    instantaneous residual (Q_cond - Q_evap - W_shaft):"
          f"  mean={res_inst.abs().mean():.3e}  max={res_inst.abs().max():.3e} kW")
    Qc = last["Q_cond_cum_kWh"]
    W = last["W_comp_cum_kWh"]
    Qe_cum_left = (d["Q_evap_kW"].values * np.append(np.diff(d["time_s"].values), 0) / 3600.0).sum()
    print(f"    Q_cond_cum {Qc:.3f}  vs Q_evap_cum {Qe_cum_left:.3f} + W_shaft_cum {W*eta_m:.3f}"
          f"  = {Qe_cum_left + W*eta_m:.3f}  | gap = {Qc - Qe_cum_left - W*eta_m:.3f} kWh")

    # 6. Water mass balance
    print("\n[6] Water mass balance")
    sum_dm = d["dm_w_total_kg"].sum()
    print(f"    sum(dm_w_total_kg): {sum_dm:.6f} kg  |  m_w_cum_kg: {last['m_w_cum_kg']:.6f}  |  diff: {sum_dm-last['m_w_cum_kg']:.2e}")

    # 7. Frost margin
    print("\n[7] Frost margin (T_evap vs floor)")
    Tev_min = cfg.heatpump.T_evap_min_C
    print(f"    T_evap_min_C: {Tev_min:.1f}  | T_evap mean {d['T_evap_C'].mean():.2f}  min {d['T_evap_C'].min():.2f}  max {d['T_evap_C'].max():.2f}")
    near_frost = (d["T_evap_C"] - Tev_min).abs() < 0.5
    print(f"    Steps within 0.5 K of frost floor: {int(near_frost.sum())}/{n}")

    # 8. HRX condensation
    print("\n[8] HRX condensation accounting")
    # When condensation: omega_exh_cooled < omega_exhaust (water dropped out on hot side).
    if "omega_exh_cooled" in d.columns:
        # We don't log omega_exhaust separately, but the flag tracks it.
        cs = int(d["HRX_condensation"].sum()) if "HRX_condensation" in d.columns else cond_steps
        print(f"    Condensation flag-on steps: {cs}/{n}  ({100*cs/n:.1f}%)")
    else:
        print("    omega_exh_cooled not logged")

    # 9. Fan share
    print("\n[9] Fan share")
    Wfan = last["W_fan_cum_kWh"]
    Welec_total = (W + Wfan)
    print(f"    W_comp_cum: {W:.3f} kWh  ({100*W/Welec_total:.1f}%)")
    print(f"    W_fan_cum : {Wfan:.3f} kWh  ({100*Wfan/Welec_total:.1f}%)")
    print(f"    SEC_elec  : {last['SEC_elec_kWh_per_kg']:.4f} kWh/kg")
    print(f"    Drying time: {last['time_h']:.2f} h")

    # 10. Headline kinematics
    print("\n[10] Headline COP & temperatures")
    print(f"    COP mean (normal mode): {d['COP'].where(nominal).mean():.3f}")
    print(f"    T_cond mean: {d['T_cond_C'].mean():.2f} °C  (set+approach = {cfg.dryer.T_set_C + cfg.heatpump.DT_evap_approach:.1f} would be ideal cond_sat - not used here)")
    print(f"    T_to_chamber mean: {d['T_to_chamber_C'].mean():.2f} °C (target {cfg.dryer.T_set_C:.1f})")
    print(f"    omega_to_chamber mean: {d['omega_to_chamber'].mean()*1000:.3f} g/kg")
    print(f"    VPD-bypass active: {int(d.get('vpd_bypass_active', pd.Series([0]*n)).sum())}/{n} steps")


def main():
    cases = [
        ("D1 KTM annual (vpd-on)", "outputs/config_D1/kathmandu/hrx_eps0.70_vpd0.05.csv"),
        ("D2 KTM annual (vpd-on)", "outputs/config_D2/kathmandu/hrx_eps0.70_vpd0.05.csv"),
        ("D1 BTN summer (vpd-on)", "outputs/config_D1/biratnagar/summer_may_jun/hrx_eps0.70_vpd0.05.csv"),
        ("D2 BTN summer (vpd-on)", "outputs/config_D2/biratnagar/summer_may_jun/hrx_eps0.70_vpd0.05.csv"),
    ]
    cfg = load_cfg("kathmandu")  # geometry & m_da same across sites
    for label, p in cases:
        audit_case(label, ROOT / p, cfg)


if __name__ == "__main__":
    main()
