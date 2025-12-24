#!/usr/bin/env python3
# sensor.py
# Modul HC-SR04P pentru Raspberry Pi 5 - Varianta Clean

from gpiozero import DistanceSensor
from time import sleep

# --- CONFIGURARE PINI ---
TRIG_PIN = 7
ECHO_PIN = 5

# --- INITIALIZARE ---
sensor = None
try:
    sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIG_PIN, max_distance=4)
except Exception:
    pass  # Ignoram eroarea la init ca sa nu opreasca importul

# --- API ---

def get_distance():
    """Returnează distanța în cm (mediana din 3 citiri) sau 0."""
    if sensor is None:
        return 0

    values = []
    for _ in range(3):
        try:
            val = sensor.distance * 100
            if 2 < val < 400:
                values.append(val)
        except:
            pass
        sleep(0.05)

    if not values:
        return 0

    values.sort()
    return round(values[len(values) // 2], 1)

def close():
    if sensor is not None:
        sensor.close()