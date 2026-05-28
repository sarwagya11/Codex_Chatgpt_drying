"""E2 vs E3 deep-dive: timestep-level decomposition of why E2 wins.

For KTM annual canonical (Ac_10m2_hrx0.70):
  1) Per-leg air-side ΔT for both configs (avg over run)
  2) Solar capture decomposition by hp_mode bin (E3) vs always-on (E2)
  3) Where E3 'saves' compressor work and where it 'pays it back'
  4) Solar clipping by hour-of-run
  5) Cumulative kWh trace alignment
  6) Cross-location robustness check

Output: outputs/audit/e2_vs_e3_deepdive.txt + plots/_audit/e2_vs_e3_*.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
PLOTS = PROJECT_ROOT / "plots" / "_audit"
AUDIT.mkdir(parents=True, exist_ok=True)
PLOTS.mkdir(parents=True, exist_ok=True)


def load(config: str, location: str = "kathmandu", season: str | None = None):
    if season:
        path = OUT / f"config_{config}/{location}/{season}/Ac_10m2_hrx0.70.csv"
    else:
        path = OUT / f"config_{config}/{location}/Ac_10m2_hrx0.70.csv"
    return pd.read_csv(path), path


def trapz_kWh(series_kW, t_s):
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    return float(np.sum(series_kW * dt_h))


def decompose_solar(df: pd.DataFrame):
    t_s = df["time_s"].to_numpy()
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    Qg = df["Q_solar_kW"].to_numpy()
    Qu = df["Q_solar_usable_kW"].to_numpy()
    daylight = Qg > 0.05
    return dict(
        gross=float(np.sum(Qg * dt_h)),
        usable=float(np.sum(Qu * dt_h)),
        clipped=float(np.sum((Qg - Qu) * dt_h)),
        daylight_h=float(np.sum(dt_h[daylight])),
    )


def deepdive_pair(loc: str = "kathmandu") -> str:
    e2, _ = load("E2", loc)
    e3, _ = load("E3", loc)
    out = []

    # 1. Average air-side T per leg
    legs = ["T_amb_C", "T_amb_heated_C", "T_solar_out_C", "T_air_in_cond_C",
            "T_cond_out_C", "T_to_chamber_C", "T_exhaust_C", "T_exh_cooled_C", "T_evap_source_C"]
    out.append(f"=== Mean air-state per leg ({loc} annual) ===")
    out.append(f"{'leg':22s}  {'E2':>8s}  {'E3':>8s}  {'ΔE3-E2':>8s}")
    for col in legs:
        m2 = e2[col].mean()
        m3 = e3[col].mean()
        out.append(f"{col:22s}  {m2:8.2f}  {m3:8.2f}  {m3 - m2:+8.2f}")

    # 2. Solar decomposition
    s2 = decompose_solar(e2)
    s3 = decompose_solar(e3)
    out.append(f"\n=== Solar decomposition (kWh) ===")
    out.append(f"{'metric':18s}  {'E2':>8s}  {'E3':>8s}  {'Δ':>8s}")
    for k in ["gross", "usable", "clipped"]:
        out.append(f"{k:18s}  {s2[k]:8.3f}  {s3[k]:8.3f}  {s3[k]-s2[k]:+8.3f}")
    out.append(f"capture_eff       {s2['usable']/s2['gross']:8.3f}  {s3['usable']/s3['gross']:8.3f}")

    # 3. Energy budget
    t2 = e2["time_s"].to_numpy(); t3 = e3["time_s"].to_numpy()
    W2 = trapz_kWh(e2["W_comp_kW"], t2);  W3 = trapz_kWh(e3["W_comp_kW"], t3)
    Qc2 = trapz_kWh(e2["Q_cond_kW"], t2); Qc3 = trapz_kWh(e3["Q_cond_kW"], t3)
    Qe2 = trapz_kWh(e2["Q_evap_kW"], t2); Qe3 = trapz_kWh(e3["Q_evap_kW"], t3)
    Wf2 = trapz_kWh(e2["W_fan_kW"], t2);  Wf3 = trapz_kWh(e3["W_fan_kW"], t3)
    Qhrx2 = trapz_kWh(e2["Q_HRX_kW"], t2); Qhrx3 = trapz_kWh(e3["Q_HRX_kW"], t3)

    out.append(f"\n=== Energy budget (kWh) ===")
    rows = [("Q_solar_usable", s2["usable"], s3["usable"]),
            ("Q_HRX",          Qhrx2,        Qhrx3),
            ("Q_cond",         Qc2,          Qc3),
            ("Q_evap",         Qe2,          Qe3),
            ("W_comp",         W2,           W3),
            ("W_fan",          Wf2,          Wf3),
            ("W_total",        W2 + Wf2,     W3 + Wf3)]
    out.append(f"{'metric':18s}  {'E2':>8s}  {'E3':>8s}  {'ΔE3-E2':>8s}")
    for n, v2, v3 in rows:
        out.append(f"{n:18s}  {v2:8.3f}  {v3:8.3f}  {v3-v2:+8.3f}")

    # 4. hp_mode breakdown — both label-based AND actual-W_comp-based
    W_OFF = 0.05  # kW: below this, HP is effectively off
    def mode_split(df):
        mode = df["hp_mode"].astype(str).str.lower().to_numpy()
        dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0
        total = dt_h.sum()
        return {m: float(dt_h[mode == m].sum() / total) for m in ["full", "partial", "off"]}
    def actual_split(df):
        W = df["W_comp_kW"].to_numpy()
        dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0
        total = dt_h.sum()
        W_running = W[W >= W_OFF]
        if len(W_running):
            W_med = float(np.median(W_running))
        else:
            W_med = 0.0
        off = W < W_OFF
        partial = (W >= W_OFF) & (W < 0.7 * W_med)
        full = W >= 0.7 * W_med
        return {
            "off": float(dt_h[off].sum() / total),
            "partial": float(dt_h[partial].sum() / total),
            "full": float(dt_h[full].sum() / total),
            "W_med_running": W_med,
        }
    m2 = mode_split(e2); m3 = mode_split(e3)
    a2 = actual_split(e2); a3 = actual_split(e3)
    out.append(f"\n=== hp_mode time fraction (LABEL — what hp_mode column says) ===")
    out.append(f"             E2       E3")
    for k in ["full", "partial", "off"]:
        out.append(f"  {k:8s}  {m2[k]:6.3f}  {m3[k]:6.3f}")
    out.append(f"\n=== hp_mode time fraction (ACTUAL — derived from W_comp_kW) ===")
    out.append(f"  W_OFF threshold = {W_OFF} kW")
    out.append(f"  W_med_running:   E2={a2['W_med_running']:.3f} kW   E3={a3['W_med_running']:.3f} kW")
    out.append(f"             E2       E3")
    for k in ["full", "partial", "off"]:
        out.append(f"  {k:8s}  {a2[k]:6.3f}  {a3[k]:6.3f}")

    # 5. Compressor work split: when does E3 save vs spend?
    # Bin by daylight (G > 100 W/m2) vs night
    G2 = e2["G_solar_Wm2"].to_numpy(); G3 = e3["G_solar_Wm2"].to_numpy()
    dt2 = np.diff(t2, prepend=t2[0]) / 3600.0
    dt3 = np.diff(t3, prepend=t3[0]) / 3600.0
    day2 = G2 > 100; day3 = G3 > 100
    W2_day = float(np.sum(e2["W_comp_kW"].to_numpy()[day2] * dt2[day2]))
    W2_nig = float(np.sum(e2["W_comp_kW"].to_numpy()[~day2] * dt2[~day2]))
    W3_day = float(np.sum(e3["W_comp_kW"].to_numpy()[day3] * dt3[day3]))
    W3_nig = float(np.sum(e3["W_comp_kW"].to_numpy()[~day3] * dt3[~day3]))
    out.append(f"\n=== W_comp by daylight (kWh) ===")
    out.append(f"             E2       E3       Δ")
    out.append(f"  daylight   {W2_day:6.3f}  {W3_day:6.3f}  {W3_day-W2_day:+6.3f}")
    out.append(f"  night      {W2_nig:6.3f}  {W3_nig:6.3f}  {W3_nig-W2_nig:+6.3f}")

    # 6. COP envelope
    def cop_full(df):
        m = df["hp_mode"].astype(str).str.lower().to_numpy()
        c = df["COP"].to_numpy()[m == "full"]
        c = c[np.isfinite(c)]
        return c
    c2 = cop_full(e2); c3 = cop_full(e3)
    out.append(f"\n=== COP at hp_mode='full' ===")
    out.append(f"           mean   median    p5      p95     min     max     n")
    out.append(f"  E2     {c2.mean():6.3f}  {np.median(c2):6.3f}  {np.percentile(c2,5):6.3f}  {np.percentile(c2,95):6.3f}  {c2.min():6.3f}  {c2.max():6.3f}  {len(c2)}")
    out.append(f"  E3     {c3.mean():6.3f}  {np.median(c3):6.3f}  {np.percentile(c3,5):6.3f}  {np.percentile(c3,95):6.3f}  {c3.min():6.3f}  {c3.max():6.3f}  {len(c3)}")

    # 7. Final SEC/SMER + drying time
    mw2 = float(e2["m_w_cum_kg"].iloc[-1]); mw3 = float(e3["m_w_cum_kg"].iloc[-1])
    out.append(f"\n=== Outputs ===")
    out.append(f"  drying_h   E2={e2['time_h'].iloc[-1]:.2f}   E3={e3['time_h'].iloc[-1]:.2f}")
    out.append(f"  m_w_kg     E2={mw2:.3f}    E3={mw3:.3f}")
    out.append(f"  SEC kWh/kg E2={(W2+Wf2)/mw2:.4f}  E3={(W3+Wf3)/mw3:.4f}  Δ={((W3+Wf3)/mw3)-((W2+Wf2)/mw2):+.4f}")
    out.append(f"  SMER kg/kWh E2={mw2/(W2+Wf2):.4f}  E3={mw3/(W3+Wf3):.4f}")

    return "\n".join(out)


def cross_location_table() -> str:
    rows = []
    for loc in ["biratnagar", "dhulikhel", "kathmandu", "taplejung"]:
        e2, _ = load("E2", loc); e3, _ = load("E3", loc)
        s2 = decompose_solar(e2); s3 = decompose_solar(e3)
        t2 = e2["time_s"].to_numpy(); t3 = e3["time_s"].to_numpy()
        W2 = trapz_kWh(e2["W_comp_kW"] + e2["W_fan_kW"], t2)
        W3 = trapz_kWh(e3["W_comp_kW"] + e3["W_fan_kW"], t3)
        mw2 = float(e2["m_w_cum_kg"].iloc[-1]); mw3 = float(e3["m_w_cum_kg"].iloc[-1])
        rows.append((loc, s2["usable"], s3["usable"], W2, W3,
                     W2/mw2, W3/mw3, mw2/W2, mw3/W3))
    out = ["", "=== Cross-location annual (canonical 10 m²) ===",
           f"{'loc':12s} {'Qsol_E2':>8s} {'Qsol_E3':>8s} {'W_E2':>7s} {'W_E3':>7s} {'SEC_E2':>7s} {'SEC_E3':>7s} {'SMER_E2':>8s} {'SMER_E3':>8s}"]
    for r in rows:
        out.append(f"{r[0]:12s} {r[1]:8.3f} {r[2]:8.3f} {r[3]:7.3f} {r[4]:7.3f} {r[5]:7.4f} {r[6]:7.4f} {r[7]:8.4f} {r[8]:8.4f}")
    return "\n".join(out)


def cumulative_plot(loc: str = "kathmandu"):
    e2, _ = load("E2", loc); e3, _ = load("E3", loc)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(f"E2 vs E3 cumulative trace — {loc} annual", fontsize=12, weight="bold")

    ax = axes[0, 0]
    ax.plot(e2["time_h"], e2["W_comp_cum_kWh"], label="E2", color="tab:blue", lw=2)
    ax.plot(e3["time_h"], e3["W_comp_cum_kWh"], label="E3", color="tab:red", lw=2)
    ax.set_ylabel("W_comp cumulative [kWh]"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[0, 1]
    ax.plot(e2["time_h"], e2["Q_solar_cum_kWh"], label="E2 solar", color="tab:blue", lw=2)
    ax.plot(e3["time_h"], e3["Q_solar_cum_kWh"], label="E3 solar", color="tab:red", lw=2)
    ax.set_ylabel("Q_solar usable cumulative [kWh]"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1, 0]
    ax.plot(e2["time_h"], e2["Q_cond_cum_kWh"], label="E2", color="tab:blue", lw=2)
    ax.plot(e3["time_h"], e3["Q_cond_cum_kWh"], label="E3", color="tab:red", lw=2)
    ax.set_ylabel("Q_cond cumulative [kWh]"); ax.set_xlabel("time [h]"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1, 1]
    ax.plot(e2["time_h"], e2["m_w_cum_kg"], label="E2", color="tab:blue", lw=2)
    ax.plot(e3["time_h"], e3["m_w_cum_kg"], label="E3", color="tab:red", lw=2)
    ax.set_ylabel("Water removed cumulative [kg]"); ax.set_xlabel("time [h]"); ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = PLOTS / f"e2_vs_e3_cumulative_{loc}.png"
    fig.savefig(out, dpi=140); plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def power_split_plot(loc: str = "kathmandu"):
    e2, _ = load("E2", loc); e3, _ = load("E3", loc)
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(f"E2 vs E3 instantaneous power — {loc} annual", fontsize=12, weight="bold")

    ax = axes[0]
    ax.plot(e2["time_h"], e2["W_comp_kW"], label="E2", color="tab:blue", lw=0.8)
    ax.plot(e3["time_h"], e3["W_comp_kW"], label="E3", color="tab:red", lw=0.8, alpha=0.85)
    ax.set_ylabel("W_comp [kW]"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(e2["time_h"], e2["Q_solar_usable_kW"], label="E2", color="tab:blue", lw=0.8)
    ax.plot(e3["time_h"], e3["Q_solar_usable_kW"], label="E3", color="tab:red", lw=0.8, alpha=0.85)
    ax.set_ylabel("Q_solar usable [kW]"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[2]
    ax.plot(e2["time_h"], e2["COP"], label="E2", color="tab:blue", lw=0.8)
    ax.plot(e3["time_h"], e3["COP"], label="E3", color="tab:red", lw=0.8, alpha=0.85)
    ax.set_ylabel("COP (raw)"); ax.set_xlabel("time [h]"); ax.legend(); ax.grid(alpha=0.3)
    ax.set_ylim(0, 10)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = PLOTS / f"e2_vs_e3_power_{loc}.png"
    fig.savefig(out, dpi=140); plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def main():
    text = deepdive_pair("kathmandu") + "\n" + cross_location_table()
    target = AUDIT / "e2_vs_e3_deepdive.txt"
    target.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved {target}")
    cumulative_plot("kathmandu")
    power_split_plot("kathmandu")


if __name__ == "__main__":
    main()
