from flask import Flask, Response, request, jsonify
import cv2, time
from threading import Thread, Lock
from picamera2 import Picamera2
import motor, sensor  # presupunem că motor.py e corect

app = Flask(__name__)

# ------------------- SETĂRI CONTROL -------------------
RADIUS = 100.0
DEADZONE = 0.10
MAX_OUT = 100
TURN_K = 1.0

# Obstacol
OBSTACLE_THRESHOLD_CM = 20     # modifici aici pragul
DIST_HZ = 10                   # frecvența citirii senzorului în thread (citiri/s)

def clamp(v, lo, hi): return max(lo, min(hi, v))
def apply_deadzone(v, dz=DEADZONE): return 0.0 if abs(v) < dz else v
# ------------------------------------------------------


# -------------------- CAMERA --------------------------
cam = Picamera2()
cam.configure(cam.create_video_configuration(main={"size": (640, 480)}))
cam.start()

def mjpeg():
    while True:
        frame = cam.capture_array()
        cv2.putText(frame, "SmartCar", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        ok, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        if ok:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')
# ------------------------------------------------------


# --------------- SENZOR: THREAD + CACHE ---------------
_last_distance = -1.0
_last_distance_ts = 0.0
_sensor_lock = Lock()

def _sensor_loop():
    global _last_distance, _last_distance_ts
    period = 1.0 / DIST_HZ
    while True:
        with _sensor_lock:
            d = sensor.get_distance_cm()
        _last_distance = d
        _last_distance_ts = time.time()
        time.sleep(period)

def obstacle_cached(threshold_cm=OBSTACLE_THRESHOLD_CM, max_age=0.3):
    """
    True dacă ultima citire este proaspătă (< max_age sec) și sub prag.
    Dacă nu e proaspătă/validă, returnăm False (nu blocăm).
    """
    age = time.time() - _last_distance_ts
    if age > max_age or _last_distance < 0:
        return False
    return _last_distance <= threshold_cm

# Pornește threadul de citire a senzorului
sensor_thread = Thread(target=_sensor_loop, daemon=True)
sensor_thread.start()
# ------------------------------------------------------


# -------------------- RUTE SERVER ---------------------
@app.route('/')
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/video')
def video():
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/distance')
def distance():
    d = _last_distance
    return jsonify(distance=round(d, 1) if isinstance(d, (int, float)) and d >= 0 else -1)

@app.route('/drive', methods=['POST'])
def drive():
    d = request.get_json(silent=True) or {}
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))

    # STOP hard dacă joystick-ul e în centru
    if x == 0 and y == 0:
        motor.stop()
        return jsonify(ok=True, left=0, right=0, x=x, y=y, speed=0)

    nx = clamp(x / RADIUS, -1, 1)
    ny = clamp(-y / RADIUS, -1, 1)

    nx = apply_deadzone(nx)
    ny = apply_deadzone(ny)

    # după deadzone, dacă suntem pe centru -> STOP
    if nx == 0.0 and ny == 0.0:
        motor.stop()
        return jsonify(ok=True, left=0, right=0, x=x, y=y, speed=0)

    # verificare obstacol în față (când vrem să mergem înainte: ny > 0)
    if ny > 0 and obstacle_cached():
        motor.stop()
        return jsonify(ok=True, left=0, right=0, x=x, y=y, speed=0, obstacle=True)

    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    s = clamp(speed / 100.0, 0, 1)
    if s == 0:
        motor.stop()
        return jsonify(ok=True, left=0, right=0, x=x, y=y, speed=0)

    left = int(left_u * s * MAX_OUT)
    right = int(right_u * s * MAX_OUT)

    motor.set_left(left)
    motor.set_right(right)

    return jsonify(ok=True, left=left, right=right, x=x, y=y, speed=s)
# ------------------------------------------------------


# -------------------- MAIN ----------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, threaded=True)
# ------------------------------------------------------
