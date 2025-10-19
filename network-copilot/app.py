from flask import Flask, request, jsonify, render_template
import sqlite3
import threading
import time
from datetime import datetime
import os

# Import your helper modules
from llm_wrapper import analyze_network_data
from security_analysis import check_for_threats

app = Flask(__name__)

DB_PATH = "data.db"
COLLECTION_INTERVAL = 5  # seconds

# -------------------- Database Setup --------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS device_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_ip TEXT,
            latency REAL,
            packet_loss REAL,
            timestamp TEXT,
            up INTEGER,
            rx_bytes INTEGER,
            tx_bytes INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# -------------------- Safe DB Write Helper --------------------

def safe_execute(query, params=()):
    retries = 5
    for attempt in range(retries):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(query, params)
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                time.sleep(0.1)
            else:
                raise

# -------------------- Data Collection Thread --------------------

def collect_metrics():
    while True:
        try:
            # Replace this with your actual metrics collection logic
            # Example placeholder metrics:
            device_ip = "192.168.1.5"
            latency = 5.2
            packet_loss = 0.0
            rx_bytes = 102400
            tx_bytes = 20480
            up = 1
            timestamp = datetime.now().isoformat()

            safe_execute('''
                INSERT INTO device_metrics (device_ip, latency, packet_loss, timestamp, up, rx_bytes, tx_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (device_ip, latency, packet_loss, timestamp, up, rx_bytes, tx_bytes))

            time.sleep(COLLECTION_INTERVAL)

        except Exception as e:
            print(f"[Error in collect_metrics] {e}")
            time.sleep(2)

# Start the data collection in a background thread
threading.Thread(target=collect_metrics, daemon=True).start()

# -------------------- Flask Routes --------------------

@app.route("/")
def index():
    return render_template("index.html") if os.path.exists("templates/index.html") else "Network Copilot running ✅"

@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM device_metrics ORDER BY timestamp DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()

    columns = ["id", "device_ip", "latency", "packet_loss", "timestamp", "up", "rx_bytes", "tx_bytes"]
    data = [dict(zip(columns, row)) for row in rows]
    return jsonify(data)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    analysis = analyze_network_data(data)
    threats = check_for_threats(data)
    return jsonify({"analysis": analysis, "threats": threats})

# -------------------- Main --------------------

if __name__ == "__main__":
    print("🚀 Starting Network Copilot Flask app...")
    app.run(host="0.0.0.0", port=5000, debug=False)
