def auto_pilot_loop():
    global AUTO_MODE, ACC_MODE
    
    # Constante Auto-Pilot Normal
    VITEZA_FATA = 60    
    VITEZA_VIRAJ = 50
    PRAG_PERICOL_AI = 140
    
    # Constante ACC (Adaptive Cruise Control) pur ULTRASONIC
    VITEZA_MAX_ACC = 45
    VITEZA_MIN_ACC = 15    # Sub acest prag, motoarele nu mai au cuplu
    DISTANTA_LIBER = 75.0  # cm - La peste 60cm de obiect, merge la viteză maximă
    DISTANTA_STOP = 15.0   # cm - La sub 15cm, mașina oprește complet
    
    while app_running:
        # Dacă ambele sunt oprite, așteptăm (nu consumăm procesor)
        if not AUTO_MODE and not ACC_MODE:
            time.sleep(0.5)
            continue
            
        # ========================================================
        # MODUL 1: ACC (Adaptive Cruise Control) - DOAR ULTRASONIC
        # ========================================================
        if ACC_MODE:
            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            DISTANTA_LIBER = 60.0  
            DISTANTA_STOP = 15.0   
            
            # --- 1. CALCUL VITEZĂ (Senzor Ultrasonic) ---
            if dist < 2 or dist <= DISTANTA_STOP:
                viteza_baza = 0
            elif dist >= DISTANTA_LIBER:
                viteza_baza = VITEZA_MAX_ACC
            else:
                procent_liber = (dist - DISTANTA_STOP) / (DISTANTA_LIBER - DISTANTA_STOP)
                viteza_baza = int(VITEZA_MIN_ACC + (procent_liber * (VITEZA_MAX_ACC - VITEZA_MIN_ACC)))

            # --- 2. CALCUL DIRECȚIE (Cameră ArUco) ---
            # Presupunem că funcția din camera.py returnează o valoare între -1.0 (stânga maxim) și 1.0 (dreapta maxim). 
            # Dacă valoarea e 0, markerul e perfect pe centru. Dacă nu vede markerul deloc, returnează None.
            pozitie_x = get_aruco_position(target_id=6) 
            
            if viteza_baza > 0:
                if pozitie_x is not None:
                    # Marker găsit! Calculăm virajul.
                    # K_VIRAJ dictează cât de agresiv trage de volan (30 e un punct de plecare bun)
                    K_VIRAJ = 30 
                    corectie = int(pozitie_x * K_VIRAJ)
                    
                    # Aplicăm diferența de putere pe roți
                    motor_stanga = viteza_baza + corectie
                    motor_dreapta = viteza_baza - corectie
                    
                    # Ne asigurăm că motoarele nu primesc valori peste 100 sau sub 0 în modul ACC
                    motor_stanga = clamp(motor_stanga, 0, 100)
                    motor_dreapta = clamp(motor_dreapta, 0, 100)
                    
                    motor.set_left(motor_stanga)
                    motor.set_right(motor_dreapta)
                    print(f"[ACC+ArUco] Dist: {dist:.1f}cm | Vit: {viteza_baza}% | Viraj: {corectie}")
                else:
                    # Nu vede markerul 6, dar drumul e liber. Merge drept.
                    # (Opțional: o poți pune să se oprească aici dacă vrei să nu plece de nebună)
                    motor.set_left(viteza_baza)
                    motor.set_right(viteza_baza)
                    print(f"[ACC] Dist: {dist:.1f}cm | Caut markerul 6...")
            else:
                motor.stop()
                
            time.sleep(0.1)
            continue  # Reia bucla doar pentru ACC (evitând procesarea AI de mai jos)
            
        # ========================================================
        # MODUL 2: AUTO-PILOT NORMAL (Evadare obstacole)
        # ========================================================
        if AUTO_MODE:
            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            # OPTIMIZARE: Procesăm scorul camerei AI DOAR aici, când suntem în modul care are nevoie de el
            stanga, centru, dreapta = get_ai_scores()
            
            # STAREA DE URGENȚĂ (Reflex Ultrasonic)
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

            # STAREA DE ANALIZĂ ȘI VIRAJ (Scor Cameră AI)
            elif centru > PRAG_PERICOL_AI:
                print(f"[FSM] Obstacol Video ({centru:.0f}). PUNEM FRÂNĂ...")
                motor.stop()
                time.sleep(0.75) 
                
                # Citim din nou camera să vedem situația actualizată după oprire
                stanga_clar, _, dreapta_clar = get_ai_scores()
                
                if stanga_clar < dreapta_clar:
                    print("[FSM] Viraj STÂNGA <-")
                    motor.set_left(-VITEZA_VIRAJ)
                    motor.set_right(VITEZA_VIRAJ)
                else:
                    print("[FSM] Viraj DREAPTA ->")
                    motor.set_left(VITEZA_VIRAJ)
                    motor.set_right(-VITEZA_VIRAJ)
                
                time.sleep(0.75) 
                motor.stop()
                time.sleep(0.75) 
                
            # STAREA DE NAVIGARE LINIȘTITĂ
            else:
                motor.set_left(VITEZA_FATA)
                motor.set_right(VITEZA_FATA)
                
            time.sleep(0.1)




/////
from flask import Flask, Response, request, jsonify, render_template
import motor
import sensor
import env_sensors 
import threading
import time

# Importăm funcțiile din camera.py (inclusiv get_aruco_position)
from camera import mjpeg, cleanup as camera_cleanup, set_mod_vizualizare, get_ai_scores, get_aruco_position

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
            
            # Watchdog-ul intervine DOAR pe condusul manual 
            if 2 < dist < SAFE_DISTANCE_CM and current_ny > 0 and not AUTO_MODE:
                print(f"Watchdog Manual: ZID la {dist:.1f}cm -> STOP FORTAT")
                motor.stop()
                current_ny = 0 
        except Exception as e:
            pass
            
        time.sleep(0.1)

# ==========================================
# --- RUTE WEB ---
# ==========================================

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
        "hum": env_data.get("hum", 0)
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
        
    return jsonify(acc=ACC_MODE)

# ==========================================
# --- SISTEME AUTONOME (FSM & ACC) ---
# ==========================================

def auto_pilot_loop():
    global AUTO_MODE, ACC_MODE
    
    # Constante Auto-Pilot FSM (Prădător)
    VITEZA_FATA = 60    
    VITEZA_VIRAJ = 50   
    VITEZA_CAUTARE = 35   
    VITEZA_APROPIERE = 60 
    
    # Constante ACC Hibrid
    VITEZA_MAX_ACC = 70
    VITEZA_MIN_ACC = 15    
    DISTANTA_LIBER_ACC = 60.0  
    DISTANTA_STOP_ACC = 15.0   
    
    # Memorie pentru căutare ArUco
    cadre_lipsa_aruco = 100 
    
    while app_running:
        # Dacă ambele sunt oprite, așteptăm (nu consumăm procesor)
        if not AUTO_MODE and not ACC_MODE:
            time.sleep(0.5)
            continue
            
        # ========================================================
        # MODUL 1: ACC (Adaptive Cruise Control) HIBRID
        # ========================================================
        if ACC_MODE:
            env_data = env_sensors.get_data()
            dist_curenta = env_data.get("distance_cm", 999)
            
            # Filtru anti-glitch senzor
            if dist_curenta > 400:
                dist_curenta = 100.0 
            
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
                    # Urmărește markerul
                    K_VIRAJ = 30 
                    corectie = int(pozitie_x * K_VIRAJ)
                    
                    # Nu lăsăm motoarele să depășească plafonul VITEZA_MAX_ACC
                    motor_stanga = clamp(viteza_baza + corectie, 0, VITEZA_MAX_ACC)
                    motor_dreapta = clamp(viteza_baza - corectie, 0, VITEZA_MAX_ACC)
                    
                    motor.set_left(motor_stanga)
                    motor.set_right(motor_dreapta)
                    print(f"[ACC+ArUco] Dist: {dist_curenta:.1f}cm | Vit: {viteza_baza}% | Viraj: {corectie}")
                else:
                    # SIGURANȚĂ: Nu vede markerul 6!
                    motor.stop()
                    print(f"[ACC] Siguranță: Am pierdut ținta! Aștept markerul 6...")
            else:
                motor.stop()
                
            time.sleep(0.1)
            continue 
            
        # ========================================================
        # MODUL 2: AUTO-PILOT FSM (Căutare "Stop-and-Stare", Interceptare, Parcare)
        # ========================================================
        if AUTO_MODE:
            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            if dist > 400:
                dist = 100.0
                
            pozitie_x = get_aruco_position(target_id=6)
            
            # --------------------------------------------------------
            # RAMURA 1: VEDE MARKERUL (Se concentrează 100% pe țintă)
            # --------------------------------------------------------
            if pozitie_x is not None:
                
                # FRÂNA DE FOCALIZARE (când tocmai a găsit markerul)
                if cadre_lipsa_aruco > 5:
                    print("[FSM] Țintă agățată! Frână pe loc pentru claritate...")
                    motor.stop()
                    cadre_lipsa_aruco = 0  
                    time.sleep(0.25)       
                    continue               
                
                cadre_lipsa_aruco = 0
                
                # A ajuns la destinație?
                if dist <= 25: 
                    print(f"[FSM] DESTINAȚIE ATINSĂ ({dist:.1f}cm)! Stau cuminte...")
                    motor.stop()
                else:
                    # Interceptare (Viraj lin spre el)
                    K_VIRAJ = 30 
                    corectie = int(pozitie_x * K_VIRAJ)
                    
                    m_stanga = clamp(VITEZA_APROPIERE + corectie, 0, VITEZA_APROPIERE)
                    m_dreapta = clamp(VITEZA_APROPIERE - corectie, 0, VITEZA_APROPIERE)
                    
                    motor.set_left(m_stanga)
                    motor.set_right(m_dreapta)
                    print(f"[FSM] Ținta blocată! Interceptare (Viraj: {corectie})")

            # --------------------------------------------------------
            # RAMURA 2: NU VEDE MARKERUL (E "orb" și scanează)
            # --------------------------------------------------------
            else:
                cadre_lipsa_aruco += 1
                
                # NOU: PARCAREA OARBĂ (Când e prea aproape de cameră)
                # Dacă l-a pierdut recent (< 20 cadre) ȘI e un obiect la sub 40cm, sigur e cutia!
                if dist <= 40 and cadre_lipsa_aruco < 20:
                    if dist <= 25:
                        print(f"[FSM] DESTINAȚIE ATINSĂ ({dist:.1f}cm)! (Sub unghiul camerei)")
                        motor.stop()
                    else:
                        print(f"[FSM] Marker prea aproape! Mă apropii orb... ({dist:.1f}cm)")
                        VITEZA_TARIRE = 30 # Merge foarte încet ultimii centimetri
                        motor.set_left(VITEZA_TARIRE)
                        motor.set_right(VITEZA_TARIRE)
                    time.sleep(0.1)
                    continue 

                # REFLEXUL DE SUPRAVIEȚUIRE intervine DOAR când e pe cale să lovească ceva necunoscut
                if 2 < dist < 15:
                    print("[FSM] Reflex: Am dat de un zid pe nevăzute! Evitare...")
                    motor.set_left(-VITEZA_FATA)
                    motor.set_right(-VITEZA_FATA)
                    time.sleep(0.8) 
                    motor.set_left(VITEZA_VIRAJ) 
                    motor.set_right(-VITEZA_VIRAJ)
                    time.sleep(0.5)
                    motor.stop()
                    cadre_lipsa_aruco = 100 
                    continue 
                
                # A pierdut markerul brusc și nu e nimic în față?
                if cadre_lipsa_aruco < 5:
                    motor.stop()
                    print("[FSM] Țintă pierdută brusc! Pun frână și focalizez...")
                
                # Niciun zid, nicio țintă. Radar în trepte!
                else:
                    print("[FSM] Radar activat: Rotesc 30 de grade...")
                    motor.set_left(VITEZA_CAUTARE)
                    motor.set_right(-VITEZA_CAUTARE)
                    time.sleep(0.2) 
                    
                    print("[FSM] Radar activat: Scanez imaginea...")
                    motor.stop()
                    time.sleep(0.5) 
                
            time.sleep(0.1)


# ==========================================
# --- PUNCT DE INTRARE APLICAȚIE ---
# ==========================================
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

        ///
        # ========================================================
        # MODUL 2: AUTO-PILOT FSM (Explorare, Radar, Interceptare)
        # ========================================================
        if AUTO_MODE:
            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            if dist > 400: dist = 100.0
                
            pozitie_x = get_aruco_position(target_id=6)
            
            # --------------------------------------------------------
            # RAMURA 1: VEDE MARKERUL
            # --------------------------------------------------------
            if pozitie_x is not None:
                rotatii_efectuate = 0 # REPARAT: L-a văzut, deci resetăm numărătoarea de explorare!
                
                if cadre_lipsa_aruco > 5:
                    print("[FSM] Țintă agățată! Frână pe loc...")
                    motor.stop()
                    cadre_lipsa_aruco = 0  
                    time.sleep(0.25)       
                    continue               
                
                cadre_lipsa_aruco = 0
                
                if dist <= 25: 
                    print(f"[FSM] DESTINAȚIE ATINSĂ ({dist:.1f}cm)!")
                    motor.stop()
                else:
                    K_VIRAJ = 30 
                    corectie = int(pozitie_x * K_VIRAJ)
                    m_stanga = clamp(VITEZA_APROPIERE + corectie, 0, VITEZA_APROPIERE)
                    m_dreapta = clamp(VITEZA_APROPIERE - corectie, 0, VITEZA_APROPIERE)
                    motor.set_left(m_stanga)
                    motor.set_right(m_dreapta)

            # --------------------------------------------------------
            # RAMURA 2: NU VEDE MARKERUL (Scanare și Explorare)
            # --------------------------------------------------------
            else:
                cadre_lipsa_aruco += 1
                
                if dist <= 40 and cadre_lipsa_aruco < 20:
                    if dist <= 25:
                        motor.stop()
                        cadre_lipsa_aruco = 0 
                    else:
                        VITEZA_TARIRE = 50 
                        motor.set_left(VITEZA_TARIRE)
                        motor.set_right(VITEZA_TARIRE)
                        cadre_lipsa_aruco = 0 
                    time.sleep(0.1)
                    continue 

                if 2 < dist < 15:
                    print("[FSM] Reflex: Zid! Evitare...")
                    motor.set_left(-VITEZA_FATA)
                    motor.set_right(-VITEZA_FATA)
                    time.sleep(0.8) 
                    motor.set_left(VITEZA_VIRAJ) 
                    motor.set_right(-VITEZA_VIRAJ)
                    time.sleep(0.5)
                    motor.stop()
                    cadre_lipsa_aruco = 100 
                    rotatii_efectuate = 0 # Și-a schimbat locul fugind, deci resetăm explorarea
                    continue 
                
                if cadre_lipsa_aruco < 5:
                    motor.stop()
                
                # NOU: RADAR SAU EXPLORARE!
                else:
                    # Dacă a scanat de mai puțin de 12 ori (un cerc de 360 grade)
                    if rotatii_efectuate < 7:
                        print(f"[FSM] Radar ({rotatii_efectuate}/12): Rotesc scurt...")
                        motor.set_left(VITEZA_CAUTARE)
                        motor.set_right(-VITEZA_CAUTARE)
                        time.sleep(0.4) 
                        
                        motor.stop()
                        time.sleep(0.5) 
                        rotatii_efectuate += 1
                        
                    # Dacă s-a învârtit complet în jurul axei și nu a găsit nimic
                    else:
                        print("[FSM] Radar complet. Nu e aici! Explorez mai departe...")
                        # Mergem în față ca să schimbăm zona camerei
                        motor.set_left(VITEZA_FATA)
                        motor.set_right(VITEZA_FATA)
                        time.sleep(1.0) # Merge o secundă în față
                        
                        motor.stop()
                        time.sleep(0.5)
                        
                        # Resetăm numărătoarea ca să înceapă din nou radarul în noul loc
                        rotatii_efectuate = 0 
                
            time.sleep(0.1)
