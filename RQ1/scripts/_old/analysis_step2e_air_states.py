"""Air-state schematic for E1/E2/E3 at hr=1, 3, 5, 10 (KTM annual).

Minimalist: dots = air states, arrows = flow legs, labels = T (°C).
Component names sit next to their dots, no boxes.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots" / "_audit"
PLOTS.mkdir(parents=True, exist_ok=True)

HOURS = [1.0, 3.0, 5.0, 10.0]


def pick_row(df: pd.DataFrame, t_h: float):
    i = (df["time_h"] - t_h).abs().idxmin()
    return df.loc[i]


def draw_arrow(ax, x0, y0, x1, y1, color="#3a7"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.4))


def T_label(ax, x, y, T, color="#d33", offset=(0, 0.25)):
    ax.text(x + offset[0], y + offset[1], f"{T:.1f}°C",
            color=color, ha="center", va="center", fontsize=9, weight="bold")


def state_dot(ax, x, y, name, color="black"):
    ax.plot(x, y, "o", color=color, markersize=7, zorder=5)
    ax.text(x, y - 0.35, name, ha="center", va="top", fontsize=8, color="#333")


def draw_panel(ax, row, config: str, t_h: float):
    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(-1.0, 5.5)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#bbb")

    Ta = row["T_amb_C"]
    Th = row["T_amb_heated_C"]
    Tso = row["T_solar_out_C"]
    Tcin = row["T_air_in_cond_C"]
    Tcout = row["T_cond_out_C"]
    Tch = row["T_to_chamber_C"]
    Te = row["T_exhaust_C"]
    Tec = row["T_exh_cooled_C"]
    Tev_src = row["T_evap_source_C"]
    Tev = row["T_evap_C"]
    G = row["G_solar_Wm2"]
    W = float(row.get("W_comp_kW", 0.0))
    if W < 0.01:
        mode = "off (solar covers)"
    elif Tcout < Tch - 0.3:
        mode = "partial (HP + solar)"
    else:
        mode = "full"

    # Top air path: 5 dots in a line
    y = 4.0
    xs = [0.5, 2.7, 5.4, 8.1, 10.8]

    if config in ("E1", "E2"):
        names = ["Amb", "HRX-out", "Solar-out", "Cond-out", "Chamber-in"]
        Ts = [Ta, Th, Tso, Tcout, Tch]
    else:  # E3: Solar AFTER condenser
        names = ["Amb", "HRX-out", "Cond-out", "Solar-out", "Chamber-in"]
        Ts = [Ta, Th, Tcout, Tso, Tch]

    for x, name, T in zip(xs, names, Ts):
        state_dot(ax, x, y, name)
        T_label(ax, x, y, T)

    # Component labels between dots
    if config in ("E1", "E2"):
        comp_names = ["HRX", "Solar", "Cond"]
    else:
        comp_names = ["HRX", "Cond", "Solar"]
    for i, cn in enumerate(comp_names):
        xm = (xs[i] + xs[i + 1]) / 2
        draw_arrow(ax, xs[i] + 0.15, y, xs[i + 1] - 0.15, y)
        ax.text(xm, y + 0.85, cn, ha="center", fontsize=9, color="#3a7", style="italic")

    # Cond -> Chamber arrow
    draw_arrow(ax, xs[3] + 0.15, y, xs[4] - 0.15, y)

    # Bottom: exhaust loop
    y2 = 1.8
    state_dot(ax, 10.8, y2, "Chamber-out")
    T_label(ax, 10.8, y2, Te, color="#a05", offset=(0.7, 0))

    state_dot(ax, 2.7, y2, "Exh-cooled")
    T_label(ax, 2.7, y2, Tec, color="#a05", offset=(-0.6, 0))

    # Chamber drop-down (right)
    draw_arrow(ax, 10.8, y - 0.2, 10.8, y2 + 0.2, color="#a05")
    # Exhaust right -> left through HRX
    draw_arrow(ax, 10.6, y2, 2.9, y2, color="#a05")
    ax.text(6.5, y2 + 0.35, "exhaust  →  HRX hot side", ha="center", fontsize=8, color="#a05", style="italic")
    # Expel up-left from HRX
    draw_arrow(ax, 2.5, y2, 0.5, y2 + 0.6, color="#888")
    ax.text(1.0, y2 + 0.85, "expel", ha="center", fontsize=8, color="#888")

    # Evap source dot (low row)
    y3 = 0.0
    if config == "E1":
        evap_label = "Evap-src = Amb"
    else:
        evap_label = "Evap-src = exh+amb"
    state_dot(ax, 5.4, y3, evap_label)
    T_label(ax, 5.4, y3, Tev_src, color="#06a", offset=(2.0, 0))
    ax.text(5.4 + 2.0, y3 - 0.25, f"T_evap(refr)={Tev:.1f}°C",
            ha="center", fontsize=7.5, color="#06a", style="italic")

    # Title strip
    ax.text(0.0, 5.15,
            f"{config}   t = {t_h:.0f} h   G = {G:.0f} W/m²   hp_mode = {mode}",
            fontsize=10.5, weight="bold", color="#111")


def make_figure(config: str, csv_rel: str):
    df = pd.read_csv(OUT / csv_rel)
    fig, axes = plt.subplots(2, 2, figsize=(15, 8.5))
    fig.suptitle(f"Air states — {config} (Kathmandu annual, 10 m² collector)",
                 fontsize=12.5, weight="bold")
    for ax, t_h in zip(axes.flat, HOURS):
        row = pick_row(df, t_h)
        draw_panel(ax, row, config, t_h)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = PLOTS / f"step2e_air_states_{config}_kathmandu_annual.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def main():
    cases = [
        ("E1", "config_E1/kathmandu/Ac_10m2_hrx0.70.csv"),
        ("E2", "config_E2/kathmandu/Ac_10m2_hrx0.70.csv"),
        ("E3", "config_E3/kathmandu/Ac_10m2_hrx0.70.csv"),
    ]
    for cfg, csv_rel in cases:
        if (OUT / csv_rel).exists():
            make_figure(cfg, csv_rel)


if __name__ == "__main__":
    main()
