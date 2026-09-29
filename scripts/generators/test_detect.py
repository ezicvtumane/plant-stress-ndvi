
import cv2, os, sys
sys.path.append('/home/pi/plant-stress-ndvi')
from web_station import detect_aruco_in_image

for f in ['last_red.jpg', 'last_nir.jpg']:
    p = os.path.join('/home/pi/plant-stress-ndvi/static', f)
    img = cv2.imread(p)
    if img is not None:
        m_id, grp, c = detect_aruco_in_image(img)
        print(f, '-> detected:', m_id, grp)
