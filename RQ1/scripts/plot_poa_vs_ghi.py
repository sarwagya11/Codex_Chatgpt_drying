"""Plot POA45 vs GHI to verify tilt actually changes irradiance pattern.

Shows two panels per site:
  (top)    one clear day in DJF (winter): POA > GHI dramatically (low sun)
  (bottom) one clear day in JJA (summer): POA ~ GHI (high sun)
Annual totals printed in the title for each panel.

Output: outputs/poa_validation/plots/poa_vs_ghi_<site>.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMBIENT_DIR = PROJECT_ROOT / "data" / "ambient"
OUT_DIR = PROJECT_ROOT / "outputs" / "poa_validation" / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITES = ["biratnagar", "kathmandu", "jomsom", "namche"]


def pick_clearest_day(df: pd.DataFrame, months: list[int]) -> pd.DataFrame:
    sub = df[df["datetime"].dt.month.isin(months)].copy()
    sub["date"] = sub["datetime"].dt.date
    daily_ghi = sub.groupby("date")["GHI_Wm2"].sum().sort_values(ascending=False)
    best_date = daily_ghi.index[0]
    return sub[sub["date"] == best_date].copy()


def plot_site(site: str):
    csv = AMBIENT_DIR / f"{site}_pvgis_standard_poa45.csv"
    df = pd.read_csv(csv)
    df["datetime"] = pd.to_datetime(df["datetime"])

    ghi_kwh = df["GHI_Wm2"].sum() / 1000.0
    poa_kwh = df["POA_Wm2"].sum() / 1000.0
    ratio = poa_kwh / ghi_kwh

    winter = pick_clearest_day(df, [12, 1, 2])
    summer = pick_clearest_day(df, [6, 7, 8])

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=False)
    fig.suptitle(
        f"{site.title()} — POA45 vs GHI (annual {ghi_kwh:.0f} vs {poa_kwh:.0f} kWh/m², ratio {ratio:.3f})",
        fontsize=12,
    )

    for ax, day_df, label in [
        (axes[0], winter, "Clearest DJF day"),
        (axes[1], summer, "Clearest JJA day"),
    ]:
        hours = day_df["datetime"].dt.hour + day_df["datetime"].dt.minute / 60.0
        ax.plot(hours, day_df["GHI_Wm2"], "o-", color="tab:orange", label="GHI (horizontal)")
        ax.plot(hours, day_df["POA_Wm2"], "s--", color="tab:blue", label="POA (45° tilt)")
        ax.fill_between(hours, day_df["GHI_Wm2"], day_df["POA_Wm2"],
                        where=day_df["POA_Wm2"] >= day_df["GHI_Wm2"],
                        alpha=0.15, color="tab:blue", label="POA gain")
        date_str = day_df["datetime"].iloc[0].strftime("%Y-%m-%d")
        ax.set_title(f"{label} ({date_str})", fontsize=10)
        ax.set_xlabel("Hour of day (local)")
        ax.set_ylabel("Irradiance [W/m²]")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    out_path = OUT_DIR / f"poa_vs_ghi_{site}.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  saved {out_path}  (annual GHI={ghi_kwh:.0f}, POA={poa_kwh:.0f}, ratio={ratio:.3f})")


def main():
    for site in SITES:
        plot_site(site)


if __name__ == "__main__":
    main()
