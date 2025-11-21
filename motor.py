# motors.py — 2x TB6612FNG 
# comanda: -100..100 (negativ = inapoi, pozitiv = inainte)

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# -------- PINI FIZICI (BOARD) --------
# Driver fata (TB6612 #1)
STBY1 = 22

AIN1_FL = 16      # front left  -> AIN1
AIN2_FL = 18      # front left  -> AIN2
PWMA1  = 12       # stanga fata  -> PWMA

BIN1_FR = 15      # front right -> BIN1
BIN2_FR = 13      # front right -> BIN2
PWMB1  = 33     # dreapta fata -> PWMB

# Driver spate (TB6612 #2)
STBY2 = 36

AIN1_RL = 40      # rear left    -> AIN1
AIN2_RL = 37      # rear left    -> AIN2
PWMA2  = 35       # stanga spate -> PWMA

BIN1_RR = 31      # rear right   -> BIN1
BIN2_RR = 24      # rear right   -> BIN2
PWMB2  = 32       # dreapta spate-> PWMB

# ---- Setari PWM ----
PWM_FREQ = 1000   # ~1 kHz (stabil pentru RPi.GPIO PWM software)

# Directii LOW (evita glitch-uri la boot)
for pin in [AIN1_FL, AIN2_FL, BIN1_FR, BIN2_FR,
            AIN1_RL, AIN2_RL, BIN1_RR, BIN2_RR]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# PWM: start(0)
for pin in [PWMA1, PWMB1, PWMA2, PWMB2]:
    GPIO.setup(pin, GPIO.OUT)

pwm_fl = GPIO.PWM(PWMA1, PWM_FREQ)  # stanga fata
pwm_fr = GPIO.PWM(PWMB1, PWM_FREQ)  # dreapta fata
pwm_rl = GPIO.PWM(PWMA2, PWM_FREQ)  # stanga spate
pwm_rr = GPIO.PWM(PWMB2, PWM_FREQ)  # dreapta spate

for p in (pwm_fl, pwm_fr, pwm_rl, pwm_rr):
    p.start(0)

# Scoate driverele din standby abia acum
for stby in (STBY1, STBY2):
    GPIO.setup(stby, GPIO.OUT)
    GPIO.output(stby, GPIO.HIGH)


# -------------------- FUNCTII --------------------
def _clamp(v):
    if v > 100: return 100
    if v < -100: return -100
    return int(v)


def _set_motor(in1, in2, pwm, value):
    v = _clamp(value)
    if v == 0:
        # COAST la 0: ambele LOW, PWM 0
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.LOW)
        pwm.ChangeDutyCycle(0)
    elif v > 0:
        GPIO.output(in1, GPIO.HIGH)
        GPIO.output(in2, GPIO.LOW)
        pwm.ChangeDutyCycle(v)
    else:  # v < 0 // mers invers
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.HIGH)
        pwm.ChangeDutyCycle(-v)


def set_left(value):
    # stanga fata + stanga spate 
    _set_motor(AIN1_FL, AIN2_FL, pwm_fl, value)
    _set_motor(AIN1_RL, AIN2_RL, pwm_rl, -value)


def set_right(value):
    # dreapta fata + dreapta spate 
    _set_motor(BIN1_FR, BIN2_FR, pwm_fr, value)
    _set_motor(BIN1_RR, BIN2_RR, pwm_rr, -value)


def stop():
    set_left(0)
    set_right(0)


def cleanup():
    # opresc tot
    stop()
    for p in (pwm_fl, pwm_fr, pwm_rl, pwm_rr):
        p.stop()
    GPIO.output(STBY1, GPIO.LOW)
    GPIO.output(STBY2, GPIO.LOW)
    GPIO.cleanup()
