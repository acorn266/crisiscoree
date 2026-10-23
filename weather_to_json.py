import requests, json

API_KEY = "4b85e0446e7fef03754bd783c58f39c2"

cities = [
"Bengaluru","Chennai","Mumbai","Hyderabad","Delhi",
"Kolkata","Ahmedabad","Pune","Jaipur","Lucknow",
"Surat","Bhopal","Indore","Nagpur","Coimbatore",
"Visakhapatnam","Patna","Vadodara","Ludhiana","Agra",
"Nashik","Faridabad","Meerut","Rajkot","Varanasi",
"Srinagar","Amritsar","Ranchi","Jodhpur","Raipur",
"Guwahati","Chandigarh","Mysuru","Thiruvananthapuram","Madurai",
"Tiruchirappalli","Kanpur","Noida","Gurgaon","Aurangabad",
"Jamshedpur","Allahabad","Gwalior","Dehradun","Udaipur",
"Shimla","Panaji","Silchar","Durgapur","Kozhikode"
]

def predict_disasters(rain, humidity, clouds, wind, temp):

    # Flood
    if rain > 10 or (humidity > 85 and clouds > 80):
        flood = "High"
    elif rain > 3:
        flood = "Medium"
    else:
        flood = "Low"

    # Cyclone
    if wind > 15:
        cyclone = "High"
    elif wind > 8:
        cyclone = "Medium"
    else:
        cyclone = "Low"

    # Drought
    if rain == 0 and temp > 35 and humidity < 40:
        drought = "High"
    elif rain < 1:
        drought = "Medium"
    else:
        drought = "Low"

    # Earthquake (simple static assumption)
    earthquake = "Medium"

    return flood, cyclone, drought, earthquake


output = {"cities": []}

for city in cities:
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    data = requests.get(url).json()

    if data.get("cod") != 200:
        continue

    rain = data.get("rain", {}).get("1h", 0)
    humidity = data["main"]["humidity"]
    clouds = data["clouds"]["all"]
    wind = data["wind"]["speed"]
    temp = data["main"]["temp"]

    flood, cyclone, drought, earthquake = predict_disasters(
        rain, humidity, clouds, wind, temp
    )

    output["cities"].append({
        "name": city,
        "lat": data["coord"]["lat"],
        "lng": data["coord"]["lon"],
        "rain": rain,
        "humidity": humidity,
        "clouds": clouds,
        "wind": wind,
        "temp": temp,
        "flood": flood,
        "cyclone": cyclone,
        "drought": drought,
        "earthquake": earthquake
    })

with open("data.json", "w") as f:
    json.dump(output, f, indent=2)

print("Updated data.json")