"""Extract key metrics from ALL simulation CSVs into one master summary table.

Walks outputs/config_*/ recursively, reads the final row of each CSV,
and produces:
  - outputs/master_summary.csv  (flat table, one row per simulation)
  - stdout: formatted summary tables

Usage:
    python scripts/make_master_summary.py
    python scripts/make_master_summary.py --format latex   # LaTeX table output
"""

import argparse
import io
import re
import sys
from pathlib import Path

import pandas as pd

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"

SEASONS_ORDER = ["annual", "autumn_oct_nov", "winter_dec_jan", "spring_mar_apr"]
CONFIG_ORDER = ["A", "B", "C1", "C2", "D1", "D2", "D3", "E1", "E2", "E3"]
LOC_ORDER = ["kathmandu", "biratnagar", "taplejung"]


def parse_output_path(csv_path: Path) -> dict:
    """Extract metadata from the output file path and filename."""
    rel = csv_path.relative_to(OUTPUT_ROOT)
    parts = list(rel.parts)

    # parts[0] = "config_X", parts[1] = location, parts[2] = season or filename
    config = parts[0].replace("config_", "")
    location = parts[1]

    if len(parts) == 4:
        season = parts[2]
        fname = parts[3]
    else:
        season = "annual"
        fname = parts[2]

    stem = Path(fname).stem

    # Parse r value
    r_match = re.search(r"_r(\d+\.\d+)", stem)
    r_val = float(r_match.group(1)) if r_match else 0.0

    # Parse solar area
    ac_match = re.search(r"Ac_(\d+)m2", stem)
    solar_area = float(ac_match.group(1)) if ac_match else 0.0

    # Parse VPD
    vpd = "vpd" in stem.lower()

    return {
        "config": config,
        "location": location,
        "season": season,
        "r_recirc": r_val,
        "solar_area_m2": solar_area,
        "vpd_bypass": vpd,
        "filename": fname,
    }


def extract_metrics(csv_path: Path) -> dict:
    """Read a simulation CSV and extract key metrics from the final row."""
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return {"error": str(e)}

    if df.empty:
        return {"error": "empty CSV"}

    final = df.iloc[-1]

    # Check if simulation completed (MR < 0.05)
    mr_final = final.get("MR_global", final.get("MR_avg", final.get("MR_tray_avg", 1.0)))
    completed = mr_final < 0.10

    # Extract metrics
    time_h = final.get("time_h", 0)
    W_comp = final.get("W_comp_cum_kWh", 0)
    W_fan = final.get("W_fan_cum_kWh", 0)
    W_elec = final.get("W_elec_cum_kWh", 0) or 0
    Q_solar = final.get("Q_solar_cum_kWh", 0)
    m_w = final.get("m_w_cum_kg", 0)

    # SEC = (W_comp + W_elec + W_fan) / m_w
    SEC = (W_comp + W_elec + W_fan) / m_w if m_w > 0.1 else float("nan")

    # Solar fraction
    Q_total = W_comp + W_fan + Q_solar
    solar_frac = Q_solar / Q_total if Q_total > 0 else 0.0

    # Mean COP (if available)
    cop_col = [c for c in df.columns if "COP" in c and "cum" not in c.lower()]
    if cop_col:
        cop_series = df[cop_col[0]].replace(0, float("nan"))
        cop_mean = cop_series.mean()
    else:
        cop_mean = float("nan")

    # Q_solar_usable (if available)
    Q_solar_usable = final.get("Q_solar_usable_cum_kWh", float("nan"))

    # Q_cond (total HP thermal delivered) and Q_HRX (sensible recovery) — best effort
    Q_cond = final.get("Q_cond_cum_kWh", float("nan"))
    Q_HRX = final.get("Q_HRX_cum_kWh", float("nan"))

    # SEC_thermal = total thermal input to the drying air / water removed
    #   Q_cond covers the HP contribution; Q_solar_usable counts what the collector
    #   actually delivered; Q_HRX counts sensible preheat recovered from exhaust.
    try:
        q_terms = [x for x in (Q_cond, Q_solar_usable if Q_solar_usable == Q_solar_usable else Q_solar, Q_HRX) if x == x]
        SEC_thermal = sum(q_terms) / m_w if m_w > 0.1 and q_terms else float("nan")
    except Exception:
        SEC_thermal = float("nan")

    # SMER (electric-basis): water removed per kWh of shaft + fan input
    SMER = m_w / (W_comp + W_fan) if (W_comp + W_fan) > 0 else float("nan")

    return {
        "completed": completed,
        "MR_final": mr_final,
        "time_h": time_h,
        "SEC_kWh_per_kg": SEC,
        "SEC_thermal_kWh_per_kg": SEC_thermal,
        "SMER_kg_per_kWh": SMER,
        "W_comp_kWh": W_comp,
        "W_fan_kWh": W_fan,
        "Q_cond_kWh": Q_cond,
        "Q_solar_kWh": Q_solar,
        "Q_solar_usable_kWh": Q_solar_usable,
        "Q_HRX_kWh": Q_HRX,
        "m_water_kg": m_w,
        "solar_fraction": solar_frac,
        "COP_mean": cop_mean,
    }


def build_master_table() -> pd.DataFrame:
    """Scan all output CSVs and build the master summary DataFrame."""
    rows = []

    for csv_path in sorted(OUTPUT_ROOT.rglob("*.csv")):
        # Skip summary/comparison files at the top level
        if csv_path.parent == OUTPUT_ROOT:
            continue
        # Must be under a config_* directory
        rel = csv_path.relative_to(OUTPUT_ROOT)
        if not rel.parts[0].startswith("config_"):
            continue

        meta = parse_output_path(csv_path)
        metrics = extract_metrics(csv_path)

        row = {**meta, **metrics}
        rows.append(row)

    df = pd.DataFrame(rows)

    # Sort nicely
    if not df.empty:
        df["_cfg_order"] = df["config"].map({c: i for i, c in enumerate(CONFIG_ORDER)}).fillna(99)
        df["_loc_order"] = df["location"].map({l: i for i, l in enumerate(LOC_ORDER)}).fillna(99)
        df["_season_order"] = df["season"].map({s: i for i, s in enumerate(SEASONS_ORDER)}).fillna(99)
        df = df.sort_values(["_cfg_order", "_loc_order", "_season_order", "r_recirc",
                             "solar_area_m2", "vpd_bypass"])
        df = df.drop(columns=["_cfg_order", "_loc_order", "_season_order"])
        df = df.reset_index(drop=True)

    return df


def print_config_ranking(df: pd.DataFrame):
    """Print the 'money table': annual SEC by config x location."""
    print("\n" + "=" * 80)
    print("CONFIG RANKING — Annual TMY, SEC (kWh/kg)")
    print("=" * 80)

    # Filter: annual, r=0 (or r=0.9 for A), solar=10 (or 0), no VPD
    annual = df[df["season"] == "annual"].copy()

    # For Config A, show r=0 as the baseline
    rows = []
    for cfg in CONFIG_ORDER:
        subset = annual[(annual["config"] == cfg) & (~annual["vpd_bypass"])]
        if cfg == "A":
            # Show r=0
            subset = subset[subset["r_recirc"] == 0.0]
        elif cfg in ("B", "C1", "C2", "E1", "E2", "E3"):
            subset = subset[subset["solar_area_m2"] == 10.0]

        row = {"Config": cfg}
        for loc in LOC_ORDER:
            loc_data = subset[subset["location"] == loc]
            if not loc_data.empty:
                sec = loc_data.iloc[0]["SEC_kWh_per_kg"]
                time_h = loc_data.iloc[0]["time_h"]
                row[f"{loc[:3].upper()} SEC"] = f"{sec:.3f}" if pd.notna(sec) else "N/A"
                row[f"{loc[:3].upper()} time"] = f"{time_h:.1f}h"
            else:
                row[f"{loc[:3].upper()} SEC"] = "-"
                row[f"{loc[:3].upper()} time"] = "-"
        rows.append(row)

    ranking = pd.DataFrame(rows)
    print(ranking.to_string(index=False))


def print_seasonal_table(df: pd.DataFrame):
    """Print SEC across seasons for key configs."""
    print("\n" + "=" * 80)
    print("SEASONAL SENSITIVITY — SEC (kWh/kg) by season")
    print("=" * 80)

    key_configs = ["A", "D1", "D2", "E1", "E2", "E3"]

    for loc in LOC_ORDER:
        print(f"\n--- {loc.upper()} ---")
        rows = []
        for cfg in key_configs:
            subset = df[(df["config"] == cfg) & (df["location"] == loc) & (~df["vpd_bypass"])]
            if cfg == "A":
                subset = subset[subset["r_recirc"] == 0.0]
            elif cfg in ("E1", "E2", "E3"):
                subset = subset[subset["solar_area_m2"] == 10.0]

            row = {"Config": cfg}
            for season in SEASONS_ORDER:
                s_data = subset[subset["season"] == season]
                if not s_data.empty:
                    row[season[:6]] = f"{s_data.iloc[0]['SEC_kWh_per_kg']:.3f}"
                else:
                    row[season[:6]] = "-"
            rows.append(row)

        print(pd.DataFrame(rows).to_string(index=False))


def print_vpd_benefit(df: pd.DataFrame):
    """Print VPD bypass benefit for D/E configs."""
    print("\n" + "=" * 80)
    print("VPD BYPASS BENEFIT — SEC reduction (%)")
    print("=" * 80)

    vpd_configs = ["D1", "D2", "E1", "E2"]

    for loc in LOC_ORDER:
        print(f"\n--- {loc.upper()} ---")
        rows = []
        for cfg in vpd_configs:
            subset = df[(df["config"] == cfg) & (df["location"] == loc) & (df["season"] == "annual")]
            if cfg in ("E1", "E2"):
                subset = subset[subset["solar_area_m2"] == 10.0]

            base = subset[~subset["vpd_bypass"]]
            vpd = subset[subset["vpd_bypass"]]

            if not base.empty and not vpd.empty:
                sec_base = base.iloc[0]["SEC_kWh_per_kg"]
                sec_vpd = vpd.iloc[0]["SEC_kWh_per_kg"]
                pct = (sec_base - sec_vpd) / sec_base * 100 if sec_base > 0 else 0
                rows.append({
                    "Config": cfg,
                    "Baseline SEC": f"{sec_base:.3f}",
                    "VPD SEC": f"{sec_vpd:.3f}",
                    "Reduction": f"{pct:.1f}%",
                })
            else:
                rows.append({"Config": cfg, "Baseline SEC": "-", "VPD SEC": "-", "Reduction": "-"})

        if rows:
            print(pd.DataFrame(rows).to_string(index=False))


def print_area_sweep(df: pd.DataFrame):
    """Print E2 area sweep results."""
    print("\n" + "=" * 80)
    print("E2 COLLECTOR AREA SWEEP — SEC (kWh/kg)")
    print("=" * 80)

    e2 = df[(df["config"] == "E2") & (~df["vpd_bypass"])].copy()

    for loc in LOC_ORDER:
        print(f"\n--- {loc.upper()} ---")
        loc_data = e2[e2["location"] == loc]
        if loc_data.empty:
            print("  No data")
            continue

        rows = []
        for area in [2, 4, 6, 8, 10]:
            row = {"Area_m2": area}
            for season in SEASONS_ORDER:
                s_data = loc_data[(loc_data["season"] == season) &
                                  (loc_data["solar_area_m2"] == area)]
                if not s_data.empty:
                    row[season[:6]] = f"{s_data.iloc[0]['SEC_kWh_per_kg']:.3f}"
                else:
                    row[season[:6]] = "-"
            rows.append(row)

        if rows:
            print(pd.DataFrame(rows).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", choices=["text", "latex"], default="text")
    args = parser.parse_args()

    print("Scanning output CSVs...")
    df = build_master_table()

    # Save master CSV
    out_path = OUTPUT_ROOT / "master_summary.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path} ({len(df)} simulations)")

    # Count stats
    completed = df[df.get("completed", True) == True] if "completed" in df.columns else df
    n_configs = df["config"].nunique()
    n_locations = df["location"].nunique()

    print(f"\nSimulations: {len(df)} total, {len(completed)} completed")
    print(f"Configs: {n_configs}, Locations: {n_locations}")

    # Print summary tables
    print_config_ranking(df)
    print_seasonal_table(df)
    print_vpd_benefit(df)
    print_area_sweep(df)

    # Summary of failed/incomplete
    if "completed" in df.columns:
        incomplete = df[df["completed"] == False]
        if not incomplete.empty:
            print(f"\n{'=' * 80}")
            print(f"INCOMPLETE SIMULATIONS ({len(incomplete)}):")
            print("=" * 80)
            for _, row in incomplete.iterrows():
                print(f"  {row['config']} {row['location']} {row['season']} "
                      f"r={row['r_recirc']} A={row['solar_area_m2']} "
                      f"MR={row['MR_final']:.3f}")


if __name__ == "__main__":
    main()
