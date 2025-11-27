# RQ1 Phase-1 Simulation

This folder contains a clean, modular Phase-1 dynamic model for the solar-assisted dryer project. The focus is on air mixing with recirculation, simple first-order drying kinetics, and fixed inlet temperature. Solar and heat pump effects are intentionally excluded for clarity.

## Layout

- `data/ambient/` – standardized ambient CSV files (temperature, RH, optional irradiance).
- `data/kinetics/` – optional Midilli k, n, b lookup tables for later use.
- `src/rq1/` – Phase-1 Python modules.
- `scripts/` – helper scripts to build ambient datasets and run simulations.

## Usage

1. Build a standardized ambient file using `scripts/build_ambient_from_weather.py` if needed.
2. Run a simulation with `scripts/run_phase1_simulation.py`, passing the ambient CSV and dryer settings.
3. Inspect the output CSV for time-series states and energy metrics.

All imports inside `rq1` use relative paths to keep the package self-contained. Dependencies are limited to Python 3, `numpy`, and `pandas`.
