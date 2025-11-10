# motors.py — 2x TB6612FNG (BOARD numbering)
# comandă -100..100 (negativ = înapoi, pozitiv = înainte)

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# -------- PINI FIZICI (BOARD) --------
# Driver față (TB6612 #1)
STBY1 = 22

AIN1_FL = 16      # front left  -> AIN1
AIN2_FL = 18      # front left  -> AIN2
PWMA1  = 12       # stânga față  -> PWMA

BIN1_FR = 15      # front right -> BIN1
BIN2_FR = 13      # front right -> BIN2
PWMB1  = 11       # dreapta față -> PWMB

# Driver spate (TB6612 #2)
STBY2 = 36

AIN1_RL = 40      # rear left   -> AIN1
AIN2_RL = 37      # rear left   -> AIN2
PWMA2  = 35       # stânga spate -> PWMA

BIN1_RR = 32      # rear right  -> BIN1
BIN2_RR = 24      # rear right  -> BIN2
PWMB2  = 38       # dreapta spate-> PWMB

PWM_FREQ = 20000  # 20 kHz (nu mai „cântă”)

# STBY: scot driverele din standby
GPIO.setup(STBY1, GPIO.OUT); GPIO.output(STBY1, GPIO.HIGH)
GPIO.setup(STBY2, GPIO.OUT); GPIO.output(STBY2, GPIO.HIGH)

# direcții
for pin in [AIN1_FL, AIN2_FL, BIN1_FR, BIN2_FR, AIN1_RL, AIN2_RL, BIN1_RR, BIN2_RR]:
    GPIO.setup(pin, GPIO.OUT)

# PWM out
for pin in [PWMA1, PWMB1, PWMA2, PWMB2]:
    GPIO.setup(pin, GPIO.OUT)

# PWM pe fiecare motor
pwm_fl = GPIO.PWM(PWMA1, PWM_FREQ)  # stânga față
pwm_fr = GPIO.PWM(PWMB1, PWM_FREQ)  # dreapta față
pwm_rl = GPIO.PWM(PWMA2, PWM_FREQ)  # stânga spate
pwm_rr = GPIO.PWM(PWMB2, PWM_FREQ)  # dreapta spate

pwm_fl.start(0); pwm_fr.start(0); pwm_rl.start(0); pwm_rr.start(0)

def _clamp(v):
    if v > 100: return 100
    if v < -100: return -100
    return int(v)

def _set_motor(in1, in2, pwm, value):
    v = _clamp(value)
    if v == 0:
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.LOW)     # „coast”
        pwm.ChangeDutyCycle(0)
    elif v > 0:
        GPIO.output(in1, GPIO.HIGH)
        GPIO.output(in2, GPIO.LOW)
        pwm.ChangeDutyCycle(v)
    else:  # v < 0
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.HIGH)
        pwm.ChangeDutyCycle(-v)

def set_left(value):
    # stânga față + stânga spate (la spate e inversat – depinde de cablaj)
    _set_motor(AIN1_FL, AIN2_FL, pwm_fl, value)
    _set_motor(AIN1_RL, AIN2_RL, pwm_rl, -value)

def set_right(value):
    # dreapta față + dreapta spate
    _set_motor(BIN1_FR, BIN2_FR, pwm_fr, value)
    _set_motor(BIN1_RR, BIN2_RR, pwm_rr, -value)

def stop():
    set_left(0); set_right(0)

def cleanup():
    stop()
    GPIO.output(STBY1, GPIO.LOW)
    GPIO.output(STBY2, GPIO.LOW)
    GPIO.cleanup()
