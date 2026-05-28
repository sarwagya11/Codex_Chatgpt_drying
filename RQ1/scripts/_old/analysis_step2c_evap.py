"""Step 2c: Evaporator audit for E1/E2/E3.

Evap stream by variant:
  E1: Amb -> EVAP (parallel)
  E2: ExhCooled + iter. Amb supplement -> EVAP (_iterative_evap_sizing)
  E3: ExhCooled + iter. Amb supplement -> EVAP (same fixed-point routine)

Per CSV check:
  - T_evap operating range (refrigerant side); flag T_evap < T_evap_min (-5 C)
  - T_evap_source range (air-side feed); E1 should track T_amb;
    E2/E3 should sit above E1 (warmer feed via exhaust + supplement)
  - Q_evap stats; pressure ratio P_cond/P_evap (must stay <= 10)
  - flag_evap_oversized fraction (controller out-of-envelope events)
  - COP envelope at hp_mode='full'

Output: outputs/audit/step2c_evap.csv
Plots:  plots/_audit/step2c_evap_*.png  (T_evap_source vs T_amb time series)
"""
from __future__ import annotations

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

T_EVAP_MIN = -5.0   # heatpump.py: refrigerant T_evap floor (R134a)
PR_MAX = 10.0       # heatpump.py: max pressure ratio

REQUIRED = ["T_amb_C", "T_evap_C", "T_evap_source_C", "Q_evap_kW",
            "P_evap_bar", "P_cond_bar", "W_comp_kW", "COP", "time_s", "hp_mode"]


def per_run(csv: Path):
    df = pd.read_csv(csv)
    rel = csv.relative_to(OUT)
    parts = rel.parts
    config = parts[0].replace("config_", "")
    location = parts[1]
    season = parts[2] if len(parts) > 3 else "annual"
    name = csv.stem

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return dict(config=config, location=location, season=season, file=name,
                    status=f"SKIP_missing:{','.join(missing)}")

    Ta = df["T_amb_C"].to_numpy()
    Tev = df["T_evap_C"].to_numpy()
    Tsrc = df["T_evap_source_C"].to_numpy()
    Q = df["Q_evap_kW"].to_numpy()
    Pe = df["P_evap_bar"].to_numpy()
    Pc = df["P_cond_bar"].to_numpy()
    W = df["W_comp_kW"].to_numpy()
    COP = df["COP"].to_numpy()
    mode = df["hp_mode"].astype(str).str.lower().to_numpy()
    dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0

    running = mode == "full"  # COP only meaningful at full lift

    # Boost from exhaust+supplement vs ambient (E2/E3 expected > 0; E1 expected = 0)
    src_boost = Tsrc - Ta

    # Pressure ratio
    PR = np.where(Pe > 0.01, Pc / Pe, np.nan)

    # Flags
    n_frost = int(np.sum((Tev < T_EVAP_MIN - 0.01) & running))
    n_PR_oob = int(np.sum((PR > PR_MAX + 0.01) & running))
    if "flag_evap_oversized" in df.columns:
        n_evap_overs = int(df["flag_evap_oversized"].astype(bool).sum())
    else:
        n_evap_overs = -1
    n_Q_neg = int(np.sum(Q < -1e-3))

    cop_run = COP[running]
    cop_run = cop_run[np.isfinite(cop_run)]

    return dict(
        config=config, location=location, season=season, file=name,
        n_steps=len(df), n_running=int(running.sum()),
        T_evap_min=float(Tev.min()), T_evap_median=float(np.median(Tev)),
        T_evap_max=float(Tev.max()),
        T_evap_source_min=float(Tsrc.min()),
        T_evap_source_median=float(np.median(Tsrc)),
        T_evap_source_max=float(Tsrc.max()),
        src_boost_median=float(np.median(src_boost)),
        src_boost_max=float(np.max(src_boost)),
        Q_evap_kWh=float(np.sum(Q * dt_h)),
        Q_evap_mean_kW_running=float(np.mean(Q[running])) if running.any() else float("nan"),
        PR_median=float(np.nanmedian(PR[running])) if running.any() else float("nan"),
        PR_max=float(np.nanmax(PR[running])) if running.any() else float("nan"),
        COP_median_run=float(np.median(cop_run)) if cop_run.size else float("nan"),
        COP_min_run=float(cop_run.min()) if cop_run.size else float("nan"),
        COP_max_run=float(cop_run.max()) if cop_run.size else float("nan"),
        n_frost=n_frost, n_PR_oob=n_PR_oob,
        n_flag_evap_oversized=n_evap_overs,
        n_Q_neg=n_Q_neg,
        status="",
    )


def make_plot(csv_rel: str, title: str):
    csv = OUT / csv_rel
    df = pd.read_csv(csv)
    t_h = df["time_h"].to_numpy()
    Ta = df["T_amb_C"].to_numpy()
    Tev = df["T_evap_C"].to_numpy()
    Tsrc = df["T_evap_source_C"].to_numpy()
    COP = df["COP"].to_numpy()
    mode = df["hp_mode"].astype(str).str.lower().to_numpy()
    running = mode == "full"

    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(f"{title}  —  evaporator behaviour", fontsize=12)

    ax0 = axes[0]
    ax0.plot(t_h, Ta, label="T_amb", color="tab:gray", lw=0.8)
    ax0.plot(t_h, Tsrc, label="T_evap_source (air feed)", color="tab:blue")
    ax0.plot(t_h, Tev, label="T_evap (refrigerant)", color="tab:cyan")
    ax0.axhline(T_EVAP_MIN, color="red", ls="--", lw=1, label=f"T_evap floor {T_EVAP_MIN}")
    ax0.set_ylabel("Temperature [C]")
    ax0.legend(loc="upper right", fontsize=9)
    ax0.grid(alpha=0.3)

    ax1 = axes[1]
    boost = Tsrc - Ta
    ax1.plot(t_h, boost, color="tab:purple")
    ax1.axhline(0, color="black", lw=0.5)
    ax1.set_ylabel("T_evap_source − T_amb  [C]\n(positive = exh+suppl. boost)")
    ax1.grid(alpha=0.3)

    ax2 = axes[2]
    cop_show = np.where(running, COP, np.nan)
    ax2.plot(t_h, cop_show, color="tab:green", lw=0.8)
    ax2.set_ylabel("COP (HP at full lift)")
    ax2.set_xlabel("Drying time [h]")
    ax2.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    parts = Path(csv_rel).parts
    tag = "_".join([parts[0], parts[1], parts[-2] if len(parts) > 3 else "", Path(csv_rel).stem]).replace("__", "_")
    out = PLOTS / f"step2c_evap_{tag}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def main():
    csvs = sorted([p for p in OUT.glob("config_E*/**/*.csv")])
    rows = [per_run(c) for c in csvs]
    df = pd.DataFrame(rows)
    if "status" not in df.columns:
        df["status"] = ""
    df["status"] = df["status"].fillna("")
    skipped = df[df["status"].astype(str).str.startswith("SKIP")]
    if not skipped.empty:
        print(f"Skipped {len(skipped)} CSVs (missing columns)")
        df = df[~df.index.isin(skipped.index)].copy()
    df.to_csv(AUDIT / "step2c_evap.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2c_evap.csv'} ({len(df)} runs)\n")

    canonical = df[df["file"] == "Ac_10m2_hrx0.70"].copy()
    print(f"=== Canonical 10m2, no VPD ({len(canonical)} runs) ===")
    cols = ["config", "location", "season", "T_evap_median", "T_evap_min",
            "T_evap_source_median", "src_boost_median", "PR_median",
            "COP_median_run", "n_frost", "n_PR_oob", "n_flag_evap_oversized"]
    print(canonical[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\n=== Per-config means (canonical) ===")
    g = canonical.groupby("config")[
        ["T_evap_median", "T_evap_source_median", "src_boost_median",
         "PR_median", "COP_median_run", "Q_evap_kWh"]
    ].mean()
    print(g.to_string(float_format=lambda v: f"{v:.3f}"))

    bad = df[(df["n_frost"] > 0) | (df["n_PR_oob"] > 0) | (df["n_Q_neg"] > 0)]
    print(f"\nRuns with evap anomalies (frost / PR_oob / Q<0): {len(bad)}")
    if not bad.empty:
        print(bad[["config", "location", "season", "n_frost", "n_PR_oob", "n_Q_neg"]].to_string(index=False))

    print("\nGenerating diagnostic plots (one per E variant at KTM annual)...")
    for case in [
        "config_E1/kathmandu/Ac_10m2_hrx0.70.csv",
        "config_E2/kathmandu/Ac_10m2_hrx0.70.csv",
        "config_E3/kathmandu/Ac_10m2_hrx0.70.csv",
    ]:
        if (OUT / case).exists():
            make_plot(case, case)


if __name__ == "__main__":
    main()
