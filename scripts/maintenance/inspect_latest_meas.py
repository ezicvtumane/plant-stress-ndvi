import csv
import json

path = "/home/pi/plant-stress-ndvi/data/experiments/exp_1791463544/measurements.csv"
with open(path, encoding="utf-8") as f:
    r = csv.reader(f)
    header = next(r)
    for row in r:
        if row and int(row[0]) >= 181:
            d = dict(zip(header, row))
            print(f"ID #{d['ID']} | Date: {d['Timestamp']} | Group: {d['Group']}")
            print(f"  Weight: {d['Weight_g']} g | Soil: {d['Moisture_Pct']}% | T_leaf: {d['T_Leaf_C']} | T_air: {d['T_Air_C']} | Delta_T: {d['Delta_T_C']}")
            print(f"  NDVI Mean: {d['NDVI_Mean']} ± {d['NDVI_Std']} | Leaf Area: {d['Leaf_Area_cm2']} cm2")
            print(f"  Cells (C1-C9): {[d[f'C{i}'] for i in range(1, 10)]}")
            print(f"  Opt File: {d['Opt_File']}")
            print(f"  Thermal File: {d['Thermal_File']}")
            print("-" * 50)
