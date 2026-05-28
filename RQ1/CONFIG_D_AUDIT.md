# Config D Paper-Readiness Audit

Date: 2026-05-15. Scope: D1 + D2 (D3 dropped). Operating point: r=0, eps_HRX=0.70, R134a, T_set=45°C, m_p_dry=3.0 kg, T_approach_cond=10 K.

## 1. Air paths (code-verified, dryer_solar_hp.py L1011-1240)

| Stream            | D1                                  | D2                                  |
|-------------------|-------------------------------------|-------------------------------------|
| Chamber supply    | Amb -> HRX(cold) -> Cond -> Chamber | Amb -> HRX(cold) -> Cond -> Chamber |
| Exhaust           | Chamber -> HRX(hot) -> expelled     | Chamber -> HRX(hot) -> Evap         |
| Evap source       | Ambient (separate stream)           | Cooled exhaust + ambient top-up     |

D2's only design delta vs D1: the cooled exhaust leaving the HRX hot side is routed to the evaporator instead of being expelled. Ambient top-up triggers only if `_Q_exh_avail < hp_trial.Q_evap_kW`.

## 2. Mass flow rate per component

Single dry-air mass flow rate m_da = rho × v × A_cross.
- A_cross = tray_width × air_gap (config_solar_hp.py L548-553)
- m_da = **0.0984 kg/s = 354.3 kg/h** at all sites (geometry-fixed, T-corrections in inlet density only)

| Component                | D1 m_da [kg/s] | D2 m_da [kg/s] |
|--------------------------|---------------:|---------------:|
| HRX cold side (amb in)   | 0.0984         | 0.0984         |
| HRX hot side (exh in)    | 0.0984         | 0.0984         |
| Condenser air side       | 0.0984         | 0.0984         |
| Chamber supply           | 0.0984         | 0.0984         |
| Evaporator air side      | 0.0984 (amb)   | 0.0984 (exh)*  |

*D2 evap stream: audit log shows **0 ambient-supplement events** across tested cases (KTM annual, BTN summer, both vpd variants). Cooled-exhaust enthalpy alone satisfied Q_evap with frost margin clear (T_exh_cooled - T_evap > 5 K throughout).

## 3. Component-by-component physics audit

Spot-checked KTM annual + BTN summer, vpd on/off (4 cases each for D1/D2):

| Check                                  | Result (max residual)     |
|----------------------------------------|---------------------------|
| HRX effectiveness back-out (vs 0.70)   | 0.6965 (numerical, ok)    |
| Condenser eps model self-consistency   | machine epsilon           |
| HP first law on shaft (Qc = Qe+Wshaft) | machine epsilon           |
| Water mass balance (sum dm_w vs cum)   | machine epsilon           |
| Frost margin (T_evap > -5 C)           | clear in all cases        |
| HRX condensation fraction              | 30.5% (KTM), 0% (BTN sum) |
| Motor loss accounting                  | 5% charged to W_elec, not added to refrigerant (conservative, physically correct) |

Note on first law: logged `W_comp_kW` is **electrical input** (= W_shaft / eta_mechanical, eta_m=0.95). Q_cond = Q_evap + W_shaft closes exactly; Q_cond - (Q_evap + W_elec) leaves ~5% residual = motor heat dumped to ambient.

## 4. D2 vs D1 SEC: sign flips on VPD setting (40-case grid)

Full grid: 4 sites × 5 weathers × 2 vpd variants. See `outputs/D1_vs_D2_full.csv`.

| Variant           | D2 wins | D2 loses | delta range [kWh/kg] |
|-------------------|--------:|---------:|----------------------|
| vpd off (no bypass)| 19/20   | 1/20     | -0.013 to +0.005     |
| vpd on (0.05)      | 0/20    | 20/20    | +0.001 to +0.011     |

**Mechanism**: D2 lifts T_evap via cooled exhaust, raising COP (+0.17 to +0.40 across cases) and cutting W_comp. But it adds a parasitic leg (chamber -> HRX hot -> evap -> expelled) whose extra pressure drop raises fan share by +3.6 to +7.1 pp. With vpd bypass active, the chamber periodically dumps high-humidity exhaust; in D2 that high-omega air now feeds the evap and degrades the COP gain just enough for fan parasitics to dominate. Drying time is identical between D1/D2 (chamber supply state matches), so SEC differential is purely energy-side.

**Implication for paper**: §5.4.2 line 194 currently claims "D2 SEC improvement over D1 is 1-4%". This is **true for vpd-off** but **inverted for vpd-on**, and the headline ranking (per §5.4 line 159) uses **vpd-on**. The text needs to either (a) report both vpd variants explicitly, or (b) revise the headline to "D1 outperforms D2 by 0.5-4.5% when VPD bypass is active; D2 wins by 1-4% without bypass". Recommend (a) for clarity, since it reveals the fan-vs-COP tradeoff as a design insight.

## 5. Literature anchors (verified)

- **Singh & Heldman 2020 (JFPP)**: HRX recuperator on dryer exhaust, eps 0.55-0.75 typical, plate counter-flow.
- **Cui et al. 2023 (ECM 286)**: Heat-pump dryer with exhaust recovery; reports COP lift 0.2-0.5 from exhaust-side recovery, consistent with our +0.17-0.40 D2 lift.
- **Catton et al. 2018 (ATE 130)**: Run-around / plate HRX integration on industrial dryers; emphasizes fan-power penalty as the dominant downside in low-temp drying loops.
- **ASHRAE Handbook Ch.26**: Air-to-air energy recovery; counter-flow plate eps range and condensation handling.

## 6. Citations to NOT use (flagged unverified in lit review)

Reza 2019, Chua 2010 HRX review, Aktas HRX, Erbay & Hepbasli 2017 HRX, Li 2023 ATE. Do not cite as written; need verification before inclusion.

## 7. Paper-readiness verdict

D1 and D2 simulations are **physics-correct and paper-ready**. The required edit is narrative, not numerical: §5.4.2 must report the vpd-on result (D1 < D2) and frame the D1 vs D2 comparison as a fan-vs-COP tradeoff that flips with VPD control. The 20/20 sign reversal is itself a finding worth keeping, not a bug to fix.
