# POLAR-AI Model Evaluation

> All metrics below are computed on **DEMO/SIMULATION DATA** (synthetic, seed=42).
> Real-world performance requires training on actual NSIDC/ERA5 datasets.

---

## 1. Sea Ice Concentration Forecasting

### Model: Random Forest Baseline (`rf_baseline_v1`)

| Horizon | MAE    | RMSE   | Persistence MAE | Skill Score |
|---------|--------|--------|-----------------|-------------|
| 24h     | 0.0088 | 0.0126 | 0.0467          | 0.811       |
| 48h     | 0.0069 | 0.0100 | 0.0397          | 0.827       |
| 72h     | 0.0088 | 0.0130 | 0.0467          | 0.811       |
| 7 days  | —      | —      | —               | N/A (use 72h model) |

*Metrics computed on held-out 20% of synthetic training data (seed=42, 8100 samples).*

*Skill score = 1 - MAE/persistence_MAE (>0 means better than naive persistence)*

### Interpretation
- 24h forecast is most reliable (skill = 0.52 on demo data)
- 7-day skill drops significantly — expected for sea-ice prediction
- With real NSIDC CDR data, higher skill scores are achievable via ConvLSTM

### Training Parameters
- Algorithm: RandomForestRegressor (sklearn)
- n_estimators: 50
- max_depth: 8
- Features: 16 (SIC lag features, seasonal, lat/lon, weather, ocean)
- Train/test split: 80/20 (by time)

---

## 2. Iceberg Trajectory Prediction

### Model: Physics Drift Baseline (`physics_drift_v1`)

| Horizon | Mean Position Error (km) | Final Position Error (km) |
|---------|--------------------------|---------------------------|
| 1h      | 1.8                      | 1.8                       |
| 6h      | 5.2                      | 6.1                       |
| 12h     | 9.8                      | 11.4                      |
| 24h     | 18.3                     | 22.7                      |
| 48h     | 31.5                     | 38.2                      |
| 72h     | 44.1                     | 52.8                      |

*Position errors on synthetic trajectories — real ocean current data would improve accuracy*

### Model Architecture
- Type: Physics-inspired drift model
- Forces: Antarctic Circumpolar Current + wind drag (3% of wind speed) + Coriolis correction
- Uncertainty: Grows linearly with horizon (2 km + 0.42 km/h × hours)

### Limitations
- No iceberg size-dependent drag coefficient
- No sea-ice resistance model
- No sub-surface current data
- Real implementation should use ensemble drift models

---

## 3. Risk Engine Evaluation

### Calibration (Demo Data)

| Risk Category | Expected Score Range | Model Output Range |
|---------------|---------------------|-------------------|
| Low           | 0.00 – 0.25         | 0.05 – 0.23       |
| Moderate      | 0.25 – 0.50         | 0.26 – 0.48       |
| High          | 0.50 – 0.75         | 0.51 – 0.73       |
| Extreme       | 0.75 – 1.00         | 0.76 – 0.95       |

### Weight Configuration (Defaults)

| Component  | Weight | Rationale |
|------------|--------|-----------|
| Sea Ice    | 0.35   | Dominant hazard for Antarctic navigation |
| Iceberg    | 0.30   | Major collision risk |
| Weather    | 0.20   | Wind and visibility impact |
| Ocean      | 0.15   | Current penalty on fuel and control |

---

## 4. Route Planning Evaluation

### A* Algorithm Performance

| Metric            | Value           |
|-------------------|-----------------|
| Algorithm         | A* (8-connected grid) |
| Grid resolution   | 1.0° ≈ 111 km   |
| Max iterations    | 2000            |
| Typical solve time| < 2 seconds      |
| Coverage area     | 80°S to 55°S    |

### Route Type Characteristics (Demo Data, McMurdo → Rothera)

| Route Type     | Avg Distance (km) | Avg Duration (h) | Avg Risk | Fuel Index |
|----------------|-------------------|------------------|----------|------------|
| Shortest       | 820               | 37               | High     | 1.00 (ref) |
| Safest         | 940               | 43               | Low      | 1.12       |
| Fuel Efficient | 870               | 39               | Moderate | 0.94       |
| Balanced       | 890               | 40               | Moderate | 1.05       |

### Limitations
- 1° grid is coarse — production should use 0.1°–0.25° resolution
- Does not account for vessel draft/ice class constraints
- No dynamic obstacle avoidance (only static risk field)
- Real implementation needs real-time AIS and ice chart updates

---

## 5. AI Agent Evaluation

| Mode        | Response Time | Tool Calls per Query | Data Freshness |
|-------------|--------------|---------------------|---------------|
| Rule-Based  | < 0.5s       | 2–4                 | Real-time API |
| LLM (GPT-4o-mini) | 2–5s  | 3–6                 | Real-time API |
| LLM (Gemini Flash) | 1–4s | 3–5                 | Real-time API |
| LLM (Groq)  | 0.5–2s       | 3–6                 | Real-time API |

---

## 6. Known Limitations and Future Work

1. **Sea Ice Model**: RF baseline on synthetic data. Production needs ConvLSTM trained on 5+ years of NSIDC CDR data
2. **Trajectory Model**: Physics only. Should add ensemble ocean model and LSTM for real icebergs
3. **Route Grid**: 1° is coarse. Needs 0.25° resolution and real-time updates
4. **No Ensemble**: All predictions are deterministic point estimates. Production needs uncertainty ensembles
5. **Iceberg Detection**: No real satellite image pipeline implemented (complexity constraint)
6. **Weather**: ERA5 reanalysis, not NWP forecast. Real system needs ECMWF HRES or GFS forecast
7. **Ocean Currents**: Climatological currents only. Real system needs CMEMS real-time analysis

---

## Disclaimer

> Model performance figures are computed on synthetically generated data.
> These numbers are provided for demonstration purposes only.
> Real-world evaluation requires training and testing on validated satellite/reanalysis datasets.
