from flask import Flask, Response, request, jsonify
import motor
import sensor
import env_sensors  # <--- IMPORTUL NOSTRU
import threading
import time
from camera import mjpeg, cleanup as camera_cleanup

app = Flask(__name__)

# --- CONSTANTE SIGURANȚĂ ---
SAFE_DISTANCE_CM = 20.0
current_ny = 0.0
TURN_K = 1.0

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# --- WATCHDOG SIGURANȚĂ (MOTOR) ---
def safety_watchdog():
    global current_ny
    while True:
        dist = sensor.get_distance()
        if dist > 0 and dist < SAFE_DISTANCE_CM and current_ny > 0:
            print(f"Watchdog: ZID la {dist}cm -> STOP FORTAT")
            motor.stop()
            current_ny = 0 
        time.sleep(0.1)

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

# --- RUTĂ NOUĂ TELEMETRIE ---
@app.route('/telemetry')
def route_telemetry():
    # 1. Luăm distanța ultrasonică
    dist = sensor.get_distance()
    
    # 2. Luăm datele de mediu din env_sensors.py
    env_data = env_sensors.get_data()
    
    # 3. Le combinăm
    response = {
        "distance_cm": dist,
        "gas_volts": env_data["gas_volts"],
        "gas_alert": env_data["gas_alert"],
        "temp": env_data["temp"],
        "hum": env_data["hum"]
    }
    return jsonify(response)

@app.route('/drive', methods=['POST'])
def drive():
    global current_ny

    d = request.get_json(silent=True) or {}
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))

    nx = clamp(x / 100, -1, 1)
    ny = clamp(-y / 100, -1, 1)
    current_ny = ny 

    # Logică viraj
    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    left = int(left_u * speed)
    right = int(right_u * speed)

    # Verificare siguranță directă
    dist = sensor.get_distance()
    if 0 < dist < SAFE_DISTANCE_CM and ny > 0:
        left = 0
        right = 0
        current_ny = 0
        # print("Refuz drive: obstacol")

    motor.set_left(left)
    motor.set_right(right)

    return jsonify(ok=True)

if __name__ == '__main__':
    try:
        # 1. Thread Siguranță Distanță
        t = threading.Thread(target=safety_watchdog, daemon=True)
        t.start()

        # 2. Thread Senzori Mediu (Gaz/Temp)
        env_sensors.start_monitoring()

        print("Server Web Pornit...")
        app.run(host='0.0.0.0', port=8000, threaded=True, debug=False)
    
    except KeyboardInterrupt:
        print("\nOprire server...")
        
    finally:
        print("Curățare resurse...")
        motor.cleanup()
        camera_cleanup()
        sensor.close()
        env_sensors.cleanup()