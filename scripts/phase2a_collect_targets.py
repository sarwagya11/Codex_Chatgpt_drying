"""Build the Phase-2 training targets table from Phase-1 outputs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from .phase2_common import _midilli_curve, parse_dataset_stem, write_run_meta


LOGGER = logging.getLogger("phase2.targets")


DEFAULT_PHASE1_ROOT = Path(
    r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\piecewise_recursive_2ndphase"
)
DEFAULT_OUT_CSV = Path(
    r"D:\Masters\RQ5\Codex_Chatgpt_drying\outputs\phase2\phase2_targets.csv"
)

OUTPUT_COLUMNS = [
    "dataset",
    "T_C",
    "v_ms",
    "thickness_mm",
    "RH_lo_pct",
    "RH_hi_pct",
    "RH_mid_pct",
    "tL_start",
    "tL_end",
    "famL",
    "kL",
    "nL",
    "bL",
    "AICcL",
    "rmseL",
    "tR_start",
    "tR_end",
    "famR",
    "kR",
    "nR",
    "bR",
    "AICcR",
    "rmseR",
    "offsetR_at_join",
    "right_time_shift_at_boundary",
    "rmse_total_raw",
    "rmse_total_corrected",
    "delta_AICc_total",
    "splits_used",
    "famL_is_page",
    "famR_is_page",
]

def _find_leaves_csv(folder: Path) -> Path | None:
    for csv_path in folder.glob("*_leaves.csv"):
        return csv_path
    return None


def _extract_value(series: pd.Series, candidates: Iterable[str], default: Any = None) -> Any:
    for name in candidates:
        if name in series:
            return series[name]
    return default


def _align_boundary(left_params, right_params, t_join, is_page_L, is_page_R):
    # Evaluate left at absolute t_join. Evaluate right at local right_t = tshift (start=0).
    yL = _midilli_curve(np.array([t_join]), left_params["k"], left_params["n"], left_params["b"], is_page_L)[0]
    # Default tshift=0 to define 'meeting place'; user can later train tshift ≠ 0
    tshift = 0.0
    yR = _midilli_curve(np.array([tshift]), right_params["k"], right_params["n"], right_params["b"], is_page_R)[0]
    offset = float(yL - yR)
    return offset, tshift


def collect_targets(phase1_root: Path, args: argparse.Namespace | None = None) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []

    for dataset_dir in sorted(p for p in phase1_root.iterdir() if p.is_dir()):
        dataset_stem = dataset_dir.name
        leaves_path = _find_leaves_csv(dataset_dir)
        summary_path = dataset_dir / "tree_summary.json"
        if not leaves_path or not summary_path.exists():
            LOGGER.debug("Skipping %s (missing leaves or summary)", dataset_stem)
            continue

        leaves_df = pd.read_csv(leaves_path)
        if len(leaves_df) != 2:
            LOGGER.info("Skipping %s because it has %d leaves", dataset_stem, len(leaves_df))
            continue

        leaves_df = leaves_df.sort_values("t_start")
        left = leaves_df.iloc[0]
        right = leaves_df.iloc[1]

        tL_end = float(_extract_value(left, ["t_end", "t_stop", "t_exit"]))
        tR_start = float(_extract_value(right, ["t_start", "t_begin"]))
        if tL_end > tR_start + 1e-6:
            LOGGER.warning("Dataset %s is not contiguous (%.3f > %.3f)", dataset_stem, tL_end, tR_start)
            continue

        with summary_path.open("r", encoding="utf-8") as fh:
            summary = json.load(fh)

        metrics = summary.get("metrics", summary)
        splits_used = metrics.get("splits_used", metrics.get("splits", None))
        if splits_used != 1:
            LOGGER.info("Skipping %s due to splits_used=%s", dataset_stem, splits_used)
            continue

        env = parse_dataset_stem(dataset_stem)

        famL = str(_extract_value(left, ["family", "fam", "model"])).strip()
        famR = str(_extract_value(right, ["family", "fam", "model"])).strip()

        bL_raw = float(_extract_value(left, ["b", "bL"], default=0.0))
        bR_raw = float(_extract_value(right, ["b", "bR"], default=0.0))
        famL_is_page = famL.lower() == "page"
        famR_is_page = famR.lower() == "page"

        record = {
            "dataset": dataset_stem,
            "T_C": env["T_C"],
            "v_ms": env["v_ms"],
            "thickness_mm": env["thickness_mm"],
            "RH_lo_pct": env["RH_lo_pct"],
            "RH_hi_pct": env["RH_hi_pct"],
            "RH_mid_pct": env["RH_mid_pct"],
            "tL_start": float(_extract_value(left, ["t_start", "t_begin"])),
            "tL_end": tL_end,
            "famL": famL,
            "kL": float(_extract_value(left, ["k", "kL"])),
            "nL": float(_extract_value(left, ["n", "nL"])),
            "bL": 0.0 if famL_is_page else bL_raw,
            "AICcL": float(_extract_value(left, ["AICc", "aicc", "AICcL"])),
            "rmseL": float(_extract_value(left, ["rmse", "rmseL"])),
            "tR_start": tR_start,
            "tR_end": float(_extract_value(right, ["t_end", "t_stop", "t_exit"])),
            "famR": famR,
            "kR": float(_extract_value(right, ["k", "kR"])),
            "nR": float(_extract_value(right, ["n", "nR"])),
            "bR": 0.0 if famR_is_page else bR_raw,
            "AICcR": float(_extract_value(right, ["AICc", "aicc", "AICcR"])),
            "rmseR": float(_extract_value(right, ["rmse", "rmseR"])),
            "offsetR_at_join": float(
                _extract_value(right, ["offsetR_at_join", "offset", "level_shift"], default=0.0)
            ),
            "right_time_shift_at_boundary": float(
                _extract_value(
                    right,
                    ["right_time_shift_at_boundary", "time_shift", "tshift"],
                    default=0.0,
                )
            ),
            "rmse_total_raw": float(metrics.get("rmse_total_raw", metrics.get("rmse_raw", np.nan))),
            "rmse_total_corrected": float(
                metrics.get("rmse_total_corrected", metrics.get("rmse_corrected", np.nan))
            ),
            "delta_AICc_total": float(metrics.get("delta_AICc_total", np.nan)),
            "splits_used": int(splits_used),
            "famL_is_page": bool(famL_is_page),
            "famR_is_page": bool(famR_is_page),
        }

        if args and getattr(args, "recompute_boundary", False):
            off, tsh = _align_boundary(
                left_params={"k": record["kL"], "n": record["nL"], "b": record["bL"]},
                right_params={"k": record["kR"], "n": record["nR"], "b": record["bR"]},
                t_join=record["tL_end"],
                is_page_L=record["famL_is_page"],
                is_page_R=record["famR_is_page"],
            )
            record["offsetR_at_join"] = float(off)
            record["right_time_shift_at_boundary"] = float(tsh)

        records.append(record)

    df = pd.DataFrame.from_records(records, columns=OUTPUT_COLUMNS)
    return df


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Collect Phase-2 training targets")
    parser.add_argument("--phase1-root", type=Path, default=DEFAULT_PHASE1_ROOT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--recompute-boundary",
        action="store_true",
        help="Ignore stored offsets/tshift and recompute to make right meet left at join.",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    phase1_root: Path = args.phase1_root
    out_csv: Path = args.out_csv

    if not phase1_root.exists():
        raise FileNotFoundError(f"Phase-1 root does not exist: {phase1_root}")

    df = collect_targets(phase1_root, args)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    df[["dataset", "tL_end", "offsetR_at_join", "right_time_shift_at_boundary"]].to_csv(
        out_csv.parent / "phase2_targets_align_debug.csv", index=False
    )

    write_run_meta(out_csv.parent, sys_argv())


def sys_argv() -> List[str]:
    import sys

    return list(sys.argv)


if __name__ == "__main__":
    main()

