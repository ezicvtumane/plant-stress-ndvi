import sys
import time
import cv2
import numpy as np
import paramiko
import os

sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

# Останавливаем службу станции чтобы полностью управлять камерой и реле
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()
time.sleep(1)

remote_capture_code = '''import cv2, time, os, gpiod, numpy as np
from gpiod.line import Direction, Value

print("[1/4] Инициализация камеры /dev/video0 и реле...")
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1600)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1200)

settings = gpiod.LineSettings(direction=Direction.OUTPUT, active_low=True, output_value=Value.INACTIVE)
req = gpiod.request_lines('/dev/gpiochip1', consumer='true_3frame', config={(4,): settings, (7,): settings})

os.makedirs('/home/pi/test_frames', exist_ok=True)

# 1. Фоновый кадр (Ambient - оба выключены)
print("[2/4] Захват Кадра 1: ФОН (Ambient, все светодиоды выключены)...")
for _ in range(5): cap.read()
ret, frame_amb = cap.read()
cv2.imwrite('/home/pi/test_frames/frame_1_ambient.jpg', frame_amb)

# 2. Кадр Red 660 нм (Включаем ТОЛЬКО Канал 1 / Pin 7)
print("[3/4] ЩЕЛЧОК 1: Включаем ТОЛЬКО КРАСНЫЙ 660 нм (Канал 1 / Pin 7)...")
req.set_value(4, Value.ACTIVE)
time.sleep(0.4)
for _ in range(5): cap.read()
ret, frame_red = cap.read()
req.set_value(4, Value.INACTIVE)
print("      ЩЕЛЧОК 2: Красный выключен.")
cv2.imwrite('/home/pi/test_frames/frame_2_red.jpg', frame_red)

time.sleep(0.3)

# 3. Кадр NIR 850 нм (Включаем ТОЛЬКО Канал 2 / Pin 10)
print("[4/4] ЩЕЛЧОК 3: Включаем ТОЛЬКО ИНФРАКРАСНЫЙ 850 нм (Канал 2 / Pin 10)...")
req.set_value(7, Value.ACTIVE)
time.sleep(0.4)
for _ in range(5): cap.read()
ret, frame_nir = cap.read()
req.set_value(7, Value.INACTIVE)
print("      ЩЕЛЧОК 4: Инфракрасный выключен.")
cv2.imwrite('/home/pi/test_frames/frame_3_nir.jpg', frame_nir)

cap.release()
req.release()
print("[OK] Все 3 кадра успешно сохранены в /home/pi/test_frames/!")
'''

sftp = ssh.open_sftp()
with sftp.file('/home/pi/run_3frame.py', 'w') as f:
    f.write(remote_capture_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/run_3frame.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err: print('ERR:', err)

# Перезапускаем веб-станцию
ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')

# Скачиваем все 3 кадра для детального анализа
print("\nСкачивание полученных кадров на рабочий ПК...")
sftp = ssh.open_sftp()
local_dir = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures\true_3frame"
os.makedirs(local_dir, exist_ok=True)

for fn in ['frame_1_ambient.jpg', 'frame_2_red.jpg', 'frame_3_nir.jpg']:
    rem = f'/home/pi/test_frames/{fn}'
    loc = os.path.join(local_dir, fn)
    sftp.get(rem, loc)
    print(f" -> Скачан {fn} ({os.path.getsize(loc)} байт)")

sftp.close()
ssh.close()
