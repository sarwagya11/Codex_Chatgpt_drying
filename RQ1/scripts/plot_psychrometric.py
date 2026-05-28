"""Psychrometric chart showing air state through each SAHPD component.

Plots the drying cycle on a T_db vs omega diagram:
  Ambient -> Mix -> Evaporator exit -> Condenser exit -> Chamber exhaust -> (recirculate)
"""

from pathlib import Path
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.psychro import p_sat_water_Pa, humidity_ratio_from_T_RH


def draw_rh_curves(ax, p_atm_Pa, T_range=(0, 55), y_max=35,
                   rh_levels=(0.2, 0.4, 0.6, 0.8, 1.0)):
    """Draw constant-RH curves as background, clipped to y_max."""
    T_vals = np.linspace(T_range[0], T_range[1], 200)
    for rh in rh_levels:
        omega_vals = np.array([
            float(humidity_ratio_from_T_RH(T, rh, p_atm_Pa)) * 1000.0
            for T in T_vals
        ])
        # Clip to y_max for display
        omega_clipped = np.where(omega_vals <= y_max, omega_vals, np.nan)
        ax.plot(T_vals, omega_clipped, 'k-', alpha=0.15, linewidth=0.8)
        # Label where curve exits the plot (last valid point)
        valid_mask = ~np.isnan(omega_clipped)
        if valid_mask.any():
            last_idx = np.where(valid_mask)[0][-1]
            ax.text(T_vals[last_idx], omega_clipped[last_idx],
                    f" {int(rh*100)}%", fontsize=7, alpha=0.4,
                    va='bottom', ha='left')


def compute_states(row, p_atm_Pa):
    """Extract T and omega at each state point from a CSV row."""
    T_amb = row['T_amb_C']
    RH_amb = row['RH_amb_pct'] / 100.0
    omega_amb = float(humidity_ratio_from_T_RH(T_amb, RH_amb, p_atm_Pa)) * 1000.0

    T_exhaust = row['T_exhaust_C']
    RH_exhaust = row['RH_exhaust_frac']
    omega_exhaust = float(humidity_ratio_from_T_RH(T_exhaust, RH_exhaust, p_atm_Pa)) * 1000.0

    return {
        'Ambient':    (T_amb, omega_amb),
        'Mix':        (row['T_mix_C'], row['omega_mix'] * 1000.0),
        'After Evap': (row['T_after_evap_C'], row['omega_to_chamber'] * 1000.0),
        'After Cond': (row['T_to_chamber_C'], row['omega_to_chamber'] * 1000.0),
        'Exhaust':    (T_exhaust, omega_exhaust),
    }


COLORS = {
    'Ambient':    '#2ca02c',
    'Mix':        '#1f77b4',
    'After Evap': '#17becf',
    'After Cond': '#d62728',
    'Exhaust':    '#ff7f0e',
}

# (from, to, label)
ARROWS = [
    ('Exhaust', 'Mix', 'Mixing'),
    ('Mix', 'After Evap', 'Evaporator'),
    ('After Evap', 'After Cond', 'Condenser'),
    ('After Cond', 'Exhaust', 'Drying Chamber'),
]

ANNOT_OFFSETS = {
    'Ambient':    (-60, -15),
    'Mix':        (10, 8),
    'After Evap': (-80, 10),
    'After Cond': (10, -15),
    'Exhaust':    (10, 8),
}


def plot_cycle(ax, states, alpha=1.0, label_suffix="", annotate=True):
    """Plot one cycle (5 points + arrows)."""
    for name, (T, w) in states.items():
        ax.scatter(T, w, c=COLORS[name], s=90, zorder=5, alpha=alpha,
                   edgecolors='black', linewidth=0.5)
        if annotate:
            xyoff = ANNOT_OFFSETS.get(name, (8, 8))
            ax.annotate(f"{name}{label_suffix}\n({T:.1f} C, {w:.1f} g/kg)",
                        (T, w), textcoords="offset points", xytext=xyoff,
                        fontsize=8, alpha=alpha, color=COLORS[name],
                        fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.15', fc='white',
                                  ec='none', alpha=0.7))

    arrow_colors = {
        'Mixing':         '#9467bd',   # purple
        'Evaporator':     '#17becf',   # cyan
        'Condenser':      '#d62728',   # red
        'Drying Chamber': '#ff7f0e',   # orange
    }
    for s, e, lbl in ARROWS:
        T1, w1 = states[s]
        T2, w2 = states[e]
        ac = arrow_colors.get(lbl, 'gray')
        ax.annotate("", xy=(T2, w2), xytext=(T1, w1),
                    arrowprops=dict(arrowstyle='->', color=ac,
                                    lw=2.0, alpha=alpha * 0.8))
        if annotate:
            # Place label at 40% along the line, offset perpendicular
            Tm = T1 + 0.4 * (T2 - T1)
            wm = w1 + 0.4 * (w2 - w1)
            # Perpendicular offset direction
            dT, dw = T2 - T1, w2 - w1
            length = max((dT**2 + dw**2)**0.5, 0.01)
            # offset in points: perpendicular to line direction
            px, py = -dw / length * 18, dT / length * 18
            ax.annotate(lbl, (Tm, wm), textcoords="offset points",
                        xytext=(px, py), fontsize=8, alpha=alpha * 0.85,
                        ha='center', va='center', color=ac,
                        fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', fc='white',
                                  ec=ac, alpha=0.8, lw=0.5))


def plot_psychrometric(csv_path, p_atm_Pa, snapshot_h=None, output_dir=None):
    """Create psychrometric chart from simulation CSV."""
    df = pd.read_csv(csv_path)

    required = ['T_mix_C', 'omega_mix', 'T_after_evap_C']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Missing columns: {missing}. Re-run simulation first.")
        return

    # Compute y-axis upper bound from data
    w_max_data = max(
        df['omega_mix'].max() * 1000.0,
        df['omega_to_chamber'].max() * 1000.0,
    )
    # Add headroom for exhaust (typically highest omega)
    y_upper = max(w_max_data * 1.6, 20.0)
    y_upper = min(y_upper, 40.0)

    fig, ax = plt.subplots(figsize=(14, 8))
    draw_rh_curves(ax, p_atm_Pa, y_max=y_upper)

    if snapshot_h is not None:
        idx = (df['time_h'] - snapshot_h).abs().idxmin()
        row = df.iloc[idx]
        states = compute_states(row, p_atm_Pa)
        plot_cycle(ax, states)
        title_extra = f" at t={row['time_h']:.1f}h"
    else:
        max_h = df['time_h'].max()
        snapshots = [
            (max_h * 0.15, 0.30, "Early"),
            (max_h * 0.50, 0.55, "Mid"),
            (max_h * 0.90, 1.00, "Late"),
        ]
        for t_h, alph, label in snapshots:
            idx = (df['time_h'] - t_h).abs().idxmin()
            row = df.iloc[idx]
            states = compute_states(row, p_atm_Pa)
            plot_cycle(ax, states, alpha=alph, label_suffix=f" ({label})",
                       annotate=(label == "Late"))
        title_extra = " (Early -> Mid -> Late)"

    stem = Path(csv_path).stem
    ax.set_xlabel("Dry-Bulb Temperature (deg C)", fontsize=12)
    ax.set_ylabel("Humidity Ratio (g/kg)", fontsize=12)
    ax.set_title(f"Psychrometric Cycle  --  {stem}{title_extra}\n"
                 f"P_atm = {p_atm_Pa/1000:.1f} kPa", fontsize=13)
    ax.grid(True, alpha=0.2)
    ax.set_xlim(0, 55)
    ax.set_ylim(0, y_upper)

    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], marker='o', color='w',
                              markerfacecolor=COLORS[n], markersize=8,
                              label=n) for n in COLORS]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9,
              framealpha=0.9)

    fig.tight_layout()

    if output_dir is None:
        output_dir = PROJECT_ROOT / "plots" / "psychrometric"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"_t{snapshot_h:.0f}h" if snapshot_h is not None else "_multi"
    out_path = output_dir / f"psychro_{stem}{suffix}.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    print(f"Saved: {out_path}")
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychrometric chart for SAHPD")
    parser.add_argument("--file", required=True, help="Simulation CSV path")
    parser.add_argument("--snapshot", type=float, default=None,
                        help="Single snapshot time (hours)")
    parser.add_argument("--p-atm", type=float, default=101325.0,
                        help="Atmospheric pressure [Pa]")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    plot_psychrometric(args.file, args.p_atm, args.snapshot, args.output_dir)
