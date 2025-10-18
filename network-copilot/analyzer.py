import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data.db"

def get_recent_metrics(seconds=30):
    """Get metrics from the last N seconds."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(seconds=seconds)
        
        c.execute('''
            SELECT latency, packet_loss, rx_bytes, tx_bytes, timestamp
            FROM metrics
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        ''', (cutoff_time.isoformat(),))
        
        rows = c.fetchall()
        conn.close()
        
        return rows
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        return []

def get_baseline_latency(seconds=60):
    """Get average latency from recent history (baseline)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(seconds=seconds)
        
        c.execute('''
            SELECT AVG(latency)
            FROM metrics
            WHERE timestamp > ?
        ''', (cutoff_time.isoformat(),))
        
        result = c.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        return 40  # Default baseline
    except Exception as e:
        print(f"Error getting baseline: {e}")
        return 40

def analyze_network():
    """Analyze network metrics and detect anomalies."""
    recent = get_recent_metrics(seconds=30)
    
    if not recent:
        return None
    
    # Get current metrics (most recent)
    current = recent[0]
    latency, packet_loss = current[0], current[1]
    
    # Get baseline
    baseline_latency = get_baseline_latency(seconds=60)
    
    # Calculate anomalies
    latency_spike = ((latency - baseline_latency) / baseline_latency) * 100 if baseline_latency > 0 else 0
    
    # Build anomaly summary
    issues = []
    
    if latency_spike > 30:
        issues.append(f"latency spike of {latency_spike:.0f}% (now {latency:.1f}ms, baseline {baseline_latency:.1f}ms)")
    
    if packet_loss > 2:
        issues.append(f"packet loss of {packet_loss:.1f}%")
    
    # Summary
    if issues:
        summary = "Detected issues: " + ", ".join(issues)
    else:
        summary = f"Network health normal. Latency: {latency:.1f}ms, No packet loss."
    
    return {
        "current_latency": latency,
        "baseline_latency": baseline_latency,
        "latency_spike_percent": latency_spike,
        "packet_loss": packet_loss,
        "summary": summary,
        "has_issues": len(issues) > 0
    }

if __name__ == "__main__":
    analysis = analyze_network()
    if analysis:
        print(analysis["summary"])
    else:
        print("No metrics available yet. Run metrics_collector.py first.")
