from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS
import time
from pymongo.errors import PyMongoError
import logging
import os

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable CORS
CORS(app)

# MongoDB Atlas Configuration
MONGO_URI = "mongodb+srv://StarlithMonitoring:Starlith136@canopyamonitoring.9bjswab.mongodb.net/?retryWrites=true&w=majority&appName=CanopyaMonitoring"

# Initialize MongoDB connection
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, socketTimeoutMS=30000, connectTimeoutMS=10000)
    db = client['iot_data']
    collection = db['sensor_readings']
    commands_collection = db['roof_commands']
    control_mode_collection = db['control_mode']
    logger.info("Successfully connected to MongoDB")
except PyMongoError as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise SystemExit(1)


@app.route('/')
def home():
    return "Flask Backend is Active!"


@app.route('/add_data', methods=['POST'])
def add_data():
    try:
        data = request.get_json()
        required_fields = ['temperature', 'humidity', 'ldr_value', 'roof_status', 'mode']
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": "Incomplete data"}), 400

        sensor_data = {
            'temperature': float(data['temperature']),
            'humidity': float(data['humidity']),
            'ldr_value': float(data['ldr_value']),
            'roof_status': data['roof_status'],
            'mode': data['mode'],
            'timestamp': time.time(),
            'status': 'active'
        }

        result = collection.insert_one(sensor_data)
        sensor_data['_id'] = str(result.inserted_id)

        return jsonify({"status": "success", "message": "Data saved", "data": sensor_data}), 201

    except Exception as e:
        logger.error(f"Error at /add_data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/whatsapp_command', methods=['POST'])
def whatsapp_command():
    data = request.get_json()
    logger.info(f"Received WhatsApp message: {data}")

    if 'Body' not in data or 'From' not in data:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    command = data['Body'].strip().upper()
    sender = data['From']

    if command in ['OPEN', 'CLOSE', 'STATUS', 'AUTO', 'MANUAL']:
        command_doc = {
            'command': command.lower(),
            'source': sender,
            'status': 'pending',
            'timestamp': time.time()
        }
        try:
            commands_collection.insert_one(command_doc)
            # Update the mode if AUTO or MANUAL is received
            if command in ['AUTO', 'MANUAL']:
                control_mode_collection.update_one({}, {'$set': {'mode': command}}, upsert=True)
            return jsonify({"status": "success", "message": f"Command '{command}' saved to database"}), 200
        except Exception as e:
            logger.error(f"Failed to save command: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "Unknown command. Use OPEN, CLOSE, STATUS, AUTO, or MANUAL."}), 400


@app.route('/get_control', methods=['GET'])
def get_control():
    """Provide the latest mode and command for ESP32"""
    try:
        # Fetch mode
        mode_doc = control_mode_collection.find_one()
        mode = mode_doc.get('mode', 'AUTO') if mode_doc else 'AUTO'

        # Fetch latest pending command
        command_doc = commands_collection.find_one({'status': 'pending'}, sort=[('timestamp', -1)])
        command = command_doc['command'] if command_doc else None

        # Mark as processed if found
        if command_doc:
            commands_collection.update_one({'_id': command_doc['_id']}, {'$set': {'status': 'processed'}})

        return jsonify({
            "status": "success",
            "mode": mode,
            "control": command
        }), 200
    except Exception as e:
        logger.error(f"Error at /get_control: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


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
                'roof_status': item['roof_status'],
                'mode': item['mode'],
                'timestamp': item['timestamp'],
                'status': item.get('status', 'active')
            })
        return jsonify({"status": "success", "count": len(data), "data": data}), 200
    except Exception as e:
        logger.error(f"Error at /get_data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
