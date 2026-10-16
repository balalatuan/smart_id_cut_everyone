import cv2
import numpy as np
from .schema import Geometry


class FaceDetector:
    """Offline Haar baseline. No downloads, landmarks or calibrated confidence."""
    def __init__(self):
        cv2.setNumThreads(1)
        self.detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if self.detector.empty():
            raise RuntimeError("Local OpenCV cascade not installed")

    def detect(self, image, config):
        small = image.copy()
        small.thumbnail((config.detector_max_side, config.detector_max_side))
        gray = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2GRAY)
        found = self.detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        sx, sy = image.width / small.width, image.height / small.height
        faces = [(round(x*sx), round(y*sy), round(w*sx), round(h*sy)) for x,y,w,h in found]
        return Geometry(faces=sorted(faces, key=lambda b: b[2]*b[3], reverse=True))
