"""Plot R134a P-h diagram with the four cycle states (Fig. 1b of the paper).

Generates the pressure-enthalpy diagram of the R134a vapor-compression cycle
at a representative operating point (default: T_evap = 5 C, T_cond = 55 C,
Q_cond = 3 kW). The saturation dome is drawn from CoolProp, the four cycle
states are marked, and the isentropic compression endpoint 2s is shown as a
dashed line for reference.

Usage:
    python scripts/plot_ph_diagram.py
    python scripts/plot_ph_diagram.py --T_evap 0 --T_cond 55 --Q_cond 3
    python scripts/plot_ph_diagram.py --out paper/figs/fig1b.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RQ1_ROOT = PROJECT_ROOT / "RQ1"
sys.path.insert(0, str(RQ1_ROOT / "src"))

import CoolProp.CoolProp as CP  # noqa: E402
from rq1.heatpump import HeatPumpConfig, compute_heat_pump_cycle  # noqa: E402


def plot_ph_diagram(
    T_evap_C: float = 5.0,
    T_cond_C: float = 55.0,
    Q_cond_kW: float = 3.0,
    out_path: Path = Path("paper/figs/fig1b.png"),
) -> None:
    fluid = "R134a"
    cfg = HeatPumpConfig()
    res = compute_heat_pump_cycle(T_evap_C, T_cond_C, Q_cond_kW, cfg)

    # Saturation dome
    T_min = 230.0
    T_crit = CP.PropsSI(fluid, "Tcrit") - 0.1
    T_sat = np.linspace(T_min, T_crit, 250)
    h_f = np.array([CP.PropsSI("H", "T", T, "Q", 0, fluid) / 1000.0 for T in T_sat])
    h_g = np.array([CP.PropsSI("H", "T", T, "Q", 1, fluid) / 1000.0 for T in T_sat])
    P_sat = np.array([CP.PropsSI("P", "T", T, "Q", 0, fluid) / 1e5 for T in T_sat])

    h1, P1 = res.state_1.h_kJ_per_kg, res.state_1.P_Pa / 1e5
    h2, P2 = res.state_2.h_kJ_per_kg, res.state_2.P_Pa / 1e5
    h2s, P2s = res.state_2s.h_kJ_per_kg, res.state_2s.P_Pa / 1e5
    h3, P3 = res.state_3.h_kJ_per_kg, res.state_3.P_Pa / 1e5
    h4, P4 = res.state_4.h_kJ_per_kg, res.state_4.P_Pa / 1e5

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.plot(h_f, P_sat, "k-", lw=1.5, label="Saturation dome")
    ax.plot(h_g, P_sat, "k-", lw=1.5)

    # Cycle 1 -> 2 (real) -> 3 -> 4 -> 1
    h_cyc = [h1, h2, h3, h4, h1]
    P_cyc = [P1, P2, P3, P4, P1]
    ax.plot(h_cyc, P_cyc, "b-", lw=2.0)
    ax.scatter([h1, h2, h3, h4], [P1, P2, P3, P4], s=70, c="b", zorder=5)

    # Isentropic 1 -> 2s (dashed)
    ax.plot([h1, h2s], [P1, P2s], "b--", lw=1.2, alpha=0.6)
    ax.scatter([h2s], [P2s], marker="x", c="b", s=60, zorder=5)

    # Labels
    label_offsets = {
        "1": (h1, P1, 10, -14),
        "2": (h2, P2, 10, 8),
        "2s": (h2s, P2s, -20, 8),
        "3": (h3, P3, -16, 8),
        "4": (h4, P4, -18, -14),
    }
    for tag, (x, y, dx, dy) in label_offsets.items():
        weight = "bold" if tag != "2s" else "normal"
        color = "k" if tag != "2s" else "b"
        ax.annotate(
            tag, (x, y),
            textcoords="offset points", xytext=(dx, dy),
            fontsize=12, fontweight=weight, color=color,
        )

    # Process annotations
    ax.text(
        (h1 + h2) / 2 + 8, (P1 + P2) / 2, "Compression",
        rotation=70, fontsize=9, color="gray", ha="left", va="center",
    )
    ax.text(
        (h2 + h3) / 2, P2 * 1.04, "Condensation",
        fontsize=9, color="gray", ha="center",
    )
    ax.text(
        h3 - 2, (P3 + P4) / 2, "Expansion",
        rotation=90, fontsize=9, color="gray", ha="right", va="center",
    )
    ax.text(
        (h4 + h1) / 2, P1 * 0.85, "Evaporation",
        fontsize=9, color="gray", ha="center",
    )

    ax.set_yscale("log")
    ax.set_xlabel("Specific enthalpy h [kJ/kg]", fontsize=11)
    ax.set_ylabel("Pressure P [bar, log scale]", fontsize=11)
    ax.set_title(
        f"R134a vapor-compression cycle: "
        f"$T_{{evap}}$={T_evap_C:.0f} C, $T_{{cond}}$={T_cond_C:.0f} C, "
        f"COP={res.COP:.2f}",
        fontsize=11,
    )
    ax.grid(True, which="both", alpha=0.3, ls=":")

    # Pad x-axis
    h_min = min(h_f.min(), h4) - 20
    h_max = max(h_g.max(), h2) + 20
    ax.set_xlim(h_min, h_max)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"P-h diagram saved to {out_path}")
    print(f"  State 1 (suction):       T={res.state_1.T_C:6.2f} C  P={P1:5.2f} bar  h={h1:6.1f} kJ/kg")
    print(f"  State 2s (isentropic):   T={res.state_2s.T_C:6.2f} C  P={P2s:5.2f} bar  h={h2s:6.1f} kJ/kg")
    print(f"  State 2  (real discharge): T={res.state_2.T_C:6.2f} C  P={P2:5.2f} bar  h={h2:6.1f} kJ/kg")
    print(f"  State 3 (cond outlet):   T={res.state_3.T_C:6.2f} C  P={P3:5.2f} bar  h={h3:6.1f} kJ/kg")
    print(f"  State 4 (exp outlet):    T={res.state_4.T_C:6.2f} C  P={P4:5.2f} bar  h={h4:6.1f} kJ/kg  x={res.state_4.quality:.3f}")
    print(f"  m_ref = {res.m_ref_kg_per_s*1000:.2f} g/s")
    print(f"  Q_cond = {res.Q_cond_kW:.2f} kW, Q_evap = {res.Q_evap_kW:.2f} kW, W_comp = {res.W_comp_kW:.2f} kW")
    print(f"  COP = {res.COP:.2f}, PR = {res.pressure_ratio:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--T_evap", type=float, default=5.0, help="Evaporator temperature [C]")
    parser.add_argument("--T_cond", type=float, default=55.0, help="Condenser temperature [C]")
    parser.add_argument("--Q_cond", type=float, default=3.0, help="Condenser duty target [kW]")
    parser.add_argument("--out", type=str, default="paper/figs/fig1b.png", help="Output path")
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = RQ1_ROOT / out

    plot_ph_diagram(args.T_evap, args.T_cond, args.Q_cond, out)
