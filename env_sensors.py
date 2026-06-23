import time
import threading
import board
import busio
import adafruit_dht
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
buzzer_pwm = GPIO.PWM(PIN_BUZZER, 500)

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

def set_distance(dist):
    with data_lock:
        sensor_data["distance_cm"] = dist

def sensor_loop():
    global sensor_data
    
    # INIȚIALIZARE SENZORI
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS1115(i2c)
        mq2_analog = AnalogIn(ads, P0)
        dht_sensor = adafruit_dht.DHT11(board.D4)
    except Exception as e:
        print(f"Eroare Hardware Init: {e}")
        return

    print("Senzorii au pornit. (Fără înregistrare pe disc)")

    # Variabilă pentru a ține minte dacă am bipăit deja
    alarma_activa = False 

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
            is_gas_danger = volts > 3
            is_dist_danger = (2 < dist < SAFE_DISTANCE_CM)
            
            is_danger = is_gas_danger or is_dist_danger

            # D. ACTUALIZARE VARIABILE GLOBALE
            with data_lock:
                sensor_data["gas_volts"] = round(volts, 2)
                sensor_data["gas_alert"] = is_gas_danger
                if t is not None:
                    sensor_data["temp"] = round(t, 1)
                if h is not None:
                    sensor_data["hum"] = int(h)
                sensor_data["last_update"] = time.time()

            # E. LOGICA ALARMĂ FIZICĂ (Bipăie doar o dată)
            if is_danger:
                GPIO.output(PIN_LED_ROSU, GPIO.HIGH)
                GPIO.output(PIN_LED_VERDE, GPIO.LOW)
                
                # Dacă alarma nu a fost încă declanșată pentru acest eveniment
                if not alarma_activa:
                    print("Atenție! Pericol detectat!")
                    # Bip de 2 ori
                    for _ in range(2):
                        buzzer_pwm.start(50)
                        time.sleep(0.1)
                        buzzer_pwm.stop()
                        time.sleep(0.1)
                    
                    # Marcăm că am sunat deja
                    alarma_activa = True 
            else:
                GPIO.output(PIN_LED_ROSU, GPIO.LOW)
                GPIO.output(PIN_LED_VERDE, GPIO.HIGH)
                buzzer_pwm.stop()
                
                # Resetăm alarma pentru când va apărea un pericol nou
                alarma_activa = False
            
            # Pauză constantă de 1 secundă
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