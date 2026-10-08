import os
import subprocess

for dev in sorted(os.listdir('/dev')):
    if dev.startswith('i2c-'):
        num = dev.split('-')[1]
        res = subprocess.run(['sudo', 'i2cdetect', '-y', num], capture_output=True, text=True)
        detected = []
        for line in res.stdout.splitlines()[1:]:
            parts = line.split(':')[1].split() if ':' in line else []
            for p in parts:
                if p != '--':
                    detected.append(p)
        print(f"{dev}: detected {detected if detected else 'NONE'}")
