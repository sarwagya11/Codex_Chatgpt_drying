"""Assemble segment-level dataset for phase-2 modelling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Iterator, Tuple

import pandas as pd

# Ensure project modules are importable when running as a script -----------------
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.phase2_utils import resolve_dataset_path  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flatten recursive Midilli segments into a modelling dataset.",
    )
    parser.add_argument(
        "--summary-index",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "recursive_split" / "summary_index.json",
        help="Path to the summary_index.json produced by Phase 1.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=_PROJECT_ROOT / "data",
        help="Directory containing the raw drying datasets.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=_PROJECT_ROOT
        / "outputs"
        / "phase2"
        / "segments_dataset.csv",
        help="Destination CSV for the assembled segment dataset.",
    )
    return parser.parse_args()


def iter_leaf_segments(tree: Dict[str, object]) -> Iterator[Tuple[Dict[str, object], int, str]]:
    """Yield leaf nodes from the recursive split tree."""

    stack: list[Tuple[Dict[str, object], int, str]] = [(tree, 0, "0")]
    while stack:
        node, depth, path = stack.pop()
        children = node.get("children") if isinstance(node, dict) else None
        if not children:
            yield node, depth, path
            continue
        if isinstance(children, Iterable):
            for idx, child in enumerate(children):
                if isinstance(child, dict):
                    stack.append((child, depth + 1, f"{path}.{idx}"))


def main() -> None:
    args = parse_args()
    output_path: Path = args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = json.loads(args.summary_index.read_text())
    default_head_trim = float(summary.get("head_trim_min", 0.0))

    records: list[dict] = []

    for dataset_index, dataset_entry in enumerate(summary.get("datasets", [])):
        raw_input = dataset_entry.get("input")
        if raw_input is None:
            continue

        resolved_path = resolve_dataset_path(raw_input, args.data_root)
        head_trim = float(dataset_entry.get("head_trim_min", default_head_trim))
        preprocess = load_and_preprocess(resolved_path, head_trim)
        hints = preprocess.metadata.get("hints", {})

        feature_values = {
            "dataset_index": dataset_index,
            "dataset_name": resolved_path.name,
            "dataset_stem": resolved_path.stem,
            "T": hints.get("T_C"),
            "RH": hints.get("RH_pct"),
            "velocity": hints.get("v_ms"),
            "thickness": hints.get("thickness_mm"),
        }

        tree = dataset_entry.get("tree")
        if not isinstance(tree, dict):
            continue

        for leaf_idx, (node, depth, path) in enumerate(iter_leaf_segments(tree)):
            params = node.get("params", {}) if isinstance(node, dict) else {}
            t_start = float(node.get("t_start", float("nan")))
            t_end = float(node.get("t_end", float("nan")))
            record = {
                **feature_values,
                "segment_index": leaf_idx,
                "segment_path": path,
                "segment_position": depth,
                "segment_start_time": t_start,
                "segment_end_time": t_end,
                "segment_duration": t_end - t_start,
                "n_obs": node.get("n_obs"),
                "rmse": node.get("rmse"),
                "aicc": node.get("aicc"),
                "k": params.get("k"),
                "n": params.get("n"),
                "b": params.get("b"),
            }
            records.append(record)

    if not records:
        raise RuntimeError("No segment records were extracted from the summary index.")

    df = pd.DataFrame.from_records(records)
    df.sort_values(["dataset_index", "segment_start_time"], inplace=True, ignore_index=True)
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} segment rows to {output_path}")


if __name__ == "__main__":
    main()
