from flask import Flask, Response, request, jsonify
import cv2
from picamera2 import Picamera2
import motor, sensor  # eu folosesc motoarele și senzorul

app = Flask(__name__)

# ------------------- SETĂRI CONTROL -------------------
# eu țin aceleași constante ca să fie previzibil
RADIUS = 100.0    # egal cu radius-ul din joystick (frontend)
DEADZONE = 0.08   # eu ignor micile variații din centru
MAX_OUT = 100     # ieșirea maximă pentru motoare (%)
TURN_K = 1.0      # factor de viraj (1 = normal)

def clamp(v, lo, hi):
    # eu limitez o valoare între [lo, hi]
    return max(lo, min(hi, v))

def apply_deadzone(v, dz=DEADZONE):
    # eu fac zona moartă ca să nu tremure pe centru
    return 0.0 if abs(v) < dz else v
# ------------------------------------------------------


# -------------------- CAMERA --------------------------
# eu pornesc camera și trimit MJPEG către browser
cam = Picamera2()
cam.configure(cam.create_video_configuration(main={"size": (640, 480)}))
cam.start()

def mjpeg():
    # eu captez cadre, le encodez JPG și le trimit ca stream
    while True:
        frame = cam.capture_array()
        # eu scriu un mic text pe video ca să văd că merge
        cv2.putText(frame, "SmartCar", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        ok, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')
# ------------------------------------------------------


# -------------------- RUTE SERVER ---------------------
@app.route('/')
def index():
    # eu servesc pagina principală
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/video')
def video():
    # eu servesc fluxul video în format MJPEG
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/distance')
def distance():
    # eu doar măsor și întorc distanța (NU opresc mașina)
    cm = sensor.distance_cm()
    return jsonify(ok=(cm is not None), cm=(cm if cm is not None else 0.0))

@app.route('/drive', methods=['POST'])
def drive():
    # eu primesc datele de la joystick (x, y, speed, angle)
    d = request.get_json(silent=True) or {}

    # eu extrag valorile ca întregi
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))  # cât de tare împing joystickul
    # angle îl primesc, dar nu-l folosesc aici

    # 1) normalizare în [-1, 1]; invers y ca să fie sus = înainte
    nx = clamp(x / RADIUS, -1, 1)
    ny = clamp(-y / RADIUS, -1, 1)

    # 2) zona moartă
    nx = apply_deadzone(nx)
    ny = apply_deadzone(ny)

    # 3) viraj stânga/dreapta
    turn = nx * TURN_K
    left_u  = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    # 4) aplic accelerația generală
    s = clamp(speed / 100.0, 0, 1)
    left  = int(left_u  * s * MAX_OUT)
    right = int(right_u * s * MAX_OUT)

    # 5) eu trimit efectiv la motoare (nu opresc pentru obstacole)
    motor.set_left(left)
    motor.set_right(right)

    # eu trimit înapoi valori pentru debug în UI
    return jsonify(ok=True, left=left, right=right, x=x, y=y, speed=speed)
# ------------------------------------------------------


# -------------------- MAIN ----------------------------
if __name__ == '__main__':
    # eu pornesc serverul Flask pe toate interfețele
    app.run(host='0.0.0.0', port=8000, threaded=True)
# ------------------------------------------------------
