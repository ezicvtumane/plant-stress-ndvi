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

print(f"1. Отправляем запрос на спектральную съемку через веб-станцию ({BASE_URL}/api/start_spectral)...")
# POST request to start spectral capture
try:
    resp = requests.post(f'{BASE_URL}/api/start_spectral', data={'group_name': 'Тест_Темнота'}, timeout=15)
    print(f"   Ответ веб-станции: HTTP {resp.status_code}")
except Exception as e:
    print(f"   Ошибка HTTP запроса: {e}")

# Download generated images via SFTP
print("\n2. Скачивание полученных снимков с Orange Pi...")
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
    local_path = os.path.join(local_dir, f'shot1_{fname}')
    try:
        sftp.get(remote_path, local_path)
        size = os.path.getsize(local_path)
        print(f"   Скачан {fname} -> {size} байт")
    except Exception as e:
        print(f"   Ошибка скачивания {fname}: {e}")

sftp.close()

# Also fetch journalctl to see what happened on server
stdin, stdout, stderr = ssh.exec_command('journalctl -u plant-station -n 20 --no-pager')
server_logs = stdout.read().decode('utf-8', errors='ignore')
print("\n3. Логи веб-станции:")
for l in server_logs.strip().split('\n'):
    if any(k in l.lower() for k in ['aruco', 'start_spectral', 'gpio', 'error', 'session', 'sht30', 'ads1115']):
        print(f"   {l}")

ssh.close()

# Analyze shot 1 images
amb_path = os.path.join(local_dir, 'shot1_last_amb.jpg')
flash_path = os.path.join(local_dir, 'shot1_last_flash_raw.jpg')

if os.path.exists(amb_path) and os.path.exists(flash_path):
    img_amb = cv2.imread(amb_path)
    img_flash = cv2.imread(flash_path)
    
    mean_amb = np.mean(img_amb)
    mean_flash = np.mean(img_flash)
    
    b_flash = np.mean(img_flash[:, :, 0])
    g_flash = np.mean(img_flash[:, :, 1])
    r_flash = np.mean(img_flash[:, :, 2])
    
    print("\n4. Анализ оптического сигнала (Shot 1):")
    print(f"   Яркость фона (без вспышки):  {mean_amb:.1f} / 255")
    print(f"   Яркость при вспышке диодов:  {mean_flash:.1f} / 255")
    print(f"   Разница освещенности (ΔL):   +{mean_flash - mean_amb:.1f}")
    print(f"   Цветовые каналы вспышки: R={r_flash:.1f}, G={g_flash:.1f}, B={b_flash:.1f}")
