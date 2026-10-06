import cv2
import numpy as np
import os

def imread_utf8(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

local_dir = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures"
amb_path = os.path.join(local_dir, 'shot2_last_amb.jpg')
flash_path = os.path.join(local_dir, 'shot2_last_flash_raw.jpg')
ndvi_path = os.path.join(local_dir, 'shot2_last_ndvi.jpg')

img_amb = imread_utf8(amb_path)
img_flash = imread_utf8(flash_path)
img_ndvi = imread_utf8(ndvi_path)

# Resize to width 640 for comparison collage
w, h = 640, 480
amb_res = cv2.resize(img_amb, (w, h))
flash_res = cv2.resize(img_flash, (w, h))
ndvi_res = cv2.resize(img_ndvi, (w, h))

# Add titles
def add_banner(img, title, subtitle, color):
    canvas = np.zeros((h + 60, w, 3), dtype=np.uint8)
    canvas[60:, :] = img
    cv2.putText(canvas, title, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
    cv2.putText(canvas, subtitle, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    return canvas

p1 = add_banner(amb_res, "1. ФОНОВЫЙ КАДР (БЕЗ СТРОБА)", "Естественная освещенность (L=121.1)", (200, 200, 200))
p2 = add_banner(flash_res, "2. СТРОБ 660 нм + 850 нм", "Вспышка светодиодов (L=139.7, ΔR=+39.2)", (0, 100, 255))
p3 = add_banner(ndvi_res, "3. СПЕКТРАЛЬНАЯ КАРТА NDVI", "Анализ зон кассеты и вегетативного индекса", (0, 220, 100))

collage = np.hstack([p1, p2, p3])

out_path = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures\strobe_verification_collage.jpg"
cv2.imwrite(out_path, collage)
print("Collage saved successfully:", out_path)
