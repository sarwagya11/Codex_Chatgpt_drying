"""One-off: regenerate plots for the 30 recently re-run baseline CSVs.

Each plot set lands in RQ1/plots/<config>/<location>/<csv_stem>/ via
visualize_results.create_all_plots.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from visualize_results import create_all_plots  # noqa: E402

OUTPUTS = PROJECT_ROOT / "outputs"
PLOTS = PROJECT_ROOT / "plots"

LOCATIONS = ["biratnagar", "kathmandu", "taplejung"]
TARGETS = [
    ("config_A",  "baseline_r0.0.csv"),
    ("config_B",  "Ac_10m2.csv"),
    ("config_C1", "Ac_10m2.csv"),
    ("config_C2", "Ac_10m2.csv"),
    ("config_D1", "hrx_eps0.70_vpd0.05.csv"),
    ("config_D2", "hrx_eps0.70_vpd0.05.csv"),
    ("config_D3", "hrx_eps0.70_vpd0.05.csv"),
    ("config_E1", "Ac_10m2_hrx0.70_vpd0.05.csv"),
    ("config_E2", "Ac_10m2_hrx0.70_vpd0.05.csv"),
    ("config_E3", "Ac_10m2_hrx0.70_vpd0.05.csv"),
]


def main() -> None:
    pairs = [(cfg, loc, csv) for cfg, csv in TARGETS for loc in LOCATIONS]
    n = len(pairs)
    failures = []
    for i, (cfg, loc, csv_name) in enumerate(pairs, 1):
        csv = OUTPUTS / cfg / loc / csv_name
        if not csv.exists():
            print(f"[{i:2d}/{n}] MISSING: {csv.relative_to(PROJECT_ROOT)}")
            failures.append(str(csv))
            continue
        out_dir = PLOTS / cfg / loc / csv.stem
        print(f"[{i:2d}/{n}] {cfg}/{loc}/{csv_name}")
        try:
            create_all_plots(csv, out_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"   ERROR: {exc!r}")
            failures.append(f"{csv}: {exc!r}")
    print()
    print(f"Done. {n - len(failures)}/{n} succeeded.")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
