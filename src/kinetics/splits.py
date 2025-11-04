# src/splits.py

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import json

def load_summary_index(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Summary index not found: {path}")
    return json.loads(path.read_text())

def list_leaf_segments(summary: dict) -> List[dict]:
    """Extract all leaf segments from a recursive split summary."""
    return summary.get("segments", [])

def get_segment_bounds(segment: dict) -> Tuple[float, float]:
    """Return the [start, end] time of a segment."""
    return float(segment["segment_start_time"]), float(segment["segment_end_time"])

def compute_split_gaps(segments: List[dict]) -> List[Tuple[int, float]]:
    """
    For consecutive segments, compute time gaps (discontinuity) between end of one and start of next.
    Returns list of (i, gap) where i is segment index.
    """
    gaps = []
    for i in range(1, len(segments)):
        _, prev_end = get_segment_bounds(segments[i - 1])
        curr_start, _ = get_segment_bounds(segments[i])
        gap = curr_start - prev_end
        gaps.append((i, gap))
    return gaps

def group_by_dataset(segments: List[dict]) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {}
    for row in segments:
        key = row.get("dataset_name", "unknown")
        grouped.setdefault(key, []).append(row)
    return grouped
