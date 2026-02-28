from flask import Flask, Response, request, jsonify, render_template
import motor
import sensor
import env_sensors 
import threading
import time
from camera import mjpeg, cleanup as camera_cleanup, set_mod_vizualizare, get_ai_scores

app = Flask(__name__)

# CONSTANTE SIGURANȚĂ
SAFE_DISTANCE_CM = 20.0
current_ny = 0.0
TURN_K = 1.0
app_running = True
AUTO_MODE = False
PRAG_PERICOL_AI = 130  # Cat de aproape pana sa vireze(mai mic = vireaza mai devreme)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safety_watchdog():
    global current_ny, app_running 
    
    while app_running:  
        try:  
            
            dist = sensor.get_distance()
            env_sensors.set_distance(dist)
            
            # Watchdog-ul intervine DOAR pe condusul manual 
            if dist > 2 and dist < SAFE_DISTANCE_CM and current_ny > 0 and not AUTO_MODE:
                print(f"Watchdog Manual: ZID la {dist}cm -> STOP FORTAT")
                motor.stop()
                current_ny = 0 
        except Exception:
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

@app.route('/schimba_mod', methods=['POST'])
def schimba_mod():
    mod_nou = request.form.get('mod')
    if mod_nou in ['normal', 'midas']:
        set_mod_vizualizare(mod_nou) 
        return "OK"
    return "Eroare", 400

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
    if AUTO_MODE:
        return jsonify(ok=False, msg="Auto-Pilot ON")

    d = request.get_json(silent=True) or {}
    x = int(d.get('x', 0))
    y = int(d.get('y', 0))
    speed = int(d.get('speed', 0))

    nx = clamp(x / 100, -1, 1)
    ny = clamp(y / 100, -1, 1)
    current_ny = ny 

    turn = nx * TURN_K
    left_u = clamp(ny + turn, -1, 1)
    right_u = clamp(ny - turn, -1, 1)

    left = int(left_u * speed)
    right = int(right_u * speed)

    # Verificare pentru modul manual
    env_data = env_sensors.get_data()
    dist = env_data["distance_cm"]
    
    if 2 < dist < SAFE_DISTANCE_CM and ny > 0:
        left = 0
        right = 0
        current_ny = 0

    motor.set_left(left)
    motor.set_right(right)

    return jsonify(ok=True)

@app.route('/toggle_auto', methods=['POST'])
def toggle_auto():
    global AUTO_MODE, current_ny
    AUTO_MODE = not AUTO_MODE
    
    if not AUTO_MODE:
        motor.stop() 
        current_ny = 0 
        print("Autopilot DEZACTIVAT")
    else:
        current_ny = 0 
        print("Autopilot ACTIVAT")
        
    return jsonify(auto=AUTO_MODE)

# --- AUTOPILOT (FSM) ---
def auto_pilot_loop():
    global AUTO_MODE
    
    VITEZA_FATA = 40    
    VITEZA_VIRAJ = 50   
    
    while app_running:
        if not AUTO_MODE:
            time.sleep(0.5)
            continue
            
        # 1. COLECTARE DATE: Citim din memorie 
        env_data = env_sensors.get_data()
        dist = env_data["distance_cm"]
        stanga, centru, dreapta = get_ai_scores()
        
        # 2. STAREA 4: URGENȚĂ (Senzorul ultrasonic detectează un obstacol critic sub 15cm)
        if 2 < dist < 15:
            print("[FSM] Reflex Ultrasonic: OBSTACOL CRITIC! Evadare...")

            
            motor.set_left(-VITEZA_FATA)
            motor.set_right(-VITEZA_FATA)
            time.sleep(0.8) 
            
            motor.set_left(VITEZA_VIRAJ) 
            motor.set_right(-VITEZA_VIRAJ)
            time.sleep(0.75)
            
            motor.stop()
            time.sleep(0.75) 
            continue 

        # 3. STAREA 2 & 3: ANALIZĂ ȘI VIRAJ (AI-ul vizual vede un obstacol în față)
        elif centru > PRAG_PERICOL_AI:
            print(f"[FSM] Obstacol Video ({centru:.0f}). PUNEM FRÂNĂ...")
            motor.stop()
            time.sleep(0.75) 
            
            stanga_clar, _, dreapta_clar = get_ai_scores()
            
            # Comparăm părțile: Scorul mai mic înseamnă că obiectele sunt mai departe
            if stanga_clar < dreapta_clar:
                print(f"[FSM] Calea e mai liberă la STÂNGA (S:{stanga_clar:.0f} vs D:{dreapta_clar:.0f}) <-")
                motor.set_left(-VITEZA_VIRAJ)
                motor.set_right(VITEZA_VIRAJ)
            else:
                print(f"[FSM] Calea e mai liberă la DREAPTA (S:{stanga_clar:.0f} vs D:{dreapta_clar:.0f}) ->")
                motor.set_left(VITEZA_VIRAJ)
                motor.set_right(-VITEZA_VIRAJ)
            
            time.sleep(0.75) 
            
            motor.stop()
            time.sleep(0.75) 
            
        # 4. STAREA 1: NAVIGARE NORMALĂ (Drum liber)
        else:
            motor.set_left(VITEZA_FATA)
            motor.set_right(VITEZA_FATA)
            
        time.sleep(0.1) 

if __name__ == '__main__':
    try:
        t = threading.Thread(target=safety_watchdog, daemon=True)
        t.start()

        env_sensors.start_monitoring()
        
        t_auto = threading.Thread(target=auto_pilot_loop, daemon=True)
        t_auto.start()

        print("Server Web Pornit pe portul 8000...")
        app.run(host='0.0.0.0', port=8000, threaded=True, debug=False)
    
    except KeyboardInterrupt:
        print("\nOprire server...")
        
    finally:
        app_running = False  
        time.sleep(0.5)      
        
        print("Curățare resurse...")
        try: motor.cleanup()
        except: pass
        try: camera_cleanup()
        except: pass
        try: sensor.close()
        except: pass
        try: env_sensors.cleanup()
        except: pass