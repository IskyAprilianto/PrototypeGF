import machine
import time
import dht
import urequests
import network

# ========== KONFIGURASI ==========
# WiFi
SSID = 'Mochi'
PASSWORD = 'cukipuki'

# Ubidots
UBIDOTS_API_KEY = 'BBUS-X22dYuktZNwot2UyXDlW0br7H6FOIF'
DEVICE_LABEL = 'CanopyaMonitoring'
VARIABLE_LABEL_TEMP = 'temperature'
VARIABLE_LABEL_HUM = 'humidity'
VARIABLE_LABEL_LDR = 'ldr_value'

# Flask API (ganti dengan URL server Flask yang benar)
FLASK_API_URL = 'https://9fda3355-e9d0-407b-8251-e35d4b04d3e4-00-2qpufjr3z6si3.riker.replit.dev:3000/add_data'

# Pin
DHT_PIN = 4
LDR_PIN = 34
SERVO_PIN = 13
LED_PIN = machine.Pin(18, machine.Pin.OUT)  # Pin untuk LED

# Servo Configuration
SERVO_OPEN_ANGLE = 30    # Sudut buka (30°)
SERVO_CLOSE_ANGLE = 110  # Sudut tutup (110°)
SERVO_MIN_DUTY = 40      # Duty cycle untuk 0°
SERVO_MAX_DUTY = 115     # Duty cycle untuk 180°

# ========== INISIALISASI ==========
# Sensor DHT11
dht_sensor = dht.DHT11(machine.Pin(DHT_PIN))

# LDR
ldr = machine.ADC(machine.Pin(LDR_PIN))

# Servo
servo = machine.PWM(machine.Pin(SERVO_PIN))
servo.freq(50)  # Frekuensi standar servo (50Hz)

# ========== FUNGSI ==========
def read_ldr():
    """Membaca nilai intensitas cahaya dari LDR"""
    return ldr.read()

def display_data(suhu, kelembaban, ldr_value):
    """Menampilkan data sensor di serial monitor"""
    print("\n=== DATA SENSOR ===")
    print(f"Suhu: {suhu:.1f}°C")
    print(f"Kelembaban: {kelembaban:.1f}%")
    print(f"Intensitas Cahaya: {ldr_value}")

def move_servo(angle):
    """Menggerakkan servo ke sudut tertentu"""
    # Konversi sudut ke duty cycle
    duty = int(SERVO_MIN_DUTY + (angle / 180) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY))
    servo.duty(duty)
    print(f"Posisi Servo: {angle}° (duty: {duty})")

def control_led(state):
    """Mengontrol LED berdasarkan state"""
    if state:
        LED_PIN.on()
        print("LED: MENYALA")
    else:
        LED_PIN.off()
        print("LED: MATI")

def send_data_to_ubidots(temp, hum, ldr_value):
    """Mengirim data ke platform Ubidots"""
    try:
        url = f"https://industrial.api.ubidots.com/api/v1.6/devices/{DEVICE_LABEL}"
        headers = {"X-Auth-Token": UBIDOTS_API_KEY}
        payload = {
            VARIABLE_LABEL_TEMP: {"value": temp},
            VARIABLE_LABEL_HUM: {"value": hum},
            VARIABLE_LABEL_LDR: {"value": ldr_value}
        }
        
        response = urequests.post(url, json=payload, headers=headers)
        print("\n[UBIDOTS] Status:", response.status_code)
        print("[UBIDOTS] Respon:", response.text)
        response.close()
        return True
    except Exception as e:
        print("\n[UBIDOTS] Error:", e)
        return False

def send_data_to_flask(temp, hum, ldr_value):
    """Mengirim data ke server Flask"""
    try:
        payload = {
            "temperature": temp,
            "humidity": hum,
            "ldr_value": ldr_value
        }
        
        response = urequests.post(FLASK_API_URL, json=payload)
        print("[FLASK] Status:", response.status_code)
        print("[FLASK] Respon:", response.text)
        response.close()
        return True
    except Exception as e:
        print("[FLASK] Error:", e)
        return False

def connect_wifi():
    """Menghubungkan ESP32 ke jaringan WiFi"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print(f"\nMenghubungkan ke WiFi: {SSID}")
        wlan.connect(SSID, PASSWORD)
        
        # Tunggu hingga terhubung (maks 10 detik)
        waktu_mulai = time.time()
        while not wlan.isconnected():
            if time.time() - waktu_mulai > 10:
                print("Gagal terhubung ke WiFi")
                return False
            time.sleep(0.5)
    
    print("\nWiFi Terhubung!")
    print("Alamat IP:", wlan.ifconfig()[0])
    return True

# ========== PROGRAM UTAMA ==========
print("\n=== SISTEM MONITORING RUMAH KACA ===")
print("Memulai inisialisasi...")

# Coba koneksi WiFi
if connect_wifi():
    print("Sistem siap!")
else:
    print("Gagal terhubung ke WiFi, sistem berjalan secara offline")

while True:
    try:
        # Baca data sensor
        dht_sensor.measure()
        suhu = dht_sensor.temperature()
        kelembaban = dht_sensor.humidity()
        nilai_ldr = read_ldr()
        
        # Tampilkan data
        display_data(suhu, kelembaban, nilai_ldr)
        
        # Kontrol perangkat berdasarkan suhu
        if suhu > 10:  # Jika suhu > 30°C
            move_servo(SERVO_CLOSE_ANGLE)  # Tutup atap (110°)
            control_led(True)  # Hidupkan LED
        else:  # Jika suhu ≤ 30°C
            move_servo(SERVO_OPEN_ANGLE)  # Buka atap (30°)
            control_led(False)  # Matikan LED
        
        # Kirim data ke cloud (jika WiFi terhubung)
        if network.WLAN(network.STA_IF).isconnected():
            print("\nMengirim data ke cloud...")
            status_ubidots = send_data_to_ubidots(suhu, kelembaban, nilai_ldr)
            status_flask = send_data_to_flask(suhu, kelembaban, nilai_ldr)
            
            if status_ubidots and status_flask:
                print("--> Semua data berhasil dikirim!")
            else:
                print("--> Ada masalah dalam pengiriman data")
        
        # Tunggu sebelum pembacaan berikutnya
        print("\nMenunggu 30 detik...")
        time.sleep(30)
        
    except OSError as e:
        print("\nError membaca sensor DHT11:", e)
        time.sleep(5)
    except Exception as e:
        print("\nError tidak terduga:", e)
        time.sleep(10)

