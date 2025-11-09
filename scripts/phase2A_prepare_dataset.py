"""Assemble segment-level dataset from recursive Midilli outputs."""

from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple

import numpy as np
import pandas as pd

try:
    from statsmodels.nonparametric.smoothers_lowess import lowess  # type: ignore
    HAVE_LOWESS = True
except ImportError:  # pragma: no cover - optional dependency
    HAVE_LOWESS = False

import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
for candidate in (_PROJECT_ROOT, _SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from kinetics import load_and_preprocess  # noqa: E402
from kinetics.phase2_utils import (  # noqa: E402
    BASE_FEATURE_COLUMNS,
    clip_mr,
    configure_logging,
    ensure_directory,
    extract_config_section,
    load_config,
    midilli_curve,
    midilli_derivative,
    prepare_feature_frame,
    resolve_dataset_path,
)

DEFAULT_RUNS_ROOT = _PROJECT_ROOT / "outputs" / "piecewise_recursive"
DEFAULT_SUMMARY_INDEX = DEFAULT_RUNS_ROOT / "summary_index.json"
DEFAULT_OUTPUT_PATH = _PROJECT_ROOT / "outputs" / "phase2" / "segments_dataset.csv"
DEFAULT_DIAGNOSTICS_DIR = _PROJECT_ROOT / "outputs" / "diagnostics"
DEFAULT_LOG_DIR = _PROJECT_ROOT / "outputs" / "logs"
DEFAULT_LOGGER_NAME = "phase2.phase2A"

REQUIRED_COLUMNS = {
    "dataset_name",
    "segment_index",
    "segment_start_time",
    "segment_end_time",
    "segment_duration",
    "segment_start_MR",
    "segment_end_MR",
    "segment_position",
    "segment_mid_time",
    "T",
    "RH",
    "velocity",
    "thickness",
}


@dataclass
class EnvironmentFeatures:
    T: float
    RH: float
    velocity: float
    thickness: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flatten recursive Midilli segments into a modelling dataset.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=DEFAULT_RUNS_ROOT,
        help="Root directory containing per-run recursive Midilli folders.",
    )
    parser.add_argument(
        "--summary-index",
        type=Path,
        default=DEFAULT_SUMMARY_INDEX,
        help="summary_index.json produced alongside recursive Midilli outputs.",
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
        default=DEFAULT_OUTPUT_PATH,
        help="Destination CSV for the assembled segment dataset.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_DIR,
        help="Directory for diagnostics CSV outputs.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for log files.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (e.g., INFO, DEBUG).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON/YAML config file providing overrides.",
    )
    return parser.parse_args()


def iter_tree_summaries(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("tree_summary.json")):
        if path.is_file():
            yield path


def parse_numeric_token(token: str) -> float | None:
    cleaned = (
        token.replace("mm", "")
        .replace("MM", "")
        .replace("pct", "")
        .replace("ms", "")
        .replace("%", "")
    )
    cleaned = cleaned.replace("p", ".")
    cleaned = cleaned.strip().lower()
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_from_tokens(tokens: List[str], keywords: Iterable[str], prefixes: Iterable[str]) -> float | None:
    lowered = [t.lower() for t in tokens]
    for idx, token in enumerate(lowered):
        if token in keywords and idx + 1 < len(tokens):
            value = parse_numeric_token(tokens[idx + 1])
            if value is not None:
                return value
    for original, token in zip(tokens, lowered):
        for prefix in prefixes:
            if token.startswith(prefix) and len(token) > len(prefix):
                remainder = original[len(prefix) :]
                value = parse_numeric_token(remainder)
                if value is not None:
                    return value
    return None


def extract_environment_features(dataset_name: str, hints: Dict[str, Any]) -> EnvironmentFeatures:
    tokens = [t for t in dataset_name.replace("-", "_").split("_") if t]

    def _hint_or_parse(keys: Iterable[str], prefixes: Iterable[str], hint_key: str) -> float:
        hint_val = None
        for key in (hint_key, hint_key.lower()):
            if key in hints and hints[key] is not None:
                hint_val = hints[key]
                break
        if hint_val is not None and isinstance(hint_val, (int, float)):
            return float(hint_val)
        parsed = extract_from_tokens(tokens, list(keys), list(prefixes))
        if parsed is None:
            raise ValueError(f"Could not determine {hint_key} for dataset {dataset_name}")
        return float(parsed)

    temperature = _hint_or_parse(["t", "temp", "temperature"], ["t"], "T_C")
    humidity = _hint_or_parse(["rh"], ["rh"], "RH_pct")
    velocity = _hint_or_parse(["v", "vel", "velocity"], ["v"], "v_ms")
    try:
        thickness = _hint_or_parse(["thickness", "thick", "th"], ["thickness", "th"], "thickness_mm")
    except ValueError:
        thickness = None
        lowered = [t.lower() for t in tokens]
        for idx, token in enumerate(lowered):
            if token == "t" and idx + 1 < len(tokens):
                next_token = tokens[idx + 1]
                if "mm" in next_token.lower() or next_token.lower().startswith("th"):
                    candidate = parse_numeric_token(next_token)
                    if candidate is not None:
                        thickness = candidate
                        break
            if token.startswith("t") and "mm" in token and len(token) > 1:
                candidate = parse_numeric_token(tokens[idx][1:])
                if candidate is not None:
                    thickness = candidate
                    break
        if thickness is None:
            hint_val = hints.get("thickness_mm") or hints.get("thickness")
            if isinstance(hint_val, (int, float)):
                thickness = float(hint_val)
        if thickness is None:
            raise ValueError(f"Could not determine thickness for dataset {dataset_name}")

    return EnvironmentFeatures(
        T=float(temperature),
        RH=float(humidity),
        velocity=float(velocity),
        thickness=float(thickness),
    )


def summary_parent_map(nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    parent_map: Dict[str, Dict[str, Any]] = {}
    for node in nodes.values():
        children = node.get("children")
        if isinstance(children, list):
            for child_id in children:
                if child_id in nodes:
                    parent_map[child_id] = node
    return parent_map


def compute_lowess_diagnostics(time: np.ndarray, residuals: np.ndarray) -> Tuple[float, float]:
    if not HAVE_LOWESS or time.size < 5:
        return float("nan"), float("nan")
    try:
        span = float(np.clip(5.0 / max(time.size, 1), 0.1, 0.6))
        smooth = lowess(residuals, time, frac=span, return_sorted=False)
    except Exception:  # pragma: no cover - statsmodels runtime errors
        return float("nan"), float("nan")
    amplitude = float(np.nanmax(smooth) - np.nanmin(smooth)) if smooth.size else float("nan")
    if smooth.size >= 3:
        first_der = np.gradient(smooth, time)
        second_der = np.gradient(first_der, time)
        curvature = float(np.nanmax(np.abs(second_der)))
    else:
        curvature = float("nan")
    return curvature, amplitude


def gather_segment_records(
    dataset_index: int,
    dataset_name: str,
    summary: Dict[str, Any],
    preprocess,
    env: EnvironmentFeatures,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes_raw = summary.get("nodes", [])
    if not isinstance(nodes_raw, list):
        raise ValueError(f"Summary for {dataset_name} is missing node list")
    nodes = {node["node_id"]: node for node in nodes_raw if isinstance(node, dict) and "node_id" in node}
    if not nodes:
        raise ValueError(f"No nodes found for {dataset_name}")

    parent_map = summary_parent_map(nodes)
    config = summary.get("config", {}) if isinstance(summary.get("config"), dict) else {}
    min_points_leaf = int(config.get("min_points_leaf", 0))

    time = preprocess.time_min.astype(float)
    actual = preprocess.mr_iso.astype(float)

    leaves = [node for node in nodes.values() if not node.get("children")]
    leaves.sort(key=lambda node: (int(node.get("start_idx", 0)), node.get("node_id", "")))

    records: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []

    prev_end_mr: float | None = None

    for order, node in enumerate(leaves):
        unsplit_info = node.get("unsplit", {})
        if not isinstance(unsplit_info, dict):
            unsplit_info = {}
        params = unsplit_info.get("params", {})
        k = float(params.get("k", float("nan")))
        n = float(params.get("n", float("nan")))
        b = float(params.get("b", float("nan")))
        if not all(math.isfinite(x) for x in (k, n, b)):
            continue

        start_idx = int(node.get("start_idx", 0))
        end_idx = int(node.get("end_idx", start_idx))
        if end_idx <= start_idx:
            continue
        segment_time = time[start_idx:end_idx]
        if segment_time.size == 0:
            continue
        segment_actual = actual[start_idx:end_idx]

        raw_preds = midilli_curve(segment_time, k, n, b)
        raw_preds = clip_mr(raw_preds)
        continuity_shift = 0.0
        if prev_end_mr is not None and raw_preds.size:
            continuity_shift = float(raw_preds[0] - prev_end_mr)
            raw_preds = clip_mr(raw_preds - continuity_shift)
        segment_start_mr = float(raw_preds[0]) if raw_preds.size else float("nan")
        segment_end_mr = float(raw_preds[-1]) if raw_preds.size else float("nan")
        prev_end_mr = segment_end_mr if math.isfinite(segment_end_mr) else prev_end_mr

        residuals = segment_actual - raw_preds
        rms = float(np.sqrt(np.nanmean(np.square(residuals)))) if residuals.size else float("nan")
        curvature, amplitude = compute_lowess_diagnostics(segment_time, residuals)

        start_time = float(segment_time[0])
        end_time = float(segment_time[-1])
        duration = max(end_time - start_time, 0.0)
        mid_time = start_time + duration / 2.0

        parent = parent_map.get(node["node_id"])
        join_gap = float(abs(parent.get("gap", 0.0))) if parent else 0.0
        is_root = bool(node.get("depth", 0) == 0)
        n_obs = int(end_idx - start_idx)
        min_points_hit = bool(n_obs < min_points_leaf)
        family = unsplit_info.get("family", "")
        if family is None:
            family = ""
        else:
            family = str(family)

        record = {
            "dataset_index": dataset_index,
            "dataset_name": dataset_name,
            "source_path": str(summary.get("file", "")),
            "segment_index": order,
            "segment_path": node.get("node_id"),
            "segment_position": order + 1,
            "segment_start_time": start_time,
            "segment_end_time": end_time,
            "segment_duration": duration,
            "segment_mid_time": mid_time,
            "segment_start_MR": segment_start_mr,
            "segment_end_MR": segment_end_mr,
            "n_obs": n_obs,
            "depth": int(node.get("depth", 0)),
            "join_gap": join_gap,
            "left_slope": float(midilli_derivative(np.array([start_time]), k, n, b)[0]),
            "right_slope": float(midilli_derivative(np.array([end_time]), k, n, b)[0]),
            "resid_rms_segment": rms,
            "lowess_curvature": curvature,
            "lowess_amplitude": amplitude,
            "is_root": 1 if is_root else 0,
            "is_leaf": 1,
            "min_points_constraint_hit": 1 if min_points_hit else 0,
            "family": family,
            "k": k,
            "n": n,
            "b": b,
            "continuity_shift": continuity_shift,
            "T": env.T,
            "RH": env.RH,
            "velocity": env.velocity,
            "thickness": env.thickness,
        }
        records.append(record)

        diagnostics.append(
            {
                "dataset_name": dataset_name,
                "segment_index": order,
                "segment_path": node.get("node_id"),
                "continuity_shift": continuity_shift,
                "join_gap": join_gap,
                "segment_start_time": start_time,
                "segment_end_time": end_time,
                "segment_start_MR": segment_start_mr,
                "segment_end_MR": segment_end_mr,
                "resid_rms_segment": rms,
                "lowess_curvature": curvature,
                "lowess_amplitude": amplitude,
            }
        )

    return records, diagnostics


def load_summary_index(summary_path: Path, data_root: Path) -> Dict[str, Tuple[Path, float]]:
    if not summary_path.exists():
        return {}
    payload = json.loads(summary_path.read_text())
    registry: Dict[str, Tuple[Path, float]] = {}
    if isinstance(payload.get("datasets"), list):
        default_trim = float(payload.get("head_trim_min", 0.0))
        for entry in payload["datasets"]:
            raw_input = entry.get("input")
            if not raw_input:
                continue
            resolved = resolve_dataset_path(raw_input, data_root)
            head_trim = float(entry.get("head_trim_min", default_trim))
            registry[Path(raw_input).stem] = (resolved, head_trim)
    elif isinstance(payload.get("summaries"), list):
        for entry in payload["summaries"]:
            raw_input = entry.get("file")
            if not raw_input:
                continue
            resolved = resolve_dataset_path(raw_input, data_root)
            head_trim = float(entry.get("head_trim_min", 0.0))
            key = Path(raw_input).stem
            registry[key] = (resolved, head_trim)
    return registry


def resolve_dataset_path_with_registry(
    summary: Dict[str, Any],
    dataset_name: str,
    registry: Dict[str, Tuple[Path, float]],
    data_root: Path,
) -> Tuple[Path, float]:
    raw_file = summary.get("file")
    if raw_file:
        try:
            resolved = resolve_dataset_path(raw_file, data_root)
            key = Path(raw_file).stem
            head_trim = registry.get(key, (None, 0.0))[1] if registry else 0.0
            return resolved, float(head_trim)
        except FileNotFoundError:
            pass
    if registry:
        if dataset_name in registry:
            return registry[dataset_name]
        alt = Path(dataset_name).stem
        if alt in registry:
            return registry[alt]
    candidate = resolve_dataset_path(f"{dataset_name}.csv", data_root)
    return candidate, 0.0


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    section = extract_config_section(config, "phase2A")

    runs_root = Path(section.get("runs_root", args.runs_root))
    summary_index_path = Path(section.get("summary_index", args.summary_index))
    data_root = Path(section.get("data_root", args.data_root))
    output_path = Path(section.get("output_path", args.output_path))
    diagnostics_dir = Path(section.get("diagnostics_dir", args.diagnostics_dir))
    log_dir = Path(section.get("log_dir", args.log_dir))
    log_level = section.get("log_level", args.log_level)

    ensure_directory(output_path.parent)
    ensure_directory(diagnostics_dir)
    log_path = ensure_directory(log_dir) / f"{DEFAULT_LOGGER_NAME.replace('.', '_')}.log"
    logger = configure_logging(DEFAULT_LOGGER_NAME, log_path=log_path, level=log_level)

    if not runs_root.exists():
        raise FileNotFoundError(f"Runs root not found: {runs_root}")

    registry = load_summary_index(summary_index_path, data_root)

    all_records: List[Dict[str, Any]] = []
    diagnostics_records: List[Dict[str, Any]] = []

    for dataset_index, summary_path in enumerate(iter_tree_summaries(runs_root)):
        dataset_name = summary_path.parent.name
        logger.info("Processing %s", dataset_name)
        summary = json.loads(summary_path.read_text())
        dataset_path, head_trim = resolve_dataset_path_with_registry(summary, dataset_name, registry, data_root)
        preprocess = load_and_preprocess(dataset_path, head_trim)
        hints = preprocess.metadata.get("hints", {}) if isinstance(preprocess.metadata, dict) else {}
        env = extract_environment_features(dataset_name, hints)
        records, diagnostics = gather_segment_records(dataset_index, dataset_name, summary, preprocess, env)
        if not records:
            logger.warning("No segments recorded for %s", dataset_name)
            continue
        for record in records:
            record["head_trim_min"] = preprocess.head_trim_min
        all_records.extend(records)
        diagnostics_records.extend(diagnostics)

    if not all_records:
        raise RuntimeError("No segment records were extracted from recursive Midilli outputs.")

    df = pd.DataFrame.from_records(all_records)
    df.sort_values(["dataset_name", "segment_start_time"], inplace=True, ignore_index=True)
    df["segment_index"] = df.groupby("dataset_name").cumcount()
    df["segment_position"] = df["segment_index"] + 1

    feature_check = prepare_feature_frame(df)
    core_missing = [col for col in BASE_FEATURE_COLUMNS if feature_check[col].isna().any()]
    if core_missing:
        raise ValueError(f"NaNs detected in core features: {core_missing}")

    df["segment_duration"] = df["segment_end_time"] - df["segment_start_time"]
    df.loc[df["segment_duration"] < 0, "segment_duration"] = 0.0

    df = df[list(dict.fromkeys(list(REQUIRED_COLUMNS) + [c for c in df.columns if c not in REQUIRED_COLUMNS]))]

    df.to_csv(output_path, index=False, float_format="%.9g")

    diagnostics_df = pd.DataFrame.from_records(diagnostics_records)
    diagnostics_path = diagnostics_dir / "phase2A_diagnostics.csv"
    diagnostics_df.to_csv(diagnostics_path, index=False, float_format="%.9g")

    logger.info("Wrote %s segment rows to %s", len(df), output_path)
    logger.info("Diagnostics written to %s", diagnostics_path)


if __name__ == "__main__":
    main()
