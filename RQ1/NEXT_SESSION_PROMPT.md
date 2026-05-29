# Handoff Prompt — Paper-1 Drafting Session (updated 2026-05-29)

Paste this block into a fresh chat to focus on **paper drafting** while the workstation runs the two-stage sweep in the background. Read `MEMORY.md` after this for project bedrock (location list, refrigerant, kinetics constants, current physical defaults).

---

## Goal of paper-1

Compare 11 dryer configurations (Config 0 baseline + Config A / B1_open / B2_open / B1_closed / B2_closed / C1 / D1 / D2 / E1 / E2 / E3) across 4 Nepali sites (Biratnagar, Kathmandu, Jomsom, Namche) under year-round daily-batch weather (PVGIS-ERA5 SARAH3, POA at slope=45°, azimuth=0°). Goals: (i) rank topologies by SEC at fixed T_set=45°C, (ii) characterise the marginal value of HRX, solar collector, and recirculation as a function of climate. Crop is apple (M1 kinetic refit, K_ref=1.5436e-4 1/s @ T_ref=50°C, Ea=30.11 kJ/mol). Config D3 was dropped from paper-1 (HRX-swapped routing pushes humid exhaust into chamber, drying ~25 % longer).

## Workstation status (end of 2026-05-29 session)

**Sweep redesigned as two-stage r-screen.** The original 52,272-sim full-year r-sweep was killed at sim 2,336 (4.3 % done, ~3 of 4 days remaining). The replacement design:

- **Stage 1 — r-screening (1,056 sims, ~3 h):** 4 r-accepting configs (A, C1, B1_closed, B2_closed) × 4 sites × 12 days/site (one per calendar month, mid-month) × {0, 0.3, 0.5, 0.7, 0.8, 0.9} r-values. Picks one r* per (config, site) with 1 % smaller-r tie-break.
- **Stage 2 — production at fixed r* (5,328 sims, ~15 h):** All 11 configs × 4 sites × every-5th-day (74 days/site, B-prime grain, n=18 per quarter) × r* (only for the 4 r-accepting configs, others at r=0) + E2 area sweep across {2, 4, 6, 8, 10, 12, 15, 20} m².

Total wall time ~18 h (vs ~4 days originally). The workstation is being re-downloaded fresh (HEAD = `b3da71c`) and stage 1 is being launched. If asked, the runbook is at the bottom of this file.

Statistical defensibility for B-prime: ±0.019 kWh/kg uncertainty on quarterly mean SEC (assumed sigma=0.08). Comfortably distinguishes cross-family rankings (typical delta 0.05-0.30); close-pair calls (e.g., E1 vs E2 within same site) may need a follow-up at finer grain.

## Paper draft state (as of 2026-05-29)

Draft lives at `RQ1/paper/DRAFT.md`.

**Ready or partially ready to draft now:**
- **§1 Introduction** — locked per `paper_section_1_status.md` (5-paragraph restructure 2026-05-19, kinetic claim wording locked). Outstanding: Aktaş 2015 + Mishra 2017 PDFs still missing.
- **§3 Methods** — reviewer pass applied 2026-05-21 (R1, R5-R7, R9a, R10-R15). Outstanding: R8 wording, R2/R3/R4 deferred.
- **§4 Setup** — §4.4 (lines 389-395) rewritten to describe the 52,272-sim daily matrix. **Needs an update** to the two-stage design (1,056 + 5,328 = 6,384 sims, every-5-days grain, r* selection logic).
- **Table 1** (lines 366-388) — rebuilt for 12-simulator list. Needs sign-off against `air_paths_verified.md`.

**Blocked (waiting on stage-2 results):**
- §5.1–5.5 numerical tables (every SEC number is stale: pre-flip series/10cm chamber, legacy kinetics, legacy site list).
- Figs 3-7 (heatmap, placement bars, T_set sweep, area sweep, seasonal).
- Headline SEC table in MEMORY.md (marked STALE).
- Aggregation pipeline (`scripts/aggregate_results.py` is a stub).

## Work to attack while sweep runs

1. **§4.4 rewrite for the two-stage design.** Replace "52,272-sim daily matrix" with the screen + production setup. Cite n=18 per quarter, tie-break rule, and that E2 area sweep is independent of r*.
2. **Sign off Table 1.** Cross-check the 12-simulator descriptions against `air_paths_verified.md` and `MEMORY.md` architecture section. The current rewrite is from 2026-05-28; topology defaults are parallel + 1.5 cm gap, K_in=0.5, K_out=1.0.
3. **Tighten §1 and §3.** §1 has the Aktaş 2015 + Mishra 2017 citation hole; §3 has R8 still open and R2/R3/R4 deferred. Resolve or note explicit defer in DRAFT.md.
4. **Draft §2 Literature Review** if not done. `RESEARCH_PLAN.md` (29 refs) and `RESEARCH_HRX.md` (15 refs) are the source pool.
5. **Scaffold the §5 aggregation pipeline.** Even without stage-2 data, you can write `scripts/aggregate_results.py` to consume `sweep_summary_stage2.csv` with the expected columns (config, site, quarter, batch_idx, r_recirc, solar_area_m2, SEC_elec_kWh_per_kg, drying_time_h, ...). Build the headline (site × config) heatmap function, seasonal bar function, and E2 area-sweep curve function. Test with `sweep_summary_stage1.csv` if it has finished by then.

## Files touched in 2026-05-29 session (commit b3da71c)

- `scripts/build_subset_batch_starts.py` — new. Filters `daily_batch_starts.csv` into 48-row screening (mid-month days per quarter) and 296-row production (every-5-days, Q4 last 2 dropped for forward-window safety).
- `scripts/run_quarterly_sweep.py` — patched. Added `--r-star-csv` flag and `load_r_star_table` helper; refactored `r_values_for` to take `site` and an optional `r_star_table`; outer loop reordered to `config → site → r → area → quarter → batch` so r* varies per site.
- `scripts/pick_r_star.py` — new. Reads stage-1 `sweep_summary.csv`, means SEC across screening days per (config, site, r), picks argmin r* per (config, site) with 1 % smaller-r tie-break. Writes `r_star_by_config_site.csv`.
- `outputs/quarterly/screening_batch_starts.csv` — new, 48 rows.
- `outputs/quarterly/production_batch_starts.csv` — new, 296 rows.

## Commits pushed to origin/main

- `b3da71c` — two-stage r-screen scaffolding (this session)
- `2df07d5` — `phase2_targets.csv` for M1 refit on workstation (prior session)
- `9337962` — 218-file workstation sync (prior session)
- `8922dfe` — initial workstation drop (prior session)

## How to start the new chat

Paste this entire file as the first message of the new chat. The natural opener is something like:

> "Section 5 is blocked until the workstation finishes (~Friday morning). Help me lock in §4.4 for the new two-stage design first, then we'll do Table 1 sign-off and scaffold the aggregation script. The sweep is running independently and doesn't need attention from this chat."

If you want a different starting point, the two safe ones are (a) write §2 Literature Review from `RESEARCH_PLAN.md` + `RESEARCH_HRX.md`, or (b) start `scripts/aggregate_results.py` so it's ready when stage-2 lands.

---

## Workstation runbook (reference — only needed if the running sweep stalls)

On the workstation in `D:\Wasti Sims\Codex_Chatgpt_drying-main\RQ1\`:

**Stage 1 (running now):**
```cmd
"C:\Users\Student\ladybug_tools\python\python.exe" scripts\run_quarterly_sweep.py ^
  --batch-starts outputs\quarterly\screening_batch_starts.csv ^
  --configs A C1 B1_closed B2_closed ^
  --summary-name sweep_summary_stage1.csv ^
  > outputs\quarterly\stage1.log 2>&1
```

**Stage 1 → r* picker (instant):**
```cmd
"C:\Users\Student\ladybug_tools\python\python.exe" scripts\pick_r_star.py ^
  --summary outputs\quarterly\sweep_summary_stage1.csv ^
  --out outputs\quarterly\r_star_by_config_site.csv
```

Sanity-check r* before launching stage 2: flag (a) any (config, site) hitting r=0.9 in every site (plateau may extend further), (b) any unexpected r=0 picks for A or C1 (would suggest a humidity or load-mismatch bug).

**Stage 2 (after r* sign-off):**
```cmd
"C:\Users\Student\ladybug_tools\python\python.exe" scripts\run_quarterly_sweep.py ^
  --batch-starts outputs\quarterly\production_batch_starts.csv ^
  --r-star-csv outputs\quarterly\r_star_by_config_site.csv ^
  --summary-name sweep_summary_stage2.csv ^
  > outputs\quarterly\stage2.log 2>&1
```

Tail any of the logs with `powershell "Get-Content <log> -Tail 30"`. If `stage1.log` or `stage2.log` stops appending for >30 min, paste the last 50 lines into the chat and we'll diagnose.

## Expected stage-2 outputs (when ready)

`outputs/quarterly/sweep_summary_stage2.csv` columns (one row per simulation):
`config, r_recirc, site, quarter, batch_idx, start_row_index, start_datetime_NPT, solar_area_m2, T_set_C, eps_HRX, vpd_threshold, success, converged, message, drying_time_h, m_water_kg, W_comp_kWh, Q_cond_kWh, Q_solar_kWh, W_fan_kWh, W_elec_kWh, SEC_elec_kWh_per_kg`

Per-batch CSVs under `outputs/quarterly/config_<X>/<site>/<quarter>/batch<i>_r<X.X>[_Ac<N>m2][_hrx0.70].csv` give the full time series for each simulation.
