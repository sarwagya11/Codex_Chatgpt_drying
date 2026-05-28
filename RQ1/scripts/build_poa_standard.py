"""Attach POA_Wm2 from the PVGIS seriescalc pull onto the legacy TMY standard CSV.

Takes the existing data/ambient/{site}_pvgis_standard.csv (which has T_amb_C,
RH_amb_pct, GHI_Wm2, wind_speed_ms from a PVGIS TMY pull) and overlays
POA = Gb(i) + Gd(i) + Gr(i) from data/ambient/poa45/{site}_pvgis_poa45_raw.csv
(45 deg south tilt, PVGIS-ERA5 seriescalc 2005-2023).

Merge key: (year, month, day, hour) in UTC. PVGIS uses different minute
conventions between TMY (HH:00) and seriescalc (HH:30) so minutes are
ignored. TMY datetimes in the standard CSV are NPT (UTC+5:45) per
Process_pvgis_data.py:32, so we shift back to UTC before matching.

Output: data/ambient/{site}_pvgis_standard_poa45.csv
        Same schema as the legacy file plus a POA_Wm2 column.

Run:
    python scripts/build_poa_standard.py
    python scripts/build_poa_standard.py --sites kathmandu
"""

from __future__ import annotations

import argparse
import io
from datetime import timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMBIENT_DIR = PROJECT_ROOT / "data" / "ambient"
POA_DIR = AMBIENT_DIR / "poa45"

NPT_OFFSET = timedelta(hours=5, minutes=45)

DEFAULT_SITES = ["biratnagar", "kathmandu", "jomsom", "namche"]


def load_seriescalc(path: Path) -> pd.DataFrame:
    """Load PVGIS seriescalc CSV. Strips header/footer metadata lines."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().lower().startswith("time,"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"Could not find header line in {path}")

    import re
    data_lines = [lines[header_idx]]
    data_re = re.compile(r"^\d{8}:\d{4},")
    for line in lines[header_idx + 1:]:
        if data_re.match(line):
            data_lines.append(line)
        elif line.strip().startswith("PVGIS"):
            break

    df = pd.read_csv(io.StringIO("\n".join(data_lines)))
    df["time"] = df["time"].astype(str).str.strip()
    valid = df["time"].str.match(r"^\d{8}:\d{4}$", na=False)
    df = df.loc[valid].copy()

    df["year"] = df["time"].str[0:4].astype(int)
    df["month"] = df["time"].str[4:6].astype(int)
    df["day"] = df["time"].str[6:8].astype(int)
    df["hour_utc"] = df["time"].str[9:11].astype(int)

    for col in ("Gb(i)", "Gd(i)", "Gr(i)"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["POA_Wm2"] = df["Gb(i)"].fillna(0) + df["Gd(i)"].fillna(0) + df["Gr(i)"].fillna(0)
    return df


def merge_one(site: str, out_dir: Path) -> Path:
    tmy_path = AMBIENT_DIR / f"{site}_pvgis_standard.csv"
    poa_path = POA_DIR / f"{site}_pvgis_poa45_raw.csv"
    if not tmy_path.exists():
        raise FileNotFoundError(tmy_path)
    if not poa_path.exists():
        raise FileNotFoundError(poa_path)

    tmy = pd.read_csv(tmy_path)
    tmy["datetime"] = pd.to_datetime(tmy["datetime"])
    tmy_utc = tmy["datetime"] - NPT_OFFSET
    tmy["_year"] = tmy_utc.dt.year
    tmy["_month"] = tmy_utc.dt.month
    tmy["_day"] = tmy_utc.dt.day
    tmy["_hour"] = tmy_utc.dt.hour

    poa = load_seriescalc(poa_path)
    poa_keyed = poa[["year", "month", "day", "hour_utc", "POA_Wm2"]].rename(
        columns={"year": "_year", "month": "_month", "day": "_day", "hour_utc": "_hour"}
    )

    merged = tmy.merge(poa_keyed, on=["_year", "_month", "_day", "_hour"], how="left")
    n_miss = int(merged["POA_Wm2"].isna().sum())
    if n_miss:
        sample = merged.loc[merged["POA_Wm2"].isna(),
                            ["_year", "_month", "_day", "_hour"]].head(5)
        raise RuntimeError(
            f"{site}: {n_miss} TMY rows have no POA match. Sample:\n{sample}"
        )

    merged = merged.drop(columns=["_year", "_month", "_day", "_hour"])

    cols = list(merged.columns)
    if "GHI_Wm2" in cols and "POA_Wm2" in cols:
        ghi_idx = cols.index("GHI_Wm2")
        cols.insert(ghi_idx + 1, cols.pop(cols.index("POA_Wm2")))
        merged = merged[cols]

    out_path = out_dir / f"{site}_pvgis_standard_poa45.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)

    ghi_sum = float(merged["GHI_Wm2"].sum()) / 1000.0
    poa_sum = float(merged["POA_Wm2"].sum()) / 1000.0
    poa_over_ghi = poa_sum / ghi_sum if ghi_sum > 0 else float("nan")
    print(f"  {site:12s}: rows={len(merged):>5d}  "
          f"sum GHI={ghi_sum:>7.1f} kWh/m2.yr  "
          f"sum POA45={poa_sum:>7.1f} kWh/m2.yr  "
          f"POA/GHI={poa_over_ghi:.3f}  -> {out_path.name}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sites", nargs="+", default=DEFAULT_SITES)
    parser.add_argument("--output-dir", type=Path, default=AMBIENT_DIR)
    args = parser.parse_args()

    print(f"Building POA-augmented standard CSVs (tilt=45 deg, az=0 deg, PVGIS-ERA5)")
    print(f"Output dir: {args.output_dir}\n")
    for site in args.sites:
        merge_one(site, args.output_dir)


if __name__ == "__main__":
    main()
