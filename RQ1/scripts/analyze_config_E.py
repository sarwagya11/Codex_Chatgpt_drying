"""Produce headline tables from outputs/run_summary_E_full.csv for CONFIG_E_AUDIT.md.

Sections targeted:
 - 4: SEC across area sweep (annual, vpd=off) per site; vpd sweep at A=10 annual per site;
      headline E1/E2/E3 ranking check at A=10 vpd=<configurable> across all sites/seasons.
 - 5: E2 solar clipping (Q_solar_clipped fraction, optimum A per site/period).
 - 9: Verdict-ready summary.
"""
import argparse
import pandas as pd
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--vpd", type=float, default=0.0,
                    help="VPD threshold for headline rank check (default 0.0 = no bypass).")
args = parser.parse_args()
VPD_HEADLINE = args.vpd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "outputs" / "run_summary_E_full.csv")

# Q_solar_clipped frac per row
df["Q_solar_clipped_kWh"] = df["Q_solar_cum_kWh"] - df["Q_solar_usable_cum_kWh"]
df["clip_frac"] = df["Q_solar_clipped_kWh"] / df["Q_solar_cum_kWh"].replace(0, pd.NA)

# ---------- Section 4: area sweep, annual, vpd=off ----------
print("=== AREA SWEEP (annual, vpd=0) — SEC kWh/kg ===")
area_sweep = df[(df["period"] == "annual") & (df["vpd"] == 0.0)]
pivot_area = area_sweep.pivot_table(index=["config", "site"], columns="area_m2",
                                     values="SEC_elec_kWh_per_kg")
print(pivot_area.round(4).to_string())

# ---------- Section 4: VPD sweep at A=10, annual ----------
print("\n=== VPD SWEEP (A=10, annual) — SEC kWh/kg ===")
vpd_sweep = df[(df["period"] == "annual") & (df["area_m2"] == 10) & (df["vpd"] > 0)]
pivot_vpd = vpd_sweep.pivot_table(index=["config", "site"], columns="vpd",
                                   values="SEC_elec_kWh_per_kg")
print(pivot_vpd.round(4).to_string())

# ---------- Headline ranking check at A=10, vpd=VPD_HEADLINE, all sites×seasons ----------
print(f"\n=== HEADLINE RANK CHECK (A=10, vpd={VPD_HEADLINE}) ===")
rank = df[(df["area_m2"] == 10) & (df["vpd"] == VPD_HEADLINE)]
rank_pivot = rank.pivot_table(index=["site", "period"], columns="config",
                              values="SEC_elec_kWh_per_kg")
print(rank_pivot.round(4).to_string())
# find ranks
rank_pivot["winner"] = rank_pivot[["E1", "E2", "E3"]].idxmin(axis=1)
rank_pivot["loser"]  = rank_pivot[["E1", "E2", "E3"]].idxmax(axis=1)
print("\nWinner per (site, period):")
print(rank_pivot["winner"].value_counts())
print("\nLoser per (site, period):")
print(rank_pivot["loser"].value_counts())
# Cases where E2 is NOT the winner:
not_e2 = rank_pivot[rank_pivot["winner"] != "E2"]
print(f"\nCases where E2 is NOT the winner: {len(not_e2)}")
if len(not_e2):
    print(not_e2.to_string())

# ---------- Section 5: E2 solar clipping, optimum A ----------
print("\n=== E2 SOLAR CLIPPING FRACTION (A sweep, vpd=0, annual) ===")
e2_area_ann = df[(df["config"] == "E2") & (df["period"] == "annual") & (df["vpd"] == 0.0)]
clip_pivot = e2_area_ann.pivot_table(index="site", columns="area_m2", values="clip_frac")
print(clip_pivot.round(3).to_string())

print("\n=== E2 OPTIMUM A_solar PER SITE × PERIOD (min SEC, vpd=0) ===")
e2_all = df[(df["config"] == "E2") & (df["vpd"] == 0.0)]
opt = e2_all.loc[e2_all.groupby(["site", "period"])["SEC_elec_kWh_per_kg"].idxmin(),
                 ["site", "period", "area_m2", "SEC_elec_kWh_per_kg"]]
print(opt.to_string(index=False))

# ---------- E3 HP-mode distribution at A=10, vpd=VPD_HEADLINE annual ----------
print(f"\n=== E3 HP-MODE FRACTIONS (A=10, vpd={VPD_HEADLINE}) ===")
e3_modes = df[(df["config"] == "E3") & (df["area_m2"] == 10) & (df["vpd"] == VPD_HEADLINE)]
print(e3_modes[["site", "period", "hp_off_frac", "hp_partial_frac", "hp_full_frac",
                "SEC_elec_kWh_per_kg"]].round(3).to_string(index=False))

# ---------- Save the three pivots ----------
pivot_area.round(4).to_csv(ROOT / "outputs" / "E_area_sweep_annual.csv")
pivot_vpd.round(4).to_csv(ROOT / "outputs" / "E_vpd_sweep_annual_A10.csv")
rank_pivot[["E1", "E2", "E3", "winner", "loser"]].to_csv(
    ROOT / "outputs" / f"E_headline_rank_A10_vpd{VPD_HEADLINE}.csv")
clip_pivot.round(3).to_csv(ROOT / "outputs" / "E2_solar_clip_frac.csv")
opt.to_csv(ROOT / "outputs" / "E2_optimum_A.csv", index=False)
print("\nSaved: E_area_sweep_annual.csv, E_vpd_sweep_annual_A10.csv, "
      "E_headline_rank_A10_vpd0.05.csv, E2_solar_clip_frac.csv, E2_optimum_A.csv")
