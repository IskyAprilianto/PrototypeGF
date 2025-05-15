from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS
import time
import json
import requests
from bson import ObjectId
from bson.json_util import dumps
from pymongo.errors import PyMongoError
import logging
import os
import threading

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable CORS for all routes
CORS(app)

# MongoDB Atlas Configuration
MONGO_URI = "mongodb+srv://StarlithMonitoring:Starlith136@canopyamonitoring.9bjswab.mongodb.net/?retryWrites=true&w=majority&appName=CanopyaMonitoring"

# Initialize MongoDB connection
try:
    client = MongoClient(MONGO_URI,
                         serverSelectionTimeoutMS=5000,
                         socketTimeoutMS=30000,
                         connectTimeoutMS=10000)
    client.server_info()
    db = client['iot_data']
    collection = db['sensor_readings']
    logger.info("Successfully connected to MongoDB")
except PyMongoError as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise SystemExit(1)

# Relay control variables
relay_active = False
relay_lock = threading.Lock()


def control_esp32_relay(
        duration=30):  # Durasi relay diperbarui menjadi 15 detik
    """Mengirim perintah ke ESP32 untuk mengaktifkan relay"""
    try:
        # Ganti dengan URL ngrok ESP32 Anda
        esp32_url = "https://ca02-114-79-3-0.ngrok-free.app/activate_relay"
        response = requests.get(
            esp32_url, params={'duration': duration},
            timeout=10)  # Timeout diatur 10 detik untuk HTTP request
        logger.info(f"ESP32 relay response: {response.text}")
        if response.status_code == 200:
            return True
        else:
            raise Exception(f"ESP32 returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Gagal mengontrol relay di ESP32: {str(e)}")
        return False


@app.route('/')
def home():
    return "Backend Flask is Active!"


@app.route('/whatsapp_command', methods=['POST'])
def whatsapp_command():
    data = request.get_json()
    logger.info(f"Received WhatsApp message: {data}")

    if 'Body' not in data or 'From' not in data:
        return jsonify({
            "status": "error",
            "message": "Missing required fields"
        }), 400

    command = data['Body'].strip().lower()
    sender = data['From']

    # Daftar perintah yang valid
    valid_commands = {
        'open': {
            'url': "https://ca02-114-79-3-0.ngrok-free.app/open_servo",
            'success_msg': "Greenhouse opened.",
            'error_msg': "Failed to open greenhouse"
        },
        'close': {
            'url': "https://ca02-114-79-3-0.ngrok-free.app/close_servo",
            'success_msg': "Greenhouse closed.",
            'error_msg': "Failed to close greenhouse"
        },
        'auto': {
            'url': "https://ca02-114-79-3-0.ngrok-free.app/auto_mode",
            'success_msg': "Automatic mode activated.",
            'error_msg': "Failed to activate auto mode"
        },
        'siram': {
            'action': 'relay',
            'success_msg': "Relay activated for 15 seconds.",
            'error_msg': "Failed to activate relay"
        }
    }

    if command not in valid_commands:
        return jsonify({
            "status":
            "error",
            "message":
            "Unknown command. Valid commands: " +
            ", ".join(valid_commands.keys())
        }), 400

    cmd_info = valid_commands[command]

    try:
        if command == 'siram':
            # Handle relay control for 15 seconds
            success = control_esp32_relay(15)  # Relay untuk 15 detik
            if not success:
                raise Exception("Failed to control relay")
        else:
            # Handle servo commands
            response = requests.get(cmd_info['url'], timeout=10)
            logger.info(f"ESP32 Response: {response.text}")
            if response.status_code != 200:
                raise Exception(
                    f"ESP32 returned status {response.status_code}")

        return jsonify({
            "status": "success",
            "message": cmd_info['success_msg']
        }), 200

    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {str(e)}")
        return jsonify({
            "status": "error",
            "message": cmd_info['error_msg']
        }), 500


@app.route('/add_data', methods=['POST'])
def add_data():
    try:
        logger.info("Received request /add_data")

        if not request.is_json:
            return jsonify({"error": "Request must be in JSON format"}), 415

        data = request.get_json()

        required_fields = ['temperature', 'humidity', 'ldr_value']
        if not all(field in data for field in required_fields):
            return jsonify({
                "error": "Incomplete data",
                "required_fields": required_fields
            }), 400

        try:
            temp = float(data['temperature'])
            hum = float(data['humidity'])
            ldr = float(data['ldr_value'])
        except ValueError as e:
            return jsonify({
                "error": "Data must be numeric",
                "example_format": {
                    "temperature": 25.5,
                    "humidity": 60.0,
                    "ldr_value": 1023.0
                }
            }), 400

        sensor_data = {
            'temperature': temp,
            'humidity': hum,
            'ldr_value': ldr,
            'timestamp': time.time(),
            'status': 'active'
        }

        result = collection.insert_one(sensor_data)
        response_data = {
            **sensor_data, '_id': str(result.inserted_id),
            'inserted_at': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }

        # Kirim data ke UBIDOTS
        ubidots_payload = {'temperature': temp, 'humidity': hum, 'light': ldr}
        ubidots_headers = {
            'X-Auth-Token': 'BBUS-X22dYuktZNwot2UyXDlW0br7H6FOIF',
            'Content-Type': 'application/json'
        }
        requests.post(
            'https://industrial.api.ubidots.com/api/v1.6/devices/canopyamonitoring',
            json=ubidots_payload,
            headers=ubidots_headers)

        return jsonify({
            "status": "success",
            "message": "Data successfully saved",
            "data": response_data
        }), 201

    except PyMongoError as e:
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get_data', methods=['GET'])
def get_data():
    try:
        limit = int(request.args.get('limit', 10))
        sort_order = int(request.args.get('sort', -1))

        cursor = collection.find().sort('_id', sort_order).limit(limit)
        data = list(cursor)

        processed_data = []
        for item in data:
            processed_data.append({
                '_id':
                str(item['_id']),
                'temperature':
                item['temperature'],
                'humidity':
                item['humidity'],
                'ldr_value':
                item['ldr_value'],
                'status':
                item.get('status', 'active'),
                'timestamp':
                item['timestamp'],
                'formatted_timestamp':
                time.strftime('%Y-%m-%d %H:%M:%S',
                              time.localtime(item['timestamp']))
            })

        return jsonify({
            "status": "success",
            "count": len(processed_data),
            "data": processed_data
        }), 200

    except PyMongoError as e:
        return jsonify({"status": "error", "message": "Database Error"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
