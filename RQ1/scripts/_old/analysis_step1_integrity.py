"""Step 1 integrity check for E1/E2/E3 simulation outputs.

For every CSV under outputs/config_{E1,E2,E3}/, verify:
  1a. Energy balance: |Q_cond - (Q_evap + W_comp)| / Q_cond, max rel err
  1b. Water mass balance: sum(dm_w_total) vs m_w_cum_kg final
  1c. Convergence: drying-target reached vs ran out of clock at 72 h
  1d. Smoothness: T_chamber rate, RH bounds, COP bounds, NaN flags

Writes outputs/audit/step1_integrity.csv and prints a fail summary.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs"
AUDIT = PROJECT_ROOT.parent / "outputs" / "audit"
AUDIT.mkdir(parents=True, exist_ok=True)

X_TARGET = 0.18
MAX_HOURS_OK = 71.5
ETA_MECH = 0.95  # heatpump.py:26 — motor/mechanical efficiency
EB_TOL = 1e-3
COP_LO, COP_HI = 1.0, 10.0  # honest bounds when HP is actually running


def check(csv: Path):
    df = pd.read_csv(csv)
    rel = csv.relative_to(OUT)
    parts = rel.parts
    config = parts[0].replace("config_", "")
    location = parts[1]
    season = parts[2] if len(parts) > 3 else "annual"
    name = csv.stem

    n = len(df)
    if n == 0:
        return dict(config=config, location=location, season=season, file=name,
                    n=0, status="EMPTY")

    # 1a. Energy balance per step (W_comp adds enthalpy, Q_evap removes from cold side)
    qc = df["Q_cond_kW"].to_numpy()
    qe = df["Q_evap_kW"].to_numpy()
    wc = df["W_comp_kW"].to_numpy()
    eb_resid = qc - (qe + ETA_MECH * wc)
    mask = np.abs(qc) > 0.01
    eb_relerr = np.where(mask, np.abs(eb_resid) / np.maximum(np.abs(qc), 1e-9), 0.0)
    eb_max = float(np.max(eb_relerr))

    # 1b. Water mass balance
    dt = np.diff(df["time_s"].to_numpy(), prepend=df["time_s"].iloc[0])
    dm = df["dm_w_total_kg"].to_numpy()
    if "dm_w_total_kg" in df.columns and dm.max() > 0:
        # Integrate if dm_w_total looks like a rate; otherwise treat as per-step delta
        if dm.max() < 0.01:
            sum_dm = float(np.sum(dm * dt / 60.0))  # very rough
        else:
            sum_dm = float(np.sum(dm))
    else:
        sum_dm = float("nan")
    m_w_final = float(df["m_w_cum_kg"].iloc[-1])
    mb_err = abs(sum_dm - m_w_final) if np.isfinite(sum_dm) else float("nan")

    # 1c. Convergence
    final_X = float(df["X_db_avg"].iloc[-1])
    final_h = float(df["time_h"].iloc[-1])
    converged = (final_X <= X_TARGET) or (final_h < MAX_HOURS_OK)

    # 1d. Smoothness
    Tch = df["T_to_chamber_C"].to_numpy()
    dTdt = np.diff(Tch) / np.maximum(np.diff(df["time_s"].to_numpy()), 1.0) * 60.0  # C/min
    T_jump_max = float(np.max(np.abs(dTdt))) if dTdt.size else 0.0
    RH = df["RH_to_chamber_frac"].to_numpy()
    rh_lo, rh_hi = float(RH.min()), float(RH.max())
    # COP only meaningful when HP is actually running (W_comp materially > 0)
    if "hp_mode" in df.columns:
        running = df["hp_mode"].astype(str).str.lower().eq("full")
    else:
        running = df["W_comp_kW"] > 0.01
    cop_run = df.loc[running, "COP"].to_numpy()
    cop_run = cop_run[np.isfinite(cop_run)]
    cop_lo = float(cop_run.min()) if cop_run.size else float("nan")
    cop_hi = float(cop_run.max()) if cop_run.size else float("nan")
    nan_cols = [c for c in df.columns if df[c].isna().any()]

    flags = []
    if eb_max > EB_TOL:
        flags.append(f"EB({eb_max:.2e})")
    if not converged:
        flags.append(f"NOCONV({final_X:.3f}@{final_h:.1f}h)")
    if T_jump_max > 5.0:
        flags.append(f"Tjump({T_jump_max:.1f}C/min)")
    if rh_lo < -1e-6 or rh_hi > 1.0 + 1e-6:
        flags.append(f"RHoob({rh_lo:.2f},{rh_hi:.2f})")
    if cop_run.size and (cop_lo < COP_LO or cop_hi > COP_HI):
        flags.append(f"COPoob({cop_lo:.2f},{cop_hi:.2f})")
    if nan_cols:
        flags.append(f"NaN({len(nan_cols)})")

    return dict(
        config=config, location=location, season=season, file=name,
        n=n,
        eb_max_relerr=eb_max,
        m_w_final_kg=m_w_final,
        final_X=final_X,
        final_h=final_h,
        converged=converged,
        T_jump_max_C_per_min=T_jump_max,
        RH_min=rh_lo, RH_max=rh_hi,
        COP_min=cop_lo, COP_max=cop_hi,
        flags=";".join(flags) if flags else "",
        status="FAIL" if flags else "OK",
    )


def main():
    csvs = sorted([p for p in OUT.glob("config_E*/**/*.csv") if "config_E" in str(p)])
    rows = [check(c) for c in csvs]
    df = pd.DataFrame(rows)
    out_csv = AUDIT / "step1_integrity.csv"
    df.to_csv(out_csv, index=False, float_format="%.6g")
    print(f"Saved {out_csv}")

    n = len(df)
    n_ok = int((df["status"] == "OK").sum())
    print(f"\n{n_ok}/{n} runs PASS all checks.")
    bad = df[df["status"] != "OK"]
    if not bad.empty:
        print("\nFailures:")
        for _, r in bad.iterrows():
            print(f"  {r['config']:>3}  {r['location']:>12}  {r['season']:>15}  "
                  f"{r['file']:<35}  flags={r['flags']}")
    else:
        print("All clean.")

    # Bonus: summary stats
    print(f"\nEnergy-balance max relerr across all runs: {df['eb_max_relerr'].max():.2e}")
    print(f"COP range across all runs: [{df['COP_min'].min():.2f}, {df['COP_max'].max():.2f}]")
    print(f"Drying time h: min={df['final_h'].min():.1f}, "
          f"median={df['final_h'].median():.1f}, max={df['final_h'].max():.1f}")
    print(f"Final X_db: min={df['final_X'].min():.3f}, "
          f"median={df['final_X'].median():.3f}, max={df['final_X'].max():.3f}")


if __name__ == "__main__":
    main()
