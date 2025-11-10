#!/usr/bin/env python3
# scripts/pw_grid_runner.py
import argparse, itertools, json, csv, subprocess, sys, time
from pathlib import Path

# ---- GRID: edit as needed ----
PARAM_GRID = {
    # Candidate density
    "candidate_grid_count":   [120, 160],
    "candidate_min_spacing":  [5, 8],

    # Acceptance pressure
    "min_rel_improvement":    [0.01, 0.04, 0.07],

    # Autotuner guidance
    "expected_splits":        [2, 3],   # informs total_gap_budget internally
}

# ---- BASE FLAGS: keep stable ----
BASE_FLAGS = [
    "--auto-tune", "--expected-splits","2",
    "--max-splits","2","--max-depth","2",
    "--min-points-root","40","--min-points-leaf","16",
    "--lowess-frac-min","0.15","--lowess-frac-max","0.45","--lowess-frac-root","0.30",
    "--min-fraction","0.10","--max-fraction","0.92",
    "--allow-per-segment-model",
    "--midbody-aicc-tolerance","10","--page-fallback-eps","0.0001",
    "--probe-better-child","--probe-better-child-passes","1",
    "--iso-rmse-tol","0.005","--lowess-points","7",
    "--max-iter","10000","--seed","42","--log-level","INFO",
    "--no-reject-nonmonotone"
]

SUMMARY_KEYS = [
    "n_leaves","splits_used","rmse_global","rmse_piecewise",
    "delta_AICc_total","sum_post_join_gap","monotonic_violations"
]

def build_runs(grid):
    keys = list(grid.keys())
    vals = [grid[k] for k in keys]
    for tup in itertools.product(*vals):
        yield {k: v for k, v in zip(keys, tup)}

def tag_from_params(p):
    parts = []
    for k, v in sorted(p.items()):
        vstr = str(v).replace(".", "p")
        parts.append(f"{k[:3]}{vstr}")
    return "_".join(parts)

def judge(m, p):
    try:
        n_leaves = int(m.get("n_leaves") or 1)
        rmse_g   = float(m.get("rmse_global") or 1e9)
        rmse_p   = float(m.get("rmse_piecewise") or rmse_g)
        dAICc    = float(m.get("delta_AICc_total") or 0.0)
        gap_sum  = float(m.get("sum_post_join_gap") or 0.0)
        splits   = int(m.get("splits_used") or 0)
    except Exception:
        return "BAD_METRICS"
    improved = (rmse_p < 0.9*rmse_g) or (dAICc <= -50)
    gap_ok = True
    if splits > 0 and "max_allowed_gap" in p:
        gap_ok = gap_sum <= (1.25 * p["max_allowed_gap"] * max(1, splits))
    if n_leaves >= 2 and improved and gap_ok: return "GOOD"
    if n_leaves >= 2 and improved:            return "OK_GAPS"
    if n_leaves >= 2:                          return "SPLITS_NO_GAIN"
    return "NO_SPLITS"

def run_once(cli, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "run.log"
    proc = subprocess.run(cli, capture_output=True, text=True)
    log_path.write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr)

    summary_path = outdir / "tree_summary.json"
    if not summary_path.exists(): return {}, "NO_SUMMARY"
    try:
        summary = json.loads(summary_path.read_text())
    except Exception:
        return {}, "BAD_JSON"

    metrics = {k: summary.get(k, None) for k in SUMMARY_KEYS}
    if metrics.get("rmse_global") is None:
        metrics["rmse_global"] = summary.get("rmse_unsplit") or summary.get("rmse_onepiece")
    if metrics.get("rmse_piecewise") is None:
        metrics["rmse_piecewise"] = summary.get("rmse_pw") or summary.get("rmse")
    return metrics, "OK"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="scripts/recursive_piecewise_midilli.py")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--base-outdir", required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    script = Path(args.script)
    base_out = Path(args.base_outdir); base_out.mkdir(parents=True, exist_ok=True)

    runs_iter = build_runs(PARAM_GRID)
    if args.limit:
        runs = []
        for i, p in enumerate(runs_iter):
            if i >= args.limit: break
            runs.append(p)
    else:
        runs = list(runs_iter)

    csv_path = base_out / "sweep_results.csv"
    header = ["tag","status"] + list(PARAM_GRID.keys()) + SUMMARY_KEYS + ["outdir"]

    with csv_path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(header)
        total = len(runs)
        for i, params in enumerate(runs, 1):
            tag = tag_from_params(params)
            outdir = base_out / tag
            cli = [sys.executable, str(script), "--data-dir", str(args.data_dir), "--outdir", str(outdir)]
            cli += BASE_FLAGS
            for k, v in params.items():
                cli += [f"--{k.replace('_','-')}", str(v)]
            t0 = time.time()
            metrics, _ = run_once(cli, outdir)
            status = judge(metrics, params)
            dt = time.time() - t0
            row = [tag, status] + [params[k] for k in PARAM_GRID.keys()] + [metrics.get(k, None) for k in SUMMARY_KEYS] + [str(outdir)]
            w.writerow(row)
            print(f"[{i}/{total}] {tag} -> {status} | {dt:.1f}s")

if __name__ == "__main__":
    main()
