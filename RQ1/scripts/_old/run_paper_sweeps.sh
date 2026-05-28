#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
LOG="outputs/_paper_sweep_$(date +%Y%m%d_%H%M%S).log"
echo "Logging to $LOG"

run_one() {
  local cfg="$1" loc="$2" ac="$3"
  echo "=== $(date +%H:%M:%S) | $cfg | $loc | Ac=$ac ===" | tee -a "$LOG"
  python scripts/run_solar_hp_configs.py --config "$cfg" --location "$loc" --solar-area "$ac" >> "$LOG" 2>&1
}

# E3 area sweep, 4 sites x 7 areas = 28
for site in biratnagar kathmandu taplejung dhulikhel; do
  for ac in 2 4 5 6 8 15 20; do
    run_one E3 "$site" "$ac"
  done
done

# E2 Dhulikhel fill-in: 7
for ac in 2 4 5 6 8 15 20; do
  run_one E2 dhulikhel "$ac"
done

# E1 Dhulikhel fill-in: 1
run_one E1 dhulikhel 5

echo "=== DONE $(date +%H:%M:%S) ===" | tee -a "$LOG"
