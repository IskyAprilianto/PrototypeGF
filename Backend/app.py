from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS
import time
import json
from bson import ObjectId
from bson.json_util import dumps
from pymongo.errors import PyMongoError
import logging
import os

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable CORS untuk semua route
CORS(app)

# Konfigurasi MongoDB Atlas
MONGO_URI = "mongodb+srv://StarlithMonitoring:Starlith136@canopyamonitoring.9bjswab.mongodb.net/?retryWrites=true&w=majority&appName=CanopyaMonitoring"

# Inisialisasi koneksi MongoDB dengan timeout dan retry
try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,  # 5 detik timeout
        socketTimeoutMS=30000,  # 30 detik socket timeout
        connectTimeoutMS=10000  # 10 detik connection timeout
    )

    # Test koneksi
    client.server_info()  # Akan memunculkan exception jika gagal
    db = client['iot_data']
    collection = db['sensor_readings']
    logger.info("Berhasil terhubung ke MongoDB")
except PyMongoError as e:
    logger.error(f"Gagal terhubung ke MongoDB: {str(e)}")
    raise SystemExit(1)  # Keluar jika tidak bisa konek ke MongoDB


@app.route('/')
def home():
    return "Backend Flask Aktif!"  # Menampilkan pesan di URL utama


@app.route('/add_data', methods=['POST'])
def add_data():
    try:
        logger.info("Menerima request /add_data")

        # Validasi content-type
        if not request.is_json:
            logger.warning("Request bukan JSON")
            return jsonify({"error": "Request harus dalam format JSON"}), 415

        data = request.get_json()
        logger.debug(f"Data diterima: {data}")

        # Validasi payload
        required_fields = ['temperature', 'humidity', 'ldr_value']
        if not all(field in data for field in required_fields):
            logger.warning(f"Data tidak lengkap, required: {required_fields}")
            return jsonify({
                "error": "Data tidak lengkap",
                "required_fields": required_fields
            }), 400

        # Validasi tipe data
        try:
            temp = float(data['temperature'])
            hum = float(data['humidity'])
            ldr = float(data['ldr_value'])
        except ValueError as e:
            logger.warning(f"Data tidak valid: {str(e)}")
            return jsonify({
                "error": "Data harus berupa angka",
                "contoh_format": {
                    "temperature": 25.5,
                    "humidity": 60.0,
                    "ldr_value": 1023.0
                }
            }), 400

        # Membuat dokumen untuk disimpan
        sensor_data = {
            'temperature': temp,
            'humidity': hum,
            'ldr_value': ldr,
            'timestamp': time.time(),
            'status': 'active'
        }
        logger.debug(f"Data yang akan disimpan: {sensor_data}")

        # Insert ke MongoDB dengan error handling khusus
        try:
            result = collection.insert_one(sensor_data)
            logger.info(
                f"Data berhasil disimpan dengan ID: {result.inserted_id}")

            # Menyiapkan response
            response_data = {
                **sensor_data, '_id': str(result.inserted_id),
                'inserted_at': time.strftime("%Y-%m-%d %H:%M:%S",
                                             time.localtime())
            }

            return jsonify({
                "status": "success",
                "message": "Data berhasil disimpan",
                "data": response_data
            }), 201

        except PyMongoError as e:
            logger.error(f"Gagal menyimpan ke MongoDB: {str(e)}")
            return jsonify({
                "status": "error",
                "error": "Database Error",
                "message": "Gagal menyimpan data ke database"
            }), 500

    except Exception as e:
        logger.error(f"Error pada /add_data: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": "Internal Server Error",
            "message": str(e)
        }), 500


@app.route('/get_data', methods=['GET'])
def get_data():
    try:
        logger.info("Menerima request /get_data")

        # Ambil parameter query
        limit = int(request.args.get('limit', 10))
        sort_order = int(request.args.get('sort', -1))  # -1 untuk descending

        # Query database dengan error handling
        try:
            cursor = collection.find().sort('timestamp',
                                            sort_order).limit(limit)
            data = list(cursor)

            # Konversi ObjectId dan format timestamp
            processed_data = []
            for item in data:
                processed_item = {
                    '_id':
                    str(item['_id']),  # Convert ObjectId to string
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
                }
                processed_data.append(processed_item)

            logger.info(f"Berhasil mengambil {len(processed_data)} dokumen")

            return jsonify({
                "status": "success",
                "count": len(processed_data),
                "data": processed_data
            }), 200

        except PyMongoError as e:
            logger.error(f"Error database: {str(e)}")
            return jsonify({
                "status": "error",
                "error": "Database Error",
                "message": "Gagal mengambil data dari database"
            }), 500

    except ValueError as e:
        logger.error(f"Parameter tidak valid: {str(e)}")
        return jsonify({
            "status": "error",
            "error": "Invalid Parameter",
            "message": "Parameter limit/sort harus berupa angka"
        }), 400

    except Exception as e:
        logger.error(f"Error pada /get_data: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": "Internal Server Error",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    # Menentukan port dari environment variable atau default ke 5000
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
