import requests
from config import WEATHER_API_KEY
import json

CITY = "Delhi"
URL = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={CITY}"

try:
    response = requests.get(URL)
    response.raise_for_status()  # raises an error for 401, 404, etc.
    data = response.json()

    print(f"City: {data['location']['name']}")
    print(f"Temperature: {data['current']['temp_c']}°C")
    print(f"Condition: {data['current']['condition']['text']}")

    weather_info = {
        "city": data['location']['name'],
        "temperature": data['current']['temp_c'],
        "condition": data['current']['condition']['text']
    }

    with open("alerts.json", "w") as file:
        json.dump(weather_info, file)

    print("✅ Weather data saved to alerts.json")

except requests.exceptions.HTTPError as e:
    print("❌ API request failed:", e)
except Exception as e:
    print("⚠️ Error fetching weather:", e)
