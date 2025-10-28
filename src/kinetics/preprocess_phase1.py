"""Preprocessing utilities for the phase-1 drying kinetics pipeline."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.switch_backend("Agg")

__all__ = ["PreprocessResult", "load_and_preprocess", "save_preprocess_artifacts"]


@dataclass
class PreprocessResult:
    """Container for preprocessed moisture-ratio data."""

    source_path: Path
    time_min: np.ndarray
    mr_raw: np.ndarray
    mr_iso: np.ndarray
    head_trim_min: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def trimmed(self) -> bool:
        return bool(self.head_trim_min and self.head_trim_min > 0)

    def to_jsonable(self) -> Dict[str, object]:
        return {
            "source_path": str(self.source_path),
            "head_trim_min": self.head_trim_min,
            "metadata": _json_safe(self.metadata),
        }


def load_and_preprocess(
    input_path: Path | str, head_trim_min: float = 0.0
) -> PreprocessResult:
    """Load a drying dataset and generate the monotone MR series."""

    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input dataset not found: {path}")

    df = _load_tabular(path)
    df = df.copy()

    time_col = _select_time_column(df.columns)
    if time_col is None:
        raise ValueError("Dataset must contain a time column (e.g., 'time_min').")
    time = df[time_col].astype(float).to_numpy()

    if head_trim_min and head_trim_min > 0:
        mask = time >= head_trim_min
        df = df.loc[mask].reset_index(drop=True)
        time = df[time_col].astype(float).to_numpy()

    mr_raw = _compute_moisture_ratio(df)
    mr_iso = _isotonic_decreasing(time, mr_raw)

    metadata = _collect_metadata(df, path)
    metadata["hints"] = _extract_hints(path, df)

    return PreprocessResult(
        source_path=path,
        time_min=time,
        mr_raw=mr_raw,
        mr_iso=mr_iso,
        head_trim_min=float(head_trim_min or 0.0),
        metadata=metadata,
    )


def save_preprocess_artifacts(
    result: PreprocessResult, plots_dir: Path, filename_prefix: str
) -> Path:
    """Write raw vs isotonic MR comparison plot to disk."""

    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plots_dir / f"{filename_prefix}.png"

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(result.time_min, result.mr_raw, "o", label="MR raw", alpha=0.7)
    ax.plot(result.time_min, result.mr_iso, "-", label="MR iso", linewidth=2)
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Moisture ratio")
    ax.set_title("MR raw vs isotonic-smoothed")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)
    return plot_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_tabular(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _select_time_column(columns: Iterable[str]) -> Optional[str]:
    for candidate in columns:
        lower = candidate.lower()
        if "time" in lower and ("min" in lower or "_min" in lower):
            return candidate
    for candidate in columns:
        if candidate.lower().startswith("time"):
            return candidate
    return None


def _compute_moisture_ratio(df: pd.DataFrame) -> np.ndarray:
    mr_columns = [c for c in df.columns if c.lower().startswith("mr")]
    if mr_columns:
        mr = df[mr_columns[0]].astype(float).to_numpy()
        return np.clip(mr, 0.0, 1.1)

    x_candidates = [
        c
        for c in df.columns
        if c.lower().startswith("x_") or c.lower() in {"x", "x_db", "moisture"}
    ]
    if not x_candidates:
        raise ValueError("Dataset must contain MR or dry-basis moisture content columns.")

    x_vals = df[x_candidates[0]].astype(float).to_numpy()
    x0 = float(x_vals[0]) if len(x_vals) else 1.0
    if not math.isfinite(x0) or x0 == 0:
        raise ValueError("Initial moisture content must be finite and non-zero.")
    mr = np.clip(x_vals / x0, 0.0, 1.1)
    return mr


def _isotonic_decreasing(time: np.ndarray, mr_raw: np.ndarray) -> np.ndarray:
    order = np.argsort(time)
    sorted_mr = mr_raw[order]
    # Apply pool-adjacent-violators on reversed scale for monotone decreasing.
    y = sorted_mr.astype(float).copy()
    blocks: List[Tuple[float, int]] = []  # (average, size)

    for value in y:
        blocks.append((value, 1))
        _enforce_monotone(blocks)

    monotone = np.concatenate([
        np.full(size, avg) for avg, size in blocks
    ])

    # Re-map to original order
    result = np.empty_like(monotone)
    result[order] = monotone
    return result


def _enforce_monotone(blocks: List[Tuple[float, int]]) -> None:
    while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
        avg1, n1 = blocks.pop()
        avg0, n0 = blocks.pop()
        merged_n = n0 + n1
        merged_avg = (avg0 * n0 + avg1 * n1) / merged_n
        blocks.append((merged_avg, merged_n))


def _collect_metadata(df: pd.DataFrame, path: Path) -> Dict[str, object]:
    metadata: Dict[str, object] = {
        "n_obs": int(len(df)),
        "columns": list(df.columns),
    }
    metadata.update({
        "time_column": _select_time_column(df.columns),
    })
    for column in ["T_C", "v_ms", "RH_pct", "thickness_mm", "run_id"]:
        if column in df.columns:
            first_valid = df[column].dropna().iloc[0] if df[column].notna().any() else None
            metadata[column] = first_valid
    metadata["source_name"] = path.name
    return metadata


def _extract_hints(path: Path, df: pd.DataFrame) -> Dict[str, Optional[float]]:
    hints: Dict[str, Optional[float]] = {
        k: None for k in ["T_C", "T_K", "v_ms", "RH_pct", "RH_frac", "thickness_mm"]
    }

    # Prefer explicit columns when available.
    for key in hints:
        if key in df.columns and df[key].notna().any():
            value = float(df[key].dropna().iloc[0])
            hints[key] = value
            if key == "T_C":
                hints["T_K"] = value + 273.15
            if key == "RH_pct":
                hints["RH_frac"] = value / 100.0

    stem = path.stem
    tokens = stem.replace("-", "_").split("_")
    for token in tokens:
        if token.upper().startswith("T") and token[1:].replace("p", "").isdigit():
            hints.setdefault("T_C", None)
            t_c = _token_to_float(token[1:])
            if t_c is not None:
                hints["T_C"] = t_c
                hints["T_K"] = t_c + 273.15
        elif token.lower().startswith("rh"):
            num = token.split("rh")[-1]
            num = num.replace("pct", "").replace("%", "")
            if num:
                rh = _token_to_float(num)
                if rh is not None:
                    hints["RH_pct"] = rh
                    hints["RH_frac"] = rh / 100.0
        elif token.lower().startswith("v") and any(ch.isdigit() for ch in token):
            hints["v_ms"] = _token_to_float(token[1:])
        elif token.lower().startswith("t") and token.lower().endswith("mm"):
            num = token[1:-2]
            if any(ch.isdigit() for ch in num):
                hints["thickness_mm"] = _token_to_float(num)

    # If relative humidity is encoded as a range (e.g., 25-28)
    if "rh" in stem.lower() and hints.get("RH_pct") is None:
        import re

        matches = re.findall(r"rh[_-]?(\d+)[_-]?(\d+)?", stem.lower())
        if matches:
            for lo, hi in matches:
                lo_val = _token_to_float(lo)
                hi_val = _token_to_float(hi) if hi else None
                if lo_val is not None and hi_val is not None:
                    rh = (lo_val + hi_val) / 2.0
                    hints["RH_pct"] = rh
                    hints["RH_frac"] = rh / 100.0
                elif lo_val is not None:
                    hints["RH_pct"] = lo_val
                    hints["RH_frac"] = lo_val / 100.0

    if hints["T_C"] is not None and hints["T_K"] is None:
        hints["T_K"] = hints["T_C"] + 273.15
    if hints["RH_pct"] is not None and hints["RH_frac"] is None:
        hints["RH_frac"] = hints["RH_pct"] / 100.0

    return hints


def _token_to_float(token: str) -> Optional[float]:
    token = token.strip().lower().replace("p", ".")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _json_safe(value):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_json_safe(v) for v in value)
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
    except Exception:  # pragma: no cover - numpy may be unavailable in rare envs
        pass
    return value
