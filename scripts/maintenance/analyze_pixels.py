import cv2
import numpy as np

red = cv2.imread('/home/pi/plant-stress-ndvi/static/fum_check_raw_red.jpg')
nir = cv2.imread('/home/pi/plant-stress-ndvi/static/fum_check_raw_nir.jpg')

# Target box
target_red = red[320:460, 530:680, 2].astype(np.float32)
target_nir = nir[320:460, 530:680].astype(np.float32).mean(axis=2)

print('Target RED - min:', target_red.min(), 'mean:', target_red.mean(), 'median:', np.median(target_red), 'max:', target_red.max())
print('Target NIR - min:', target_nir.min(), 'mean:', target_nir.mean(), 'median:', np.median(target_nir), 'max:', target_nir.max())

sat_pixels = np.sum(target_red >= 250)
total_pixels = target_red.size
print(f'Saturated pixels in target: {sat_pixels} / {total_pixels} ({sat_pixels/total_pixels*100:.1f}%)')

diffuse_mask = target_red < 220
if np.any(diffuse_mask):
    d_red = target_red[diffuse_mask].mean()
    d_nir = target_nir[diffuse_mask].mean()
    print(f'Diffuse non-glare RED: {d_red:.1f}, NIR: {d_nir:.1f}, Ratio (RED/NIR): {d_red/d_nir:.2f}')

bg_red = red[300:500, 300:450, 2].astype(np.float32)
bg_nir = nir[300:500, 300:450].astype(np.float32).mean(axis=2)
print(f'Background sheet - RED: {bg_red.mean():.1f}, NIR: {bg_nir.mean():.1f}, Ratio: {bg_red.mean()/bg_nir.mean():.2f}')
