# Phase-1 Drying Kinetics Pipeline

This repository contains drying-kinetics datasets and a runnable Phase-1 fitting
pipeline. The tooling can be executed from the command line or directly inside
VS Code's Interactive Window without any manual `PYTHONPATH` tweaks.

## Mathematical model summary

Given a tabular dataset containing either moisture ratio (MR) or dry-basis
moisture content \(X\), the pipeline assumes an equilibrium moisture content of
\(X_{eq}=0\). Moisture ratio is therefore computed as

\[
MR(t) = \frac{X(t) - X_{eq}}{X_0 - X_{eq}} = \frac{X(t)}{X_0}.
\]

The raw series is smoothed via a monotone (non-increasing) isotonic regression
before fitting.

Four empirical drying models are fitted using bounded non-linear least squares:

1. **Page**: \(MR(t) = \exp(-k t^n)\)
2. **Page (shifted)**: \(MR(t) = \exp(-k \max(t-\tau, 0)^n)\)
3. **Midilli (a = 1)**: \(MR(t) = \exp(-k t^n) + b t\)
4. **Midilli (shifted)**: \(MR(t) = \exp(-k \max(t-\tau, 0)^n) + b \max(t-\tau, 0)\)

Bounds enforce physically plausible parameters
(\(10^{-6} \le k \le 1\), \(0.2 \le n \le 2.5\), \(-0.01 \le b \le 0\),
\(0 \le \tau \le 10\)). Solver outputs include RMSE, SSE, AIC, AICc, BIC, and
a blocked leave-one-out RMSE (LOO-RMSE). Models are ranked primarily by AICc
with LOO-RMSE as a tie-breaker.

## Repository layout

```
src/kinetics/           # Preprocessing, models, and fitters
scripts/                # CLI + interactive entry points
phase1_out/             # Generated outputs (created at runtime)
.vscode/settings.json   # Ensures VS Code resolves imports
.env                    # Configures PYTHONPATH for shells and editors
```

Each dataset processed by the pipeline generates the following folder tree in
`phase1_out/<dataset_stem>/`:

```
summary.json
params.csv
fit_results.joblib
plots/
  01_mr_raw_vs_iso.png
  02_fit_best.png
  03_residuals_best.png
  04_qq_best.png
```

A consolidated `phase1_out/phase1_master.csv` is also maintained. It records the
fitted parameters, goodness-of-fit metrics, and experimental hints
(temperature, humidity, air speed, thickness).

## How to run

### Terminal (recommended)

1. Activate your Python environment.
2. Execute the pipeline using absolute paths on Windows:

   ```powershell
   python -m scripts.phase1_fit_once --input "D:\Masters\RQ5\Codex_chatgpt\T_40_v1p1.csv" --outdir "D:\Masters\RQ5\Codex_chatgpt\phase1_out" --head_trim_min 0
   python -m scripts.phase1_fit_all --outdir "D:\Masters\RQ5\Codex_chatgpt\phase1_out"
   ```

### VS Code Interactive Window

1. Open `scripts/phase1_fit_once.py`.
2. Run the **Quick-start (VS Code Interactive)** cell at the top, editing the
   input and output paths if necessary.
3. Artifacts appear in `phase1_out/…`.

The repository ships with `.env` and `.vscode/settings.json`, so imports resolve
without manual path adjustments.

## Outputs and diagnostics

* `01_mr_raw_vs_iso.png` – monotonic smoothing check.
* `02_fit_best.png` – best-model overlay with parameter annotations.
* `03_residuals_best.png` – residuals vs. time with zero reference.
* `04_qq_best.png` – QQ plot to visually assess residual normality.
* `summary.json` – structured metadata, parameters, metrics, warnings.
* `params.csv` – one row per model, suitable for analysis.
* `fit_results.joblib` – serialized fit objects for reuse.
* `phase1_master.csv` – master table for downstream Phase-2 mapping.

## Troubleshooting

* Ensure SciPy, NumPy, Pandas, Matplotlib, and Joblib are installed in your
  environment.
* If you add new modules, confirm they live under `src/` so the provided
  `PYTHONPATH` picks them up automatically.
* Use the `--head_trim_min` flag if early-time noise impacts the fits.
