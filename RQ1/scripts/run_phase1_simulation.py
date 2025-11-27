"""CLI entry point to run Phase-1 dryer simulation."""

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = SCRIPT_DIR / "src"

# Ensure the rq1 package is importable whether the script is executed from the
# repository root or another working directory.
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rq1.config import AmbientConfig, DryerConfig, KineticsConfig, SimulationConfig
from rq1.dryer_phase1 import run_phase1_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ambient-csv", type=Path, required=True, help="Path to standardized ambient CSV")
    parser.add_argument("--r", type=float, required=True, help="Recirculation ratio (0-1)")
    parser.add_argument("--Tset", type=float, required=True, help="Inlet temperature setpoint [°C]")
    parser.add_argument("--m_da", type=float, required=True, help="Dry air mass flow rate [kg/s]")
    parser.add_argument("--X0", type=float, required=True, help="Initial moisture content (dry basis)")
    parser.add_argument("--Xeq", type=float, required=True, help="Equilibrium moisture content (dry basis)")
    parser.add_argument("--m_p_dry", type=float, required=True, help="Dry mass of product [kg]")
    parser.add_argument("--dt_s", type=float, required=True, help="Time step [s]")
    parser.add_argument(
        "--max-steps", type=int, default=None, help="Optional limit on number of ambient steps to use"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("RQ1/data/phase1_runs/phase1_output.csv"),
        help="Path to write simulation results CSV",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ambient_cfg = AmbientConfig(
        csv_path=args.ambient_csv,
        start_index=0,
        max_steps=args.max_steps,
    )

    dryer_cfg = DryerConfig(
        m_da_kg_per_s=args.m_da,
        r_recirc=args.r,
        T_set_C=args.Tset,
        X0_db=args.X0,
        X_eq_db=args.Xeq,
        m_p_dry_kg=args.m_p_dry,
        dt_s=args.dt_s,
    )

    kinetics_cfg = KineticsConfig(use_simple_K=True, use_knb_table=False)

    sim_cfg = SimulationConfig(
        ambient=ambient_cfg,
        dryer=dryer_cfg,
        kinetics=kinetics_cfg,
    )

    result = run_phase1_simulation(sim_cfg)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.df.to_csv(args.output, index=False)

    summary = {
        "SEC_kWh_per_kg": result.df.get("SEC_kWh_per_kg", pd.Series([None])).iloc[-1],
        "total_time_s": result.df["time_s"].iloc[-1] if not result.df.empty else None,
        "final_MR": result.df["MR"].iloc[-1] if not result.df.empty else None,
    }
    print("Simulation complete.")
    print(summary)


if __name__ == "__main__":
    main()
