"""Figure 5.2b: Six-panel deep dive on Config A r=0 at three sites.

Time-series traces pulled directly from outputs/config_A/{loc}/baseline_r0.0.csv.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DST = Path(__file__).parent / "fig_5_2b_deep.png"

SITES = [("biratnagar", "Biratnagar", "tab:red"),
         ("kathmandu", "Kathmandu", "tab:blue"),
         ("taplejung", "Taplejung", "tab:green")]


def load(loc):
    return pd.read_csv(ROOT / f"outputs/config_A/{loc}/baseline_r0.0.csv")


fig, axes = plt.subplots(3, 2, figsize=(11.5, 10))
ax_T, ax_VPD, ax_Q, ax_COP, ax_X, ax_W = axes.flatten()

for loc, label, color in SITES:
    d = load(loc)
    t = d["time_h"]
    ax_T.plot(t, d["T_amb_C"], color=color, label=label, lw=1.1)
    ax_VPD.plot(t, d["VPD_ambient_Pa"]/1000.0, color=color, lw=1.1)
    ax_Q.plot(t, d["Q_cond_kW"], color=color, lw=1.0)
    ax_COP.plot(t, d["COP"], color=color, lw=1.1)
    ax_X.plot(t, d["X_db_avg"], color=color, lw=1.3)
    ax_W.plot(t, d["W_comp_cum_kWh"], color=color, lw=1.3)

ax_T.set_ylabel("T_amb [°C]");          ax_T.set_title("(a) Ambient temperature")
ax_VPD.set_ylabel("VPD_amb [kPa]");     ax_VPD.set_title("(b) Ambient vapour-pressure deficit")
ax_Q.set_ylabel("Q_cond [kW]");         ax_Q.set_title("(c) Condenser thermal duty")
ax_COP.set_ylabel("COP [-]");           ax_COP.set_title("(d) Heat-pump COP")
ax_X.set_ylabel("X_db [kg kg⁻¹ db]");  ax_X.set_title("(e) Bulk-average drying curve")
ax_X.axhline(0.10, color="k", ls=":", lw=0.7); ax_X.text(0.2, 0.13, "X_target=0.10", fontsize=8)
ax_W.set_ylabel("W_comp cum. [kWh]");   ax_W.set_title("(f) Cumulative compressor work")

for ax in axes.flatten():
    ax.set_xlabel("Time [h]"); ax.grid(alpha=0.3)
ax_T.legend(loc="lower right", fontsize=9)

fig.suptitle("Config A (HP only, r=0): time-series drilldown at three sites", fontsize=11)
fig.tight_layout()
fig.savefig(DST, dpi=180, bbox_inches="tight")
print(f"Wrote {DST}")
