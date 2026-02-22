from flask import Flask, Response, request, jsonify
import motor
import sensor
import env_sensors 
import threading
import time
from camera import mjpeg, cleanup as camera_cleanup

app = Flask(__name__)

# CONSTANTE SIGURANȚĂ
SAFE_DISTANCE_CM = 20.0
current_ny = 0.0
TURN_K = 1.0
app_running = True

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# WATCHDOG SIGURANȚĂ (MOTOR)
def safety_watchdog():
    global current_ny, app_running 
    
    while app_running:  
        try:  
            dist = sensor.get_distance()
            env_sensors.set_distance(dist)
            
            if dist > 0 and dist < SAFE_DISTANCE_CM and current_ny > 0:
                print(f"Watchdog: ZID la {dist}cm -> STOP FORTAT")
                motor.stop()
                current_ny = 0 
        except Exception:
            # Dacă dă eroare la citire, ignorăm
            pass
            
        time.sleep(0.1)

# RUTE 
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

@app.route('/telemetry')
def route_telemetry():
    env_data = env_sensors.get_data()
    
    response = {
        "distance_cm": env_data["distance_cm"],
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
    ny = clamp(y / 100, -1, 1)
    current_ny = ny 

    # Logică viraj
    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    left = int(left_u * speed)
    right = int(right_u * speed)

    # VERIFICĂ PERICOL Distanță
    env_data = env_sensors.get_data()
    dist = env_data["distance_cm"]
    
    if 0 < dist < SAFE_DISTANCE_CM and ny > 0:
        left = 0
        right = 0
        current_ny = 0

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
        # Oprire ordonată a thread-urilor și curățare pini
        app_running = False  
        time.sleep(0.5)      
        
        print("Curățare resurse...")
        try:
            motor.cleanup()
        except: pass
        
        try:
            camera_cleanup()
        except: pass
        
        try:
            sensor.close()
        except: pass
        
        try:
            env_sensors.cleanup()
        except: pass