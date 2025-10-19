import os
import sqlite3
import datetime
from typing import Dict, Any, List

from device_discovery import discover_devices

# Conservative global thresholds (keep in sync with app defaults, but duplicated to avoid import cycles)
GLOBAL_THRESHOLDS = {
    'latency': 200.0,   # ms
    'loss': 5.0         # percent
}


def _mask_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    mac = mac.lower()
    parts = mac.split(':')
    if len(parts) >= 3:
        return ':'.join(parts[:3]) + ':xx:xx:xx'
    return mac[:8] + 'xx:xx:xx'


def _percentile(arr: List[float], p: float) -> float | None:
    if not arr:
        return None
    arr = sorted(arr)
    k = (len(arr) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return arr[int(k)]
    return arr[f] + (arr[c] - arr[f]) * (k - f)


def build_security_snapshot(window_seconds: int = 900) -> Dict[str, Any]:
    """Build a compact per-device snapshot for AI/heuristic security analysis.

    Returns:
        dict with keys: window_seconds, generated_at, devices: [...]
    """
    now = datetime.datetime.now()
    cutoff = (now - datetime.timedelta(seconds=window_seconds)).isoformat()

    devices = discover_devices() or []  # [{ip, mac, hostname}]

    snapshot_devices: List[Dict[str, Any]] = []
    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    for d in devices:
        ip = d.get('ip')
        mac = d.get('mac')
        hostname = d.get('hostname')

        c.execute('''
            SELECT timestamp, latency, packet_loss, rx_bytes, tx_bytes
            FROM device_metrics
            WHERE device_ip = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (ip, cutoff))
        rows = c.fetchall()

        latencies = [r[1] for r in rows if r[1] is not None]
        losses = [r[2] for r in rows if r[2] is not None]

        # Compute avg bandwidth over window using first and last sample
        avg_rx_bps = None
        avg_tx_bps = None
        if len(rows) >= 2 and rows[0][3] is not None and rows[-1][3] is not None and rows[0][4] is not None and rows[-1][4] is not None:
            try:
                t_new = datetime.datetime.fromisoformat(rows[0][0])
                t_old = datetime.datetime.fromisoformat(rows[-1][0])
                dt = (t_new - t_old).total_seconds()
                if dt > 0:
                    avg_rx_bps = (rows[0][3] - rows[-1][3]) / dt
                    avg_tx_bps = (rows[0][4] - rows[-1][4]) / dt
            except Exception:
                pass

        # Threshold violations count
        violations = 0
        for r in rows:
            l = r[1]
            pl = r[2]
            if (l is not None and l > GLOBAL_THRESHOLDS['latency']) or (pl is not None and pl > GLOBAL_THRESHOLDS['loss']):
                violations += 1

        last_seen = rows[0][0] if rows else None

        device_entry = {
            'ip': ip,
            'masked_mac': _mask_mac(mac),
            'hostname': hostname,
            'last_seen': last_seen,
            'latency_avg_ms': round(sum(latencies)/len(latencies), 1) if latencies else None,
            'latency_p95_ms': round(_percentile(latencies, 95), 1) if latencies else None,
            'latency_max_ms': round(max(latencies), 1) if latencies else None,
            'loss_avg_pct': round(sum(losses)/len(losses), 2) if losses else None,
            'sustained_threshold_violations': violations,
            'avg_rx_bps': round(avg_rx_bps, 2) if avg_rx_bps is not None else None,
            'avg_tx_bps': round(avg_tx_bps, 2) if avg_tx_bps is not None else None,
            'threshold_exceeded': violations >= 1,
            'is_new_device': len(rows) == 0,
        }
        snapshot_devices.append(device_entry)

    conn.close()

    return {
        'window_seconds': window_seconds,
        'generated_at': now.isoformat(),
        'devices': snapshot_devices,
        'thresholds': GLOBAL_THRESHOLDS
    }


def detect_suspects(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic suspect detection as a fallback or complement to LLM analysis."""
    suspects: List[Dict[str, Any]] = []
    observations: List[str] = []

    for dev in snapshot.get('devices', []):
        reasons = []
        score = 0

        # High outbound tx rate (possible exfil)
        tx = dev.get('avg_tx_bps') or 0
        rx = dev.get('avg_rx_bps') or 0
        if tx > 1_000_000 and tx > 2 * (rx + 1):  # >1 Mbps and dominantly outbound
            reasons.append(f"high outbound {int(tx)} bps")
            score += 35

        # Sustained threshold violations
        if (dev.get('sustained_threshold_violations') or 0) >= 3:
            reasons.append("sustained latency/loss violations")
            score += 25

        # New device with activity
        if dev.get('is_new_device') and (tx > 200_000 or rx > 200_000):
            reasons.append("new device with traffic")
            score += 20

        # Missing hostname / unknown
        if not dev.get('hostname'):
            reasons.append("unknown hostname")
            score += 10

        if score > 0:
            suspects.append({
                'ip': dev.get('ip'),
                'risk_score': min(100, score),
                'reasons': reasons,
                'recommended_actions': [
                    "verify the device identity",
                    "check for firmware updates",
                    "limit cloud syncs or camera uploads if unintended"
                ]
            })

    # Simple global observations
    if not snapshot.get('devices'):
        observations.append('no devices in snapshot')

    return {
        'suspected_devices': sorted(suspects, key=lambda x: x['risk_score'], reverse=True)[:10],
        'global_observations': observations,
        'confidence': 'medium' if suspects else 'low'
    }
