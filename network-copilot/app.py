from flask import Flask, render_template, jsonify
from metrics_collector import start_collection
from analyzer import analyze_network
from llm_wrapper import get_llm_diagnosis
from device_discovery import discover_devices
import sqlite3
import os
import subprocess
import re

app = Flask(__name__)

# Start metrics collection in background
start_collection(interval=5)

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/api/metrics')
def get_metrics():
    """Return current network metrics."""
    analysis = analyze_network()
    
    if not analysis:
        return jsonify({
            "status": "waiting",
            "message": "Collecting metrics... Please wait."
        })
    
    return jsonify({
        "status": "ok",
        "current_latency": round(analysis["current_latency"], 1),
        "baseline_latency": round(analysis["baseline_latency"], 1),
        "latency_spike_percent": round(analysis["latency_spike_percent"], 1),
        "packet_loss": round(analysis["packet_loss"], 1),
        "has_issues": analysis["has_issues"]
    })

@app.route('/api/diagnosis')
def get_diagnosis():
    """Get LLM-powered network diagnosis."""
    diagnosis = get_llm_diagnosis()
    
    return jsonify({
        "diagnosis": diagnosis
    })


@app.route('/api/devices')
def api_devices():
    """Return discovered devices."""
    devs = discover_devices()
    return jsonify({ 'devices': devs })


@app.route('/api/device/<ip>/metrics')
def api_device_metrics(ip):
    """Return recent metrics for a device from the DB."""
    try:
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('''
            SELECT timestamp, latency, packet_loss, up
            FROM device_metrics
            WHERE device_ip = ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (ip,))
        rows = c.fetchall()
        conn.close()

        data = []
        for r in rows:
            data.append({
                'timestamp': r[0],
                'latency': r[1],
                'packet_loss': r[2],
                'up': bool(r[3])
            })

        return jsonify({ 'device': ip, 'metrics': data })
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500

output = subprocess.check_output(["arp", "-a"]).decode()
devices = re.findall(r"\(([\d\.]+)\) at ([\w:]+)", output)

for device in devices:
    ip, mac = device
    print(f"Device IP: {ip}, MAC: {mac}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
