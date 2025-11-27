"""Convenience scenario builders for Phase-1 simulations."""

from pathlib import Path

from .config import AmbientConfig, DryerConfig, KineticsConfig, SimulationConfig


def make_default_kathmandu_summer_phase1() -> SimulationConfig:
    """Return a sample configuration for Kathmandu summer conditions."""

    ambient_cfg = AmbientConfig(
        csv_path=Path("RQ1/data/ambient/kathmandu_summer_ambient.csv"),
        start_index=0,
        max_steps=1440,
    )

    dryer_cfg = DryerConfig(
        m_da_kg_per_s=0.2,
        r_recirc=0.5,
        T_set_C=50.0,
        X0_db=2.5,
        X_eq_db=0.05,
        m_p_dry_kg=10.0,
        dt_s=60.0,
    )

    kinetics_cfg = KineticsConfig(use_simple_K=True, use_knb_table=False)

    return SimulationConfig(
        ambient=ambient_cfg,
        dryer=dryer_cfg,
        kinetics=kinetics_cfg,
    )
