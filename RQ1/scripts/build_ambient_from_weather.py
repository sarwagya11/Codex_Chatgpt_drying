"""Convert raw weather CSV to standardized ambient format for Phase-1 simulations."""

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to raw weather CSV")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write standardized ambient CSV (e.g., RQ1/data/ambient/...)",
    )
    parser.add_argument("--temp-col", type=str, required=True, help="Column name for ambient temperature [°C]")
    parser.add_argument("--rh-col", type=str, required=True, help="Column name for relative humidity [%]")
    parser.add_argument("--ghi-col", type=str, default=None, help="Optional column name for global horizontal irradiance [W/m^2]")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df_raw = pd.read_csv(args.input)

    for col in [args.temp_col, args.rh_col]:
        if col not in df_raw.columns:
            raise ValueError(f"Input file missing required column: {col}")

    df_out = pd.DataFrame({
        "time_index": range(len(df_raw)),
        "T_amb_C": df_raw[args.temp_col],
        "RH_amb_pct": df_raw[args.rh_col],
    })

    if args.ghi_col:
        if args.ghi_col not in df_raw.columns:
            raise ValueError(f"Input file missing requested GHI column: {args.ghi_col}")
        df_out["G_hor_Wm2"] = df_raw[args.ghi_col]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(args.output, index=False)
    print(f"Wrote standardized ambient CSV to {args.output}")


if __name__ == "__main__":
    main()
