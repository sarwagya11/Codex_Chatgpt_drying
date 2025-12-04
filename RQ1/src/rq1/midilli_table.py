"""Lookup and utilities for loading phase2C Midilli parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

PHASE2C_FILENAME = "phase2c_for_chamber.csv"
EXPECTED_COLUMNS = {
    "id",
    "T_C",
    "RH_mid_pct",
    "v_ms",
    "thickness_mm",
    "t_split",
    "kL",
    "nL",
    "bL_used",
    "is_page_L",
    "kR",
    "nR",
    "bR_used",
    "is_page_R",
    "offsetR_at_join",
    "right_time_shift_at_boundary",
}


@dataclass
class MidilliRow:
    """Container for a single row of the phase2c chamber table."""

    id: str
    T_C: float
    RH_mid_pct: float
    v_ms: float
    thickness_mm: float
    t_split: float
    kL: float
    nL: float
    bL_used: float
    is_page_L: bool
    kR: float
    nR: float
    bR_used: float
    is_page_R: bool
    offsetR_at_join: float
    right_time_shift_at_boundary: float

    @property
    def left_params(self) -> Mapping[str, float]:
        return {"k": self.kL, "n": self.nL, "b": self.bL_used}

    @property
    def right_params(self) -> Mapping[str, float]:
        return {"k": self.kR, "n": self.nR, "b": self.bR_used}


_table_cache: Dict[Path, Dict[str, MidilliRow]] = {}


def _ensure_bool(value: object) -> bool:
    return bool(int(value)) if isinstance(value, (int, np.integer)) else bool(value)


def _row_from_series(row: pd.Series) -> MidilliRow:
    return MidilliRow(
        id=str(row["id"]),
        T_C=float(row["T_C"]),
        RH_mid_pct=float(row["RH_mid_pct"]),
        v_ms=float(row["v_ms"]),
        thickness_mm=float(row["thickness_mm"]),
        t_split=float(row["t_split"]),
        kL=float(row["kL"]),
        nL=float(row["nL"]),
        bL_used=float(row["bL_used"]),
        is_page_L=_ensure_bool(row["is_page_L"]),
        kR=float(row["kR"]),
        nR=float(row["nR"]),
        bR_used=float(row["bR_used"]),
        is_page_R=_ensure_bool(row["is_page_R"]),
        offsetR_at_join=float(row["offsetR_at_join"]),
        right_time_shift_at_boundary=float(row["right_time_shift_at_boundary"]),
    )


def _validate_columns(df: pd.DataFrame) -> None:
    missing = EXPECTED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")


def load_midilli_rows(csv_path: Path | str) -> Dict[str, MidilliRow]:
    """Load Midilli rows from ``phase2c_for_chamber.csv`` and check ``id`` uniqueness."""

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    df = pd.read_csv(csv_path)
    _validate_columns(df)

    duplicates = df[df["id"].duplicated()]["id"].unique()
    if duplicates.size:
        dup_list = ", ".join(str(x) for x in duplicates)
        raise ValueError(f"Duplicate id entries found: {dup_list}")

    return {str(row["id"]): _row_from_series(row) for _, row in df.iterrows()}


def load_midilli_surfaces(models_root: Path | None) -> Dict[str, MidilliRow]:
    """Load and cache the chamber Midilli table."""

    if models_root is None:
        raise FileNotFoundError("models_root is required to resolve phase2c_for_chamber.csv")

    root = Path(models_root)
    csv_path = root / PHASE2C_FILENAME
    if csv_path not in _table_cache:
        _table_cache[csv_path] = load_midilli_rows(csv_path)
    return _table_cache[csv_path]


def _select_row_nearest(
    table: Mapping[str, MidilliRow],
    target: Iterable[float],
) -> MidilliRow:
    ordered_rows: Sequence[MidilliRow] = [table[key] for key in sorted(table.keys())]
    features = np.array(
        [
            [
                row.T_C,
                row.RH_mid_pct,
                row.v_ms,
                row.thickness_mm,
                row.t_split,
            ]
            for row in ordered_rows
        ],
        dtype=float,
    )
    target_arr = np.asarray(list(target), dtype=float)
    distances = np.sum((features - target_arr) ** 2, axis=1)
    best_idx = int(np.argmin(distances))
    return ordered_rows[best_idx]


def predict_midilli_params_for_operating_point(
    T_C: float,
    v_ms: float,
    thickness_mm: float,
    RH_mid_pct: float,
    t_split_min: float,
    models_root: Path | None,
    identifier: str | None = None,
) -> MidilliRow:
    """Select Midilli parameters from the cached table by ``identifier`` or nearest neighbor."""

    table = load_midilli_surfaces(models_root)
    if identifier is not None:
        try:
            return table[identifier]
        except KeyError as exc:
            raise KeyError(f"No Midilli row with id '{identifier}'") from exc

    return _select_row_nearest(table, (T_C, RH_mid_pct, v_ms, thickness_mm, t_split_min))


def midilli_curve(time: Iterable[float] | np.ndarray, k: float, n: float, b: float, is_page: bool) -> np.ndarray:
    """Evaluate the Midilli (or Page when ``is_page``) curve."""

    t = np.asarray(time, dtype=float)
    safe_t = np.maximum(t, 0.0)
    base = np.exp(-k * np.power(safe_t, n))
    return base if is_page else base + b * safe_t


def reconstruct_piecewise_mr(
    time_min: Iterable[float] | np.ndarray,
    row: MidilliRow,
    mr_floor: float = 0.0,
    mr_ceiling: float | None = 1.0,
) -> np.ndarray:
    """Reconstruct a piecewise Midilli curve using absolute time."""

    time_arr = np.asarray(time_min, dtype=float)
    MR_L = midilli_curve(time_arr, row.kL, row.nL, row.bL_used, row.is_page_L)

    MR_R_shifted = np.zeros_like(time_arr)
    right_mask = time_arr >= row.t_split
    if right_mask.any():
        right_times = np.maximum(time_arr[right_mask] + row.right_time_shift_at_boundary, 0.0)
        right_vals = midilli_curve(right_times, row.kR, row.nR, row.bR_used, row.is_page_R)
        MR_R_shifted[right_mask] = right_vals + row.offsetR_at_join

    MR_final = MR_L.copy()
    if right_mask.any():
        MR_final[right_mask] = np.minimum.accumulate(MR_R_shifted[right_mask])

    if mr_floor > 0:
        MR_final = np.maximum(MR_final, mr_floor)
    if mr_ceiling is not None:
        MR_final = np.minimum(MR_final, mr_ceiling)

    return MR_final


def evaluate_piecewise_midilli_MR(
    time_s: Iterable[float] | np.ndarray,
    params: MidilliRow,
    mr_floor: float = 0.0,
    mr_ceiling: float | None = 1.0,
) -> np.ndarray:
    """Evaluate MR(t) using ``params`` on a seconds grid."""

    time_min = np.asarray(time_s, dtype=float) / 60.0
    return reconstruct_piecewise_mr(time_min, params, mr_floor=mr_floor, mr_ceiling=mr_ceiling)


def X_db_from_MR(MR: Iterable[float] | np.ndarray, X0_db: float, X_eq_db: float) -> np.ndarray:
    """Convert moisture ratio to dry-basis moisture content."""

    MR_arr = np.asarray(MR, dtype=float)
    return X_eq_db + MR_arr * (X0_db - X_eq_db)


def build_keff_table_from_phase2(
    models_root: Path,
    X0_db: float,
    X_eq_db: float,
    max_time_s: float = 6 * 3600.0,
    dt_s: float = 60.0,
    mr_window: tuple[float, float] = (0.9, 0.5),
) -> pd.DataFrame:
    """
    Build an effective drying coefficient table K_eff(T,RH,v,d) from the Phase-2 Midilli rows.

    For each row in phase2c_for_chamber.csv:
      - reconstruct MR(t) on a 0..max_time_s grid with step dt_s using evaluate_piecewise_midilli_MR
      - convert MR(t) to X_db(t) using X0_db, X_eq_db
      - compute dX/dt using np.gradient
      - compute K_eff(t) = -(1 / (X_db - X_eq_db)) * dX/dt
      - restrict to times where MR is between mr_window[0] and mr_window[1] (e.g. 0.9..0.5)
      - take the mean K_eff over that window as a single representative K_eff for that operating point

    Returns a DataFrame with columns:
      ["T_C", "RH_mid_pct", "v_ms", "thickness_mm", "K_eff_1_per_s"].
    """

    phase2c_path = models_root / PHASE2C_FILENAME
    table = load_midilli_rows(phase2c_path)

    time_s = np.arange(0.0, max_time_s + dt_s, dt_s)
    rows_out: list[dict] = []

    for row in table.values():
        MR = evaluate_piecewise_midilli_MR(time_s, row)
        MR = np.clip(MR, 1e-6, 1.0)
        X_db = X_eq_db + MR * (X0_db - X_eq_db)
        dX_dt = np.gradient(X_db, time_s)
        with np.errstate(divide="ignore", invalid="ignore"):
            K_eff_t = -dX_dt / (X_db - X_eq_db)

        mask = (MR <= mr_window[0]) & (MR >= mr_window[1])
        if not np.any(mask):
            mask = (MR <= 0.99) & (MR >= 0.4)

        K_eff_vals = K_eff_t[mask]
        K_eff_vals = K_eff_vals[np.isfinite(K_eff_vals) & (K_eff_vals > 0)]
        if K_eff_vals.size == 0:
            continue

        K_eff_eff = float(np.mean(K_eff_vals))

        rows_out.append(
            {
                "T_C": row.T_C,
                "RH_mid_pct": row.RH_mid_pct,
                "v_ms": row.v_ms,
                "thickness_mm": row.thickness_mm,
                "K_eff_1_per_s": K_eff_eff,
            }
        )

    return pd.DataFrame(rows_out)
