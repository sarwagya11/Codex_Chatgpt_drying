"""Figure 4: solar-collector placement (pre-cond vs post-cond).

Two-by-two panel comparing B1 vs B2 (single-component solar family) and
E2 vs E3 (HP + HRX + Solar family) on cumulative solar capture (Q_solar)
and specific energy consumption (SEC) at the four Nepali sites.

Source: outputs/placement_summary.csv (extracted from per-run CSVs at
A_c = 10 m^2, T_set = 45 C, r = 0, annual TMY).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "outputs" / "placement_summary.csv"
OUT_DIR = ROOT / "outputs" / "paperplots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITES = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
SITE_LABELS = {
    "biratnagar": "BTN\n(72 m)",
    "kathmandu":  "KTM\n(1350 m)",
    "dhulikhel":  "DHK\n(1550 m)",
    "taplejung":  "TPJ\n(1820 m)",
}

PRE_COLOR = "#1f78b4"
POST_COLOR = "#e6772f"


def _pair_bars(ax, df, cfg_pre, cfg_post, metric, ylabel, title, fmt="{:.2f}", ymin=None):
    n = len(SITES)
    x = np.arange(n)
    w = 0.36
    vals_pre = [float(df[(df.cfg == cfg_pre) & (df.site == s)][metric].iloc[0]) for s in SITES]
    vals_post = [float(df[(df.cfg == cfg_post) & (df.site == s)][metric].iloc[0]) for s in SITES]

    b1 = ax.bar(x - w / 2, vals_pre, w, color=PRE_COLOR, edgecolor="black", linewidth=0.6, label=f"{cfg_pre} (pre-cond)")
    b2 = ax.bar(x + w / 2, vals_post, w, color=POST_COLOR, edgecolor="black", linewidth=0.6, label=f"{cfg_post} (post-cond)")

    for bar, v in zip(b1, vals_pre):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), fmt.format(v),
                ha="center", va="bottom", fontsize=7.5)
    for bar, v in zip(b2, vals_post):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), fmt.format(v),
                ha="center", va="bottom", fontsize=7.5)

    for xi, vp, vq in zip(x, vals_pre, vals_post):
        if metric == "SEC":
            delta = (vq - vp) / vp * 100.0
            sign = "+"
            color = "#b00000"
        else:
            delta = (vq - vp) / vp * 100.0
            sign = ""
            color = "#005000" if delta >= 0 else "#b00000"
        y_top = max(vp, vq)
        ax.annotate(f"{sign}{delta:.1f}%", xy=(xi, y_top),
                    xytext=(0, 14), textcoords="offset points",
                    ha="center", fontsize=7.0, color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([SITE_LABELS[s] for s in SITES], fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9.5)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    if ymin is not None:
        cur_lo, cur_hi = ax.get_ylim()
        ax.set_ylim(ymin, cur_hi * 1.18)
    else:
        cur_lo, cur_hi = ax.get_ylim()
        ax.set_ylim(0, cur_hi * 1.18)
    ax.legend(loc="upper right", fontsize=8, frameon=True, framealpha=0.95)


def main() -> None:
    df = pd.read_csv(CSV)

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), dpi=200)

    _pair_bars(axes[0, 0], df, "B1", "B2", "Q_sol",
               r"$Q_\mathrm{solar}$  (kWh)",
               "(a) Cumulative solar capture — single-component (B1 vs B2)",
               fmt="{:.1f}")
    _pair_bars(axes[0, 1], df, "E2", "E3", "Q_sol",
               r"$Q_\mathrm{solar}$  (kWh)",
               "(b) Cumulative solar capture — with HRX (E2 vs E3)",
               fmt="{:.1f}")
    _pair_bars(axes[1, 0], df, "B1", "B2", "SEC",
               r"SEC  (kWh kg$^{-1}$ water)",
               "(c) Specific energy consumption — single-component (B1 vs B2)",
               fmt="{:.3f}")
    _pair_bars(axes[1, 1], df, "E2", "E3", "SEC",
               r"SEC  (kWh kg$^{-1}$ water)",
               "(d) Specific energy consumption — with HRX (E2 vs E3)",
               fmt="{:.3f}")

    fig.suptitle(
        "Solar-collector placement: pre-condenser (B1, E2) vs post-condenser (B2, E3)\n"
        r"$A_c = 10\ \mathrm{m}^2$, $T_\mathrm{set} = 45\ \mathrm{^\circ C}$, $r = 0$, annual TMY",
        fontsize=11, y=1.00,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out_png = OUT_DIR / "fig4_placement_pre_vs_post.png"
    out_svg = OUT_DIR / "fig4_placement_pre_vs_post.svg"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    print(f"wrote {out_png}")
    print(f"wrote {out_svg}")


if __name__ == "__main__":
    main()
