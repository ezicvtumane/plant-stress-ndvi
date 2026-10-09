import os
import shutil

base = "/home/pi/plant-stress-ndvi"
for root, dirs, files in os.walk(base, topdown=False):
    for d in dirs:
        if d.lower().startswith('c:') or 'Users' in d or 'Администратор' in d:
            full_path = os.path.join(root, d)
            try:
                shutil.rmtree(full_path)
                print("Removed:", full_path)
            except Exception as e:
                print("Error removing", full_path, e)

print("Done directory cleanup.")
