"""Orchestrator: re-run all simulations affected by the 2026-05-04 M1 refit.

Three sweeps + plot regen:
  A. Seasonal: 10 configs x 4 locations x 3 seasons (autumn/winter/spring),
     A_solar=10, VPD=0.05 for D/E.
  B. r-sweep (annual): A,B,C1,C2 x 4 locations x 6 r-values, A_solar=10.
  C. VPD-off D/E (annual): D1..E3 x 4 locations, vpd-threshold=0.
  D. Plot regen: visualize_results.create_all_plots over every CSV touched.

Logs to outputs/_rerun_post_m1_refit.log.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "scripts" / "run_solar_hp_configs.py"
LOG = PROJECT_ROOT / "outputs" / "_rerun_post_m1_refit.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

LOCATIONS = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
SEASONS = {
    "autumn_oct_nov": "autumn_oct_nov",
    "winter_dec_jan": "winter_dec_jan",
    "spring_mar_apr": "spring_mar_apr",
}
ALL_CONFIGS = ["A", "B", "C1", "C2", "D1", "D2", "D3", "E1", "E2", "E3"]
RECIRC_CONFIGS = ["A", "B", "C1", "C2"]
DE_CONFIGS = ["D1", "D2", "D3", "E1", "E2", "E3"]
R_VALUES = ["0.0", "0.3", "0.5", "0.7", "0.9", "1.0"]


def run(args, label):
    cmd = [sys.executable, str(RUNNER), *args]
    msg = f"\n{'=' * 78}\n[{time.strftime('%H:%M:%S')}] {label}\n  CMD: {' '.join(cmd)}\n{'=' * 78}\n"
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg)
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=f, stderr=subprocess.STDOUT)
    return proc.returncode


def block_a_seasonal():
    n = len(LOCATIONS) * len(SEASONS)
    i = 0
    for loc in LOCATIONS:
        for season_tag, season_stem in SEASONS.items():
            i += 1
            wfile = PROJECT_ROOT / "data" / "ambient" / "seasonal" / f"{loc}_{season_stem}.csv"
            if not wfile.exists():
                print(f"  MISSING weather: {wfile}", flush=True)
                continue
            args = [
                "--configs", *ALL_CONFIGS,
                "--locations", loc,
                "--solar-area", "10",
                "--vpd-threshold", "0.05",
                "--weather-file", str(wfile.relative_to(PROJECT_ROOT)),
            ]
            run(args, f"[A {i}/{n}] seasonal {loc}/{season_tag}")


def block_b_rsweep():
    args = [
        "--configs", *RECIRC_CONFIGS,
        "--locations", *LOCATIONS,
        "--solar-area", "10",
        "--recirc-values", *R_VALUES,
    ]
    run(args, "[B] r-sweep annual A,B,C1,C2 x 4 loc x 6 r")


def block_c_vpd_off():
    args = [
        "--configs", *DE_CONFIGS,
        "--locations", *LOCATIONS,
        "--solar-area", "10",
        "--vpd-threshold", "0.0",
    ]
    run(args, "[C] VPD-off D/E annual")


def block_d_plots():
    """Walk every CSV under outputs/config_* and regenerate plots."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from visualize_results import create_all_plots  # noqa: E402

    out_root = PROJECT_ROOT / "outputs"
    plots_root = PROJECT_ROOT / "plots"
    csvs = sorted(out_root.glob("config_*/**/*.csv"))
    n = len(csvs)
    msg = f"\n{'=' * 78}\n[{time.strftime('%H:%M:%S')}] [D] regenerating plots for {n} CSVs\n{'=' * 78}\n"
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg)
    fails = 0
    for k, csv in enumerate(csvs, 1):
        rel = csv.relative_to(out_root)
        out_dir = plots_root / rel.parent / csv.stem
        try:
            create_all_plots(csv, out_dir)
            line = f"  [{k:3d}/{n}] OK  {rel}\n"
        except Exception as exc:
            fails += 1
            line = f"  [{k:3d}/{n}] FAIL {rel}: {exc!r}\n"
        print(line, end="", flush=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    summary = f"\n[D] done: {n - fails}/{n} plot sets succeeded.\n"
    print(summary, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(summary)


def main():
    LOG.write_text(f"Rerun started {time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")
    t0 = time.time()
    block_a_seasonal()
    block_b_rsweep()
    block_c_vpd_off()
    block_d_plots()
    dt = (time.time() - t0) / 60.0
    print(f"\nALL DONE in {dt:.1f} min. Log: {LOG}")


if __name__ == "__main__":
    main()
