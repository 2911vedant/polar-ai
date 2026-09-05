"""
Download ERA5 weather reanalysis data via Copernicus CDS API.
Requires free CDS account and API key in ~/.cdsapirc

Limitation: Requires CDS_API_KEY. Falls back to demo data when unavailable.
"""
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "weather"


def download_era5_weather(
    year: int = 2024,
    months: list = None,
    output_dir: Path = OUTPUT_DIR
):
    """
    Download ERA5 monthly reanalysis for Antarctic region.
    
    Requires:
      pip install cdsapi
      ~/.cdsapirc with API key from https://cds.climate.copernicus.eu/
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if months is None:
        months = [1, 2, 3]  # demo: first 3 months

    try:
        import cdsapi
    except ImportError:
        print("  ✗ cdsapi not installed. Install with: pip install cdsapi")
        print("  Falling back to demo weather data.")
        return None

    try:
        c = cdsapi.Client()
        out_path = output_dir / f"era5_antarctic_{year}.nc"

        if out_path.exists():
            print(f"  Already downloaded: {out_path}")
            return str(out_path)

        print(f"  Downloading ERA5 for {year} months {months}...")
        c.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": "monthly_averaged_reanalysis",
                "variable": [
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                    "2m_temperature",
                    "mean_sea_level_pressure",
                    "total_precipitation",
                ],
                "year": str(year),
                "month": [f"{m:02d}" for m in months],
                "time": "00:00",
                "area": [-55, -180, -80, 180],  # Antarctic region
                "format": "netcdf",
            },
            str(out_path),
        )
        print(f"  ✓ Saved: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"  ✗ ERA5 download failed: {e}")
        print("    Ensure ~/.cdsapirc is configured with CDS API key.")
        print("    Falling back to demo weather data.")
        return None


if __name__ == "__main__":
    download_era5_weather()
