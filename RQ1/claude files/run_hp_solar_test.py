#!/usr/bin/env python3
"""Test script for HP+Solar dryer simulation.

This script runs the Phase-1 dryer with combined heat pump and solar
collector heating, demonstrating the hybrid system performance.

Usage:
    python run_hp_solar_test.py --ambient-csv data/ambient/kathmandu_extended.csv
    python run_hp_solar_test.py --location kathmandu --A_col 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_ROOT = SCRIPT_DIR.parent / "src" if (SCRIPT_DIR.parent / "src").exists() else SCRIPT_DIR

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rq1.config import (
    AmbientConfig,
    DryerConfig,
    KineticsConfig,
    SimulationConfig,
    HeatPumpConfig,
    SolarCollectorConfig,
)
from rq1.dryer_phase1 import run_phase1_simulation


# Default ambient file paths by location
LOCATION_FILES = {
    "kathmandu": "data/ambient/kathmandu_extended.csv",
    "dhulikhel": "data/ambient/dhulikhel_extended.csv",
    "biratnagar": "data/ambient/biratnagar_extended.csv",
    "taplejung": "data/ambient/taplejung_extended.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    
    # Input options
    parser.add_argument(
        "--ambient-csv",
        type=Path,
        help="Path to ambient weather CSV file",
    )
    parser.add_argument(
        "--location",
        choices=list(LOCATION_FILES.keys()),
        help="Location name (uses default path)",
    )
    
    # Dryer parameters
    parser.add_argument("--Tset", type=float, default=50.0, help="Target temperature [°C]")
    parser.add_argument("--X0", type=float, default=2.5, help="Initial moisture content (dry basis)")
    parser.add_argument("--Xeq", type=float, default=0.05, help="Equilibrium moisture content")
    parser.add_argument("--m_p_dry", type=float, default=10.0, help="Dry mass of product [kg]")
    parser.add_argument("--dt_s", type=float, default=60.0, help="Time step [s]")
    parser.add_argument("--n-trays", type=int, default=4, help="Number of trays")
    parser.add_argument("--max-steps", type=int, default=None, help="Max simulation steps")
    
    # HP parameters
    parser.add_argument("--Q_HP_nom", type=float, default=10.0, help="HP nominal capacity [kW]")
    parser.add_argument("--COP_nom", type=float, default=3.33, help="HP nominal COP")
    parser.add_argument("--eta_carnot", type=float, default=0.50, help="Carnot efficiency factor")
    parser.add_argument(
        "--hp-source",
        choices=["ambient", "exhaust", "dual"],
        default="ambient",
        help="HP heat source mode",
    )
    
    # Solar parameters
    parser.add_argument("--A_col", type=float, default=10.0, help="Collector area [m²]")
    parser.add_argument("--eta_optical", type=float, default=0.75, help="Optical efficiency")
    parser.add_argument("--U_loss", type=float, default=6.0, help="Heat loss coefficient [W/(m²·K)]")
    parser.add_argument("--GHI_threshold", type=float, default=50.0, help="Min GHI for operation [W/m²]")
    
    # Control options
    parser.add_argument(
        "--use-backup",
        action="store_true",
        help="Enable backup electric heater",
    )
    parser.add_argument(
        "--MR-threshold",
        type=float,
        default=0.05,
        help="MR termination threshold",
    )
    
    # Output
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/hp_solar_test"),
        help="Output directory",
    )
    
    return parser.parse_args()


def get_ambient_path(args: argparse.Namespace) -> Path:
    """Resolve ambient CSV path from arguments."""
    if args.ambient_csv:
        return args.ambient_csv
    elif args.location:
        return Path(LOCATION_FILES[args.location])
    else:
        raise ValueError("Must specify either --ambient-csv or --location")


def main() -> None:
    args = parse_args()
    
    ambient_path = get_ambient_path(args)
    if not ambient_path.exists():
        print(f"ERROR: Ambient file not found: {ambient_path}")
        print("Please ensure weather data is available.")
        sys.exit(1)
    
    print(f"=" * 60)
    print("HP + SOLAR DRYER TEST")
    print(f"=" * 60)
    print(f"Ambient file: {ambient_path}")
    print(f"T_set: {args.Tset}°C")
    print(f"HP capacity: {args.Q_HP_nom} kW")
    print(f"Solar area: {args.A_col} m²")
    print(f"Backup heater: {'Enabled' if args.use_backup else 'Disabled'}")
    print(f"=" * 60)
    
    # Configure ambient
    ambient_cfg = AmbientConfig(
        csv_path=ambient_path,
        start_index=0,
        max_steps=args.max_steps,
    )
    
    # Configure heat pump (enabled)
    hp_cfg = HeatPumpConfig(
        enabled=True,
        Q_HP_nom_kW=args.Q_HP_nom,
        COP_nom=args.COP_nom,
        eta_carnot=args.eta_carnot,
        source_mode=args.hp_source,
    )
    
    # Configure solar (enabled)
    solar_cfg = SolarCollectorConfig(
        enabled=True,
        A_col_m2=args.A_col,
        eta_optical=args.eta_optical,
        U_loss_W_per_m2K=args.U_loss,
        GHI_threshold_W_per_m2=args.GHI_threshold,
    )
    
    # Configure dryer
    dryer_cfg = DryerConfig(
        r_recirc=0.0,  # No recirculation for baseline
        T_set_C=args.Tset,
        X0_db=args.X0,
        X_eq_db=args.Xeq,
        m_p_dry_kg=args.m_p_dry,
        dt_s=args.dt_s,
        n_trays=args.n_trays,
        tray_depth_m=0.05,
        require_all_trays_dried=True,
        MR_termination_threshold=args.MR_threshold,
        allow_variable_Tset=not args.use_backup,
        use_backup_heater=args.use_backup,
    )
    
    # Configure kinetics
    kinetics_cfg = KineticsConfig(
        mode="phase2_midilli",
        use_simple_K=True,
        use_knb_table=True,
        debug_keff=False,
    )
    
    # Build simulation config
    sim_cfg = SimulationConfig(
        ambient=ambient_cfg,
        dryer=dryer_cfg,
        kinetics=kinetics_cfg,
        heat_pump=hp_cfg,
        solar=solar_cfg,
    )
    
    # Run simulation
    print("\nRunning simulation...")
    result = run_phase1_simulation(sim_cfg)
    
    # Save results
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_dir / "hp_solar_results.csv"
    result.df.to_csv(output_csv, index=False)
    print(f"\nResults saved to: {output_csv}")
    
    # Print summary
    df = result.df
    if not df.empty:
        print("\n" + "=" * 60)
        print("SIMULATION SUMMARY")
        print("=" * 60)
        
        final_row = df.iloc[-1]
        
        # Time
        drying_time_h = final_row["time_s"] / 3600.0
        print(f"Drying time:      {drying_time_h:.2f} hours")
        
        # Final state
        print(f"Final MR:         {final_row['MR']:.4f}")
        
        # Check all trays
        all_trays_dried = all(
            df[f"MR_tray{i}"].iloc[-1] < args.MR_threshold
            for i in range(args.n_trays)
        )
        print(f"All trays dried:  {'✓' if all_trays_dried else '✗'}")
        
        # Energy metrics
        print("\n--- Energy Performance ---")
        if "SEC_kWh_per_kg" in final_row and final_row["SEC_kWh_per_kg"] is not None:
            print(f"SEC (elec):       {final_row['SEC_kWh_per_kg']:.3f} kWh/kg")
        
        if "COP_system" in final_row and final_row["COP_system"] is not None:
            print(f"System COP:       {final_row['COP_system']:.2f}")
        
        if "solar_fraction" in final_row:
            print(f"Solar fraction:   {100*final_row['solar_fraction']:.1f}%")
        
        if "hp_fraction" in final_row:
            print(f"HP fraction:      {100*final_row['hp_fraction']:.1f}%")
        
        # Energy totals
        print("\n--- Energy Totals ---")
        if "W_HP_total_kWh" in final_row:
            print(f"W_HP (elec):      {final_row['W_HP_total_kWh']:.2f} kWh")
        
        if "Q_HP_total_kWh" in final_row:
            print(f"Q_HP (thermal):   {final_row['Q_HP_total_kWh']:.2f} kWh")
        
        if "Q_solar_total_kWh" in final_row:
            print(f"Q_solar:          {final_row['Q_solar_total_kWh']:.2f} kWh")
        
        if "Q_backup_total_kWh" in final_row and final_row["Q_backup_total_kWh"] > 0:
            print(f"Q_backup:         {final_row['Q_backup_total_kWh']:.2f} kWh")
        
        # Temperature stats
        print("\n--- Temperature Performance ---")
        print(f"T_in mean:        {df['T_in_C'].mean():.1f}°C")
        print(f"T_in min:         {df['T_in_C'].min():.1f}°C")
        print(f"T_in max:         {df['T_in_C'].max():.1f}°C")
        
        # Count hours in different temperature ranges
        hours_above_45 = (df["T_in_C"] >= 45).sum() * args.dt_s / 3600.0
        hours_40_45 = ((df["T_in_C"] >= 40) & (df["T_in_C"] < 45)).sum() * args.dt_s / 3600.0
        hours_below_40 = (df["T_in_C"] < 40).sum() * args.dt_s / 3600.0
        print(f"Hours T>=45°C:    {hours_above_45:.1f} h ({100*hours_above_45/drying_time_h:.0f}%)")
        print(f"Hours 40-45°C:    {hours_40_45:.1f} h ({100*hours_40_45/drying_time_h:.0f}%)")
        print(f"Hours T<40°C:     {hours_below_40:.1f} h ({100*hours_below_40/drying_time_h:.0f}%)")
        
        # HP operation
        print("\n--- HP Operation ---")
        hp_hours_active = (df["HP_running"].sum() * args.dt_s) / 3600.0
        hp_hours_at_cap = (df["HP_at_capacity"].sum() * args.dt_s) / 3600.0
        print(f"HP hours active:  {hp_hours_active:.1f} h")
        print(f"HP at capacity:   {hp_hours_at_cap:.1f} h ({100*hp_hours_at_cap/drying_time_h:.0f}%)")
        
        cop_when_running = df.loc[df["HP_running"], "COP_actual"].mean()
        print(f"Avg COP (running):{cop_when_running:.2f}")
        
        # Solar operation
        print("\n--- Solar Operation ---")
        solar_hours_active = (df["solar_active"].sum() * args.dt_s) / 3600.0
        print(f"Solar hours:      {solar_hours_active:.1f} h")
        
        if df["solar_active"].any():
            avg_eta_solar = df.loc[df["solar_active"], "eta_collector"].mean()
            avg_q_solar = df.loc[df["solar_active"], "Q_solar_kW"].mean()
            print(f"Avg efficiency:   {100*avg_eta_solar:.1f}%")
            print(f"Avg Q_solar:      {avg_q_solar:.2f} kW")
        
        # GHI stats
        print(f"\nGHI mean:         {df['GHI_Wm2'].mean():.0f} W/m²")
        print(f"GHI max:          {df['GHI_Wm2'].max():.0f} W/m²")
        
        # Comparison note
        print("\n" + "=" * 60)
        print("COMPARISON WITH BASELINE")
        print("=" * 60)
        print("Electric-only baseline: SEC = 4.81 kWh/kg")
        if "SEC_kWh_per_kg" in final_row and final_row["SEC_kWh_per_kg"] is not None:
            sec_reduction = 100 * (1 - final_row["SEC_kWh_per_kg"] / 4.81)
            print(f"HP+Solar SEC:           {final_row['SEC_kWh_per_kg']:.3f} kWh/kg")
            print(f"Reduction:              {sec_reduction:.0f}%")
        print("=" * 60)


if __name__ == "__main__":
    main()
