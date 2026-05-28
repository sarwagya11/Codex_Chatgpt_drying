"""Step 3 — Energy split: where does each kWh come from and go?

Two questions answered, one closure each:

(A) HEAT DELIVERED TO INLET AIR (kWh):
      Q_cond  +  Q_solar_usable  +  Q_HRX_used   (heat that actually raises air to T_set)
    Source-side:
      Q_cond  ← W_comp + Q_evap   (HP cycle, η_mech = 0.95 baked into Q_cond/W_comp)
      Q_solar_usable ← Q_solar_gross − Q_solar_clipped   (clipped at T_set demand)
      Q_HRX_used ← Q_HRX_kW summed when not in bypass

(B) WHERE PAID ENERGY ENDS UP:
      Paid_in = W_total + Q_irradiance    (electricity bought + sun on aperture)
    Sinks (all dissipated to atmosphere):
      • Q_solar_clipped               ← collector saturated at T_set
      • Q_coll_thermal_loss           ← Q_irr − Q_solar_gross (UL+optical)
      • Q_exhaust_to_amb_after_HRX    ← exhaust enthalpy that leaves system
      • Q_evap_lifted_from_amb        ← HP took this from ambient (negative-cost)
      • W_fan irreversibility (≈W_fan)
    Useful product:
      • m_w (kg water evaporated)  ←  m_w · h_fg  carried out as vapor in exhaust

Note: chamber sensible drop = chamber latent gain (adiabatic-saturation-ish), so
they aren't independent line items. The latent enthalpy ends up in the exhaust
stream and is then either recovered (HRX condensation) or dumped.

Output: outputs/audit/step3_energy_split.csv
Plot:   plots/_audit/step3_energy_split_<config>.png
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

CP_AIR = 1.006   # kJ/kg.K
H_FG = 2442.0    # kJ/kg, reference latent heat at ~25 C
M_DA = 0.0929    # kg/s, canonical mass flow
A_COLL = 10.0    # m², canonical collector area


def trapz_kWh(s, t_s):
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    return float(np.sum(np.asarray(s) * dt_h))


def ledger(csv: Path) -> dict:
    rel = csv.relative_to(OUT).parts
    config = rel[0].replace("config_", "")
    location = rel[1]
    season = rel[2] if len(rel) > 3 else "annual"

    df = pd.read_csv(csv)
    t_s = df["time_s"].to_numpy()

    # === paid inputs ===
    W_comp = trapz_kWh(df["W_comp_kW"], t_s)
    W_fan = trapz_kWh(df["W_fan_kW"], t_s) if "W_fan_kW" in df.columns else 0.0
    W_total = W_comp + W_fan
    G = df["G_solar_Wm2"].to_numpy()
    Q_irr = float(np.sum(G * np.diff(t_s, prepend=t_s[0])) * A_COLL / 3.6e6)

    # === heat delivered to inlet air (the "thermal envelope" view) ===
    Q_cond = trapz_kWh(df["Q_cond_kW"], t_s)
    Q_evap = trapz_kWh(df["Q_evap_kW"], t_s)
    Q_HRX = trapz_kWh(df["Q_HRX_kW"], t_s) if "Q_HRX_kW" in df.columns else 0.0
    Q_sol_gross = trapz_kWh(df["Q_solar_kW"], t_s)
    Q_sol_usable = (trapz_kWh(df["Q_solar_usable_kW"], t_s)
                    if "Q_solar_usable_kW" in df.columns else Q_sol_gross)
    Q_sol_clipped = max(Q_sol_gross - Q_sol_usable, 0.0)

    Q_to_inlet = Q_cond + Q_sol_usable + Q_HRX  # heat delivered to air at T_set

    # === collector loss ===
    Q_coll_loss = max(Q_irr - Q_sol_gross, 0.0)

    # === exhaust enthalpy lost (after HRX recovery) ===
    # Sensible only (latent is treated separately as the useful carrier of m_w)
    exh_sens_kW = M_DA * CP_AIR * (df["T_exhaust_C"] - df["T_amb_C"])
    Q_exh_sens_total = trapz_kWh(exh_sens_kW.clip(lower=0), t_s)
    Q_exh_sens_lost = max(Q_exh_sens_total - Q_HRX, 0.0)

    # === useful: water evaporated (latent energy carried out) ===
    m_w = float(df["m_w_cum_kg"].iloc[-1])
    Q_useful_latent = m_w * H_FG / 3600.0  # kWh

    # === KPIs ===
    SEC = W_total / m_w if m_w > 1e-6 else float("nan")
    SMER = m_w / W_total if W_total > 1e-6 else float("nan")
    # what fraction of paid electricity ends up as latent (electrical efficiency)
    eta_elec = Q_useful_latent / W_total if W_total > 1e-6 else float("nan")
    # what fraction of paid (W_total + solar gross) ends up as latent
    eta_overall = Q_useful_latent / (W_total + Q_sol_usable) if W_total > 1e-6 else float("nan")
    # collector capture (gross)
    eta_coll = Q_sol_gross / Q_irr if Q_irr > 1e-6 else float("nan")
    # collector usable (after clipping)
    eta_coll_usable = Q_sol_usable / Q_irr if Q_irr > 1e-6 else float("nan")
    # HP COP (annualised)
    COP = Q_cond / W_comp if W_comp > 1e-6 else float("nan")
    # share of inlet-air heat from each source
    share_cond = Q_cond / Q_to_inlet if Q_to_inlet > 1e-6 else float("nan")
    share_solar = Q_sol_usable / Q_to_inlet if Q_to_inlet > 1e-6 else float("nan")
    share_hrx = Q_HRX / Q_to_inlet if Q_to_inlet > 1e-6 else float("nan")

    return dict(
        config=config, location=location, season=season,
        W_comp=W_comp, W_fan=W_fan, W_total=W_total,
        Q_irr=Q_irr, Q_sol_gross=Q_sol_gross, Q_sol_usable=Q_sol_usable,
        Q_sol_clipped=Q_sol_clipped, Q_coll_loss=Q_coll_loss,
        Q_HRX=Q_HRX, Q_evap=Q_evap, Q_cond=Q_cond, Q_to_inlet=Q_to_inlet,
        Q_exh_sens_lost=Q_exh_sens_lost,
        Q_useful_latent=Q_useful_latent,
        m_w=m_w, SEC=SEC, SMER=SMER, COP=COP,
        eta_elec=eta_elec, eta_overall=eta_overall,
        eta_coll=eta_coll, eta_coll_usable=eta_coll_usable,
        share_cond=share_cond, share_solar=share_solar, share_hrx=share_hrx,
    )


def plot_per_config(df: pd.DataFrame, config: str, out_path: Path):
    sub = df[df["config"] == config].copy()
    if sub.empty:
        return
    sub = sub.sort_values(["location", "season"])
    labels = [f"{r.location[:3]}\n{r.season[:6]}" for r in sub.itertuples()]
    x = np.arange(len(sub))
    w = 0.6

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Config {config} — energy ledger (no-VPD canonical)",
                 fontsize=12, weight="bold")

    # (1) inlet-air heat budget by source
    ax = axes[0]
    ax.bar(x, sub["Q_cond"], w, label="Q_cond (HP)", color="#d62728")
    bot = sub["Q_cond"].copy()
    ax.bar(x, sub["Q_sol_usable"], w, bottom=bot, label="Q_solar (usable)", color="#ff7f0e")
    bot += sub["Q_sol_usable"]
    ax.bar(x, sub["Q_HRX"], w, bottom=bot, label="Q_HRX", color="#1f77b4")
    ax.set_title("Heat delivered to inlet air (kWh)")
    ax.set_ylabel("kWh")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=8)
    ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")

    # (2) where solar irradiance ends up
    ax = axes[1]
    ax.bar(x, sub["Q_sol_usable"], w, label="solar → air (usable)", color="#2ca02c")
    bot = sub["Q_sol_usable"].copy()
    ax.bar(x, sub["Q_sol_clipped"], w, bottom=bot, label="clipped (over T_set)", color="#fdd835")
    bot += sub["Q_sol_clipped"]
    ax.bar(x, sub["Q_coll_loss"], w, bottom=bot, label="collector U_L+optical loss", color="#9467bd")
    ax.set_title("Solar irradiance fate (kWh)")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=8)
    ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")

    # (3) electricity → latent KPI
    ax = axes[2]
    ax.bar(x, sub["W_total"], w, label="W_total paid", color="#7f7f7f")
    ax.bar(x, sub["Q_useful_latent"], w * 0.5, label="Q_latent (useful)", color="#2ca02c")
    ax2 = ax.twinx()
    ax2.plot(x, sub["SEC"], "o-", color="black", label="SEC [kWh/kg]")
    ax.set_title("Electricity in → water out")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=8)
    ax.legend(fontsize=8, loc="upper left")
    ax2.legend(fontsize=8, loc="upper right")
    ax2.set_ylabel("SEC [kWh/kg]")
    ax.grid(alpha=0.3, axis="y")

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path.relative_to(PROJECT_ROOT)}")


def main():
    rows = []
    for csv in sorted(OUT.glob("config_E[123]/**/Ac_10m2_hrx0.70.csv")):
        try:
            rows.append(ledger(csv))
        except Exception as e:
            print(f"  skip {csv.relative_to(OUT)}: {e}")
    df = pd.DataFrame(rows)
    out_csv = AUDIT / "step3_energy_split.csv"
    df.to_csv(out_csv, index=False, float_format="%.6g")
    print(f"Saved {out_csv} ({len(df)} runs)\n")

    print("=== Per-config means (kWh) ===")
    means = df.groupby("config")[
        ["W_comp", "W_fan", "Q_irr", "Q_sol_gross", "Q_sol_usable",
         "Q_sol_clipped", "Q_coll_loss", "Q_HRX", "Q_cond", "Q_to_inlet",
         "Q_exh_sens_lost", "Q_useful_latent", "m_w", "SEC", "COP",
         "eta_elec", "eta_overall", "eta_coll", "eta_coll_usable",
         "share_cond", "share_solar", "share_hrx"]
    ].mean()
    print(means.to_string(float_format=lambda v: f"{v:8.3f}"))

    print("\n=== Inlet-air heat-source share (% of Q_to_inlet) ===")
    shares = means[["share_cond", "share_solar", "share_hrx"]] * 100
    print(shares.to_string(float_format=lambda v: f"{v:7.1f}%"))

    print("\n=== Solar collector capture (% of Q_irr) ===")
    print((means[["eta_coll", "eta_coll_usable"]] * 100)
          .to_string(float_format=lambda v: f"{v:7.1f}%"))

    print("\n=== Drying efficiency ===")
    print(means[["eta_elec", "eta_overall", "SEC"]]
          .to_string(float_format=lambda v: f"{v:7.4f}"))

    print("\nGenerating per-config plots...")
    for cfg in ("E1", "E2", "E3"):
        plot_per_config(df, cfg, PLOTS / f"step3_energy_split_{cfg}.png")


if __name__ == "__main__":
    main()
