"""Parallel batch runner for the Config E completion matrix.

Reads scripts/_run_plan_config_E.csv (produced by plan_config_E_matrix.py) and
dispatches subprocess calls to run_solar_hp_configs.py with N parallel workers.

Each row: config,site,period,area_m2,vpd_threshold
period: "annual" or seasonal tag like "autumn_oct_nov"
"""
import csv
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "scripts" / "_run_plan_config_E.csv"
LOG_DIR = ROOT / "outputs" / "_config_E_batch"
LOG_DIR.mkdir(parents=True, exist_ok=True)

WORKERS = 6


def run_one(row):
    cfg, site, period, area, vpd = row
    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_solar_hp_configs.py"),
        "--config", cfg,
        "--location", site,
        "--solar-area", str(area),
        "--eps-hrx", "0.70",
    ]
    if vpd:
        cmd += ["--vpd-threshold", str(vpd)]
    if period != "annual":
        weather = ROOT / "data" / "ambient" / "seasonal" / f"{site}_{period}.csv"
        cmd += ["--weather-file", str(weather)]

    tag = f"{cfg}_{site}_{period}_A{area}" + (f"_vpd{vpd}" if vpd else "")
    log_path = LOG_DIR / f"{tag}.log"
    t0 = time.time()
    try:
        with open(log_path, "w", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(ROOT))
        dt = time.time() - t0
        return (tag, proc.returncode, dt, str(log_path))
    except Exception as e:
        return (tag, -1, time.time() - t0, f"EXCEPTION: {e}")


def main():
    rows = []
    with open(PLAN, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((
                r["config"], r["site"], r["period"], r["area_m2"],
                r["vpd_threshold"] if r["vpd_threshold"] else "",
            ))
    total = len(rows)
    print(f"[BATCH] {total} sims, {WORKERS} workers", flush=True)

    failures = []
    done = 0
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_one, r): r for r in rows}
        for fut in as_completed(futs):
            tag, rc, dt, info = fut.result()
            done += 1
            elapsed = time.time() - t0
            eta = elapsed / done * (total - done) if done else 0
            status = "OK " if rc == 0 else f"FAIL({rc})"
            print(f"[{done}/{total}] {status} {tag} ({dt:.1f}s) elapsed={elapsed/60:.1f}m eta={eta/60:.1f}m", flush=True)
            if rc != 0:
                failures.append((tag, rc, info))

    print(f"\n[BATCH] done in {(time.time()-t0)/60:.1f} min. failures: {len(failures)}", flush=True)
    if failures:
        print("Failed tags:")
        for tag, rc, info in failures:
            print(f"  {tag} (rc={rc}) -> {info}")


if __name__ == "__main__":
    main()
