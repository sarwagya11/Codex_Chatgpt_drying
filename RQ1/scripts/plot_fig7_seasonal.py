"""Figure 7: seasonal SEC and solar capture for the preferred topology (E2).

Two-panel figure across four meteorological seasons (autumn Oct-Nov,
winter Dec-Jan, spring Mar-Apr, summer May-Jun) at the four Nepali sites:
  (a) E2 SEC by season, grouped by site, with the annual baseline marked.
  (b) E2 cumulative solar capture (Q_solar) by season, showing the winter
      irradiance trough that drives the SEC peak.

Source: outputs/paper_matrix_summary.csv (block = "seasonal", config = E2).
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
SEASONS = ["autumn_oct_nov", "winter_dec_jan", "spring_mar_apr", "summer_may_jun"]
SEASON_LABELS = {
    "autumn_oct_nov": "Autumn\n(Oct-Nov)",
    "winter_dec_jan": "Winter\n(Dec-Jan)",
    "spring_mar_apr": "Spring\n(Mar-Apr)",
    "summer_may_jun": "Summer\n(May-Jun)",
}


def main() -> None:
    df = pd.read_csv(CSV)
    e2_s = df[(df.block == "seasonal") & (df.config == "E2")].copy()
    e2_a = df[(df.block == "annual") & (df.config == "E2")].set_index("location")["SEC_kWh_per_kg"].to_dict()

    sec_pv = e2_s.pivot_table(index="location", columns="season", values="SEC_kWh_per_kg").reindex(index=SITES, columns=SEASONS)
    qsol_pv = e2_s.pivot_table(index="location", columns="season", values="Q_solar_kWh").reindex(index=SITES, columns=SEASONS)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.8), dpi=200)

    n_seasons = len(SEASONS)
    n_sites = len(SITES)
    x = np.arange(n_seasons)
    bar_w = 0.18

    for i, site in enumerate(SITES):
        offset = (i - (n_sites - 1) / 2) * bar_w
        vals = sec_pv.loc[site].values
        ax1.bar(x + offset, vals, bar_w, color=SITE_COLORS[site], edgecolor="black", linewidth=0.5, label=SITE_LABELS[site])
        ann = e2_a[site]
        ax1.hlines(ann, x[0] + offset - bar_w / 2, x[-1] + offset + bar_w / 2,
                   colors=SITE_COLORS[site], linestyles=":", linewidth=1.2, alpha=0.75)

    ax1.set_xticks(x)
    ax1.set_xticklabels([SEASON_LABELS[s] for s in SEASONS], fontsize=9)
    ax1.set_ylabel(r"SEC  (kWh kg$^{-1}$ water)", fontsize=10)
    ax1.set_title("(a) E2 specific energy consumption by season", fontsize=10.5, fontweight="bold")
    ax1.grid(axis="y", linestyle=":", alpha=0.45)
    ax1.set_axisbelow(True)
    ax1.legend(loc="upper right", fontsize=8.2, ncol=2, frameon=True, framealpha=0.95)
    cur_lo, cur_hi = ax1.get_ylim()
    ax1.set_ylim(0, cur_hi * 1.15)
    ax1.text(0.02, 0.95, "Dotted line: annual baseline\nat each site (Table 7)",
             transform=ax1.transAxes, fontsize=8, va="top",
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="grey", alpha=0.9))

    for i, site in enumerate(SITES):
        offset = (i - (n_sites - 1) / 2) * bar_w
        vals = qsol_pv.loc[site].values
        ax2.bar(x + offset, vals, bar_w, color=SITE_COLORS[site], edgecolor="black", linewidth=0.5, label=SITE_LABELS[site])

    ax2.set_xticks(x)
    ax2.set_xticklabels([SEASON_LABELS[s] for s in SEASONS], fontsize=9)
    ax2.set_ylabel(r"$Q_\mathrm{solar}$ per batch  (kWh)", fontsize=10)
    ax2.set_title("(b) E2 cumulative solar capture by season", fontsize=10.5, fontweight="bold")
    ax2.grid(axis="y", linestyle=":", alpha=0.45)
    ax2.set_axisbelow(True)
    ax2.legend(loc="lower right", fontsize=8.2, ncol=2, frameon=True, framealpha=0.95)
    cur_lo, cur_hi = ax2.get_ylim()
    ax2.set_ylim(0, cur_hi * 1.15)

    fig.suptitle(
        "Seasonal breakdown of E2 at the four Nepali sites "
        r"($A_c = 10\ \mathrm{m}^2$, $T_\mathrm{set} = 45\ \mathrm{^\circ C}$, $r = 0$)",
        fontsize=11.5, y=1.00,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out_png = OUT_DIR / "fig7_seasonal.png"
    out_svg = OUT_DIR / "fig7_seasonal.svg"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    print(f"wrote {out_png}")
    print(f"wrote {out_svg}")


if __name__ == "__main__":
    main()
