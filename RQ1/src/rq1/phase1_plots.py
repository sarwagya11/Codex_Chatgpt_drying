"""Plotting utilities for Phase-1 dryer simulations."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import pandas as pd

from .dryer_phase1 import Phase1Result


def _ensure_parent_dir(out_path: Path) -> None:
    """Ensure the parent directory for a file path exists."""

    out_path.parent.mkdir(parents=True, exist_ok=True)


def plot_temperatures(
    results_by_r: Dict[float, Phase1Result],
    out_path: Path,
    title: str = "Dryer air temperatures vs time",
) -> None:
    """
    Plot ambient, mix, inlet, and outlet temperatures versus time for multiple recirculation ratios.

    Parameters
    ----------
    results_by_r:
        Mapping from recirculation ratio to Phase1Result.
    out_path:
        Destination file path for the PNG figure.
    title:
        Figure title.
    """

    _ensure_parent_dir(out_path)

    fig, ax = plt.subplots(figsize=(8, 5))

    # Plot outlet temperatures for each recirculation ratio
    for r, res in sorted(results_by_r.items()):
        df = res.df
        if df.empty:
            continue
        times_min = df["time_s"] / 60.0
        ax.plot(times_min, df["T_out_C"], label=f"r = {r:.2f}")

    # Use the first non-empty result for common ambient and inlet traces
    for res in results_by_r.values():
        df = res.df
        if df.empty:
            continue
        times_min = df["time_s"] / 60.0
        ax.plot(times_min, df["T_in_C"], color="black", linewidth=2.5, label="T_in (set)")
        ax.plot(times_min, df["T_amb_C"], color="gray", linestyle="--", label="T_amb")
        break

    ax.set_title(title)
    ax.set_xlabel("Time [min]")
    ax.set_ylabel("Temperature [°C]")
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_humidity_and_MR(
    results_by_r: Dict[float, Phase1Result],
    out_path: Path,
    title: str = "Outlet RH and moisture ratio vs time",
) -> None:
    """
    Plot outlet relative humidity and moisture ratio on two subplots for multiple recirculation ratios.

    Left subplot shows outlet relative humidity (percent) vs time; right subplot shows moisture ratio.
    """

    _ensure_parent_dir(out_path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(title)
    ax_rh, ax_mr = axes

    for r, res in sorted(results_by_r.items()):
        df = res.df
        if df.empty:
            continue
        times_min = df["time_s"] / 60.0
        ax_rh.plot(times_min, 100.0 * df["RH_out_frac"], label=f"r = {r:.2f}")
        ax_mr.plot(times_min, df["MR"], label=f"r = {r:.2f}")

        if {"X_tray_0", "X_tray_last"}.issubset(df.columns):
            X0_first = df["X_tray_0"].iloc[0]
            X0_last = df["X_tray_last"].iloc[0]

            if X0_first != 0:
                ax_mr.plot(
                    times_min,
                    df["X_tray_0"] / X0_first,
                    linestyle="--",
                    label=f"Tray 0 (norm), r={r:.2f}",
                )

            if X0_last != 0:
                ax_mr.plot(
                    times_min,
                    df["X_tray_last"] / X0_last,
                    linestyle=":",
                    label=f"Tray last (norm), r={r:.2f}",
                )

    ax_rh.set_title("Outlet relative humidity")
    ax_rh.set_xlabel("Time [min]")
    ax_rh.set_ylabel("Outlet RH [%]")
    ax_rh.grid(True, alpha=0.3)
    ax_rh.legend()

    ax_mr.set_title("Moisture ratio")
    ax_mr.set_xlabel("Time [min]")
    ax_mr.set_ylabel("Moisture ratio [-]")
    ax_mr.grid(True, alpha=0.3)
    ax_mr.legend()

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_energy_and_water(
    results_by_r: Dict[float, Phase1Result],
    out_path: Path,
    title: str = "Cumulative heater energy and water removed",
) -> None:
    """
    Plot cumulative heater energy and cumulative water removed for multiple recirculation ratios.

    The left subplot shows cumulative heater energy; the right shows cumulative water removed.
    """

    _ensure_parent_dir(out_path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(title)
    ax_energy, ax_water = axes

    for r, res in sorted(results_by_r.items()):
        df = res.df
        if df.empty:
            continue
        times_min = df["time_s"] / 60.0
        ax_energy.plot(times_min, df["Q_heater_cum_kJ"], label=f"r = {r:.2f}")

        tray_dm_cols = sorted(col for col in df.columns if col.startswith("dm_w_tray"))
        if tray_dm_cols:
            tray_totals = [df[col].sum() for col in tray_dm_cols]
            tray_summary = ", ".join(f"{i}: {total:.3f} kg" for i, total in enumerate(tray_totals))
            label_water = f"r = {r:.2f} (tray dm: {tray_summary})"
        else:
            label_water = f"r = {r:.2f}"

        ax_water.plot(times_min, df["m_w_cum_kg"], label=label_water)

    ax_energy.set_title("Cumulative heater energy")
    ax_energy.set_xlabel("Time [min]")
    ax_energy.set_ylabel("Cumulative heater energy [kJ]")
    ax_energy.grid(True, alpha=0.3)
    ax_energy.legend()

    ax_water.set_title("Cumulative water removed")
    ax_water.set_xlabel("Time [min]")
    ax_water.set_ylabel("Cumulative water removed [kg]")
    ax_water.grid(True, alpha=0.3)
    ax_water.legend()

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def summarize_SEC_vs_r(
    results_by_r: Dict[float, Phase1Result],
    out_path: Path,
    title: str = "Specific energy consumption vs recirculation ratio",
) -> None:
    """
    Plot specific energy consumption (SEC) against recirculation ratio and save a summary CSV.

    The CSV shares the same stem as the figure and includes the recirculation ratio, SEC, total time, and final MR.
    """

    _ensure_parent_dir(out_path)

    summary_rows = []
    for r, res in sorted(results_by_r.items()):
        df = res.df
        if df.empty:
            summary_rows.append({"r": r, "SEC_kWh_per_kg": None, "total_time_s": None, "final_MR": None})
            continue
        sec_series = df.get("SEC_kWh_per_kg", pd.Series(dtype=float)).dropna()
        sec_value = sec_series.iloc[-1] if not sec_series.empty else None
        summary_rows.append(
            {
                "r": r,
                "SEC_kWh_per_kg": sec_value,
                "total_time_s": df["time_s"].iloc[-1],
                "final_MR": df["MR"].iloc[-1],
            }
        )

    summary_df = pd.DataFrame(summary_rows)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(summary_df["r"], summary_df["SEC_kWh_per_kg"], marker="o")
    ax.set_title(title)
    ax.set_xlabel("Recirculation ratio r [-]")
    ax.set_ylabel("SEC [kWh/kg water removed]")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    csv_path = out_path.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(csv_path, index=False)


def plot_MR_trays_per_r(results_by_r: Dict[float, Phase1Result], output_dir: Path, n_trays: int) -> None:
    """Plot tray-wise moisture ratios vs time for each recirculation ratio."""

    for r, res in sorted(results_by_r.items()):
        df = res.df
        if df.empty:
            continue

        fig, ax = plt.subplots(figsize=(6, 4))
        t_min = df["time_s"] / 60.0

        for j in range(n_trays):
            col = f"MR_tray{j}"
            if col in df.columns:
                ax.plot(t_min, df[col], label=f"Tray {j}")

        ax.set_xlabel("Time [min]")
        ax.set_ylabel("Moisture ratio [-]")
        ax.set_title(f"Tray-wise MR vs time (r = {r:.2f})")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / f"phase1_MR_trays_r{r:.2f}.png", dpi=150)
        plt.close(fig)


def plot_air_trays_per_r(results_by_r: Dict[float, Phase1Result], output_dir: Path, n_trays: int) -> None:
    """Plot air outlet temperature and RH per tray for each recirculation ratio."""

    for r, res in sorted(results_by_r.items()):
        df = res.df
        if df.empty:
            continue

        t_min = df["time_s"] / 60.0
        fig, (axT, axRH) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)

        for j in range(n_trays):
            T_col = f"T_tray{j}_out_C"
            RH_col = f"RH_tray{j}_out_frac"
            if T_col in df.columns:
                axT.plot(t_min, df[T_col], label=f"Tray {j}")
            if RH_col in df.columns:
                axRH.plot(t_min, df[RH_col] * 100.0, label=f"Tray {j}")

        axT.set_ylabel("T outlet [°C]")
        axT.set_title(f"Air outlet per tray (r = {r:.2f})")
        axT.legend()

        axRH.set_xlabel("Time [min]")
        axRH.set_ylabel("RH outlet [%]")

        fig.tight_layout()
        fig.savefig(output_dir / f"phase1_air_trays_r{r:.2f}.png", dpi=150)
        plt.close(fig)
