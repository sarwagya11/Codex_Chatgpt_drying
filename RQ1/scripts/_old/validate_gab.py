"""Validate the GAB sorption isotherm used in RQ1.

Reproduces X_eq(aw, T) curves for the apple GAB parameters hard-coded in
``rq1.kinetics.gab_equilibrium_moisture`` and writes:

  outputs/audit/gab_validation.csv   table of X_eq at (T, aw)
  outputs/audit/gab_validation.png   X_eq vs aw at T = 25, 35, 45, 55, 60 C

Also prints a sanity report flagging:
  * high-aw blow-up driven by K ~ 1
  * the dHk = -0.8 J/mol parameter (suspected unit error vs source)
  * comparison against published-range bands for apple at selected states.

Run:
    python -m scripts.validate_gab
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rq1.kinetics import (
    _GAB_C0, _GAB_K0, _GAB_R, _GAB_Xm0,
    _GAB_dH_xm, _GAB_dHc, _GAB_dHk,
    gab_equilibrium_moisture,
)

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def gab_params(T_C: float) -> dict:
    T_K = T_C + 273.15
    return {
        "T_C": T_C,
        "Xm": _GAB_Xm0 * math.exp(_GAB_dH_xm / (_GAB_R * T_K)),
        "C":  _GAB_C0  * math.exp(_GAB_dHc   / (_GAB_R * T_K)),
        "K":  _GAB_K0  * math.exp(_GAB_dHk   / (_GAB_R * T_K)),
    }


def _build_table() -> pd.DataFrame:
    rows = []
    for T_C in (25, 30, 35, 40, 45, 50, 55, 60):
        p = gab_params(T_C)
        for aw in np.linspace(0.05, 0.95, 19):
            X_eq = gab_equilibrium_moisture(T_C, float(aw))
            rows.append({"T_C": T_C, "aw": round(float(aw), 3),
                         "Xm": p["Xm"], "C": p["C"], "K": p["K"],
                         "X_eq_db": X_eq})
    return pd.DataFrame(rows)


def _plot(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for T_C in (25, 35, 45, 55, 60):
        sub = df[df.T_C == T_C]
        ax.plot(sub.aw, sub.X_eq_db, marker="o", ms=3, label=f"{T_C} °C")
    ax.axhline(0.10, color="k", ls="--", lw=0.8, alpha=0.4,
               label="X_final target = 0.20")
    ax.set_xlabel("water activity  a_w (= RH)")
    ax.set_ylabel("X_eq  [kg water / kg dry mass]")
    ax.set_title("GAB isotherm as implemented in rq1.kinetics")
    ax.set_ylim(0, 1.2)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _sanity_checks(df: pd.DataFrame) -> list[str]:
    msgs: list[str] = []
    # Param values
    msgs.append("─── Parameter values ───")
    msgs.append(f"  Xm0  = {_GAB_Xm0:.4e}  kg/kg db   (monolayer pre-exp)")
    msgs.append(f"  ΔHm  = {_GAB_dH_xm:.1f} J/mol")
    msgs.append(f"  C0   = {_GAB_C0:.4e}              (Guggenheim pre-exp)")
    msgs.append(f"  ΔHc  = {_GAB_dHc:.1f} J/mol")
    msgs.append(f"  K0   = {_GAB_K0:.4f}              (multilayer pre-exp)")
    msgs.append(f"  ΔHk  = {_GAB_dHk:.4f} J/mol")
    msgs.append("")

    # Temperature trend of K
    p25 = gab_params(25); p60 = gab_params(60)
    msgs.append("─── Temperature dependence of K ───")
    msgs.append(f"  K(25 °C) = {p25['K']:.4f}")
    msgs.append(f"  K(60 °C) = {p60['K']:.4f}")
    msgs.append(f"  ΔK / K   = {(p60['K'] - p25['K']) / p25['K'] * 100:+.3f}%")
    if abs(p60['K'] - p25['K']) / p25['K'] < 0.01:
        msgs.append("  ⚠ K is essentially T-independent. Published apple-GAB "
                    "fits typically report ΔHk on the order of 0.1-5 kJ/mol "
                    "(i.e. 100-5000 J/mol). The current −0.8 J/mol may be a "
                    "kJ → J unit error in the source transcription.")
    msgs.append("")

    # High-aw blow-up
    msgs.append("─── High-aw behaviour ───")
    for T_C in (25, 45, 60):
        for aw in (0.80, 0.90, 0.95):
            v = gab_equilibrium_moisture(T_C, aw)
            tag = " ⚠ unphysical (>0.50 kg/kg db)" if v > 0.50 else ""
            msgs.append(f"  X_eq({T_C} °C, aw={aw:.2f}) = {v:.3f} kg/kg db{tag}")
    msgs.append("")

    # Pole location
    K_mean = 0.5 * (p25['K'] + p60['K'])
    msgs.append(f"  K ≈ {K_mean:.4f} → singularity at aw = 1/K = {1/K_mean:.4f}")
    msgs.append("  Code clamps aw ≤ 0.95 to dodge the pole.")
    msgs.append("")

    # Headline-condition values
    msgs.append("─── Values at typical chamber-inlet states ───")
    for T_C, RH in [(45, 0.10), (45, 0.20), (45, 0.30), (45, 0.50),
                    (50, 0.20), (55, 0.20)]:
        msgs.append(f"  X_eq({T_C} °C, RH={RH:.2f}) = "
                    f"{gab_equilibrium_moisture(T_C, RH):.4f} kg/kg db")
    msgs.append("")

    # Comparison band (qualitative)
    msgs.append("─── Comparison vs published apple sorption band ───")
    msgs.append("  Reference band (Mbarek & Mihoubi 2019, Bhandari fruits)")
    msgs.append("  T=25 °C, aw=0.50:  X_eq ≈ 0.10-0.15.  Model: "
                f"{gab_equilibrium_moisture(25, 0.50):.3f}")
    msgs.append("  T=25 °C, aw=0.70:  X_eq ≈ 0.22-0.28.  Model: "
                f"{gab_equilibrium_moisture(25, 0.70):.3f}")
    msgs.append("  T=25 °C, aw=0.90:  X_eq ≈ 0.30-0.40.  Model: "
                f"{gab_equilibrium_moisture(25, 0.90):.3f}")
    msgs.append("  T=50 °C, aw=0.50:  X_eq ≈ 0.08-0.12.  Model: "
                f"{gab_equilibrium_moisture(50, 0.50):.3f}")

    return msgs


def main() -> None:
    df = _build_table()
    csv_path = OUT_DIR / "gab_validation.csv"
    png_path = OUT_DIR / "gab_validation.png"
    df.to_csv(csv_path, index=False)
    _plot(df, png_path)
    print(f"  wrote  {csv_path}")
    print(f"  wrote  {png_path}\n")
    print("\n".join(_sanity_checks(df)))


if __name__ == "__main__":
    main()
