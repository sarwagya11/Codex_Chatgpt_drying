"""Step 2b: HRX (heat recovery exchanger) audit for E1/E2/E3.

Sensible-only HRX; effectiveness target = 0.70.

Per CSV, characterise the HRX:
  - Achieved eps_HRX = (T_amb_heated - T_amb) / (T_exhaust - T_amb)
    (only when T_exhaust > T_amb + 0.5 C; else gradient too small to measure)
  - Q_HRX_kWh total + cumulative trace
  - Condensation flag fraction (HRX_condensation)
  - Cold-side dT vs hot-side dT envelope (energy balance)
  - Anomaly flags: eps > 0.95 (above target+slack), eps < 0 (heat backflow),
    Q_HRX < 0 daytime (energy goes the wrong way)

Per-config aggregate written to outputs/audit/step2b_hrx.csv.
Plot: plots/_audit/step2b_hrx_*.png for canonical E2 cases.
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

EPS_TARGET = 0.70
EPS_TOL = 0.02   # achieved should be within +/- 2% of target

REQUIRED = ["T_amb_C", "T_amb_heated_C", "T_exhaust_C", "T_exh_cooled_C",
            "Q_HRX_kW", "time_s"]


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
    Th = df["T_amb_heated_C"].to_numpy()
    Te = df["T_exhaust_C"].to_numpy()
    Tec = df["T_exh_cooled_C"].to_numpy()
    Q = df["Q_HRX_kW"].to_numpy()
    cond = df["HRX_condensation"].to_numpy() if "HRX_condensation" in df.columns else np.zeros_like(Q, dtype=bool)
    dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0

    # eps_HRX where the gradient is meaningful
    grad = Te - Ta
    valid = grad > 0.5
    eps = np.where(valid, (Th - Ta) / np.maximum(grad, 1e-6), np.nan)
    eps_med = float(np.nanmedian(eps)) if valid.any() else float("nan")
    eps_5 = float(np.nanpercentile(eps, 5)) if valid.any() else float("nan")
    eps_95 = float(np.nanpercentile(eps, 95)) if valid.any() else float("nan")

    # Cold-side vs hot-side sensible dT
    dT_cold = Th - Ta
    dT_hot = Te - Tec
    # In ideal HRX (equal m_dot, equal cp, sensible only): dT_cold == dT_hot
    bal = dT_cold - dT_hot
    bal_max = float(np.nanmax(np.abs(bal[valid]))) if valid.any() else float("nan")

    Q_total = float(np.sum(Q * dt_h))
    cond_frac = float(np.sum(cond.astype(bool) * dt_h) / np.sum(dt_h))

    # Flags
    n_eps_too_high = int(np.sum((eps > EPS_TARGET + EPS_TOL) & valid))
    n_eps_too_low = int(np.sum((eps < EPS_TARGET - EPS_TOL) & valid))
    n_eps_neg = int(np.sum((eps < 0) & valid))
    n_Q_neg_daytime = int(np.sum((Q < -1e-3) & (Th > Ta - 0.5)))

    return dict(
        config=config, location=location, season=season, file=name,
        n_steps=len(df),
        eps_median=eps_med, eps_5pct=eps_5, eps_95pct=eps_95,
        eps_target=EPS_TARGET,
        eps_meets_target=abs(eps_med - EPS_TARGET) < EPS_TOL,
        Q_HRX_kWh=Q_total,
        condensation_time_frac=cond_frac,
        sens_balance_max_C=bal_max,
        n_eps_high=n_eps_too_high, n_eps_low=n_eps_too_low, n_eps_neg=n_eps_neg,
        n_Q_neg_daytime=n_Q_neg_daytime,
        T_amb_min=float(Ta.min()), T_amb_max=float(Ta.max()),
        T_exh_max=float(np.nanmax(Te)),
        T_amb_heated_max=float(np.nanmax(Th)),
        status="",
    )


def make_plot(csv_rel: str, title: str):
    csv = OUT / csv_rel
    df = pd.read_csv(csv)
    t_h = df["time_h"].to_numpy()
    Ta = df["T_amb_C"].to_numpy()
    Th = df["T_amb_heated_C"].to_numpy()
    Te = df["T_exhaust_C"].to_numpy()
    Tec = df["T_exh_cooled_C"].to_numpy()
    Q = df["Q_HRX_kW"].to_numpy()
    cond = df["HRX_condensation"].to_numpy().astype(bool) if "HRX_condensation" in df.columns else np.zeros_like(Q, dtype=bool)

    grad = Te - Ta
    eps = np.where(grad > 0.5, (Th - Ta) / np.maximum(grad, 1e-6), np.nan)

    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=True)
    fig.suptitle(f"{title}  —  HRX behaviour (target eps=0.70)", fontsize=12)

    ax0 = axes[0]
    ax0.plot(t_h, Ta, label="T_amb (cold-in)", color="tab:blue")
    ax0.plot(t_h, Th, label="T_amb_heated (cold-out)", color="tab:cyan")
    ax0.plot(t_h, Te, label="T_exhaust (hot-in)", color="tab:red")
    ax0.plot(t_h, Tec, label="T_exh_cooled (hot-out)", color="tab:orange")
    ax0.set_ylabel("Temperature [C]")
    ax0.legend(loc="upper right", fontsize=9)
    ax0.grid(alpha=0.3)

    ax1 = axes[1]
    ax1.plot(t_h, eps, color="tab:purple", lw=0.8)
    ax1.axhline(EPS_TARGET, color="black", lw=1, ls="--", label=f"target {EPS_TARGET}")
    ax1.set_ylabel("eps_HRX achieved")
    ax1.set_ylim(0, 1.2)
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(alpha=0.3)

    ax2 = axes[2]
    ax2.plot(t_h, Q, color="tab:green", lw=0.8, label="Q_HRX [kW]")
    ax2.fill_between(t_h, 0, np.where(cond, Q.max() if Q.size else 1, 0),
                     color="tab:gray", alpha=0.15, label="condensation active")
    ax2.set_ylabel("Q_HRX [kW]")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(alpha=0.3)

    ax3 = axes[3]
    dT_cold = Th - Ta
    dT_hot = Te - Tec
    ax3.plot(t_h, dT_cold, label="cold-side dT (Th - Ta)", color="tab:cyan")
    ax3.plot(t_h, dT_hot, label="hot-side dT (Te - Tec)", color="tab:orange")
    ax3.set_ylabel("Sensible dT [C]")
    ax3.set_xlabel("Drying time [h]")
    ax3.legend(loc="upper right", fontsize=9)
    ax3.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = PLOTS / f"step2b_hrx_{Path(csv_rel).parent.name}_{Path(csv_rel).stem}.png"
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
    df.to_csv(AUDIT / "step2b_hrx.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2b_hrx.csv'} ({len(df)} runs)\n")

    # canonical = non-VPD 10 m2
    canonical = df[df["file"] == "Ac_10m2_hrx0.70"].copy()
    print(f"=== Canonical 10m2, no VPD ({len(canonical)} runs) ===")
    cols = ["config", "location", "season", "eps_median", "eps_5pct", "eps_95pct",
            "Q_HRX_kWh", "condensation_time_frac", "sens_balance_max_C"]
    print(canonical[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\n=== Per-config means (canonical) ===")
    g = canonical.groupby("config")[
        ["eps_median", "Q_HRX_kWh", "condensation_time_frac", "sens_balance_max_C"]
    ].mean()
    print(g.to_string(float_format=lambda v: f"{v:.4f}"))

    # Anomaly summary
    bad = df[(df["n_eps_neg"] > 0) | (df["n_Q_neg_daytime"] > 0)]
    print(f"\nRuns with HRX anomalies (eps<0 or Q<0 daytime): {len(bad)}")
    if not bad.empty:
        print(bad[["config", "location", "season", "n_eps_neg", "n_Q_neg_daytime"]].to_string(index=False))

    # Plot for one canonical run
    print("\nGenerating diagnostic plots...")
    for case in [
        "config_E2/kathmandu/Ac_10m2_hrx0.70.csv",
        "config_E2/biratnagar/spring_mar_apr/Ac_10m2_hrx0.70.csv",
        "config_E2/kathmandu/winter_dec_jan/Ac_10m2_hrx0.70.csv",
    ]:
        if (OUT / case).exists():
            make_plot(case, case)


if __name__ == "__main__":
    main()
