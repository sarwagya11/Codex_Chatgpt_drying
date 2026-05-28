"""Config C2 (solar -> evap source, r=0) summary across 4 sites x 5 weathers x N areas.

Panels:
  1. SEC bars at A_solar=10 m^2 (with SMER labels)
  2. Drying time bars at A_solar=10 m^2
  3. Q_solar routed to evap-source vs wasted (stacked)
  4. Area sweep: SEC vs A_solar (one line per site, annual weather)

Config C2 (r=0) physics: chamber stream = Amb -> Cond -> Chamber.
Solar heats a parallel ambient stream and that warm air feeds the evaporator,
boosting T_evap and COP. So Q_solar_cum_kWh logs total collected solar and
Q_solar_to_evap_cum_kWh logs what landed on the evap side (~equal at r=0).
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SITES = ["biratnagar", "dhulikhel", "kathmandu", "taplejung"]
WEATHERS = ["annual", "spring_mar_apr", "summer_may_jun", "autumn_oct_nov", "winter_dec_jan"]
WLABEL = {"annual": "Annual", "spring_mar_apr": "Spring", "summer_may_jun": "Summer",
          "autumn_oct_nov": "Autumn", "winter_dec_jan": "Winter"}
AREAS = [2, 5, 10, 15, 20]
HEADLINE_AREA = 10
CFG_C = ROOT / "outputs" / "config_C2"


def load_run(site: str, weather: str, area: int):
    fname = f"Ac_{area}m2.csv"
    p = CFG_C / site / (fname if weather == "annual" else f"{weather}/{fname}")
    if not p.exists():
        return None
    d = pd.read_csv(p).iloc[-1]
    q_total = float(d.get("Q_solar_cum_kWh", 0.0))
    q_evap  = float(d.get("Q_solar_to_evap_cum_kWh", 0.0))
    q_wasted = float(d.get("Q_solar_wasted_cum_kWh", 0.0))
    return {
        "sec":      float(d["SEC_elec_kWh_per_kg"]),
        "smer":     float(d.get("SMER_kg_per_kWh", 1.0 / d["SEC_elec_kWh_per_kg"])),
        "time_h":   float(d["time_h"]),
        "q_total":  q_total,
        "q_evap":   q_evap,
        "q_wasted": q_wasted,
    }


def main():
    fig, axes = plt.subplots(4, 1, figsize=(14, 14), sharex=False)

    pairs = [(s, w) for s in SITES for w in WEATHERS]
    x = np.arange(len(pairs))
    xlabels = [f"{s[:4].title()}\n{WLABEL[w]}" for s, w in pairs]

    headline = [load_run(s, w, HEADLINE_AREA) for s, w in pairs]
    sec  = [r["sec"]      if r else np.nan for r in headline]
    smer = [r["smer"]     if r else np.nan for r in headline]
    tim  = [r["time_h"]   if r else np.nan for r in headline]
    qevap = [r["q_evap"]    if r else np.nan for r in headline]
    qwas  = [r["q_wasted"]  if r else np.nan for r in headline]

    # --- Panel 1: SEC + SMER labels ---
    ax = axes[0]
    bars = ax.bar(x, sec, 0.7, color="#17becf", edgecolor="black", linewidth=0.4)
    for b, s_v, m_v in zip(bars, sec, smer):
        if not np.isnan(s_v):
            ax.text(b.get_x() + b.get_width()/2, s_v + 0.01,
                    f"{s_v:.2f}\nSMER {m_v:.2f}", ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("SEC [kWh / kg water]")
    ax.set_title(f"Config C2 (solar -> evap, r=0) — A_solar = {HEADLINE_AREA} m²")
    ax.grid(True, axis="y", alpha=0.3)
    vals = [v for v in sec if not np.isnan(v)]
    if vals: ax.set_ylim(0, max(vals) * 1.30)
    ax.set_xticks(x); ax.set_xticklabels([""] * len(x))

    # --- Panel 2: Drying time ---
    ax = axes[1]
    ax.bar(x, tim, 0.7, color="#1f77b4", edgecolor="black", linewidth=0.4)
    for xi, t in enumerate(tim):
        if not np.isnan(t):
            ax.text(xi, t + 0.3, f"{t:.1f}", ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("Drying time [h]")
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_xticks(x); ax.set_xticklabels([""] * len(x))

    # --- Panel 3: Q_solar routed to evap vs wasted ---
    ax = axes[2]
    ax.bar(x, qevap, 0.7, color="#ff7f0e", edgecolor="black", linewidth=0.4,
           label="Q_solar -> evap source")
    ax.bar(x, qwas, 0.7, bottom=qevap, color="#7f7f7f", edgecolor="black", linewidth=0.4,
           label="Q_solar wasted")
    for xi, (e, w) in enumerate(zip(qevap, qwas)):
        if not np.isnan(e):
            tot = e + w
            ax.text(xi, tot + 0.6, f"{e:.1f}+{w:.1f}",
                    ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("Q_solar [kWh]")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_xticks(x); ax.set_xticklabels(xlabels, fontsize=8)

    # --- Panel 4: Area sweep (annual only) ---
    ax = axes[3]
    colors = {"biratnagar": "#d62728", "dhulikhel": "#9467bd",
              "kathmandu": "#1f77b4", "taplejung": "#2ca02c"}
    for site in SITES:
        ys = []
        for a in AREAS:
            r = load_run(site, "annual", a)
            ys.append(r["sec"] if r else np.nan)
        ax.plot(AREAS, ys, marker="o", color=colors[site], label=site.title())
        for a, y in zip(AREAS, ys):
            if not np.isnan(y):
                ax.text(a, y + 0.01, f"{y:.2f}", ha="center", va="bottom", fontsize=7)
    ax.set_xlabel("Solar collector area A_solar [m²]")
    ax.set_ylabel("SEC [kWh / kg water]  (annual)")
    ax.set_title("Area sweep — annual weather")
    ax.legend(loc="upper right", fontsize=8); ax.grid(True, alpha=0.3)
    ax.set_xticks(AREAS)

    fig.tight_layout()
    out = ROOT / "plots" / "config_C_summary.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"Saved {out}")

    # --- Dump tables ---
    rows = []
    for s in SITES:
        for w in WEATHERS:
            for a in AREAS:
                r = load_run(s, w, a)
                if r is None: continue
                rows.append({"site": s, "weather": w, "A_solar_m2": a, **r})
    df = pd.DataFrame(rows)
    out_csv = ROOT / "outputs" / "config_C_sweep_summary.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved {out_csv}")

    head = df[df["A_solar_m2"] == HEADLINE_AREA][
        ["site", "weather", "sec", "smer", "time_h", "q_evap", "q_wasted"]
    ]
    out_head = ROOT / "outputs" / f"config_C_summary_A{HEADLINE_AREA}.csv"
    head.to_csv(out_head, index=False)
    print(f"Saved {out_head}")


if __name__ == "__main__":
    main()
