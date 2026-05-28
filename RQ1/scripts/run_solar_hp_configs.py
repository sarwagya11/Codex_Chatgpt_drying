"""Runner script for solar-HP dryer simulations.

Usage:
    python scripts/run_solar_hp_configs.py --config A --location kathmandu
    python scripts/run_solar_hp_configs.py --config B --location kathmandu --solar-area 10
    python scripts/run_solar_hp_configs.py --full
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rq1.config_solar_hp import (
    DryerConfiguration,
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
from rq1.dryer_solar_hp import run_solar_hp_dryer_simulation


def parse_args():
    parser = argparse.ArgumentParser(description="Run solar-HP dryer simulations")
    
    parser.add_argument("--test", action="store_true", help="Quick test (Config A, Kathmandu)")
    parser.add_argument("--full", action="store_true", help="Full sweep (all configs x locations x solar areas)")
    
    parser.add_argument("--config", type=str, choices=["0", "A", "B1_open", "B2_open", "B1_closed", "B2_closed", "C1", "D1", "D2", "D3", "E1", "E2", "E3"], help="Single config")
    parser.add_argument("--location", type=str, help="Location name (e.g., kathmandu)")
    parser.add_argument("--solar-area", type=float, help="Solar collector area [m2]")

    parser.add_argument("--configs", nargs="+", choices=["0", "A", "B1_open", "B2_open", "B1_closed", "B2_closed", "C1", "D1", "D2", "D3", "E1", "E2", "E3"], help="Multiple configs")
    parser.add_argument("--locations", nargs="+", help="Multiple locations")
    parser.add_argument("--solar-areas", nargs="+", type=float, help="Multiple solar areas")
    
    parser.add_argument("--recirc-values", nargs="+", type=float,
                        help="Recirculation ratios for Config A sweep (e.g. 0.0 0.2 0.4 0.6 0.8 1.0)")
    parser.add_argument("--n-sections", type=int, default=1,
                        help="Sections per tray for within-tray discretization (1,2,3,5)")
    parser.add_argument("--flow-reversal", type=float, default=0.0,
                        help="Flow reversal interval in minutes (0=disabled, e.g. 30)")
    parser.add_argument("--cond-threshold", type=float, default=0.0,
                        help="Cond-penalty threshold [0-1] for condenser-direct bypass mode "
                             "(0=disabled). When cond_penalty_frac < threshold, exhaust routes "
                             "directly to condenser (closed loop); switches back when "
                             "cond_penalty > 3x threshold. Typical value: 0.05 (5%%).")
    parser.add_argument("--eps-hrx", type=float, default=0.70,
                        help="HRX effectiveness for Config D (default: 0.70)")
    parser.add_argument("--vpd-threshold", "--vpd", dest="vpd_threshold",
                        type=float, default=0.0,
                        help="VPD exhaust bypass threshold for D/E configs [0-1] "
                             "(0=disabled). When VPD utilization < threshold, exhaust "
                             "routes directly to condenser. Typical value: 0.05 (5%%). "
                             "--vpd is a short alias.")
    parser.add_argument("--T-set", "--t-set", dest="T_set_C", type=float, default=45.0,
                        help="Chamber air target temperature [degC] (default 45). "
                             "Kinetics validated 40-50; 55 is +5 K extrapolation.")
    parser.add_argument("--max-hours", type=float, default=72.0, help="Max simulation time [hours]")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Output directory")
    parser.add_argument("--weather-file", type=str, default=None,
                        help="Override weather CSV path (e.g., data/ambient/seasonal/kathmandu_autumn_oct_nov.csv). "
                             "When set, --location is still required for elevation lookup and output naming.")

    return parser.parse_args()


def get_weather_path(location: str) -> Path:
    """Get weather file path for location."""
    possible_paths = [
        PROJECT_ROOT / "data" / "ambient" / f"{location}_pvgis_standard_poa45.csv",
        PROJECT_ROOT / "data" / "ambient" / f"{location}_pvgis_standard.csv",
        PROJECT_ROOT / "data" / "ambient" / f"{location}.csv",
        PROJECT_ROOT / "outputs" / f"{location}_pvgis_standard.csv",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError(f"Weather file for '{location}' not found. Tried: {possible_paths}")


def get_phase2_path() -> Path:
    """Get phase2c_for_chamber.csv path."""
    possible_paths = [
        PROJECT_ROOT / "outputs" / "phase2c_for_chamber.csv",
        PROJECT_ROOT / "data" / "phase2c_for_chamber.csv",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    print("[WARNING] phase2c_for_chamber.csv not found, using fallback kinetics")
    return None


def run_single_simulation(config_letter: str, location: str, solar_area_m2: float, args,
                          r_recirc: float = 0.0):
    """Run one simulation."""
    header = f"Running: Config {config_letter}, {location}"
    if config_letter in ("A", "B1_closed", "B2_closed", "C1") and r_recirc > 0:
        header += f", r_recirc={r_recirc:.2f}"
    if config_letter not in ("A", "D1", "D2", "D3"):
        header += f", A_solar={solar_area_m2}m2"
    if config_letter in ("E1", "E2", "E3"):
        header += f", eps_HRX={getattr(args, 'eps_hrx', 0.70) or 0.70:.2f}"
    print(f"\n{'='*70}")
    print(header)
    print(f"{'='*70}\n")

    # Weather file: explicit override or auto-resolve from location name
    weather_override = getattr(args, 'weather_file', None)
    if weather_override:
        weather_path = Path(weather_override)
        if not weather_path.is_absolute():
            weather_path = PROJECT_ROOT / weather_path
        if not weather_path.exists():
            raise FileNotFoundError(f"Weather file not found: {weather_path}")
    else:
        weather_path = get_weather_path(location)
    phase2_path = get_phase2_path()

    n_sections = getattr(args, 'n_sections', 1) or 1
    flow_reversal = getattr(args, 'flow_reversal', 0.0) or 0.0
    elevation_m = LOCATION_ELEVATIONS_M.get(location.lower(), 0)
    cond_thresh = getattr(args, 'cond_threshold', 0.0) or 0.0
    T_set_C = getattr(args, 'T_set_C', 45.0) or 45.0

    # Create config
    if config_letter == "0":
        cfg = make_config_0_electric(
            ambient_csv=weather_path,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal,
        )
    elif config_letter == "A":
        cfg = make_config_A_HP_only(
            ambient_csv=weather_path,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            r_recirc=r_recirc,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal,
            cond_penalty_thresh=cond_thresh,
        )
    elif config_letter == "B1_open":
        cfg = make_config_B1_open(
            ambient_csv=weather_path,
            solar_area_m2=solar_area_m2,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal,
        )
    elif config_letter == "B2_open":
        cfg = make_config_B2_open(
            ambient_csv=weather_path,
            solar_area_m2=solar_area_m2,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal,
        )
    elif config_letter == "B1_closed":
        cfg = make_config_B1_closed(
            ambient_csv=weather_path,
            solar_area_m2=solar_area_m2,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            r_recirc=r_recirc,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal,
        )
    elif config_letter == "B2_closed":
        cfg = make_config_B2_closed(
            ambient_csv=weather_path,
            solar_area_m2=solar_area_m2,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            r_recirc=r_recirc,
            n_sections=n_sections,
            flow_reversal_interval_min=flow_reversal,
        )
    elif config_letter == "C1":
        cfg = make_config_C1_solar_on_evap_source(
            ambient_csv=weather_path,
            solar_area_m2=solar_area_m2,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            n_sections=n_sections,
            r_recirc=r_recirc,
            flow_reversal_interval_min=flow_reversal,
            cond_penalty_thresh=cond_thresh,
        )
    elif config_letter in ("D1", "D2", "D3"):
        eps_hrx = getattr(args, 'eps_hrx', 0.70) or 0.70
        vpd_thresh = getattr(args, 'vpd_threshold', 0.0) or 0.0
        cfg = make_config_D_HRX(
            ambient_csv=weather_path,
            d_variant=config_letter,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            eps_HRX=eps_hrx,
            vpd_bypass_thresh=vpd_thresh,
        )
    elif config_letter in ("E1", "E2", "E3"):
        eps_hrx = getattr(args, 'eps_hrx', 0.70) or 0.70
        vpd_thresh = getattr(args, 'vpd_threshold', 0.0) or 0.0
        cfg = make_config_E_HRX_solar(
            ambient_csv=weather_path,
            solar_area_m2=solar_area_m2,
            e_variant=config_letter,
            T_set_C=T_set_C,
            elevation_m=elevation_m,
            phase2_root=phase2_path.parent if phase2_path else None,
            eps_HRX=eps_hrx,
            vpd_bypass_thresh=vpd_thresh,
        )

    cfg.max_simulation_time_s = args.max_hours * 3600.0
    
    # Run simulation
    result = run_solar_hp_dryer_simulation(cfg)
    
    # Save output — add season subdirectory when using a seasonal weather file
    season_tag = ""
    if weather_override:
        stem = Path(weather_override).stem          # e.g. kathmandu_autumn_oct_nov
        # Strip the location prefix to get the season tag
        loc_lower = location.lower()
        if stem.lower().startswith(loc_lower + "_"):
            season_tag = stem[len(loc_lower) + 1:]  # e.g. autumn_oct_nov
        else:
            season_tag = stem                        # fallback: use full stem
    if season_tag:
        output_dir = PROJECT_ROOT / args.output_dir / f"config_{config_letter}" / location / season_tag
    else:
        output_dir = PROJECT_ROOT / args.output_dir / f"config_{config_letter}" / location
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build descriptive output filename
    suffix_parts = []
    if r_recirc > 0:
        suffix_parts.append(f"r{r_recirc:.1f}")
    if flow_reversal > 0:
        suffix_parts.append(f"fr{flow_reversal:.0f}")
    if n_sections > 1:
        suffix_parts.append(f"s{n_sections}")
    suffix = "_" + "_".join(suffix_parts) if suffix_parts else ""
    vpd_tag = "_vpd" if cond_thresh > 0 else ""

    vpd_thresh_val = getattr(args, 'vpd_threshold', 0.0) or 0.0
    T_tag = f"_T{T_set_C:.0f}" if abs(T_set_C - 45.0) > 1e-6 else ""

    if config_letter == "0":
        output_file = output_dir / f"electric_baseline{T_tag}{suffix}.csv"
    elif config_letter == "A":
        output_file = output_dir / f"baseline_r{r_recirc:.1f}{T_tag}{vpd_tag}{suffix.replace(f'_r{r_recirc:.1f}', '')}.csv"
    elif config_letter in ("D1", "D2", "D3"):
        eps_hrx = getattr(args, 'eps_hrx', 0.70) or 0.70
        vpd_tag_de = f"_vpd{vpd_thresh_val:.2f}" if vpd_thresh_val > 0 else ""
        output_file = output_dir / f"hrx_eps{eps_hrx:.2f}{T_tag}{vpd_tag_de}.csv"
    elif config_letter in ("E1", "E2", "E3"):
        eps_hrx = getattr(args, 'eps_hrx', 0.70) or 0.70
        vpd_tag_de = f"_vpd{vpd_thresh_val:.2f}" if vpd_thresh_val > 0 else ""
        output_file = output_dir / f"Ac_{solar_area_m2:.0f}m2_hrx{eps_hrx:.2f}{T_tag}{vpd_tag_de}.csv"
    else:
        output_file = output_dir / f"Ac_{solar_area_m2:.0f}m2{T_tag}{vpd_tag}{suffix}.csv"
    
    result.df.to_csv(output_file, index=False)
    
    print(f"\n{result.final_message}")
    print(f"Saved: {output_file}")
    
    # Print summary
    if not result.df.empty:
        final_row = result.df.iloc[-1]
        print(f"  Water removed: {final_row['m_w_cum_kg']:.2f} kg")
        print(f"  Time: {final_row['time_h']:.1f} hours")
        print(f"  W_comp: {final_row['W_comp_cum_kWh']:.2f} kWh")
        print(f"  W_fan:  {final_row['W_fan_cum_kWh']:.2f} kWh")
        if "W_elec_cum_kWh" in result.df.columns and final_row["W_elec_cum_kWh"] > 0:
            print(f"  W_elec: {final_row['W_elec_cum_kWh']:.2f} kWh")
        if final_row["Q_solar_cum_kWh"] > 0:
            print(f"  Q_solar: {final_row['Q_solar_cum_kWh']:.2f} kWh")
        if "SEC_elec_kWh_per_kg" in result.df.columns:
            sec = result.df["SEC_elec_kWh_per_kg"].dropna()
            if not sec.empty:
                print(f"  SEC: {sec.iloc[-1]:.3f} kWh/kg")
    
    return result


def calculate_total_runs(configs, locations, solar_areas, recirc_values):
    """Calculate total runs, accounting for Config A/B/C1/C2 recirc sweep."""
    total = 0
    for config in configs:
        if config == "A":
            total += len(locations) * len(recirc_values)
        elif config in ("D1", "D2", "D3"):
            total += len(locations)  # single run per location
        elif config in ("E1", "E2", "E3"):
            total += len(locations) * len(solar_areas)  # sweep solar areas
        elif config in ("B1_open", "B2_open"):
            total += len(locations) * len(solar_areas)  # open loop: no recirc sweep
        elif config in ("B1_closed", "B2_closed", "C1"):
            total += len(locations) * len(solar_areas) * len(recirc_values)
        else:
            total += len(locations) * len(solar_areas)
    return total


def main():
    args = parse_args()
    
    print("\n" + "="*70)
    print("SOLAR-HP DRYER SIMULATION RUNNER")
    print("="*70 + "\n")
    
    # Determine what to run
    if args.test:
        configs = ["A"]
        locations = ["kathmandu"]
        solar_areas = [10.0]
        print("MODE: Quick test (Config A, Kathmandu)\n")

    elif args.full:
        configs = ["A", "B1_open", "B2_open", "B1_closed", "B2_closed", "C1"]
        locations = ["kathmandu", "dhulikhel", "biratnagar", "taplejung"]
        solar_areas = [2, 4, 6, 8, 10, 12, 15, 20]  # No 0 - redundant for solar configs
        # Default recirc sweep for Config A in full mode
        if not args.recirc_values:
            args.recirc_values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        print("MODE: Full parametric sweep\n")

    elif args.config and args.location:
        configs = [args.config]
        locations = [args.location]
        if args.config in ("0", "A", "D1", "D2", "D3"):
            solar_areas = [0.0]  # Config 0/A/D don't use solar
        elif args.config in ("E1", "E2", "E3"):
            solar_areas = [args.solar_area if args.solar_area is not None else 5.0]
        else:
            solar_areas = [args.solar_area if args.solar_area is not None else 10.0]
        print(f"MODE: Single simulation\n")

    elif args.configs or args.locations or args.solar_areas or args.config or args.location or args.solar_area:
        configs = args.configs if args.configs else ([args.config] if args.config else ["A"])
        locations = args.locations if args.locations else ([args.location] if args.location else ["kathmandu"])
        solar_areas = args.solar_areas if args.solar_areas else ([args.solar_area] if args.solar_area else [10.0])
        print(f"MODE: Custom sweep\n")

    else:
        print("ERROR: Must specify --test, --full, or provide --config and --location\n")
        print("Examples:")
        print("  python scripts/run_solar_hp_configs.py --test")
        print("  python scripts/run_solar_hp_configs.py --config A --location kathmandu")
        print("  python scripts/run_solar_hp_configs.py --config B --location kathmandu --solar-area 10")
        print("  python scripts/run_solar_hp_configs.py --full")
        print("  python scripts/run_solar_hp_configs.py --config A --location kathmandu --recirc-values 0.0 0.4 0.8")
        sys.exit(1)

    # Recirculation sweep for Config A
    recirc_values = args.recirc_values if args.recirc_values else [0.0]

    # Calculate and display run count
    total = calculate_total_runs(configs, locations, solar_areas, recirc_values)
    print(f"Configurations: {configs}")
    print(f"Locations: {locations}")
    print(f"Solar areas: {solar_areas}")
    if any(c in ("A", "B1_closed", "B2_closed", "C1") for c in configs) and len(recirc_values) > 1:
        print(f"Config A/B1_closed/B2_closed/C1 recirc values: {recirc_values}")
    print(f"Total simulations: {total}")
    
    # Run simulations
    start_time = datetime.now()
    results = []
    count = 0
    
    for config in configs:
        for location in locations:
            if config == "0":
                count += 1
                print(f"\n[{count}/{total}] ", end="")
                try:
                    result = run_single_simulation(config, location, 0.0, args)
                    results.append({
                        "config": config, "location": location,
                        "solar_area_m2": 0.0, "r_recirc": 0.0,
                        "success": True, "converged": result.converged,
                        "message": result.final_message,
                        "drying_time_h": result.df["time_h"].iloc[-1] if not result.df.empty else None,
                        "W_comp_kWh": result.df["W_comp_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "W_elec_kWh": (result.df["W_elec_cum_kWh"].iloc[-1] if ("W_elec_cum_kWh" in result.df.columns and not result.df.empty) else 0.0),
                        "W_fan_kWh": result.df["W_fan_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "Q_solar_kWh": 0.0,
                        "m_water_kg": result.df["m_w_cum_kg"].iloc[-1] if not result.df.empty else None,
                    })
                except Exception as e:
                    print(f"ERROR: {e}")
                    import traceback; traceback.print_exc()
                    results.append({
                        "config": config, "location": location,
                        "solar_area_m2": 0.0, "r_recirc": 0.0,
                        "success": False, "converged": False, "message": str(e),
                    })
            elif config == "A":
                # Config A: sweep over recirculation ratios
                for r_val in recirc_values:
                    count += 1
                    print(f"\n[{count}/{total}] ", end="")
                    try:
                        result = run_single_simulation(config, location, 0.0, args,
                                                       r_recirc=r_val)
                        results.append({
                            "config": config,
                            "location": location,
                            "solar_area_m2": 0.0,
                            "r_recirc": r_val,
                            "success": True,
                            "converged": result.converged,
                            "message": result.final_message,
                            "drying_time_h": result.df["time_h"].iloc[-1] if not result.df.empty else None,
                            "W_comp_kWh": result.df["W_comp_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "W_elec_kWh": (result.df["W_elec_cum_kWh"].iloc[-1] if ("W_elec_cum_kWh" in result.df.columns and not result.df.empty) else 0.0),
                            "W_fan_kWh": result.df["W_fan_cum_kWh"].iloc[-1] if not result.df.empty else None,
                            "Q_solar_kWh": result.df["Q_solar_cum_kWh"].iloc[-1] if not result.df.empty else None,
                            "m_water_kg": result.df["m_w_cum_kg"].iloc[-1] if not result.df.empty else None,
                        })
                    except Exception as e:
                        print(f"ERROR: {e}")
                        import traceback
                        traceback.print_exc()
                        results.append({
                            "config": config, "location": location,
                            "solar_area_m2": 0.0, "r_recirc": r_val,
                            "success": False, "converged": False, "message": str(e),
                        })
            elif config in ("D1", "D2", "D3"):
                # Config D: single run per location (no solar, no recirc sweep)
                count += 1
                print(f"\n[{count}/{total}] ", end="")
                try:
                    result = run_single_simulation(config, location, 0.0, args)
                    results.append({
                        "config": config,
                        "location": location,
                        "solar_area_m2": 0.0,
                        "r_recirc": 0.0,
                        "success": True,
                        "converged": result.converged,
                        "message": result.final_message,
                        "drying_time_h": result.df["time_h"].iloc[-1] if not result.df.empty else None,
                        "W_comp_kWh": result.df["W_comp_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "W_elec_kWh": (result.df["W_elec_cum_kWh"].iloc[-1] if ("W_elec_cum_kWh" in result.df.columns and not result.df.empty) else 0.0),
                        "W_fan_kWh": result.df["W_fan_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "Q_solar_kWh": result.df["Q_solar_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "m_water_kg": result.df["m_w_cum_kg"].iloc[-1] if not result.df.empty else None,
                    })
                except Exception as e:
                    print(f"ERROR: {e}")
                    import traceback
                    traceback.print_exc()
                    results.append({
                        "config": config, "location": location,
                        "solar_area_m2": 0.0, "r_recirc": 0.0,
                        "success": False, "converged": False, "message": str(e),
                    })
            elif config in ("E1", "E2", "E3"):
                # Config E: sweep solar areas (no recirc)
                for solar_area in solar_areas:
                    count += 1
                    print(f"\n[{count}/{total}] ", end="")
                    try:
                        result = run_single_simulation(config, location, solar_area, args)
                        results.append({
                            "config": config,
                            "location": location,
                            "solar_area_m2": solar_area,
                            "r_recirc": 0.0,
                            "success": True,
                            "converged": result.converged,
                            "message": result.final_message,
                            "drying_time_h": result.df["time_h"].iloc[-1] if not result.df.empty else None,
                            "W_comp_kWh": result.df["W_comp_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "W_elec_kWh": (result.df["W_elec_cum_kWh"].iloc[-1] if ("W_elec_cum_kWh" in result.df.columns and not result.df.empty) else 0.0),
                            "W_fan_kWh": result.df["W_fan_cum_kWh"].iloc[-1] if not result.df.empty else None,
                            "Q_solar_kWh": result.df["Q_solar_cum_kWh"].iloc[-1] if not result.df.empty else None,
                            "m_water_kg": result.df["m_w_cum_kg"].iloc[-1] if not result.df.empty else None,
                        })
                    except Exception as e:
                        print(f"ERROR: {e}")
                        import traceback
                        traceback.print_exc()
                        results.append({
                            "config": config, "location": location,
                            "solar_area_m2": solar_area, "r_recirc": 0.0,
                            "success": False, "converged": False, "message": str(e),
                        })
            elif config in ("B1_closed", "B2_closed", "C1"):
                # Closed-loop solar configs: sweep solar areas × recirc values
                for solar_area in solar_areas:
                    for r_val in recirc_values:
                        count += 1
                        print(f"\n[{count}/{total}] ", end="")
                        try:
                            result = run_single_simulation(config, location, solar_area, args,
                                                           r_recirc=r_val)
                            results.append({
                                "config": config,
                                "location": location,
                                "solar_area_m2": solar_area,
                                "r_recirc": r_val,
                                "success": True,
                                "converged": result.converged,
                                "message": result.final_message,
                                "drying_time_h": result.df["time_h"].iloc[-1] if not result.df.empty else None,
                                "W_comp_kWh": result.df["W_comp_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "W_elec_kWh": (result.df["W_elec_cum_kWh"].iloc[-1] if ("W_elec_cum_kWh" in result.df.columns and not result.df.empty) else 0.0),
                                "W_fan_kWh": result.df["W_fan_cum_kWh"].iloc[-1] if not result.df.empty else None,
                                "Q_solar_kWh": result.df["Q_solar_cum_kWh"].iloc[-1] if not result.df.empty else None,
                                "m_water_kg": result.df["m_w_cum_kg"].iloc[-1] if not result.df.empty else None,
                            })
                        except Exception as e:
                            print(f"ERROR: {e}")
                            import traceback
                            traceback.print_exc()
                            results.append({
                                "config": config, "location": location,
                                "solar_area_m2": solar_area, "r_recirc": r_val,
                                "success": False, "converged": False, "message": str(e),
                            })
            else:
                for solar_area in solar_areas:
                    count += 1
                    print(f"\n[{count}/{total}] ", end="")
                    try:
                        result = run_single_simulation(config, location, solar_area, args)
                        results.append({
                            "config": config,
                            "location": location,
                            "solar_area_m2": solar_area,
                            "r_recirc": 0.0,
                            "success": True,
                            "converged": result.converged,
                            "message": result.final_message,
                            "drying_time_h": result.df["time_h"].iloc[-1] if not result.df.empty else None,
                            "W_comp_kWh": result.df["W_comp_cum_kWh"].iloc[-1] if not result.df.empty else None,
                        "W_elec_kWh": (result.df["W_elec_cum_kWh"].iloc[-1] if ("W_elec_cum_kWh" in result.df.columns and not result.df.empty) else 0.0),
                            "W_fan_kWh": result.df["W_fan_cum_kWh"].iloc[-1] if not result.df.empty else None,
                            "Q_solar_kWh": result.df["Q_solar_cum_kWh"].iloc[-1] if not result.df.empty else None,
                            "m_water_kg": result.df["m_w_cum_kg"].iloc[-1] if not result.df.empty else None,
                        })
                    except Exception as e:
                        print(f"ERROR: {e}")
                        import traceback
                        traceback.print_exc()
                        results.append({
                            "config": config, "location": location,
                            "solar_area_m2": solar_area, "r_recirc": 0.0,
                            "success": False, "converged": False, "message": str(e),
                        })
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("SIMULATION COMPLETE")
    print("="*70)
    print(f"Total time: {duration/60:.1f} minutes")
    print(f"Successful: {sum(1 for r in results if r['success'])}/{len(results)}")
    print(f"Converged: {sum(1 for r in results if r.get('converged', False))}/{len(results)}")
    
    # Save summary
    summary_df = pd.DataFrame(results)
    summary_file = PROJECT_ROOT / args.output_dir / "run_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"\nSummary saved: {summary_file}")
    
    # Print comparison table
    if len(results) > 1:
        print("\n" + "-"*80)
        print("COMPARISON (SEC = Specific Energy Consumption)")
        print("-"*80)
        print(f"{'Config':<8} {'Location':<12} {'A_solar':<8} {'r_recirc':<9} {'Time(h)':<10} {'W_comp':<10} {'W_fan':<10} {'SEC':<10}")
        print("-"*90)
        for r in results:
            if r['success'] and r.get('W_comp_kWh') is not None and r.get('m_water_kg'):
                w_fan = r.get('W_fan_kWh', 0.0) or 0.0
                sec = (r['W_comp_kWh'] + w_fan) / r['m_water_kg'] if r['m_water_kg'] > 0 else float('inf')
                print(f"{r['config']:<8} {r['location']:<12} {r['solar_area_m2']:<8.0f} "
                      f"{r.get('r_recirc', 0.0):<9.2f} "
                      f"{r.get('drying_time_h', 0):<10.1f} {r['W_comp_kWh']:<10.2f} {w_fan:<10.2f} {sec:<10.3f}")


if __name__ == "__main__":
    main()
