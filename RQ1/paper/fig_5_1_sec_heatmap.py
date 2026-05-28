"""Figure 5.1: 8x3 SEC heatmap (M1) with M2 bracket annotated per cell."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "outputs" / "audit" / "phase_d_sec_summary.csv"
DST = Path(__file__).parent / "fig_5_1_sec_heatmap.png"

CONFIGS = ["A", "B", "C1", "C2", "D1", "D2", "E1", "E2"]
LOCS = ["biratnagar", "kathmandu", "taplejung"]
LOC_LABEL = ["Biratnagar\n(72 m)", "Kathmandu\n(1350 m)", "Taplejung\n(1820 m)"]


def main():
    df = pd.read_csv(SRC)
    M1 = df[df["model"] == "M1"].pivot(index="config", columns="location", values="SEC")
    M2 = df[df["model"] == "M2"].pivot(index="config", columns="location", values="SEC")
    M1 = M1.reindex(index=CONFIGS, columns=LOCS)
    M2 = M2.reindex(index=CONFIGS, columns=LOCS)

    fig, ax = plt.subplots(figsize=(6.0, 7.5))
    norm = LogNorm(vmin=0.09, vmax=1.0)
    im = ax.imshow(M1.values, aspect="auto", cmap="viridis_r", norm=norm)

    for i, cfg in enumerate(CONFIGS):
        for j, loc in enumerate(LOCS):
            m1 = M1.iloc[i, j]; m2 = M2.iloc[i, j]
            color = "white" if m1 > 0.35 else "black"
            ax.text(j, i - 0.12, f"{m1:.3f}", ha="center", va="center",
                    color=color, fontsize=9, fontweight="bold")
            ax.text(j, i + 0.22, f"({m2:.3f})", ha="center", va="center",
                    color=color, fontsize=7.5, style="italic")

    ax.set_xticks(range(3)); ax.set_xticklabels(LOC_LABEL, fontsize=9)
    ax.set_yticks(range(len(CONFIGS))); ax.set_yticklabels(CONFIGS, fontsize=10)
    ax.set_title("SEC [kWh kg$^{-1}$ water]: M1 bold, (M2) italic", fontsize=10)
    cbar = fig.colorbar(im, ax=ax, fraction=0.06, pad=0.04)
    cbar.set_label("SEC [kWh kg$^{-1}$]", fontsize=9)
    fig.tight_layout()
    fig.savefig(DST, dpi=200, bbox_inches="tight")
    print(f"Wrote {DST}")


if __name__ == "__main__":
    main()
