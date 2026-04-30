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

# ==============================================================================
# LOCATION ELEVATION DATA
# Standard atmosphere formula: P = 101325 × (1 - 0.0065×h/288.15)^5.2561
# ==============================================================================
LOCATION_ELEVATIONS_M: dict = {
    "kathmandu":  1350,   # Capital city, Bagmati Province
    "biratnagar":   72,   # Terai lowlands, Koshi Province
    "taplejung":  1820,   # Eastern hills, Koshi Province
    "dhulikhel":  1550,   # Kavrepalanchok, near Kathmandu
}


def elevation_to_P_atm_Pa(elevation_m: float) -> float:
    """Standard atmosphere: elevation [m] → pressure [Pa]."""
    return 101325.0 * (1.0 - 0.0065 * elevation_m / 288.15) ** 5.2561


class DryerConfiguration(str, Enum):
    """Dryer configurations to simulate."""

    CONFIG_A  = "A_HP_only"                      # Heat pump only, 24/7
    CONFIG_B  = "B_solar_HP_series"              # Solar → HP condenser (series boost)
    CONFIG_C1 = "C1_solar_cascade_mix_before"    # Mix before solar: [r×Exh+(1-r)×Amb] → Solar → Evap → Cond
    CONFIG_C2 = "C2_solar_cascade_mix_after"     # Mix after solar:  Amb → Solar → [Mix+r×Exh] → Evap → Cond
    CONFIG_D1 = "D1_HRX_exhaust_expelled"        # HRX + HP: preheated amb -> Cond, cooled exh expelled
    CONFIG_D2 = "D2_HRX_exhaust_to_evap"         # HRX + HP: preheated amb -> Cond, cooled exh -> Evap
    CONFIG_D3 = "D3_HRX_exhaust_to_cond"         # HRX + HP: cooled exh -> Cond, preheated amb -> Evap
    CONFIG_E1 = "E1_HRX_solar_evap_ambient"      # HRX + Solar + HP: amb -> HRX -> Solar -> Cond, evap = ambient
    CONFIG_E2 = "E2_HRX_solar_evap_exhaust_mix"  # HRX + Solar + HP: amb -> HRX -> Solar -> Cond, evap = exh+amb mix
    CONFIG_E3 = "E3_HRX_solar_on_evap"           # HRX + HP: amb -> HRX -> Cond, exh_cooled+amb -> Solar -> Evap


@dataclass
class AmbientConfig:
    """Ambient weather data configuration."""
    
    csv_path: Path
    start_index: int = 0
    max_steps: Optional[int] = None

    # Site elevation — used to compute P_atm and air density in __post_init__
    # Use LOCATION_ELEVATIONS_M dict or pass directly [metres above sea level]
    elevation_m: float = 0.0

    # Column names in CSV
    time_col: str = "datetime"
    temp_col: str = "T_amb_C"
    rh_col: str = "RH_amb_pct"
    ghi_col: str = "G_hor_Wm2"
    wind_col: Optional[str] = None
    pressure_col: Optional[str] = None

    # Computed from elevation_m in SimulationConfig.__post_init__
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
    
    refrigerant: str = "R134a"        # Standard heat-pump dryer refrigerant
    eta_isentropic: float = 0.75
    eta_mechanical: float = 0.95
    superheat_K: float = 5.0
    subcooling_K: float = 5.0
    epsilon_evap: float = 0.85
    epsilon_cond: float = 0.85
    # R134a limits: T_evap_min=-5°C (anti-frost), T_cond_max=70°C (critical=101°C)
    T_evap_min_C: float = -5.0
    T_evap_max_C: float = 20.0
    T_cond_min_C: float = 30.0
    T_cond_max_C: float = 70.0
    COP_min: float = 2.0
    pressure_ratio_max: float = 10.0
    T_approach_evap_K: float = 10.0
    T_approach_cond_K: float = 10.0
    # Fixed evaporator saturation temperature for closed-loop HPCD [°C]
    # Real AC units run at ~5°C; coil surface = T_evap_target + DT_evap_approach
    T_evap_target_C: float = 5.0
    allow_modulation: bool = True
    modulation_min_pct: float = 30.0
    enabled: bool = True
    # 1-ton AC reference thresholds [kW] — flags only, no capping
    Q_cond_max_kW: float = 4.0
    Q_evap_max_kW: float = 3.5
    # Evaporator coil approach temperature [K]
    # Coil surface = T_evap_sat + DT_evap_approach (refrigerant-to-surface resistance)
    DT_evap_approach: float = 3.0


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
    
    # Target conditions — 45°C: safer for AC (R410A P_cond=31bar vs cutout 42-45bar)
    T_set_C: float = 45.0
    T_set_tolerance_C: float = 2.0

    # =========================================================================
    # PRODUCT PARAMETERS (KEY VARIABLES YOU CAN CHANGE)
    # =========================================================================
    X0_db: float = 6.5           # Initial moisture [kg water/kg dry]
    X_final_db: float = 0.10     # Target final moisture [kg water/kg dry]
    X_eq_db: float = 0.0         # Equilibrium moisture (use 0 per your request)
    # m_p_dry_kg = 3.0 → ~22.5 kg fresh; Q_cond_req ≈ 4.0 kW (matches 1-ton AC)
    m_p_dry_kg: float = 3.0      # Dry mass [kg]

    # Product properties
    product_thickness_m: float = 0.006  # 6 mm apple slices
    product_apparent_density_kg_per_m3: float = 600.0

    # =========================================================================
    # TRAY CONFIGURATION
    # =========================================================================
    n_trays: int = 10
    max_trays: int = 10
    loading_density_kg_m2: float = 0.0   # 0 = auto-calculate from rho_bulk × thickness
    
    # =========================================================================
    # GEOMETRY PARAMETERS (NEW - for proper air flow calculation)
    # =========================================================================
    # These are calculated automatically from product specs if set to 0
    tray_length_m: float = 0.0           # Auto-calculated if 0
    tray_width_m: float = 0.0            # Auto-calculated if 0
    tray_area_m2: Optional[float] = None # Horizontal area per tray
    air_gap_m: float = 0.12              # 12 cm gap between trays
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
    # air_density_kg_per_m3 = 0.0 → computed in __post_init__ from P_atm and T_set_C
    # Formula: rho = P_atm / (287.05 × (T_set + 273.15))
    # Examples at T_set=45°C: Biratnagar≈1.100, Kathmandu≈0.937, Taplejung≈0.891 kg/m³
    air_density_kg_per_m3: float = 0.0   # 0 = auto-compute from elevation+T_set
    
    # Convenience (for backward compatibility)
    tray_depth_m: float = 0.05
    
    # Thermodynamic — latent heat at T_set = 45 degC (IAPWS-IF97)
    h_fg_kJ_per_kg: float = 2394.8
    
    # Timestep
    dt_s: float = 60.0
    
    # Recirculation — fixed fraction only (dynamic modes removed 2026-04-20)
    r_recirc: float = 0.0

    # Section discretization
    n_sections: int = 1                  # Sections per tray along airflow [1=legacy]

    # Flow reversal
    flow_reversal_interval_min: float = 0.0  # 0=disabled; e.g. 30.0 = reverse every 30 min

    # Condenser-direct bypass: VPD-based oscillating strategy.
    # When cond_penalty_frac < this threshold, exhaust routes directly to condenser
    # (closed loop, tiny Q_cond) and evaporator runs on ambient air (heat source only).
    # When humidity builds and cond_penalty_frac > 3× threshold, switch back to evap.
    # Set to 0.0 to disable (default). Typical value: 0.05 (5%).
    # cond_penalty = (VPD_post_evap - VPD_exhaust) / VPD_post_evap
    cond_penalty_thresh: float = 0.0

    # =========================================================================
    # ADAPTIVE EVAPORATOR TEMPERATURE (closed-loop r > 0 only)
    # =========================================================================
    # Strategy for setting T_evap when recirculating:
    #   "fixed"          — use T_evap_target_C (default, standard dehumidifier)
    #   "onset-tracking" — set T_evap relative to the onset temperature where
    #                      evaporator outlet just reaches the mixed-air dew point.
    #                      Subcooling below onset varies with MR (drying phase).
    evap_strategy: str = "fixed"
    # Subcooling below onset [K] for onset-tracking, by drying phase:
    evap_onset_delta_early_K: float = 2.0   # MR > 0.5
    evap_onset_delta_mid_K: float = 3.0     # 0.2 < MR <= 0.5
    evap_onset_delta_late_K: float = 5.0    # MR <= 0.2

    # =========================================================================
    # HEAT RECOVERY EXCHANGER (Config D1/D2/D3)
    # =========================================================================
    eps_HRX: float = 0.70               # HRX effectiveness [-]
    d_variant: str = ""                  # "D1", "D2", "D3", "E1", "E2", or "E3" (set by factory)
    evap_ambient_mixing: bool = False    # D2: mix ambient with cooled exhaust at evap
    # VPD-based exhaust bypass for open-loop D/E configs.
    # When VPD utilization (drying%) < this threshold, route warm exhaust
    # directly to condenser (tiny Q_cond) instead of HRX+ambient path.
    # Set to 0.0 to disable (default). Typical value: 0.05 (5%).
    vpd_bypass_thresh: float = 0.0

    # =========================================================================
    # STREAM 2: Evaporator source air circuit (Config C1/C2)
    # =========================================================================
    # A separate air blower passes solar-heated air over the HP evaporator
    # coil. This mass flow determines how much the source air cools before
    # reaching the refrigerant — directly setting T_evap_C and COP.
    #   0.0 = legacy mode (infinite flow assumed, T_evap_source = T_solar_out)
    #   >0  = finite flow: T_evap_source = T_solar_out - Q_evap/(m*cp)
    m_evap_stream_kg_per_s: float = 0.0   # Stream 2 blower mass flow [kg/s]
    dP_evap_stream_Pa: float = 80.0       # Stream 2 evap coil pressure drop [Pa]

    # =========================================================================
    # FAN & PRESSURE DROP PARAMETERS
    # =========================================================================
    eta_fan: float = 0.60                # Fan total efficiency [-]
    dP_evap_Pa: float = 80.0            # Evaporator coil air-side ΔP [Pa]
    dP_cond_Pa: float = 80.0            # Condenser coil air-side ΔP [Pa]
    dP_duct_Pa: float = 50.0            # Ductwork ΔP [Pa]
    K_bend: float = 2.0                 # 180-degree serpentine turn loss coeff [-]
    wall_roughness_m: float = 0.0       # Wall roughness [m]; 0 = smooth
    mu_air_Pa_s: float = 2.0e-5         # Air dynamic viscosity at ~50°C [Pa·s]

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
        """Calculate air flow cross-sectional area.

        For cross-flow design (air flows horizontally across tray surface):
        Cross-section = tray_width x air_gap
        """
        return self.tray_width_m * self.air_gap_m


@dataclass
class KineticsConfig:
    """Drying kinetics configuration."""

    mode: Literal["phase2_midilli"] = "phase2_midilli"
    model_type: str = "midilli"
    phase2_models_root: Optional[Path] = None
    fallback_to_page: bool = True
    use_knb_table: bool = True  # Use pre-computed k,n,b table (fallback mode)
    knb_csv_path: Optional[Path] = None

    # Reference conditions — updated to match new T_set_C = 45°C
    T_ref_C: float = 45.0
    T_C_ref: float = 45.0  # Alias for T_ref_C
    T_ref_arrhenius_C: float = 45.0  # Arrhenius scaling reference temperature
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
    alpha_RH: float = 1.75  # matches parametric OLS fit of phase2c_for_chamber.csv (R2=0.898)

    # Valid ranges (hard limits) — expanded upper bound to 70°C for generality
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
    RH_out_max_frac: float = 1.0
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
        elif self.config_type == DryerConfiguration.CONFIG_C1:
            self.solar.enabled = True
            self.heatpump.enabled = True
        elif self.config_type == DryerConfiguration.CONFIG_C2:
            self.solar.enabled = True
            self.heatpump.enabled = True
        elif self.config_type in (DryerConfiguration.CONFIG_D1,
                                  DryerConfiguration.CONFIG_D2,
                                  DryerConfiguration.CONFIG_D3):
            self.solar.enabled = False
            self.heatpump.enabled = True
        
        # Set reference parameters for kinetics
        self.kinetics.X0_db_ref = self.dryer.X0_db
        self.kinetics.X_eq_db_ref = self.dryer.X_eq_db

        # =====================================================================
        # COMPUTE P_ATM FROM ELEVATION (must be before geometry calculation)
        # =====================================================================
        self.ambient.default_pressure_Pa = elevation_to_P_atm_Pa(self.ambient.elevation_m)

        # =====================================================================
        # COMPUTE AIR DENSITY FROM P_ATM AND T_SET (must be before geometry)
        # rho = P_atm / (R_da × T_abs)  where R_da = 287.05 J/(kg·K)
        # =====================================================================
        if self.dryer.air_density_kg_per_m3 <= 0:
            R_da = 287.05
            self.dryer.air_density_kg_per_m3 = (
                self.ambient.default_pressure_Pa
                / (R_da * (self.dryer.T_set_C + 273.15))
            )

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

        # Auto-calculate loading density from product properties if not set
        if dryer.loading_density_kg_m2 <= 0:
            dryer.loading_density_kg_m2 = (
                dryer.product_apparent_density_kg_per_m3 * dryer.product_thickness_m
            )

        # Fresh mass per tray (what's actually loaded at start)
        m_p_tray = dryer.m_p_dry_kg / dryer.n_trays
        m_fresh_tray = m_p_tray * (1 + dryer.X0_db)

        # Tray area from loading density [kg fresh / m²]
        tray_area = m_fresh_tray / dryer.loading_density_kg_m2
        tray_side = tray_area ** 0.5

        # Set tray dimensions
        dryer.tray_length_m = tray_side
        dryer.tray_width_m = tray_side
        dryer.tray_area_m2 = tray_area

        # Cross-flow: air flows horizontally through gap between trays
        # A_cross = tray_width × air_gap (NOT tray_area)
        if dryer.m_da_kg_per_s <= 0:
            A_cross = dryer.tray_width_m * dryer.air_gap_m
            dryer.m_da_kg_per_s = (
                dryer.air_density_kg_per_m3 *
                A_cross *
                dryer.target_velocity_m_s
            )
        
        # Chamber dimensions
        tray_pitch = dryer.product_thickness_m + dryer.tray_frame_m + dryer.air_gap_m
        stack_height = dryer.n_trays * tray_pitch
        
        dryer.chamber_height_m = stack_height + 0.20  # Add plenums
        dryer.chamber_length_m = dryer.tray_length_m + 0.20
        dryer.chamber_width_m = dryer.tray_width_m + 0.20
    
    def compute_pressure_drop_and_fan_power(self) -> dict:
        """Compute air-side pressure drop and fan power.

        Returns dict with all intermediate values for display/debugging.

        Physics:
            Channel friction: Darcy-Weisbach with Haaland friction factor
                Ref: Incropera & DeWitt Ch. 8; Haaland (1983) J. Fluids Eng. 105(1)
            Bend losses: K_bend × (ρv²/2) per 180° serpentine turn
                Ref: Idelchik, "Handbook of Hydraulic Resistance" 3rd ed, Section 6
            HX losses: parametric ΔP for condenser/evaporator coils
                Ref: ASHRAE Fundamentals
            Fan power: W_fan = V_dot × ΔP_total / η_fan
                Ref: ASHRAE Fundamentals Ch. 21
        """
        import math

        d = self.dryer
        W = d.tray_width_m      # channel width [m]
        h = d.air_gap_m         # channel height (air gap) [m]
        L = d.tray_length_m     # channel length (= tray length for cross-flow) [m]
        rho = d.air_density_kg_per_m3
        v = d.target_velocity_m_s
        mu = d.mu_air_Pa_s
        eps = d.wall_roughness_m
        n_trays = d.n_trays

        # --- Dynamic pressure ---
        q = 0.5 * rho * v**2  # [Pa]

        # --- Hydraulic diameter (rectangular channel) ---
        D_h = 2.0 * W * h / (W + h)

        # --- Reynolds number ---
        Re = rho * v * D_h / mu

        # --- Darcy friction factor ---
        if Re < 1:
            f = 0.0
        elif Re < 2300:
            # Laminar: f = 64 / Re
            f = 64.0 / Re
        else:
            # Turbulent: Haaland explicit approximation (1983)
            # 1/√f = -1.8 log10[(ε/D_h/3.7)^1.11 + 6.9/Re]
            term = (eps / D_h / 3.7)**1.11 + 6.9 / Re
            f = 1.0 / (-1.8 * math.log10(term))**2

        # --- Channel friction ΔP (per gap, then total) ---
        dP_per_gap = f * (L / D_h) * q if D_h > 0 else 0.0
        dP_channels = dP_per_gap * n_trays

        # --- Bend losses (n_trays - 1 serpentine turns) ---
        n_bends = max(0, n_trays - 1)
        dP_per_bend = d.K_bend * q
        dP_bends = dP_per_bend * n_bends

        # --- HX pressure drops ---
        dP_cond = d.dP_cond_Pa if self.heatpump.enabled else 0.0
        # Evaporator in air path only when r_recirc > 0 (closed-loop) or D2/D3
        dP_evap = d.dP_evap_Pa if (d.r_recirc > 0 or d.d_variant in ("D2", "D3")) else 0.0
        # HRX adds ~50 Pa for plate heat exchanger
        dP_HRX = 50.0 if d.d_variant in ("D1", "D2", "D3") else 0.0

        # --- Ductwork ---
        dP_duct = d.dP_duct_Pa

        # --- Total ---
        dP_total = dP_channels + dP_bends + dP_cond + dP_evap + dP_HRX + dP_duct

        # --- Fan power ---
        V_dot = d.m_da_kg_per_s / rho if rho > 0 else 0.0  # [m³/s]
        W_fan_W = V_dot * dP_total / d.eta_fan if d.eta_fan > 0 else 0.0
        W_fan_kW = W_fan_W / 1000.0

        return {
            "D_h_m": D_h,
            "Re": Re,
            "f": f,
            "q_Pa": q,
            "dP_per_gap_Pa": dP_per_gap,
            "dP_channels_Pa": dP_channels,
            "n_bends": n_bends,
            "dP_per_bend_Pa": dP_per_bend,
            "dP_bends_Pa": dP_bends,
            "dP_cond_Pa": dP_cond,
            "dP_evap_Pa": dP_evap,
            "dP_duct_Pa": dP_duct,
            "dP_total_Pa": dP_total,
            "V_dot_m3_per_s": V_dot,
            "W_fan_W": W_fan_W,
            "W_fan_kW": W_fan_kW,
        }

    # def _setup_multizone(self):
    #     """Setup multi-zone configuration - DISABLED."""
    #     pass
    
    def _display_geometry(self):
        """Display chamber geometry summary."""
        
        dryer = self.dryer
        m_fresh = dryer.m_p_dry_kg * (1 + dryer.X0_db)
        m_water = dryer.m_p_dry_kg * (dryer.X0_db - dryer.X_final_db)
        # Cross-flow: air flows through gap between trays
        A_cross = dryer.tray_width_m * dryer.air_gap_m
        v_actual = dryer.m_da_kg_per_s / (dryer.air_density_kg_per_m3 * A_cross)
        
        print("\n" + "="*70)
        print(f"CHAMBER GEOMETRY - {self.config_type.value}")
        print(f"  Location: elevation={self.ambient.elevation_m:.0f}m, "
              f"P_atm={self.ambient.default_pressure_Pa/1000:.2f}kPa, "
              f"rho_air={dryer.air_density_kg_per_m3:.3f}kg/m³")
        print("="*70)
        
        print(f"""
PRODUCT:
  Dry mass (m_p_dry_kg):     {dryer.m_p_dry_kg:.2f} kg
  Initial moisture (X0_db):  {dryer.X0_db:.2f} kg/kg db
  Fresh apple mass:          {m_fresh:.2f} kg
  Water to remove:           {m_water:.2f} kg

TRAYS:
  Number of trays:           {dryer.n_trays}
  Tray dimensions:           {dryer.tray_length_m*100:.1f} x {dryer.tray_width_m*100:.1f} cm
  Tray area (each):          {dryer.tray_area_m2:.3f} m2
  Loading (fresh/tray):      {m_fresh/dryer.n_trays/dryer.tray_area_m2:.1f} kg/m2 (actual)
  Air gap:                   {dryer.air_gap_m*100:.1f} cm

CHAMBER:
  Height:                    {dryer.chamber_height_m*100:.1f} cm
  Length:                    {dryer.chamber_length_m*100:.1f} cm
  Width:                     {dryer.chamber_width_m*100:.1f} cm

AIR FLOW:
  Mass flow rate:            {dryer.m_da_kg_per_s:.4f} kg/s = {dryer.m_da_kg_per_s*3600:.1f} kg/h
  Target velocity:           {dryer.target_velocity_m_s:.2f} m/s
  Actual velocity:           {v_actual:.2f} m/s
  Cross-section area:        {A_cross:.4f} m2
""")
        if dryer.n_sections > 1:
            print(f"SECTION DISCRETIZATION:")
            print(f"  Sections per tray:         {dryer.n_sections}")
            print(f"  Total nodes:               {dryer.n_trays * dryer.n_sections}")
            print()
        if dryer.flow_reversal_interval_min > 0:
            print(f"FLOW REVERSAL:")
            print(f"  Reversal interval:         {dryer.flow_reversal_interval_min:.0f} min")
            print()
        
        # Pressure drop breakdown
        pd_info = self.compute_pressure_drop_and_fan_power()
        flow_regime = "laminar" if pd_info["Re"] < 2300 else "turbulent"
        print(f"""PRESSURE DROP BREAKDOWN:
  Hydraulic diameter D_h:    {pd_info['D_h_m']*1000:.1f} mm
  Reynolds number Re:        {pd_info['Re']:.0f} ({flow_regime})
  Darcy friction factor f:   {pd_info['f']:.4f}
  Dynamic pressure q:        {pd_info['q_Pa']:.3f} Pa

  Channels ({dryer.n_trays} gaps):       {pd_info['dP_per_gap_Pa']:.3f} Pa/gap x {dryer.n_trays} = {pd_info['dP_channels_Pa']:.1f} Pa
  Bends ({pd_info['n_bends']} turns):          {pd_info['dP_per_bend_Pa']:.2f} Pa/bend x {pd_info['n_bends']} = {pd_info['dP_bends_Pa']:.1f} Pa
  Condenser coil:            {pd_info['dP_cond_Pa']:.0f} Pa
  Evaporator coil:           {pd_info['dP_evap_Pa']:.0f} Pa {'(r_recirc > 0)' if dryer.r_recirc > 0 else '(not in air path)'}
  Ductwork:                  {pd_info['dP_duct_Pa']:.0f} Pa
  ----------------------------------------
  TOTAL dP:                  {pd_info['dP_total_Pa']:.1f} Pa

FAN:
  Volume flow rate:          {pd_info['V_dot_m3_per_s']:.4f} m3/s
  Fan efficiency:            {dryer.eta_fan*100:.0f}%
  Fan power:                 {pd_info['W_fan_W']:.1f} W = {pd_info['W_fan_kW']:.4f} kW
""")
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
        DryerConfiguration.CONFIG_C1,
        DryerConfiguration.CONFIG_C2,
    ])
    n_parallel_jobs: int = 1
    output_root: Path = Path("outputs/parametric_sweep")


# ==============================================================================
# HELPER FUNCTIONS - Updated for multi-zone support
# ==============================================================================

def make_config_A_HP_only(
    ambient_csv: Path,
    T_set_C: float = 45.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 3.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    r_recirc: float = 0.0,
    n_sections: int = 1,
    flow_reversal_interval_min: float = 0.0,
    elevation_m: float = 0.0,
    display_geometry: bool = True,
    cond_penalty_thresh: float = 0.0,
    evap_strategy: str = 'fixed',
) -> SimulationConfig:
    """Create Config A (HP-only, 24/7 baseline).

    Parameters:
        ambient_csv: Path to weather data CSV
        T_set_C: Target drying temperature [°C]
        phase2_root: Path to Phase-2 kinetics models
        m_p_dry_kg: Dry mass of product [kg]
        n_trays: Number of trays
        target_velocity: Target air velocity [m/s]
        r_recirc: Recirculation ratio [0..1]. 0=open-loop, 1=fully closed.
        n_sections: Sections per tray along airflow [1=legacy]
        flow_reversal_interval_min: Flow reversal interval [min]. 0=disabled.
        display_geometry: Display geometry on creation
    """

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_A,
        ambient=AmbientConfig(csv_path=ambient_csv, elevation_m=elevation_m),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
            r_recirc=r_recirc,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal_interval_min,
            cond_penalty_thresh=cond_penalty_thresh,
            evap_strategy=evap_strategy,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_B_solar_HP_series(
    ambient_csv: Path,
    solar_area_m2: float,
    T_set_C: float = 45.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 3.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    r_recirc: float = 0.0,
    n_sections: int = 1,
    flow_reversal_interval_min: float = 0.0,
    elevation_m: float = 0.0,
    display_geometry: bool = True,
    cond_penalty_thresh: float = 0.0,
) -> SimulationConfig:
    """Create Config B (Solar → HP condenser series).

    Parameters:
        r_recirc: Recirculation ratio [0..1]. 0=open-loop, >0=closed-loop
                  with evaporator dehumidification before solar preheating.
        n_sections: Sections per tray along airflow [1=legacy]
        flow_reversal_interval_min: Flow reversal interval [min]. 0=disabled.
    """

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_B,
        ambient=AmbientConfig(csv_path=ambient_csv, elevation_m=elevation_m),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
            r_recirc=r_recirc,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal_interval_min,
            cond_penalty_thresh=cond_penalty_thresh,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_C1_solar_cascade_mix_before(
    ambient_csv: Path,
    solar_area_m2: float,
    T_set_C: float = 45.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 3.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    n_sections: int = 1,
    flow_reversal_interval_min: float = 0.0,
    r_recirc: float = 0.0,
    elevation_m: float = 0.0,
    cond_penalty_thresh: float = 0.0,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config C1: Solar cascade — mix BEFORE solar.

    Air path: [r×Exhaust + (1-r)×Ambient] → Solar → Evap → Cond → Chamber

    Parameters
    ----------
    r_recirc : float
        Recirculation ratio [0..1].  Exhaust mixes with ambient BEFORE the
        solar collector (warmer inlet → lower η_solar but pre-heated air).
    cond_penalty_thresh : float
        VPD condenser-direct bypass threshold (0=disabled, typical 0.05).
    """

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_C1,
        ambient=AmbientConfig(csv_path=ambient_csv, elevation_m=elevation_m),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal_interval_min,
            r_recirc=r_recirc,
            cond_penalty_thresh=cond_penalty_thresh,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_C2_solar_cascade_mix_after(
    ambient_csv: Path,
    solar_area_m2: float,
    T_set_C: float = 45.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 3.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    n_sections: int = 1,
    flow_reversal_interval_min: float = 0.0,
    r_recirc: float = 0.0,
    elevation_m: float = 0.0,
    cond_penalty_thresh: float = 0.0,
    display_geometry: bool = True,
) -> SimulationConfig:
    """Create Config C2: Solar cascade — mix AFTER solar.

    Air path: Ambient → Solar → [Mix + r×Exhaust] → Evap → Cond → Chamber

    Parameters
    ----------
    r_recirc : float
        Recirculation ratio [0..1].  Exhaust mixes with solar outlet
        AFTER the solar collector (preserves collector efficiency).
    cond_penalty_thresh : float
        VPD condenser-direct bypass threshold (0=disabled, typical 0.05).
    """

    cfg = SimulationConfig(
        config_type=DryerConfiguration.CONFIG_C2,
        ambient=AmbientConfig(csv_path=ambient_csv, elevation_m=elevation_m),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal_interval_min,
            r_recirc=r_recirc,
            cond_penalty_thresh=cond_penalty_thresh,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_D_HRX(
    ambient_csv: Path,
    d_variant: str = "D1",
    T_set_C: float = 45.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 3.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    eps_HRX: float = 0.70,
    evap_ambient_mixing: bool = False,
    elevation_m: float = 0.0,
    display_geometry: bool = True,
    vpd_bypass_thresh: float = 0.0,
) -> SimulationConfig:
    """Create Config D (HRX + HP, r=0 only).

    Parameters
    ----------
    d_variant : str
        "D1" — preheated amb -> Cond, cooled exh expelled, evap = separate ambient
        "D2" — preheated amb -> Cond, cooled exh -> Evap
        "D3" — cooled exh -> Cond, preheated amb -> Evap (swapped routing)
    eps_HRX : float
        HRX effectiveness [0..1]. Default 0.70.
    vpd_bypass_thresh : float
        VPD utilization threshold for exhaust bypass (0.0 = disabled).
    """
    variant_map = {"D1": DryerConfiguration.CONFIG_D1,
                   "D2": DryerConfiguration.CONFIG_D2,
                   "D3": DryerConfiguration.CONFIG_D3}
    if d_variant not in variant_map:
        raise ValueError(f"d_variant must be D1, D2, or D3, got {d_variant!r}")

    cfg = SimulationConfig(
        config_type=variant_map[d_variant],
        ambient=AmbientConfig(csv_path=ambient_csv, elevation_m=elevation_m),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
            r_recirc=0.0,  # D configs are r=0 only
            eps_HRX=eps_HRX,
            d_variant=d_variant,
            evap_ambient_mixing=evap_ambient_mixing,
            vpd_bypass_thresh=vpd_bypass_thresh,
        ),
        kinetics=KineticsConfig(phase2_models_root=phase2_root),
        display_geometry=display_geometry,
    )

    return cfg


def make_config_E_HRX_solar(
    ambient_csv: Path,
    solar_area_m2: float,
    e_variant: str = "E1",
    T_set_C: float = 45.0,
    phase2_root: Optional[Path] = None,
    m_p_dry_kg: float = 3.0,
    n_trays: int = 10,
    target_velocity: float = 1.1,
    eps_HRX: float = 0.70,
    elevation_m: float = 0.0,
    display_geometry: bool = True,
    vpd_bypass_thresh: float = 0.0,
) -> SimulationConfig:
    """Create Config E (HRX + Solar + HP, r=0 only).

    Parameters
    ----------
    solar_area_m2 : float
        Solar collector area [m2].
    e_variant : str
        "E1" — evaporator on separate ambient (like D1)
        "E2" — evaporator on mixed cooled exhaust + ambient (like D2)
        "E3" — solar on evaporator stream (amb->HRX->Cond, exh+amb->Solar->Evap)
    eps_HRX : float
        HRX effectiveness [0..1]. Default 0.70.
    vpd_bypass_thresh : float
        VPD utilization threshold for exhaust bypass (0.0 = disabled).
    """
    variant_map = {"E1": DryerConfiguration.CONFIG_E1,
                   "E2": DryerConfiguration.CONFIG_E2,
                   "E3": DryerConfiguration.CONFIG_E3}
    if e_variant not in variant_map:
        raise ValueError(f"e_variant must be E1, E2, or E3, got {e_variant!r}")

    cfg = SimulationConfig(
        config_type=variant_map[e_variant],
        ambient=AmbientConfig(csv_path=ambient_csv, elevation_m=elevation_m),
        solar=SolarConfig(area_m2=solar_area_m2),
        dryer=DryerConfig(
            T_set_C=T_set_C,
            m_p_dry_kg=m_p_dry_kg,
            n_trays=n_trays,
            target_velocity_m_s=target_velocity,
            r_recirc=0.0,  # E configs are r=0 only
            eps_HRX=eps_HRX,
            d_variant=e_variant,
            vpd_bypass_thresh=vpd_bypass_thresh,
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
    
    # Test 2: Config C2 cascade (mix after solar)
    print("\n>>> Test 2: Config C2 (Cascade, mix after solar) - Single Inlet")
    cfg_c2 = make_config_C2_solar_cascade_mix_after(
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