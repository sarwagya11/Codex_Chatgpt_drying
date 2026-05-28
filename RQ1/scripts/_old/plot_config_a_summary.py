"""Config A vs Config 0: SEC + SMER bar summary across 4 sites x 5 weathers (annual + 4 seasons)."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SITES = ["biratnagar", "dhulikhel", "kathmandu", "taplejung"]
WEATHERS = ["annual", "spring_mar_apr", "summer_may_jun", "autumn_oct_nov", "winter_dec_jan"]
WLABEL = {"annual": "Annual", "spring_mar_apr": "Spring", "summer_may_jun": "Summer",
          "autumn_oct_nov": "Autumn", "winter_dec_jan": "Winter"}


def load(config_dir: Path, fname: str, site: str, weather: str):
    p = config_dir / site / (fname if weather == "annual" else f"{weather}/{fname}")
    if not p.exists():
        return None
    d = pd.read_csv(p).iloc[-1]
    return {
        "sec": float(d["SEC_elec_kWh_per_kg"]),
        "smer": float(d.get("SMER_kg_per_kWh", 1.0 / d["SEC_elec_kWh_per_kg"])),
        "time_h": float(d["time_h"]),
    }


def main():
    fig, axes = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True)
    x = np.arange(len(SITES) * len(WEATHERS))
    labels = [f"{s[:4].title()}\n{WLABEL[w]}" for s in SITES for w in WEATHERS]

    cfg0 = [load(ROOT / "outputs/config_0", "electric_baseline.csv", s, w) for s in SITES for w in WEATHERS]
    cfgA = [load(ROOT / "outputs/config_A", "baseline_r0.0.csv",      s, w) for s in SITES for w in WEATHERS]

    sec0 = [r["sec"] if r else np.nan for r in cfg0]
    secA = [r["sec"] if r else np.nan for r in cfgA]
    smer0 = [r["smer"] if r else np.nan for r in cfg0]
    smerA = [r["smer"] if r else np.nan for r in cfgA]

    w = 0.38
    # --- SEC panel ---
    ax = axes[0]
    b0 = ax.bar(x - w/2, sec0, w, color="#d62728", label="Config 0 (electric)")
    bA = ax.bar(x + w/2, secA, w, color="#1f77b4", label="Config A (HP r=0)")
    for bars, vals, smer in [(b0, sec0, smer0), (bA, secA, smerA)]:
        for bar, sec_v, smer_v in zip(bars, vals, smer):
            if not np.isnan(sec_v):
                ax.text(bar.get_x() + bar.get_width()/2, sec_v + 0.04,
                        f"{sec_v:.2f}\nSMER {smer_v:.2f}",
                        ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("SEC [kWh / kg water]")
    ax.set_title("Config 0 vs Config A: SEC with SMER (kg/kWh) per site × season")
    ax.legend(loc="upper right"); ax.grid(True, axis="y", alpha=0.3)
    ax.set_ylim(0, max([v for v in sec0 + secA if not np.isnan(v)]) * 1.25)

    # --- Drying time panel ---
    ax = axes[1]
    t0 = [r["time_h"] if r else np.nan for r in cfg0]
    tA = [r["time_h"] if r else np.nan for r in cfgA]
    ax.bar(x - w/2, t0, w, color="#d62728")
    ax.bar(x + w/2, tA, w, color="#1f77b4")
    for xi, (a, b) in enumerate(zip(t0, tA)):
        if not np.isnan(a):
            ax.text(xi - w/2, a + 0.3, f"{a:.1f}", ha="center", va="bottom", fontsize=7)
        if not np.isnan(b):
            ax.text(xi + w/2, b + 0.3, f"{b:.1f}", ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("Drying time [h]")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    out = ROOT / "plots" / "config_A_vs_0_summary.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"Saved {out}")

    # Also dump the table to CSV
    rows = []
    for s, w_ in [(s, w_) for s in SITES for w_ in WEATHERS]:
        i = SITES.index(s) * len(WEATHERS) + WEATHERS.index(w_)
        rows.append({
            "site": s, "weather": w_,
            "SEC_config0": sec0[i], "SMER_config0": smer0[i], "time_h_config0": t0[i],
            "SEC_configA": secA[i], "SMER_configA": smerA[i], "time_h_configA": tA[i],
        })
    df = pd.DataFrame(rows)
    out_csv = ROOT / "outputs" / "config_A_vs_0_summary.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved {out_csv}")


if __name__ == "__main__":
    main()
