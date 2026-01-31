"""Batch plot generator for all simulation results.

Automatically finds all CSV files in outputs/ and creates plots for each.
"""

from pathlib import Path
import sys

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from visualize_results import create_all_plots


def batch_plot_all_results(outputs_dir: Path = None, plot_dir: Path = None):
    """Create plots for all simulation CSV files.
    
    Parameters
    ----------
    outputs_dir : Path, optional
        Directory containing simulation outputs (default: PROJECT_ROOT/outputs)
    plot_dir : Path, optional
        Directory to save plots (default: PROJECT_ROOT/plots)
    """
    
    if outputs_dir is None:
        outputs_dir = PROJECT_ROOT / "outputs"
    
    if plot_dir is None:
        plot_dir = PROJECT_ROOT / "plots"
    
    # Find all CSV files
    csv_files = list(outputs_dir.glob("**/*.csv"))
    csv_files = [f for f in csv_files if f.stem != "run_summary"]  # Exclude summary
    
    if not csv_files:
        print(f"No CSV files found in {outputs_dir}")
        return
    
    print(f"\n{'='*70}")
    print(f"BATCH PLOTTING - Found {len(csv_files)} simulation files")
    print(f"{'='*70}\n")
    
    for i, csv_file in enumerate(csv_files, 1):
        print(f"[{i}/{len(csv_files)}] Processing: {csv_file.relative_to(outputs_dir)}")
        
        # Create subdirectory structure in plots folder
        rel_path = csv_file.relative_to(outputs_dir)
        output_subdir = plot_dir / rel_path.parent
        
        try:
            create_all_plots(csv_file, output_subdir)
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    print(f"\n{'='*70}")
    print(f"BATCH PLOTTING COMPLETE")
    print(f"Plots saved to: {plot_dir}")
    print(f"{'='*70}\n")


def plot_single_config(config_letter: str, location: str = None, 
                       solar_area: float = None):
    """Plot results for a specific configuration.
    
    Parameters
    ----------
    config_letter : str
        Config to plot (A, B, C, D, or E)
    location : str, optional
        Specific location (if None, plot all)
    solar_area : float, optional
        Specific solar area (if None, plot all)
    """
    
    outputs_dir = PROJECT_ROOT / "outputs" / f"config_{config_letter}"
    plot_dir = PROJECT_ROOT / "plots" / f"config_{config_letter}"
    
    if not outputs_dir.exists():
        print(f"No results found for Config {config_letter}")
        return
    
    # Build search pattern
    if location and solar_area is not None:
        pattern = f"{location}/Ac_{solar_area:.0f}m2.csv"
        csv_files = [outputs_dir / pattern] if (outputs_dir / pattern).exists() else []
    elif location:
        csv_files = list((outputs_dir / location).glob("*.csv"))
    else:
        csv_files = list(outputs_dir.glob("**/*.csv"))
    
    if not csv_files:
        print(f"No matching files found")
        return
    
    print(f"\nPlotting {len(csv_files)} file(s) for Config {config_letter}")
    
    for csv_file in csv_files:
        rel_path = csv_file.relative_to(outputs_dir)
        output_subdir = plot_dir / rel_path.parent
        
        try:
            create_all_plots(csv_file, output_subdir)
        except Exception as e:
            print(f"Error processing {csv_file.name}: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create plots for simulation results"
    )
    
    parser.add_argument(
        "--all", action="store_true",
        help="Plot all simulation results"
    )
    parser.add_argument(
        "--config", type=str, choices=["A", "B", "C", "D", "E"],
        help="Plot specific configuration"
    )
    parser.add_argument(
        "--location", type=str,
        help="Specific location (e.g., kathmandu)"
    )
    parser.add_argument(
        "--solar-area", type=float,
        help="Specific solar area [m²]"
    )
    parser.add_argument(
        "--file", type=str,
        help="Plot single CSV file"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # Plot single file
        csv_path = Path(args.file)
        if not csv_path.exists():
            print(f"File not found: {csv_path}")
            sys.exit(1)
        
        output_dir = PROJECT_ROOT / "plots" / csv_path.stem
        create_all_plots(csv_path, output_dir)
        print(f"\nPlots saved to: {output_dir}")
    
    elif args.all:
        # Plot everything
        batch_plot_all_results()
    
    elif args.config:
        # Plot specific config
        plot_single_config(args.config, args.location, args.solar_area)
    
    else:
        print("Usage examples:")
        print("  python scripts/batch_plot.py --all")
        print("  python scripts/batch_plot.py --config A")
        print("  python scripts/batch_plot.py --config B --location kathmandu")
        print("  python scripts/batch_plot.py --file outputs/config_A/kathmandu/Ac_0m2.csv")
