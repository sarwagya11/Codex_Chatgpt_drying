"""Build screening and production subsets of daily_batch_starts.csv.

Two outputs:
  - screening_batch_starts.csv: 3 days per (site, quarter) at evenly spaced
    batch_idx values (15, 45, 75). 4 sites x 4 quarters x 3 days = 48 rows.
    Used for stage-1 r-screening.

  - production_batch_starts.csv: every Nth batch_idx per (site, quarter),
    where N defaults to 5 (B-prime grain). ~73 days/site x 4 = ~292 rows.
    Used for stage-2 full-year production at fixed r*.

Run:
    python scripts/build_subset_batch_starts.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUARTERLY_DIR = PROJECT_ROOT / "outputs" / "quarterly"
SRC = QUARTERLY_DIR / "daily_batch_starts.csv"
SCREEN_OUT = QUARTERLY_DIR / "screening_batch_starts.csv"
PROD_OUT = QUARTERLY_DIR / "production_batch_starts.csv"

SCREEN_BATCH_IDX_TARGETS = [15, 45, 75]  # mid-month of each month in the quarter
PROD_STEP = 5  # every 5th day = B-prime grain
# Drop the last N batches of Q4 per site (Dec 30/31 lack forward weather window).
DROP_LAST_Q4 = 2


def _drop_last_q4(grp: pd.DataFrame, quarter: str) -> pd.DataFrame:
    if quarter != "Q4":
        return grp
    sorted_grp = grp.sort_values("batch_idx")
    return sorted_grp.iloc[:-DROP_LAST_Q4] if DROP_LAST_Q4 > 0 else sorted_grp


def build_screening(df: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for (site, quarter), grp in df.groupby(["site", "quarter"], sort=False):
        grp = _drop_last_q4(grp, quarter)
        max_idx = grp["batch_idx"].max()
        targets = [i for i in SCREEN_BATCH_IDX_TARGETS if i <= max_idx]
        keep.append(grp[grp["batch_idx"].isin(targets)])
    return pd.concat(keep, ignore_index=True)


def build_production(df: pd.DataFrame, step: int = PROD_STEP) -> pd.DataFrame:
    keep = []
    for (site, quarter), grp in df.groupby(["site", "quarter"], sort=False):
        grp = _drop_last_q4(grp, quarter)
        keep.append(grp[grp["batch_idx"] % step == 0])
    return pd.concat(keep, ignore_index=True)


def main() -> None:
    df = pd.read_csv(SRC)
    print(f"[in ] {SRC.name}: {len(df)} rows")

    screen = build_screening(df)
    screen.to_csv(SCREEN_OUT, index=False)
    print(f"[out] {SCREEN_OUT.name}: {len(screen)} rows")
    print(screen.groupby(["site", "quarter"]).size().to_string())

    prod = build_production(df)
    prod.to_csv(PROD_OUT, index=False)
    print(f"\n[out] {PROD_OUT.name}: {len(prod)} rows (step={PROD_STEP})")
    print(prod.groupby(["site", "quarter"]).size().to_string())


if __name__ == "__main__":
    main()
