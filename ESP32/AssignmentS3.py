import machine
import time
import dht
import urequests
import network
import ssd1306  # Library SSD1306 untuk OLED

# ========== KONFIGURASI ========== 
# WiFi
SSID = 'Mochi'
PASSWORD = 'cukipuki'

# Ubidots
UBIDOTS_API_KEY = 'BBUS-X22dYuktZNwot2UyXDlW0br7H6FOIF'
DEVICE_LABEL = 'canopyamonitoring'
VARIABLE_LABEL_TEMP = 'temperature'
VARIABLE_LABEL_HUM = 'humidity'
VARIABLE_LABEL_LDR = 'ldr_value'

# Flask API
FLASK_API_URL = 'https://9fda3355-e9d0-407b-8251-e35d4b04d3e4-00-2qpufjr3z6si3.riker.replit.dev:3000/add_data'

# Pin Configuration
DHT_PIN = 4
LDR_PIN = 34
SERVO1_PIN = 13  # Servo pertama
SERVO2_PIN = 12  # Servo kedua (bergerak berlawanan)
LED_PIN = machine.Pin(18, machine.Pin.OUT)

# Servo Configuration - ANGLE FIXED HERE
SERVO_OPEN_ANGLE = 160    # Sudut buka (180°)
SERVO_CLOSE_ANGLE = 0     # Sudut tutup (0°)
SERVO_MIN_DUTY = 20       # Duty cycle untuk 0°
SERVO_MAX_DUTY = 100      # Duty cycle untuk 180°

# ========== INISIALISASI ========== 
# Sensor
dht_sensor = dht.DHT11(machine.Pin(DHT_PIN))
ldr = machine.ADC(machine.Pin(LDR_PIN))

# Servo (dua servo dengan gerakan berlawanan)
servo1 = machine.PWM(machine.Pin(SERVO1_PIN))
servo2 = machine.PWM(machine.Pin(SERVO2_PIN))
servo1.freq(50)
servo2.freq(50)

# OLED
i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# ========== FUNGSI ========== 
def read_ldr():
    """Membaca nilai intensitas cahaya dari LDR"""
    return ldr.read()

def display_data_oled(temp, hum, ldr_value):
    """Menampilkan data di OLED"""
    oled.fill(0)
    oled.text('Suhu: {:.1f}C'.format(temp), 0, 0)
    oled.text('Kelembaban: {:.1f}%'.format(hum), 0, 10)
    oled.text('LDR: {}'.format(ldr_value), 0, 20)
    oled.text('Status Atap:', 0, 35)
    oled.text('TERBUKA' if temp <= 30 else 'TERTUTUP', 0, 45)
    oled.show()

def move_servos(angle):
    """Menggerakkan dua servo dengan arah berlawanan"""
    # Servo 1: normal (0° tutup, 180° buka)
    duty1 = int(SERVO_MIN_DUTY + (angle / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY))
    # Servo 2: terbalik (180° tutup, 0° buka)
    duty2 = int(SERVO_MIN_DUTY + ((195 - angle) / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY))
    
    servo1.duty(duty1)
    servo2.duty(duty2)
    print(f"Servo1: {angle}° (duty: {duty1}), Servo2: {180-angle}° (duty: {duty2})")

def control_led(state):
    """Mengontrol LED"""
    LED_PIN.value(state)
    print("LED:", "ON" if state else "OFF")

def send_data_to_ubidots(temp, hum, ldr_value):
    """Mengirim data ke Ubidots"""
    try:
        url = f"https://industrial.api.ubidots.com/api/v1.6/devices/{DEVICE_LABEL}"
        headers = {"X-Auth-Token": UBIDOTS_API_KEY}
        payload = {
            VARIABLE_LABEL_TEMP: {"value": temp},
            VARIABLE_LABEL_HUM: {"value": hum},
            VARIABLE_LABEL_LDR: {"value": ldr_value}
        }
        print(f"[UBIDOTS] Sending data to: {url}")
        print(f"[UBIDOTS] Data: {payload}")
        response = urequests.post(url, json=payload, headers=headers, timeout=10)
        print("[UBIDOTS] Status Code:", response.status_code)
        print("[UBIDOTS] Response:", response.text)
        response.close()
        return response.status_code == 200
    except Exception as e:
        print("[UBIDOTS] Error:", e)
        return False

def send_data_to_flask(temp, hum, ldr_value):
    """Mengirim data ke Flask"""
    try:
        payload = {
            "temperature": temp,
            "humidity": hum,
            "ldr_value": ldr_value
        }
        print(f"[FLASK] Sending data to: {FLASK_API_URL}")
        print(f"[FLASK] Data: {payload}")
        response = urequests.post(FLASK_API_URL, json=payload, timeout=10)
        print("[FLASK] Status Code:", response.status_code)
        print("[FLASK] Response:", response.text)
        response.close()
        return response.status_code == 200
    except Exception as e:
        print("[FLASK] Error:", e)
        return False

def connect_wifi():
    """Menghubungkan ke WiFi"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(SSID, PASSWORD)
        for _ in range(10):
            if wlan.isconnected():
                break
            time.sleep(1)
    if wlan.isconnected():
        print("WiFi Connected!")
        print("IP:", wlan.ifconfig()[0])
        return True
    else:
        print("WiFi Failed!")
        return False

# ========== PROGRAM UTAMA ========== 
print("\n=== SISTEM KONTROL ATAP OTOMATIS ===")
connect_wifi()

while True:
    try:
        # Baca sensor
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        hum = dht_sensor.humidity()
        ldr_value = read_ldr()
        
        # Tampilkan di OLED
        display_data_oled(temp, hum, ldr_value)
        
        # Kontrol atap dan LED - LOGIC FIXED HERE
        if temp > 30:  # Jika PANAS
            move_servos(SERVO_CLOSE_ANGLE)  # TUTUP (0°)
            control_led(True)  # LED on
            roof_status = "TERTUTUP"
            led_status = "HIDUP"
        else:  # Jika DINGIN
            move_servos(SERVO_OPEN_ANGLE)  # BUKA (180°)
            control_led(False)  # LED off
            roof_status = "TERBUKA"
            led_status = "MATI"
        
        # Kirim data ke cloud jika WiFi terhubung
        if network.WLAN(network.STA_IF).isconnected():
            print("\nMengirim data ke cloud...")
            ubidots_status = send_data_to_ubidots(temp, hum, ldr_value)
            flask_status = send_data_to_flask(temp, hum, ldr_value)
        else:
            ubidots_status = flask_status = "Gagal menghubungkan WiFi"

        # Print data to Thonny
        print(f"Suhu: {temp:.1f} C")
        print(f"Kelembaban: {hum:.1f}%")
        print(f"LDR: {ldr_value}")
        print(f"Lampu: {led_status}")
        print(f"Status Atap: {roof_status}")
        print(f"Status Pengiriman ke Ubidots: {'Sukses' if ubidots_status == True else 'Gagal'}")
        print(f"Status Pengiriman ke Flask: {'Sukses' if flask_status == True else 'Gagal'}")
        
        time.sleep(15)  # Delay 15 detik
        
    except OSError as e:
        print("Sensor Error:", e)
        time.sleep(5)
    except Exception as e:
        print("System Error:", e)
        time.sleep(10)

