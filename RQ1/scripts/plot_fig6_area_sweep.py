"""Figure 6: E2 collector-area sweep at the four Nepali sites.

Two-panel figure:
  (a) SEC vs A_c at A_c in {2, 4, 6, 8, 10, 12, 15} m^2 for the four sites,
      with the 10 m^2 baseline marked.
  (b) Cumulative fractional SEC reduction relative to the A_c = 2 m^2 floor,
      normalised to the largest reduction in the sweep (A_c = 15 m^2). The
      knee in panel (a) appears here as the area at which the curve crosses
      80 % and 90 % of its maximum.

Source: outputs/paper_matrix_summary.csv (block = "solar_sweep", config = E2).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "outputs" / "paper_matrix_summary.csv"
OUT_DIR = ROOT / "outputs" / "paperplots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITES = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
SITE_LABELS = {
    "biratnagar": "Biratnagar (72 m)",
    "kathmandu":  "Kathmandu (1350 m)",
    "dhulikhel":  "Dhulikhel (1550 m)",
    "taplejung":  "Taplejung (1820 m)",
}
SITE_COLORS = {
    "biratnagar": "#d62728",
    "kathmandu":  "#1f77b4",
    "dhulikhel":  "#2ca02c",
    "taplejung":  "#9467bd",
}


def main() -> None:
    df = pd.read_csv(CSV)
    sub = df[(df["block"] == "solar_sweep") & (df["config"] == "E2")].copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.8), dpi=200)

    for site in SITES:
        s = sub[sub.location == site].sort_values("solar_area_m2")
        ax1.plot(s["solar_area_m2"], s["SEC_kWh_per_kg"],
                 marker="o", linestyle="-",
                 color=SITE_COLORS[site], linewidth=2.0, markersize=7,
                 label=SITE_LABELS[site])

    ax1.axvline(10.0, color="black", linestyle=":", linewidth=1.2, alpha=0.6)
    cur_lo, cur_hi = ax1.get_ylim()
    ax1.text(10.0, cur_hi * 0.97, "  $A_c = 10\\ \\mathrm{m}^2$\n  (baseline)",
             ha="left", va="top", fontsize=8.5, color="#404040")

    ax1.set_xlabel(r"Collector area $A_c$  (m$^2$)", fontsize=10)
    ax1.set_ylabel(r"SEC  (kWh kg$^{-1}$ water)", fontsize=10)
    ax1.set_title("(a) SEC vs collector area — E2, annual TMY, $r = 0$", fontsize=10.5, fontweight="bold")
    ax1.grid(linestyle=":", alpha=0.45)
    ax1.legend(loc="upper right", fontsize=8.5, frameon=True, framealpha=0.95)
    ax1.set_xticks([2, 4, 6, 8, 10, 12, 15])

    for site in SITES:
        s = sub[sub.location == site].sort_values("solar_area_m2").reset_index(drop=True)
        sec0 = s["SEC_kWh_per_kg"].iloc[0]
        sec_min = s["SEC_kWh_per_kg"].iloc[-1]
        denom = sec0 - sec_min
        if denom <= 0:
            continue
        frac = (sec0 - s["SEC_kWh_per_kg"]) / denom * 100.0
        ax2.plot(s["solar_area_m2"], frac, marker="o", linestyle="-",
                 color=SITE_COLORS[site], linewidth=2.0, markersize=7,
                 label=SITE_LABELS[site])

    for thresh, label in [(80, "80 %"), (90, "90 %")]:
        ax2.axhline(thresh, color="black", linestyle="--", linewidth=0.8, alpha=0.5)
        ax2.text(15.4, thresh, label, va="center", ha="left", fontsize=8, color="#404040")

    ax2.axvline(10.0, color="black", linestyle=":", linewidth=1.2, alpha=0.6)

    ax2.set_xlabel(r"Collector area $A_c$  (m$^2$)", fontsize=10)
    ax2.set_ylabel("Fraction of maximum SEC reduction  (%)", fontsize=10)
    ax2.set_title("(b) Diminishing-returns knee, normalised to $A_c = 15\\ \\mathrm{m}^2$ ceiling",
                  fontsize=10.5, fontweight="bold")
    ax2.grid(linestyle=":", alpha=0.45)
    ax2.legend(loc="lower right", fontsize=8.5, frameon=True, framealpha=0.95)
    ax2.set_xticks([2, 4, 6, 8, 10, 12, 15])
    ax2.set_xlim(1.5, 16)
    ax2.set_ylim(-3, 105)

    fig.suptitle("Collector-area sweep for the preferred topology (E2)",
                 fontsize=11.5, y=1.00)
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out_png = OUT_DIR / "fig6_area_sweep.png"
    out_svg = OUT_DIR / "fig6_area_sweep.svg"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    print(f"wrote {out_png}")
    print(f"wrote {out_svg}")


if __name__ == "__main__":
    main()
