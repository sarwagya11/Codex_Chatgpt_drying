#!/usr/bin/env bash
# VPD threshold sensitivity sweep for E2 (recommended config).
# Two representative cases: KTM annual (mid-elevation) + BTN autumn (humid).
set -e
cd "$(dirname "$0")/.."

THRESHOLDS=(0.02 0.10 0.15 0.20)   # 0.00 (=no-VPD) and 0.05 already exist

for T in "${THRESHOLDS[@]}"; do
  echo "=== E2 KTM annual VPD=$T ==="
  python scripts/run_solar_hp_configs.py --config E2 --location kathmandu \
    --solar-area 10 --eps-hrx 0.70 --vpd-threshold "$T"

  echo "=== E2 BTN autumn VPD=$T ==="
  python scripts/run_solar_hp_configs.py --config E2 --location biratnagar \
    --weather-file data/ambient/seasonal/biratnagar_autumn_oct_nov.csv \
    --solar-area 10 --eps-hrx 0.70 --vpd-threshold "$T"
done
echo "=== sweep done ==="
