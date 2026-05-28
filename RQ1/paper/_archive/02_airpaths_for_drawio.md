# Air-path reference for draw.io diagrams (Configs B, C, E)

_Verified against `RQ1/src/rq1/dryer_solar_hp.py` on 2026-04-30 and consistent with `air_paths_verified.md`. Use these chains as the source of truth when drawing the topology figures._

Convention used below:
- `Amb` = ambient inlet
- `HRX_c` / `HRX_h` = HRX cold side (gains heat) / hot side (gives heat)
- `Sol` = solar air collector
- `Cond` = HP condenser (heating side)
- `Evap` = HP evaporator (cooling/dehumidifying side)
- `Cham` = drying chamber
- `Exh` = chamber exhaust
- `Mix(a + b)` = adiabatic mixing junction
- `r` = recirculation fraction (0 = full open loop; D/E configs are r = 0 by design)
- "→ Discharge" = stream leaves the system

---

## Config A — HP-only reference (no solar, no HRX)

**r = 0 (open loop)**

- Heating stream: `Amb → Cond → Cham → Exh → Discharge`
- Evaporator side: `Amb (independent draw) → Evap → Discharge` (parallel; not coupled to the heating stream at r = 0)

**r > 0 (closed/partial loop)**

- Single loop: `Mix(Amb + r·Exh) → Evap → Cond → Cham → Exh splitter:`
  - r·Exh routed back to Mix
  - (1 − r)·Exh discharged

**Comment for figure:** A is the HP-only reference. The evaporator is parallel at r = 0 and inline (after the mix node) at r > 0. All other configurations are obtained by inserting Sol and/or HRX into this base topology.

---

## Config D1 — HRX only, ambient evaporator

(All D configs are r = 0 by design.)

- Heating stream: `Amb → HRX_c → Cond → Cham → Exh → HRX_h → Discharge`
- Evaporator stream: `Amb (independent draw) → Evap → Discharge`

**Comment for figure:** counter-flow HRX with ε ≈ 0.70 between chamber exhaust and ambient inlet; evaporator decoupled on a separate ambient draw.

---

## Config D2 — HRX only, exhaust-supplied evaporator

- Heating stream: `Amb → HRX_c → Cond → Cham → Exh → HRX_h → Mix(+ Amb_supplement) → Evap → Discharge`
- The ambient supplement at the evaporator inlet is sized dynamically so the evaporator load matches the condenser duty under the first-law constraint.

**Comment for figure:** identical heating-side path to D1; the only visual difference is that the post-HRX exhaust feeds the evaporator (with an ambient supplement mix node) instead of being expelled. Mark the dynamic mix node.

---

## Config D3 — HRX swapped (inversion test)

- Heating stream: `Exh → HRX_c → Cond → Cham` (chamber exhaust enters the cold side, then heated by the condenser, then back to the chamber)
- Evaporator stream: `Amb → HRX_h → Evap → Discharge`

**Comment for figure:** D3 inverts the HRX routing. The chamber sees recycled humid air on the supply, which raises chamber humidity and degrades drying. Included as an inversion test to demonstrate the humidity penalty in the SEC results; not a serious operating candidate.

---

## Config B — Solar + HP series on the heating stream

**r = 0 (open loop)**

- Heating stream: `Amb → Sol → Cond → Cham → Exh → Discharge`
- Evaporator side: `Amb (independent draw) → Evap → Discharge` (parallel; not coupled to the heating stream at r = 0)

**r > 0 (closed/partial loop)**

- Single loop: `Mix(Amb + r·Exh) → Evap → Sol → Cond → Cham → Exh splitter:`
  - r·Exh routed back to Mix
  - (1 − r)·Exh discharged

**Comment for figure:** B is "solar in series with the condenser, on the heating stream". Most directly comparable to Hawlader 2003 / Şevik 2013.

---

## Config C1 — Solar cascade, mix BEFORE solar (inline evap)

**r = 0 (open loop, single inline stream)**

- `Amb → Sol → Evap → Cond → Cham → Exh → Discharge`
- The evap sits inline between solar and condenser, so solar preheat is partially undone by the dehumidifying evaporator before the condenser reheats.

**r > 0 (closed/partial loop)**

- `Mix(Amb + r·Exh) → Sol → Evap → Cond → Cham → Exh splitter`

**Comment for figure:** C1 deliberately puts the evaporator inline. The thermal penalty (solar gain wasted on the cooling step) is the design trade-off being illustrated.

---

## Config C2 — Solar cascade, mix AFTER solar (parallel paths at r = 0)

> ⚠ The code and the docstring disagree at r = 0. The figure must follow the **code**, not the docstring. See `air_paths_verified.md`.

**r = 0 (open loop, two parallel paths) — code-true**

- Heating path: `Amb → Cond → Cham → Exh → Discharge` (no solar in the main path)
- Cooling path: `Sol → Evap → Discharge` (solar feeds the evaporator side, separate stream)

**r > 0 (closed/partial loop) — solar feeds the recirculation mix**

- `Sol → Mix(Sol-heated air + r·Exh) → Evap → Cond → Cham → Exh splitter`

**Comment for figure:** the r = 0 case must be drawn with two clearly separate paths; do **not** draw a Sol→Cond connection at r = 0 even though the docstring suggests it. Add a footnote in the figure caption acknowledging the topology change between r = 0 and r > 0.

---

## Config E1 — HRX + Solar on the condenser stream, ambient evaporator

(All E configs are r = 0 by design; D/E paths are open-loop with VPD-triggered exhaust bypass on top.)

- Heating stream: `Amb → HRX_c → Sol → Cond → Cham → Exh → HRX_h → Discharge`
- Evaporator stream: `Amb (independent draw) → Evap → Discharge`

**Comment for figure:** counter-flow HRX with ε ≈ 0.70; solar preheat sits between HRX and condenser; evaporator runs on ambient, so dehumidification is decoupled from the heating loop.

---

## Config E2 — HRX + Solar on the condenser stream, exhaust-supplied evaporator

- Heating stream: `Amb → HRX_c → Sol → Cond → Cham → Exh splitter:`
  - portion 1 → `HRX_h → Discharge` (gives heat back to the cold side)
  - portion 2 → `Mix(Exh + Amb_supplement) → Evap → Discharge`
- The ambient supplement mass flow feeding the evaporator mix is solved by the fixed-point iteration in `_iterative_evap_sizing()`, so the evaporator load matches the condenser duty under the first-law constraint.

**Comment for figure:** the key visual difference from E1 is that the evaporator now sees a recovered (warmer, more humid) inlet stream, raising COP. Mark the iterative mix node clearly. This is the best-performing topology in the present study.

---

## Config E3 — HRX + Solar AFTER condenser, exhaust-supplied evaporator, solar-priority control

- Heating stream: `Amb → HRX_c → Cond → Sol → Cham → Exh splitter:`
  - portion 1 → `HRX_h → Discharge`
  - portion 2 → `Mix(Exh + Amb_supplement) → Evap → Discharge`

**Solar-priority control overlay (must be shown on the figure or in the caption):**
1. If `HRX_c → Sol` outlet alone reaches T_set, HP is **OFF**. Solar finishes the lift.
2. Otherwise, HP runs at a variable T_cond chosen so that the post-solar stream meets T_set. Solar tops up; HP only provides the residual lift.

**Comment for figure:** key difference from E2 is solar AFTER the condenser, not before. This lets solar opportunistically replace HP duty when irradiance is high. Worth a small inset on the figure showing the control logic switch.

---

## Notes for all figures

- Use the same icon set across all 10 figures so the reader can compare topologies at a glance.
- Mark r = 0 vs r > 0 paths in different stroke styles when both are shown on one figure (e.g., solid for r = 0 open loop, dashed for the recirculation overlay).
- Show direction arrows on every segment.
- Label all heat exchangers with the duty name (Q_sol, Q_cond, Q_evap, Q_HRX) so §3 can refer back to the same labels.
- VPD-bypass exhaust valve is the same on all 10 configs; draw it on the master schematic only and reference it in the others.
