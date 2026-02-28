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
        
        # Adăugăm o dimensiune suplimentară pentru batch (1, 256, 256, 3), deoarece modelul a fost antrenat să primească un lot de imagini
        input_tensor = np.expand_dims(img_normalized, axis=0)

        # 2. RULAREA MODELULUI
        self.interpreter.set_tensor(self.input_details[0]['index'], input_tensor)
        self.interpreter.invoke() 
        
        # 3. EXTRAGEREA HĂRȚII DE ADÂNCIME
        # Modelul ne dă o hartă de adâncime în format 256x256, unde fiecare pixel are o valoare care indică cât de aproape sau de departe e obiectul respectiv.
        depth_map = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        depth_map = np.squeeze(depth_map) 

        # 4. VIZUALIZARE HARTĂ DE ADÂNCIME
        # Pentru a o putea afișa pe site, normalizăm valorile hărții de adâncime la intervalul [0, 255] și le transformăm în uint8 (alb-negru).
        depth_min, depth_max = depth_map.min(), depth_map.max()
        if depth_max - depth_min > 1e-6: # Evităm o eroare matematică (împărțirea la zero)
            depth_normalized = (depth_map - depth_min) / (depth_max - depth_min)
        else:
            depth_normalized = np.zeros_like(depth_map)
            
        depth_visual = (depth_normalized * 255).astype(np.uint8)

        # 5. ANALIZA HĂRȚII DE ADÂNCIME PENTRU AUTOPILOT
        # Tăiem poza vizuală în 3 felii egale (Stânga, Centru, Dreapta)
        h, w = depth_visual.shape
        third = w // 3
        # np.mean calculează media de alb (adică cât de aproape e obstacolul) pe acea felie
        stanga = np.mean(depth_visual[:, :third])
        centru = np.mean(depth_visual[:, third:2*third])
        dreapta = np.mean(depth_visual[:, 2*third:])

        # Returnăm poza pentru site și scorurile pentru Autopilot
        return depth_visual, stanga, centru, dreapta

# --- INIȚIALIZARE HARDWARE ---
detector = MidasObstacleDetector("midas_v2_1_small_256.tflite")


cam = Picamera2()
config = cam.create_video_configuration(
    main={"size": (640, 360), "format": "RGB888"}, # Rezoluția pentru site-ul web
    controls={
        "AfMode": 2,          # Autofocus activ
        "AwbEnable": True,    # Balans de alb automat
        "NoiseReductionMode": 1,
        "ExposureTime": 0,    # Lăsăm camera să aleagă singură timpul de expunere
        "AnalogueGain": 0
    }
)
cam.configure(config)
cam.start()

# --- VARIABILE GLOBALE ---
latest_frame_bgr = None      # Aici ținem cea mai recentă poză normală
depth_visual_global = None   # Aici ținem cea mai recentă poză de la AI
ai_scores = (0, 0, 0)        # Aici ținem scorurile (Stânga, Centru, Dreapta)
_running = True              # Cât timp e True, programul rulează
MOD_VIZUALIZARE = "normal"   # Ce arătăm ("normal" sau "midas")
JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 70] # Calitatea imaginii (70%)

# lock thread pentru a proteja accesul la variabilele globale între thread-uri (Camera, AI, Web)
data_lock = threading.Lock()

# Flag poza noua pentru Web și AI (
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


def camera_loop():
    
    global latest_frame_bgr
    while _running:
        try:
            frame = cam.capture_array()
            with data_lock:
                latest_frame_bgr = frame
            
            new_frame_event_web.set()
            new_frame_event_ai.set()
            
        except Exception as e:
            print(f"Eroare la captura camerei: {e}")
            time.sleep(0.5)


def ai_loop():
    
    global depth_visual_global, ai_scores
    while _running:
        
        if new_frame_event_ai.wait(timeout=1.0):
            new_frame_event_ai.clear() 
            
            with data_lock:
                if latest_frame_bgr is None:
                    continue
                
                frame_de_analizat = latest_frame_bgr.copy()
            
            try:
                # Procesăm poza prin MiDaS: Ne întoarce harta de adâncime și scorurile pentru Stânga, Centru, Dreapta
                depth_map, s, c, d = detector.process_frame(frame_de_analizat)
                
                # Transformă harta alb-negru în culori "termice" 
                depth_colored = cv2.applyColorMap(depth_map, cv2.COLORMAP_INFERNO)
                depth_visual_resized = cv2.resize(depth_colored, (640, 360))
                
                
                with data_lock:
                    ai_scores = (s, c, d)
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
            
            # Dacă modul de vizualizare e "midas" și avem o poză de la AI, o folosim pe aia. Altfel, folosim poza normală.
            if MOD_VIZUALIZARE == "midas" and depth_visual_global is not None:
                frame_de_trimis = depth_visual_global.copy()
            else:
                frame_de_trimis = latest_frame_bgr.copy()

        # Comprimăm poza în format JPEG pentru a o trimite eficient pe rețea către browser
        ok, jpg = cv2.imencode('.jpg', frame_de_trimis, JPEG_PARAMS)
        
        # Dacă s-a comprimat cu succes, o trimitem pe rețea 
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