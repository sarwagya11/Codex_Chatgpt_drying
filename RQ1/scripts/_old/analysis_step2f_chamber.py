"""Step 2f: Chamber audit for E1/E2/E3.

Per CSV (canonical 10 m², no VPD):
  - T_to_chamber tracking T_set (should be 45.00 in all E configs)
  - RH_to_chamber range, omega_to_chamber range
  - Chamber sensible cooling (T_to_chamber − T_exhaust): air gives up sensible
    heat for evaporation
  - Water pickup across chamber (omega_exhaust − omega_to_chamber)
  - X_db trajectory: time at constant rate (X > X_crit) vs falling rate
  - MR_global trajectory; t_50, t_90 (time to reach MR=0.5 and 0.1)
  - Per-tray uniformity (tray_0 vs tray_9 final X_db spread)
  - Drying rate envelope dm_w/dt

Output: outputs/audit/step2f_chamber.csv
Plots:  plots/_audit/step2f_chamber_*.png
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

T_SET = 45.0
N_TRAYS = 10


def per_run(csv: Path):
    df = pd.read_csv(csv)
    rel = csv.relative_to(OUT)
    parts = rel.parts
    config = parts[0].replace("config_", "")
    location = parts[1]
    season = parts[2] if len(parts) > 3 else "annual"
    name = csv.stem

    t_s = df["time_s"].to_numpy()
    t_h = df["time_h"].to_numpy()
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0

    Tch = df["T_to_chamber_C"].to_numpy()
    Texh = df["T_exhaust_C"].to_numpy()
    RHch = df["RH_to_chamber_frac"].to_numpy()
    RHexh = df["RH_exhaust_frac"].to_numpy()
    omega_ch = df["omega_to_chamber"].to_numpy()
    X = df["X_db_avg"].to_numpy()
    MR = df["MR_global"].to_numpy()
    dm_w = df["dm_w_total_kg"].to_numpy()
    m_w_cum = df["m_w_cum_kg"].to_numpy()

    # T_set tracking
    Tch_dev = Tch - T_SET

    # Sensible cooling across chamber
    sens_cool = Tch - Texh

    # Water pickup: estimate omega_exhaust from RH/T (use psychro? simpler: m_w/m_air via m_w_cum)
    # Use exhaust RH and assume same T to approximate omega_exh; but easier: use dm_w over interval / m_dot_air
    # dm_w_total_kg is per timestep; over a step, water added per kg dry air = dm_w / (m_dot_air * dt)
    # m_dot_air not directly in CSV; use proxy: omega_pickup ~ proportional to dm_w
    # We'll just report dm_w and Δomega as proxy: omega_exh - omega_ch when available
    if "omega_exhaust" in df.columns:
        omega_exh = df["omega_exhaust"].to_numpy()
        d_omega = omega_exh - omega_ch
    else:
        d_omega = np.full_like(omega_ch, np.nan)

    # Drying milestones
    def time_to_MR(target):
        idx = np.where(MR <= target)[0]
        return float(t_h[idx[0]]) if idx.size else float("nan")
    t_MR50 = time_to_MR(0.5)
    t_MR10 = time_to_MR(0.1)

    # Constant-rate vs falling-rate split (drying rate per hr)
    # rate = dm_w / dt_h
    rate = np.where(dt_h > 1e-6, dm_w / dt_h, 0.0)
    rate_max = float(np.nanmax(rate))
    # Constant-rate window: rate within 80% of peak
    cr_mask = rate >= 0.8 * rate_max
    t_constant_h = float(np.sum(dt_h[cr_mask]))
    rate_avg_const = float(np.mean(rate[cr_mask])) if cr_mask.any() else float("nan")

    # Per-tray uniformity (final X)
    X_final = []
    for i in range(N_TRAYS):
        col = f"X_tray_{i}"
        if col in df.columns:
            X_final.append(float(df[col].iloc[-1]))
    if X_final:
        X_final = np.array(X_final)
        X_tray_mean = float(X_final.mean())
        X_tray_spread = float(X_final.max() - X_final.min())
        X_tray_std = float(X_final.std())
    else:
        X_tray_mean = X_tray_spread = X_tray_std = float("nan")

    return dict(
        config=config, location=location, season=season, file=name,
        n_steps=len(df),
        T_to_chamber_mean=float(Tch.mean()),
        T_to_chamber_max_dev=float(np.max(np.abs(Tch_dev))),
        sens_cool_mean=float(sens_cool.mean()),
        sens_cool_max=float(sens_cool.max()),
        RH_chamber_min=float(RHch.min()),
        RH_chamber_max=float(RHch.max()),
        RH_exhaust_min=float(RHexh.min()),
        RH_exhaust_max=float(RHexh.max()),
        omega_chamber_mean=float(omega_ch.mean()),
        d_omega_mean=float(np.nanmean(d_omega)) if np.any(np.isfinite(d_omega)) else float("nan"),
        X_initial=float(X[0]), X_final_avg=float(X[-1]),
        MR_final=float(MR[-1]),
        t_h_total=float(t_h[-1]),
        t_h_to_MR50=t_MR50, t_h_to_MR10=t_MR10,
        rate_max_kg_per_h=rate_max,
        rate_avg_constant_kg_per_h=rate_avg_const,
        t_h_constant_rate=t_constant_h,
        m_w_total_kg=float(m_w_cum[-1]),
        X_tray_final_mean=X_tray_mean,
        X_tray_final_spread=X_tray_spread,
        X_tray_final_std=X_tray_std,
    )


def make_plot(csv_rel: str, title: str):
    csv = OUT / csv_rel
    df = pd.read_csv(csv)
    t_h = df["time_h"].to_numpy()
    Tch = df["T_to_chamber_C"].to_numpy()
    Texh = df["T_exhaust_C"].to_numpy()
    RHch = df["RH_to_chamber_frac"].to_numpy() * 100
    RHexh = df["RH_exhaust_frac"].to_numpy() * 100
    X = df["X_db_avg"].to_numpy()
    MR = df["MR_global"].to_numpy()
    m_w = df["m_w_cum_kg"].to_numpy()
    dt_h = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0]) / 3600.0
    rate = np.where(dt_h > 1e-6, df["dm_w_total_kg"].to_numpy() / dt_h, 0.0)

    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=True)
    fig.suptitle(f"{title}  —  chamber behaviour", fontsize=12)

    ax = axes[0]
    ax.plot(t_h, Tch, label="T_to_chamber", color="tab:red")
    ax.plot(t_h, Texh, label="T_exhaust", color="tab:orange")
    ax.axhline(T_SET, color="black", lw=1, ls="--", label=f"T_set = {T_SET}")
    ax.set_ylabel("Temperature [°C]")
    ax.legend(loc="lower right", fontsize=9); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(t_h, RHch, label="RH_to_chamber", color="tab:blue")
    ax.plot(t_h, RHexh, label="RH_exhaust", color="tab:cyan")
    ax.set_ylabel("RH [%]")
    ax.legend(loc="upper right", fontsize=9); ax.grid(alpha=0.3)

    ax = axes[2]
    ax.plot(t_h, X, color="tab:purple", label="X_db_avg [kg w / kg dry]")
    ax2 = ax.twinx()
    ax2.plot(t_h, MR, color="tab:green", label="MR_global", lw=0.9)
    ax.set_ylabel("X_db [kg/kg]", color="tab:purple")
    ax2.set_ylabel("MR (dimensionless)", color="tab:green")
    ax.grid(alpha=0.3)

    ax = axes[3]
    ax.plot(t_h, rate, color="tab:gray", lw=0.8, label="dm_w/dt [kg/h]")
    ax_b = ax.twinx()
    ax_b.plot(t_h, m_w, color="tab:olive", lw=1.4, label="m_w cumulative [kg]")
    ax.set_ylabel("Drying rate [kg/h]", color="tab:gray")
    ax_b.set_ylabel("m_w cumulative [kg]", color="tab:olive")
    ax.set_xlabel("Drying time [h]")
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    parts = Path(csv_rel).parts
    tag = "_".join([parts[0], parts[1], parts[-2] if len(parts) > 3 else "",
                    Path(csv_rel).stem]).replace("__", "_")
    out = PLOTS / f"step2f_chamber_{tag}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def make_tray_plot(csv_rel: str, title: str):
    csv = OUT / csv_rel
    df = pd.read_csv(csv)
    t_h = df["time_h"].to_numpy()

    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    fig.suptitle(f"{title}  —  per-tray drying", fontsize=12)

    ax = axes[0]
    cmap = plt.cm.viridis
    for i in range(N_TRAYS):
        col = f"X_tray_{i}"
        if col in df.columns:
            ax.plot(t_h, df[col], color=cmap(i / (N_TRAYS - 1)),
                    label=f"tray {i}", lw=1.0, alpha=0.9)
    ax.set_ylabel("X_db [kg w / kg dry]")
    ax.legend(loc="upper right", ncol=2, fontsize=8); ax.grid(alpha=0.3)

    ax = axes[1]
    for i in range(N_TRAYS):
        col = f"T_tray_{i}_out_C"
        if col in df.columns:
            ax.plot(t_h, df[col], color=cmap(i / (N_TRAYS - 1)),
                    lw=0.9, alpha=0.9, label=f"tray {i}")
    ax.set_ylabel("T_tray_out [°C]")
    ax.set_xlabel("Drying time [h]")
    ax.legend(loc="lower right", ncol=2, fontsize=8); ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    parts = Path(csv_rel).parts
    tag = "_".join([parts[0], parts[1], parts[-2] if len(parts) > 3 else "",
                    Path(csv_rel).stem]).replace("__", "_")
    out = PLOTS / f"step2f_chamber_trays_{tag}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def main():
    csvs = sorted([p for p in OUT.glob("config_E*/**/Ac_10m2_hrx0.70.csv")])
    rows = [per_run(c) for c in csvs]
    df = pd.DataFrame(rows)
    df.to_csv(AUDIT / "step2f_chamber.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2f_chamber.csv'} ({len(df)} runs)\n")

    print("=== Per-run ===")
    cols = ["config", "location", "season", "T_to_chamber_mean", "T_to_chamber_max_dev",
            "sens_cool_mean", "RH_chamber_min", "RH_chamber_max",
            "X_final_avg", "MR_final", "t_h_to_MR50", "t_h_to_MR10",
            "t_h_constant_rate", "rate_max_kg_per_h",
            "X_tray_final_spread", "X_tray_final_std"]
    print(df[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\n=== Per-config means ===")
    g = df.groupby("config")[
        ["T_to_chamber_mean", "T_to_chamber_max_dev", "sens_cool_mean",
         "RH_chamber_max", "RH_exhaust_max",
         "X_final_avg", "MR_final", "t_h_to_MR50", "t_h_to_MR10",
         "t_h_constant_rate", "rate_max_kg_per_h",
         "X_tray_final_spread", "X_tray_final_std"]
    ].mean()
    print(g.to_string(float_format=lambda v: f"{v:7.4f}"))

    print("\nGenerating diagnostic plots (KTM annual, all 3 E variants)...")
    for case, title in [
        ("config_E1/kathmandu/Ac_10m2_hrx0.70.csv", "E1 Kathmandu annual"),
        ("config_E2/kathmandu/Ac_10m2_hrx0.70.csv", "E2 Kathmandu annual"),
        ("config_E3/kathmandu/Ac_10m2_hrx0.70.csv", "E3 Kathmandu annual"),
    ]:
        if (OUT / case).exists():
            make_plot(case, title)
            make_tray_plot(case, title)


if __name__ == "__main__":
    main()
