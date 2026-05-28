"""Pick optimal recirculation r* per (config, site) from stage-1 screening.

Reads a sweep_summary CSV produced by run_quarterly_sweep.py and emits
r_star_by_config_site.csv with one row per (config, site).

Decision rule:
  1. For each (config, site, r), compute mean SEC across the screening days.
  2. r* = argmin of mean SEC.
  3. Tie-break (within --tol fraction of the min): prefer the smaller r,
     since lower recirc is more robust to humidity-buildup assumptions.

Run:
    python scripts/pick_r_star.py \
        --summary outputs/quarterly/sweep_summary_stage1.csv \
        --out outputs/quarterly/r_star_by_config_site.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUARTERLY_DIR = PROJECT_ROOT / "outputs" / "quarterly"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--summary", type=Path,
                   default=QUARTERLY_DIR / "sweep_summary_stage1.csv",
                   help="Stage-1 sweep_summary CSV")
    p.add_argument("--out", type=Path,
                   default=QUARTERLY_DIR / "r_star_by_config_site.csv",
                   help="Output CSV path")
    p.add_argument("--tol", type=float, default=0.01,
                   help="Tie-break tolerance: any r within (1+tol)*min is "
                        "treated as a tie, smaller r wins (default 0.01 = 1%%)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.summary.exists():
        raise SystemExit(f"Stage-1 summary not found: {args.summary}")

    df = pd.read_csv(args.summary)
    needed = {"config", "site", "r_recirc", "SEC_elec_kWh_per_kg", "success"}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"Summary CSV missing columns: {missing}")

    df = df[df["success"] == True].copy()  # noqa: E712
    df = df.dropna(subset=["SEC_elec_kWh_per_kg"])

    # Mean SEC across screening days per (config, site, r)
    grouped = (df.groupby(["config", "site", "r_recirc"])["SEC_elec_kWh_per_kg"]
                 .mean()
                 .reset_index())

    rows: list[dict] = []
    for (config, site), sub in grouped.groupby(["config", "site"], sort=False):
        sub = sub.sort_values("r_recirc")
        sec_min = sub["SEC_elec_kWh_per_kg"].min()
        threshold = sec_min * (1.0 + args.tol)
        # Smaller r within tolerance wins
        within = sub[sub["SEC_elec_kWh_per_kg"] <= threshold]
        r_star = float(within["r_recirc"].min())
        sec_at_rstar = float(sub.loc[sub["r_recirc"] == r_star,
                                     "SEC_elec_kWh_per_kg"].iloc[0])
        rows.append(dict(
            config=config,
            site=site,
            r_star=r_star,
            sec_mean_at_rstar=sec_at_rstar,
            sec_mean_min=float(sec_min),
            n_r_values_screened=len(sub),
        ))

    out_df = pd.DataFrame(rows).sort_values(["config", "site"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False)
    print(f"[out] {args.out.name}: {len(out_df)} rows")
    print(out_df.to_string(index=False))


if __name__ == "__main__":
    main()
