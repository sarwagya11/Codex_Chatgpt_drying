"""
Phase 6 / Study 1 -- Leave-One-Condition-Out cross-validation
for the piecewise + ML kinetic model.

For each of the 14 (T, v, RH, thickness) conditions:
  1. Hold that row out of phase2_targets.csv.
  2. Re-train all 9 regressors on the remaining 13 rows:
       kL, nL, bL, kR, nR, bR, offsetR_at_join, right_time_shift_at_boundary, t_split
  3. Predict the 9 parameters for the held-out condition.
  4. Reconstruct MR(t) on the raw data time grid using piecewise Midilli/Page
     (same formula as RQ1/src/rq1/midilli_table.reconstruct_piecewise_mr).
  5. Score RMSE_MR, R^2, MBE, chi^2, EF, time_at_MR=0.1, parameter errors.

Outputs:
  outputs/phase2/diagnostics/loco_cv_results.csv
  outputs/phase2/diagnostics/loco_cv_summary.json
  outputs/phase2/diagnostics/loco_cv_predictions/<dataset>_pred_vs_actual.csv
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = PROJECT_ROOT / "outputs" / "phase2" / "phase2_targets.csv"
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "outputs" / "phase2" / "diagnostics"
PRED_DIR = OUT_DIR / "loco_cv_predictions"

FEATURES = ["T_C", "v_ms", "thickness_mm", "RH_mid_pct"]

# 9 regression targets. t_split is sourced from tR_start in phase2_targets.
TARGETS: List[str] = [
    "kL", "nL", "bL",
    "kR", "nR", "bR",
    "offsetR_at_join", "right_time_shift_at_boundary",
    "t_split",
]

# Match meta.json transforms for ML targets; t_split uses log too (positive, spans wide range).
LOG_TARGETS = {"kL", "nL", "kR", "nR", "t_split"}

# ElasticNet hyperparameters per target (alpha = l1_ratio in sklearn convention).
EN_PARAMS: Dict[str, Tuple[float, float]] = {
    "kL":                          (0.0,  6.21),
    "nL":                          (0.0,  6.21),
    "bL":                          (0.25, 1e-5),
    "kR":                          (0.5,  6.21),
    "nR":                          (0.75, 0.92),
    "bR":                          (0.0,  2.59e-5),
    "offsetR_at_join":             (0.25, 3.86),
    "right_time_shift_at_boundary":(0.75, 10.0),
    "t_split":                     (0.5,  1.0),
}


@dataclass
class FoldResult:
    dataset: str
    rmse_mr: float
    r2: float
    mbe: float
    chi2_red: float
    ef: float
    t_at_target_actual: float
    t_at_target_pred: float
    t_at_target_rel_err: float
    n_obs: int
    pred_params: Dict[str, float]
    actual_params: Dict[str, float]


def load_raw_mr(dataset: str) -> Tuple[np.ndarray, np.ndarray]:
    """Return (time_min, MR_iso) for a dataset."""
    path = DATA_DIR / f"{dataset}.csv"
    df = pd.read_csv(path)
    time = df["time_min"].astype(float).to_numpy()
    x = df["X_db"].astype(float).to_numpy()
    if not np.isfinite(x[0]) or x[0] == 0:
        raise ValueError(f"Initial moisture invalid for {dataset}")
    mr = np.clip(x / x[0], 0.0, 1.1)
    # Pool-adjacent-violators monotone decreasing (matches preprocess_phase1).
    order = np.argsort(time)
    time_s = time[order]
    mr_s = mr[order].astype(float)
    blocks: List[Tuple[float, int]] = []
    for v in mr_s:
        blocks.append((float(v), 1))
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            (a, ca), (b, cb) = blocks[-2], blocks[-1]
            blocks[-2:] = [((a * ca + b * cb) / (ca + cb), ca + cb)]
    iso = np.empty_like(mr_s)
    i = 0
    for value, count in blocks:
        iso[i:i + count] = value
        i += count
    return time_s, iso


def midilli(t: np.ndarray, k: float, n: float, b: float, is_page: bool) -> np.ndarray:
    safe_t = np.maximum(t, 0.0)
    base = np.exp(-k * np.power(safe_t, n))
    return base if is_page else base + b * safe_t


def reconstruct_piecewise(
    time_min: np.ndarray,
    kL: float, nL: float, bL: float, is_page_L: bool,
    kR: float, nR: float, bR: float, is_page_R: bool,
    t_split: float, offsetR: float, t_shift: float,
) -> np.ndarray:
    t = np.asarray(time_min, dtype=float)
    MR_L = midilli(t, kL, nL, bL, is_page_L)
    MR_out = MR_L.copy()
    right_mask = t >= t_split
    if right_mask.any():
        right_t = np.maximum(t[right_mask] + t_shift, 0.0)
        right_vals = midilli(right_t, kR, nR, bR, is_page_R) + offsetR
        # enforce monotone non-increasing on the right segment (matches midilli_table)
        MR_out[right_mask] = np.minimum.accumulate(right_vals)
    return np.clip(MR_out, 0.0, 1.0)


def fit_predict_params(
    train_df: pd.DataFrame, test_row: pd.Series
) -> Dict[str, float]:
    """Fit one ElasticNet per target on the 13-row train set, predict for test row."""
    X_train = train_df[FEATURES].to_numpy(dtype=float)
    X_test = test_row[FEATURES].to_numpy(dtype=float).reshape(1, -1)
    scaler = StandardScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    pred: Dict[str, float] = {}
    for tgt in TARGETS:
        y_train_raw = train_df[tgt].to_numpy(dtype=float)
        if tgt in LOG_TARGETS:
            # Guard against zero/negative; t_split is positive, k/n are positive in this dataset.
            y_train = np.log(np.clip(y_train_raw, 1e-12, None))
        else:
            y_train = y_train_raw

        l1, lam = EN_PARAMS[tgt]
        # ElasticNet alpha = lam, l1_ratio = l1. l1_ratio in [0, 1].
        if l1 == 0.0:
            # Pure Ridge via ElasticNet not supported; use small l1 instead.
            l1 = 1e-3
        model = ElasticNet(alpha=lam, l1_ratio=l1, max_iter=20000, fit_intercept=True, random_state=0)
        model.fit(X_train_s, y_train)
        y_pred = float(model.predict(X_test_s)[0])
        if tgt in LOG_TARGETS:
            y_pred = float(np.exp(y_pred))
        pred[tgt] = y_pred
    return pred


def metrics_mr(actual: np.ndarray, pred: np.ndarray, n_params: int = 9) -> Dict[str, float]:
    mask = np.isfinite(actual) & np.isfinite(pred)
    a = actual[mask]
    p = pred[mask]
    if a.size == 0:
        return dict(rmse=float("nan"), r2=float("nan"), mbe=float("nan"),
                    chi2_red=float("nan"), ef=float("nan"))
    res = a - p
    sse = float(np.sum(res * res))
    sst = float(np.sum((a - a.mean()) ** 2))
    rmse = float(np.sqrt(sse / a.size))
    r2 = 1.0 - sse / sst if sst > 0 else float("nan")
    mbe = float(np.mean(res))
    dof = max(a.size - n_params, 1)
    chi2_red = sse / dof
    ef = r2  # Nash-Sutcliffe Efficiency = R^2 here for a 1:1 model
    return dict(rmse=rmse, r2=r2, mbe=mbe, chi2_red=chi2_red, ef=ef)


def time_at_mr(time_min: np.ndarray, mr: np.ndarray, target: float = 0.1) -> float:
    """Linear interpolation of t when MR first crosses `target` (decreasing)."""
    if mr[0] < target:
        return float(time_min[0])
    if mr[-1] > target:
        return float("nan")  # never reached
    for i in range(1, len(mr)):
        if mr[i] <= target:
            t1, t2 = time_min[i - 1], time_min[i]
            m1, m2 = mr[i - 1], mr[i]
            if m1 == m2:
                return float(t1)
            return float(t1 + (target - m1) * (t2 - t1) / (m2 - m1))
    return float("nan")


def run_loco_cv() -> None:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(TARGETS_CSV)
    df = df.copy()
    # Canonical t_split from phase2 targets: rR_start.
    df["t_split"] = df["tR_start"].astype(float)
    # Convert string flags to bool just in case.
    df["famL_is_page"] = df["famL_is_page"].astype(str).str.lower().isin(["true", "1"])
    df["famR_is_page"] = df["famR_is_page"].astype(str).str.lower().isin(["true", "1"])

    folds: List[FoldResult] = []
    target_mr = 0.1

    for i in range(len(df)):
        test_row = df.iloc[i]
        train_df = df.drop(df.index[i]).reset_index(drop=True)
        dataset = str(test_row["dataset"])

        pred_params = fit_predict_params(train_df, test_row)

        # Carry family flags from majority vote of training (binary; conservative).
        is_page_L = bool(train_df["famL_is_page"].mode().iat[0])
        is_page_R = bool(train_df["famR_is_page"].mode().iat[0])

        # Load raw MR
        time, mr_actual = load_raw_mr(dataset)

        # Reconstruct using PREDICTED params on this dataset's time grid.
        mr_pred = reconstruct_piecewise(
            time,
            kL=pred_params["kL"], nL=pred_params["nL"], bL=pred_params["bL"],
            is_page_L=is_page_L,
            kR=pred_params["kR"], nR=pred_params["nR"], bR=pred_params["bR"],
            is_page_R=is_page_R,
            t_split=pred_params["t_split"],
            offsetR=pred_params["offsetR_at_join"],
            t_shift=pred_params["right_time_shift_at_boundary"],
        )

        m = metrics_mr(mr_actual, mr_pred)

        t_actual = time_at_mr(time, mr_actual, target_mr)
        t_pred = time_at_mr(time, mr_pred, target_mr)
        if np.isfinite(t_actual) and np.isfinite(t_pred) and t_actual > 0:
            t_rel = abs(t_pred - t_actual) / t_actual
        else:
            t_rel = float("nan")

        actual_params = {
            "kL": float(test_row["kL"]), "nL": float(test_row["nL"]), "bL": float(test_row["bL"]),
            "kR": float(test_row["kR"]), "nR": float(test_row["nR"]), "bR": float(test_row["bR"]),
            "offsetR_at_join": float(test_row["offsetR_at_join"]),
            "right_time_shift_at_boundary": float(test_row["right_time_shift_at_boundary"]),
            "t_split": float(test_row["t_split"]),
        }

        folds.append(FoldResult(
            dataset=dataset, rmse_mr=m["rmse"], r2=m["r2"], mbe=m["mbe"],
            chi2_red=m["chi2_red"], ef=m["ef"],
            t_at_target_actual=t_actual, t_at_target_pred=t_pred, t_at_target_rel_err=t_rel,
            n_obs=int(np.sum(np.isfinite(mr_actual))),
            pred_params=pred_params, actual_params=actual_params,
        ))

        # Per-fold pred-vs-actual CSV
        out_pred = pd.DataFrame({
            "time_min": time, "mr_actual": mr_actual, "mr_pred": mr_pred,
        })
        out_pred.to_csv(PRED_DIR / f"{dataset}_pred_vs_actual.csv", index=False, float_format="%.9g")

        print(f"[{i+1:2d}/{len(df)}] {dataset:30s} RMSE={m['rmse']:.4f} R2={m['r2']:.4f} "
              f"MBE={m['mbe']:+.4f} t10%_relerr={t_rel:.3f}")

    # Aggregate
    rows = []
    for f in folds:
        row = {
            "dataset": f.dataset,
            "rmse_mr": f.rmse_mr, "r2": f.r2, "mbe": f.mbe,
            "chi2_red": f.chi2_red, "ef": f.ef,
            "t_at_MR0p1_actual": f.t_at_target_actual,
            "t_at_MR0p1_pred": f.t_at_target_pred,
            "t_at_MR0p1_rel_err": f.t_at_target_rel_err,
            "n_obs": f.n_obs,
        }
        for k, v in f.pred_params.items():
            row[f"pred_{k}"] = v
        for k, v in f.actual_params.items():
            row[f"actual_{k}"] = v
        rows.append(row)
    results_df = pd.DataFrame(rows)
    results_df.to_csv(OUT_DIR / "loco_cv_results.csv", index=False, float_format="%.9g")

    # Summary
    summary = {
        "n_folds": len(folds),
        "rmse_mr_mean": float(np.nanmean(results_df["rmse_mr"])),
        "rmse_mr_std": float(np.nanstd(results_df["rmse_mr"])),
        "rmse_mr_max": float(np.nanmax(results_df["rmse_mr"])),
        "r2_mean": float(np.nanmean(results_df["r2"])),
        "r2_min": float(np.nanmin(results_df["r2"])),
        "mbe_mean": float(np.nanmean(results_df["mbe"])),
        "ef_mean": float(np.nanmean(results_df["ef"])),
        "t_at_MR0p1_rel_err_mean": float(np.nanmean(results_df["t_at_MR0p1_rel_err"])),
        "t_at_MR0p1_rel_err_max": float(np.nanmax(results_df["t_at_MR0p1_rel_err"])),
        "n_pass_rmse_lt_0p025": int(np.sum(results_df["rmse_mr"] < 0.025)),
        "n_pass_r2_gt_0p99": int(np.sum(results_df["r2"] > 0.99)),
        "acceptance_threshold_rmse": 0.025,
        "acceptance_threshold_r2": 0.99,
        "acceptance_threshold_t_rel_err": 0.10,
    }
    (OUT_DIR / "loco_cv_summary.json").write_text(json.dumps(summary, indent=2))

    print()
    print("=" * 70)
    print(f"LOCO-CV summary  (n={summary['n_folds']})")
    print("=" * 70)
    print(f"RMSE_MR  mean={summary['rmse_mr_mean']:.4f}  std={summary['rmse_mr_std']:.4f}  max={summary['rmse_mr_max']:.4f}")
    print(f"R^2      mean={summary['r2_mean']:.4f}  min={summary['r2_min']:.4f}")
    print(f"MBE      mean={summary['mbe_mean']:+.4f}")
    print(f"t@MR=0.1 mean rel-err={summary['t_at_MR0p1_rel_err_mean']:.3f}  max={summary['t_at_MR0p1_rel_err_max']:.3f}")
    print(f"Folds passing RMSE<0.025  : {summary['n_pass_rmse_lt_0p025']}/{summary['n_folds']}")
    print(f"Folds passing R^2>0.99    : {summary['n_pass_r2_gt_0p99']}/{summary['n_folds']}")
    print(f"\nResults : {OUT_DIR / 'loco_cv_results.csv'}")
    print(f"Summary : {OUT_DIR / 'loco_cv_summary.json'}")


if __name__ == "__main__":
    run_loco_cv()
