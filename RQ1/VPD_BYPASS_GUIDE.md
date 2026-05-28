# VPD Utilization and Bypass Mechanisms — Basic Guide

Source code: `src/rq1/dryer_solar_hp.py`. Two distinct bypass mechanisms live in the simulator. Do not confuse them.

1. **VPD exhaust bypass** (D1/D2/E1/E2/E3): a *control* decision that re-routes warm exhaust around the HRX path into the condenser when the drying air is "spent". Triggered by a humidity metric.
2. **E3 condenser bypass** (E3 only): a *physics* decision that turns the heat pump OFF when solar alone can hit T_set.

---

## 1. The vapour-pressure deficit (VPD) — what it is

For moist air, the partial pressure of water vapour is `p_v`. The saturation pressure at temperature T is `P_sat(T)`. The vapour-pressure deficit is

```
VPD(T) = P_sat(T) - p_v        [Pa]
```

VPD is the thermodynamic "thirst" of the air at that temperature. High VPD means the air can still absorb a lot of water; VPD = 0 means saturated, no drying possible. Apple drying at T_set = 45 °C uses `P_sat(45 °C) ≈ 9590 Pa` as the reference.

Code: `compute_vpd_utilization()` at L587–612.

```python
P_sat_Tset = p_sat_water_Pa(T_set_C)
p_v_amb = omega_amb * p_atm / (0.622 + omega_amb)        # fresh-air vapour pressure
p_v_exh = omega_exhaust * p_atm / (0.622 + omega_exhaust) # exhaust vapour pressure

VPD_in  = P_sat_Tset - p_v_amb     # how thirsty fresh air is at T_set
VPD_exh = P_sat_Tset - p_v_exh     # how thirsty exhaust is at T_set

utilization = 1 - VPD_exh / VPD_in
```

Both VPDs are evaluated *at T_set* so the comparison is apples-to-apples (it removes the temperature dependence of P_sat and isolates the humidity loading).

Interpretation:
- `utilization ≈ 1`: exhaust is nearly saturated; the air did a lot of drying work this pass. This is the **early drying** regime (constant-rate, high MR).
- `utilization ≈ 0`: exhaust looks just like fresh air; the chamber barely pulled any moisture. This is the **late drying** regime (falling-rate, MR near X_eq), and pushing more fresh dry air through is wasteful.

So `utilization` is a real-time signal for "are we still in the productive part of the dry?".

---

## 2. VPD exhaust bypass — the control law

Once `utilization` drops low, paying the full HRX + HP energy cost to produce 45 °C, low-omega chamber air no longer makes sense. The drying rate is now moisture-diffusion-limited inside the apple, not air-thirst-limited. The controller bypasses the HRX and feeds the still-warm exhaust *directly* to the condenser:

```
NORMAL:  Amb -> HRX -> Cond -> Chamber -> Exh -> HRX -> Expelled
BYPASS:  Exh -> Cond -> Chamber  (HRX skipped, no fresh-air mixing)
```

This saves two energies:
- The HP delta-T is tiny because exhaust is already ~40 °C, so `W_comp` collapses.
- The HRX is dropped from the heat accounting (`Q_HRX_cum_kWh` only accrues when `not _vpd_bypass_active`, L1213–1215).

The cost: humidity rises slowly in the chamber because moisture is no longer flushed. Acceptable in the falling-rate phase because drying is internally diffusion-limited.

### The hysteresis state machine (L1090–1106, mirrored at L1413–1427 for E)

State variables: `_vpd_bypass_active` (bool), `_vpd_last_switch_s`, `_vpd_utilization`.

```
threshold = cfg.dryer.vpd_bypass_thresh    # default 0.05
dwell_s   = 600                            # 10-minute minimum between switches

if currently bypassing:
    if utilization > 3 * threshold AND dwell elapsed:
        switch OFF (back to normal HRX path)
else:
    if utilization < threshold AND dwell elapsed:
        switch ON (bypass)
```

Three design choices to note:

| Mechanism | Value | Why |
|---|---|---|
| Threshold | 0.05 | Below 5% utilization, the air is essentially passing through unused. Audited 2026-05-17: 0.05 robust default; 0.20 always worst (over-bypass starves condenser of dryable air). |
| Hysteresis ratio | 3× | Asymmetric band, `[0.05, 0.15]`. Prevents chatter: once OFF you need utilization to *rise* to 0.15 before returning to normal. Without this the controller would flap every timestep near the boundary. |
| Dwell | 600 s | Hard minimum between switches. Compressor protection (no short-cycling). Even if utilization crosses, you wait 10 minutes. |

In the chamber loop (L1123): if `_vpd_bypass_active`, the air going into the condenser is the previous exhaust, not the HRX-heated ambient. `T_evap_source` reverts to ambient. The condenser still runs (with tiny lift), so `bypass_mode = "exhaust_bypass"` is recorded but the HP isn't off.

---

## 3. The other bypass criterion you may see: `compute_cond_penalty_est`

L466–513 defines `cond_penalty_frac = (VPD_post_evap - VPD_exhaust) / VPD_post_evap`. This is an alternative metric that estimates whether the *evaporator* dehumidification step is still useful (relevant only when r > 0 and the evap is doing real dehumidification work). It's currently **not used** for the D/E configs in the runner; those use the simpler `compute_vpd_utilization`. It exists for the r > 0 recirculating configs (A r>0, B/C with recirc).

Practical takeaway: when you see `vpd_bypass_active` in the output CSVs, it was decided by `compute_vpd_utilization`, not `compute_cond_penalty_est`.

---

## 4. E3's condenser bypass (a different thing)

E3 has its own logic, layered *on top of* VPD bypass. The geometry is `Amb -> HRX -> Cond -> Solar -> Chamber`, so on a sunny day the solar collector might raise the HRX-heated air all the way to T_set without any HP help.

L1617–1647 implements a one-shot collector model:

```
ΔT_solar(predicted) ≈ α - β·(T_HRX_out - T_amb)

α = F_R · η_optical · G_solar · A_solar / (m_da · cp · 1000)   # gain
β = F_R · U_loss · A_solar / (m_da · cp · 1000)                # loss coefficient

if T_HRX_out + ΔT_solar_predicted >= T_set AND G_solar > 10 W/m²:
    HP OFF (T_cond_target = T_HRX_out, condenser does no work)
else:
    HP ON, partial lift to a variable T_cond_target < T_set,
    solar finishes the rest
```

Variable-T_cond control: the HP only lifts to whatever T_cond is needed so that solar can carry the air the rest of the way to T_set. Computed by inverting the collector equation (L1652–1655):

```
T_cond_target = (T_set - α - β·T_amb) / (1 - β)
```

clamped to `[T_HRX_out, T_set]`.

Audit finding: E3 HP-off fraction peaks 38–39% in summer at BTN/TPJ; drops to 13% in KTM annual (cloud-suppressed). Saves W_comp at midday but loses to E2 across all 20 site×season cases because lower T_cond means warmer evaporator means less dehumidification per pass.

---

## 5. Where it shows up in outputs

Each per-row CSV has these columns (record assembly at L1234–1235 for D, L1806 for E):
- `vpd_utilization` — the metric, 0..1
- `vpd_bypass_active` — 0 or 1
- `bypass_mode` — `"none"`, `"exhaust_bypass"`, or `"electric"` (config 0)

For E3 only, `_hp_mode` is logged as `"off"`, `"vpd_bypass_off"`, `"vpd_bypass_partial"`, `"vpd_bypass_full"`, or normal lift. This separates VPD bypass (control) from E3 cond bypass (physics).

---

---

## 6. Condenser-direct / evaporator bypass (A, B, C1, C2 with r > 0)

This is a **completely separate mechanism** from the D/E VPD bypass above. It only fires in the recirculating configs (`r > 0`) and is controlled by `cfg.dryer.cond_penalty_thresh`, not `vpd_bypass_thresh`. Code lives in three places:
- Config A: around L1943–2070 of `_run_config_A_recirc_simulation` (Config B uses the same block, L1855 says "Supports evaporator bypass, same logic as Config A").
- Config B: L1943–2065.
- Config C1: L2321–2475.
- Config C2: L2744–2860 (same pattern).

### Why it exists

When recirculation is on, every pass through the loop has structure:

```
NORMAL r>0:  [r·Exh + (1-r)·Amb] -> Evap (cool + dehumid) -> Cond (heat) -> Chamber -> Exh
```

The evaporator is doing two jobs at once: (a) acting as the HP's heat source, and (b) dehumidifying the recirculated exhaust before it goes back to the chamber. Job (b) is only valuable when the mix is significantly more humid than ambient. Late in the dry, exhaust is barely wetter than fresh air, so the dehumidification step costs compressor work for almost no humidity benefit.

### The criterion: `cond_penalty_frac`

Defined in `compute_cond_penalty_est` (L469–513). Runs a "what-if" evaporator step at the current operating point:

```
omega_mix       = r·omega_exh + (1-r)·omega_amb          # actual mix entering evap
omega_sat_coil  = humidity_ratio_at_saturation(T_evap_coil)  # what the coil can pull air down to
omega_after_evap = omega_mix - epsilon_evap · max(0, omega_mix - omega_sat_coil)

p_v_post_evap = partial pressure from omega_after_evap
p_v_exhaust   = partial pressure from omega_exhaust  (current exhaust, skipping evap)

VPD_post_evap = P_sat(T_set) - p_v_post_evap     # drying power if evap is used
VPD_exhaust   = P_sat(T_set) - p_v_exhaust       # drying power if you just route exhaust around the evap

cond_penalty_frac = (VPD_post_evap - VPD_exhaust) / VPD_post_evap
```

This is the *fractional drying-power loss from skipping the evaporator*. If `cond_penalty_frac < 0.05`, skipping the evap costs you less than 5% of available VPD: the evap is a waste of compressor work.

### The state machine (A/B identical, C1/C2 identical)

```python
_cond_thresh = cfg.dryer.cond_penalty_thresh    # CLI flag; 0 disables
if _cond_thresh > 0 and omega_exhaust_prev is not None and r > 0:
    cond_penalty_frac = compute_cond_penalty_est(...)

    # Adaptive dwell: how long it takes humidity to drift back across the threshold
    target = 3·_cond_thresh if _cond_bypass_active else _cond_thresh
    dwell  = compute_humidity_dwell_s(... target_penalty=target ...)
    dwell_ok = (time_s - _last_mode_switch_s) >= dwell

    if _cond_bypass_active:
        if cond_penalty_frac > 3·_cond_thresh and dwell_ok:
            switch OFF
    else:
        if cond_penalty_frac < _cond_thresh and dwell_ok:
            switch ON
```

Difference from D/E VPD bypass:
- **Different metric**: `cond_penalty_frac` (humidity drop *across the evaporator*), not `vpd_utilization` (humidity loading *across the chamber*).
- **Different CLI flag**: `cond_penalty_thresh` vs `vpd_bypass_thresh`. They are independent.
- **Adaptive dwell**: `compute_humidity_dwell_s` (L516–584) estimates how long until the threshold is crossed again from the current drying rate `dm_w / (m_da · dt_s)` and the sensitivity `d(cond_penalty)/d(omega_exh)` via finite difference. Clamped to `[300, 7200]` s. The D/E bypass uses a fixed 600 s dwell instead.
- **3× hysteresis** is the same idea both places.

### What happens when bypass is active (Config A example, L1988–1999)

```
CONDENSER-DIRECT MODE (r > 0, bypass active):
  Solar collector input:  ambient (not the mix)
  Solar collector output: T_evap_source     ← solar feeds the EVAP side
  Evaporator (on chamber stream): SKIPPED
  Condenser input:        T_exhaust_prev    ← exhaust goes straight to cond
  Chamber humidity:       omega_exhaust_prev (carried over unchanged)
```

Two structural changes happen at once:

1. **Chamber stream**: exhaust skips both solar *and* evaporator and goes directly to the condenser. The condenser sees warm exhaust (~40 °C), so the lift to T_set is tiny → tiny W_comp.
2. **Evap-side heat source**: solar is rerouted from the chamber stream to the evaporator inlet. The HP now draws heat from solar-heated ambient air instead of the recirculated mix. This is why solar-equipped configs (B, C1, C2) benefit from this mode more than Config A.

Config B does the same swap (L2056–2061). Config C1 (L2356–2369) is structurally identical with the solar inlet at ambient. Config C2 (L2781+) follows the same pattern.

### The fourth mode: `bypass_mode = "bypass"` (impossible cycle)

L2022–2031 (Config B) and the matching block in A/C: a hard-stop *physics* guard. If the dynamic evap-coil calculation produces `T_evap_sat >= T_cond_C_hp`, the refrigeration cycle is thermodynamically impossible (evaporator would need to be hotter than the condenser). The simulator falls back to open-loop sizing for that timestep with `bypass_mode = "bypass"` and sets `flag_impossible = True`. This is rare with current settings (fixed T_evap=5 °C, T_cond~55 °C, never triggers) but the guard exists for sensitivity sweeps.

### What you see in CSVs for A/B/C

| `bypass_mode` value | Meaning |
|---|---|
| `"none"` | Open-loop (r = 0), or recirc disabled |
| `"evap"` | Normal r > 0 path: mix → evap → cond |
| `"cond_direct"` | VPD-style bypass active: exhaust → cond, solar → evap |
| `"bypass"` | Impossible-cycle fallback (rare) |

For D/E configs you instead see `"exhaust_bypass"` (from VPD utilization), which is a *different code path* and a *different metric*. Don't conflate.

---

## 7. Summary table

| Mechanism | Configs | Trigger | Action | Why it saves energy |
|---|---|---|---|---|
| **Cond-direct / evap bypass** | A, B, C1, C2 (r > 0 only) | `cond_penalty_frac < 0.05` with 3× hysteresis and *adaptive* dwell from humidity rate | Exhaust → Cond (skip evap on chamber stream); solar → Evap | Tiny HP lift + no useless dehumid work |
| **Impossible-cycle fallback** | A, B, C1, C2 | `T_evap_sat ≥ T_cond` (thermo guard) | Evap removed; open-loop HP sizing | Prevents division-by-zero / nonphysical cycle |
| **VPD exhaust bypass** | D1, D2, E1, E2, E3 | `vpd_utilization < 0.05` with 3× hysteresis and fixed 600 s dwell | Reroute exhaust directly to condenser, skip HRX | Tiny HP lift, no HRX accounting |
| **E3 cond bypass** (HP off) | E3 only | `T_HRX_out + ΔT_solar_pred ≥ T_set` AND `G > 10 W/m²` | HP fully off, solar alone heats to T_set | W_comp = 0 |
| **Variable T_cond** (E3 HP on) | E3 only | Below E3-bypass threshold, G > 10 | HP lifts to lower T_cond; solar finishes | Smaller HP delta-T, smaller W_comp |

Both VPD-bypass parameters (`vpd_bypass_thresh`, dwell, hysteresis ratio) live in:
- `cfg.dryer.vpd_bypass_thresh` (set on the CLI as `--vpd-threshold 0.05`)
- `_vpd_dwell_s = 600.0` (hard-coded inline at L1074 and L1396)
- `_vpd_utilization > _vpd_thresh * 3.0` (hard-coded hysteresis at L1099, L1421)
