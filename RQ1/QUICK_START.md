# 🚀 QUICK START GUIDE
## Solar-HP Dryer Simulation - Ready to Run!

---

## 📥 STEP 1: DOWNLOAD THESE 5 FILES

1. **heatpump_coolprop.py** → Rename to `heatpump.py`
2. **solar.py**
3. **config_solar_hp.py**
4. **dryer_solar_hp_complete.py** → Rename to `dryer_solar_hp.py`
5. **run_solar_hp_configs.py**

---

## 📂 STEP 2: COPY TO THESE LOCATIONS

```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\src\rq1\
    ├── heatpump.py              (FILE #1)
    ├── solar.py                 (FILE #2)
    ├── config_solar_hp.py       (FILE #3)
    └── dryer_solar_hp.py        (FILE #4)

D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\scripts\
    └── run_solar_hp_configs.py  (FILE #5)
```

---

## ⚙️ STEP 3: INSTALL COOLPROP

Open Command Prompt:
```bash
pip install CoolProp
```

---

## ▶️ STEP 4: RUN TEST

Open Command Prompt:
```bash
cd D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1
python scripts\run_solar_hp_configs.py --test
```

**Should see:**
```
[CONFIG A] HP-only, 10 trays, m_da=0.367 kg/s
All trays dry at t=21.0h
Water removed: 64.75 kg
SEC: 1.824 kWh/kg
```

**Output file:**
```
D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\outputs\config_A\kathmandu\Ac_0m2.csv
```

---

## 🎯 STEP 5: RUN FULL SWEEP

```bash
python scripts\run_solar_hp_configs.py --full
```

**Runs:**
- 5 configs × 3 locations × 9 solar areas = 135 simulations
- Takes: 3-6 hours
- Outputs: 135 CSV files in `outputs/` folder

---

## 📊 OUTPUTS

Each CSV has ~80 columns:
- Time, weather, solar, heat pump states
- 10 trays moisture content
- Energy flows and totals
- Final SEC (kWh/kg water removed)

**Example analysis:**
```python
import pandas as pd
df = pd.read_csv("outputs/config_A/kathmandu/Ac_0m2.csv")
print(f"SEC: {df['SEC_elec_kWh_per_kg'].iloc[-1]:.3f} kWh/kg")
```

---

## 🔧 OTHER RUN OPTIONS

**Single config:**
```bash
python scripts\run_solar_hp_configs.py --config A --location kathmandu --solar-area 0
```

**Custom sweep:**
```bash
python scripts\run_solar_hp_configs.py --configs A B --locations kathmandu --solar-areas 0 5 10
```

---

## ❓ TROUBLESHOOTING

**Error: CoolProp not found**
→ `pip install CoolProp`

**Error: No module rq1**
→ Make sure you're in: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1`

**Error: Weather file not found**
→ Put `kathmandu_pvgis_standard.csv` in:
   - `data\ambient\` OR
   - `outputs\`

**Simulation slow?**
→ Normal! Each simulation takes 1-5 minutes

---

## ✅ SUCCESS CHECKLIST

- [ ] Downloaded all 5 files
- [ ] Copied to correct folders
- [ ] Installed CoolProp
- [ ] Test run completed
- [ ] Output CSV file created
- [ ] Ready for full sweep!

---

## 🎉 YOU'RE DONE!

Everything is ready. Your simulation system includes:
✅ 5 dryer configurations
✅ Heat pump thermodynamics (CoolProp)
✅ Solar thermal collector
✅ 10-tray cascade chamber
✅ Phase-2 Midilli kinetics
✅ Complete energy tracking

**Just run and analyze results!**
