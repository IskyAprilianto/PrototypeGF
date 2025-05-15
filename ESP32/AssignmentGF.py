import network
import socket
import machine
import time
import urequests
import dht
import ssd1306
from machine import Pin, PWM
import _thread
import ujson
from machine import Pin, I2C

# ========== KONFIGURASI ========== #
SSID = 'Mochi'
PASSWORD = 'cukipuki'

# Konfigurasi UBIDOTS
UBIDOTS_TOKEN = "BBUS-X22dYuktZNwot2UyXDlW0br7H6FOIF"
UBIDOTS_URL = "http://industrial.api.ubidots.com/api/v1.6/devices/canopyamonitoring"

# Konfigurasi Flask
FLASK_URL = "https://9fda3355-e9d0-407b-8251-e35d4b04d3e4-00-2qpufjr3z6si3.riker.replit.dev:3000/add_data"

# Pin Configuration
DHT_PIN = 4
LDR_PIN = 34
SERVO1_PIN = 13  # Servo pertama
SERVO2_PIN = 12  # Servo kedua (berlawanan arah)
LED_PIN = Pin(18, Pin.OUT)
RELAY_PIN = Pin(33, Pin.OUT)  # Pin relay

# Servo Configuration
SERVO_MIN_DUTY = 20
SERVO_MAX_DUTY = 110

# Threshold Sensor
SUHU_MINIMAL = 18
SUHU_IDEAL_MIN = 22
SUHU_IDEAL_MAX = 28
SUHU_MAKSIMAL = 32

LEMBAB_MINIMAL = 40
LEMBAB_IDEAL_MIN = 50
LEMBAB_IDEAL_MAX = 70
LEMBAB_MAKSIMAL = 80

# System Variables
mode_manual = True
current_servo_position = 160
wifi_connected = False
relay_active = False
relay_lock = _thread.allocate_lock()
last_send_time = 0
send_interval = 15  # detik

# Initialize Hardware
sensor_dht = dht.DHT11(Pin(DHT_PIN))
sensor_ldr = machine.ADC(Pin(LDR_PIN))

servo1 = PWM(Pin(SERVO1_PIN))
servo2 = PWM(Pin(SERVO2_PIN))
servo1.freq(50)
servo2.freq(50)

i2c = machine.I2C(0, scl=Pin(22), sda=Pin(21))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Initialize Relay
RELAY_PIN.value(0)  # Start with relay OFF

def print_status(temp, hum, ldr, ubidots_status, flask_status):
    print("\n========== STATUS SISTEM ==========")
    print(f"Suhu: {temp} C")
    print(f"Kelembaban: {hum}%")
    print(f"LDR: {ldr}")
    print(f"Lampu: {'HIDUP' if LED_PIN.value() else 'MATI'}")
    print(f"Status Atap: {'TERTUTUP' if current_servo_position < 90 else 'TERBUKA'}")
    print(f"Status Pengiriman ke Ubidots: {'Sukses' if ubidots_status else 'Gagal'}")
    print(f"Status Pengiriman ke Flask: {'Sukses' if flask_status else 'Gagal'}")
    print(f"Servo1: {current_servo_position}° (duty: {SERVO_MIN_DUTY + (current_servo_position / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY)}), "
          f"Servo2: {180 - current_servo_position}° (duty: {SERVO_MIN_DUTY + ((180 - current_servo_position) / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY)})")
    print(f"LED: {'ON' if LED_PIN.value() else 'OFF'}")
    print("===================================\n")

def connect_wifi():
    global wifi_connected
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print('Menghubungkan ke WiFi...')
        wlan.connect(SSID, PASSWORD)
        
        max_attempts = 20
        for attempt in range(max_attempts):
            if wlan.isconnected():
                break
            print(f'Percobaan {attempt + 1}/{max_attempts}', end='\r')
            time.sleep(1)
    
    if wlan.isconnected():
        print('\nWiFi Terhubung!')
        print('IP:', wlan.ifconfig()[0])
        wifi_connected = True
        LED_PIN.value(1)
        return True
    else:
        print('\nGagal menghubungkan WiFi')
        wifi_connected = False
        LED_PIN.value(0)
        return False

def read_sensors():
    try:
        sensor_dht.measure()
        temp = sensor_dht.temperature()
        hum = sensor_dht.humidity()
        ldr = sensor_ldr.read()
        return temp, hum, ldr
    except Exception as e:
        print("Error membaca sensor:", str(e))
        return None, None, None

def control_servo(angle):
    global current_servo_position
    angle = max(0, min(180, angle))
    duty1 = int(SERVO_MIN_DUTY + (angle / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY))
    duty2 = int(SERVO_MIN_DUTY + ((180 - angle) / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY))
    
    servo1.duty(duty1)
    servo2.duty(duty2)
    current_servo_position = angle
    print(f"Servo diposisikan ke {angle}° (Duty1: {duty1}, Duty2: {duty2})")

def display_data(temp, hum, ldr, status, reason):
    oled.fill(0)
    oled.text("Rumah Kaca Pintar", 0, 0)
    
    if temp is not None and hum is not None:
        oled.text(f"Suhu: {temp}C", 0, 15)
        oled.text(f"Lembab: {hum}%", 0, 25)
        oled.text(f"Cahaya: {ldr}", 0, 35)
    else:
        oled.text("Gagal baca sensor!", 0, 15)
    
    oled.text(f"Mode: {'MANUAL' if mode_manual else 'AUTO'}", 0, 45)
    oled.text(f"Status: {status}", 0, 55)
    oled.show()

def activate_relay(duration):
    global relay_active
    
    with relay_lock:
        if relay_active:
            return "Relay sudah aktif"
        
        relay_active = True
    
    try:
        print(f"Menghidupkan relay selama {duration} detik")
        RELAY_PIN.value(1)
        LED_PIN.value(1)
        start_time = time.time()
        
        while (time.time() - start_time) < duration:
            if not relay_active:
                break
            time.sleep(1)
        
        RELAY_PIN.value(0)
        LED_PIN.value(0)
        return f"Relay aktif selama {int(time.time() - start_time)} detik"
    finally:
        with relay_lock:
            relay_active = False

def send_to_ubidots(temp, hum, ldr):
    if not wifi_connected:
        print("[UBIDOTS] WiFi tidak terhubung")
        return False
    
    try:
        print("\n[MENGIRIM DATA KE UBIDOTS]")
        print(f"[UBIDOTS] Mengirim data ke: {UBIDOTS_URL}")
        
        data = {
            "temperature": {"value": temp},
            "humidity": {"value": hum},
            "light": {"value": ldr}
        }
        
        print(f"[UBIDOTS] Data: {data}")
        
        headers = {
            "X-Auth-Token": UBIDOTS_TOKEN,
            "Content-Type": "application/json"
        }
        
        response = urequests.post(
            UBIDOTS_URL,
            headers=headers,
            json=data,
            timeout=10
        )
        
        print(f"[UBIDOTS] Status Code: {response.status_code}")
        print(f"[UBIDOTS] Response: {response.text}")
        response.close()
        
        return response.status_code == 200
    except Exception as e:
        print(f"[UBIDOTS] Error: {str(e)}")
        return False

def send_to_flask(temp, hum, ldr):
    if not wifi_connected:
        print("[FLASK] WiFi tidak terhubung")
        return False
    
    try:
        print("\n[MENGIRIM DATA KE FLASK]")
        print(f"[FLASK] Mengirim data ke: {FLASK_URL}")
        
        data = {
            "temperature": temp,
            "humidity": hum,
            "ldr_value": ldr
        }
        
        print(f"[FLASK] Data: {data}")
        
        response = urequests.post(
            FLASK_URL,
            json=data,
            timeout=10
        )
        
        print(f"[FLASK] Status Code: {response.status_code}")
        print(f"[FLASK] Response: {response.text}")
        response.close()
        
        return response.status_code == 200
    except Exception as e:
        print(f"[FLASK] Error: {str(e)}")
        return False

def web_server():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print('Web server running on port 80')

    while True:
        cl, addr = s.accept()
        request = cl.recv(1024).decode()
        
        response = None
        
        if '/open_servo' in request:
            control_servo(160)
            response = "Servo terbuka (160°)"
        elif '/close_servo' in request:
            control_servo(0)
            response = "Servo tertutup (0°)"
        elif '/auto_mode' in request:
            global mode_manual
            mode_manual = not mode_manual
            response = f"Mode {'AUTO' if not mode_manual else 'MANUAL'} aktif"
        elif '/activate_relay' in request:
            duration = 10
            if 'duration=' in request:
                try:
                    duration = int(request.split('duration=')[1].split(' ')[0])
                except:
                    pass
            result = activate_relay(duration)
            response = result
        elif '/relay_status' in request:
            response = f"Relay {'ON' if relay_active else 'OFF'}"
        else:
            response = "Perintah tidak valid. Gunakan: /open_servo, /close_servo, /auto_mode, /activate_relay?duration=30, /relay_status"
        
        cl.send('HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n')
        cl.send(response)
        cl.close()

def kontrol_iklim(temp, hum, ldr):
    if temp is None or hum is None or ldr is None:
        return 160, "ERROR", "Sensor tidak valid"

    if temp >= 32:
        return 0, "TUTUP", "Suhu terlalu tinggi"
    elif temp <= 18:
        return 180, "BUKA", "Suhu terlalu rendah"
    elif hum >= 80:
        return 180, "BUKA", "Kelembaban terlalu tinggi"
    elif hum <= 40:
        return 0, "TUTUP", "Kelembaban terlalu rendah"
    elif ldr > 800 and temp > 28:
        return 90, "BUKA SEBAGIAN", "Cerah dan panas"
    elif ldr > 600 and 22 < temp <= 28:
        return 135, "BUKA LEBAR", "Cerah tapi suhu ideal"
    elif ldr <= 600:
        return 160, "BUKA", "Cuaca mendung atau malam"
    else:
        return 160, "BUKA", "Kondisi normal"

def main_loop():
    global wifi_connected, last_send_time
    
    if not connect_wifi():
        print("Mode offline tanpa WiFi")
    
    _thread.start_new_thread(web_server, ())
    control_servo(160)
    
    while True:
        current_time = time.time()
        temp, hum, ldr = read_sensors()
        
        angle, status, reason = kontrol_iklim(temp, hum, ldr)
        if not mode_manual:
            control_servo(angle)
        
        display_data(temp, hum, ldr, status, reason)
        
        if current_time - last_send_time >= send_interval:
            if wifi_connected or connect_wifi():
                ubidots_success = False
                flask_success = False
                
                if temp is not None and hum is not None and ldr is not None:
                    print("\nMengirim data ke cloud...")
                    ubidots_success = send_to_ubidots(temp, hum, ldr)
                    flask_success = send_to_flask(temp, hum, ldr)
                    print_status(temp, hum, ldr, ubidots_success, flask_success)
                
                last_send_time = current_time
            else:
                print("Gagal terhubung ke WiFi, tidak dapat mengirim data")
        
        time.sleep(1)

if __name__ == '__main__':
    main_loop()
