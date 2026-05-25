# -*- coding: utf-8 -*-
"""
Coordinate Simulator (OOP version)
Simulates GPS movement and sends coordinates to the backend API.

Usage:
    .venv/Scripts/python.exe simulator.py
"""

import random
import time
import requests
from datetime import datetime

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CoordinateSimulator:
    """
    Simulates smooth GPS movement around a starting point.
    Generates realistic coordinate updates and sends them to the server.
    """

    def __init__(
        self,
        api_url: str = "https://localhost:5001/api/coordinates",
        start_lat: float = 49.8397,
        start_lon: float = 24.0297,
        step_range: float = 0.0005,
        interval_sec: float = 4.0,
    ):
        self._api_url = api_url
        self._current_lat = start_lat
        self._current_lon = start_lon
        self._step_range = step_range
        self._interval_sec = interval_sec

    @property
    def current_position(self) -> tuple[float, float]:
        """Return the current (latitude, longitude) as a tuple."""
        return self._current_lat, self._current_lon

    def generate_next(self) -> dict:
        """Generate the next coordinate by applying a small random offset."""
        self._current_lat += random.uniform(-self._step_range, self._step_range)
        self._current_lon += random.uniform(-self._step_range, self._step_range)
        return {
            'latitude': self._current_lat,
            'longitude': self._current_lon,
        }

    def send_coordinate(self, data: dict):
        """Send a single coordinate to the backend API."""
        try:
            response = requests.post(self._api_url, json=data, verify=False)
            if response.status_code == 201:
                print(f"[{datetime.now().isoformat()}] Sent: {data}")
            else:
                print(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Connection error: {e}")

    def clear_database(self):
        """Delete all coordinates from the database via API."""
        print("Clearing old coordinates...")
        try:
            requests.delete(self._api_url, verify=False)
            print("Database cleared.")
        except Exception as e:
            print(f"Could not clear database: {e}")

    def run(self):
        """Main loop — clear database, then continuously generate and send coordinates."""
        self.clear_database()
        print("Starting coordinate simulator...")

        while True:
            coord = self.generate_next()
            self.send_coordinate(coord)
            time.sleep(self._interval_sec)

    def __repr__(self):
        return (f"CoordinateSimulator(lat={self._current_lat:.4f}, "
                f"lon={self._current_lon:.4f}, interval={self._interval_sec}s)")


if __name__ == '__main__':
    simulator = CoordinateSimulator()
    simulator.run()