"""Extended configuration system for solar-assisted heat pump dryer.

UPDATED VERSION with Multi-Zone Support
========================================

This file REPLACES your existing config_solar_hp.py

Changes from original:
1. Added imports for chamber_geometry module
2. Updated DryerConfig with geometry parameters
3. Added MultiZoneConfig integration
4. Added geometry calculation in SimulationConfig.__post_init__
5. Updated all make_config_* functions to support multi-zone

Integrates:
- Ambient weather data
- Solar thermal collector
- Heat pump thermodynamics
- Multi-tray drying chamber (single or multi-zone)
- Phase-2 Midilli kinetics
- Chamber geometry calculations

Author: Wasti (SAHPD Thesis)
Date: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, List

# Import chamber geometry module removed - single-inlet only


class DryerConfiguration(str, Enum):
    """Five dryer configurations to simulate."""
    
    CONFIG_A = "A_HP_only"  # Heat pump only, 24/7
    CONFIG_B = "B_solar_HP_series"  # Solar → HP condenser (series boost)
    CONFIG_C = "C_solar_HP_evap"  # Solar → HP evaporator (COP boost)
    CONFIG_D = "D_solar_only"  # Solar only, no HP
    CONFIG_E = "E_solar_evap_cond_cascade"  # Solar → HP evap → HP cond (your design)


@dataclass
class AmbientConfig:
    """Ambient weather data configuration."""
    
    csv_path: Path
    start_index: int = 0
    max_steps: Optional[int] = None
    
    # Column names in CSV
    time_col: str = "datetime"
    temp_col: str = "T_amb_C"
    rh_col: str = "RH_amb_pct"
    ghi_col: str = "G_hor_Wm2"
    wind_col: Optional[str] = None
    pressure_col: Optional[str] = None
    
    # Default values if columns missing
    default_pressure_Pa: float = 101325.0
    default_wind_speed_m_per_s: float = 1.0


@dataclass
class SolarConfig:
    """Solar collector configuration."""
    
    area_m2: float = 10.0
    eta_optical: float = 0.75
    K_theta: float = 1.0
    U_loss_W_per_m2K: float = 5.0
    C_collector_kJ_per_K: float = 10.0
    T_stagnation_max_C: float = 150.0
    T_min_useful_C: float = 5.0
    enabled: bool = True


@dataclass
class HeatPumpConfig:
    """Heat pump configuration."""
    
    refrigerant: str = "R134a"
    eta_isentropic: float = 0.75
    eta_mechanical: float = 0.95
    superheat_K: float = 5.0
    subcooling_K: float = 5.0
    epsilon_evap: float = 0.85
    epsilon_cond: float = 0.85
    T_evap_min_C: float = -15.0
    T_evap_max_C: float = 20.0
    T_cond_min_C: float = 30.0
    T_cond_max_C: float = 70.0
    COP_min: float = 2.0
    pressure_ratio_max: float = 8.0
    T_approach_evap_K: float = 10.0
    T_approach_cond_K: float = 10.0
    allow_modulation: bool = True
    modulation_min_pct: float = 30.0
    enabled: bool = True


@dataclass
class DryerConfig:
    """Drying chamber configuration.
    
    UPDATED with explicit geometry parameters and multi-zone support.
    
    KEY VARIABLES YOU CAN CHANGE:
    ─────────────────────────────
    m_p_dry_kg:            Dry mass of product [kg]
                           → Fresh mass = m_dry × (1 + X0_db)
                           → Current: 10.0 kg dry = 75 kg fresh apples
    
    X0_db:                 Initial moisture content [kg water / kg dry]
                           → For fresh apples: ~6.5 (87% wet basis)
    
    n_trays:               Number of trays
                           → More trays = more non-uniformity
    
    loading_density_kg_m2: Loading density [kg fresh / m²]
                           → Typical: 3-5 kg/m² for 6mm apple slices
    
    target_velocity_m_s:   Target air velocity [m/s]
                           → Typical: 0.8-1.5 m/s
                           → Higher = faster drying, more fan power
    
    air_gap_m:             Vertical gap between trays [m]
                           → Typical: 0.05-0.10 m
    
    HOW AIR MASS FLOW RATE IS CALCULATED:
    ─────────────────────────────────────
    The mass flow rate is calculated to achieve the target velocity:
    
        Cross-section area: A_cross = tray_width × air_gap
        Mass flow rate:     m_da = ρ_air × v_target × A_cross
    
    Example (your 75 kg batch):
        Tray width:     1.225 m
        Air gap:        0.08 m
        A_cross:        0.098 m²
        ρ_air:          1.1 kg/m³ (at 50°C)
        v_target:       1.1 m/s
        m_da:           1.1 × 1.1 × 0.098 = 0.119 kg/s = 428 kg/h
    """
    
    # Target conditions
    T_set_C: float = 50.0
    T_set_tolerance_C: float = 2.0
    
    # =========================================================================
    # PRODUCT PARAMETERS (KEY VARIABLES YOU CAN CHANGE)
    # =========================================================================
    X0_db: float = 6.5           # Initial moisture [kg water/kg dry]
    X_final_db: float = 0.10     # Target final moisture [kg water/kg dry]
    X_eq_db: float = 0.0         # Equilibrium moisture (use 0 per your request)
    m_p_dry_kg: float = 10.0     # Dry mass [kg] → 75 kg fresh at X0=6.5
    
    # Product properties
    product_thickness_m: float = 0.006  # 6 mm apple slices
    product_apparent_density_kg_per_m3: float = 600.0
    
    # =========================================================================
    # TRAY CONFIGURATION
    # =========================================================================
    n_trays: int = 10
    max_trays: int = 10
    loading_density_kg_m2: float = 5.0   # kg fresh per m² (NEW - explicit)
    
    # =========================================================================
    # GEOMETRY PARAMETERS (NEW - for proper air flow calculation)
    # =========================================================================
    # These are calculated automatically from product specs if set to 0
    tray_length_m: float = 0.0           # Auto-calculated if 0
    tray_width_m: float = 0.0            # Auto-calculated if 0
    tray_area_m2: Optional[float] = None # Horizontal area per tray
    air_gap_m: float = 0.08              # 8 cm gap between trays
    tray_frame_m: float = 0.02           # 2 cm tray frame thickness
    
    # Chamber dimensions (calculated)
    chamber_height_m: float = 0.0
    chamber_length_m: float = 0.0
    chamber_width_m: float = 0.0
    
    # =========================================================================
    # AIR FLOW PARAMETERS
    # =========================================================================
    # Air flow rate: if 0, calculated from target_velocity
    m_da_kg_per_s: float = 0.0           # Auto-calculated from velocity
    target_velocity_m_s: float = 1.1     # Target air velocity [m/s]
    air_density_kg_per_m3: float = 1.1   # At ~50°C
    
    # Convenience (for backward compatibility)
    tray_depth_m: float = 0.05
    
    # Thermodynamic
    h_fg_kJ_per_kg: float = 2400.0
    
    # Timestep
    dt_s: float = 60.0
    
    # Recirculation (DISABLED per user request)
    r_recirc: float = 0.0
    
    # =========================================================================
    # MULTI-ZONE CONFIGURATION (DISABLED - single-inlet only)
    # =========================================================================
    # multizone: MultiZoneConfig = field(default_factory=MultiZoneConfig)
    
    # Diagnostics
    enable_tray_diagnostics: bool = True
    debug_checks: bool = False
    
    # =========================================================================
    # CALCULATED PROPERTIES
    # =========================================================================
    
    @property
    def m_fresh_kg(self) -> float:
        """Calculate fresh product mass from dry mass and initial moisture."""
        return self.m_p_dry_kg * (1 + self.X0_db)
    
    @property
    def m_water_to_remove_kg(self) -> float:
        """Calculate total water to be removed."""
        m_water_initial = self.m_p_dry_kg * self.X0_db
        m_water_final = self.m_p_dry_kg * self.X_final_db
        return m_water_initial - m_water_final
    
    def get_tray_pitch_m(self) -> float:
        """Calculate tray-to-tray vertical spacing."""
        return self.product_thickness_m + self.tray_frame_m + self.air_gap_m
    
    def get_cross_section_m2(self) -> float:
        """Calculate air flow cross-sectional area."""
        return self.tray_width_m * self.air_gap_m


@dataclass
class KineticsConfig:
    """Drying kinetics configuration."""

    mode: Literal["phase2_midilli"] = "phase2_midilli"
    model_type: str = "midilli"
    phase2_models_root: Optional[Path] = None
    fallback_to_page: bool = True
    use_knb_table: bool = False  # Use pre-computed k,n,b table (fallback mode)
    knb_csv_path: Optional[Path] = None

    # Reference conditions
    T_ref_C: float = 50.0
    T_C_ref: float = 50.0  # Alias for T_ref_C
    v_ref_m_per_s: float = 1.1
    v_ms_ref: float = 1.1  # Alias for v_ref_m_per_s
    v_ms: float = 1.1
    X0_db_ref: float = 6.5
    X_eq_db_ref: float = 0.0
    thickness_ref_mm: float = 6.0
    thickness_mm_ref: float = 6.0  # Alias for thickness_ref_mm
    thickness_mm: float = 6.0
    RH_ref_pct: float = 30.0
    RH_lo_pct_ref: float = 25.0
    RH_hi_pct_ref: float = 35.0
    t_split_h: float = 2.0
    t_split_min_ref: float = 120.0  # 2 hours in minutes

    # Kinetic parameters (fallback mode)
    K_ref_1_per_s: float = 1e-4  # 0.0001
    K_min_1_per_s: float = 1e-6
    alpha_T_per_C: float = 0.05
    alpha_RH: float = 2.0

    # Valid ranges (hard limits)
    T_min_valid_C: float = 30.0
    T_max_valid_C: float = 70.0
    RH_min_valid_frac: float = 0.1
    RH_max_valid_frac: float = 0.9
    RH_min_valid_pct: float = 10.0
    RH_max_valid_pct: float = 90.0

    # Soft limits (for scaling)
    T_soft_min_C: float = 40.0
    T_soft_max_C: float = 60.0
    RH_soft_min_pct: float = 20.0
    RH_soft_max_pct: float = 50.0

    # Extrapolation parameters
    use_arrhenius_extrapolation: bool = True
    E_a_kJ_per_mol: float = 30.0
    Ea_over_R_K: float = 3609.0  # E_a / R where R = 8.314 J/(mol·K)
    T_ref_arrhenius_C: float = 50.0
    max_RH_scale: float = 2.0

    # Correction factors
    use_velocity_correction: bool = True
    velocity_exponent: float = 0.5
    use_RH_correction: bool = True
    RH_sensitivity: float = 0.005
    use_thickness_correction: bool = True
    thickness_exponent: float = 2.0

    # Limits
    k_eff_min: float = 1e-6
    k_eff_max: float = 0.1
    RH_out_max_frac: float = 0.95
    min_domega_drive: float = 1e-4
    enable_air_limit: bool = True  # MUST be enabled for correct temperature profiles
    debug_keff: bool = False  # Disable verbose logging
@dataclass
class SimulationConfig:
    """Complete simulation configuration for one run.
    
    This is the main configuration object that combines all sub-configs.
    The __post_init__ method automatically:
    1. Sets component enable/disable based on config type
    2. Calculates chamber geometry if not specified
    3. Calculates air mass flow rate for target velocity
    4. Generates zone configuration if multi-zone is enabled
    """
    
    config_type: DryerConfiguration = DryerConfiguration.CONFIG_A
    
    # Sub-configurations
    ambient: AmbientConfig = field(default_factory=lambda: AmbientConfig(csv_path=Path(".")))
    solar: SolarConfig = field(default_factory=SolarConfig)
    heatpump: HeatPumpConfig = field(default_factory=HeatPumpConfig)
    dryer: DryerConfig = field(default_factory=DryerConfig)
    kinetics: KineticsConfig = field(default_factory=KineticsConfig)
    
    # Simulation control
    stop_criterion: Literal["all_trays_dry", "avg_dry", "time_limit"] = "all_trays_dry"
    max_simulation_time_s: float = 72 * 3600.0
    
    # Output control
    output_dir: Path = Path("outputs")
    save_every_n_steps: int = 1
    
    # Display geometry on init
    display_geometry: bool = True
    
    def __post_init__(self):
        """Validate and apply configuration-specific settings."""
        
        # =====================================================================
        # SET COMPONENT ENABLE/DISABLE BASED ON CONFIG TYPE
        # =====================================================================
        if self.config_type == DryerConfiguration.CONFIG_A:
            self.solar.enabled = False
            self.heatpump.enabled = True
        elif self.config_type == DryerConfiguration.CONFIG_B:
            self.solar.enabled = True
            self.heatpump.enabled = True
        elif self.config_type == DryerConfiguration.CONFIG_C:
            self.solar.enabled = True
            self.heatpump.enabled = True
        elif self.config_type == DryerConfiguration.CONFIG_D:
            self.solar.enabled = True
            self.heatpump.enabled = False
        elif self.config_type == DryerConfiguration.CONFIG_E:
            self.solar.enabled = True
            self.heatpump.enabled = True
        
        # Always disable recirculation
        self.dryer.r_recirc = 0.0
        
        # Set reference parameters for kinetics
        self.kinetics.X0_db_ref = self.dryer.X0_db
        self.kinetics.X_eq_db_ref = self.dryer.X_eq_db
        
        # =====================================================================
        # CALCULATE CHAMBER GEOMETRY
        # =====================================================================
        self._calculate_geometry()
        
        # =====================================================================
        # MULTI-ZONE DISABLED - single-inlet only
        # =====================================================================
        # if self.dryer.multizone.enabled:
        #     self._setup_multizone()
        
        # =====================================================================
        # DISPLAY GEOMETRY (if enabled)
        # =====================================================================
        if self.display_geometry:
            self._display_geometry()
    
    def _calculate_geometry(self):
        """Calculate chamber geometry from product specifications.
        
        This implements the equations:
            m_fresh = m_dry × (1 + X0_db)
            A_tray = m_fresh_per_tray / loading_density
            tray_side = √A_tray
            A_cross = tray_width × air_gap
            m_da = ρ_air × v_target × A_cross
        """
        
        dryer = self.dryer
        
        # Dry mass per tray
        m_p_tray = dryer.m_p_dry_kg / dryer.n_trays

        # Tray area from product properties (through-flow design)
        # This matches the validated setup_simulation() formula
        rho_bulk = dryer.product_apparent_density_kg_per_m3
        thickness = dryer.product_thickness_m
        tray_area = m_p_tray / (rho_bulk * thickness)
        tray_side = tray_area ** 0.5
        
        # Set tray dimensions
        dryer.tray_length_m = tray_side
        dryer.tray_width_m = tray_side
        dryer.tray_area_m2 = tray_area
        
        # Air mass flow rate: use tray area as flow cross-section
        # (through-flow design: air passes vertically through product bed)
        if dryer.m_da_kg_per_s <= 0:
            dryer.m_da_kg_per_s = (
                dryer.air_density_kg_per_m3 *
                dryer.tray_area_m2 *
                dryer.target_velocity_m_s
            )
        
        # Chamber dimensions
        tray_pitch = dryer.product_thickness_m + dryer.tray_frame_m + dryer.air_gap_m
        stack_height = dryer.n_trays * tray_pitch
        
        dryer.chamber_height_m = stack_height + 0.20  # Add plenums
        dryer.chamber_length_m = dryer.tray_length_m + 0.20
        dryer.chamber_width_m = dryer.tray_width_m + 0.20
    
    # def _setup_multizone(self):
    #     """Setup multi-zone configuration - DISABLED."""
    #     pass
    
    def _display_geometry(self):
        """Display chamber geometry summary."""
        
        dryer = self.dryer
        m_fresh = dryer.m_p_dry_kg * (1 + dryer.X0_db)
        m_water = dryer.m_p_dry_kg * (dryer.X0_db - dryer.X_final_db)
        A_cross = dryer.tray_width_m * dryer.air_gap_m
        v_actual = dryer.m_da_kg_per_s / (dryer.air_density_kg_per_m3 * A_cross)
        
        print("\n" + "="*70)
        print(f"CHAMBER GEOMETRY - {self.config_type.value}")
        print("="*70)
        
        print(f"""
PRODUCT:
  Dry mass (m_p_dry_kg):     {dryer.m_p_dry_kg:.2f} kg
  Initial moisture (X0_db):  {dryer.X0_db:.2f} kg/kg db
  Fresh apple mass:          {m_fresh:.2f} kg
  Water to remove:           {m_water:.2f} kg

TRAYS:
  Number of trays:           {dryer.n_trays}
  Tray dimensions:           {dryer.tray_length_m*100:.1f} × {dryer.tray_width_m*100:.1f} cm
  Tray area (each):          {dryer.tray_area_m2:.3f} m²
  Loading density:           {dryer.loading_density_kg_m2:.1f} kg/m²
  Air gap:                   {dryer.air_gap_m*100:.1f} cm

CHAMBER:
  Height:                    {dryer.chamber_height_m*100:.1f} cm
  Length:                    {dryer.chamber_length_m*100:.1f} cm
  Width:                     {dryer.chamber_width_m*100:.1f} cm

AIR FLOW:
  Mass flow rate:            {dryer.m_da_kg_per_s:.4f} kg/s = {dryer.m_da_kg_per_s*3600:.1f} kg/h
  Target velocity:           {dryer.target_velocity_m_s:.2f} m/s
  Actual velocity:           {v_actual:.2f} m/s
  Cross-section area:        {A_cross:.4f} m²
""")
        
        # Zone information - single-inlet only
        print("ZONES (Single-Inlet):")
        print(f"  Number of inlets:          1")
        print(f"  Number of outlets:         1")
        
        print("="*70 + "\n")


@dataclass
class ParametricSweepConfig:
    """Configuration for parametric sweep over solar collector areas."""
    
    base_config: SimulationConfig
    solar_areas_m2: list[float] = field(default_factory=lambda: [0, 2, 4, 6, 8, 10, 12, 15, 20])
    locations: list[tuple[str, Path]] = field(default_factory=list)
    configs_to_run: list[DryerConfiguration] = field(default_factory=lambda: [
        DryerConfiguration.CONFIG_A,
        DryerConfiguration.CONFIG_B,
        DryerConfiguration.CONFIG_C,
        DryerConfiguration.CONFIG_D,
        DryerConfiguration.CONFIG_E,
    ])
    n_parallel_jobs: int = 1
    output_root: Path = Path("outputs/parametric_sweep")


# ==============================================================================
# HELPER FUNCTIONS - Updated for multi-zone support
# ==============================================================================

def make_config_A_HP_only(
    ambient_csv: Path,
    T_set_C: float = 50.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 10.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config A (HP-only, 24/7 baseline).

    Parameters:
        ambient_csv: Path to weather data CSV
        T_set_C: Target drying temperature [°C]
        phase2_root: Path to Phase-2 kinetics models
        m_p_dry_kg: Dry mass of product [kg]
        n_trays: Number of trays
        target_velocity: Target air velocity [m/s]
        display_geometry: Display geometry on creation
    """

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_A,
        ambient=AmbientConfig(csv_path=ambient_csv),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_B_solar_HP_series(
    ambient_csv: Path,
    solar_area_m2: float,
    T_set_C: float = 50.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 10.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config B (Solar → HP condenser series)."""

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_B,
        ambient=AmbientConfig(csv_path=ambient_csv),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_C_solar_HP_evap(
    ambient_csv: Path,
    solar_area_m2: float,
    T_set_C: float = 50.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 10.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config C (Solar-assisted HP evaporator)."""

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_C,
        ambient=AmbientConfig(csv_path=ambient_csv),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_D_solar_only(
    ambient_csv: Path,
    solar_area_m2: float,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 10.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config D (Solar-only, no HP)."""

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_D,
        ambient=AmbientConfig(csv_path=ambient_csv),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=50.0,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_E_solar_evap_cond_cascade(
    ambient_csv: Path,
    solar_area_m2: float,
    T_set_C: float = 50.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 10.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config E (Solar → HP evap → HP cond cascade)."""

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_E,
        ambient=AmbientConfig(csv_path=ambient_csv),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


# ==============================================================================
# MAIN - TEST CONFIGURATION
# ==============================================================================

if __name__ == "__main__":
    print("="*70)
    print("CONFIGURATION SYSTEM TEST - Multi-Zone Support")
    print("="*70)
    
    # Test 1: Config A without multi-zone
    print("\n>>> Test 1: Config A (HP-only) - Single Inlet")
    cfg_a = make_config_A_HP_only(
        ambient_csv=Path("weather/kathmandu.csv"),
        T_set_C=50.0,
        m_p_dry_kg=10.0,  # 75 kg fresh apples
    )
    
    # Test 2: Config E cascade
    print("\n>>> Test 2: Config E (Cascade) - Single Inlet")
    cfg_e = make_config_E_solar_evap_cond_cascade(
        ambient_csv=Path("weather/kathmandu.csv"),
        solar_area_m2=12.0,
        m_p_dry_kg=10.0,
    )
    
    print("\n" + "="*70)
    print("KEY VARIABLES SUMMARY")
    print("="*70)
    print("""
To change product amount:
    m_p_dry_kg = 10.0    → 75 kg fresh apples
    m_p_dry_kg = 1.33    → 10 kg fresh apples
    m_p_dry_kg = 20.0    → 150 kg fresh apples

To change air velocity (affects m_da):
    target_velocity_m_s = 1.1   → default (0.8-1.5 typical)

Air mass flow rate equation:
    m_da = ρ_air × v_target × A_cross
    where A_cross = tray_width × air_gap
""")