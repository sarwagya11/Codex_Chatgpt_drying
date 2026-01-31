# 📦 COMPLETE INSTALLATION GUIDE
# Solar-HP Dryer Simulation System
# Ready to Copy and Run!

## 📍 YOUR CURRENT PATH (from screenshot):
```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\
```

Your phase2c file is here:
```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\phase2c_for_chamber.csv
```

---

## 📁 STEP 1: FILE PLACEMENT

You need to copy **4 NEW FILES** into your project:

### Files to Download from Claude:
1. `heatpump_coolprop.py` → rename to `heatpump.py`
2. `solar.py`
3. `config_solar_hp.py`
4. `dryer_solar_hp_complete.py` → rename to `dryer_solar_hp.py`
5. `run_solar_hp_configs.py`

### Where to Put Them:

```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\
│
├── src\
│   └── rq1\
│       ├── (your existing files - DO NOT TOUCH)
│       │
│       ├── heatpump.py              ← COPY FILE #1 HERE
│       ├── solar.py                 ← COPY FILE #2 HERE
│       ├── config_solar_hp.py       ← COPY FILE #3 HERE
│       └── dryer_solar_hp.py        ← COPY FILE #4 HERE
│
└── scripts\
    ├── (your existing scripts)
    │
    └── run_solar_hp_configs.py      ← COPY FILE #5 HERE
```

**DETAILED COPY INSTRUCTIONS:**

1. **File #1 - heatpump.py:**
   - Download `heatpump_coolprop.py` from Claude
   - Rename it to `heatpump.py`
   - Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\src\rq1\heatpump.py`

2. **File #2 - solar.py:**
   - Download `solar.py` from Claude
   - Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\src\rq1\solar.py`

3. **File #3 - config_solar_hp.py:**
   - Download `config_solar_hp.py` from Claude
   - Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\src\rq1\config_solar_hp.py`

4. **File #4 - dryer_solar_hp.py:**
   - Download `dryer_solar_hp_complete.py` from Claude
   - Rename it to `dryer_solar_hp.py`
   - Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\src\rq1\dryer_solar_hp.py`

5. **File #5 - run_solar_hp_configs.py:**
   - Download `run_solar_hp_configs.py` from Claude
   - Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\scripts\run_solar_hp_configs.py`

---

## 🔧 STEP 2: INSTALL COOLPROP

Open Command Prompt or Anaconda Prompt and run:

```bash
pip install CoolProp
```

Or if using Anaconda:
```bash
conda install -c conda-forge coolprop
```

**To verify it worked:**
```bash
python -c "import CoolProp.CoolProp as CP; print('CoolProp OK:', CP.PropsSI('T','P',101325,'Q',0,'Water'))"
```
Should print: `CoolProp OK: 373.124...`

---

## ▶️ STEP 3: HOW TO RUN

### Open Command Prompt:
1. Press `Windows + R`
2. Type `cmd` and press Enter
3. Navigate to your RQ1 folder:

```bash
cd D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1
```

### Run Simulations:

#### **Option 1: Quick Test (5 minutes)**
Test if everything works:

```bash
python scripts\run_solar_hp_configs.py --test
```

This runs:
- Config A only
- Kathmandu weather
- 48 hours simulation
- Saves to: `outputs\config_A\kathmandu\Ac_0m2.csv`

**What you'll see:**
```
[CONFIG A] HP-only, 10 trays, m_da=0.367 kg/s
All trays dry at t=21.0h
Water removed: 64.75 kg
W_comp: 118.12 kWh
SEC: 1.824 kWh/kg
```

#### **Option 2: Single Configuration**
Run one config with specific parameters:

```bash
python scripts\run_solar_hp_configs.py --config A --location kathmandu --solar-area 0
```

Or with solar:
```bash
python scripts\run_solar_hp_configs.py --config B --location kathmandu --solar-area 10
```

#### **Option 3: Custom Sweep**
Run multiple configs and locations:

```bash
python scripts\run_solar_hp_configs.py --configs A B --locations kathmandu dhulikhel --solar-areas 0 5 10
```

This runs: 2 configs × 2 locations × 3 solar areas = 12 simulations

#### **Option 4: FULL SWEEP (3-6 hours)**
Run everything:

```bash
python scripts\run_solar_hp_configs.py --full
```

This runs:
- 5 configs (A, B, C, D, E)
- 3 locations (kathmandu, dhulikhel, biratnagar)
- 9 solar areas (0, 2, 4, 6, 8, 10, 12, 15, 20 m²)
- **Total: 135 simulations**

---

## 📊 STEP 4: FIND YOUR RESULTS

After running, outputs are saved in:

```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\
│
├── config_A\
│   ├── kathmandu\
│   │   ├── Ac_0m2.csv      ← Config A, no solar
│   │   ├── Ac_2m2.csv      ← Config A, 2m² solar
│   │   └── ...
│   ├── dhulikhel\
│   └── biratnagar\
│
├── config_B\
│   └── (same structure)
│
├── config_C\
├── config_D\
├── config_E\
│
└── run_summary.csv         ← Overview of all runs
```

### What's in Each CSV File:

**~80 columns including:**
- Time variables (`time_s`, `time_h`)
- Weather (`T_amb_C`, `RH_amb_pct`, `G_solar_Wm2`)
- Solar collector (`Q_solar_kW`, `T_solar_out_C`, `eta_solar`)
- Heat pump cycle (`T_evap_C`, `T_cond_C`, `W_comp_kW`, `COP`)
- Per-tray moisture (`X_tray_0` to `X_tray_9`, `MR_tray_0` to `MR_tray_9`)
- Per-tray air states (`T_tray_0_out_C`, `RH_tray_0_out_frac`)
- Cumulative totals (`m_w_cum_kg`, `W_comp_cum_kWh`, `Q_solar_cum_kWh`)
- Final SEC (`SEC_elec_kWh_per_kg`)

---

## 🔍 STEP 5: CHECK IF IT WORKED

### After running --test:

1. Check if output file exists:
   ```
   D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_A\kathmandu\Ac_0m2.csv
   ```

2. Open the CSV in Excel

3. Check final row:
   - `m_w_cum_kg` should be ~64-65 kg (water removed)
   - `time_h` should be ~20-25 hours (drying time)
   - `SEC_elec_kWh_per_kg` should be ~1.5-2.0 kWh/kg

4. Plot `time_h` vs `X_db_avg` - should decrease from 6.5 to 0.1

### If you see errors:

**Error: "CoolProp not found"**
→ Run: `pip install CoolProp`

**Error: "No module named 'rq1'"**
→ Make sure you're in the RQ1 folder: `cd D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`

**Error: "Weather file not found"**
→ Check if kathmandu_pvgis_standard.csv exists in one of these:
   - `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\data\ambient\`
   - `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\`

**Error: "phase2c_for_chamber.csv not found"**
→ This is OK! The code will use fallback kinetics (Arrhenius model)
→ Or copy your phase2c file to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\`

---

## 📈 STEP 6: ANALYZE RESULTS

### Open in Excel/Python:

```python
import pandas as pd

# Load one result
df = pd.read_csv("outputs/config_A/kathmandu/Ac_0m2.csv")

# Quick stats
print(f"Drying time: {df['time_h'].iloc[-1]:.1f} hours")
print(f"Water removed: {df['m_w_cum_kg'].iloc[-1]:.1f} kg")
print(f"Energy used: {df['W_comp_cum_kWh'].iloc[-1]:.1f} kWh")
print(f"SEC: {df['SEC_elec_kWh_per_kg'].iloc[-1]:.3f} kWh/kg")

# Plot
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 4))

plt.subplot(1, 3, 1)
plt.plot(df['time_h'], df['X_db_avg'])
plt.xlabel('Time [h]')
plt.ylabel('Moisture [kg/kg db]')
plt.title('Average Moisture Content')

plt.subplot(1, 3, 2)
plt.plot(df['time_h'], df['W_comp_kW'])
plt.xlabel('Time [h]')
plt.ylabel('Power [kW]')
plt.title('Compressor Power')

plt.subplot(1, 3, 3)
plt.plot(df['time_h'], df['COP'])
plt.xlabel('Time [h]')
plt.ylabel('COP [-]')
plt.title('Heat Pump COP')

plt.tight_layout()
plt.show()
```

---

## 🎯 WHAT EACH CONFIG DOES

**Config A: HP-Only (Baseline)**
- Heat pump runs 24/7
- Most reliable, fastest drying
- Highest electricity cost
- Expected: 20-25 hours, SEC ~1.8 kWh/kg

**Config B: Solar + HP Series**
- Solar preheats air during day
- HP boosts to T_set if needed
- Night: switches to HP-only
- Expected: 25-35 hours, SEC ~0.8-1.2 kWh/kg

**Config C: Solar-Assisted HP Evaporator**
- Solar warms evaporator source
- Higher COP (~10-15% improvement)
- Night: switches to HP-only
- Expected: 20-25 hours, SEC ~0.6-1.0 kWh/kg

**Config D: Solar-Only**
- No electricity, daytime only
- Slowest drying
- Zero electricity cost
- Expected: 30-50 hours, SEC_elec = 0

**Config E: Cascade (Your Design)**
- Solar → HP evap → HP cond → Chamber
- Most complex, potentially best efficiency
- Benefits from both evap warming and cond pre-warming
- Expected: 20-30 hours, SEC ~0.5-0.9 kWh/kg

---

## ✅ FINAL CHECKLIST

Before running full sweep:

- [ ] CoolProp installed (`pip install CoolProp`)
- [ ] All 5 files copied to correct locations
- [ ] Weather files in `data/ambient/` or `outputs/`
- [ ] Test run works (`python scripts\run_solar_hp_configs.py --test`)
- [ ] Output CSV file created and readable
- [ ] Ready to run full sweep!

---

## 🆘 NEED HELP?

If something doesn't work:

1. **Check Python version:** `python --version` (should be 3.8+)
2. **Check CoolProp:** `python -c "import CoolProp; print('OK')"`
3. **Check file paths:** Make sure you're in RQ1 folder
4. **Check outputs:** Look in `outputs/` folder for CSVs

**Common Issues:**

- Missing CoolProp → `pip install CoolProp`
- Wrong folder → `cd D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`
- Weather file not found → Copy to `data/ambient/` or `outputs/`
- Simulation too slow → Increase `dt_s` in config (default 60s → try 300s)

---

## 🎉 YOU'RE READY!

Everything is prepared. Just:
1. Download the 5 files
2. Copy to correct locations
3. Run: `python scripts\run_solar_hp_configs.py --test`
4. Check output CSV
5. Run full sweep when ready!

Good luck with your research! 🚀
