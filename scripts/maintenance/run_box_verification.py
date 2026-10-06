import sys
import time
import math
import requests
import paramiko
import os
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

PI_IP = '192.168.0.23'
BASE_URL = f'http://{PI_IP}:8000'

print("==================================================================")
print("     ПРОВЕРКА СТАНЦИИ ПОСЛЕ МОНТАЖА В РАСПРЕДКОРОБКУ              ")
print("==================================================================")

# --- 1. ПРОВЕРКА ШИНЫ I2C И ДАТЧИКОВ ---
print("\n[1/3] ОПРОС ДАТЧИКОВ НА ШИНЕ I2C-0:")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, port=22, username='pi', password='1', timeout=5)

sensor_script = '''
import smbus2, math, time

bus = smbus2.SMBus(0)

# SHT30
try:
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    d = bus.read_i2c_block_data(0x44, 0x00, 6)
    t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
    rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
    es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
    ea = es * (rh / 100.0)
    vpd = round(float(es - ea), 2)
    print(f"SHT30_OK: {t_c:.2f} °C | {rh:.1f} % RH | VPD: {vpd:.2f} kPa")
except Exception as e:
    print(f"SHT30_ERR: {e}")

# ADS1115 (A0)
try:
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.04)
    c = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (c[0] << 8) | c[1]
    if raw > 32767: raw -= 65536
    v_soil = raw * 0.000125
    pct_soil = max(0.0, min(100.0, (2.03 - v_soil) / (2.03 - 0.57) * 100.0))
    print(f"ADS1115_OK: Raw={raw} | V={v_soil:.3f} V | Soil={pct_soil:.1f} %")
except Exception as e:
    print(f"ADS1115_ERR: {e}")

bus.close()
'''

stdin, stdout, stderr = ssh.exec_command(f'python3 -c """{sensor_script}"""')
res_sensors = stdout.read().decode('utf-8', errors='ignore').strip()
print(res_sensors)

# --- 2. СЪЕМКА КАДРА С АКТИВНЫМ СТРОБОМ ЧЕРЕЗ ВЕБ-СТАНЦИЮ ---
print("\n[2/3] ВЫПОЛНЕНИЕ ТЕСТОВОЙ СПЕКТРАЛЬНОЙ СЪЕМКИ (/api/start_spectral)...")
try:
    resp = requests.post(f'{BASE_URL}/api/start_spectral', data={'group_name': 'Тест_Коробка'}, timeout=15)
    print(f" -> Ответ веб-станции: HTTP {resp.status_code}")
except Exception as e:
    print(f" -> Ошибка запроса: {e}")

# Скачивание полученных кадров
local_dir = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures"
os.makedirs(local_dir, exist_ok=True)

sftp = ssh.open_sftp()
for fname in ['last_amb.jpg', 'last_flash_raw.jpg', 'last_red.jpg', 'last_nir.jpg', 'last_ndvi.jpg']:
    rem = f'/home/pi/plant-stress-ndvi/static/{fname}'
    loc = os.path.join(local_dir, f'box_{fname}')
    try:
        sftp.get(rem, loc)
    except Exception as e:
        print(f" Ошибка скачивания {fname}: {e}")
sftp.close()

# Проверяем журнал веб-станции
stdin, stdout, stderr = ssh.exec_command('journalctl -u plant-station -n 15 --no-pager')
print(" -> Логи веб-станции:")
for line in stdout.read().decode('utf-8', errors='ignore').strip().split('\n'):
    if any(k in line.lower() for k in ['aruco', 'start_spectral', 'gpio', 'session', '303', 'sht30']):
        print(f"    {line}")

ssh.close()

# Сброс сессии обратно в idle
try:
    requests.get(f'{BASE_URL}/api/cancel_session', timeout=5)
except Exception:
    pass

# --- 3. ОПТИЧЕСКИЙ АНАЛИЗ СНИМКОВ ---
print("\n[3/3] АНАЛИЗ ОПТИЧЕСКИХ СИГНАЛОВ:")
def imread_utf8(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

def imwrite_utf8(path, img):
    ext = os.path.splitext(path)[1]
    ret, buf = cv2.imencode(ext, img)
    with open(path, 'wb') as f:
        f.write(buf)

p_amb = os.path.join(local_dir, 'box_last_amb.jpg')
p_flash = os.path.join(local_dir, 'box_last_flash_raw.jpg')
p_ndvi = os.path.join(local_dir, 'box_last_ndvi.jpg')

if os.path.exists(p_amb) and os.path.exists(p_flash):
    img_amb = imread_utf8(p_amb)
    img_flash = imread_utf8(p_flash)
    img_ndvi = imread_utf8(p_ndvi)

    mean_amb = np.mean(img_amb)
    mean_flash = np.mean(img_flash)

    r_amb = np.mean(img_amb[:, :, 2])
    g_amb = np.mean(img_amb[:, :, 1])
    b_amb = np.mean(img_amb[:, :, 0])

    r_flash = np.mean(img_flash[:, :, 2])
    g_flash = np.mean(img_flash[:, :, 1])
    b_flash = np.mean(img_flash[:, :, 0])

    print(f" -> Яркость фона без строба (Ambient):  {mean_amb:.1f} / 255 (R={r_amb:.1f}, G={g_amb:.1f}, B={b_amb:.1f})")
    print(f" -> Яркость при вспышке (Flash):       {mean_flash:.1f} / 255 (R={r_flash:.1f}, G={g_flash:.1f}, B={b_flash:.1f})")
    print(f" -> Импульсный прирост яркости (ΔL):   +{mean_flash - mean_amb:.1f} единиц")
    print(f" -> Прирост в красном канале 660 нм:   +{r_flash - r_amb:.1f} единиц")
    print(f" -> Прирост в ИК канале 850 нм:        +{(b_flash - b_amb + g_flash - g_amb)/2:.1f} единиц")

    # Сборка триптиха
    w, h = 640, 480
    a_res = cv2.resize(img_amb, (w, h))
    f_res = cv2.resize(img_flash, (w, h))
    n_res = cv2.resize(img_ndvi, (w, h))

    def add_banner(img, title, subtitle, color):
        c = np.zeros((h + 60, w, 3), dtype=np.uint8)
        c[60:, :] = img
        cv2.putText(c, title, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(c, subtitle, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
        return c

    p1 = add_banner(a_res, '1. AMBIENT (BEFORE FLASH)', f'L = {mean_amb:.1f} / 255', (200, 200, 200))
    p2 = add_banner(f_res, '2. STROBE (660nm + 850nm)', f'L = {mean_flash:.1f}, dR = +{r_flash - r_amb:.1f}', (50, 120, 255))
    p3 = add_banner(n_res, '3. NDVI SPECTRAL MAP', 'Physical enclosure test', (50, 220, 100))

    collage = np.hstack([p1, p2, p3])

    brain_out = r'C:\Users\Администратор\.gemini\antigravity\brain\1ce5efc4-55e3-45ca-b07c-b34c127075fc\box_verification_collage.jpg'
    imwrite_utf8(brain_out, collage)
    print(f"\n[ГОТОВО] Сравнительный триптих сохранен: {brain_out}")
