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

print("==================================================================")
print("     СЪЕМКА В ТЕМНОТЕ: ЧЕСТНЫЙ 3-КАДРОВЫЙ АППАРАТНЫЙ ПРОТОКОЛ     ")
print("==================================================================")

print("\n1. Запуск спектрального замера со стробированием в темноте...")
t0 = time.time()
resp = requests.post(f'{BASE_URL}/api/start_spectral', data={'group_name': 'Темнота_Калибровка'}, timeout=25)
t1 = time.time()
print(f" -> Ответ веб-станции: HTTP {resp.status_code} за {t1 - t0:.2f} сек")

# Скачиваем полученные снимки
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, port=22, username='pi', password='1', timeout=5)
sftp = ssh.open_sftp()

local_dir = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures\dark_shots"
os.makedirs(local_dir, exist_ok=True)

files = ['last_amb.jpg', 'last_red.jpg', 'last_nir.jpg', 'last_ndvi.jpg']
for fn in files:
    rem = f'/home/pi/plant-stress-ndvi/static/{fn}'
    loc = os.path.join(local_dir, fn)
    sftp.get(rem, loc)

sftp.close()

# Сбрасываем сессию в idle
try:
    requests.get(f'{BASE_URL}/api/cancel_session', timeout=5)
except Exception:
    pass

ssh.close()

# Анализ фотометрии
def imread_utf8(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

def imwrite_utf8(path, img):
    ext = os.path.splitext(path)[1]
    ret, buf = cv2.imencode(ext, img)
    with open(path, 'wb') as f:
        f.write(buf)

f_amb = imread_utf8(os.path.join(local_dir, 'last_amb.jpg'))
f_red = imread_utf8(os.path.join(local_dir, 'last_red.jpg'))
f_nir = imread_utf8(os.path.join(local_dir, 'last_nir.jpg'))
f_ndvi = imread_utf8(os.path.join(local_dir, 'last_ndvi.jpg'))

l_amb = np.mean(f_amb)
l_red = np.mean(f_red)
l_nir = np.mean(f_nir)

r_red = np.mean(f_red[:, :, 2])
nir_nir = np.mean(f_nir)

print("\n2. Фотометрический анализ сигналов в темноте:")
print(f" -> 1. Кадр Ambient (в темноте):    яркость L = {l_amb:.2f} / 255 (R={np.mean(f_amb[:,:,2]):.1f}, G={np.mean(f_amb[:,:,1]):.1f}, B={np.mean(f_amb[:,:,0]):.1f})")
print(f" -> 2. Вспышка Красного 660 нм:     яркость L = {l_red:.2f} / 255 (R={r_red:.1f}, прирост в красном: +{r_red - np.mean(f_amb[:,:,2]):.1f})")
print(f" -> 3. Вспышка Инфракрасного 850нм:  яркость L = {l_nir:.2f} / 255 (прирост общего ИК-потока: +{l_nir - l_amb:.1f})")

# Генерация 4-панельного триптиха
w, h = 640, 480
a_res = cv2.resize(f_amb, (w, h))
r_res = cv2.resize(f_red, (w, h))
n_res = cv2.resize(f_nir, (w, h))
v_res = cv2.resize(f_ndvi, (w, h))

def add_banner(img, title, subtitle, color):
    c = np.zeros((h + 60, w, 3), dtype=np.uint8)
    c[60:, :] = img
    cv2.putText(c, title, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    cv2.putText(c, subtitle, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1)
    return c

p1 = add_banner(a_res, '1. AMBIENT (LIGHTS OFF)', f'Dark room: L={l_amb:.1f} / 255', (200, 200, 200))
p2 = add_banner(r_res, '2. RED 660nm SOLO (CLICK 1-2)', f'Pure Red strobe: R={r_red:.1f}', (50, 50, 255))
p3 = add_banner(n_res, '3. NIR 850nm SOLO (CLICK 3-4)', f'Pure NIR strobe: L={l_nir:.1f}', (255, 120, 50))
p4 = add_banner(v_res, '4. HARDWARE NDVI MAP', 'Zero-noise dark baseline', (50, 220, 100))

collage_top = np.hstack([p1, p2])
collage_bot = np.hstack([p3, p4])
collage = np.vstack([collage_top, collage_bot])

out_p = r'C:\Users\Администратор\.gemini\antigravity\brain\1ce5efc4-55e3-45ca-b07c-b34c127075fc\dark_room_strobe_verification.jpg'
imwrite_utf8(out_p, collage)
print(f"\n[ГОТОВО] Фотоколлаж в темноте сохранен: {out_p}")
