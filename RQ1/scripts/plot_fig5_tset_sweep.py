"""Figure 5: T_set sensitivity for E2 (pre-cond) vs E3 (post-cond).

Two stacked panels:
  (a) SEC vs T_set, 4 sites x 2 configs (8 traces). Solid = E2, dashed = E3.
  (b) Relative E2-over-E3 SEC advantage vs T_set, one trace per site.

Source: outputs/T_sweep_summary.csv (E2/E3 x 4 sites x T_set {40,45,50,55}).
T_set in {40, 45, 50} is inside the kinetic calibration band (40-50 C);
55 C is shaded as a +5 K extrapolation.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "outputs" / "T_sweep_summary.csv"
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

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.6, 8.4), dpi=200,
                                   gridspec_kw={"height_ratios": [1.3, 1.0]})

    T_vals = sorted(df["T_set"].unique())

    for site in SITES:
        color = SITE_COLORS[site]
        e2 = df[(df.cfg == "E2") & (df.site == site)].sort_values("T_set")
        e3 = df[(df.cfg == "E3") & (df.site == site)].sort_values("T_set")
        ax1.plot(e2["T_set"], e2["SEC"], marker="o", linestyle="-",
                 color=color, linewidth=2.0, markersize=6,
                 label=f"{SITE_LABELS[site]} — E2 (pre-cond)")
        ax1.plot(e3["T_set"], e3["SEC"], marker="s", linestyle="--",
                 color=color, linewidth=1.6, markersize=5,
                 label=f"{SITE_LABELS[site]} — E3 (post-cond)")

    cur_lo, cur_hi = ax1.get_ylim()
    ax1.axvspan(50, 56, alpha=0.10, color="grey", zorder=0)
    ax1.text(52.5, cur_hi - (cur_hi - cur_lo) * 0.05,
             "+5 K kinetic extrapolation",
             ha="center", va="top", fontsize=8.5, color="#404040",
             style="italic")
    ax1.set_xlim(39, 56)
    ax1.set_ylim(cur_lo, cur_hi)

    ax1.set_xticks(T_vals)
    ax1.set_xlabel(r"$T_\mathrm{set}$  ($^\circ$C)", fontsize=10)
    ax1.set_ylabel(r"SEC  (kWh kg$^{-1}$ water)", fontsize=10)
    ax1.set_title("(a) SEC vs set-point — E2 (solid) vs E3 (dashed) at four sites", fontsize=10.5, fontweight="bold")
    ax1.grid(linestyle=":", alpha=0.45)
    ax1.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
               fontsize=7.8, frameon=True, framealpha=0.95)

    for site in SITES:
        color = SITE_COLORS[site]
        e2 = df[(df.cfg == "E2") & (df.site == site)].sort_values("T_set").reset_index(drop=True)
        e3 = df[(df.cfg == "E3") & (df.site == site)].sort_values("T_set").reset_index(drop=True)
        gap_pct = (e3["SEC"].values - e2["SEC"].values) / e2["SEC"].values * 100.0
        ax2.plot(e2["T_set"], gap_pct, marker="o", linestyle="-",
                 color=color, linewidth=2.0, markersize=6,
                 label=SITE_LABELS[site])
        for x, y in zip(e2["T_set"], gap_pct):
            ax2.annotate(f"{y:.1f}%", xy=(x, y), xytext=(0, 7),
                         textcoords="offset points",
                         ha="center", fontsize=7.5, color=color)

    ax2.axvspan(50, 56, alpha=0.10, color="grey", zorder=0)
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlim(39, 56)
    ax2.set_xticks(T_vals)
    ax2.set_xlabel(r"$T_\mathrm{set}$  ($^\circ$C)", fontsize=10)
    ax2.set_ylabel("E3 SEC relative to E2  (%)", fontsize=10)
    ax2.set_title("(b) Post-condenser placement penalty widens with $T_\\mathrm{set}$ at every site",
                  fontsize=10.5, fontweight="bold")
    ax2.grid(linestyle=":", alpha=0.45)
    ax2.legend(loc="upper left", fontsize=8.5, frameon=True, framealpha=0.95)

    fig.suptitle(
        r"Set-point sensitivity of pre-cond vs post-cond placement at $A_c = 10\ \mathrm{m}^2$, $r = 0$",
        fontsize=11.5, y=1.00,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    out_png = OUT_DIR / "fig5_tset_sweep.png"
    out_svg = OUT_DIR / "fig5_tset_sweep.svg"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    print(f"wrote {out_png}")
    print(f"wrote {out_svg}")


if __name__ == "__main__":
    main()
