from flask import Flask, render_template, jsonify
from metrics_collector import start_collection
from analyzer import analyze_network
from llm_wrapper import get_llm_diagnosis
import os

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
