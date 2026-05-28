"""Step 2g: VPD-bypass controller audit for E1/E2/E3.

VPD bypass: at high ambient humidity, switch the air path from
  Amb → HRX → Solar → Cond → Chamber
to
  Exhaust → Solar → Cond → Chamber
(the HRX is bypassed and the warmer/drier exhaust feeds the heat side).
This is gated by `--vpd-threshold 0.05` (5 % VPD utilisation) with
hysteresis (3×) and dwell (600 s) — see notes in CLAUDE memory.

Question this audit answers: does VPD bypass (vpd0.05) reduce SEC and
SMER vs the no-VPD canonical? At which locations / seasons / configs?
What's the cost (more clipping? lower COP? frost risk?)

Compares: <name>.csv (no VPD)  vs  <name>_vpd0.05.csv (with VPD)
Output:  outputs/audit/step2g_vpd.csv
Plots:   plots/_audit/step2g_vpd_*.png
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


def trapz_kWh(s, t_s):
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    return float(np.sum(s * dt_h))


def per_run(csv_no: Path, csv_vpd: Path):
    rel = csv_no.relative_to(OUT)
    parts = rel.parts
    config = parts[0].replace("config_", "")
    location = parts[1]
    season = parts[2] if len(parts) > 3 else "annual"

    a = pd.read_csv(csv_no)
    b = pd.read_csv(csv_vpd)

    def metrics(df):
        t_s = df["time_s"].to_numpy()
        dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
        Wc = trapz_kWh(df["W_comp_kW"], t_s)
        Wf = trapz_kWh(df["W_fan_kW"], t_s) if "W_fan_kW" in df.columns else 0.0
        Wt = Wc + Wf
        Qsu = trapz_kWh(df["Q_solar_usable_kW"], t_s) if "Q_solar_usable_kW" in df.columns else trapz_kWh(df["Q_solar_kW"], t_s)
        Qsg = trapz_kWh(df["Q_solar_kW"], t_s)
        Qhrx = trapz_kWh(df["Q_HRX_kW"], t_s) if "Q_HRX_kW" in df.columns else 0.0
        mw = float(df["m_w_cum_kg"].iloc[-1])
        th = float(df["time_h"].iloc[-1])
        bypass_frac = float(df["vpd_bypass_active"].astype(int).sum() / len(df)) if "vpd_bypass_active" in df.columns else 0.0
        # Compress Δomega (water pickup) for diagnostic
        if "omega_exhaust" in df.columns and "omega_to_chamber" in df.columns:
            d_omega = df["omega_exhaust"] - df["omega_to_chamber"]
            d_omega_mean = float(np.nanmean(d_omega))
        else:
            d_omega_mean = float("nan")
        # COP envelope
        full = df["hp_mode"].astype(str).str.lower() == "full"
        cop = df["COP"][full].to_numpy()
        cop = cop[np.isfinite(cop)]
        cop_med = float(np.median(cop)) if cop.size else float("nan")
        return dict(W_total=Wt, W_comp=Wc, W_fan=Wf, Q_solar_usable=Qsu, Q_solar_gross=Qsg,
                    Q_HRX=Qhrx, m_w=mw, t_h=th, bypass_frac=bypass_frac,
                    d_omega_mean=d_omega_mean, COP_full_med=cop_med,
                    SEC=Wt/mw if mw > 1e-6 else float("nan"),
                    SMER=mw/Wt if Wt > 1e-6 else float("nan"))

    A = metrics(a); B = metrics(b)
    return dict(
        config=config, location=location, season=season,
        # baseline
        SEC_no=A["SEC"], SEC_vpd=B["SEC"], dSEC=B["SEC"] - A["SEC"], dSEC_pct=100*(B["SEC"]-A["SEC"])/A["SEC"],
        SMER_no=A["SMER"], SMER_vpd=B["SMER"],
        W_no=A["W_total"], W_vpd=B["W_total"], dW=B["W_total"]-A["W_total"],
        Qsu_no=A["Q_solar_usable"], Qsu_vpd=B["Q_solar_usable"], dQsu=B["Q_solar_usable"]-A["Q_solar_usable"],
        Qhrx_no=A["Q_HRX"], Qhrx_vpd=B["Q_HRX"], dQhrx=B["Q_HRX"]-A["Q_HRX"],
        t_h_no=A["t_h"], t_h_vpd=B["t_h"], dt_h=B["t_h"]-A["t_h"],
        m_w_no=A["m_w"], m_w_vpd=B["m_w"],
        bypass_frac_vpd=B["bypass_frac"],
        d_omega_no=A["d_omega_mean"], d_omega_vpd=B["d_omega_mean"],
        COP_no=A["COP_full_med"], COP_vpd=B["COP_full_med"],
    )


def plot_pair(csv_no: Path, csv_vpd: Path, title: str):
    a = pd.read_csv(csv_no); b = pd.read_csv(csv_vpd)
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(f"{title} — VPD off vs VPD 0.05", fontsize=12, weight="bold")

    ax = axes[0]
    ax.plot(a["time_h"], a["W_comp_kW"], label="no-VPD", color="tab:blue", lw=0.8)
    ax.plot(b["time_h"], b["W_comp_kW"], label="VPD 0.05", color="tab:red", lw=0.8, alpha=0.85)
    ax.set_ylabel("W_comp [kW]"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    if "vpd_utilization" in b.columns:
        ax.plot(b["time_h"], b["vpd_utilization"], color="tab:purple", lw=0.8, label="vpd_utilization")
    ax.axhline(0.05, color="black", ls="--", lw=1, label="threshold 0.05")
    if "vpd_bypass_active" in b.columns:
        ax.fill_between(b["time_h"], 0, 1,
                        where=b["vpd_bypass_active"].astype(bool),
                        color="orange", alpha=0.2, label="bypass active", transform=ax.get_xaxis_transform())
    ax.set_ylabel("VPD utilization")
    ax.legend(); ax.grid(alpha=0.3)
    ax.set_ylim(0, max(0.3, b["vpd_utilization"].max() if "vpd_utilization" in b.columns else 0.3))

    ax = axes[2]
    ax.plot(a["time_h"], a["m_w_cum_kg"], label="no-VPD", color="tab:blue", lw=1.4)
    ax.plot(b["time_h"], b["m_w_cum_kg"], label="VPD 0.05", color="tab:red", lw=1.4, alpha=0.85)
    ax.set_ylabel("Water removed cum [kg]"); ax.set_xlabel("time [h]")
    ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    parts = csv_no.relative_to(OUT).parts
    tag = "_".join([parts[0], parts[1], parts[-2] if len(parts) > 3 else "", csv_no.stem]).replace("__", "_")
    out = PLOTS / f"step2g_vpd_{tag}.png"
    fig.savefig(out, dpi=130); plt.close(fig)
    print(f"  saved {out.relative_to(PROJECT_ROOT)}")


def main():
    pairs = []
    for vpd_csv in sorted(OUT.glob("config_E*/**/Ac_10m2_hrx0.70_vpd0.05.csv")):
        no_csv = vpd_csv.with_name("Ac_10m2_hrx0.70.csv")
        if no_csv.exists():
            pairs.append((no_csv, vpd_csv))
    print(f"Found {len(pairs)} no-VPD/VPD0.05 pairs")
    rows = [per_run(a, b) for a, b in pairs]
    df = pd.DataFrame(rows)
    df.to_csv(AUDIT / "step2g_vpd.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT / 'step2g_vpd.csv'} ({len(df)} pairs)\n")

    print("=== Per-run pairs ===")
    cols = ["config", "location", "season", "bypass_frac_vpd",
            "SEC_no", "SEC_vpd", "dSEC_pct",
            "Qhrx_no", "Qhrx_vpd", "Qsu_no", "Qsu_vpd",
            "t_h_no", "t_h_vpd", "COP_no", "COP_vpd"]
    print(df[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\n=== Per-config means ===")
    g = df.groupby("config")[
        ["bypass_frac_vpd", "SEC_no", "SEC_vpd", "dSEC_pct",
         "Qhrx_no", "Qhrx_vpd", "Qsu_no", "Qsu_vpd",
         "t_h_no", "t_h_vpd", "dt_h", "COP_no", "COP_vpd"]
    ].mean()
    print(g.to_string(float_format=lambda v: f"{v:7.4f}"))

    print("\n=== Best-case VPD wins (largest SEC reduction) ===")
    print(df.nsmallest(5, "dSEC_pct")[
        ["config", "location", "season", "bypass_frac_vpd", "SEC_no", "SEC_vpd", "dSEC_pct"]
    ].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\n=== Worst VPD outcomes (SEC went up) ===")
    print(df.nlargest(5, "dSEC_pct")[
        ["config", "location", "season", "bypass_frac_vpd", "SEC_no", "SEC_vpd", "dSEC_pct"]
    ].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    print("\nGenerating diagnostic plots (E2 KTM annual + best/worst VPD case)...")
    targets = [
        OUT / "config_E2/kathmandu/Ac_10m2_hrx0.70_vpd0.05.csv",
    ]
    # Add the absolute-best case
    if not df.empty:
        best = df.loc[df["dSEC_pct"].idxmin()]
        season_part = f"/{best['season']}" if best['season'] != 'annual' else ""
        targets.append(OUT / f"config_{best['config']}/{best['location']}{season_part}/Ac_10m2_hrx0.70_vpd0.05.csv")
    for t in targets:
        if t.exists():
            no = t.with_name("Ac_10m2_hrx0.70.csv")
            if no.exists():
                title = f"{t.parts[-3]} {t.parts[-2]}" if "/" in str(t.relative_to(OUT)) else str(t.parent)
                plot_pair(no, t, str(t.relative_to(OUT)))


if __name__ == "__main__":
    main()
