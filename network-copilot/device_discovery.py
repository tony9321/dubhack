
import subprocess
import re
import socket

def discover_devices():
    """Discover devices on the local network using `ip neigh` and `arp -a` as fallback.
    Returns a list of dicts: { ip, mac, hostname }
    """
    devices = {}
    try:
        out = subprocess.check_output(['ip', 'neigh'], text=True)
        for line in out.splitlines():
            # format: 10.0.0.5 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
            parts = line.split()
            if len(parts) >= 1:
                ip = parts[0]
                mac = None
                if 'lladdr' in parts:
                    idx = parts.index('lladdr')
                    if idx+1 < len(parts):
                        mac = parts[idx+1]
                hostname = None
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except Exception:
                    hostname = None

                devices[ip] = { 'ip': ip, 'mac': mac, 'hostname': hostname }
    except Exception:
        # fallback to arp -a
        try:
            out = subprocess.check_output(['arp', '-a'], text=True)
            matches = re.findall(r"([\w\-]+) \((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-f:]+)", out)
            for m in matches:
                name, ip, mac = m
                devices[ip] = { 'ip': ip, 'mac': mac, 'hostname': name }
        except Exception:
            pass

    return list(devices.values())

def ping_host(ip, count=1, timeout=2):
    """Ping a host once and return (latency_ms, packet_loss_pct, up_bool)."""
    try:
        # Use single ping packet
        result = subprocess.run(['ping', '-c', str(count), '-W', str(timeout), ip], capture_output=True, text=True)
        out = result.stdout
        latency = None
        packet_loss = 100.0
        up = False
        for line in out.splitlines():
            if 'packet loss' in line:
                try:
                    packet_loss = float(line.split('%')[0].strip().split()[-1])
                except Exception:
                    packet_loss = 100.0
            if 'time=' in line:
                # example: 64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=3.45 ms
                m = re.search(r'time=([0-9\.]+)\s*ms', line)
                if m:
                    try:
                        latency = float(m.group(1))
                    except Exception:
                        latency = None
        up = (packet_loss < 100.0)
        return latency, packet_loss, up
    except Exception:
        return None, None, False
