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
    model_type: Literal["first_order", "midilli"] = "first_order"
    mode: str = "first_order"  # "first_order" or "phase2_midilli"
    use_simple_K: bool = True
    use_knb_table: bool = False
    knb_csv_path: Optional[Path] = None

    # Air-side limitation
    enable_air_limit: bool = True
    RH_out_max_frac: float = 0.95  # max allowed outlet RH in the chamber
    # Safety: minimum allowed driving force in humidity ratio [kg/kg]
    min_domega_drive: float = 1e-4

    # Temperature-RH dependence of K
    K_ref_1_per_s: float = 1e-4
    T_ref_C: float = 50.0
    alpha_T_per_C: float = 0.05
    alpha_RH: float = 1.5

    # Operating point metadata for Midilli lookup
    v_ms: float = 1.0
    thickness_mm: float = 6.0

    # Phase-2 Midilli settings
    phase2_models_root: Optional[Path] = None
    T_C_ref: float = 50.0
    RH_lo_pct_ref: float = 30.0
    RH_hi_pct_ref: float = 40.0
    v_ms_ref: float = 1.1
    thickness_mm_ref: float = 6.0


@dataclass
class SimulationConfig:
    ambient: AmbientConfig
    dryer: DryerConfig
    kinetics: KineticsConfig
