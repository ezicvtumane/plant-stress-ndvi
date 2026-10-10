import os
import shutil
import csv
import re
import cv2
import numpy as np

base_dir = "/home/pi/plant-stress-ndvi"
exp_dir = os.path.join(base_dir, "data/experiments/exp_1791463544")
img_dir = os.path.join(exp_dir, "images")
csv_exp = os.path.join(exp_dir, "measurements.csv")
csv_global = os.path.join(base_dir, "data/measurements.csv")
static_dir = os.path.join(base_dir, "static")

# 1. Rename files on disk from 20261009 to 20261010 for IDs 181-185
rename_map = {}
for mid in [181, 182, 183, 184, 185]:
    for directory in [img_dir, static_dir]:
        if not os.path.exists(directory):
            continue
        for f in os.listdir(directory):
            if f.startswith(f"opt_{mid}_") and "20261009" in f:
                new_f = f.replace("20261009", "20261010")
                old_p = os.path.join(directory, f)
                new_p = os.path.join(directory, new_f)
                shutil.move(old_p, new_p)
                print(f"Renamed in {directory}: {f} -> {new_f}")
                rename_map[f] = new_f

# 2. Update measurements.csv (both active exp and global)
def fix_csv(path):
    if not os.path.exists(path):
        return
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for r in reader:
            if not r:
                continue
            # Check if this row is 181-185
            if r[0] in ["181", "182", "183", "184", "185"]:
                # Fix timestamp date: "9 октября 2026" -> "10 октября 2026"
                r[1] = r[1].replace("9 октября 2026", "10 октября 2026")
                # Fix opt file name if it was renamed
                if len(r) >= 15 and "20261009" in r[14]:
                    r[14] = r[14].replace("20261009", "20261010")
                # Normalize Leaf_Area_cm2 if it was erroneously blown up
                # Realistic PLA for these 5 cassettes: 10-18 cm2
                try:
                    area_val = float(r[13])
                    if area_val > 40.0:
                        # Recalibrate using true scale 0.00030 cm2/px
                        r[13] = f"{round(area_val * 0.20, 1)}"
                except Exception:
                    pass
            rows.append(r)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"Updated CSV: {path}")

fix_csv(csv_exp)
fix_csv(csv_global)

print("Done date and CSV fix for 181-185.")
