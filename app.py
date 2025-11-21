from flask import Flask, Response, request, jsonify
import cv2
from picamera2 import Picamera2
import motor, sensor
import threading
import time

app = Flask(__name__)

# ------------------- SETĂRI -------------------
RADIUS = 100.0
DEADZONE = 0.08
MAX_OUT = 100
TURN_K = 1.0
SAFE_DISTANCE_CM = 20.0


current_ny = 0.0 



def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def apply_deadzone(v, dz=DEADZONE):
    return 0.0 if abs(v) < dz else v


# -------------------- (WATCHDOG) --------------------
def safety_watchdog():
    global current_ny

    while True:

        dist = sensor.distance()
        if dist is not None and 0 < dist < SAFE_DISTANCE_CM and current_ny > 0:
            print(f"Watchdog: ZID la {dist}cm -> STOP FORTAT")
            motor.stop()

        time.sleep(0.05)  # ~20 verificări/secundă


# -------------------- CAMERA --------------------------
cam = Picamera2()
config = cam.create_video_configuration(
    main={"size": (640, 360), "format": "BGR888"}
)
cam.configure(config)
cam.start()


def mjpeg():
    while True:
        frame = cam.capture_array()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
        ok, jpg = cv2.imencode('.jpg', frame, encode_param)
        if ok:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')


# -------------------- RUTE ---------------------
@app.route('/')
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.route('/video')
def video():
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/distance')
def get_distance():
    return jsonify(cm=sensor.distance())


@app.route('/drive', methods=['POST'])
def drive():
    global current_ny

    d = request.get_json(silent=True) or {}
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))

    nx = clamp(x / RADIUS, -1, 1)
    ny = clamp(-y / RADIUS, -1, 1)

    # deadzone
    nx = apply_deadzone(nx)
    ny = apply_deadzone(ny)

    # actualizăm intenția pentru paznic DUPĂ deadzone
    current_ny = ny

    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    s = clamp(speed / 100.0, 0, 1)
    left = int(left_u * s * MAX_OUT)
    right = int(right_u * s * MAX_OUT)

    motor.set_left(left)
    motor.set_right(right)

    return jsonify(ok=True, left=left, right=right)


if __name__ == '__main__':
    try:
        # PORNIM WATCHDOG-UL AICI, nu la import
        t = threading.Thread(target=safety_watchdog, daemon=True)
        t.start()

        app.run(host='0.0.0.0', port=8000, threaded=True, debug=False)
    finally:
        motor.cleanup()
        try:
            cam.stop()
        except Exception:
            pass
