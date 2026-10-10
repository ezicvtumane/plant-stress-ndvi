import os
import cv2
import numpy as np
import glob
import csv

base_dir = "/home/pi/plant-stress-ndvi"
exp_dir = os.path.join(base_dir, "data/experiments/exp_1791463544")
img_dir = os.path.join(exp_dir, "images")
static_dir = os.path.join(base_dir, "static")
csv_path = os.path.join(exp_dir, "measurements.csv")

def get_agronomic_ndvi_lut():
    lut = np.zeros((256, 1, 3), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        if t < 0.25: # Red to Orange-Red (stress / low NDVI)
            k = t / 0.25
            r = int(180 + k * 40)
            g = int(20 + k * 80)
            b = 20
        elif t < 0.60: # Orange to Yellow-Green
            k = (t - 0.25) / 0.35
            r = int(220 - k * 140)
            g = int(100 + k * 120)
            b = 25
        else: # Yellow-Green to Lush Forest Green (healthy vegetation)
            k = (t - 0.60) / 0.40
            r = int(80 - k * 60)
            g = int(220 - k * 30)
            b = int(25 + k * 30)
        lut[i, 0] = [b, g, r] # BGR
    return lut

NDVI_LUT = get_agronomic_ndvi_lut()
TURBO_LUT = cv2.applyColorMap(np.arange(256, dtype=np.uint8), cv2.COLORMAP_TURBO).reshape(256, 3).astype(np.float32)

# Load measurement metadata
meas_meta = {}
with open(csv_path, encoding='utf-8') as f:
    r = csv.reader(f)
    header = next(r)
    for row in r:
        if row and int(row[0]) >= 181:
            mid = int(row[0])
            meas_meta[mid] = {
                'id': mid,
                'timestamp': row[1],
                'group': row[2],
                'weight': row[3],
                't_air': row[4],
                'rh': row[5],
                'soil': row[7],
                't_leaf': row[8],
                'delta_t': row[9],
                'ndvi_mean': row[11],
                'ndvi_std': row[12],
                'leaf_area': row[13],
                'opt_file': row[14],
                'therm_file': row[15],
                'cells': [float(row[16 + i]) for i in range(9)]
            }

print(f"Loaded metadata for measurements: {list(meas_meta.keys())}")

for mid, meta in meas_meta.items():
    opt_file = meta['opt_file']
    src_paths = [
        os.path.join(img_dir, opt_file),
        os.path.join(static_dir, opt_file)
    ]
    
    # Try finding file
    found_path = None
    for p in src_paths:
        if os.path.exists(p):
            found_path = p
            break
            
    if not found_path:
        # Check glob
        matches = glob.glob(os.path.join(img_dir, f"opt_{mid}_*.jpg"))
        if matches:
            found_path = matches[0]
            
    if not found_path:
        print(f"Warning: could not find image for #{mid}")
        continue
        
    print(f"Processing #{mid}: {found_path}")
    orig_bgr = cv2.imread(found_path)
    h, w, _ = orig_bgr.shape
    
    # Background in original is [35, 15, 30]
    bg_color = np.array([35, 15, 30], dtype=np.float32)
    diff_from_bg = np.sqrt(np.sum((orig_bgr.astype(np.float32) - bg_color)**2, axis=2))
    
    # Text and white grid borders have high intensity and low saturation
    hsv = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2HSV)
    is_white_border_text = (hsv[:, :, 1] < 30) & (hsv[:, :, 2] > 180)
    is_black_border_text = (hsv[:, :, 2] < 30)
    
    # Mask of colored plant pixels (TURBO colored leaves)
    # They differ significantly from background and are not white/black text
    is_plant_pixel = (diff_from_bg > 30.0) & (~is_white_border_text) & (~is_black_border_text)
    
    # Invert TURBO LUT for plant pixels
    plant_coords = np.where(is_plant_pixel)
    plant_colors = orig_bgr[plant_coords].astype(np.float32) # N x 3
    
    if len(plant_colors) > 0:
        # Vectorized distance to TURBO LUT (N x 256)
        # Using KDTree or batch chunking for memory safety
        chunk_size = 50000
        indices = np.zeros(len(plant_colors), dtype=np.uint8)
        for c_start in range(0, len(plant_colors), chunk_size):
            c_end = min(c_start + chunk_size, len(plant_colors))
            sub = plant_colors[c_start:c_end] # M x 3
            # dist to each of 256 colors
            dists = np.sum((sub[:, None, :] - TURBO_LUT[None, :, :])**2, axis=2) # M x 256
            indices[c_start:c_end] = np.argmin(dists, axis=1).astype(np.uint8)
            
        # Map indices to Agronomic LUT
        recolored_plant = NDVI_LUT[indices, 0, :] # N x 3 (BGR)
    else:
        recolored_plant = np.zeros((0, 3), dtype=np.uint8)
        
    # Create clean canvas with dark neutral background
    clean_canvas = np.full((h, w, 3), [35, 15, 30], dtype=np.uint8)
    clean_canvas[plant_coords] = recolored_plant
    
    # Draw standard 3x3 grid
    cell_h, cell_w = h // 3, w // 3
    cells_val = meta['cells']
    
    # Estimate cell areas proportionally
    total_la = float(meta['leaf_area'])
    cell_counts = []
    for r in range(3):
        for c in range(3):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            sub_mask = is_plant_pixel[y1:y2, x1:x2]
            cell_counts.append(np.count_nonzero(sub_mask))
    sum_cnt = max(1, sum(cell_counts))
    cell_areas = [round(total_la * (cnt / sum_cnt), 1) if val > 0 else 0.0 for cnt, val in zip(cell_counts, cells_val)]
    
    for r in range(3):
        for c in range(3):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            idx = r * 3 + c
            c_area = cell_areas[idx]
            cell_val = cells_val[idx]

            cv2.rectangle(clean_canvas, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(clean_canvas, f'#{r*3+c+1}: {cell_val:.3f}', (x1 + 12, y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
            cv2.putText(clean_canvas, f'#{r*3+c+1}: {cell_val:.3f}', (x1 + 12, y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(clean_canvas, f'{c_area} cm2', (x1 + 12, y1 + 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
            cv2.putText(clean_canvas, f'{c_area} cm2', (x1 + 12, y1 + 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 255, 200), 1)
                        
    # Draw Header & Diagnostic telemetry (top right - NO overlap with cell 1!)
    cv2.putText(clean_canvas, f'PLA: {meta["leaf_area"]} cm2', (w - 260, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3)
    cv2.putText(clean_canvas, f'PLA: {meta["leaf_area"]} cm2', (w - 260, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2)

    cv2.putText(clean_canvas, 'Calib: k=4.07', (w - 260, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
    cv2.putText(clean_canvas, 'Calib: k=4.07', (w - 260, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 255, 200), 1)
                
    # Overwrite images with newly rendered agronomic image
    target_name = f'opt_{mid}_{meta["group"]}_20261010_{mid:03d}.jpg'
    # Use standard filename from meta
    std_name = meta['opt_file']
    for dest in [os.path.join(img_dir, std_name), os.path.join(static_dir, std_name)]:
        cv2.imwrite(dest, clean_canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        print(f"Saved: {dest}")

print("Done recoloring and re-rendering Oct 10 NDVI images.")
