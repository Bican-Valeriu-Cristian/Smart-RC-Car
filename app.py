from flask import Flask, Response, request, jsonify
import threading, time, cv2
from picamera2 import Picamera2
import motor, sensor

app = Flask(__name__)

PRAG_CM = 25
ESTOP = False

# ======== CAMERA (Picamera2) ========
cam = Picamera2()
# rezoluție bună pentru viteză + compatibilă cu modele AI
cam.configure(cam.create_video_configuration(main={"size": (640, 480)}))
cam.start()

def mjpeg():
    while True:
        frame = cam.capture_array()
        # conversie RGB->BGR (necesară dacă vrei să adaugi YOLO / OpenCV ulterior)
        # frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        cv2.putText(frame, "SmartCar", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        ok, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')

# ======== ROUTES ========
@app.route('/')
def index():
    with open("index.html") as f:
        return f.read()

@app.route('/video')
def video():
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ======== MAIN ========
if __name__ == '__main__':
    threading.Thread(target=safety_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=8000, threaded=True)
