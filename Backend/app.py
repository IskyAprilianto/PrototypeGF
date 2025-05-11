from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS
import time
import logging
import os
from datetime import datetime

# Inisialisasi aplikasi Flask
app = Flask(_name_)

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)

# Aktifkan CORS
CORS(app)

# Konfigurasi MongoDB
MONGO_URI = "mongodb+srv://StarlithMonitoring:Starlith136@canopyamonitoring.9bjswab.mongodb.net/?retryWrites=true&w=majority&appName=CanopyaMonitoring"
try:
    client = MongoClient(MONGO_URI)
    db = client['iot_data']
    collection = db['sensor_readings']
    logger.info("Berhasil terhubung ke MongoDB")
except Exception as e:
    logger.error(f"Gagal terhubung ke MongoDB: {str(e)}")
    raise SystemExit(1)

# Variabel Kontrol di Memory
current_mode = "otomatis"  # 'manual' atau 'otomatis'
current_control = "tutup"  # 'buka' atau 'tutup'

# Root Endpoint
@app.route('/')
def home():
    return "Backend Flask Aktif - Sistem Kontrol Rumah Kaca"

# Endpoint untuk Menyimpan Data Sensor
@app.route('/add_data', methods=['POST'])
def add_data():
    try:
        data = request.get_json()
        sensor_data = {
            'temperature': float(data['temperature']),
            'humidity': float(data['humidity']),
            'ldr_value': float(data['ldr_value']),
            'roof_status': data.get('roof_status', 'unknown'),
            'mode': data.get('mode', 'otomatis'),
            'timestamp': time.time(),
            'status': 'active'
        }
        collection.insert_one(sensor_data)
        return jsonify({"status": "success", "data": sensor_data}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Endpoint untuk Mengambil Data Sensor
@app.route('/get_data', methods=['GET'])
def get_data():
    try:
        limit = int(request.args.get('limit', 10))
        cursor = collection.find().sort('_id', -1).limit(limit)
        data = []
        for item in cursor:
            data.append({
                '_id': str(item['_id']),
                'temperature': item['temperature'],
                'humidity': item['humidity'],
                'ldr_value': item['ldr_value'],
                'roof_status': item.get('roof_status', 'unknown'),
                'mode': item.get('mode', 'otomatis'),
                'timestamp': item['timestamp'],
                'formatted_timestamp': datetime.fromtimestamp(item['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            })
        return jsonify({"status": "success", "count": len(data), "data": data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Endpoint untuk Mengatur Mode
@app.route('/set_mode', methods=['POST'])
def set_mode():
    global current_mode
    data = request.json
    mode = data.get('mode', '').lower()
    if mode not in ['manual', 'otomatis']:
        return jsonify({"status": "error", "message": "Mode harus 'manual' atau 'otomatis'"}), 400
    current_mode = mode
    return jsonify({"status": "success", "mode": current_mode}), 200

# Endpoint untuk Mendapatkan Mode Saat Ini
@app.route('/get_mode', methods=['GET'])
def get_mode():
    return jsonify({"status": "success", "mode": current_mode}), 200

# Endpoint untuk Mengatur Control Manual
@app.route('/set_control', methods=['POST'])
def set_control():
    global current_control
    data = request.json
    control = data.get('control', '').lower()
    if control not in ['buka', 'tutup']:
        return jsonify({"status": "error", "message": "Control harus 'buka' atau 'tutup'"}), 400
    current_control = control
    return jsonify({"status": "success", "control": current_control}), 200

# Endpoint untuk Mendapatkan Control Saat Ini
@app.route('/get_control', methods=['GET'])
def get_control():
    return jsonify({"status": "success", "control": current_control}), 200

# Jalankan Aplikasi
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
