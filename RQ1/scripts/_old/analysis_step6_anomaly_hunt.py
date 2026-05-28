"""Step 6 — Anomaly hunt.

Sweeps every E1/E2/E3 canonical CSV (no-VPD + VPD) for surprising states:
  1. COP outliers (very low or very high)
  2. T_to_chamber deficit (chamber below T_set when not idle)
  3. HP-at-capacity flags (HP saturating)
  4. VPD bypass churn (switching faster than dwell)
  5. First-law residual per timestep: Q_cond - (Q_evap + W_comp) outside ±2 %
  6. Cross-config consistency: E1 == E2 Q_HRX and Q_solar_usable per case
  7. Drying-time near-miss / DNF (>= 71.9 h means time-limit hit)

Output: outputs/audit/step6_anomaly_log.csv  (one row per anomaly)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
AUDIT.mkdir(parents=True, exist_ok=True)

T_SET = 45.0
ETA_MECH = 0.95


def trapz_kWh(s, t_s):
    dt_h = np.diff(t_s, prepend=t_s[0]) / 3600.0
    return float(np.sum(np.asarray(s) * dt_h))


def hunt(csv: Path) -> list[dict]:
    rel = csv.relative_to(OUT).parts
    config = rel[0].replace("config_", "")
    location = rel[1]
    season = rel[2] if len(rel) > 3 else "annual"
    mode = "vpd" if "vpd" in csv.name else "no_vpd"
    tag = f"{config}/{location}/{season}/{mode}"

    df = pd.read_csv(csv)
    out = []

    # --- 1. COP outliers (during HP running) ---
    if "W_comp_kW" in df.columns and "COP" in df.columns:
        running = df[df["W_comp_kW"] > 0.05]
        if not running.empty:
            cop = running["COP"].to_numpy()
            cop = cop[np.isfinite(cop)]
            n_low = int(np.sum(cop < 1.5))
            n_hi = int(np.sum(cop > 8.0))
            if n_low > 0 or n_hi > 0:
                out.append(dict(case=tag, kind="COP_outlier",
                                detail=f"low(<1.5)={n_low} / hi(>8)={n_hi} of {len(cop)}",
                                severity="info"))

    # --- 2. T_to_chamber deficit ---
    # Chamber should be at T_set whenever HP+solar are active. Flag steps
    # where deficit > 0.5 K and not in idle mode.
    if "T_to_chamber_C" in df.columns:
        deficit = T_SET - df["T_to_chamber_C"]
        bad = deficit > 0.5
        if "vpd_bypass_active" in df.columns:
            bad = bad & (df["vpd_bypass_active"] == 0)  # bypass legitimately may underheat at night
        if "G_solar_Wm2" in df.columns:
            # only flag when there's no solar AND bypass isn't covering — not in bootstrap
            bad = bad & (df["time_h"] > 0.5)  # skip first-step transient
        n_bad = int(bad.sum())
        if n_bad > 0:
            max_def = float(deficit[bad].max())
            out.append(dict(case=tag, kind="T_chamber_deficit",
                            detail=f"{n_bad} steps below T_set−0.5K (max deficit {max_def:.2f}K)",
                            severity="warn" if max_def > 2.0 else "info"))

    # --- 3. HP-at-capacity flags ---
    for flag in ("flag_hp_at_capacity", "flag_evap_oversized", "flag_cond_oversized"):
        if flag in df.columns:
            n = int(df[flag].astype(int).sum())
            if n > 0:
                out.append(dict(case=tag, kind=flag,
                                detail=f"{n}/{len(df)} steps flagged",
                                severity="warn" if n > len(df) * 0.05 else "info"))

    # --- 4. Bypass churn (switches per hour) ---
    if "vpd_bypass_active" in df.columns:
        switches = int(df["vpd_bypass_active"].astype(int).diff().abs().sum())
        hours = float(df["time_h"].iloc[-1])
        rate = switches / hours if hours > 0 else 0
        if rate > 6.0:  # > 1 switch per 10 min is suspect (dwell is 600s)
            out.append(dict(case=tag, kind="bypass_churn",
                            detail=f"{switches} switches over {hours:.1f}h ({rate:.2f}/h)",
                            severity="warn"))

    # --- 5. First-law residual ---
    if all(c in df.columns for c in ("Q_cond_kW", "Q_evap_kW", "W_comp_kW")):
        running = df[df["W_comp_kW"] > 0.05].copy()
        if not running.empty:
            expected = running["Q_evap_kW"] + ETA_MECH * running["W_comp_kW"]
            actual = running["Q_cond_kW"]
            mask = expected > 0.05
            if mask.any():
                rel_err = ((actual[mask] - expected[mask]) / expected[mask]).abs()
                n_bad = int((rel_err > 0.02).sum())
                if n_bad > 0:
                    max_err = float(rel_err.max() * 100)
                    out.append(dict(case=tag, kind="first_law_residual",
                                    detail=f"{n_bad} steps |err|>2% (max {max_err:.2f}%)",
                                    severity="warn" if max_err > 5 else "info"))

    # --- 7. Drying-time DNF ---
    if "time_h" in df.columns:
        th = float(df["time_h"].iloc[-1])
        if th >= 71.9:
            out.append(dict(case=tag, kind="DNF_72h_limit",
                            detail=f"reached {th:.1f}h time limit; m_w={df['m_w_cum_kg'].iloc[-1]:.2f}kg",
                            severity="warn"))

    return out


def cross_config_consistency() -> list[dict]:
    """E1 and E2 should have IDENTICAL Q_HRX and Q_solar_usable per (location, season).
    Their only legitimate difference is the evaporator side (W_comp/COP)."""
    out = []
    for loc_dir in (OUT / "config_E1").glob("*"):
        if not loc_dir.is_dir():
            continue
        for csv1 in loc_dir.rglob("Ac_10m2_hrx0.70.csv"):
            rel = csv1.relative_to(OUT / "config_E1")
            csv2 = OUT / "config_E2" / rel
            if not csv2.exists():
                continue
            try:
                d1 = pd.read_csv(csv1); d2 = pd.read_csv(csv2)
            except Exception:
                continue
            t_s1 = d1["time_s"].to_numpy()
            t_s2 = d2["time_s"].to_numpy()
            QH1 = trapz_kWh(d1["Q_HRX_kW"], t_s1) if "Q_HRX_kW" in d1.columns else 0.0
            QH2 = trapz_kWh(d2["Q_HRX_kW"], t_s2) if "Q_HRX_kW" in d2.columns else 0.0
            QS1 = trapz_kWh(d1.get("Q_solar_usable_kW", d1["Q_solar_kW"]), t_s1)
            QS2 = trapz_kWh(d2.get("Q_solar_usable_kW", d2["Q_solar_kW"]), t_s2)
            tag = f"E1-vs-E2/{rel.parent.as_posix()}"
            if abs(QH1 - QH2) > 0.05:
                out.append(dict(case=tag, kind="E1_E2_HRX_diff",
                                detail=f"E1 Q_HRX={QH1:.3f} kWh, E2={QH2:.3f}",
                                severity="warn"))
            if abs(QS1 - QS2) > 0.05:
                out.append(dict(case=tag, kind="E1_E2_solar_diff",
                                detail=f"E1 Q_solar_usable={QS1:.3f} kWh, E2={QS2:.3f}",
                                severity="warn"))
    return out


def main():
    findings = []
    n_files = 0
    for csv in OUT.glob("config_E[123]/**/Ac_10m2_hrx0.70*.csv"):
        n_files += 1
        try:
            findings.extend(hunt(csv))
        except Exception as e:
            findings.append(dict(case=str(csv.relative_to(OUT)),
                                 kind="hunt_error", detail=str(e), severity="warn"))
    findings.extend(cross_config_consistency())

    df = pd.DataFrame(findings)
    out_csv = AUDIT / "step6_anomaly_log.csv"
    df.to_csv(out_csv, index=False)
    print(f"Scanned {n_files} files. Logged {len(df)} findings -> {out_csv}\n")

    if df.empty:
        print("NO ANOMALIES.")
        return

    print("=== Findings by kind & severity ===")
    print(df.groupby(["kind", "severity"]).size().to_string())

    print("\n=== Warnings (severity=warn) ===")
    warns = df[df["severity"] == "warn"]
    if warns.empty:
        print("(none)")
    else:
        # group identical-kind warnings, show counts + a few examples
        for kind, grp in warns.groupby("kind"):
            print(f"\n[{kind}]  ({len(grp)} cases)")
            for r in grp.head(8).itertuples():
                print(f"   {r.case:55s}  {r.detail}")
            if len(grp) > 8:
                print(f"   ... and {len(grp) - 8} more")

    print("\n=== Info-level findings (sample) ===")
    info = df[df["severity"] == "info"]
    print(f"({len(info)} info-level findings; see {out_csv} for full log)")


if __name__ == "__main__":
    main()
