# -*- coding: utf-8 -*-
"""
Business-logic services layer.
Each service encapsulates a distinct responsibility (Single Responsibility Principle).
"""

import os
import sys
import json
import subprocess
import requests
from abc import ABC, abstractmethod


# ============================================================
# ABSTRACT BASE CLASS for Location Services (Polymorphism)
# ============================================================

class LocationService(ABC):
    """
    Abstract base class for all location-detection strategies.
    Demonstrates polymorphism — each subclass provides its own
    implementation of get_location().
    """

    @abstractmethod
    def get_location(self) -> dict:
        """Return location data or raise an exception."""
        pass


# ============================================================
# GEOCODING SERVICE
# ============================================================

class GeocodingService:
    """Service for geocoding addresses via OpenStreetMap Nominatim."""

    BASE_URL = 'https://nominatim.openstreetmap.org/search'
    USER_AGENT = 'LocationTrackerApp'
    DEFAULT_REGION = ', Lviv, Ukraine'

    def __init__(self, region: str = None):
        if region is not None:
            self.DEFAULT_REGION = region

    def geocode(self, address: str) -> tuple[float, float] | None:
        """
        Convert a text address to (latitude, longitude) coordinates.

        Args:
            address: Human-readable address string.

        Returns:
            Tuple (lat, lon) or None if address was not found.
        """
        params = {'q': address + self.DEFAULT_REGION, 'format': 'json'}
        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                headers={'User-Agent': self.USER_AGENT}
            )
            response.raise_for_status()
            results = response.json()
            if not results:
                return None
            return float(results[0]['lat']), float(results[0]['lon'])
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None

    def __repr__(self):
        return f"GeocodingService(region='{self.DEFAULT_REGION}')"


# ============================================================
# ROUTE SERVICE
# ============================================================

class RouteService:
    """
    Service for calculating driving routes via OSRM.
    Uses composition — receives a GeocodingService as a dependency.
    """

    OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

    def __init__(self, geocoding_service: GeocodingService = None):
        self._geocoding = geocoding_service or GeocodingService()

    def calculate_route(self, address1: str, address2: str) -> tuple[dict | None, str | None]:
        """
        Calculate a driving route between two addresses.

        Returns:
            (route_data, None) on success, or (None, error_message) on failure.
        """
        start = self._geocoding.geocode(address1)
        end = self._geocoding.geocode(address2)

        if not start or not end:
            return None, "Could not find one or both addresses"

        try:
            url = f"{self.OSRM_BASE_URL}/{start[1]},{start[0]};{end[1]},{end[0]}"
            params = {"overview": "full", "geometries": "geojson"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            route_data = response.json()

            if 'routes' not in route_data or not route_data['routes']:
                return None, "No route found"

            coordinates = route_data['routes'][0]['geometry']['coordinates']
            latlng_route = [[lat, lon] for lon, lat in coordinates]

            return {
                'route': latlng_route,
                'distance': route_data['routes'][0]['distance'],
                'duration': route_data['routes'][0]['duration']
            }, None
        except Exception as e:
            return None, f"Route calculation failed: {str(e)}"

    def calculate_route_by_coords(self, lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[dict | None, str | None]:
        """
        Calculate a driving route directly between two coordinates.

        Returns:
            (route_data, None) on success, or (None, error_message) on failure.
        """
        try:
            url = f"{self.OSRM_BASE_URL}/{lon1},{lat1};{lon2},{lat2}"
            params = {"overview": "full", "geometries": "geojson"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            route_data = response.json()

            if 'routes' not in route_data or not route_data['routes']:
                return None, "No route found"

            coordinates = route_data['routes'][0]['geometry']['coordinates']
            latlng_route = [[lat, lon] for lon, lat in coordinates]

            return {
                'route': latlng_route,
                'distance': route_data['routes'][0]['distance'],
                'duration': route_data['routes'][0]['duration']
            }, None
        except Exception as e:
            return None, f"Route calculation failed: {str(e)}"

    def __repr__(self):
        return f"RouteService(geocoding={self._geocoding!r})"


# ============================================================
# IP LOCATION SERVICE (inherits LocationService)
# ============================================================

class IPLocationService(LocationService):
    """Determines approximate location based on the client's IP address."""

    BASE_URL = 'https://ipapi.co'
    USER_AGENT = 'LocationTrackerApp'

    def get_location(self, client_ip: str = None) -> dict:
        """
        Fetch location for a given IP address from ipapi.co.

        Args:
            client_ip: The IP address of the client browser. If provided,
                       looks up that specific IP instead of the server's IP.

        Returns:
            Dict with 'latitude', 'longitude', 'city', 'ip' keys.

        Raises:
            ValueError: if coordinates are missing from the API response.
            requests.RequestException: on network errors.
        """
        if client_ip:
            # Look up the specific client IP: ipapi.co/{ip}/json/
            url = f'{self.BASE_URL}/{client_ip}/json/'
        else:
            url = f'{self.BASE_URL}/json/'

        response = requests.get(url, headers={'User-Agent': self.USER_AGENT})
        response.raise_for_status()
        data = response.json()

        if 'latitude' in data and 'longitude' in data:
            return {
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'city': data.get('city', 'Unknown'),
                'ip': data.get('ip', client_ip or 'Unknown'),
            }
        raise ValueError("Coordinates not found in IP API response")


# ============================================================
# BLUETOOTH LOCATION SERVICE (inherits LocationService)
# ============================================================

class BluetoothLocationService(LocationService):
    """
    Determines location by launching the Bluetooth tracker in a subprocess.
    Inherits from LocationService — demonstrates polymorphism.
    """

    def __init__(self, script_dir: str = None):
        self._script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))

    def get_location(self) -> dict:
        """
        Run bluetooth_tracker.py as a subprocess and return the result.

        Returns:
            Dict with location data from the Bluetooth scanner.
            Returns an error dict if Bluetooth is unavailable (e.g., on cloud servers).

        Raises:
            subprocess.TimeoutExpired: if scanning takes too long.
            json.JSONDecodeError: if output is not valid JSON.
        """
        try:
            result = subprocess.run(
                [sys.executable, '-c',
                 'import asyncio, json; '
                 'from bluetooth_tracker import locate_by_bluetooth; '
                 'r = asyncio.run(locate_by_bluetooth()); '
                 'print(json.dumps(r, ensure_ascii=False))'],
                capture_output=True, text=True, timeout=15,
                cwd=self._script_dir,
                encoding='utf-8'
            )

            if result.returncode != 0:
                return {'error': 'Bluetooth is not available in this environment', 'available': False}

            output_lines = result.stdout.strip().split('\n')
            json_line = output_lines[-1] if output_lines else '{}'
            return json.loads(json_line)
        except FileNotFoundError:
            return {'error': 'Bluetooth tracker script not found', 'available': False}
        except Exception as e:
            return {'error': f'Bluetooth unavailable: {str(e)}', 'available': False}
