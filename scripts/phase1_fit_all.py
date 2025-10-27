# %%
# Quick-start example for VS Code Interactive Window
# from pathlib import Path
# from scripts.phase1_fit_all import run_batch
# run_batch(
#     outdir=Path("outputs/phase1_fits"),
#     head_trim_min=0.0,
# )

# %%
"""Batch fitting utility for Phase-1 drying kinetics datasets."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

try:
    _HERE = Path(__file__).resolve()
except NameError:
    _HERE = Path.cwd()

if len(_HERE.parents) >= 2:
    _PROJECT_ROOT = _HERE.parents[1]
else:
    _PROJECT_ROOT = _HERE.parent

_SRC_PATH = _PROJECT_ROOT / "src"
if _SRC_PATH.exists() and str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

import pandas as pd

from scripts.phase1_fit_once import run_pipeline


def discover_datasets(root: Path) -> List[str]:
    candidates: List[Path] = []
    search_locations: List[Tuple[Path, bool]] = [
        (root, False),
        (root / "data" / "raw", True),
    ]
    seen = set()
    for location, allow_subdirs in search_locations:
        if not location.exists():
            continue
        patterns = ["*.csv", "*.xlsx", "*.xls"]
        for pattern in patterns:
            iterator = location.rglob(pattern) if allow_subdirs else location.glob(pattern)
            for path in iterator:
                if any(part.startswith("outputs") or part == "scripts" for part in path.parts):
                    continue
                resolved = str(path.resolve())
                if resolved not in seen:
                    candidates.append(path)
                    seen.add(resolved)
    return [str(path.resolve()) for path in candidates]


def run_batch(outdir: Path, head_trim_min: float = 0.0) -> pd.DataFrame:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        root = Path(__file__).resolve().parents[1]
    except NameError:
        root = Path.cwd()
    datasets = discover_datasets(root)
    results: List[dict] = []
    failures: List[Tuple[str, str]] = []

    for dataset in datasets:
        try:
            output = run_pipeline(dataset, outdir=outdir, head_trim_min=head_trim_min)
            best = output["best"]
            results.append({
                "file": dataset,
                "model": best["model"],
                "rmse": best["rmse"],
                "aicc": best["aicc"],
                "loo_rmse": best["loo_rmse"],
            })
        except Exception as exc:
            failures.append((dataset, str(exc)))
            print(f"Failed on {dataset}: {exc}")

    master_path = outdir / "phase1_master.csv"
    master_df = pd.read_csv(master_path) if master_path.exists() else pd.DataFrame()

    print(
        f"Batch completed. {len(results)} successes, {len(failures)} failures. Master CSV: {master_path}"
    )
    if failures:
        print("Failed files:")
        for file_path, message in failures:
            print(f"  - {file_path}: {message}")

    return master_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch Phase-1 fitting across datasets")
    parser.add_argument(
        "--outdir",
        default="outputs/phase1_fits",
        help="Directory for output artifacts",
    )
    parser.add_argument(
        "--head_trim_min",
        type=float,
        default=0.0,
        help="Minutes of head segment to trim before fitting",
    )
    return parser.parse_args()


def _running_interactively() -> bool:
    try:
        from IPython import get_ipython  # type: ignore
    except Exception:
        return False
    return get_ipython() is not None


def main():
    if len(sys.argv) <= 1 and _running_interactively():
        print(
            "Interactive session detected — call run_batch(...) from the first cell "
            "instead of invoking the CLI without arguments."
        )
        return

    args = _parse_args()
    run_batch(outdir=Path(args.outdir), head_trim_min=args.head_trim_min)


if __name__ == "__main__":
    main()
