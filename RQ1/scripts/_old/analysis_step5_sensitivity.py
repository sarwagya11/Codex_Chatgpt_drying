"""Step 5 — Sensitivity sweeps.

Consolidates four sensitivity axes for E2 (recommended config):

  (a) collector area A_c  (2..20 m²)   — main NEW analysis
  (b) location             (BTN/KTM/TPJ annual + Dhulikhel)
  (c) season               (autumn/winter/spring × 4 locations)
  (d) M1 vs M2 kinetics    — pulled from phase_d_sec_delta.csv

VPD threshold sensitivity already covered in Step 2g sweep.

Outputs:
  outputs/audit/step5_area_sweep.csv
  outputs/audit/step5_season_location.csv
  plots/_audit/step5_area_sweep.png
  plots/_audit/step5_season_heatmap.png
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
PLOTS = PROJECT_ROOT / "plots" / "_audit"
AUDIT.mkdir(parents=True, exist_ok=True)
PLOTS.mkdir(parents=True, exist_ok=True)


def trapz_kWh(s, t_s):
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    return float(np.sum(np.asarray(s) * dt_h))


def metrics_from_csv(csv: Path) -> dict:
    df = pd.read_csv(csv)
    t_s = df["time_s"].to_numpy()
    Wc = trapz_kWh(df["W_comp_kW"], t_s)
    Wf = trapz_kWh(df["W_fan_kW"], t_s) if "W_fan_kW" in df.columns else 0.0
    Wt = Wc + Wf
    Qsg = trapz_kWh(df["Q_solar_kW"], t_s)
    Qsu = (trapz_kWh(df["Q_solar_usable_kW"], t_s)
           if "Q_solar_usable_kW" in df.columns else Qsg)
    Qsc = max(Qsg - Qsu, 0.0)
    mw = float(df["m_w_cum_kg"].iloc[-1])
    th = float(df["time_h"].iloc[-1])
    return dict(t_h=th, m_w=mw, W_total=Wt,
                Q_solar_gross=Qsg, Q_solar_usable=Qsu, Q_solar_clipped=Qsc,
                clip_frac=Qsc/Qsg if Qsg > 1e-6 else 0.0,
                SEC=Wt/mw if mw > 1e-6 else float("nan"),
                SMER=mw/Wt if Wt > 1e-6 else float("nan"))


# ----- (a) area sweep on E2 annual -----
def area_sweep() -> pd.DataFrame:
    rows = []
    pat = re.compile(r"Ac_(\d+)m2_hrx0\.70\.csv$")
    for csv in OUT.glob("config_E2/*/Ac_*m2_hrx0.70.csv"):
        # only annual (parent is location dir, not season)
        if "season" in csv.parent.name or csv.parent.parent.name != "outputs":
            # parent.parent for annual: outputs/config_E2/<loc>/  -> grandparent is config_E2
            pass
        m = pat.search(csv.name)
        if not m:
            continue
        rel = csv.relative_to(OUT)
        if len(rel.parts) > 3:  # skip seasonal
            continue
        location = rel.parts[1]
        Ac = int(m.group(1))
        try:
            r = metrics_from_csv(csv)
        except Exception as e:
            print(f"  skip {rel}: {e}")
            continue
        r["location"] = location
        r["A_collector_m2"] = Ac
        rows.append(r)
    return pd.DataFrame(rows).sort_values(["location", "A_collector_m2"])


def plot_area_sweep(df: pd.DataFrame, out_path: Path):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("E2 collector-area sweep (annual, no-VPD)", fontsize=12, weight="bold")
    colors = {"biratnagar": "tab:red", "kathmandu": "tab:blue", "taplejung": "tab:green"}

    ax = axes[0]
    for loc, sub in df.groupby("location"):
        ax.plot(sub["A_collector_m2"], sub["SEC"], "o-",
                color=colors.get(loc, "k"), label=loc, lw=1.6)
    ax.axvline(10, color="black", ls="--", lw=1, label="canonical 10 m²")
    ax.set_xlabel("Collector area [m²]")
    ax.set_ylabel("SEC [kWh/kg]")
    ax.set_title("SEC vs area")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    for loc, sub in df.groupby("location"):
        ax.plot(sub["A_collector_m2"], sub["t_h"], "o-",
                color=colors.get(loc, "k"), label=loc, lw=1.6)
    ax.axvline(10, color="black", ls="--", lw=1)
    ax.set_xlabel("Collector area [m²]")
    ax.set_ylabel("Drying time [h]")
    ax.set_title("Drying time vs area")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[2]
    for loc, sub in df.groupby("location"):
        ax.plot(sub["A_collector_m2"], sub["clip_frac"] * 100, "o-",
                color=colors.get(loc, "k"), label=loc, lw=1.6)
    ax.axvline(10, color="black", ls="--", lw=1)
    ax.set_xlabel("Collector area [m²]")
    ax.set_ylabel("Solar clipping [%]")
    ax.set_title("Clipping fraction vs area")
    ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path.relative_to(PROJECT_ROOT)}")


# ----- (b)+(c) season × location heatmap (E2 SEC) -----
def season_location() -> pd.DataFrame:
    rows = []
    for csv in OUT.glob("config_E2/**/Ac_10m2_hrx0.70.csv"):
        rel = csv.relative_to(OUT)
        location = rel.parts[1]
        season = rel.parts[2] if len(rel.parts) > 3 else "annual"
        try:
            r = metrics_from_csv(csv)
        except Exception:
            continue
        r["location"] = location
        r["season"] = season
        rows.append(r)
    return pd.DataFrame(rows)


def plot_season_heatmap(df: pd.DataFrame, out_path: Path):
    pivot = df.pivot_table(index="location", columns="season", values="SEC")
    season_order = ["winter_dec_jan", "spring_mar_apr", "autumn_oct_nov", "annual"]
    pivot = pivot[[c for c in season_order if c in pivot.columns]]
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.3f}", ha="center", va="center",
                        color="black", fontsize=9)
    ax.set_title("E2 SEC [kWh/kg] — season × location (no-VPD, A=10 m²)")
    fig.colorbar(im, ax=ax, label="SEC [kWh/kg]")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path.relative_to(PROJECT_ROOT)}")


# ----- (d) M1 vs M2 (phase D) -----
def m1_vs_m2() -> pd.DataFrame:
    csv = AUDIT / "phase_d_sec_delta.csv"
    if not csv.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv)
    return df


def main():
    # (a) area sweep
    print("=== (a) E2 collector-area sweep ===")
    df_area = area_sweep()
    df_area.to_csv(AUDIT / "step5_area_sweep.csv", index=False, float_format="%.6g")
    pivot = df_area.pivot_table(index="A_collector_m2", columns="location",
                                values="SEC")
    print(pivot.to_string(float_format=lambda v: f"{v:7.4f}"))
    print("\nDrying time [h] vs area:")
    print(df_area.pivot_table(index="A_collector_m2", columns="location",
                              values="t_h").to_string(float_format=lambda v: f"{v:6.2f}"))
    print("\nClipping fraction [%] vs area:")
    print((df_area.pivot_table(index="A_collector_m2", columns="location",
                               values="clip_frac") * 100)
          .to_string(float_format=lambda v: f"{v:6.2f}"))
    plot_area_sweep(df_area, PLOTS / "step5_area_sweep.png")

    # (b)+(c) season × location
    print("\n=== (b+c) season × location E2 SEC ===")
    df_sl = season_location()
    df_sl.to_csv(AUDIT / "step5_season_location.csv", index=False, float_format="%.6g")
    print(df_sl.pivot_table(index="location", columns="season", values="SEC")
          .to_string(float_format=lambda v: f"{v:7.4f}"))
    plot_season_heatmap(df_sl, PLOTS / "step5_season_heatmap.png")

    # (d) M1 vs M2
    print("\n=== (d) M1 vs M2 kinetics ===")
    df_k = m1_vs_m2()
    if not df_k.empty:
        print(f"phase_d_sec_delta has {len(df_k)} rows")
        if "config" in df_k.columns and "SEC_rel_delta_pct" in df_k.columns:
            e_only = df_k[df_k["config"].isin(["E1", "E2", "E3"])]
            if not e_only.empty:
                print("\nM2 SEC delta vs M1 (% change) for E configs:")
                print(e_only.groupby("config")["SEC_rel_delta_pct"]
                      .agg(["mean", "min", "max", "count"])
                      .to_string(float_format=lambda v: f"{v:7.2f}"))
                print("\nFull table:")
                print(e_only.to_string(index=False, float_format=lambda v: f"{v:7.4f}"))


if __name__ == "__main__":
    main()
