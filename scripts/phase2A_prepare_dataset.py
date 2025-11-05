"""Assemble segment-level dataset for phase-2 modelling."""  # CHANGE: Updated script header

from __future__ import annotations  # CHANGE: Future annotations retained

import argparse  # CHANGE: CLI parsing import
import json  # CHANGE: Summary index parsing
from pathlib import Path  # CHANGE: Path operations
from typing import Any, Dict, Iterable, Iterator, Tuple  # CHANGE: Typing helpers

import pandas as pd  # CHANGE: DataFrame handling

import sys  # CHANGE: Ensure project importability

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # CHANGE: Project root
_SRC_ROOT = _PROJECT_ROOT / "src"  # CHANGE: Source directory
for candidate in (_PROJECT_ROOT, _SRC_ROOT):  # CHANGE: Extend sys.path loop
    candidate_str = str(candidate)  # CHANGE: Convert to string
    if candidate_str not in sys.path:  # CHANGE: Avoid duplicates
        sys.path.insert(0, candidate_str)  # CHANGE: Insert path

from kinetics import load_and_preprocess  # noqa: E402  # CHANGE: Preprocessing import
from kinetics.metrics import (  # noqa: E402  # CHANGE: Metrics utilities
    check_time_monotonicity,  # CHANGE: Time monotonicity check
    segment_discontinuities,  # CHANGE: Continuity diagnostics
)
from kinetics.phase2_utils import (  # noqa: E402  # CHANGE: Shared utilities import
    configure_logging,  # CHANGE: Logger factory
    ensure_directory,  # CHANGE: Directory helper
    extract_config_section,  # CHANGE: Config section helper
    load_config,  # CHANGE: Config loader
    resolve_dataset_path,  # CHANGE: Dataset resolver
)

DEFAULT_OUTPUT_PATH = _PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv"  # CHANGE: Default dataset path
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"  # CHANGE: Diagnostics directory
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"  # CHANGE: Log directory
DEFAULT_LOGGER_NAME = "phase2.phase2A"  # CHANGE: Logger name constant


def parse_args() -> argparse.Namespace:  # CHANGE: CLI parser definition
    parser = argparse.ArgumentParser(  # CHANGE: Parser creation
        description="Flatten recursive Midilli segments into a modelling dataset.",  # CHANGE: Description update
    )
    parser.add_argument(  # CHANGE: Summary index argument
        "--summary-index",
        type=Path,
        default=_PROJECT_ROOT / "outputs" / "recursive_split" / "summary_index.json",
        help="Path to the summary_index.json produced by Phase 1.",
    )
    parser.add_argument(  # CHANGE: Data root argument
        "--data-root",
        type=Path,
        default=_PROJECT_ROOT / "data",
        help="Directory containing the raw drying datasets.",
    )
    parser.add_argument(  # CHANGE: Output dataset argument
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Destination CSV for the assembled segment dataset.",
    )
    parser.add_argument(  # CHANGE: Diagnostics directory argument
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for diagnostics CSV outputs.",
    )
    parser.add_argument(  # CHANGE: Continuity threshold argument
        "--continuity-threshold",
        type=float,
        default=0.02,
        help="Normalized gap threshold for continuity warnings.",
    )
    parser.add_argument(  # CHANGE: Config path argument
        "--config",
        type=Path,
        default=None,
        help="Optional JSON/YAML config file providing overrides.",
    )
    parser.add_argument(  # CHANGE: Log level argument
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (e.g., INFO, DEBUG).",
    )
    parser.add_argument(  # CHANGE: Log directory argument
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for log files.",
    )
    return parser.parse_args()  # CHANGE: Return parsed args


def iter_leaf_segments(tree: Dict[str, Any]) -> Iterator[Tuple[Dict[str, Any], int, str]]:  # CHANGE: Leaf iterator retained
    stack: list[Tuple[Dict[str, Any], int, str]] = [(tree, 0, "0")]  # CHANGE: DFS stack initialization
    while stack:  # CHANGE: Iterate stack
        node, depth, path = stack.pop()  # CHANGE: Pop node
        children = node.get("children") if isinstance(node, dict) else None  # CHANGE: Access children
        if not children:  # CHANGE: Leaf detection
            yield node, depth, path  # CHANGE: Yield leaf info
            continue  # CHANGE: Continue traversal
        if isinstance(children, Iterable):  # CHANGE: Iterable guard
            for idx, child in enumerate(children):  # CHANGE: Enumerate children
                if isinstance(child, dict):  # CHANGE: Dict guard
                    stack.append((child, depth + 1, f"{path}.{idx}"))  # CHANGE: Push child


def main() -> None:  # CHANGE: Main entrypoint
    args = parse_args()  # CHANGE: Parse CLI args
    config = load_config(args.config)  # CHANGE: Load optional config
    section = extract_config_section(config, "phase2A")  # CHANGE: Phase 2A config section

    summary_path = Path(section.get("summary_index", args.summary_index))  # CHANGE: Summary path resolution
    data_root = Path(section.get("data_root", args.data_root))  # CHANGE: Data root resolution
    output_path = Path(section.get("output_path", args.output_path))  # CHANGE: Output path resolution
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))  # CHANGE: Diagnostics directory resolution
    continuity_threshold = float(section.get("continuity_threshold", args.continuity_threshold))  # CHANGE: Threshold resolution
    log_dir = Path(section.get("log_dir", args.log_dir))  # CHANGE: Log directory resolution
    log_level = section.get("log_level", args.log_level)  # CHANGE: Log level resolution

    ensure_directory(output_path.parent)  # CHANGE: Ensure output directory
    ensure_directory(diagnostics_dir)  # CHANGE: Ensure diagnostics directory
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"  # CHANGE: Log file path
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)  # CHANGE: Configure logger
    logger.info("Loading summary index from %s", summary_path)  # CHANGE: Log summary path

    summary = json.loads(summary_path.read_text())  # CHANGE: Read summary JSON
    default_head_trim = float(summary.get("head_trim_min", 0.0))  # CHANGE: Default head trim

    records: list[dict[str, Any]] = []  # CHANGE: Segment records container
    diagnostics_records: list[dict[str, Any]] = []  # CHANGE: Diagnostics container

    for dataset_index, dataset_entry in enumerate(summary.get("datasets", [])):  # CHANGE: Iterate datasets
        raw_input = dataset_entry.get("input")  # CHANGE: Dataset input path
        if raw_input is None:  # CHANGE: Skip missing entries
            logger.debug("Skipping dataset without input reference at index %s", dataset_index)  # CHANGE: Debug skip
            continue  # CHANGE: Continue loop

        resolved_path = resolve_dataset_path(str(raw_input), data_root)  # CHANGE: Resolve dataset path
        head_trim = float(dataset_entry.get("head_trim_min", default_head_trim))  # CHANGE: Determine head trim
        preprocess = load_and_preprocess(resolved_path, head_trim)  # CHANGE: Preprocess dataset
        hints = preprocess.metadata.get("hints", {})  # CHANGE: Extract metadata hints

        feature_values = {  # CHANGE: Static feature fields
            "dataset_index": dataset_index,  # CHANGE: Dataset index
            "dataset_name": resolved_path.name,  # CHANGE: Dataset name
            "dataset_stem": resolved_path.stem,  # CHANGE: Dataset stem
            "T": hints.get("T_C"),  # CHANGE: Temperature hint
            "RH": hints.get("RH_pct"),  # CHANGE: Humidity hint
            "velocity": hints.get("v_ms"),  # CHANGE: Velocity hint
            "thickness": hints.get("thickness_mm"),  # CHANGE: Thickness hint
        }

        time_full = pd.Series(preprocess.time_min)  # CHANGE: Time series
        mr_full = pd.Series(preprocess.mr_iso)  # CHANGE: MR series

        tree = dataset_entry.get("tree")  # CHANGE: Tree retrieval
        if not isinstance(tree, dict):  # CHANGE: Guard invalid tree
            logger.warning("Dataset %s has invalid tree structure; skipping", resolved_path.name)  # CHANGE: Warning log
            continue  # CHANGE: Continue loop

        for leaf_idx, (node, depth, path) in enumerate(iter_leaf_segments(tree)):  # CHANGE: Iterate leaf segments
            params = node.get("params", {}) if isinstance(node, dict) else {}  # CHANGE: Parameters retrieval
            t_start = float(node.get("t_start") or float("nan"))  # CHANGE: Segment start
            t_end = float(node.get("t_end") or float("nan"))  # CHANGE: Segment end
            t_end = t_end if pd.notna(t_end) else t_start  # CHANGE: Fallback end time

            segment_mask = (time_full >= t_start) & (time_full <= t_end + 1e-9)  # CHANGE: Segment mask
            time_segment = time_full.loc[segment_mask].dropna().sort_values()  # CHANGE: Segment times
            mr_segment = mr_full.loc[segment_mask].reindex(time_segment.index)  # CHANGE: Segment MR values
            monotonic = check_time_monotonicity(time_segment.to_numpy(dtype=float))  # CHANGE: Monotonic check
            has_duplicates = time_segment.duplicated().any()  # CHANGE: Duplicate detection

            if not monotonic or has_duplicates:  # CHANGE: Log anomalies
                logger.warning(
                    "Time monotonicity issue in %s segment %s (monotonic=%s, duplicates=%s)",
                    resolved_path.name,
                    path,
                    monotonic,
                    has_duplicates,
                )  # CHANGE: Warning log

            segment_start_mr = float(mr_segment.iloc[0]) if not mr_segment.empty else float("nan")  # CHANGE: Start MR
            segment_end_mr = float(mr_segment.iloc[-1]) if not mr_segment.empty else float("nan")  # CHANGE: End MR

            record = {  # CHANGE: Segment record assembly
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
                "segment_start_MR": segment_start_mr,
                "segment_end_MR": segment_end_mr,
            }
            records.append(record)  # CHANGE: Append record

            diagnostics_records.append(  # CHANGE: Append diagnostics
                {
                    "dataset_name": resolved_path.name,
                    "segment_index": leaf_idx,
                    "segment_path": path,
                    "segment_start_time": t_start,
                    "segment_end_time": t_end,
                    "segment_start_MR": segment_start_mr,
                    "segment_end_MR": segment_end_mr,
                    "time_monotonic": bool(monotonic),
                    "has_duplicate_time": bool(has_duplicates),
                    "segment_obs_count": int(len(time_segment)),
                }
            )

    if not records:  # CHANGE: Guard missing segments
        raise RuntimeError("No segment records were extracted from the summary index.")  # CHANGE: Error message

    df = pd.DataFrame.from_records(records)  # CHANGE: Create DataFrame
    df.sort_values(["dataset_index", "segment_start_time"], inplace=True, ignore_index=True)  # CHANGE: Sort segments
    df["segment_order"] = df.groupby("dataset_name").cumcount()  # CHANGE: Order within dataset

    diagnostics_df = pd.DataFrame(diagnostics_records)  # CHANGE: Diagnostics DataFrame
    if not diagnostics_df.empty:  # CHANGE: Merge diagnostics order
        diagnostics_df = diagnostics_df.merge(
            df[["dataset_name", "segment_index", "segment_order"]],
            on=["dataset_name", "segment_index"],
            how="left",
        )  # CHANGE: Attach order info

    continuity_df = segment_discontinuities(df)  # CHANGE: Compute continuity gaps
    if not continuity_df.empty:  # CHANGE: Annotate continuity diagnostics
        continuity_df.rename(columns={"gap": "continuity_gap"}, inplace=True)  # CHANGE: Rename gap column
        continuity_df["is_continuity_violation"] = continuity_df["continuity_gap"].astype(float) > continuity_threshold  # CHANGE: Violation flag
        diagnostics_df = diagnostics_df.merge(
            continuity_df,
            left_on=["dataset_name", "segment_order"],
            right_on=["dataset_name", "segment_index"],
            how="left",
            suffixes=("", "_continuity"),
        )  # CHANGE: Merge continuity info
    else:  # CHANGE: Continuity fallback
        diagnostics_df["continuity_gap"] = pd.NA  # CHANGE: Fill NA
        diagnostics_df["is_continuity_violation"] = pd.NA  # CHANGE: Fill NA

    df.to_csv(output_path, index=False)  # CHANGE: Write dataset CSV
    logger.info("Wrote %s segment rows to %s", len(df), output_path)  # CHANGE: Log output size

    diagnostics_path = diagnostics_dir / "phase2A_report.csv"  # CHANGE: Diagnostics path
    diagnostics_df.to_csv(diagnostics_path, index=False)  # CHANGE: Write diagnostics CSV
    logger.info(
        "Recorded diagnostics for %s segments to %s", len(diagnostics_df), diagnostics_path
    )  # CHANGE: Log diagnostics path


if __name__ == "__main__":  # CHANGE: Script guard
    main()  # CHANGE: Invoke main
