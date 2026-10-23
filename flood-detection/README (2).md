# Satellite Flood Detection Toolkit

Five scripts, included in this package:

0. **`app.py`** — **Click-on-map web app.** No typing place names — open a map in
   your browser, click anywhere, and it automatically analyzes that spot for
   recent flooding. This is the easiest way to use the toolkit. See below.

1. **`gee_flood_detection.py`** — Original version. You manually pick "before" and
   "after" date ranges. Good for looking back at a past flood event.

2. **`monitor_flood.py`** — Improved, interactive version. Automatically finds the
   *most recent* available satellite pass (no manual dates), uses a stricter/cleaner
   detection method, and gives you a rough flooded-area estimate in km².

3. **`monitor_flood_auto.py`** — Same as above but non-interactive, for scheduled/
   automatic runs (see "Near-real-time monitoring" section below). Edit the
   `PLACE_NAME` at the top of the file, then it can run unattended.

4. **`local_flood_detection.py`** — For when you already have a satellite image
   file (GeoTIFF) downloaded to your computer and want to process it locally,
   no cloud account needed.

**A note on "real-time":** true real-time (live, this-second) satellite flood
detection isn't physically possible — Sentinel-1 only passes over any given spot
roughly every 6-12 days, which is a limit of the satellite's orbit, not this
software. `monitor_flood.py` / `monitor_flood_auto.py` give you the closest
practical version: they always fetch whatever the *newest available* image is,
and can be scheduled to auto-check daily so you get updated results the moment
new data lands.

---

## PART 1: Google Earth Engine Setup (do this once)

### Step 1 — Get a free Earth Engine account
1. Go to https://code.earthengine.google.com/register
2. Sign in with a Google account, follow the prompts (choose "unpaid/noncommercial use" if asked).
3. Approval is usually instant to a few hours.

### Step 2 — Install Python and dependencies
Open a terminal (Command Prompt / Terminal app) in the folder you extracted this zip into, then run:

```bash
pip install -r requirements.txt
```

### Step 3 — Run it
```bash
python gee_flood_detection.py
```
The first time you run any script in this folder, it'll ask for your Earth
Engine project ID (see "For a new teammate" below if you don't have one yet)
and may open a browser to log in and approve access. After that first time,
it's saved and you won't be asked again on this computer.

It will then prompt you for:
- A place name or bounding box (e.g., "Jakarta, Indonesia" or coordinates)
- A "before" date range (normal conditions)
- An "after" date range (during/after the flood event)

It will output:
- `flood_extent.tif` — a GeoTIFF map of detected flood area
- `flood_map.html` — an interactive map you can open in any browser

---

## PART 2: Local Processing (if you already have imagery)

If you've downloaded a Sentinel-1 or Sentinel-2 image yourself (e.g. from
https://browser.dataspace.copernicus.eu or https://earthexplorer.usgs.gov),
use this instead:

```bash
python local_flood_detection.py --before before_image.tif --after after_image.tif --output flood_result.tif
```

Run `python local_flood_detection.py --help` for all options.

---

## Click-on-map web app (easiest option)

```bash
python app.py
```
Then open **http://127.0.0.1:5000** in your browser (Chrome, Edge, whatever you use).

A world map loads (starting centered on Assam). Click anywhere, and within
20-40 seconds it shows you:
- The detected flood extent (red overlay) at that spot
- The date of the satellite image used
- An estimated flood area in km²

Click a different spot any time to re-run the analysis there. Leave the
Command Prompt window open while you use it — closing it shuts down the app.
To stop the app, click back into that Command Prompt window and press `Ctrl+C`.

## Running the improved monitor

```bash
python monitor_flood.py
```
Just enter a place name — it handles the rest, including a rough flood-area
estimate in km². Open `flood_map.html` afterward and toggle the "Baseline
(before)" layer on/off in the top-right panel to visually compare.

## Near-real-time monitoring (auto-refresh on a schedule)

1. Open `monitor_flood_auto.py` in Notepad and change `PLACE_NAME = "Chennai, India"`
   to your location.
2. Test it manually first: `python monitor_flood_auto.py` — confirm it runs without
   errors and updates `flood_map.html`.
3. Set it to run automatically once a day using Windows Task Scheduler:
   - Open Task Scheduler (search for it in the Start menu)
   - Click **Create Basic Task**
   - Name it "Flood Monitor", click Next
   - Trigger: **Daily**, pick a time, click Next
   - Action: **Start a program**
   - Program/script: browse to `run_monitor.bat` inside this folder
   - Finish
4. Each run overwrites `flood_map.html` with the latest result and appends a row
   to `flood_history.csv`, so you can track flood extent over time in Excel.
   Logs of each run are saved to `monitor_log.txt`.

## For a new teammate (setting this up on a different computer)

Each person needs their own Google account and their own free Earth Engine
project — this is a Google requirement, access can't be shared or copy-pasted
between people. The good news: it only takes a few minutes, and you only do
it once.

1. **Install everything** — same as above: install Python 3.9+, extract this
   folder, run `pip install -r requirements.txt`.
2. **Register for Earth Engine** (free): go to
   https://code.earthengine.google.com/register, sign in with your Google
   account, choose "unpaid/noncommercial use."
3. **Create a Cloud project**: if it doesn't create one automatically, go to
   https://console.cloud.google.com/earth-engine, click **Create project**,
   name it anything (e.g. `flood-detection`). Note the project ID shown in
   the browser's address bar afterward (looks like `your-name-123456`).
4. **Run any script** — e.g. `python app.py` or `python monitor_flood.py`.
   The first time, it'll ask for your Earth Engine project ID — paste the one
   from step 3. It's saved to `config.txt` in this folder automatically, so
   you're only asked once on that computer.
5. If it also asks you to authenticate in a browser (first-time only), log in
   and click **Allow**.

That's it — from then on, every script (the click-on-map app, the monitor,
the manual date-range version) just works, using the saved project ID.

## Where to get free satellite imagery manually

- **Copernicus Data Space** (Sentinel-1/2, free): https://browser.dataspace.copernicus.eu
- **USGS EarthExplorer** (Landsat, free account): https://earthexplorer.usgs.gov
- **NASA Worldview** (quick visual check, no processing): https://worldview.earthdata.nasa.gov

## How the detection actually works (short version)

- **Radar (SAR)** imagery: water reflects radar signal away from the satellite, so
  flooded areas appear very dark. The script flags pixels below a brightness
  threshold as water.
- It compares a "before" image to an "after" image, so only *new* water
  (i.e., flooding) is flagged — not permanent rivers/lakes.
- A cleanup step removes isolated noise pixels and slope artifacts using a
  digital elevation model, so mountainsides in radar shadow aren't
  mistaken for flooding.

## Troubleshooting

- **`earthengine authenticate` fails / opens nothing** — copy the URL it prints
  into a browser manually.
- **"Project not registered" error** — Earth Engine now requires a Google Cloud
  project; the script will print a one-line command to fix this if it happens.
- **Local script: "CRS mismatch" error** — your before/after images use different
  map projections. Re-download both from the same source/dataset to match.
