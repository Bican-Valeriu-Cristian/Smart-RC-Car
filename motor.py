# motors.py — 2x TB6612FNG
from gpiozero import PWMOutputDevice, DigitalOutputDevice

# 1. DEFINIRE PINI (Sistem BCM)

# --- Driver 1 (STANGA) ---
STBY1_PIN   = 25  

# Stanga Fata (Motor A din Driver 1)
AIN1_FL_PIN = 23  
AIN2_FL_PIN = 24  
PWMA1_PIN   = 18  

# Stanga Spate (Motor B din Driver 1)
BIN1_RL_PIN = 22  
BIN2_RL_PIN = 27  
PWMB1_PIN   = 13  

# --- Driver 2 (DREAPTA) ---
STBY2_PIN   = 16  

# Dreapta Fata (Motor A din Driver 2 )
AIN1_FR_PIN = 21  
AIN2_FR_PIN = 26  
PWMA2_PIN   = 19  

# Dreapta Spate (Motor B din Driver 2)
BIN1_RR_PIN = 6   
BIN2_RR_PIN = 8   
PWMB2_PIN   = 12  

# Frecvența PWM
PWM_FREQ = 100

# 2. INIȚIALIZARE DISPOZITIVE

# --- Driver 1 (STANGA) ---
stby1 = DigitalOutputDevice(STBY1_PIN, initial_value=True)

# Stanga Fata
ain1_fl = DigitalOutputDevice(AIN1_FL_PIN)
ain2_fl = DigitalOutputDevice(AIN2_FL_PIN)
pwm_fl  = PWMOutputDevice(PWMA1_PIN, frequency=PWM_FREQ)

# Stanga Spate
bin1_rl = DigitalOutputDevice(BIN1_RL_PIN)
bin2_rl = DigitalOutputDevice(BIN2_RL_PIN)
pwm_rl  = PWMOutputDevice(PWMB1_PIN, frequency=PWM_FREQ)

# --- Driver 2 (DREAPTA) ---
stby2 = DigitalOutputDevice(STBY2_PIN, initial_value=True)

# Dreapta Fata
ain1_fr = DigitalOutputDevice(AIN1_FR_PIN)
ain2_fr = DigitalOutputDevice(AIN2_FR_PIN)
pwm_fr  = PWMOutputDevice(PWMA2_PIN, frequency=PWM_FREQ)

# Dreapta Spate
bin1_rr = DigitalOutputDevice(BIN1_RR_PIN)
bin2_rr = DigitalOutputDevice(BIN2_RR_PIN)
pwm_rr  = PWMOutputDevice(PWMB2_PIN, frequency=PWM_FREQ)

# 3. FUNCȚII LOGICE

def _clamp(v):
    if v > 100: return 100
    if v < -100: return -100
    return int(v)

def _set_motor(in1, in2, pwm, value):
    # Valoarea poate fi între -100 și 100, unde:
    #   -100 = Viteza maximă înapoi
    #     0 = Oprit
    #   +100 = Viteza maximă înainte
    v = _clamp(value)
    
    # GPIO Zero lucrează cu valori 0.0 -> 1.0
    speed = abs(v) / 100.0

    if v == 0:
        # Totul oprit
        in1.off()
        in2.off()
        pwm.value = 0
    elif v > 0:
        # ÎNAINTE
        in1.on()
        in2.off()
        pwm.value = speed
    else: 
        # ÎNAPOI (v < 0)
        in1.off()
        in2.on()
        pwm.value = speed

def set_right(value):
    # Controlăm Driver 1 (partea stângă)
    _set_motor(ain1_fl, ain2_fl, pwm_fl,  value)
    _set_motor(bin1_rl, bin2_rl, pwm_rl, -value) 

def set_left(value):
    # Controlăm Driver 2 (partea dreaptă)
    _set_motor(ain1_fr, ain2_fr, pwm_fr, -value)
    _set_motor(bin1_rr, bin2_rr, pwm_rr, -value) 

def stop():
    # Oprim ambele motoare
    set_left(0)
    set_right(0)

def cleanup():
    # Funcție de curățare
    stop()
    stby1.off()
    stby2.off()
    
    # Închidem conexiunile
    pwm_fl.close()
    pwm_rl.close()
    pwm_fr.close()
    pwm_rr.close()

    