"""Step 2b textbook-style HRX diagram: counter-flow T vs position.

Mirrors the classical 'Counter flow' panel from heat-exchanger textbooks:
  - x-axis: dimensionless position along the exchanger (0 -> 1)
  - red curve: hot stream (exhaust), enters at x=0, leaves at x=1
  - blue curve: cold stream (ambient), enters at x=1, leaves at x=0
  - vertical arrows mark dT_a (cold-out / hot-in) and dT_b (hot-out / cold-in)

HRX in our model has equal m*cp on both sides (same air mass flow each way),
so Cr = 1, and both temperature profiles are LINEAR in x (textbook ideal
counter-flow case).

For each case we pick a representative steady-state timestep (median time
in the run) and label all four corner temperatures with the actual values.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots" / "_audit"
PLOTS.mkdir(parents=True, exist_ok=True)

CASES = [
    ("config_E2/kathmandu/Ac_10m2_hrx0.70.csv", "E2 Kathmandu annual"),
    ("config_E2/biratnagar/spring_mar_apr/Ac_10m2_hrx0.70.csv", "E2 Biratnagar spring"),
    ("config_E2/kathmandu/winter_dec_jan/Ac_10m2_hrx0.70.csv", "E2 Kathmandu winter"),
]


def pick_representative_idx(df: pd.DataFrame) -> int:
    """Pick the timestep closest to median drying time, with measurable HRX action."""
    grad = df["T_exhaust_C"] - df["T_amb_C"]
    valid = grad > 1.0  # need a real T-gradient
    candidates = df.index[valid]
    if len(candidates) == 0:
        return len(df) // 2
    median_t = df.loc[candidates, "time_h"].median()
    return int(candidates[np.argmin(np.abs(df.loc[candidates, "time_h"] - median_t))])


def make_plot(csv_rel: str, title: str):
    csv = OUT / csv_rel
    df = pd.read_csv(csv)
    i = pick_representative_idx(df)
    Ta = df["T_amb_C"].iloc[i]
    Th = df["T_amb_heated_C"].iloc[i]
    Te = df["T_exhaust_C"].iloc[i]
    Tec = df["T_exh_cooled_C"].iloc[i]
    t_h = df["time_h"].iloc[i]

    eps_a = (Th - Ta) / max(Te - Ta, 1e-6)

    # Counter-flow with Cr=1: linear profiles
    x = np.linspace(0, 1, 50)
    T_hot = Te - (Te - Tec) * x         # hot enters x=0, leaves x=1
    T_cold = Ta + (Th - Ta) * (1 - x)   # cold enters x=1, leaves x=0

    dT_a = Te - Th     # at x=0: hot-in vs cold-out
    dT_b = Tec - Ta    # at x=1: hot-out vs cold-in

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.suptitle(f"{title}  —  HRX counter-flow profile @ t = {t_h:.1f} h "
                 f"(achieved eps = {eps_a:.3f}, target 0.70)", fontsize=11)

    # Streams
    ax.plot(x, T_hot, color="tab:red", lw=2.4, label="hot stream (exhaust)")
    ax.plot(x, T_cold, color="tab:blue", lw=2.4, label="cold stream (ambient)")

    # Direction arrows above the plot (textbook style)
    ymax = max(Te, Th) + 8
    ymin = min(Ta, Tec) - 8
    ax.set_ylim(ymin, ymax)
    ax.annotate("", xy=(0.95, ymax - 2), xytext=(0.05, ymax - 2),
                arrowprops=dict(arrowstyle="->", color="tab:red", lw=1.5))
    ax.text(0.5, ymax - 1, "hot flow", ha="center", color="tab:red", fontsize=9)
    ax.annotate("", xy=(0.05, ymax - 5), xytext=(0.95, ymax - 5),
                arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.5))
    ax.text(0.5, ymax - 4, "cold flow", ha="center", color="tab:blue", fontsize=9)

    # Corner temperature labels
    ax.scatter([0, 0, 1, 1], [Te, Th, Tec, Ta], color=["tab:red", "tab:blue", "tab:red", "tab:blue"], zorder=5)
    ax.annotate(f"T_exhaust = {Te:.1f} °C", xy=(0, Te), xytext=(0.03, Te + 1.5), fontsize=9, color="tab:red")
    ax.annotate(f"T_amb_heated = {Th:.1f} °C", xy=(0, Th), xytext=(0.03, Th + 1.5), fontsize=9, color="tab:blue")
    ax.annotate(f"T_exh_cooled = {Tec:.1f} °C", xy=(1, Tec), xytext=(0.65, Tec + 1.5), fontsize=9, color="tab:red")
    ax.annotate(f"T_amb = {Ta:.1f} °C", xy=(1, Ta), xytext=(0.65, Ta - 3.0), fontsize=9, color="tab:blue")

    # dT arrows (textbook)
    ax.annotate("", xy=(0.02, Te), xytext=(0.02, Th),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.4))
    ax.text(-0.05, (Te + Th) / 2, f"ΔT_a\n{dT_a:.1f} °C", ha="right", va="center", fontsize=10)

    ax.annotate("", xy=(0.98, Tec), xytext=(0.98, Ta),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.4))
    ax.text(1.05, (Tec + Ta) / 2, f"ΔT_b\n{dT_b:.1f} °C", ha="left", va="center", fontsize=10)

    ax.set_xlabel("Dimensionless position along HRX  (0 = hot inlet / cold outlet)")
    ax.set_ylabel("Temperature [°C]")
    ax.set_xlim(-0.15, 1.15)
    ax.legend(loc="center right", fontsize=10)
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = PLOTS / f"step2b_hrx_textbook_{Path(csv_rel).parent.name}_{Path(csv_rel).stem}.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def main():
    for csv_rel, title in CASES:
        print(title)
        make_plot(csv_rel, title)


if __name__ == "__main__":
    main()
