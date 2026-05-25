# -*- coding: utf-8 -*-
"""
Main Flask application.
Uses OOP services and repository classes via Dependency Injection.
"""

import os
from flask import Flask, render_template, request, jsonify
import subprocess
from datetime import datetime

from models import DatabaseManager, CoordinateRepository
from services import (
    GeocodingService,
    RouteService,
    IPLocationService,
    BluetoothLocationService,
)

# ============================================================
# APPLICATION FACTORY
# ============================================================

def create_app() -> Flask:
    """
    Application Factory pattern — creates and configures the Flask app.
    Registers all routes with injected service dependencies.
    """
    app = Flask(__name__)

    # --- Dependency Injection: create shared service instances ---
    db_manager = DatabaseManager(
        uri=os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/'),
        db_name='kursova_tracker'
    )
    coord_repo = CoordinateRepository(db_manager)
    route_service = RouteService(GeocodingService())
    ip_location_service = IPLocationService()
    bluetooth_service = BluetoothLocationService()

    # --- Routes ---

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/route', methods=['POST'])
    def get_route():
        data = request.get_json()
        address1 = data.get('address1')
        address2 = data.get('address2')

        if not address1 or not address2:
            return jsonify({'error': 'Both addresses are required'}), 400

        result, error = route_service.calculate_route(address1, address2)
        if error:
            code = 404 if 'No route' in error else (400 if 'not find' in error.lower() else 500)
            return jsonify({'error': error}), code
        return jsonify(result)

    @app.route('/api/coordinates', methods=['POST'])
    def add_coordinate():
        data = request.get_json()
        if not data or 'latitude' not in data or 'longitude' not in data:
            return jsonify({"error": "Latitude and longitude are required"}), 400

        try:
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
        except ValueError:
            return jsonify({"error": "Invalid coordinate values"}), 400

        try:
            record = coord_repo.insert(latitude, longitude)
            return jsonify({
                "message": "Coordinate added successfully",
                "id": record["id"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "timestamp": record["timestamp"].isoformat()
            }), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/coordinates', methods=['DELETE'])
    def clear_coordinates():
        try:
            coord_repo.delete_all()
            return jsonify({"message": "Coordinates cleared"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/coordinates/latest', methods=['GET'])
    def last_coordinate():
        try:
            record = coord_repo.get_latest()
            if not record:
                return jsonify({"message": "No coordinates found"}), 200
            return jsonify(record)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/location/ip', methods=['GET'])
    def get_ip_location():
        try:
            location = ip_location_service.get_location()
            return jsonify(location)
        except ValueError as e:
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/location/bluetooth', methods=['GET'])
    def get_bluetooth_location():
        try:
            data = bluetooth_service.get_location()
            return jsonify(data)
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Bluetooth scan took too long'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/coordinates/track', methods=['GET'])
    def current_track():
        try:
            coordinates = coord_repo.get_all()
            return jsonify({"track": coordinates})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == '__main__':
    app = create_app()
    debug_mode = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    port = int(os.environ.get('PORT', 5001))
    use_ssl = os.environ.get('USE_SSL', 'true').lower() == 'true'
    ssl_ctx = 'adhoc' if use_ssl else None
    app.run(host='0.0.0.0', port=port, debug=debug_mode, ssl_context=ssl_ctx)