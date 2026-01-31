"""Dataclasses for Phase-1 simulation configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass
class AmbientConfig:
    csv_path: Path
    start_index: int = 0
    max_steps: Optional[int] = None


@dataclass
class HeatPumpConfig:
    """Configuration for heat pump subsystem."""

    enabled: bool = True

    # Nominal capacity and COP at reference conditions
    Q_HP_nom_kW: float = 10.0
    COP_nom: float = 3.33

    # Reference conditions for nominal ratings (EN 14511 standard)
    T_source_nom_C: float = 7.0  # A7/W35 or A7/A35 rating
    T_sink_nom_C: float = 35.0

    # Carnot efficiency factor (typically 0.4-0.6 for real HP)
    eta_carnot: float = 0.50

    # Capacity degradation at low ambient
    T_defrost_C: float = 2.0  # Temperature below which defrost cycles occur
    capacity_degrade_per_C: float = 0.02  # 2% capacity loss per °C below T_source_nom

    # Minimum operating conditions
    T_source_min_C: float = -15.0  # HP shuts off below this
    T_sink_max_C: float = 60.0  # Maximum achievable outlet temperature
    T_lift_max_C: float = 50.0  # Maximum temperature lift

    # Source selection mode
    source_mode: Literal["ambient", "exhaust", "dual"] = "ambient"
    exhaust_recovery_fraction: float = 0.3  # Fraction of exhaust heat recoverable

    # Control parameters
    modulation_min: float = 0.3  # Minimum part-load ratio (30%)
    enable_capacity_limit: bool = True


@dataclass
class SolarCollectorConfig:
    """Configuration for flat-plate solar collector subsystem."""

    enabled: bool = True

    # Collector geometry
    A_col_m2: float = 10.0  # Collector area [m²]

    # Optical and thermal properties (typical flat-plate values)
    eta_optical: float = 0.75  # Optical efficiency (tau*alpha product)
    U_loss_W_per_m2K: float = 6.0  # Overall heat loss coefficient [W/(m²·K)]

    # Flow and operation
    collector_tilt_deg: float = 27.0  # Tilt angle (typically ~latitude)
    GHI_threshold_W_per_m2: float = 50.0  # Minimum GHI for operation

    # Temperature limits
    T_stagnation_C: float = 120.0  # Maximum collector temperature (no flow)
    T_fluid_max_C: float = 80.0  # Maximum outlet temperature

    # Incidence angle modifier (IAM) coefficients
    b0_IAM: float = 0.1  # First-order IAM coefficient

    # Heat removal factor (for air-based collectors)
    F_R: float = 0.85  # Heat removal factor (0.8-0.95 for good design)


@dataclass
class DryerConfig:
    r_recirc: float
    T_set_C: float
    X0_db: float
    X_eq_db: float
    m_p_dry_kg: float
    dt_s: float
    m_da_kg_per_s: float = 0.0
    h_fg_kJ_per_kg: float = 2400.0
    n_trays: int = 1

    # Optional geometry for diagnostics (not yet used for physics)
    tray_area_m2: float | None = None  # horizontal area per tray
    tray_depth_m: float | None = None  # flow depth / height of air above product
    air_density_kg_per_m3: float = 1.2  # used only for residence-time estimates

    product_thickness_m: float = 0.006  # Thickness of apple slices (6 mm)
    product_apparent_density_kg_per_m3: float = 600.0  # Bulk density
    max_trays: int = 4  # Maximum allowed tray count

    enable_tray_diagnostics: bool = True  # controls writing extra per-tray columns
    debug_checks: bool = False  # run lightweight monotonicity and RH checks

    # HP+Solar integration options
    require_all_trays_dried: bool = True  # Stricter termination: all trays MR < threshold
    MR_termination_threshold: float = 0.05  # MR threshold for termination
    allow_variable_Tset: bool = False  # True = no backup heater, accept HP+Solar temperature
    use_backup_heater: bool = True  # If False and allow_variable_Tset, T_in is variable


@dataclass
class KineticsConfig:
    mode: Literal["phase2_midilli", "first_order"] = "phase2_midilli"
    model_type: Literal["first_order", "midilli"] = "first_order"
    use_simple_K: bool = True
    use_knb_table: bool = True
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

    # Validity guardrails for Phase-2-derived kinetics
    T_min_valid_C: float = 40.0
    T_max_valid_C: float = 50.0
    T_soft_min_C: float = 35.0
    T_soft_max_C: float = 55.0

    RH_min_valid_pct: float = 25.0
    RH_max_valid_pct: float = 45.0
    RH_soft_min_pct: float = 20.0
    RH_soft_max_pct: float = 55.0
    RH_min_valid_frac: float = 0.25
    RH_max_valid_frac: float = 0.45

    # Valid box for Phase-2-derived K_eff usage
    keff_valid_T_min_C: float = 35.0
    keff_valid_T_max_C: float = 60.0
    keff_valid_RH_min_frac: float = 0.20
    keff_valid_RH_max_frac: float = 0.60

    Ea_over_R_K: float | None = 3839.0
    max_RH_scale: float = 1.5

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

    # Debugging
    debug_keff: bool = False


@dataclass
class SimulationConfig:
    ambient: AmbientConfig
    dryer: DryerConfig
    kinetics: KineticsConfig
    heat_pump: HeatPumpConfig = field(default_factory=HeatPumpConfig)
    solar: SolarCollectorConfig = field(default_factory=SolarCollectorConfig)
