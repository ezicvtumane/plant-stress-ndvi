import cv2
import numpy as np
import glob
import os

for mid in [181, 182, 183, 184, 185]:
    files = glob.glob(f"/home/pi/plant-stress-ndvi/static/opt_{mid}_*.jpg")
    if not files:
        continue
    img = cv2.imread(files[0])
    # The image is 960x1280 BGR
    # Background pixels are [35, 15, 30]
    is_bg = (img[:, :, 0] == 35) & (img[:, :, 1] == 15) & (img[:, :, 2] == 30)
    leaf_px = np.count_nonzero(~is_bg)
    print(f"#{mid} leaf pixels: {leaf_px}")
