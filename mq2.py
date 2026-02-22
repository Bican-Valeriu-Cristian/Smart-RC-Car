import time
import board
import busio
import adafruit_dht
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# P0 este întotdeauna canalul 0.
P0 = 0 

# --- CONFIGURARE ---
# 1. Configurare I2C
try:
    i2c = busio.I2C(board.SCL, board.SDA)
except ValueError:
    print("EROARE: I2C nu este detectat.")
    exit()

# 2. Inițializare ADS1115
try:
    ads = ADS1115(i2c) # Inițializăm ADS1115
    mq2_analog = AnalogIn(ads, P0) # Creăm canalul de citire pentru MQ-2
    print("ADS1115 (MQ-2) inițializat cu succes.")

except Exception as e:
    print(f"Eroare la ADS1115: {e}") # Dacă primești eroare de I/O, e de la fire.
    exit()

# 3. Inițializare DHT11 (Pin GPIO 4)
try:
    dht_sensor = adafruit_dht.DHT11(board.D4)
    print("DHT11 inițializat.")
except Exception as e:
    print(f"Eroare la inițializare DHT11: {e}")


# --- BUCLA DE CITIRE ---
try:
    while True:
        try:
            # --- Pasul A: Citim DHT11 ---
            try:
                temperatura = dht_sensor.temperature
                umiditate = dht_sensor.humidity
            except RuntimeError:
                # Erorile DHT11 sunt normale, continuăm
                temperatura = None
                umiditate = None

            # --- Pasul B: Citim MQ-2 ---
            voltaj = mq2_analog.voltage
            valoare_raw = mq2_analog.value

            # --- Pasul C: Afișăm rezultatele ---
            print(f"Gaz: {voltaj:.2f}V", end=" | ")
            
            if temperatura is not None and umiditate is not None:
                print(f"Temp: {temperatura:.1f}°C | Umid: {umiditate}%")
            else:
                print("Citire...")

            # --- Pasul D: Alertă ---
            if voltaj > 2.5: # Prag de alertă pentru gaz 
                print("\n!!! ALERTA: GAZ DETECTAT !!!\n")

        except Exception as error: # Dacă apare o eroare critică, ieșim curat
            dht_sensor.exit()
            raise error

        time.sleep(2.0)

except KeyboardInterrupt:
    print("\nProgram oprit.")
    dht_sensor.exit()