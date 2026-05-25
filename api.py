from flask import Flask, request, jsonify
import psycopg2
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


def connect_db():
    return psycopg2.connect(
        dbname="coordinates",
        user="postgres",
        password="123",
        host="localhost"
    )


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

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO coordinates (latitude, longitude, timestamp) VALUES (%s, %s, %s) RETURNING id",
            (latitude, longitude, datetime.now())
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({
            "message": "Coordinate added successfully",
            "id": new_id,
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": datetime.now().isoformat()
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/coordinates/latest', methods=['GET'])
def last_coordinate():
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, latitude, longitude, timestamp 
            FROM coordinates 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return jsonify({"message": "No coordinates found"}), 404

        return jsonify({
            "id": row[0],
            "latitude": row[1],
            "longitude": row[2],
            "timestamp": row[3].isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/coordinates/track', methods=['GET'])
def current_track():
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, latitude, longitude, timestamp 
            FROM coordinates 
            ORDER BY timestamp DESC
        """)
        rows = cur.fetchall()
        coordinates = [{
            "id": row[0],
            "latitude": row[1],
            "longitude": row[2],
            "timestamp": row[3].isoformat()
        } for row in rows]

        return jsonify({"track": coordinates})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)