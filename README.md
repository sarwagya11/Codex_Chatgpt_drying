# Phase-1 Drying Kinetics Pipeline

This repository contains a small toolkit for preprocessing raw drying data and fitting Page and Midilli Phase-1 models.

## Environment

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Project Layout

- `src/kinetics/`: library code for preprocessing, model evaluation, and fitting.
- `scripts/`: runnable scripts designed for command line or VS Code's Interactive Window.
- `data/raw/`: optional location for raw CSV/XLSX files (files can also live at the project root).
- `outputs/phase1_fits/`: generated fit artifacts, plots, and the consolidated `phase1_master.csv`.

## Running a Single File

Use the `phase1_fit_once.py` script:

```bash
python scripts/phase1_fit_once.py --input "D:\\Masters\\RQ5\\Codex_chatgpt\\T_40_v1p1.csv" --outdir outputs/phase1_fits
```

The script accepts `--head_trim_min` to remove the specified number of minutes from the start of the curve before fitting.

In VS Code's Interactive Window, open the script and run the top `# %%` cell, then edit and execute the provided example block.

## Batch Processing

Run the batch pipeline to process every CSV/XLSX file in the project root and `data/raw/`:

```bash
python scripts/phase1_fit_all.py --outdir outputs/phase1_fits
```

The batch runner skips files inside `outputs/` and `scripts/`, continues on errors, and reports a summary with a consolidated master CSV.

