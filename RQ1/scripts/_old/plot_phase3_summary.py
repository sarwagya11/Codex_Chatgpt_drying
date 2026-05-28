"""Phase 3 summary plots: cross-config comparison and solar sensitivity."""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUTS = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots" / "phase3_summary"
PLOTS.mkdir(parents=True, exist_ok=True)


def load_final_row(csv_path):
    """Load CSV and return the final row."""
    df = pd.read_csv(csv_path)
    r = df.iloc[-1]
    mw = r["m_w_cum_kg"]
    welec = r["W_comp_cum_kWh"] + r["W_fan_cum_kWh"] + (r.get("W_elec_cum_kWh", 0) or 0)
    sec_e = welec / mw if mw > 0 else 999
    qsol = r.get("Q_solar_cum_kWh", 0)
    qhrx = r.get("Q_HRX_cum_kWh", 0)
    qcond = r.get("Q_cond_cum_kWh", 0)
    sec_th = (qcond + qsol) / mw if mw > 0 else 0
    smer = mw / welec if welec > 0 else 0
    return {
        "sec_e": sec_e, "sec_th": sec_th, "time_h": r["time_h"],
        "smer": smer, "q_sol": qsol, "q_hrx": qhrx,
        "w_comp": r["W_comp_cum_kWh"], "w_fan": r["W_fan_cum_kWh"],
        "q_cond": qcond, "mw": mw,
    }


# ── Plot 1: SEC bar chart across all configs ────────────────────────────────
def plot_sec_comparison():
    configs = []
    for loc in ["kathmandu", "biratnagar"]:
        loc_tag = loc[:3].upper()
        entries = [
            ("A", f"config_A/{loc}/baseline_r0.0.csv", 0),
            ("B 10m2", f"config_B/{loc}/Ac_10m2.csv", 10),
            ("C2 10m2", f"config_C2/{loc}/Ac_10m2.csv", 10),
            ("D1", f"config_D1/{loc}/hrx_eps0.70.csv", 0),
            ("D2", f"config_D2/{loc}/hrx_eps0.70.csv", 0),
            ("D1+VPD", f"config_D1/{loc}/hrx_eps0.70_vpd0.05.csv", 0),
            ("D2+VPD", f"config_D2/{loc}/hrx_eps0.70_vpd0.05.csv", 0),
            ("E1 10m2", f"config_E1/{loc}/Ac_10m2_hrx0.70.csv", 10),
            ("E2 10m2", f"config_E2/{loc}/Ac_10m2_hrx0.70.csv", 10),
            ("E1+VPD", f"config_E1/{loc}/Ac_10m2_hrx0.70_vpd0.05.csv", 10),
            ("E2+VPD", f"config_E2/{loc}/Ac_10m2_hrx0.70_vpd0.05.csv", 10),
            ("E3 10m2", f"config_E3/{loc}/Ac_10m2_hrx0.70.csv", 10),
        ]
        for name, rel, sol in entries:
            p = OUTPUTS / rel
            if p.exists():
                d = load_final_row(p)
                configs.append({"Config": name, "Location": loc_tag, **d})

    df = pd.DataFrame(configs)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    for ax, loc_tag in zip(axes, ["KAT", "BIR"]):
        sub = df[df["Location"] == loc_tag].sort_values("sec_e")
        colors = []
        for c in sub["Config"]:
            if "E" in c and "VPD" in c:
                colors.append("#1b7837")
            elif "E" in c:
                colors.append("#5aae61")
            elif "D" in c and "VPD" in c:
                colors.append("#2166ac")
            elif "D" in c:
                colors.append("#67a9cf")
            elif "B" in c:
                colors.append("#f4a582")
            elif "C" in c:
                colors.append("#fddbc7")
            else:
                colors.append("#d6604d")

        bars = ax.barh(range(len(sub)), sub["sec_e"], color=colors, edgecolor="k", lw=0.5)
        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels(sub["Config"])
        ax.set_xlabel("SEC_elec (kWh/kg)")
        ax.set_title(f"{'Kathmandu (1350m)' if loc_tag == 'KAT' else 'Biratnagar (72m)'}")
        ax.axvline(0.665, color="gray", ls="--", lw=1, label="Latent heat min")
        for bar, val in zip(bars, sub["sec_e"]):
            ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:.3f}", va="center", fontsize=8)
        ax.legend(loc="lower right", fontsize=8)
        ax.set_xlim(0, max(sub["sec_e"]) * 1.25)

    fig.suptitle("SEC_elec Comparison Across All Configurations (r=0, A_solar=10 m2)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(PLOTS / "sec_comparison_bar.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {PLOTS / 'sec_comparison_bar.png'}")
    plt.close(fig)


# ── Plot 2: Solar area sensitivity for E2 ───────────────────────────────────
def plot_solar_sensitivity():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    for loc, marker, color in [("kathmandu", "o", "#2166ac"), ("biratnagar", "s", "#b2182b")]:
        areas, secs, smers = [], [], []
        for area in [2, 5, 10, 15, 20]:
            p = OUTPUTS / f"config_E2/{loc}/Ac_{area}m2_hrx0.70.csv"
            if p.exists():
                d = load_final_row(p)
                areas.append(area)
                secs.append(d["sec_e"])
                smers.append(d["smer"])

        loc_label = "Kathmandu" if "kat" in loc else "Biratnagar"
        ax1.plot(areas, secs, f"-{marker}", color=color, label=loc_label, lw=2, ms=8)
        ax2.plot(areas, smers, f"-{marker}", color=color, label=loc_label, lw=2, ms=8)

    ax1.set_xlabel("Solar Collector Area (m2)")
    ax1.set_ylabel("SEC_elec (kWh/kg)")
    ax1.set_title("E2: SEC vs Solar Area")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axhline(0.665, color="gray", ls="--", lw=1, label="Latent min")

    ax2.set_xlabel("Solar Collector Area (m2)")
    ax2.set_ylabel("SMER (kg/kWh)")
    ax2.set_title("E2: SMER vs Solar Area")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Config E2 Solar Area Sensitivity (HRX + Solar + HP, eps_HRX=0.70)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(PLOTS / "e2_solar_sensitivity.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {PLOTS / 'e2_solar_sensitivity.png'}")
    plt.close(fig)


# ── Plot 3: Energy breakdown stacked bar ─────────────────────────────────────
def plot_energy_breakdown():
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)

    for ax, loc in zip(axes, ["kathmandu", "biratnagar"]):
        loc_tag = "Kathmandu" if "kat" in loc else "Biratnagar"
        entries = [
            ("A", f"config_A/{loc}/baseline_r0.0.csv"),
            ("B", f"config_B/{loc}/Ac_10m2.csv"),
            ("C2", f"config_C2/{loc}/Ac_10m2.csv"),
            ("D2", f"config_D2/{loc}/hrx_eps0.70.csv"),
            ("D2+VPD", f"config_D2/{loc}/hrx_eps0.70_vpd0.05.csv"),
            ("E2", f"config_E2/{loc}/Ac_10m2_hrx0.70.csv"),
            ("E2+VPD", f"config_E2/{loc}/Ac_10m2_hrx0.70_vpd0.05.csv"),
        ]

        names, w_comps, w_fans, q_sols, q_hrxs = [], [], [], [], []
        for name, rel in entries:
            p = OUTPUTS / rel
            if p.exists():
                d = load_final_row(p)
                names.append(name)
                w_comps.append(d["w_comp"])
                w_fans.append(d["w_fan"])
                q_sols.append(d["q_sol"])
                q_hrxs.append(d["q_hrx"])

        x = np.arange(len(names))
        w = 0.6
        ax.bar(x, w_comps, w, label="W_comp", color="#d73027")
        ax.bar(x, w_fans, w, bottom=w_comps, label="W_fan", color="#fc8d59")
        bottoms2 = [a + b for a, b in zip(w_comps, w_fans)]
        ax.bar(x, q_sols, w, bottom=bottoms2, label="Q_solar", color="#fee090")
        bottoms3 = [a + b for a, b in zip(bottoms2, q_sols)]
        ax.bar(x, q_hrxs, w, bottom=bottoms3, label="Q_HRX", color="#91bfdb")

        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right")
        ax.set_ylabel("Energy (kWh)")
        ax.set_title(loc_tag)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Energy Source Breakdown by Configuration (10 m2 solar where applicable)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(PLOTS / "energy_breakdown.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {PLOTS / 'energy_breakdown.png'}")
    plt.close(fig)


# ── Plot 4: SEC_elec vs Drying Time (Pareto) ────────────────────────────────
def plot_pareto():
    fig, ax = plt.subplots(figsize=(12, 8))

    all_pts = []
    for loc in ["kathmandu", "biratnagar"]:
        loc_tag = loc[:3].upper()
        entries = [
            ("A", f"config_A/{loc}/baseline_r0.0.csv"),
            ("B 10m2", f"config_B/{loc}/Ac_10m2.csv"),
            ("C2 10m2", f"config_C2/{loc}/Ac_10m2.csv"),
            ("D1", f"config_D1/{loc}/hrx_eps0.70.csv"),
            ("D2", f"config_D2/{loc}/hrx_eps0.70.csv"),
            ("D1+VPD", f"config_D1/{loc}/hrx_eps0.70_vpd0.05.csv"),
            ("D2+VPD", f"config_D2/{loc}/hrx_eps0.70_vpd0.05.csv"),
            ("E1 10m2", f"config_E1/{loc}/Ac_10m2_hrx0.70.csv"),
            ("E2 10m2", f"config_E2/{loc}/Ac_10m2_hrx0.70.csv"),
            ("E1+VPD", f"config_E1/{loc}/Ac_10m2_hrx0.70_vpd0.05.csv"),
            ("E2+VPD", f"config_E2/{loc}/Ac_10m2_hrx0.70_vpd0.05.csv"),
            ("E3 10m2", f"config_E3/{loc}/Ac_10m2_hrx0.70.csv"),
        ]
        for name, rel in entries:
            p = OUTPUTS / rel
            if p.exists():
                d = load_final_row(p)
                all_pts.append({"Config": name, "Location": loc_tag,
                                "sec_e": d["sec_e"], "time_h": d["time_h"]})

    df = pd.DataFrame(all_pts)

    markers = {"KAT": "o", "BIR": "s"}
    for loc_tag, marker in markers.items():
        sub = df[df["Location"] == loc_tag]
        ax.scatter(sub["time_h"], sub["sec_e"], marker=marker, s=80,
                   label=f"{'Kathmandu' if loc_tag == 'KAT' else 'Biratnagar'}",
                   edgecolors="k", lw=0.5, zorder=5)
        for _, row in sub.iterrows():
            ax.annotate(row["Config"], (row["time_h"], row["sec_e"]),
                        fontsize=7, ha="left", va="bottom",
                        xytext=(4, 4), textcoords="offset points")

    ax.set_xlabel("Drying Time (hours)")
    ax.set_ylabel("SEC_elec (kWh/kg)")
    ax.set_title("Pareto Front: SEC_elec vs Drying Time", fontsize=13, fontweight="bold")
    ax.axhline(0.665, color="gray", ls="--", lw=1, alpha=0.5, label="Latent heat min")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(PLOTS / "pareto_sec_vs_time.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {PLOTS / 'pareto_sec_vs_time.png'}")
    plt.close(fig)


if __name__ == "__main__":
    plot_sec_comparison()
    plot_solar_sensitivity()
    plot_energy_breakdown()
    plot_pareto()
    print("\nAll Phase 3 summary plots generated.")
