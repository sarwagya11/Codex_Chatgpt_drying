"""Step 2e: Heat-pump whole-cycle audit + E1/E2/E3 verdict.

Per CSV (canonical 10 m2, no VPD):
  - COP_run mean/median/5/95 pct (hp_mode='full' only)
  - W_comp total kWh, run-time hours, duty fraction
  - Q_cond total kWh, Q_evap total kWh, Q_solar_usable total kWh
  - Solar capture eff = Q_solar_usable / Q_solar_gross
  - SEC = (W_comp + W_fan) / m_w   [kWh / kg water]
  - SMER = m_w / (W_comp + W_fan)   [kg water / kWh]
  - Drying time, m_w cumulative

Output: outputs/audit/step2e_hp.csv  + verdict table E1/E2/E3 per location.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
AUDIT.mkdir(parents=True, exist_ok=True)


def per_run(csv: Path):
    df = pd.read_csv(csv)
    rel = csv.relative_to(OUT)
    parts = rel.parts
    config = parts[0].replace("config_", "")
    location = parts[1]
    season = parts[2] if len(parts) > 3 else "annual"

    t_s = df["time_s"].to_numpy()
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    drying_h = float(df["time_h"].iloc[-1])

    mode = df["hp_mode"].astype(str).str.lower().to_numpy()
    full = mode == "full"
    running = full | (mode == "partial")

    W_comp = df["W_comp_kW"].to_numpy()
    Q_cond = df["Q_cond_kW"].to_numpy()
    Q_evap = df["Q_evap_kW"].to_numpy()
    Q_solar_g = df["Q_solar_kW"].to_numpy()
    Q_solar_u = df["Q_solar_usable_kW"].to_numpy() if "Q_solar_usable_kW" in df.columns else Q_solar_g
    W_fan = df["W_fan_kW"].to_numpy() if "W_fan_kW" in df.columns else np.zeros_like(W_comp)
    COP = df["COP"].to_numpy()

    cop_full = COP[full]
    cop_full = cop_full[np.isfinite(cop_full)]

    W_comp_total = float(np.sum(W_comp * dt_h))
    W_fan_total = float(np.sum(W_fan * dt_h))
    Q_cond_total = float(np.sum(Q_cond * dt_h))
    Q_evap_total = float(np.sum(Q_evap * dt_h))
    Q_solar_g_total = float(np.sum(Q_solar_g * dt_h))
    Q_solar_u_total = float(np.sum(Q_solar_u * dt_h))

    m_w = float(df["m_w_cum_kg"].iloc[-1])
    W_total = W_comp_total + W_fan_total

    SEC = W_total / m_w if m_w > 1e-6 else float("nan")
    SMER = m_w / W_total if W_total > 1e-6 else float("nan")
    capture_eff = Q_solar_u_total / Q_solar_g_total if Q_solar_g_total > 1e-6 else float("nan")
    duty_full = float(np.sum(dt_h[full]) / drying_h) if drying_h > 0 else float("nan")
    duty_run = float(np.sum(dt_h[running]) / drying_h) if drying_h > 0 else float("nan")

    return dict(
        config=config, location=location, season=season,
        drying_h=drying_h, m_w_kg=m_w,
        COP_full_mean=float(np.mean(cop_full)) if cop_full.size else float("nan"),
        COP_full_median=float(np.median(cop_full)) if cop_full.size else float("nan"),
        COP_full_5pct=float(np.percentile(cop_full, 5)) if cop_full.size else float("nan"),
        COP_full_95pct=float(np.percentile(cop_full, 95)) if cop_full.size else float("nan"),
        duty_full=duty_full, duty_running=duty_run,
        W_comp_kWh=W_comp_total, W_fan_kWh=W_fan_total, W_total_kWh=W_total,
        Q_cond_kWh=Q_cond_total, Q_evap_kWh=Q_evap_total,
        Q_solar_gross_kWh=Q_solar_g_total, Q_solar_usable_kWh=Q_solar_u_total,
        capture_eff=capture_eff,
        SEC_kWh_per_kg=SEC, SMER_kg_per_kWh=SMER,
    )


def main():
    csvs = sorted([p for p in OUT.glob("config_E*/**/Ac_10m2_hrx0.70.csv")])
    rows = [per_run(c) for c in csvs]
    df = pd.DataFrame(rows)
    df.to_csv(AUDIT / "step2e_hp.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2e_hp.csv'} ({len(df)} runs)\n")

    print("=== Per-run (canonical) ===")
    cols = ["config", "location", "season", "drying_h", "m_w_kg",
            "COP_full_mean", "duty_full",
            "W_total_kWh", "Q_cond_kWh", "Q_evap_kWh", "Q_solar_usable_kWh",
            "capture_eff", "SEC_kWh_per_kg", "SMER_kg_per_kWh"]
    print(df[cols].to_string(index=False, float_format=lambda v: f"{v:8.3f}"))

    print("\n=== Means by config (across all locations/seasons) ===")
    g = df.groupby("config")[
        ["drying_h", "COP_full_mean", "duty_full",
         "W_total_kWh", "Q_solar_usable_kWh", "capture_eff",
         "SEC_kWh_per_kg", "SMER_kg_per_kWh"]
    ].mean()
    print(g.to_string(float_format=lambda v: f"{v:8.4f}"))

    # Annual head-to-head: E1 vs E2 vs E3 at each location
    print("\n=== Annual head-to-head (E1 / E2 / E3) ===")
    annual = df[df["season"] == "annual"].copy()
    for loc in sorted(annual["location"].unique()):
        sub = annual[annual["location"] == loc].set_index("config")
        if not all(c in sub.index for c in ["E1", "E2", "E3"]):
            continue
        print(f"\n--- {loc} ---")
        e1, e2, e3 = sub.loc["E1"], sub.loc["E2"], sub.loc["E3"]
        print(f"  COP_full_mean : E1={e1.COP_full_mean:.3f}  E2={e2.COP_full_mean:.3f}  E3={e3.COP_full_mean:.3f}"
              f"   (E2 vs E1: {(e2.COP_full_mean - e1.COP_full_mean):+.3f},  E3 vs E2: {(e3.COP_full_mean - e2.COP_full_mean):+.3f})")
        print(f"  duty_full     : E1={e1.duty_full:.3f}  E2={e2.duty_full:.3f}  E3={e3.duty_full:.3f}")
        print(f"  W_comp+fan    : E1={e1.W_total_kWh:.3f}  E2={e2.W_total_kWh:.3f}  E3={e3.W_total_kWh:.3f}  kWh")
        print(f"  Q_solar_used  : E1={e1.Q_solar_usable_kWh:.3f}  E2={e2.Q_solar_usable_kWh:.3f}  E3={e3.Q_solar_usable_kWh:.3f}  kWh")
        print(f"  capture_eff   : E1={e1.capture_eff:.3f}  E2={e2.capture_eff:.3f}  E3={e3.capture_eff:.3f}")
        print(f"  SEC           : E1={e1.SEC_kWh_per_kg:.4f}  E2={e2.SEC_kWh_per_kg:.4f}  E3={e3.SEC_kWh_per_kg:.4f}  kWh/kg")
        print(f"  SMER          : E1={e1.SMER_kg_per_kWh:.4f}  E2={e2.SMER_kg_per_kWh:.4f}  E3={e3.SMER_kg_per_kWh:.4f}  kg/kWh")
        winner = sub["SEC_kWh_per_kg"].idxmin()
        print(f"  WINNER (min SEC): {winner}")


if __name__ == "__main__":
    main()
