"""Compare n_bends=4 (single-pass) vs n_bends=9 (serpentine) for KTM E2 Q1+Q3 batch0.

Plots fan power, total elec, MR, and SEC time series side-by-side.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "quarterly_test_compare"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    ("Q1 batch0 (Jan)", "Q1"),
    ("Q3 batch0 (Jul)", "Q3"),
]

REL = "config_E2/kathmandu/{quarter}/batch0_Ac_10m2_hrx0.70.csv"


def load(parent: str, quarter: str) -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / "outputs" / parent / REL.format(quarter=quarter))


fig, axes = plt.subplots(2, 4, figsize=(20, 9))

for row, (title, quarter) in enumerate(CASES):
    df4 = load("quarterly_test_nbend4", quarter)
    df9 = load("quarterly_test_nbend9", quarter)

    # --- MR curve ---
    ax = axes[row, 0]
    ax.plot(df4["time_h"], df4["MR_global"], "b-", lw=2, label=f"N_bend=4 (SEC={df4['SEC_elec_kWh_per_kg'].iloc[-1]:.4f})")
    ax.plot(df9["time_h"], df9["MR_global"], "r--", lw=1.5, label=f"N_bend=9 (SEC={df9['SEC_elec_kWh_per_kg'].iloc[-1]:.4f})")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("MR [-]")
    ax.set_title(f"{title}\nDrying curve")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # --- Fan power instantaneous ---
    ax = axes[row, 1]
    ax.plot(df4["time_h"], df4["W_fan_kW"] * 1000, "b-", lw=2, label="N_bend=4")
    ax.plot(df9["time_h"], df9["W_fan_kW"] * 1000, "r--", lw=1.5, label="N_bend=9")
    dP4_proxy = df4["W_fan_kW"].mean() / df4["W_fan_kW"].mean() if df4["W_fan_kW"].mean() else 0
    ax.set_xlabel("Time [h]"); ax.set_ylabel("Fan power [W]")
    delta_pct = 100 * (df9["W_fan_kW"].mean() - df4["W_fan_kW"].mean()) / df4["W_fan_kW"].mean()
    ax.set_title(f"Fan power (Δmean = +{delta_pct:.1f}%)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # --- Cumulative fan energy ---
    ax = axes[row, 2]
    ax.plot(df4["time_h"], df4["W_fan_cum_kWh"], "b-", lw=2, label=f"N_bend=4 ({df4['W_fan_cum_kWh'].iloc[-1]:.3f} kWh)")
    ax.plot(df9["time_h"], df9["W_fan_cum_kWh"], "r--", lw=1.5, label=f"N_bend=9 ({df9['W_fan_cum_kWh'].iloc[-1]:.3f} kWh)")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("W_fan cumulative [kWh]")
    delta_kwh = df9['W_fan_cum_kWh'].iloc[-1] - df4['W_fan_cum_kWh'].iloc[-1]
    ax.set_title(f"Cum fan energy (Δ = +{delta_kwh:.3f} kWh)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # --- Total elec cum (W_comp + W_fan) ---
    ax = axes[row, 3]
    elec4 = df4["W_comp_cum_kWh"] + df4["W_fan_cum_kWh"]
    elec9 = df9["W_comp_cum_kWh"] + df9["W_fan_cum_kWh"]
    ax.plot(df4["time_h"], elec4, "b-", lw=2, label=f"N_bend=4 ({elec4.iloc[-1]:.3f} kWh)")
    ax.plot(df9["time_h"], elec9, "r--", lw=1.5, label=f"N_bend=9 ({elec9.iloc[-1]:.3f} kWh)")
    ax.set_xlabel("Time [h]"); ax.set_ylabel("W_comp + W_fan cumulative [kWh]")
    delta_pct_elec = 100 * (elec9.iloc[-1] - elec4.iloc[-1]) / elec4.iloc[-1]
    ax.set_title(f"Cum total elec (delta = +{delta_pct_elec:.2f}%)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

plt.suptitle("KTM E2 — Single-pass (N_bend=4) vs Serpentine (N_bend=9) | A_solar=10 m², T_set=45°C", fontsize=12)
plt.tight_layout()
out_path = OUT_DIR / "nbend_compare_ktm_E2.png"
plt.savefig(out_path, dpi=130, bbox_inches="tight")
print(f"Saved: {out_path}")

# --- Numerical summary ---
print("\n=== Summary table ===")
print(f"{'Case':<20s} {'N=4 SEC':>10s} {'N=9 SEC':>10s} {'dSEC %':>8s} {'N=4 Wfan':>10s} {'N=9 Wfan':>10s} {'dWfan %':>8s}")
for title, quarter in CASES:
    df4 = load("quarterly_test_nbend4", quarter)
    df9 = load("quarterly_test_nbend9", quarter)
    sec4 = df4['SEC_elec_kWh_per_kg'].iloc[-1]
    sec9 = df9['SEC_elec_kWh_per_kg'].iloc[-1]
    wf4 = df4['W_fan_cum_kWh'].iloc[-1]
    wf9 = df9['W_fan_cum_kWh'].iloc[-1]
    print(f"{title:<20s} {sec4:>10.4f} {sec9:>10.4f} {100*(sec9-sec4)/sec4:>7.2f}% {wf4:>10.4f} {wf9:>10.4f} {100*(wf9-wf4)/wf4:>7.2f}%")
