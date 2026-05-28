"""Step 2a: Solar collector behaviour audit for E1/E2/E3.

Per CSV, characterise the solar collector:
  - Operating envelope: G range, T_solar_in/out range
  - Efficiency curve: eta_sol vs (T_in - T_amb)/G  (Hottel-Whillier-Bliss form)
  - Daily Q_solar (kWh) vs daily insolation (kWh/m2)
  - Clipping: how much potential solar was thrown away (Q_solar_clipped)
  - Anomaly flags: negative gain at G>0, eta_sol > 0.85 or < 0, T_solar_out > T_in when G==0

Per-config aggregate written to outputs/audit/step2a_solar.csv.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
AUDIT.mkdir(parents=True, exist_ok=True)

# Solar area sniffed from filename "Ac_<N>m2_..."
import re
_AREA_RE = re.compile(r"Ac_(\d+)m2")


def area_from_name(name: str) -> float:
    m = _AREA_RE.search(name)
    return float(m.group(1)) if m else float("nan")


REQUIRED = ["G_solar_Wm2", "T_solar_out_C", "T_amb_C", "Q_solar_kW", "eta_solar", "time_s"]


def per_run(csv: Path):
    df = pd.read_csv(csv)
    rel = csv.relative_to(OUT)
    parts = rel.parts
    config = parts[0].replace("config_", "")
    location = parts[1]
    season = parts[2] if len(parts) > 3 else "annual"
    name = csv.stem
    A = area_from_name(name)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return dict(config=config, location=location, season=season, file=name,
                    A_m2=A, status=f"SKIP_missing:{','.join(missing)}")

    G = df["G_solar_Wm2"].to_numpy()
    if "T_solar_in_C" in df.columns:
        Tin = df["T_solar_in_C"].to_numpy()
    else:
        Tin = df["T_amb_C"].to_numpy()  # fallback for older CSVs (open-loop only)
    Tout = df["T_solar_out_C"].to_numpy()
    Tamb = df["T_amb_C"].to_numpy()
    Q = df["Q_solar_kW"].to_numpy()
    Q_clip = df["Q_solar_clipped_kW"].to_numpy() if "Q_solar_clipped_kW" in df.columns else np.zeros_like(Q)
    eta = df["eta_solar"].to_numpy()
    dt_s = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0])
    dt_h = dt_s / 3600.0

    on = G > 50.0  # daytime mask, ignore noise
    on_n = int(on.sum())

    # Energy totals
    Q_total_kWh = float(np.sum(Q * dt_h))
    Q_clip_kWh = float(np.sum(Q_clip * dt_h))
    insol_kWh_per_m2 = float(np.sum(G * dt_h) / 1000.0)
    avail_kWh = insol_kWh_per_m2 * A if np.isfinite(A) else float("nan")

    # Mean efficiency over daytime steps (energy-weighted)
    if on_n > 0 and np.sum(G[on]) > 0:
        eta_mean = float(np.sum(eta[on] * G[on]) / np.sum(G[on]))
    else:
        eta_mean = float("nan")

    # HWB-style efficiency vs reduced T (T_in - T_amb)/G
    valid = on & (G > 100) & np.isfinite(eta)
    eta_lo = float(np.percentile(eta[valid], 5)) if valid.any() else float("nan")
    eta_hi = float(np.percentile(eta[valid], 95)) if valid.any() else float("nan")

    # Anomalies
    n_neg_gain = int(np.sum((Q < -1e-6) & on))
    n_eta_oob = int(np.sum(((eta > 0.95) | (eta < -0.05)) & on))
    n_T_out_gt_in_dark = int(np.sum((Tout - Tin > 0.5) & ~on))

    # Operating envelope
    return dict(
        config=config, location=location, season=season, file=name,
        A_m2=A,
        n_steps=len(df), n_daytime=on_n,
        G_max_Wm2=float(np.nanmax(G)) if G.size else float("nan"),
        T_in_min_C=float(np.nanmin(Tin)) if Tin.size else float("nan"),
        T_in_max_C=float(np.nanmax(Tin)) if Tin.size else float("nan"),
        T_out_max_C=float(np.nanmax(Tout)) if Tout.size else float("nan"),
        deltaT_max_C=float(np.nanmax(Tout - Tin)) if Tout.size else float("nan"),
        eta_mean_daytime=eta_mean,
        eta_5pct=eta_lo, eta_95pct=eta_hi,
        Q_solar_kWh=Q_total_kWh,
        Q_clipped_kWh=Q_clip_kWh,
        clip_frac=Q_clip_kWh / Q_total_kWh if Q_total_kWh > 0 else 0.0,
        insol_kWh_per_m2=insol_kWh_per_m2,
        avail_kWh=avail_kWh,
        capture_eff=Q_total_kWh / avail_kWh if avail_kWh and avail_kWh > 0 else float("nan"),
        n_neg_gain=n_neg_gain,
        n_eta_oob=n_eta_oob,
        n_T_out_gt_in_dark=n_T_out_gt_in_dark,
    )


def main():
    csvs = sorted([p for p in OUT.glob("config_E*/**/*.csv")])
    rows = [per_run(c) for c in csvs]
    df = pd.DataFrame(rows)
    if "status" not in df.columns:
        df["status"] = ""
    df["status"] = df["status"].fillna("")
    skipped = df[df["status"].astype(str).str.startswith("SKIP")]
    if not skipped.empty:
        print(f"Skipped {len(skipped)} CSVs (missing columns):")
        for _, r in skipped.iterrows():
            print(f"  {r['config']} {r['location']} {r['season']} {r['file']}")
        df = df[~df.index.isin(skipped.index)].copy()
    df.to_csv(AUDIT / "step2a_solar.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2a_solar.csv'}  ({len(df)} runs)\n")

    # Quick anomaly summary
    bad = df[(df["n_neg_gain"] > 0) | (df["n_eta_oob"] > 0) | (df["n_T_out_gt_in_dark"] > 0)]
    print(f"Runs with solar anomalies: {len(bad)}")
    if not bad.empty:
        cols = ["config", "location", "season", "n_neg_gain", "n_eta_oob", "n_T_out_gt_in_dark"]
        print(bad[cols].to_string(index=False))

    # Per (config, location, season) summary on the canonical 10 m2 + vpd0.05 file
    canonical = df[df["file"].str.contains("Ac_10m2") & df["file"].str.contains("vpd0.05")].copy()
    print("\n=== Canonical 10m2 + VPD=0.05 runs ===")
    cols = ["config", "location", "season", "eta_mean_daytime", "Q_solar_kWh",
            "clip_frac", "capture_eff", "deltaT_max_C", "T_out_max_C"]
    print(canonical[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    # Aggregate by config (mean across canonical runs)
    print("\n=== Per-config means (canonical runs) ===")
    g = canonical.groupby("config")[["eta_mean_daytime", "Q_solar_kWh",
                                     "clip_frac", "capture_eff", "deltaT_max_C"]].mean()
    print(g.to_string(float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
