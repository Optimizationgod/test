from flask import Flask, request, jsonify
import sqlite3
import secrets
import string
import requests
import os

app = Flask(__name__)

database = "database.db"
url = "http://worldtimeapi.org/api/timezone/Africa/Cairo"

try:
    response = requests.get(url)
    response.raise_for_status()
    date = int(response.json()["day_of_year"])
    expiration_date = date + 30
except requests.RequestException as e:
    app.logger.error(f"Error fetching date from API: {e}")
    date = None
    expiration_date = None


def init_db():
    with sqlite3.connect(database) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_key TEXT,
                device_id TEXT,
                activated INTEGER default 0,
                expired INTEGER default 0,
                started_day_of_year INTEGER,
                will_expire_on INTEGER)"""
        )
        conn.commit()


init_db()


def generate_key(length=32):
    """Generates a cryptographically secure random key."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.route("/add_key", methods=["POST"])
def add_key():
    key = generate_key()
    login = request.get_json()
    username = "memo"
    password = "1464"

    if login["username"] == username and login["password"] == password:
        try:
            with sqlite3.connect(database) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (device_key) VALUES (?)", (key,))
                conn.commit()
                return jsonify({"message": "Key added successfully", "key": key}), 200
        except sqlite3.IntegrityError:
            return jsonify({"error": "Key already exists"}), 400
    else:
        return jsonify({"error": "Invalid username or password"}), 401


@app.route("/activate", methods=["POST"])
def activate():
    if date is None or expiration_date is None:
        return jsonify({"error": "Date information is not available"}), 500

    data = request.get_json()
    device_key = data.get("device_key")
    device_id = data.get("device_id")

    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT device_id, activated, expired, started_day_of_year, will_expire_on FROM users WHERE device_key = ?""",
            (device_key,),
        )
        result = cursor.fetchone()

        if result:
            db_device_id, activated, expired, started_day_of_year, will_expire_on = (
                result
            )
            if (
                activated == 0
                and (db_device_id is None or db_device_id == "")
                and expired == 0
            ):
                cursor.execute(
                    """UPDATE users SET device_id = ?, activated = 1, started_day_of_year = ?, will_expire_on = ? WHERE device_key = ?""",
                    (device_id, date, expiration_date, device_key),
                )
                conn.commit()
                return jsonify({"message": "Activated successfully"}), 200
            elif (
                activated == 1
                and db_device_id == device_id
                and expired == 0
                and will_expire_on > date
            ):
                cursor.execute(
                    """UPDATE users SET started_day_of_year = ? WHERE device_key = ?""",
                    (date, device_key),
                )
                conn.commit()
                return jsonify({"message": "Activated successfully"}), 200
            else:
                days_left = will_expire_on - date
                if days_left <= 0:
                    cursor.execute(
                        """UPDATE users SET expired = 1 WHERE device_key = ?""",
                        (device_key,),
                    )
                    conn.commit()
                    return jsonify({"error": "Key has expired"}), 400

    return jsonify({"error": "Invalid key or already activated"}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
