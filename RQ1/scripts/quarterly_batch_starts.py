"""Build the (site, quarter, batch_idx) -> start_row table for the quarterly K-batch sweep.

Quarters Q1..Q4 are calendar quarters (Q1=Jan+Feb+Mar, ..., Q4=Oct+Nov+Dec).
For each quarter we pick K=6 batch starts at SPACING_DAYS=15 day spacing
(offsets 0,15,30,45,60,75 from the first row of the quarter). The actual
start row is the first row at-or-after the target offset whose NPT hour
is >= 6 (06:45 NPT in our PVGIS files; row 0 sits at 05:45 NPT and is
pre-dawn, so it is intentionally skipped).

Run:
    python scripts/quarterly_batch_starts.py
    python scripts/quarterly_batch_starts.py --sites kathmandu jomsom

Output: outputs/quarterly/batch_starts.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMBIENT_DIR = PROJECT_ROOT / "data" / "ambient"
OUT_DIR = PROJECT_ROOT / "outputs" / "quarterly"

QUARTERS: dict[str, list[int]] = {
    "Q1": [1, 2, 3],
    "Q2": [4, 5, 6],
    "Q3": [7, 8, 9],
    "Q4": [10, 11, 12],
}

DEFAULT_SITES: list[str] = ["biratnagar", "kathmandu", "jomsom", "namche"]
K_BATCHES: int = 6
SPACING_DAYS: int = 15
SPACING_HOURS: int = SPACING_DAYS * 24
MIN_HOUR_NPT: int = 6  # skip 05:45 NPT rows (pre-dawn)


def site_csv(site: str) -> Path:
    poa = AMBIENT_DIR / f"{site}_pvgis_standard_poa45.csv"
    if poa.exists():
        return poa
    return AMBIENT_DIR / f"{site}_pvgis_standard.csv"


def find_batch_starts_for_site(site: str) -> list[dict]:
    csv_path = site_csv(site)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing standard CSV: {csv_path}")

    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["month"] = df["datetime"].dt.month
    df["hour"] = df["datetime"].dt.hour
    df = df.reset_index(drop=True)

    records: list[dict] = []
    for q_name, months in QUARTERS.items():
        q_mask = df["month"].isin(months)
        q_rows = df[q_mask]
        if q_rows.empty:
            raise ValueError(f"{site}: no rows for quarter {q_name}")
        q_first_idx = int(q_rows.index.min())

        for k in range(K_BATCHES):
            base_idx = q_first_idx + k * SPACING_HOURS
            if base_idx >= len(df):
                raise ValueError(
                    f"{site} {q_name} batch{k}: base index {base_idx} out of range"
                )

            # Walk forward until we hit a row in the same quarter with NPT hour >= 6.
            chosen_idx = None
            for cur in range(base_idx, len(df)):
                if df.at[cur, "month"] not in months:
                    break  # quarter exhausted
                if int(df.at[cur, "hour"]) >= MIN_HOUR_NPT:
                    chosen_idx = cur
                    break
            if chosen_idx is None:
                raise ValueError(
                    f"{site} {q_name} batch{k}: no row >= {MIN_HOUR_NPT}:00 NPT "
                    f"found from idx {base_idx} within quarter"
                )

            row = df.iloc[chosen_idx]
            records.append({
                "site": site,
                "quarter": q_name,
                "batch_idx": k,
                "target_offset_h": k * SPACING_HOURS,
                "start_row_index": int(chosen_idx),
                "start_datetime_NPT": row["datetime"].isoformat(),
                "start_T_C": float(row["T_amb_C"]),
                "start_RH_pct": float(row["RH_amb_pct"]),
                "start_solar_Wm2": float(row["POA_Wm2"] if "POA_Wm2" in row else row["GHI_Wm2"]),
            })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites", nargs="+", default=DEFAULT_SITES,
                        help="Sites to compute (default: all 4)")
    parser.add_argument("--output", type=Path,
                        default=OUT_DIR / "batch_starts.csv",
                        help="Output CSV path")
    args = parser.parse_args()

    all_records: list[dict] = []
    for site in args.sites:
        site_records = find_batch_starts_for_site(site)
        all_records.extend(site_records)
        n = sum(1 for r in site_records)
        print(f"  {site:12s}: {n:>2d} batch starts ({K_BATCHES}/quarter)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_out = pd.DataFrame(all_records)
    df_out.to_csv(args.output, index=False)
    print(f"\nSaved: {args.output}  ({len(df_out)} rows)")

    # Sanity preview
    print("\nFirst 8 batch starts:")
    print(df_out.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
