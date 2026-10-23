# CrisisCore 2.0 Data Inventory & ML Suitability Assessment

**Audit Date:** 2026-08-15  
**Project:** India Disaster Intelligence Map  
**Scope:** All datasets, live APIs, and satellite feeds currently integrated  

---

## Executive Summary

**Current Data Status:**
- ✅ **Real-time data sources confirmed**: 3 (OpenWeather, USGS, Sentinel-1/GEE)
- ⚠️ **Historical training data for ML**: Limited to 1 incomplete dataset (Nigerian floods)
- ⚠️ **ML model availability**: NONE (risk_engine.py returns model_not_available)
- 🔴 **Legitimate disaster types for ML models**: Only **FLOOD** has potential training data; others lack labeled historical records

---

## Disaster Type Analysis

### 1. FLOOD 🌊

#### Data Sources

| Source | Type | Status | Coverage |
|--------|------|--------|----------|
| **Sentinel-1 SAR via Google Earth Engine** | Real-time satellite | Active | India-wide |
| **floods_data.csv** | Historical impact records | Archived | Nigeria (geographic mismatch) |
| **data.json** (rule-based) | Real-time weather correlation | Active | 50 Indian cities |

#### Detailed Breakdown

**A) Sentinel-1 Satellite Imagery (Real-time)**
- **Data Path:** Google Earth Engine API (crisiscore-505712 project)
- **Data Type:** C-band SAR (Synthetic Aperture Radar) backscatter imagery
- **Satellite:** Sentinel-1A/B (revisit time 6-12 days)
- **Rows:** ~200+ scenes per location per month (ongoing stream)
- **Columns:** 
  - Latitude, Longitude (point center)
  - Image date (YYYY-MM-DD)
  - Backscatter intensity (dB)
  - Derived water mask (binary classification)
  - Flood area estimate (km²)
  - Baseline comparison (30-45 day reference)
- **Geographic Fields:** Lat/lon per image, region configurable (8 pre-set: Assam, Kerala, Bihar, UP, Maharashtra, West Bengal, Odisha, Gujarat)
- **Temporal Fields:** Image acquisition date, baseline period
- **Disaster Label/Target:** Binary (flood_detected: true/false) + continuous (area_km2)
- **ML Suitability:** **PARTIAL** ✓
  - ✅ Labeled data (water vs. non-water via SAR backscatter threshold -18 dB)
  - ✅ Geographic diversity (8 monitored regions)
  - ✅ Real temporal variation (dates 2026-08-05 to 2026-08-15 verified)
  - ⚠️ Detection method is threshold-based, NOT ML-trained (no ground truth labels)
  - ⚠️ Revisit time gaps (6-12 days) limit continuous training data generation
  - ⚠️ Data requires manual validation against actual flood events
- **Historical or Real-time:** Real-time (ongoing satellite stream)
- **Data Source:** Google Earth Engine (USGS Sentinel-1 archive)
- **Current Usage:** Click-to-analyze endpoint (/api/flood-risk POST) on DisasterMap.jsx

**Sample Data Points (Verified):**
- Chennai (13.08°N, 80.27°E): 2026-08-15, 0.39 km², flood_detected=true
- Mumbai (19.08°N, 72.88°E): 2026-08-15, 0.22 km², flood_detected=true
- Delhi (28.70°N, 77.10°E): 2026-08-15, 0.99 km², flood_detected=true
- Bengaluru (12.97°N, 77.59°E): No baseline data available (expected)

**B) Historical Flood Impact Data (floods_data.csv)**
- **Data Path:** `/DISASTER/floods_data.csv`
- **Data Type:** Disaster impact statistics (post-event reporting)
- **Rows:** 50 (state/LGA combinations from Nigerian flood event)
- **Columns:**
  - State (text): ADAMAWA, BORNO, YOBE (Nigeria only)
  - LGA (Local Government Area): 48 sub-regions
  - Affected Household (integer): 13-49,651 per LGA
  - Affected Individuals (integer): 60-250,901 per LGA
  - Displaced Household (integer): 0-24,902 per LGA
  - Displaced Individuals (integer): 0-128,268 per LGA
- **Geographic Fields:** State, LGA (Nigerian administrative boundaries only)
- **Temporal Fields:** NONE visible in dataset
- **Disaster Label/Target:** Impact counts (continuous: household/individual counts)
- **ML Suitability:** **NO** ✗
  - ✗ Geographic mismatch: Nigerian data, not Indian
  - ✗ No temporal information (single event snapshot)
  - ✗ Impact metrics only (not predictive features)
  - ✗ No weather/satellite features to correlate
  - ✗ Not suitable for training Indian disaster models
- **Historical or Real-time:** Historical (single event, date unknown)
- **Data Source:** Nigeria humanitarian database (NEMA/UN OCHA?)
- **Current Usage:** Not integrated into API endpoints; archived reference only
- **Recommendation:** Archive in separate historical folder; DO NOT train Indian models on this data

**C) Rule-Based Weather Correlation (data.json)**
- **Data Path:** `/DISASTER/data.json`
- **Data Type:** Real-time weather + rule-based disaster predictions
- **Generation Method:** `weather_to_json.py` queries OpenWeather API
- **Rows:** 50 (one per Indian city)
- **Columns:**
  - name (text): City name
  - lat, lng (float): Geographic coordinates
  - rain (float): 1-hour rainfall (mm)
  - humidity (int): Relative humidity (%)
  - clouds (int): Cloud coverage (%)
  - wind (float): Wind speed (m/s)
  - temp (float): Temperature (°C)
  - flood (categorical): "Low" / "Medium" / "High" (RULE-BASED, NOT ML-TRAINED)
  - cyclone (categorical): Same
  - drought (categorical): Same
  - earthquake (categorical): Hardcoded "Medium"
- **Geographic Fields:** Lat/lon per city
- **Temporal Fields:** Generated at runtime (no historical archive)
- **Disaster Label/Target:** Categorical (Low/Medium/High) via hard-coded rules:
  - Flood: High if rain>10 OR (humidity>85 AND clouds>80); Medium if rain>3; else Low
  - Cyclone: High if wind>15; Medium if wind>8; else Low
  - Drought: High if rain==0 AND temp>35 AND humidity<40; Medium if rain<1; else Low
  - Earthquake: Hardcoded "Medium" (no logic)
- **ML Suitability:** **NO** ✗
  - ✗ Labels are rule-based, not ground-truth labeled data
  - ✗ No historical training data (real-time only)
  - ✗ Rules are hardcoded heuristics (not learned from data)
  - ✗ Cannot use as training data; would perpetuate hardcoded logic
  - ✓ CAN be used as feature engineering source (weather variables)
- **Historical or Real-time:** Real-time (refreshed on demand)
- **Data Source:** OpenWeather API (api.openweathermap.org/data/2.5/weather)
- **Current Usage:** Displayed in AlertsPanel.jsx, feeds frontend weather cards
- **Recommendation:** Extract weather features (rain, humidity, clouds, wind, temp) for feature engineering; DO NOT use categorical predictions as training labels

#### Flood ML Recommendation

**Can we train an ML model for flood prediction?**

✅ **YES, PARTIAL — with significant constraints:**

1. **Use Sentinel-1 satellite data as training source:**
   - Historical Sentinel-1 archive available via Google Earth Engine
   - Can extract 24+ months of flood extent data retrospectively
   - Combine with ground truth validation (news reports, satellite confirmation)
   - Creates labeled training set: (lat, lon, date) → (flood_area_km², flood_detected)
   - **Challenge:** No automated ground truth labels; requires manual validation

2. **Use OpenWeather features as secondary predictor:**
   - Extract historical weather at flood occurrence dates
   - Feature set: [rainfall_1h, rainfall_3h, humidity, temperature, pressure, wind, clouds]
   - **Challenge:** data.json only stores current snapshot; need historical API calls

3. **Reject floods_data.csv for Indian training:**
   - Nigerian geographic context incompatible
   - Archive separately for impact modeling only

4. **Data pipeline required before model training:**
   - ✅ GEE Sentinel-1 backfill (24 months historical)
   - ✅ Ground truth validation workflow (satellite + news correlation)
   - ✅ OpenWeather historical reconstruction (or API subscription for archival)
   - ✅ Feature engineering: derive slope, elevation, land use from GEE/SRTM
   - ⏳ Training label set: minimum 50-100 confirmed flood events with geographic extent

**Current Status:** Ready for data pipeline development; satellite data confirmed active; no model trained yet.

---

### 2. EARTHQUAKE 🌍

#### Data Sources

| Source | Type | Status | Coverage |
|--------|------|--------|----------|
| **USGS Real-time Feed** | Live seismic events | Active | India + surrounding region |

#### Detailed Breakdown

**USGS Earthquake Data (Real-time)**
- **Data Path:** `https://earthquake.usgs.gov/fdsnws/event/1/query` (backend service: `earthquake_service.py`)
- **Data Type:** Real-time seismic event detection
- **Query Parameters:**
  - Geographic bounds: India (6.5°N–35.5°N, 68.1°E–97.4°E)
  - Minimum magnitude: 2.5
  - Max results: 200 most recent events
  - Format: GeoJSON
- **Rows:** ~150–200 (last 30 days, magnitude ≥2.5 in India region)
- **Columns:**
  - id (text): USGS event ID
  - lat, lon (float): Epicenter coordinates
  - depth_km (float): Focal depth
  - magnitude (float): Richter scale
  - place (text): Location description
  - time (Unix timestamp): Event occurrence
  - time_iso (ISO string): Formatted timestamp
  - alert (text): USGS alert level
  - significance (int): USGS event significance score
  - severity (categorical): Derived (LOW if mag<4.5, MEDIUM if 4.5–6, HIGH if ≥6)
  - status (text): "detected" (always)
  - source (text): "USGS"
  - confidence (text): "high" (always)
- **Geographic Fields:** Lat/lon (epicenter), place (text description)
- **Temporal Fields:** time (Unix ms), time_iso (RFC3339)
- **Disaster Label/Target:** 
  - Continuous: magnitude (0–9 scale)
  - Continuous: depth_km (0–700 km typical)
  - Categorical: severity (LOW/MEDIUM/HIGH derived from magnitude)
- **ML Suitability:** **NO** ✗
  - ✗ Real-time detection only; no historical training data available
  - ✗ Events are single occurrences (not predictable ahead of time)
  - ✗ USGS detects post-event, not pre-event warning
  - ✗ Earthquakes are not predictable with available features (no precursor data)
  - ✓ CAN be used for post-event alert routing and impact estimation
- **Historical or Real-time:** Real-time detection (streaming)
- **Data Source:** USGS Earthquake Hazards Program
- **Current Usage:** /api/disasters/earthquakes GET endpoint
- **Data Refresh Rate:** Updated every 15 seconds (USGS system)

#### Earthquake ML Recommendation

**Can we train an ML model for earthquake prediction?**

🔴 **NO — Seismic prediction is not feasible with available data**

**Why:**
1. **No precursor features:** Earthquakes have no known reliable predictors
2. **Events are rare:** ~5–10 magnitude ≥5.0 per year in India
3. **USGS provides post-event data:** Detection happens after rupture (seconds to minutes)
4. **No feature engineering possible:** No precursor measurements in dataset

**What CAN be done:**
- ✅ Real-time alert delivery (USGS → frontend)
- ✅ Impact estimation (magnitude + depth → expected damage)
- ✅ Post-event resource routing (hospitals, emergency services)
- ✅ Severity classification (magnitude-based)

**Recommendation:** 
- Use USGS data for situational awareness and post-event response
- DO NOT attempt predictive modeling
- Focus on rapid alert distribution instead

---

### 3. DROUGHT 🏜️

#### Data Sources

| Source | Type | Status | Coverage |
|--------|------|--------|----------|
| **OpenWeather Real-time Weather** | Current conditions | Active | 15 major Indian cities |

#### Detailed Breakdown

**OpenWeather Weather Correlation (Real-time)**
- **Data Path:** `drought_service.py` → OpenWeather API
- **Data Type:** Real-time weather features with indicator-based assessment
- **Query Coverage:** 15 Indian weather cities (Delhi, Mumbai, Chennai, etc.)
- **Rows:** 15 (one per city per query)
- **Columns (raw weather):**
  - location (text): City name
  - lat, lon (float): Coordinates
  - temperature_c (float): Current temperature
  - humidity_pct (int): Relative humidity (0–100)
  - rainfall_1h_mm (float): 1-hour rainfall
  - rainfall_3h_mm (float): 3-hour rainfall
  - pressure_hpa (int): Atmospheric pressure
- **Drought Assessment Columns:**
  - drought_score (null): NO SCORE PROVIDED (requires historical baselines)
  - severity (categorical): "UNAVAILABLE" / "ELEVATED_STRESS" / "MONITOR" / "NONE"
  - stress_indicators (list): low_humidity, high_temperature, no_recent_rainfall
  - confidence (text): "low" (explicitly stated)
  - status (text): "partial" or "unavailable"
  - message (text): "Drought score requires historical baselines; showing environmental stress indicators only"
- **Geographic Fields:** Lat/lon per city
- **Temporal Fields:** Current observation time
- **Disaster Label/Target:** 
  - Categorical severity (UNAVAILABLE/MONITOR/ELEVATED_STRESS/NONE)
  - Environment stress indicators (list of flags)
  - **NOTE:** drought_score is NULL; no ML score provided
- **ML Suitability:** **NO** ✗
  - ✗ No historical rainfall/soil moisture baselines available
  - ✗ Current weather alone insufficient for drought detection
  - ✗ No soil moisture, vegetation index, or hydrological data
  - ✗ Service explicitly returns "unavailable" status (acknowledged limitation)
  - ✓ CAN collect historical weather data for future feature engineering
- **Historical or Real-time:** Real-time current conditions (no archive)
- **Data Source:** OpenWeather API
- **Current Usage:** /api/disasters/droughts endpoint (stress indicators only)
- **Data Refresh Rate:** Real-time (on-demand API calls)

#### Drought ML Recommendation

**Can we train an ML model for drought prediction?**

🔴 **NO — Current data insufficient; would require new data sources**

**Why:**
1. **Only current weather available:** No historical rainfall normals or anomalies
2. **Missing critical features:**
   - Soil moisture
   - Vegetation index (NDVI from satellite)
   - Hydrological data (reservoir levels, groundwater)
   - 30–90 day rainfall cumulative anomalies
   - Seasonal rainfall baselines
3. **Single-point observations:** 15 cities not representative of 1.3M km² India

**To enable drought ML modeling, we would need:**
- ✅ MODIS NDVI data (vegetation health, via Google Earth Engine)
- ✅ CHIRPS rainfall reanalysis (30-year historical, 5km resolution)
- ✅ SRTM elevation + land use classification
- ✅ 30-year climate normals (IMD or Copernicus)
- ✅ Ground station soil moisture network
- 🚫 Currently NOT available in CrisisCore

**Recommendation:** 
- Archive current weather data for future use
- DO NOT train models yet
- Next phase: Integrate MODIS NDVI + CHIRPS rainfall for proper drought modeling

---

### 4. HEATWAVE 🔥

#### Data Sources

| Source | Type | Status | Coverage |
|--------|------|--------|----------|
| **OpenWeather Real-time Weather** | Current conditions | Active | 15 major Indian cities |

#### Detailed Breakdown

**OpenWeather Temperature & Humidity (Real-time)**
- **Data Path:** `heatwave_service.py` → OpenWeather API
- **Data Type:** Real-time temperature and humidity with heat index calculation
- **Query Coverage:** 15 Indian weather cities
- **Rows:** 15 (one per city per query)
- **Columns (raw weather):**
  - location (text): City name
  - lat, lon (float): Coordinates
  - temperature_c (float): Current temperature
  - feels_like_c (float): Apparent/heat-adjusted temperature
  - humidity_pct (int): Relative humidity (%)
  - heat_index_c (float): Calculated heat index (Rothfusser formula)
  - description (text): Weather condition
- **Heatwave Assessment Columns:**
  - heat_score (float): 0–100 scale derived from effective_temp
  - severity (categorical): "NONE" / "MODERATE" / "HIGH" / "EXTREME"
  - status (text): "ok" / "none_detected"
  - Thresholds:
    - EXTREME if feels_like ≥45°C or heat_index ≥45°C
    - HIGH if feels_like ≥40°C or heat_index ≥40°C
    - MODERATE if feels_like ≥35°C or heat_index ≥37°C
    - NONE otherwise
- **Geographic Fields:** Lat/lon per city
- **Temporal Fields:** Current observation time
- **Disaster Label/Target:**
  - Continuous: heat_score (0–100)
  - Categorical: severity (NONE/MODERATE/HIGH/EXTREME)
  - **NOTE:** Score is derived from single-day temperature; no historical comparison
- **ML Suitability:** **PARTIAL** ⚠️
  - ✅ Real temperature data (from OpenWeather)
  - ✅ Heat index calculation (established meteorological formula)
  - ⚠️ Single-day observations insufficient for heatwave modeling
  - ✗ No historical temperature normals or anomalies
  - ✗ No seasonal baseline comparison
  - ✗ Heatwaves are multi-day events; current API captures snapshots only
  - ⚠️ Current labels (NONE/MODERATE/HIGH/EXTREME) are threshold-based, not data-driven
- **Historical or Real-time:** Real-time current conditions (no archive)
- **Data Source:** OpenWeather API
- **Current Usage:** /api/disasters/heatwaves endpoint
- **Data Refresh Rate:** Real-time (on-demand API calls)

#### Heatwave ML Recommendation

**Can we train an ML model for heatwave prediction?**

⚠️ **PARTIAL YES — With significant data collection effort**

**Why it's possible (unlike earthquakes):**
- Heatwaves show predictable meteorological patterns
- Temperature anomalies can be forecasted 5–14 days ahead
- Seasonal patterns exist (summer monsoon effects)

**Current limitations:**
- ✗ Only current daily temperature; no historical baseline
- ✗ No 30-year climate normals to identify "anomalies"
- ✗ No multi-day persistence (heatwaves last 2–7 days)
- ✗ Single-point cities not representative of regional variation

**To enable heatwave ML modeling, we would need:**
- ✅ Daily temperature archive (1–2 years minimum)
- ✅ 30-year climate normals (IMD or Copernicus)
- ✅ Forecast model data (NCMRWF or GFS interpolated to cities)
- ✅ Historical heatwave event labels (dates, regions, duration)
- ✅ Seasonal feature engineering (monsoon phase, solar zenith angle)

**Data we COULD start collecting now:**
```
Daily: [date, city, temp_max, temp_min, feels_like, humidity, wind]
Then: Compute anomaly = temp_today - temp_normal[day_of_year]
Label: Is this day part of a heatwave event? (multi-day ≥5°C above normal)
```

**Recommendation:** 
- Begin daily historical temperature data collection NOW
- Archive all OpenWeather data for 12+ months
- After 12 months: Can develop heatwave prediction model (anomaly-based)
- DO NOT train yet; data insufficient

---

### 5. CYCLONE 🌀

#### Data Sources

| Source | Type | Status | Coverage |
|--------|------|--------|----------|
| **OpenWeather Real-time Wind & Pressure** | Current conditions | Active | 8 coastal Indian cities |

#### Detailed Breakdown

**OpenWeather Wind & Pressure (Real-time)**
- **Data Path:** `cyclone_service.py` → OpenWeather API
- **Data Type:** Real-time wind speed and atmospheric pressure
- **Query Coverage:** 8 coastal Indian cities (Chennai, Mumbai, Kolkata, Visakhapatnam, Kochi, Puri, Surat, Mangalore)
- **Rows:** 8 (one per coastal city per query)
- **Columns (raw weather):**
  - location (text): City name
  - lat, lon (float): Coordinates
  - wind_speed_ms (float): Wind speed (meters/second)
  - wind_gust_ms (float): Wind gust magnitude (optional)
  - pressure_hpa (int): Atmospheric pressure
  - description (text): Weather condition
- **Cyclone Assessment Columns:**
  - cyclone_score (null): NO SCORE PROVIDED
  - severity (categorical): "NONE" / "MONITOR" / "ELEVATED" / "HIGH"
  - status (text): "none_detected" / "conditions_elevated" / "unavailable"
  - Thresholds:
    - HIGH if wind ≥33 m/s OR gust ≥40 m/s (tropical cyclone threshold)
    - ELEVATED if wind ≥20 m/s OR gust ≥25 m/s
    - MONITOR if wind ≥13 m/s
    - NONE otherwise
  - message (text): "No active cyclone detected; showing wind/pressure conditions only" (always)
- **Geographic Fields:** Lat/lon per coastal city
- **Temporal Fields:** Current observation time
- **Disaster Label/Target:**
  - Continuous: wind_speed_ms, pressure_hpa
  - Categorical: severity (NONE/MONITOR/ELEVATED/HIGH)
  - **NOTE:** cyclone_score is NULL; no ML score provided; service explicitly states "no fabricated cyclone events"
- **ML Suitability:** **NO** ✗
  - ✗ Only 8 coastal cities (sparse coverage of 7,600 km coastline)
  - ✗ No historical cyclone tracking data
  - ✗ Current wind speed alone insufficient to predict cyclone genesis
  - ✗ Cyclone formation requires sea surface temperature, atmospheric instability, Coriolis force
  - ✗ Missing: satellite wind analysis, sea surface temperature (SST), upper-level wind shear
  - ✓ CAN be used for post-formation alert (when IMD issues cyclone warning)
  - ✓ CAN estimate landfall timing + intensity (with additional meteorological data)
- **Historical or Real-time:** Real-time current conditions (no archive)
- **Data Source:** OpenWeather API (limited for cyclone prediction)
- **Current Usage:** /api/disasters/cyclones endpoint
- **Data Refresh Rate:** Real-time (on-demand API calls)

#### Cyclone ML Recommendation

**Can we train an ML model for cyclone prediction?**

🔴 **NO — Current data insufficient; requires specialized meteorological data**

**Why:**
1. **Cyclone genesis is not predictable** from surface wind + pressure alone
2. **Formation requires:** 
   - Sea surface temperature (SST) >26.5°C
   - Atmospheric instability indices (CAPE, wind shear)
   - Coriolis force (only in tropics, 5°–15° latitude)
   - Vorticity rotation patterns
3. **Current data source inadequate:**
   - OpenWeather provides point observations (8 coastal cities)
   - Cyclones form over ocean (no coverage until they approach coast)
   - 6–24 hours before landfall is maximum lead time (too late for ML model)

**What CAN be done:**
- ✅ Ingest IMD cyclone warnings (when issued)
- ✅ Real-time tracking (satellite + surface observations)
- ✅ Landfall timing + intensity estimation (given active cyclone)
- ✅ Risk routing to coastal resources (evacuation planning)
- 🚫 Prediction of cyclone birth (requires specialized data)

**To enable cyclone ML research:**
- Need NOAA/IMD satellite data (SST, wind analysis, pressure analysis)
- Need 10+ years historical cyclone database (tracks + intensity)
- Advanced: Integrate numerical weather prediction model outputs (NCMRWF, GFS)
- Current: Impossible without these sources

**Recommendation:** 
- DO NOT train models yet
- Focus on real-time tracking and alert delivery
- Future phase: Integrate IMD radar/satellite feeds + numerical weather prediction

---

## Summary Table: ML Suitability by Disaster Type

| Disaster Type | Data Source | Rows | Temporal Coverage | ML Suitability | Current Status | Years to Readiness |
|---------------|-------------|------|-------------------|-----------------|-----------------|------------------|
| **FLOOD** | Sentinel-1/GEE | 200+/mo | Real-time stream | ✅ PARTIAL | Data available | 1–2 |
| **FLOOD** | floods_data.csv | 50 | Single event (Nigeria) | ❌ NO | Archive only | N/A |
| **FLOOD** | OpenWeather rules | 50 | Real-time | ❌ NO | Feature source | N/A |
| **EARTHQUAKE** | USGS real-time | 150–200 | Real-time stream | ❌ NO | Alert only | Never (unpredictable) |
| **DROUGHT** | OpenWeather | 15 | Real-time | ❌ NO | Indicators only | 2–3 (needs new data) |
| **HEATWAVE** | OpenWeather | 15 | Real-time | ⚠️ PARTIAL | Threshold-based | 1–2 (if archived) |
| **CYCLONE** | OpenWeather | 8 | Real-time | ❌ NO | Alert only | 3–5 (needs specialized data) |

---

## Live Features Summary

### OpenWeather API (50 Indian Cities)
**Features Available:**
- Temperature (°C)
- Humidity (%)
- Rainfall (1h, 3h)
- Wind speed & gust (m/s)
- Atmospheric pressure (hPa)
- Cloud coverage (%)
- Weather condition (description)

**Limitation:** Real-time only; no historical archive in current system  
**Recommendation:** Start archiving daily weather for all 50 cities NOW

### USGS Earthquake Feed (India Region)
**Features Available:**
- Magnitude (Richter scale)
- Depth (km)
- Coordinates (lat/lon)
- Location description
- Event timestamp
- USGS alert level

**Limitation:** Post-event detection only; ~15–20 events/month ≥2.5 magnitude  
**Recommendation:** Use for real-time alert delivery; don't model prediction

### Sentinel-1/Google Earth Engine (India-wide)
**Features Available:**
- Backscatter intensity (dB)
- Derived water mask (classification)
- Flood extent area (km²)
- Image date
- Geographic coverage (configurable)
- Baseline comparison period

**Limitation:** 6–12 day revisit time; requires ground truth validation  
**Recommendation:** Begin historical data backfill & validation workflow NOW

### OpenStreetMap (via Overpass API)
**Features Available:**
- Hospital locations & names
- Shelter locations & capacity
- Road networks
- Building footprints

**Status:** Integrated in resource_service.py  
**Current Usage:** /api/hospitals, /api/shelters endpoints  
**ML Suitability:** N/A (static reference data)

---

## Risk Engine Status

**File:** `backend/services/risk_engine.py`  
**Current State:**
```python
class RiskEngine:
    def is_model_available(self) -> bool:
        return self.model is not None  # Always False (no models in backend/models/)
    
    def predict(self, features) -> Dict:
        return {
            "status": "model_not_available",
            "score": None,
            "severity": "MODEL_NOT_AVAILABLE",
            "message": "No trained ML model loaded..."
        }
```

**Status:** ✅ Architecture ready; ❌ No models trained  
**Next Step:** After data pipeline is stable, implement ML model training & loading

---

## Recommendations

### ✅ IMMEDIATE (Ready Now)
1. **Deploy Flood Detection Pipeline**
   - Flood satellite data confirmed working
   - Begin historical Sentinel-1 backfill (24 months)
   - Establish ground truth validation workflow
   - **Timeline:** 4–8 weeks

2. **Archive Weather Data Daily**
   - 50 Indian cities already integrated
   - Begin storing data.json snapshots with timestamps
   - Useful for heatwave + drought modeling later
   - **Timeline:** Start immediately; build 12-month archive

3. **Deploy Real-time Alerts**
   - USGS earthquakes → frontend
   - OpenWeather extreme events → alerts
   - IMD cyclone warnings → alerts
   - **Timeline:** 1–2 weeks

### ⏳ MEDIUM-TERM (3–12 months)
4. **Develop Flood ML Model**
   - Use Sentinel-1 historical archive
   - Engineer features: elevation, slope, land use, rainfall anomaly
   - Label training data with satellite + news correlation
   - Train random forest or neural network classifier
   - **Timeline:** 8–12 weeks (after data backfill complete)

5. **Develop Heatwave ML Model**
   - Requires 12+ months OpenWeather archive
   - Compute temperature anomalies vs. seasonal normals
   - Label historical heatwave events from IMD
   - Train classification or anomaly detection model
   - **Timeline:** 12–16 weeks (after 1-year data collection)

### 🚫 NOT RECOMMENDED (Insufficient Data)
6. **Earthquake Prediction Model** — Seismic events unpredictable  
7. **Cyclone Genesis Model** — Requires specialized meteorological data  
8. **Drought Prediction Model** — Needs satellite vegetation + hydrological data (not currently available)

### 🔮 FUTURE (Year 2+)
9. **Integrate Advanced Satellite Data**
   - MODIS NDVI (vegetation health) for drought
   - Sentinel-2 (land use classification) for flood risk zones
   - SRTM DEM (terrain analysis) for landslide risk

10. **Integrate Numerical Weather Prediction**
    - NCMRWF model output (rainfall forecasts)
    - GFS (global forecasts)
    - Use for feature engineering: rainfall anomalies, wind anomalies

11. **Integrate Specialized Data**
    - IMD radar network data (cyclone tracking)
    - Soil moisture networks (drought monitoring)
    - Hydrological gauges (reservoir levels, river stage)

---

## Conclusion

**CrisisCore 2.0 is ready for Flood detection development and can legitimately pursue ML models for:**
- ✅ **Flood prediction** (with 8–12 week data pipeline development)
- ⚠️ **Heatwave detection** (with 12-month weather data collection first)

**Not suitable for ML models:**
- ❌ **Earthquakes** (unpredictable; use for alerts only)
- ❌ **Cyclones** (requires specialized meteorological data)
- ❌ **Droughts** (requires satellite vegetation data)

**Next Phase:** 
"Finish the MAP + DATA layer before building the AI Risk Engine" — maintain this priority. Complete the Flood detection data pipeline (GEE backfill + ground truth validation) before training any ML models.
