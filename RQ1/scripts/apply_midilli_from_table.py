"""Evaluate Midilli curves from a chamber table row."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = SCRIPT_DIR / "src"

# Ensure the rq1 package is importable whether the script is executed from the
# repository root or another working directory.
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rq1 import midilli_table  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table_csv", type=Path, help="Path to phase2c_for_chamber.csv")
    parser.add_argument("row_id", type=str, help="Row identifier to extract")
    parser.add_argument(
        "--total-time-s",
        type=float,
        default=3600.0,
        help="Total time window (s) for evaluation",
    )
    parser.add_argument(
        "--dt-s",
        type=float,
        default=10.0,
        help="Time step (s) for the output grid",
    )
    parser.add_argument(
        "--X0-db",
        type=float,
        default=None,
        help="Optional initial moisture content (dry basis) to compute X_db",
    )
    parser.add_argument(
        "--Xeq-db",
        type=float,
        default=None,
        help="Optional equilibrium moisture content (dry basis) to compute X_db",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("midilli_curve.csv"),
        help="Output CSV path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rows = midilli_table.load_midilli_rows(args.table_csv)
    try:
        params = rows[args.row_id]
    except KeyError as exc:
        raise SystemExit(f"Row id '{args.row_id}' not found in {args.table_csv}") from exc

    t_s = pd.Series(np.arange(0.0, args.total_time_s + args.dt_s, args.dt_s))
    MR = pd.Series(midilli_table.evaluate_piecewise_midilli_MR(t_s.values, params))

    df = pd.DataFrame({
        "time_s": t_s,
        "time_min": t_s / 60.0,
        "MR": MR,
    })

    if args.X0_db is not None and args.Xeq_db is not None:
        df["X_db"] = midilli_table.X_db_from_MR(df["MR"].to_numpy(), args.X0_db, args.Xeq_db)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote Midilli curve for row '{args.row_id}' to {args.output}")


if __name__ == "__main__":
    main()
