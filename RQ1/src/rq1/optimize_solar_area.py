"""
Solar Collector Area Optimization Script
=========================================

STEP 1 of Multi-Zone Implementation Plan

This script runs single-inlet simulations across multiple solar collector
areas to find the optimal size for each location.

Optimization Criteria:
1. SEC (Specific Energy Consumption) - lower is better
2. Drying time - shorter is better  
3. Solar fraction - higher is better
4. Diminishing returns - find the "knee" in the curve

Run this BEFORE implementing multi-zone to establish baseline
optimal collector areas for each location.

Usage:
------
python optimize_solar_area.py --location kathmandu
python optimize_solar_area.py --all-locations
python optimize_solar_area.py --quick  # Fewer area points for testing

Author: Wasti (SAHPD Thesis)
Date: January 2026
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
import time

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add project to path (src/rq1/ -> parents[2] = RQ1/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Import simulation functions
from rq1.config_solar_hp import (
    make_config_A_HP_only as make_config_A,
    make_config_B1_solar_before_cond as make_config_B,
    make_config_E_solar_evap_cond_cascade as make_config_E,
)
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation as run_solar_hp_dryer


def _get_weather_path(location: str) -> Path:
    """Resolve weather CSV path for a location."""
    candidates = [
        PROJECT_ROOT / "data" / "ambient" / f"{location}_pvgis_standard.csv",
        PROJECT_ROOT / "data" / "ambient" / f"{location}.csv",
        PROJECT_ROOT / "outputs" / f"{location}_pvgis_standard.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f"Weather file for '{location}' not found. Tried: {candidates}")


@dataclass
class OptimizationResult:
    """Results from one simulation run."""
    location: str
    config_type: str
    solar_area_m2: float
    drying_time_h: float
    W_comp_total_kWh: float
    Q_solar_total_kWh: float
    SEC_elec_kWh_per_kg: float
    solar_fraction: float
    converged: bool
    final_X_avg: float


def run_single_simulation(
    config_type: str,
    location: str, 
    solar_area: float,
    verbose: bool = False
) -> OptimizationResult:
    """Run one simulation and extract key metrics."""
    
    weather_csv = _get_weather_path(location)

    # Create configuration
    if config_type == "A":
        cfg = make_config_A(ambient_csv=weather_csv, display_geometry=verbose)
    elif config_type == "B":
        cfg = make_config_B(ambient_csv=weather_csv, solar_area_m2=solar_area, display_geometry=verbose)
    elif config_type == "E":
        cfg = make_config_E(ambient_csv=weather_csv, solar_area_m2=solar_area, display_geometry=verbose)
    else:
        raise ValueError(f"Unknown config type: {config_type}")

    # Run simulation
    result = run_solar_hp_dryer(cfg)
    
    # Extract metrics
    df = result.df
    
    # =========================================================================
    # FIND ACTUAL DRYING TIME (when ALL trays reach MR < 0.05)
    # =========================================================================
    # This is the CORRECT way - find when the slowest tray (tray 9) finishes
    tray_finish_times = []
    for t in range(10):
        mr_col = f'MR_tray_{t}'
        if mr_col in df.columns:
            below_threshold = df[df[mr_col] < 0.05]
            if not below_threshold.empty:
                finish_time = below_threshold.iloc[0]['time_h']
            else:
                # Tray didn't finish - use simulation end time
                finish_time = df['time_h'].iloc[-1]
            tray_finish_times.append(finish_time)
    
    # Actual drying time = when LAST (slowest) tray finishes
    if tray_finish_times:
        drying_time_h = max(tray_finish_times)
    else:
        drying_time_h = df['time_h'].iloc[-1]
    
    # =========================================================================
    # GET METRICS AT DRYING COMPLETION (not simulation end)
    # =========================================================================
    # Find the row closest to drying completion time
    completion_idx = (df['time_h'] - drying_time_h).abs().idxmin()
    completion_row = df.loc[completion_idx]
    
    W_comp_total = completion_row.get('W_comp_cum_kWh', 0)
    Q_solar_total = completion_row.get('Q_solar_cum_kWh', 0)
    m_w_removed = completion_row.get('m_w_cum_kg', 0)
    
    # SEC (electrical only) - at completion time
    SEC = W_comp_total / m_w_removed if m_w_removed > 0 else float('inf')
    
    # Solar fraction
    Q_total = W_comp_total + Q_solar_total
    solar_frac = Q_solar_total / Q_total if Q_total > 0 else 0
    
    # Final moisture
    final_X = completion_row.get('X_db_avg', 0)
    
    return OptimizationResult(
        location=location,
        config_type=config_type,
        solar_area_m2=solar_area,
        drying_time_h=drying_time_h,
        W_comp_total_kWh=W_comp_total,
        Q_solar_total_kWh=Q_solar_total,
        SEC_elec_kWh_per_kg=SEC,
        solar_fraction=solar_frac,
        converged=result.converged,
        final_X_avg=final_X,
    )


def run_optimization_sweep(
    location: str,
    config_type: str = "E",  # Use Config E (cascade) as best solar integration
    solar_areas: List[float] = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """Run optimization sweep for one location."""
    
    if solar_areas is None:
        # Default sweep: 0 to 50 m² in steps
        solar_areas = [0, 5, 8, 10, 12, 14, 16, 18, 20, 25, 28, 30, 34, 36, 40, 44, 48, 50]
    
    print(f"\n{'='*60}")
    print(f"SOLAR AREA OPTIMIZATION: {location.upper()}")
    print(f"Config: {config_type}, Areas: {solar_areas}")
    print(f"{'='*60}\n")
    
    results = []
    
    for i, area in enumerate(solar_areas):
        print(f"[{i+1}/{len(solar_areas)}] Running Ac = {area} m²...", end=" ")
        start = time.time()
        
        try:
            # For Ac=0, use Config A (HP-only)
            if area == 0:
                result = run_single_simulation("A", location, 0, verbose)
            else:
                result = run_single_simulation(config_type, location, area, verbose)
            
            results.append(result)
            elapsed = time.time() - start
            
            status = "✓" if result.converged else "✗"
            print(f"{status} Time: {result.drying_time_h:.1f}h, "
                  f"SEC: {result.SEC_elec_kWh_per_kg:.3f} kWh/kg, "
                  f"Solar: {result.solar_fraction*100:.1f}% "
                  f"({elapsed:.1f}s)")
            
        except Exception as e:
            print(f"✗ ERROR: {e}")
            continue
    
    # Convert to DataFrame
    df = pd.DataFrame([vars(r) for r in results])
    
    return df


def find_optimal_area(df: pd.DataFrame, method: str = "knee") -> Tuple[float, Dict]:
    """Find optimal solar area from sweep results.
    
    Methods:
    - "knee": Find knee point where diminishing returns start
    - "min_sec": Minimum SEC
    - "min_time": Minimum drying time
    """
    
    if df.empty:
        return 0, {}
    
    # Sort by area
    df = df.sort_values('solar_area_m2')
    
    if method == "min_sec":
        # Simply minimum SEC
        idx = df['SEC_elec_kWh_per_kg'].idxmin()
        optimal_area = df.loc[idx, 'solar_area_m2']
        
    elif method == "min_time":
        # Minimum drying time
        idx = df['drying_time_h'].idxmin()
        optimal_area = df.loc[idx, 'solar_area_m2']
        
    elif method == "knee":
        # Find knee point using second derivative
        # Where additional area gives diminishing returns
        
        areas = df['solar_area_m2'].values
        secs = df['SEC_elec_kWh_per_kg'].values
        
        if len(areas) < 3:
            # Not enough points, use min SEC
            idx = df['SEC_elec_kWh_per_kg'].idxmin()
            optimal_area = df.loc[idx, 'solar_area_m2']
        else:
            # Calculate improvement per m² added
            improvements = []
            for i in range(1, len(areas)):
                dA = areas[i] - areas[i-1]
                dSEC = secs[i-1] - secs[i]  # Positive if SEC improved
                improvement_per_m2 = dSEC / dA if dA > 0 else 0
                improvements.append(improvement_per_m2)
            
            # Find where improvement drops below threshold
            # Threshold: 10% of initial improvement rate
            if improvements and improvements[0] > 0:
                threshold = 0.1 * improvements[0]
                
                optimal_idx = 0
                for i, imp in enumerate(improvements):
                    if imp > threshold:
                        optimal_idx = i + 1  # +1 because improvements[i] is for areas[i+1]
                    else:
                        break
                
                optimal_area = areas[min(optimal_idx, len(areas)-1)]
            else:
                # No improvement from solar, use baseline
                optimal_area = 0
    
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Get metrics at optimal point
    optimal_row = df[df['solar_area_m2'] == optimal_area].iloc[0]
    
    metrics = {
        'optimal_area_m2': optimal_area,
        'SEC_kWh_per_kg': optimal_row['SEC_elec_kWh_per_kg'],
        'drying_time_h': optimal_row['drying_time_h'],
        'solar_fraction': optimal_row['solar_fraction'],
        'W_comp_kWh': optimal_row['W_comp_total_kWh'],
    }
    
    return optimal_area, metrics


def plot_optimization_results(
    df: pd.DataFrame,
    location: str,
    optimal_area: float = None,
    output_path: Path = None,
):
    """Create visualization of optimization results."""
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    areas = df['solar_area_m2']
    
    # Panel 1: SEC vs Solar Area
    ax1 = axes[0, 0]
    ax1.plot(areas, df['SEC_elec_kWh_per_kg'], 'b-o', linewidth=2, markersize=8)
    ax1.set_xlabel('Solar Collector Area [m²]', fontsize=11)
    ax1.set_ylabel('SEC [kWh/kg water]', fontsize=11)
    ax1.set_title('Specific Energy Consumption', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    if optimal_area is not None:
        ax1.axvline(x=optimal_area, color='r', linestyle='--', label=f'Optimal: {optimal_area} m²')
        ax1.legend()
    
    # Panel 2: Drying Time vs Solar Area
    ax2 = axes[0, 1]
    ax2.plot(areas, df['drying_time_h'], 'g-o', linewidth=2, markersize=8)
    ax2.set_xlabel('Solar Collector Area [m²]', fontsize=11)
    ax2.set_ylabel('Drying Time [hours]', fontsize=11)
    ax2.set_title('Drying Time', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    if optimal_area is not None:
        ax2.axvline(x=optimal_area, color='r', linestyle='--')
    
    # Panel 3: Solar Fraction vs Solar Area
    ax3 = axes[1, 0]
    ax3.plot(areas, df['solar_fraction'] * 100, 'm-o', linewidth=2, markersize=8)
    ax3.set_xlabel('Solar Collector Area [m²]', fontsize=11)
    ax3.set_ylabel('Solar Fraction [%]', fontsize=11)
    ax3.set_title('Solar Energy Contribution', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim([0, 100])
    
    if optimal_area is not None:
        ax3.axvline(x=optimal_area, color='r', linestyle='--')
    
    # Panel 4: Energy Breakdown
    ax4 = axes[1, 1]
    ax4.stackplot(areas, 
                  df['W_comp_total_kWh'], 
                  df['Q_solar_total_kWh'],
                  labels=['Compressor (electric)', 'Solar (thermal)'],
                  colors=['steelblue', 'orange'],
                  alpha=0.7)
    ax4.set_xlabel('Solar Collector Area [m²]', fontsize=11)
    ax4.set_ylabel('Energy [kWh]', fontsize=11)
    ax4.set_title('Energy Sources', fontsize=12, fontweight='bold')
    ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)
    
    if optimal_area is not None:
        ax4.axvline(x=optimal_area, color='r', linestyle='--')
    
    fig.suptitle(f'Solar Area Optimization - {location.title()}', 
                 fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def run_all_locations(
    locations: List[str] = None,
    config_type: str = "E",
    solar_areas: List[float] = None,
    output_dir: Path = None,
) -> pd.DataFrame:
    """Run optimization for all locations and create summary."""
    
    if locations is None:
        locations = ["kathmandu", "dhulikhel", "biratnagar", "taplejung"]
    
    if output_dir is None:
        output_dir = PROJECT_ROOT / "outputs" / "solar_optimization"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = []
    summary = []
    
    for location in locations:
        # Run sweep
        df = run_optimization_sweep(location, config_type, solar_areas)
        
        if df.empty:
            print(f"WARNING: No results for {location}")
            continue
        
        # Save raw results
        csv_path = output_dir / f"{location}_sweep.csv"
        df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")
        
        # Find optimal
        optimal_area, metrics = find_optimal_area(df, method="knee")
        
        # Create plot
        plot_path = output_dir / f"{location}_optimization.png"
        plot_optimization_results(df, location, optimal_area, plot_path)
        
        # Store summary
        summary.append({
            'location': location,
            'optimal_Ac_m2': optimal_area,
            **metrics
        })
        
        all_results.append(df)
    
    # Create summary table
    summary_df = pd.DataFrame(summary)
    summary_path = output_dir / "optimization_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSaved summary: {summary_path}")
    
    # Print summary
    print("\n" + "="*70)
    print("OPTIMIZATION SUMMARY")
    print("="*70)
    print(summary_df.to_string(index=False))
    print("="*70)
    
    return summary_df


def main():
    parser = argparse.ArgumentParser(
        description="Optimize solar collector area for SAHPD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
---------
  # Optimize for one location
  python optimize_solar_area.py --location kathmandu

  # Optimize all locations
  python optimize_solar_area.py --all-locations

  # Quick test (fewer points)
  python optimize_solar_area.py --location kathmandu --quick

  # Custom area range
  python optimize_solar_area.py --location kathmandu --areas 5 10 15 20

  # Use Config B instead of E
  python optimize_solar_area.py --all-locations --config B
        """
    )
    
    parser.add_argument('--location', type=str,
                       help='Single location to optimize')
    parser.add_argument('--all-locations', action='store_true',
                       help='Optimize all 4 Nepal locations')
    parser.add_argument('--config', type=str, default='E',
                       choices=['B', 'E'],
                       help='Solar config to use (default: E)')
    parser.add_argument('--areas', type=float, nargs='+',
                       help='Custom solar areas to test')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test with fewer area points')
    parser.add_argument('--output-dir', type=str,
                       help='Output directory for results')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose simulation output')
    
    args = parser.parse_args()
    
    # Determine solar areas to test
    if args.areas:
        solar_areas = args.areas
    elif args.quick:
        solar_areas = [0, 10, 20, 30, 40, 50]
    else:
        solar_areas = [0, 5, 8, 10, 12, 14, 16, 18, 20, 25, 28, 30, 34, 36, 40, 44, 48, 50]
    
    # Output directory
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    if args.all_locations:
        # Run all locations
        run_all_locations(
            config_type=args.config,
            solar_areas=solar_areas,
            output_dir=output_dir,
        )
    
    elif args.location:
        # Single location
        if output_dir is None:
            output_dir = PROJECT_ROOT / "outputs" / "solar_optimization"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        df = run_optimization_sweep(
            args.location,
            args.config,
            solar_areas,
            args.verbose,
        )
        
        if not df.empty:
            # Save results
            csv_path = output_dir / f"{args.location}_sweep.csv"
            df.to_csv(csv_path, index=False)
            
            # Find optimal
            optimal_area, metrics = find_optimal_area(df, method="knee")
            
            print(f"\n{'='*50}")
            print(f"OPTIMAL FOR {args.location.upper()}: {optimal_area} m²")
            print(f"{'='*50}")
            for k, v in metrics.items():
                if isinstance(v, float):
                    print(f"  {k}: {v:.3f}")
                else:
                    print(f"  {k}: {v}")
            
            # Plot
            plot_path = output_dir / f"{args.location}_optimization.png"
            plot_optimization_results(df, args.location, optimal_area, plot_path)
    
    else:
        parser.print_help()
        print("\n" + "="*50)
        print("Quick start:")
        print("  python optimize_solar_area.py --location kathmandu --quick")
        print("  python optimize_solar_area.py --all-locations")
        print("="*50)


if __name__ == "__main__":
    main()