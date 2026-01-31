"""Master runner script for solar-HP dryer simulations with Multi-Zone support.

UPDATED VERSION - Supports both single-inlet and multi-zone configurations.

Usage in VSCode Terminal:
=========================

# Quick test (single-inlet, Config A, Kathmandu)
python run_solar_hp_configs.py --test

# Quick test with multi-zone
python run_solar_hp_configs.py --test --multizone

# Run all configs for one location (single-inlet)
python run_solar_hp_configs.py --configs A B C D E --location kathmandu --solar-area 12

# Run all configs for one location (multi-zone)
python run_solar_hp_configs.py --configs A B C D E --location kathmandu --solar-area 12 --multizone

# Run all configs, all locations (single-inlet)
python run_solar_hp_configs.py --full

# Run all configs, all locations (multi-zone)
python run_solar_hp_configs.py --full --multizone

# Compare single vs multi-zone for one config
python run_solar_hp_configs.py --compare --config A --location kathmandu --solar-area 12

# Full comparison (all configs, all locations)
python run_solar_hp_configs.py --compare --full

# Custom: specific configs, locations, and solar areas
python run_solar_hp_configs.py --configs A E --locations kathmandu dhulikhel --solar-areas 10 12 15 --multizone

# Change number of zones (default is 3)
python run_solar_hp_configs.py --test --multizone --n-zones 4

# Change product amount (dry mass in kg)
python run_solar_hp_configs.py --test --m-dry 5.0

# Change air velocity
python run_solar_hp_configs.py --test --velocity 1.0


Author: Wasti (SAHPD Thesis)
Date: January 2026
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

import pandas as pd

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import (
    DryerConfiguration,
    make_config_A_HP_only,
    make_config_B_solar_HP_series,
    make_config_C_solar_HP_evap,
    make_config_D_solar_only,
    make_config_E_solar_evap_cond_cascade,
)
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run solar-HP dryer simulations with optional multi-zone support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
---------
  # Quick test
  python run_solar_hp_configs.py --test
  
  # All configs, all locations, with multi-zone
  python run_solar_hp_configs.py --full --multizone
  
  # Compare single vs multi-zone
  python run_solar_hp_configs.py --compare --config A --location kathmandu
  
  # Custom run
  python run_solar_hp_configs.py --configs A E --locations kathmandu dhulikhel --multizone
        """
    )
    
    # Run modes
    mode_group = parser.add_argument_group("Run Modes")
    mode_group.add_argument("--test", action="store_true", 
                           help="Quick test (Config A, Kathmandu, 48h)")
    mode_group.add_argument("--full", action="store_true", 
                           help="Full sweep (all configs × locations × solar areas)")
    mode_group.add_argument("--compare", action="store_true",
                           help="Compare single-inlet vs multi-zone")
    
    # Configuration selection
    config_group = parser.add_argument_group("Configuration Selection")
    config_group.add_argument("--config", type=str, choices=["A", "B", "C", "D", "E"],
                             help="Single config to run")
    config_group.add_argument("--configs", nargs="+", choices=["A", "B", "C", "D", "E"],
                             help="Multiple configs to run")
    config_group.add_argument("--location", type=str,
                             help="Single location (e.g., kathmandu)")
    config_group.add_argument("--locations", nargs="+",
                             help="Multiple locations")
    config_group.add_argument("--solar-area", type=float,
                             help="Single solar collector area [m²]")
    config_group.add_argument("--solar-areas", nargs="+", type=float,
                             help="Multiple solar areas [m²]")
    
    # Multi-zone options
    mz_group = parser.add_argument_group("Multi-Zone Options")
    mz_group.add_argument("--multizone", action="store_true",
                         help="Enable multi-zone design")
    mz_group.add_argument("--n-zones", type=int, default=3,
                         help="Number of zones (default: 3)")
    mz_group.add_argument("--mixing-efficiency", type=float, default=1.0,
                         help="Mixing efficiency 0-1 (default: 1.0 = perfect)")
    
    # Product/dryer options
    dryer_group = parser.add_argument_group("Dryer Options")
    dryer_group.add_argument("--m-dry", type=float, default=10.0,
                            help="Dry mass of product [kg] (default: 10.0 = 75kg fresh)")
    dryer_group.add_argument("--n-trays", type=int, default=10,
                            help="Number of trays (default: 10)")
    dryer_group.add_argument("--velocity", type=float, default=1.1,
                            help="Target air velocity [m/s] (default: 1.1)")
    dryer_group.add_argument("--T-set", type=float, default=50.0,
                            help="Target drying temperature [°C] (default: 50)")
    
    # Simulation options
    sim_group = parser.add_argument_group("Simulation Options")
    sim_group.add_argument("--max-hours", type=float, default=72.0,
                          help="Max simulation time [hours] (default: 72)")
    sim_group.add_argument("--output-dir", type=str, default="outputs",
                          help="Output directory (default: outputs)")
    sim_group.add_argument("--quiet", action="store_true",
                          help="Suppress geometry display")
    
    return parser.parse_args()


def get_weather_path(location: str) -> Path:
    """Get weather file path for location."""
    
    possible_paths = [
        PROJECT_ROOT / "data" / "ambient" / f"{location}_pvgis_standard.csv",
        PROJECT_ROOT / "data" / "ambient" / f"{location}.csv",
        PROJECT_ROOT / "outputs" / f"{location}_pvgis_standard.csv",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError(f"Weather file for '{location}' not found. Tried: {possible_paths}")


def get_phase2_path() -> Optional[Path]:
    """Get phase2c_for_chamber.csv path."""
    
    possible_paths = [
        PROJECT_ROOT / "outputs" / "phase2c_for_chamber.csv",
        PROJECT_ROOT / "data" / "phase2c_for_chamber.csv",
        PROJECT_ROOT / "outputs" / "phase1_runs" / "phase2c_for_chamber.csv",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    print("[WARNING] phase2c_for_chamber.csv not found, using fallback kinetics")
    return None


def create_config(config_letter: str, location: str, solar_area_m2: float, args):
    """Create simulation configuration."""
    
    weather_path = get_weather_path(location)
    phase2_path = get_phase2_path()
    
    # Common kwargs for all config types
    common_kwargs = {
        "ambient_csv": weather_path,
        "phase2_root": phase2_path.parent if phase2_path else None,
        "m_p_dry_kg": args.m_dry,
        "n_trays": args.n_trays,
        "target_velocity": args.velocity,
        "enable_multizone": args.multizone,
        "n_zones": args.n_zones,
        "display_geometry": not args.quiet,
    }
    
    if config_letter == "A":
        cfg = make_config_A_HP_only(
            T_set_C=args.T_set,
            **common_kwargs,
        )
    elif config_letter == "B":
        cfg = make_config_B_solar_HP_series(
            solar_area_m2=solar_area_m2,
            T_set_C=args.T_set,
            **common_kwargs,
        )
    elif config_letter == "C":
        cfg = make_config_C_solar_HP_evap(
            solar_area_m2=solar_area_m2,
            T_set_C=args.T_set,
            **common_kwargs,
        )
    elif config_letter == "D":
        cfg = make_config_D_solar_only(
            solar_area_m2=solar_area_m2,
            **common_kwargs,
        )
    elif config_letter == "E":
        cfg = make_config_E_solar_evap_cond_cascade(
            solar_area_m2=solar_area_m2,
            T_set_C=args.T_set,
            **common_kwargs,
        )
    else:
        raise ValueError(f"Unknown config: {config_letter}")
    
    # Set mixing efficiency if multi-zone
    if args.multizone:
        cfg.dryer.multizone.mixing_efficiency = args.mixing_efficiency
    
    # Set simulation limits
    cfg.max_simulation_time_s = args.max_hours * 3600.0
    
    return cfg


def run_single_simulation(config_letter: str, location: str, solar_area_m2: float, 
                          args, mode_suffix: str = "") -> Dict[str, Any]:
    """Run one simulation and return results."""
    
    mode_str = "Multi-Zone" if args.multizone else "Single-Inlet"
    
    print(f"\n{'='*80}")
    print(f"Config {config_letter} | {location} | A_solar={solar_area_m2}m² | {mode_str}")
    print(f"{'='*80}\n")
    
    # Create config
    cfg = create_config(config_letter, location, solar_area_m2, args)
    
    # Run simulation
    result = run_solar_hp_dryer_simulation(cfg)
    
    # Determine output path
    mz_suffix = f"_mz{args.n_zones}" if args.multizone else ""
    output_dir = PROJECT_ROOT / args.output_dir / f"config_{config_letter}{mz_suffix}" / location
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"Ac_{solar_area_m2:.0f}m2{mode_suffix}.csv"
    result.df.to_csv(output_file, index=False)
    
    print(f"\n{result.final_message}")
    print(f"Saved: {output_file}")
    
    # Extract summary metrics
    summary = {
        "config": config_letter,
        "location": location,
        "solar_area_m2": solar_area_m2,
        "multizone": args.multizone,
        "n_zones": args.n_zones if args.multizone else 1,
        "success": True,
        "message": result.final_message,
    }
    
    if not result.df.empty:
        final_row = result.df.iloc[-1]
        summary["water_removed_kg"] = final_row.get("m_w_cum_kg", 0)
        summary["time_h"] = final_row.get("time_h", 0)
        summary["W_comp_kWh"] = final_row.get("W_comp_cum_kWh", 0)
        summary["Q_solar_kWh"] = final_row.get("Q_solar_cum_kWh", 0)
        
        # Get final SEC
        if "SEC_elec_kWh_per_kg" in result.df.columns:
            sec = result.df["SEC_elec_kWh_per_kg"].dropna()
            if not sec.empty:
                summary["SEC_kWh_per_kg"] = sec.iloc[-1]
        
        # Calculate uniformity (tray drying times)
        tray_times = []
        for i in range(cfg.dryer.n_trays):
            mr_col = f"MR_tray_{i}"
            if mr_col in result.df.columns:
                # Find time when MR < 0.05
                below_threshold = result.df[result.df[mr_col] < 0.05]
                if not below_threshold.empty:
                    tray_times.append(below_threshold.iloc[0]["time_h"])
        
        if tray_times:
            summary["t_dry_min_h"] = min(tray_times)
            summary["t_dry_max_h"] = max(tray_times)
            summary["t_dry_range_h"] = max(tray_times) - min(tray_times)
            summary["uniformity_pct"] = 100 * (1 - summary["t_dry_range_h"] / max(tray_times))
        
        # Print summary
        print(f"\n  Water removed: {summary.get('water_removed_kg', 0):.2f} kg")
        print(f"  Time: {summary.get('time_h', 0):.1f} hours")
        if summary.get("W_comp_kWh", 0) > 0:
            print(f"  W_comp: {summary['W_comp_kWh']:.2f} kWh")
        if summary.get("Q_solar_kWh", 0) > 0:
            print(f"  Q_solar: {summary['Q_solar_kWh']:.2f} kWh")
        if "SEC_kWh_per_kg" in summary:
            print(f"  SEC: {summary['SEC_kWh_per_kg']:.3f} kWh/kg")
        if "uniformity_pct" in summary:
            print(f"  Uniformity: {summary['uniformity_pct']:.1f}% (range: {summary['t_dry_range_h']:.1f}h)")
    
    return summary


def run_comparison(config_letter: str, location: str, solar_area_m2: float, args):
    """Run both single-inlet and multi-zone, then compare."""
    
    print(f"\n{'#'*80}")
    print(f"# COMPARISON: Config {config_letter} | {location} | A_solar={solar_area_m2}m²")
    print(f"{'#'*80}")
    
    results = []
    
    # Run single-inlet
    print("\n>>> Running SINGLE-INLET simulation...")
    args_single = argparse.Namespace(**vars(args))
    args_single.multizone = False
    result_single = run_single_simulation(config_letter, location, solar_area_m2, 
                                          args_single, "_single")
    results.append(result_single)
    
    # Run multi-zone
    print("\n>>> Running MULTI-ZONE simulation...")
    args_mz = argparse.Namespace(**vars(args))
    args_mz.multizone = True
    result_mz = run_single_simulation(config_letter, location, solar_area_m2,
                                      args_mz, "_multizone")
    results.append(result_mz)
    
    # Print comparison
    print(f"\n{'='*80}")
    print("COMPARISON RESULTS")
    print(f"{'='*80}")
    
    print(f"\n{'Metric':<25} {'Single-Inlet':>15} {'Multi-Zone':>15} {'Improvement':>15}")
    print("-" * 70)
    
    metrics = [
        ("Drying time (h)", "time_h", "lower"),
        ("SEC (kWh/kg)", "SEC_kWh_per_kg", "lower"),
        ("Uniformity (%)", "uniformity_pct", "higher"),
        ("Time range (h)", "t_dry_range_h", "lower"),
    ]
    
    for name, key, better in metrics:
        v_single = result_single.get(key, "N/A")
        v_mz = result_mz.get(key, "N/A")
        
        if isinstance(v_single, (int, float)) and isinstance(v_mz, (int, float)):
            if better == "lower":
                improvement = (v_single - v_mz) / v_single * 100 if v_single > 0 else 0
            else:
                improvement = (v_mz - v_single) / v_single * 100 if v_single > 0 else 0
            
            print(f"{name:<25} {v_single:>15.2f} {v_mz:>15.2f} {improvement:>14.1f}%")
        else:
            print(f"{name:<25} {str(v_single):>15} {str(v_mz):>15} {'N/A':>15}")
    
    return results


def main():
    args = parse_args()
    
    print("\n" + "=" * 80)
    print("SOLAR-HP DRYER SIMULATION RUNNER (with Multi-Zone Support)")
    print("=" * 80)
    
    # Determine what to run
    if args.test:
        configs = ["A"]
        locations = ["kathmandu"]
        solar_areas = [0.0] if not args.multizone else [12.0]
        mode = "TEST"
        
    elif args.full:
        configs = ["A", "B", "C", "D", "E"]
        locations = ["kathmandu", "dhulikhel", "biratnagar", "taplejung"]
        solar_areas = [0, 5, 10, 12, 15, 20]
        mode = "FULL SWEEP"
        
    elif args.config and args.location:
        configs = [args.config]
        locations = [args.location]
        solar_areas = [args.solar_area if args.solar_area is not None else 12.0]
        mode = "SINGLE"
        
    elif args.configs or args.locations:
        configs = args.configs if args.configs else ["A"]
        locations = args.locations if args.locations else ["kathmandu"]
        solar_areas = args.solar_areas if args.solar_areas else [12.0]
        mode = "CUSTOM"
        
    else:
        print("\nERROR: Must specify --test, --full, or provide --config/--configs\n")
        print("Quick examples:")
        print("  python run_solar_hp_configs.py --test")
        print("  python run_solar_hp_configs.py --test --multizone")
        print("  python run_solar_hp_configs.py --full --multizone")
        print("  python run_solar_hp_configs.py --compare --config A --location kathmandu")
        sys.exit(1)
    
    # Print run info
    mz_str = f"Multi-Zone ({args.n_zones} zones)" if args.multizone else "Single-Inlet"
    print(f"\nMode: {mode} | {mz_str}")
    print(f"Configs: {configs}")
    print(f"Locations: {locations}")
    print(f"Solar areas: {solar_areas}")
    print(f"Product: {args.m_dry} kg dry ({args.m_dry * 7.5:.1f} kg fresh)")
    print(f"Air velocity: {args.velocity} m/s")
    
    if args.compare:
        total = len(configs) * len(locations) * len(solar_areas)
        print(f"Comparisons: {total} (each runs single + multi-zone)")
    else:
        total = len(configs) * len(locations) * len(solar_areas)
        print(f"Total simulations: {total}")
    
    # Run simulations
    start_time = datetime.now()
    all_results = []
    count = 0
    
    for config in configs:
        for location in locations:
            for solar_area in solar_areas:
                count += 1
                print(f"\n[{count}/{total}] ", end="")
                
                try:
                    if args.compare:
                        results = run_comparison(config, location, solar_area, args)
                        all_results.extend(results)
                    else:
                        result = run_single_simulation(config, location, solar_area, args)
                        all_results.append(result)
                        
                except Exception as e:
                    print(f"ERROR: {e}")
                    import traceback
                    traceback.print_exc()
                    all_results.append({
                        "config": config,
                        "location": location,
                        "solar_area_m2": solar_area,
                        "multizone": args.multizone,
                        "success": False,
                        "message": str(e),
                    })
    
    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 80)
    print("ALL SIMULATIONS COMPLETE")
    print("=" * 80)
    print(f"Total time: {duration/60:.1f} minutes ({duration:.0f} seconds)")
    print(f"Successful: {sum(1 for r in all_results if r.get('success', False))}/{len(all_results)}")
    
    # Save summary
    summary_df = pd.DataFrame(all_results)
    
    mz_suffix = "_multizone" if args.multizone else ""
    if args.compare:
        mz_suffix = "_comparison"
    
    summary_file = PROJECT_ROOT / args.output_dir / f"run_summary{mz_suffix}.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"\nSummary saved: {summary_file}")
    
    # Print summary table
    if not summary_df.empty and "time_h" in summary_df.columns:
        print("\n" + "-" * 80)
        print("RESULTS SUMMARY")
        print("-" * 80)
        
        cols_to_show = ["config", "location", "solar_area_m2", "multizone", 
                        "time_h", "SEC_kWh_per_kg", "uniformity_pct"]
        cols_available = [c for c in cols_to_show if c in summary_df.columns]
        
        print(summary_df[cols_available].to_string(index=False))


if __name__ == "__main__":
    main()