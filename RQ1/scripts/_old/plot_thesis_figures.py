"""Generate thesis-quality comparison figures from master_summary.csv.

Figures generated:
  1. Config ranking bar chart (SEC by config, grouped by location)
  2. Seasonal sensitivity heatmap (SEC across config x season)
  3. VPD bypass benefit (grouped bars: baseline vs VPD)
  4. E2 collector area sweep (SEC vs area, per location/season)
  5. Config A: r=0 vs r=0.9 vs r=1.0 comparison
  6. Config A/B: VPD benefit across r values
  7. Solar fraction by config and season
  8. COP comparison across configs

Usage:
    python scripts/plot_thesis_figures.py
"""

import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_CSV = PROJECT_ROOT / "outputs" / "master_summary.csv"
FIG_DIR = PROJECT_ROOT / "figures" / "thesis"
FIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_ORDER = ["A", "B", "C1", "C2", "D1", "D2", "D3", "E1", "E2", "E3"]
LOC_ORDER = ["kathmandu", "biratnagar", "taplejung"]
LOC_SHORT = {"kathmandu": "KTM", "biratnagar": "BTN", "taplejung": "TPJ"}
SEASON_ORDER = ["annual", "autumn_oct_nov", "winter_dec_jan", "spring_mar_apr"]
SEASON_SHORT = {"annual": "Annual", "autumn_oct_nov": "Autumn", "winter_dec_jan": "Winter", "spring_mar_apr": "Spring"}

# Consistent colors
CONFIG_COLORS = {
    "A": "#1f77b4", "B": "#ff7f0e", "C1": "#2ca02c", "C2": "#d62728",
    "D1": "#9467bd", "D2": "#8c564b", "D3": "#e377c2",
    "E1": "#7f7f7f", "E2": "#bcbd22", "E3": "#17becf",
}
LOC_COLORS = {"kathmandu": "#1f77b4", "biratnagar": "#ff7f0e", "taplejung": "#2ca02c"}

plt.rcParams.update({
    "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 12,
    "legend.fontsize": 10, "figure.dpi": 150, "savefig.dpi": 200,
})


def load_data():
    df = pd.read_csv(SUMMARY_CSV)
    return df


# ─── Figure 1: Config ranking bar chart ──────────────────────────────────────

def fig1_config_ranking(df):
    """Bar chart: SEC by config, grouped by location (annual, r=0, 10m2, no VPD)."""
    fig, ax = plt.subplots(figsize=(14, 6))

    # Filter: annual, no VPD, r=0 for A/B/C, solar=10 for solar configs
    rows = []
    for cfg in CONFIG_ORDER:
        sub = df[(df["config"] == cfg) & (df["season"] == "annual") & (~df["vpd_bypass"])]
        if cfg == "A":
            sub = sub[sub["r_recirc"] == 0.0]
        elif cfg in ("B", "C1", "C2", "E1", "E2", "E3"):
            sub = sub[sub["solar_area_m2"] == 10.0]

        for loc in LOC_ORDER:
            loc_data = sub[sub["location"] == loc]
            if not loc_data.empty:
                rows.append({"config": cfg, "location": loc,
                             "SEC": loc_data.iloc[0]["SEC_kWh_per_kg"]})

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return

    x = np.arange(len(CONFIG_ORDER))
    width = 0.25

    for i, loc in enumerate(LOC_ORDER):
        loc_df = plot_df[plot_df["location"] == loc]
        secs = []
        for cfg in CONFIG_ORDER:
            v = loc_df[loc_df["config"] == cfg]["SEC"]
            secs.append(v.values[0] if len(v) > 0 else 0)
        bars = ax.bar(x + i * width, secs, width, label=LOC_SHORT[loc],
                       color=LOC_COLORS[loc], alpha=0.85)
        # Value labels on bars
        for bar, val in zip(bars, secs):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=7)

    ax.set_xlabel("Configuration")
    ax.set_ylabel("SEC (kWh/kg)")
    ax.set_title("Specific Energy Consumption by Configuration and Location (Annual TMY)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(CONFIG_ORDER)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)

    fig.savefig(FIG_DIR / "fig1_config_ranking.png")
    plt.close(fig)
    print("  fig1_config_ranking.png")


# ─── Figure 2: Seasonal sensitivity ──────────────────────────────────────────

def fig2_seasonal_sensitivity(df):
    """Grouped bar chart: SEC by season for key configs, one subplot per location."""
    key_configs = ["A", "D2", "E2"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)

    for ax, loc in zip(axes, LOC_ORDER):
        x = np.arange(len(SEASON_ORDER))
        width = 0.25
        for i, cfg in enumerate(key_configs):
            sub = df[(df["config"] == cfg) & (df["location"] == loc) & (~df["vpd_bypass"])]
            if cfg == "A":
                sub = sub[sub["r_recirc"] == 0.0]
            elif cfg in ("E1", "E2", "E3"):
                sub = sub[sub["solar_area_m2"] == 10.0]

            secs = []
            for season in SEASON_ORDER:
                s_data = sub[sub["season"] == season]
                secs.append(s_data.iloc[0]["SEC_kWh_per_kg"] if len(s_data) > 0 else 0)

            ax.bar(x + i * width, secs, width, label=f"Config {cfg}",
                   color=CONFIG_COLORS[cfg], alpha=0.85)

        ax.set_xticks(x + width)
        ax.set_xticklabels([SEASON_SHORT[s] for s in SEASON_ORDER], fontsize=9)
        ax.set_title(LOC_SHORT[loc], fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("SEC (kWh/kg)")
    axes[0].legend()
    fig.suptitle("Seasonal Sensitivity: Config A vs D2 vs E2", fontsize=14, fontweight="bold")
    fig.savefig(FIG_DIR / "fig2_seasonal_sensitivity.png")
    plt.close(fig)
    print("  fig2_seasonal_sensitivity.png")


# ─── Figure 3: VPD bypass benefit ────────────────────────────────────────────

def fig3_vpd_benefit(df):
    """Grouped bars: baseline vs VPD for D1, D2, E1, E2 across locations (annual)."""
    vpd_configs = ["D1", "D2", "E1", "E2"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    for ax, loc in zip(axes, LOC_ORDER):
        x = np.arange(len(vpd_configs))
        width = 0.35

        base_vals, vpd_vals = [], []
        for cfg in vpd_configs:
            sub = df[(df["config"] == cfg) & (df["location"] == loc) & (df["season"] == "annual")]
            if cfg in ("E1", "E2"):
                sub = sub[sub["solar_area_m2"] == 10.0]

            base = sub[~sub["vpd_bypass"]]
            vpd = sub[sub["vpd_bypass"]]
            base_vals.append(base.iloc[0]["SEC_kWh_per_kg"] if len(base) > 0 else 0)
            vpd_vals.append(vpd.iloc[0]["SEC_kWh_per_kg"] if len(vpd) > 0 else 0)

        bars1 = ax.bar(x - width/2, base_vals, width, label="Baseline", color="#4c72b0", alpha=0.85)
        bars2 = ax.bar(x + width/2, vpd_vals, width, label="+ VPD Bypass", color="#55a868", alpha=0.85)

        # Add % reduction labels
        for j, (b, v) in enumerate(zip(base_vals, vpd_vals)):
            if b > 0 and v > 0:
                pct = (b - v) / b * 100
                ax.text(x[j] + width/2, v + 0.005, f"-{pct:.0f}%",
                        ha="center", fontsize=8, color="#55a868", fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(vpd_configs)
        ax.set_title(LOC_SHORT[loc], fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("SEC (kWh/kg)")
    axes[0].legend()
    fig.suptitle("VPD Exhaust Bypass Benefit (Annual TMY)", fontsize=14, fontweight="bold")
    fig.savefig(FIG_DIR / "fig3_vpd_benefit.png")
    plt.close(fig)
    print("  fig3_vpd_benefit.png")


# ─── Figure 4: E2 area sweep ─────────────────────────────────────────────────

def fig4_area_sweep(df):
    """Line plot: E2 SEC vs collector area, one line per location, subplots by season."""
    e2 = df[(df["config"] == "E2") & (~df["vpd_bypass"])].copy()
    areas = sorted(e2["solar_area_m2"].unique())
    areas = [a for a in areas if a in [2, 4, 6, 8, 10]]

    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5), sharey=True)

    for ax, season in zip(axes, SEASON_ORDER):
        for loc in LOC_ORDER:
            sub = e2[(e2["location"] == loc) & (e2["season"] == season)]
            secs = []
            valid_areas = []
            for a in areas:
                a_data = sub[sub["solar_area_m2"] == a]
                if len(a_data) > 0:
                    secs.append(a_data.iloc[0]["SEC_kWh_per_kg"])
                    valid_areas.append(a)

            if valid_areas:
                ax.plot(valid_areas, secs, "o-", color=LOC_COLORS[loc],
                        label=LOC_SHORT[loc], linewidth=2, markersize=6)

        ax.set_xlabel("Collector Area (m$^2$)")
        ax.set_title(SEASON_SHORT[season], fontweight="bold")
        ax.grid(True, alpha=0.3)
        ax.set_xticks(areas)

    axes[0].set_ylabel("SEC (kWh/kg)")
    axes[0].legend()
    fig.suptitle("Config E2: SEC vs Collector Area", fontsize=14, fontweight="bold")
    fig.savefig(FIG_DIR / "fig4_e2_area_sweep.png")
    plt.close(fig)
    print("  fig4_e2_area_sweep.png")


# ─── Figure 5: Config A recirculation comparison ─────────────────────────────

def fig5_config_a_recirc(df):
    """Grouped bars: r=0 vs r=0.9 vs r=1.0 for Config A, by season, per location."""
    a = df[(df["config"] == "A") & (~df["vpd_bypass"])].copy()
    r_vals = [0.0, 0.9, 1.0]
    r_colors = {0.0: "#1f77b4", 0.9: "#ff7f0e", 1.0: "#2ca02c"}

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)

    for ax, loc in zip(axes, LOC_ORDER):
        x = np.arange(len(SEASON_ORDER))
        width = 0.25

        for i, r in enumerate(r_vals):
            sub = a[(a["location"] == loc) & (a["r_recirc"] == r)]
            secs = []
            for season in SEASON_ORDER:
                s_data = sub[sub["season"] == season]
                secs.append(s_data.iloc[0]["SEC_kWh_per_kg"] if len(s_data) > 0 else 0)

            ax.bar(x + i * width, secs, width, label=f"r={r}",
                   color=r_colors[r], alpha=0.85)

        ax.set_xticks(x + width)
        ax.set_xticklabels([SEASON_SHORT[s] for s in SEASON_ORDER], fontsize=9)
        ax.set_title(LOC_SHORT[loc], fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("SEC (kWh/kg)")
    axes[0].legend()
    fig.suptitle("Config A: Effect of Recirculation Ratio on SEC", fontsize=14, fontweight="bold")
    fig.savefig(FIG_DIR / "fig5_config_a_recirc.png")
    plt.close(fig)
    print("  fig5_config_a_recirc.png")


# ─── Figure 6: Config A/B VPD benefit ────────────────────────────────────────

def fig6_ab_vpd(df):
    """Grouped bars: Config A and B, baseline vs VPD, r=0.9 (annual)."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    for ax, loc in zip(axes, LOC_ORDER):
        configs_r = [("A", 0.9), ("A", 1.0), ("B", 0.9), ("B", 1.0)]
        labels = ["A r=0.9", "A r=1.0", "B r=0.9", "B r=1.0"]
        x = np.arange(len(configs_r))
        width = 0.35

        base_vals, vpd_vals = [], []
        for cfg, r in configs_r:
            sub = df[(df["config"] == cfg) & (df["location"] == loc) & (df["season"] == "annual")]
            if cfg == "B":
                sub = sub[sub["solar_area_m2"] == 10.0]
            sub_r = sub[sub["r_recirc"] == r]

            base = sub_r[~sub_r["vpd_bypass"]]
            vpd = sub_r[sub_r["vpd_bypass"]]
            base_vals.append(base.iloc[0]["SEC_kWh_per_kg"] if len(base) > 0 else 0)
            vpd_vals.append(vpd.iloc[0]["SEC_kWh_per_kg"] if len(vpd) > 0 else 0)

        bars1 = ax.bar(x - width/2, base_vals, width, label="Baseline", color="#4c72b0", alpha=0.85)
        bars2 = ax.bar(x + width/2, vpd_vals, width, label="+ VPD", color="#55a868", alpha=0.85)

        for j, (b, v) in enumerate(zip(base_vals, vpd_vals)):
            if b > 0 and v > 0:
                pct = (b - v) / b * 100
                ax.text(x[j] + width/2, v + 0.005, f"-{pct:.0f}%",
                        ha="center", fontsize=8, color="#55a868", fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, rotation=15)
        ax.set_title(LOC_SHORT[loc], fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("SEC (kWh/kg)")
    axes[0].legend()
    fig.suptitle("Config A & B: Condenser-Direct VPD Bypass Benefit (Annual)", fontsize=13, fontweight="bold")
    fig.savefig(FIG_DIR / "fig6_ab_vpd_benefit.png")
    plt.close(fig)
    print("  fig6_ab_vpd_benefit.png")


# ─── Figure 7: Solar fraction ────────────────────────────────────────────────

def fig7_solar_fraction(df):
    """Bar chart: solar fraction by config (B, E1, E2, E3), grouped by location, annual."""
    solar_cfgs = ["B", "C2", "E1", "E2", "E3"]
    fig, ax = plt.subplots(figsize=(12, 5))

    x = np.arange(len(solar_cfgs))
    width = 0.25

    for i, loc in enumerate(LOC_ORDER):
        fracs = []
        for cfg in solar_cfgs:
            sub = df[(df["config"] == cfg) & (df["location"] == loc) &
                     (df["season"] == "annual") & (~df["vpd_bypass"]) &
                     (df["solar_area_m2"] == 10.0) & (df["r_recirc"] == 0.0)]
            fracs.append(sub.iloc[0]["solar_fraction"] * 100 if len(sub) > 0 else 0)

        ax.bar(x + i * width, fracs, width, label=LOC_SHORT[loc],
               color=LOC_COLORS[loc], alpha=0.85)

    ax.set_xlabel("Configuration")
    ax.set_ylabel("Solar Fraction (%)")
    ax.set_title("Solar Energy Contribution by Configuration (Annual TMY, 10 m$^2$)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(solar_cfgs)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, 100)

    fig.savefig(FIG_DIR / "fig7_solar_fraction.png")
    plt.close(fig)
    print("  fig7_solar_fraction.png")


# ─── Figure 8: COP comparison ────────────────────────────────────────────────

def fig8_cop_comparison(df):
    """Bar chart: mean COP by config and location (annual)."""
    fig, ax = plt.subplots(figsize=(14, 5))

    x = np.arange(len(CONFIG_ORDER))
    width = 0.25

    for i, loc in enumerate(LOC_ORDER):
        cops = []
        for cfg in CONFIG_ORDER:
            sub = df[(df["config"] == cfg) & (df["location"] == loc) &
                     (df["season"] == "annual") & (~df["vpd_bypass"])]
            if cfg == "A":
                sub = sub[sub["r_recirc"] == 0.0]
            elif cfg in ("B", "C1", "C2", "E1", "E2", "E3"):
                sub = sub[sub["solar_area_m2"] == 10.0]
            cops.append(sub.iloc[0]["COP_mean"] if len(sub) > 0 else 0)

        ax.bar(x + i * width, cops, width, label=LOC_SHORT[loc],
               color=LOC_COLORS[loc], alpha=0.85)

    ax.set_xlabel("Configuration")
    ax.set_ylabel("Mean COP")
    ax.set_title("Heat Pump COP by Configuration and Location (Annual TMY)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(CONFIG_ORDER)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.savefig(FIG_DIR / "fig8_cop_comparison.png")
    plt.close(fig)
    print("  fig8_cop_comparison.png")


# ─── Figure 9: Overall ranking — best SEC per config ─────────────────────────

def fig9_best_sec_summary(df):
    """Horizontal bar chart: best achievable SEC for each config (any location/season/VPD)."""
    fig, ax = plt.subplots(figsize=(10, 7))

    labels = []
    secs = []
    colors = []
    descriptions = []

    for cfg in reversed(CONFIG_ORDER):
        sub = df[df["config"] == cfg].copy()
        if cfg == "A":
            sub = sub[sub["r_recirc"].isin([0.0, 0.9, 1.0])]
        elif cfg in ("B", "C1", "C2", "E1", "E2", "E3"):
            sub = sub[sub["solar_area_m2"] == 10.0]

        if sub.empty:
            continue

        best_idx = sub["SEC_kWh_per_kg"].idxmin()
        best = sub.loc[best_idx]
        labels.append(f"Config {cfg}")
        secs.append(best["SEC_kWh_per_kg"])
        colors.append(CONFIG_COLORS[cfg])
        desc = f"{LOC_SHORT.get(best['location'], best['location'])}"
        if best["season"] != "annual":
            desc += f" {SEASON_SHORT.get(best['season'], best['season'])}"
        if best["vpd_bypass"]:
            desc += " +VPD"
        if best["r_recirc"] > 0:
            desc += f" r={best['r_recirc']:.1f}"
        descriptions.append(desc)

    y = np.arange(len(labels))
    bars = ax.barh(y, secs, color=colors, alpha=0.85)

    for bar, desc, sec in zip(bars, descriptions, secs):
        ax.text(sec + 0.005, bar.get_y() + bar.get_height()/2,
                f"{sec:.3f} ({desc})", va="center", fontsize=9)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("Best Achievable SEC (kWh/kg)")
    ax.set_title("Best SEC by Configuration (any location, season, VPD setting)")
    ax.grid(axis="x", alpha=0.3)
    ax.set_xlim(0, max(secs) * 1.4)

    fig.savefig(FIG_DIR / "fig9_best_sec_summary.png")
    plt.close(fig)
    print("  fig9_best_sec_summary.png")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading {SUMMARY_CSV}...")
    df = load_data()
    print(f"  {len(df)} simulations loaded")
    print(f"\nGenerating thesis figures in {FIG_DIR}/")

    fig1_config_ranking(df)
    fig2_seasonal_sensitivity(df)
    fig3_vpd_benefit(df)
    fig4_area_sweep(df)
    fig5_config_a_recirc(df)
    fig6_ab_vpd(df)
    fig7_solar_fraction(df)
    fig8_cop_comparison(df)
    fig9_best_sec_summary(df)

    print(f"\nDone! {len(list(FIG_DIR.glob('*.png')))} figures saved to {FIG_DIR}/")


if __name__ == "__main__":
    main()
