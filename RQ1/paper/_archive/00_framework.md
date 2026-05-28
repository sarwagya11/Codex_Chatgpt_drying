# Paper Framework

## Target journal

**Primary: Energy Conversion and Management (Elsevier).**
IF ~10 (2024), acceptance rate ~18%, word target 7,000-9,000, ~5-8 figures, ~40-70 refs.
Scope fit: hybrid-energy systems, comparative modelling, thermal storage, solar integration.
Typical section pattern for SAHPD modelling papers: Introduction, System description,
Mathematical model, Simulation setup, Results and discussion, Conclusions.

**Backup 1: Applied Thermal Engineering.**
IF ~6.4, broader component scope, easier acceptance, same IMRaD layout.

**Backup 2: Drying Technology.**
IF ~3.2. Use only if reviewer feedback pushes the paper toward kinetics over system comparison.

## Paper structure (working)

1. **Introduction** (~1,000 words)
   1.1 Context (apple post-harvest losses in Nepal, grid electricity cost, solar potential)
   1.2 Heat pump drying overview
   1.3 Solar-assisted heat pump dryers: state of the art
   1.4 Literature gap
   1.5 Contribution of this work

2. **System description** (~1,200 words, 3-4 figures)
   2.1 Reference configuration (Config A, HP-only)
   2.2 Solar-assisted variants (B, C1, C2)
   2.3 Heat-recovery variants (D1, D2) — D3 excluded
   2.4 Combined variants (E1, E2, E3)
   2.5 VPD bypass control

3. **Mathematical model** (~1,800 words, heavy equations)
   3.1 Vapour-compression cycle (R134a, CoolProp, eta_is = 0.75)
   3.2 Solar collector (Hottel-Whillier-Bliss)
   3.3 Counter-flow HRX (eps-NTU)
   3.4 Drying kinetics (parametric Midilli with alpha_RH)
   3.5 GAB sorption isotherm
   3.6 Psychrometrics and control
   3.7 First-law enforcement and validation

4. **Simulation setup** (~700 words, 1 figure, 1 table)
   4.1 Sites and TMY data (Kathmandu, Biratnagar, Taplejung)
   4.2 Operating inputs (T_set, batch, trays, v_air)
   4.3 Model validation (water balance, energy balance, COP realism)

5. **Results and discussion** (~2,500 words, 5-6 figures, 3-4 tables)
   5.1 Baseline (A) and site sensitivity
   5.2 Solar integration (B, C1, C2)
   5.3 Heat recovery (D1, D2)
   5.4 VPD bypass as an independent control lever
   5.5 Combined systems (E1, E2, E3) and area sensitivity
   5.6 Synthesis: Pareto of SEC vs. capital complexity

6. **Conclusions** (~500 words)
   Quantified headline numbers + limitations + future work

7. **References** (~50-60 entries, pulled from RESEARCH_*.md)

## Contribution claim

Three specific claims that a reviewer will test:

1. **Systematic comparative scope.** Ten air-path topologies compared under one
   validated thermodynamic model, one kinetic model, and one TMY dataset, at three
   Nepalese sites. Prior work reports individual configurations, not a directly
   comparable set.

2. **HRX + solar + VPD bypass combination.** Annual SEC reaches 0.097 kWh/kg at
   Biratnagar with E2 + VPD (A_c = 10 m^2), below every value in the SEC survey
   in RESEARCH_NOVELTY_SEC.md. The novelty is the combination rather than any
   single component; the paper must frame it this way.

3. **Site-dependence mapping.** The closed-loop recirculation crossover (SEC
   benefit at Kathmandu, penalty at Biratnagar) is explicitly traced to the
   interaction between fixed T_evap and ambient climate; this guides geographic
   configuration choice.

## Writing conventions

- SI units throughout. kWh/kg for SEC. Absolute units in tables.
- Refrigerant: R134a (switched from R410A 2026-03-23).
- Configuration labels: Config A, Config B, Config C1, Config C2, Config D1,
  Config D2, Config E1, Config E2, Config E3. Never Config D3.
- Cite the validation note (2026-04-09, six-configuration first-law check) once
  in Section 4.3.
- Objective tone. Do not write "negative result" or similar framing. State
  magnitudes and direction, let the reader judge.
- Figures: SEC bar by site and config; recirculation sweep; collector area
  sweep; Pareto scatter. Diagrams of the ten air paths go in §2.

## Deliverable order

1. 00_framework.md (this file)
2. 01_literature_review.md (Introduction §1.2-1.5 + the supporting lit review paragraphs)
3. 02_system_description.md
4. 03_mathematical_model.md
5. 04_simulation_setup.md
6. 05_results.md (condensed from thesis Results_Discussion_v3.docx)
7. 06_conclusions.md
8. 07_references.bib
