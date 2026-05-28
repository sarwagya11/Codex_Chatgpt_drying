"""Step 4 — E1 vs E2 vs E3 head-to-head.

Pulls together Steps 2e (HP whole-cycle), 2g (VPD), 3 (energy split) into
a single paper-ready decision matrix. For every (location, season, mode)
triple, compute per-config KPIs and tally win-rates.

KPIs:
  SEC  [kWh/kg]   ← lower is better
  SMER [kg/kWh]   ← higher is better
  t_h  [h]        ← lower is better
  COP_full_med    ← higher is better
  Q_solar_usable  ← higher is better
  capture_eff     ← higher is better

Outputs:
  outputs/audit/step4_head_to_head.csv     (long-format with all KPIs per row)
  outputs/audit/step4_winrate.csv          (per-KPI win count by config)
  outputs/audit/step4_pivot_SEC.csv        (paper-ready SEC matrix)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
HP_CSV = AUDIT / "step2e_hp.csv"
VPD_CSV = AUDIT / "step2g_vpd.csv"


def load_no_vpd() -> pd.DataFrame:
    df = pd.read_csv(HP_CSV)
    df = df[df["config"].isin(["E1", "E2", "E3"])].copy()
    df["mode"] = "no_vpd"
    df = df.rename(columns={
        "drying_h": "t_h",
        "Q_solar_usable_kWh": "Q_solar_usable",
        "capture_eff": "capture_eff",
        "COP_full_median": "COP_med",
        "SEC_kWh_per_kg": "SEC",
        "SMER_kg_per_kWh": "SMER",
        "W_total_kWh": "W_total",
    })
    return df[["config", "location", "season", "mode",
               "SEC", "SMER", "t_h", "COP_med",
               "Q_solar_usable", "capture_eff", "W_total", "m_w_kg"]]


def load_vpd() -> pd.DataFrame:
    df = pd.read_csv(VPD_CSV)
    rows = []
    for r in df.itertuples():
        rows.append({
            "config": r.config, "location": r.location, "season": r.season,
            "mode": "vpd",
            "SEC": r.SEC_vpd, "SMER": r.SMER_vpd,
            "t_h": r.t_h_vpd,
            "COP_med": r.COP_vpd,
            "Q_solar_usable": r.Qsu_vpd,
            "capture_eff": float("nan"),  # not in step2g
            "W_total": r.W_vpd,
            "m_w_kg": r.m_w_vpd,
        })
    return pd.DataFrame(rows)


def winrate(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """For each (location, season) within the given mode, find the winner per KPI."""
    sub = df[df["mode"] == mode].copy()
    if sub.empty:
        return pd.DataFrame()
    # KPIs and direction (lower-better = -1, higher-better = +1)
    kpis = [("SEC", -1), ("SMER", +1), ("t_h", -1),
            ("COP_med", +1), ("Q_solar_usable", +1)]
    counts = {cfg: {kpi: 0 for kpi, _ in kpis} for cfg in ("E1", "E2", "E3")}
    n_cases = 0
    for (loc, sea), grp in sub.groupby(["location", "season"]):
        if grp["config"].nunique() < 3:
            continue
        n_cases += 1
        for kpi, direction in kpis:
            grp2 = grp.dropna(subset=[kpi])
            if grp2.empty:
                continue
            if direction > 0:
                winner = grp2.loc[grp2[kpi].idxmax(), "config"]
            else:
                winner = grp2.loc[grp2[kpi].idxmin(), "config"]
            counts[winner][kpi] += 1
    out = pd.DataFrame(counts).T
    out["mode"] = mode
    out["n_cases"] = n_cases
    return out


def main():
    no_vpd = load_no_vpd()
    vpd = load_vpd()
    df = pd.concat([no_vpd, vpd], ignore_index=True)
    df.to_csv(AUDIT / "step4_head_to_head.csv", index=False, float_format="%.6g")
    print(f"Saved {AUDIT/'step4_head_to_head.csv'} ({len(df)} rows)\n")

    # Per-config means by mode
    print("=== Per-config × mode means ===")
    means = df.groupby(["mode", "config"])[
        ["SEC", "SMER", "t_h", "COP_med", "Q_solar_usable", "W_total"]
    ].mean()
    print(means.to_string(float_format=lambda v: f"{v:8.4f}"))

    # Win-rate
    print("\n=== Win-rate by KPI (no-VPD) ===")
    wr_no = winrate(df, "no_vpd")
    if not wr_no.empty:
        print(wr_no.to_string())
    print("\n=== Win-rate by KPI (VPD) ===")
    wr_vpd = winrate(df, "vpd")
    if not wr_vpd.empty:
        print(wr_vpd.to_string())

    pd.concat([wr_no, wr_vpd]).to_csv(AUDIT / "step4_winrate.csv")

    # Paper-ready SEC pivot (no-VPD)
    print("\n=== SEC matrix [kWh/kg] (no-VPD) ===")
    p1 = df[df["mode"] == "no_vpd"].pivot_table(
        index=["location", "season"], columns="config", values="SEC")
    p1["best"] = p1[["E1", "E2", "E3"]].idxmin(axis=1)
    p1["E2_vs_E1_pct"] = 100 * (p1["E2"] - p1["E1"]) / p1["E1"]
    p1["E3_vs_E1_pct"] = 100 * (p1["E3"] - p1["E1"]) / p1["E1"]
    p1["E3_vs_E2_pct"] = 100 * (p1["E3"] - p1["E2"]) / p1["E2"]
    print(p1.to_string(float_format=lambda v: f"{v:7.4f}" if isinstance(v, float) else str(v)))
    p1.to_csv(AUDIT / "step4_pivot_SEC_no_vpd.csv", float_format="%.6g")

    # Paper-ready SEC pivot (VPD)
    print("\n=== SEC matrix [kWh/kg] (VPD on) ===")
    p2 = df[df["mode"] == "vpd"].pivot_table(
        index=["location", "season"], columns="config", values="SEC")
    p2["best"] = p2[["E1", "E2", "E3"]].idxmin(axis=1)
    p2["E2_vs_E1_pct"] = 100 * (p2["E2"] - p2["E1"]) / p2["E1"]
    p2["E3_vs_E1_pct"] = 100 * (p2["E3"] - p2["E1"]) / p2["E1"]
    p2["E3_vs_E2_pct"] = 100 * (p2["E3"] - p2["E2"]) / p2["E2"]
    print(p2.to_string(float_format=lambda v: f"{v:7.4f}" if isinstance(v, float) else str(v)))
    p2.to_csv(AUDIT / "step4_pivot_SEC_vpd.csv", float_format="%.6g")

    # Best-config tally
    print("\n=== Best-SEC config tally ===")
    print("no-VPD:", p1["best"].value_counts().to_dict())
    print("VPD on:", p2["best"].value_counts().to_dict())


if __name__ == "__main__":
    main()
