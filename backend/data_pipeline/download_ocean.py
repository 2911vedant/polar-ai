"""
Download Copernicus Marine ocean data.
Requires free CMEMS account credentials.

Limitation: Requires CMEMS_USERNAME and CMEMS_PASSWORD environment variables.
Falls back to demo data when unavailable.
"""
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "ocean"


def download_cmems_ocean(output_dir: Path = OUTPUT_DIR):
    """
    Download global ocean physics analysis for Antarctic region.
    
    Requires:
      pip install copernicusmarine
      CMEMS account: https://marine.copernicus.eu/
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    username = os.getenv("CMEMS_USERNAME")
    password = os.getenv("CMEMS_PASSWORD")

    if not username or not password:
        print("  ✗ CMEMS credentials not set.")
        print("    Set CMEMS_USERNAME and CMEMS_PASSWORD in .env")
        print("    Register at: https://marine.copernicus.eu/")
        print("    Falling back to demo ocean data.")
        return None

    try:
        import copernicusmarine
    except ImportError:
        print("  ✗ copernicusmarine not installed. Install with: pip install copernicusmarine")
        return None

    try:
        out_path = output_dir / "cmems_antarctic_ocean.nc"
        if out_path.exists():
            print(f"  Already downloaded: {out_path}")
            return str(out_path)

        print("  Downloading CMEMS ocean physics data...")
        copernicusmarine.subset(
            dataset_id="GLOBAL_ANALYSISFORECAST_PHY_001_024",
            variables=["uo", "vo", "thetao", "so"],
            minimum_latitude=-80,
            maximum_latitude=-55,
            minimum_longitude=-180,
            maximum_longitude=180,
            minimum_depth=0,
            maximum_depth=1,
            output_filename=str(out_path),
            username=username,
            password=password,
        )
        print(f"  ✓ Saved: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"  ✗ CMEMS download failed: {e}")
        print("    Falling back to demo ocean data.")
        return None


if __name__ == "__main__":
    download_cmems_ocean()
