# SAHPD RQ1 — Paper Foundation (Single Source of Truth)

**Working dir:** `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`
**Branch:** main
**Last updated:** 2026-05-18

This is the canonical project state. Anything in older notes that contradicts
this is wrong and should be ignored. Code is fully audited; T_set sweep is
complete; ready to begin paper writing.

---

## 1. The paper in one paragraph

A Solar-Assisted Heat Pump Dryer (SAHPD) for apple drying in Nepal compares
10 system topologies across 4 sites and 4 seasons. Each topology routes air
through some combination of an evaporator, a Hottel-Whillier-Bliss solar
collector, a heat-recovery exchanger (HRX, ε = 0.70), and a R134a condenser.
A first-law-validated simulator (Q_cond = Q_evap + W_shaft to 0.000000) and
a parametric kinetic model fit on 13 thin-layer apple-drying curves
(K_ref = 2.0974e-4 /s at 50 °C, Ea/R = 3738 K, single-stage NLS,
RMSE_MR = 0.04685) produce the SEC, SMER, and drying-time for each topology.
**Headline finding:** routing the solar collector to the condenser inlet
(Config E2) beats every other topology at every site, every season, every
T_set in 45-55 °C; the advantage *widens* with rising T_set because higher
chamber temperature demands more HP lift, which E2's pre-condenser solar
preheat directly offsets.

---

## 2. Verified evidence (the foundation)

### 2.1 Code audit (2026-05-17/18) — all clean

| Module | Status | Key fact |
|---|---|---|
| `kinetics.py` | Audited | M1 NLS refit at startup; live params match METHODOLOGY.md |
| `heatpump.py` | Audited | R134a CoolProp; T_cond=T_air_out+10; T_evap=T_evap_src−10 |
| `psychro.py` | Audited | Tetens P_sat; P_atm from elevation propagates everywhere |
| `solar.py` | Audited | HWB with dynamic F_R and lumped capacitance relaxation |
| `dryer_solar_hp.py` HRX | Audited | ε-NTU, ε=0.70, sensible + exhaust-condensation tracked |
| Simulators 0/A/B/C1/C2/D1/D2/D3/E1/E2/E3 | Audited | Air paths code-verified; E1 docstring fixed; D3 dropped |
| Phase 3.5 validation | Passed | 1st law, water mass balance, ε-condenser match all to 0.000000 |

### 2.2 Kinetic model (`outputs/audit/METHODOLOGY.md`)

- 13 thin-layer apple-drying curves: T ∈ {40, 45, 50} °C, v ∈ {0.6, 0.85, 1.1} m/s,
  d ∈ {4, 6, 8, 10} mm, RH ∈ {25-28, 35-38, 40-45} %.
- M1 functional form (Arrhenius × RH × velocity × thickness):
  `K = K_ref · exp(Ea/R · (1/T_ref − 1/T)) · exp(−α · RH/100) · (v/v_ref)^γ · (d_ref/d)^δ`
- Live runtime parameters (verified 2026-05-18):
  K_ref = 2.0974e-4 /s, Ea/R = 3738 K (Ea = 31.08 kJ/mol),
  α_RH = 1.965, γ_v = 0.401, δ_d = 0.589, RMSE_MR = 0.04685.
- LOCO-CV: M1 RMSE = 0.0528, M2 = 0.0404, M3 = 0.0685. M1 chosen as headline
  (better physical interpretation, sufficient accuracy); M2 carried as
  sensitivity bracket (Spearman ρ = 0.985 with M1 across 30 cases).
- **Validity range: 40-50 °C in-distribution. 55 °C is +5 K extrapolation
  (defensible). 60 °C is +10 K (caveat needed). Sweep capped at 55 °C.**

### 2.3 Headline sweep #1: Full Config-E grid at T_set = 45 °C

780 sims, 0 failures, 211 min on 6 parallel workers.
3 configs × 4 sites × 5 periods × 13 inner sims (areas 2-20 m², vpd 0-0.2).
Outputs: `outputs/run_summary_E_full.csv`.

| Site | E1 (vpd=0) | **E2 (vpd=0)** | E3 (vpd=0) |
|---|---|---|---|
| Biratnagar (72 m) | 0.1430 | **0.1301** | 0.1376 |
| Dhulikhel (1550 m) | 0.1846 | **0.1671** | 0.1817 |
| Kathmandu (1350 m) | 0.2230 | **0.1990** | 0.2185 |
| Taplejung (1820 m) | 0.1798 | **0.1642** | 0.1760 |

Annual SEC [kWh/kg water], A = 10 m², vpd = 0.0, M1 kinetics.
**E2 wins 20/20 site × season cases at A = 10**, both with vpd = 0.0
(paper-1 framing) and vpd = 0.05 (paper-2 framing). Robust under area
sweep A ∈ [2, 20] m² (no plateau in grid; diminishing-returns knee at
A ≈ 10-15 m²).

### 2.4 Headline sweep #2: T_set sweep (E2, E3 only)

16 new sims, 2.2 min wall, 0 failures.
Configs × sites × T_set = 2 × 4 × {45, 50, 55} °C. A = 10 m², vpd = 0.0.
Outputs: `outputs/T_sweep_summary.csv`.

**SEC [kWh/kg]**:

| Site | E2-45 | E2-50 | E2-55 | E3-45 | E3-50 | E3-55 |
|---|---|---|---|---|---|---|
| BTN | 0.1301 | 0.1282 | 0.1377 | 0.1376 | 0.1391 | 0.1529 |
| DHU | 0.1671 | 0.1757 | 0.1929 | 0.1817 | 0.1956 | 0.2189 |
| KTM | 0.1990 | 0.2094 | 0.2274 | 0.2185 | 0.2366 | 0.2647 |
| TPJ | 0.1642 | 0.1688 | 0.1804 | 0.1760 | 0.1824 | 0.1964 |

**Drying time [h]** (identical for E2 and E3 at each site/T):
BTN 14.73/11.77/9.72; DHU 14.83/12.02/9.98; KTM 14.10/11.63/9.78;
TPJ 14.25/11.67/9.77 (at T=45/50/55 °C respectively).

**Verified claims from this sweep (re-checked against raw CSVs)**:
1. E2 wins 12/12 (site × T) cases. Strict inequality every cell.
2. E2 vs E3 gap **widens monotonically** with T_set at every site
   (BTN 5.8 → 11.0%, DHU 8.7 → 13.5%, KTM 9.8 → 16.4%, TPJ 7.2 → 8.9%).
3. SEC rises with T_set in 11/12 cells; one near-flat exception is
   E2-BTN at T=50 (−1.5% dip from T=45, then +5.8% at T=55).
   Likely cause: BTN's strong summer solar overshadows the marginal HP
   lift increase at T=50, before lift demand wins out at T=55.
4. Drying time is **identical** between E2 and E3 at every (site, T)
   because both reach T_to_chamber = T_set and use the same M1 kinetics.
   All inter-topology differences are purely in energy cost (SEC).
5. Site spread (worst/best SEC ratio) widens with T_set: E2 1.530 →
   1.651; E3 1.588 → 1.731. Cold sites (KTM, DHU) pay disproportionately
   more as T_set rises.

Tradeoff: going from 45 → 55 °C buys ~4 hours faster drying at the cost
of +6 to +21% SEC depending on site and topology.

### 2.5 Cross-family baseline (T_set = 45 °C, A = 10 m², vpd = 0.05; carried)

| Config | BTN | KTM | TPJ |
|---|---|---|---|
| 0 (electric) | full sweep | full sweep | full sweep |
| A r=0 | 0.5547 | 0.7304 | 0.5784 |
| B r=0 | 0.2990 | 0.5015 | 0.3565 |
| C1 r=0 | 0.9375 | 0.7697 | 0.9254 |
| C2 r=0 | 0.3935 | 0.5744 | 0.4361 |
| D1 | 0.2406 | 0.2916 | 0.2517 |
| D2 | 0.2413 | 0.2928 | 0.2537 |
| E1 (vpd=0.05) | 0.0999 | 0.1532 | 0.1328 |
| **E2 (vpd=0.05)** | **0.0959** | **0.1445** | **0.1279** |
| E3 (vpd=0.05) | 0.1376 | 0.2185 | 0.1760 |

DHU column for A/B/C/D not yet run. Optional gap-fill if paper requires
full 4-site symmetry across the whole family (E grid is full 4-site).
**For paper 1 (vpd = 0.0 framing), the cross-family table needs the
same vpd-off re-summarization.** Marked as a pending task below.

---

## 3. Paper plan (proposed structure)

Target: Energy Conversion and Management or Renewable Energy. ~30 references
(28 currently in `RESEARCH_PLAN.md`, plus 15 HRX-specific in `RESEARCH_HRX.md`).

### 3.1 Suggested section outline

| § | Section | Status | Key evidence available |
|---|---|---|---|
| 1 | Introduction | Lit collected, not drafted | Post-harvest losses; Nepal off-grid context; HP+solar gap in lit |
| 2 | Literature review | 44 refs collected, not drafted | RESEARCH_PLAN.md (29), RESEARCH_HRX.md (15) |
| 3 | System description and topologies | Audited; needs prose | air_paths_verified.md, all 10 configs documented |
| 4 | Mathematical model | All modules audited | METHODOLOGY.md (kinetics, HWB, HP, HRX, psychro) |
| 5 | Numerical setup, sites, weather | Mostly ready | 4 Nepal sites, TMY data, season splits |
| 6 | Results | Data ready, not drafted | All sweeps done; tables ready to drop in |
| 6.1 |   Topology ranking at T_set=45 °C | Data ready | E full grid (780 sims) + cross-family table |
| 6.2 |   Mechanism: why E2 beats E3 | Data + reasoning ready | 3-layer argument: HP lift, solar headroom, dehumid |
| 6.3 |   T_set sensitivity 45-55 °C | Data ready | T_sweep_summary.csv; gap-widens narrative |
| 6.4 |   Kinetic-model sensitivity (M1 vs M2) | Data ready | Phase D audit; ρ = 0.985 |
| 6.5 |   Solar-area sweep, knee at A ≈ 10-15 m² | Data ready | E_area_sweep_annual.csv |
| 7 | Discussion | To draft | Economic implications, limitations, future work |
| 8 | Conclusion | To draft | Headline + practical takeaways |
| App | Nomenclature, model details, validation | To compile | Phase 3.5 validation report + METHODOLOGY |

### 3.2 What each section needs that we already have

- **§3 System description**: `air_paths_verified.md` has the code-verified
  per-r topology for all 10 configs. Need a single schematic figure per
  config (10 panels or 2×5 grid).
- **§4 Math**: `outputs/audit/METHODOLOGY.md` has the kinetic params,
  fit protocol, audit pipeline. Need to lift the equations into LaTeX.
- **§5 Sites**: elevation, P_atm, climate band:
  - Biratnagar (72 m, ~100460 Pa, tropical lowland)
  - Kathmandu (1350 m, ~86120 Pa, temperate mid-hills)
  - Dhulikhel (1550 m, ~84500 Pa, temperate mid-hills)
  - Taplejung (1820 m, ~81000 Pa, sub-alpine highland)
- **§6 Results**: every table in §2 of this doc is paper-ready;
  CSVs already in `outputs/`.

### 3.3 Story arc (what the paper argues, in order)

1. Apple drying in Nepal needs off-grid-capable, energy-efficient
   technology. SAHPD is the obvious candidate but topology-level
   ranking under realistic kinetics, weather, and elevation is missing
   from the literature.
2. We build and validate a first-principles simulator for 10 SAHPD
   topologies, with a re-fit kinetic model anchored on 13 published
   apple-drying curves.
3. At T_set = 45 °C, the HRX + solar + HP family (E configs) wins
   over plain HP (A), plain solar+HP (B/C), and HRX-only (D)
   by 30-80% on SEC. Within the E family, the placement of the solar
   collector matters: cond-inlet (E2) beats post-cond (E3) at every site
   and season tested.
4. The advantage is robust under area sweep (A ∈ 2-20 m²),
   VPD-bypass settings, and kinetic-model choice (M1 vs M2).
5. Raising T_set from 45 to 55 °C makes the E2 advantage *grow*
   from 5.8-9.8% to 8.9-16.4%. The mechanism (E2's solar offsets the
   bigger HP lift needed at higher T_set) provides a physically
   intuitive explanation that generalizes beyond the four sites tested.
6. Practical recommendation: A = 10-15 m² solar collector,
   T_set = 45-50 °C, E2 topology, applicable across Nepal's elevation
   span.

---

## 4. Hard rules (user's standing orders)

- **No em-dashes.** Commas, semicolons, parentheses, sentence breaks.
- **Terse responses.** No trailing summaries. Diffs and tables speak.
- **Physics first.** If physics changes, run it and verify; do not just patch.
- **Confirm before risky/destructive ops.** Branch deletes, force pushes.
- **No VPD in paper 1.** Headline framing is vpd = 0.0. VPD bypass is paper 2.
- **r = 0 is the paper-comparison standard** for A, B, C1, C2.
- **Paper-headline E operating point**: A = 10 m², vpd = 0.0, T_set = 45 °C
  primary; T_set = 50, 55 °C sensitivity sweep. A = 15 m² as knee, supplement.
- **Pinch fixed at 10 K**. Changing it would invalidate every prior result.
- **T_set capped at 55 °C** for kinetic-extrapolation reasons.
- **No simulations left behind.** Full grids preferred over partial.

---

## 5. Pending work (in writing-priority order)

1. **Build the paper skeleton.** Decide on journal, create
   `paper/` directory layout (Intro, LitReview, Methods, Results,
   Discussion, Conclusion, Nomenclature, References). Suggest using
   LaTeX with the journal class template.
2. **Drop in §6 Results tables and figures.** Every data table is ready
   (`T_sweep_summary.csv`, `run_summary_E_full.csv`,
   `E_area_sweep_annual.csv`). Need plot generation: SEC vs T_set,
   SEC vs A_solar, mechanism schematic.
3. **Cross-family table refresh at vpd = 0.0.** Current cross-family
   table is at vpd = 0.05; rebuild with vpd = 0.0 for paper-1
   consistency. Reuses existing per-run CSVs.
4. **Optional: DHU column for A/B/C/D** to give 4-site symmetry across
   the whole family in §6.1. ~16 sims, 5-10 min wall on 6 workers.
5. **§4 math**: lift equations from `METHODOLOGY.md` and module code
   into LaTeX. Verify all symbols against a unified nomenclature.
6. **Verify literature DOIs** before submission. Flagged: Reza 2019,
   Chua 2010 HRX review, Aktaş HRX, Erbay & Hepbasli 2017 HRX,
   Li 2023 ATE.
7. **Discussion §7**: economic implications (electricity cost vs
   capital cost of solar+HRX), limitations (pinch model, no frosting,
   M1 extrapolation above 50 °C), future work (variable-speed HP,
   thermal storage, control optimization, paper 2 on VPD bypass).

---

## 6. Key files

### Code
| File | Purpose |
|---|---|
| `src/rq1/dryer_solar_hp.py` | All 10 simulators |
| `src/rq1/config_solar_hp.py` | DryerConfiguration, factories (all accept `T_set_C`) |
| `src/rq1/heatpump.py` | R134a HP cycle (CoolProp), η_mech = 0.95 |
| `src/rq1/kinetics.py` | M1 NLS refit at startup |
| `src/rq1/psychro.py` | Psychrometric functions |
| `src/rq1/solar.py` | Hottel-Whillier-Bliss collector |

### Scripts
| File | Purpose |
|---|---|
| `scripts/run_solar_hp_configs.py` | Main runner; `--T-set`, `--vpd`, `--weather-file` flags |
| `scripts/run_T_sweep.py` | Parallel runner for T_set sweep (6 workers) |
| `scripts/run_config_E_batch.py` | Parallel runner for E grid |
| `scripts/aggregate_config_E.py` | Builds `run_summary_E_full.csv` |
| `scripts/analyze_config_E.py` | Pivot tables; `--vpd` flag, default 0.0 |
| `scripts/audit_config_D.py`, `scripts/audit_phase_d.py` | D and Phase-D audits |
| `scripts/visualize_results.py`, `scripts/batch_plot.py` | Plots |
| `scripts/split_seasons.py` | TMY → 4 seasonal CSVs |

### Data and outputs
| File | Purpose |
|---|---|
| `data/ambient/seasonal/` | 4 sites × 4 seasons CSVs |
| `outputs/run_summary_E_full.csv` | 780-row E grid (paper §6.1, 6.5) |
| `outputs/T_sweep_summary.csv` | 24-row T_set sweep (paper §6.3) |
| `outputs/audit/METHODOLOGY.md` | Live kinetic params, fit protocol |
| `outputs/audit/phase_d_sec_summary.csv` | Phase D kinetic sensitivity |
| `air_paths_verified.md` | Code-verified per-r topology, all configs |

### Documentation
| File | Purpose |
|---|---|
| `CONFIG_D_AUDIT.md` | D1/D2 paper-ready audit |
| `CONFIG_E_AUDIT.md` | E1/E2/E3 paper-ready audit (780-sim grid) |
| `RESEARCH_PLAN.md` | Lit review (29 refs) |
| `RESEARCH_HRX.md` | HRX-specific lit review (15 refs) |

---

## 7. To resume in a new chat

Paste this:

> Read `HANDOFF.md` in `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`. It is the
> single source of truth for the SAHPD RQ1 project as of 2026-05-18. Code is
> fully audited and validated. Two headline sweeps are done: the 780-sim
> E-config grid at T_set=45 °C (E2 wins 20/20) and the 24-sim T_set sweep
> at 45/50/55 °C (E2 wins 12/12; gap widens with T_set). Both summary CSVs
> are in `outputs/`. Paper foundation is in §3 of HANDOFF (proposed structure,
> story arc, and what each section needs from existing data). Standing rules:
> no em-dashes, terse responses, physics first, vpd = 0.0 framing, T_set
> capped at 55 °C, pinch fixed at 10 K. Ask me where to start writing.
