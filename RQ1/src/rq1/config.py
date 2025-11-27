"""Dataclasses for Phase-1 simulation configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AmbientConfig:
    csv_path: Path
    start_index: int = 0
    max_steps: Optional[int] = None


@dataclass
class DryerConfig:
    m_da_kg_per_s: float
    r_recirc: float
    T_set_C: float
    X0_db: float
    X_eq_db: float
    m_p_dry_kg: float
    dt_s: float
    h_fg_kJ_per_kg: float = 2400.0


@dataclass
class KineticsConfig:
    use_simple_K: bool = True
    use_knb_table: bool = False
    knb_csv_path: Optional[Path] = None


@dataclass
class SimulationConfig:
    ambient: AmbientConfig
    dryer: DryerConfig
    kinetics: KineticsConfig
