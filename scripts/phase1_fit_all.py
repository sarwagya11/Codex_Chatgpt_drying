"""Batch execution of the phase-1 drying kinetics pipeline."""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import Iterable, List

# Bootstrap sys.path for interactive usage -----------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from scripts.phase1_fit_once import run_pipeline  # noqa: E402


def run_batch(
    input_glob: str | None = None,
    outdir: str | Path = "phase1_out",
    head_trim_min: float = 0.0,
) -> List[dict]:
    """Run the phase-1 pipeline for each dataset matching the glob pattern."""

    datasets = _discover_datasets(input_glob)
    if not datasets:
        raise ValueError("No datasets matched the provided criteria.")

    summaries: List[dict] = []
    total = len(datasets)
    for idx, dataset in enumerate(datasets, start=1):
        print(f"[{idx}/{total}] Processing {dataset}")
        summary = run_pipeline(dataset, outdir=outdir, head_trim_min=head_trim_min)
        summaries.append(summary)
    return summaries


def _discover_datasets(pattern: str | None) -> List[Path]:
    if pattern:
        expanded = glob.glob(str(Path(pattern).expanduser()))
        return [Path(p).resolve() for p in expanded if Path(p).is_file()]

    candidates: List[Path] = []
    ignored = {"phase1_out", "src", "scripts", ".git", ".pytest_cache"}
    for child in _PROJECT_ROOT.iterdir():
        if child.is_dir() and child.name in ignored:
            continue
        if child.is_file() and child.suffix.lower() in {".csv", ".xlsx"}:
            candidates.append(child.resolve())
    return sorted(candidates)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run phase-1 drying pipeline across datasets.")
    parser.add_argument(
        "--glob",
        dest="glob_pattern",
        default=None,
        help="Glob pattern for selecting input datasets (defaults to project root *.csv/*.xlsx).",
    )
    parser.add_argument(
        "--outdir",
        default="phase1_out",
        help="Directory for all outputs.",
    )
    parser.add_argument(
        "--head_trim_min",
        type=float,
        default=0.0,
        help="Trim leading minutes before fitting.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    run_batch(args.glob_pattern, outdir=args.outdir, head_trim_min=args.head_trim_min)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
