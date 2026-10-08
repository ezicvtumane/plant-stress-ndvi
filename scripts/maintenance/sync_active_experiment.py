import csv
import os
import shutil

BASE_DIR = '/home/pi/plant-stress-ndvi'
EXP_DIR = os.path.join(BASE_DIR, 'data', 'experiments', 'exp_1791463544')
EXP_CSV = os.path.join(EXP_DIR, 'measurements.csv')
EXP_IMG_DIR = os.path.join(EXP_DIR, 'images')
GLOBAL_CSV = os.path.join(BASE_DIR, 'data', 'measurements.csv')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

os.makedirs(EXP_IMG_DIR, exist_ok=True)

existing_ids = set()
if os.path.exists(EXP_CSV):
    with open(EXP_CSV, 'r', encoding='utf-8') as f:
        existing_ids = {r[0].strip() for r in csv.reader(f) if r}

missing_rows = []
with open(GLOBAL_CSV, 'r', encoding='utf-8') as f:
    for r in csv.reader(f):
        if not r or r[0].strip() == 'ID':
            continue
        try:
            m_id = int(r[0].strip())
            if m_id >= 118 and str(m_id) not in existing_ids:
                missing_rows.append(r)
        except ValueError:
            pass

print(f"Found {len(missing_rows)} missing rows: {[r[0] for r in missing_rows]}")

with open(EXP_CSV, 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    for r in missing_rows:
        writer.writerow(r)
        # Copy opt file
        if len(r) > 14 and r[14]:
            src = os.path.join(STATIC_DIR, r[14])
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(EXP_IMG_DIR, r[14]))
        # Copy thermal file
        if len(r) > 15 and r[15]:
            src = os.path.join(STATIC_DIR, r[15])
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(EXP_IMG_DIR, r[15]))

with open(EXP_CSV, 'r', encoding='utf-8') as f:
    total_count = sum(1 for line in f if line.strip()) - 1

print(f"Sync complete! Active experiment now has {total_count} measurements.")
