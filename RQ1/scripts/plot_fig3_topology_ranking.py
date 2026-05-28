"""Figure 3: cross-family SEC heatmap (config x site x season).

Renders one heatmap from `outputs/paper_matrix_summary.csv`:
  - 11 configurations (rows, ordered by annual-mean SEC ascending)
  - 4 sites x 5 blocks (annual + 4 seasons) -> 20 columns
  - cell fill = SEC (kWh / kg water); annotation = the same number
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "outputs" / "paper_matrix_summary.csv"
OUT_DIR = ROOT / "outputs" / "paperplots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITE_ORDER = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
SITE_LABELS = {
    "biratnagar": "Biratnagar\n(72 m)",
    "kathmandu": "Kathmandu\n(1350 m)",
    "dhulikhel": "Dhulikhel\n(1550 m)",
    "taplejung": "Taplejung\n(1820 m)",
}
SEASON_ORDER = ["annual", "autumn_oct_nov", "winter_dec_jan", "spring_mar_apr", "summer_may_jun"]
SEASON_LABELS = {
    "annual": "Ann",
    "autumn_oct_nov": "Aut",
    "winter_dec_jan": "Win",
    "spring_mar_apr": "Spr",
    "summer_may_jun": "Sum",
}

CONFIG_LABELS = {
    "0": "0",
    "A": "A",
    "B1": "B1",
    "B2": "B2",
    "C1": "C1",
    "D1": "D1",
    "D2": "D2",
    "D3": "D3",
    "E1": "E1",
    "E2": "E2",
    "E3": "E3",
}


def load_matrix() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    keep = df[df["block"].isin(["annual", "seasonal"])].copy()
    keep["season"] = keep["season"].replace({"annual": "annual"})
    return keep


FAMILY_GROUPS = [
    ("HP + HRX\n+ Solar", ["E2", "E1", "E3"]),
    ("HP + HRX", ["D1", "D2"]),
    ("HP + Solar", ["B1", "B2", "C1"]),
    ("HP", ["A"]),
    ("Electric", ["0"]),
]


def pivot_sec(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    config_order = [c for _, members in FAMILY_GROUPS for c in members]

    columns = []
    for site in SITE_ORDER:
        for season in SEASON_ORDER:
            columns.append((site, season))

    table = pd.DataFrame(index=config_order, columns=pd.MultiIndex.from_tuples(columns), dtype=float)
    for _, row in df.iterrows():
        cfg = row["config"]
        site = row["location"]
        season = row["season"]
        if cfg in table.index and (site, season) in table.columns:
            table.loc[cfg, (site, season)] = row["SEC_kWh_per_kg"]
    return table, config_order


def _fmt(v: float) -> str:
    if v >= 10:
        return f"{v:.2f}"
    if v >= 1:
        return f"{v:.3f}"
    return f"{v:.3f}"


def render(table: pd.DataFrame, config_order: list[str]) -> None:
    hp_configs = [c for c in config_order if c != "0"]
    hp_table = table.loc[hp_configs]
    el_table = table.loc[["0"]] if "0" in table.index else None

    hp_values = hp_table.values.astype(float)
    ncols = hp_values.shape[1]
    seasons_per_site = len(SEASON_ORDER)

    fig = plt.figure(figsize=(11.5, 6.4), dpi=200)
    gs = fig.add_gridspec(
        nrows=2, ncols=2,
        width_ratios=[1.0, 0.025],
        height_ratios=[len(hp_configs), 1.0],
        hspace=0.10, wspace=0.02,
    )
    ax_hp = fig.add_subplot(gs[0, 0])
    cax_hp = fig.add_subplot(gs[0, 1])
    ax_el = fig.add_subplot(gs[1, 0], sharex=ax_hp)
    cax_el = fig.add_subplot(gs[1, 1])

    cmap = plt.get_cmap("cividis_r")

    vmin_hp = 0.10
    vmax_hp = max(0.55, float(np.nanmax(hp_values)))
    im_hp = ax_hp.imshow(hp_values, aspect="auto", cmap=cmap, vmin=vmin_hp, vmax=vmax_hp)

    for i in range(len(hp_configs)):
        for j in range(ncols):
            v = hp_values[i, j]
            norm = (v - vmin_hp) / (vmax_hp - vmin_hp)
            txt_color = "white" if norm > 0.55 else "black"
            ax_hp.text(j, i, _fmt(v), ha="center", va="center", fontsize=7, color=txt_color)

    ax_hp.set_yticks(range(len(hp_configs)))
    ax_hp.set_yticklabels([CONFIG_LABELS[c] for c in hp_configs], fontsize=9)
    ax_hp.tick_params(axis="x", labelbottom=False)

    for s in range(1, len(SITE_ORDER)):
        ax_hp.axvline(s * seasons_per_site - 0.5, color="black", lw=1.2)

    cum = 0
    for fam_label, members in FAMILY_GROUPS:
        if fam_label == "Electric":
            continue
        cum_next = cum + len(members)
        if cum_next < len(hp_configs):
            ax_hp.axhline(cum_next - 0.5, color="black", lw=0.9, linestyle="--", alpha=0.75)
        mid = cum + (len(members) - 1) / 2
        ax_hp.text(
            -0.075, mid,
            fam_label,
            transform=ax_hp.get_yaxis_transform(),
            ha="right", va="center", fontsize=9, fontweight="bold",
        )
        cum = cum_next

    site_centers = [s * seasons_per_site + (seasons_per_site - 1) / 2 for s in range(len(SITE_ORDER))]
    secax = ax_hp.secondary_xaxis("top")
    secax.set_xticks(site_centers)
    secax.set_xticklabels([SITE_LABELS[s] for s in SITE_ORDER], fontsize=9)
    secax.tick_params(length=0)

    ax_hp.set_xticks(np.arange(-0.5, ncols, 1), minor=True)
    ax_hp.set_yticks(np.arange(-0.5, len(hp_configs), 1), minor=True)
    ax_hp.grid(which="minor", color="white", linewidth=0.4)
    ax_hp.tick_params(which="minor", length=0)

    cbar = fig.colorbar(im_hp, cax=cax_hp)
    cbar.set_label("SEC (kWh / kg water) - HP family", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    el_values = el_table.values.astype(float)
    vmin_el = float(np.nanmin(el_values)) * 0.98
    vmax_el = float(np.nanmax(el_values)) * 1.02
    im_el = ax_el.imshow(el_values, aspect="auto", cmap=cmap, vmin=vmin_el, vmax=vmax_el)

    for j in range(ncols):
        v = el_values[0, j]
        norm = (v - vmin_el) / max(vmax_el - vmin_el, 1e-9)
        txt_color = "white" if norm > 0.55 else "black"
        ax_el.text(j, 0, _fmt(v), ha="center", va="center", fontsize=7, color=txt_color)

    ax_el.set_yticks([0])
    ax_el.set_yticklabels([CONFIG_LABELS["0"]], fontsize=9)
    ax_el.text(
        -0.075, 0,
        "Electric",
        transform=ax_el.get_yaxis_transform(),
        ha="right", va="center", fontsize=9, fontweight="bold",
    )

    season_ticks = list(range(ncols))
    ax_el.set_xticks(season_ticks)
    ax_el.set_xticklabels(
        [SEASON_LABELS[season] for _, season in table.columns],
        fontsize=8,
    )
    for s in range(1, len(SITE_ORDER)):
        ax_el.axvline(s * seasons_per_site - 0.5, color="black", lw=1.2)
    ax_el.set_xticks(np.arange(-0.5, ncols, 1), minor=True)
    ax_el.set_yticks(np.arange(-0.5, 1, 1), minor=True)
    ax_el.grid(which="minor", color="white", linewidth=0.4)
    ax_el.tick_params(which="minor", length=0)
    ax_el.set_xlabel("Season block (annual + 4 seasons per site)", fontsize=9)

    cbar_el = fig.colorbar(im_el, cax=cax_el)
    cbar_el.set_label("electric", fontsize=8)
    cbar_el.ax.tick_params(labelsize=7)

    out_png = OUT_DIR / "fig3_topology_ranking_heatmap.png"
    out_svg = OUT_DIR / "fig3_topology_ranking_heatmap.svg"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    print(f"wrote {out_png}")
    print(f"wrote {out_svg}")


def main() -> None:
    df = load_matrix()
    table, config_order = pivot_sec(df)
    missing = table.isna().sum().sum()
    if missing:
        print(f"WARNING: {missing} cells missing")
    render(table, config_order)


if __name__ == "__main__":
    main()
