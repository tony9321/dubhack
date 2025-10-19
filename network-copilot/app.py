from flask import Flask, render_template, jsonify, Response
from metrics_collector import start_collection
from analyzer import analyze_network, get_recent_metrics
from llm_wrapper import get_llm_diagnosis
from device_discovery import discover_devices
import sqlite3
import re

app = Flask(__name__)

# Start metrics collection in background (don’t crash the app if it fails)
try:
    start_collection(interval=5)
except Exception as e:
    print(f"[metrics] background collection failed to start: {e}")

def _rate_latency(ms: float) -> str:
    if ms is None:
        return "unknown"
    if ms < 20: return "excellent"
    if ms < 50: return "good"
    if ms < 100: return "fair"
    return "poor"

def _infer_device_type(hostname: str | None, mac: str | None) -> str:
    hn = (hostname or "").lower()
    mac = (mac or "").lower()

    # Hostname heuristics (expanded)
    if any(k in hn for k in ["iphone", "ios"]): return "phone (iPhone/iOS)"
    if any(k in hn for k in ["ipad"]): return "tablet (iPad/iOS)"
    if any(k in hn for k in ["android", "pixel", "galaxy", "oneplus", "samsung"]): return "phone (Android)"
    if any(k in hn for k in ["macbook", "imac", "mac-mini", "macpro", "macos"]): return "laptop/desktop (Mac)"
    if any(k in hn for k in ["intel", "nuc"]): return "desktop (Intel)"
    if any(k in hn for k in ["windows", "win", "dell", "hp", "lenovo", "thinkpad", "xps", "surface", "msi", "acer", "asus"]): return "laptop/desktop (Windows/PC)"
    if any(k in hn for k in ["laptop", "notebook"]): return "laptop (generic)"
    if any(k in hn for k in ["desktop", "pc"]): return "desktop (generic)"
    if any(k in hn for k in ["roku", "apple-tv", "firetv", "chromecast", "tv"]): return "streaming/TV"
    if any(k in hn for k in ["ps5", "ps4", "xbox", "switch"]): return "game console"

    # OUI (MAC prefix) heuristics (expanded)
    oui = mac[:8] if len(mac) >= 8 else ""
    apple_ouis = {"88:e9:fe", "d8:30:62", "8c:85:90", "f0:18:98", "a4:5e:60", "b8:8d:12", "ac:bc:32"}
    samsung_ouis = {"1c:5a:6b", "14:32:d1", "30:07:4d", "f4:09:d8", "00:16:6c"}
    google_ouis = {"3c:5a:b4", "f4:f5:d8", "a4:77:33", "e4:f0:42"}
    intel_ouis = {"00:1b:21", "00:13:e8", "00:03:47", "00:15:17"}
    dell_ouis = {"00:14:22", "00:1a:a0", "00:21:70"}
    hp_ouis = {"00:1d:60", "00:23:7d", "00:26:2d"}
    lenovo_ouis = {"00:09:6b", "00:0a:e4", "00:13:02"}
    asus_ouis = {"00:17:31", "00:1a:92", "00:21:91"}
    if oui in apple_ouis: return "Apple device (Mac/iOS)"
    if oui in samsung_ouis: return "Samsung device (Android)"
    if oui in google_ouis: return "Google device (Android/IoT)"
    if oui in intel_ouis: return "Intel device (PC/NIC)"
    if oui in dell_ouis: return "Dell device (PC)"
    if oui in hp_ouis: return "HP device (PC)"
    if oui in lenovo_ouis: return "Lenovo device (PC)"
    if oui in asus_ouis: return "ASUS device (PC)"

    # Fallback
    return "unknown"

@app.route('/favicon.ico')
def favicon():
    """Serve a tiny inline SVG favicon to avoid 404s."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64'>"
        "<defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'><stop offset='0%' stop-color='#667eea'/><stop offset='100%' stop-color='#764ba2'/></linearGradient></defs>"
        "<rect width='64' height='64' rx='12' fill='url(#g)'/>"
        "<circle cx='32' cy='32' r='18' fill='none' stroke='white' stroke-width='3'/>"
        "<path d='M14 32 H50' stroke='white' stroke-width='3' stroke-linecap='round'/>"
        "<path d='M32 14 V50' stroke='white' stroke-width='3' stroke-linecap='round'/>"
        "</svg>"
    )
    return Response(svg, mimetype='image/svg+xml')

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

    current = float(analysis.get("current_latency", 0.0))
    baseline = float(analysis.get("baseline_latency", current or 0.0))
    loss = float(analysis.get("packet_loss", 0.0))
    spike = float(analysis.get("latency_spike_percent",
                               (max(0.0, (current - baseline) / baseline * 100) if baseline else 0.0)))
    has_issues = bool(analysis.get("has_issues", (spike > 30.0 or loss > 2.0)))

    payload = {
        "status": "ok",
        "current_latency": round(current, 1),
        "baseline_latency": round(baseline, 1),
        "latency_spike_percent": round(spike, 1),
        "packet_loss": round(loss, 1),
        "has_issues": has_issues,
        # Aliases some frontends expect:
        "latency_ms": round(current, 1),
        "baseline_ms": round(baseline, 1),
        "spike_pct": round(spike, 1),
        "packet_loss_pct": round(loss, 1),
        # Extras:
        "latency_rating": _rate_latency(current),
        "usual_latency_range_ms": {
            "min": round(max(0.0, baseline - 10.0), 1),
            "max": round(baseline + 10.0, 1)
        }
    }
    return jsonify(payload)

@app.route('/api/diagnosis')
def get_diagnosis():
    """Get LLM-powered network diagnosis (with fallback)."""
    diagnosis = get_llm_diagnosis()
    return jsonify({ "diagnosis": diagnosis })

@app.route('/api/summary')
def api_summary():
    """Summarize last 5 minutes of samples for quick trend view."""
    try:
        rows = get_recent_metrics(seconds=300)  # (latency, packet_loss, rx_bytes, tx_bytes, timestamp)
        if not rows:
            return jsonify({
                "status": "waiting",
                "message": "No recent samples to summarize"
            })

        latencies = [r[0] for r in rows if r[0] is not None]
        losses = [r[1] for r in rows if r[1] is not None]

        def _percentile(arr, p):
            if not arr:
                return None
            arr = sorted(arr)
            k = (len(arr) - 1) * (p / 100.0)
            f = int(k)
            c = min(f + 1, len(arr) - 1)
            if f == c:
                return arr[int(k)]
            return arr[f] + (arr[c] - arr[f]) * (k - f)

        avg_latency = sum(latencies)/len(latencies) if latencies else None
        max_latency = max(latencies) if latencies else None
        p95_latency = _percentile(latencies, 95) if latencies else None
        avg_loss = sum(losses)/len(losses) if losses else None

        return jsonify({
            "status": "ok",
            "window_seconds": 300,
            "samples": len(rows),
            "avg_latency": round(avg_latency, 1) if avg_latency is not None else None,
            "p95_latency": round(p95_latency, 1) if p95_latency is not None else None,
            "max_latency": round(max_latency, 1) if max_latency is not None else None,
            "avg_packet_loss": round(avg_loss, 2) if avg_loss is not None else None
        })
    except Exception as e:
        return jsonify({"status":"error", "error": str(e)}), 500

@app.route('/api/devices')
def api_devices():
    """Return discovered devices, with simple type inference."""
    try:
        devs = discover_devices()  # expected dicts with keys: ip, mac, hostname
        enriched = []
        for d in devs:
            ip = d.get("ip")
            mac = d.get("mac")
            hostname = d.get("hostname")
            dtype = _infer_device_type(hostname, mac)
            enriched.append({ **d, "type": dtype })
        return jsonify({ 'devices': enriched })
    except Exception as e:
        # Keep UI responsive even if discovery fails
        return jsonify({ 'devices': [], 'error': str(e) }), 200

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

# Removed ARP scan on import (it can block/fail in some environments)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)