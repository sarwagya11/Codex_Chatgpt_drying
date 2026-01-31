"""Visualization tools for solar-HP dryer simulation results.

Creates publication-quality plots for:
- Time-series analysis
- Energy flows
- Moisture profiles
- Heat pump performance
- Solar collector performance
- Per-tray evolution
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from matplotlib.gridspec import GridSpec


def plot_overview(csv_path: Path, output_dir: Path = None) -> None:
    """Create comprehensive 6-panel overview plot.
    
    Panels:
    1. Moisture content (average + trays)
    2. Temperatures (ambient, chamber inlet, exhaust)
    3. Heat pump COP
    4. Energy flows (compressor, solar)
    5. Relative humidity
    6. Cumulative water removed
    
    Parameters
    ----------
    csv_path : Path
        Path to simulation CSV file
    output_dir : Path, optional
        Directory to save plot (if None, display only)
    """
    
    df = pd.read_csv(csv_path)
    
    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.3)
    
    # Panel 1: Moisture Content
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(df['time_h'], df['X_db_avg'], 'b-', linewidth=2, label='Average')
    
    # Add first and last tray
    if 'X_tray_0' in df.columns:
        ax1.plot(df['time_h'], df['X_tray_0'], 'r--', alpha=0.5, label='Tray 0 (first)')
    if 'X_tray_9' in df.columns:
        ax1.plot(df['time_h'], df['X_tray_9'], 'g--', alpha=0.5, label='Tray 9 (last)')
    
    ax1.axhline(y=0.1, color='k', linestyle=':', label='Target (0.1)')
    ax1.set_xlabel('Time [hours]', fontsize=11)
    ax1.set_ylabel('Moisture Content [kg/kg db]', fontsize=11)
    ax1.set_title('Moisture Content Evolution', fontsize=12, fontweight='bold')
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Temperatures
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(df['time_h'], df['T_amb_C'], 'gray', alpha=0.5, label='Ambient')
    ax2.plot(df['time_h'], df['T_to_chamber_C'], 'r-', linewidth=2, label='Chamber Inlet')
    ax2.plot(df['time_h'], df['T_exhaust_C'], 'b-', linewidth=1.5, label='Exhaust')
    
    if 'T_solar_out_C' in df.columns and df['T_solar_out_C'].max() > df['T_amb_C'].max():
        ax2.plot(df['time_h'], df['T_solar_out_C'], 'orange', linewidth=1, label='Solar Out')
    
    ax2.set_xlabel('Time [hours]', fontsize=11)
    ax2.set_ylabel('Temperature [°C]', fontsize=11)
    ax2.set_title('Air Temperature Profile', fontsize=12, fontweight='bold')
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # Panel 3: Heat Pump COP
    ax3 = fig.add_subplot(gs[1, 0])
    if 'COP' in df.columns:
        # Filter out zero/invalid COP values
        valid_cop = df[df['COP'] > 0]['COP']
        valid_time = df[df['COP'] > 0]['time_h']
        
        if len(valid_cop) > 0:
            ax3.plot(valid_time, valid_cop, 'g-', linewidth=2)
            avg_cop = valid_cop.mean()
            ax3.axhline(y=avg_cop, color='k', linestyle='--', 
                       label=f'Average: {avg_cop:.2f}')
            ax3.set_ylim([0, max(6, valid_cop.max() * 1.1)])
        
    ax3.set_xlabel('Time [hours]', fontsize=11)
    ax3.set_ylabel('COP [-]', fontsize=11)
    ax3.set_title('Heat Pump Coefficient of Performance', fontsize=12, fontweight='bold')
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # Panel 4: Power/Energy Flows
    ax4 = fig.add_subplot(gs[1, 1])
    ax4_twin = ax4.twinx()
    
    # Power (left axis)
    if 'W_comp_kW' in df.columns:
        ax4.plot(df['time_h'], df['W_comp_kW'], 'r-', linewidth=1.5, label='Compressor Power')
    if 'Q_solar_kW' in df.columns and df['Q_solar_kW'].max() > 0:
        ax4.plot(df['time_h'], df['Q_solar_kW'], 'orange', linewidth=1.5, label='Solar Heat')
    
    ax4.set_xlabel('Time [hours]', fontsize=11)
    ax4.set_ylabel('Power [kW]', fontsize=11, color='r')
    ax4.tick_params(axis='y', labelcolor='r')
    ax4.legend(loc='upper left', fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    # Cumulative energy (right axis)
    if 'W_comp_cum_kWh' in df.columns:
        ax4_twin.plot(df['time_h'], df['W_comp_cum_kWh'], 'b--', linewidth=1, label='Cumulative Energy')
    ax4_twin.set_ylabel('Cumulative Energy [kWh]', fontsize=11, color='b')
    ax4_twin.tick_params(axis='y', labelcolor='b')
    ax4_twin.legend(loc='upper right', fontsize=9)
    
    ax4.set_title('Energy Flows', fontsize=12, fontweight='bold')
    
    # Panel 5: Relative Humidity
    ax5 = fig.add_subplot(gs[2, 0])
    ax5.plot(df['time_h'], df['RH_amb_pct'], 'gray', alpha=0.5, label='Ambient')
    
    if 'RH_to_chamber_frac' in df.columns:
        ax5.plot(df['time_h'], df['RH_to_chamber_frac'] * 100, 'r-', linewidth=1.5, label='Chamber Inlet')
    if 'RH_exhaust_frac' in df.columns:
        ax5.plot(df['time_h'], df['RH_exhaust_frac'] * 100, 'b-', linewidth=1.5, label='Exhaust')
    
    ax5.axhline(y=100, color='k', linestyle=':', alpha=0.5)
    ax5.set_xlabel('Time [hours]', fontsize=11)
    ax5.set_ylabel('Relative Humidity [%]', fontsize=11)
    ax5.set_title('Relative Humidity Profile', fontsize=12, fontweight='bold')
    ax5.legend(loc='best', fontsize=9)
    ax5.grid(True, alpha=0.3)
    ax5.set_ylim([0, 105])
    
    # Panel 6: Cumulative Water Removed
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.plot(df['time_h'], df['m_w_cum_kg'], 'b-', linewidth=2)
    
    # Add target line
    if 'X_db_avg' in df.columns:
        X0 = df['X_db_avg'].iloc[0]
        X_final = 0.1
        m_dry = df['m_w_cum_kg'].iloc[-1] / (X0 - X_final) if X0 != X_final else 10.0
        m_w_target = m_dry * (X0 - X_final)
        ax6.axhline(y=m_w_target, color='r', linestyle='--', label=f'Target: {m_w_target:.1f} kg')
    
    ax6.set_xlabel('Time [hours]', fontsize=11)
    ax6.set_ylabel('Water Removed [kg]', fontsize=11)
    ax6.set_title('Cumulative Water Removal', fontsize=12, fontweight='bold')
    ax6.legend(loc='best', fontsize=9)
    ax6.grid(True, alpha=0.3)
    
    # Overall title
    fig.suptitle(f'Dryer Simulation Overview - {csv_path.stem}', 
                 fontsize=14, fontweight='bold', y=0.995)
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_overview.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_tray_evolution(csv_path: Path, output_dir: Path = None) -> None:
    """Plot moisture evolution for all 10 trays.
    
    Shows how moisture content changes across trays over time.
    """
    
    df = pd.read_csv(csv_path)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Panel 1: Moisture content per tray
    colors = plt.cm.viridis(np.linspace(0, 1, 10))
    
    for i in range(10):
        col_name = f'X_tray_{i}'
        if col_name in df.columns:
            ax1.plot(df['time_h'], df[col_name], color=colors[i], 
                    linewidth=1.5, label=f'Tray {i}')
    
    ax1.axhline(y=0.1, color='r', linestyle='--', linewidth=2, label='Target')
    ax1.set_xlabel('Time [hours]', fontsize=11)
    ax1.set_ylabel('Moisture Content [kg/kg db]', fontsize=11)
    ax1.set_title('Moisture Content - All Trays', fontsize=12, fontweight='bold')
    ax1.legend(ncol=2, fontsize=8, loc='best')
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Moisture Ratio per tray
    for i in range(10):
        col_name = f'MR_tray_{i}'
        if col_name in df.columns:
            ax2.plot(df['time_h'], df[col_name], color=colors[i], 
                    linewidth=1.5, label=f'Tray {i}')
    
    ax2.set_xlabel('Time [hours]', fontsize=11)
    ax2.set_ylabel('Moisture Ratio [-]', fontsize=11)
    ax2.set_title('Moisture Ratio - All Trays', fontsize=12, fontweight='bold')
    ax2.legend(ncol=2, fontsize=8, loc='best')
    ax2.grid(True, alpha=0.3)
    
    fig.suptitle(f'Tray-wise Moisture Evolution - {csv_path.stem}', 
                 fontsize=14, fontweight='bold')
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_trays.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_heat_pump_cycle(csv_path: Path, output_dir: Path = None) -> None:
    """Plot heat pump operating conditions.
    
    Shows evaporator and condenser temperatures, pressures, and COP.
    """
    
    df = pd.read_csv(csv_path)
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Panel 1: Evaporator and Condenser Temperatures
    ax1 = axes[0, 0]
    if 'T_evap_C' in df.columns:
        valid = df['T_evap_C'] != 0
        ax1.plot(df[valid]['time_h'], df[valid]['T_evap_C'], 'b-', 
                linewidth=1.5, label='Evaporator')
    if 'T_cond_C' in df.columns:
        valid = df['T_cond_C'] != 0
        ax1.plot(df[valid]['time_h'], df[valid]['T_cond_C'], 'r-', 
                linewidth=1.5, label='Condenser')
    
    ax1.set_xlabel('Time [hours]', fontsize=10)
    ax1.set_ylabel('Temperature [°C]', fontsize=10)
    ax1.set_title('HP Saturation Temperatures', fontsize=11, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Pressures
    ax2 = axes[0, 1]
    if 'P_evap_bar' in df.columns:
        valid = df['P_evap_bar'] > 0
        ax2.plot(df[valid]['time_h'], df[valid]['P_evap_bar'], 'b-', 
                linewidth=1.5, label='Evaporator')
    if 'P_cond_bar' in df.columns:
        valid = df['P_cond_bar'] > 0
        ax2.plot(df[valid]['time_h'], df[valid]['P_cond_bar'], 'r-', 
                linewidth=1.5, label='Condenser')
    
    ax2.set_xlabel('Time [hours]', fontsize=10)
    ax2.set_ylabel('Pressure [bar]', fontsize=10)
    ax2.set_title('HP Pressures', fontsize=11, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # Panel 3: Heat Flows
    ax3 = axes[1, 0]
    if 'Q_evap_kW' in df.columns:
        valid = df['Q_evap_kW'] > 0
        ax3.plot(df[valid]['time_h'], df[valid]['Q_evap_kW'], 'b-', 
                linewidth=1.5, label='Evaporator Heat')
    if 'Q_cond_kW' in df.columns:
        valid = df['Q_cond_kW'] > 0
        ax3.plot(df[valid]['time_h'], df[valid]['Q_cond_kW'], 'r-', 
                linewidth=1.5, label='Condenser Heat')
    if 'W_comp_kW' in df.columns:
        valid = df['W_comp_kW'] > 0
        ax3.plot(df[valid]['time_h'], df[valid]['W_comp_kW'], 'g-', 
                linewidth=1.5, label='Compressor Work')
    
    ax3.set_xlabel('Time [hours]', fontsize=10)
    ax3.set_ylabel('Power [kW]', fontsize=10)
    ax3.set_title('HP Energy Flows', fontsize=11, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # Panel 4: COP and Refrigerant Flow
    ax4 = axes[1, 1]
    ax4_twin = ax4.twinx()
    
    if 'COP' in df.columns:
        valid = df['COP'] > 0
        ax4.plot(df[valid]['time_h'], df[valid]['COP'], 'g-', 
                linewidth=2, label='COP')
        avg_cop = df[valid]['COP'].mean()
        ax4.axhline(y=avg_cop, color='k', linestyle='--', 
                   label=f'Avg: {avg_cop:.2f}')
    
    if 'm_ref_kg_per_s' in df.columns:
        valid = df['m_ref_kg_per_s'] > 0
        ax4_twin.plot(df[valid]['time_h'], df[valid]['m_ref_kg_per_s'] * 1000, 'b--', 
                     linewidth=1, label='Refrigerant Flow', alpha=0.7)
    
    ax4.set_xlabel('Time [hours]', fontsize=10)
    ax4.set_ylabel('COP [-]', fontsize=10, color='g')
    ax4.tick_params(axis='y', labelcolor='g')
    ax4.legend(loc='upper left', fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    ax4_twin.set_ylabel('Refrigerant Flow [g/s]', fontsize=10, color='b')
    ax4_twin.tick_params(axis='y', labelcolor='b')
    ax4_twin.legend(loc='upper right', fontsize=9)
    
    ax4.set_title('COP & Refrigerant Flow', fontsize=11, fontweight='bold')
    
    fig.suptitle(f'Heat Pump Performance - {csv_path.stem}', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_heatpump.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_solar_performance(csv_path: Path, output_dir: Path = None) -> None:
    """Plot solar collector performance (if solar is used).
    
    Shows solar irradiance, useful heat, efficiency, and temperatures.
    """
    
    df = pd.read_csv(csv_path)
    
    # Check if solar is actually used
    if 'Q_solar_kW' not in df.columns or df['Q_solar_kW'].max() == 0:
        print("No solar data in this simulation (Config A or zero solar area)")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Panel 1: Solar Irradiance and Useful Heat
    ax1 = axes[0, 0]
    ax1_twin = ax1.twinx()
    
    ax1.plot(df['time_h'], df['G_solar_Wm2'], 'orange', alpha=0.5, 
            linewidth=1, label='Irradiance')
    ax1_twin.plot(df['time_h'], df['Q_solar_kW'], 'r-', 
                 linewidth=2, label='Useful Heat')
    
    ax1.set_xlabel('Time [hours]', fontsize=10)
    ax1.set_ylabel('Solar Irradiance [W/m²]', fontsize=10, color='orange')
    ax1.tick_params(axis='y', labelcolor='orange')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    ax1_twin.set_ylabel('Useful Heat [kW]', fontsize=10, color='r')
    ax1_twin.tick_params(axis='y', labelcolor='r')
    ax1_twin.legend(loc='upper right', fontsize=9)
    
    ax1.set_title('Solar Irradiance & Heat Output', fontsize=11, fontweight='bold')
    
    # Panel 2: Solar Collector Efficiency
    ax2 = axes[0, 1]
    if 'eta_solar' in df.columns:
        valid = df['eta_solar'] > 0
        ax2.plot(df[valid]['time_h'], df[valid]['eta_solar'] * 100, 'g-', 
                linewidth=1.5)
        avg_eff = df[valid]['eta_solar'].mean() * 100
        ax2.axhline(y=avg_eff, color='k', linestyle='--', 
                   label=f'Average: {avg_eff:.1f}%')
    
    ax2.set_xlabel('Time [hours]', fontsize=10)
    ax2.set_ylabel('Solar Efficiency [%]', fontsize=10)
    ax2.set_title('Solar Collector Efficiency', fontsize=11, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 100])
    
    # Panel 3: Solar Outlet Temperature
    ax3 = axes[1, 0]
    ax3.plot(df['time_h'], df['T_amb_C'], 'gray', alpha=0.5, 
            linewidth=1, label='Ambient')
    if 'T_solar_out_C' in df.columns:
        ax3.plot(df['time_h'], df['T_solar_out_C'], 'orange', 
                linewidth=2, label='Solar Outlet')
    ax3.plot(df['time_h'], df['T_to_chamber_C'], 'r--', 
            linewidth=1.5, label='Chamber Inlet')
    
    ax3.set_xlabel('Time [hours]', fontsize=10)
    ax3.set_ylabel('Temperature [°C]', fontsize=10)
    ax3.set_title('Solar Temperature Boost', fontsize=11, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # Panel 4: Cumulative Solar Energy
    ax4 = axes[1, 1]
    if 'Q_solar_cum_kWh' in df.columns:
        ax4.plot(df['time_h'], df['Q_solar_cum_kWh'], 'orange', 
                linewidth=2, label='Solar Energy')
    if 'W_comp_cum_kWh' in df.columns:
        ax4.plot(df['time_h'], df['W_comp_cum_kWh'], 'b-', 
                linewidth=2, label='Compressor Energy')
    
    ax4.set_xlabel('Time [hours]', fontsize=10)
    ax4.set_ylabel('Cumulative Energy [kWh]', fontsize=10)
    ax4.set_title('Cumulative Energy Comparison', fontsize=11, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    fig.suptitle(f'Solar Collector Performance - {csv_path.stem}', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_solar.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def plot_energy_summary(csv_path: Path, output_dir: Path = None) -> None:
    """Create energy summary bar chart.
    
    Shows total energy consumption breakdown and SEC.
    """
    
    df = pd.read_csv(csv_path)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Panel 1: Energy breakdown
    final_row = df.iloc[-1]
    
    energies = []
    labels = []
    colors = []
    
    if 'W_comp_cum_kWh' in df.columns and final_row['W_comp_cum_kWh'] > 0:
        energies.append(final_row['W_comp_cum_kWh'])
        labels.append('Compressor')
        colors.append('royalblue')
    
    if 'Q_solar_cum_kWh' in df.columns and final_row['Q_solar_cum_kWh'] > 0:
        energies.append(final_row['Q_solar_cum_kWh'])
        labels.append('Solar')
        colors.append('orange')
    
    if 'Q_cond_cum_kWh' in df.columns and final_row['Q_cond_cum_kWh'] > 0:
        energies.append(final_row['Q_cond_cum_kWh'])
        labels.append('Heat to Air')
        colors.append('red')
    
    if energies:
        bars = ax1.bar(labels, energies, color=colors, alpha=0.7, edgecolor='black')
        
        # Add value labels on bars
        for bar, energy in zip(bars, energies):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{energy:.1f} kWh',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax1.set_ylabel('Energy [kWh]', fontsize=11)
    ax1.set_title('Total Energy Breakdown', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Panel 2: Performance metrics
    metrics = []
    values = []
    
    if 'm_w_cum_kg' in df.columns:
        metrics.append('Water Removed')
        values.append(final_row['m_w_cum_kg'])
    
    if 'time_h' in df.columns:
        metrics.append('Drying Time')
        values.append(final_row['time_h'])
    
    if 'SEC_elec_kWh_per_kg' in df.columns:
        sec = df['SEC_elec_kWh_per_kg'].dropna()
        if not sec.empty:
            metrics.append('SEC')
            values.append(sec.iloc[-1])
    
    if 'COP' in df.columns:
        avg_cop = df[df['COP'] > 0]['COP'].mean()
        if not np.isnan(avg_cop):
            metrics.append('Avg COP')
            values.append(avg_cop)
    
    # Create text summary
    summary_text = ""
    for metric, value in zip(metrics, values):
        if metric == 'Water Removed':
            summary_text += f"{metric}: {value:.2f} kg\n"
        elif metric == 'Drying Time':
            summary_text += f"{metric}: {value:.1f} hours\n"
        elif metric == 'SEC':
            summary_text += f"{metric}: {value:.3f} kWh/kg\n"
        elif metric == 'Avg COP':
            summary_text += f"{metric}: {value:.2f}\n"
    
    ax2.text(0.5, 0.5, summary_text, 
            ha='center', va='center', fontsize=14,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            transform=ax2.transAxes)
    ax2.axis('off')
    ax2.set_title('Performance Summary', fontsize=12, fontweight='bold')
    
    fig.suptitle(f'Energy & Performance Summary - {csv_path.stem}', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_summary.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    
    plt.close(fig)


def create_all_plots(csv_path: Path, output_dir: Path = None) -> None:
    """Create all visualization plots for a simulation.
    
    Parameters
    ----------
    csv_path : Path
        Path to simulation CSV file
    output_dir : Path, optional
        Directory to save plots (if None, display only)
    """
    
    print(f"\nCreating plots for: {csv_path.name}")
    print("=" * 60)
    
    plot_overview(csv_path, output_dir)
    print("✓ Overview plot created")
    
    plot_tray_evolution(csv_path, output_dir)
    print("✓ Tray evolution plot created")
    
    plot_heat_pump_cycle(csv_path, output_dir)
    print("✓ Heat pump plot created")
    
    plot_solar_performance(csv_path, output_dir)
    print("✓ Solar plot created (if applicable)")
    
    plot_energy_summary(csv_path, output_dir)
    print("✓ Energy summary created")
    
    print("=" * 60)
    print("All plots created successfully!\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python visualize_results.py <path_to_csv> [output_dir]")
        print("\nExample:")
        print("  python visualize_results.py outputs/config_A/kathmandu/Ac_0m2.csv")
        print("  python visualize_results.py outputs/config_A/kathmandu/Ac_0m2.csv plots/")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not csv_file.exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)
    
    create_all_plots(csv_file, output)
