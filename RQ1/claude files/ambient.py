"""Ambient time-series loader for standardized CSV inputs."""

import pandas as pd

from .config import AmbientConfig


REQUIRED_COLUMNS = ["T_amb_C", "RH_amb_pct"]
OPTIONAL_COLUMNS = ["GHI_Wm2", "wind_speed_ms", "datetime"]


def load_ambient_series(cfg: AmbientConfig) -> pd.DataFrame:
    """
    Load standardized ambient CSV and subset rows.

    Returns a DataFrame with at least:
    - 'time_index'
    - 'T_amb_C'
    - 'RH_amb_pct'
    - optional: 'GHI_Wm2' (solar irradiance)
    - optional: 'wind_speed_ms'
    - optional: 'datetime'
    """

    df = pd.read_csv(cfg.csv_path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Ambient CSV missing required columns: {missing}")

    if "time_index" not in df.columns:
        df = df.reset_index().rename(columns={"index": "time_index"})

    # Handle GHI column with various possible names
    ghi_aliases = ["GHI_Wm2", "G_hor_Wm2", "GHI", "ghi", "G(i)"]
    ghi_found = False
    for alias in ghi_aliases:
        if alias in df.columns and "GHI_Wm2" not in df.columns:
            df["GHI_Wm2"] = df[alias]
            ghi_found = True
            break
        elif alias == "GHI_Wm2" and alias in df.columns:
            ghi_found = True
            break

    if not ghi_found:
        # Create zero GHI column if not present (for backward compatibility)
        df["GHI_Wm2"] = 0.0

    start = cfg.start_index
    end = None if cfg.max_steps is None else start + cfg.max_steps
    df_subset = df.iloc[start:end].copy()

    if df_subset.empty:
        raise ValueError("Ambient DataFrame is empty after applying start_index/max_steps.")

    return df_subset
