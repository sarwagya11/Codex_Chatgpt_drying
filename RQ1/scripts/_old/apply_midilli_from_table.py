# apply_midilli_from_table.py

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = SCRIPT_DIR / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rq1 import midilli_table  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate MR(t) and X_db(t) from a single Phase-2C Midilli row."
    )

    parser.add_argument(
        "--table-csv",
        type=Path,
        required=True,
        help="Path to phase2c_for_chamber.csv.",
    )
    parser.add_argument(
        "--row-id",
        type=int,
        required=True,
        help="0-based row index over sorted Midilli table ids.",
    )
    parser.add_argument(
        "--total-time-s",
        type=float,
        default=3600.0,
        help="Total simulation time in seconds (default: 3600).",
    )
    parser.add_argument(
        "--dt-s",
        type=float,
        default=10.0,
        help="Time step in seconds (default: 10).",
    )
    parser.add_argument(
        "--X0-db",
        type=float,
        required=True,
        help="Initial moisture content (dry basis).",
    )
    parser.add_argument(
        "--Xeq-db",
        type=float,
        required=True,
        help="Equilibrium moisture content (dry basis).",
    )
    parser.add_argument(
        "--mr-floor",
        type=float,
        default=0.0,
        help="Lower bound for MR(t); e.g. 0.03.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output CSV path.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 1) Load the full Midilli table
    table = midilli_table.load_midilli_rows(args.table_csv)

    # 2) Pick a row by integer index (0-based) over sorted ids
    row_ids = sorted(table.keys())
    try:
        row_key = row_ids[args.row_id]
    except IndexError as exc:
        raise SystemExit(
            f"row-id {args.row_id} out of range; "
            f"valid range is 0..{len(row_ids) - 1}"
        ) from exc

    row = table[row_key]
    print(f"USING_ROW_ID={args.row_id}, DATASET_ID={row_key}")

    # 3) Build time grid in seconds
    time_s = np.arange(0.0, args.total_time_s + args.dt_s, args.dt_s)

    # 4) Evaluate MR(t) and X_db(t)
    MR_midilli = midilli_table.evaluate_piecewise_midilli_MR(
        time_s, row, mr_floor=args.mr_floor
    )
    X_db_midilli = midilli_table.X_db_from_MR(
        MR_midilli, X0_db=args.X0_db, X_eq_db=args.Xeq_db
    )

    # 5) Write output CSV
    out_df = pd.DataFrame(
        {
            "time_s": time_s,
            "MR_midilli": MR_midilli,
            "X_db_midilli": X_db_midilli,
        }
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False)

    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
