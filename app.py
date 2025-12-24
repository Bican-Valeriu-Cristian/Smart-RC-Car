from flask import Flask, Response, request, jsonify
import motor
import sensor  # Acesta va importa noul fisier sensor.py "clean"
import threading
import time


# IMPORT CAMERA
from camera import mjpeg, cleanup as camera_cleanup

app = Flask(__name__)

# ------------------- SETĂRI -------------------
RADIUS = 100.0
MAX_OUT = 100
TURN_K = 1.0
SAFE_DISTANCE_CM = 20.0

current_ny = 0.0

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# -------------------- (WATCHDOG) --------------------
# Rulează în fundal și oprește robotul dacă se apropie de zid
def safety_watchdog():
    global current_ny

    print("Watchdog de siguranță activat...")
    
    while True:
        # Aici folosim noua funcție din sensor.py
        dist = sensor.get_distance()
        
        # Dacă avem o citire validă, suntem sub 20cm și robotul vrea să meargă în față
        if dist > 0 and dist < SAFE_DISTANCE_CM and current_ny > 0:
            print(f"Watchdog: ZID la {dist}cm -> STOP FORTAT")
            motor.stop()
            # Resetăm comanda ca să nu pornească iar singur
            current_ny = 0 

        time.sleep(0.1)  # Verifică de 10 ori pe secundă


# -------------------- RUTE ---------------------
@app.route('/')
def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Eroare: Fisierul index.html lipseste!"


@app.route('/video')
def video():
    return Response(mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/distance')
def route_get_distance():
    # Returnează distanța curentă către interfața web (pentru afișare)
    return jsonify(cm=sensor.get_distance())


@app.route('/drive', methods=['POST'])
def drive():
    global current_ny

    d = request.get_json(silent=True) or {}
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))

    nx = clamp(x / 100, -1, 1)
    ny = clamp(-y / 100, -1, 1)

    current_ny = ny  # Actualizăm variabila globală pentru watchdog

    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    left = int(left_u * speed)
    right = int(right_u * speed)

    # --- VERIFICARE SIGURANȚĂ ȘI ÎN RUTA DE DRIVE ---
    # Citim distanța actuală
    dist = sensor.get_distance()

    # Dacă distanța e critică și utilizatorul vrea să meargă în față (ny > 0)
    if 0 < dist < SAFE_DISTANCE_CM and ny > 0:
        left = 0
        right = 0
        current_ny = 0
        print(f"Drive refuzat! Obstacol la {dist} cm.")

    motor.set_left(left)
    motor.set_right(right)

    return jsonify(ok=True, left=left, right=right)


if __name__ == '__main__':
    try:
        # Pornim thread-ul de siguranță
        t = threading.Thread(target=safety_watchdog, daemon=True)
        t.start()

        # Pornim serverul web
        app.run(host='0.0.0.0', port=8000, threaded=True, debug=False)
    
    except KeyboardInterrupt:
        print("\nOprire server...")
        
    finally:
        print("Curățare resurse...")
        motor.cleanup()
        camera_cleanup()
        sensor.close() # Închidem și senzorul corect