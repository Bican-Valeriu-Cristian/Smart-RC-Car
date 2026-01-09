import time
import threading
import board
import busio
import adafruit_dht
import csv
import os
from datetime import datetime

# Importăm biblioteca GPIO
import RPi.GPIO as GPIO

# Importurile pentru ADS1115
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# --- CONFIGURARE PINI HARDWARE (LED/BUZZER) ---
PIN_LED_ROSU = 17
PIN_LED_VERDE = 27
PIN_BUZZER = 22

# [HARDWARE] Decomentează când ai piesele
# GPIO.setmode(GPIO.BCM)
# GPIO.setwarnings(False)
# GPIO.setup(PIN_LED_ROSU, GPIO.OUT)
# GPIO.setup(PIN_LED_VERDE, GPIO.OUT)
# GPIO.setup(PIN_BUZZER, GPIO.OUT)
# GPIO.output(PIN_LED_ROSU, GPIO.LOW)
# GPIO.output(PIN_LED_VERDE, GPIO.LOW)
# GPIO.output(PIN_BUZZER, GPIO.LOW)

# --- VARIABILE GLOBALE ---
sensor_data = {
    "gas_volts": 0.0,
    "gas_alert": False,
    "temp": 0.0,
    "hum": 0.0,
    "distance_cm": 0, # Adăugăm și distanța aici dacă o citim
    "last_update": 0
}

data_lock = threading.Lock()
_running = True
P0 = 0 

# --- CONFIGURARE LOGGING (FISIER CSV) ---
LOG_FILE = "istoric_date.csv"

# Dacă fișierul nu există, îl creăm și scriem capul de tabel
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Data_Ora", "Gaz_Volti", "Temperatura", "Umiditate", "Alerta"])

def sensor_loop():
    global sensor_data
    
    # 1. Configurare Hardware
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS1115(i2c)
        mq2_analog = AnalogIn(ads, P0)
        dht_sensor = adafruit_dht.DHT11(board.D4)
    except Exception as e:
        print(f"Eroare Hardware Init: {e}")
        return

    print("Senzorii au pornit. Se înregistrează datele în 'istoric_date.csv'...")

    while _running:
        try:
            # --- A. CITIRE DATE ---
            try:
                t = dht_sensor.temperature
                h = dht_sensor.humidity
            except RuntimeError:
                t = None
                h = None

            volts = mq2_analog.voltage
            is_danger = volts > 1.5

            # --- B. SALVARE ÎN FIȘIER (LOGGING) ---
            # Scriem datele doar dacă avem temperatură validă
            if t is not None:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(LOG_FILE, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, round(volts, 2), t, h, "DA" if is_danger else "NU"])

            # --- C. ACTUALIZARE VARIABILE GLOBALE ---
            with data_lock:
                sensor_data["gas_volts"] = round(volts, 2)
                sensor_data["gas_alert"] = is_danger
                if t is not None:
                    sensor_data["temp"] = round(t, 1)
                if h is not None:
                    sensor_data["hum"] = int(h)
                sensor_data["last_update"] = time.time()

            # --- D. LOGICA ALARMĂ FIZICĂ ---
            if is_danger:
                # GPIO.output(PIN_LED_ROSU, GPIO.HIGH)
                # GPIO.output(PIN_BUZZER, GPIO.HIGH)
                # GPIO.output(PIN_LED_VERDE, GPIO.LOW)
                pass
            else:
                # GPIO.output(PIN_LED_ROSU, GPIO.LOW)
                # GPIO.output(PIN_BUZZER, GPIO.LOW)
                # GPIO.output(PIN_LED_VERDE, GPIO.HIGH)
                pass

        except Exception as e:
            print(f"Eroare citire senzori: {e}")
        
        time.sleep(2.0)

def start_monitoring():
    t = threading.Thread(target=sensor_loop, daemon=True)
    t.start()

def get_data():
    with data_lock:
        return sensor_data.copy()

def cleanup():
    global _running
    _running = False
    # GPIO.cleanup()