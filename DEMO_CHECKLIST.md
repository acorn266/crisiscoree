# CrisisCore 2.0 — Demo Checklist

Everything here runs on free tiers and free public data: no paid APIs, no credit card.

| Part | URL | Port |
|---|---|---|
| **Website (open this)** | **http://localhost:5173** | 5173 |
| Backend (FastAPI) | http://localhost:8000 | 8000 |
| Backend API docs | http://localhost:8000/docs | 8000 |

The separate Flask app in `flood-detection/` (port 5000) is **not** needed for the demo.

---

## 1. One-time setup (already done on this machine)

Requires Python 3.12 and Node.js 20.19+ (tested with Node 22).

```powershell
# Backend
cd backend
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Frontend
cd ..\frontend
npm install
```

Create `backend\.env` from `backend\.env.example` and fill in:

| Variable | Needed for | Where to get it (free) |
|---|---|---|
| `OPENWEATHER_API_KEY` | Weather card, heat / drought / wind indicators, AI risk estimates | https://home.openweathermap.org/api_keys (new keys can take up to ~2 h to activate) |
| `GEMINI_API_KEY` | AI chatbot answers | https://aistudio.google.com/apikey |

Both are optional for the app to *run*: without them, weather shows "Unavailable" and the
chatbot answers from its built-in safety guide. `backend\.env` is git-ignored — never commit it.

---

## 2. Start everything (in this order)

**Option A — one click:** double-click `start-crisiscore.bat` in the project folder.
It opens two terminal windows (backend, then frontend) and then the browser.

**Option B — two terminals (PowerShell):**

Terminal 1 — backend (start first):
```powershell
cd "D:\my projects\crisiscore-disaster-preparedness-2.0\backend"
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000
```
Wait for `Application startup complete.` (official warnings load in the background for ~10–20 s).

Terminal 2 — frontend:
```powershell
cd "D:\my projects\crisiscore-disaster-preparedness-2.0\frontend"
npm run dev -- --port 5173 --strictPort
```
Then open **http://localhost:5173**

To stop: press `Ctrl+C` in each terminal (or close the two windows).

---

## 3. Pre-demo checks (5 minutes before)

Run these in a third PowerShell window. Each should print JSON quickly.

```powershell
curl.exe http://localhost:8000/health
curl.exe "http://localhost:8000/api/weather?lat=19.07&lon=72.88"
curl.exe http://localhost:8000/api/alerts/official
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/chat -ContentType 'application/json' -Body '{"message":"What should I do during an earthquake?"}' | Select-Object source, reply | Format-List
```

- Weather should say `"status":"ok"`. If it says `unavailable`, check `OPENWEATHER_API_KEY`.
- Official alerts should list `"sachet": {"status": "ok"...}` and `"gdacs": {"status": "ok"...}`.
- Chat should say `source : gemini`. `fallback` still works for the demo (built-in answers).
  Bullets may print as `â¢` in Windows PowerShell — that's only the terminal; the browser is fine.
- Load http://localhost:5173 once so the caches warm up. **Don't restart the backend right before presenting.**
- Use the **📍 location picker** (top right) to choose a demo city — Bengaluru or Chennai work well.

---

## 4. What's on the dashboard (and what kind of data it is)

Every value is labelled with where it comes from:

| Label | Meaning |
|---|---|
| **LIVE** | Fetched just now from a public source (OpenWeather, USGS, OpenStreetMap) |
| **OFFICIAL** | Issued by an authority: NDMA SACHET (IMD / CWC / state SDMAs) or GDACS (UN / EC) |
| **OBSERVED** | Measured event, e.g. a USGS earthquake |
| **INDICATOR** | CrisisCore threshold on live weather — *not* an official warning |
| **AI ESTIMATE** | Isolation Forest anomaly score on live data — indicative only |
| **SAVED** | Saved OpenStreetMap snapshot (hospitals / shelters) used when live lookups fail |
| **DEMO** | Sample flood zones, only when "Demo flood data" is switched on |
| **UNAVAILABLE / OFF** | No data — this is *not* proof that there is no danger |

---

## 5. Demo script

1. **Header** — CrisisCore branding, location picker, last-updated time, Refresh.
2. **Summary cards** — live weather, overall risk (AI estimate), active alerts split into
   official / observed / indicators, and the **Data sources** card showing what is live, saved or off.
3. **Map** — layers (top-right): Floods, Earthquakes, Official warnings, Hospitals, Shelters are on;
   switch on Cyclones / Heatwave / Drought to show those. Click any marker for details.
   Earthquake popups say **Inside India** or **Outside India · country**.
4. **Floods** — the line under the map always states the flood situation: official CWC/IMD flood
   warnings (blue 🌊, dashed area = approximate), recent GDACS floods (grey = ended), and that
   satellite detection is off.
5. **Alerts panel** (right of the map) — filter by type (chips with counts), by source
   (Official / Observed / Indicators) and by severity. **Click an alert** → the map zooms there and
   highlights it. Pick a type with no alerts (e.g. Cyclone) to show the honest empty state.
6. **Nearest hospital / shelter** — choose **Bengaluru** in the location picker, then
   **Show on map →**: the map zooms in and highlights the place. Hospitals ✚ (red) and shelters ⌂
   (green) appear on the map; the badge says whether the data is live or saved.
7. **Local risk estimates** — five hazard tiles, each labelled *AI estimate* with its inputs and any
   IMD-style cap that was applied.
8. **AI Assistant** — click a suggestion or type a question (see below).
9. **Demo flood data** (optional) — toggle in the map toolbar: striped **DEMO** zones and a banner
   appear; switch it off again afterwards. It is off by default and never mixed with real data.

### Sample chatbot questions
- Are there any earthquakes inside India right now? Which is the strongest?
- Was the M7 earthquake in India?
- Are there any official flood warnings in India right now?
- Where is the nearest hospital and shelter, and is that information live?
- What is the current weather and overall risk here, and how is the risk calculated?
- What should I do during an earthquake?
- What are the signs of heat stroke?

Answers take ~2–15 s from Gemini. If Gemini is slow (>15 s), down, or out of free quota, the
assistant instantly answers from its offline safety guide and shows a small notice.
The chat allows 10 messages per minute per user.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Red banner "Some data could not be loaded" | Backend not running or still starting. Start Terminal 1, then click **↻ Refresh**. |
| Weather "Unavailable" | `OPENWEATHER_API_KEY` missing/invalid in `backend\.env`, or a brand-new key not yet active. Restart the backend after editing `.env`. |
| "Loading official warnings…" for a while | NDMA SACHET fetch takes ~10–20 s after a backend start; it then refreshes in the background every 10 min. |
| Data sources card shows SACHET / GDACS **Unavailable** | That public feed is down; last good warnings are kept. Missing data ≠ no danger. |
| Hospital/shelter shows **Saved · <city>** | Expected fallback: live Overpass (OpenStreetMap) didn't answer within 5 s, so the saved snapshot for the nearest demo city is used. Live is retried automatically after 60 s. |
| Nearest Hospital/Shelter "No live or saved data" | Live Overpass is down **and** the location is more than 100 km from a saved city (Bengaluru, Mumbai, Delhi, Chennai, Kolkata, Hyderabad, Nagpur). Pick one of those cities. |
| No flood markers | Normal when there are no current flood warnings — read the status line under the map. Use **Demo flood data** only if you need to show what a flood alert looks like. |
| Chat replies with "Offline safety guide" notice | No `GEMINI_API_KEY`, Gemini free quota reached, or slow network. The answers are still correct safety guidance. |
| Chat says "You're sending messages quickly" | Per-user rate limit (10/min). Wait the number of seconds shown. |
| `Port 5173 is in use` / `8000` in use | Another copy is running. Close the old terminal windows (or Task Manager → end `node.exe` / `python.exe`). |
| Page is blank | Hard refresh (`Ctrl+Shift+R`); check the frontend terminal for errors. |

---

## 7. Refreshing the saved hospital/shelter snapshots

Snapshots live in `backend\data\resource_snapshots\*.json` — real OpenStreetMap data
(© OpenStreetMap contributors, ODbL), each covering ~28 km around the city centre.
To refresh them (takes a few minutes; retries across free mirrors):
```powershell
cd backend
.\venv\Scripts\python.exe scripts\fetch_resource_snapshots.py           # all 7 cities
.\venv\Scripts\python.exe scripts\fetch_resource_snapshots.py mumbai    # just one
```
The running backend picks up new or refreshed files automatically (no restart needed).

---

## 8. Data sources

| Data | Source | Type |
|---|---|---|
| Official warnings (rain, thunderstorm, lightning, flood, cyclone, heat…) | NDMA SACHET CAP feed (IMD, CWC, state SDMAs) | Official, live |
| Floods, cyclones, droughts (verified events) | GDACS (UN / European Commission) | Official, live |
| Earthquakes | USGS | Observed, live |
| Weather, heat / drought / wind indicators | OpenWeather (free tier) | Live + CrisisCore indicators |
| Hospitals, shelters | OpenStreetMap via Overpass | Live, or saved snapshot |
| Risk estimates | CrisisCore Isolation Forest models on the live data above | AI estimate |
| Satellite flood detection | Sentinel-1 / Google Earth Engine | Off (optional, see below) |

---

## 9. Optional: satellite flood detection

Off by default. To enable (needs a free Google Earth Engine account):
```powershell
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements-flood.txt
.\venv\Scripts\earthengine.exe authenticate
```
Then set `FLOOD_DETECTION_ENABLED=true` in `backend\.env` and restart the backend.
Each satellite analysis takes 20–40 s, so leave this off for live demos.
