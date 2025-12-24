import RPi.GPIO as GPIO
import time

# --- CONFIGURARE ---
# Pe Pi 5 folosim BCM pentru stabilitate maximă cu noua bibliotecă
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# PINII (Convertiți din BOARD în BCM pentru Pi 5)
# Pinul Fizic 26 = BCM 7
# Pinul Fizic 29 = BCM 5
TRIG = 7
ECHO = 5

def setup_sensor():
    """Inițializează pinii. Apelăm asta intern dacă e nevoie."""
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.output(TRIG, False)
    # Lăsăm senzorul să se 'așeze' puțin
    time.sleep(0.1)

# Facem setup-ul la import
setup_sensor()

# Timeout pentru a nu bloca codul dacă senzorul nu răspunde (0.04s = 40ms = ~7 metri)
TIMEOUT = 0.04 

def _read_one():
    """
    Citește o singură dată folosind logica clasică TIME.
    """
    try:
        # 1. Trimitem pulsul de Trigger (10 microsecunde)
        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)

        # 2. Așteptăm să înceapă semnalul ECHO (LOW -> HIGH)
        pulse_start = time.time()
        timeout_start = time.time()
        
        while GPIO.input(ECHO) == 0:
            pulse_start = time.time()
            if pulse_start - timeout_start > TIMEOUT:
                return None

        # 3. Așteptăm să se termine semnalul ECHO (HIGH -> LOW)
        pulse_end = time.time()
        timeout_start = time.time()
        
        while GPIO.input(ECHO) == 1:
            pulse_end = time.time()
            if pulse_end - timeout_start > TIMEOUT:
                return None

        # 4. Calculăm durata și distanța
        pulse_duration = pulse_end - pulse_start
        
        # Viteza sunetului = 34300 cm/s
        distance = pulse_duration * 17150
        
        return distance

    except Exception as e:
        # În caz de eroare I/O, reinițializăm pinii
        setup_sensor()
        return None

def get_distance():
    """
    Face 3 măsurători și returnează mediana.
    Aceasta este funcția pe care o cheamă app.py.
    """
    measurements = []
    
    for _ in range(3):
        d = _read_one()
        # Filtrăm valori nerealiste (sub 2cm sau peste 400cm)
        if d is not None and 2 < d < 400:
            measurements.append(d)
        time.sleep(0.015) # Mică pauză între măsurători

    if len(measurements) > 0:
        measurements.sort()
        # Returnăm mediana
        mid_val = measurements[len(measurements) // 2]
        return round(mid_val, 1)
    else:
        return 0

def close():
    """Curățare pini"""
    print("Curățare GPIO Senzor...")
    GPIO.cleanup([TRIG, ECHO])