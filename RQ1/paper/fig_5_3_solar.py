"""Figures for §5.3 solar configs: B, C1, C2.

fig_5_3a_sec_bar.png        — SEC comparison vs Config A baseline at 3 sites
fig_5_3b_B_timeseries.png   — Config B six-panel time-series drilldown
fig_5_3c_C1_TPJ_diag.png    — C1-TPJ chamber-temperature diagnostic
fig_5_3d_C2_evap.png        — C2 T_evap & COP profile vs A
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
ROOT = HERE.parent
SITES = [("biratnagar", "Biratnagar", "tab:red"),
         ("kathmandu", "Kathmandu", "tab:blue"),
         ("taplejung", "Taplejung", "tab:green")]
A_BASE = {"biratnagar": 0.555, "kathmandu": 0.730, "taplejung": 0.578}


def load(cfg, loc, fname="Ac_10m2.csv"):
    return pd.read_csv(ROOT / f"outputs/config_{cfg}/{loc}/{fname}")


def sec_of(d):
    last = d.iloc[-1]
    return (last["W_comp_cum_kWh"] + last["W_fan_cum_kWh"]) / last["m_w_cum_kg"]


# --- 5.3a SEC bars ----------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.2))
configs = ["A", "B", "C1", "C2"]
loc_keys = [s[0] for s in SITES]
x = np.arange(len(configs))
width = 0.26
for i, (loc, lab, color) in enumerate(SITES):
    vals = []
    for cfg in configs:
        if cfg == "A":
            d = pd.read_csv(ROOT / f"outputs/config_A/{loc}/baseline_r0.0.csv")
        else:
            d = load(cfg, loc)
        vals.append(sec_of(d))
    ax.bar(x + (i-1)*width, vals, width, label=lab, color=color)
    for xi, v in zip(x + (i-1)*width, vals):
        ax.text(xi, v + 0.012, f"{v:.3f}", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(configs); ax.set_ylabel("SEC [kWh kg$^{-1}$]")
ax.set_title("Solar configs vs HP-only baseline (r=0, A_c = 10 m$^2$)")
ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=9)
fig.tight_layout(); fig.savefig(HERE / "fig_5_3a_sec_bar.png", dpi=180, bbox_inches="tight")
plt.close(fig)

# --- 5.3b Config B time series ----------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
axQs, axQc, axCOP, axX = axes.flatten()
for loc, lab, color in SITES:
    d = load("B", loc)
    t = d["time_h"]
    axQs.plot(t, d["Q_solar_kW"], color=color, lw=1.1, label=lab)
    axQc.plot(t, d["Q_cond_kW"], color=color, lw=1.1)
    axCOP.plot(t, d["COP"], color=color, lw=1.1)
    axX.plot(t, d["X_db_avg"], color=color, lw=1.3)
axQs.set_ylabel("Q_solar [kW]"); axQs.set_title("(a) Solar thermal delivery")
axQc.set_ylabel("Q_cond [kW]"); axQc.set_title("(b) Condenser duty (reduced by Q_solar)")
axCOP.set_ylabel("COP [-]"); axCOP.set_title("(c) HP COP (unchanged, ambient evap)")
axX.set_ylabel("X_db"); axX.set_title("(d) Drying curve")
axX.axhline(0.10, color="k", ls=":", lw=0.7)
for ax in axes.flatten():
    ax.set_xlabel("Time [h]"); ax.grid(alpha=0.3)
axQs.legend(fontsize=9, loc="upper right")
fig.suptitle("Config B (solar + HP series, r=0, A_c=10 m$^2$): solar offsets condenser duty",
             fontsize=11)
fig.tight_layout(); fig.savefig(HERE / "fig_5_3b_B_timeseries.png", dpi=180, bbox_inches="tight")
plt.close(fig)

# --- 5.3c C1-Taplejung diagnostic -------------------------------------------
d = load("C1", "taplejung")
fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
ax1, ax2 = axes
t = d["time_h"]
ax1.plot(t, d["T_amb_C"], color="grey", lw=0.9, label="T_amb")
ax1.plot(t, d["T_solar_out_C"], color="orange", lw=0.9, label="T_after_solar")
ax1.plot(t, d["T_after_evap_C"], color="tab:cyan", lw=0.9, label="T_after_evap")
ax1.plot(t, d["T_to_chamber_C"], color="tab:red", lw=1.2, label="T_to_chamber")
ax1.axhline(45, color="k", ls="--", lw=0.7, label="T_set = 45 °C")
ax1.set_ylabel("Temperature [°C]")
ax1.set_title("C1-Taplejung: inline evaporator drags supply air below set-point")
ax1.legend(fontsize=8, ncol=5, loc="upper right"); ax1.grid(alpha=0.3)

ax2.plot(t, d["T_evap_C"], color="tab:purple", lw=0.9, label="T_evap (refrigerant)")
ax2.axhline(-5, color="tab:red", ls=":", lw=0.7, label="frost floor (-5 °C)")
ax2.fill_between(t, -8, 12, where=d["flag_frost_risk"]>0,
                 color="tab:red", alpha=0.10, label="frost flag active")
ax2.plot(t, d["G_solar_Wm2"]/100.0, color="goldenrod", lw=0.7, label="GHI / 100 [W m⁻² → 10 W m⁻²]")
ax2.set_ylabel("T_evap [°C] / GHI scaled")
ax2.set_xlabel("Time [h]")
ax2.legend(fontsize=8, ncol=4); ax2.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(HERE / "fig_5_3c_C1_TPJ_diag.png", dpi=180, bbox_inches="tight")
plt.close(fig)

# --- 5.3d C2 T_evap & COP boost ---------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
axT, axCOP = axes
for loc, lab, color in SITES:
    dA = pd.read_csv(ROOT / f"outputs/config_A/{loc}/baseline_r0.0.csv")
    dC2 = load("C2", loc)
    axT.plot(dA["time_h"], dA["T_evap_C"], color=color, lw=0.9, ls=":", alpha=0.7)
    axT.plot(dC2["time_h"], dC2["T_evap_C"], color=color, lw=1.2, label=f"{lab} (C2)")
    axCOP.plot(dA["time_h"], dA["COP"], color=color, lw=0.9, ls=":", alpha=0.7)
    axCOP.plot(dC2["time_h"], dC2["COP"], color=color, lw=1.2, label=f"{lab} (C2)")
axT.set_ylabel("T_evap [°C]"); axT.set_xlabel("Time [h]"); axT.set_title("(a) Evaporator refrigerant temperature: dotted=A, solid=C2")
axCOP.set_ylabel("COP [-]"); axCOP.set_xlabel("Time [h]"); axCOP.set_title("(b) HP COP: dotted=A, solid=C2")
for ax in axes: ax.grid(alpha=0.3); ax.legend(fontsize=8)
fig.suptitle("Config C2 (mix-after-solar): solar feeds the evaporator side, raising T_evap and COP",
             fontsize=11)
fig.tight_layout(); fig.savefig(HERE / "fig_5_3d_C2_evap.png", dpi=180, bbox_inches="tight")
plt.close(fig)

print("Wrote fig_5_3a, 5_3b, 5_3c, 5_3d")
