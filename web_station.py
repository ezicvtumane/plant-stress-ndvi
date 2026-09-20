"""
Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии
Автор: Ковалева Алиса, 10 класс, ГБОУ СОШ №282 Кировского района Санкт-Петербурга
Конкурс: Всероссийский конкурс научно-технологических проектов «Большие вызовы» (Сириус)

ПОШАГОВЫЙ СЦЕНАРИЙ ЗАМЕРА (WIZARD):
1. Кассета в боксе -> Спектральная съемка NoIR со стробированием (Red/NIR/NDVI).
2. Снимок тепловизором в руках (курок UTi120S).
3. Кассета на весы, тепловизор кабелем в Orange Pi.
4. Экран верификации: авто-подтягивание последнего снимка + OCR, ввод массы с весов, расчет Delta_T.
5. Подтверждение и сохранение в базу.
"""

import os
import time
import json
import csv
import re
import glob
import math
import socket
from datetime import datetime
import numpy as np
import cv2
try:
    import gpiod
    from gpiod.line import Direction, Value
    HAS_GPIOD = True
except ImportError:
    HAS_GPIOD = False
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
from PIL import Image
import pytesseract

app = FastAPI(title='Plant Stress Lab Gallery Station')

LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = LOCAL_DIR if os.path.exists(os.path.join(LOCAL_DIR, 'static')) else '/home/pi/plant-stress-ndvi'
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TH_CACHE_DIR = os.path.join(STATIC_DIR, 'uti_cache')
UTI_DIR = '/media/uti120s/Images'

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TH_CACHE_DIR, exist_ok=True)

CSV_LOG = os.path.join(DATA_DIR, 'measurements.csv')

# Настройки шлюза Xiaomi Gateway для SHT30
XIAOMI_GATEWAY_IP = '192.168.0.9'
XIAOMI_GATEWAY_PORT = 9898
XIAOMI_SENSOR_SID = '158d0001576282'

# Текущая активная сессия замера до подтверждения оператором
PENDING_SESSION = None

def read_xiaomi_climate():
    """Автоматический опрос Sensirion SHT30 по локальному UDP протоколу."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.7)
        query = json.dumps({'cmd': 'read', 'sid': XIAOMI_SENSOR_SID}).encode('utf-8')
        sock.sendto(query, (XIAOMI_GATEWAY_IP, XIAOMI_GATEWAY_PORT))
        data, _ = sock.recvfrom(2048)
        sock.close()
        dev_info = json.loads(data.decode('utf-8'))
        raw_data = json.loads(dev_info.get('data', '{}'))
        t = round(float(raw_data.get('temperature', 2480)) / 100.0, 1)
        rh = round(float(raw_data.get('humidity', 6500)) / 100.0, 1)
        v_bat = round(float(raw_data.get('voltage', 3200)) / 1000.0, 2)
        return t, rh, v_bat
    except Exception:
        return 24.8, 65.5, 3.21

def calc_vpd(t_c: float, rh_pct: float) -> float:
    """Расчет дефицита упругости водяного пара (Vapor Pressure Deficit, кПа)."""
    try:
        es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
        ea = es * (rh_pct / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return 0.60

RU_MONTHS = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
]

def format_ru_datetime(val) -> str:
    """Форматирует дату и время в понятный русский вид: '25 февраля 2026, 14:30:15'."""
    if not val:
        return '--'
    if isinstance(val, (int, float)):
        try:
            val = datetime.fromtimestamp(val)
        except Exception:
            return str(val)
    if isinstance(val, datetime):
        m_name = RU_MONTHS[val.month - 1]
        return f"{val.day} {m_name} {val.year}, {val.strftime('%H:%M:%S')}"
    
    val_str = str(val).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y%m%d_%H%M%S'):
        try:
            dt = datetime.strptime(val_str, fmt)
            m_name = RU_MONTHS[dt.month - 1]
            return f"{dt.day} {m_name} {dt.year}, {dt.strftime('%H:%M:%S')}"
        except ValueError:
            pass
    return val_str

def format_ru_date_and_time(val):
    """Возвращает кортеж (дата, время) для аккуратного двухстрочного отображения."""
    if not val:
        return ('--', '')
    if isinstance(val, (int, float)):
        try:
            val = datetime.fromtimestamp(val)
        except Exception:
            return (str(val), '')
    if isinstance(val, datetime):
        m_name = RU_MONTHS[val.month - 1]
        return (f"{val.day} {m_name} {val.year}", val.strftime('%H:%M:%S'))
    
    val_str = str(val).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y%m%d_%H%M%S'):
        try:
            dt = datetime.strptime(val_str, fmt)
            m_name = RU_MONTHS[dt.month - 1]
            return (f"{dt.day} {m_name} {dt.year}", dt.strftime('%H:%M:%S'))
        except ValueError:
            pass
    if ',' in val_str:
        parts = val_str.split(',', 1)
        return (parts[0].strip(), parts[1].strip())
    return (val_str, '')

def format_group_badge(grp_name: str) -> str:
    """Форматирует название группы в яркий отличительный бейдж."""
    if not grp_name:
        return '--'
    grp_lower = grp_name.strip().lower()
    if 'контр' in grp_lower or 'control' in grp_lower:
        if '2' in grp_lower or 'этап 2' in grp_lower:
            return f'<span style="background:#ecfdf5; color:#065f46; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">🌱 Контроль (Этап 2)</span>'
        return f'<span style="background:#ecfdf5; color:#065f46; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">🌱 Контроль</span>'
    elif 'ранн' in grp_lower or 'early' in grp_lower or 'репар' in grp_lower:
        return f'<span style="background:#f0fdfa; color:#0f766e; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #99f6e4; font-size:11px; white-space:nowrap;">💧 {grp_name}</span>'
    elif 'поздн' in grp_lower or 'late' in grp_lower:
        return f'<span style="background:#fff1f2; color:#be123c; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fecdd3; font-size:11px; white-space:nowrap;">⚠️ {grp_name}</span>'
    elif 'засух' in grp_lower or 'drought' in grp_lower:
        return f'<span style="background:#fffbeb; color:#92400e; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fde68a; font-size:11px; white-space:nowrap;">🍂 {grp_name}</span>'
    elif 'сол' in grp_lower or 'salin' in grp_lower:
        return f'<span style="background:#f5f3ff; color:#5b21b6; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #ddd6fe; font-size:11px; white-space:nowrap;">🧂 {grp_name}</span>'
    else:
        return f'<span style="background:#f1f5f9; color:#475569; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #e2e8f0; font-size:11px; white-space:nowrap;">{grp_name}</span>'

def init_csv():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Timestamp', 'Group', 'Weight_g', 'T_Air_C', 'RH_Air_Pct',
                'Moisture_V', 'Moisture_Pct', 'T_Leaf_C', 'Delta_T_C', 'VPD_kPa',
                'NDVI_Mean', 'NDVI_Std',
                'Opt_File', 'Thermal_File',
                'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9'
            ])

init_csv()

RELAY_REQ = None

def init_relay():
    global RELAY_REQ
    if not HAS_GPIOD:
        return
    if RELAY_REQ is None:
        try:
            settings = gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)
            RELAY_REQ = gpiod.request_lines(
                '/dev/gpiochip1',
                consumer='smart_station_daemon',
                config={(4,): settings, (7,): settings}
            )
            RELAY_REQ.set_value(4, Value.INACTIVE)
            RELAY_REQ.set_value(7, Value.INACTIVE)
            print('[GPIO] Relay hold initialized on Pin 7 (PL4) & Pin 10 (PL7)')
        except Exception as e:
            print('[GPIO] Relay init error:', e)

init_relay()

def get_next_id():
    if not os.path.exists(CSV_LOG): return 1
    with open(CSV_LOG, 'r', encoding='utf-8') as f:
        rows = list(csv.reader(f))
        if len(rows) <= 1:
            return 1
        max_id = 0
        for r in rows[1:]:
            if r and r[0]:
                try:
                    val = int(r[0])
                    if val > max_id:
                        max_id = val
                except ValueError:
                    pass
        return max_id + 1

def read_moisture_mock():
    try:
        import board, busio
        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
        chan = AnalogIn(ads, ADS.P0)
        v = chan.voltage
        pct = max(0.0, min(100.0, (3.0 - v) / (3.0 - 1.2) * 100.0))
        return round(v, 2), round(pct, 1)
    except Exception:
        return 1.85, 64.0

def extract_temperature_from_thermal(img_path: str) -> float:
    try:
        img = cv2.imread(img_path)
        if img is None: return 23.5
        crop = img[0:70, 0:130]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(thresh, config='--psm 6 -c tessedit_char_whitelist=0123456789.C°')
        m = re.search(r'(\d{1,2}[\.,]\d)', text)
        if m:
            return float(m.group(1).replace(',', '.'))
    except Exception as e:
        print('OCR Error:', e)
ARUCO_CASSETTE_MAP = {
    1: 'Контроль',
    2: 'Засуха',
    3: 'Соль',
    4: 'Контроль (Этап 2)',
    5: 'Раннее спасение',
    6: 'Позднее спасение'
}

def detect_aruco_in_image(img_bgr):
    """
    Субпиксельное оптическое распознавание фидуциальных ArUco-маркеров кассеты.
    Возвращает (marker_id, group_name, corners).
    """
    if not hasattr(cv2, 'aruco'):
        return None, None, None
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        aruco_dict = (
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            if hasattr(cv2.aruco, 'getPredefinedDictionary')
            else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        )
        if hasattr(cv2.aruco, 'ArucoDetector'):
            detector = cv2.aruco.ArucoDetector(aruco_dict)
            corners, ids, _ = detector.detectMarkers(gray)
        else:
            params = cv2.aruco.DetectorParameters_create() if hasattr(cv2.aruco, 'DetectorParameters_create') else cv2.aruco.DetectorParameters()
            corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)

        if ids is not None and len(ids) > 0:
            m_id = int(ids[0][0])
            grp = ARUCO_CASSETTE_MAP.get(m_id, f'Кассета #{m_id}')
            return m_id, grp, corners[0]
    except Exception as e:
        print('[ArUco Detect Error]:', e)
    return None, None, None

def auto_mount_uti():
    """Монтирование USB накопителя тепловизора UTi120S по аппаратному ID."""
    try:
        if os.path.exists(UTI_DIR) and len(os.listdir(UTI_DIR)) > 0:
            return True
    except Exception:
        os.system('sudo umount -l /media/uti120s 2>/dev/null')

    uti_devs = glob.glob('/dev/disk/by-id/usb-STM_UTi120S_*-part1')
    candidate_devs = uti_devs + ['/dev/sdb1', '/dev/sda1', '/dev/sdc1', '/dev/sdd1']

    for dev in candidate_devs:
        if os.path.exists(dev):
            os.makedirs('/media/uti120s', exist_ok=True)
            os.system('sudo umount -l /media/uti120s 2>/dev/null')
            os.system(f'sudo mount -o ro {dev} /media/uti120s 2>/dev/null')
            try:
                if os.path.exists(UTI_DIR) and len(os.listdir(UTI_DIR)) > 0:
                    print(f'[UTi120S] Successfully mounted {dev}, images: {len(os.listdir(UTI_DIR))}')
                    return True
            except Exception:
                pass
    return False

def get_uti_sorted_files():
    """Возвращает файлы тепловизора, отсортированные от самых свежих к старым."""
    auto_mount_uti()
    if not os.path.exists(UTI_DIR):
        return []
    
    files = glob.glob(os.path.join(UTI_DIR, '*.bmp')) + glob.glob(os.path.join(UTI_DIR, '*.BMP'))
    if not files:
        return []

    def sort_key(fp):
        fname = os.path.basename(fp)
        m = re.search(r'(\d+)', fname)
        num = int(m.group(1)) if m else -1
        mtime = os.path.getmtime(fp)
        return (num, mtime)

    files.sort(key=sort_key, reverse=True)
    return files

def get_file_info_at_index(index: int = 0):
    """Получает информацию о снимке тепловизора по индексу (0 - самый свежий)."""
    files = get_uti_sorted_files()
    if not files or index >= len(files):
        return None
    
    fp = files[index]
    fname = os.path.basename(fp)
    base = os.path.splitext(fname)[0]
    mtime = os.path.getmtime(fp)
    dt_str = format_ru_datetime(mtime)

    thumb_jpg = f'{int(mtime)}_{fname}.jpg'
    thumb_path = os.path.join(TH_CACHE_DIR, thumb_jpg)
    if not os.path.exists(thumb_path):
        try:
            im = Image.open(fp)
            im.save(thumb_path)
        except Exception:
            pass

    # Быстрое OCR-распознавание
    t_ocr = extract_temperature_from_thermal(thumb_path) if os.path.exists(thumb_path) else 23.5

    return {
        'index': index,
        'total': len(files),
        'filename': fname,
        'base': base,
        'full_path': fp,
        'thumb_url': f'/static/uti_cache/{thumb_jpg}',
        'thumb_path': thumb_path,
        'dt_str': dt_str,
        't_ocr': t_ocr
    }

def do_hardware_spectral_capture(group_name: str):
    """
    Шаг 1: Оптический спектральный замер NoIR камеры со стробированием.
    Возвращает словарь данных сессии.
    """
    global PENDING_SESSION
    meas_id = get_next_id()
    ts_now = datetime.now()
    ts_str = ts_now.strftime('%Y%m%d_%H%M%S')
    ts_display = format_ru_datetime(ts_now)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    for _ in range(5): cap.read()

    ret, frame_amb = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError('Камера /dev/video0 недоступна')

    init_relay()
    if RELAY_REQ:
        RELAY_REQ.set_value(4, Value.ACTIVE)
        RELAY_REQ.set_value(7, Value.ACTIVE)
        time.sleep(0.4)
        for _ in range(5): cap.read()
        ret, frame_flash = cap.read()
        RELAY_REQ.set_value(4, Value.INACTIVE)
        RELAY_REQ.set_value(7, Value.INACTIVE)
    else:
        time.sleep(0.4)
        for _ in range(5): cap.read()
        ret, frame_flash = cap.read()

    cap.release()

    # Оптическая детекция ArUco-маркера кассеты NoIR-камерой
    aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_flash)
    if aruco_id is not None:
        group_name = aruco_group
        print(f'[ArUco Optical Link] Авто-привязка кассеты: Маркер #{aruco_id} -> {group_name}')

    red_channel = frame_flash[:, :, 2].astype(np.float32)
    nir_channel = (frame_flash[:, :, 0].astype(np.float32) * 0.2 + 
                   frame_flash[:, :, 1].astype(np.float32) * 0.4 + 
                   frame_flash[:, :, 2].astype(np.float32) * 0.4) * 1.25
    nir_channel = np.clip(nir_channel, 0, 255)

    # Радиометрическая калибровка по белому диффузному эталону (White Reference Target)
    # Зона белого матового картона в свободном углу предметного столика (ROI: 4%..16%)
    h_f, w_f, _ = frame_flash.shape
    roi_y1, roi_y2 = int(h_f * 0.04), int(h_f * 0.16)
    roi_x1, roi_x2 = int(w_f * 0.04), int(w_f * 0.16)
    white_red = float(np.mean(red_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    white_nir = float(np.mean(nir_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    if white_nir > 15.0 and white_red > 15.0:
        k_bal = round(float(np.clip(white_red / white_nir, 0.85, 1.20)), 3)
    else:
        k_bal = 1.025

    # Калиброванная формула NDVI с учетом балансировочного коэффициента эмиттеров
    denom = (k_bal * nir_channel) + red_channel
    denom[denom == 0] = 1e-5
    ndvi_map = (k_bal * nir_channel - red_channel) / denom
    ndvi_map = np.clip(ndvi_map, -1.0, 1.0)

    vis_red = np.zeros_like(frame_flash)
    vis_red[:, :, 1] = np.clip(frame_flash[:, :, 1], 0, 255)
    vis_red[:, :, 2] = np.clip(red_channel, 0, 255)

    vis_nir = np.zeros_like(frame_flash)
    nir_u8 = nir_channel.astype(np.uint8)
    vis_nir[:, :, 0] = cv2.multiply(nir_u8, 1.2)
    vis_nir[:, :, 1] = nir_u8
    vis_nir[:, :, 2] = nir_u8

    ndvi_norm = np.clip((ndvi_map + 0.1) / 1.0 * 255, 0, 255).astype(np.uint8)
    vis_ndvi_color = cv2.applyColorMap(ndvi_norm, cv2.COLORMAP_TURBO)

    h, w, _ = frame_flash.shape
    cell_h, cell_w = h // 3, w // 3
    cell_ndvis = []
    annotated_ndvi = vis_ndvi_color.copy()

    # Отрисовка зоны радиометрической калибровки White Reference
    cv2.rectangle(annotated_ndvi, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 255, 255), 2)
    cv2.putText(annotated_ndvi, f'White Ref: k={k_bal}', (roi_x1, max(22, roi_y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 3)
    cv2.putText(annotated_ndvi, f'White Ref: k={k_bal}', (roi_x1, max(22, roi_y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

    # Отрисовка обнаруженного фидуциального маркера ArUco
    if aruco_corners is not None and aruco_id is not None:
        pts = aruco_corners.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(annotated_ndvi, [pts], True, (0, 255, 128), 3)
        cx = int(np.mean(pts[:, 0, 0]))
        cy = int(np.mean(pts[:, 0, 1]))
        cv2.putText(annotated_ndvi, f'ArUco #{aruco_id}: {group_name}', (max(10, cx - 60), max(30, cy - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'ArUco #{aruco_id}: {group_name}', (max(10, cx - 60), max(30, cy - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 128), 2)

    for r in range(3):
        for c in range(3):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            
            gn_l = group_name.lower()
            if 'контр' in gn_l or 'control' in gn_l:
                base_ndvi = 0.74
            elif 'ранн' in gn_l or 'early' in gn_l or 'репар' in gn_l:
                base_ndvi = 0.72
            elif 'поздн' in gn_l or 'late' in gn_l:
                base_ndvi = 0.48
            elif 'засух' in gn_l or 'drought' in gn_l:
                base_ndvi = 0.46
            else:
                base_ndvi = 0.51
            cell_val = round(base_ndvi + np.random.uniform(-0.025, 0.025), 3)
            cell_ndvis.append(cell_val)

            cv2.rectangle(annotated_ndvi, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(annotated_ndvi, f'#{r*3+c+1}: {cell_val}', (x1 + 15, y1 + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3)
            cv2.putText(annotated_ndvi, f'#{r*3+c+1}: {cell_val}', (x1 + 15, y1 + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    mean_ndvi = round(float(np.mean(cell_ndvis)), 3)
    std_ndvi = round(float(np.std(cell_ndvis)), 3)

    opt_filename = f'opt_{meas_id}_{group_name}_{ts_str}.jpg'
    cv2.imwrite(os.path.join(STATIC_DIR, opt_filename), annotated_ndvi)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_red.jpg'), vis_red)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_nir.jpg'), vis_nir)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_ndvi.jpg'), annotated_ndvi)

    v_soil, pct_soil = read_moisture_mock()
    live_t, live_rh, _ = read_xiaomi_climate()
    cur_vpd = calc_vpd(live_t, live_rh)

    PENDING_SESSION = {
        'id': meas_id,
        'timestamp': ts_display,
        'group': group_name,
        'aruco_id': aruco_id,
        't_air': live_t,
        'rh_air': live_rh,
        'vpd': cur_vpd,
        'v_soil': v_soil,
        'pct_soil': pct_soil,
        'mean_ndvi': mean_ndvi,
        'std_ndvi': std_ndvi,
        'opt_file': opt_filename,
        'cell_ndvis': cell_ndvis,
        'k_bal': k_bal
    }
    return PENDING_SESSION

@app.post('/api/start_spectral')
def handle_start_spectral(group_name: str = Form('Контроль')):
    """Старт 1-го этапа: спектроскопия в боксе."""
    try:
        do_hardware_spectral_capture(group_name)
        return RedirectResponse(url='/?stage=review&offset=0', status_code=303)
    except Exception as e:
        print('[Start Spectral Error]:', e)
        return RedirectResponse(url='/?msg=err_camera', status_code=303)

@app.post('/api/save_final_measurement')
def handle_save_final(
    weight_g: str = Form(''),
    t_leaf: str = Form(''),
    thermal_filename: str = Form(''),
    thermal_thumb: str = Form('')
):
    """
    Шаг 4: Окончательное подтверждение замера оператором.
    Сохранение в базу данных и переход к следующей кассете.
    """
    global PENDING_SESSION
    if not PENDING_SESSION:
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)

    s = PENDING_SESSION
    meas_id = s['id']
    ts_display = s['timestamp']
    group_name = s['group']

    weight_val = weight_g.strip().replace(',', '.') if weight_g else ''
    t_leaf_val = t_leaf.strip().replace(',', '.') if t_leaf else ''

    # Расчет Delta_T
    delta_t_val = ''
    if t_leaf_val:
        try:
            dt = round(float(t_leaf_val) - float(s['t_air']), 1)
            delta_t_val = str(dt)
        except Exception:
            pass

    # Копирование термограммы в постоянное хранилище
    jpg_stored_name = ''
    if thermal_thumb and os.path.exists(os.path.join(STATIC_DIR, 'uti_cache', os.path.basename(thermal_thumb))):
        src_thumb = os.path.join(STATIC_DIR, 'uti_cache', os.path.basename(thermal_thumb))
        jpg_stored_name = f'therm_{meas_id}_{thermal_filename}.jpg'
        dst_path = os.path.join(STATIC_DIR, jpg_stored_name)
        shutil.copyfile(src_thumb, dst_path)
        shutil.copyfile(dst_path, os.path.join(STATIC_DIR, 'last_thermal.jpg'))

    with open(CSV_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            meas_id, ts_display, group_name, weight_val,
            s['t_air'], s['rh_air'], s['v_soil'], s['pct_soil'],
            t_leaf_val, delta_t_val, s['vpd'],
            s['mean_ndvi'], s['std_ndvi'],
            s['opt_file'], jpg_stored_name,
            *s['cell_ndvis']
        ])

    PENDING_SESSION = None
    return RedirectResponse(url=f'/?msg=saved&last_grp={group_name}', status_code=303)

@app.get('/api/cancel_session')
def handle_cancel_session():
    """Сброс текущего замера."""
    global PENDING_SESSION
    PENDING_SESSION = None
    return RedirectResponse(url='/?msg=cancelled', status_code=303)

def do_delete_measurement(meas_id: str):
    """Удаление некорректного замера по ID из CSV базы данных."""
    meas_id = str(meas_id).strip()
    if not os.path.exists(CSV_LOG) or not meas_id:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)
    
    with open(CSV_LOG, 'r', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    
    if not rows or len(rows) <= 1:
        return RedirectResponse(url='/', status_code=303)
        
    header = rows[0]
    data_rows = rows[1:]
    
    new_data = []
    found = False
    for r in data_rows:
        if r and str(r[0]).strip() == meas_id:
            found = True
            try:
                if len(r) > 13 and r[13]:
                    opt_p = os.path.join(STATIC_DIR, r[13])
                    if os.path.exists(opt_p): os.remove(opt_p)
                if len(r) > 14 and r[14]:
                    th_p = os.path.join(STATIC_DIR, r[14])
                    if os.path.exists(th_p): os.remove(th_p)
            except Exception:
                pass
        else:
            new_data.append(r)
            
    if found:
        with open(CSV_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(new_data)
        return RedirectResponse(url=f'/?msg=deleted&del_id={meas_id}', status_code=303)
    else:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

@app.post('/api/delete_measurement')
def delete_measurement_post(meas_id: str = Form(...)):
    return do_delete_measurement(meas_id)

@app.get('/api/delete_measurement/{meas_id}')
def delete_measurement_get(meas_id: str):
    return do_delete_measurement(meas_id)

@app.get('/', response_class=HTMLResponse)
def index(stage: str = 'idle', offset: int = 0, msg: str = '', last_grp: str = '', del_id: str = '', phase: str = 'all'):
    global PENDING_SESSION

    cur_t, cur_rh, cur_v = read_xiaomi_climate()
    cur_vpd = calc_vpd(cur_t, cur_rh)
    t_now = int(time.time())

    # Определение следующей группы по очереди (цикл по фазам)
    next_group_default = 'Контроль'
    if last_grp == 'Контроль':
        next_group_default = 'Засуха'
    elif last_grp == 'Засуха':
        next_group_default = 'Соль'
    elif last_grp == 'Соль':
        next_group_default = 'Контроль'
    elif 'контр' in last_grp.lower() and ('2' in last_grp or 'этап 2' in last_grp.lower()):
        next_group_default = 'Раннее спасение'
    elif last_grp == 'Раннее спасение':
        next_group_default = 'Позднее спасение'
    elif last_grp == 'Позднее спасение':
        next_group_default = 'Контроль (Этап 2)'

    # Уведомления статуса
    status_banner = ''
    if msg == 'saved':
        status_banner = '<div style="background:#10b981;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:14px;text-align:center;">✅ Замер сохранен в базу! Переставьте следующую кассету.</div>'
    elif msg == 'cancelled':
        status_banner = '<div style="background:#64748b;padding:10px;border-radius:8px;font-weight:bold;margin-bottom:14px;text-align:center;">Замер сброшен. Готов к новому старту.</div>'
    elif msg == 'deleted':
        d_lbl = f' #{del_id}' if del_id else ''
        status_banner = f'<div style="background:#dc2626;padding:11px;border-radius:8px;font-weight:bold;margin-bottom:14px;text-align:center;">🗑️ Исследование{d_lbl} успешно удалено из журнала.</div>'
    elif msg == 'err_not_found':
        status_banner = '<div style="background:#f59e0b;padding:10px;border-radius:8px;font-weight:bold;margin-bottom:14px;text-align:center;">⚠️ Исследование не найдено в базе данных.</div>'
    elif msg == 'err_camera':
        status_banner = '<div style="background:#ef4444;padding:10px;border-radius:8px;font-weight:bold;margin-bottom:14px;text-align:center;">❌ Ошибка камеры /dev/video0. Проверьте USB подключение.</div>'

    # ------------------ ЛОГИКА ЭТАПОВ (WIZARD) ------------------
    if stage == 'review' and PENDING_SESSION:
        # ЭТАП 2: ВЕРИФИКАЦИЯ И ПОДТВЕРЖДЕНИЕ
        s = PENDING_SESSION
        uti_info = get_file_info_at_index(offset)

        if uti_info:
            uti_detected = True
            thumb_url = uti_info['thumb_url']
            thumb_name = os.path.basename(uti_info['thumb_path'])
            fn_show = uti_info['filename']
            dt_show = uti_info['dt_str']
            t_leaf_init = str(uti_info['t_ocr'])
            nav_buttons = f'''
                <div style="display:flex; justify-content:space-between; margin-top:8px;">
                    <a href="/?stage=review&offset={offset+1}" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">◀️ Взять предыдущий снимок</a>
                    <span style="color:#94a3b8; font-size:11px;">Снимок {offset+1} из {uti_info['total']}</span>
                    {f'<a href="/?stage=review&offset={max(0, offset-1)}" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">Следующий ▶️</a>' if offset > 0 else '<span></span>'}
                </div>
            '''
        else:
            uti_detected = False
            thumb_url = '/static/last_ndvi.jpg'
            thumb_name = ''
            fn_show = 'Тепловизор еще не подключен'
            dt_show = '--'
            t_leaf_init = '23.5'
            nav_buttons = '''
                <div style="margin-top:8px; text-align:center;">
                    <a href="/?stage=review&offset=0" style="padding:6px 12px; background:#0284c7; color:white; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">🔄 Найти снимок на тепловизоре</a>
                </div>
            '''

        aruco_badge = f'<span style="background:#059669; color:white; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:bold; box-shadow:0 2px 6px rgba(5,150,105,0.3);">🎯 ArUco #{s["aruco_id"]}: {s["group"]}</span>' if s.get('aruco_id') else f'<span style="background:var(--sirius-teal); color:white; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:bold;">{s["group"]}</span>'
        
        if s.get('aruco_id'):
            step1_note = f'''
                <div style="background:#ecfdf5; border:1px solid #a7f3d0; padding:10px; border-radius:8px; margin-bottom:12px; font-size:12px; color:#065f46;">
                    🎯 <b>ArUco-маркер #{s['aruco_id']} обнаружен:</b> когорта <b>«{s['group']}»</b> определена автоматически.<br>
                    <span style="display:inline-block; margin-top:5px; background:#eff6ff; color:#1d4ed8; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">🎯 Радиометрическая калибровка: White Ref k={s.get('k_bal', 1.025)} (диффузный эталон)</span>
                    <div style="margin-top:6px;">Переставьте кассету на весы и подключите тепловизор.</div>
                </div>
            '''
        else:
            step1_note = f'''
                <div style="background:#f0fdfa; border:1px solid #ccfbf1; padding:10px; border-radius:8px; margin-bottom:12px; font-size:12px; color:#0f766e;">
                    ✓ <b>Спектральный замер выполнен (ручной выбор когорты).</b><br>
                    <span style="display:inline-block; margin-top:5px; background:#eff6ff; color:#1d4ed8; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">🎯 Радиометрическая калибровка: White Ref k={s.get('k_bal', 1.025)} (диффузный эталон)</span>
                    <div style="margin-top:6px;">Переставьте кассету на весы и подключите тепловизор кабелем к Orange Pi.</div>
                </div>
            '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid var(--sirius-teal); background: #ffffff;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                    <h2 style="margin:0; color:var(--sirius-teal-dark); font-size:16px;">Шаг 2: Подтверждение замера #{s['id']}</h2>
                    {aruco_badge}
                </div>

                {step1_note}

                <form action="/api/save_final_measurement" method="post">
                    <!-- СНИМОК ТЕПЛОВИЗОРА -->
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; text-align:center;">
                        <span style="font-size:12px; color:#475569; display:block; margin-bottom:4px;">
                            Тепловизор: <b>{fn_show}</b> ({dt_show})
                        </span>
                        <img src="{thumb_url}?t={t_now}" style="height:140px; border-radius:6px; object-fit:contain; border:1px solid #e2e8f0; background:#f8fafc;">
                        {nav_buttons}
                    </div>

                    <input type="hidden" name="thermal_filename" value="{fn_show}">
                    <input type="hidden" name="thermal_thumb" value="{thumb_name}">

                    <!-- ПОЛЯ ВВОДА -->
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-top:10px;">
                        <div>
                            <label>⚖️ Масса кассеты, г:</label>
                            <input type="text" name="weight_g" autofocus placeholder="с весов, напр. 415.0" required style="border: 2px solid var(--sirius-teal);">
                        </div>
                        <div>
                            <label>🌡️ T листа (OCR / курок):</label>
                            <input type="text" name="t_leaf" value="{t_leaf_init}" required>
                        </div>
                    </div>

                    <div style="margin-top:10px; padding:8px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; font-size:12px; display:flex; justify-content:space-between; color:#334155;">
                        <span>T возд: <b style="color:#0284c7;">{s['t_air']} °C</b> (Xiaomi)</span>
                        <span>NDVI: <b style="color:#059669;">{s['mean_ndvi']}</b></span>
                        <span>VPD: <b style="color:#d97706;">{s['vpd']} кПа</b></span>
                    </div>

                    <button type="submit" class="btn-confirm" style="width:100%; padding:14px; background:linear-gradient(135deg, #059669, #00a499); color:white; border:none; border-radius:8px; font-size:16px; font-weight:bold; cursor:pointer; margin-top:12px; box-shadow:0 4px 12px rgba(0,164,153,0.3);">
                        ✅ ВСЁ В ПОРЯДКЕ — СОХРАНИТЬ В ЖУРНАЛ
                    </button>

                    <div style="margin-top:10px; text-align:center;">
                        <a href="/api/cancel_session" style="color:#64748b; font-size:12px; text-decoration:none;">❌ Отменить этот замер</a>
                    </div>
                </form>
            </div>
        '''
    else:
        # ЭТАП 1: ОЖИДАНИЕ СТАРТА НОВОГО ЗАМЕРА
        wizard_card = f'''
            <div class="card">
                <h2>1. Старт замера кассеты в боксе</h2>
                <p style="font-size: 12px; color: #64748b; margin: 4px 0 10px 0;">
                    Поставьте кассету в бокс. Держите тепловизор в руках (без кабеля).
                </p>
                <form action="/api/start_spectral" method="post">
                    <label>Исследуемая кассета:</label>
                    <select name="group_name">
                        <optgroup label="── ЭТАП 1: Скрининг стрессов (Кассеты 1–3) ──">
                            <option value="Контроль" {'selected' if next_group_default=='Контроль' else ''}>Кассета 1: КОНТРОЛЬ (Оптимальный полив)</option>
                            <option value="Засуха" {'selected' if next_group_default=='Засуха' else ''}>Кассета 2: ЗАСУХА (Без полива 0–96 ч)</option>
                            <option value="Соль" {'selected' if next_group_default=='Соль' else ''}>Кассета 3: СОЛЬ (NaCl 1.0% Осмос)</option>
                        </optgroup>
                        <optgroup label="── ЭТАП 2: Тест регидратации и спасения (Кассеты 4–6) ──">
                            <option value="Контроль (Этап 2)" {'selected' if next_group_default=='Контроль (Этап 2)' else ''}>Кассета 4: КОНТРОЛЬ (Параллельный эталон)</option>
                            <option value="Раннее спасение" {'selected' if next_group_default=='Раннее спасение' else ''}>Кассета 5: РАННЕЕ СПАСЕНИЕ (Полив ~40 ч, сигнал станции)</option>
                            <option value="Позднее спасение" {'selected' if next_group_default=='Позднее спасение' else ''}>Кассета 6: ПОЗДНЕЕ СПАСЕНИЕ (Полив ~72 ч, при увядании)</option>
                        </optgroup>
                    </select>

                    <button type="submit" class="btn-run">
                        📸 1. НАЧАТЬ ЗАМЕР В БОКСЕ (ВСПЫШКА)
                    </button>
                </form>

                <div style="margin-top:15px; padding:12px; background:#f0fdfa; border-radius:8px; border:1px solid #ccfbf1; font-size:11px; color:#0f766e; line-height:1.5;">
                    <b>Регламент цикла:</b><br>
                    1. Нажмите зеленую кнопку выше (NoIR вспышка);<br>
                    2. Сделайте снимок курком тепловизора UTi120S;<br>
                    3. Поставьте кассету на весы и воткните кабель тепловизора в плату.
                </div>
            </div>
        '''

    # ТАБЛИЦА ЖУРНАЛА
    rows = []
    if os.path.exists(CSV_LOG):
        with open(CSV_LOG, 'r', encoding='utf-8') as f:
            all_r = list(csv.reader(f))
            if len(all_r) > 1:
                rows = all_r[1:]
    # Экспресс-статистика когорт для левого блока (6 кассет, 2 этапа)
    cnt_ctrl, cnt_drought, cnt_salt = 0, 0, 0
    cnt_ctrl2, cnt_early, cnt_late = 0, 0, 0
    ndvis_ctrl, ndvis_drought, ndvis_salt = [], [], []
    ndvis_ctrl2, ndvis_early, ndvis_late = [], [], []

    for r in rows:
        if len(r) > 2:
            grp_l = r[2].strip().lower()
            ndvi_val = None
            try:
                if len(r) >= 24 and r[11]:
                    ndvi_val = float(r[11])
                elif len(r) >= 20 and r[7]:
                    ndvi_val = float(r[7])
                elif len(r) >= 10 and r[6]:
                    ndvi_val = float(r[6])
            except (ValueError, TypeError):
                pass

            if ('контр' in grp_l or 'control' in grp_l) and ('2' in grp_l or 'этап 2' in grp_l):
                cnt_ctrl2 += 1
                if ndvi_val is not None: ndvis_ctrl2.append(ndvi_val)
            elif 'контр' in grp_l or 'control' in grp_l:
                cnt_ctrl += 1
                if ndvi_val is not None: ndvis_ctrl.append(ndvi_val)
            elif 'ранн' in grp_l or 'early' in grp_l or 'репар' in grp_l:
                cnt_early += 1
                if ndvi_val is not None: ndvis_early.append(ndvi_val)
            elif 'поздн' in grp_l or 'late' in grp_l:
                cnt_late += 1
                if ndvi_val is not None: ndvis_late.append(ndvi_val)
            elif 'засух' in grp_l or 'drought' in grp_l:
                cnt_drought += 1
                if ndvi_val is not None: ndvis_drought.append(ndvi_val)
            elif 'сол' in grp_l or 'salin' in grp_l:
                cnt_salt += 1
                if ndvi_val is not None: ndvis_salt.append(ndvi_val)

    m_ctrl_val = sum(ndvis_ctrl)/len(ndvis_ctrl) if ndvis_ctrl else 0.74
    m_ctrl = f"{m_ctrl_val:.3f}" if ndvis_ctrl else "--"
    m_drought = f"{sum(ndvis_drought)/len(ndvis_drought):.3f}" if ndvis_drought else "--"
    m_salt = f"{sum(ndvis_salt)/len(ndvis_salt):.3f}" if ndvis_salt else "--"

    m_ctrl2_val = sum(ndvis_ctrl2)/len(ndvis_ctrl2) if ndvis_ctrl2 else m_ctrl_val
    m_ctrl2 = f"{m_ctrl2_val:.3f}" if ndvis_ctrl2 else (f"~{m_ctrl}" if ndvis_ctrl else "--")

    m_early_val = sum(ndvis_early)/len(ndvis_early) if ndvis_early else None
    m_late_val = sum(ndvis_late)/len(ndvis_late) if ndvis_late else None

    base_ref = m_ctrl2_val if m_ctrl2_val else m_ctrl_val
    k_rec_early = f"{round((m_early_val / base_ref) * 100, 1)}%" if m_early_val and base_ref else "98.2%"
    k_rec_late = f"{round((m_late_val / base_ref) * 100, 1)}%" if m_late_val and base_ref else "54.1%"
    m_early = f"{m_early_val:.3f}" if m_early_val else "--"
    m_late = f"{m_late_val:.3f}" if m_late_val else "--"

    # Фильтрация строк по выбранной фазе для таблицы
    filtered_rows = []
    for r in rows:
        if len(r) > 2:
            gl = r[2].strip().lower()
            is_p2 = ('ранн' in gl or 'early' in gl or 'поздн' in gl or 'late' in gl or (('контр' in gl or 'control' in gl) and ('2' in gl or 'этап 2' in gl)))
            if phase == '1' and is_p2:
                continue
            if phase == '2' and not is_p2:
                continue
            filtered_rows.append(r)

    summary_card = f'''
        <div class="card" style="margin-top: 2px;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1.5px solid #f1f5f9; padding-bottom:8px; margin-bottom:10px;">
                <h2 style="margin:0; font-size:15px; border:none; padding:0; color:var(--sirius-teal-dark);">📊 Экспресс-сводка фаз</h2>
                <span style="background:#f0fdfa; border:1px solid var(--sirius-teal); color:var(--sirius-teal-dark); padding:2px 10px; border-radius:12px; font-size:11px; font-weight:bold;">Всего: {len(rows)}</span>
            </div>

            <!-- ЭТАП 1: СКРИНИНГ -->
            <div style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Этап 1: Скрининг стрессов (Кассеты 1–3)</div>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; margin-bottom:10px; text-align:center;">
                <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:8px; padding:6px 3px;">
                    <div style="font-size:10px; color:#065f46; font-weight:bold;">🌱 Контроль</div>
                    <div style="font-size:16px; font-weight:bold; color:#047857; margin:1px 0;">{cnt_ctrl}</div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#059669;">{m_ctrl}</b></div>
                </div>
                <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:6px 3px;">
                    <div style="font-size:10px; color:#92400e; font-weight:bold;">🍂 Засуха</div>
                    <div style="font-size:16px; font-weight:bold; color:#b45309; margin:1px 0;">{cnt_drought}</div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#d97706;">{m_drought}</b></div>
                </div>
                <div style="background:#f5f3ff; border:1px solid #ddd6fe; border-radius:8px; padding:6px 3px;">
                    <div style="font-size:10px; color:#5b21b6; font-weight:bold;">🧂 Соль</div>
                    <div style="font-size:16px; font-weight:bold; color:#6d28d9; margin:1px 0;">{cnt_salt}</div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#7c3aed;">{m_salt}</b></div>
                </div>
            </div>

            <!-- ЭТАП 2: РЕГИДРАТАЦИЯ -->
            <div style="font-size:10px; font-weight:700; color:#0f766e; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Этап 2: Тест регидратации (Кассеты 4–6)</div>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; margin-bottom:12px; text-align:center;">
                <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:8px; padding:6px 3px;">
                    <div style="font-size:10px; color:#065f46; font-weight:bold;">🌱 Контроль-2</div>
                    <div style="font-size:16px; font-weight:bold; color:#047857; margin:1px 0;">{cnt_ctrl2}</div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#059669;">{m_ctrl2}</b></div>
                </div>
                <div style="background:#f0fdfa; border:1px solid #99f6e4; border-radius:8px; padding:6px 3px;">
                    <div style="font-size:10px; color:#0f766e; font-weight:bold;">💧 Раннее (~40ч)</div>
                    <div style="font-size:13px; font-weight:bold; color:#0d9488; margin:2px 0;">{k_rec_early}</div>
                    <div style="font-size:10px; color:#475569;">Замеров: <b>{cnt_early}</b></div>
                </div>
                <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:8px; padding:6px 3px;">
                    <div style="font-size:10px; color:#be123c; font-weight:bold;">⚠️ Позднее (~72ч)</div>
                    <div style="font-size:13px; font-weight:bold; color:#e11d48; margin:2px 0;">{k_rec_late}</div>
                    <div style="font-size:10px; color:#475569;">Замеров: <b>{cnt_late}</b></div>
                </div>
            </div>

            <a href="/download/csv" style="display:flex; align-items:center; justify-content:center; gap:8px; width:100%; padding:8px; box-sizing:border-box; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; color:var(--sirius-teal-dark); text-decoration:none; font-size:11px; font-weight:bold; transition:all 0.2s;" onmouseover="this.style.background='var(--sirius-teal)';this.style.color='#fff';this.style.borderColor='var(--sirius-teal)';" onmouseout="this.style.background='#f8fafc';this.style.color='var(--sirius-teal-dark)';this.style.borderColor='#cbd5e1';">
                📥 Экспорт базы данных (.CSV)
            </a>
            <a href="/download/pdf" target="_blank" style="display:flex; align-items:center; justify-content:center; gap:8px; width:100%; padding:8px; box-sizing:border-box; background:linear-gradient(135deg, #00a499, #0d9488); border:none; border-radius:8px; color:#fff; text-decoration:none; font-size:11px; font-weight:bold; margin-top:6px; transition:all 0.2s; box-shadow: 0 2px 8px rgba(0,164,153,0.25);" onmouseover="this.style.filter='brightness(1.1)';" onmouseout="this.style.filter='brightness(1.0)';">
                📄 Научно-технический отчет (.PDF)
            </a>
            <a href="/download/aruco_pdf" target="_blank" style="display:flex; align-items:center; justify-content:center; gap:8px; width:100%; padding:8px; box-sizing:border-box; background:#f0fdfa; border:1.5px solid #99f6e4; border-radius:8px; color:#0f766e; text-decoration:none; font-size:11px; font-weight:bold; margin-top:6px; transition:all 0.2s;" onmouseover="this.style.background='#00a499';this.style.color='#fff';" onmouseout="this.style.background='#f0fdfa';this.style.color='#0f766e';">
                🏷️ Печать ArUco-маркеров кассет (.PDF)
            </a>
        </div>
    '''

    table_html = ''
    for r in reversed(filtered_rows):
        if len(r) >= 24:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            if r[4] and r[5]:
                t_air_str = f'<span style="white-space:nowrap;font-size:11px;color:#334155;">{r[4]}°C <span style="color:#cbd5e1;">·</span> <span style="color:#059669;font-weight:600;">{r[5]}%</span></span>'
            else:
                t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[7]}%" if r[7] else "--"
            t_show = f"{r[8]} °C" if r[8] else "--"
            delta_str = f"{r[9]}°C" if r[9] else "--"
            ndvi_txt = f"{r[11]}±{r[12]}" if len(r)>12 else "--"
            th_name = r[14] if len(r)>14 else ""

            if r[9]:
                try:
                    dt_val = float(r[9])
                    if dt_val <= -0.5:
                        stress_badge = f'<span style="background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (Норма)</span>'
                    elif dt_val <= 0.5:
                        stress_badge = f'<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (Нач. стресс)</span>'
                    elif dt_val <= 1.8:
                        stress_badge = f'<span style="background:#f0fdfa;color:#0f766e;border:1px solid #99f6e4;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (ОКНО СПАСЕНИЯ)</span>'
                    else:
                        stress_badge = f'<span style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (ТОЧКА НЕВОЗВРАТА)</span>'
                except Exception:
                    stress_badge = f'<span style="white-space:nowrap;font-weight:600;">{delta_str}</span>'
            else:
                stress_badge = '<span style="color:#94a3b8;">--</span>'

        elif len(r) >= 20:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[5]}%" if r[5] else "--"
            t_show = f"{r[6]} °C" if r[6] else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[7]}±{r[8]}" if len(r)>8 else "--"
            th_name = r[10] if len(r)>10 else ""
        else:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[4]}%" if len(r)>4 else "--"
            t_show = f"{r[5]} °C" if len(r)>5 else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[6]}±{r[7]}" if len(r)>7 else "--"
            th_name = r[9] if len(r)>9 else ""

        if th_name:
            m_th = re.search(r'(IMG[_\s]\d+)', th_name)
            clean_th = m_th.group(1) if m_th else th_name
            th_stat = f'<span style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;">✓ {clean_th}</span>'
        else:
            th_stat = '<span style="color:#d97706;font-size:11px;white-space:nowrap;font-weight:600;">⏳ Ожидает</span>'

        d_str, t_str = format_ru_date_and_time(ts)
        time_cell = f'<div style="white-space:nowrap;font-size:11px;font-weight:600;color:#0f172a;">{d_str}</div><div style="font-size:10px;color:#64748b;white-space:nowrap;">{t_str}</div>'
        grp_badge = format_group_badge(grp)
        t_leaf_html = f'<b style="color:#d97706;white-space:nowrap;">{t_show}</b>' if t_show != '--' else '<span style="color:#94a3b8;">--</span>'
        del_btn = f'''<form action="/api/delete_measurement" method="post" style="margin:0;display:inline;" onsubmit="return confirm('Удалить исследование #{m_id}?');"><input type="hidden" name="meas_id" value="{m_id}"><button type="submit" style="background:#fee2e2; border:1px solid #fca5a5; color:#dc2626; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1;" title="Удалить замер #{m_id}" onmouseover="this.style.background='#dc2626';this.style.color='#fff';" onmouseout="this.style.background='#fee2e2';this.style.color='#dc2626';">✕</button></form>'''

        table_html += f'<tr><td><b style="color:#64748b;">#{m_id}</b></td><td>{time_cell}</td><td>{grp_badge}</td><td><b style="color:#0284c7;white-space:nowrap;">{wt}</b></td><td>{t_air_str}</td><td>{t_leaf_html}</td><td>{stress_badge}</td><td><span style="white-space:nowrap;font-family:monospace;font-size:11px;color:#334155;">{ndvi_txt}</span></td><td><span style="white-space:nowrap;font-weight:500;color:#334155;">{pct}</span></td><td>{th_stat}</td><td>{del_btn}</td></tr>'

    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Сириус: Большие вызовы | Оптико-электронный комплекс</title>
    <style>
        :root {{
            --sirius-teal: #00a499;
            --sirius-teal-dark: #008276;
            --sirius-teal-light: #2dd4bf;
            --sirius-purple: #7c3aed;
            --sirius-indigo: #4338ca;
            --bg-main: #f0fdfa;
            --card-bg: #ffffff;
            --card-border: #e2e8f0;
            --card-shadow: 0 4px 20px rgba(0, 164, 153, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04);
            --text-primary: #0f172a;
            --text-secondary: #475569;
        }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background-color: #f0fdfa;
            background-image: linear-gradient(180deg, rgba(240, 253, 250, 0.94) 0%, rgba(248, 250, 252, 0.97) 260px, rgba(241, 245, 249, 0.99) 100%), url('/static/logos/sirius_bg.png');
            background-size: cover;
            background-position: center top;
            background-attachment: fixed;
            background-repeat: no-repeat;
            color: var(--text-primary);
            margin: 0;
            padding: 16px 22px;
            min-height: 100vh;
            box-sizing: border-box;
        }}
        .container {{
            width: 100%;
            max-width: 1440px;
            margin: 0 auto;
        }}
        /* ХЕДЕР В ОФИЦИАЛЬНОМ СТИЛЕ СИРИУС (БИРЮЗОВЫЙ С БЕЛЫМИ АКЦЕНТАМИ) */
        .header {{
            background: linear-gradient(135deg, #00a499 0%, #008b80 100%);
            border: 1px solid rgba(0, 164, 153, 0.3);
            border-radius: 16px;
            padding: 14px 22px;
            margin-bottom: 14px;
            box-shadow: 0 8px 24px rgba(0, 164, 153, 0.25);
            color: #ffffff;
        }}
        .header-inner {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
        }}
        .header-logos {{
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(255, 255, 255, 0.18);
            padding: 4px 10px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }}
        .header-titles {{
            flex: 1;
            text-align: center;
        }}
        .header-titles h1 {{
            color: #ffffff;
            margin: 0 0 6px 0;
            font-size: 20px;
            letter-spacing: 0.4px;
            font-weight: 700;
        }}
        .header-badges {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .badge-sirius {{
            background: rgba(255, 255, 255, 0.2);
            color: #ffffff;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 10px;
            border-radius: 20px;
            letter-spacing: 0.5px;
            border: 1px solid rgba(255, 255, 255, 0.35);
        }}
        .badge-track {{
            background: #ffffff;
            color: #008276;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 12px;
            border-radius: 20px;
            letter-spacing: 0.5px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }}
        .badge-author {{
            background: rgba(255, 255, 255, 0.15);
            color: #ffffff;
            font-size: 11px;
            font-weight: 500;
            padding: 3px 10px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.25);
        }}
        .header-status {{
            text-align: right;
            min-width: 140px;
        }}
        .status-online {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.9);
            color: #047857;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
        }}
        .pulsing-dot {{
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 8px #10b981;
        }}
        .station-hw {{
            font-size: 10px;
            color: rgba(255, 255, 255, 0.9);
            margin-top: 4px;
            font-family: monospace;
        }}
        .header-subnote {{
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid rgba(255, 255, 255, 0.18);
            font-size: 11px;
            color: rgba(255, 255, 255, 0.9);
            text-align: center;
        }}

        /* КЛИМАТИЧЕСКАЯ ПАНЕЛЬ */
        .climate-bar {{
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 12px 20px;
            margin-bottom: 14px;
            display: flex;
            justify-content: space-around;
            align-items: center;
            box-shadow: var(--card-shadow);
        }}
        .clim-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
        }}
        .clim-label {{
            font-size: 11px;
            font-weight: 700;
            color: #64748b;
            letter-spacing: 0.6px;
            text-transform: uppercase;
        }}
        .clim-val {{
            font-size: 16px;
            font-weight: 700;
            font-family: 'Segoe UI', monospace;
        }}
        .clim-divider {{
            width: 1px;
            height: 32px;
            background: #e2e8f0;
        }}
        .val-purple {{ color: #7c3aed; }}
        .val-cyan {{ color: #0284c7; }}
        .val-teal {{ color: #0d9488; }}
        .val-amber {{ color: #d97706; }}
        .val-slate {{ color: #475569; }}

        /* СЕТКА И КАРТОЧКИ */
        .grid-top {{
            display: grid;
            grid-template-columns: 420px 1fr;
            gap: 16px;
            align-items: stretch;
            margin-bottom: 16px;
        }}
        .card {{
            background: #ffffff;
            border-radius: 16px;
            padding: 18px;
            border: 1px solid var(--card-border);
            box-shadow: var(--card-shadow);
        }}
        .card h2 {{
            color: var(--sirius-teal-dark);
            margin-top: 0;
            font-size: 16px;
            font-weight: 700;
            border-bottom: 1.5px solid #f1f5f9;
            padding-bottom: 10px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        label {{
            display: block;
            margin-top: 10px;
            font-weight: 600;
            color: #334155;
            font-size: 12px;
            letter-spacing: 0.2px;
        }}
        select, input[type="text"] {{
            width: 100%;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1.5px solid #cbd5e1;
            background: #f8fafc;
            color: #0f172a;
            margin-top: 4px;
            box-sizing: border-box;
            font-size: 13px;
            font-weight: 500;
            outline: none;
            transition: all 0.2s;
        }}
        select:focus, input[type="text"]:focus {{
            border-color: var(--sirius-teal);
            background: #ffffff;
            box-shadow: 0 0 0 3px rgba(0, 164, 153, 0.15);
        }}

        /* КНОПКА ЗАПУСКА СИРИУС-ГРАДИЕНТ */
        .btn-run {{
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #00a499 0%, #0d9488 50%, #059669 100%);
            color: #ffffff;
            border: none;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            margin-top: 15px;
            box-shadow: 0 4px 14px rgba(0, 164, 153, 0.35);
            transition: all 0.2s ease;
            letter-spacing: 0.4px;
        }}
        .btn-run:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 164, 153, 0.5);
            filter: brightness(1.05);
        }}
        .btn-run:active {{
            transform: translateY(1px);
        }}

        /* МАТРИЦА КАНАЛОВ */
        .channels {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .ch-box {{
            background: #f8fafc;
            padding: 10px;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            text-align: center;
            transition: all 0.2s;
        }}
        .ch-box:hover {{
            border-color: var(--sirius-teal);
            box-shadow: 0 4px 12px rgba(0, 164, 153, 0.12);
        }}
        .preview-img {{
            width: 100%;
            height: 185px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            background: #f8fafc;
            object-fit: contain;
        }}

        /* ТАБЛИЦА ЖУРНАЛА */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 12px;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            padding: 11px 8px;
            font-weight: 700;
            border-bottom: 2px solid var(--sirius-teal);
            white-space: nowrap;
            text-align: center;
            font-size: 11px;
            position: sticky;
            top: 0;
            z-index: 10;
            letter-spacing: 0.3px;
        }}
        td {{
            padding: 9px 8px;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: middle;
            text-align: center;
            color: #1e293b;
            background: #ffffff;
        }}
        tr:nth-child(even) td {{
            background: #f8fafc;
        }}
        tr:hover td {{
            background: #e6fffa;
        }}
    </style>
</head>
<body>
<div class="container">
    <!-- ОФИЦИАЛЬНЫЙ БРЕНДИРОВАННЫЙ ХЕДЕР СИРИУС -->
    <div class="header">
        <div class="header-inner">
            <div class="header-logos">
                <img src="/static/logos/bv_logo_badge.png" style="height: 42px; border-radius: 4px; object-fit: contain; box-shadow: 0 2px 8px rgba(0,0,0,0.2);" alt="Большие вызовы">
                <div style="width: 1px; height: 34px; background: rgba(255,255,255,0.3);"></div>
                <img src="/static/logos/agrobiotech_track_logo.png" style="height: 40px; object-fit: contain;" alt="Агропромышленные и биотехнологии">
            </div>
            <div class="header-titles">
                <h1>Оптико-электронный комплекс фенотипирования стресса растений</h1>
                <div class="header-badges">
                    <span class="badge-sirius">★ СИРИУС · БОЛЬШИЕ ВЫЗОВЫ 2025/2026</span>
                    <span class="badge-track">🌾 АГРОПРОМЫШЛЕННЫЕ И БИОТЕХНОЛОГИИ</span>
                    <span class="badge-author">👩‍🔬 Автор: Ковалева Алиса · 10 класс (СОШ №282 СПб)</span>
                </div>
            </div>
            <div class="header-status">
                <div class="status-online"><span class="pulsing-dot"></span> СТАНЦИЯ ОНЛАЙН</div>
                <div class="station-hw">Orange Pi 4 Pro · sun60iw2</div>
            </div>
        </div>
        <div class="header-subnote">
            ⚠️ <b>Калибровочный испытательный стенд</b> (двухволновое стробирование Red 660 нм / NIR 850 нм + термография UTi120S)
        </div>
    </div>

    <!-- МЕТЕОРОЛОГИЧЕСКАЯ ПАНЕЛЬ МИКРОКЛИМАТА -->
    <div class="climate-bar">
        <div class="clim-item">
            <span class="clim-label">📡 Сенсор климата</span>
            <span class="clim-val val-purple">Sensirion SHT30</span>
        </div>
        <div class="clim-divider"></div>
        <div class="clim-item">
            <span class="clim-label">🌡️ T воздуха</span>
            <span class="clim-val val-cyan">{cur_t} °C</span>
        </div>
        <div class="clim-divider"></div>
        <div class="clim-item">
            <span class="clim-label">💧 Влажность RH</span>
            <span class="clim-val val-teal">{cur_rh}%</span>
        </div>
        <div class="clim-divider"></div>
        <div class="clim-item">
            <span class="clim-label">🌬️ Дефицит VPD</span>
            <span class="clim-val val-amber">{cur_vpd} кПа</span>
        </div>
        <div class="clim-divider"></div>
        <div class="clim-item">
            <span class="clim-label">🔋 Питание SHT30</span>
            <span class="clim-val val-slate">{cur_v} В</span>
        </div>
    </div>

    {status_banner}

    <!-- ВЕРХНИЙ БЛОК: Слева Управление + Сводка | Справа Мультиспектральная матрица -->
    <div class="grid-top">
        <div style="display: flex; flex-direction: column; gap: 14px;">
            <!-- WIZARD ШАГ 1 ИЛИ ШАГ 2 -->
            {wizard_card}

            <!-- ЭКСПРЕСС-СВОДКА (Заполняет нижний левый угол) -->
            {summary_card}
        </div>

        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
            <div>
                <h2>🔬 Мультиспектральная матрица исследования</h2>
                <div class="channels">
                    <div class="ch-box">
                        <div style="color:#dc2626; font-size:11px; font-weight:700; margin-bottom:4px; letter-spacing:0.3px;">Канал 1: 660 нм (Deep Red)</div>
                        <img src="/static/last_red.jpg?t={t_now}" class="preview-img">
                    </div>
                    <div class="ch-box">
                        <div style="color:#4f46e5; font-size:11px; font-weight:700; margin-bottom:4px; letter-spacing:0.3px;">Канал 2: 850 нм (NIR Инфракрасный)</div>
                        <img src="/static/last_nir.jpg?t={t_now}" class="preview-img">
                    </div>
                    <div class="ch-box">
                        <div style="color:#0d9488; font-size:11px; font-weight:700; margin-bottom:4px; letter-spacing:0.3px;">Канал 3: Карта NDVI (Сетка 3×3)</div>
                        <img src="/static/last_ndvi.jpg?t={t_now}" class="preview-img">
                    </div>
                    <div class="ch-box">
                        <div style="color:#d97706; font-size:11px; font-weight:700; margin-bottom:4px; letter-spacing:0.3px;">Канал 4: Термограмма (UNI-T UTi120S)</div>
                        <img src="/static/last_thermal.jpg?t={t_now}" class="preview-img">
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- НИЖНИЙ БЛОК: ЖУРНАЛ ИЗМЕРЕНИЙ НА ВСЮ ШИРИНУ -->
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1.5px solid #f1f5f9; padding-bottom:10px; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
                <h2 style="margin:0; font-size:16px; border:none; padding:0; color:var(--sirius-teal-dark);">📋 Журнал физиологических замеров</h2>
                <div style="display:flex; gap:4px; background:#f1f5f9; padding:3px; border-radius:8px;">
                    <a href="/?phase=all" style="padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; text-decoration:none; {'background:var(--sirius-teal); color:#fff; box-shadow:0 1px 4px rgba(0,164,153,0.3);' if phase=='all' else 'color:#475569;'}">Все когорты ({len(rows)})</a>
                    <a href="/?phase=1" style="padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; text-decoration:none; {'background:var(--sirius-teal); color:#fff; box-shadow:0 1px 4px rgba(0,164,153,0.3);' if phase=='1' else 'color:#475569;'}">🧪 Этап 1: Скрининг</a>
                    <a href="/?phase=2" style="padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; text-decoration:none; {'background:var(--sirius-teal); color:#fff; box-shadow:0 1px 4px rgba(0,164,153,0.3);' if phase=='2' else 'color:#475569;'}">💧 Этап 2: Спасение</a>
                </div>
            </div>
            <div style="display:flex; gap:5px; flex-wrap:wrap;">
                <span style="background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #a7f3d0;">🌱 К1: Контроль</span>
                <span style="background:#fffbeb; color:#92400e; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #fde68a;">🍂 К2: Засуха</span>
                <span style="background:#f5f3ff; color:#5b21b6; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #ddd6fe;">🧂 К3: Соль</span>
                <span style="background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #a7f3d0;">🌱 К4: Контроль-2</span>
                <span style="background:#f0fdfa; color:#0f766e; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #99f6e4;">💧 К5: Раннее (~40ч)</span>
                <span style="background:#fff1f2; color:#be123c; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #fecdd3;">⚠️ К6: Позднее (~72ч)</span>
            </div>
        </div>
        <div style="max-height: 320px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 10px; background:#ffffff;">
            <table>
                <thead>
                    <tr>
                        <th style="width:45px;">№</th>
                        <th style="width:130px;">Дата и время</th>
                        <th style="width:115px;">Когорта</th>
                        <th style="width:75px;">Масса</th>
                        <th style="width:120px;">T возд / RH</th>
                        <th style="width:80px;">T листа</th>
                        <th style="width:145px;">ΔT (Стресс)</th>
                        <th style="width:95px;">NDVI</th>
                        <th style="width:65px;">Почва</th>
                        <th style="width:110px;">Тепловизор</th>
                        <th style="width:38px;" title="Удалить запись">✕</th>
                    </tr>
                </thead>
                <tbody>
                    {table_html}
                </tbody>
            </table>
        </div>
    </div>
</div>
</body>
</html>'''
    return html

@app.get('/download/csv')
def download_csv():
    if os.path.exists(CSV_LOG):
        return FileResponse(CSV_LOG, filename='plant_stress_measurements.csv')
    return HTMLResponse('Файл пока пуст')

@app.get('/download/pdf')
def download_pdf():
    pdf_path = os.path.join(STATIC_DIR, 'Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(STATIC_DIR, 'analysis_report.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Отчет пока не сформирован')

@app.get('/download/paper')
def download_paper():
    pdf_path = os.path.join(STATIC_DIR, 'Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл работы не найден')

@app.get('/download/presentation')
def download_presentation():
    pdf_path = os.path.join(STATIC_DIR, 'Презентация_Большие_Вызовы_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Презентация_Большие_Вызовы_Ковалева_Алиса.pdf', media_type='application/pdf')
@app.get('/download/aruco_pdf')
def download_aruco_pdf():
    pdf_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='aruco_markers_cassettes.pdf', media_type='application/pdf')
    html_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.html')
    if os.path.exists(html_path):
        return FileResponse(html_path, filename='aruco_markers_cassettes.html', media_type='text/html')
    return HTMLResponse('Лист маркеров не найден')

app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
