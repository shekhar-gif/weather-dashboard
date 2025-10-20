from flask import Flask, jsonify, render_template
import requests, time
import sqlite3
from datetime import date
from config import WEATHER_API_KEY

app = Flask(__name__)
city_cache = {}

def init_db():
    with sqlite3.connect("weather_history.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS weather_history (
                city TEXT,
                record_date TEXT,
                mintemp REAL,
                maxtemp REAL,
                condition TEXT
            )
        ''')
init_db()

def fetch_weather(city):
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={city}&days=3&alerts=yes"
    try:
        response = requests.get(url)
        data = response.json()
        if 'error' in data:
            return {"error": data['error']['message']}
        alerts = []
        for day in data["forecast"]["forecastday"]:
            if day["day"]["maxtemp_c"] > 40:
                alerts.append(f"Heat Wave Alert on {day['date']}! ({day['day']['maxtemp_c']}°C)")
            if day["day"]["mintemp_c"] < 5:
                alerts.append(f"Cold Wave Alert on {day['date']}! ({day['day']['mintemp_c']}°C)")
            condition_lower = day["day"]["condition"]["text"].lower()
            if "rain" in condition_lower or "thunder" in condition_lower:
                alerts.append(f"Heavy Rain Alert on {day['date']}! ({day['day']['condition']['text']})")

        # Official Alerts (WeatherAPI)
        official_alerts = []
        if "alerts" in data and "alert" in data["alerts"]:
            for alert in data["alerts"]["alert"]:
                desc = (
                    f"⚡ <b>{alert.get('event', 'Alert')}</b>: "
                    f"{alert.get('headline', '')} "
                    f"(area: {alert.get('areas', 'N/A')}, at: {alert.get('effective', '')}, severity: {alert.get('severity', '')})<br>"
                    f"{alert.get('desc', '')}"
                )
                official_alerts.append(desc)

        # Save today's data for trends/history
        try:
            today = str(date.today())
            with sqlite3.connect("weather_history.db") as conn:
                cur = conn.execute("SELECT 1 FROM weather_history WHERE city=? AND record_date=?",
                                   (data["location"]["name"], today))
                if cur.fetchone() is None:
                    min_temp = min([d['day']['mintemp_c'] for d in data["forecast"]["forecastday"]])
                    max_temp = max([d['day']['maxtemp_c'] for d in data["forecast"]["forecastday"]])
                    condition = data["current"]["condition"]["text"]
                    conn.execute(
                        "INSERT INTO weather_history (city, record_date, mintemp, maxtemp, condition) VALUES (?, ?, ?, ?, ?)",
                        (data["location"]["name"], today, min_temp, max_temp, condition)
                    )
        except Exception as dberr:
            print("DB save error:", dberr)

        weatherinfo = {
            "city": data["location"]["name"],
            "temperature": data["current"]["temp_c"],
            "condition": data["current"]["condition"]["text"],
            "lastupdated": data["current"]["last_updated"],
            "forecast": [
                {
                    "date": day["date"],
                    "min": day["day"]["mintemp_c"],
                    "max": day["day"]["maxtemp_c"],
                    "condition": day["day"]["condition"]["text"]
                }
                for day in data["forecast"]["forecastday"]
            ],
            "alerts": alerts,
            "official_alerts": official_alerts
        }
        return weatherinfo
    except Exception as e:
        return {"error": str(e)}

@app.route("/", methods=["GET"])
def home():
    return render_template("dashboard.html")

@app.route("/getalerts/<city>", methods=["GET"])
def get_alerts(city):
    city_lower = city.strip().lower()
    now = time.time()
    if city_lower in city_cache and now - city_cache[city_lower]["timestamp"] < 600:
        info = city_cache[city_lower]["weather"]
    else:
        info = fetch_weather(city)
        city_cache[city_lower] = {"weather": info, "timestamp": now}
    return jsonify(info)

@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")

@app.route("/trends/<city>", methods=["GET"])
def city_trends(city):
    with sqlite3.connect("weather_history.db") as conn:
        rows = conn.execute(
            "SELECT record_date, mintemp, maxtemp FROM weather_history WHERE city=? ORDER BY record_date DESC LIMIT 7",
            (city.capitalize(),)
        ).fetchall()
    trends = [{"date": r[0], "mintemp": r[1], "maxtemp": r[2]} for r in rows][::-1]
    return jsonify(trends)

if __name__ == "__main__":
    app.run(debug=True)
