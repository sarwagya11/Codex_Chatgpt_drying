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
    df = df.iloc[10:].reset_index(drop=True)  # skip startup jump (first ~10 min settling)

    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.3)
    
    # Panel 1: Moisture Content
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(df['time_h'], df['X_db_avg'], 'b-', linewidth=2, label='Average')
    
    # Add first and last tray (auto-detect last tray)
    if 'X_tray_0' in df.columns:
        ax1.plot(df['time_h'], df['X_tray_0'], 'r--', alpha=0.5, label='Tray 0 (first)')
    tray_x_cols = sorted([c for c in df.columns if c.startswith('X_tray_') and '_sec_' not in c],
                         key=lambda c: int(c.split('_')[2]))
    if len(tray_x_cols) > 1:
        last_col = tray_x_cols[-1]
        last_idx = last_col.split('_')[2]
        ax1.plot(df['time_h'], df[last_col], 'g--', alpha=0.5, label=f'Tray {last_idx} (last)')
    
    ax1.axhline(y=0.20, color='k', linestyle=':', label='Target (0.20)')
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
    if 'W_fan_kW' in df.columns and df['W_fan_kW'].max() > 0:
        ax4.plot(df['time_h'], df['W_fan_kW'], 'teal', linewidth=1.5, label='Fan Power')
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

    # Add bypass mode shading if available
    if 'bypass_mode' in df.columns:
        for i in range(len(df)):
            if df['bypass_mode'].iloc[i] == 'bypass':
                ax5.axvspan(df['time_h'].iloc[max(0, i-1)], df['time_h'].iloc[i],
                           alpha=0.12, color='green')

    # Add flow reversal shading if available
    if 'flow_direction' in df.columns and (df['flow_direction'] == 'reverse').any():
        for i in range(len(df)):
            if df['flow_direction'].iloc[i] == 'reverse':
                ax5.axvspan(df['time_h'].iloc[max(0, i-1)], df['time_h'].iloc[i],
                           alpha=0.08, color='purple')

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
        X_final = 0.20
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
    """Plot moisture evolution for all trays (auto-detects tray count).

    Shows how moisture content changes across trays over time.
    """

    df = pd.read_csv(csv_path)

    # Auto-detect number of trays
    tray_x_cols = sorted([c for c in df.columns if c.startswith('X_tray_') and '_sec_' not in c],
                         key=lambda c: int(c.split('_')[2]))
    n_trays = len(tray_x_cols)
    if n_trays == 0:
        print("No per-tray X data in this file")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    colors = plt.cm.viridis(np.linspace(0, 1, max(n_trays, 2)))

    for i in range(n_trays):
        col_name = f'X_tray_{i}'
        if col_name in df.columns:
            ax1.plot(df['time_h'], df[col_name], color=colors[i],
                    linewidth=1.5, label=f'Tray {i}')

    ax1.axhline(y=0.20, color='r', linestyle='--', linewidth=2, label='Target (0.20)')
    ax1.set_xlabel('Time [hours]', fontsize=11)
    ax1.set_ylabel('Moisture Content [kg/kg db]', fontsize=11)
    ax1.set_title('Moisture Content - All Trays', fontsize=12, fontweight='bold')
    ax1.legend(ncol=2, fontsize=8, loc='best')
    ax1.grid(True, alpha=0.3)

    for i in range(n_trays):
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


def plot_tray_temperature_rh(csv_path: Path, output_dir: Path = None) -> None:
    """Plot per-tray air temperature and RH profiles over time.

    Shows how air degrades as it passes through each tray (T drops, RH rises).
    """
    df = pd.read_csv(csv_path)
    # Skip the first 10 rows (~10 minutes) to remove the startup jump.
    # Row 0: open-loop (no recirculation, identical to r=0).
    # Row 1: recirculation starts abruptly with full humid exhaust — large step change.
    # Rows 1-8: system settles to stable recirculation state over ~8 minutes.
    # At 14-16 hour plot scale, starting at t=0.17h is completely invisible.
    df = df.iloc[10:].reset_index(drop=True)

    # Detect number of trays from columns
    tray_t_cols = [c for c in df.columns if c.startswith('T_tray_') and c.endswith('_out_C')]
    tray_rh_cols = [c for c in df.columns if c.startswith('RH_tray_') and c.endswith('_out_frac')]
    n_trays = len(tray_t_cols)

    if n_trays == 0:
        print("No per-tray T/RH data in this file")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    colors = plt.cm.viridis(np.linspace(0, 1, n_trays))

    # Panel 1: Temperature per tray over time
    ax1 = axes[0, 0]
    ax1.plot(df['time_h'], df['T_to_chamber_C'], 'r-', linewidth=2.5,
             label='Inlet (50 C)', zorder=10)
    for i in range(n_trays):
        col = f'T_tray_{i}_out_C'
        if col in df.columns:
            ax1.plot(df['time_h'], df[col], color=colors[i],
                     linewidth=1, label=f'Tray {i}', alpha=0.8)
    ax1.set_xlabel('Time [hours]', fontsize=11)
    ax1.set_ylabel('Temperature [C]', fontsize=11)
    ax1.set_title('Air Temperature After Each Tray', fontsize=12, fontweight='bold')
    ax1.legend(ncol=3, fontsize=7, loc='lower right')
    ax1.grid(True, alpha=0.3)

    # Panel 2: RH per tray over time
    ax2 = axes[0, 1]
    if 'RH_to_chamber_frac' in df.columns:
        ax2.plot(df['time_h'], df['RH_to_chamber_frac'] * 100, 'r-',
                 linewidth=2.5, label='Inlet', zorder=10)
    for i in range(n_trays):
        col = f'RH_tray_{i}_out_frac'
        if col in df.columns:
            ax2.plot(df['time_h'], df[col] * 100, color=colors[i],
                     linewidth=1, label=f'Tray {i}', alpha=0.8)
    ax2.axhline(y=100, color='k', linestyle=':', alpha=0.4)
    ax2.set_xlabel('Time [hours]', fontsize=11)
    ax2.set_ylabel('Relative Humidity [%]', fontsize=11)
    ax2.set_title('Air RH After Each Tray', fontsize=12, fontweight='bold')
    ax2.legend(ncol=3, fontsize=7, loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 105])

    # Panel 3: Snapshot - T profile across trays at selected times
    ax3 = axes[1, 0]
    snapshot_hours = [0.5, 2.0, 4.0, 6.0, 8.0, 10.0]
    snap_colors = plt.cm.coolwarm(np.linspace(0, 1, len(snapshot_hours)))
    tray_indices = list(range(n_trays))

    for sh, sc in zip(snapshot_hours, snap_colors):
        row_idx = (df['time_h'] - sh).abs().idxmin()
        t_vals = [df.loc[row_idx, 'T_to_chamber_C']]
        for i in range(n_trays):
            col = f'T_tray_{i}_out_C'
            if col in df.columns:
                t_vals.append(df.loc[row_idx, col])
        actual_h = df.loc[row_idx, 'time_h']
        ax3.plot(range(len(t_vals)), t_vals, 'o-', color=sc,
                 markersize=4, linewidth=1.5, label=f't={actual_h:.1f}h')

    ax3.set_xlabel('Position (0=inlet, 1-10=trays)', fontsize=11)
    ax3.set_ylabel('Temperature [C]', fontsize=11)
    ax3.set_title('Temperature Profile Across Trays', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.set_xticks(range(n_trays + 1))
    ax3.set_xticklabels(['In'] + [str(i) for i in range(n_trays)], fontsize=8)

    # Panel 4: Snapshot - RH profile across trays at selected times
    ax4 = axes[1, 1]
    for sh, sc in zip(snapshot_hours, snap_colors):
        row_idx = (df['time_h'] - sh).abs().idxmin()
        rh_vals = []
        if 'RH_to_chamber_frac' in df.columns:
            rh_vals.append(df.loc[row_idx, 'RH_to_chamber_frac'] * 100)
        for i in range(n_trays):
            col = f'RH_tray_{i}_out_frac'
            if col in df.columns:
                rh_vals.append(df.loc[row_idx, col] * 100)
        actual_h = df.loc[row_idx, 'time_h']
        ax4.plot(range(len(rh_vals)), rh_vals, 'o-', color=sc,
                 markersize=4, linewidth=1.5, label=f't={actual_h:.1f}h')

    ax4.axhline(y=100, color='k', linestyle=':', alpha=0.4)
    ax4.set_xlabel('Position (0=inlet, 1-10=trays)', fontsize=11)
    ax4.set_ylabel('Relative Humidity [%]', fontsize=11)
    ax4.set_title('RH Profile Across Trays', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)
    ax4.set_xticks(range(n_trays + 1))
    ax4.set_xticklabels(['In'] + [str(i) for i in range(n_trays)], fontsize=8)
    ax4.set_ylim([0, 105])

    fig.suptitle(f'Per-Tray Air State Evolution - {csv_path.stem}',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_tray_T_RH.png"
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
    df = df.iloc[10:].reset_index(drop=True)  # skip startup jump (first ~10 min settling)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Panel 1: Evaporator and Condenser Temperatures with operational zones
    ax1 = axes[0, 0]
    t_max = df['time_h'].max()

    # Shade frost-risk zone (T_evap < 2°C) — light blue
    ax1.axhspan(-30, 2.0, alpha=0.10, color='blue', label='_nolegend_')
    ax1.axhline(y=2.0, color='blue', linestyle=':', linewidth=1.0, alpha=0.7, label='Frost risk limit (2°C)')

    # Shade outside-AC-range zone (T_evap > 20°C) — light orange
    ax1.axhspan(20.0, 60, alpha=0.10, color='orange', label='_nolegend_')
    ax1.axhline(y=20.0, color='orange', linestyle=':', linewidth=1.0, alpha=0.7, label='AC upper limit (20°C)')

    # Frost-risk and outside-AC-range steps are indicated by the threshold lines above.
    # No scatter dots — the shaded zones and lines are sufficient.

    if 'T_evap_C' in df.columns:
        valid = df['T_evap_C'] != 0
        ax1.plot(df[valid]['time_h'], df[valid]['T_evap_C'], 'b-',
                linewidth=1.5, label='T_evap')
    if 'T_cond_C' in df.columns:
        valid = df['T_cond_C'] != 0
        ax1.plot(df[valid]['time_h'], df[valid]['T_cond_C'], 'r-',
                linewidth=1.5, label='T_cond')

    ax1.set_xlabel('Time [hours]', fontsize=10)
    ax1.set_ylabel('Temperature [°C]', fontsize=10)
    ax1.set_title('HP Saturation Temperatures', fontsize=11, fontweight='bold')
    ax1.legend(fontsize=8, loc='center right')
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Pressures
    ax2 = axes[0, 1]
    # Shade HP-off periods (W_comp == 0) with grey background
    if 'W_comp_kW' in df.columns:
        hp_off_mask = df['W_comp_kW'] < 0.001
        in_off = False
        t_off_start = None
        for _, row in df[['time_h', 'W_comp_kW']].iterrows():
            off = row['W_comp_kW'] < 0.001
            if off and not in_off:
                t_off_start = row['time_h']
                in_off = True
            elif not off and in_off:
                ax2.axvspan(t_off_start, row['time_h'], alpha=0.25, color='#f0c060', label='HP off (solar)')
                in_off = False
        if in_off:
            ax2.axvspan(t_off_start, df['time_h'].iloc[-1], alpha=0.25, color='#f0c060', label='HP off (solar)')
    if 'P_evap_bar' in df.columns:
        p_evap = df['P_evap_bar'].where(df['P_evap_bar'] > 0)  # NaN when HP off → gap in line
        ax2.plot(df['time_h'], p_evap, 'b-', linewidth=1.5, label='Evaporator')
    if 'P_cond_bar' in df.columns:
        p_cond = df['P_cond_bar'].where(df['P_cond_bar'] > 0)  # NaN when HP off → gap in line
        ax2.plot(df['time_h'], p_cond, 'r-', linewidth=1.5, label='Condenser')

    ax2.set_xlabel('Time [hours]', fontsize=10)
    ax2.set_ylabel('Pressure [bar]', fontsize=10)
    ax2.set_title('HP Pressures', fontsize=11, fontweight='bold')
    # Deduplicate legend entries (axvspan may create duplicates)
    handles, labels = ax2.get_legend_handles_labels()
    seen = {}
    for h, l in zip(handles, labels):
        if l not in seen:
            seen[l] = h
    ax2.legend(seen.values(), seen.keys(), fontsize=9)
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
        # Mark timesteps where Q_cond exceeds 1-ton AC limit (4 kW)
        if 'flag_hp_at_capacity' in df.columns:
            at_cap = df[(df['flag_hp_at_capacity'] == 1) & (df['Q_cond_kW'] > 0)]
            if len(at_cap):
                ax3.scatter(at_cap['time_h'], at_cap['Q_cond_kW'], color='red', s=8,
                            zorder=5, label=f'Above AC limit ({len(at_cap)} steps)')
    if 'W_comp_kW' in df.columns:
        valid = df['W_comp_kW'] > 0
        ax3.plot(df[valid]['time_h'], df[valid]['W_comp_kW'], 'g-',
                linewidth=1.5, label='Compressor Work')
    # Reference line: 1-ton AC condenser capacity limit
    ax3.axhline(y=4.0, color='red', linestyle='--', linewidth=1.0, alpha=0.7,
                label='AC capacity limit (4 kW)')

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

    if 'W_fan_cum_kWh' in df.columns and final_row['W_fan_cum_kWh'] > 0:
        energies.append(final_row['W_fan_cum_kWh'])
        labels.append('Fan')
        colors.append('teal')

    q_solar_wasted = float(final_row.get('Q_solar_wasted_cum_kWh', 0.0) or 0.0)
    q_solar_total  = float(final_row.get('Q_solar_cum_kWh', 0.0) or 0.0)
    q_solar_delivered = max(0.0, q_solar_total - q_solar_wasted)
    solar_split = q_solar_total > 0
    if solar_split:
        # Stacked: delivered + wasted
        energies.append(q_solar_delivered)
        labels.append('Solar (delivered)')
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

        # Overlay wasted-solar segment on the Solar bar
        if solar_split and q_solar_wasted > 0:
            solar_idx = labels.index('Solar (delivered)')
            sbar = bars[solar_idx]
            ax1.bar(sbar.get_x() + sbar.get_width()/2, q_solar_wasted,
                    width=sbar.get_width(), bottom=q_solar_delivered,
                    color='gray', alpha=0.7, edgecolor='black',
                    label='Solar (wasted > T_set)')
            pct = 100.0 * q_solar_wasted / q_solar_total
            ax1.text(sbar.get_x() + sbar.get_width()/2,
                     q_solar_delivered + q_solar_wasted,
                     f'+{q_solar_wasted:.1f} kWh\n({pct:.0f}% lost)',
                     ha='center', va='bottom', fontsize=9, color='dimgray')
            ax1.legend(loc='upper left', fontsize=8)
    
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
            metrics.append('SEC (comp+fan)')
            values.append(sec.iloc[-1])

    if 'SMER_kg_per_kWh' in df.columns:
        smer = df['SMER_kg_per_kWh'].dropna()
        if not smer.empty:
            metrics.append('SMER')
            values.append(smer.iloc[-1])
    elif 'SEC_elec_kWh_per_kg' in df.columns:
        sec = df['SEC_elec_kWh_per_kg'].dropna()
        if not sec.empty and sec.iloc[-1] > 0:
            metrics.append('SMER')
            values.append(1.0 / sec.iloc[-1])

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
        elif metric == 'SEC (comp+fan)':
            summary_text += f"{metric}: {value:.3f} kWh/kg\n"
        elif metric == 'SMER':
            summary_text += f"{metric}: {value:.2f} kg/kWh\n"
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


def _detect_sections(df: pd.DataFrame):
    """Detect per-section columns and return (n_trays, n_sections) or (0, 0)."""
    import re
    sec_cols = [c for c in df.columns if re.match(r'X_tray_\d+_sec_\d+$', c)]
    if not sec_cols:
        return 0, 0
    trays = set()
    secs = set()
    for c in sec_cols:
        parts = c.split('_')
        trays.add(int(parts[2]))
        secs.add(int(parts[4]))
    return max(trays) + 1, max(secs) + 1


def plot_section_moisture(csv_path: Path, output_dir: Path = None) -> None:
    """Plot per-section moisture evolution over time.

    For each tray, plots each section's X vs time on the same panel.
    Only created when n_sections > 1.
    """
    df = pd.read_csv(csv_path)
    n_trays, n_sec = _detect_sections(df)
    if n_sec <= 1:
        return

    fig, axes = plt.subplots(1, n_trays, figsize=(4 * n_trays, 5), sharey=True)
    if n_trays == 1:
        axes = [axes]

    for i in range(n_trays):
        ax = axes[i]
        colors = plt.cm.plasma(np.linspace(0.15, 0.85, n_sec))
        for j in range(n_sec):
            col = f'X_tray_{i}_sec_{j}'
            if col in df.columns:
                label = f'Sec {j} ({"inlet" if j == 0 else "outlet" if j == n_sec - 1 else str(j)})'
                ax.plot(df['time_h'], df[col], color=colors[j], linewidth=1.5, label=label)
        ax.axhline(y=0.20, color='k', linestyle=':', linewidth=1, alpha=0.6)
        ax.set_xlabel('Time [hours]', fontsize=10)
        if i == 0:
            ax.set_ylabel('Moisture Content [kg/kg db]', fontsize=10)
        ax.set_title(f'Tray {i}', fontsize=11, fontweight='bold')
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, alpha=0.3)

    fig.suptitle(f'Within-Tray Section Moisture - {csv_path.stem}',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_sections.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_section_heatmap(csv_path: Path, output_dir: Path = None) -> None:
    """Plot spatial moisture heatmaps at selected time snapshots.

    x-axis = section index, y-axis = tray index, color = moisture X.
    Only created when n_sections > 1.
    """
    df = pd.read_csv(csv_path)
    n_trays, n_sec = _detect_sections(df)
    if n_sec <= 1:
        return

    # Select ~6 time snapshots
    max_h = df['time_h'].max()
    snap_hours = [h for h in [0.5, 2.0, 4.0, 6.0, 8.0, 10.0] if h <= max_h]
    if not snap_hours:
        snap_hours = [max_h / 2]

    n_snaps = len(snap_hours)
    fig, axes = plt.subplots(1, n_snaps, figsize=(3.5 * n_snaps, 4), sharey=True)
    if n_snaps == 1:
        axes = [axes]

    X0 = df['X_db_avg'].iloc[0] if 'X_db_avg' in df.columns else 6.5
    vmin, vmax = 0.0, X0

    for idx, sh in enumerate(snap_hours):
        row_idx = (df['time_h'] - sh).abs().idxmin()
        actual_h = df.loc[row_idx, 'time_h']

        grid = np.zeros((n_trays, n_sec))
        for i in range(n_trays):
            for j in range(n_sec):
                col = f'X_tray_{i}_sec_{j}'
                grid[i, j] = df.loc[row_idx, col] if col in df.columns else 0.0

        ax = axes[idx]
        im = ax.imshow(grid, aspect='auto', cmap='YlOrRd_r', vmin=vmin, vmax=vmax,
                        origin='lower')
        ax.set_xlabel('Section', fontsize=10)
        if idx == 0:
            ax.set_ylabel('Tray', fontsize=10)
        ax.set_title(f't = {actual_h:.1f} h', fontsize=10)
        ax.set_xticks(range(n_sec))
        ax.set_yticks(range(n_trays))

    fig.colorbar(im, ax=axes, label='Moisture X [kg/kg db]', shrink=0.8)
    fig.suptitle(f'Moisture Heatmap (Tray x Section) - {csv_path.stem}',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_heatmap.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_bypass_mode(csv_path: Path, output_dir: Path = None) -> None:
    """Plot evaporator bypass analysis.

    Top panel: Exhaust RH with bypass threshold line and shaded regions.
    Bottom panel: Compressor power colored by bypass mode.
    Only created when bypass_mode column has non-'n/a' values.
    """
    df = pd.read_csv(csv_path)
    df = df.iloc[10:].reset_index(drop=True)  # skip startup jump (first ~10 min settling)
    if 'bypass_mode' not in df.columns:
        return
    modes = df['bypass_mode'].unique()
    if set(modes) <= {'none'}:
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    t = df['time_h']

    # --- Top panel: Exhaust RH ---
    ax1.plot(t, df['RH_exhaust_frac'] * 100, 'b-', linewidth=1.5, label='Exhaust RH')

    # Shade bypass/evap regions
    for i in range(len(df)):
        if df['bypass_mode'].iloc[i] == 'bypass':
            ax1.axvspan(t.iloc[max(0, i-1)], t.iloc[i], alpha=0.15, color='green')
        elif df['bypass_mode'].iloc[i] == 'evap':
            ax1.axvspan(t.iloc[max(0, i-1)], t.iloc[i], alpha=0.08, color='blue')

    # Add proxy patches for legend
    from matplotlib.patches import Patch
    ax1.legend(handles=[
        plt.Line2D([0], [0], color='b', linewidth=1.5, label='Exhaust RH'),
        Patch(facecolor='green', alpha=0.3, label='Bypass mode'),
        Patch(facecolor='blue', alpha=0.2, label='Evap mode'),
    ], fontsize=9, loc='best')

    ax1.set_ylabel('Relative Humidity [%]', fontsize=11)
    ax1.set_title('Exhaust RH & Bypass Mode', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([0, 105])

    # --- Bottom panel: Compressor power ---
    if 'W_comp_kW' in df.columns:
        # Color by mode
        for mode_val, color in [('evap', 'blue'), ('bypass', 'green'), ('n/a', 'gray')]:
            mask = df['bypass_mode'] == mode_val
            if mask.any():
                ax2.scatter(t[mask], df.loc[mask, 'W_comp_kW'], c=color,
                           s=2, alpha=0.6, label=mode_val)

    ax2.set_xlabel('Time [hours]', fontsize=11)
    ax2.set_ylabel('Compressor Power [kW]', fontsize=11)
    ax2.set_title('Compressor Power by Operating Mode', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=9, loc='best')
    ax2.grid(True, alpha=0.3)

    # Add flow direction indicators at reversal points
    if 'flow_direction' in df.columns and (df['flow_direction'] == 'reverse').any():
        dirs = df['flow_direction'].values
        for i in range(1, len(dirs)):
            if dirs[i] != dirs[i - 1]:
                marker = r'$\downarrow$' if dirs[i] == 'reverse' else r'$\uparrow$'
                ax1.annotate(marker, xy=(t.iloc[i], 0), xycoords=('data', 'axes fraction'),
                            fontsize=10, ha='center', va='bottom', color='purple', alpha=0.7)

    fig.suptitle(f'Evaporator Bypass Analysis - {csv_path.stem}',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{csv_path.stem}_bypass.png"
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
    print("[OK] Overview plot created")
    
    plot_tray_evolution(csv_path, output_dir)
    print("[OK] Tray evolution plot created")

    plot_tray_temperature_rh(csv_path, output_dir)
    print("[OK] Per-tray T/RH plot created")

    plot_heat_pump_cycle(csv_path, output_dir)
    print("[OK] Heat pump plot created")
    
    plot_solar_performance(csv_path, output_dir)
    print("[OK] Solar plot created (if applicable)")
    
    plot_energy_summary(csv_path, output_dir)
    print("[OK] Energy summary created")

    # Section plots (only when n_sections > 1)
    df_check = pd.read_csv(csv_path)
    n_t, n_s = _detect_sections(df_check)
    if n_s > 1:
        plot_section_moisture(csv_path, output_dir)
        print(f"[OK] Section moisture plot created ({n_t} trays x {n_s} sections)")
        plot_section_heatmap(csv_path, output_dir)
        print("[OK] Section heatmap created")

    # Bypass mode plot
    if 'bypass_mode' in df_check.columns and not (set(df_check['bypass_mode'].unique()) <= {'none'}):
        plot_bypass_mode(csv_path, output_dir)
        print("[OK] Bypass mode plot created")

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
