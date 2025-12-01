"""Apply a Midilli curve (from Phase-2 table) to a Phase-1 time grid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = SCRIPT_DIR / "src"

# Ensure the rq1 package is importable whether the script is executed from the
# repository root or another working directory.
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rq1 import midilli_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase1-csv", type=Path, required=True, help="Path to Phase-1 simulation CSV")
    parser.add_argument("--table-csv", type=Path, required=True, help="Path to Phase-2 Midilli table CSV")
    parser.add_argument("--row-id", type=int, required=True, help="Row index in the Midilli table to use")
    parser.add_argument("--X0-db", type=float, required=True, help="Initial dry-basis moisture content")
    parser.add_argument("--Xeq-db", type=float, required=True, help="Equilibrium dry-basis moisture content")
    parser.add_argument("--mr-floor", type=float, default=0.0, help="Minimum MR clamp for Midilli curve")
    parser.add_argument(
        "--output", type=Path, required=True, help="Destination CSV path to write augmented Phase-1 results"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    phase1_df = pd.read_csv(args.phase1_csv)
    params = midilli_table.load_midilli_rows(args.table_csv, args.row_id)

    time_min = phase1_df["time_s"].to_numpy(dtype=float) / 60.0
    MR_midilli = params.evaluate_MR(time_min, mr_floor=args.mr_floor)
    X_db_midilli = midilli_table.X_db_from_MR(MR_midilli, X0_db=args.X0_db, X_eq_db=args.Xeq_db)

    phase1_df["MR_midilli"] = MR_midilli
    phase1_df["X_db_midilli"] = X_db_midilli

    args.output.parent.mkdir(parents=True, exist_ok=True)
    phase1_df.to_csv(args.output, index=False)

    print(args.output)


if __name__ == "__main__":
    main()
