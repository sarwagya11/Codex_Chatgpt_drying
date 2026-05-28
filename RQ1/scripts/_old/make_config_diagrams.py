"""Generate schematic diagrams for all 5 SAHPD configuration families.

Produces publication-quality flow diagrams showing:
  - Config A: HP-only (open-loop baseline)
  - Config B: Solar + HP series
  - Config C: Solar-assisted evaporator (COP improvement)
  - Config D: HRX + HP (heat recovery)
  - Config E: HRX + Solar + HP (full integration)

Each diagram shows component boxes, air flow arrows, and energy annotations.

Usage:
    python scripts/make_config_diagrams.py
    python scripts/make_config_diagrams.py --format pdf
    python scripts/make_config_diagrams.py --format svg
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "figures"

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
C_AMB    = '#4FC3F7'   # Light blue — ambient air
C_SOLAR  = '#FFB74D'   # Orange — solar collector
C_EVAP   = '#81C784'   # Green — evaporator
C_COND   = '#E57373'   # Red — condenser
C_CHAM   = '#CE93D8'   # Purple — chamber
C_HRX    = '#FFD54F'   # Yellow — HRX
C_COMP   = '#90A4AE'   # Grey — compressor
C_EXH    = '#BCAAA4'   # Brown-grey — exhaust
C_BG     = '#FAFAFA'   # Background

# Component text style
COMP_FONT = dict(fontsize=9, fontweight='bold', ha='center', va='center',
                 fontfamily='sans-serif')
LABEL_FONT = dict(fontsize=7.5, ha='center', va='center',
                  fontfamily='sans-serif', style='italic', color='#555555')
ARROW_STYLE = dict(arrowstyle='->', color='#333333', lw=1.8,
                   connectionstyle='arc3,rad=0',
                   mutation_scale=15)
THIN_ARROW = dict(arrowstyle='->', color='#777777', lw=1.2,
                  connectionstyle='arc3,rad=0', mutation_scale=12)


def draw_box(ax, xy, w, h, color, text, text2=None, rounded=True):
    """Draw a component box with label."""
    x, y = xy
    style = "round,pad=0.02" if rounded else "square,pad=0.01"
    box = FancyBboxPatch((x, y), w, h, boxstyle=style,
                         facecolor=color, edgecolor='#333333', linewidth=1.3,
                         zorder=3)
    ax.add_patch(box)
    cx, cy = x + w/2, y + h/2
    if text2:
        ax.text(cx, cy + 0.018, text, **COMP_FONT, zorder=4)
        ax.text(cx, cy - 0.018, text2, **LABEL_FONT, zorder=4)
    else:
        ax.text(cx, cy, text, **COMP_FONT, zorder=4)
    return (cx, cy)


def draw_arrow(ax, start, end, label=None, offset=(0, 0.02), style=None):
    """Draw an arrow between two points with optional label."""
    s = style or ARROW_STYLE
    arrow = FancyArrowPatch(start, end, **s, zorder=2)
    ax.add_patch(arrow)
    if label:
        mx = (start[0] + end[0]) / 2 + offset[0]
        my = (start[1] + end[1]) / 2 + offset[1]
        ax.text(mx, my, label, fontsize=7, ha='center', va='center',
                fontfamily='sans-serif', color='#333333',
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85),
                zorder=5)


def draw_ambient(ax, xy, direction='right'):
    """Draw ambient air source symbol."""
    x, y = xy
    ax.annotate('', xy=(x + 0.03, y) if direction == 'right' else (x - 0.03, y),
                xytext=(x, y), arrowprops=dict(arrowstyle='->', lw=1.5, color=C_AMB[:-2]))
    ax.text(x - 0.04 if direction == 'right' else x + 0.04, y, 'Ambient\nAir',
            fontsize=7, ha='right' if direction == 'right' else 'left',
            va='center', color='#0277BD', fontweight='bold')


def draw_exhaust(ax, xy, direction='right'):
    """Draw exhaust symbol."""
    x, y = xy
    ax.annotate('', xy=(x + 0.04, y) if direction == 'right' else (x - 0.04, y),
                xytext=(x, y), arrowprops=dict(arrowstyle='->', lw=1.5, color=C_EXH))
    ax.text(x + 0.07 if direction == 'right' else x - 0.07, y, 'Exhaust',
            fontsize=7, ha='left' if direction == 'right' else 'right',
            va='center', color='#5D4037', fontweight='bold')


def setup_ax(ax, title):
    """Configure axes."""
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 0.55)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_facecolor(C_BG)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10,
                 fontfamily='sans-serif')


# ======================================================================
# CONFIG A: HP-only (open-loop)
# ======================================================================
def draw_config_A(ax):
    setup_ax(ax, 'Configuration A: Heat Pump Convective Dryer')

    bw, bh = 0.16, 0.08  # box width, height

    # Components left to right
    amb_pt = (0.02, 0.28)
    evap_c = draw_box(ax, (0.15, 0.08), bw, bh, C_EVAP, 'Evaporator', 'Q_evap')
    cond_c = draw_box(ax, (0.35, 0.24), bw, bh, C_COND, 'Condenser', 'Q_cond')
    cham_c = draw_box(ax, (0.62, 0.24), bw, bh, C_CHAM, 'Drying\nChamber')

    # Compressor (small box between evap and cond)
    comp_c = draw_box(ax, (0.26, 0.39), 0.12, 0.06, C_COMP, 'Compressor', 'W_comp')

    # Ambient air to condenser
    draw_ambient(ax, (0.08, 0.28))
    draw_arrow(ax, (0.12, 0.28), (0.35, 0.28), 'T_amb, \u03c9_amb')

    # Condenser to chamber
    draw_arrow(ax, (0.51, 0.28), (0.62, 0.28), 'T_set')

    # Chamber to exhaust
    draw_arrow(ax, (0.78, 0.28), (0.88, 0.28))
    draw_exhaust(ax, (0.88, 0.28))

    # Separate ambient to evaporator
    draw_ambient(ax, (0.08, 0.12))
    draw_arrow(ax, (0.12, 0.12), (0.15, 0.12))

    # Evaporator discards air
    draw_arrow(ax, (0.31, 0.12), (0.40, 0.12))
    ax.text(0.44, 0.12, 'Discarded', fontsize=7, color='#777', va='center')

    # Refrigerant loop (dashed)
    ax.annotate('', xy=(0.26, 0.42), xytext=(0.23, 0.16),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))
    ax.annotate('', xy=(0.43, 0.28), xytext=(0.38, 0.39),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))
    ax.text(0.19, 0.30, 'R134a\ncycle', fontsize=6, color='#666', ha='center',
            style='italic')


# ======================================================================
# CONFIG B: Solar + HP series
# ======================================================================
def draw_config_B(ax):
    setup_ax(ax, 'Configuration B: Solar + Heat Pump Series')

    bw, bh = 0.15, 0.08

    # Components
    solar_c = draw_box(ax, (0.12, 0.24), bw, bh, C_SOLAR, 'Solar\nCollector')
    cond_c  = draw_box(ax, (0.38, 0.24), bw, bh, C_COND, 'Condenser', 'Q_cond')
    cham_c  = draw_box(ax, (0.64, 0.24), bw, bh, C_CHAM, 'Drying\nChamber')
    evap_c  = draw_box(ax, (0.38, 0.06), bw, bh, C_EVAP, 'Evaporator', 'Q_evap')
    comp_c  = draw_box(ax, (0.38, 0.40), 0.12, 0.06, C_COMP, 'Compressor')

    # Ambient to solar
    draw_ambient(ax, (0.02, 0.28))
    draw_arrow(ax, (0.06, 0.28), (0.12, 0.28), 'T_amb')

    # Solar to condenser
    draw_arrow(ax, (0.27, 0.28), (0.38, 0.28), 'T_solar')

    # Condenser to chamber
    draw_arrow(ax, (0.53, 0.28), (0.64, 0.28), 'T_set')

    # Chamber exhaust
    draw_arrow(ax, (0.79, 0.28), (0.90, 0.28))
    draw_exhaust(ax, (0.90, 0.28))

    # Separate ambient to evaporator
    draw_ambient(ax, (0.15, 0.10))
    draw_arrow(ax, (0.19, 0.10), (0.38, 0.10))
    draw_arrow(ax, (0.53, 0.10), (0.62, 0.10))
    ax.text(0.66, 0.10, 'Discarded', fontsize=7, color='#777', va='center')

    # Refrigerant loop
    ax.annotate('', xy=(0.40, 0.40), xytext=(0.44, 0.14),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))
    ax.annotate('', xy=(0.46, 0.32), xytext=(0.48, 0.40),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))

    # Solar annotation
    ax.annotate('GHI', xy=(0.20, 0.35), fontsize=8, color='#E65100',
                fontweight='bold', ha='center')
    ax.annotate('', xy=(0.20, 0.32), xytext=(0.20, 0.37),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#E65100'))


# ======================================================================
# CONFIG C: Solar-assisted evaporator
# ======================================================================
def draw_config_C(ax):
    setup_ax(ax, 'Configuration C: Solar-Assisted Evaporator')

    bw, bh = 0.15, 0.08

    # Components — solar heats evaporator air stream
    solar_c = draw_box(ax, (0.12, 0.06), bw, bh, C_SOLAR, 'Solar\nCollector')
    evap_c  = draw_box(ax, (0.38, 0.06), bw, bh, C_EVAP, 'Evaporator', 'Higher T_evap')
    cond_c  = draw_box(ax, (0.38, 0.24), bw, bh, C_COND, 'Condenser', 'Q_cond')
    cham_c  = draw_box(ax, (0.64, 0.24), bw, bh, C_CHAM, 'Drying\nChamber')
    comp_c  = draw_box(ax, (0.38, 0.40), 0.12, 0.06, C_COMP, 'Compressor')

    # Ambient to condenser (main stream)
    draw_ambient(ax, (0.12, 0.28))
    draw_arrow(ax, (0.16, 0.28), (0.38, 0.28), 'T_amb')

    # Condenser to chamber
    draw_arrow(ax, (0.53, 0.28), (0.64, 0.28), 'T_set')

    # Chamber exhaust
    draw_arrow(ax, (0.79, 0.28), (0.90, 0.28))
    draw_exhaust(ax, (0.90, 0.28))

    # Ambient to solar (evaporator stream)
    draw_ambient(ax, (0.02, 0.10))
    draw_arrow(ax, (0.06, 0.10), (0.12, 0.10), 'T_amb')

    # Solar to evaporator
    draw_arrow(ax, (0.27, 0.10), (0.38, 0.10), 'T_solar')

    # Evaporator discard
    draw_arrow(ax, (0.53, 0.10), (0.62, 0.10))
    ax.text(0.66, 0.10, 'Discarded', fontsize=7, color='#777', va='center')

    # Refrigerant loop
    ax.annotate('', xy=(0.40, 0.40), xytext=(0.44, 0.14),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))
    ax.annotate('', xy=(0.46, 0.32), xytext=(0.48, 0.40),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))

    # Solar annotation
    ax.annotate('GHI', xy=(0.20, 0.17), fontsize=8, color='#E65100',
                fontweight='bold', ha='center')
    ax.annotate('', xy=(0.20, 0.14), xytext=(0.20, 0.20),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#E65100'))

    # COP improvement annotation
    ax.text(0.55, 0.46, 'Higher COP\n(reduced \u0394T lift)',
            fontsize=7, ha='center', color='#2E7D32',
            bbox=dict(boxstyle='round,pad=0.3', fc='#E8F5E9', ec='#81C784'))


# ======================================================================
# CONFIG D: HRX + HP
# ======================================================================
def draw_config_D(ax):
    setup_ax(ax, 'Configuration D: Heat Recovery + Heat Pump')

    bw, bh = 0.14, 0.08

    # HRX is the key new component
    hrx_c  = draw_box(ax, (0.14, 0.20), bw + 0.02, bh + 0.04, C_HRX, 'HRX', '\u03b5 = 0.70')
    cond_c = draw_box(ax, (0.42, 0.30), bw, bh, C_COND, 'Condenser', 'Q_cond')
    cham_c = draw_box(ax, (0.66, 0.30), bw, bh, C_CHAM, 'Drying\nChamber')
    evap_c = draw_box(ax, (0.42, 0.06), bw, bh, C_EVAP, 'Evaporator')
    comp_c = draw_box(ax, (0.42, 0.44), 0.11, 0.06, C_COMP, 'Comp.')

    # Ambient in -> HRX cold side
    draw_ambient(ax, (0.02, 0.34))
    draw_arrow(ax, (0.06, 0.34), (0.14, 0.34), 'Cold in')

    # HRX cold out -> Condenser
    draw_arrow(ax, (0.30, 0.34), (0.42, 0.34), 'Pre-warmed')

    # Condenser -> Chamber
    draw_arrow(ax, (0.56, 0.34), (0.66, 0.34), 'T_set')

    # Chamber exhaust -> HRX hot side
    draw_arrow(ax, (0.80, 0.34), (0.88, 0.34))
    # Exhaust goes down and back to HRX
    draw_arrow(ax, (0.88, 0.34), (0.88, 0.22), style=THIN_ARROW)
    draw_arrow(ax, (0.88, 0.22), (0.30, 0.22), label='Hot exhaust', style=THIN_ARROW)

    # HRX hot out -> exhaust
    draw_arrow(ax, (0.14, 0.22), (0.04, 0.22), style=THIN_ARROW)
    ax.text(0.01, 0.18, 'Cooled\nExhaust', fontsize=6.5, color='#5D4037',
            fontweight='bold', ha='center')

    # Separate ambient to evaporator
    draw_ambient(ax, (0.20, 0.10))
    draw_arrow(ax, (0.24, 0.10), (0.42, 0.10))
    draw_arrow(ax, (0.56, 0.10), (0.64, 0.10))
    ax.text(0.68, 0.10, 'Discarded', fontsize=7, color='#777', va='center')

    # Refrigerant loop
    ax.annotate('', xy=(0.44, 0.44), xytext=(0.48, 0.14),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))
    ax.annotate('', xy=(0.50, 0.38), xytext=(0.51, 0.44),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))

    # HRX energy annotation
    ax.text(0.22, 0.44, 'Waste heat\nrecovery',
            fontsize=7, ha='center', color='#F57F17',
            bbox=dict(boxstyle='round,pad=0.3', fc='#FFF9C4', ec='#FFD54F'))


# ======================================================================
# CONFIG E: HRX + Solar + HP (full integration)
# ======================================================================
def draw_config_E(ax):
    setup_ax(ax, 'Configuration E: HRX + Solar + Heat Pump')

    bw, bh = 0.13, 0.07

    # All three thermal sources
    hrx_c   = draw_box(ax, (0.08, 0.20), bw + 0.01, bh + 0.04, C_HRX, 'HRX', '\u03b5 = 0.70')
    solar_c = draw_box(ax, (0.28, 0.30), bw, bh, C_SOLAR, 'Solar', 'Q_solar')
    cond_c  = draw_box(ax, (0.48, 0.30), bw, bh, C_COND, 'Condenser', 'Q_cond')
    cham_c  = draw_box(ax, (0.68, 0.30), bw, bh, C_CHAM, 'Chamber')
    evap_c  = draw_box(ax, (0.48, 0.06), bw, bh, C_EVAP, 'Evaporator')
    comp_c  = draw_box(ax, (0.48, 0.44), 0.10, 0.055, C_COMP, 'Comp.')

    # Ambient -> HRX cold
    draw_ambient(ax, (0.00, 0.34))
    draw_arrow(ax, (0.04, 0.34), (0.08, 0.34))

    # HRX cold out -> Solar
    draw_arrow(ax, (0.22, 0.34), (0.28, 0.34), 'Pre-warmed')

    # Solar -> Condenser
    draw_arrow(ax, (0.41, 0.34), (0.48, 0.34), 'T_solar')

    # Condenser -> Chamber
    draw_arrow(ax, (0.61, 0.34), (0.68, 0.34), 'T_set')

    # Chamber -> HRX hot side (return path)
    draw_arrow(ax, (0.81, 0.34), (0.90, 0.34), style=THIN_ARROW)
    draw_arrow(ax, (0.90, 0.34), (0.90, 0.22), style=THIN_ARROW)
    draw_arrow(ax, (0.90, 0.22), (0.22, 0.22), label='Hot exhaust', style=THIN_ARROW)

    # HRX hot out -> expelled
    draw_arrow(ax, (0.08, 0.22), (0.00, 0.22), style=THIN_ARROW)
    ax.text(-0.02, 0.18, 'Cooled\nExh.', fontsize=6, color='#5D4037',
            fontweight='bold', ha='center')

    # Evaporator stream (ambient)
    draw_ambient(ax, (0.25, 0.10))
    draw_arrow(ax, (0.29, 0.10), (0.48, 0.10))
    draw_arrow(ax, (0.61, 0.10), (0.68, 0.10))
    ax.text(0.72, 0.10, 'Disc.', fontsize=7, color='#777', va='center')

    # Refrigerant loop
    ax.annotate('', xy=(0.50, 0.44), xytext=(0.53, 0.13),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))
    ax.annotate('', xy=(0.56, 0.37), xytext=(0.56, 0.44),
                arrowprops=dict(arrowstyle='->', lw=1, color='#666', ls='--'))

    # Solar annotation
    ax.annotate('GHI', xy=(0.35, 0.40), fontsize=8, color='#E65100',
                fontweight='bold', ha='center')
    ax.annotate('', xy=(0.35, 0.37), xytext=(0.35, 0.43),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#E65100'))

    # Triple benefit annotation
    ax.text(0.82, 0.47, 'HRX + Solar + HP\n= Max. savings',
            fontsize=7, ha='center', color='#1565C0',
            bbox=dict(boxstyle='round,pad=0.3', fc='#E3F2FD', ec='#64B5F6'))


# ======================================================================
# COMBINED FIGURE
# ======================================================================
def make_combined(fmt='png'):
    """Generate all 5 configs in a single tall figure."""
    fig, axes = plt.subplots(5, 1, figsize=(10, 28))
    fig.patch.set_facecolor('white')

    draw_config_A(axes[0])
    draw_config_B(axes[1])
    draw_config_C(axes[2])
    draw_config_D(axes[3])
    draw_config_E(axes[4])

    plt.tight_layout(pad=2.0)
    out = OUT_DIR / f"SAHPD_configurations_combined.{fmt}"
    fig.savefig(str(out), dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Combined: {out}")
    return out


def make_individual(fmt='png'):
    """Generate each config as a separate figure."""
    configs = [
        ('Config_A_HP_only', draw_config_A),
        ('Config_B_Solar_HP_series', draw_config_B),
        ('Config_C_Solar_evaporator', draw_config_C),
        ('Config_D_HRX_HP', draw_config_D),
        ('Config_E_HRX_Solar_HP', draw_config_E),
    ]
    paths = []
    for name, draw_fn in configs:
        fig, ax = plt.subplots(1, 1, figsize=(10, 5))
        fig.patch.set_facecolor('white')
        draw_fn(ax)
        plt.tight_layout(pad=1.0)
        out = OUT_DIR / f"{name}.{fmt}"
        fig.savefig(str(out), dpi=300, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        paths.append(out)
        print(f"  {name}: {out}")
    return paths


def main():
    parser = argparse.ArgumentParser(description="Generate SAHPD configuration diagrams")
    parser.add_argument('--format', '-f', default='png', choices=['png', 'pdf', 'svg'],
                        help='Output format (default: png)')
    parser.add_argument('--combined-only', action='store_true',
                        help='Only generate combined figure')
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fmt = args.format

    print("=" * 60)
    print("SAHPD Configuration Diagram Generator")
    print("=" * 60)

    if not args.combined_only:
        print("\nIndividual diagrams:")
        make_individual(fmt)

    print("\nCombined diagram:")
    make_combined(fmt)

    print(f"\nOutput directory: {OUT_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()
