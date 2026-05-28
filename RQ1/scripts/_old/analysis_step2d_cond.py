"""Step 2d: Condenser audit for E1/E2/E3.

Per CSV checks:
  - T_cond range; flag T_cond > T_cond_max (70 C, R134a limit in heatpump.py)
  - Air-side: T_air_in_cond, T_cond_out, achieved eps_cond
        eps_cond_achieved = (T_cond_out - T_air_in_cond) / (T_cond_sat - T_air_in_cond)
        with T_cond_sat = T_cond_target + 10 (heatpump.py line ~1727,1686)
  - Approach dT to chamber: T_set - T_to_chamber  (E1/E2 should hit T_set exactly,
    E3 may sit below at high solar)
  - Q_cond statistics
  - flag_cond_oversized fraction
  - E3 partial-lift behaviour: T_cond_target time series, hp_mode distribution

Output: outputs/audit/step2d_cond.csv
Plots: plots/_audit/step2d_cond_*.png
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

T_COND_MAX = 70.0
T_SET = 45.0
EPS_COND_TARGET = 0.85  # heatpump.py (typical, verify below)

REQUIRED = ["T_cond_C", "T_air_in_cond_C", "T_cond_out_C", "T_cond_target_C",
            "T_to_chamber_C", "Q_cond_kW", "time_s", "hp_mode"]


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

    Tc = df["T_cond_C"].to_numpy()
    Ta_in = df["T_air_in_cond_C"].to_numpy()
    Tc_out = df["T_cond_out_C"].to_numpy()
    Tc_tgt = df["T_cond_target_C"].to_numpy()
    Tch = df["T_to_chamber_C"].to_numpy()
    Q = df["Q_cond_kW"].to_numpy()
    mode = df["hp_mode"].astype(str).str.lower().to_numpy()
    dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0

    running = mode == "full"

    # Achieved eps_cond on full-lift steps
    Tcs = Tc_tgt + 10.0
    denom = Tcs - Ta_in
    eps_a = np.where((denom > 1.0) & running, (Tc_out - Ta_in) / np.maximum(denom, 1e-6), np.nan)
    eps_med = float(np.nanmedian(eps_a)) if np.any(np.isfinite(eps_a)) else float("nan")
    eps_5 = float(np.nanpercentile(eps_a, 5)) if np.any(np.isfinite(eps_a)) else float("nan")
    eps_95 = float(np.nanpercentile(eps_a, 95)) if np.any(np.isfinite(eps_a)) else float("nan")

    # Approach to T_set
    approach = T_SET - Tch
    approach_med = float(np.median(approach))
    approach_max = float(np.max(approach))

    # Mode breakdown
    mode_counts = pd.Series(mode).value_counts(normalize=True).to_dict()

    n_oob_Tcond = int(np.sum(Tc > T_COND_MAX + 0.01))
    if "flag_cond_oversized" in df.columns:
        n_flag = int(df["flag_cond_oversized"].astype(bool).sum())
    else:
        n_flag = -1
    n_Q_neg = int(np.sum(Q < -1e-3))

    return dict(
        config=config, location=location, season=season, file=name,
        n_steps=len(df),
        T_cond_min=float(Tc.min()), T_cond_median=float(np.median(Tc)),
        T_cond_max=float(Tc.max()),
        T_cond_target_median=float(np.median(Tc_tgt)),
        T_air_in_cond_median=float(np.median(Ta_in)),
        T_cond_out_median=float(np.median(Tc_out)),
        eps_cond_median=eps_med, eps_cond_5pct=eps_5, eps_cond_95pct=eps_95,
        approach_to_Tset_median=approach_med,
        approach_to_Tset_max=approach_max,
        Q_cond_kWh=float(np.sum(Q * dt_h)),
        Q_cond_mean_kW_running=float(np.mean(Q[running])) if running.any() else float("nan"),
        frac_full=float(mode_counts.get("full", 0)),
        frac_partial=float(mode_counts.get("partial", 0)),
        frac_off=float(mode_counts.get("off", 0)),
        n_T_cond_oob=n_oob_Tcond,
        n_flag_cond_oversized=n_flag,
        n_Q_neg=n_Q_neg,
        status="",
    )


def make_plot(csv_rel: str, title: str):
    csv = OUT / csv_rel
    df = pd.read_csv(csv)
    t_h = df["time_h"].to_numpy()
    Tc = df["T_cond_C"].to_numpy()
    Ta_in = df["T_air_in_cond_C"].to_numpy()
    Tc_out = df["T_cond_out_C"].to_numpy()
    Tc_tgt = df["T_cond_target_C"].to_numpy()
    Tch = df["T_to_chamber_C"].to_numpy()
    Q = df["Q_cond_kW"].to_numpy()
    mode = df["hp_mode"].astype(str).str.lower().to_numpy()

    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(f"{title}  —  condenser behaviour", fontsize=12)

    ax0 = axes[0]
    ax0.plot(t_h, Ta_in, label="T_air_in_cond", color="tab:blue")
    ax0.plot(t_h, Tc_out, label="T_cond_out", color="tab:cyan")
    ax0.plot(t_h, Tch, label="T_to_chamber", color="tab:green")
    ax0.plot(t_h, Tc_tgt, label="T_cond_target", color="tab:purple", lw=0.8, ls=":")
    ax0.axhline(T_SET, color="black", lw=1, ls="--", label=f"T_set = {T_SET}")
    ax0.set_ylabel("Air-side T [C]")
    ax0.legend(loc="lower right", fontsize=9)
    ax0.grid(alpha=0.3)

    ax1 = axes[1]
    ax1.plot(t_h, Tc, color="tab:red", label="T_cond (refrigerant)")
    ax1.axhline(T_COND_MAX, color="red", lw=1, ls="--", label=f"T_cond ceiling {T_COND_MAX}")
    ax1.set_ylabel("Refrigerant T_cond [C]")
    ax1.legend(loc="lower right", fontsize=9)
    ax1.grid(alpha=0.3)

    ax2 = axes[2]
    ax2.plot(t_h, Q, color="tab:orange", lw=0.8, label="Q_cond [kW]")
    # mark hp_mode as colored bands
    full = mode == "full"; partial = mode == "partial"; off = mode == "off"
    ymin, ymax = ax2.get_ylim()
    ax2.fill_between(t_h, ymin, ymax, where=off, color="lightgray", alpha=0.3, label="HP off")
    ax2.fill_between(t_h, ymin, ymax, where=partial, color="khaki", alpha=0.3, label="partial lift")
    ax2.set_ylabel("Q_cond [kW]")
    ax2.set_xlabel("Drying time [h]")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    parts = Path(csv_rel).parts
    tag = "_".join([parts[0], parts[1], parts[-2] if len(parts) > 3 else "",
                    Path(csv_rel).stem]).replace("__", "_")
    out = PLOTS / f"step2d_cond_{tag}.png"
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
    df.to_csv(AUDIT / "step2d_cond.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2d_cond.csv'} ({len(df)} runs)\n")

    canonical = df[df["file"] == "Ac_10m2_hrx0.70"].copy()
    print(f"=== Canonical 10m2, no VPD ({len(canonical)} runs) ===")
    cols = ["config", "location", "season", "T_cond_median", "T_cond_max",
            "eps_cond_median", "approach_to_Tset_median",
            "frac_full", "frac_partial", "frac_off",
            "n_T_cond_oob", "n_flag_cond_oversized"]
    print(canonical[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\n=== Per-config means (canonical) ===")
    g = canonical.groupby("config")[
        ["T_cond_median", "T_cond_max", "eps_cond_median",
         "approach_to_Tset_median", "frac_full", "frac_partial", "frac_off",
         "Q_cond_kWh"]
    ].mean()
    print(g.to_string(float_format=lambda v: f"{v:.3f}"))

    bad = df[(df["n_T_cond_oob"] > 0) | (df["n_Q_neg"] > 0) |
             (df["n_flag_cond_oversized"] > 0)]
    print(f"\nRuns with cond anomalies: {len(bad)}")
    if not bad.empty:
        print(bad[["config", "location", "season",
                   "n_T_cond_oob", "n_Q_neg", "n_flag_cond_oversized"]].to_string(index=False))

    print("\nGenerating diagnostic plots (KTM annual, all 3 E variants)...")
    for case in [
        "config_E1/kathmandu/Ac_10m2_hrx0.70.csv",
        "config_E2/kathmandu/Ac_10m2_hrx0.70.csv",
        "config_E3/kathmandu/Ac_10m2_hrx0.70.csv",
    ]:
        if (OUT / case).exists():
            make_plot(case, case)


if __name__ == "__main__":
    main()
