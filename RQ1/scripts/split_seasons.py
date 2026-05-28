"""Split PVGIS TMY standard CSV files into seasonal subsets.

Each season is written as a standalone CSV with time_index re-starting from 0,
ready to be used directly by the simulation runner.

Seasons (Nepal apple drying context):
  - post_harvest : Oct + Nov  (apple harvest, primary drying window)
  - winter       : Dec + Jan  (cold stress test)
  - spring       : Mar + Apr  (warm, dry, high solar — comparison)

Usage:
    python scripts/split_seasons.py
    python scripts/split_seasons.py --locations kathmandu biratnagar taplejung
    python scripts/split_seasons.py --locations kathmandu --seasons post_harvest winter
"""

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMBIENT_DIR = PROJECT_ROOT / "data" / "ambient"

# ---------------------------------------------------------------------------
# Season definitions: dict of {season_name: [list of months]}
# Months are 1-indexed (Jan=1, Dec=12).
# ---------------------------------------------------------------------------
SEASONS = {
    "autumn_oct_nov": [10, 11],   # Sharad — apple harvest & primary drying window
    "winter_dec_jan": [12, 1],    # Hemanta — cold, dry, low solar
    "spring_mar_apr": [3, 4],     # Basanta — warm, low RH, high solar
    "summer_may_jun": [5, 6],     # Grishma — hot, rising humidity, high solar
}

# Location → standard CSV filename
LOCATIONS = {
    "kathmandu":  "kathmandu_pvgis_standard.csv",
    "biratnagar": "biratnagar_pvgis_standard.csv",
    "taplejung":  "taplejung_pvgis_standard.csv",
    "dhulikhel":  "dhulikhel_pvgis_standard.csv",
}


def split_one(location: str, season_name: str, months: list[int]) -> Path:
    """Extract months from a TMY file and write a seasonal CSV.

    The TMY file contains 8760 rows (Jan 1 00:00 → Dec 31 23:00).
    Each month's rows are identified by the datetime column.

    For seasons that wrap around the year boundary (e.g. Dec+Jan),
    December rows come first, then January rows — preserving the
    natural chronological order for a drying batch that starts in
    December and runs into January.

    The output CSV has:
      - time_index re-numbered from 0 (required by the simulator)
      - All other columns preserved exactly
      - GHI_Wm2 column added as alias of GHI_Wm2 if needed

    Returns the output path.
    """
    csv_in = AMBIENT_DIR / LOCATIONS[location]
    if not csv_in.exists():
        raise FileNotFoundError(f"Missing: {csv_in}")

    df = pd.read_csv(csv_in)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["_month"] = df["datetime"].dt.month

    # Collect rows month-by-month in the order specified
    parts = []
    for m in months:
        chunk = df[df["_month"] == m].copy()
        if chunk.empty:
            raise ValueError(f"{location}: no data for month {m}")
        parts.append(chunk)

    df_season = pd.concat(parts, ignore_index=True)
    df_season.drop(columns=["_month"], inplace=True)

    # Re-index time_index from 0 (simulator reads this column)
    df_season["time_index"] = range(len(df_season))

    # Write output
    out_dir = AMBIENT_DIR / "seasonal"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{location}_{season_name}.csv"
    df_season.to_csv(out_path, index=False)

    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--locations", nargs="+",
                        default=list(LOCATIONS.keys()),
                        help="Locations to process (default: all)")
    parser.add_argument("--seasons", nargs="+",
                        default=list(SEASONS.keys()),
                        help="Seasons to extract (default: all)")
    args = parser.parse_args()

    print("=" * 70)
    print("SEASONAL WEATHER FILE SPLITTER")
    print("=" * 70)

    for loc in args.locations:
        if loc not in LOCATIONS:
            print(f"[SKIP] Unknown location: {loc}")
            continue

        csv_in = AMBIENT_DIR / LOCATIONS[loc]
        if not csv_in.exists():
            print(f"[SKIP] {loc}: file not found ({csv_in.name})")
            continue

        # Print location summary
        df_full = pd.read_csv(csv_in)
        df_full["datetime"] = pd.to_datetime(df_full["datetime"])
        print(f"\n--- {loc.upper()} ({len(df_full)} hours) ---")

        for season_name in args.seasons:
            if season_name not in SEASONS:
                print(f"  [SKIP] Unknown season: {season_name}")
                continue

            months = SEASONS[season_name]
            out_path = split_one(loc, season_name, months)

            # Verify output
            df_out = pd.read_csv(out_path)
            df_out["datetime"] = pd.to_datetime(df_out["datetime"])
            n = len(df_out)
            t_mean = df_out["T_amb_C"].mean()
            rh_mean = df_out["RH_amb_pct"].mean()
            ghi_mean = df_out["GHI_Wm2"].mean()
            dt_start = df_out["datetime"].iloc[0]
            dt_end = df_out["datetime"].iloc[-1]

            month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May",
                           6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct",
                           11: "Nov", 12: "Dec"}
            month_str = "+".join(month_names[m] for m in months)

            print(f"  {season_name:15s} ({month_str:>7s}): "
                  f"{n:>5d}h  T={t_mean:5.1f}C  RH={rh_mean:4.1f}%  "
                  f"GHI={ghi_mean:5.1f}  -> {out_path.name}")

    print(f"\n{'=' * 70}")
    print(f"Output directory: {AMBIENT_DIR / 'seasonal'}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
