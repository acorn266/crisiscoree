# 🌊 CrisisCore 2.0 Flood Detection Integration - Quick Start

## What Was Done ✅

1. **Integrated satellite-based flood detection** from friend's Google Earth Engine project
2. **Created FastAPI backend service** (`flood_service.py`) that wraps Sentinel-1 SAR flood detection
3. **Added `/api/flood-risk` endpoint** to CrisisCore backend for real-time flood analysis
4. **Updated Leaflet map** in React to allow click-to-analyze flood detection
5. **Added CORS middleware** so frontend can communicate with backend
6. **No training required** - uses real satellite data and threshold-based detection

## Run Instructions

### Terminal 1: Start Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

First time? You'll be prompted to authenticate with Google Earth Engine (opens browser)

### Terminal 2: Start Frontend
```bash
cd frontend
npm run dev
```

### Browser
Open http://localhost:5173 → Click anywhere on the map → Wait 20-40s → See flood result

---

## Integration Summary

### Data Flow
```
Map Click (React)
    ↓
HTTP POST /api/flood-risk
    ↓
flood_service.py (GEE wrapper)
    ↓
Sentinel-1 SAR Imagery (Google Earth Engine)
    ↓
Threshold Detection + Filtering
    ↓
Flood Mask + Area (km²)
    ↓
Blue dashed box + 🌊 marker on map
```

### What Type of Flood Detection?
- **Type**: Satellite-based SAR radar image classification
- **Not a deep learning model** - uses threshold-based water detection on backscatter values
- **Real-time data**: Sentinel-1 satellite passes every 6-12 days
- **Automatic baseline**: Compares against normal conditions from 30-45 days ago
- **Geolocation**: YES - uses exact lat/lon coordinates

### Which Files Are Used from Friend's Project?
Friend's project is in: `flood-detection/` folder

**NOT copied** (stays in original folder, used as reference):
- `gee_flood_detection.py` (original CLI version)
- `monitor_flood.py` (improved CLI version)
- `local_flood_detection.py` (local file processing)
- `app.py` (Flask standalone app)
- Templates and configs

**REUSED** (logic extracted & adapted):
- Water detection algorithm (threshold-based)
- Baseline comparison logic
- Flood extent filtering
- Area calculation
- Google Earth Engine initialization

**NEW in CrisisCore**:
- `backend/flood_service.py` - Wraps GEE functions as reusable service class
- `/api/flood-risk` FastAPI endpoint
- React DisasterMap integration
- Click-to-analyze interface

---

## Files Changed

### Created
```
backend/flood_service.py ...................... 370 lines
backend/requirements.txt ....................... 13 packages
FLOOD_DETECTION_SETUP.md ....................... Full setup guide
FLOOD_DETECTION_QUICKREF.md .................... This file
```

### Modified
```
backend/main.py
  ├─ Added: FastAPI CORS middleware
  ├─ Added: Pydantic models (FloodAnalysisRequest/Response)
  ├─ Added: /api/flood-risk POST endpoint
  └─ Added: /api/flood-status GET endpoint
  
frontend/src/components/DisasterMap.jsx
  ├─ Added: floodData, floodAnalyzing, floodError state
  ├─ Added: MapClickHandler component
  ├─ Added: handleFloodAnalysis async function
  ├─ Added: Rectangle visualization for flood analysis area
  ├─ Added: 🌊 marker when flood detected
  └─ Added: Status messages + error display
```

### NOT Changed (Preserved)
```
map.html ......................... Original standalone map
data.json ......................... Weather/city data
floods_data.csv ................... Nigerian incident data
weather_to_json.py ................ Weather data generation
frontend/src/App.jsx .............. Main React app
frontend/src/App.css .............. Styling
All other CrisisCore files ........ Unchanged
```

---

## Backend API

### POST /api/flood-risk
Analyze flood risk at any lat/lon

**Request:**
```json
{
  "lat": 13.0878,
  "lon": 80.2785,
  "buffer_deg": 0.15
}
```

**Response (Flood Detected):**
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
  "error": "No recent Sentinel-1 imagery available for this location. Try again in a few days."
}
```

### GET /health
Backend health check (now includes flood service status)

```json
{
  "status": "healthy",
  "flood_service_ready": true
}
```

### GET /api/flood-status
Check if flood detection is ready

```json
{
  "service_ready": true,
  "message": "✓ Flood detection service ready (Google Earth Engine initialized)"
}
```

---

## Frontend Integration

### How Flood Appears on Map
1. **Click anywhere** on the Leaflet map
2. Blue dashed box appears around clicked area (15 km radius)
3. Status message: "🔍 Analyzing flood risk... (20-40 seconds)"
4. **If flood detected**: 🌊 marker appears at center with popup showing:
   - Area in km²
   - Satellite image date
   - "Satellite: Sentinel-1 SAR"
5. **Error message** if analysis fails (shown at top of map)

### Legend Update
Map legend now shows: `🌊 Flood (click map)`

---

## How to Test

### Test 1: Check Backend is Ready
```bash
curl http://localhost:8000/health
```
Should return: `{"status":"healthy","flood_service_ready":true}`

### Test 2: Manual API Call
```bash
curl -X POST http://localhost:8000/api/flood-risk \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 13.0878,
    "lon": 80.2785,
    "buffer_deg": 0.15
  }'
```

### Test 3: Frontend Map
1. Open http://localhost:5173 in browser
2. Scroll/zoom to India
3. Click on a city (e.g., Chennai, Bengaluru)
4. Watch console for: 🔍 Analyzing flood risk...
5. After 20-40 seconds, result appears on map

---

## Important Notes

### Google Earth Engine Requirement
✅ **FREE account needed** (not API key, actual account)
1. Go to: https://code.earthengine.google.com/register
2. Sign in with Google account
3. Approval is instant/few hours
4. First run of backend will prompt for browser login
5. Auth is cached after that

### Sentinel-1 Satellite Coverage
- **Every location**: Satellite passes every 6-12 days
- **No daily updates**: SAR satellite orbit is fixed
- **Real-time limit**: This is the best "real-time" gets with radar
- **Monsoon advantage**: Works through clouds (unlike optical)

### Processing Time
- **First request**: 20-40 seconds (GEE computation)
- **Subsequent same location**: Faster (partial caching)
- **Different location**: 20-40 seconds again

### False Positives Reduced By
- Speckle filtering (noise reduction)
- Slope filtering (>5° = not flood)
- Blob filtering (< 20 pixels = ignore)
- Permanent water removal (JRC GSW dataset)
- 30-45 day baseline comparison

---

## Limitations (Be Aware)

1. **Not daily updates** - Satellite passes every 6-12 days
2. **Cannot show live current** - Only latest available image
3. **May miss very small floods** - < 0.01 km² may be below detection
4. **Radar shadow zones** - Areas behind mountains unobservable
5. **May have false positives** - Bare soil, metal structures can look like water
6. **No optical validation** - Only uses SAR, not visible light data

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Earth Engine not initialized" | Run: `python -c "import ee; ee.Authenticate()"` |
| "CORS error" in browser | Check backend is running on port 8000 |
| "No Sentinel-1 imagery found" | Satellite hasn't passed lately, try another location |
| "Network timeout" | Check backend logs for errors |
| "Blue box but no marker" | Flood not detected = no flooding at that location |

---

## Next: What Could Be Added

1. Scheduled monitoring (check flood status daily)
2. Alert notifications (alert user if flood detected)
3. Trend analysis (historical flood tracking)
4. Impact prediction (combine with buildings/population data)
5. Export maps (download as GeoTIFF/KML)
6. Combine with weather data (precipitation → flood risk)

---

## Architecture Diagram

```
FRONTEND (React + Leaflet)
┌─────────────────────────────────┐
│  DisasterMap.jsx                │
│  - Click on map                 │
│  - Show blue box                │
│  - Display 🌊 marker            │
│  - Show flood area              │
└────────────┬────────────────────┘
             │
             │ HTTP POST /api/flood-risk
             │ {lat, lon, buffer_deg}
             ↓
BACKEND (FastAPI)
┌─────────────────────────────────┐
│  main.py                        │
│  - /api/flood-risk endpoint     │
│  - CORS middleware              │
│  - Request validation           │
└────────────┬────────────────────┘
             │
             │ Call flood_service.py
             ↓
FLOOD SERVICE (Python)
┌─────────────────────────────────┐
│  flood_service.py               │
│  - Get region geometry          │
│  - Fetch latest Sentinel-1      │
│  - Fetch 30-45 day baseline     │
│  - Threshold water detection    │
│  - Filter false positives       │
│  - Calculate area               │
└────────────┬────────────────────┘
             │
             │ Use Google Earth Engine API
             ↓
GOOGLE EARTH ENGINE
┌─────────────────────────────────┐
│  Public Satellite Data          │
│  - Sentinel-1 A/B SAR           │
│  - JRC Global Surface Water     │
│  - USGS SRTM DEM                │
│  - Performs computation         │
└────────────┬────────────────────┘
             │
             │ Return: Flood mask, area_km2, date
             ↓
RESPONSE
{
  "success": true,
  "area_km2": 12.45,
  "flood_detected": true,
  "image_date": "2026-08-15"
}
```

---

## Summary

✅ **Flood detection integrated successfully**  
✅ **Uses real Sentinel-1 satellite data (every 6-12 days)**  
✅ **Click-to-analyze interface on Leaflet map**  
✅ **Geolocation-aware (actual coordinates)**  
✅ **No model training needed**  
✅ **All CrisisCore existing functionality preserved**  
✅ **Ready for testing and deployment**  

🎉 **CrisisCore 2.0 now has satellite-based flood detection!**

