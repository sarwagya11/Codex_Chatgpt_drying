"""Dataclasses for Phase-1 simulation configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


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
    mode: Literal["phase2_midilli", "first_order"] = "phase2_midilli"
    model_type: Literal["first_order", "midilli"] = "first_order"
    use_simple_K: bool = True
    use_knb_table: bool = False
    knb_csv_path: Optional[Path] = None

    # Existing first-order parameters
    K_ref_1_per_s: float = 1e-4
    K_min_1_per_s: float = 1e-6
    T_ref_C: float = 50.0
    alpha_T_per_C: float = 0.05
    alpha_RH: float = 2.0

    # Air capacity / RH-out controls
    RH_out_max_frac: float = 0.95  # max allowed outlet RH in the chamber
    min_domega_drive: float = 1e-4
    enable_air_limit: bool = True

    # Operating point metadata for Midilli lookup
    v_ms: float = 1.0
    thickness_mm: float = 6.0

    # Phase-2 integration
    phase2_models_root: Optional[Path] = None
    # Reference conditions for K_eff lookup when v, thickness are not explicit in Phase-1
    v_ms_ref: float = 1.1
    thickness_mm_ref: float = 6.0
    # Reference moisture levels used for K_eff extraction
    X0_db_ref: float = 2.5
    X_eq_db_ref: float = 0.05
    T_C_ref: float = 50.0
    RH_lo_pct_ref: float = 30.0
    RH_hi_pct_ref: float = 40.0
    t_split_min_ref: float = 60.0


@dataclass
class SimulationConfig:
    ambient: AmbientConfig
    dryer: DryerConfig
    kinetics: KineticsConfig
