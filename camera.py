import cv2
import time
import threading
import numpy as np
from picamera2 import Picamera2

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter

# -CLASA PENTRU MIDAS-

class MidasObstacleDetector:
    def __init__(self, model_path="/home/pi/Desktop/SD_Bux/SmartCar/midas_v2_1_small_256.tflite"):
        
        self.interpreter = Interpreter(model_path=model_path, num_threads=1)
        self.interpreter.allocate_tensors() # Rezervăm memoria RAM necesară AI-ului
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # Valorile de normalizare pentru MiDaS (așa cum a fost antrenat modelul)
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def process_frame(self, frame):
        # 1. PREPROCESARE: MiDaS 
        # MiDaS funcționează cel mai bine pe imagini alb-negru, așa că transformăm poza RGB în gri 
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        
        # Redimensionăm imaginea la 256x256, așa cum cere modelul 
        img_resized = cv2.resize(img, (256, 256))
        
        # Normalizăm pixelii la intervalul [0, 1], apoi aplicăm normalizarea specifică MiDaS
        img_normalized = (img_resized.astype(np.float32) / 255.0 - self.mean) / self.std
        
        # Adăugăm o dimensiune suplimentară pentru batch (1, 256, 256, 3)
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

        # 5. ANALIZA HĂRȚII DE ADÂNCIME PENTRU AUTOPILOT
        h, w = depth_visual.shape
        third = w // 3
        stanga = np.mean(depth_visual[:, :third])
        centru = np.mean(depth_visual[:, third:2*third])
        dreapta = np.mean(depth_visual[:, 2*third:])

        return depth_visual, stanga, centru, dreapta

# --- INIȚIALIZARE HARDWARE ---
detector = MidasObstacleDetector("midas_v2_1_small_256.tflite")

# Inițializare detector ArUco (Folosim familia 4x4)
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

cam = Picamera2()
config = cam.create_video_configuration(
    main={"size": (640, 360), "format": "RGB888"},
    controls={
        "AfMode": 2,          
        "AwbEnable": True,    
        "NoiseReductionMode": 1,
        "ExposureTime": 0,    
        "AnalogueGain": 0
    }
)
cam.configure(config)
cam.start()

# --- VARIABILE GLOBALE ---
latest_frame_bgr = None      # Aici ținem cea mai recentă poză normală
annotated_frame_global = None # AICI ȚINEM POZA CU PĂTRATUL VERDE (Să nu fie ștearsă)
depth_visual_global = None   
ai_scores = (0, 0, 0)        
aruco_target_x = None        
_running = True              
MOD_VIZUALIZARE = "normal"   
JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 70] 

# lock thread pentru a proteja accesul la variabilele globale între thread-uri (Camera, AI, Web)
data_lock = threading.Lock()

# Flag poza noua pentru Web și AI
new_frame_event_web = threading.Event()
new_frame_event_ai = threading.Event()

def set_mod_vizualizare(mod):
    global MOD_VIZUALIZARE
    with data_lock: 
        MOD_VIZUALIZARE = mod
    print(f"Camera a trecut în modul: {MOD_VIZUALIZARE}")

def get_ai_scores():
    with data_lock: 
        return ai_scores

# Funcție nouă pentru APP.PY ca să ceară poziția markerului
def get_aruco_position(target_id=6):
    with data_lock:
        return aruco_target_x

def camera_loop():
    global latest_frame_bgr
    while _running:
        try:
            frame = cam.capture_array()
            
            # REPARAT: Convertim poza la formatul nativ OpenCV ca să vadă perfect markerul
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            with data_lock:
                latest_frame_bgr = frame
            
            new_frame_event_web.set()
            new_frame_event_ai.set()
          
        except Exception as e:
            print(f"Eroare la captura camerei: {e}")
            time.sleep(0.5)

def ai_loop():
    global depth_visual_global, ai_scores, aruco_target_x, latest_frame_bgr, annotated_frame_global
    
    TARGET_ID = 6 # Markerul pe care vrem să-l urmărim
    
    while _running:
        if new_frame_event_ai.wait(timeout=1.0):
            new_frame_event_ai.clear() 
            
            with data_lock:
                if latest_frame_bgr is None:
                    continue
                frame_de_analizat = latest_frame_bgr.copy()
            
            try:
                # ----------------------------------------------------
                # 1. DETECȚIE ARUCO (Rulează mereu)
                # ----------------------------------------------------
                gray_for_aruco = cv2.cvtColor(frame_de_analizat, cv2.COLOR_BGR2GRAY)
                corners, ids, rejected = aruco_detector.detectMarkers(gray_for_aruco)
                
                current_target_x = None
                
                if ids is not None:
                    for i in range(len(ids)):
                        if ids[i][0] == TARGET_ID:
                            marker_corners = corners[i][0]
                            centru_x = int(np.mean(marker_corners[:, 0]))
                            centru_y = int(np.mean(marker_corners[:, 1]))
                            
                            current_target_x = (centru_x - 320) / 320.0 
                            
                            cv2.aruco.drawDetectedMarkers(frame_de_analizat, corners)
                            cv2.circle(frame_de_analizat, (centru_x, centru_y), 5, (0, 0, 255), -1)
                            break
                            
                # ----------------------------------------------------
                # 2. DETECȚIE MIDAS
                # ----------------------------------------------------
                depth_visual_resized = None
                s, c, d = (0, 0, 0)
                
                with data_lock:
                    mod_curent = MOD_VIZUALIZARE
                
                if mod_curent == "midas":
                    depth_map, s, c, d = detector.process_frame(frame_de_analizat)
                    depth_colored = cv2.applyColorMap(depth_map, cv2.COLORMAP_INFERNO)
                    depth_visual_resized = cv2.resize(depth_colored, (640, 360))
                
                # Salvăm datele
                with data_lock:
                    aruco_target_x = current_target_x
                    ai_scores = (s, c, d)
                    
                    # REPARAT: Acum salvăm poza cu desenul verde într-o memorie sigură
                    annotated_frame_global = frame_de_analizat.copy()
                    
                    if depth_visual_resized is not None:
                        depth_visual_global = depth_visual_resized
                    
            except Exception as e:
                print(f"Eroare AI: {e}")

t_cam = threading.Thread(target=camera_loop, daemon=True)
t_cam.start()

t_ai = threading.Thread(target=ai_loop, daemon=True)
t_ai.start()

def mjpeg():
    while _running:
        if not new_frame_event_web.wait(timeout=1.0):
            continue 

        new_frame_event_web.clear()
        
        with data_lock:
            if latest_frame_bgr is None:
                continue
            
            # REPARAT: Decidem ce arătăm pe site
            if MOD_VIZUALIZARE == "midas" and depth_visual_global is not None:
                frame_de_trimis = depth_visual_global.copy()
            elif annotated_frame_global is not None: # Arată poza cu pătratul verde!
                frame_de_trimis = annotated_frame_global.copy()
            else:
                frame_de_trimis = latest_frame_bgr.copy()

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