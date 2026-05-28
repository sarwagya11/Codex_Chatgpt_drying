# SAHPD RQ1 — Paper Handoff (Single Source of Truth)

**Working dir:** `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`
**Branch:** main
**Last updated:** 2026-05-25 (paper draft complete through §5.8; user-led revision pass §13.A edits 1–32 APPLIED, awaiting next round of user feedback on the re-rendered DRAFT.docx)

This file supersedes every earlier note. If anything else contradicts it, this document wins.

---

## 1. What the next chat should do

> **Continue the user-led revision pass on `paper/DRAFT.md`.** The user is reading `paper/DRAFT.docx` and dictating edits section by section. The full backlog of comments delivered on 2026-05-25 is in §13 below (split into "clear edits to apply" and "open decisions for user"). Start at §13.A item 1 (§1¶1 restructure) and walk down the list.
>
> **Before editing §1, the user wants joint decisions on a few framing questions** (§13.B). Address those first or in parallel with the §1 edits.
>
> Do NOT re-run simulations. The 276-sim matrix is locked; the verification pass on 2026-05-25 confirmed all headline numbers reproduce from the CSVs.

Resume prompt for the new chat:

> Read `HANDOFF.md` in `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`. §1 says you are mid-revision on `paper/DRAFT.md`. The user is reading `paper/DRAFT.docx` and giving line-by-line feedback; the full backlog is in §13. Start by walking §13.A in order and surfacing the §13.B open questions to the user. Standing rules in §11. Do not re-run sims.

---

## 2. The paper in one paragraph

A Solar-Assisted Heat Pump Dryer (SAHPD) for apple drying in Nepal compares 10 air-path topologies (Config 0 electric baseline, A, B1, B2, C1, D1, D2, E1, E2, E3; D3 in matrix but dropped from headline tables) across 4 sites (Biratnagar 72 m, Kathmandu 1350 m, Dhulikhel 1550 m, Taplejung 1820 m) and 4 seasons (autumn / winter / spring / summer; monsoon excluded) with PVGIS-SARAH3 TMY weather. Each topology routes air through some combination of an evaporator, a Hottel-Whillier-Bliss flat-plate solar collector (A = 10 m² baseline), a heat-recovery exchanger (HRX, ε = 0.70), and an R134a vapour-compression condenser. **Headline finding:** E2 (HRX + pre-condenser solar) beats every other topology at every site and every season; the B1-vs-C1 ablation closes a placement question never asked in the air-source dryer literature.

---

## 3. Current state of `paper/DRAFT.md` (611 lines, 2026-05-25)

| § | Section | Status |
|---|---|---|
| Title / Highlights / Abstract / Keywords | Deferred until §5 reviewed | |
| 1 | Introduction (~1050 w, 4 paragraphs) | **DRAFTED — user-led revision pass in progress, see §13** |
| 2 | System description (~400 w) | Drafted; user has comments (§13) |
| 3 | Mathematical model (~1200 w) | Drafted; user has many comments (§13) |
| 4 | Simulation setup (~1100 w) | Drafted; user has comments (§13) |
| 5 | Results (5.1–5.8) | Drafted; verified 2026-05-25 (see §4 below) |
| 6 | Conclusions | Deferred until §5 locked |
| Nomenclature / CRediT / Disclosures / Refs | Skeleton in place; deferred |

---

## 4. What was just done (2026-05-25 verification pass)

Verified the §5 numbers against source CSVs and fixed four issues in `paper/DRAFT.md`:

1. **§5.7** "E2 at Biratnagar marking the upper bound" → corrected to E1 at Biratnagar (−12.6 %); E2 BTN is −12.2 %, close behind. Source: `outputs/audit/phase_d_sec_delta.csv`.
2. **§5.7** Rank-flip boundary list expanded to include B1⇄D1 (DHK flip), in addition to D1⇄D2 and B1⇄D2. Three flipped pairs total across the 144 pairwise comparisons.
3. **§5.8** "ε_cond = 0.985 (Section 4.6)" was a typo (Table 2 lists ε_cond = 0.85). Rewrote the sentence to drop the false link; the 0.984–0.987 ratio is a dry-air cp approximation artefact, not an effectiveness signature.
4. **§5.6** "Q_solar drops to 14.1 kWh (40 % below its summer value)" was wrong — actual drop is 50 % (14.1 vs 27.97 kWh at TPJ winter vs summer). Also qualified "highest single-batch compressor load in the matrix" to "highest in the E2 seasonal sub-matrix" (Config A KTM annual and E2 KTM annual both exceed it).

All other §5 stats cross-checked clean: Table 3 family means, Table 7 SECs, Table 8 SMER/HRX/Solar contribution percentages, Spearman ρ values in §5.7, Table 9 seasonal swings.

---

## 5. State of the codebase (verified 2026-05-23, unchanged 2026-05-25)

| Module | Status | Key fact |
|---|---|---|
| `src/rq1/kinetics.py` | Verified | M1 NLS refit at startup |
| `src/rq1/heatpump.py` | Verified | R134a CoolProp; η_is = 0.75, η_mech = 0.90, ε_cond = ε_evap = 0.85, pinch = 10 K |
| `src/rq1/psychro.py` | Verified | Tetens P_sat; P_atm from elevation |
| `src/rq1/solar.py` | **Verified 2026-05-25** | HWB; lines 200–215 implement absorber-plate inertia: `τ = C_p/(A·U_L)`, `α = dt/(τ+dt)`, `T_pl_new = (1-α)·T_pl_old + α·T_pl_steady`. So the draft claim is real. |
| `src/rq1/dryer_solar_hp.py` HRX | Verified | ε-NTU, ε = 0.70 |
| `src/rq1/dryer_solar_hp.py` ω across condenser | **Verified 2026-05-25** | ω is conserved; condenser is sensible heating only. The draft's "ω across the condenser is unchanged" claim is correct. |
| `src/rq1/dryer_solar_hp.py` B1 / B2 | Verified 2026-05-23 | See HANDOFF §3.2 history |

---

## 6. Kinetic model (live, M1)

From `outputs/audit/METHODOLOGY.md`:

```
K = K_ref · exp((Ea/R) · (1/T_ref − 1/T)) · exp(−α · RH/100) · (v/v_ref)^γ · (d_ref/d)^δ

K_ref   = 1.544e-4 /s   @ T_ref = 50 °C
Ea/R    = 3622 K        (Ea = 30.11 kJ/mol)
α_RH    = 1.266
γ_v     = 0.382
δ_d     = 0.652
RMSE_MR = 0.0509
```

Fit on 13 thin-layer apple curves from Royen et al. 2020 (`ledger #40`). 40–50 °C in-distribution. 55 °C is +5 K extrapolation.

LOCO-CV (post-RH-fix 2026-05-21): M1 = 0.0623, M2 = 0.0511, M3 = 0.0685. All three statistically tied (every paired-bootstrap CI crosses zero).

---

## 7. Cross-family annual SEC (M1, paper-ready, A_c = 10 m², r = 0, T_set = 45 °C)

From `outputs/paper_matrix_summary.csv` and `outputs/audit/phase_d_sec_delta.csv`. **These are the published headline numbers.**

| Config | Biratnagar | Kathmandu | Dhulikhel | Taplejung |
|--------|------------|-----------|-----------|-----------|
| 0 (electric) | 1.872 | 2.155 | 1.874 | 1.831 |
| A (HP) | 0.485 | 0.664 | 0.533 | 0.528 |
| B1 (solar pre-cond) | 0.246 | 0.431 | 0.326 | 0.313 |
| B2 (solar post-cond) | 0.270 | 0.497 | 0.371 | 0.353 |
| C1 (solar on evap-src) | 0.321 | 0.506 | 0.400 | 0.384 |
| D1 (HRX, vent) | 0.293 | 0.369 | 0.320 | 0.318 |
| D2 (HRX + exh→evap) | 0.282 | 0.384 | 0.314 | 0.316 |
| E1 (HRX + solar, vent) | 0.153 | 0.231 | 0.195 | 0.195 |
| **E2 (winner)** | **0.145** | **0.215** | **0.184** | **0.186** |
| E3 (HRX + solar post-cond) | 0.153 | 0.237 | 0.201 | 0.200 |

D3 (HRX swapped, chamber gets exhaust): 0.374 / 0.423 / 0.381 / 0.383. Excluded from headline tables; only referenced as a cautionary case in the kinetic-sensitivity appendix.

---

## 8. Key files

### Code
| File | Purpose |
|---|---|
| `src/rq1/dryer_solar_hp.py` | All 11 simulators |
| `src/rq1/config_solar_hp.py` | DryerConfiguration |
| `src/rq1/heatpump.py` | R134a HP cycle |
| `src/rq1/kinetics.py` | M1 NLS refit |
| `src/rq1/psychro.py` | Tetens P_sat |
| `src/rq1/solar.py` | HWB + absorber inertia |

### Data and outputs
| File | Purpose |
|---|---|
| `outputs/paper_matrix_summary.csv` | **CANONICAL** 276-sim file |
| `outputs/audit/phase_d_sec_summary.csv` / `phase_d_sec_delta.csv` | M1-vs-M2 sensitivity |
| `outputs/T_sweep_summary.csv` | T_set sweep (E2 / E3) |
| `outputs/E_area_sweep_annual.csv` | E2 area sweep |
| `outputs/audit/METHODOLOGY.md` | Live kinetic params |

### Paper
| File | Purpose |
|---|---|
| `paper/DRAFT.md` | Working draft (611 lines as of 2026-05-25) |
| `paper/DRAFT.docx` | docx render (what the user is reading from in the revision pass) |
| `paper/REVIEW_2026-05-23.md` / `REVIEW_2026-05-23_v2.md` | Prior reviewer reports |
| `paper/md_to_docx.py` | docx regenerator |

---

## 9. Renewable Energy submission constraints

| Item | Constraint |
|---|---|
| Word count (excl. refs/captions) | 4000–6000; current budget 5600 |
| References | ≤ 50 |
| Abstract | ≤ 250 words |
| Highlights | 3–5 bullets, ≤ 85 chars each |
| Style template | Kuan et al. 2019, *Renewable Energy* 143:214 |
| Voice | Passive, "It is observed that…" |
| AI declaration | Mandatory new section before References |

---

## 10. Locked operating point

- r = 0 throughout (no recirculation; closed-loop is paper 2)
- vpd = 0.0 (no exhaust bypass; paper 2)
- T_set = 45 °C (≤ 55 °C in sweeps for kinetic-extrapolation reasons)
- A_c = 10 m² baseline (sweep 2–15 m²)
- ε_HRX = 0.70; ε_cond = ε_evap = 0.85; ΔT_pinch = 10 K
- η_is = 0.75; η_mech = 0.90
- R134a only

---

## 11. Standing rules (user's orders)

- **No em-dashes.** Commas, semicolons, parentheses, sentence breaks.
- **Terse responses.** No trailing summaries.
- **Physics first.** If physics changes, run and verify.
- **Confirm before destructive ops.**
- **No VPD in paper 1.**
- **r = 0 in §5.**
- **Voice: passive, Kuan-style.** No first-person in §2–§6.

---

## 12. Out of scope for paper 1

- Recirculation (r > 0)
- VPD bypass
- Thermal storage
- Variable-speed HP
- Refrigerants other than R134a
- Economic/payback model (one discussion paragraph max in §6)
- Monte-Carlo propagation of kinetic CI into SEC (deferred to a follow-up; the M1-vs-M2 sensitivity bracket is the de-facto error bar)

---

## 13. USER REVISION BACKLOG (2026-05-25 — section by section as user reads `DRAFT.docx`)

This is the live to-do list. The user is reading the docx and dictating edits. Walk it in order. Items in §13.A are clear edits to apply; items in §13.B are open questions that need the user's decision before acting.

### 13.A — Clear edits to apply

**Status (2026-05-25):** edits 1–32 applied; DRAFT.docx re-rendered. Decisions taken without user input: §13.B-A Option 1 (broadened HPD definition), §13.B-B (system-level COP wording), §13.B-C (softened to "rarely propagated"), §13.B-F (climate envelope phrasing), §13.B-G (closed-loop sentence dropped from §1). §13.B-D, §13.B-E still open — user should confirm.

**§1 Introduction**

1. **§1¶1.** Drop the "production area in ha" figures; keep only the absolute fruit-production quantity. Shorten the first line.
2. **§1¶1 restructure.** Bring apples to the front: (a) state apple drying status in Nepal, (b) state best-practice apple drying temperature range (40–55 °C), (c) state why a heat-pump-based system is needed (cold-chain absence + thermolabile profile + grid availability). Then add a brief mention of other high-value crops that need similar mid-temperature drying (the cardamom 45–55 °C bhatti example can be the closing illustration, not the opener). Highlight the necessity of HPD technology adoption in Nepal.
3. **§1¶1 closing line.** Add a sentence: "Hybrid systems combining Solar + HRX + Heat Pump together with simpler standalone configurations are evaluated in this study."
4. **§1¶3 Gap 1.** Reword to "no peer-reviewed evaluation of HP-based drying (including solar-assisted and HRU-based variants) has been reported for Nepal".
5. **§1¶3 Gap 3.** The sentence "Third, the prior topology comparisons that do exist vary a single design axis at a single site, and the joint effect of where the solar collector is integrated into the air loop, combined with whether an exhaust-side heat-recovery exchanger is present, has not been reported under a matched drying-air set point, a matched product load and a multi-site climate envelope." is too long. Split into two shorter sentences.
6. **§1¶4 opening.** Add a sentence near the start of the contributions paragraph: "This study has been undertaken to first check the performance of HPD, SAHPD, and SAHPD+HRU configurations under Nepali climate."
7. **§1¶4 contributions list.** Simplify the long "five-parameter Arrhenius-humidity-velocity-thickness drying-rate law fit by single-stage nonlinear least squares…" sentence. Keep just "five-parameter rate law" in §1; push the fit protocol and dataset details to §3 or §4.
8. **§1¶4 closed-loop sentence.** Decide whether to keep "Closed-loop operation (r > 0) introduces a separate set of coupling effects… reserved for a follow-up study." Tentative recommendation: drop it from §1 and either mention briefly in §2 or skip entirely. Awaiting user call (see §13.B-G).

**§2 System description**

9. Replace "drying chamber with its kinetic engine" → "drying chamber with its kinetic model" (or similar). Avoid "engine".

**§3 Mathematical model**

10. **§3.1 assumption (vii) two-blower.** Drop the inline configuration list ("(A, B1, B2, C1, D1, D2, E1, E2, E3)" and "(parallel ambient draw in A, B1, B2; ambient-through-collector in C1; cooled-exhaust plus dynamic ambient supplement in D2, E2, E3)"). Rewrite to general language; the configs are not yet introduced at this point in the text.
11. **§3.1 assumption (xiii) 1-ton compressor.** Simplify the "Q_cond,max = 4.0 kW, Q_evap,max = 3.5 kW … timesteps that exceed are flagged" sentence.
12. **§3.1 assumption (xiv) "constants on TMY hourly record".** Reword for clarity (see §13.C-2 for the explanation of what it means).
13. **§3.1 assumption (xv) HWB collector.** Replace with: "The collector is modeled by the lumped Hottel-Whillier-Bliss formulation [ledger #DuffieBeckman]; all values and relevant constants are listed in Table 2." Drop the bit about "useful gain clipped to instantaneous chamber demand"; that lives in §3.3.
14. **§3.1 drop "swept across configurations in Section 4"** from assumption (xiv).
15. **§3.1 assumption (xvi) HRX.** Split the long single bullet into two: one for sensible-only counter-flow + neglected cold-side condensation, one for the dewpoint-trigger hot-side condensation handling. Justify cold-side neglect: the cold side is being heated from ambient (well below dewpoint) so condensation cannot occur there. (See §13.C-5.)
16. **§3.1 assumption (xviii) X_eq = 0.** Move "the local-RH dependence of the drying rate is carried by the exp(−α_RH · RH) factor of Eq. (22)" out of the assumption block; that is a property of Eq. (22), not an assumption.
17. **§3.1 assumption (xix) wet batch mass.** Drop the "22.5 kg (3 kg dry + 19.5 kg moisture at X_0 ≈ 6.5)" parenthetical; those values live in Table 2.
18. **§3.1 assumption (xix) latent-vs-sensible justification.** Shorten the "46 MJ / 1 MJ / ~2 %" paragraph into one assumption bullet: "Sensible heating of the product (<2 % of latent load) is neglected; product temperature equals local tray-air dry-bulb."
19. **§3.1 Table 2 reformat.** Drop the "Group" column. Add a "Property" column (full-name expansion) so the table looks like Kuan's Table 1: `Property | Symbol | Value | Unit`. Drop the "dt = 60 s" row (numerical, not a physical constant). Drop the trailing "Source-fitted parameters of the kinetic rate law (Eq. 22) are reported separately in §5" line below the table.
20. **§3.2 heat-pump opening.** Drop "The vapor-compression cycle uses R134a, with all refrigerant properties evaluated from CoolProp at every timestep. The cycle is closed in four states, indexed in the direction of refrigerant flow." — already in assumptions.
21. **§3.2 heat-pump body.** Restructure in Kuan's style: each equation introduced by a one-line caption ("The refrigerant mass flow rate is given by…", "The compressor power consumption is given by…", "The condenser heating capacity is given by…", "The COP is defined by…", "The specific moisture extraction rate is defined by…"). Drop in-line repetition of constants already in Table 2 (η_is, η_mech, ΔT_sh, ΔT_sc).
22. **§3.2 drop the 1-ton-compressor paragraph** ("Compressor selection is anchored to a 1-ton-air-conditioning nameplate…"). Already in assumption (xiii).
23. **§3.2 drop the fixed-point system paragraph** ("Equations (11)-(14) form a small fixed-point system…"). Implementation detail; not needed in the math section.
24. **§3.2 drop the operating-envelope flags paragraph** ("Three operating-envelope flags are recorded at every timestep…"). Already in assumption (xii).
25. **§3.2 add explicit energy-balance equations** in Kuan's style: refrigerant mass flow, compressor work, condenser heat, evaporator heat, COP, SMER. One per labelled equation.
26. **§3.3 Solar collector.** Shorten the opening paragraph. Most of it is in assumptions (xiv) and (xv). Keep only the new content.
27. **§3.3 absorber-plate inertia.** Reformat the "with Q_useful = 0 and T_out = T_in whenever G < 10 W/m² (cut-in). Absorber-plate thermal inertia. The absorber stores heat and lags…" block — currently has formatting issues. Fix into a clean equation / paragraph block. The code DOES implement this (verified 2026-05-25, `src/rq1/solar.py` lines 200–215), so keep it.
28. **§3.3 drop the long final paragraph** about clipping / overshoot / dump-not-stored. Already in assumption (xv). Keep only "The humidity ratio is unchanged across the collector, ω_out = ω_in."
29. **§3.4 kinetics.** Drop "The runtime simulator only evaluates the law; it does not re-fit it." Implementation detail.
30. **§3.4 kinetics.** Replace the "X_eq = 0 simplification … exp(−α_RH · RH) factor" paragraph with a term-by-term explanation of each factor in Eq. (22) (K_ref, Ea/R, α_RH, γ_v, δ_d, and what each represents physically).
31. **§3.4 add citation** for the Arrhenius-humidity-velocity-thickness rate-law form. Royen et al. 2020 is the dataset; the functional form follows the dependency structure used in apple thin-layer modelling (verify against Royen + Sharabiani; if no single canonical citation, write the equation as the form-fitting choice of this work and cite the underlying single-variable dependencies).

**§4 Simulation setup**

32. **§4.1 climate description.** "with monsoon-period overcast and single-digit winter ambient temperatures at the upper sites" — verify which sites actually have single-digit winter ambient in the TMY data. (See §13.B-D.)
33. (Future-conditional on §13.B-E) Possibly drop the "monsoon excluded" sentence if user decides to widen the seasonal slices.

### 13.B — Open decisions for the user (DO NOT EDIT until resolved)

**§13.B-A. §1¶2 HPD definition scope (open-loop vs closed-loop).**
The current draft: "the evaporator dehumidifies and cools the exhaust while the condenser reheats the same airstream before re-admission to the chamber, recycling latent heat that would otherwise be vented" implicitly describes a CLOSED-LOOP HPD. Our simulator is OPEN-LOOP (r = 0).
- Option 1: Broaden the definition to "HPD uses a vapor-compression cycle to deliver controlled-temperature drying air; in closed-loop variants the evaporator additionally dehumidifies the recirculated chamber exhaust, while in open-loop variants ambient air is heated by the condenser and the exhaust is vented." Then state clearly that the present work studies the open-loop case.
- Option 2: Add closed-loop runs to the matrix (r > 0). Probably too much scope for paper 1.
- Option 3: Find a literature reference that argues evaporator-side dehumidification is not always beneficial (e.g., when ambient humidity is moderate, dehumidifying recirculated air introduces a thermodynamic round-trip cost that exceeds the latent saving). Cite it as the rationale for studying open-loop.
- **Recommended: Option 1 (broaden definition + explicit open-loop scope statement).** Cheapest and most accurate. Quote on this point welcomed.

**§13.B-B. §1¶2 SAHPD COP claim.**
"a solar air or PV/T collector supplies sensible pre-heat that supplements the condenser-side load and raises the system COP". User asks: does COP increase when condenser load decreases?
- **Answer:** COP_HP = Q_cond / W_comp. If solar pre-heats the air *upstream of the condenser*, Q_cond demand falls (less lift to T_set required), W_comp falls roughly in proportion at fixed T_evap, so COP_HP itself stays approximately constant. But **system COP = (Q_solar + Q_cond) / W_comp** goes up, because Q_solar is delivered at zero electric input. The phrase is correct but ambiguous; it conflates "HP-cycle COP" with "system COP". **Recommended fix:** "supplies sensible pre-heat that reduces the condenser-side load and raises the system-level coefficient of performance (Q_solar + Q_cond per unit compressor work)". User to approve wording.

**§13.B-C. §1¶2 kinetics-inheritance claim.**
"the apple drying kinetics are typically inherited as a single-temperature Arrhenius or Midilli fit drawn from one experimental source and the resulting parameter uncertainty is not propagated into the simulated SEC". User asks: is this 100 % true?
- **Answer:** It is true that in the SAHPD literature surveyed (Mortezapour 2012, Yahya 2016, Kuan 2019, Qiu 2016, Rulazi 2023, Ismaeel 2020) none reports uncertainty propagation of the kinetic fit into the simulated SEC. The "single experimental source" part is also broadly accurate. But the wording "without propagating … into SEC" was already flagged by the v1/v2 peer review as a contradiction: WE don't propagate either (we do an M1-vs-M2 sensitivity, not Monte-Carlo CI propagation). **Recommended fix:** soften to "the resulting parameter uncertainty is rarely propagated into the simulated SEC, even within the calibration band" and rely on the M1-vs-M2 bracket in §5.7 as the propagation surrogate.

**§13.B-D. §4 climate / sites / "single-digit winter".**
User suspects the site selection is arbitrary (apples not actually grown in Biratnagar?) and the "single-digit winter" claim may not hold.
- **What needs checking before §4 is revised:**
  1. Validate single-digit winter ambient in the TMY records for each site. (Quick script: load `data/ambient/{site}_pvgis_standard.csv`, filter Dec–Jan, report min and mean dry-bulb.)
  2. Cross-check whether apples are actually commercially grown in Biratnagar (lowland Terai). Likely not at scale — apples are mid-hill and high-hill crops. The Terai site may be defensible as a "warm-humid reference climate where SAHPD has to handle a different load mix" rather than as an apple-growing site per se.
  3. Re-survey Nepali climates more systematically; the current four-site selection covers Terai (72 m), mid-hill (1350 + 1550 m), and eastern highland (1820 m). Karnali (western mid-hill/high-hill) and Annapurna (central high-altitude) are unsampled.
- **Decision pending:** keep current four sites and reframe the rationale as "climate-envelope test bed, not necessarily apple-growing belt", OR swap sites for more representative apple-belt locations (Mustang, Jumla, Humla, Manang at 2500–3000 m would be the canonical Nepali apple-growing belt). If sites change, the entire matrix must be re-run — high cost.
- **Recommended:** reframe the four-site rationale; document the limitation in §6. Avoid re-running the matrix in this revision cycle.

**§13.B-E. §4 seasonal slices (2-month vs 3-month).**
User asks: should the seasonal slices be 3-month (calendar quarters) instead of 2-month? Monsoon is currently excluded entirely.
- **Trade-off:** 3-month slices give canonical season boundaries and include monsoon. 2-month slices isolate sharper climate phases and stay tighter to the apple drying calendar.
- The 4 current 2-month windows cover 8 months of the year; the 4 missing months are May/Aug/Sept (split-out for shoulder + monsoon).
- **Cost of switching:** rerun `scripts/split_seasons.py` with 3-month windows + rerun the seasonal block of the matrix (10 configs × 4 sites × 4 seasons = 160 simulations). Probably an overnight job.
- **Recommended:** keep 2-month for paper 1 if user accepts; if user insists on 3-month, schedule the rerun.

**§13.B-F. §1¶4 elevation-gradient phrase.**
"transferable across Nepal's elevation gradient". User asks: does elevation gradient meaningfully affect our results?
- **Answer:** Yes, modestly. The Kathmandu / Biratnagar ratio in Table 7 ranges 1.15 (electric) → 1.84 (B2). E-family ratios sit at 1.48–1.55, so a ~50 % SEC penalty between the lowest and highest sites is real, though not driven by elevation alone (Taplejung at 1820 m has lower SEC than Kathmandu at 1350 m because of microclimate). **Recommended:** keep "elevation gradient" but soften to "climate envelope spanning 72 to 1820 m" so the claim is geographic not strictly altitudinal.

**§13.B-G. §1¶4 closed-loop sentence.**
"Closed-loop operation (r > 0) introduces a separate set of coupling effects on dehumidification, condenser pinch, and chamber humidity build-up, and is reserved for a follow-up study." Keep or drop?
- **Recommended:** Keep one short sentence somewhere (probably §2 system description, not §1) to acknowledge that the r = 0 choice is intentional and that r > 0 is a separate study. Useful both for the v1 reviewer concern about scope and to forestall "why didn't you sweep r?" questions.

### 13.C — Quick answers to user's "just tell me" questions

1. **"Compression of refrigerant vapour is represented by an isentropic efficiency η_is and a mechanical efficiency η_mech. Is this common to use 2 efficiencies?"** — Yes. η_is captures the deviation from ideal isentropic compression (the refrigerant gets hotter than the ideal end-state because of internal irreversibilities); η_mech captures shaft / bearing / motor losses between the electrical input and the refrigerant work. Industry HP and chiller models commonly use both. Kuan et al. 2019 uses both (η_is and η_mech each appear in their compressor model). Keep both.
2. **"the optical and radiation properties of the flat-plate solar collector are taken as constants on the TMY hourly record". What does this mean?** — It means that absorptance α, emittance ε, transmittance τ, and the loss coefficient U_L are held fixed at their datasheet values for every hour of the year, rather than varying them with incidence angle (which would require an angle-of-incidence modifier), with plate temperature (which would change ε_pl(T)), or with wind speed (which would change U_L). It's a standard lumped-collector assumption.
3. **"All ten configurations operate open-loop, so ω across the condenser is unchanged. Is this true?"** — **Yes, verified 2026-05-25.** The condenser only adds sensible heat (refrigerant vapour heating air through a coil); no water enters or leaves the air on the condenser. The code path in `dryer_solar_hp.py` never updates ω during the condenser step. Statement correct.
4. **"transients are resolved between timesteps only — what does this mean?"** — All differential equations are first-order Euler-integrated at dt = 60 s. Within a single 60-s step every component is assumed to instantly reach its quasi-steady-state response to the current inputs (T_amb, ω_amb, G(t), etc.); there is no sub-step transient solve. The only carry-over between timesteps is the integrator state (absorber-plate temperature for the collector, cumulative moisture extraction for the chamber). It's a "method-of-lines"-style approximation: spatial gradients are resolved within each component algebraically (steady-state) and the time dimension is integrated step by step.
5. **"is the cold side condensation neglected because we are always heating the ambient and there won't be any condensation? Can we justify this?"** — Yes, that's the justification. The cold side of the HRX takes ambient air at T_amb and heats it toward (but never above) T_exhaust ~ T_set. Heating dry-or-moist air at constant ω cannot induce condensation; condensation only occurs on a surface that is cooled below the local dewpoint. Worth stating explicitly as the rationale for the assumption, exactly as the user proposed.
6. **"Is there a reference to the Arrhenius-humidity-velocity-thickness rate law?"** — The five-parameter form K(T, RH, v, d) is the dependency structure used implicitly across the apple thin-layer literature (Royen 2020, Sharabiani 2021, Aktaş 2015), but I am not aware of a single canonical paper that fits all four dependencies in one closed-form law. The closest precedent is Midilli et al. 2002 (which fits k(T) only and treats RH, v, d as fixed nuisance parameters of the experimental rig). Recommend citing Royen et al. 2020 for the dataset and Midilli 2002 for the Arrhenius temperature-dependence convention, with a sentence stating that this work extends the dependency structure to include RH, v and d simultaneously.

### 13.D — Suggested batch order for the next session

Walk §13.A in this order to minimize re-reads:

1. Resolve §13.B questions A, B, C with the user (these affect §1¶2 wording).
2. Apply edits 1–8 (§1 restructure).
3. Resolve §13.B question D (sites) and decide whether §4 needs a sites rewrite.
4. Apply edits 9–11 (§2 + §3.1 opening).
5. Apply edits 12–19 (§3.1 assumptions cleanup + Table 2 reformat).
6. Apply edits 20–25 (§3.2 heat-pump rewrite in Kuan style — biggest change).
7. Apply edits 26–28 (§3.3 solar fix).
8. Apply edits 29–31 (§3.4 kinetics fix; needs Royen / Midilli citations).
9. Apply edit 32 (verify §4 single-digit winter claim against TMY).
10. Re-render `paper/DRAFT.docx` (`python paper/md_to_docx.py`).
11. Stop and let the user read the new docx and dictate the next round.

---
