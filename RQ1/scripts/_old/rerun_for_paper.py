"""Launcher for the paper rerun batch (Tiers 1a, 1b, 2a, 2b).

Runs every command sequentially through run_solar_hp_configs.py so the
kinetics path is identical to the existing audit-pipeline data.
Logs everything to outputs/_rerun_pre_paper_2026-05-11.log.

Tier 1a: Config A recirculation sweep, 3 sites x 7 r values        =  3 calls (vector r)
Tier 1b: A/B/D1 with VPD = 0.05 at 3 sites                          =  9 calls
Tier 2a: E2 TPJ area sweep at 5, 15, 20 m^2 (no VPD)                =  3 calls
Tier 2b: E2 annual VPD threshold sweep at BTN and TPJ, 5 thresholds = 10 calls
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "outputs" / "_rerun_pre_paper_2026-05-11.log"
PY = sys.executable
RUNNER = "scripts/run_solar_hp_configs.py"

LOCATIONS = ["biratnagar", "kathmandu", "taplejung"]


def make_jobs():
    jobs: list[tuple[str, list[str]]] = []

    # ----- Tier 1a: Config A r-sweep, 3 sites, 7 r values -----
    r_values = ["0.0", "0.3", "0.5", "0.7", "0.8", "0.9", "1.0"]
    for loc in LOCATIONS:
        jobs.append((
            f"Tier1a_A_rsweep_{loc}",
            ["--config", "A", "--location", loc, "--recirc-values", *r_values,
             "--max-hours", "48"],
        ))

    # ----- Tier 1b: A/B/D1 with VPD = 0.05 at 3 sites -----
    for cfg in ["A", "B", "D1"]:
        for loc in LOCATIONS:
            args = ["--config", cfg, "--location", loc, "--vpd-threshold", "0.05",
                    "--max-hours", "48"]
            if cfg in ("B",):
                args += ["--solar-area", "10"]
            if cfg in ("D1",):
                args += ["--eps-hrx", "0.70"]
            jobs.append((f"Tier1b_{cfg}_VPD05_{loc}", args))

    # ----- Tier 2a: E2 TPJ area sweep at 5, 15, 20 m^2 -----
    for A_c in ["5", "15", "20"]:
        jobs.append((
            f"Tier2a_E2_TPJ_Ac{A_c}",
            ["--config", "E2", "--location", "taplejung",
             "--solar-area", A_c, "--eps-hrx", "0.70", "--max-hours", "48"],
        ))

    # ----- Tier 2b: E2 annual VPD sweep at BTN, TPJ at 5 thresholds -----
    for loc in ["biratnagar", "taplejung"]:
        for vpd in ["0.02", "0.05", "0.10", "0.15", "0.20"]:
            jobs.append((
                f"Tier2b_E2_{loc}_VPD{vpd}",
                ["--config", "E2", "--location", loc,
                 "--solar-area", "10", "--eps-hrx", "0.70",
                 "--vpd-threshold", vpd, "--max-hours", "48"],
            ))

    return jobs


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    jobs = make_jobs()
    n = len(jobs)
    started = datetime.now()
    with LOG.open("w", encoding="utf-8") as f:
        f.write(f"# Paper rerun batch — started {started.isoformat()}\n")
        f.write(f"# n_jobs = {n}\n\n")

    for i, (tag, args) in enumerate(jobs, 1):
        cmd = [PY, RUNNER, *args]
        t0 = time.time()
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"\n========== [{i}/{n}] {tag} ==========\n")
            f.write("CMD: " + " ".join(cmd) + "\n")
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                  timeout=900)
            elapsed = time.time() - t0
            with LOG.open("a", encoding="utf-8") as f:
                f.write(proc.stdout[-4000:])
                if proc.stderr:
                    f.write("\n[stderr]\n" + proc.stderr[-1500:])
                f.write(f"\n[done in {elapsed:.1f} s, exit={proc.returncode}]\n")
            print(f"[{i}/{n}] {tag}  exit={proc.returncode}  ({elapsed:.1f} s)")
        except subprocess.TimeoutExpired:
            with LOG.open("a", encoding="utf-8") as f:
                f.write("[TIMEOUT > 900 s]\n")
            print(f"[{i}/{n}] {tag}  TIMEOUT")

    print(f"\nAll done. Log: {LOG}")


if __name__ == "__main__":
    main()
