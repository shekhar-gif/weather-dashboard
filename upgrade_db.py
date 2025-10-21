import sqlite3

conn = sqlite3.connect("weather_history.db")
cur = conn.cursor()

# Add humidity column (if it doesn't exist)
try:
    cur.execute("ALTER TABLE weather_history ADD COLUMN humidity INTEGER;")
except Exception as e:
    print("Column 'humidity' may already exist.", e)

# Add wind_kph column (if it doesn't exist)
try:
    cur.execute("ALTER TABLE weather_history ADD COLUMN wind_kph REAL;")
except Exception as e:
    print("Column 'wind_kph' may already exist.", e)

# Add precip_mm column (if it doesn't exist)
try:
    cur.execute("ALTER TABLE weather_history ADD COLUMN precip_mm REAL;")
except Exception as e:
    print("Column 'precip_mm' may already exist.", e)

conn.commit()
conn.close()
print("Columns added successfully!")
