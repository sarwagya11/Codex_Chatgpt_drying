# Paper Revision Plan: Reviewer Response

**Paper:** Comparative simulation of ten SAHPD configurations for fruit drying in Nepal
**Date:** 2026-04-25
**Approach:** One section at a time, one paragraph at a time. No bulk rewrites.

---

## How to use this plan

Each section lists the reviewer issues that apply, tagged by reviewer category (A=fatal, B=numerical, C=physical, D=reference, E=vague, F=missing, G=minor). Work top-to-bottom. Check off items as completed.

---

## PASS 0: Front-matter and figure numbering (Reviewer A1, A2, A3)

These are blocking issues that affect the entire paper.

- [ ] **A1** Fill author names and affiliation (line 1-2)
- [ ] **A2** Create all figures (currently placeholder captions). This is a separate multi-session effort; track in a FIGURES_TODO list.
- [ ] **A3** Adopt a single figure numbering system (1, 2, 3, ...). Remove "5b", "5.1", "5.2", "7b" variants.

---

## PASS 1: Abstract (line 4)

- [ ] **B9** Remove or qualify Taplejung E2+bypass claim (Taplejung E2+bypass was never run). Either run it or restrict abstract to KTM+BTN.
- [ ] **G-dash** Standardize dash style (use "," or ";" instead of mixed em/en dashes per user style preference).
- [ ] **E** "to the authors' knowledge" appears 3x in paper; keep only one instance (not in abstract).
- [ ] **B1** Fix wet-mass number if it appears here (check: "19.3 kg" in Fig 5b caption, "22.4 kg" in Table 11).

---

## PASS 2: Section 1 -- Introduction

### 1.1 Fruit drying in Nepal (line 8)
- [ ] **E** "approximately 1.53 Mt" -- add inline citation [MoALD, 2023] (already at end of sentence, OK).
- [ ] **E** "reported post-harvest losses...15-35 %" -- add inline citation. Likely [33] Shrestha 2017.

### 1.2 Heat-pump drying (lines 11-12)
- [ ] **E** COP and SEC ranges given without per-paper breakdown. Add which paper gives which number.
- [ ] **E** "to the authors' knowledge, absent from the literature" (line 12) -- this is instance #1. Keep or cut.

### 1.3 Solar-assisted HPDs (lines 14-16)
- [ ] **D2** "Mohanraj & Chandrasekar, 2008, on copra" is mis-attributed. Ref [23] is a forced-convection solar dryer, NOT a SAHPD. Find a real Mohanraj SAHPD paper or remove the claim.
- [ ] **D3** "Mohanraj et al., 2016" is cited in prose but missing from bibliography. Add it or remove.
- [ ] **D6** Yan et al. [2023] SMER=22.9 -- verify the paper actually reports this; cite operating point and load conditions.

### 1.4 Heat-recovery exchangers (lines 17-19)
- [ ] **D1** [12] Erbay & Koca 2014 is spray-drying of milk, NOT HRX-equipped SAHPD. Replace with a correct reference for "SEC reductions of 15-35% at eps=0.60-0.75".
- [ ] **C2** "Hottel-Whillier-Bliss" heading in 3.2 -- Bliss (1959) missing from refs. Either add the reference or drop "Bliss" from the name. (Fix in 3.2, flag here.)

### 1.5 Humidity-aware control (lines 20-21)
- [ ] **E** "to the authors' knowledge" instance #2. Keep this one (strongest novelty claim) or merge with 1.6.

### 1.6 Prior Nepali work (lines 22-27)
- [ ] **E** "a substantial line of solar-drying research" -- quantify or soften.
- [ ] **E** "to the authors' knowledge" instance #3. Remove this one (weakest).
- [ ] **G** Roadmap (line 28): "Section 5 reports results; Section 6 concludes" omits Section 7 (refs). Fix.

---

## PASS 3: Section 2 -- System description

### 2.1 Config A (lines 31-33)
- [ ] No specific issues. Review for clarity.

### 2.2 Configs B, C1, C2 (lines 34-37)
- [ ] No specific issues. Review for clarity.

### 2.3 Configs D1, D2 (lines 38-41)
- [ ] **G** Heading "D3 excluded" in the title reads as defensive. Move D3 exclusion rationale into the prose, remove from heading.
- [ ] **C8** D3 exclusion is hand-wavy: "failed the water-mass-balance consistency check at one of the three sites" without a residual value, the failing site, or a diagnosis. Either: (a) state the site and residual, (b) explain the physics of the failure, or (c) rerun D3 and include it. Option (a) is simplest.

### 2.4 Configs E1, E2, E3 (lines 42-45)
- [ ] **C7** Solar fraction definition fails for E3. SF = Q_solar_usable / Q_cond can exceed 1 when HP is off. Define "usable" and explain clipping. (Also affects 5.5.)

### 2.5 VPD bypass (lines 46-48)
- [ ] **E** "physically justified by the diminishing drying-rate penalty" -- the justification is operational/economic, not physical. Reword.

### 2.6 Summary (lines 49-50)
- [ ] No specific issues.

---

## PASS 4: Section 3 -- Mathematical model

### 3.1 Vapour-compression cycle (lines 53-64)
- [ ] **C3** W_comp labelled "electrical" but eq. (4) divides by eta_mech only (shaft power). Either rename to "shaft power" or add eta_motor. Simplest: rename to shaft power and note that motor losses are excluded.
- [ ] **C4** Pinch model is internally inconsistent with air-side effectiveness. T_cond = T_set + 10 = 55C, then eps_cond=0.85 gives T_air_out = 20 + 0.85*(55-20) = 49.75C, not 45C. The system is over-determined. Reconcile: explain that T_cond is set by the pinch, and eps_cond then determines actual T_air_out, which may exceed T_set; the code caps at T_set. OR: clarify that T_cond is the result (not the input) when eps=0.85 is binding.

### 3.2 Solar collector (lines 65-74)
- [ ] **C2** "Hottel-Whillier-Bliss" -- add Bliss (1959) reference, or drop "Bliss" from heading.

### 3.3 HRX (lines 75-82)
- [ ] No specific issues.

### 3.4 Drying kinetics (lines 83-96)
- [ ] **E** "Phase-1/2 pipeline is validated separately in the RQ1 kinetic-identification study" -- references unpublished work. Either include the validation summary here or remove the claim.
- [ ] **D8** "piecewise-Midilli R^2 of 0.90" attributed to [Royen et al., 2020] but it's from OUR Phase-3 fit. Reattribute.
- [ ] **D5-inline** Midilli (2002) [20] is the eponymous model used in eq. 17b but not cited there. Add inline citation.

### 3.5 GAB isotherm (lines 97-103)
- [ ] **C5** X_m(T) = X_m,0 * exp(+DH_xm/RT) implies monolayer capacity INCREASES with T. Standard convention has it decreasing. Check sign or cite source.
- [ ] **F** GAB parameter source for apple not cited. Add citation.

### 3.6 Psychrometrics (lines 104-115)
- [ ] **C1** "Tetens correlation" (eq. 26) is misnamed. The constants 610.94, 17.625, 243.04 are Magnus-Alduchov-Eskridge (1996), not Tetens (1930). Fix name and add correct citation.
- [ ] **C6** alpha_RH units not stated. Make explicit: "RH is expressed as a fraction (0-1)" so alpha_RH=1.75 gives moderate suppression.

### 3.7 First-law closure (lines 116-122)
- [ ] No specific issues.

### 3.8 SEC metric (lines 123-127)
- [ ] No specific issues.

---

## PASS 5: Section 4 -- Simulation setup and validation

### 4.1 Sites and TMY (lines 129-133)
- [ ] No specific issues. (TMY uncertainty addressed in F.)

### 4.2 Operating inputs (lines 134-137)
- [ ] **B1** Table 11: "3.0 kg dry (approx 22.4 kg wet at X0=5.5 kg/kg db)". Correct: m_wet = 3*(1+5.5) = 19.5 kg, water = 3*5.5 = 16.5 kg. Fix both numbers.
- [ ] **G** R134a footnote "selected for low-GWP substitution path" -- R134a GWP=1430, this is wrong. Justify on T_cond_max grounds instead.
- [ ] **C10** Fan power "<=5% of W_comp" asserted but never characterized; in bypass mode the fraction changes. Add a sentence acknowledging this.
- [ ] **C9** No time-step convergence study for dt=60s. MUST ADD: run dt=30s and dt=120s for one config, show SEC converges.

### 4.3 Validation (lines 138-150)
- [ ] **E** "COP 3.5-4.8...Carnot ratio 0.61-0.62, consistent with eta_is=0.75" -- the algebra linking these three is not shown. Show it or soften.
- [ ] **E** "broadly consistent with" -- quantify.
- [ ] **B1** Fig 5b caption: "19.3-kg-water batch". Correct: water = 16.5 kg. Fix.

---

## PASS 6: Section 5 -- Results and discussion

### 5.1 Baseline Config A (lines 153-157)
- [ ] **B5** "Taplejung falls between the two at 0.59 kWh/kg". Table 5.1 shows 0.566. Use the table value.
- [ ] **B6** r=0.3 spike at Biratnagar (SEC=1.647, +203%). Prose only flags "+39% at r=0.9". Either explain the spike physically or label it a numerical artefact.
- [ ] **B7** Taplejung entries r=0.3, 0.5, 0.7 shown as "--" with no explanation. State why (non-convergence within 72h timeout).

### 5.2 Solar integration (lines 158-162)
- [ ] Review numbers against tables. No specific reviewer flags beyond general accuracy.

### 5.3 Heat recovery (lines 163-165)
- [ ] No specific issues flagged.

### 5.4 VPD bypass (lines 166-168)
- [ ] **B4** "Largest absolute reductions are on the combined E-configurations" -- Table 5.4 (Table 15): KTM E1 reduces by 0.068, E2 by 0.053; D1 reduces by 0.078. D1 has the largest absolute reduction, not E. Fix the claim.

### 5.5 Combined configs (lines 169-177)
- [ ] **E** "the headline number of the paper" -- informal. Remove.
- [ ] **C7** SF definition for E3 (can exceed 1). Add clarifying sentence or cap SF at 1 with explanation.

### 5.6 Seasonal variation (lines 178-184)
- [ ] **B3** "Spring gives the lowest SEC at every site-configuration pair" -- FALSE. Table 5.6 (Table 17): Taplejung autumn D1=0.261 < spring 0.267; Taplejung autumn E2=0.102 < spring 0.115. Fix: "Spring gives the lowest SEC at most site-configuration pairs; at Taplejung, autumn is marginally lower for D1 and E2."
- [ ] **B8** "annual-mean SMER of 7.8 kg/kWh (E2+bypass, Biratnagar)" -- Table 5.4/5.7 gives 10.29, abstract gives 10.31. The 7.8 figure appears nowhere else. Remove or reconcile. (7.8 may be seasonal, not annual.)

### 5.7 Configuration ranking (lines 185-189)
- [ ] **F** "capital-complexity ordering A < D1 ~ D2 < B..." makes a capital-cost claim with no analysis. Remove or explicitly label as qualitative assumption without cost data.

### 5.8 Comparison with published (lines 190-192)
- [ ] **E** "five times better" than Hawlader -- the author concedes unfair comparison, then prints the ratio. Drop the "5x" framing.
- [ ] **D2** "Mohanraj et al. [2008] reported SMER=0.85 kg/kWh for a copra SAHPD" -- that paper is NOT a heat-pump study. Remove or replace.
- [ ] **C11** "~18% uncertainty on the vapour-pressure driving force" from pressure extrapolation. The dominant dependence is D_AB (proportional to 1/p, ~22%), not VPD. Tighten the framing.

---

## PASS 7: Section 6 -- Conclusions

- [ ] **B2** "Five limitations" but six are listed (i)-(vi). Change to "Six limitations".
- [ ] **E** "a pilot build at that scale is now the critical-path item for the RQ1 research programme" -- "RQ1" is internal jargon. Remove or rephrase as "the authors' research programme" or just "future work".

---

## PASS 8: Section 7 -- References

- [ ] **D1** Replace [12] Erbay & Koca 2014 (spray drying, wrong context).
- [ ] **D2** Fix [23] Mohanraj & Chandrasekar 2008 usage (not a SAHPD).
- [ ] **D3** Add missing "Mohanraj et al., 2016" reference.
- [ ] **D4** Remove duplicate: [24] and [47] are the same Mortezapour 2012.
- [ ] **D5** Add inline citations for uncited refs or remove them. Reviewer lists ~25 uncited/irrelevant refs:
  - Definitely remove (off-topic): [26] Pitchai (microwave ovens), [44] Ganesapillai (microwave plaster of Paris)
  - Remove if no inline citation added: [5], [7], [11], [13], [17], [19], [25], [30], [31], [33], [42], [43], [45], [46], [48], [49], [50], [51], [52]
  - Keep but add inline citation: [3] Bell/CoolProp (cite in 3.1), [15] Hottel & Whillier (cite in 3.2), [20] Midilli (cite in 3.4 eq 17b)
- [ ] **D6** Yan et al. [2023] -- verify SMER=22.9 and cite operating conditions.
- [ ] **D7** Verify DOIs for Bhandari 2025, Aacharya 2024, Adhikari 2025.
- [ ] **D8** Reattribute R^2=0.90 (it's ours, not Royen's).
- [ ] **C2** Add Bliss (1959) reference if keeping "Hottel-Whillier-Bliss".

---

## PASS 9: New content required (Reviewer F)

- [ ] **F1** Sensitivity analysis on eps_cond, eps_evap, eps_HRX. Run 3 values each (e.g., 0.75/0.85/0.95 for coils, 0.60/0.70/0.80 for HRX). Add table + 1-2 paragraphs.
- [ ] **F2** Time-step convergence table. Run dt=30s, 60s, 120s for Config A and E2 at KTM. Show SEC converges.
- [ ] **F3** Either run Taplejung E1/E2/E3 +/- bypass OR remove Taplejung from abstract claims.
- [ ] **F4** TMY uncertainty: state PVGIS confidence interval, discuss propagation to SEC.
- [ ] **F5** GAB parameter source for apple: find and cite.
- [ ] **F6** Add [3] CoolProp inline citation in Section 3.1.

---

## Execution order

The recommended order is:

1. **Pass 9 first** (new simulations: F1, F2, F3) -- these take compute time; start them while editing text.
2. **Pass 0** (front-matter, figure numbering) -- mechanical.
3. **Pass 8** (references) -- clean the bibliography before touching prose that cites it.
4. **Passes 1-7** in order (Abstract through Conclusions), one paragraph at a time.

Within each pass, we work one checkbox at a time, draft the fix, review it, then move on.
