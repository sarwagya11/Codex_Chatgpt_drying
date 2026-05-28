# Handoff Prompt — Paper-1 (updated 2026-05-28)

Paste this block into a fresh chat to continue cleanly.

---

I am working on the SAHPD apple-drying paper at `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`. Read `MEMORY.md` first for project context, then continue from this state. This file supersedes the 2026-05-27 handoff.

## What this paper is and what changed

Paper-1 is a **comparison of 11 dryer configurations across 4 Nepali sites and 365 days at 9 solar areas**, with apple as the target crop. The original 2026-05-27 plan was: 11 configs × 4 sites × 9 areas × daily-year batches = 86k sims, configs frozen.

**Session 2026-05-28 expanded the scope slightly** for two literature-driven reasons:
1. A focused literature audit (2020-2026 SAHPD papers, see below) showed that **closed-loop / semi-open recirculation is now the default architecture in current SAHPD/HPD research**, not open-loop. My earlier "open-loop is the standard" framing was based on 2008-2018 papers and is outdated.
2. Config A was hard-locked to r=0 by an earlier 2026-05-13 design decision. The user wants closed-loop A back in the matrix as the canonical Mujumdar Mode A closed-cycle HPCD baseline.

**Late-2026-05-28 update**: a follow-up Namche r=1.0 probe overturned the mid-day "closed-loop HPCD fails at altitude" finding. Config A has two viable operating modes per site (r=0 OR r=1.0; partial-r is a dead zone at cold sites). The recommended matrix scope is now **11 configs** with Config A reported at the per-site best r (BTN: r=0; KTM/JSM/Namche: r=1.0). No new B/C architectures needed for paper-1.

**Architecture/matrix scope is now closed.** Both scope questions resolved during session 2026-05-28:
- Config A runs at **per-site best r** in the headline matrix (BTN r=0; KTM/JSM/Namche r=1.0). See §9.
- B/C stay at r=0; D2/E2/E3 already provide the semi-open exhaust→evap routing via HRX, so no new Bx/B2x code. See "B/C exhaust routing — resolved by code review".

The remaining gate for launch is plumbing (runner needs per-site r dispatch for Config A, SLURM partitioning, post-sweep aggregation), not physics or architecture.

## Session 2026-05-28 — what got done

### 1. POA45 weather pipeline (DONE)
PVGIS-ERA5 seriescalc at slope=45°, aspect=0°, components=1, usehorizon=1.
- `scripts/fetch_pvgis_poa.py` — pulls per-site CSV.
- `scripts/build_poa_standard.py` — merges POA into existing standard CSVs (kept blank-line-aware via `r"^\d{8}:\d{4},"` regex).
- Output: `data/ambient/{site}_pvgis_standard_poa45.csv` with both GHI_Wm2 and POA_Wm2.
- Annual POA/GHI ratios: Biratnagar 1.110, Kathmandu 1.116, Jomsom 1.125, Namche 1.206.
- Dryer reads POA: `src/rq1/dryer_solar_hp.py:load_weather_data_raw` promotes POA_Wm2 into the GHI_Wm2 column at load (one-time print per path so it's auditable).
- All downstream scripts prefer POA file: `scripts/run_quarterly_sweep.py:97`, `scripts/smoke_topology_parity.py:43`, `scripts/run_solar_hp_configs.py:81-86`, `scripts/daily_batch_starts.py`, `scripts/quarterly_batch_starts.py`.
- Verification plots: `scripts/plot_poa_vs_ghi.py` → `outputs/poa_validation/plots/poa_vs_ghi_{site}.png`. Winter DJF gain ~+30-35% peak; summer JJA slight loss (tilt overshoots high sun).

### 2. Single-run validation (DONE)
- Config A KTM r=0: SEC=0.586 kWh/kg, 9.2 h, W_comp=10.60 kWh, m_w=18.90 kg. ✓
- Config E2 KTM A_solar=15: SEC=0.164 kWh/kg, 9.2 h, W_comp=1.94 kWh, Q_solar=20.47 kWh, W_fan=1.17 kWh. ✓
- Plots in `outputs/poa_validation/plots/`.

### 3. r-sweep on B1 (KTM, A_solar=15) (DONE)
B1's recirc engine already supports r>0. Results:

| r    | Time (h) | W_comp | W_fan | SEC (kWh/kg) | notes |
|------|----------|--------|-------|--------------|-------|
| 0.0  | 9.2  | 3.58 | 0.48 | 0.215 |  |
| 0.5  | 10.5 | 2.97 | 0.43 | **0.180** | min |
| 0.7  | 10.1 | 3.08 | 0.41 | 0.185 |  |
| 0.85 | 9.6  | 3.28 | 0.39 | 0.195 |  |
| 0.95 | 9.6  | 3.27 | 0.40 | 0.194 |  |

Bowl shape, ~16% improvement from r=0 to r=0.5. Mechanism: recirc carries moisture to evap drain → less ambient enthalpy waste; past r=0.5 warm humid mix slows kinetics. Note: B1's collector takes a η_coll penalty at r>0 (warm inlet) — this curve is the *combined* effect.

### 4. Literature audit — two stages (DONE)

**Stage 1: original SAHPD claims (2008-2018).** Most of my opening citations were sloppy:
- "Mohanraj 2008 grape" — does not exist (2008 paper is copra). Drop or fix.
- "Mortezapour & Ghobadian 2009 saffron" — actual year is **2012** (*Drying Technology* 30(6):560-566). Fix.
- "Aktaş 2015 apple" — Aktaş apple SAHPD is actually **2009**. Fix.
- "Şevik 2013 mushroom = open-loop SAHPD" — **refuted**. The paper explicitly compares open / closed / semi-open modes; "closed" performed well.
- "Aktaş 2016 kiwi" — exists; full-text architecture not verified.
- "Yousefi 2018 herbs" — actual reference is Alishah/Yousefi 2018 coriander (*IJACR* 26(4):1850037); architecture unverified.
- "Daghigh 2010 review" — exists (paywalled), do not quote-attribute "open-loop is dominant" without PDF.

**Stage 2: current (2020-2026) SAHPD research.** Trend has shifted to closed-loop / semi-open:
- Zhu et al. 2025, *Foods* 14(15):2569 review — "closed / semi-closed circulation is the default; exhaust through evaporator + reheat in condenser is a defining feature".
- Wang et al. 2025, *Agriculture* 16(6):633 — apple slices in a closed HPD oven (40-50 °C, 30-60 % RH).
- Tang et al. 2025, tomato — solar + multistage HPD, ~25% fresh-air semi-open.
- Loemba et al. 2024, banana SAHPD + storage, closed-loop.
- Rulazi et al. 2024, *Food Sci Nutr*, tomato/carrot closed-loop SAHPD (Tanzania).
- Zhao et al. 2023, *Solar Energy*, closed-loop SE-HPD with ejector.
- Kang et al. 2022, *Foods* 11(21):3509 — kelp, switchable open/closed/semi-open.
- Loemba et al. 2023, *Energy Sci Eng* 11(8) — banana 3.3 kWh open vs 2.41 kWh closed = ~27% saving.
- Hossain et al. 2024, *J Therm Anal Calorim* HPD review — emphasises exhaust recovery / recirculation.
- **Apple-specific high-altitude SAHPD: no precedent. This is the paper's publishable gap.**

### 5. Config A closed-loop branch (DONE — code shipped)

- Removed the r=0 hard-lock at the old `dryer_solar_hp.py:857-861`.
- Added `_simulate_config_A_closed_loop()` (new helper) that mirrors B1's recirc engine *minus* the solar collector. Path at r>0: Mix(r·exh + (1-r)·amb) → Evap (dehumid, T_evap_coil modulated) → Cond (first-law enforced: Q_cond = Q_evap_air·COP/(COP-η_m)) → Chamber → split.
- Dispatcher in `simulate_config_A_HP_only()`: r=0 path unchanged (byte-identical); r>0 routes to the new helper.
- config_type returned for the closed-loop branch is `"CONFIG_A_CL"` (so the CSV is distinguishable).
- Same low-pass exhaust filter (τ=300 s), impossible-cycle guard, saturation clamp as B1.

### 6. Config A r-sweep (DONE — first pass, KTM)

Sweep `r ∈ {0, 0.3, 0.5, 0.8, 0.9, 1.0}` at Kathmandu, A_solar=0:

| r    | Time (h) | W_comp | m_water | SEC | status |
|------|----------|--------|---------|-----|--------|
| 0.0  | 9.2  | 10.60 | 18.90 | 0.586 | open-loop baseline |
| 0.3  | 24.0 | 7.02  | 15.13 | — | **STALL (DNF)** |
| 0.5  | 24.0 | 7.01  | 15.47 | — | **STALL (DNF)** |
| 0.8  | 11.0 | 9.94  | 18.90 | 0.550 | converged |
| 0.9  | 9.6  | 9.48  | 18.90 | 0.523 | converged |
| 1.0  | 9.6  | 9.42  | 18.90 | **0.519** | best |

**The stall at r ∈ [0.3, 0.5] is physical, not a bug.** Mechanism: at low r, T_mix is dominated by cool ambient. The evap coil modulator (`_min_dt_evap = 5 K`) keeps T_evap_coil ≥ T_mix − 5 K, so the coil floats near ambient dewpoint and dehumidifies poorly. Chamber-inlet ω stays near ambient ω, drying asymptotes to X_eq, sim hits the 24-h cap before finishing. At r ≥ 0.8 the warm humid exhaust lifts T_mix, the coil drops to its 8 °C target, full dehumidification, drying completes.

### 7. Stall literature verification (DONE)

Sent the stall finding through a dedicated literature audit. Result:
- **Not explicitly named / mapped in published HPCD literature.** Standard practice has been to skip the unstable mid-r band; nobody reports a low-r optimum.
- **Closest prior**: Liu, Aziz, Kansha et al. 2019, *Energies* 12(16):3125 — designed a "unit-room" to *avoid* cold ambient air's influence on the evap. Engineered around the same physics without naming it.
- **Counterpoint**: Mohammadi, Tabatabaekoloor, Motevali 2019, *Energy* 170:149-158 — full RAR sweep on kiwifruit, monotonic improvement, no stall (warm climate).
- Standard r recommendation in HPCD literature: r ≈ 0.7-0.9.
- **DO NOT call this "cold-attractor bistability"** — overclaim (no hysteresis, no two stable branches).
- **DO call it** "approach-temperature-limited dehumidification" or "low-recirculation dehumidification deficit" or "X_eq trap" — defensible.
- Project's own `RESEARCH_PLAN.md` Section 3.2 already calls this "the valley of death" — colloquial fine for section heading, not for abstract.

### 8. Cleaned A r-sweep at KTM (DONE — finished after handoff was first written)

`outputs/r_sweep_A_clean/run_summary.csv`:

| r    | Time (h) | W_comp | W_fan | SEC (kWh/kg) | notes |
|------|----------|--------|-------|--------------|-------|
| 0.0  | 9.17 | 10.60 | 0.485 | 0.586 | open-loop |
| 0.80 | 10.98 | 9.94 | 0.452 | 0.550 | edge of stall band |
| 0.85 | 9.57 | 9.51 | 0.394 | 0.524 |  |
| 0.90 | 9.58 | 9.48 | 0.395 | 0.523 |  |
| 0.95 | 9.60 | 9.45 | 0.395 | 0.521 |  |
| 1.00 | 9.62 | 9.42 | 0.396 | **0.519** | best |

Monotone from r=0.85→1.0; flat plateau (~0.52). Best r=1.0 gives **−11.5%** vs open-loop. r=0.8 is the cold edge of the stall band at KTM (slow drying, +1.4 h).

### 9. Namche stall-band probe (DONE — and overturned by a follow-up r=1.0 probe)

`outputs/r_sweep_A_namche/run_summary.csv` (the first probe):

| r    | Status | Time | W_comp | m_water | message |
|------|--------|------|--------|---------|---------|
| 0.0  | OK | 8.3 h | 11.46 | 18.90 | dry, SEC=0.629 |
| 0.3  | **STALL DNF** | 24 h | 0.22 | 11.55 | impossible-cycle bypass |
| 0.5  | **STALL DNF** | 24 h | 0.08 | 8.89  | impossible-cycle bypass |
| 0.7  | **STALL DNF** | 24 h | 0.13 | 5.57  | impossible-cycle bypass |
| 0.8  | **STALL DNF** | 24 h | 0.28 | 4.16  | impossible-cycle bypass |
| 0.9  | **STALL DNF** | 24 h | 4.63 | 13.76 | partial drying |

The follow-up `outputs/r_sweep_A_namche_r1/run_summary.csv` then ran r=1.0 alone at Namche and converged cleanly: **SEC=0.433 kWh/kg, 10.20 h, W_comp=8.55 kWh** — the lowest Config A SEC of any of the four sites.

**Corrected reading.** Config A has **two viable operating modes**, separated by a stall band:
- **r=0 (open-loop)** — only viable mode at warm-humid sites where ω_amb is already moderate.
- **r=1.0 (fully closed)** — viable and best at cool→cold sites. With no ambient ingress, T_mix is dominated by warm humid exhaust → coil drops to its 8 °C target → full dehumidification → loop self-sustains.
- **r ∈ [0.3, 0.9]** is a thermodynamic dead zone at cold sites: cold ambient bleed drags T_mix below the evap coil floor (T_evap_min_C + DT_approach ≈ 0 °C), Q_evap collapses, the first-law constraint zeroes Q_cond, runaway cold-trap.

**Earlier "closed-loop HPCD non-viable at altitudes ≥ Namche" framing was wrong** and has been retracted; it came from probing the stall band without then testing r=1.0. The corrected story is published-defensible and stronger: cold sites force a binary choice between open-loop and fully-closed; partial recirculation (the standard HPCD recommendation of r ≈ 0.7-0.9 from warm-climate literature) is the *worst* choice at altitude.

**Implication for the headline matrix:** Config A should be run at **per-site best r** (see the consolidated table further down): BTN r=0; KTM/JSM/Namche r=1.0. This is one Config A column with four r-values in the production CSV, not a separate "A r-sweep" architecture. Matrix size stays at **11 configs** (the original plan); no new architectures need to ship for paper-1.

Consolidated plot: `outputs/config_A_r_sweep/SEC_vs_r_per_site.png` (script: `scripts/plot_config_A_r_sweep.py`).

Re-run if missing:
```bash
PYTHONPATH=src python scripts/run_solar_hp_configs.py --configs A --location kathmandu  --solar-areas 0 --recirc-values 0.0 0.8 0.85 0.9 0.95 1.0 --max-hours 24 --output-dir outputs/r_sweep_A_clean
PYTHONPATH=src python scripts/run_solar_hp_configs.py --configs A --location namche     --solar-areas 0 --recirc-values 0.0 0.3 0.5 0.7 0.8 0.9       --max-hours 24 --output-dir outputs/r_sweep_A_namche
PYTHONPATH=src python scripts/run_solar_hp_configs.py --configs A --location namche     --solar-areas 0 --recirc-values 1.0                            --max-hours 24 --output-dir outputs/r_sweep_A_namche_r1
PYTHONPATH=src python scripts/run_solar_hp_configs.py --configs A --location biratnagar --solar-areas 0 --recirc-values 0.0 0.7 0.85 0.9 0.95 1.0      --max-hours 24 --output-dir outputs/r_sweep_A_biratnagar
PYTHONPATH=src python scripts/run_solar_hp_configs.py --configs A --location jomsom     --solar-areas 0 --recirc-values 0.0 0.3 0.5 0.7 0.85 0.9 1.0  --max-hours 24 --output-dir outputs/r_sweep_A_jomsom
PYTHONPATH=src python scripts/plot_config_A_r_sweep.py
```

## B/C exhaust routing — resolved by code review

The user asked: where should the chamber exhaust go in B and C, can we dump it all into the evaporator? Before writing any new architecture, we audited the existing code paths in `dryer_solar_hp.py`:

- **B1 at r>0** (`simulate_config_B1_solar_before_cond`, line 2298): Mix → Evap → **Solar** → Cond. Solar collector sees warm-humid mix inlet → η drops. The bowl-shaped KTM B1 r-sweep (Section 3) reflects this combined penalty; not a "fair" closed-loop B1.
- **B2 at r=0** (`simulate_config_B2_solar_after_cond`, line 2286): delegates to `simulate_config_E_HRX_solar` with `d_variant="B2"`, `eps_HRX=0`; **locked at r=0** in code.
- **C1 at r>0** (`simulate_config_C1_solar_on_evap_source`, line 2679): Amb → Solar → Mix → Evap → Cond. Solar is consumed *before* mixing, but it's still on the main loop, not a separate side branch.
- **D2, E2, E3 already implement the exhaust→evap side-branch pattern via HRX** (with the side branch carrying sensible-only recovery into the evap source stream). The "semi-open Bx/B2x" idea is therefore not a new architecture; it is what D2/E2/E3 already do, with HRX providing the physical separation between the two air streams.

**Decision: no new Bx/B2x code for paper-1.** Matrix stays at the original **11 configs**. B and C stay at r=0 (open-loop, vent). The closed-loop story is told by:
- Config A at per-site best r (the four r-sweeps reported above), and
- D2/E2/E3 (the HRX-based semi-open architectures already in the matrix).

C1 remains as the "weak architecture reference" (solar on evap raises COP, but bounded compared to solar on cond).

**Verification of the BTN r=0.8 behaviour** (user-requested mid-session): at BTN r=0.8 the evaporator IS dehumidifying — Δω ≈ 3.7 g/kg per pass. But T_mix=32 °C is cooled to 11.7 °C then reheated to 45 °C, and chamber-inlet ω=8.6 g/kg vs ambient ω=8.4 g/kg ends up net no drying benefit. ~30% more W_comp for the same kinetics → r=0 wins at BTN. This is consistent with the consolidated per-site best-r table further down.

## Scope-creep flag (honest read)

The user asked mid-session **"are we going away from our paper?"** Resolution: matrix stays at the original **11 configs**, no new Bx/B2x. The closed-loop A branch (+1 over 2026-05-13's r=0 lock) was the only architecture change that shipped, and it folds into Config A at per-site best r (not a separate column).

Recommended discipline for the next session:
1. Lock the matrix at 11 configs, Config A at per-site best r.
2. Launch.
3. Defer Bx/B2x and any other architecture iteration to paper-2.

## Citations to fix in DRAFT.md before submission

- Mohanraj 2008 grape — doesn't exist; fix or drop.
- Mortezapour & Ghobadian 2009 saffron → 2012.
- Aktaş 2015 apple → 2009.
- Şevik 2013 mushroom = open-loop SAHPD → refuted, the paper compares open/closed/semi-open and finds closed best.

Add to DRAFT.md citation list:
- Liu, Aziz, Kansha et al. 2019, *Energies* 12(16):3125 — closest prior on the stall, "unit-room" cold-climate HP dryer.
- Mohammadi, Tabatabaekoloor, Motevali 2019, *Energy* 170:149-158 — warm-climate RAR sweep counterpoint.
- Zhu et al. 2025, *Foods* 14(15):2569 — current SAHPD review.
- Loemba et al. 2023, *Energy Sci Eng* 11(8) — banana closed vs open quantitative comparison.
- Wang et al. 2025, *Agriculture* 16(6):633 — apple HPD closed-loop precedent.

## Code state (files touched in this session)

| File | Change |
|---|---|
| `src/rq1/dryer_solar_hp.py` | (1) Added `_simulate_config_A_closed_loop()` helper. (2) Replaced r=0 hard-lock in `simulate_config_A_HP_only` with dispatcher. (3) `load_weather_data_raw` now accepts POA_Wm2 and promotes it to GHI_Wm2. |
| `scripts/fetch_pvgis_poa.py` | NEW — PVGIS-ERA5 POA fetcher (45° tilt). |
| `scripts/build_poa_standard.py` | NEW — merges POA into existing standard CSVs. |
| `scripts/plot_poa_vs_ghi.py` | NEW — winter/summer panel plot, verifies tilt. |
| `scripts/run_quarterly_sweep.py:97` | Prefers `_pvgis_standard_poa45.csv`. |
| `scripts/smoke_topology_parity.py:43` | Auto-selects POA file when present. |
| `scripts/run_solar_hp_configs.py:81-86` | POA path first in `possible_paths`. |
| `scripts/daily_batch_starts.py`, `scripts/quarterly_batch_starts.py` | `site_csv()` prefers POA file; renamed `start_GHI_Wm2` → `start_solar_Wm2`. |
| `data/ambient/*_pvgis_standard_poa45.csv` (4 files) | NEW — POA-merged weather. |
| `outputs/r_sweep/` | B1 r-sweep at KTM, A_solar=15. |
| `outputs/r_sweep_A/` | First A r-sweep (with stall band, KTM). |
| `outputs/r_sweep_A_clean/` | Cleaned A r-sweep at KTM (DONE; best r=1.0 @ SEC=0.519, −11.5%). |
| `outputs/r_sweep_A_namche/` | A stall-band probe at Namche (DONE; r=0 only — all r ∈ [0.3, 0.9] DNF). |
| `outputs/r_sweep_A_biratnagar/` | A r-sweep at BTN (DONE; r=0 wins SEC=0.450; all r ∈ [0.7,1.0] worse — ω_amb already high). |
| `outputs/r_sweep_A_jomsom/` | A r-sweep at JSM (DONE; **U-shape**: r=0 SEC=0.974, r=1.0 SEC=0.462 best, r=0.3→0.9 ALL DNF). |
| `outputs/r_sweep_A_namche_r1/` | Namche r=1.0 probe (DONE; converged, SEC=0.433 — overturned the "non-viable at altitude" framing). |
| `scripts/plot_config_A_r_sweep.py` | NEW — consolidated SEC vs r per-site plot + CSV; DNF marked with x's. |
| `outputs/config_A_r_sweep/SEC_vs_r_per_site.{png,csv}` | NEW — paper-figure-quality summary of the four r-sweeps. |
| `CLAUDE.md` (project root) | NEW — copied from `C:\Users\sarwa\Downloads\CLAUDE.md`; 4 behavioural sections (think before coding, simplicity, surgical changes, goal-driven). |

**Per-site best-r for Config A (consolidated):**
| Site | T_amb mean | r_best | SEC | Notes |
|---|---|---|---|---|
| Biratnagar | 18 °C | 0 | 0.450 | Warm-humid: ω_amb high, exhaust ω higher → closed-loop net wetter chamber inlet |
| Kathmandu | 12 °C | 1.0 | 0.519 | Cool-dry: recirc lifts T_mix, no cold-trap |
| Jomsom | 7 °C | 1.0 | 0.462 | U-shape: r=0 or r=1.0; partial-r cold-traps |
| Namche | −3 °C | **1.0** | **0.433** | r=1.0 WORKS and is best of all 4 sites; r ∈ [0.3, 0.9] DNF (partial-r dead zone) |

**Major narrative correction (2026-05-28 late):** the Namche r=1.0 probe rewrites the earlier "HPCD fails at altitude" framing. Config A has two viable operating modes:
- **r=0 (open-loop)** — wins at warm-humid (BTN) where ω_amb is already moderate.
- **r=1.0 (fully closed)** — wins at cool→cold (KTM, JSM, Namche). At full closure no cold ambient enters → no cold-trap → loop self-sustains.

Partial-r ∈ [0.3, 0.9] is a thermodynamic no-man's-land at cold sites (cold ambient ingress drags T_mix below the evap floor, runaway cold-trap).

Headline implication: **Namche r=1.0 SEC=0.433 is now the lowest of any Config A site**. B/D/E configs need to *beat* 0.433 at Namche, not "rescue" a stalled cycle. Honest, defensible baseline.
| `outputs/poa_validation/plots/` | POA vs GHI panels and validation overview/E2 plots. |

## What did NOT change in this session

- Chamber geometry (parallel, 1.5 cm gap, ρ=750 kg/m³) — unchanged from 2026-05-26 flip.
- Smoke parity test — still passes 5/5 with the new POA pipeline.
- Refrigerant (R134a), T_set (45 °C), product mass (3 kg dry / 22.5 kg fresh), 10 trays — unchanged.
- D / E config code — untouched.
- Supercomputer launch commands (in the "Tomorrow" section below) — still valid for whatever matrix is chosen.

## What failed and was abandoned

- "Open-loop SAHPD is the published standard" framing — refuted by 2020-2026 audit. Drop it from DRAFT.md if it appears there.
- A r ∈ {0.3, 0.5} as headline data points — physically degenerate (stall). Keep as a methodology figure only.
- "Cold-attractor bistability" terminology — overclaim. Use approach-temperature-limited dehumidification or X_eq trap instead.
- **"Closed-loop HPCD non-viable at altitudes ≥ Namche"** — written mid-session after the r ∈ [0.3, 0.9] stall sweep, retracted same day after the r=1.0 probe converged at SEC=0.433 (best of any Config A site). Do not repeat this framing.
- **"AC systems don't work at Namche"** — same lineage; refuted by both literature (cold-climate heat pumps work to −25 °C) and our own r=1.0 result. The actual model constraint is T_evap_min_C = −5 °C + DT_approach = 5 K → coil floor 0 °C; the cold-trap is a closed-loop dynamic at partial r, not a fundamental device limit.
- **Bx / B2x architectures** — proposed mid-session, dropped after code review showed D2/E2/E3 already implement the exhaust→evap side-branch pattern via HRX. No new code; deferred to paper-2 if a non-HRX semi-open variant is later motivated.

## What the next session should do (priority order)

The architecture/matrix scope is **closed**. The remaining work is launch plumbing + paper polish:

1. **Confirm the matrix decision is still: 11 configs, Config A at per-site best r** (BTN r=0; KTM/JSM/Namche r=1.0). One quick re-read of `outputs/config_A_r_sweep/SEC_vs_r_per_site.png` and the consolidated CSV is the verification.
2. **Wire per-site recirc into the runner**: `scripts/run_quarterly_sweep.py` and `scripts/run_solar_hp_configs.py` need to dispatch Config A's r per location (today they take a flat `--recirc-values` list). Smallest change: special-case Config A with a `LOCATION_TO_BEST_R = {"biratnagar": 0.0, "kathmandu": 1.0, "jomsom": 1.0, "namche": 1.0}` lookup in the runner. Verify the closed-loop branch in `dryer_solar_hp.py:_simulate_config_A_closed_loop` still runs for r=1.0 (already validated at Namche, KTM, JSM in the r-sweeps above).
3. **Citation cleanup in DRAFT.md** (4 fixes + 5 additions, all listed earlier in this file).
4. **SLURM job-array partitioning** in `scripts/run_quarterly_sweep.py`: add `--worker-id N --total-workers M`. ~15 min.
5. **Post-sweep aggregation script**: roll daily summary into per-(config, site, area) statistics for headline tables/figures. Doesn't exist yet.
6. **Q_cond peak vs 1-ton flag**: 4.065 kW peaks against the 4.0 kW `Q_cond_max_kW` informational flag at `src/rq1/heatpump.py:44`. Bump to 4.5 or leave noisy logs.
7. **Storage trim flag** `--summary-only` if disk pressure on Lund matters. Decision: trim ~95% bytes vs keep full per-step CSVs.
8. **Smoke parity 5/5** then **launch** the 11-config × 4-site × 9-area × 365-day matrix on Lund.

---

## (Carried forward from 2026-05-27) Locked launch commands

Once the matrix scope is decided, these still work — just edit the `--configs` list:

```bash
# 0. Regenerate batch starts on the supercomputer's PVGIS files (clean rerun)
PYTHONPATH=src python scripts/quarterly_batch_starts.py
PYTHONPATH=src python scripts/daily_batch_starts.py

# 1. Smoke parity — must pass 5/5 before launching
PYTHONPATH=src python scripts/smoke_topology_parity.py

# 2. Dry-run gate
PYTHONPATH=src python scripts/run_quarterly_sweep.py \
    --configs 0 A B1 B2 C1 D1 D2 D3 E1 E2 E3 \
    --solar-areas 5 8 10 12 15 18 20 22 25 \
    --batch-starts outputs/quarterly/daily_batch_starts.csv \
    --batches $(seq 0 91) \
    --dry-run

# 3a. RECOMMENDED: daily-yearly sweep (86,140 sims at 11 configs; bumps to ~94k at 12 configs)
PYTHONPATH=src python scripts/run_quarterly_sweep.py \
    --configs 0 A B1 B2 C1 D1 D2 D3 E1 E2 E3 \
    --solar-areas 5 8 10 12 15 18 20 22 25 \
    --batch-starts outputs/quarterly/daily_batch_starts.csv \
    --batches $(seq 0 91) \
    --output-dir outputs/paper1_daily_yearly

# 3b. Alternative: quarterly headline only (5,664 sims, faster)
PYTHONPATH=src python scripts/run_quarterly_sweep.py \
    --configs 0 A B1 B2 C1 D1 D2 D3 E1 E2 E3 \
    --solar-areas 5 8 10 12 15 18 20 22 25 \
    --output-dir outputs/paper1_quarterly
```

Note: at 12 configs (adding A r-sweep with 6 r values, A_solar=0 only since A has no solar), the increment is ~6 × 4 sites × 365 days = ~8,760 extra sims = ~95k total. At 13 configs (add Bx, B2x each with 9 solar areas), add ~2 × 9 × 4 × 365 = ~26k more = ~120k total. The runner already handles this; the only thing that changes is the `--configs` list and per-config `recirc_values` logic.

## Sourced ΔP references (locked 2026-05-27, still valid)

Placeholders in `DryerConfig` (config_solar_hp.py:317-328) replaced with values grounded in primary documents.

| Field | Value | Primary source | Notes |
|---|---|---|---|
| `dP_HRX_side_Pa` | 150 Pa | ASHRAE Handbook 2020 HVAC Systems & Equipment, Ch. 26 "Air-to-Air Energy Recovery", Table 3 / Fig. 5; Klingenburg GS-25 catalogue 140 Pa @ 300 m³/h corroborates | Per side; code at line 699 doubles for hot+cold so fan sees 300 Pa total on D/E configs |
| `dP_solar_Pa` | 40 Pa | Duffie & Beckman, *Solar Engineering of Thermal Processes*, 4th ed (2013), Ch. 6 §6.21 "Air Heaters" + worked Example 6.21.1; underlying channel-flow friction factor traces to Kays & London 1984 *Compact Heat Exchangers* 3rd ed | Low end of D&B range because per-channel mass flux ~0.011 kg/s into a 5-15 m² array is at the low end |
| `dP_cond_Pa` | 60 Pa | ASHRAE Handbook 2020 HVAC Systems & Equipment, Ch. 23, Fig. 18 (dry-coil air-side ΔP vs face velocity, 8-14 fpi); v^1.8 scaling per Ch. 23 text + Wang 2nd ed Ch. 15 | Chart starts at 2 m/s; our 1.0-1.5 m/s extrapolated via the endorsed scaling |
| `dP_evap_Pa` | 90 Pa | Same ASHRAE Ch. 23 + 30-50% wet-coil penalty | Wet (dehumidifying) coil |
| `dP_evap_stream_Pa` | 90 Pa | Same | Consistency with `dP_evap_Pa` (used on C1 second-blower path) |
| `dP_duct_Pa` | 60 Pa | ASHRAE Handbook 2021 Fundamentals, Ch. 21 "Duct Design", Table 10 friction chart + Table 14 elbow loss coefficients (C ≈ 0.22 for smooth-radius 90°) + Table 11 supply grille | 5 m run + 2 elbows + 1 grille at ~2.5 m/s duct velocity, 200 mm round, galv. steel ε = 0.09 mm |

**Caveats for reviewer-defence:**
- Coil ΔP at 1.0-1.5 m/s is extrapolated below ASHRAE Ch. 23's 2 m/s lower bound using the v^1.8 scaling that Ch. 23 endorses in text.
- Solar air-collector ΔP has no commercial-catalogue primary source (Apricus/SunMaxx publish water-side only); Duffie & Beckman + Kays & London is the deepest defensible cite.
- HRX `dP_HRX_side_Pa` is per side; code at `config_solar_hp.py:699` doubles for hot+cold so fan burden on D/E configs is 300 Pa.

**Impact on comparison:** HRX configs (D1/D2/D3/E1/E2/E3) gain ~200 Pa of fan ΔP (~25-30% main-blower power) vs old placeholders. Non-HRX configs net-neutral. HRX advantage shrinks slightly, which is the right direction for fairness.

## Files to look at first in the new session

1. `C:\Users\sarwa\.claude\projects\D--Masters-RQ5-Codex-Chatgpt-drying\memory\MEMORY.md` — current project state, decisions, references.
2. This file (`NEXT_SESSION_PROMPT.md`) for the 2026-05-28 deltas.
3. `outputs/r_sweep_A_clean/run_summary.csv` and `outputs/r_sweep_A_namche/run_summary.csv` — the two in-flight A sweeps; analyse first.
4. `src/rq1/dryer_solar_hp.py` — `_simulate_config_A_closed_loop` (new) and `simulate_config_A_HP_only` (dispatcher). Verify both paths still work.
5. `outputs/r_sweep/run_summary.csv` — B1 r-sweep table for reference.
6. `outputs/poa_validation/plots/poa_vs_ghi_*.png` — POA verification plots; refer to these when discussing solar-yield differences across sites.
7. `scripts/run_quarterly_sweep.py` — the runner; will need SLURM `--worker-id` patch.

---

## Behavioral guidelines

Tradeoff: these bias toward caution over speed. For trivial tasks, use judgment.

1. **Think before coding.** State assumptions explicitly. If multiple interpretations exist, present them — don't pick silently. If something is unclear, ask before writing code.

2. **Simplicity first.** No features beyond what was asked. No abstractions for single-use code. No "flexibility" that wasn't requested. No error handling for impossible scenarios.

3. **Surgical changes.** Touch only what you must. Don't refactor adjacent code. Match existing style. If you notice unrelated dead code, mention it — don't delete it.

4. **Goal-driven execution.** Transform tasks into verifiable goals. "Fix the bug" → "write a test that reproduces it, then make it pass". Loop until verified.

5. **No em-dashes / en-dashes.** The user dislikes AI-style dash connectors. Use commas, semicolons, parentheses, or sentence breaks.

6. **Verify before claiming "literature says X".** This session's biggest correction was a literature claim I made from memory that turned out to be partially wrong. When in doubt, search and quote — don't paraphrase from training data.

7. **Cite specifically.** Author, year, journal, volume / page if you have it. DOIs welcome. Vague "according to the literature" is not acceptable.
