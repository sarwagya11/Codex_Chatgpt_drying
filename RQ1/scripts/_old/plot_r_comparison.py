"""Cross-recirculation-ratio comparison plots for Config A, B, C1, and C2.

Creates 4 plot sets:
1. Baseline (no VPD): SEC vs r, COP vs time, T_evap vs r, drying time vs r
2. VPD-enabled: same plots comparing VPD-on results
3. Combined: overlay baseline and VPD for direct comparison

Usage:
    python scripts/plot_r_comparison.py
    python scripts/plot_r_comparison.py --config A --location kathmandu
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots" / "r_comparison"

R_VALUES = [0.0, 0.3, 0.5, 0.7, 0.9]
R_VALUES_VPD = [0.3, 0.5, 0.7, 0.9]  # no r=0 for VPD
COLORS = {0.0: "#1f77b4", 0.3: "#ff7f0e", 0.5: "#2ca02c", 0.7: "#d62728", 0.9: "#9467bd"}
LOCATIONS = {"kathmandu": "Kathmandu (1350m)", "biratnagar": "Biratnagar (72m)"}


def load_csv(config: str, location: str, r: float, vpd: bool = False,
             n_sec: int = 4) -> pd.DataFrame:
    """Load simulation CSV for given config/location/r/vpd combination."""
    sec_tag = f"_s{n_sec}" if n_sec > 1 else ""
    if config == "A":
        vpd_tag = "_vpd" if vpd else ""
        fname = f"baseline_r{r:.1f}{vpd_tag}{sec_tag}.csv"
    else:
        vpd_tag = "_vpd" if vpd else ""
        r_tag = f"_r{r:.1f}" if r > 0 else ""
        fname = f"Ac_10m2{vpd_tag}{r_tag}{sec_tag}.csv"
    path = OUTPUTS / f"config_{config}" / location / fname
    if not path.exists():
        # Fallback: try without section tag
        if config == "A":
            fname_fb = f"baseline_r{r:.1f}{vpd_tag}.csv"
        else:
            fname_fb = f"Ac_10m2{vpd_tag}{r_tag}.csv"
        path_fb = OUTPUTS / f"config_{config}" / location / fname_fb
        if path_fb.exists():
            return pd.read_csv(path_fb)
        return None
    return pd.read_csv(path)


def get_summary(df: pd.DataFrame) -> dict:
    """Extract summary metrics from a simulation DataFrame."""
    final = df.iloc[-1]
    sec = final.get("SEC_elec_kWh_per_kg", np.nan)
    time_h = final["time_s"] / 3600.0
    w_comp = final["W_comp_cum_kWh"]
    w_fan = final["W_fan_cum_kWh"]
    m_water = final["m_w_cum_kg"]
    avg_cop = df["COP"].replace(0, np.nan).mean()
    return {
        "SEC": sec, "time_h": time_h, "W_comp": w_comp, "W_fan": w_fan,
        "m_water": m_water, "avg_COP": avg_cop,
    }


# ============================================================================
# PLOT 1: SEC vs r (bar chart with baseline and VPD side by side)
# ============================================================================
def plot_sec_vs_r(config: str, location: str, out_dir: Path):
    """SEC vs recirculation ratio — baseline and VPD comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Baseline
    secs_base = []
    for r in R_VALUES:
        df = load_csv(config, location, r, vpd=False)
        if df is not None:
            secs_base.append(get_summary(df)["SEC"])
        else:
            secs_base.append(np.nan)

    # VPD
    secs_vpd = []
    for r in R_VALUES:
        if r == 0.0:
            secs_vpd.append(np.nan)
            continue
        df = load_csv(config, location, r, vpd=True)
        if df is not None:
            secs_vpd.append(get_summary(df)["SEC"])
        else:
            secs_vpd.append(np.nan)

    x = np.arange(len(R_VALUES))
    width = 0.35
    bars1 = ax.bar(x - width/2, secs_base, width, label="Baseline", color="#4C72B0", alpha=0.85)
    bars2 = ax.bar(x + width/2, secs_vpd, width, label="VPD Cond-Direct", color="#DD8452", alpha=0.85)

    # Add value labels
    for bar in bars1:
        if not np.isnan(bar.get_height()):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8)
    for bar in bars2:
        if not np.isnan(bar.get_height()):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Recirculation Ratio (r)", fontsize=12)
    ax.set_ylabel("SEC [kWh/kg]", fontsize=12)
    ax.set_title(f"Config {config} — {LOCATIONS[location]}\nSpecific Energy Consumption vs Recirculation Ratio",
                 fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([f"r={r}" for r in R_VALUES])
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"config_{config}_{location}_SEC_vs_r.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: SEC_vs_r")


# ============================================================================
# PLOT 2: COP vs time for different r values
# ============================================================================
def plot_cop_vs_time(config: str, location: str, out_dir: Path, vpd: bool = False):
    """COP over drying time for different r values."""
    tag = "VPD" if vpd else "Baseline"
    r_list = R_VALUES_VPD if vpd else R_VALUES

    fig, ax = plt.subplots(figsize=(12, 6))

    for r in r_list:
        df = load_csv(config, location, r, vpd=vpd)
        if df is None:
            continue
        h = df["time_s"] / 3600.0
        cop = df["COP"].replace(0, np.nan)
        # Smooth with rolling window for readability
        cop_smooth = cop.rolling(window=15, min_periods=1, center=True).mean()
        ax.plot(h, cop_smooth, label=f"r={r:.1f}", color=COLORS[r], linewidth=1.5)

    ax.set_xlabel("Time [h]", fontsize=12)
    ax.set_ylabel("COP [-]", fontsize=12)
    ax.set_title(f"Config {config} — {LOCATIONS[location]} ({tag})\nHP Coefficient of Performance vs Time",
                 fontsize=13)
    ax.legend(fontsize=10, ncol=2)
    ax.grid(alpha=0.3)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_vpd" if vpd else ""
    fig.savefig(out_dir / f"config_{config}_{location}_COP_vs_time{suffix}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: COP_vs_time{suffix}")


# ============================================================================
# PLOT 3: T_evap vs time for different r values
# ============================================================================
def plot_tevap_vs_time(config: str, location: str, out_dir: Path, vpd: bool = False):
    """Evaporator temperature over drying time for different r values."""
    tag = "VPD" if vpd else "Baseline"
    r_list = R_VALUES_VPD if vpd else R_VALUES

    fig, ax = plt.subplots(figsize=(12, 6))

    for r in r_list:
        df = load_csv(config, location, r, vpd=vpd)
        if df is None:
            continue
        h = df["time_s"] / 3600.0
        t_evap = df["T_evap_C"].replace(0, np.nan)
        t_evap_smooth = t_evap.rolling(window=15, min_periods=1, center=True).mean()
        ax.plot(h, t_evap_smooth, label=f"r={r:.1f}", color=COLORS[r], linewidth=1.5)

    # Reference lines
    ax.axhline(y=2, color="blue", linestyle="--", alpha=0.4, linewidth=0.8, label="Frost limit (2°C)")
    ax.axhline(y=20, color="orange", linestyle="--", alpha=0.4, linewidth=0.8, label="AC upper limit (20°C)")

    ax.set_xlabel("Time [h]", fontsize=12)
    ax.set_ylabel("T_evap [°C]", fontsize=12)
    ax.set_title(f"Config {config} — {LOCATIONS[location]} ({tag})\nEvaporator Temperature vs Time",
                 fontsize=13)
    ax.legend(fontsize=9, ncol=2)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_vpd" if vpd else ""
    fig.savefig(out_dir / f"config_{config}_{location}_Tevap_vs_time{suffix}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: Tevap_vs_time{suffix}")


# ============================================================================
# PLOT 4: Drying time vs r (bar chart with baseline and VPD)
# ============================================================================
def plot_drying_time_vs_r(config: str, location: str, out_dir: Path):
    """Drying time vs recirculation ratio — baseline and VPD comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))

    times_base = []
    for r in R_VALUES:
        df = load_csv(config, location, r, vpd=False)
        if df is not None:
            times_base.append(get_summary(df)["time_h"])
        else:
            times_base.append(np.nan)

    times_vpd = []
    for r in R_VALUES:
        if r == 0.0:
            times_vpd.append(np.nan)
            continue
        df = load_csv(config, location, r, vpd=True)
        if df is not None:
            times_vpd.append(get_summary(df)["time_h"])
        else:
            times_vpd.append(np.nan)

    x = np.arange(len(R_VALUES))
    width = 0.35
    bars1 = ax.bar(x - width/2, times_base, width, label="Baseline", color="#4C72B0", alpha=0.85)
    bars2 = ax.bar(x + width/2, times_vpd, width, label="VPD Cond-Direct", color="#DD8452", alpha=0.85)

    for bar in bars1:
        if not np.isnan(bar.get_height()):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f"{bar.get_height():.1f}h", ha="center", va="bottom", fontsize=8)
    for bar in bars2:
        if not np.isnan(bar.get_height()):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f"{bar.get_height():.1f}h", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Recirculation Ratio (r)", fontsize=12)
    ax.set_ylabel("Drying Time [h]", fontsize=12)
    ax.set_title(f"Config {config} — {LOCATIONS[location]}\nDrying Time vs Recirculation Ratio",
                 fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([f"r={r}" for r in R_VALUES])
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"config_{config}_{location}_time_vs_r.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: time_vs_r")


# ============================================================================
# PLOT 5: W_comp breakdown vs r (stacked: baseline vs VPD savings)
# ============================================================================
def plot_energy_vs_r(config: str, location: str, out_dir: Path):
    """Energy consumption breakdown vs r — shows VPD savings."""
    fig, ax = plt.subplots(figsize=(10, 6))

    wcomp_base = []
    wfan_base = []
    for r in R_VALUES:
        df = load_csv(config, location, r, vpd=False)
        if df is not None:
            s = get_summary(df)
            wcomp_base.append(s["W_comp"])
            wfan_base.append(s["W_fan"])
        else:
            wcomp_base.append(np.nan)
            wfan_base.append(np.nan)

    wcomp_vpd = []
    wfan_vpd = []
    for r in R_VALUES:
        if r == 0.0:
            wcomp_vpd.append(np.nan)
            wfan_vpd.append(np.nan)
            continue
        df = load_csv(config, location, r, vpd=True)
        if df is not None:
            s = get_summary(df)
            wcomp_vpd.append(s["W_comp"])
            wfan_vpd.append(s["W_fan"])
        else:
            wcomp_vpd.append(np.nan)
            wfan_vpd.append(np.nan)

    x = np.arange(len(R_VALUES))
    width = 0.35

    ax.bar(x - width/2, wcomp_base, width, label="W_comp (Baseline)", color="#4C72B0", alpha=0.85)
    ax.bar(x - width/2, wfan_base, width, bottom=wcomp_base, label="W_fan (Baseline)",
           color="#4C72B0", alpha=0.4)
    ax.bar(x + width/2, wcomp_vpd, width, label="W_comp (VPD)", color="#DD8452", alpha=0.85)
    ax.bar(x + width/2, wfan_vpd, width, bottom=wcomp_vpd, label="W_fan (VPD)",
           color="#DD8452", alpha=0.4)

    # Annotate savings
    for i, r in enumerate(R_VALUES):
        if r > 0 and not np.isnan(wcomp_base[i]) and not np.isnan(wcomp_vpd[i]):
            saving = (1 - (wcomp_vpd[i] + wfan_vpd[i]) / (wcomp_base[i] + wfan_base[i])) * 100
            total_vpd = wcomp_vpd[i] + wfan_vpd[i]
            ax.text(x[i] + width/2, total_vpd + 0.2,
                    f"-{saving:.0f}%", ha="center", va="bottom", fontsize=9, color="red",
                    fontweight="bold")

    ax.set_xlabel("Recirculation Ratio (r)", fontsize=12)
    ax.set_ylabel("Energy [kWh]", fontsize=12)
    ax.set_title(f"Config {config} — {LOCATIONS[location]}\nTotal Electrical Energy vs Recirculation Ratio",
                 fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([f"r={r}" for r in R_VALUES])
    ax.legend(fontsize=9, ncol=2)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"config_{config}_{location}_energy_vs_r.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: energy_vs_r")


# ============================================================================
# PLOT 6: Summary table as figure
# ============================================================================
def plot_summary_table(config: str, location: str, out_dir: Path):
    """Summary comparison table as a figure."""
    rows = []
    for r in R_VALUES:
        df_base = load_csv(config, location, r, vpd=False)
        df_vpd = load_csv(config, location, r, vpd=True) if r > 0 else None

        base = get_summary(df_base) if df_base is not None else {}
        vpd = get_summary(df_vpd) if df_vpd is not None else {}

        sec_change = ""
        if base.get("SEC") and vpd.get("SEC"):
            pct = (vpd["SEC"] - base["SEC"]) / base["SEC"] * 100
            sec_change = f"{pct:+.1f}%"

        rows.append([
            f"r={r:.1f}",
            f"{base.get('SEC', 0):.3f}" if base.get("SEC") else "—",
            f"{vpd.get('SEC', 0):.3f}" if vpd.get("SEC") else "—",
            sec_change,
            f"{base.get('time_h', 0):.1f}" if base.get("time_h") else "—",
            f"{vpd.get('time_h', 0):.1f}" if vpd.get("time_h") else "—",
            f"{base.get('avg_COP', 0):.2f}" if base.get("avg_COP") else "—",
            f"{vpd.get('avg_COP', 0):.2f}" if vpd.get("avg_COP") else "—",
        ])

    col_labels = ["r", "SEC\n(Base)", "SEC\n(VPD)", "SEC\nChange",
                  "Time\n(Base)", "Time\n(VPD)", "COP\n(Base)", "COP\n(VPD)"]

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=col_labels, loc="center",
                     cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.4)

    # Color header
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#4C72B0")
        table[0, j].set_text_props(color="white", fontweight="bold")

    ax.set_title(f"Config {config} — {LOCATIONS[location]} — Recirculation Comparison",
                 fontsize=13, pad=20)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"config_{config}_{location}_summary_table.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: summary_table")


# ============================================================================
# MAIN
# ============================================================================
def generate_all_plots(config: str, location: str):
    """Generate all comparison plots for one config+location."""
    out_dir = PLOTS / f"config_{config}" / location
    print(f"\n{'='*60}")
    print(f"Generating plots: Config {config}, {LOCATIONS[location]}")
    print(f"{'='*60}")

    plot_sec_vs_r(config, location, out_dir)
    plot_drying_time_vs_r(config, location, out_dir)
    plot_energy_vs_r(config, location, out_dir)
    plot_cop_vs_time(config, location, out_dir, vpd=False)
    plot_cop_vs_time(config, location, out_dir, vpd=True)
    plot_tevap_vs_time(config, location, out_dir, vpd=False)
    plot_tevap_vs_time(config, location, out_dir, vpd=True)
    plot_summary_table(config, location, out_dir)


def main():
    parser = argparse.ArgumentParser(description="Cross-r comparison plots")
    parser.add_argument("--config", type=str, choices=["A", "B", "C1", "C2"], default=None)
    parser.add_argument("--location", type=str, default=None)
    args = parser.parse_args()

    configs = [args.config] if args.config else ["A", "B", "C1", "C2"]
    locations = [args.location] if args.location else ["kathmandu", "biratnagar"]

    for config in configs:
        for location in locations:
            generate_all_plots(config, location)

    print(f"\nAll comparison plots saved to: {PLOTS}")


if __name__ == "__main__":
    main()
