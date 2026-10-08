import cv2
import numpy as np

path = '/home/pi/plant-stress-ndvi/static/last_red.jpg'
red = cv2.imread(path)
if red is not None:
    r_chan = red[:, :, 2].astype(np.float32)
    p_high_r = float(np.percentile(r_chan, 99.5))
    if p_high_r > 5.0:
        norm_r = np.clip((r_chan / p_high_r) * 255.0, 0, 255).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced_mono = clahe.apply(norm_r)
        enhanced_bgr = np.zeros_like(red)
        enhanced_bgr[:, :, 2] = enhanced_mono
        enhanced_bgr[:, :, 0] = (enhanced_mono * 0.15).astype(np.uint8)
        enhanced_bgr[:, :, 1] = (enhanced_mono * 0.05).astype(np.uint8)
        cv2.imwrite(path, enhanced_bgr)
        print("Updated static/last_red.jpg in-place!")
