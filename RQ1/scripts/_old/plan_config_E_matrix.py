"""Enumerate the full Config E simulation matrix and report what's missing.

Target matrix (matching the gold E2-KTM pattern, extended to all sites/configs/seasons):
- For each (config in E1,E2,E3) x (site in BTN,KTM,DHU,TPJ) x (period in annual + 4 seasons):
  - Areas: {2,4,5,6,8,10,15,20} m2 at hrx=0.70, vpd=off  (8 sims)
  - VPD sweep at A=10, hrx=0.70: {0.02, 0.05, 0.10, 0.15, 0.20}  (5 sims for annual; 1 sim @ 0.05 for each season)

Total per (config,site,period):
  annual: 8 + 5 = 13
  each season: 8 + 1 = 9
Per (config,site) = 13 + 9*4 = 49
Grand total = 49 * 4 sites * 3 configs = 588
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

CONFIGS = ["E1", "E2", "E3"]
SITES = ["biratnagar", "kathmandu", "dhulikhel", "taplejung"]
SEASONS = {
    "annual": None,
    "autumn_oct_nov": "autumn_oct_nov",
    "winter_dec_jan": "winter_dec_jan",
    "spring_mar_apr": "spring_mar_apr",
    "summer_may_jun": "summer_may_jun",
}
AREAS = [2, 4, 5, 6, 8, 10, 15, 20]
ANNUAL_VPDS = [0.02, 0.05, 0.10, 0.15, 0.20]
SEASONAL_VPDS = [0.02, 0.05, 0.10, 0.15, 0.20]


def expected_file(cfg: str, site: str, season_key: str, area: int, vpd: float | None) -> Path:
    base = OUT / f"config_{cfg}" / site
    if season_key != "annual":
        base = base / season_key
    name = f"Ac_{area}m2_hrx0.70"
    if vpd is not None:
        name += f"_vpd{vpd:.2f}"
    return base / f"{name}.csv"


def enumerate_targets():
    rows = []
    for cfg in CONFIGS:
        for site in SITES:
            for season_key in SEASONS:
                vpds = ANNUAL_VPDS if season_key == "annual" else SEASONAL_VPDS
                # area sweep at vpd=off
                for a in AREAS:
                    rows.append((cfg, site, season_key, a, None))
                # vpd sweep at A=10
                for v in vpds:
                    rows.append((cfg, site, season_key, 10, v))
    return rows


def main():
    targets = enumerate_targets()
    missing = []
    existing = 0
    for cfg, site, season_key, a, v in targets:
        p = expected_file(cfg, site, season_key, a, v)
        if p.exists():
            existing += 1
        else:
            missing.append((cfg, site, season_key, a, v, p))
    print(f"Total target sims: {len(targets)}")
    print(f"Already exist:     {existing}")
    print(f"Missing:           {len(missing)}")
    print()
    # breakdown by config
    print("Missing by config:")
    for cfg in CONFIGS:
        n = sum(1 for m in missing if m[0] == cfg)
        print(f"  {cfg}: {n}")
    print()
    print("Missing by site:")
    for site in SITES:
        n = sum(1 for m in missing if m[1] == site)
        print(f"  {site}: {n}")
    print()
    print("Missing by period:")
    for season_key in SEASONS:
        n = sum(1 for m in missing if m[2] == season_key)
        print(f"  {season_key}: {n}")

    # write the run plan
    plan_path = ROOT / "scripts" / "_run_plan_config_E.csv"
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write("config,site,period,area_m2,vpd_threshold\n")
        for cfg, site, season_key, a, v, _ in missing:
            f.write(f"{cfg},{site},{season_key},{a},{'' if v is None else v}\n")
    print(f"\nRun plan written: {plan_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
