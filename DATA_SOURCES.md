# POLAR-AI Data Sources Documentation

> **Note:** POLAR-AI is a research decision-support prototype. All data marked as DEMO/SIMULATION has been synthetically generated using deterministic algorithms with fixed random seeds. The architecture is designed to accept real datasets when credentials/access are available.

---

## Dataset Summary Table

| Dataset | Purpose | Provider | URL | Variables | Resolution | Format | License | Access | Status |
|---------|---------|----------|-----|-----------|------------|--------|---------|--------|--------|
| NSIDC Sea Ice Index (G02135 v3) | Sea-ice concentration, extent maps | NSIDC/NOAA | https://noaadata.apps.nsidc.org/NOAA/G02135/ | SIC, extent, area | 25 km grid, daily/monthly | GeoTIFF, CSV | Public Domain (US Gov) | Open HTTP | **REAL (download script provided)** |
| NOAA/NSIDC CDR Passive Microwave SIC (G02202 v6) | Historical sea-ice concentration CDR | NSIDC/NOAA | https://nsidc.org/data/g02202/versions/6 | SIC, quality flags | 25 km, daily 1978–present | NetCDF-4 | Public Domain | Earthdata Login required | **REAL (Earthdata account needed)** |
| NIC Antarctic Iceberg Tracking | Iceberg positions, sizes | US National Ice Center | https://usicecenter.gov/Products/AntarcIcebergs | lat, lon, iceberg_id, length, width | Weekly | CSV, Shapefile | Public Domain (US Gov) | Open HTTP | **REAL (download script provided)** |
| BYU/NIC Iceberg Database | Historical iceberg trajectories 1992–present | BYU Microwave Earth Remote Sensing Lab | https://www.scp.byu.edu/data/iceberg/ | lat, lon, date, iceberg_id, backscatter | Daily | ASCII | Public Domain | Open HTTP | **REAL (partial; older records)** |
| ERA5 Reanalysis (Copernicus CDS) | Wind, temperature, pressure, humidity | ECMWF / Copernicus | https://cds.climate.copernicus.eu/ | u10, v10, t2m, msl, tp | 0.25°, hourly 1940–present | NetCDF-4 | Copernicus License (free) | CDS API key required | **REAL (CDS registration needed)** |
| Copernicus Marine Global Physics (GLOBAL_ANALYSISFORECAST_PHY_001_024) | Ocean currents, SST | Copernicus Marine Service | https://data.marine.copernicus.eu/ | uo, vo, thetao (SST), so | 0.083°, daily | NetCDF-4 | Copernicus Marine License (free) | CMEMS account required | **REAL (CMEMS registration needed)** |
| NSIDC Sea Ice Index Monthly CSV | Monthly sea-ice extent/area timeseries | NSIDC/NOAA | https://noaadata.apps.nsidc.org/NOAA/G02135/south/monthly/ | extent, area | Monthly | CSV | Public Domain | Open HTTP | **REAL (no login needed)** |
| Synthetic Antarctic Data | Demo/fallback for all variables | POLAR-AI (generated) | local: data/demo/ | SIC, iceberg pos, trajectories, weather, ocean, vessel | Configurable | JSON, CSV, NumPy | MIT (this project) | Local | **DEMO DATA** |

---

## Dataset Details

### 1. NSIDC Sea Ice Index — G02135 Version 3

**Provider:** NSIDC / NOAA  
**URL:** https://noaadata.apps.nsidc.org/NOAA/G02135/  
**Why selected:** The Sea Ice Index is the primary public source for Antarctic sea-ice extent and concentration images derived from passive microwave satellite data. It is freely downloadable without login for GeoTIFF and CSV formats.  
**Variables:** Sea ice concentration (%), sea ice extent (km²), sea ice area (km²)  
**Temporal resolution:** Daily images and monthly time-series CSVs  
**Spatial resolution:** 25 × 25 km (NSIDC polar stereographic projection, EPSG:3412 for Southern Hemisphere)  
**Coordinate system:** NSIDC Polar Stereographic South, EPSG:3412  
**Format:** GeoTIFF (concentration images), PNG (extent images), CSV (monthly extent/area time-series)  
**License:** Public Domain (US Government)  
**Access:** Open HTTP — no login required for GeoTIFF/CSV files  
**Approximate download size:** ~5 MB/month for GeoTIFFs; monthly CSV <1 MB  
**Limitations:** GeoTIFFs are concentration images (scaled 0–250 where 250=100%); no per-pixel NetCDF for free access without Earthdata  
**Preprocessing required:** Rescale pixel values (0–250 → 0–100%), reproject to WGS84 for web mapping, extract Antarctic region (lat < –50°)

---

### 2. NOAA/NSIDC CDR Passive Microwave SIC — G02202 Version 6

**Provider:** NSIDC / NOAA  
**URL:** https://nsidc.org/data/g02202/versions/6  
**Why selected:** The Climate Data Record (CDR) provides the most scientifically rigorous daily sea-ice concentration at 25 km resolution. Contains quality flags and uncertainty estimates.  
**Variables:** `cdr_seaice_conc`, `nsidc_bt_seaice_conc`, quality flags  
**Temporal resolution:** Daily, 1978–present  
**Spatial resolution:** 25 km polar stereographic  
**Format:** NetCDF-4  
**License:** Public Domain  
**Access:** Requires NASA Earthdata login (free registration). Download via `earthaccess` Python library.  
**Limitations:** Requires Earthdata credentials. Large files (~100 MB/year). For demo mode, synthetic data is used instead.  
**Status in this project:** Earthdata adapter code is provided; falls back to demo data if credentials absent.

---

### 3. NIC Antarctic Iceberg Tracking Database

**Provider:** US National Ice Center (USICECENTER)  
**URL:** https://usicecenter.gov/Products/AntarcIcebergs  
**Why selected:** Official US Government tracking of named Antarctic tabular icebergs. Publicly accessible CSV/Shapefile with position, dimensions, and dates.  
**Variables:** Iceberg name, latitude, longitude, length (nm), width (nm), date  
**Temporal resolution:** Weekly updates  
**Format:** CSV, PDF, Shapefile  
**License:** Public Domain (US Government)  
**Access:** Direct HTTP download — no login required  
**Limitations:** Only large named icebergs (>18.5 km²). Does not include small icebergs or density information.  
**Preprocessing required:** Parse CSV, validate coordinates, create trajectory sequences from sequential position records.

---

### 4. BYU/NIC Combined Iceberg Database

**Provider:** Brigham Young University (BYU) Microwave Earth Remote Sensing  
**URL:** https://www.scp.byu.edu/data/iceberg/  
**Why selected:** Provides historical daily positions from scatterometer satellite data for known icebergs from 1992 onwards, enabling trajectory construction.  
**Variables:** Iceberg ID, date, latitude, longitude, satellite backscatter  
**Temporal resolution:** Daily (where satellite passes available)  
**Format:** ASCII text tables  
**License:** Public Domain (academic research use)  
**Access:** Open HTTP  
**Limitations:** Older records may have gaps. Data quality varies by satellite era. Coverage up to ~2022.

---

### 5. ERA5 Atmospheric Reanalysis

**Provider:** ECMWF / Copernicus Climate Change Service  
**URL:** https://cds.climate.copernicus.eu/  
**API:** `cdsapi` Python library  
**Why selected:** Gold-standard global atmospheric reanalysis. Contains all required meteorological variables at 0.25° resolution from 1940 to near-present. Free for all uses after free registration.  
**Variables:** `u10` (10m u-wind), `v10` (10m v-wind), `t2m` (2m temperature), `msl` (mean sea level pressure), `tp` (total precipitation), `sp` (surface pressure)  
**Temporal resolution:** Hourly (ERA5); monthly means available  
**Spatial resolution:** 0.25° (~28 km globally)  
**Format:** NetCDF-4 (via CDS API), GRIB2 (native)  
**License:** Copernicus License — free for all uses including commercial  
**Access:** Requires free CDS account + API key set in `~/.cdsapirc`  
**Limitations:** Requires CDS registration. API requests can be queued (delays possible). Large datasets (multi-GB for years). POLAR-AI downloads only the Antarctic region (lat < –50°) and a limited time window.  
**Preprocessing required:** Subset to Antarctic domain, extract variables, convert GRIB/NetCDF to pandas/numpy arrays, interpolate to routing grid.

---

### 6. Copernicus Marine Global Physics Analysis & Forecast

**Provider:** Copernicus Marine Service (CMEMS)  
**URL:** https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/  
**Why selected:** Provides global ocean current vectors and sea-surface temperature at ~9 km resolution with near-real-time and forecast capability.  
**Variables:** `uo` (eastward ocean velocity), `vo` (northward ocean velocity), `thetao` (SST), `so` (salinity)  
**Temporal resolution:** Daily analysis + 10-day forecast  
**Spatial resolution:** 0.083° (~9 km)  
**Format:** NetCDF-4  
**License:** Copernicus Marine License — free with account  
**Access:** Requires free CMEMS registration + `copernicusmarine` Python toolbox  
**Limitations:** Free account required. Large download volumes for global product; POLAR-AI subsets to Antarctic domain.  
**Preprocessing required:** Subset to lat < –50°, extract u/v velocity components, compute speed and direction, interpolate to routing grid.

---

### 7. Synthetic / Demo Data (POLAR-AI Internal)

**Provider:** POLAR-AI project  
**Status:** DEMO / SIMULATION DATA  
**Why included:** Guarantees the application is fully functional without any external credentials or network access. Uses deterministic random seeds for reproducibility.  
**Generated variables:**  
- Sea-ice concentration grid (polar stereographic, 100 × 100 cells, Antarctica domain)
- Iceberg positions with dimensions and trajectories (physics-based drift simulation)
- Weather fields (wind speed/direction, temperature, pressure)
- Ocean current fields (speed, direction, SST)
- Synthetic vessel track for route testing
**Deterministic seed:** `POLAR_AI_SEED = 42`  
**Label:** All demo data is clearly marked `DATA_MODE=demo` in API responses and UI.

---

## Data Mode Configuration

Set `DATA_MODE` in `.env`:

```
DATA_MODE=demo        # Use fully synthetic data (default, no credentials needed)
DATA_MODE=real        # Use real datasets where available (requires credentials)
DATA_MODE=hybrid      # Use real data where available, fall back to demo for missing
```

---

## Credential Requirements for Real Data

| Dataset | Required Credential | Registration URL |
|---------|--------------------|--------------------|
| NSIDC CDR (G02202) | NASA Earthdata login | https://urs.earthdata.nasa.gov/ |
| ERA5 | CDS API key | https://cds.climate.copernicus.eu/ |
| Copernicus Marine | CMEMS account | https://marine.copernicus.eu/ |
| NSIDC Sea Ice Index (G02135) | None required | — |
| NIC Icebergs | None required | — |
| BYU Icebergs | None required | — |

---

## Disclaimer

> POLAR-AI uses publicly available scientific datasets for research and demonstration purposes. All data downloads respect provider terms of service. No data requiring redistribution rights is bundled in this repository. Users must obtain their own credentials for datasets that require registration.
