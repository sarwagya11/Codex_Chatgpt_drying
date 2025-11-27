"""Ambient time-series loader for standardized CSV inputs."""

import pandas as pd

from .config import AmbientConfig


REQUIRED_COLUMNS = ["T_amb_C", "RH_amb_pct"]


def load_ambient_series(cfg: AmbientConfig) -> pd.DataFrame:
    """
    Load standardized ambient CSV and subset rows.

    Returns a DataFrame with at least:
    - 'time_index'
    - 'T_amb_C'
    - 'RH_amb_pct'
    - optional irradiance columns
    """

    df = pd.read_csv(cfg.csv_path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Ambient CSV missing required columns: {missing}")

    if "time_index" not in df.columns:
        df = df.reset_index().rename(columns={"index": "time_index"})

    start = cfg.start_index
    end = None if cfg.max_steps is None else start + cfg.max_steps
    df_subset = df.iloc[start:end].copy()

    if df_subset.empty:
        raise ValueError("Ambient DataFrame is empty after applying start_index/max_steps.")

    return df_subset
