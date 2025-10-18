import sqlite3
import subprocess
import time
import threading
from datetime import datetime
import os

DB_PATH = "data.db"

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            latency REAL,
            packet_loss REAL,
            rx_bytes INTEGER,
            tx_bytes INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_ping_metrics():
    """Get latency and packet loss from ping."""
    try:
        # Ping 8.8.8.8 (Google DNS) 4 times
        result = subprocess.run(
            ["ping", "-c", "4", "8.8.8.8"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout
        
        # Parse latency (avg from the summary line)
        latency = None
        packet_loss = 0.0
        
        for line in output.split('\n'):
            if 'min/avg/max' in line:
                # Example: min/avg/max/stddev = 10.1/15.5/20.3/4.2 ms
                parts = line.split('=')[1].strip().split('/')
                latency = float(parts[1])  # avg
            if '%' in line and 'packet' in line.lower():
                # Example: 0% packet loss
                packet_loss = float(line.split('%')[0].split()[-1])
        
        return latency, packet_loss
    except Exception as e:
        print(f"Error getting ping metrics: {e}")
        return None, None

def get_throughput_metrics():
    """Get RX/TX bytes from /proc/net/dev."""
    try:
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()
        
        # Sum up all non-loopback interfaces
        rx_total = 0
        tx_total = 0
        
        for line in lines[2:]:  # Skip header
            if 'lo' in line:  # Skip loopback
                continue
            
            # Format: "  iface: rx_bytes rx_packets rx_errs ... tx_bytes tx_packets ..."
            parts = line.split()
            if len(parts) >= 10:
                try:
                    rx_total += int(parts[1])
                    tx_total += int(parts[9])
                except ValueError:
                    pass
        
        return rx_total, tx_total
    except Exception as e:
        print(f"Error getting throughput metrics: {e}")
        return 0, 0

def store_metrics():
    """Store metrics to database."""
    latency, packet_loss = get_ping_metrics()
    rx_bytes, tx_bytes = get_throughput_metrics()
    
    if latency is not None:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO metrics (latency, packet_loss, rx_bytes, tx_bytes)
            VALUES (?, ?, ?, ?)
        ''', (latency, packet_loss, rx_bytes, tx_bytes))
        conn.commit()
        conn.close()
        
        print(f"[{datetime.now()}] Latency: {latency:.1f}ms, Loss: {packet_loss:.1f}%, RX: {rx_bytes}, TX: {tx_bytes}")

def start_collection(interval=5):
    """Start background metrics collection."""
    init_db()
    
    def collector():
        while True:
            try:
                store_metrics()
                time.sleep(interval)
            except Exception as e:
                print(f"Error in collector: {e}")
                time.sleep(interval)
    
    thread = threading.Thread(target=collector, daemon=True)
    thread.start()
    print(f"Metrics collection started (interval: {interval}s)")

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
    
    # Collect for 60 seconds for testing
    start_collection(interval=5)
    try:
        for i in range(12):
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nCollection stopped.")
