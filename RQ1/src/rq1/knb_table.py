"""Nearest-neighbor lookup for Midilli k, n, b parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

REQUIRED_COLS = ["T_C", "RH_pct", "v_ms", "thickness_mm", "k", "n", "b"]


class KNBTable:
    """Load Midilli parameter grid and provide nearest-neighbor lookup."""

    def __init__(self, csv_path: Path):
        self.df = pd.read_csv(csv_path)
        missing = [c for c in REQUIRED_COLS if c not in self.df.columns]
        if missing:
            raise ValueError(f"KNB CSV missing columns: {missing}")

    def get_knb_nearest(
        self,
        T_C: float,
        RH_pct: float,
        v_ms: float,
        thickness_mm: float,
    ) -> Tuple[float, float, float]:
        """
        Return (k, n, b) for the nearest neighbor in (T_C, RH_pct, v_ms, thickness_mm) space.
        """

        targets = np.array([T_C, RH_pct, v_ms, thickness_mm])
        features = self.df[["T_C", "RH_pct", "v_ms", "thickness_mm"]].to_numpy()
        diffs = features - targets
        distances = np.sum(diffs ** 2, axis=1)
        idx = int(np.argmin(distances))
        row = self.df.iloc[idx]
        return float(row["k"]), float(row["n"]), float(row["b"])
