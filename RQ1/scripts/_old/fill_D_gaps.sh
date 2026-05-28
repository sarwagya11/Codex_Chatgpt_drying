#!/usr/bin/env bash
# Fill coverage gaps in Config D{1,2,3}: summer at all sites + Dhulikhel non-vpd, both variants.
set -u
cd "$(dirname "$0")/.."
LOG="outputs/_fill_D_$(date +%Y%m%d_%H%M%S).log"
echo "Logging to $LOG"

SITES=(biratnagar dhulikhel kathmandu taplejung)
CONFIGS=(D1 D2 D3)

run() {
  local cfg="$1" site="$2" wfile="$3" vpd="$4" tag="$5"
  local vpd_flag=""
  [ -n "$vpd" ] && vpd_flag="--vpd-threshold $vpd"
  echo "=== $(date +%H:%M:%S) | $cfg | $site | $tag | vpd=${vpd:-none} ===" | tee -a "$LOG"
  if [ -n "$wfile" ]; then
    python scripts/run_solar_hp_configs.py --config "$cfg" --location "$site" --weather-file "$wfile" $vpd_flag >> "$LOG" 2>&1
  else
    python scripts/run_solar_hp_configs.py --config "$cfg" --location "$site" $vpd_flag >> "$LOG" 2>&1
  fi
}

# Summer for all sites x all D configs, both variants
for cfg in "${CONFIGS[@]}"; do
  for site in "${SITES[@]}"; do
    wfile="data/ambient/seasonal/${site}_summer_may_jun.csv"
    [ -f "$wfile" ] || { echo "[SKIP] $wfile"; continue; }
    run "$cfg" "$site" "$wfile" ""    "summer"
    run "$cfg" "$site" "$wfile" "0.05" "summer"
  done
done

# Dhulikhel non-vpd fill for spring/autumn/winter (vpd variants already exist)
for cfg in "${CONFIGS[@]}"; do
  for season in spring_mar_apr autumn_oct_nov winter_dec_jan; do
    wfile="data/ambient/seasonal/dhulikhel_${season}.csv"
    [ -f "$wfile" ] || { echo "[SKIP] $wfile"; continue; }
    run "$cfg" "dhulikhel" "$wfile" "" "$season"
  done
done

echo "=== DONE $(date +%H:%M:%S) ===" | tee -a "$LOG"
