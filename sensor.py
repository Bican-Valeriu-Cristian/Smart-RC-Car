import RPi.GPIO as GPIO
import time

# --- CONFIGURARE ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# PINII (Convertiți din BOARD în BCM)
TRIG = 7 # Pinul Fizic 26 = BCM 7
ECHO = 5 # Pinul Fizic 29 = BCM 5

def setup_sensor():
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.output(TRIG, False)
    time.sleep(0.1)

def reset_sensor_hardware():
    """Deblochează fizic senzorul dacă pinul ECHO rămâne blocat."""
    # Setăm ECHO pe OUTPUT și îl forțăm să LOW pentru a debloca senzorul
    GPIO.setup(ECHO, GPIO.OUT)
    GPIO.output(ECHO, False)
    time.sleep(0.05)
    # Îl punem înapoi pe INPUT pentru a citi date
    GPIO.setup(ECHO, GPIO.IN)

setup_sensor()

# Timeout pentru a nu bloca codul dacă senzorul nu răspunde
TIMEOUT = 0.04 

def _read_one():
    # Asigurăm-ne că TRIG e 0 înainte de a începe
    GPIO.output(TRIG, False)
    time.sleep(0.002)

    try:
        # 1. Trimitem pulsul de Trigger (10 microsecunde)
        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)

        pulse_start = time.time()
        timeout_start = time.time()
        
        # 2. Așteptăm să înceapă semnalul ECHO (LOW -> HIGH)
        while GPIO.input(ECHO) == 0:
            pulse_start = time.time()
            if pulse_start - timeout_start > TIMEOUT:
                reset_sensor_hardware()
                return None

        pulse_end = time.time()
        timeout_start = time.time() # Resetăm timeout-ul pentru a doua buclă
        
        # 3. Așteptăm să se termine semnalul ECHO (HIGH -> LOW)
        while GPIO.input(ECHO) == 1:
            pulse_end = time.time()
            if pulse_end - timeout_start > TIMEOUT:
                reset_sensor_hardware()
                return None

        # 4. Calculăm durata și distanța
        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150
        
        return distance

    except Exception as e:
        setup_sensor()
        return None

def get_distance():
    # Facem 3 măsurători și returnăm mediana pentru a filtra zgomotul
    measurements = []
    
    for _ in range(3):
        d = _read_one()
        # Filtrăm valori nerealiste (sub 2cm sau peste 400cm)
        if d is not None and 2 < d < 400:
            measurements.append(d)
        time.sleep(0.015)

    if len(measurements) > 0:
        measurements.sort()
        mid_val = measurements[len(measurements) // 2]
        return round(mid_val, 1)
    else:
        # Dacă senzorul ratează complet (ex: mâna prea aproape), putem returna 1.0 în loc de 0
        return 1.0 

def close():
    print("Curățare GPIO Senzor...")
    try:
        GPIO.cleanup([TRIG, ECHO])
    except:
        pass