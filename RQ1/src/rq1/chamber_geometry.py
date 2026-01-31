"""
Chamber Geometry Calculations for Multi-Zone Drying System
==========================================================

This module calculates and displays chamber dimensions, tray sizes,
air flow rates, and zone configurations for the SAHPD system.

NEW FILE - Add this to your rq1/ folder as: chamber_geometry.py

Author: Wasti (SAHPD Thesis)
Date: January 2026
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# =============================================================================
# ZONE CONFIGURATION DATACLASS
# =============================================================================

@dataclass
class ZoneConfig:
    """Configuration for a single drying zone.
    
    A zone is a group of trays that receive air from the same inlet.
    Fresh air is injected at the start of each zone and mixed with
    upstream exhaust (except for the first zone).
    
    Attributes:
        name: Zone identifier (e.g., "Zone_A", "Zone_B")
        tray_indices: List of tray indices in this zone [0,1,2,3]
        flow_fraction: Fraction of TOTAL fresh air directed to this zone
        receives_upstream_exhaust: True for all zones except the first
    """
    
    name: str
    tray_indices: List[int]
    flow_fraction: float
    receives_upstream_exhaust: bool = True
    
    def __post_init__(self):
        """Validate zone configuration."""
        if not 0.0 <= self.flow_fraction <= 1.0:
            raise ValueError(f"flow_fraction must be 0-1, got {self.flow_fraction}")
        if not self.tray_indices:
            raise ValueError("Zone must have at least one tray")
    
    @property
    def n_trays(self) -> int:
        """Number of trays in this zone."""
        return len(self.tray_indices)


@dataclass
class MultiZoneConfig:
    """Configuration for multi-zone drying chamber.
    
    Multi-zone design injects fresh hot air at multiple points in the
    chamber, improving drying uniformity by "refreshing" the air quality
    at strategic intervals.
    
    Attributes:
        enabled: Toggle multi-zone on/off (False = single inlet)
        n_zones: Number of zones to create
        zones: List of ZoneConfig objects (auto-generated if empty)
        mixing_efficiency: 1.0 = perfect mixing, <1.0 = partial mixing
    """
    
    enabled: bool = False
    n_zones: int = 3
    zones: List[ZoneConfig] = field(default_factory=list)
    mixing_efficiency: float = 1.0
    
    def validate(self, n_trays: int):
        """Validate zone configuration against total number of trays."""
        if not self.enabled:
            return
        
        # Check all trays are covered
        all_indices = []
        for zone in self.zones:
            all_indices.extend(zone.tray_indices)
        
        if sorted(all_indices) != list(range(n_trays)):
            raise ValueError(
                f"Zone tray indices must cover all trays 0-{n_trays-1}. "
                f"Got: {sorted(all_indices)}"
            )
        
        # Check flow fractions sum to 1.0
        total_flow = sum(z.flow_fraction for z in self.zones)
        if abs(total_flow - 1.0) > 0.001:
            raise ValueError(
                f"Zone flow fractions must sum to 1.0, got {total_flow:.4f}"
            )


# =============================================================================
# CHAMBER GEOMETRY DATACLASS
# =============================================================================

@dataclass
class ChamberGeometry:
    """Complete chamber geometry specification.
    
    This dataclass holds all physical dimensions and flow parameters
    for the drying chamber. It can be auto-calculated from product
    specifications or manually specified.
    
    KEY VARIABLES YOU CAN CHANGE:
    ─────────────────────────────
    m_p_dry_kg:          Dry mass of product (determines fresh mass)
    X0_db:               Initial moisture content (dry basis)
    n_trays:             Number of trays
    loading_density:     kg fresh product per m² of tray area
    target_velocity:     Target air velocity over product (m/s)
    air_gap_m:           Vertical gap between trays (m)
    
    The air mass flow rate is calculated from:
        m_da = rho_air × v_target × A_cross
    
    Where A_cross = tray_width × air_gap
    """
    
    # Product specifications
    m_p_dry_kg: float = 10.0           # Dry mass [kg]
    X0_db: float = 6.5                 # Initial moisture content [kg/kg db]
    X_final_db: float = 0.10           # Target final moisture [kg/kg db]
    product_thickness_m: float = 0.006  # Product thickness [m] (6mm)
    
    # Tray configuration
    n_trays: int = 10
    loading_density_kg_per_m2: float = 5.0  # kg fresh per m² tray
    
    # Calculated tray dimensions (set by calculate())
    tray_length_m: float = 0.0
    tray_width_m: float = 0.0
    tray_area_m2: float = 0.0
    
    # Air gap and chamber structure
    air_gap_m: float = 0.08            # 8 cm air gap
    tray_frame_m: float = 0.02         # 2 cm tray frame
    plenum_height_m: float = 0.10      # 10 cm inlet/outlet plenum
    wall_clearance_m: float = 0.10     # 10 cm clearance around trays
    
    # Calculated chamber dimensions (set by calculate())
    chamber_height_m: float = 0.0
    chamber_length_m: float = 0.0
    chamber_width_m: float = 0.0
    chamber_volume_m3: float = 0.0
    
    # Air flow parameters
    target_velocity_m_per_s: float = 1.1   # Target velocity [m/s]
    air_density_kg_per_m3: float = 1.1     # At ~50°C
    
    # Calculated air flow (set by calculate())
    m_da_kg_per_s: float = 0.0         # Air mass flow rate
    volumetric_flow_m3_per_s: float = 0.0
    cross_section_m2: float = 0.0
    actual_velocity_m_per_s: float = 0.0
    
    # Multi-zone configuration
    multizone: MultiZoneConfig = field(default_factory=MultiZoneConfig)
    
    # Derived product masses
    m_fresh_kg: float = 0.0
    m_water_initial_kg: float = 0.0
    m_water_to_remove_kg: float = 0.0
    m_fresh_per_tray_kg: float = 0.0
    
    def calculate(self) -> 'ChamberGeometry':
        """Calculate all derived dimensions from input parameters.
        
        This method computes:
        1. Product masses (fresh, water content)
        2. Tray dimensions from loading density
        3. Chamber dimensions
        4. Air flow rate for target velocity
        5. Zone configuration (if multi-zone enabled)
        
        Returns:
            self (for method chaining)
        """
        
        # =====================================================================
        # STEP 1: Product Mass Calculations
        # =====================================================================
        # Fresh mass = dry mass × (1 + initial moisture)
        self.m_fresh_kg = self.m_p_dry_kg * (1 + self.X0_db)
        
        # Initial water = fresh - dry
        self.m_water_initial_kg = self.m_fresh_kg - self.m_p_dry_kg
        
        # Final water = dry mass × final moisture
        m_water_final = self.m_p_dry_kg * self.X_final_db
        
        # Water to remove
        self.m_water_to_remove_kg = self.m_water_initial_kg - m_water_final
        
        # Fresh mass per tray
        self.m_fresh_per_tray_kg = self.m_fresh_kg / self.n_trays
        
        # =====================================================================
        # STEP 2: Tray Dimensions
        # =====================================================================
        # Tray area from loading density
        # loading_density = m_fresh_per_tray / A_tray
        # A_tray = m_fresh_per_tray / loading_density
        self.tray_area_m2 = self.m_fresh_per_tray_kg / self.loading_density_kg_per_m2
        
        # Assume square trays
        self.tray_length_m = math.sqrt(self.tray_area_m2)
        self.tray_width_m = self.tray_length_m
        
        # =====================================================================
        # STEP 3: Chamber Dimensions
        # =====================================================================
        # Tray pitch = product + frame + air gap
        tray_pitch = self.product_thickness_m + self.tray_frame_m + self.air_gap_m
        
        # Stack height = n_trays × pitch
        stack_height = self.n_trays * tray_pitch
        
        # Chamber height = stack + inlet plenum + outlet plenum
        self.chamber_height_m = stack_height + 2 * self.plenum_height_m
        
        # Chamber length and width = tray + clearance
        self.chamber_length_m = self.tray_length_m + 2 * self.wall_clearance_m
        self.chamber_width_m = self.tray_width_m + 2 * self.wall_clearance_m
        
        # Chamber volume
        self.chamber_volume_m3 = (
            self.chamber_height_m * 
            self.chamber_length_m * 
            self.chamber_width_m
        )
        
        # =====================================================================
        # STEP 4: Air Flow Rate Calculation
        # =====================================================================
        # Cross-sectional area for air flow
        # A_cross = tray_width × air_gap
        self.cross_section_m2 = self.tray_width_m * self.air_gap_m
        
        # Air mass flow rate from target velocity
        # m_da = rho × v × A
        self.m_da_kg_per_s = (
            self.air_density_kg_per_m3 * 
            self.target_velocity_m_per_s * 
            self.cross_section_m2
        )
        
        # Volumetric flow rate
        self.volumetric_flow_m3_per_s = self.m_da_kg_per_s / self.air_density_kg_per_m3
        
        # Actual velocity (should equal target)
        self.actual_velocity_m_per_s = (
            self.m_da_kg_per_s / 
            (self.air_density_kg_per_m3 * self.cross_section_m2)
        )
        
        # =====================================================================
        # STEP 5: Zone Configuration
        # =====================================================================
        if self.multizone.enabled and not self.multizone.zones:
            self.multizone.zones = generate_default_zones(
                self.n_trays, 
                self.multizone.n_zones
            )
        
        if self.multizone.enabled:
            self.multizone.validate(self.n_trays)
        
        return self
    
    def get_tray_pitch_m(self) -> float:
        """Get tray-to-tray vertical spacing."""
        return self.product_thickness_m + self.tray_frame_m + self.air_gap_m
    
    def display(self) -> str:
        """Generate a formatted display of chamber specifications.
        
        Returns:
            Formatted string showing all chamber parameters.
        """
        
        lines = []
        lines.append("=" * 70)
        lines.append("DRYING CHAMBER SPECIFICATIONS")
        lines.append("=" * 70)
        
        # Product section
        lines.append("\n┌─────────────────────────────────────────────────────────────────────┐")
        lines.append("│                        PRODUCT SPECIFICATIONS                        │")
        lines.append("├─────────────────────────────────────────────────────────────────────┤")
        lines.append(f"│  Dry mass (m_p_dry_kg):        {self.m_p_dry_kg:>10.2f} kg                       │")
        lines.append(f"│  Initial moisture (X0_db):     {self.X0_db:>10.2f} kg/kg db                   │")
        lines.append(f"│  Fresh apple mass:             {self.m_fresh_kg:>10.2f} kg                       │")
        lines.append(f"│  Water to remove:              {self.m_water_to_remove_kg:>10.2f} kg                       │")
        lines.append(f"│  Product thickness:            {self.product_thickness_m*1000:>10.1f} mm                       │")
        lines.append("└─────────────────────────────────────────────────────────────────────┘")
        
        # Tray section
        lines.append("\n┌─────────────────────────────────────────────────────────────────────┐")
        lines.append("│                        TRAY CONFIGURATION                            │")
        lines.append("├─────────────────────────────────────────────────────────────────────┤")
        lines.append(f"│  Number of trays:              {self.n_trays:>10d}                            │")
        lines.append(f"│  Loading density:              {self.loading_density_kg_per_m2:>10.1f} kg/m²                     │")
        lines.append(f"│  Fresh mass per tray:          {self.m_fresh_per_tray_kg:>10.2f} kg                       │")
        lines.append(f"│  Tray dimensions:              {self.tray_length_m*100:>6.1f} × {self.tray_width_m*100:>6.1f} cm               │")
        lines.append(f"│  Tray area (each):             {self.tray_area_m2:>10.3f} m²                      │")
        lines.append(f"│  Total tray area:              {self.tray_area_m2 * self.n_trays:>10.2f} m²                      │")
        lines.append(f"│  Tray pitch (spacing):         {self.get_tray_pitch_m()*100:>10.1f} cm                       │")
        lines.append(f"│  Air gap between trays:        {self.air_gap_m*100:>10.1f} cm                       │")
        lines.append("└─────────────────────────────────────────────────────────────────────┘")
        
        # Chamber section
        lines.append("\n┌─────────────────────────────────────────────────────────────────────┐")
        lines.append("│                        CHAMBER DIMENSIONS                            │")
        lines.append("├─────────────────────────────────────────────────────────────────────┤")
        lines.append(f"│  Height (internal):            {self.chamber_height_m*100:>10.1f} cm                       │")
        lines.append(f"│  Length (internal):            {self.chamber_length_m*100:>10.1f} cm                       │")
        lines.append(f"│  Width (internal):             {self.chamber_width_m*100:>10.1f} cm                       │")
        lines.append(f"│  Internal volume:              {self.chamber_volume_m3*1000:>10.0f} liters                   │")
        lines.append("└─────────────────────────────────────────────────────────────────────┘")
        
        # Air flow section
        lines.append("\n┌─────────────────────────────────────────────────────────────────────┐")
        lines.append("│                        AIR FLOW PARAMETERS                           │")
        lines.append("├─────────────────────────────────────────────────────────────────────┤")
        lines.append(f"│  Target velocity:              {self.target_velocity_m_per_s:>10.2f} m/s                     │")
        lines.append(f"│  Actual velocity:              {self.actual_velocity_m_per_s:>10.2f} m/s                     │")
        lines.append(f"│  Cross-section area:           {self.cross_section_m2:>10.4f} m²                      │")
        lines.append(f"│  Mass flow rate:               {self.m_da_kg_per_s:>10.4f} kg/s                    │")
        lines.append(f"│  Mass flow rate:               {self.m_da_kg_per_s*3600:>10.1f} kg/h                     │")
        lines.append(f"│  Volumetric flow:              {self.volumetric_flow_m3_per_s*3600:>10.1f} m³/h                     │")
        lines.append(f"│  Air density (at 50°C):        {self.air_density_kg_per_m3:>10.2f} kg/m³                   │")
        lines.append("└─────────────────────────────────────────────────────────────────────┘")
        
        # Zone configuration section
        lines.append("\n┌─────────────────────────────────────────────────────────────────────┐")
        lines.append("│                        ZONE CONFIGURATION                            │")
        lines.append("├─────────────────────────────────────────────────────────────────────┤")
        
        if self.multizone.enabled:
            lines.append(f"│  Multi-zone:                   {'ENABLED':>10s}                            │")
            lines.append(f"│  Number of zones:              {len(self.multizone.zones):>10d}                            │")
            lines.append(f"│  Mixing efficiency:            {self.multizone.mixing_efficiency*100:>10.1f} %                       │")
            lines.append(f"│  Number of inlets:             {len(self.multizone.zones):>10d}                            │")
            lines.append(f"│  Number of outlets:            {1:>10d} (single exhaust)           │")
            lines.append("├─────────────────────────────────────────────────────────────────────┤")
            
            for zone in self.multizone.zones:
                trays_str = f"[{zone.tray_indices[0]}-{zone.tray_indices[-1]}]"
                flow_kg_s = self.m_da_kg_per_s * zone.flow_fraction
                inlet_type = "Fresh only" if not zone.receives_upstream_exhaust else "Mixed"
                lines.append(f"│  {zone.name}: Trays {trays_str:<8s}  Flow: {zone.flow_fraction*100:>4.0f}% = {flow_kg_s:.4f} kg/s  ({inlet_type:<10s}) │")
        else:
            lines.append(f"│  Multi-zone:                   {'DISABLED':>10s}                           │")
            lines.append(f"│  Configuration:                {'Single inlet':>12s}                        │")
            lines.append(f"│  Number of inlets:             {1:>10d}                            │")
            lines.append(f"│  Number of outlets:            {1:>10d}                            │")
        
        lines.append("└─────────────────────────────────────────────────────────────────────┘")
        
        # Equations section
        lines.append("\n┌─────────────────────────────────────────────────────────────────────┐")
        lines.append("│                        KEY EQUATIONS USED                            │")
        lines.append("├─────────────────────────────────────────────────────────────────────┤")
        lines.append("│  Fresh mass:     m_fresh = m_dry × (1 + X0_db)                       │")
        lines.append("│  Tray area:      A_tray = m_fresh_per_tray / loading_density         │")
        lines.append("│  Cross-section:  A_cross = tray_width × air_gap                      │")
        lines.append("│  Air flow:       m_da = ρ_air × v_target × A_cross                   │")
        lines.append("│  Tray pitch:     pitch = δ_product + δ_frame + air_gap               │")
        lines.append("└─────────────────────────────────────────────────────────────────────┘")
        
        return "\n".join(lines)
    
    def print_display(self):
        """Print the chamber specifications to console."""
        print(self.display())


# =============================================================================
# ZONE GENERATION HELPER
# =============================================================================

def generate_default_zones(n_trays: int, n_zones: int) -> List[ZoneConfig]:
    """Generate default zone configuration.
    
    This function creates a balanced zone distribution where:
    - Trays are divided as evenly as possible among zones
    - The first zone gets slightly more flow (40%) to compensate
      for its exhaust being diluted downstream
    - Later zones get equal shares of remaining flow
    
    Args:
        n_trays: Total number of trays
        n_zones: Number of zones to create
    
    Returns:
        List of ZoneConfig objects
    
    Example for 10 trays, 3 zones:
        Zone_A: trays [0,1,2,3], flow=0.40, receives_upstream=False
        Zone_B: trays [4,5,6],   flow=0.30, receives_upstream=True
        Zone_C: trays [7,8,9],   flow=0.30, receives_upstream=True
    """
    
    if n_zones < 1:
        raise ValueError("n_zones must be >= 1")
    if n_zones > n_trays:
        raise ValueError(f"n_zones ({n_zones}) cannot exceed n_trays ({n_trays})")
    
    # Calculate trays per zone
    base_trays = n_trays // n_zones
    extra_trays = n_trays % n_zones
    
    # First zones get extra trays if not evenly divisible
    trays_per_zone = [
        base_trays + (1 if i < extra_trays else 0) 
        for i in range(n_zones)
    ]
    
    # Flow fractions based on number of zones
    # First zone gets more to compensate for dilution downstream
    if n_zones == 1:
        flow_fractions = [1.0]
    elif n_zones == 2:
        flow_fractions = [0.55, 0.45]
    elif n_zones == 3:
        flow_fractions = [0.40, 0.30, 0.30]
    elif n_zones == 4:
        flow_fractions = [0.35, 0.25, 0.20, 0.20]
    elif n_zones == 5:
        flow_fractions = [0.30, 0.20, 0.20, 0.15, 0.15]
    else:
        # Generic: first zone 35%, rest split evenly
        first_zone_frac = 0.35
        remaining = 1.0 - first_zone_frac
        other_frac = remaining / (n_zones - 1)
        flow_fractions = [first_zone_frac] + [other_frac] * (n_zones - 1)
    
    # Normalize to ensure sum = 1.0
    total = sum(flow_fractions)
    flow_fractions = [f / total for f in flow_fractions]
    
    # Build zone configs
    zones = []
    tray_idx = 0
    
    for i in range(n_zones):
        tray_indices = list(range(tray_idx, tray_idx + trays_per_zone[i]))
        tray_idx += trays_per_zone[i]
        
        zones.append(ZoneConfig(
            name=f"Zone_{chr(65+i)}",  # Zone_A, Zone_B, Zone_C, ...
            tray_indices=tray_indices,
            flow_fraction=flow_fractions[i],
            receives_upstream_exhaust=(i > 0)  # First zone doesn't receive exhaust
        ))
    
    return zones


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def calculate_chamber_geometry(
    m_p_dry_kg: float = 10.0,
    X0_db: float = 6.5,
    n_trays: int = 10,
    loading_density: float = 5.0,
    target_velocity: float = 1.1,
    air_gap_m: float = 0.08,
    enable_multizone: bool = False,
    n_zones: int = 3,
    mixing_efficiency: float = 1.0,
) -> ChamberGeometry:
    """Convenience function to calculate chamber geometry.
    
    Args:
        m_p_dry_kg: Dry mass of product [kg]
        X0_db: Initial moisture content [kg water / kg dry]
        n_trays: Number of trays
        loading_density: Loading density [kg fresh / m²]
        target_velocity: Target air velocity [m/s]
        air_gap_m: Air gap between trays [m]
        enable_multizone: Enable multi-zone design
        n_zones: Number of zones (if multi-zone enabled)
        mixing_efficiency: Mixing efficiency (1.0 = perfect)
    
    Returns:
        Calculated ChamberGeometry object
    """
    
    geom = ChamberGeometry(
        m_p_dry_kg=m_p_dry_kg,
        X0_db=X0_db,
        n_trays=n_trays,
        loading_density_kg_per_m2=loading_density,
        target_velocity_m_per_s=target_velocity,
        air_gap_m=air_gap_m,
        multizone=MultiZoneConfig(
            enabled=enable_multizone,
            n_zones=n_zones,
            mixing_efficiency=mixing_efficiency,
        )
    )
    
    return geom.calculate()


# =============================================================================
# MAIN - DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CHAMBER GEOMETRY CALCULATION DEMONSTRATION")
    print("="*70)
    
    # Example 1: Your current 75 kg batch (m_dry = 10 kg)
    print("\n>>> Example 1: Your current simulation (75 kg fresh apples)")
    geom1 = calculate_chamber_geometry(
        m_p_dry_kg=10.0,      # This gives 75 kg fresh
        X0_db=6.5,
        n_trays=10,
        loading_density=5.0,
        target_velocity=1.1,
        enable_multizone=False
    )
    geom1.print_display()
    
    # Example 2: Same batch with multi-zone
    print("\n\n>>> Example 2: Same batch with 3-zone multi-inlet design")
    geom2 = calculate_chamber_geometry(
        m_p_dry_kg=10.0,
        X0_db=6.5,
        n_trays=10,
        loading_density=5.0,
        target_velocity=1.1,
        enable_multizone=True,
        n_zones=3,
        mixing_efficiency=1.0
    )
    geom2.print_display()
    
    # Example 3: Smaller 10 kg fresh batch
    print("\n\n>>> Example 3: Smaller batch (10 kg fresh apples)")
    geom3 = calculate_chamber_geometry(
        m_p_dry_kg=10.0 / 7.5,  # 1.33 kg dry = 10 kg fresh
        X0_db=6.5,
        n_trays=5,
        loading_density=4.5,
        target_velocity=1.0,
        enable_multizone=True,
        n_zones=2
    )
    geom3.print_display()
    
    print("\n" + "="*70)
    print("KEY VARIABLES YOU CAN MODIFY:")
    print("="*70)
    print("""
    1. m_p_dry_kg       : Dry mass of product
                          → Determines fresh mass: m_fresh = m_dry × (1 + X0)
                          → Your current value: 10.0 kg (= 75 kg fresh apples)
    
    2. n_trays          : Number of trays
                          → More trays = thinner layers, faster drying
                          → But: more non-uniformity without multi-zone
    
    3. loading_density  : kg fresh product per m² tray area
                          → Typical: 3-5 kg/m² for apple slices
                          → Lower = faster drying, larger trays
    
    4. target_velocity  : Air velocity over product [m/s]
                          → Typical: 0.8-1.5 m/s
                          → Higher = faster drying, more fan power
    
    5. air_gap_m        : Vertical gap between trays [m]
                          → Typical: 0.05-0.10 m (5-10 cm)
                          → Larger = more uniform airflow, taller chamber
    
    6. enable_multizone : Enable multi-inlet design
                          → True = fresh air injected at multiple levels
                          → Improves uniformity by 50-70%
    
    7. n_zones          : Number of zones (if multi-zone enabled)
                          → Rule: max 3-4 trays per zone
                          → For 10 trays: 3 zones recommended
    """)
