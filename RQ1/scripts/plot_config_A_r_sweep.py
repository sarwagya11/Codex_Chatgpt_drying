"""Plot Config A SEC vs r_recirc for all four sites.

Two viable operating modes revealed: r=0 (open-loop) and r=1.0 (fully closed).
Partial-r (0.3-0.9) is a stall band at cold sites.

Outputs:
  outputs/config_A_r_sweep/SEC_vs_r_per_site.png
  outputs/config_A_r_sweep/SEC_vs_r_per_site.csv  (consolidated table)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "config_A_r_sweep"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "biratnagar": [PROJECT_ROOT / "outputs" / "r_sweep_A_biratnagar" / "run_summary.csv"],
    "kathmandu":  [PROJECT_ROOT / "outputs" / "r_sweep_A_clean" / "run_summary.csv"],
    "jomsom":     [PROJECT_ROOT / "outputs" / "r_sweep_A_jomsom" / "run_summary.csv"],
    "namche":     [PROJECT_ROOT / "outputs" / "r_sweep_A_namche" / "run_summary.csv",
                   PROJECT_ROOT / "outputs" / "r_sweep_A_namche_r1" / "run_summary.csv"],
}

T_AMB_MEAN = {"biratnagar": 18, "kathmandu": 12, "jomsom": 7, "namche": -3}

COLORS = {"biratnagar": "tab:red", "kathmandu": "tab:orange",
          "jomsom": "tab:green", "namche": "tab:blue"}


def load_site(site: str) -> pd.DataFrame:
    frames = []
    for p in SOURCES[site]:
        if p.exists():
            df = pd.read_csv(p)
            df["site"] = site
            frames.append(df)
    out = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["config", "location", "r_recirc"], keep="last"
    )
    out["SEC"] = (out["W_comp_kWh"] + out["W_fan_kWh"]) / out["m_water_kg"]
    return out.sort_values("r_recirc").reset_index(drop=True)


def main():
    all_frames = []
    for site in SOURCES:
        df = load_site(site)
        all_frames.append(df)
    combined = pd.concat(all_frames, ignore_index=True)
    combined.to_csv(OUT_DIR / "SEC_vs_r_per_site.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    for site in SOURCES:
        df = combined[combined.site == site].copy()
        conv = df[df.converged == True]
        dnf  = df[df.converged == False]
        ax.plot(conv["r_recirc"], conv["SEC"], "o-",
                color=COLORS[site],
                label=f"{site.title()} (T_amb≈{T_AMB_MEAN[site]}°C)",
                linewidth=2, markersize=8)
        if len(dnf) > 0:
            ax.plot(dnf["r_recirc"], [0.95] * len(dnf), "x",
                    color=COLORS[site], markersize=10, markeredgewidth=2)

    ax.axhline(0.95, color="grey", linestyle=":", alpha=0.4)
    ax.text(0.02, 0.95, "DNF marker line", color="grey", fontsize=8,
            ha="left", va="bottom")

    ax.set_xlabel("Recirculation fraction r")
    ax.set_ylabel("SEC [kWh/kg water]")
    ax.set_title("Config A (HP-only, A_solar=0): SEC vs r per site\n"
                 "Two viable modes — r=0 (open-loop) and r=1.0 (fully closed). "
                 "x = DNF (24 h cap).")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=9)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0.3, 1.0)

    out_path = OUT_DIR / "SEC_vs_r_per_site.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"saved {out_path}")
    print(f"saved {OUT_DIR / 'SEC_vs_r_per_site.csv'}")
    print()
    print("Best-r per site:")
    for site in SOURCES:
        df = combined[(combined.site == site) & (combined.converged == True)]
        if len(df) > 0:
            best = df.loc[df.SEC.idxmin()]
            print(f"  {site}: r={best.r_recirc:.2f}  SEC={best.SEC:.4f}  "
                  f"time={best.drying_time_h:.2f}h")


if __name__ == "__main__":
    main()
