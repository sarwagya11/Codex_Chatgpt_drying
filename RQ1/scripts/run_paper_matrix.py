"""Paper simulation matrix driver — 276 M1 sims for §5 Results.

Three blocks:
  1) Annual baseline (11 configs x 4 sites x A_c=10)                 -> 44 sims
  2) Seasonal      (11 configs x 4 sites x 4 seasons x A_c=10)       -> 176 sims
  3) Solar sweep   (E1, E2 x 4 sites x A_c in {2,4,6,8,10,12,15})    -> 56 sims

D/E configs use vpd_bypass_thresh = 0.0 (no exhaust bypass; paper-1 framing).
All runs r=0, T_set=45 C, eta_mech=0.90.

Outputs land under outputs/config_X/<location>/[<season>/]<file>.csv
Progress log: outputs/paper_matrix_progress.log
Final summary: outputs/paper_matrix_summary.csv
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from run_solar_hp_configs import run_single_simulation  # noqa: E402

SITES = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
CONFIGS_ALL = ["0", "A", "B1", "B2", "C1", "D1", "D2", "D3", "E1", "E2", "E3"]
SEASONS = ["autumn_oct_nov", "winter_dec_jan", "spring_mar_apr", "summer_may_jun"]
SOLAR_AREAS = [2, 4, 6, 8, 10, 12, 15]

OUTPUT_DIR = "outputs"
MAX_HOURS = 72.0
VPD_THRESH_DE = 0.0
PROGRESS_LOG = PROJECT_ROOT / OUTPUT_DIR / "paper_matrix_progress.log"
SUMMARY_CSV = PROJECT_ROOT / OUTPUT_DIR / "paper_matrix_summary.csv"


def make_args(weather_file: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        eps_hrx=0.70,
        vpd_threshold=VPD_THRESH_DE,
        cond_threshold=0.0,
        T_set_C=45.0,
        max_hours=MAX_HOURS,
        output_dir=OUTPUT_DIR,
        n_sections=1,
        flow_reversal=0.0,
        weather_file=weather_file,
    )


def get_solar_area_for(config: str, requested: float) -> float:
    if config in ("0", "A", "D1", "D2", "D3"):
        return 0.0
    return requested


def log(msg: str) -> None:
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def run_one(config: str, location: str, solar_area: float, weather_file: str | None,
            tag: str, idx: int, total: int) -> dict:
    args = make_args(weather_file=weather_file)
    t0 = time.time()
    log(f"[{idx}/{total}] {tag} config={config} site={location} A_c={solar_area} weather={weather_file or 'annual'}")
    try:
        result = run_single_simulation(config, location, solar_area, args, r_recirc=0.0)
        elapsed = time.time() - t0
        row = {
            "block": tag,
            "config": config,
            "location": location,
            "season": Path(weather_file).stem.replace(f"{location}_", "") if weather_file else "annual",
            "solar_area_m2": solar_area,
            "success": True,
            "converged": result.converged,
            "elapsed_s": elapsed,
        }
        if not result.df.empty:
            last = result.df.iloc[-1]
            row.update({
                "drying_time_h": float(last["time_h"]),
                "W_comp_kWh": float(last.get("W_comp_cum_kWh", 0.0)),
                "W_fan_kWh": float(last.get("W_fan_cum_kWh", 0.0)),
                "W_elec_kWh": float(last.get("W_elec_cum_kWh", 0.0)) if "W_elec_cum_kWh" in result.df.columns else 0.0,
                "Q_solar_kWh": float(last.get("Q_solar_cum_kWh", 0.0)),
                "m_water_kg": float(last["m_w_cum_kg"]),
                "SEC_kWh_per_kg": float(result.df["SEC_elec_kWh_per_kg"].dropna().iloc[-1]) if "SEC_elec_kWh_per_kg" in result.df.columns and not result.df["SEC_elec_kWh_per_kg"].dropna().empty else float("nan"),
            })
        return row
    except Exception as e:
        elapsed = time.time() - t0
        log(f"  ERROR: {e}")
        traceback.print_exc()
        return {
            "block": tag, "config": config, "location": location,
            "season": Path(weather_file).stem.replace(f"{location}_", "") if weather_file else "annual",
            "solar_area_m2": solar_area,
            "success": False, "converged": False, "elapsed_s": elapsed,
            "error": str(e),
        }


def build_plan() -> list[tuple[str, str, str, float, str | None]]:
    """Return list of (tag, config, location, solar_area, weather_file)."""
    plan: list[tuple[str, str, str, float, str | None]] = []

    # Block 1: annual baseline
    for cfg in CONFIGS_ALL:
        for site in SITES:
            sa = get_solar_area_for(cfg, 10.0)
            plan.append(("annual", cfg, site, sa, None))

    # Block 2: seasonal
    for season in SEASONS:
        for cfg in CONFIGS_ALL:
            for site in SITES:
                sa = get_solar_area_for(cfg, 10.0)
                wf = f"data/ambient/seasonal/{site}_{season}.csv"
                plan.append(("seasonal", cfg, site, sa, wf))

    # Block 3: solar sweep (E1, E2 only, annual)
    for cfg in ("E1", "E2"):
        for site in SITES:
            for ac in SOLAR_AREAS:
                plan.append(("solar_sweep", cfg, site, float(ac), None))

    return plan


def main() -> None:
    plan = build_plan()
    total = len(plan)
    log(f"=== Paper matrix start: {total} sims ===")
    PROGRESS_LOG.write_text("")  # reset
    log(f"=== Paper matrix start: {total} sims ===")

    rows: list[dict] = []
    t_start = time.time()
    for i, (tag, cfg, site, sa, wf) in enumerate(plan, start=1):
        row = run_one(cfg, site, sa, wf, tag, i, total)
        rows.append(row)
        # Incremental save (so we can inspect mid-run)
        pd.DataFrame(rows).to_csv(SUMMARY_CSV, index=False)

    log(f"=== Paper matrix done: {total} sims in {(time.time()-t_start)/60:.1f} min ===")
    log(f"Summary: {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
