"""Run missing Config A and B simulations:
  - Config A: r=0.9, 1.0 with --cond-threshold 0.05 (VPD bypass) x 3 locs x 4 seasons
  - Config B: r=0.9, 1.0 x 3 locs x 4 seasons (baseline + VPD)

r=0 has no exhaust to bypass, so VPD doesn't apply.
"""

import io
import subprocess
import sys
import time
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = str(PROJECT_ROOT / "scripts" / "run_solar_hp_configs.py")
SEASONAL_DIR = PROJECT_ROOT / "data" / "ambient" / "seasonal"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"

LOCATIONS = ["kathmandu", "biratnagar", "taplejung"]
SEASONS = ["", "autumn_oct_nov", "winter_dec_jan", "spring_mar_apr"]  # "" = annual


def expected_path(config, loc, season, r, vpd, area=0):
    base = OUTPUT_ROOT / f"config_{config}" / loc
    if season:
        base = base / season
    vpd_tag = "_vpd" if vpd else ""
    if config == "A":
        return base / f"baseline_r{r:.1f}{vpd_tag}.csv"
    else:
        return base / f"Ac_{area:.0f}m2{vpd_tag}_r{r:.1f}.csv"


def build_cmd(config, loc, season, r, vpd, area=10):
    cmd = [sys.executable, RUNNER, "--config", config, "--location", loc]
    if season:
        wf = SEASONAL_DIR / f"{loc}_{season}.csv"
        cmd += ["--weather-file", str(wf)]
    if area > 0 and config != "A":
        cmd += ["--solar-area", str(area)]
    cmd += ["--recirc-values", str(r)]
    if vpd:
        cmd += ["--cond-threshold", "0.05"]
    return cmd


def main():
    jobs = []

    # Config A: r=0.9, 1.0 with VPD
    for loc in LOCATIONS:
        for season in SEASONS:
            for r in [0.9, 1.0]:
                jobs.append(("A", loc, season, r, True, 0))

    # Config B: r=0.9, 1.0 baseline + VPD, all seasons
    for loc in LOCATIONS:
        for season in SEASONS:
            for r in [0.9, 1.0]:
                jobs.append(("B", loc, season, r, False, 10))
                jobs.append(("B", loc, season, r, True, 10))

    # Filter out existing
    to_run = []
    for config, loc, season, r, vpd, area in jobs:
        path = expected_path(config, loc, season, r, vpd, area)
        if not path.exists():
            to_run.append((config, loc, season, r, vpd, area))

    print(f"Total planned: {len(jobs)}, Already exist: {len(jobs)-len(to_run)}, To run: {len(to_run)}")

    failed = []
    t0_all = time.time()

    for i, (config, loc, season, r, vpd, area) in enumerate(to_run, 1):
        tag = f"{config} {loc[:3].upper()} {season[:3] if season else 'ann'} r={r}"
        if vpd:
            tag += " VPD"
        print(f"\n[{i}/{len(to_run)}] {tag}")

        cmd = build_cmd(config, loc, season, r, vpd, area)
        t0 = time.time()
        try:
            result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True,
                                    text=True, timeout=600, encoding="utf-8", errors="replace")
            elapsed = time.time() - t0
            if result.returncode != 0:
                print(f"  FAILED ({elapsed:.0f}s): {result.stderr[-200:]}")
                failed.append(tag)
            else:
                for line in result.stdout.strip().split("\n")[-4:]:
                    if any(k in line for k in ["Water", "Time:", "W_comp", "Saved"]):
                        print(f"  {line.strip()}")
                print(f"  OK ({elapsed:.0f}s)")
        except subprocess.TimeoutExpired:
            print("  TIMEOUT")
            failed.append(tag)

    elapsed_all = time.time() - t0_all
    print(f"\nDONE: {len(to_run)-len(failed)}/{len(to_run)} in {elapsed_all/60:.1f} min")
    if failed:
        print(f"FAILED: {failed}")


if __name__ == "__main__":
    main()
