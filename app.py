from flask import Flask, Response, request, jsonify
import cv2
from picamera2 import Picamera2
import motor, sensor  # le las aici in caz ca vreau sa le folosesc mai tarziu

app = Flask(__name__)

# ------------------- SETARI CONTROL -------------------
# aici setez niste valori de baza pentru controlul masinii
RADIUS = 100.0   # trebuie sa fie la fel ca "radius" din joystick (frontend)
DEADZONE = 0.08  # zona moarta (cand joystick-ul e aproape pe centru, nu face nimic)
MAX_OUT = 100    # iesirea maxima pentru motoare (%)
TURN_K = 1.0     # cat de brusc vireaza (1 = normal, mai mic = vireaza mai moale)

# o functie simpla ca sa nu depasesc limitele
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# aici fac ca joystickul sa ignore micile miscari cand e aproape pe centru
def apply_deadzone(v, dz=DEADZONE):
    return 0.0 if abs(v) < dz else v
# ------------------------------------------------------


# -------------------- CAMERA --------------------------
# aici pornesc camera si o configurez
cam = Picamera2()
cam.configure(cam.create_video_configuration(main={"size": (640, 480)}))
cam.start()

# functia asta trimite cadrele video unul dupa altul catre browser
def mjpeg():
    while True:
        frame = cam.capture_array()

        # scriu un text mic pe video, doar ca sa stiu ca merge
        cv2.putText(frame, "SmartCar", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # comprim imaginea ca jpg (pentru fluxul video)
        ok, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')
# ------------------------------------------------------


# -------------------- RUTE SERVER ---------------------
@app.route('/')
def index():
    # cand accesez serverul in browser, trimit pagina principala
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/video')
def video():
    # ruta care intoarce fluxul video
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/drive', methods=['POST'])
def drive():
    # aici ajung datele trimise de joystick (x, y, speed, angle)
    d = request.get_json(silent=True) or {}

    # extrag valorile si ma asigur ca sunt numere
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))  # cat de tare imping joystickul
    # angle il primesc, dar momentan nu il folosesc

    # 1. normalizare: pun valorile in intervalul [-1, 1]
    # invers y ca sa fie "sus" = inainte
    nx = clamp(x / RADIUS, -1, 1)
    ny = clamp(-y / RADIUS, -1, 1)

    # 2. aplic zona moarta (sa nu tremure cand joystickul e pe centru)
    nx = apply_deadzone(nx)
    ny = apply_deadzone(ny)

    # 3. calculez directiile pentru motoarele din stanga si dreapta
    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    # 4. aplic viteza generala (acceleratia)
    s = clamp(speed / 100.0, 0, 1)
    left = int(left_u * s * MAX_OUT)
    right = int(right_u * s * MAX_OUT)

    # daca vreau sa testez fara sa misc masina, las linia asta comentata
    # motor.set_left(left)
    # motor.set_right(right)

    # trimit inapoi valorile ca sa vad ce face joystickul
    return jsonify(ok=True, left=left, right=right, x=x, y=y, speed=speed)
# ------------------------------------------------------


# -------------------- MAIN ----------------------------
# aici rulez serverul Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, threaded=True)
# ------------------------------------------------------
