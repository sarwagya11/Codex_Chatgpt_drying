"""Parallel runner for the T_set sweep (E2/E3, T=50/55, 4 sites)."""
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from time import time

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "outputs" / "_T_sweep_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

CONFIGS = ["E2", "E3"]
SITES = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
T_VALUES = [50, 55]
AREA = 10.0
MAX_HOURS = 72.0


def run_one(args):
    cfg, site, T, area = args
    tag = f"{cfg}_{site}_T{T}_A{int(area)}"
    log = LOG_DIR / f"{tag}.log"
    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_solar_hp_configs.py"),
        "--config", cfg, "--location", site, "--solar-area", str(area),
        "--T-set", str(T), "--max-hours", str(MAX_HOURS),
    ]
    t0 = time()
    with log.open("w", encoding="utf-8") as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    dt = time() - t0
    return tag, result.returncode, dt


def main():
    plan = [(c, s, T, AREA) for c in CONFIGS for s in SITES for T in T_VALUES]
    print(f"Running {len(plan)} sims on 6 workers...")
    t_start = time()
    with ProcessPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(run_one, p): p for p in plan}
        for fut in as_completed(futures):
            tag, rc, dt = fut.result()
            status = "OK" if rc == 0 else f"FAIL({rc})"
            print(f"  [{status}] {tag}  ({dt/60:.1f} min)")
    print(f"\nTotal wall: {(time() - t_start)/60:.1f} min")


if __name__ == "__main__":
    main()
