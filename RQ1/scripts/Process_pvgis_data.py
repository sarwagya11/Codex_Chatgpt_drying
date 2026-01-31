"""Convert PVGIS TMY CSV to standardized ambient format."""

import argparse
from pathlib import Path
import pandas as pd
from datetime import datetime
import json
import time


def parse_pvgis_time(time_str: str) -> datetime:
    """Convert PVGIS time format '20050101:0010' to datetime."""
    # Format: YYYYMMdd:HHMM
    date_part = time_str[:8]  # 20050101
    time_part = time_str[9:]  # 0010
    
    year = int(date_part[:4])
    month = int(date_part[4:6])
    day = int(date_part[6:8])
    hour = int(time_part[:2])
    minute = int(time_part[2:4])
    
    return datetime(year, month, day, hour, minute)


# #region agent log
def _log(hypothesisId: str, location: str, message: str, data: dict):
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": "pvgis-header-fix",
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(r"d:\Masters\RQ5\Codex_Chatgpt_drying\.cursor\debug.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        # Never fail the pipeline due to logging
        pass
# #endregion agent log


def _looks_like_time_header(line: str) -> bool:
    """Return True if line is a PVGIS data header (first column is time/time(UTC)/etc.)."""
    raw = line.strip().lstrip("\ufeff")  # handle UTF-8 BOM if present
    if not raw:
        return False
    # PVGIS can be comma-separated or tab-separated; we just check the first token
    if "," in raw:
        first = raw.split(",", 1)[0].strip().lower()
    elif "\t" in raw:
        first = raw.split("\t", 1)[0].strip().lower()
    else:
        return False
    # accept: time, time(utc), time(UTC), time (UTC), etc.
    return first.startswith("time")


def process_pvgis_file(input_path: Path, output_path: Path, location_name: str):
    """
    Process raw PVGIS CSV to standardized format.
    
    Parameters
    ----------
    input_path : Path
        Path to raw PVGIS CSV (e.g., kathmandu_pvgis_raw.csv)
    output_path : Path
        Path to write standardized CSV
    location_name : str
        Location identifier (e.g., 'kathmandu')
    """
    
    # Read PVGIS file, skipping header lines
    # PVGIS typically has 10-16 header lines before data starts
    # We'll detect where data starts by looking for 'time' column
    
    _log("A", "Process_pvgis_data.py:process_pvgis_file", "start", {"input_path": str(input_path), "output_path": str(output_path), "location": location_name})

    with open(input_path, 'r', encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    
    # Find line with column headers (contains time*,T2m,RH,...)
    header_line_idx = None
    header_line = None
    for i, line in enumerate(lines):
        if _looks_like_time_header(line):
            header_line_idx = i
            header_line = line.strip()
            break
    _log("A", "Process_pvgis_data.py:process_pvgis_file", "header_scan_result", {"header_line_idx": header_line_idx, "header_line": header_line})
    
    if header_line_idx is None:
        _log("A", "Process_pvgis_data.py:process_pvgis_file", "header_not_found", {"first_5_lines": [l.strip() for l in lines[:5]]})
        raise ValueError(f"Could not find header line in {input_path}")
    
    # Read data starting from header line
    df_raw = pd.read_csv(input_path, skiprows=header_line_idx)
    _log("B", "Process_pvgis_data.py:process_pvgis_file", "raw_columns", {"columns": df_raw.columns.tolist()})
    
    print(f"\n{'='*60}")
    print(f"Processing: {location_name}")
    print(f"{'='*60}")
    print(f"Raw data shape: {df_raw.shape}")
    print(f"Columns found: {df_raw.columns.tolist()}")
    
    # Parse datetime (PVGIS commonly uses 'time(UTC)' not 'time')
    time_col = None
    for cand in ("time", "time(UTC)", "time(utc)", "time_utc", "Time", "TIME"):
        if cand in df_raw.columns:
            time_col = cand
            break
    if time_col is None:
        # fallback: first column if it starts with "time"
        first_col = str(df_raw.columns[0])
        if first_col.lower().startswith("time"):
            time_col = first_col
    _log("B", "Process_pvgis_data.py:process_pvgis_file", "time_column_selected", {"time_col": time_col})
    if time_col is None:
        raise ValueError(f"Could not identify time column. Columns: {df_raw.columns.tolist()}")

    # PVGIS exports often include footer metadata lines after the 8760 rows.
    # Filter to rows that look like timestamps: YYYYMMDD:HHMM
    time_series = df_raw[time_col].astype(str).str.strip()
    valid_time = time_series.str.match(r"^\d{8}:\d{4}$", na=False)
    n_invalid = int((~valid_time).sum())
    if n_invalid:
        _log("B", "Process_pvgis_data.py:process_pvgis_file", "dropping_non_data_rows", {"n_invalid": n_invalid})
        df_raw = df_raw.loc[valid_time].copy()
        time_series = time_series.loc[valid_time]

    df_raw['datetime'] = time_series.apply(parse_pvgis_time)

    # Coerce key columns to numeric (PVGIS files can include mixed types / strings).
    for col in ["T2m", "RH", "G(h)", "WS10m", "Gd(h)", "Gb(n)", "SP"]:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")
    
    # Create standardized DataFrame
    df_standard = pd.DataFrame({
        'time_index': range(len(df_raw)),
        'datetime': df_raw['datetime'],
        'T_amb_C': df_raw['T2m'],
        'RH_amb_pct': df_raw['RH'],
        'GHI_Wm2': df_raw['G(h)'],
        'wind_speed_ms': df_raw['WS10m'],
    })
    _log("C", "Process_pvgis_data.py:process_pvgis_file", "standard_columns_preview", {"head": df_standard.head(2).to_dict(orient="records")})
    
    # Optional: Add other useful columns if available
    if 'Gd(h)' in df_raw.columns:
        df_standard['DIF_Wm2'] = df_raw['Gd(h)']  # Diffuse irradiance
    
    if 'Gb(n)' in df_raw.columns:
        df_standard['DNI_Wm2'] = df_raw['Gb(n)']  # Direct normal irradiance
    
    if 'SP' in df_raw.columns:
        df_standard['pressure_Pa'] = df_raw['SP']
    
    # Data quality checks
    print(f"\nData Quality Report:")
    print(f"  Total rows: {len(df_standard)}")
    print(f"  Expected: 8760 (hourly for one year)")
    # Avoid unicode degree symbols on some Windows consoles
    print(f"  Temperature range: {df_standard['T_amb_C'].min():.1f} to {df_standard['T_amb_C'].max():.1f} C")
    print(f"  RH range: {df_standard['RH_amb_pct'].min():.1f} to {df_standard['RH_amb_pct'].max():.1f} %")
    print(f"  GHI max: {df_standard['GHI_Wm2'].max():.0f} W/m2")
    print(f"  Missing values:")
    for col in df_standard.columns:
        n_missing = df_standard[col].isna().sum()
        if n_missing > 0:
            print(f"    {col}: {n_missing}")
    
    # Save standardized file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_standard.to_csv(output_path, index=False)
    _log("C", "Process_pvgis_data.py:process_pvgis_file", "saved", {"output_path": str(output_path), "rows": int(len(df_standard))})
    
    print(f"\nSaved to: {output_path}")
    print(f"{'='*60}\n")
    
    return df_standard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Path to raw PVGIS CSV'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Path for standardized output CSV'
    )
    parser.add_argument(
        '--location',
        type=str,
        required=True,
        help='Location name (e.g., kathmandu)'
    )
    
    args = parser.parse_args()
    
    process_pvgis_file(args.input, args.output, args.location)


if __name__ == '__main__':
    main()