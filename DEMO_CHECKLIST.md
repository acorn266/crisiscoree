# CrisisCore 2.0 — Demo Checklist

Everything here runs on free tiers: no paid APIs, no credit card.

| Part | URL | Port |
|---|---|---|
| Frontend (React + Vite) | http://localhost:5173 | 5173 |
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
| `OPENWEATHER_API_KEY` | Weather, heatwave, drought, cyclone layers, AI risk | https://home.openweathermap.org/api_keys (new keys can take up to ~2 h to activate) |
| `GEMINI_API_KEY` | AI chatbot answers | https://aistudio.google.com/apikey |

Both are optional for the app to *run*: without them, weather shows "Data unavailable" and the
chatbot answers from its built-in safety guide. `backend\.env` is git-ignored — never commit it.

---

## 2. Start everything (in this order)

**Option A — one click:** double-click `start-crisiscore.bat` in the project folder.
It opens two terminal windows (backend, then frontend) and the browser.

**Option B — two terminals (PowerShell):**

Terminal 1 — backend (start first):
```powershell
cd "D:\my projects\crisiscore-disaster-preparedness-2.0\backend"
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000
```
Wait for `Application startup complete.`

Terminal 2 — frontend:
```powershell
cd "D:\my projects\crisiscore-disaster-preparedness-2.0\frontend"
npm run dev -- --port 5173 --strictPort
```
Then open http://localhost:5173

To stop: press `Ctrl+C` in each terminal.

---

## 3. Pre-demo checks (5 minutes before)

Run these in a third PowerShell window. Each should print JSON quickly.

```powershell
curl.exe http://localhost:8000/health
curl.exe "http://localhost:8000/api/weather?lat=19.07&lon=72.88"
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/chat -ContentType 'application/json' -Body '{"message":"What should I do during an earthquake?"}' | Select-Object source, reply | Format-List
```

- Weather should say `"status":"ok"`. If it says `unavailable`, check `OPENWEATHER_API_KEY`.
- Chat should say `source : gemini`. `fallback` still works for the demo (built-in answers).
  Bullets may print as `â¢` in Windows PowerShell — that's only the terminal; the browser is fine.
- Then load http://localhost:5173 once so the data caches warm up (later loads are instant).
- **Don't restart the backend right before presenting** — caches live in memory.
- Allow location access when the browser asks (or deny it — the app falls back to central India).

---

## 4. Demo script

1. **Dashboard overview** — top cards: live weather, overall AI risk level, active alert count.
2. **Map** — earthquake markers (USGS, sized/colored by magnitude). Click a marker for details.
   Use the layer panel (top-right) to toggle Drought / Heatwave / Cyclone / Hospitals / Shelters.
   (Weather layers only show markers where conditions are actually elevated — calm days show none.)
3. **🎯 Fit to Events** — zooms the map to all current events.
4. **Alerts panel** — scroll down; alerts are sorted by severity. **Click an alert** — the page
   jumps back to the map, zoomed to that event.
5. **Risk Analysis panel** — per-hazard AI scores with "Why?" explanations. Scores are capped by
   IMD-style physical thresholds (e.g. no heatwave alarm below 35 °C), and the reason is shown.
6. **Hospitals & Shelters** — turn on the 🏥/🏠 layers and zoom into a city (zoom level 7+).
   Data comes live from OpenStreetMap's free Overpass servers; if they don't answer within 5 s,
   saved OpenStreetMap snapshots are used for Bengaluru, Mumbai, Delhi, Chennai, Kolkata,
   Hyderabad and Nagpur, with a small "Saved data" note. **Demo inside one of these cities.**
7. **AI Assistant** — click a sample question chip, then type your own.
8. **↻ Refresh Data** — reloads all sources (weather is served from a 10-minute cache).

### Sample chatbot questions
- What should I do during an earthquake?
- How do I prepare for a flood?
- Is there any earthquake activity near India right now?  *(uses live dashboard data)*
- What are the signs of heat stroke?
- A cyclone warning was issued for Odisha. What should my family do?
- There is smoke coming from my neighbour's house, what do I do?
- We have a water shortage because of drought. How can we save water?

Answers take ~2–15 s from Gemini. If Gemini is slow (>15 s), down, or out of free quota, the
assistant instantly answers from its offline safety guide and shows a small notice.
The chat allows 10 messages per minute per user.

---

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Red banner "Could not load: …" | Backend not running or still starting. Start Terminal 1, then click **↻ Refresh Data**. |
| Weather "Data unavailable" | `OPENWEATHER_API_KEY` missing/invalid in `backend\.env`, or a brand-new key not yet active. Restart the backend after editing `.env`. |
| Hospital/shelter card or map shows "ⓘ Saved data for <city> …" | Expected fallback: live Overpass (OpenStreetMap) didn't answer within 5 s, so the backend served the saved snapshot for the nearest demo city. Live is retried automatically after 2 minutes. |
| Nearest Hospital/Shelter "Data unavailable", no 🏥/🏠 markers | Live Overpass is down **and** the location is more than 100 km from a saved demo city (Bengaluru, Mumbai, Delhi, Chennai, Kolkata, Hyderabad, Nagpur). Zoom into one of those cities. |
| Chat replies with "offline safety guide" notice | No `GEMINI_API_KEY`, Gemini free quota reached, or slow network. The answers are still correct safety guidance. |
| Chat says "You're sending messages quickly" | Per-user rate limit (10/min). Wait the number of seconds shown. |
| Flood layer shows nothing / "unavailable" | Expected: satellite flood detection (Google Earth Engine) is disabled for the demo. |
| `Port 5173 is in use` / `8000` in use | Another copy is running. Close the old terminal windows (or Task Manager → end `node.exe` / `python.exe`). |
| Page is blank | Hard refresh (`Ctrl+Shift+R`); check the frontend terminal for errors. |

---

## 6. Refreshing the saved hospital/shelter snapshots

Snapshots live in `backend\data\resource_snapshots\*.json` — real OpenStreetMap data
(© OpenStreetMap contributors, ODbL), each covering ~28 km around the city centre.
To refresh them (takes a few minutes; retries across free mirrors):
```powershell
cd backend
.\venv\Scripts\python.exe scripts\fetch_resource_snapshots.py           # all 7 cities
.\venv\Scripts\python.exe scripts\fetch_resource_snapshots.py mumbai    # just one
```
Restart the backend afterwards so it loads the new files.

---

## 7. Optional: satellite flood detection

Off by default. To enable (needs a free Google Earth Engine account):
```powershell
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements-flood.txt
.\venv\Scripts\earthengine.exe authenticate
```
Then set `FLOOD_DETECTION_ENABLED=true` in `backend\.env` and restart the backend.
Each satellite analysis takes 20–40 s, so leave this off for live demos.
