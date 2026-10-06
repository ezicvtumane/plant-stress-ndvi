import sys
import time
import requests
import paramiko
import os
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

PI_IP = '192.168.0.23'
BASE_URL = f'http://{PI_IP}:8000'

def imread_utf8(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

print("Запуск спектрального замера №2...")
resp = requests.post(f'{BASE_URL}/api/start_spectral', data={'group_name': 'Тест_СветВыкл'}, timeout=15)
print(f"Статус ответа: {resp.status_code}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, port=22, username='pi', password='1', timeout=5)
sftp = ssh.open_sftp()

local_dir = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures"
os.makedirs(local_dir, exist_ok=True)

files_to_fetch = [
    'last_amb.jpg',
    'last_flash_raw.jpg',
    'last_red.jpg',
    'last_nir.jpg',
    'last_ndvi.jpg'
]

for fname in files_to_fetch:
    remote_path = f'/home/pi/plant-stress-ndvi/static/{fname}'
    local_path = os.path.join(local_dir, f'shot2_{fname}')
    sftp.get(remote_path, local_path)

sftp.close()
ssh.close()

p_amb = os.path.join(local_dir, 'shot2_last_amb.jpg')
p_flash = os.path.join(local_dir, 'shot2_last_flash_raw.jpg')

img_amb = imread_utf8(p_amb)
img_flash = imread_utf8(p_flash)

mean_amb = np.mean(img_amb)
mean_flash = np.mean(img_flash)

r_amb = np.mean(img_amb[:, :, 2])
g_amb = np.mean(img_amb[:, :, 1])
b_amb = np.mean(img_amb[:, :, 0])

r_flash = np.mean(img_flash[:, :, 2])
g_flash = np.mean(img_flash[:, :, 1])
b_flash = np.mean(img_flash[:, :, 0])

print("\nРезультаты замера №2:")
print(f"1. Фоновый кадр (Ambient без строба):   яркость = {mean_amb:.1f} / 255 (R={r_amb:.1f}, G={g_amb:.1f}, B={b_amb:.1f})")
print(f"2. Кадр со стробом (Flash 660+850 нм):  яркость = {mean_flash:.1f} / 255 (R={r_flash:.1f}, G={g_flash:.1f}, B={b_flash:.1f})")
print(f"3. Прирост фотонного потока (ΔL):      +{mean_flash - mean_amb:.1f} единиц яркости")
print(f"   - Прирост в Red (660 нм):           +{r_flash - r_amb:.1f}")
print(f"   - Прирост в NIR (через B/G матрицу): +{(b_flash - b_amb + g_flash - g_amb)/2:.1f}")
