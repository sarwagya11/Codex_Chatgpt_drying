"""Build a (site, quarter, batch_idx) -> start_row table with one batch per day.

This is the densified version of scripts/quarterly_batch_starts.py: instead of
6 batches per quarter at 15-day spacing, we emit one batch per calendar day
(starting at the first row >= 08:00 NPT for that day, which lands on 08:45 NPT
since PVGIS rows are at HH:45). The `quarter` column follows the same Q1..Q4
calendar definition so the consuming sweep script can still group by quarter
for plotting.

Per quarter we get ~90-92 daily batches per site; over 4 sites for one year
we get ~1460 rows. Each row is independent (the sweep launches each as its
own short simulation reading the same PVGIS file).

Output: outputs/quarterly/daily_batch_starts.csv

Run:
    python scripts/daily_batch_starts.py
    python scripts/daily_batch_starts.py --sites kathmandu jomsom
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMBIENT_DIR = PROJECT_ROOT / "data" / "ambient"
OUT_DIR = PROJECT_ROOT / "outputs" / "quarterly"

QUARTER_OF_MONTH: dict[int, str] = {
    1: "Q1", 2: "Q1", 3: "Q1",
    4: "Q2", 5: "Q2", 6: "Q2",
    7: "Q3", 8: "Q3", 9: "Q3",
    10: "Q4", 11: "Q4", 12: "Q4",
}

DEFAULT_SITES: list[str] = ["biratnagar", "kathmandu", "jomsom", "namche"]
MIN_HOUR_NPT: int = 8  # start drying at 08:45 NPT (first hourly slot after 08:00)


def site_csv(site: str) -> Path:
    poa = AMBIENT_DIR / f"{site}_pvgis_standard_poa45.csv"
    if poa.exists():
        return poa
    return AMBIENT_DIR / f"{site}_pvgis_standard.csv"


def find_daily_starts_for_site(site: str) -> list[dict]:
    csv_path = site_csv(site)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing standard CSV: {csv_path}")

    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date
    df["month"] = df["datetime"].dt.month
    df["hour"] = df["datetime"].dt.hour
    df = df.reset_index(drop=True)

    # First post-dawn row per calendar day
    valid = df[df["hour"] >= MIN_HOUR_NPT]
    first_per_day = valid.groupby("date", sort=True).head(1).reset_index()
    first_per_day = first_per_day.rename(columns={"index": "start_row_index"})

    # Quarter-local batch index resets per quarter (so Q1 -> 0..~89, Q2 -> 0..~90, ...)
    records: list[dict] = []
    counters: dict[str, int] = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for _, row in first_per_day.iterrows():
        month = int(row["month"])
        q_name = QUARTER_OF_MONTH[month]
        batch_idx = counters[q_name]
        counters[q_name] += 1
        records.append({
            "site": site,
            "quarter": q_name,
            "batch_idx": batch_idx,
            "target_offset_h": batch_idx * 24,
            "start_row_index": int(row["start_row_index"]),
            "start_datetime_NPT": row["datetime"].isoformat(),
            "start_T_C": float(row["T_amb_C"]),
            "start_RH_pct": float(row["RH_amb_pct"]),
            "start_solar_Wm2": float(row["POA_Wm2"] if "POA_Wm2" in row else row["GHI_Wm2"]),
        })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sites", nargs="+", default=DEFAULT_SITES)
    parser.add_argument("--output", type=Path,
                        default=OUT_DIR / "daily_batch_starts.csv")
    args = parser.parse_args()

    all_records: list[dict] = []
    for site in args.sites:
        site_records = find_daily_starts_for_site(site)
        all_records.extend(site_records)
        per_q = {}
        for r in site_records:
            per_q[r["quarter"]] = per_q.get(r["quarter"], 0) + 1
        breakdown = " ".join(f"{q}={n}" for q, n in sorted(per_q.items()))
        print(f"  {site:12s}: {len(site_records):>3d} daily starts ({breakdown})")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_out = pd.DataFrame(all_records)
    df_out.to_csv(args.output, index=False)
    print(f"\nSaved: {args.output}  ({len(df_out)} rows)")

    print("\nFirst 6 daily starts:")
    print(df_out.head(6).to_string(index=False))


if __name__ == "__main__":
    main()
