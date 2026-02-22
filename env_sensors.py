import time
import threading
import board
import busio
import adafruit_dht
import csv
import os
from datetime import datetime
import RPi.GPIO as GPIO
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# CONFIGURARE PINI (LED/BUZZER)
PIN_LED_ROSU = 10  # 19 fizic
PIN_LED_VERDE = 17 # 11 fizic
PIN_BUZZER = 20    # 38 fizic

# CONSTANTA PENTRU DISTANȚĂ
SAFE_DISTANCE_CM = 20.0

# CONFIGURARE PINI
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PIN_LED_ROSU, GPIO.OUT)
GPIO.setup(PIN_LED_VERDE, GPIO.OUT)
GPIO.setup(PIN_BUZZER, GPIO.OUT)

# OPRIM LEDURILE LA START
GPIO.output(PIN_LED_ROSU, GPIO.LOW)
GPIO.output(PIN_LED_VERDE, GPIO.LOW)

# INIȚIALIZARE PWM PENTRU BUZZER (Hz)
buzzer_pwm = GPIO.PWM(PIN_BUZZER, 2000)

# VARIABILE GLOBALE
sensor_data = {
    "gas_volts": 0.0,
    "gas_alert": False,
    "temp": 0.0,
    "hum": 0.0,
    "distance_cm": 999.0,
    "last_update": 0
}

data_lock = threading.Lock()
_running = True
P0 = 0 

# CONFIGURARE LOGGING (FISIER CSV)
LOG_FILE = "istoric_date.csv"

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Data_Ora", "Gaz_Volti", "Temperatura", "Umiditate", "Alerta_Gaz"])

# FUNCȚIE PENTRU A PRIMI DISTANȚĂ DIN APP.PY
def set_distance(dist):
    with data_lock:
        sensor_data["distance_cm"] = dist

def sensor_loop():
    global sensor_data
    
    # 1. INIȚIALIZARE SENZORI
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
            # A. CITIRE DATE DE MEDIU
            try:
                t = dht_sensor.temperature
                h = dht_sensor.humidity
            except RuntimeError:
                # Erorile DHT11 sunt normale, continuăm
                t = None
                h = None

            volts = mq2_analog.voltage
            
            # B. PRELUARE DISTANȚĂ
            with data_lock:
                dist = sensor_data["distance_cm"]

            # C. EVALUARE PERICOL
            is_gas_danger = volts > 2.5
            is_dist_danger = (0 < dist < SAFE_DISTANCE_CM)
            
            is_danger = is_gas_danger or is_dist_danger

            # D. SALVARE ÎN FIȘIER CSV 
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            temp_log = round(t, 1) if t is not None else "N/A"
            hum_log = int(h) if h is not None else "N/A"
            
            with open(LOG_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, round(volts, 2), temp_log, hum_log, "DA" if is_gas_danger else "NU"])

            # E. ACTUALIZARE VARIABILE GLOBALE
            with data_lock:
                sensor_data["gas_volts"] = round(volts, 2)
                sensor_data["gas_alert"] = is_gas_danger
                if t is not None:
                    sensor_data["temp"] = round(t, 1)
                if h is not None:
                    sensor_data["hum"] = int(h)
                sensor_data["last_update"] = time.time()

            # F. LOGICA ALARMĂ FIZICĂ
            if is_danger:
                GPIO.output(PIN_LED_ROSU, GPIO.HIGH)
                GPIO.output(PIN_LED_VERDE, GPIO.LOW)
                
                # Bip de 4 ori 
                for _ in range(4):
                    buzzer_pwm.start(50)
                    time.sleep(0.25)
                    buzzer_pwm.stop()
                    time.sleep(0.25)
            else:
                GPIO.output(PIN_LED_ROSU, GPIO.LOW)
                GPIO.output(PIN_LED_VERDE, GPIO.HIGH)
                buzzer_pwm.stop()
                
                # Așteptăm 1 secundă 
                time.sleep(1.0)

        except Exception as e:
            print(f"Eroare în bucla de senzori: {e}")
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
    try:
        buzzer_pwm.stop()
    except:
        pass
    GPIO.cleanup()