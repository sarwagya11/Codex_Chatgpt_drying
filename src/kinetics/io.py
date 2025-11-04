# src/io.py

from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from typing import Any, Dict
from joblib import dump, load

def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")
    return pd.read_csv(path)

def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.8g")

def read_json(path: Path) -> dict:
    return json.loads(path.read_text())

def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def save_model(artifact: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dump(artifact, path)

def load_model(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    obj = load(path)
    if not isinstance(obj, dict) or "model" not in obj:
        raise ValueError(f"Malformed model file: {path}")
    return obj

def resolve_dataset_path(input_spec: str, data_root: Path) -> Path:
    candidate = data_root / input_spec
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Dataset not found in data/ folder: {input_spec}")
