"""Quarterly K-batch sweep runner for the new 4-site climate-zone matrix.

For each (config, site, quarter, batch_idx) we:
  - Build the simulation config via the standard factory
  - Override cfg.ambient.start_index from outputs/quarterly/batch_starts.csv
  - Cap cfg.ambient.max_steps (default 168 h = 7 d of weather, more than
    enough for any single drying batch)
  - Run the sim, save the per-batch CSV
  - Append a summary row to outputs/quarterly/sweep_summary.csv

Run examples:
    # smoke test: 1 site, 1 quarter, 2 batches, 2 configs
    python scripts/run_quarterly_sweep.py --sites kathmandu \
        --quarters Q1 --batches 0 1 --configs A E2

    # full quarterly matrix for the 10 paper configs
    python scripts/run_quarterly_sweep.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import (  # noqa: E402
    LOCATION_ELEVATIONS_M,
    make_config_0_electric,
    make_config_A_HP_only,
    make_config_B1_open,
    make_config_B2_open,
    make_config_B1_closed,
    make_config_B2_closed,
    make_config_C1_solar_on_evap_source,
    make_config_D_HRX,
    make_config_E_HRX_solar,
)
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation  # noqa: E402

AMBIENT_DIR = PROJECT_ROOT / "data" / "ambient"
QUARTERLY_DIR = PROJECT_ROOT / "outputs" / "quarterly"
BATCH_STARTS_CSV = QUARTERLY_DIR / "batch_starts.csv"

DEFAULT_CONFIGS = ["A", "B1_open", "B2_open", "B1_closed", "B2_closed", "C1",
                   "D1", "D2", "E1", "E2", "E3"]
DEFAULT_SITES = ["biratnagar", "kathmandu", "jomsom", "namche"]
DEFAULT_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
DEFAULT_BATCHES: list[int] | None = None  # None -> auto-detect from batch-starts CSV

# Per-config recirculation sweep. Configs not listed run at r=0 (or N/A) once.
# Override globally via --recirc-values.
RECIRC_VALUES_BY_CONFIG: dict[str, list[float]] = {
    "A":         [0.0, 0.3, 0.5, 0.7, 0.8, 0.9],
    "B1_closed": [0.3, 0.5, 0.7, 0.8, 0.9],
    "B2_closed": [0.3, 0.5, 0.7, 0.8, 0.9],
    "C1":        [0.0, 0.3, 0.5, 0.7, 0.8, 0.9],
}

# Per-config solar-area sweep. Solar configs not listed use --solar-area (single).
# Override globally via --solar-areas.
AREA_SWEEP_BY_CONFIG: dict[str, list[float]] = {
    "E2": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0],
}

SOLAR_CONFIGS = {"B1_open", "B2_open", "B1_closed", "B2_closed",
                 "C1", "E1", "E2", "E3"}
R_ACCEPTING_CONFIGS = set(RECIRC_VALUES_BY_CONFIG.keys())


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--configs", nargs="+", default=DEFAULT_CONFIGS,
                   help="Configs to run (default: 10 paper configs)")
    p.add_argument("--sites", nargs="+", default=DEFAULT_SITES,
                   help="Sites to run (default: 4 climate-zone sites)")
    p.add_argument("--quarters", nargs="+", default=DEFAULT_QUARTERS,
                   help="Quarters to run (Q1 Q2 Q3 Q4)")
    p.add_argument("--batches", nargs="+", type=int, default=DEFAULT_BATCHES,
                   help="Batch indices to run (default: auto-detect all from batch-starts CSV).")
    p.add_argument("--skip-last-days-per-year", type=int, default=0,
                   help="Drop the last N daily batches from the YEAR (last N rows of Q4 per site). "
                        "Applies only to dense daily CSVs (default: 0).")
    p.add_argument("--solar-area", type=float, default=10.0,
                   help="Solar area [m^2] baseline for solar configs not in AREA_SWEEP_BY_CONFIG.")
    p.add_argument("--solar-areas", nargs="+", type=float, default=None,
                   help="Global override: sweep these areas [m^2] for ALL solar configs. "
                        "If not given, uses AREA_SWEEP_BY_CONFIG (E2-only sweep) + --solar-area for others.")
    p.add_argument("--recirc-values", nargs="+", type=float, default=None,
                   help="Global override: sweep these r values for r-accepting configs (A, B*_closed, C1). "
                        "If not given, uses RECIRC_VALUES_BY_CONFIG. "
                        "Configs not in R_ACCEPTING_CONFIGS always run at r=0.")
    p.add_argument("--T-set", type=float, default=45.0)
    p.add_argument("--eps-hrx", type=float, default=0.70)
    p.add_argument("--vpd-threshold", type=float, default=0.0)
    p.add_argument("--max-batch-hours", type=float, default=168.0,
                   help="Weather rows fed per batch (default 168 = 7 d)")
    p.add_argument("--max-sim-hours", type=float, default=72.0,
                   help="Hard sim cap (default 72 h)")
    p.add_argument("--batch-starts", type=Path, default=BATCH_STARTS_CSV)
    p.add_argument("--r-star-csv", type=Path, default=None,
                   help="CSV with columns config,site,r_star. When given, "
                        "r-accepting configs run at r=r_star[(config,site)] only. "
                        "Overrides RECIRC_VALUES_BY_CONFIG and --recirc-values.")
    p.add_argument("--output-dir", type=Path, default=QUARTERLY_DIR)
    p.add_argument("--summary-name", type=str, default="sweep_summary.csv",
                   help="Filename for the rolling summary (under --output-dir)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print planned matrix and exit without simulating")
    return p.parse_args()


def load_r_star_table(path: Path | None) -> dict[tuple[str, str], float] | None:
    if path is None:
        return None
    if not path.exists():
        sys.exit(f"--r-star-csv not found: {path}")
    df = pd.read_csv(path)
    needed = {"config", "site", "r_star"}
    missing = needed - set(df.columns)
    if missing:
        sys.exit(f"r-star CSV missing columns: {missing}")
    table = {(row["config"], row["site"]): float(row["r_star"])
             for _, row in df.iterrows()}
    print(f"[r-star] loaded {len(table)} (config, site) entries from {path.name}")
    return table


def get_phase2_path() -> Path | None:
    for p in [PROJECT_ROOT / "outputs" / "phase2c_for_chamber.csv"]:
        if p.exists():
            return p
    return None


def build_cfg(config_letter: str, site: str, r_val: float, area_m2: float, args):
    """Factory-build a SimulationConfig for the given (config, r, area, site)."""
    weather_path = AMBIENT_DIR / f"{site}_pvgis_standard_poa45.csv"
    if not weather_path.exists():
        legacy = AMBIENT_DIR / f"{site}_pvgis_standard.csv"
        if not legacy.exists():
            raise FileNotFoundError(weather_path)
        print(f"[weather] {weather_path.name} missing; falling back to legacy {legacy.name} (GHI)")
        weather_path = legacy
    elev = LOCATION_ELEVATIONS_M.get(site, 0)
    phase2_path = get_phase2_path()
    phase2_root = phase2_path.parent if phase2_path else None
    common = dict(
        ambient_csv=weather_path,
        T_set_C=args.T_set,
        elevation_m=elev,
        phase2_root=phase2_root,
        display_geometry=False,
    )

    if config_letter == "0":
        cfg = make_config_0_electric(**common)
    elif config_letter == "A":
        cfg = make_config_A_HP_only(r_recirc=r_val, **common)
    elif config_letter == "B1_open":
        cfg = make_config_B1_open(solar_area_m2=area_m2, **common)
    elif config_letter == "B2_open":
        cfg = make_config_B2_open(solar_area_m2=area_m2, **common)
    elif config_letter == "B1_closed":
        cfg = make_config_B1_closed(
            solar_area_m2=area_m2, r_recirc=r_val, **common)
    elif config_letter == "B2_closed":
        cfg = make_config_B2_closed(
            solar_area_m2=area_m2, r_recirc=r_val, **common)
    elif config_letter == "C1":
        cfg = make_config_C1_solar_on_evap_source(
            solar_area_m2=area_m2, r_recirc=r_val, **common)
    elif config_letter in ("D1", "D2", "D3"):
        cfg = make_config_D_HRX(
            d_variant=config_letter,
            eps_HRX=args.eps_hrx,
            vpd_bypass_thresh=args.vpd_threshold,
            **common,
        )
    elif config_letter in ("E1", "E2", "E3"):
        cfg = make_config_E_HRX_solar(
            solar_area_m2=area_m2,
            e_variant=config_letter,
            eps_HRX=args.eps_hrx,
            vpd_bypass_thresh=args.vpd_threshold,
            **common,
        )
    else:
        raise ValueError(f"Unknown config: {config_letter}")

    cfg.max_simulation_time_s = args.max_sim_hours * 3600.0
    return cfg


def r_values_for(
    cfg_letter: str,
    site: str,
    args,
    r_star_table: dict[tuple[str, str], float] | None = None,
) -> list[float]:
    # Highest priority: per-(config, site) r* lookup (stage-2 production)
    if r_star_table is not None and cfg_letter in R_ACCEPTING_CONFIGS:
        key = (cfg_letter, site)
        if key in r_star_table:
            return [r_star_table[key]]
        print(f"[r-star] WARN no entry for {key}; falling back to r=0")
        return [0.0]
    if r_star_table is not None:
        # r-star CSV given but this config doesn't accept r
        return [0.0]
    if args.recirc_values is not None:
        # Global override; but configs that don't accept r still run at r=0
        return args.recirc_values if cfg_letter in R_ACCEPTING_CONFIGS else [0.0]
    return RECIRC_VALUES_BY_CONFIG.get(cfg_letter, [0.0])


def areas_for(cfg_letter: str, args) -> list[float]:
    if cfg_letter not in SOLAR_CONFIGS:
        return [args.solar_area]  # ignored downstream
    if args.solar_areas is not None:
        return list(args.solar_areas)
    return AREA_SWEEP_BY_CONFIG.get(cfg_letter, [args.solar_area])


def extract_metrics(result, start_idx: int) -> dict:
    df = result.df
    out = dict(
        success=True,
        converged=bool(result.converged),
        message=str(result.final_message),
        start_index=int(start_idx),
        drying_time_h=None,
        W_comp_kWh=None,
        W_fan_kWh=None,
        W_elec_kWh=None,
        Q_solar_kWh=None,
        m_water_kg=None,
        SEC_elec_kWh_per_kg=None,
    )
    if df.empty:
        out["success"] = False
        return out
    last = df.iloc[-1]
    out["drying_time_h"] = float(last["time_h"])
    out["W_comp_kWh"] = float(last["W_comp_cum_kWh"])
    out["W_fan_kWh"] = float(last["W_fan_cum_kWh"])
    out["m_water_kg"] = float(last["m_w_cum_kg"])
    if "W_elec_cum_kWh" in df.columns:
        out["W_elec_kWh"] = float(last["W_elec_cum_kWh"])
    if "Q_solar_cum_kWh" in df.columns:
        out["Q_solar_kWh"] = float(last["Q_solar_cum_kWh"])
    if "SEC_elec_kWh_per_kg" in df.columns:
        sec = df["SEC_elec_kWh_per_kg"].dropna()
        if not sec.empty:
            out["SEC_elec_kWh_per_kg"] = float(sec.iloc[-1])
    return out


def output_path_for(cfg_letter: str, site: str, quarter: str,
                    batch_idx: int, r_val: float, area_m2: float, args) -> Path:
    folder = args.output_dir / f"config_{cfg_letter}" / site / quarter
    folder.mkdir(parents=True, exist_ok=True)
    pieces = [f"batch{batch_idx}"]
    if cfg_letter in R_ACCEPTING_CONFIGS:
        pieces.append(f"r{r_val:.1f}")
    if cfg_letter in SOLAR_CONFIGS:
        pieces.append(f"Ac{area_m2:.0f}m2")
    if cfg_letter in ("D1", "D2", "D3", "E1", "E2", "E3"):
        pieces.append(f"hrx{args.eps_hrx:.2f}")
    if cfg_letter == "0":
        pieces.append("electric")
    return folder / ("_".join(pieces) + ".csv")


def main():
    args = parse_args()

    if not args.batch_starts.exists():
        sys.exit(f"Missing batch-starts CSV: {args.batch_starts}\n"
                 "Run scripts/quarterly_batch_starts.py first.")
    starts_df = pd.read_csv(args.batch_starts)

    # Optional: skip the last N daily batches of the year (last N rows of Q4 per site)
    if args.skip_last_days_per_year > 0:
        keep_rows: list[int] = []
        n_skip = args.skip_last_days_per_year
        for site, sub in starts_df.groupby("site", sort=False):
            sub_sorted = sub.sort_values(["quarter", "batch_idx"])
            q4 = sub_sorted[sub_sorted["quarter"] == "Q4"]
            non_q4 = sub_sorted[sub_sorted["quarter"] != "Q4"]
            q4_kept = q4.iloc[:-n_skip] if n_skip < len(q4) else q4.iloc[:0]
            keep_rows.extend(non_q4.index.tolist())
            keep_rows.extend(q4_kept.index.tolist())
        starts_df = starts_df.loc[sorted(keep_rows)].reset_index(drop=True)
        print(f"[skip-last] dropped last {n_skip} Q4 day(s) per site; "
              f"{len(starts_df)} batch rows remain")

    starts_lookup = {
        (r["site"], r["quarter"], int(r["batch_idx"])): r
        for _, r in starts_df.iterrows()
    }
    # Auto-detect available batch indices per (site, quarter) when --batches omitted
    batches_by_sq: dict[tuple[str, str], list[int]] = {}
    for (s, q, b), _ in starts_lookup.items():
        batches_by_sq.setdefault((s, q), []).append(b)
    for k in batches_by_sq:
        batches_by_sq[k] = sorted(batches_by_sq[k])

    r_star_table = load_r_star_table(args.r_star_csv)

    runs: list[tuple[str, float, str, str, int, float]] = []
    for cfg_letter in args.configs:
        areas_for_cfg = areas_for(cfg_letter, args)
        for site in args.sites:
            r_vals = r_values_for(cfg_letter, site, args, r_star_table)
            for r_val in r_vals:
                for area in areas_for_cfg:
                    for quarter in args.quarters:
                        batches_iter = (args.batches if args.batches is not None
                                        else batches_by_sq.get((site, quarter), []))
                        for batch_idx in batches_iter:
                            key = (site, quarter, batch_idx)
                            if key not in starts_lookup:
                                continue
                            runs.append((cfg_letter, r_val, site, quarter, batch_idx, area))

    total = len(runs)
    print(f"\nSweep matrix: {total} simulations")
    print(f"  configs={args.configs}\n  sites={args.sites}\n"
          f"  quarters={args.quarters}\n"
          f"  batches={'auto' if args.batches is None else args.batches}\n"
          f"  recirc per-config: {RECIRC_VALUES_BY_CONFIG}"
          f"{' (overridden by --recirc-values=' + str(args.recirc_values) + ')' if args.recirc_values else ''}\n"
          f"  areas per-config: AREA_SWEEP_BY_CONFIG={AREA_SWEEP_BY_CONFIG}, baseline={args.solar_area} m2"
          f"{' (overridden by --solar-areas=' + str(args.solar_areas) + ')' if args.solar_areas else ''}\n"
          f"  T_set={args.T_set} C, eps_HRX={args.eps_hrx}, vpd_thresh={args.vpd_threshold}\n"
          f"  max_batch_hours={args.max_batch_hours}, max_sim_hours={args.max_sim_hours}")
    if args.dry_run:
        print("[DRY RUN] exiting before simulation.")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict] = []
    start_wall = datetime.now()

    for idx, (cfg_letter, r_val, site, quarter, batch_idx, area) in enumerate(runs, 1):
        bs = starts_lookup[(site, quarter, batch_idx)]
        start_row = int(bs["start_row_index"])
        start_dt = bs["start_datetime_NPT"]
        print(f"\n[{idx}/{total}] config={cfg_letter} r={r_val} site={site} "
              f"{quarter} batch{batch_idx}  A={area} m2  start_row={start_row} "
              f"({start_dt})")

        row = dict(
            config=cfg_letter,
            r_recirc=r_val,
            site=site,
            quarter=quarter,
            batch_idx=batch_idx,
            start_row_index=start_row,
            start_datetime_NPT=start_dt,
            solar_area_m2=(area if cfg_letter in SOLAR_CONFIGS else 0.0),
            T_set_C=args.T_set,
            eps_HRX=(args.eps_hrx if cfg_letter in (
                "D1", "D2", "D3", "E1", "E2", "E3"
            ) else None),
            vpd_threshold=args.vpd_threshold,
        )

        try:
            cfg = build_cfg(cfg_letter, site, r_val, area, args)
            cfg.ambient.start_index = start_row
            cfg.ambient.max_steps = int(args.max_batch_hours)
            result = run_solar_hp_dryer_simulation(cfg)
            metrics = extract_metrics(result, start_row)
            row.update(metrics)
            out_csv = output_path_for(cfg_letter, site, quarter, batch_idx, r_val, area, args)
            result.df.to_csv(out_csv, index=False)
            try:
                shown = out_csv.resolve().relative_to(PROJECT_ROOT)
            except ValueError:
                shown = out_csv
            print(f"    OK SEC={metrics['SEC_elec_kWh_per_kg']}  "
                  f"t={metrics['drying_time_h']}h  "
                  f"m_w={metrics['m_water_kg']} kg  -> {shown}")
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            row.update(dict(success=False, converged=False, message=str(exc)))
        summary_rows.append(row)

        # Periodically flush summary so a crash does not lose progress
        if idx % 20 == 0 or idx == total:
            pd.DataFrame(summary_rows).to_csv(
                args.output_dir / args.summary_name, index=False)

    wall_min = (datetime.now() - start_wall).total_seconds() / 60.0
    df_out = pd.DataFrame(summary_rows)
    df_out.to_csv(args.output_dir / args.summary_name, index=False)
    print(f"\nWall time: {wall_min:.1f} min")
    print(f"Summary: {args.output_dir / args.summary_name}")
    print(f"Successful: {df_out['success'].sum()}/{len(df_out)}")
    converged = df_out.get("converged", pd.Series([False]))
    print(f"Converged: {int(converged.sum())}/{len(df_out)}")


if __name__ == "__main__":
    main()
