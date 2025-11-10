# sensor.py - HC-SR04P simplu (GPIO.BOARD – pinuri fizice)
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

TRIG = 26  # pin fizic 37? (verifică placa ta; atenție la confuzie)
ECHO = 29  # pin fizic 40? (verifică)

GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def _read_once():
    # puls TRIG scurt LOW -> HIGH -> LOW
    GPIO.output(TRIG, False)
    time.sleep(0.000002)   # 2us
    GPIO.output(TRIG, True)
    time.sleep(0.00001)    # 10us
    GPIO.output(TRIG, False)

    # așteptăm începutul impulsului pe ECHO (max 20ms)
    start = time.time()
    timeout = start + 0.02
    while GPIO.input(ECHO) == 0:
        start = time.time()
        if start > timeout:
            return -1

    # măsurăm durata impulsului HIGH (max 20ms)
    stop = time.time()
    timeout = stop + 0.02
    while GPIO.input(ECHO) == 1:
        stop = time.time()
        if stop > timeout:
            return -1

    # durata în secunde -> cm (dus-întors)
    return (stop - start) * 17150.0

def get_distance_cm():
    """Întoarce distanța în cm sau -1 dacă e eroare, cu 3 încercări."""
    for _ in range(3):
        d = _read_once()
        if d > 0:
            return d
        time.sleep(0.01)
    return -1

def is_obstacle(threshold_cm=15):
    """True dacă există obstacol mai aproape decât threshold_cm."""
    d = get_distance_cm()
    if d < 0:
        return False  # citire aiurea, nu blocăm
    return d <= threshold_cm

def cleanup():
    GPIO.cleanup((TRIG, ECHO))
