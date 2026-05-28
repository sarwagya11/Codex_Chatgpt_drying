"""Walk outputs/config_E{1,2,3}/{site}/[period/]Ac_*.csv, read final row of each,
write outputs/run_summary_E_full.csv with parsed (config, site, period, area, vpd)
and key cumulative energy/SEC fields.
"""
import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CONFIGS = ["E1", "E2", "E3"]
SITES = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
SEASONS = ["autumn_oct_nov", "winter_dec_jan", "spring_mar_apr", "summer_may_jun"]

FNAME_RE = re.compile(r"^Ac_(?P<area>\d+(?:\.\d+)?)m2_hrx(?P<hrx>[\d.]+)(?:_vpd(?P<vpd>[\d.]+))?\.csv$")

FIELDS = [
    "time_h", "SEC_elec_kWh_per_kg",
    "W_comp_cum_kWh", "W_fan_cum_kWh",
    "Q_cond_cum_kWh", "Q_solar_cum_kWh", "Q_solar_usable_cum_kWh",
    "Q_HRX_cum_kWh", "m_w_cum", "T_to_chamber_deficit_C",
    "hp_mode",
]


def parse_one(path: Path, cfg: str, site: str, period: str):
    m = FNAME_RE.match(path.name)
    if not m:
        return None
    area = float(m.group("area"))
    vpd = float(m.group("vpd")) if m.group("vpd") else 0.0
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return {"config": cfg, "site": site, "period": period, "area_m2": area,
                "vpd": vpd, "error": str(e)}
    if len(df) == 0:
        return None
    last = df.iloc[-1]
    row = {"config": cfg, "site": site, "period": period, "area_m2": area,
           "vpd": vpd, "n_rows": len(df)}
    for f in FIELDS:
        row[f] = last.get(f, None)
    # also report mean hp_mode distribution (E3)
    if cfg == "E3" and "hp_mode" in df.columns:
        modes = df["hp_mode"].value_counts(normalize=True)
        row["hp_off_frac"] = modes.get("off", 0.0)
        row["hp_partial_frac"] = modes.get("partial", 0.0)
        row["hp_full_frac"] = modes.get("full", 0.0)
    return row


def main():
    rows = []
    for cfg in CONFIGS:
        for site in SITES:
            site_dir = OUT / f"config_{cfg}" / site
            if not site_dir.exists():
                continue
            # annual files (direct children)
            for p in site_dir.glob("Ac_*.csv"):
                r = parse_one(p, cfg, site, "annual")
                if r:
                    rows.append(r)
            # seasonal files
            for season in SEASONS:
                season_dir = site_dir / season
                if not season_dir.exists():
                    continue
                for p in season_dir.glob("Ac_*.csv"):
                    r = parse_one(p, cfg, site, season)
                    if r:
                        rows.append(r)

    df = pd.DataFrame(rows)
    df.sort_values(["config", "site", "period", "area_m2", "vpd"], inplace=True)
    out_path = OUT / "run_summary_E_full.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")

    # quick summary
    print("\nRows per config:")
    print(df.groupby("config").size())
    print("\nRows per (config, site, period):")
    print(df.groupby(["config", "site", "period"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
