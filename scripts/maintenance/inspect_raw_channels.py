import cv2
import numpy as np
import glob
import os

static_dir = "/home/pi/plant-stress-ndvi/static"

# Let's inspect last_red, last_nir, last_ndvi, last_amb
for fname in ["last_red.jpg", "last_nir.jpg", "last_ndvi.jpg", "last_amb.jpg", "last_flash_raw.jpg"]:
    p = os.path.join(static_dir, fname)
    if os.path.exists(p):
        img = cv2.imread(p)
        print(f"{fname}: shape={img.shape}, min={img.min()}, mean={img.mean():.1f}, max={img.max()}")
        if fname in ["last_red.jpg", "last_nir.jpg"]:
            # check channel means
            print(f"   B={img[:,:,0].mean():.1f}, G={img[:,:,1].mean():.1f}, R={img[:,:,2].mean():.1f}")

# Check calibrated_k_bal.txt
k_file = "/home/pi/plant-stress-ndvi/data/calibrated_k_bal.txt"
if os.path.exists(k_file):
    with open(k_file) as f:
        print("calibrated_k_bal.txt:", f.read().strip())
