"""Multi-Zone Drying Chamber Visualization Module.

Creates publication-quality plots for:
- Single-inlet vs Multi-zone comparison
- Tray uniformity analysis
- Zone inlet/outlet conditions
- Drying time distribution

NEW FILE - Add this to your rq1/ or scripts/ folder as: multizone_plots.py

Usage in VSCode Terminal:
=========================

# Compare single vs multizone for one simulation
python multizone_plots.py --compare outputs/config_A/kathmandu/Ac_12m2.csv outputs/config_A_mz3/kathmandu/Ac_12m2.csv

# Plot uniformity analysis
python multizone_plots.py --uniformity outputs/config_A_mz3/kathmandu/Ac_12m2.csv

# Batch compare all configs
python multizone_plots.py --batch-compare

# Plot all multi-zone results
python multizone_plots.py --all

Author: Wasti (SAHPD Thesis)
Date: January 2026
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MaxNLocator

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_simulation_data(csv_path: Path) -> pd.DataFrame:
    """Load simulation CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"File not found: {csv_path}")
    return pd.read_csv(csv_path)


def calculate_tray_drying_times(df: pd.DataFrame, threshold: float = 0.05, 
                                 n_trays: int = 10) -> Dict[str, float]:
    """Calculate drying time for each tray.
    
    Parameters
    ----------
    df : DataFrame
        Simulation data
    threshold : float
        MR threshold for "dry" (default 0.05)
    n_trays : int
        Number of trays
    
    Returns
    -------
    dict
        Tray drying times and statistics
    """
    
    times = {}
    tray_times = []
    
    for i in range(n_trays):
        mr_col = f'MR_tray_{i}'
        if mr_col in df.columns:
            below = df[df[mr_col] < threshold]
            if not below.empty:
                t = below.iloc[0]['time_h']
                times[f'tray_{i}'] = t
                tray_times.append(t)
            else:
                times[f'tray_{i}'] = df['time_h'].iloc[-1]  # Not finished
                tray_times.append(df['time_h'].iloc[-1])
    
    if tray_times:
        times['min'] = min(tray_times)
        times['max'] = max(tray_times)
        times['mean'] = np.mean(tray_times)
        times['std'] = np.std(tray_times)
        times['range'] = times['max'] - times['min']
        times['uniformity_pct'] = 100 * (1 - times['range'] / times['max']) if times['max'] > 0 else 100
    
    return times


def plot_uniformity_comparison(df_single: pd.DataFrame, df_multi: pd.DataFrame,
                                output_path: Path = None, title: str = None) -> None:
    """Create side-by-side uniformity comparison plot.
    
    Shows tray drying times for both configurations.
    """
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    n_trays = 10
    colors = plt.cm.viridis(np.linspace(0, 1, n_trays))
    
    # =========================================================================
    # Panel 1: Single-Inlet MR curves
    # =========================================================================
    ax1 = axes[0, 0]
    for i in range(n_trays):
        mr_col = f'MR_tray_{i}'
        if mr_col in df_single.columns:
            ax1.plot(df_single['time_h'], df_single[mr_col], color=colors[i],
                    linewidth=1.5, label=f'Tray {i}')
    
    ax1.axhline(y=0.05, color='r', linestyle='--', linewidth=2, label='Target (MR=0.05)')
    ax1.set_xlabel('Time [hours]', fontsize=11)
    ax1.set_ylabel('Moisture Ratio [-]', fontsize=11)
    ax1.set_title('Single-Inlet: Tray Moisture Ratio', fontsize=12, fontweight='bold')
    ax1.legend(ncol=2, fontsize=8, loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([0, 1.05])
    
    # =========================================================================
    # Panel 2: Multi-Zone MR curves
    # =========================================================================
    ax2 = axes[0, 1]
    for i in range(n_trays):
        mr_col = f'MR_tray_{i}'
        if mr_col in df_multi.columns:
            ax2.plot(df_multi['time_h'], df_multi[mr_col], color=colors[i],
                    linewidth=1.5, label=f'Tray {i}')
    
    ax2.axhline(y=0.05, color='r', linestyle='--', linewidth=2, label='Target (MR=0.05)')
    ax2.set_xlabel('Time [hours]', fontsize=11)
    ax2.set_ylabel('Moisture Ratio [-]', fontsize=11)
    ax2.set_title('Multi-Zone: Tray Moisture Ratio', fontsize=12, fontweight='bold')
    ax2.legend(ncol=2, fontsize=8, loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 1.05])
    
    # =========================================================================
    # Panel 3: Drying Time Bar Chart
    # =========================================================================
    ax3 = axes[1, 0]
    
    times_single = calculate_tray_drying_times(df_single)
    times_multi = calculate_tray_drying_times(df_multi)
    
    x = np.arange(n_trays)
    width = 0.35
    
    single_times = [times_single.get(f'tray_{i}', 0) for i in range(n_trays)]
    multi_times = [times_multi.get(f'tray_{i}', 0) for i in range(n_trays)]
    
    bars1 = ax3.bar(x - width/2, single_times, width, label='Single-Inlet', color='steelblue', alpha=0.8)
    bars2 = ax3.bar(x + width/2, multi_times, width, label='Multi-Zone', color='darkorange', alpha=0.8)
    
    ax3.set_xlabel('Tray Number', fontsize=11)
    ax3.set_ylabel('Drying Time [hours]', fontsize=11)
    ax3.set_title('Drying Time per Tray', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels([f'{i}' for i in range(n_trays)])
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Add range indicators
    ax3.axhline(y=times_single['min'], color='steelblue', linestyle=':', alpha=0.5)
    ax3.axhline(y=times_single['max'], color='steelblue', linestyle=':', alpha=0.5)
    ax3.axhline(y=times_multi['min'], color='darkorange', linestyle=':', alpha=0.5)
    ax3.axhline(y=times_multi['max'], color='darkorange', linestyle=':', alpha=0.5)
    
    # =========================================================================
    # Panel 4: Summary Statistics
    # =========================================================================
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    # Calculate improvement
    range_improvement = (times_single['range'] - times_multi['range']) / times_single['range'] * 100
    time_improvement = (times_single['max'] - times_multi['max']) / times_single['max'] * 100
    uniformity_diff = times_multi['uniformity_pct'] - times_single['uniformity_pct']
    
    summary_text = f"""
UNIFORMITY COMPARISON
{'='*40}

                    Single-Inlet    Multi-Zone    Improvement
                    ────────────    ──────────    ───────────
Min drying time:    {times_single['min']:>8.1f} h     {times_multi['min']:>8.1f} h
Max drying time:    {times_single['max']:>8.1f} h     {times_multi['max']:>8.1f} h     {time_improvement:>+6.1f}%
Mean drying time:   {times_single['mean']:>8.1f} h     {times_multi['mean']:>8.1f} h
Std deviation:      {times_single['std']:>8.2f} h     {times_multi['std']:>8.2f} h

Time range:         {times_single['range']:>8.1f} h     {times_multi['range']:>8.1f} h     {range_improvement:>+6.1f}%
Uniformity:         {times_single['uniformity_pct']:>7.1f}%      {times_multi['uniformity_pct']:>7.1f}%     {uniformity_diff:>+6.1f}%

{'='*40}
MULTI-ZONE BENEFIT: {range_improvement:.0f}% better uniformity
"""
    
    ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Overall title
    if title:
        fig.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    else:
        fig.suptitle('Single-Inlet vs Multi-Zone Uniformity Comparison', 
                     fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_tray_conditions(df: pd.DataFrame, output_path: Path = None,
                         title: str = None) -> None:
    """Plot air conditions at each tray outlet.
    
    Shows how temperature and RH change through the chamber.
    """
    
    n_trays = 10
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    colors = plt.cm.viridis(np.linspace(0, 1, n_trays))
    
    # =========================================================================
    # Panel 1: Temperature at each tray outlet
    # =========================================================================
    ax1 = axes[0, 0]
    
    ax1.plot(df['time_h'], df['T_to_chamber_C'], 'r-', linewidth=2, label='Inlet')
    
    for i in range(n_trays):
        col = f'T_tray_{i}_out_C'
        if col in df.columns:
            ax1.plot(df['time_h'], df[col], color=colors[i], linewidth=1, 
                    alpha=0.7, label=f'Tray {i}')
    
    ax1.set_xlabel('Time [hours]', fontsize=11)
    ax1.set_ylabel('Temperature [°C]', fontsize=11)
    ax1.set_title('Air Temperature Profile Through Trays', fontsize=12, fontweight='bold')
    ax1.legend(ncol=3, fontsize=8, loc='best')
    ax1.grid(True, alpha=0.3)
    
    # =========================================================================
    # Panel 2: RH at each tray outlet
    # =========================================================================
    ax2 = axes[0, 1]
    
    if 'RH_to_chamber_frac' in df.columns:
        ax2.plot(df['time_h'], df['RH_to_chamber_frac']*100, 'r-', linewidth=2, label='Inlet')
    
    for i in range(n_trays):
        col = f'RH_tray_{i}_out_frac'
        if col in df.columns:
            ax2.plot(df['time_h'], df[col]*100, color=colors[i], linewidth=1,
                    alpha=0.7, label=f'Tray {i}')
    
    ax2.axhline(y=100, color='k', linestyle=':', alpha=0.5)
    ax2.set_xlabel('Time [hours]', fontsize=11)
    ax2.set_ylabel('Relative Humidity [%]', fontsize=11)
    ax2.set_title('Air RH Profile Through Trays', fontsize=12, fontweight='bold')
    ax2.legend(ncol=3, fontsize=8, loc='best')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 105])
    
    # =========================================================================
    # Panel 3: Temperature drop through chamber (snapshot at different times)
    # =========================================================================
    ax3 = axes[1, 0]
    
    time_points = [1, 4, 8, 12]  # hours to snapshot
    line_styles = ['-', '--', '-.', ':']
    
    for t, ls in zip(time_points, line_styles):
        # Find closest row to this time
        idx = (df['time_h'] - t).abs().idxmin()
        row = df.iloc[idx]
        
        temps = [row['T_to_chamber_C']]
        for i in range(n_trays):
            col = f'T_tray_{i}_out_C'
            if col in df.columns:
                temps.append(row[col])
        
        x = list(range(len(temps)))
        ax3.plot(x, temps, ls, linewidth=2, marker='o', markersize=4,
                label=f't = {row["time_h"]:.1f}h')
    
    ax3.set_xlabel('Position (Inlet → Tray 0 → ... → Tray 9)', fontsize=11)
    ax3.set_ylabel('Temperature [°C]', fontsize=11)
    ax3.set_title('Temperature Drop at Different Times', fontsize=12, fontweight='bold')
    ax3.set_xticks(range(n_trays + 1))
    ax3.set_xticklabels(['In'] + [f'{i}' for i in range(n_trays)])
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # =========================================================================
    # Panel 4: RH rise through chamber (snapshot at different times)
    # =========================================================================
    ax4 = axes[1, 1]
    
    for t, ls in zip(time_points, line_styles):
        idx = (df['time_h'] - t).abs().idxmin()
        row = df.iloc[idx]
        
        rhs = [row.get('RH_to_chamber_frac', 0.1) * 100]
        for i in range(n_trays):
            col = f'RH_tray_{i}_out_frac'
            if col in df.columns:
                rhs.append(row[col] * 100)
        
        x = list(range(len(rhs)))
        ax4.plot(x, rhs, ls, linewidth=2, marker='o', markersize=4,
                label=f't = {row["time_h"]:.1f}h')
    
    ax4.axhline(y=100, color='k', linestyle=':', alpha=0.5, label='Saturation')
    ax4.set_xlabel('Position (Inlet → Tray 0 → ... → Tray 9)', fontsize=11)
    ax4.set_ylabel('Relative Humidity [%]', fontsize=11)
    ax4.set_title('RH Rise at Different Times', fontsize=12, fontweight='bold')
    ax4.set_xticks(range(n_trays + 1))
    ax4.set_xticklabels(['In'] + [f'{i}' for i in range(n_trays)])
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim([0, 105])
    
    if title:
        fig.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_drying_time_distribution(results: List[Dict], output_path: Path = None) -> None:
    """Create box plot comparing drying time distributions.
    
    Parameters
    ----------
    results : list of dict
        Each dict should have 'name', 'times' (list of tray times)
    """
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # =========================================================================
    # Panel 1: Box plot
    # =========================================================================
    data = []
    labels = []
    
    for r in results:
        data.append(r['times'])
        labels.append(r['name'])
    
    bp = ax1.boxplot(data, labels=labels, patch_artist=True)
    
    colors = ['steelblue', 'darkorange', 'green', 'red', 'purple']
    for patch, color in zip(bp['boxes'], colors[:len(data)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    ax1.set_ylabel('Drying Time [hours]', fontsize=11)
    ax1.set_title('Drying Time Distribution by Tray', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # =========================================================================
    # Panel 2: Statistics comparison
    # =========================================================================
    metrics = ['Mean', 'Std Dev', 'Range', 'Min', 'Max']
    x = np.arange(len(metrics))
    width = 0.8 / len(results)
    
    for i, r in enumerate(results):
        times = r['times']
        values = [
            np.mean(times),
            np.std(times),
            max(times) - min(times),
            min(times),
            max(times),
        ]
        offset = (i - len(results)/2 + 0.5) * width
        ax2.bar(x + offset, values, width, label=r['name'], alpha=0.8)
    
    ax2.set_xlabel('Metric', fontsize=11)
    ax2.set_ylabel('Time [hours]', fontsize=11)
    ax2.set_title('Uniformity Metrics Comparison', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(metrics)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_comprehensive_comparison(single_csv: Path, multi_csv: Path,
                                   output_dir: Path = None) -> None:
    """Create comprehensive comparison between single-inlet and multi-zone.
    
    Generates multiple plots:
    1. Uniformity comparison
    2. Energy comparison
    3. Tray conditions
    4. Summary metrics
    """
    
    print(f"\n{'='*70}")
    print("MULTI-ZONE COMPARISON PLOTS")
    print(f"{'='*70}")
    print(f"Single-inlet: {single_csv}")
    print(f"Multi-zone:   {multi_csv}")
    
    df_single = load_simulation_data(single_csv)
    df_multi = load_simulation_data(multi_csv)
    
    if output_dir is None:
        output_dir = single_csv.parent / "comparison_plots"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Plot 1: Uniformity comparison
    print("\n1. Creating uniformity comparison plot...")
    plot_uniformity_comparison(
        df_single, df_multi,
        output_dir / "01_uniformity_comparison.png",
        title=f"Uniformity: {single_csv.stem}"
    )
    
    # Plot 2: Single-inlet tray conditions
    print("2. Creating single-inlet tray conditions plot...")
    plot_tray_conditions(
        df_single,
        output_dir / "02_single_inlet_conditions.png",
        title="Single-Inlet Air Conditions"
    )
    
    # Plot 3: Multi-zone tray conditions
    print("3. Creating multi-zone tray conditions plot...")
    plot_tray_conditions(
        df_multi,
        output_dir / "03_multizone_conditions.png",
        title="Multi-Zone Air Conditions"
    )
    
    # Plot 4: Drying time distribution
    print("4. Creating drying time distribution plot...")
    times_single = calculate_tray_drying_times(df_single)
    times_multi = calculate_tray_drying_times(df_multi)
    
    results = [
        {'name': 'Single-Inlet', 'times': [times_single.get(f'tray_{i}', 0) for i in range(10)]},
        {'name': 'Multi-Zone', 'times': [times_multi.get(f'tray_{i}', 0) for i in range(10)]},
    ]
    plot_drying_time_distribution(results, output_dir / "04_drying_time_distribution.png")
    
    # Create summary CSV
    print("5. Creating summary metrics CSV...")
    summary = {
        'Metric': ['Min time (h)', 'Max time (h)', 'Mean time (h)', 'Std dev (h)',
                   'Range (h)', 'Uniformity (%)', 'SEC (kWh/kg)', 'Total time (h)'],
        'Single-Inlet': [
            times_single['min'], times_single['max'], times_single['mean'],
            times_single['std'], times_single['range'], times_single['uniformity_pct'],
            df_single['SEC_elec_kWh_per_kg'].dropna().iloc[-1] if 'SEC_elec_kWh_per_kg' in df_single.columns else 0,
            df_single['time_h'].iloc[-1],
        ],
        'Multi-Zone': [
            times_multi['min'], times_multi['max'], times_multi['mean'],
            times_multi['std'], times_multi['range'], times_multi['uniformity_pct'],
            df_multi['SEC_elec_kWh_per_kg'].dropna().iloc[-1] if 'SEC_elec_kWh_per_kg' in df_multi.columns else 0,
            df_multi['time_h'].iloc[-1],
        ],
    }
    
    summary_df = pd.DataFrame(summary)
    summary_df['Improvement (%)'] = (
        (summary_df['Single-Inlet'] - summary_df['Multi-Zone']) / 
        summary_df['Single-Inlet'].replace(0, np.nan) * 100
    ).round(1)
    
    summary_csv = output_dir / "comparison_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"   Saved: {summary_csv}")
    
    print(f"\n{'='*70}")
    print(f"All plots saved to: {output_dir}")
    print(f"{'='*70}\n")
    
    # Print summary
    print("\nSUMMARY:")
    print(summary_df.to_string(index=False))


def batch_compare_all(outputs_dir: Path = None, plot_dir: Path = None) -> None:
    """Find and compare all single vs multi-zone pairs.
    
    Looks for matching files in config_X/ and config_X_mz3/ directories.
    """
    
    if outputs_dir is None:
        outputs_dir = PROJECT_ROOT / "outputs"
    if plot_dir is None:
        plot_dir = PROJECT_ROOT / "plots" / "multizone_comparison"
    
    print(f"\n{'='*70}")
    print("BATCH MULTI-ZONE COMPARISON")
    print(f"{'='*70}")
    print(f"Scanning: {outputs_dir}")
    
    # Find all single-inlet configs
    single_dirs = list(outputs_dir.glob("config_[A-E]"))
    
    comparisons = []
    
    for single_dir in single_dirs:
        config_letter = single_dir.name.split('_')[1]
        
        # Find corresponding multi-zone directory
        mz_dir = outputs_dir / f"config_{config_letter}_mz3"
        
        if not mz_dir.exists():
            continue
        
        # Find matching CSV files
        for single_csv in single_dir.glob("**/*.csv"):
            if single_csv.name == "run_summary.csv":
                continue
            
            rel_path = single_csv.relative_to(single_dir)
            mz_csv = mz_dir / rel_path
            
            if mz_csv.exists():
                comparisons.append((single_csv, mz_csv))
    
    if not comparisons:
        print("No matching single/multi-zone pairs found.")
        print("Make sure you have both config_X/ and config_X_mz3/ directories.")
        return
    
    print(f"Found {len(comparisons)} comparison pairs.\n")
    
    for i, (single_csv, mz_csv) in enumerate(comparisons, 1):
        print(f"\n[{i}/{len(comparisons)}] Comparing: {single_csv.stem}")
        
        try:
            output_subdir = plot_dir / single_csv.parent.name / single_csv.stem
            plot_comprehensive_comparison(single_csv, mz_csv, output_subdir)
        except Exception as e:
            print(f"  ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Zone Drying Chamber Visualization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
---------
  # Compare single vs multi-zone
  python multizone_plots.py --compare single.csv multi.csv

  # Plot tray conditions for one simulation
  python multizone_plots.py --conditions simulation.csv

  # Batch compare all available pairs
  python multizone_plots.py --batch-compare

  # Create uniformity plot only
  python multizone_plots.py --uniformity multi.csv
        """
    )
    
    parser.add_argument('--compare', nargs=2, metavar=('SINGLE', 'MULTI'),
                       help='Compare single-inlet vs multi-zone CSV files')
    parser.add_argument('--conditions', type=str, metavar='CSV',
                       help='Plot tray conditions for single CSV')
    parser.add_argument('--uniformity', type=str, metavar='CSV',
                       help='Plot uniformity analysis for single CSV')
    parser.add_argument('--batch-compare', action='store_true',
                       help='Batch compare all single/multi-zone pairs')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='Output directory for plots')
    
    args = parser.parse_args()
    
    if args.compare:
        single_csv = Path(args.compare[0])
        multi_csv = Path(args.compare[1])
        output_dir = Path(args.output_dir) if args.output_dir else None
        plot_comprehensive_comparison(single_csv, multi_csv, output_dir)
    
    elif args.conditions:
        csv_path = Path(args.conditions)
        output_path = Path(args.output_dir) / f"{csv_path.stem}_conditions.png" if args.output_dir else None
        df = load_simulation_data(csv_path)
        plot_tray_conditions(df, output_path, title=csv_path.stem)
    
    elif args.uniformity:
        csv_path = Path(args.uniformity)
        df = load_simulation_data(csv_path)
        times = calculate_tray_drying_times(df)
        
        print(f"\nUniformity Analysis: {csv_path.name}")
        print("=" * 50)
        print(f"Min drying time:  {times['min']:.1f} h")
        print(f"Max drying time:  {times['max']:.1f} h")
        print(f"Mean drying time: {times['mean']:.1f} h")
        print(f"Std deviation:    {times['std']:.2f} h")
        print(f"Range:            {times['range']:.1f} h")
        print(f"Uniformity:       {times['uniformity_pct']:.1f}%")
    
    elif args.batch_compare:
        output_dir = Path(args.output_dir) if args.output_dir else None
        batch_compare_all(plot_dir=output_dir)
    
    else:
        parser.print_help()
        print("\n" + "="*50)
        print("Quick start:")
        print("  python multizone_plots.py --batch-compare")
        print("="*50)


if __name__ == "__main__":
    main()
