#!/usr/bin/env bash
# Config C2 full sweep: 4 sites x 5 weathers (annual + 4 seasons) x 5 areas = 100 sims, r=0.
set -u
cd "$(dirname "$0")/.."
LOG="outputs/_config_C_sweep_$(date +%Y%m%d_%H%M%S).log"
echo "Logging to $LOG"

SITES=(biratnagar dhulikhel kathmandu taplejung)
SEASONS=(spring_mar_apr summer_may_jun autumn_oct_nov winter_dec_jan)
AREAS=(2 5 10 15 20)

run_one() {
  local site="$1" ac="$2" weather="$3"
  if [ -n "$weather" ]; then
    echo "=== $(date +%H:%M:%S) | C2 | $site | Ac=$ac | $(basename "$weather") ===" | tee -a "$LOG"
    python scripts/run_solar_hp_configs.py --config C2 --location "$site" --solar-area "$ac" --weather-file "$weather" >> "$LOG" 2>&1
  else
    echo "=== $(date +%H:%M:%S) | C2 | $site | Ac=$ac | annual ===" | tee -a "$LOG"
    python scripts/run_solar_hp_configs.py --config C2 --location "$site" --solar-area "$ac" >> "$LOG" 2>&1
  fi
}

for site in "${SITES[@]}"; do
  # annual
  for ac in "${AREAS[@]}"; do
    run_one "$site" "$ac" ""
  done
  # seasonal
  for season in "${SEASONS[@]}"; do
    wfile="data/ambient/seasonal/${site}_${season}.csv"
    if [ ! -f "$wfile" ]; then
      echo "[SKIP] missing $wfile" | tee -a "$LOG"
      continue
    fi
    for ac in "${AREAS[@]}"; do
      run_one "$site" "$ac" "$wfile"
    done
  done
done

echo "=== DONE $(date +%H:%M:%S) ===" | tee -a "$LOG"
