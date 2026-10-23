# CrisisCore 2.0 — System Architecture

Rendered image: [`CrisisCore_System_Architecture.svg`](CrisisCore_System_Architecture.svg) · [`CrisisCore_System_Architecture.png`](CrisisCore_System_Architecture.png)
(The Mermaid source below can also be pasted into https://mermaid.live to edit or re-render.)

```mermaid
%%{init: {"theme": "base", "layout": "elk", "flowchart": {"curve": "basis", "nodeSpacing": 22, "rankSpacing": 55, "padding": 12}, "themeVariables": {"fontFamily": "Arial, Helvetica, sans-serif", "fontSize": "16px", "lineColor": "#475569", "edgeLabelBackground": "#ffffff"}}}%%
flowchart TB

    USER["User — web browser"]

    subgraph FE["FRONTEND · React + Vite · :5173"]
        APP["App.jsx<br/>state · data loading · location picker"]
        subgraph UI["UI components"]
            MAP["DisasterMap<br/>React-Leaflet"]
            ALERTS["AlertPanel<br/>filters"]
            CARDS["Summary, risk and<br/>resource cards"]
            CHATUI["ChatAssistant"]
            DEMO["demoFloods.js<br/>Demo mode, OFF by default"]
        end
        UTILS["services/api.js — fetch<br/>utils: chat context · alerts · geo"]
    end

    subgraph BE["BACKEND · FastAPI · :8000"]
        API["main.py — REST API · TTL cache · config from .env<br/>/api/disasters/india · /api/alerts/official · /api/weather<br/>/api/hospitals · /api/shelters · /api/ai-risk · /api/chat"]
        subgraph SVC["Service layer"]
            AI["ai_risk_engine<br/>+ risk_guards"]
            RES["resource_service<br/>5 s budget + fallback"]
            HAZ["hazard services<br/>quake · weather · heat<br/>drought · cyclone"]
            ALG["alert_service<br/>unified alerts"]
            OFF["official_alerts_service<br/>background refresh"]
            CHAT["chat_service<br/>rate limit · fallback"]
            FLOOD["flood_service<br/>optional"]
        end
    end

    subgraph LOCAL["LOCAL DATA"]
        MODELS["models/*.joblib<br/>5 Isolation Forest models"]
        SNAP["resource_snapshots/*.json<br/>OSM data · 7 cities"]
    end

    subgraph EXT["EXTERNAL FREE SERVICES"]
        OVP["OSM Overpass<br/>hospitals · shelters"]
        USGS["USGS<br/>earthquakes"]
        OWM["OpenWeather<br/>free tier"]
        SACHET["NDMA SACHET<br/>official alerts"]
        GDACS["GDACS<br/>UN / EC"]
        GEM["Google Gemini<br/>free tier"]
        GEE["Earth Engine<br/>disabled"]
        TILES["OSM map tiles"]
    end

    USER -->|uses| APP
    APP --> UI
    UI --> UTILS
    DEMO -.->|only in Demo mode| MAP
    UTILS ==>|HTTP · JSON| API

    API --> AI
    API --> RES
    API --> HAZ
    API --> OFF
    API --> CHAT
    API --> FLOOD
    HAZ -->|events| ALG
    HAZ -.->|model inputs| AI

    AI -->|loads| MODELS
    RES -.->|fallback| SNAP
    RES -->|live query| OVP
    HAZ -->|GeoJSON| USGS
    HAZ -->|weather| OWM
    OFF -->|CAP XML| SACHET
    OFF -->|events| GDACS
    CHAT -->|generateContent| GEM
    FLOOD -.->|if enabled| GEE
    MAP -.->|tiles| TILES

    classDef user fill:#1e293b,stroke:#0f172a,color:#ffffff,stroke-width:2px
    classDef fe fill:#dbeafe,stroke:#2563eb,color:#0f172a,stroke-width:1.5px
    classDef be fill:#dcfce7,stroke:#16a34a,color:#0f172a,stroke-width:1.5px
    classDef data fill:#fef3c7,stroke:#d97706,color:#0f172a,stroke-width:1.5px
    classDef ext fill:#ede9fe,stroke:#7c3aed,color:#0f172a,stroke-width:1.5px
    classDef optional fill:#f1f5f9,stroke:#94a3b8,color:#475569,stroke-width:1.5px,stroke-dasharray:5 4

    class USER user
    class APP,MAP,ALERTS,CARDS,CHATUI,UTILS fe
    class API,AI,RES,HAZ,ALG,OFF,CHAT be
    class MODELS,SNAP data
    class OVP,USGS,OWM,SACHET,GDACS,GEM,TILES ext
    class DEMO,FLOOD,GEE optional

    style FE fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    style UI fill:#f8fbff,stroke:#93c5fd,color:#1e3a8a
    style BE fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#14532d
    style SVC fill:#f7fef9,stroke:#86efac,color:#14532d
    style LOCAL fill:#fffbeb,stroke:#d97706,stroke-width:2px,color:#78350f
    style EXT fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#4c1d95
```

**Legend:** blue = frontend · green = backend · amber = local data · purple = external free services ·
grey dashed = optional / disabled by default · thick arrow = HTTP/JSON between browser and API.

---

## Architecture overview

CrisisCore 2.0 is a two-tier web application:

- **Frontend (React 19 + Vite, port 5173)** — a single-page dashboard. `App.jsx` loads every data
  source independently (one failing source never blanks the page) and passes data to the map,
  alerts panel, summary/risk cards and chat assistant. The map uses React-Leaflet with OpenStreetMap
  tiles. All backend calls go through `services/api.js`.
- **Backend (FastAPI + Uvicorn, port 8000)** — `main.py` exposes REST endpoints and delegates to
  service modules. Secrets (OpenWeather and Gemini keys) are read from `backend/.env` by `config.py`.
  An in-memory TTL cache (`cache_utils`) keeps external calls within free-tier limits.
- **Local data** — five pre-trained Isolation Forest models (`models/*.joblib`) and saved
  OpenStreetMap hospital/shelter snapshots for seven cities (`data/resource_snapshots/`).
- **External free sources** — NDMA SACHET, GDACS, USGS, OpenWeather, OpenStreetMap Overpass,
  Google Gemini (free tier) and OpenStreetMap tiles. Google Earth Engine is optional and off by default.

## Major data flows

1. **Dashboard data** — the browser calls `/api/disasters/india`; the backend fetches USGS earthquakes
   and OpenWeather readings for 15 cities + 8 coastal points (in parallel, cached ~10 min), derives
   heat / drought / wind indicators, and `alert_service` turns them into a unified alert list. Each
   earthquake is tagged inside or outside India from USGS's own place name.
2. **Official warnings** — `official_alerts_service` reads the NDMA SACHET CAP feed (IMD, CWC and state
   SDMA warnings) and GDACS events, drops expired/cancelled alerts, and refreshes in the background every
   10 minutes; `/api/alerts/official` serves the cached result instantly. CAP alerts carry district names
   only, so their map position is the approximate centre of the named state (labelled "approximate").
3. **Hospitals & shelters** — `/api/hospitals`, `/api/shelters` and their `/map` (viewport) variants
   query OpenStreetMap Overpass with a 5-second budget. If live lookups fail, a circuit breaker skips live
   calls for 60 s and the nearest saved city snapshot is served, marked "saved" in the UI.
4. **Risk estimates** — `/api/ai-risk` gathers live weather and the nearest USGS earthquake, scores each
   hazard with its Isolation Forest model, then `risk_guards` caps scores that contradict observed
   conditions (IMD-style thresholds). Results are labelled "AI estimate", not official forecasts.
5. **AI assistant** — the frontend builds a factual dashboard snapshot (`utils/assistantContext.js`) and
   posts it with the question to `/api/chat`. `chat_service` applies a per-IP rate limit and calls Gemini
   with a timeout; if the key is missing, the call fails or quota is reached, it answers from a built-in
   offline safety guide.
6. **Floods** — the flood layer shows official flood warnings (SACHET/CWC), recent GDACS flood events and,
   only when Earth Engine is enabled, Sentinel-1 satellite analysis. Demo flood zones are local sample
   data shown only when the user switches Demo mode on.
