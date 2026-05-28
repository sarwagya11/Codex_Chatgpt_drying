"""Fetch PVGIS plane-of-array (POA) hourly TMY data for the paper-1 sites.

Replaces the legacy GHI pull. Uses PVGIS v5.3 /seriescalc endpoint with
slope=45 deg, aspect=0 deg (south), database=PVGIS-ERA5 (SARAH3 doesn't
cover Nepal; coverage ends near 70 deg E), components=1 so
we get Gb(i)+Gd(i)+Gr(i) split out (sum = G(i) = POA). We then TMY-filter
the multi-year series to a single 8760-row representative year per site.

PVGIS already applies the Perez transposition and embeds incidence-angle
behaviour in G(i), so the downstream solar model keeps K_theta = 1.0
(do NOT re-apply IAM on top of POA).

Output: data/ambient/poa45/{site}_pvgis_poa45_raw.csv  (PVGIS native format)

Run:
    python scripts/fetch_pvgis_poa.py
    python scripts/fetch_pvgis_poa.py --sites kathmandu jomsom
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "ambient" / "poa45"

PVGIS_ENDPOINT = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"

SITES: dict[str, tuple[float, float]] = {
    "biratnagar": (26.4525, 87.2718),
    "kathmandu":  (27.7172, 85.3240),
    "jomsom":     (28.7800, 83.7233),
    "namche":     (27.8044, 86.7142),
}

TILT_DEG: float = 45.0
AZIMUTH_DEG: float = 0.0   # PVGIS convention: 0 = south
DATABASE: str = "PVGIS-ERA5"  # SARAH3 stops at ~70 deg E, no Nepal coverage


def fetch_one(site: str, lat: float, lon: float, out_path: Path) -> None:
    params = {
        "lat": lat,
        "lon": lon,
        "raddatabase": DATABASE,
        "startyear": 2005,
        "endyear": 2023,  # ERA5 extends through ~2023
        "angle": TILT_DEG,
        "aspect": AZIMUTH_DEG,
        "components": 1,
        "usehorizon": 1,
        "outputformat": "csv",
        "browser": 0,
    }
    print(f"  {site:12s} lat={lat:.4f} lon={lon:.4f} tilt={TILT_DEG}deg ... ", end="", flush=True)
    t0 = time.time()
    resp = requests.get(PVGIS_ENDPOINT, params=params, timeout=120)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(resp.text, encoding="utf-8")
    print(f"OK ({len(resp.text)/1024:.0f} kB in {time.time()-t0:.1f} s) -> {out_path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sites", nargs="+", default=list(SITES.keys()),
                        help="Subset of sites to fetch (default: all 4)")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    print(f"PVGIS POA fetch ({DATABASE}, tilt={TILT_DEG} deg, az={AZIMUTH_DEG} deg)")
    print(f"Output dir: {args.output_dir}")
    print()

    for site in args.sites:
        if site not in SITES:
            print(f"  {site:12s} SKIP (not in SITES table)")
            continue
        lat, lon = SITES[site]
        out_path = args.output_dir / f"{site}_pvgis_poa45_raw.csv"
        try:
            fetch_one(site, lat, lon, out_path)
        except requests.HTTPError as e:
            print(f"FAIL: HTTP {e.response.status_code}")
            print(f"    URL: {e.response.url}")
            print(f"    Body: {e.response.text[:300]}")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
