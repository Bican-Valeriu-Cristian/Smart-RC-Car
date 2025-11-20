import RPi.GPIO as GPIO
import time

# Setări standard
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Pinii (FIZICI)
TRIG = 26
ECHO = 29

# Configurare
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.output(TRIG, False)

def _read_one():
    """Citește o singură dată senzorul. Returnează cm sau None."""
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    # Timeout-uri scurte pentru viteză
    start = time.time()
    timeout = start + 0.04
    
    # Aștept semnalul HIGH
    while GPIO.input(ECHO) == 0:
        start = time.time()
        if start > timeout: return None

    # Aștept semnalul LOW
    stop = time.time()
    timeout = stop + 0.04
    while GPIO.input(ECHO) == 1:
        stop = time.time()
        if stop > timeout: return None

    dist = (stop - start) * 34300 / 2
    return dist

def distance():
    """
    Face 3 măsurători rapide și returnează valoarea din mijloc (mediana).
    Asta elimină erorile bruște.
    """
    values = []
    for _ in range(3): # 3 e de ajuns pentru viteză
        d = _read_one()
        if d and 2 < d < 400: # Validăm limitele senzorului (2cm - 400cm)
            values.append(d)
        time.sleep(0.01) # Mică pauză între citiri

    if len(values) > 0:
        values.sort()
        # Returnăm valoarea din mijloc
        return round(values[len(values) // 2], 1)
    else:
        return 0 # Dacă nu detectează nimic, zicem 0