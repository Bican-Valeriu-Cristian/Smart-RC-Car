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

# Timeout maxim pentru o măsurătoare (în secunde)
TIMEOUT = 0.04  # 40 ms


def _read_one():
    """Citește o singură dată senzorul. Returnează cm sau None."""
    # Dacă GPIO a fost curățat (GPIO.cleanup()), nu mai citim
    if GPIO.getmode() is None:
        return None

    try:
        # trigger scurt de 10 µs
        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)

        # Aștept tranziția LOW -> HIGH (începutul pulsului de la ECHO)
        start_wait = time.time()
        while GPIO.input(ECHO) == 0:
            if time.time() - start_wait > TIMEOUT:
                return None
        pulse_start = time.time()

        # Aștept tranziția HIGH -> LOW (sfârșitul pulsului)
        start_wait = time.time()
        while GPIO.input(ECHO) == 1:
            if time.time() - start_wait > TIMEOUT:
                return None
        pulse_end = time.time()

        # Conversie timp -> distanță (viteză sunet ~34300 cm/s)
        dist = (pulse_end - pulse_start) * 34300 / 2
        return dist
    except RuntimeError:
        # Dacă totuși GPIO dă eroare (ex. închidere), nu lăsăm să pice aplicația
        return None


def distance():
    """
    Face 3 măsurători rapide și returnează valoarea din mijloc (mediana),
    ca să elimine spike-urile. Dacă nu avem valori întoarce 0.
    """
    # Dacă GPIO nu mai e configurat, nu încercăm să citim
    if GPIO.getmode() is None:
        return 0

    values = []
    for _ in range(3):  # 3 citiri sunt suficiente pentru viteză + stabilitate
        d = _read_one()
        if d is not None and 2 < d < 400:  # validăm 2–400 cm
            values.append(d)
        time.sleep(0.01)  # mică pauză între citiri

    if not values:
        # dacă nu am reușit nicio citire validă
        return 0

    values.sort()
    # returnăm valoarea de mijloc (mediana)
    mid = values[len(values) // 2]
    return round(mid, 1)
