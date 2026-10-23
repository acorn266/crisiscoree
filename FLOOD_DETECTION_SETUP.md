# CrisisCore 2.0 + Satellite Flood Detection Integration

## Overview

This document explains the integration of satellite-based flood detection (Sentinel-1 SAR imagery via Google Earth Engine) into CrisisCore 2.0.

### Architecture

```
Leaflet Map (React)
       ↓ (Click to analyze)
/api/flood-risk (FastAPI)
       ↓ (HTTP POST)
flood_service.py (GEE wrapper)
       ↓ (Python API calls)
Google Earth Engine
       ↓ (Sentinel-1 SAR data)
Flood Extent Detection
       ↓
Result: Area (km²), Date, Status
       ↓
Display on Leaflet map
```

### What Was Integrated

| Component | Location | Purpose |
|-----------|----------|---------|
| **flood_service.py** | `backend/flood_service.py` | Wraps Google Earth Engine flood detection |
| **FastAPI Endpoint** | `backend/main.py` | `/api/flood-risk` POST endpoint |
| **React Frontend** | `frontend/src/components/DisasterMap.jsx` | Map click handler + flood layer display |
| **CORS Middleware** | `backend/main.py` | Allows React → Backend communication |
| **Requirements** | `backend/requirements.txt` | All necessary Python packages |

### Key Features

✅ **Real Satellite Data**: Uses Sentinel-1 C-band SAR radar (not optical, works through clouds/night)  
✅ **Automatic Latest Image**: Automatically finds newest satellite pass (every 6-12 days per location)  
✅ **Baseline Comparison**: Compares against 30-45 day baseline (normal conditions)  
✅ **Flood Area Estimation**: Calculates flooded area in km²  
✅ **Geolocation Support**: Works with lat/lon coordinates  
✅ **Noise Filtering**: Removes false positives using slope/DEM/blob analysis  
✅ **Interactive Map**: Click anywhere on the map to trigger analysis  

---

## Setup Instructions

### Step 1: Google Earth Engine Account (Free)

1. Go to: https://code.earthengine.google.com/register
2. Sign in with a Google account
3. Accept terms (approval is usually instant to a few hours)
4. Make note of your **Google Cloud Project ID** (if prompted)

### Step 2: Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- FastAPI + Uvicorn (web server)
- earthengine-api (GEE client)
- geemap (GEE utilities)
- rasterio, numpy, scipy, scikit-image (image processing)
- geopandas, folium (geospatial tools)

### Step 3: Authenticate with Google Earth Engine (First Time Only)

```bash
# From any Python shell or script that imports ee:
python -c "import ee; ee.Authenticate()"
```

This opens a browser window where you:
1. Sign in to your Google account
2. Authorize "Google Earth Engine"
3. Get an auth code → paste it back into the terminal

After this, authentication is cached and you won't need to do it again on this computer.

### Step 4: Start the Backend

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 5: Start the Frontend (in another terminal)

```bash
cd frontend
npm install
npm run dev
```

Your React app will run on `http://localhost:5173` (or similar)

### Step 6: Test Flood Detection

1. Open the frontend in your browser
2. **Click anywhere on the map** to trigger flood analysis
3. A blue dashed box appears around the clicked area
4. Status message shows: "🔍 Analyzing flood risk... (20-40 seconds)"
5. If flood detected: 🌊 marker appears with area in km² and satellite image date

---

## API Reference

### POST /api/flood-risk

**Request:**
```json
{
  "lat": 13.0878,
  "lon": 80.2785,
  "buffer_deg": 0.15
}
```

**Response (Success):**
```json
{
  "success": true,
  "lat": 13.0878,
  "lon": 80.2785,
  "image_date": "2026-08-15",
  "area_km2": 12.45,
  "flood_detected": true,
  "buffer_deg": 0.15
}
```

**Response (No Flood):**
```json
{
  "success": true,
  "lat": 13.0878,
  "lon": 80.2785,
  "image_date": "2026-08-15",
  "area_km2": 0.0,
  "flood_detected": false,
  "buffer_deg": 0.15
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "No recent Sentinel-1 imagery available for this location..."
}
```

### GET /api/flood-status

Check if flood detection service is ready:
```json
{
  "service_ready": true,
  "message": "✓ Flood detection service ready (Google Earth Engine initialized)"
}
```

### GET /health

Backend health check:
```json
{
  "status": "healthy",
  "flood_service_ready": true
}
```

---

## Data Sources

### Sentinel-1 SAR Imagery
- **Source**: European Space Agency (ESA)
- **Satellite**: Sentinel-1 A/B constellation
- **Resolution**: 10 meters per pixel
- **Revisit**: Every 6-12 days per location
- **Coverage**: Global (except extreme polar regions)
- **Free/Open**: Yes, via Google Earth Engine

### Ancillary Datasets (Used in Processing)
- **Global Surface Water** (JRC GSW 1.4): Permanent water bodies
- **SRTM DEM** (USGS): Terrain/slope filtering

---

## How Flood Detection Works

### Algorithm

1. **Fetch Latest Satellite Image** (current conditions)
   - Search Sentinel-1 last 14 days
   - Use most recent available pass
   - Filter to VH polarization (specific to SAR)

2. **Fetch Baseline Image** (normal conditions)
   - Search 30-45 days ago
   - Median composite of all images in window
   - Ensures no flood signal

3. **Detect Water in Both Images**
   - Apply speckle filter (reduce SAR noise)
   - Threshold backscatter at -18 dB
   - SAR values below -18 dB = water

4. **Calculate Flood Extent** (new water)
   - Subtract permanent water (JRC GSW dataset)
   - Remove water that existed 30-45 days ago
   - Filter by slope < 5° (remove false positives from mountainsides)
   - Remove noise blobs < 20 connected pixels

5. **Estimate Area**
   - Count pixels in flood mask
   - Multiply by 100 m² (10m × 10m pixel)
   - Report in km²

### Why SAR (Not Optical)?

| Factor | SAR | Optical |
|--------|-----|---------|
| **Cloud Penetration** | Works through clouds ✓ | Blocked by clouds ✗ |
| **Night Capability** | Works at night ✓ | Needs daylight ✗ |
| **Water Detection** | Clear/reliable ✓ | Can be ambiguous |
| **Revisit** | Every 6-12 days ✓ | Every 5-10 days, weather dependent |
| **Use Case** | Monsoons, monsoons | Clear weather regions only |

For tropical monsoon regions (India, SE Asia), SAR is superior.

---

## Limitations & Notes

### Satellite Coverage
- **Revisit Time**: 6-12 days per location (not daily)
- **First Request**: Takes 20-40 seconds (GEE computation)
- **Cached**: Subsequent requests are faster

### Detection Limitations
- **Minimum Area**: ~0.01 km² (very small floods may be missed)
- **Mountainsides**: Steep slopes filtered to reduce false positives
- **Radar Shadow**: Areas behind mountains may be unobservable
- **Temporary Water**: Cannot distinguish recent temporary flooding from permanent features without baseline

### False Positives
Can occur from:
- Bare soil/dirt roads (low backscatter)
- Metallic surfaces
- Man-made structures with radar-quiet signatures

Reduced by:
- Speckle filtering (smoothing)
- Slope filtering
- Blob size thresholding
- Comparison against baseline

---

## Troubleshooting

### "Earth Engine not initialized"
**Problem**: Google Earth Engine failed to authenticate  
**Solution**:
```bash
python -c "import ee; ee.Authenticate()"
# Complete browser login
```

### "No Sentinel-1 imagery found"
**Problem**: Satellite hasn't passed over that location recently  
**Solution**: Try again tomorrow, or choose a different location

### "CORS error" in browser console
**Problem**: Frontend cannot reach backend  
**Solution**: 
- Check backend is running: `http://localhost:8000/health`
- Check CORS middleware is added to `main.py`
- Restart backend

### "Network error" when clicking map
**Problem**: Frontend fetch failed  
**Solution**:
- Check backend is running
- Verify backend URL is correct: `http://localhost:8000`
- Check browser network tab for actual error

---

## Files Changed/Created

### New Files
- `backend/flood_service.py` — Google Earth Engine wrapper
- `backend/requirements.txt` — Python dependencies

### Modified Files
- `backend/main.py` — Added FastAPI endpoints + CORS
- `frontend/src/components/DisasterMap.jsx` — Added flood click handler + visualization

### Unchanged
- `frontend/src/App.jsx` — Still works as before
- `frontend/src/App.css` — No CSS changes needed
- `map.html` — Original standalone map preserved
- `data.json` — Original weather/risk data unchanged
- `floods_data.csv` — Original Nigerian incident data unchanged
- `weather_to_json.py` — Original weather script unchanged
- CrisisCore project structure intact

---

## Next Steps (Optional Enhancements)

1. **Automated Monitoring**: Run flood analysis on a schedule (e.g., daily)
2. **Alerts**: Send notifications when flood is detected
3. **Historical Trends**: Archive flood detections over time
4. **Multi-Region**: Analyze multiple locations simultaneously
5. **Custom Thresholds**: User-adjustable SAR backscatter thresholds
6. **Export**: Download flood maps as GeoTIFF/KML
7. **Machine Learning**: Combine flood extent with weather/terrain data for impact prediction

---

## Support & Resources

- **Google Earth Engine**: https://earthengine.google.com
- **Sentinel-1 Handbook**: https://sentinel.esa.int/web/sentinel/user-guides
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **React Leaflet**: https://react-leaflet.js.org

---

## License & Attribution

- **Sentinel-1 Data**: European Space Agency (open)
- **Google Earth Engine**: Google LLC (free for research/non-profit)
- **Original Flood Detection Code**: Friend's project (flood-detection folder)
- **Integration**: CrisisCore 2.0 by Sherisha

