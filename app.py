# -*- coding: utf-8 -*-
"""
Main Flask application.
Uses OOP services and repository classes via Dependency Injection.
"""

import os
from flask import Flask, render_template, request, jsonify
import subprocess
from datetime import datetime
import random

from models import DatabaseManager, CoordinateRepository
from services import (
    GeocodingService,
    RouteService,
    IPLocationService,
    BluetoothLocationService,
)



def create_app() -> Flask:
    """
    Application Factory pattern — creates and configures the Flask app.
    Registers all routes with injected service dependencies.
    """
    app = Flask(__name__)

    # --- Dependency Injection: create shared service instances ---
    mongo_uri = os.environ.get('MONGODB_URL') or os.environ.get('MONGODB_URI')
    
    # Якщо змінні Railway не налаштовані правильно, використовуємо наданий внутрішній URL Railway
    if not mongo_uri:
        if os.environ.get('RAILWAY_ENVIRONMENT_NAME') or os.environ.get('PORT'):
            # Ми на Railway
            mongo_uri = 'mongodb://mongo:CJymzscBBoTTJSGTOsnIrUgTNqJVNrnA@mainline.proxy.rlwy.net:56322'
        else:
            # Ми на локальному комп'ютері
            mongo_uri = 'mongodb://localhost:27017/'
    db_manager = DatabaseManager(
        uri=mongo_uri,
        db_name='test'
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
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip:
                if ',' in client_ip:
                    client_ip = client_ip.split(',')[0].strip()
                if client_ip in ('127.0.0.1', '::1', 'localhost'):
                    client_ip = None
            
            location = ip_location_service.get_location(client_ip)
            location['detected_client_ip'] = client_ip
            location['all_headers'] = {k: v for k, v in request.headers.items() if k.lower() in ('x-forwarded-for', 'x-real-ip', 'cf-connecting-ip', 'client-ip')}
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

    @app.route('/api/coordinates/stats', methods=['GET'])
    def coordinate_stats():
        """Return aggregated statistics using MongoDB Aggregation Pipeline."""
        try:
            stats = coord_repo.get_stats()
            if not stats:
                return jsonify({"message": "No coordinates found for aggregation"}), 200
            return jsonify(stats)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/location/random_route', methods=['GET'])
    def get_random_route():
        """Generate a random real route within Lviv bounding box."""
        # Lviv rough bounding box
        min_lat, max_lat = 49.79, 49.88
        min_lon, max_lon = 23.95, 24.06
        
        lat1 = random.uniform(min_lat, max_lat)
        lon1 = random.uniform(min_lon, max_lon)
        lat2 = random.uniform(min_lat, max_lat)
        lon2 = random.uniform(min_lon, max_lon)
        
        result, error = route_service.calculate_route_by_coords(lat1, lon1, lat2, lon2)
        if error:
            return jsonify({'error': error}), 500
        return jsonify(result)

    @app.route('/api/debug/env', methods=['GET'])
    def debug_env():
        """Debug endpoint to check available MongoDB environment variables."""
        mongo_vars = {k: v for k, v in os.environ.items() if 'MONGO' in k.upper()}
        return jsonify({
            "mongo_variables_found": mongo_vars,
            "current_uri_used": mongo_uri,
            "message": "Якщо mongo_variables_found порожній, значить Railway не передає базу даних у веб-сервіс."
        })

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