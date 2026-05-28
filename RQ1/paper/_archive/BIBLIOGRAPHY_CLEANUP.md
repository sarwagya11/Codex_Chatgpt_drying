# Bibliography Cleanup Plan

27 of 52 references are not cited inline. The reviewer flagged ~25 as uncited/irrelevant.
Action for each reference below.

## Legend
- **KEEP + ADD CITE** = reference is relevant, just needs an inline citation added
- **REMOVE** = off-topic or padding, delete from bibliography
- **FIX** = citation is present but wrong/misleading, needs correction
- **DUPLICATE** = same paper listed twice

---

## References with problems (reviewer-flagged)

| Ref# | Author | Year | Reviewer issue | Action |
|------|--------|------|---------------|--------|
| [3]  | Bell (CoolProp) | 2014 | Not cited inline | **KEEP + ADD CITE** in Section 3.1 where CoolProp is mentioned |
| [5]  | Cengel & Boles | 2015 | Not cited inline | **REMOVE** (standard textbook, not specifically referenced) |
| [7]  | Chua 2003 | 2003 | Not cited inline | **REMOVE** (intermittent drying overview, not used) |
| [10] | Duffie & Beckman | 2013 | Not cited inline | **KEEP + ADD CITE** in Section 3.2 (solar collector theory source) |
| [11] | Erbay & Icier | 2010 | Not cited inline | **REMOVE** (thin-layer review, not specifically used) |
| [12] | Erbay & Koca | 2014 | **D1: WRONG PAPER** for HRX context. Spray-drying of milk, not HRX-SAHPD | **FIX**: Replace with correct ref for "SEC reductions 15-35% at eps=0.60-0.75". Use Ismaeel [16] alone or find a better HRX-HPD ref |
| [13] | Hawlader 2006 | 2006 | Not cited inline | **REMOVE** (modified atmosphere, not referenced) |
| [15] | Hottel & Whillier | 1955 | Not cited inline | **KEEP + ADD CITE** in Section 3.2 heading/equation |
| [17] | Jangam 2011 | 2011 | Not cited inline | **REMOVE** (R&D overview, not used) |
| [19] | Lewis 1921 | 1921 | Not cited inline | **REMOVE** (historical, not specifically referenced) |
| [20] | Midilli 2002 | 2002 | Not cited inline for eq 17b | **KEEP + ADD CITE** at eq 17b where Midilli model is used |
| [22] | MoALD 2023 | 2023 | My script missed it | **KEEP** (already cited as [MoALD, 2023]) |
| [23] | Mohanraj & Chandrasekar | 2008 | **D2: MIS-ATTRIBUTION**. This is a forced-convection solar dryer, NOT a SAHPD. Cited as "copra SAHPD" in Section 1.3 and 5.8 | **FIX**: Remove from SAHPD claims. Find actual Mohanraj SAHPD paper or remove copra SAHPD claim |
| [24] | Mortezapour 2012 | 2012 | **D4: DUPLICATE** of [47] | **REMOVE [47]**, keep [24] |
| [25] | Mujumdar 2014 | 2014 | Not cited inline | **REMOVE** (handbook, not specifically referenced) |
| [26] | Pitchai 2012 | 2012 | **Off-topic**: microwave heating in domestic ovens | **REMOVE** |
| [30] | Sarkar 2006 | 2006 | Not cited inline; transcritical CO2, not R134a | **REMOVE** |
| [31] | Sevik 2013 | 2013 | Not cited inline | **REMOVE** |
| [33] | Shrestha 2017 | 2017 | Not cited inline but should be cited for "15-35% post-harvest losses" in Section 1.1 | **KEEP + ADD CITE** in Section 1.1 |
| [41] | PVGIS JRC 2024 | 2024 | Mentioned by name but not bracket-cited | **KEEP + ADD CITE** in Section 4.1 |
| [42] | ASHRAE 2021 | 2021 | Not cited inline | **REMOVE** (standard handbook, not specifically referenced) |
| [43] | Erbay & Hepbasli 2017 | 2017 | Not cited inline | **REMOVE** (exergoeconomic, not used) |
| [44] | Ganesapillai 2011 | 2011 | **Off-topic**: microwave drying of plaster of Paris | **REMOVE** |
| [45] | Kaveh 2021 | 2021 | Not cited inline | **REMOVE** (sweet potato drying methods, not used) |
| [46] | Sahin & Ozturk 2018 | 2018 | Not cited inline | **REMOVE** |
| [47] | Mortezapour 2012 | 2012 | **DUPLICATE** of [24] | **REMOVE** |
| [48] | Singh 2020 | 2020 | Not cited inline | **REMOVE** |
| [49] | Karagoz 2021 | 2021 | Not cited inline | **REMOVE** |
| [50] | Fayose 2016 | 2016 | Not cited inline | **REMOVE** |
| [51] | Vega-Mercado 2001 | 2001 | Not cited inline | **REMOVE** |
| [52] | Jangam 2010 | 2010 | Not cited inline | **REMOVE** |

## Missing references to ADD

| Author | Year | Where to cite | Why |
|--------|------|---------------|-----|
| Bliss, R.W. | 1959 | Section 3.2 heading | "Hottel-Whillier-Bliss" formulation. Ref: Bliss, R.W., 1959. The derivations of several plate-efficiency factors useful in the design of flat-plate solar heat collectors. Solar Energy 3 (4), 55-64. |
| Mohanraj et al. | 2016 | Section 1.3 | Cited in prose but MISSING from bibliography. Ref: Mohanraj, M., Belyayev, Y., Jayaraj, S., Kaltayev, A., 2018. Research progress on solar assisted heat pump drying systems. Renewable and Sustainable Energy Reviews 93, 86-104. (Note: reviewer says 2016; verify correct year -- may be 2018) |
| Alduchov & Eskridge | 1996 | Section 3.6, eq 26 | Correct attribution for the "Tetens" correlation constants used. Ref: Alduchov, O.A., Eskridge, R.E., 1996. Improved Magnus form approximation of saturation vapor pressure. Journal of Applied Meteorology 35 (4), 601-609. |

## Additional fixes

| Issue | Section | Fix |
|-------|---------|-----|
| **D6**: Yan et al. [2023] SMER=22.9 | 1.3 | Could NOT verify this paper via web search. The paper [39] in our bibliography (Applied Thermal Engineering 220, 119767) could not be found on ScienceDirect. Either verify from a downloaded copy or remove the claim. If keeping, MUST add operating conditions. |
| **D7**: Verify DOIs | Refs | Aacharya [1] confirmed in CSTE. Adhikari [2] confirmed in Results in Engineering 26, 105553. Bhandari [4] needs verification. |
| **D8**: R^2=0.90 attributed to Royen [2020] | 4.3 | Reattribute to "the present Phase-3 fit" (it's our number, not Royen's) |

## Verified new references

**Bliss (1959):**
Bliss, R.W., 1959. The derivations of several "plate-efficiency factors" useful in the design of flat-plate solar heat collectors. Solar Energy 3 (4), 55-64. DOI: 10.1016/0038-092X(59)90006-4

**Mohanraj et al. (2018):** (reviewer wrote 2016; actual year is 2018)
Mohanraj, M., Belyayev, Ye., Jayaraj, S., Kaltayev, A., 2018. Research and developments on solar assisted compression heat pump systems: a comprehensive review (Part-B: Applications). Renewable and Sustainable Energy Reviews 83, 124-155.

**Alduchov & Eskridge (1996):**
Alduchov, O.A., Eskridge, R.E., 1996. Improved Magnus form approximation of saturation vapor pressure. Journal of Applied Meteorology 35 (4), 601-609.

---

## Summary of actions

- **REMOVE**: 19 references ([5], [7], [11], [13], [17], [19], [25], [26], [30], [31], [42], [43], [44], [45], [46], [47], [48], [49], [50], [51], [52])
- **KEEP + ADD CITE**: 6 references ([3], [10], [15], [20], [33], [41])
- **FIX**: 2 references ([12], [23])
- **ADD NEW**: 3 references (Bliss 1959, Mohanraj 2016/2018, Alduchov & Eskridge 1996)
- **Final bibliography**: ~36 references (52 - 19 removed + 3 added)

After removing and renumbering, the bibliography will be much cleaner and every entry will have at least one inline citation.
