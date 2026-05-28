"""VPD threshold sensitivity sweep (E2 config).

Tests whether the chosen threshold (0.05) is the SEC-optimum, and quantifies
the SEC vs drying-time trade-off across thresholds {0.00, 0.02, 0.05, 0.10,
0.15, 0.20} for two representative cases:
  - E2 Kathmandu annual    (mid-elevation, mixed conditions)
  - E2 Biratnagar autumn   (humid lowland, where bypass helps most)

Output:
  outputs/audit/step4_vpd_sweep.csv
  plots/_audit/step4_vpd_sweep.png   (SEC + drying time + bypass_frac vs threshold)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
PLOTS = PROJECT_ROOT / "plots" / "_audit"
AUDIT.mkdir(parents=True, exist_ok=True)
PLOTS.mkdir(parents=True, exist_ok=True)


def trapz_kWh(s, t_s):
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    return float(np.sum(np.asarray(s) * dt_h))


def metrics(csv: Path, threshold: float, case: str) -> dict:
    df = pd.read_csv(csv)
    t_s = df["time_s"].to_numpy()
    Wc = trapz_kWh(df["W_comp_kW"], t_s)
    Wf = trapz_kWh(df["W_fan_kW"], t_s) if "W_fan_kW" in df.columns else 0.0
    Wt = Wc + Wf
    Qsu = trapz_kWh(df["Q_solar_usable_kW"], t_s) if "Q_solar_usable_kW" in df.columns else float("nan")
    mw = float(df["m_w_cum_kg"].iloc[-1])
    th = float(df["time_h"].iloc[-1])
    bypass = (float(df["vpd_bypass_active"].astype(int).sum() / len(df))
              if "vpd_bypass_active" in df.columns else 0.0)
    return dict(case=case, threshold=threshold, t_h=th, m_w=mw,
                W_comp=Wc, W_fan=Wf, W_total=Wt, Q_solar_usable=Qsu,
                SEC=Wt/mw if mw > 1e-6 else float("nan"),
                SMER=mw/Wt if Wt > 1e-6 else float("nan"),
                bypass_frac=bypass)


CASES = [
    ("KTM_annual", OUT / "config_E2/kathmandu", ""),
    ("BTN_autumn", OUT / "config_E2/biratnagar/autumn_oct_nov", ""),
]
THRESHOLDS = [0.00, 0.02, 0.05, 0.10, 0.15, 0.20]


def main():
    rows = []
    for case_name, base, _ in CASES:
        for t in THRESHOLDS:
            if t == 0.0:
                csv = base / "Ac_10m2_hrx0.70.csv"
            else:
                csv = base / f"Ac_10m2_hrx0.70_vpd{t:.2f}.csv"
            if not csv.exists():
                print(f"  missing {csv.relative_to(OUT)}")
                continue
            rows.append(metrics(csv, t, case_name))
    df = pd.DataFrame(rows)
    out_csv = AUDIT / "step4_vpd_sweep.csv"
    df.to_csv(out_csv, index=False, float_format="%.6g")
    print(f"Saved {out_csv} ({len(df)} rows)\n")

    print("=== SEC vs threshold ===")
    print(df.pivot_table(index="threshold", columns="case",
                         values="SEC").to_string(float_format=lambda v: f"{v:7.4f}"))
    print("\n=== drying time t_h vs threshold ===")
    print(df.pivot_table(index="threshold", columns="case",
                         values="t_h").to_string(float_format=lambda v: f"{v:7.3f}"))
    print("\n=== bypass_frac vs threshold ===")
    print(df.pivot_table(index="threshold", columns="case",
                         values="bypass_frac").to_string(float_format=lambda v: f"{v:7.3f}"))

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("E2 VPD threshold sweep — SEC vs drying time trade-off",
                 fontsize=12, weight="bold")
    colors = {"KTM_annual": "tab:blue", "BTN_autumn": "tab:red"}
    markers = {"KTM_annual": "o", "BTN_autumn": "s"}

    ax = axes[0]
    for case in df["case"].unique():
        sub = df[df["case"] == case].sort_values("threshold")
        ax.plot(sub["threshold"], sub["SEC"], marker=markers[case],
                color=colors[case], label=case, lw=1.6)
    ax.axvline(0.05, color="black", ls="--", lw=1, label="recommended")
    ax.set_xlabel("VPD threshold")
    ax.set_ylabel("SEC [kWh/kg]")
    ax.set_title("SEC vs threshold")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    for case in df["case"].unique():
        sub = df[df["case"] == case].sort_values("threshold")
        ax.plot(sub["threshold"], sub["t_h"], marker=markers[case],
                color=colors[case], label=case, lw=1.6)
    ax.axvline(0.05, color="black", ls="--", lw=1)
    ax.set_xlabel("VPD threshold")
    ax.set_ylabel("Drying time [h]")
    ax.set_title("Drying time vs threshold")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[2]
    for case in df["case"].unique():
        sub = df[df["case"] == case].sort_values("threshold")
        ax.plot(sub["threshold"], sub["bypass_frac"] * 100,
                marker=markers[case], color=colors[case], label=case, lw=1.6)
    ax.axvline(0.05, color="black", ls="--", lw=1)
    ax.set_xlabel("VPD threshold")
    ax.set_ylabel("Bypass active fraction [%]")
    ax.set_title("Bypass duty vs threshold")
    ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out_png = PLOTS / "step4_vpd_sweep.png"
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    print(f"\nSaved {out_png.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
