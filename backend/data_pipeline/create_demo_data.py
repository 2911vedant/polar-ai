"""
POLAR-AI Demo Data Generator
Creates deterministic synthetic Antarctic datasets for demo/testing.
All data clearly labeled as SIMULATION DATA.
"""
import os
import json
import math
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

SEED = 42
RNG = np.random.default_rng(SEED)

BASE_DIR = Path(__file__).parent.parent
DEMO_DIR = BASE_DIR / "data" / "demo"


def generate_sea_ice_data(output_dir: Path):
    """Generate sea-ice concentration grid data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    lat_steps, lon_steps = 30, 36
    lats = np.linspace(-80, -55, lat_steps)
    lons = np.linspace(-180, 180, lon_steps)

    records = []
    now = datetime.now(timezone.utc)

    for day_offset in range(365):
        ts = now - timedelta(days=day_offset)
        doy = ts.timetuple().tm_yday
        for lat in lats:
            for lon in lons:
                lat_factor = (abs(lat) - 55) / 25
                lat_factor = float(np.clip(lat_factor, 0, 1))
                seasonal = 0.5 + 0.5 * math.cos(2 * math.pi * (doy - 210) / 365)
                lon_factor = 0.1 * math.sin(math.radians(lon) + 0.5)
                noise_seed = int(abs(lat * 100 + lon * 100 + day_offset)) % 99991
                noise = np.random.default_rng(noise_seed).normal(0, 0.05)
                sic = float(np.clip(lat_factor * (0.6 + 0.3 * seasonal) + lon_factor + noise, 0, 1))
                records.append({
                    "date": ts.strftime("%Y-%m-%d"),
                    "lat": round(float(lat), 2),
                    "lon": round(float(lon), 2),
                    "sic": round(sic, 4),
                })

    # Save as JSONL (one record per line for efficiency)
    out_path = output_dir / "sea_ice_daily.jsonl"
    with open(out_path, "w") as f:
        for rec in records[:5000]:  # limit for demo
            f.write(json.dumps(rec) + "\n")
    print(f"  ✓ Sea ice data: {out_path} ({len(records[:5000])} records)")

    # Monthly summary CSV
    import csv
    monthly_path = output_dir / "sea_ice_monthly.csv"
    with open(monthly_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "month", "coverage_pct", "extent_km2"])
        writer.writeheader()
        for m in range(1, 13):
            doy = (m - 1) * 30 + 15
            seasonal = 0.5 + 0.5 * math.cos(2 * math.pi * (doy - 210) / 365)
            coverage = 45 + 20 * seasonal + RNG.normal(0, 1.5)
            writer.writerow({
                "year": 2024,
                "month": m,
                "coverage_pct": round(float(np.clip(coverage, 25, 70)), 2),
                "extent_km2": round(float(np.clip(coverage / 100 * 20_000_000, 5_000_000, 14_000_000)), 0),
            })
    print(f"  ✓ Sea ice monthly summary: {monthly_path}")


def generate_iceberg_data(output_dir: Path):
    """Generate iceberg position and trajectory data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    import csv

    icebergs = [
        {"name": "A-76A", "lat": -67.2, "lon": -51.8, "length_km": 135, "width_km": 26},
        {"name": "A-76B", "lat": -68.9, "lon": -53.2, "length_km": 89, "width_km": 18},
        {"name": "A-83",  "lat": -74.5, "lon": -60.1, "length_km": 105, "width_km": 31},
        {"name": "B-22A", "lat": -72.1, "lon": -102.3, "length_km": 58, "width_km": 14},
        {"name": "C-38",  "lat": -64.8, "lon": 148.7, "length_km": 31, "width_km": 9},
        {"name": "D-15A", "lat": -66.1, "lon": 95.4, "length_km": 77, "width_km": 22},
    ]

    positions_path = output_dir / "iceberg_positions.csv"
    now = datetime.now(timezone.utc)

    with open(positions_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "date", "lat", "lon", "length_km", "width_km", "area_km2", "source"
        ])
        writer.writeheader()
        for i, ib in enumerate(icebergs):
            for day_back in range(0, 365, 7):  # weekly positions
                ts = now - timedelta(days=day_back)
                # Simple drift model
                seed = int(abs(ib["lat"] * 100 + ib["lon"] * 100 + day_back + i)) % 99991
                rng = np.random.default_rng(seed)
                lat_drift = -day_back * 0.005 + rng.normal(0, 0.02)
                lon_drift = day_back * 0.020 + rng.normal(0, 0.05)
                lat = round(float(np.clip(ib["lat"] + lat_drift, -80, -55)), 4)
                lon = round(float(ib["lon"] + lon_drift), 4)
                if lon > 180: lon -= 360
                area = ib["length_km"] * ib["width_km"] * 0.85
                writer.writerow({
                    "name": ib["name"],
                    "date": ts.strftime("%Y-%m-%d"),
                    "lat": lat,
                    "lon": lon,
                    "length_km": ib["length_km"],
                    "width_km": ib["width_km"],
                    "area_km2": round(area, 1),
                    "source": "demo_simulation",
                })

    print(f"  ✓ Iceberg positions: {positions_path}")


def generate_weather_data(output_dir: Path):
    """Generate weather observations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    import csv

    now = datetime.now(timezone.utc)
    lats = np.linspace(-78, -60, 8)
    lons = np.linspace(-180, 180, 12)

    weather_path = output_dir / "weather_obs.csv"
    with open(weather_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "lat", "lon", "wind_speed_ms", "wind_dir_deg",
            "temp_celsius", "pressure_hpa", "source"
        ])
        writer.writeheader()
        for day_back in range(0, 30):
            ts = now - timedelta(days=day_back)
            for lat in lats:
                for lon in lons:
                    seed = int(abs(lat * 100 + lon * 100 + day_back)) % 99991
                    rng = np.random.default_rng(seed)
                    lat_factor = (abs(lat) - 55) / 25
                    writer.writerow({
                        "date": ts.strftime("%Y-%m-%d"),
                        "lat": round(float(lat), 2),
                        "lon": round(float(lon), 2),
                        "wind_speed_ms": round(float(rng.uniform(5, 18)), 2),
                        "wind_dir_deg": round(float(rng.uniform(0, 360)), 1),
                        "temp_celsius": round(float(-5 - 20 * lat_factor + rng.normal(0, 3)), 1),
                        "pressure_hpa": round(float(rng.uniform(960, 1010)), 1),
                        "source": "demo_simulation",
                    })
    print(f"  ✓ Weather data: {weather_path}")


def generate_ocean_data(output_dir: Path):
    """Generate ocean current observations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    import csv

    now = datetime.now(timezone.utc)
    lats = np.linspace(-78, -60, 8)
    lons = np.linspace(-180, 180, 12)

    ocean_path = output_dir / "ocean_obs.csv"
    with open(ocean_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "lat", "lon", "current_u_ms", "current_v_ms",
            "sst_celsius", "salinity_psu", "wave_height_m", "source"
        ])
        writer.writeheader()
        for day_back in range(0, 30):
            ts = now - timedelta(days=day_back)
            for lat in lats:
                for lon in lons:
                    seed = int(abs(lat * 200 + lon * 200 + day_back)) % 99991
                    rng = np.random.default_rng(seed)
                    lat_factor = (abs(lat) - 55) / 25
                    sst = float(8 - 10 * lat_factor + rng.normal(0, 1))
                    writer.writerow({
                        "date": ts.strftime("%Y-%m-%d"),
                        "lat": round(float(lat), 2),
                        "lon": round(float(lon), 2),
                        "current_u_ms": round(float(rng.uniform(0.05, 0.45)), 4),
                        "current_v_ms": round(float(rng.normal(0, 0.15)), 4),
                        "sst_celsius": round(sst, 1),
                        "salinity_psu": round(float(rng.uniform(33.5, 34.8)), 2),
                        "wave_height_m": round(float(rng.uniform(1.5, 5.0)), 2),
                        "source": "demo_simulation",
                    })
    print(f"  ✓ Ocean data: {ocean_path}")


def generate_ml_features(output_dir: Path):
    """Generate ML training features from synthetic data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    import csv

    features_path = output_dir / "ml_features.csv"
    now = datetime.now(timezone.utc)
    lat_steps, lon_steps = 15, 18
    lats = np.linspace(-80, -60, lat_steps)
    lons = np.linspace(-180, 180, lon_steps)

    with open(features_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "lat", "lon",
            "sic_t", "sic_t1", "sic_t2", "sic_t7",
            "wind_speed", "wind_dir", "temp",
            "current_u", "current_v", "sst",
            "lat_factor", "seasonal",
            "target_24h", "target_48h", "target_72h",
        ])
        writer.writeheader()
        for day_back in range(30, 0, -1):
            ts = now - timedelta(days=day_back)
            doy = ts.timetuple().tm_yday
            seasonal = 0.5 + 0.5 * math.cos(2 * math.pi * (doy - 210) / 365)
            for lat in lats:
                for lon in lons:
                    lat_factor = float(np.clip((abs(lat) - 55) / 25, 0, 1))
                    lon_factor = 0.1 * math.sin(math.radians(lon) + 0.5)

                    def sic_at(d_offset):
                        s = 0.5 + 0.5 * math.cos(2 * math.pi * ((doy + d_offset) - 210) / 365)
                        n_s = int(abs(lat * 100 + lon * 100 + d_offset)) % 99991
                        n = np.random.default_rng(n_s).normal(0, 0.04)
                        return float(np.clip(lat_factor * (0.6 + 0.3 * s) + lon_factor + n, 0, 1))

                    seed = int(abs(lat * 100 + lon * 100 + day_back * 10)) % 99991
                    rng = np.random.default_rng(seed)
                    writer.writerow({
                        "date": ts.strftime("%Y-%m-%d"),
                        "lat": round(float(lat), 2),
                        "lon": round(float(lon), 2),
                        "sic_t":  round(sic_at(0), 4),
                        "sic_t1": round(sic_at(-1), 4),
                        "sic_t2": round(sic_at(-2), 4),
                        "sic_t7": round(sic_at(-7), 4),
                        "wind_speed": round(float(rng.uniform(5, 18)), 2),
                        "wind_dir": round(float(rng.uniform(0, 360)), 1),
                        "temp": round(float(-5 - 20 * lat_factor + rng.normal(0, 3)), 1),
                        "current_u": round(float(rng.uniform(0.05, 0.45)), 4),
                        "current_v": round(float(rng.normal(0, 0.15)), 4),
                        "sst": round(float(8 - 10 * lat_factor + rng.normal(0, 1)), 1),
                        "lat_factor": round(lat_factor, 4),
                        "seasonal": round(float(seasonal), 4),
                        "target_24h": round(sic_at(1), 4),
                        "target_48h": round(sic_at(2), 4),
                        "target_72h": round(sic_at(3), 4),
                    })

    print(f"  ✓ ML features: {features_path}")


def create_demo_data(output_dir: Path = None):
    """Generate all demo datasets."""
    if output_dir is None:
        output_dir = DEMO_DIR

    print("\n🧊 POLAR-AI Demo Data Generator")
    print(f"   Seed: {SEED}")
    print(f"   Output: {output_dir}")
    print(f"   Status: SIMULATION DATA (not real satellite data)\n")

    generate_sea_ice_data(output_dir)
    generate_iceberg_data(output_dir)
    generate_weather_data(output_dir)
    generate_ocean_data(output_dir)
    generate_ml_features(output_dir)

    # Write metadata
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "status": "DEMO_SIMULATION_DATA",
        "disclaimer": "This data is synthetically generated for demonstration purposes only.",
        "files": [
            "sea_ice_daily.jsonl",
            "sea_ice_monthly.csv",
            "iceberg_positions.csv",
            "weather_obs.csv",
            "ocean_obs.csv",
            "ml_features.csv",
        ]
    }
    with open(output_dir / "DEMO_METADATA.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✅ Demo data generation complete!")
    print(f"   All data is SIMULATION DATA. See DATA_SOURCES.md for real data sources.")


if __name__ == "__main__":
    create_demo_data()
