with open('/home/pi/plant-stress-ndvi/web_station.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for j in range(1760, 1890):
    print(f"{j}: {lines[j]}", end='')
