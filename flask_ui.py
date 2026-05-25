# -*- coding: utf-8 -*-
"""
Alternative Flask UI (legacy).
Refactored to use shared OOP models.
"""

from flask import Flask, render_template, request, jsonify, render_template_string
from datetime import datetime

from models import DatabaseManager, CoordinateRepository

# app = Flask(__name__)
#
# Commented-out legacy code preserved below
# def connect_db():
#     return psycopg2.connect(
#         dbname="coordinates",
#         user="postgres",
#         password="123",
#         host="localhost"
#     )
#
# @app.route('/')
# def index():
#     return render_template('index.html')
#
# @app.route('/add_coordinate', methods=['POST'])
# def add_coordinate():
#     data = request.get_json()
#     latitude = data['latitude']
#     longitude = data['longitude']
#     conn = connect_db()
#     cur = conn.cursor()
#     cur.execute("INSERT INTO coordinates (latitude, longitude) VALUES (%s, %s)", (latitude, longitude))
#     conn.commit()
#     cur.close()
#     conn.close()
#     return {'status': 'success'}, 200
#
# @app.route('/api/last_coordinate')
# def last_coordinate():
#     conn = connect_db()
#     cur = conn.cursor()
#     cur.execute("SELECT latitude, longitude, timestamp FROM coordinates ORDER BY id DESC LIMIT 1")
#     row = cur.fetchone()
#     cur.close()
#     conn.close()
#     if row:
#         return jsonify({"latitude": row[0], "longitude": row[1], "timestamp": row[2]})
#     else:
#         return jsonify({"error": "No data"}), 404
#
# if __name__ == '__main__':
#     app.run(debug=True)

app = Flask(__name__)

# --- Dependency Injection ---
db_manager = DatabaseManager()
coord_repo = CoordinateRepository(db_manager)


@app.route('/')
def index():
    return render_template('index.html')

# @app.route('/')
# def index():
#     return render_template_string('''
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <title>Location on Map</title>
#             <meta charset="utf-8" />
#             <meta name="viewport" content="width=device-width, initial-scale=1.0">
#
#             <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
#             <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
#
#             <style>
#                 #map { height: 100vh; }
#             </style>
#         </head>
#         <body>
#             <div id="map"></div>
#
#             <script>
#                 var map = L.map('map').setView([49.8397, 24.0297], 13);
#
#                 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
#                     maxZoom: 19,
#                     attribution: '© OpenStreetMap'
#                 }).addTo(map);
#
#                 var marker = L.circleMarker([49.8397, 24.0297], {radius: 10, color: 'red'}).addTo(map);
#
#                 async function fetchLocation() {
#                     const response = await fetch('/get_latest');
#                     const data = await response.json();
#                     if (data.latitude && data.longitude) {
#                         marker.setLatLng([data.latitude, data.longitude]);
#                         map.panTo([data.latitude, data.longitude]);
#                     }
#                 }
#
#                 setInterval(fetchLocation, 2000);
#             </script>
#         </body>
#         </html>
#     ''')


@app.route('/get_latest')
def get_latest():
    record = coord_repo.get_latest()
    if record:
        return jsonify({"latitude": float(record["latitude"]), "longitude": float(record["longitude"])})
    else:
        return jsonify({})


@app.route('/add_coordinate', methods=['POST'])
def add_coordinate():
    data = request.get_json()
    latitude = data['latitude']
    longitude = data['longitude']
    coord_repo.insert(float(latitude), float(longitude))
    return {'status': 'success'}, 200


if __name__ == '__main__':
    app.run(debug=True)
