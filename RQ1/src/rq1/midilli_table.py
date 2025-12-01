"""Utility helpers for evaluating Midilli curves from a parameter table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class MidilliParams:
    """Container for Midilli parameters."""

    k: float
    n: float
    b: float

    def evaluate_MR(self, time_min: Iterable[float], mr_floor: float = 0.0) -> np.ndarray:
        """Return MR(t) on the supplied time grid (in minutes)."""

        t_arr = np.asarray(time_min, dtype=float)
        MR = np.exp(-self.k * np.power(np.maximum(t_arr, 0.0), self.n)) + self.b * np.maximum(t_arr, 0.0)
        return np.maximum(MR, mr_floor)


def load_midilli_row(table_csv: Path, row_id: int) -> MidilliParams:
    """Load a single Midilli parameter row from ``table_csv`` by integer index."""

    df = pd.read_csv(table_csv)
    if row_id < 0 or row_id >= len(df):
        raise IndexError(f"row_id {row_id} is out of bounds for table of length {len(df)}")

    row = df.iloc[row_id]
    return MidilliParams(k=float(row["k"]), n=float(row["n"]), b=float(row.get("b", 0.0)))


def X_db_from_MR(MR: np.ndarray, X0_db: float, X_eq_db: float) -> np.ndarray:
    """Convert moisture ratio array to dry-basis moisture content."""

    return X_eq_db + np.asarray(MR, dtype=float) * (X0_db - X_eq_db)
