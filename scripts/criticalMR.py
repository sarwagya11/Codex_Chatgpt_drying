#!/usr/bin/env python3
# scripts/criticalMR.py

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# add project root so `src/` is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.kinetics.critical_moisture import detect_critical_moisture


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Detect critical moisture (phase split).")
    ap.add_argument("csv", help="CSV with columns: time_min,X_db")
    ap.add_argument("--lowess-frac", type=float, default=0.15)
    ap.add_argument("--lambda-const", type=float, default=5.0)
    ap.add_argument("--acceptance-delta", type=float, default=6.0)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    # coerce to float arrays and drop non-finite
    t = pd.to_numeric(df["time_min"], errors="coerce").to_numpy(dtype=float)
    x = pd.to_numeric(df["X_db"],   errors="coerce").to_numpy(dtype=float)
    m = np.isfinite(t) & np.isfinite(x)
    t, x = t[m], x[m]

    res = detect_critical_moisture(
        t,
        x,
        lowess_frac=args.lowess_frac,
        lambda_const=args.lambda_const,
        acceptance_delta=args.acceptance_delta,
        debug=args.debug,
    )

    if res is None:
        print("NO SPLIT")
        sys.exit(2)

    print(
        f"t_split={res.t_split:.3f} | Xc={res.Xc:.6f} | ΔBIC={res.delta_bic:.2f} | "
        f"left={len(res.left_indices)} | right={len(res.right_indices)}"
    )


if __name__ == "__main__":
    main()
