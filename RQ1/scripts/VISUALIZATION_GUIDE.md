# 📊 VISUALIZATION GUIDE
## How to Create Plots from Your Simulation Results

---

## 🎨 WHAT VISUALIZATIONS YOU'LL GET

For each simulation, you get **5 comprehensive plots**:

### 1. **Overview Plot** (6 panels)
- Moisture content (average + first/last tray)
- Temperature profile (ambient, inlet, exhaust, solar)
- Heat pump COP over time
- Energy flows (power + cumulative)
- Relative humidity profile
- Cumulative water removed

### 2. **Tray Evolution Plot** (2 panels)
- Moisture content for all 10 trays
- Moisture ratio for all 10 trays
- Color-coded from Tray 0 (first) to Tray 9 (last)

### 3. **Heat Pump Performance** (4 panels)
- Evaporator & condenser temperatures
- Evaporator & condenser pressures
- Heat flows (Q_evap, Q_cond, W_comp)
- COP & refrigerant mass flow

### 4. **Solar Performance** (4 panels - if solar used)
- Solar irradiance & useful heat
- Solar collector efficiency
- Temperature boost from solar
- Cumulative energy comparison

### 5. **Energy Summary** (2 panels)
- Bar chart: energy breakdown
- Text summary: key metrics (water removed, time, SEC, COP)

---

## 📥 STEP 1: COPY VISUALIZATION FILES

Download and copy these 2 files:

**File 1:** `visualize_results.py`
- Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\scripts\`

**File 2:** `batch_plot.py`
- Copy to: `D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1\scripts\`

---

## ▶️ STEP 2: CREATE PLOTS

Open Command Prompt and navigate to your RQ1 folder:
```bash
cd D:\Masters\RQ5\Codex_Chatgpt_drying\RQ1
```

### **Option 1: Plot ONE Simulation**

```bash
python scripts\visualize_results.py outputs\config_A\kathmandu\Ac_0m2.csv
```

This creates 5 plots and **displays them on screen**.

To **save the plots** instead of displaying:
```bash
python scripts\visualize_results.py outputs\config_A\kathmandu\Ac_0m2.csv plots\
```

**Output:**
```
plots\
├── Ac_0m2_overview.png
├── Ac_0m2_trays.png
├── Ac_0m2_heatpump.png
├── Ac_0m2_solar.png
└── Ac_0m2_summary.png
```

### **Option 2: Plot ALL Your Results at Once**

```bash
python scripts\batch_plot.py --all
```

This finds ALL CSV files in `outputs\` and creates plots for each.

**Output:**
```
plots\
├── config_A\
│   ├── kathmandu\
│   │   ├── Ac_0m2_overview.png
│   │   ├── Ac_0m2_trays.png
│   │   ├── Ac_0m2_heatpump.png
│   │   ├── Ac_0m2_solar.png
│   │   ├── Ac_0m2_summary.png
│   │   ├── Ac_2m2_overview.png
│   │   └── ...
│   ├── dhulikhel\
│   └── biratnagar\
├── config_B\
├── config_C\
├── config_D\
└── config_E\
```

### **Option 3: Plot One Configuration**

```bash
python scripts\batch_plot.py --config A
```

Creates plots for ALL Config A results.

Or for specific location:
```bash
python scripts\batch_plot.py --config B --location kathmandu
```

### **Option 4: Plot Specific File**

```bash
python scripts\batch_plot.py --file outputs\config_A\kathmandu\Ac_0m2.csv
```

---

## 📊 STEP 3: VIEW YOUR PLOTS

### **Method 1: Open PNG files**
Just double-click any `.png` file in the `plots\` folder

### **Method 2: Open in PowerPoint/Word**
Insert → Pictures → Select your plots

### **Method 3: View in Python** (for analysis)
```python
from PIL import Image
import matplotlib.pyplot as plt

img = Image.open("plots/config_A/kathmandu/Ac_0m2_overview.png")
plt.figure(figsize=(16, 10))
plt.imshow(img)
plt.axis('off')
plt.show()
```

---

## 🔍 WHAT TO LOOK FOR IN PLOTS

### **Overview Plot - CHECK:**
1. **Moisture Content** (Panel 1):
   - Should decrease from 6.5 to 0.1 kg/kg
   - Tray 0 dries first, Tray 9 dries last
   - All trays reach target (0.1)

2. **Temperature Profile** (Panel 2):
   - Inlet should be steady at 50°C (Config A)
   - Exhaust should be lower (30-40°C)
   - Solar outlet shows daytime heating (Config B-E)

3. **Heat Pump COP** (Panel 3):
   - Should be 2.5-4.5 (typical range)
   - Lower at night (colder ambient)
   - Average shown as dashed line

4. **Energy Flows** (Panel 4):
   - Compressor power steady or varying
   - Solar power follows sun (daytime peaks)
   - Cumulative increases over time

5. **Relative Humidity** (Panel 5):
   - Exhaust RH should be high (60-95%)
   - Never exceed 100%
   - Inlet RH low (~10-30%)

6. **Water Removed** (Panel 6):
   - Should reach target (~64 kg for 10 kg dry mass)
   - Increases over time
   - Levels off when dry

### **Tray Evolution - CHECK:**
- Trays dry in sequence (0 → 9)
- Tray 0 reaches target first
- All trays converge to 0.1 kg/kg
- No trays stuck at high moisture

### **Heat Pump Performance - CHECK:**
- T_evap: 0-15°C (typical)
- T_cond: 55-65°C (typical)
- Pressures stable
- COP > 2.0

### **Solar Performance - CHECK:**
- Efficiency: 40-70% during sunny hours
- Temperature boost during day
- Solar energy reduces compressor energy

### **Energy Summary - CHECK:**
- SEC (kWh/kg):
  - Config A: 1.5-2.0
  - Config B: 0.8-1.5
  - Config C: 0.6-1.2
  - Config D: 0.0 (solar only)
  - Config E: 0.5-1.0
- COP: 2.5-4.5

---

## ⚠️ WARNING SIGNS IN PLOTS

**RED FLAGS - Something is Wrong:**

1. **Moisture NOT decreasing**
   → Check kinetics, check air flow

2. **COP < 1.5 or > 6.0**
   → Heat pump problem, check temperatures

3. **RH > 100%**
   → Physics error, condensation not handled

4. **Temperature jumps/discontinuities**
   → Numerical instability, reduce dt_s

5. **Tray 9 dries before Tray 0**
   → Flow direction reversed!

6. **No solar heat despite high irradiance**
   → Solar collector not working

7. **Compressor power = 0 all the time**
   → Heat pump not running (Config A should always run)

---

## 💡 TIPS FOR BETTER PLOTS

### **Make Plots Bigger:**
Edit `visualize_results.py` line 25:
```python
fig = plt.figure(figsize=(20, 12))  # Increase from (16, 10)
```

### **Save as High-Res PDF:**
Edit line ~100:
```python
fig.savefig(output_path.with_suffix('.pdf'), dpi=300, bbox_inches='tight')
```

### **Change Color Scheme:**
Line 235 (tray colors):
```python
colors = plt.cm.plasma(np.linspace(0, 1, 10))  # Change viridis to plasma
```

### **Add More Details:**
Uncomment debug sections or add your own:
```python
ax1.text(0.5, 0.95, f"SEC = {sec:.3f} kWh/kg", transform=ax1.transAxes)
```

---

## 📈 ANALYZE RESULTS PROGRAMMATICALLY

If you want to do more analysis in Python:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load result
df = pd.read_csv("outputs/config_A/kathmandu/Ac_0m2.csv")

# Custom plot
fig, ax = plt.subplots(figsize=(10, 6))

# Plot what you want
ax.plot(df['time_h'], df['X_db_avg'], 'b-', linewidth=2)
ax.set_xlabel('Time [h]')
ax.set_ylabel('Moisture [kg/kg db]')
ax.set_title('My Custom Plot')
ax.grid(True)

plt.savefig('my_plot.png', dpi=300)
plt.show()

# Calculate statistics
print(f"Average COP: {df['COP'].mean():.2f}")
print(f"Max compressor power: {df['W_comp_kW'].max():.2f} kW")
print(f"Total solar energy: {df['Q_solar_cum_kWh'].iloc[-1]:.1f} kWh")
```

---

## ✅ CHECKLIST

Before submitting results:

- [ ] Created plots for ALL configurations
- [ ] Checked all plots for errors/warnings
- [ ] SEC values are reasonable
- [ ] Moisture reaches target in all trays
- [ ] COP values are realistic (2-5)
- [ ] Solar is working (if used)
- [ ] No NaN or Inf values
- [ ] Plots saved as high-res PNG

---

## 🆘 TROUBLESHOOTING

**Error: "No module named 'matplotlib'"**
→ `pip install matplotlib`

**Error: "File not found"**
→ Check path is correct, use full path if needed

**Plots look weird/corrupted**
→ Try saving as PDF instead of PNG

**Text too small**
→ Increase `figsize` and `dpi` parameters

**Takes too long**
→ Don't plot all at once, do one config at a time

---

## 🎉 YOU'RE READY!

Now you can:
1. Run simulations
2. Create beautiful plots
3. Analyze results
4. Write your thesis!

**Happy plotting!** 📊✨
