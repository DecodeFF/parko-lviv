# -*- coding: utf-8 -*-
"""
Bluetooth Location Tracker (OOP version)
=========================================
Module for locating objects via Bluetooth Low Energy (BLE).

Classes:
    SignalProcessor   — converts RSSI to distance
    Trilaterator      — determines position from 3+ beacons
    BLEScanner        — scans for nearby BLE devices
    BluetoothTracker  — main facade combining all components

Usage:
    python bluetooth_tracker.py          — single scan
    python bluetooth_tracker.py --live   — continuous scanning every 5 sec
"""

import asyncio
import math
import sys
import requests
from datetime import datetime
from dataclasses import dataclass, field

# Fix Windows encoding issues when called from Flask
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from bleak import BleakScanner
except ImportError:
    print("=" * 60)
    print("ERROR: 'bleak' library is not installed!")
    print("Install it: pip install bleak")
    print("=" * 60)
    sys.exit(1)

# Disable SSL warnings for self-signed certificates
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class BeaconConfig:
    """Configuration for a known BLE beacon with fixed coordinates."""
    name: str
    lat: float
    lon: float


@dataclass
class ScannedDevice:
    """Represents a BLE device found during scanning."""
    address: str
    name: str
    rssi: int
    distance_m: float


@dataclass
class LocationResult:
    """Result of a location determination attempt."""
    latitude: float = 0.0
    longitude: float = 0.0
    accuracy_m: float = 0.0
    method: str = ""
    error: str = ""
    devices_found: int = 0
    nearest_device: dict = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.error == ""

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dictionary."""
        if not self.is_success:
            result = {"error": self.error}
            if self.devices_found > 0:
                result["devices_found"] = self.devices_found
            if self.nearest_device:
                result["nearest_device"] = self.nearest_device
            return result
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_m": self.accuracy_m,
            "method": self.method,
        }


# ============================================================
# SIGNAL PROCESSOR — RSSI to distance conversion
# ============================================================

class SignalProcessor:
    """
    Converts RSSI (signal strength) to estimated distance in meters.
    Uses the Log-Distance Path Loss Model.
    """

    def __init__(self, rssi_at_1m: int = -59, path_loss_exponent: float = 2.5):
        self._rssi_at_1m = rssi_at_1m
        self._path_loss_exponent = path_loss_exponent

    def rssi_to_distance(self, rssi: int) -> float:
        """
        Convert RSSI (dBm) to distance (meters).

        Formula:
            distance = 10 ^ ((RSSI_at_1m - RSSI) / (10 * n))
        """
        if rssi >= 0:
            return 0.0
        ratio = (self._rssi_at_1m - rssi) / (10 * self._path_loss_exponent)
        return round(math.pow(10, ratio), 2)

    def __repr__(self):
        return (f"SignalProcessor(rssi_at_1m={self._rssi_at_1m}, "
                f"path_loss_exponent={self._path_loss_exponent})")


# ============================================================
# TRILATERATOR — Position calculation from 3+ points
# ============================================================

class Trilaterator:
    """
    Determines coordinates of an object using trilateration.
    Requires at least 3 reference points with known coordinates
    and measured distances.
    """

    @staticmethod
    def trilaterate(beacons_with_distances: list[dict]) -> dict:
        """
        Calculate position from 3+ beacons.

        Args:
            beacons_with_distances: list of dicts with keys:
                lat, lon, distance

        Returns:
            {"latitude": float, "longitude": float, "accuracy_m": float}

        Raises:
            ValueError: if fewer than 3 beacons or they are collinear.
        """
        if len(beacons_with_distances) < 3:
            raise ValueError(
                f"Need at least 3 beacons for trilateration, "
                f"found only {len(beacons_with_distances)}"
            )

        b1, b2, b3 = beacons_with_distances[:3]

        # Convert degrees to meters (approx.)
        lat_ref = b1["lat"]
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(lat_ref))

        x1, y1 = 0.0, 0.0
        x2 = (b2["lat"] - b1["lat"]) * meters_per_lat
        y2 = (b2["lon"] - b1["lon"]) * meters_per_lon
        x3 = (b3["lat"] - b1["lat"]) * meters_per_lat
        y3 = (b3["lon"] - b1["lon"]) * meters_per_lon

        r1, r2, r3 = b1["distance"], b2["distance"], b3["distance"]

        A = 2 * (x2 - x1)
        B = 2 * (y2 - y1)
        C = r1**2 - r2**2 - x1**2 + x2**2 - y1**2 + y2**2
        D = 2 * (x3 - x2)
        E = 2 * (y3 - y2)
        F = r2**2 - r3**2 - x2**2 + x3**2 - y2**2 + y3**2

        denominator = A * E - B * D
        if abs(denominator) < 1e-10:
            raise ValueError("Beacons are collinear — trilateration impossible")

        x = (C * E - F * B) / denominator
        y = (A * F - D * C) / denominator

        result_lat = b1["lat"] + x / meters_per_lat
        result_lon = b1["lon"] + y / meters_per_lon

        # Accuracy estimate
        calc_distances = [
            math.sqrt((x - x1)**2 + (y - y1)**2),
            math.sqrt((x - x2)**2 + (y - y2)**2),
            math.sqrt((x - x3)**2 + (y - y3)**2),
        ]
        accuracy = sum(abs(c - r) for c, r in zip(calc_distances, [r1, r2, r3])) / 3

        return {
            "latitude": round(result_lat, 7),
            "longitude": round(result_lon, 7),
            "accuracy_m": round(accuracy, 2),
        }


# ============================================================
# BLE SCANNER
# ============================================================

class BLEScanner:
    """Scans for nearby BLE devices using the bleak library."""

    def __init__(self, signal_processor: SignalProcessor = None):
        self._signal_processor = signal_processor or SignalProcessor()

    async def scan(self, duration: float = 3.0) -> list[ScannedDevice]:
        """
        Scan for BLE devices and return a sorted list (nearest first).
        """
        print(f"[SCAN] Scanning BLE devices ({duration} sec)...")
        devices = await BleakScanner.discover(timeout=duration)

        results = []
        for device in devices:
            rssi = device.rssi if hasattr(device, 'rssi') else -100
            distance = self._signal_processor.rssi_to_distance(rssi)
            results.append(ScannedDevice(
                address=device.address,
                name=device.name or "Unknown device",
                rssi=rssi,
                distance_m=distance,
            ))

        results.sort(key=lambda d: d.distance_m)
        return results


# ============================================================
# BLUETOOTH TRACKER — Main Facade
# ============================================================

class BluetoothTracker:
    """
    Facade class that combines BLE scanning, beacon matching,
    and trilateration into a single high-level interface.
    """

    API_URL = "https://localhost:5001/api/coordinates"

    def __init__(
        self,
        known_beacons: dict[str, BeaconConfig] = None,
        signal_processor: SignalProcessor = None,
        scanner: BLEScanner = None,
        trilaterator: Trilaterator = None,
    ):
        self._known_beacons = known_beacons or {}
        self._signal_processor = signal_processor or SignalProcessor()
        self._scanner = scanner or BLEScanner(self._signal_processor)
        self._trilaterator = trilaterator or Trilaterator()

    async def locate(self) -> LocationResult:
        """
        Main method — scan BLE, match known beacons, trilaterate.
        """
        all_devices = await self._scanner.scan()

        if not all_devices:
            return LocationResult(error="No BLE devices found")

        self._print_devices(all_devices)

        if not self._known_beacons:
            print("\n[WARN] No beacons configured in known_beacons!")
            return LocationResult(
                error="Beacons not configured",
                devices_found=len(all_devices),
                nearest_device={
                    "address": all_devices[0].address,
                    "name": all_devices[0].name,
                    "rssi": all_devices[0].rssi,
                    "distance_m": all_devices[0].distance_m,
                } if all_devices else {}
            )

        matched = self._match_beacons(all_devices)

        if len(matched) == 0:
            return LocationResult(error="No known beacons detected")
        elif len(matched) == 1:
            return LocationResult(
                latitude=matched[0]["lat"],
                longitude=matched[0]["lon"],
                accuracy_m=matched[0]["distance"],
                method="single_beacon",
            )
        elif len(matched) == 2:
            avg_lat = (matched[0]["lat"] + matched[1]["lat"]) / 2
            avg_lon = (matched[0]["lon"] + matched[1]["lon"]) / 2
            return LocationResult(
                latitude=avg_lat,
                longitude=avg_lon,
                accuracy_m=max(m["distance"] for m in matched),
                method="two_beacons_average",
            )

        # 3+ beacons — trilateration
        try:
            result = self._trilaterator.trilaterate(matched)
            print(f"\n[POS] Position: {result['latitude']}, {result['longitude']}")
            print(f"      Accuracy: ~{result['accuracy_m']} m")
            return LocationResult(
                latitude=result["latitude"],
                longitude=result["longitude"],
                accuracy_m=result["accuracy_m"],
                method="trilateration",
            )
        except ValueError as e:
            return LocationResult(error=str(e))

    def send_to_server(self, location: LocationResult):
        """Send the determined location to the backend API."""
        if not location.is_success:
            print(f"[ERR] Error: {location.error}")
            return

        data = {"latitude": location.latitude, "longitude": location.longitude}
        try:
            response = requests.post(self.API_URL, json=data, verify=False)
            if response.status_code == 201:
                print(f"[OK] Coordinates sent to server: {data}")
            else:
                print(f"[ERR] Server error: {response.status_code}")
        except Exception as e:
            print(f"[ERR] Connection error: {e}")

    def _match_beacons(self, devices: list[ScannedDevice]) -> list[dict]:
        """Match scanned devices against known beacon MAC addresses."""
        matched = []
        for dev in devices:
            addr_upper = dev.address.upper()
            if addr_upper in self._known_beacons:
                beacon = self._known_beacons[addr_upper]
                matched.append({
                    "lat": beacon.lat,
                    "lon": beacon.lon,
                    "distance": dev.distance_m,
                    "name": beacon.name,
                    "rssi": dev.rssi,
                })
                print(f"\n[OK] Found beacon: {beacon.name} "
                      f"(RSSI: {dev.rssi} dBm, ~{dev.distance_m}m)")
        return matched

    @staticmethod
    def _print_devices(devices: list[ScannedDevice]):
        """Print a formatted table of scanned devices."""
        print(f"\n[BLE] Found {len(devices)} BLE devices:")
        print("-" * 65)
        print(f"{'Address':<20} {'Name':<20} {'RSSI':>6} {'Distance':>10}")
        print("-" * 65)
        for dev in devices:
            print(f"{dev.address:<20} {dev.name[:20]:<20} "
                  f"{dev.rssi:>4} dBm {dev.distance_m:>7.1f} m")


# ============================================================
# STANDALONE ENTRY POINT (kept for backward compatibility)
# ============================================================

# Known beacons configuration (replace with real MAC addresses)
KNOWN_BEACONS = {
    # "AA:BB:CC:DD:EE:01": BeaconConfig("Beacon 1 (Entrance)", 49.8397, 24.0297),
    # "AA:BB:CC:DD:EE:02": BeaconConfig("Beacon 2 (Corridor)", 49.8398, 24.0299),
    # "AA:BB:CC:DD:EE:03": BeaconConfig("Beacon 3 (Room)",     49.8396, 24.0298),
}


async def locate_by_bluetooth() -> dict:
    """Wrapper function for backward compatibility with app.py subprocess calls."""
    tracker = BluetoothTracker(known_beacons=KNOWN_BEACONS)
    result = await tracker.locate()
    return result.to_dict()


async def main():
    """Entry point."""
    live_mode = "--live" in sys.argv
    tracker = BluetoothTracker(known_beacons=KNOWN_BEACONS)

    if live_mode:
        print("=" * 60)
        print("[LIVE] CONTINUOUS SCANNING MODE")
        print("       Press Ctrl+C to stop")
        print("=" * 60)

        while True:
            location = await tracker.locate()
            tracker.send_to_server(location)
            print(f"\n[WAIT] Next scan in 5 seconds...\n")
            await asyncio.sleep(5)
    else:
        print("=" * 60)
        print("[BLE] BLUETOOTH LOCATION TRACKER")
        print("      Single scan")
        print("=" * 60)

        location = await tracker.locate()
        if location.is_success:
            tracker.send_to_server(location)
        return location.to_dict()


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[STOP] Scanning stopped by user.")
