import sys
import torch
import numpy as np

# Adaugă calea până la repo-ul YOLOv5
sys.path.append('/home/pi/Desktop/SD_Bux/SmartCar/yolov5')  

# ----------------- ÎNCĂRCARE MODEL 1 (PERSOANE - COCO) -----------------
model_persoane = torch.hub.load('/home/pi/Desktop/SD_Bux/SmartCar/yolov5', 'yolov5n', source='local')
model_persoane.to('cpu')        
model_persoane.conf = 0.4       
model_persoane.iou = 0.45
model_persoane.max_det = 5    

names_persoane = model_persoane.names    
allowed_classes = [0]  # 0 = person

# ----------------- ÎNCĂRCARE MODEL 2 (FOC - CUSTOM) -----------------
cale_model_foc = '/home/pi/Desktop/SD_Bux/SmartCar/model_foc.pt' 

model_foc = torch.hub.load('/home/pi/Desktop/SD_Bux/SmartCar/yolov5', 'custom', path=cale_model_foc, source='local')
model_foc.to('cpu')
model_foc.conf = 0.25   
model_foc.iou = 0.45
model_foc.max_det = 5

names_foc = model_foc.names 

def detect_objects(img, img_size=320):
    """
    Rulează ambele modele YOLOv5 pe un frame și întoarce:
      - imaginea originală (nemodificată)
      - detections: listă de (label, conf, (x1, y1, x2, y2))
    """
    
    # 1. Rulăm frame-ul prin ambele modele
    results_persoane = model_persoane(img, size=img_size)
    results_foc = model_foc(img, size=img_size)

    # 2. Extragem tensorii cu rezultate
    det_persoane = results_persoane.xyxy[0].cpu().numpy()
    det_foc = results_foc.xyxy[0].cpu().numpy()

    detections = []

    # 3. Procesăm detecțiile pentru PERSOANE
    for x1, y1, x2, y2, conf, cls_idx in det_persoane:
        cls_idx = int(cls_idx)
        
        # Filtrăm să fie doar persoană
        if allowed_classes is not None and cls_idx not in allowed_classes:
            continue

        label = names_persoane[cls_idx]
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        
        detections.append((label, float(conf), (x1, y1, x2, y2)))

    # 4. Procesăm detecțiile pentru FOC
    for x1, y1, x2, y2, conf, cls_idx in det_foc:
        cls_idx = int(cls_idx)
        
        label = names_foc[cls_idx] # Ia numele din modelul de foc (ex: 'fire')
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        
        detections.append((label, float(conf), (x1, y1, x2, y2)))

    return img, detections