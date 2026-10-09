import csv
import os

files_to_update = [
    "/home/pi/plant-stress-ndvi/data/measurements.csv",
    "/home/pi/plant-stress-ndvi/data/experiments/exp_1791463544/measurements.csv"
]

target_ids = {"175", "176", "177", "178", "179"}
WIN_T = 23.9
WIN_RH = 57.2
WIN_VPD = 1.27

for path in files_to_update:
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        reader = list(csv.reader(f))
    
    updated_rows = []
    header = reader[0]
    updated_rows.append(header)

    for r in reader[1:]:
        if len(r) > 10 and r[0] in target_ids:
            # Columns: 
            # 0: ID, 1: Timestamp, 2: Group, 3: Weight, 
            # 4: T_Air, 5: RH_Air, 6: V_soil, 7: Pct_soil, 
            # 8: T_Leaf, 9: Delta_T, 10: VPD
            t_leaf_str = r[8]
            try:
                t_leaf = float(t_leaf_str)
                delta_t = round(t_leaf - WIN_T, 1)
            except Exception:
                delta_t = r[9]
            
            r[4] = str(WIN_T)
            r[5] = str(WIN_RH)
            r[9] = str(delta_t)
            r[10] = str(WIN_VPD)
            print(f"Updated {r[0]} ({r[2]}): T_air={r[4]}, RH={r[5]}, T_leaf={r[8]}, Delta_T={r[9]}, VPD={r[10]}")
        updated_rows.append(r)
    
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(updated_rows)

print("Update completed successfully.")
