# Live video minimal cu Raspberry Pi Camera
# Autor: <Numele tau> - Proiect Licenta "SmartCar"

from flask import Flask, Response
from picamera2 import Picamera2
import cv2

app = Flask(__name__)

cam = Picamera2()
cam.configure(cam.create_video_configuration(main={"size": (1920, 1080)}))
cam.start()

def generate():
    while True:
        frame = cam.capture_array()
        ok, jpg = cv2.imencode(".jpg", frame)
        if ok:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpg.tobytes() + b'\r\n')

@app.route('/')
def index():
    return '''
    <html>
      <head>
        <title>SmartCar</title>
      </head>
      <body style="background-color:black; color:white; text-align:center;">
        <h1>SmartCar</h1>
        <img src="/video" width="1000" height="580">
      </body>
    </html>
    '''

@app.route('/video')
def video():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
