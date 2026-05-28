"""Figures for §5.4 HRX configs D1, D2, D3.

fig_5_4a_sec_bar.png   — SEC for A | D1 off/on | D2 off/on | D3 at three sites
fig_5_4b_D2_evap.png   — D2 T_evap & COP profile vs D1 and A (BTN)
fig_5_4c_D3_humidity.png — D3 chamber humidity inversion: supply omega vs A/D1
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


def sec_of(f):
    d = pd.read_csv(f); l = d.iloc[-1]
    return (l["W_comp_cum_kWh"] + l["W_fan_cum_kWh"]) / l["m_w_cum_kg"]


# --- 5.4a SEC bars ----------------------------------------------------------
labels = ["A r=0", "D1", "D1+VPD", "D2", "D2+VPD", "D3"]
def file_for(cfg, loc):
    if cfg == "A r=0":
        return ROOT / f"outputs/config_A/{loc}/baseline_r0.0.csv"
    if cfg == "D1":     return ROOT / f"outputs/config_D1/{loc}/hrx_eps0.70.csv"
    if cfg == "D1+VPD": return ROOT / f"outputs/config_D1/{loc}/hrx_eps0.70_vpd0.05.csv"
    if cfg == "D2":     return ROOT / f"outputs/config_D2/{loc}/hrx_eps0.70.csv"
    if cfg == "D2+VPD": return ROOT / f"outputs/config_D2/{loc}/hrx_eps0.70_vpd0.05.csv"
    if cfg == "D3":     return ROOT / f"outputs/config_D3/{loc}/hrx_eps0.70.csv"

fig, ax = plt.subplots(figsize=(10, 4.4))
x = np.arange(len(labels))
width = 0.27
for i, (loc, lab, color) in enumerate(SITES):
    vals = [sec_of(file_for(cfg, loc)) for cfg in labels]
    ax.bar(x + (i-1)*width, vals, width, label=lab, color=color)
    for xi, v in zip(x + (i-1)*width, vals):
        ax.text(xi, v + 0.008, f"{v:.3f}", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel("SEC [kWh kg$^{-1}$]")
ax.set_title("HRX family vs HP-only baseline (r=0, ε_HRX=0.70)")
ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=9)
fig.tight_layout(); fig.savefig(HERE / "fig_5_4a_sec_bar.png", dpi=180, bbox_inches="tight")
plt.close(fig)

# --- 5.4b D2 vs D1 vs A at BTN: T_evap and COP -----------------------------
loc = "biratnagar"
dA  = pd.read_csv(file_for("A r=0", loc))
dD1 = pd.read_csv(file_for("D1", loc))
dD2 = pd.read_csv(file_for("D2", loc))
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
axT, axCOP = axes
for d, lab, col, ls in [(dA, "A r=0", "k", "-"), (dD1, "D1", "tab:purple", "-"), (dD2, "D2", "tab:cyan", "-")]:
    axT.plot(d["time_h"], d["T_evap_C"], color=col, ls=ls, lw=1.1, label=lab)
    axCOP.plot(d["time_h"], d["COP"], color=col, ls=ls, lw=1.1, label=lab)
axT.set_xlabel("Time [h]"); axT.set_ylabel("T_evap [°C]"); axT.set_title("(a) Refrigerant T_evap")
axT.legend(fontsize=9); axT.grid(alpha=0.3)
axCOP.set_xlabel("Time [h]"); axCOP.set_ylabel("COP [-]"); axCOP.set_title("(b) HP COP")
axCOP.legend(fontsize=9); axCOP.grid(alpha=0.3)
fig.suptitle("Biratnagar: D2 raises T_evap and COP by routing exhaust to the evaporator", fontsize=11)
fig.tight_layout(); fig.savefig(HERE / "fig_5_4b_D2_evap.png", dpi=180, bbox_inches="tight")
plt.close(fig)

# --- 5.4c D3 chamber-humidity inversion ------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(13, 4.0), sharey=True)
for ax, (loc, lab, _) in zip(axes, SITES):
    dA  = pd.read_csv(file_for("A r=0", loc))
    dD1 = pd.read_csv(file_for("D1", loc))
    dD3 = pd.read_csv(file_for("D3", loc))
    ax.plot(dA["time_h"], dA["omega_to_chamber"]*1000, color="k", lw=1.0, label="A (ambient supply)")
    ax.plot(dD1["time_h"], dD1["omega_to_chamber"]*1000, color="tab:purple", lw=1.0, label="D1 (HRX, amb)")
    ax.plot(dD3["time_h"], dD3["omega_to_chamber"]*1000, color="tab:orange", lw=1.3, label="D3 (HRX, exhaust-side)")
    ax.set_xlabel("Time [h]"); ax.set_title(lab); ax.grid(alpha=0.3)
axes[0].set_ylabel("ω_to_chamber [g kg$^{-1}$ dry air]")
axes[0].legend(fontsize=8, loc="upper right")
fig.suptitle("D3 inverts the HRX: chamber supply ω rises to ~19 g kg$^{-1}$, slowing kinetics",
             fontsize=11)
fig.tight_layout(); fig.savefig(HERE / "fig_5_4c_D3_humidity.png", dpi=180, bbox_inches="tight")
plt.close(fig)

print("Wrote fig_5_4a, 5_4b, 5_4c")
