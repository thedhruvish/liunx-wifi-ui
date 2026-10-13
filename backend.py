#!/usr/bin/env python3
"""
Backend module for Wi-Fi and Bluetooth management on Linux Debian.
Uses NetworkManager (nmcli) and BlueZ (bluetoothctl) under the hood.
"""

import os
import re
import time
import subprocess
from typing import Dict, List, Optional, Tuple, Set


def run_cmd(cmd: List[str], timeout: int = 15) -> Tuple[int, str, str]:
    """Execute a system command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as e:
        return -1, "", str(e)


def format_bytes_speed(bytes_per_sec: float) -> str:
    """Format bytes per second into human readable string."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    elif bytes_per_sec < 1024 * 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"


# ==========================================
# Wi-Fi Backend
# ==========================================

class WiFiBackend:
    def __init__(self):
        self.last_rx = 0
        self.last_tx = 0
        self.last_time = 0.0
        self.cached_iface: Optional[str] = None

    def get_wifi_interface(self) -> Optional[str]:
        """Detect current Wi-Fi interface (connected or available)."""
        # First check connected wifi
        code, out, _ = run_cmd(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'dev', 'status'])
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(':')
                if len(parts) >= 3 and parts[1] == 'wifi' and parts[2] == 'connected':
                    self.cached_iface = parts[0]
                    return parts[0]

            # If not connected, find any wifi device
            for line in out.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] == 'wifi':
                    self.cached_iface = parts[0]
                    return parts[0]

        # Fallback to sysfs
        try:
            net_dir = '/sys/class/net'
            if os.path.isdir(net_dir):
                for iface in os.listdir(net_dir):
                    wireless_dir = os.path.join(net_dir, iface, 'wireless')
                    phy_dir = os.path.join(net_dir, iface, 'phy80211')
                    if os.path.isdir(wireless_dir) or os.path.isdir(phy_dir):
                        self.cached_iface = iface
                        return iface
        except Exception:
            pass

        return self.cached_iface

    def is_wifi_enabled(self) -> bool:
        """Check if Wi-Fi radio is turned on."""
        code, out, _ = run_cmd(['nmcli', 'radio', 'wifi'])
        if code == 0:
            return out.strip().lower() == 'enabled'
        return True

    def set_wifi_enabled(self, enabled: bool) -> Tuple[bool, str]:
        """Turn Wi-Fi radio on or off."""
        state = 'on' if enabled else 'off'
        code, out, err = run_cmd(['nmcli', 'radio', 'wifi', state])
        if code == 0:
            return True, f"Wi-Fi switched {state}"
        return False, err or out

    def get_saved_connections(self) -> Set[str]:
        """Get set of SSIDs for saved connections."""
        saved = set()
        code, out, _ = run_cmd(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'])
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] in ('802-11-wireless', 'wifi'):
                    saved.add(parts[0])
        return saved

    def scan_networks(self, rescan: bool = False) -> List[Dict]:
        """
        Scan and return available Wi-Fi networks.
        rescan=False reads cached results instantaneously.
        """
        rescan_opt = 'yes' if rescan else 'no'
        cmd = [
            'nmcli', '-t', '-f',
            'SSID,BSSID,CHAN,RATE,SIGNAL,BARS,SECURITY,IN-USE',
            'device', 'wifi', 'list',
            '--rescan', rescan_opt
        ]
        code, out, _ = run_cmd(cmd, timeout=12 if rescan else 5)
        if code != 0 or not out:
            return []

        saved_ssids = self.get_saved_connections()
        networks: Dict[str, Dict] = {}

        for line in out.splitlines():
            if not line.strip():
                continue
            # Regex split by unescaped colon
            parts = re.split(r'(?<!\\):', line)
            parts = [p.replace(r'\:', ':').strip() for p in parts]

            if len(parts) < 8:
                continue

            ssid = parts[0]
            bssid = parts[1]
            channel = parts[2]
            rate = parts[3]
            try:
                signal = int(parts[4])
            except ValueError:
                signal = 0
            bars = parts[5]
            security = parts[6] if parts[6] else "Open"
            in_use = (parts[7] == '*')

            # Ignore empty/hidden SSID unless in use
            display_name = ssid if ssid else "Hidden Network"
            key = ssid if ssid else bssid

            net_info = {
                'ssid': display_name,
                'raw_ssid': ssid,
                'bssid': bssid,
                'channel': channel,
                'rate': rate,
                'signal': signal,
                'bars': bars,
                'security': security,
                'is_secured': security != "Open" and security != "--",
                'in_use': in_use,
                'is_saved': ssid in saved_ssids
            }

            # If duplicate SSID, keep the one that is currently connected or has stronger signal
            if key in networks:
                if in_use or (not networks[key]['in_use'] and signal > networks[key]['signal']):
                    networks[key] = net_info
            else:
                networks[key] = net_info

        # Sort: connected first, then by signal strength descending
        result = list(networks.values())
        result.sort(key=lambda n: (1 if n['in_use'] else 0, n['signal']), reverse=True)
        return result

    def get_connected_details(self) -> Optional[Dict]:
        """Get rich details about the currently connected Wi-Fi network."""
        iface = self.get_wifi_interface()
        if not iface:
            return None

        code, out, _ = run_cmd(['nmcli', '-s', 'dev', 'show', iface])
        if code != 0 or not out:
            return None

        data = {}
        for line in out.splitlines():
            if ':' in line:
                key, val = line.split(':', 1)
                data[key.strip()] = val.strip()

        # Check if connected
        state = data.get('GENERAL.STATE', '')
        if 'connected' not in state.lower():
            return None

        conn_name = data.get('GENERAL.CONNECTION', '')
        ip4 = data.get('IP4.ADDRESS[1]', 'N/A')
        gateway = data.get('IP4.GATEWAY', 'N/A')
        dns = data.get('IP4.DNS[1]', 'N/A')
        hwaddr = data.get('GENERAL.HWADDR', 'N/A')

        # Get active SSID and bitrate from wifi list
        active_net = None
        for n in self.scan_networks(rescan=False):
            if n['in_use']:
                active_net = n
                break

        ssid = active_net['ssid'] if active_net else (conn_name or "Connected Wi-Fi")
        signal = active_net['signal'] if active_net else 0
        rate = active_net['rate'] if active_net else "N/A"
        security = active_net['security'] if active_net else "Protected"

        return {
            'interface': iface,
            'connection_name': conn_name,
            'ssid': ssid,
            'bssid': active_net['bssid'] if active_net else 'N/A',
            'signal': signal,
            'rate': rate,
            'security': security,
            'ip4': ip4,
            'gateway': gateway,
            'dns': dns,
            'hwaddr': hwaddr
        }

    def get_live_speed(self) -> Dict[str, float]:
        """
        Calculate current download & upload throughput in bytes/second.
        Reads from /sys/class/net/<iface>/statistics.
        """
        iface = self.get_wifi_interface()
        now = time.time()
        if not iface:
            return {'rx_speed': 0.0, 'tx_speed': 0.0, 'rx_fmt': '0 B/s', 'tx_fmt': '0 B/s'}

        rx_path = f"/sys/class/net/{iface}/statistics/rx_bytes"
        tx_path = f"/sys/class/net/{iface}/statistics/tx_bytes"

        try:
            with open(rx_path, 'r') as f:
                rx_bytes = int(f.read().strip())
            with open(tx_path, 'r') as f:
                tx_bytes = int(f.read().strip())
        except Exception:
            return {'rx_speed': 0.0, 'tx_speed': 0.0, 'rx_fmt': '0 B/s', 'tx_fmt': '0 B/s'}

        if self.last_time == 0.0:
            self.last_rx = rx_bytes
            self.last_tx = tx_bytes
            self.last_time = now
            return {'rx_speed': 0.0, 'tx_speed': 0.0, 'rx_fmt': '0 B/s', 'tx_fmt': '0 B/s'}

        dt = now - self.last_time
        if dt <= 0:
            dt = 1.0

        rx_speed = max(0.0, (rx_bytes - self.last_rx) / dt)
        tx_speed = max(0.0, (tx_bytes - self.last_tx) / dt)

        self.last_rx = rx_bytes
        self.last_tx = tx_bytes
        self.last_time = now

        return {
            'rx_speed': rx_speed,
            'tx_speed': tx_speed,
            'rx_fmt': format_bytes_speed(rx_speed),
            'tx_fmt': format_bytes_speed(tx_speed)
        }

    def connect_network(self, ssid: str, password: Optional[str] = None, bssid: Optional[str] = None) -> Tuple[bool, str]:
        """Connect to a Wi-Fi network."""
        cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
        if password:
            cmd.extend(['password', password])
        if bssid:
            cmd.extend(['bssid', bssid])

        iface = self.get_wifi_interface()
        if iface:
            cmd.extend(['ifname', iface])

        code, out, err = run_cmd(cmd, timeout=25)
        if code == 0:
            return True, f"Successfully connected to {ssid}"
        
        # Check if failed because secrets were required
        err_msg = err or out or "Connection failed"
        if "Secrets were required" in err_msg or "password" in err_msg.lower():
            return False, "Password required or incorrect password."
        return False, err_msg

    def disconnect_network(self) -> Tuple[bool, str]:
        """Disconnect active Wi-Fi connection."""
        iface = self.get_wifi_interface()
        if not iface:
            return False, "No Wi-Fi interface found"

        code, out, err = run_cmd(['nmcli', 'device', 'disconnect', iface])
        if code == 0:
            return True, "Wi-Fi disconnected"
        return False, err or out


# ==========================================
# Bluetooth Backend
# ==========================================

class BluetoothBackend:
    def __init__(self):
        pass

    def get_controller_status(self) -> Dict:
        """Get default Bluetooth controller status."""
        code, out, _ = run_cmd(['bluetoothctl', 'show'], timeout=4)
        if code != 0 or not out:
            return {
                'available': False,
                'powered': False,
                'name': 'No Bluetooth Controller',
                'mac': 'N/A',
                'discoverable': False
            }

        powered = False
        discoverable = False
        name = "Bluetooth Controller"
        mac = "N/A"

        for line in out.splitlines():
            line_str = line.strip()
            if line_str.startswith("Controller"):
                parts = line_str.split()
                if len(parts) >= 2:
                    mac = parts[1]
            elif line_str.startswith("Name:"):
                name = line_str.split("Name:", 1)[1].strip()
            elif line_str.startswith("Powered:"):
                powered = ("yes" in line_str.lower())
            elif line_str.startswith("Discoverable:"):
                discoverable = ("yes" in line_str.lower())

        return {
            'available': True,
            'powered': powered,
            'name': name,
            'mac': mac,
            'discoverable': discoverable
        }

    def set_powered(self, enabled: bool) -> Tuple[bool, str]:
        """Toggle Bluetooth power on or off."""
        action = 'power on' if enabled else 'power off'
        code, out, err = run_cmd(['bluetoothctl', *action.split()], timeout=8)
        if code == 0:
            return True, f"Bluetooth {action}"
        return False, err or out

    def get_paired_devices(self) -> List[Dict]:
        """Get list of paired Bluetooth devices."""
        code, out, _ = run_cmd(['bluetoothctl', 'devices', 'Paired'], timeout=4)
        if code != 0 or not out:
            return []

        devices = []
        for line in out.splitlines():
            line_str = line.strip()
            if line_str.startswith("Device"):
                parts = line_str.split(None, 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    devices.append(self.get_device_details(mac, default_name=name, is_paired=True))
        return devices

    def get_all_devices(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Return (paired_devices, nearby_unpaired_devices).
        """
        code, out, _ = run_cmd(['bluetoothctl', 'devices'], timeout=4)
        if code != 0 or not out:
            return [], []

        paired_macs = set()
        code_p, out_p, _ = run_cmd(['bluetoothctl', 'devices', 'Paired'], timeout=4)
        if code_p == 0 and out_p:
            for line in out_p.splitlines():
                if line.startswith("Device"):
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        paired_macs.add(parts[1])

        paired_list = []
        nearby_list = []

        for line in out.splitlines():
            line_str = line.strip()
            if line_str.startswith("Device"):
                parts = line_str.split(None, 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    is_paired = mac in paired_macs
                    dev_info = self.get_device_details(mac, default_name=name, is_paired=is_paired)
                    if is_paired:
                        paired_list.append(dev_info)
                    else:
                        nearby_list.append(dev_info)

        return paired_list, nearby_list

    def get_device_details(self, mac: str, default_name: str = "Unknown", is_paired: bool = False) -> Dict:
        """Fetch details for a specific device."""
        code, out, _ = run_cmd(['bluetoothctl', 'info', mac], timeout=3)
        connected = False
        paired = is_paired
        icon = "bluetooth"
        rssi = 0
        name = default_name

        if code == 0 and out:
            for line in out.splitlines():
                line_str = line.strip()
                if line_str.startswith("Name:"):
                    name = line_str.split("Name:", 1)[1].strip()
                elif line_str.startswith("Alias:"):
                    name = line_str.split("Alias:", 1)[1].strip()
                elif line_str.startswith("Connected:"):
                    connected = ("yes" in line_str.lower())
                elif line_str.startswith("Paired:"):
                    paired = ("yes" in line_str.lower())
                elif line_str.startswith("Icon:"):
                    icon = line_str.split("Icon:", 1)[1].strip()
                elif line_str.startswith("RSSI:"):
                    try:
                        rssi = int(line_str.split("RSSI:", 1)[1].strip())
                    except ValueError:
                        pass

        # Map bluetooth icon to user-friendly label
        icon_type = "device"
        if "audio" in icon or "headset" in icon or "headphone" in icon:
            icon_type = "headset"
        elif "phone" in icon:
            icon_type = "phone"
        elif "keyboard" in icon or "input" in icon:
            icon_type = "keyboard"
        elif "mouse" in icon:
            icon_type = "mouse"

        return {
            'mac': mac,
            'name': name,
            'paired': paired,
            'connected': connected,
            'icon': icon_type,
            'raw_icon': icon,
            'rssi': rssi
        }

    def scan_for_devices(self, timeout_sec: int = 6) -> Tuple[bool, str]:
        """Trigger bluetooth discovery scan."""
        code, out, err = run_cmd(['bluetoothctl', f'--timeout={timeout_sec}', 'scan', 'on'], timeout=timeout_sec + 3)
        if code == 0:
            return True, "Scan completed"
        return False, err or out

    def pair_device(self, mac: str) -> Tuple[bool, str]:
        """Pair and trust a device."""
        # Pair
        code, out, err = run_cmd(['bluetoothctl', 'pair', mac], timeout=15)
        # Also trust so future connections work automatically
        run_cmd(['bluetoothctl', 'trust', mac], timeout=5)
        if code == 0 or "Pairing successful" in out:
            return True, f"Paired with {mac}"
        return False, err or out

    def connect_device(self, mac: str) -> Tuple[bool, str]:
        """Connect to a bluetooth device."""
        code, out, err = run_cmd(['bluetoothctl', 'connect', mac], timeout=12)
        if code == 0 or "Connection successful" in out:
            return True, f"Connected to {mac}"
        return False, err or out

    def disconnect_device(self, mac: str) -> Tuple[bool, str]:
        """Disconnect a bluetooth device."""
        code, out, err = run_cmd(['bluetoothctl', 'disconnect', mac], timeout=8)
        if code == 0 or "Successful disconnected" in out:
            return True, f"Disconnected {mac}"
        return False, err or out

    def remove_device(self, mac: str) -> Tuple[bool, str]:
        """Unpair/Remove a bluetooth device."""
        code, out, err = run_cmd(['bluetoothctl', 'remove', mac], timeout=6)
        if code == 0:
            return True, f"Removed device {mac}"
        return False, err or out
