"""Network monitoring: rule-based detection of unknown devices, IP/MAC conflicts and risky open ports."""
import ipaddress, re

MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")
RISKY_PORTS = {21: "FTP", 23: "Telnet", 445: "SMB", 3389: "RDP", 5900: "VNC"}


def _alert(conn, device_id, alert_type, severity, description):
    """Insert an alert unless an identical one is still open for the device (avoids repeat spam)."""
    dup = conn.execute(
        "SELECT id FROM security_alerts WHERE device_id=? AND alert_type=? AND status='Open'",
        (device_id, alert_type)).fetchone()
    if dup:
        return False
    conn.execute(
        "INSERT INTO security_alerts (device_id, alert_type, severity, description) VALUES (?,?,?,?)",
        (device_id, alert_type, severity, description))
    conn.execute("INSERT INTO activities (title, description) VALUES (?,?)",
                 ("Network Security", f"{severity}: {alert_type} - {description}"))
    return True


def process_scan(conn, observed):
    """observed: list of {name, ip, mac, type, open_ports}. Returns (devices_seen, new_alerts)."""
    new_alerts = seen = 0
    for d in observed:
        mac = str(d.get("mac", "")).strip().lower().replace("-", ":")
        try:
            ip = str(ipaddress.ip_address(str(d.get("ip", "")).strip()))
        except ValueError:
            continue
        if not MAC_RE.match(mac):
            continue
        name = str(d.get("name") or "Unknown device")[:80]
        dtype = str(d.get("type") or "Unknown")[:40]
        row = conn.execute("SELECT * FROM network_devices WHERE mac_address=?", (mac,)).fetchone()
        clash = conn.execute(
            "SELECT id, mac_address FROM network_devices WHERE ip_address=? AND mac_address!=? "
            "AND last_seen >= datetime('now','-15 minutes')", (ip, mac)).fetchone()
        if row is None:
            cur = conn.execute(
                "INSERT INTO network_devices (device_name, ip_address, mac_address, device_type, status) "
                "VALUES (?,?,?,?, 'Unknown')", (name, ip, mac, dtype))
            dev_id = cur.lastrowid
            new_alerts += _alert(conn, dev_id, "Unknown Device", "High",
                                 f"Unrecognised device {mac} joined the network at {ip}.")
        else:
            dev_id = row["id"]
            conn.execute("UPDATE network_devices SET ip_address=?, last_seen=CURRENT_TIMESTAMP WHERE id=?",
                         (ip, dev_id))
        if clash:
            conn.execute("UPDATE network_devices SET status='Suspicious' WHERE id IN (?,?)", (dev_id, clash["id"]))
            new_alerts += _alert(conn, dev_id, "IP/MAC Conflict", "Critical",
                                 f"{ip} is claimed by {mac} and {clash['mac_address']} (possible ARP spoofing).")
        for port in d.get("open_ports") or []:
            if port in RISKY_PORTS:
                sev = "High" if port in (23, 3389, 445) else "Medium"
                new_alerts += _alert(conn, dev_id, f"Risky Port {port}", sev,
                                     f"{name} ({ip}) exposes {RISKY_PORTS[port]} on port {port}.")
        seen += 1
    return seen, new_alerts


def demo_scan():
    """Simulated scan result (a real deployment would feed ARP/nmap/router data to process_scan)."""
    rogue = "de:ad:be:ef:00:99"  # fixed so repeated demo scans do not create endless devices
    return [
        {"name": "Main Router", "ip": "192.168.1.1", "mac": "aa:bb:cc:00:00:01", "type": "Router", "open_ports": [80, 443]},
        {"name": "Manager Laptop", "ip": "192.168.1.20", "mac": "aa:bb:cc:00:00:02", "type": "Laptop", "open_ports": []},
        {"name": "Lobby Camera", "ip": "192.168.1.30", "mac": "aa:bb:cc:00:00:03", "type": "Camera", "open_ports": [554, 23]},
        {"name": "Unknown", "ip": "192.168.1.77", "mac": rogue, "type": "Unknown", "open_ports": [3389]},
    ]
