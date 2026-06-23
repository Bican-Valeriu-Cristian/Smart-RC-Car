from flask import Flask, Response, request, jsonify, render_template
import motor
import sensor
import env_sensors 
import threading
import time

from camera import mjpeg, cleanup as camera_cleanup, set_mod_vizualizare, get_ai_scores, get_aruco_position,set_auto_active

app = Flask(__name__)

# --- CONSTANTE SIGURANȚĂ ---
SAFE_DISTANCE_CM = 20.0
current_ny = 0.0
TURN_K = 1.0
app_running = True
AUTO_MODE = False
ACC_MODE = False

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def safety_watchdog():
    global current_ny, app_running 
    
    while app_running:  
        try:  
            dist = sensor.get_distance()
            env_sensors.set_distance(dist)
            
            # Watchdog-ul 
            if 2 < dist < SAFE_DISTANCE_CM and current_ny > 0 and not AUTO_MODE:
                print(f"Watchdog Manual: ZID la {dist:.1f}cm -> STOP FORTAT")
                motor.stop()
                current_ny = 0 
        except Exception as e:
            pass
            
        time.sleep(0.1)

# --- RUTE WEB ---

@app.route('/')
def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Eroare: Fișierul index.html lipsește!", 404

@app.route('/schimba_mod', methods=['POST'])
def schimba_mod():
    mod_nou = request.form.get('mod')
    if mod_nou in ['normal', 'midas']:
        set_mod_vizualizare(mod_nou) 
        return "OK"
    return "Eroare", 400

@app.route('/video')
def video():
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/telemetry')
def route_telemetry():
    env_data = env_sensors.get_data()
    
    response = {
        "distance_cm": env_data.get("distance_cm", 0),
        "gas_volts": env_data.get("gas_volts", 0),
        "gas_alert": env_data.get("gas_alert", False),
        "temp": env_data.get("temp", 0),
        "hum": env_data.get("hum", 0),
        "auto_mode": AUTO_MODE
    }
    return jsonify(response)

@app.route('/drive', methods=['POST'])
def drive():
    global current_ny
    if AUTO_MODE or ACC_MODE:
        return jsonify(ok=False, msg="Mod Autonom ON")

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

    # Verificare de siguranță pentru modul manual
    env_data = env_sensors.get_data()
    dist = env_data.get("distance_cm", 999)
    
    if 2 < dist < SAFE_DISTANCE_CM and ny > 0:
        left = 0
        right = 0
        current_ny = 0

    motor.set_left(left)
    motor.set_right(right)

    return jsonify(ok=True)

@app.route('/toggle_auto', methods=['POST'])
def toggle_auto():
    global AUTO_MODE, ACC_MODE, current_ny
    AUTO_MODE = not AUTO_MODE
    
    if AUTO_MODE:
        ACC_MODE = False  # Oprim ACC-ul dacă era pornit
        current_ny = 0 
        print("Mod Prădător (Căutare ArUco) ACTIVAT")
    else:
        motor.stop() 
        print("Mod Prădător DEZACTIVAT")
    set_auto_active(AUTO_MODE or ACC_MODE)    
    return jsonify(auto=AUTO_MODE)

@app.route('/toggle_acc', methods=['POST'])
def toggle_acc():
    global AUTO_MODE, ACC_MODE, current_ny
    ACC_MODE = not ACC_MODE
    
    if ACC_MODE:
        AUTO_MODE = False  # Oprim Auto-Pilot-ul normal dacă era pornit
        current_ny = 0 
        print("Mod ACC (Urmărire Ultrasonică + ArUco) ACTIVAT")
    else:
        motor.stop() 
        print("Mod ACC DEZACTIVAT")
    set_auto_active(AUTO_MODE or ACC_MODE)   
    return jsonify(acc=ACC_MODE)

# --- SISTEME AUTONOME (FSM & ACC) ---

def auto_pilot_loop():
    global AUTO_MODE, ACC_MODE
    
    # Constante Auto-Pilot FSM 
    VITEZA_FATA = 45   
    VITEZA_VIRAJ = 50   
    VITEZA_CAUTARE = 35   
    VITEZA_APROPIERE = 60 
    PRAG_PERICOL_AI = 130
    
    # Constante ACC Hibrid
    VITEZA_MAX_ACC = 60
    VITEZA_MIN_ACC = 15    
    DISTANTA_LIBER_ACC = 60.0  
    DISTANTA_STOP_ACC = 15  

    memorie_urmarire = 0 
    
    # Memorie pentru căutare ArUco
    cadre_lipsa_aruco = 100 
    
    while app_running:
        # Dacă ambele sunt oprite, așteptăm (nu consumăm procesor)
        if not AUTO_MODE and not ACC_MODE:
            time.sleep(0.5)
            continue
            
        # MODUL 1: ACC (Adaptive Cruise Control) HIBRID
        
        if ACC_MODE:
            env_data = env_sensors.get_data()
            dist_curenta = env_data.get("distance_cm", 999)
            
        
            
            # 1. CALCUL VITEZĂ (Senzor Ultrasonic)
            if dist_curenta < 2 or dist_curenta <= DISTANTA_STOP_ACC:
                viteza_baza = 0
            elif dist_curenta >= DISTANTA_LIBER_ACC:
                viteza_baza = VITEZA_MAX_ACC
            else:
                procent_liber = (dist_curenta - DISTANTA_STOP_ACC) / (DISTANTA_LIBER_ACC - DISTANTA_STOP_ACC)
                viteza_baza = int(VITEZA_MIN_ACC + (procent_liber * (VITEZA_MAX_ACC - VITEZA_MIN_ACC)))

            # 2. CALCUL DIRECȚIE (Cameră ArUco)
            pozitie_x = get_aruco_position(target_id=6) 
            
            if viteza_baza > 0:
                if pozitie_x is not None:
                    # Vede markerul -> Calculează virajul și trage de volan
                    K_VIRAJ = 50 
                    corectie = int(pozitie_x * K_VIRAJ)
                    
                    # Nu lăsăm motoarele să depășească plafonul VITEZA_MAX_ACC
                    motor_stanga = clamp(viteza_baza + corectie, 0, VITEZA_MAX_ACC)
                    motor_dreapta = clamp(viteza_baza - corectie, 0, VITEZA_MAX_ACC)
                    
                    motor.set_left(motor_stanga)
                    motor.set_right(motor_dreapta)
                    print(f"[ACC+ArUco] Dist: {dist_curenta:.1f}cm | Vit: {viteza_baza}% | Viraj: {corectie}")
                else:
                    # Nu vede markerul -> Merge drept ca un ACC normal
                    motor.set_left(viteza_baza)
                    motor.set_right(viteza_baza)
                    print(f"[ACC NORMAL] Dist: {dist_curenta:.1f}cm | Merg drept cu: {viteza_baza}%")
            else:
                # E prea aproape de obstacol (sub DISTANTA_STOP_ACC)
                motor.stop()
                print(f"[ACC] Frână pusă! Obstacol la {dist_curenta:.1f}cm.")
                
            time.sleep(0.1)
            continue
            

        # MODUL 2: AUTO-PILOT NORMAL (Explorare + Interceptare ArUco)
        
        if AUTO_MODE:
            # Inițializăm timestamp-ul local dacă nu există deja în memorie
            if 'ultimul_timp_aruco' not in locals():
                ultimul_timp_aruco = 0.0

            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            stanga, centru, dreapta = get_ai_scores()
            pozitie_x = get_aruco_position(target_id=6)
            
            # 1. ACTUALIZARE TARGET LOCK: Salvăm timpul curent când codul e în cadru
            if pozitie_x is not None:
                ultimul_timp_aruco = time.time()
                
            # Memoria de Target Lock rămâne activă timp de 2.0 secunde după dispariția codului
            target_lock_activ = (time.time() - ultimul_timp_aruco) < 1

            # --- STAREA 1: VEDE MARKERUL (Prioritate maximă: Aliniere și Oprire) ---
            if pozitie_x is not None:
                if 2 < dist <= 30:
                    print(f"[FSM] GATA! Am ajuns în fața codului la {dist:.1f}cm.")
                    motor.stop()
                    AUTO_MODE = False  # Pune pauză totală
                else:
                    # Virează spre cod în timp ce merge în față
                    K_VIRAJ = 45 
                    corectie = int(pozitie_x * K_VIRAJ)
                    
                    # Permitem motoarelor să urce până la 100% ca să poată lua curba eficient
                    m_stanga = clamp(VITEZA_FATA + corectie, 0, 100)
                    m_dreapta = clamp(VITEZA_FATA - corectie, 0, 100)
                    
                    motor.set_left(m_stanga)
                    motor.set_right(m_dreapta)
                    print(f"[FSM] Mă duc spre cod! Viraj: {corectie}")
                time.sleep(0.1)
                continue # Sare peste detectarea de pereți ca să se concentreze doar pe marker

            # --- STAREA 1.5: OPRIRE CORECTĂ PRIN TARGET LOCK ---
            # Dacă ai pierdut codul din ochi (ești prea aproape), dar ești în lock și senzorul 
            # ultrasonic confirmă apropierea de perete, mașina oprește cu succes!
            if target_lock_activ and (2 < dist <= 30):
                print(f"[FSM] GATA (Target Lock)! Destinație atinsă la {dist:.1f}cm, chiar dacă am pierdut codul din ochi.")
                motor.stop()
                AUTO_MODE = False
                time.sleep(0.1)
                continue

            # --- STAREA 2: EVITARE URGENȚĂ ULTRASONICĂ (Zid la sub 10cm) ---
            if 2 < dist < 10:
                print("[FSM] Zid fizic! Dau cu spatele...")
                motor.set_left(-VITEZA_FATA)
                motor.set_right(-VITEZA_FATA)
                time.sleep(1)
                motor.stop()
                time.sleep(1)
                
                stanga_clar, _, dreapta_clar = get_ai_scores()
                if stanga_clar < dreapta_clar:
                    print("[FSM] Mai mult spațiu la stânga, virează stânga.")
                    motor.set_left(-VITEZA_VIRAJ)
                    motor.set_right(VITEZA_VIRAJ)
                else:
                    print("[FSM] Mai mult spațiu la dreapta, virează dreapta.")
                    motor.set_left(VITEZA_VIRAJ)
                    motor.set_right(-VITEZA_VIRAJ)
                
                time.sleep(0.75)
                motor.stop()
                continue # După manevra de evitare, re-evaluăm scena

            # --- STAREA 3: OCOLIRE OBSTACOLE CU MIDAS (AI) ---
            # MiDaS ocolește DOAR dacă NU ești în faza finală de abordare (Target Lock inactiv)
            elif centru > PRAG_PERICOL_AI and not target_lock_activ:
                print("[FSM] Obstacol văzut de AI. Ocolesc...")
                motor.stop()
                time.sleep(0.5) 
                
                stanga_clar, _, dreapta_clar = get_ai_scores()
                if stanga_clar < dreapta_clar:
                    motor.set_left(-VITEZA_VIRAJ)
                    motor.set_right(VITEZA_VIRAJ)
                else:
                    motor.set_left(VITEZA_VIRAJ)
                    motor.set_right(-VITEZA_VIRAJ)
                
                time.sleep(0.75) 
                motor.stop()
                continue # După ocolire, re-evaluăm scena
                
            # --- STAREA 4: PLIMBARE LIBERĂ (Nu vede nici cod, nici zid) ---
            else:
                # Dacă MiDaS se panică din cauza peretelui final, dar ai Target Lock, ignori AI-ul și mergi drept în față
                if centru > PRAG_PERICOL_AI and target_lock_activ:
                    print("[FSM] MiDaS vede peretele, dar TARGET LOCK e activ. Ignor AI-ul și merg drept spre destinație!")
                    
                motor.set_left(VITEZA_FATA)
                motor.set_right(VITEZA_FATA)
                
            time.sleep(0.1)



# --- PUNCT DE INTRARE APLICAȚIE ---

if __name__ == '__main__':
    try:
        # Pornire thread-uri de background
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
        # Semnalăm thread-urilor să se oprească
        app_running = False  
        time.sleep(0.5)      
        
        print("Curățare resurse hardware...")
        try: motor.cleanup()
        except: pass
        try: camera_cleanup()
        except: pass
        try: sensor.close()
        except: pass
        try: env_sensors.cleanup()
        except: pass
