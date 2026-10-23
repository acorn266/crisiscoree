"""Shared configuration for India Disaster Intelligence Map."""
import os

# OpenWeather API key (from existing weather_to_json.py)
OPENWEATHER_API_KEY = os.getenv(
    "OPENWEATHER_API_KEY", "4b85e0446e7fef03754bd783c58f39c2"
)

# India geographic bounds
INDIA_BOUNDS = {
    "southwest": {"lat": 6.5, "lon": 68.1},
    "northeast": {"lat": 35.5, "lon": 97.4},
    "center": {"lat": 20.5937, "lon": 78.9629},
}

# Cache TTL in seconds (GEE queries are expensive)
CACHE_TTL_SECONDS = int(os.getenv("DISASTER_CACHE_TTL", "3600"))

# Configurable Indian regions for automated flood monitoring
INDIA_FLOOD_MONITOR_REGIONS = [
    {"id": "assam", "name": "Assam (Brahmaputra)", "lat": 26.2006, "lon": 92.9376},
    {"id": "kerala", "name": "Kerala", "lat": 10.8505, "lon": 76.2711},
    {"id": "bihar", "name": "Bihar", "lat": 25.0961, "lon": 85.3131},
    {"id": "uttar-pradesh", "name": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
    {"id": "maharashtra", "name": "Maharashtra", "lat": 19.7515, "lon": 75.7139},
    {"id": "west-bengal", "name": "West Bengal", "lat": 22.5726, "lon": 88.3639},
    {"id": "odisha", "name": "Odisha", "lat": 20.9517, "lon": 85.0985},
    {"id": "gujarat", "name": "Gujarat", "lat": 22.2587, "lon": 71.1924},
]

# Major Indian cities for weather-based disaster monitoring
INDIA_WEATHER_CITIES = [
    {"name": "Delhi", "lat": 28.7041, "lon": 77.1025},
    {"name": "Mumbai", "lat": 19.076, "lon": 72.8777},
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"name": "Hyderabad", "lat": 17.385, "lon": 78.4867},
    {"name": "Ahmedabad", "lat": 23.0225, "lon": 72.5714},
    {"name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
    {"name": "Lucknow", "lat": 26.8467, "lon": 80.9462},
    {"name": "Bhopal", "lat": 23.2599, "lon": 77.4126},
    {"name": "Patna", "lat": 25.5941, "lon": 85.1376},
    {"name": "Guwahati", "lat": 26.1445, "lon": 91.7362},
    {"name": "Thiruvananthapuram", "lat": 8.5241, "lon": 76.9366},
    {"name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
    {"name": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
]

# Coastal cities for cyclone monitoring
INDIA_COASTAL_CITIES = [
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Mumbai", "lat": 19.076, "lon": 72.8777},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"name": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185},
    {"name": "Kochi", "lat": 9.9312, "lon": 76.2673},
    {"name": "Puri", "lat": 19.8135, "lon": 85.8312},
    {"name": "Surat", "lat": 21.1702, "lon": 72.8311},
    {"name": "Mangalore", "lat": 12.9141, "lon": 74.8560},
]
