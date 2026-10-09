import os
import re

rep_files = [
    '/home/pi/plant-stress-ndvi/data/measurements.csv',
    '/home/pi/plant-stress-ndvi/data/experiments/exp_1791463544/measurements.csv'
]

targets = ['175', '176', '177', '178', '179']

# 1. Update CSVs
for fpath in rep_files:
    if not os.path.exists(fpath):
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        updated = line
        for tid in targets:
            if line.startswith(f'{tid},'):
                # Replace date
                updated = updated.replace('8 октября 2026, 22:', '9 октября 2026, 22:')
                # Replace filename timestamp
                updated = updated.replace('_20261008_22', '_20261009_22')
                print(f"Updated line for ID {tid} in {fpath}")
                break
        new_lines.append(updated)
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

# 2. Rename files
img_dirs = [
    '/home/pi/plant-stress-ndvi/data/experiments/exp_1791463544/images',
    '/home/pi/plant-stress-ndvi/static'
]

for d in img_dirs:
    if not os.path.exists(d):
        continue
    for fname in os.listdir(d):
        if any(fname.startswith(f'opt_{tid}_') for tid in targets) and '20261008_22' in fname:
            old_p = os.path.join(d, fname)
            new_name = fname.replace('20261008_22', '20261009_22')
            new_p = os.path.join(d, new_name)
            os.rename(old_p, new_p)
            print(f"Renamed: {fname} -> {new_name}")

print("Date fix completed.")
