"""Run a recirculation sweep for the Phase-1 dryer model and generate plots.

Example:

python RQ1/scripts/run_phase1_recirc_sweep.py ^
    --ambient-csv RQ1/data/ambient/weather_amb_ktm.csv ^
    --r-list 0,0.3,0.5,0.7,0.9 ^
    --Tset 50 ^
    --m_da 0.2 ^
    --X0 2.5 ^
    --Xeq 0.05 ^
    --m_p_dry 20 ^
    --dt_s 60 ^
    --max-steps 480 ^
    --n-trays 4 ^
    --output-dir RQ1/data/phase1_runs_recirc/ktm_summer
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

SCRIPT_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = SCRIPT_DIR / "src"

# Ensure the rq1 package is importable whether the script is executed from the
# repository root or another working directory.
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rq1.config import AmbientConfig, DryerConfig, KineticsConfig, SimulationConfig
from rq1.dryer_phase1 import Phase1Result, run_phase1_simulation
from rq1.phase1_plots import (
    plot_energy_and_water,
    plot_air_trays_per_r,
    plot_humidity_and_MR,
    plot_MR_trays_per_r,
    plot_final_tray_profiles,
    plot_temperatures,
    summarize_SEC_vs_r,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the recirculation sweep."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ambient-csv", type=Path, required=True, help="Path to standardized ambient CSV")
    parser.add_argument("--r-list", type=str, required=True, help="Comma-separated list of recirculation ratios")
    parser.add_argument("--Tset", type=float, required=True, help="Inlet temperature setpoint [°C]")
    parser.add_argument("--m_da", type=float, default=0.0, help="Dry air mass flow rate [kg/s]")
    parser.add_argument("--X0", type=float, required=True, help="Initial moisture content (dry basis)")
    parser.add_argument("--Xeq", type=float, required=True, help="Equilibrium moisture content (dry basis)")
    parser.add_argument("--m_p_dry", type=float, required=True, help="Dry mass of product [kg]")
    parser.add_argument("--dt_s", type=float, required=True, help="Time step [s]")
    parser.add_argument("--n-trays", type=int, default=1, help="Number of trays/nodes in series")
    parser.add_argument("--max-steps", type=int, default=None, help="Optional limit on number of ambient steps to use")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("RQ1/data/phase1_runs_recirc"), help="Directory to write results"
    )
    parser.add_argument(
        "--kinetics-mode",
        choices=["first_order", "phase2_midilli"],
        default="phase2_midilli",
        help="Drying kinetics model to use.",
    )
    parser.add_argument("--phase2-models-root", type=Path, default=None)
    parser.add_argument("--T_ref", type=float, default=50.0)
    parser.add_argument("--RH_lo_ref", type=float, default=30.0)
    parser.add_argument("--RH_hi_ref", type=float, default=40.0)
    parser.add_argument("--v_ref", type=float, default=1.1)
    parser.add_argument("--thickness_ref", type=float, default=6.0)
    return parser.parse_args()


def parse_r_list(r_list_str: str) -> list[float]:
    """Convert a comma-separated string of recirculation ratios to a list of floats."""

    values = [item.strip() for item in r_list_str.split(",") if item.strip()]
    if not values:
        raise ValueError("--r-list must contain at least one recirculation ratio")
    try:
        return [float(val) for val in values]
    except ValueError as exc:
        raise ValueError("Could not parse --r-list; ensure it is comma-separated floats") from exc


def run_sweep(args: argparse.Namespace) -> Dict[float, Phase1Result]:
    """Execute Phase-1 simulations across the requested recirculation ratios."""

    r_list = parse_r_list(args.r_list)
    results_by_r: Dict[float, Phase1Result] = {}

    for r in r_list:
        ambient_cfg = AmbientConfig(
            csv_path=args.ambient_csv,
            start_index=0,
            max_steps=args.max_steps,
        )

        dryer_cfg = DryerConfig(
            m_da_kg_per_s=args.m_da,
            r_recirc=r,
            T_set_C=args.Tset,
            X0_db=args.X0,
            X_eq_db=args.Xeq,
            m_p_dry_kg=args.m_p_dry,
            dt_s=args.dt_s,
            n_trays=args.n_trays,
        )
        dryer_cfg.tray_depth_m = 0.05  # Sets air depth above product to 5 cm


        kinetics_cfg = KineticsConfig(
            mode=args.kinetics_mode,
            use_simple_K=True,
            use_knb_table=True,
            phase2_models_root=args.phase2_models_root,
            T_C_ref=args.T_ref,
            RH_lo_pct_ref=args.RH_lo_ref,
            RH_hi_pct_ref=args.RH_hi_ref,
            v_ms_ref=args.v_ref,
            thickness_mm_ref=args.thickness_ref,
        )
        kinetics_cfg.debug_keff = True
        sim_cfg = SimulationConfig(
            ambient=ambient_cfg,
            dryer=dryer_cfg,
            kinetics=kinetics_cfg,   
        )

        results_by_r[r] = run_phase1_simulation(sim_cfg)

    return results_by_r


def save_results(results_by_r: Dict[float, Phase1Result], output_dir: Path, n_trays: int) -> None:
    """Persist per-r simulation data and plots."""

    output_dir.mkdir(parents=True, exist_ok=True)

    for r, res in results_by_r.items():
        csv_path = output_dir / f"phase1_recirc_r{r:.2f}.csv"
        res.df.to_csv(csv_path, index=False)

    plot_temperatures(results_by_r, output_dir / "phase1_temps.png")
    plot_humidity_and_MR(results_by_r, output_dir / "phase1_RH_MR.png")
    plot_energy_and_water(results_by_r, output_dir / "phase1_energy_water.png", n_trays=n_trays)
    summarize_SEC_vs_r(results_by_r, output_dir / "phase1_SEC_vs_r.png")

    if results_by_r:
        any_df = next(iter(results_by_r.values())).df
        has_tray_cols = any(col.startswith("MR_tray") for col in any_df.columns)
        if has_tray_cols and n_trays > 0:
            plot_MR_trays_per_r(results_by_r, output_dir, n_trays)
            plot_air_trays_per_r(results_by_r, output_dir, n_trays)
            plot_final_tray_profiles(results_by_r, output_dir, n_trays)


def print_summary(results_by_r: Dict[float, Phase1Result]) -> None:
    """Print a concise summary to stdout."""

    for r, res in sorted(results_by_r.items()):
        df = res.df
        sec_series = df.get("SEC_kWh_per_kg") if "SEC_kWh_per_kg" in df else None
        sec_value = sec_series.dropna().iloc[-1] if sec_series is not None and not sec_series.dropna().empty else None
        total_time_s = df["time_s"].iloc[-1] if not df.empty else None
        final_MR = df["MR"].iloc[-1] if not df.empty else None
        print(f"r = {r:.2f}: SEC = {sec_value}, total_time_s = {total_time_s}, final_MR = {final_MR}")


def main() -> None:
    args = parse_args()
    results_by_r = run_sweep(args)
    save_results(results_by_r, args.output_dir, args.n_trays)
    print_summary(results_by_r)


if __name__ == "__main__":
    main()
