from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests, time
import sqlite3
from datetime import date
from config import WEATHER_API_KEY
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'replace_this_with_a_secret_key'

def init_db():
    with sqlite3.connect("weather_history.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS weather_history (
                city TEXT,
                record_date TEXT,
                mintemp REAL,
                maxtemp REAL,
                condition TEXT,
                humidity INTEGER,
                wind_kph REAL,
                precip_mm REAL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT, email TEXT, password_hash TEXT
            );
        ''')
init_db()
city_cache = {}

def fetch_weather(city):
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={city}&days=3&alerts=yes"
    try:
        response = requests.get(url)
        data = response.json()
        if 'error' in data:
            return {"error": data['error']['message']}
        alerts, official_alerts = [], []
        for day in data["forecast"]["forecastday"]:
            if day["day"]["maxtemp_c"] > 40:
                alerts.append(f"Heat Wave Alert on {day['date']}! ({day['day']['maxtemp_c']}°C)")
            if day["day"]["mintemp_c"] < 5:
                alerts.append(f"Cold Wave Alert on {day['date']}! ({day['day']['mintemp_c']}°C)")
            if "rain" in day["day"]["condition"]["text"].lower() or "thunder" in day["day"]["condition"]["text"].lower():
                alerts.append(f"Heavy Rain Alert on {day['date']}! ({day['day']['condition']['text']})")
        if "alerts" in data and "alert" in data["alerts"]:
            for alert in data["alerts"]["alert"]:
                desc = (
                    f"⚡ <b>{alert.get('event', 'Alert')}</b>: "
                    f"{alert.get('headline', '')} "
                    f"(area: {alert.get('areas', 'N/A')}, at: {alert.get('effective', '')}, severity: {alert.get('severity', '')})<br>"
                    f"{alert.get('desc', '')}"
                )
                official_alerts.append(desc)
        try:
            today = str(date.today())
            with sqlite3.connect("weather_history.db") as conn:
                cur = conn.execute(
                    "SELECT 1 FROM weather_history WHERE city=? AND record_date=?",
                    (data["location"]["name"], today))
                if cur.fetchone() is None:
                    min_temp = min([d['day']['mintemp_c'] for d in data["forecast"]["forecastday"]])
                    max_temp = max([d['day']['maxtemp_c'] for d in data["forecast"]["forecastday"]])
                    condition = data["current"]["condition"]["text"]
                    humidity = data["current"]["humidity"]
                    wind_kph = data["current"]["wind_kph"]
                    precip_mm = data["current"]["precip_mm"]
                    conn.execute(
                        "INSERT INTO weather_history (city, record_date, mintemp, maxtemp, condition, humidity, wind_kph, precip_mm) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (data["location"]["name"], today, min_temp, max_temp, condition, humidity, wind_kph, precip_mm)
                    )
        except Exception as dberr:
            print("DB save error:", dberr)
        weatherinfo = {
            "city": data["location"]["name"],
            "temperature": data["current"]["temp_c"],
            "condition": data["current"]["condition"]["text"],
            "lastupdated": data["current"]["last_updated"],
            "humidity": data["current"]["humidity"],
            "wind_kph": data["current"]["wind_kph"],
            "precip_mm": data["current"]["precip_mm"],
            "latitude": data["location"]["lat"],
            "longitude": data["location"]["lon"],
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        conn = sqlite3.connect('weather_history.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email))
        existing = cursor.fetchone()
        if existing:
            message = "Username or email already exists!"
            conn.close()
        else:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
    return render_template('register.html', message=message)

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('weather_history.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('home'))
        else:
            message = "Invalid username or password."
    return render_template('login.html', message=message)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.before_request
def protect_routes():
    unauthenticated_routes = ['login', 'register', 'static', None]
    if not session.get('user_id'):
        if request.endpoint not in unauthenticated_routes:
            return redirect(url_for('login'))

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
            "SELECT record_date, mintemp, maxtemp, humidity, wind_kph, precip_mm FROM weather_history WHERE city=? ORDER BY record_date DESC LIMIT 7",
            (city.capitalize(),)
        ).fetchall()
    trends = [
        {"date": r[0], "mintemp": r[1], "maxtemp": r[2], "humidity": r[3], "wind_kph": r[4], "precip_mm": r[5]}
        for r in rows
    ][::-1]
    return jsonify(trends)

@app.route("/admin")
def admin_panel():
    with sqlite3.connect("weather_history.db") as conn:
        stats = conn.execute(
              "SELECT city, COUNT(*) AS records, MAX(maxtemp), MIN(mintemp) FROM weather_history GROUP BY city"
          ).fetchall()
        users = conn.execute("SELECT username, email FROM users").fetchall()
    return render_template("admin.html", stats=stats, users=users)

if __name__ == "__main__":
    app.run(debug=True)

