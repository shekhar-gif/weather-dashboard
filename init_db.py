import sqlite3

# Connect to your existing weather_history.db database
conn = sqlite3.connect("weather_history.db")
cursor = conn.cursor()

# Create users table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
)
""")

conn.commit()
conn.close()
print("Users table created successfully.")
