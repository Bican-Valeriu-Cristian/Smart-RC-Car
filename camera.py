import cv2
import time
import threading
import numpy as np
from picamera2 import Picamera2

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter

# --- CLASA OPTIMIZATĂ PENTRU MIDAS ---

class MidasObstacleDetector:
    def __init__(self, model_path="/home/pi/Desktop/SD_Bux/SmartCar/midas_v2_1_small_256.tflite"):
        
        # 2 thread-uri (fără supraîncălzire)
        self.interpreter = Interpreter(model_path=model_path, num_threads=2)
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # Valorile de normalizare pentru MiDaS
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def process_frame(self, frame_bgr):
        # 1. PREPROCESARE DIRECTĂ: Convertim direct din BGR în RGB 
        img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (256, 256))
        
        img_normalized = (img_resized.astype(np.float32) / 255.0 - self.mean) / self.std
        input_tensor = np.expand_dims(img_normalized, axis=0)

        # 2. RULAREA MODELULUI 
        self.interpreter.set_tensor(self.input_details[0]['index'], input_tensor)
        self.interpreter.invoke() 
        
        # 3. EXTRAGEREA HĂRȚII DE ADÂNCIME
        depth_map = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        depth_map = np.squeeze(depth_map) 

        # 4. VIZUALIZARE HARTĂ DE ADÂNCIME
        depth_min, depth_max = depth_map.min(), depth_map.max()
        if depth_max - depth_min > 1e-6:
            depth_normalized = (depth_map - depth_min) / (depth_max - depth_min)
        else:
            depth_normalized = np.zeros_like(depth_map)
            
        depth_visual = (depth_normalized * 255).astype(np.uint8)

        # 5. ANALIZA ZONEI PENTRU AUTOPILOT
        h, w = depth_visual.shape
        third = w // 3
        stanga = np.mean(depth_visual[:, :third])
        centru = np.mean(depth_visual[:, third:2*third])
        dreapta = np.mean(depth_visual[:, 2*third:])

        return depth_visual, stanga, centru, dreapta

# --- INIȚIALIZARE HARDWARE ---
detector = MidasObstacleDetector("midas_v2_1_small_256.tflite")

# Inițializare detector ArUco
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

cam = Picamera2()
config = cam.create_video_configuration(
    
    main={"size": (640, 360), "format": "BGR888"},
    controls={
        "AfMode": 2,          
        "AwbEnable": True,    
        "NoiseReductionMode": 1,
        "ExposureTime": 8000,    # 8ms pentru a elimina motion blur-ul
        "AnalogueGain": 0      # Gain mărit fix (ajustează între 1.0 și 8.0 dacă e prea întunecat/luminos)
    }
)
cam.configure(config)
cam.start()

# --- VARIABILE GLOBALE ---
latest_frame_bgr = None       # Frame-ul cel mai proaspăt în format BGR
depth_visual_global = None    # Ultima hartă MiDaS colorată
ai_scores = (0, 0, 0)         
aruco_target_x = None         
aruco_target_size = None      
aruco_corners_cache = None    
aruco_center_cache = None     
_running = True
MOD_VIZUALIZARE = "normal"
IS_AUTO_ACTIVE = False
JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 70] 

data_lock = threading.Lock()

# Event-uri pentru trezirea thread-urilor
new_frame_event_aruco = threading.Event()
new_frame_event_midas = threading.Event()


def set_mod_vizualizare(mod):
    global MOD_VIZUALIZARE
    with data_lock: 
        MOD_VIZUALIZARE = mod
    print(f"Camera a trecut în modul: {MOD_VIZUALIZARE}")

def get_ai_scores():
    with data_lock: 
        return ai_scores

def set_auto_active(stare):
    global IS_AUTO_ACTIVE
    with data_lock:
        IS_AUTO_ACTIVE = stare

def get_aruco_position(target_id=6):
    with data_lock:
        return aruco_target_x

def get_aruco_size(target_id=6):
    with data_lock:
        return aruco_target_size


def camera_loop():
    """Capturează frame-uri la viteză maximă și anunță thread-urile AI."""
    global latest_frame_bgr
    while _running:
        try:
            frame = cam.capture_array()
            
            with data_lock:
                # Salvăm referința direct (fără .copy() costisitor)
                latest_frame_bgr = frame
            
            new_frame_event_aruco.set()
            new_frame_event_midas.set()
            
        except Exception as e:
            print(f"Eroare la captura camerei: {e}")
            time.sleep(0.1)


def aruco_loop():
    """Thread ultra-rapid pentru detecția ArUco (Rulează la ~30 FPS)."""
    global aruco_target_x, aruco_target_size, aruco_corners_cache, aruco_center_cache
    TARGET_ID = 6
    
    while _running:
        if not new_frame_event_aruco.wait(timeout=1.0):
            continue
        new_frame_event_aruco.clear()
        
        with data_lock:
            if latest_frame_bgr is None:
                continue
            # Doar citim, nu modificăm, deci nu avem nevoie de .copy()
            frame_de_analizat = latest_frame_bgr
        
        try:
            
            gray_for_aruco = cv2.cvtColor(frame_de_analizat, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = aruco_detector.detectMarkers(gray_for_aruco)
            
            current_target_x = None
            current_target_size = None
            current_corners = None
            current_center = None
            
            if ids is not None:
                for i in range(len(ids)):
                    if ids[i][0] == TARGET_ID:
                        marker_corners = corners[i][0]
                        cx = int(np.mean(marker_corners[:, 0]))
                        cy = int(np.mean(marker_corners[:, 1]))
                        current_target_x = (cx - 320) / 320.0
                        
                        laturi = []
                        for j in range(4):
                            p1 = marker_corners[j]
                            p2 = marker_corners[(j + 1) % 4]
                            latura = np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                            laturi.append(latura)
                        current_target_size = float(np.mean(laturi))
                        
                        current_corners = corners[i]
                        current_center = (cx, cy)
                        break
            
            with data_lock:
                aruco_target_x = current_target_x
                aruco_target_size = current_target_size
                aruco_corners_cache = current_corners
                aruco_center_cache = current_center
                
        except Exception as e:
            print(f"Eroare ArUco: {e}")


def midas_loop():
    """
    Thread dedicat MiDaS optimizat termic.
    Rulează pe 2 thread-uri hardware (rapid), dar face pauze lungi ca să nu încingă Pi-ul.
    """
    global depth_visual_global, ai_scores
    
    while _running:
        if not new_frame_event_midas.wait(timeout=1.0):
            continue
        new_frame_event_midas.clear()
        
        with data_lock:
            if latest_frame_bgr is None:
                continue
            mod_curent = MOD_VIZUALIZARE
            auto_activ = IS_AUTO_ACTIVE
            frame_de_analizat = latest_frame_bgr  # Nu facem .copy(), citim direct
        
        # Rulează doar dacă este activat modul sau pilotul automat
        ruleaza_midas = (mod_curent == "midas") or auto_activ
        if not ruleaza_midas:
            time.sleep(0.2)  # Idle total dacă nu e folosit
            continue
        
        try:
           # Procesăm frame-ul cu MiDaS și obținem harta de adâncime + scorurile AI
            depth_map, s, c, d = detector.process_frame(frame_de_analizat)
            
            depth_visual_resized = None
            if mod_curent == "midas":
                depth_colored = cv2.applyColorMap(depth_map, cv2.COLORMAP_INFERNO)
                depth_visual_resized = cv2.resize(depth_colored, (640, 360))
            
            with data_lock:
                ai_scores = (s, c, d)
                if depth_visual_resized is not None:
                    depth_visual_global = depth_visual_resized
            
        
            time.sleep(0.1) 
                    
        except Exception as e:
            print(f"Eroare MiDaS: {e}")


# Pornire thread-uri în paralel
t_cam = threading.Thread(target=camera_loop, daemon=True)
t_cam.start()

t_aruco = threading.Thread(target=aruco_loop, daemon=True)
t_aruco.start()

t_midas = threading.Thread(target=midas_loop, daemon=True)
t_midas.start()


def mjpeg():
    
    target_fps = 25
    frame_interval = 1.0 / target_fps
    last_frame_time = 0
    
    while _running:
        now = time.time()
        if now - last_frame_time < frame_interval:
            time.sleep(0.002)
            continue
        last_frame_time = now
        
        with data_lock:
            if latest_frame_bgr is None:
                continue
            
            mod_curent = MOD_VIZUALIZARE
            
            if mod_curent == "midas" and depth_visual_global is not None:
                frame_de_trimis = depth_visual_global.copy()
                corners_local = None
                center_local = None
            else:
                # Facem .copy() DOAR aici pentru că urmează să modificăm pe el
                frame_de_trimis = latest_frame_bgr.copy()
                corners_local = aruco_corners_cache
                center_local = aruco_center_cache
        
        # Desenare adnotări ArUco pe frame-ul live curat
        if mod_curent != "midas" and corners_local is not None:
            try:
                cv2.aruco.drawDetectedMarkers(frame_de_trimis, [corners_local])
                if center_local is not None:
                    cv2.circle(frame_de_trimis, center_local, 5, (0, 0, 255), -1)
            except Exception:
                pass
        
        ok, jpg = cv2.imencode('.jpg', frame_de_trimis, JPEG_PARAMS)
        
        if ok:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() +
                   b'\r\n')


def cleanup():
    global _running
    _running = False 
    try:
        cam.stop() 
    except Exception:
        pass