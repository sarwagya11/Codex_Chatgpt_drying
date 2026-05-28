#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

CFGS=(E1 E2 E3)
ANNUAL_LOCS=(biratnagar kathmandu taplejung)
SEAS_LOCS=(biratnagar dhulikhel kathmandu taplejung)
SEASONS=(autumn_oct_nov spring_mar_apr winter_dec_jan)

for C in "${CFGS[@]}"; do
  for L in "${ANNUAL_LOCS[@]}"; do
    echo "=== $C $L annual ==="
    python scripts/run_solar_hp_configs.py --config "$C" --location "$L" \
      --solar-area 10 --eps-hrx 0.70 --vpd-threshold 0.05
  done
  for L in "${SEAS_LOCS[@]}"; do
    for S in "${SEASONS[@]}"; do
      echo "=== $C $L $S ==="
      python scripts/run_solar_hp_configs.py --config "$C" --location "$L" \
        --weather-file "data/ambient/seasonal/${L}_${S}.csv" \
        --solar-area 10 --eps-hrx 0.70 --vpd-threshold 0.05
    done
  done
done
echo "=== E1/E2/E3 VPD re-runs done ==="
