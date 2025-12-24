# motors.py — 2x TB6612FNG 
# ADAPTAT PENTRU RASPBERRY PI 5 (folosind gpiozero)
# Variabile curatate (fara _dev)

from gpiozero import PWMOutputDevice, DigitalOutputDevice

# =========================================================
# 1. DEFINIRE PINI (Sistem BCM pentru Pi 5)
# =========================================================
# Am convertit pinii tai fizici (BOARD) in pinii logici (BCM).

# --- Driver Fata (TB6612 #1) ---
STBY1_PIN   = 25  # (Era Pin Fizic 22)

AIN1_FL_PIN = 23  # (Era Pin Fizic 16)
AIN2_FL_PIN = 24  # (Era Pin Fizic 18)
PWMA1_PIN   = 18  # (Era Pin Fizic 12)

BIN1_FR_PIN = 22  # (Era Pin Fizic 15)
BIN2_FR_PIN = 27  # (Era Pin Fizic 13)
PWMB1_PIN   = 13  # (Era Pin Fizic 33)

# --- Driver Spate (TB6612 #2) ---
STBY2_PIN   = 16  # (Era Pin Fizic 36)

AIN1_RL_PIN = 21  # (Era Pin Fizic 40)
AIN2_RL_PIN = 26  # (Era Pin Fizic 37)
PWMA2_PIN   = 19  # (Era Pin Fizic 35)

BIN1_RR_PIN = 6   # (Era Pin Fizic 31)
BIN2_RR_PIN = 8   # (Era Pin Fizic 24)
PWMB2_PIN   = 12  # (Era Pin Fizic 32)

# Frecventa PWM
PWM_FREQ = 1000


# =========================================================
# 2. INITIALIZARE DISPOZITIVE
# =========================================================

# --- Driver Fata ---
stby1 = DigitalOutputDevice(STBY1_PIN, initial_value=True)

# Stanga Fata
ain1_fl = DigitalOutputDevice(AIN1_FL_PIN)
ain2_fl = DigitalOutputDevice(AIN2_FL_PIN)
pwm_fl  = PWMOutputDevice(PWMA1_PIN, frequency=PWM_FREQ)

# Dreapta Fata
bin1_fr = DigitalOutputDevice(BIN1_FR_PIN)
bin2_fr = DigitalOutputDevice(BIN2_FR_PIN)
pwm_fr  = PWMOutputDevice(PWMB1_PIN, frequency=PWM_FREQ)

# --- Driver Spate ---
stby2 = DigitalOutputDevice(STBY2_PIN, initial_value=True)

# Stanga Spate
ain1_rl = DigitalOutputDevice(AIN1_RL_PIN)
ain2_rl = DigitalOutputDevice(AIN2_RL_PIN)
pwm_rl  = PWMOutputDevice(PWMA2_PIN, frequency=PWM_FREQ)

# Dreapta Spate
bin1_rr = DigitalOutputDevice(BIN1_RR_PIN)
bin2_rr = DigitalOutputDevice(BIN2_RR_PIN)
pwm_rr  = PWMOutputDevice(PWMB2_PIN, frequency=PWM_FREQ)


# =========================================================
# 3. FUNCTII LOGICE
# =========================================================

def _clamp(v):
    if v > 100: return 100
    if v < -100: return -100
    return int(v)


def _set_motor(in1, in2, pwm, value):
    """
    Controleaza directia si viteza unui singur motor.
    """
    v = _clamp(value)
    
    # GPIO Zero lucreaza cu valori 0.0 -> 1.0
    speed = abs(v) / 100.0

    if v == 0:
        # COAST: totul oprit
        in1.off()
        in2.off()
        pwm.value = 0
    elif v > 0:
        # INAINTE
        in1.on()
        in2.off()
        pwm.value = speed
    else: 
        # INAPOI (v < 0)
        in1.off()
        in2.on()
        pwm.value = speed


def set_left(value):
    # Controlam motoarele de pe stanga
    _set_motor(ain1_fl, ain2_fl, pwm_fl, value)
    _set_motor(ain1_rl, ain2_rl, pwm_rl, -value)


def set_right(value):
    # Controlam motoarele de pe dreapta
    _set_motor(bin1_fr, bin2_fr, pwm_fr, value)
    _set_motor(bin1_rr, bin2_rr, pwm_rr, -value)


def stop():
    set_left(0)
    set_right(0)


def cleanup():
    # Functie de curatare
    stop()
    stby1.off()
    stby2.off()
    
    # Inchidem conexiunile
    pwm_fl.close()
    pwm_fr.close()
    pwm_rl.close()
    pwm_rr.close()