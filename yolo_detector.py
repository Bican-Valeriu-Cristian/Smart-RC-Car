# yolo_detector.py
import sys
import torch
import cv2
import numpy as np

# adaugă calea până la repo-ul YOLOv5
sys.path.append('/home/pi/Desktop/SD_Bux/SmartCar/yolov5')  # ajustează dacă ai alt path

# ----------------- ÎNCĂRCARE MODEL -----------------
# încarcă YOLOv5n (nano) COCO din repo-ul local
model = torch.hub.load('/home/pi/Desktop/SD_Bux/SmartCar/yolov5', 'yolov5n', source='local')
model.to('cpu')        # pe Raspberry Pi 4B, CPU
model.conf = 0.4       # confidence threshold
model.iou = 0.45
model.max_det = 50     # maxim detecții per imagine

names = model.names    # numele claselor COCO

# dacă vrei să limitezi clasele:
# COCO: 0=person, 1=bicycle, 2=car, 3=motorbike, 5=bus, 7=truck etc.
# allowed_classes = [0, 1, 2, 3, 5, 7]
allowed_classes = None   # None = toate


def detect_objects(img_bgr, img_size=320):
    """
    Rulează YOLOv5n pe un frame BGR și întoarce:
      - annotated_img: imaginea cu bounding box-uri desenate
      - detections: listă de (label, conf, (x1, y1, x2, y2))
    """
    # YOLOv5 acceptă direct BGR (face intern conversia)
    # img_size = 320 sau 416 etc. (multiplu de 32)
    results = model(img_bgr, size=img_size)

    # tensor Nx6: x1, y1, x2, y2, conf, cls
    det = results.xyxy[0].cpu().numpy()

    annotated = img_bgr.copy()
    detections = []

    for x1, y1, x2, y2, conf, cls_idx in det:
        cls_idx = int(cls_idx)
        conf_f = float(conf)

        if allowed_classes is not None and cls_idx not in allowed_classes:
            continue

        label = names[cls_idx]

        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        # desenăm bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        text = f"{label} {conf_f:.2f}"
        cv2.putText(annotated, text, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        detections.append((label, conf_f, (x1, y1, x2, y2)))

    return annotated, detections
