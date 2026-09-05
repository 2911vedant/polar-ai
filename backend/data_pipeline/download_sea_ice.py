"""
Download NSIDC Sea Ice Index (G02135 v3) — free, no login required.
Downloads monthly sea ice extent CSV for Antarctic (South).
"""
import os
import requests
from pathlib import Path

BASE_URL = "https://noaadata.apps.nsidc.org/NOAA/G02135/south/monthly/data/"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "sea_ice"


def download_sea_ice_index(output_dir: Path = OUTPUT_DIR):
    """Download NSIDC Sea Ice Index monthly extent CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Monthly sea ice area and extent data for the south (Antarctic)
    filename = "S_seaice_extent_monthly_v3.0.csv"
    url = BASE_URL + filename
    out_path = output_dir / filename

    if out_path.exists():
        print(f"  Already downloaded: {out_path}")
        return str(out_path)

    print(f"  Downloading {url}...")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"  ✓ Saved: {out_path} ({len(resp.content):,} bytes)")
        return str(out_path)
    except requests.RequestException as e:
        print(f"  ✗ Download failed: {e}")
        print("    Falling back to demo data.")
        return None


if __name__ == "__main__":
    download_sea_ice_index()
