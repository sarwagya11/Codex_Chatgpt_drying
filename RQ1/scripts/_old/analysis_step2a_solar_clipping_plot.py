"""Step 2a diagnostic plot: solar gross vs usable vs clipped, with T_solar_out vs T_set.

Picks one canonical E2 run + spring (high clipping) + winter (low clipping) for
visual contrast. Output: plots/_audit/step2a_solar_clipping_*.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates  # noqa: F401
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PLOTS = PROJECT_ROOT / "plots" / "_audit"
OUT_PLOTS.mkdir(parents=True, exist_ok=True)

CASES = [
    ("config_E2/biratnagar/spring_mar_apr/Ac_10m2_hrx0.70.csv",
     "E2 Biratnagar spring (high clipping case)"),
    ("config_E2/kathmandu/winter_dec_jan/Ac_10m2_hrx0.70.csv",
     "E2 Kathmandu winter (low clipping case)"),
    ("config_E2/kathmandu/Ac_10m2_hrx0.70.csv",
     "E2 Kathmandu annual"),
]


def make_plot(csv_rel: str, title: str):
    csv = PROJECT_ROOT / "outputs" / csv_rel
    df = pd.read_csv(csv)
    t_h = df["time_h"].to_numpy()

    G = df["G_solar_Wm2"].to_numpy()
    Q_gross = df["Q_solar_kW"].to_numpy()
    Q_usable = df["Q_solar_usable_kW"].to_numpy() if "Q_solar_usable_kW" in df.columns else Q_gross
    Q_clip = df["Q_solar_clipped_kW"].to_numpy() if "Q_solar_clipped_kW" in df.columns else (Q_gross - Q_usable)
    T_out = df["T_solar_out_C"].to_numpy()
    T_in = df["T_solar_in_C"].to_numpy() if "T_solar_in_C" in df.columns else df["T_amb_C"].to_numpy()
    T_set = 45.0

    dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0
    Q_gross_kWh = float(np.sum(Q_gross * dt_h))
    Q_usable_kWh = float(np.sum(Q_usable * dt_h))
    Q_clip_kWh = float(np.sum(Q_clip * dt_h))
    clip_frac = Q_clip_kWh / Q_gross_kWh if Q_gross_kWh > 0 else 0.0

    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=True)
    fig.suptitle(f"{title}\nSolar clipping diagnostic — gross {Q_gross_kWh:.1f} kWh, "
                 f"usable {Q_usable_kWh:.1f} kWh, clipped {Q_clip_kWh:.1f} kWh "
                 f"({clip_frac*100:.1f}%)", fontsize=12)

    ax0 = axes[0]
    ax0.fill_between(t_h, 0, Q_usable, color="tab:green", alpha=0.7, label="Usable Q_solar (delivered)")
    ax0.fill_between(t_h, Q_usable, Q_usable + Q_clip, color="tab:red", alpha=0.5, label="Clipped Q_solar (wasted)")
    ax0.plot(t_h, Q_gross, color="black", lw=0.6, label="Gross Q_solar")
    ax0.set_ylabel("Solar power [kW]")
    ax0.legend(loc="upper right", fontsize=9)
    ax0.grid(alpha=0.3)

    ax1 = axes[1]
    ax1.plot(t_h, T_out, color="tab:red", label="T_solar_out")
    ax1.plot(t_h, T_in, color="tab:blue", label="T_solar_in (post HRX)")
    ax1.axhline(T_set, color="black", lw=1, ls="--", label=f"T_set = {T_set} °C (clipping bites here)")
    ax1.set_ylabel("Temperature [°C]")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(alpha=0.3)

    ax2 = axes[2]
    ax2.plot(t_h, G, color="tab:orange", lw=0.8)
    ax2.set_ylabel("G_solar [W/m²]")
    ax2.grid(alpha=0.3)

    ax3 = axes[3]
    cum_usable = np.cumsum(Q_usable * dt_h)
    cum_clip = np.cumsum(Q_clip * dt_h)
    ax3.fill_between(t_h, 0, cum_usable, color="tab:green", alpha=0.6, label="Cumulative usable")
    ax3.fill_between(t_h, cum_usable, cum_usable + cum_clip, color="tab:red", alpha=0.4, label="Cumulative clipped")
    ax3.set_ylabel("Cumulative [kWh]")
    ax3.set_xlabel("Drying time [h]")
    ax3.legend(loc="upper left", fontsize=9)
    ax3.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = OUT_PLOTS / f"step2a_clipping_{Path(csv_rel).parent.name}_{Path(csv_rel).stem}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")
    return Q_gross_kWh, Q_usable_kWh, Q_clip_kWh, clip_frac


def main():
    for csv_rel, title in CASES:
        print(title)
        make_plot(csv_rel, title)


if __name__ == "__main__":
    main()
