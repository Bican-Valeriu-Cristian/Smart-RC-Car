# camera.py
import cv2
import time
import threading
from picamera2 import Picamera2
from yolo_detector import detect_objects

# --- Configurare Cameră ---
cam = Picamera2()
config = cam.create_video_configuration(
    # IMPORTANT: pentru OpenCV trebuie 'RGB888', care în memorie e BGR
    main={"size": (640, 360), "format": "RGB888"},
    controls = {
    "AfMode": 2,
    "AwbEnable": True,
    "NoiseReductionMode": 1,
    "ExposureTime": 0,
    "AnalogueGain": 0
}

)
cam.configure(config)
cam.start()

# --- Variabile Globale & Threading ---
latest_frame_bgr = None
latest_detections = []
_running = True

# 🔒 LOCK
data_lock = threading.Lock()

YOLO_INTERVAL = 0.1
YOLO_IMG_SIZE = 320
JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 70]

def camera_loop():
    """Citește continuu de la cameră."""
    global latest_frame_bgr
    while _running:
        frame = cam.capture_array()
        # frame este deja BGR datorită 'RGB888'
        with data_lock:
            latest_frame_bgr = frame

def yolo_loop():
    """Rulează YOLO periodic."""
    global latest_detections
    while _running:
        frame_to_process = None
        with data_lock:
            if latest_frame_bgr is not None:
                frame_to_process = latest_frame_bgr.copy()
        
        if frame_to_process is not None:
            try:
                _, detections = detect_objects(
                    frame_to_process,
                    img_size=YOLO_IMG_SIZE
                )
                with data_lock:
                    latest_detections = detections
            except Exception as e:
                print(f"EROARE YOLO: {e}")
        
        time.sleep(YOLO_INTERVAL)

# Pornire Thread-uri
t_cam = threading.Thread(target=camera_loop, daemon=True)
t_cam.start()

t_yolo = threading.Thread(target=yolo_loop, daemon=True)
t_yolo.start()

def mjpeg():
    """Flux MJPEG LIVE."""
    while True:
        frame = None
        detections = []

        with data_lock:
            if latest_frame_bgr is not None:
                frame = latest_frame_bgr.copy()
                detections = list(latest_detections)

        if frame is None:
            time.sleep(0.1)
            continue

        for label, conf, (x1, y1, x2, y2) in detections:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            text = f"{label} {conf:.2f}"
            cv2.putText(frame, text, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        ok, jpg = cv2.imencode('.jpg', frame, JPEG_PARAMS)
        
        if ok:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() +
                   b'\r\n')
        
        time.sleep(0.03)

def cleanup():
    global _running
    _running = False
    try:
        cam.stop()
    except Exception:
        pass
