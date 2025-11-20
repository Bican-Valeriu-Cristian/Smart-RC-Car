from flask import Flask, Response, request, jsonify
import cv2
from picamera2 import Picamera2
import motor, sensor  #  folosesc motoarele și senzorul

app = Flask(__name__)

# ------------------- SETĂRI CONTROL -------------------
#  țin aceleași constante ca să fie previzibil
RADIUS = 100.0    # egal cu radius-ul din joystick (frontend)
DEADZONE = 0.08   #  ignor micile variații din centru
MAX_OUT = 100     # ieșirea maximă pentru motoare (%)
TURN_K = 1.0      # factor de viraj (1 = normal)

def clamp(v, lo, hi):
    #  limitez o valoare între [lo, hi]
    return max(lo, min(hi, v))

def apply_deadzone(v, dz=DEADZONE):
    #  fac zona moartă ca să nu tremure pe centru
    return 0.0 if abs(v) < dz else v
# ------------------------------------------------------


# -------------------- CAMERA --------------------------
# pornesc camera și trimit MJPEG către browser
              
cam = Picamera2()
config = cam.create_video_configuration(
    main={
        "size": (640, 360),
        "format": "BGR888" 
    }
)
cam.configure(config)
cam.start()

def mjpeg():
    while True:
        frame = cam.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
        ok, jpg = cv2.imencode('.jpg', frame, encode_param)
        
        if ok:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')

# -------------------- RUTE SERVER ---------------------
@app.route('/')
def index():
    # servesc pagina principală
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/video')
def video():
    #  servesc fluxul video în format MJPEG
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/distance')
def get_distance():
    cm = sensor.distance()
    return jsonify(cm=cm)


@app.route('/drive', methods=['POST'])
def drive():
    #  primesc datele de la joystick (x, y, speed, angle)
    d = request.get_json(silent=True) or {}

    #  extrag valorile ca întregi
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))  # cât de tare împing joystickul
    
   # angle = int(d.get('angle', 0))# angle îl primesc, dar nu-l folosesc aici

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

    # Citim distanța actuală
    dist = sensor.distance()

    # 2. Verificăm condiția de stop
    # Dacă distanța e validă (mai mare ca 0) 
    # ȘI e mai mică de 20cm 
    # ȘI utilizatorul vrea să meargă în față (speed > 0)
    if 0 < dist < 20 and ny > 0:
        left = 0
        right = 0
        print("STOP! Obstacol detectat.")

    # --------------------------------
    # 5)  trimit efectiv la motoare 
    motor.set_left(left)
    motor.set_right(right)

    # trimit înapoi valori pentru debug în UI
    return jsonify(ok=True, left=left, right=right, x=x, y=y, speed=speed)
# ------------------------------------------------------


# -------------------- MAIN ----------------------------
if __name__ == '__main__':
    # pornesc serverul Flask pe toate interfețele
    app.run(host='0.0.0.0', port=8000, threaded=True, debug=False, use_reloader=False)
# ------------------------------------------------------
