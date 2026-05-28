"""Run ALL thesis simulations: every config × location × season × parameter combo.

This is the master batch runner. Each simulation takes ~30-120s.
Total: ~350+ simulations.

Usage:
    python scripts/run_all_thesis_simulations.py
    python scripts/run_all_thesis_simulations.py --dry-run          # preview commands
    python scripts/run_all_thesis_simulations.py --skip-existing     # skip already-done runs
    python scripts/run_all_thesis_simulations.py --only-group D      # run only D-config group
"""

import argparse
import io
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "scripts" / "run_solar_hp_configs.py"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
SEASONAL_DIR = PROJECT_ROOT / "data" / "ambient" / "seasonal"

LOCATIONS = ["kathmandu", "biratnagar", "taplejung", "dhulikhel"]
SEASONS = ["autumn_oct_nov", "winter_dec_jan", "spring_mar_apr", "summer_may_jun"]
SOLAR_AREAS_SWEEP = [2, 4, 6, 8, 10]   # for area sweep
SOLAR_AREA_DEFAULT = 10                  # for non-sweep runs


@dataclass
class SimJob:
    config: str
    location: str
    season: str = ""          # "" = annual (standard TMY)
    r_recirc: float = 0.0
    solar_area: float = 0.0
    vpd_threshold: float = 0.0
    group: str = ""

    @property
    def expected_output(self) -> Path:
        """Predict the output file path the runner would create."""
        base = OUTPUT_ROOT / f"config_{self.config}" / self.location
        if self.season:
            base = base / self.season

        if self.config == "A":
            vpd_tag = "_vpd" if self.vpd_threshold > 0 else ""
            # Note: cond-threshold uses _vpd tag in filename
            return base / f"baseline_r{self.r_recirc:.1f}{vpd_tag}.csv"
        elif self.config in ("D1", "D2", "D3"):
            vpd_tag = f"_vpd{self.vpd_threshold:.2f}" if self.vpd_threshold > 0 else ""
            return base / f"hrx_eps0.70{vpd_tag}.csv"
        elif self.config in ("E1", "E2", "E3"):
            vpd_tag = f"_vpd{self.vpd_threshold:.2f}" if self.vpd_threshold > 0 else ""
            return base / f"Ac_{self.solar_area:.0f}m2_hrx0.70{vpd_tag}.csv"
        else:
            # B1, B2, C1
            vpd_tag = "_vpd" if self.vpd_threshold > 0 else ""
            suffix = f"_r{self.r_recirc:.1f}" if self.r_recirc > 0 else ""
            return base / f"Ac_{self.solar_area:.0f}m2{vpd_tag}{suffix}.csv"

    @property
    def cli_args(self) -> list[str]:
        args = [
            sys.executable, str(RUNNER),
            "--config", self.config,
            "--location", self.location,
        ]
        if self.season:
            weather_file = SEASONAL_DIR / f"{self.location}_{self.season}.csv"
            args += ["--weather-file", str(weather_file)]
        if self.config in ("B1", "B2", "C1", "E1", "E2", "E3"):
            args += ["--solar-area", str(self.solar_area)]
        if self.r_recirc > 0:
            args += ["--recirc-values", str(self.r_recirc)]
        if self.vpd_threshold > 0:
            if self.config in ("D1", "D2", "D3", "E1", "E2", "E3"):
                args += ["--vpd-threshold", str(self.vpd_threshold)]
            else:
                args += ["--cond-threshold", str(self.vpd_threshold)]
        return args

    @property
    def short_desc(self) -> str:
        parts = [f"{self.config}", self.location[:3].upper()]
        if self.season:
            parts.append(self.season.split("_")[0][:3])
        if self.r_recirc > 0:
            parts.append(f"r={self.r_recirc}")
        if self.solar_area > 0:
            parts.append(f"{self.solar_area:.0f}m²")
        if self.vpd_threshold > 0:
            parts.append("VPD")
        return " ".join(parts)


def build_job_list() -> list[SimJob]:
    jobs = []

    # ── GROUP A: Config A (HP-only) ──────────────────────────────
    for loc in LOCATIONS:
        for season in [""] + SEASONS:
            for r in [0.0, 0.9, 1.0]:
                jobs.append(SimJob("A", loc, season, r_recirc=r, group="A"))

    # ── GROUP B: Config B1 + B2 (Solar+HP, r=0 only) ─────────────
    for cfg in ["B1", "B2"]:
        for loc in LOCATIONS:
            for season in [""] + SEASONS:
                jobs.append(SimJob(cfg, loc, season, solar_area=SOLAR_AREA_DEFAULT, group="B"))

    # ── GROUP C: Config C1 (Solar on evap source, r=0 only) ─────
    for cfg in ["C1"]:
        for loc in LOCATIONS:
            for season in [""] + SEASONS:
                jobs.append(SimJob(cfg, loc, season, solar_area=SOLAR_AREA_DEFAULT, group="C"))

    # ── GROUP D: Config D1, D2, D3 (HRX) ────────────────────────
    for cfg in ["D1", "D2", "D3"]:
        for loc in LOCATIONS:
            for season in [""] + SEASONS:
                jobs.append(SimJob(cfg, loc, season, group="D"))

    # ── GROUP E: Config E1, E2, E3 (HRX+Solar) ──────────────────
    for cfg in ["E1", "E2", "E3"]:
        for loc in LOCATIONS:
            for season in [""] + SEASONS:
                jobs.append(SimJob(cfg, loc, season, solar_area=SOLAR_AREA_DEFAULT, group="E"))

    # ── GROUP S: Solar area sweep (E2 only, all locations × seasons) ─
    for loc in LOCATIONS:
        for season in [""] + SEASONS:
            for area in SOLAR_AREAS_SWEEP:
                if area == SOLAR_AREA_DEFAULT:
                    continue  # already covered in GROUP E
                jobs.append(SimJob("E2", loc, season, solar_area=area, group="S"))

    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument("--skip-existing", action="store_true", help="Skip simulations whose output CSV exists")
    parser.add_argument("--only-group", type=str, default="",
                        help="Only run jobs in this group (A, B, C, D, E, S)")
    parser.add_argument("--only-location", type=str, default="",
                        help="Only run jobs for this location")
    parser.add_argument("--only-config", type=str, default="",
                        help="Only run jobs for this config (e.g. E2)")
    args = parser.parse_args()

    jobs = build_job_list()

    # Filters
    if args.only_group:
        jobs = [j for j in jobs if j.group == args.only_group.upper()]
    if args.only_location:
        jobs = [j for j in jobs if j.location == args.only_location.lower()]
    if args.only_config:
        jobs = [j for j in jobs if j.config == args.only_config.upper()]

    # Count existing
    existing = sum(1 for j in jobs if j.expected_output.exists())
    to_run = jobs
    if args.skip_existing:
        to_run = [j for j in jobs if not j.expected_output.exists()]

    print("=" * 70)
    print("THESIS SIMULATION BATCH RUNNER")
    print("=" * 70)
    print(f"Total jobs planned:  {len(jobs)}")
    print(f"Already completed:   {existing}")
    print(f"Jobs to run:         {len(to_run)}")

    # Group summary
    groups = {}
    for j in to_run:
        groups.setdefault(j.group, 0)
        groups[j.group] += 1
    for g, n in sorted(groups.items()):
        print(f"  Group {g}: {n} jobs")

    print("=" * 70)

    if args.dry_run:
        for i, j in enumerate(to_run, 1):
            status = "[EXISTS]" if j.expected_output.exists() else "[NEW]"
            print(f"  {i:3d}. {status} {j.short_desc}")
            print(f"       -> {j.expected_output.relative_to(OUTPUT_ROOT)}")
        return

    # Run
    failed = []
    t_start_all = time.time()

    for i, job in enumerate(to_run, 1):
        print(f"\n{'─' * 70}")
        print(f"[{i}/{len(to_run)}] {job.short_desc}")
        print(f"  Output: {job.expected_output.relative_to(OUTPUT_ROOT)}")
        print(f"{'─' * 70}")

        t0 = time.time()
        try:
            result = subprocess.run(
                job.cli_args,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600,  # 10 min max per simulation
                encoding="utf-8",
                errors="replace",
            )
            elapsed = time.time() - t0

            if result.returncode != 0:
                print(f"  FAILED (exit {result.returncode}, {elapsed:.0f}s)")
                print(f"  stderr: {result.stderr[-500:]}")
                failed.append((job, result.stderr[-200:]))
            else:
                # Extract key metrics from stdout
                lines = result.stdout.strip().split("\n")
                for line in lines[-6:]:
                    if any(k in line for k in ["Water removed", "Time:", "W_comp:", "SEC", "Saved:"]):
                        print(f"  {line.strip()}")
                print(f"  OK ({elapsed:.0f}s)")

        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT (>600s)")
            failed.append((job, "TIMEOUT"))
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append((job, str(e)))

    elapsed_all = time.time() - t_start_all
    print(f"\n{'=' * 70}")
    print(f"BATCH COMPLETE: {len(to_run) - len(failed)}/{len(to_run)} succeeded in {elapsed_all/60:.1f} min")
    if failed:
        print(f"\nFAILED ({len(failed)}):")
        for job, err in failed:
            print(f"  {job.short_desc}: {err[:100]}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
