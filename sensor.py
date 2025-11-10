# sensor.py – HC-SR04P pe BOARD (TRIG=26, ECHO=29)
# eu fac codul cât mai scurt: doar măsor și întorc distanța în cm (sau None)

import RPi.GPIO as GPIO, time
from statistics import median

# eu setez modul și pinii
GPIO.setmode(GPIO.BOARD); GPIO.setwarnings(False)
TRIG, ECHO = 26, 29
GPIO.setup(TRIG, GPIO.OUT); GPIO.setup(ECHO, GPIO.IN)
SPEED_CM_S = 34300.0  # viteza sunetului ~343 m/s

def _once(timeout=0.04):
    """eu fac o măsurătoare; întorc cm sau None dacă e timeout/zgomot"""
    # eu trimit un puls scurt (10us) pe TRIG
    GPIO.output(TRIG, GPIO.LOW); time.sleep(2e-6)
    GPIO.output(TRIG, GPIO.HIGH); time.sleep(1e-5)
    GPIO.output(TRIG, GPIO.LOW)

    t0 = time.monotonic()
    while GPIO.input(ECHO) == 0:
        if time.monotonic() - t0 > timeout: return None
    start = time.monotonic()
    while GPIO.input(ECHO) == 1:
        if time.monotonic() - start > timeout: return None

    dt = time.monotonic() - start  # eu calculez durata
    cm = (dt * SPEED_CM_S) / 2.0   # dus-întors -> împart la 2
    return cm if 1.0 < cm < 500.0 else None

def distance_cm(samples=5):
    """eu iau câteva probe rapide și întorc mediana pentru stabilitate"""
    vals = []
    for _ in range(max(1, samples)):
        v = _once()
        if v is not None: vals.append(v)
        time.sleep(0.005)  # eu las un mic răgaz
    return float(median(vals)) if vals else None

def cleanup():
    """eu eliberez GPIO la închidere (opțional)"""
    GPIO.cleanup()
