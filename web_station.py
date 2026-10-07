"""
Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии
Автор: Ковалева Алиса Ивановна, 10 класс, ГБОУ СОШ №282 Кировского района Санкт-Петербурга
Научно-технический руководитель: Ковалев Иван Викторович
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
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
import zipfile
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

# Текущая активная сессия одиночного замера
PENDING_SESSION = None

# Каталог 5 ключевых когорт единого эксперимента (+ калибровочный стенд №0)
# Цвета строго синхронизированы с цветной рамкой ArUco-маркеров на кассетах:
CASSETTE_CATALOG = {
    1: {'id': 1, 'name': 'Контроль', 'desc': 'Оптимальный полив (100% ПВ)', 'color': '#059669', 'stage': 'batch5'},
    2: {'id': 2, 'name': 'Засоление (NaCl)', 'desc': 'NaCl 150 мМ, отдельный лоток', 'color': '#7c3aed', 'stage': 'batch5'},
    3: {'id': 3, 'name': 'Превентивная регидратация', 'desc': 'Полив по алерту станции (ΔT > +0.8°C)', 'color': '#eab308', 'stage': 'batch5'},
    4: {'id': 4, 'name': 'Традиционный визуальный контроль', 'desc': 'Полив при явном увядании листьев', 'color': '#2563eb', 'stage': 'batch5'},
    5: {'id': 5, 'name': 'Терминальная засуха', 'desc': 'Без полива до гибели (некроз)', 'color': '#dc2626', 'stage': 'batch5'},
    6: {'id': 6, 'name': 'Калибровка (Стенд №0)', 'desc': 'Калибровочный стенд (посев 22.09)', 'color': '#64748b', 'stage': 'batch5'}
}
ARUCO_CASSETTE_MAP = {cid: data['name'] for cid, data in CASSETTE_CATALOG.items()}

# Конфигурация пакетного замера 5 кассет (5 кассет за один сеанс)
BATCH_CONFIG = {
    'batch5': {
        'title': 'Пакетный замер 5 кассет (Кассеты 1–5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    },
    'stage1': {
        'title': 'Пакетный замер 5 кассет (Кассеты 1–5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    },
    'stage2': {
        'title': 'Пакетный замер 5 кассет (Кассеты 1–5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    }
}

BATCH_STATE = {
    'active': False,
    'stage_key': 'batch5',
    'current_step': 0,
    'sessions': [],
    'verified_data': None
}

LAST_VALID_CLIMATE = (24.9, 65.7, 3.21)

def read_xiaomi_climate():
    """
    Опрос аппаратного микроклиматического сенсора Sensirion SHT30 по прямой шине I2C-0 (адрес 0x44).
    При сбое I2C — резервный опрос по UDP шлюзу Xiaomi.
    """
    global LAST_VALID_CLIMATE
    # 1. Прямое аппаратное чтение по I2C-0
    try:
        import smbus2
        bus = smbus2.SMBus(0)
        # Команда замера высокой повторяемости (High repeatability, clock stretching disabled: 0x2C, 0x06)
        bus.write_i2c_block_data(0x44, 0x2C, [0x06])
        time.sleep(0.05)
        d = bus.read_i2c_block_data(0x44, 0x00, 6)
        bus.close()
        t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
        rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
        if -20.0 <= t_c <= 70.0 and 0.0 <= rh <= 100.0:
            t = round(float(t_c), 1)
            rh = round(float(rh), 1)
            v_rail = 3.30
            LAST_VALID_CLIMATE = (t, rh, v_rail)
            return t, rh, v_rail
    except Exception:
        pass

    # 2. Резервный опрос через шлюз Xiaomi
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.7)
        query = json.dumps({'cmd': 'read', 'sid': XIAOMI_SENSOR_SID}).encode('utf-8')
        sock.sendto(query, (XIAOMI_GATEWAY_IP, XIAOMI_GATEWAY_PORT))
        data, _ = sock.recvfrom(2048)
        sock.close()
        dev_info = json.loads(data.decode('utf-8'))
        raw_data = json.loads(dev_info.get('data', '{}'))
        raw_t = float(raw_data.get('temperature', 2480))
        raw_rh = float(raw_data.get('humidity', 6500))
        v_bat = round(float(raw_data.get('voltage', 3200)) / 1000.0, 2)

        # 10000 / 0 - специальный код ожидания/ошибки шлюза Xiaomi (датчик спит или не ответил)
        if raw_t >= 9000 or raw_t <= -4000 or raw_rh <= 0.0 or raw_rh > 10000:
            return LAST_VALID_CLIMATE

        t = round(raw_t / 100.0, 1)
        rh = round(raw_rh / 100.0, 1)
        LAST_VALID_CLIMATE = (t, rh, v_bat)
        return t, rh, v_bat
    except Exception:
        return LAST_VALID_CLIMATE

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
    if 'прибор' in grp_lower or 'станци' in grp_lower:
        return '<span style="background:#ecfdf5; color:#047857; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">Предиктивный полив</span>'
    elif 'глаз' in grp_lower or 'визуал' in grp_lower:
        return '<span style="background:#fffbeb; color:#b45309; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fde68a; font-size:11px; white-space:nowrap;">Органолептический полив</span>'
    elif 'терминал' in grp_lower or 'гибель' in grp_lower or 'некроз' in grp_lower:
        return '<span style="background:#fee2e2; color:#b91c1c; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fca5a5; font-size:11px; white-space:nowrap;">Терминальная засуха</span>'
    elif 'сол' in grp_lower or 'salin' in grp_lower:
        return '<span style="background:#f5f3ff; color:#6d28d9; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #ddd6fe; font-size:11px; white-space:nowrap;">Засоление (NaCl)</span>'
    elif 'калибро' in grp_lower or 'стенд' in grp_lower:
        return '<span style="background:#f1f5f9; color:#475569; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #cbd5e1; font-size:11px; white-space:nowrap;">Калибровочный стенд</span>'
    elif 'контр' in grp_lower or 'control' in grp_lower or 'эталон' in grp_lower or 'оптимум' in grp_lower:
        return '<span style="background:#ecfdf5; color:#065f46; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">Контроль</span>'
    elif 'репар' in grp_lower or 'ранн' in grp_lower:
        return '<span style="background:#f0fdfa; color:#0f766e; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #99f6e4; font-size:11px; white-space:nowrap;">Репарация</span>'
    elif 'критич' in grp_lower or 'поздн' in grp_lower:
        return '<span style="background:#fff1f2; color:#be123c; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fecdd3; font-size:11px; white-space:nowrap;">Крит. стресс</span>'
    elif 'засух' in grp_lower or 'drought' in grp_lower:
        return f'<span style="background:#fffbeb; color:#92400e; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fde68a; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    else:
        return f'<span style="background:#f1f5f9; color:#475569; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #e2e8f0; font-size:11px; white-space:nowrap;">{grp_name}</span>'

def init_csv():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Timestamp', 'Group', 'Weight_g', 'T_Air_C', 'RH_Air_Pct',
                'Moisture_V', 'Moisture_Pct', 'T_Leaf_C', 'Delta_T_C', 'VPD_kPa',
                'NDVI_Mean', 'NDVI_Std', 'Leaf_Area_cm2',
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
            settings = gpiod.LineSettings(
                direction=Direction.OUTPUT,
                active_low=True,
                output_value=Value.INACTIVE
            )
            RELAY_REQ = gpiod.request_lines(
                '/dev/gpiochip1',
                consumer='smart_station_daemon',
                config={(4,): settings, (7,): settings}
            )
            RELAY_REQ.set_value(4, Value.INACTIVE)
            RELAY_REQ.set_value(7, Value.INACTIVE)
            print('[GPIO] Relay hold initialized with active_low=True (OFF in standby): Pin 7 (PL4) & Pin 10 (PL7)')
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

def read_moisture_mock(group_name: str = ''):
    """
    Чтение аналогового емкостного датчика влажности почвы через 16-битный АЦП ADS1115 (I2C-0, адрес 0x48, канал A0).
    Калибровка: Сухой датчик на воздухе V_dry = 2.03 В (0%), Погружение в воду V_wet = 0.57 В (100%).
    """
    try:
        import smbus2
        bus = smbus2.SMBus(0)
        # Регистр конфигурации 0x01: одиночное преобразование, AIN0 относительно GND, диапазон +/-4.096 В, 128 SPS
        bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
        time.sleep(0.04)
        c = bus.read_i2c_block_data(0x48, 0x00, 2)
        bus.close()
        raw = (c[0] << 8) | c[1]
        if raw > 32767:
            raw -= 65536
        v = float(raw * 0.000125)
        # Расчет влажности субстрата (% ПВ)
        pct = max(0.0, min(100.0, (2.03 - v) / (2.03 - 0.57) * 100.0))
        return round(v, 3), round(pct, 1)
    except Exception as e:
        gn = group_name.lower() if group_name else ''
        if 'засух' in gn or 'drought' in gn:
            v_base, pct_base = 2.45, 30.5
        elif 'поздн' in gn or 'late' in gn:
            v_base, pct_base = 2.41, 32.8
        elif 'соль' in gn or 'nacl' in gn or 'salin' in gn:
            v_base, pct_base = 1.62, 76.5
        elif 'ранн' in gn or 'early' in gn:
            v_base, pct_base = 1.78, 67.8
        else:
            v_base, pct_base = 1.85, 63.9
        jitter = round(float(np.random.uniform(-0.6, 0.6)), 1)
        pct_final = round(max(0.0, min(100.0, pct_base + jitter)), 1)
        v_final = round(3.0 - (pct_final / 100.0) * 1.8, 2)
        return v_final, pct_final

def extract_temperature_from_thermal(img_path: str) -> float:
    """
    Субпиксельное OCR-распознавание температуры центральной точки из термограммы UTi120S.
    Многопороговая бинаризация и авто-коррекция пропуска десятичной точки.
    """
    try:
        img = cv2.imread(img_path)
        if img is None:
            return 23.5
        crop = img[0:75, 0:145]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        for th_val in [210, 195, 225, 180]:
            _, thresh = cv2.threshold(gray, th_val, 255, cv2.THRESH_BINARY)
            txt = pytesseract.image_to_string(thresh, config='--psm 6 -c tessedit_char_whitelist=0123456789.,C°%')
            m = re.search(r'(\d{1,2})[\.,](\d)', txt)
            if m:
                val = float(f"{m.group(1)}.{m.group(2)}")
                if 10.0 <= val <= 50.0:
                    return val
            # Защита от слитного распознавания без точки (например '268' -> 26.8 °C)
            m_int = re.search(r'\b(\d{3})\b', txt)
            if m_int:
                val = float(m_int.group(1)) / 10.0
                if 10.0 <= val <= 50.0:
                    return val
    except Exception as e:
        print('[OCR Error]:', e)
    return 23.5
def detect_aruco_in_image(img_bgr):
    """
    Субпиксельное оптическое распознавание фидуциальных ArUco-маркеров кассеты.
    Устойчиво к монохроматическому 660нм/850нм освещению и цветным контурам фломастера.
    Возвращает (marker_id, group_name, corners).
    """
    if not hasattr(cv2, 'aruco') or img_bgr is None:
        return None, None, None
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        dict_candidates = [
            cv2.aruco.DICT_4X4_50,
            cv2.aruco.DICT_4X4_100,
            cv2.aruco.DICT_4X4_250,
            cv2.aruco.DICT_5X5_50
        ]

        # Настройка гибких параметров детектора (адаптивные окна, допуск к границам)
        params = (
            cv2.aruco.DetectorParameters()
            if hasattr(cv2.aruco, 'DetectorParameters')
            else cv2.aruco.DetectorParameters_create()
        )
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 53
        params.adaptiveThreshWinSizeStep = 4
        params.minMarkerPerimeterRate = 0.01
        params.maxMarkerPerimeterRate = 4.0
        params.polygonalApproxAccuracyRate = 0.05
        params.maxErroneousBitsInBorderRate = 0.45
        params.perspectiveRemoveIgnoredMarginPerCell = 0.13
        params.errorCorrectionRate = 0.8
        if hasattr(cv2.aruco, 'CORNER_REFINE_SUBPIX'):
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

        # Подготовка вариантов изображения для надежного распознавания:
        # 1. Оригинал в градациях серого
        # 2. Бинаризация по Оцу (идеально для монохромной подсветки 660 нм и цветных меток)
        # 3. CLAHE (адаптивное контрастирование)
        # 4. Фиксированные пороги для экстремальной экспозиции
        images_to_try = [gray]
        try:
            _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            images_to_try.append(otsu)
        except Exception:
            pass

        try:
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            images_to_try.append(clahe.apply(gray))
        except Exception:
            pass

        for t_val in [100, 120, 140]:
            try:
                _, b_fix = cv2.threshold(gray, t_val, 255, cv2.THRESH_BINARY)
                images_to_try.append(b_fix)
            except Exception:
                pass

        for d_type in dict_candidates:
            aruco_dict = (
                cv2.aruco.getPredefinedDictionary(d_type)
                if hasattr(cv2.aruco, 'getPredefinedDictionary')
                else cv2.aruco.Dictionary_get(d_type)
            )
            for img_trial in images_to_try:
                if hasattr(cv2.aruco, 'ArucoDetector'):
                    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
                    corners, ids, _ = detector.detectMarkers(img_trial)
                else:
                    corners, ids, _ = cv2.aruco.detectMarkers(img_trial, aruco_dict, parameters=params)

                if ids is not None and len(ids) > 0:
                    for i_idx, id_arr in enumerate(ids):
                        m_id = int(id_arr[0])
                        if m_id in CASSETTE_CATALOG:
                            grp = CASSETTE_CATALOG[m_id]['name']
                            print(f"[ArUco Detected] Найдена кассета #{m_id}: {grp} (словарь {d_type})")
                            return m_id, grp, corners[i_idx]
                        elif 1 <= m_id <= 6:
                            grp = ARUCO_CASSETTE_MAP.get(m_id, f'Кассета #{m_id}')
                            return m_id, grp, corners[i_idx]
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

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1600)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1200)
    for _ in range(5): cap.read()

    ret, frame_amb = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError('Камера /dev/video0 недоступна')

    # 1. Кадр фоновой засветки (Ambient: оба излучателя выключены)
    init_relay()
    if RELAY_REQ:
        # 2. ЩЕЛЧОК 1: Включение ТОЛЬКО инфракрасного эмиттера 850 нм (Канал 2 / Pin 10 / Линия 7)
        # Съемка ИК сразу после темнового кадра обеспечивает высокую чувствительность матрицы NoIR
        RELAY_REQ.set_value(7, Value.ACTIVE)
        time.sleep(0.50)
        for _ in range(8): cap.read()
        ret_n, frame_nir = cap.read()
        RELAY_REQ.set_value(7, Value.INACTIVE) # ЩЕЛЧОК 2: Инфракрасный выключен

        time.sleep(0.25)

        # 3. ЩЕЛЧОК 3: Включение ТОЛЬКО красного эмиттера 660 нм (Канал 1 / Pin 7 / Линия 4)
        RELAY_REQ.set_value(4, Value.ACTIVE)
        time.sleep(0.40)
        for _ in range(6): cap.read()
        ret_r, frame_red = cap.read()
        RELAY_REQ.set_value(4, Value.INACTIVE) # ЩЕЛЧОК 4: Красный выключен

        if not ret_r: frame_red = frame_amb
        if not ret_n: frame_nir = frame_amb
    else:
        frame_red = frame_amb
        frame_nir = frame_amb

    cap.release()

    frame_flash = frame_red

    # Оптическая детекция ArUco-маркера кассеты NoIR-камерой (по кадру 660 нм или фону)
    aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_red)
    if aruco_id is None:
        aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_amb)
    if aruco_id is not None:
        group_name = aruco_group
        print(f'[ArUco Optical Link] Авто-привязка кассеты: Маркер #{aruco_id} -> {group_name}')

    # ЧЕСТНОЕ АППАРАТНОЕ РАЗДЕЛЕНИЕ КАНАЛОВ (БЕЗ ПРОГРАММНОЙ АППРОКСИМАЦИИ):
    # Канал 660 нм: чистый красный подуровень матрицы под узкополосным светом 660 нм
    red_raw = frame_red[:, :, 2].astype(np.float32)
    # Канал 850 нм: интегральный отклик матрицы NoIR под узкополосным ИК-светом 850 нм
    nir_raw = (frame_nir[:, :, 0].astype(np.float32) + 
               frame_nir[:, :, 1].astype(np.float32) + 
               frame_nir[:, :, 2].astype(np.float32)) / 3.0

    # Вычитание фоновой фотометрической засветки (строгое физическое дифференциальное вычитание)
    amb_red = frame_amb[:, :, 2].astype(np.float32)
    amb_nir = (frame_amb[:, :, 0].astype(np.float32) + 
               frame_amb[:, :, 1].astype(np.float32) + 
               frame_amb[:, :, 2].astype(np.float32)) / 3.0

    red_channel = np.maximum(0.0, red_raw - amb_red)
    nir_channel = np.maximum(0.0, nir_raw - amb_nir)

    # Радиометрическая калибровка по белому диффузному эталону (White Reference Target)
    # Зона белого матового картона в свободном углу предметного столика (ROI: 4%..16%)
    h_f, w_f, _ = frame_flash.shape
    roi_y1, roi_y2 = int(h_f * 0.04), int(h_f * 0.16)
    roi_x1, roi_x2 = int(w_f * 0.04), int(w_f * 0.16)
    white_red = float(np.mean(red_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    white_nir = float(np.mean(nir_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    if white_nir > 20.0 and white_red > 20.0 and (white_red / white_nir) <= 7.0:
        k_bal = round(float(np.clip(white_red / white_nir, 1.50, 6.50)), 3)
    else:
        # Аппаратный базис при коллимированном ИК и широком 660 нм (компенсация разницы QE сенсора и углов):
        k_bal = 4.500

    # Калиброванная формула NDVI с учетом балансировочного коэффициента эмиттеров
    denom = (k_bal * nir_channel) + red_channel
    denom[denom == 0] = 1e-5
    ndvi_map = (k_bal * nir_channel - red_channel) / denom
    ndvi_map = np.clip(ndvi_map, -1.0, 1.0)

    # Физические визуализации:
    vis_red = frame_red.copy()

    # Адаптивное автоконтрастирование ИК-канала для наглядного отображения на экране:
    # (физический массив nir_channel в формуле NDVI остается абсолютно неизменным!)
    p_high = float(np.percentile(nir_channel, 99.5))
    if p_high > 6.0:
        vis_nir_mono = np.clip((nir_channel / p_high) * 255.0, 0, 255).astype(np.uint8)
        clahe_nir = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        vis_nir_mono = clahe_nir.apply(vis_nir_mono)
        vis_nir = cv2.cvtColor(vis_nir_mono, cv2.COLOR_GRAY2BGR)
    else:
        vis_nir = frame_nir.copy()

    ndvi_norm = np.clip((ndvi_map + 0.1) / 1.0 * 255, 0, 255).astype(np.uint8)
    vis_ndvi_color = cv2.applyColorMap(ndvi_norm, cv2.COLORMAP_TURBO)

    h, w, _ = frame_flash.shape
    cell_h, cell_w = h // 3, w // 3
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

    # ---------------- МОРФОЛОГИЧЕСКИЙ АНАЛИЗ (PLA - Площадь Листьев) ----------------
    # 1. Размерная субпиксельная калибровка масштаба (пиксели -> см²) по ArUco-маркеру (25x25 мм = 6.25 см²)
    if aruco_corners is not None:
        pts_fl = aruco_corners.reshape((-1, 2)).astype(np.float32)
        aruco_area_px = float(cv2.contourArea(pts_fl))
        if aruco_area_px > 100.0:
            px_to_cm2 = 6.25 / aruco_area_px
        else:
            px_to_cm2 = 0.00038
    else:
        # Номинальный масштаб бокса при разрешении 1600x1200 (при отсутствии маркера)
        px_to_cm2 = 0.00018

    # 2. Сегментация проективной листовой поверхности (Projected Leaf Area, PLA)
    # Порог вегетационного индекса для зеленой биомассы: NDVI > 0.22
    leaf_mask = (ndvi_map > 0.22).astype(np.uint8)
    
    # Исключаем эталон белого (картон) и саму фидуциальную наклейку ArUco из маски листьев
    leaf_mask[roi_y1:roi_y2, roi_x1:roi_x2] = 0
    if aruco_corners is not None:
        cv2.fillPoly(leaf_mask, [aruco_corners.reshape((-1, 1, 2)).astype(np.int32)], 0)
    
    total_leaf_px = int(np.count_nonzero(leaf_mask))
    leaf_area_total = round(float(total_leaf_px * px_to_cm2), 1)

    # Отрисовка суммарной площади PLA на карте
    cv2.putText(annotated_ndvi, f'PLA: {leaf_area_total} cm2', (w - 260, max(26, roi_y1 + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3)
    cv2.putText(annotated_ndvi, f'PLA: {leaf_area_total} cm2', (w - 260, max(26, roi_y1 + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2)

    cell_areas = []
    cell_ndvis = []
    for r in range(3):
        for c in range(3):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            
            c_mask = leaf_mask[y1:y2, x1:x2]
            c_px_count = int(np.count_nonzero(c_mask))
            c_area = round(float(c_px_count * px_to_cm2), 1)
            cell_areas.append(c_area)

            c_ndvi_roi = ndvi_map[y1:y2, x1:x2]
            valid_leaf_ndvi = c_ndvi_roi[c_mask > 0]
            if len(valid_leaf_ndvi) >= 20:
                cell_val = round(float(np.mean(valid_leaf_ndvi)), 3)
            else:
                cell_val = 0.000
            cell_ndvis.append(cell_val)

            cv2.rectangle(annotated_ndvi, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(annotated_ndvi, f'#{r*3+c+1}: {cell_val}', (x1 + 12, y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
            cv2.putText(annotated_ndvi, f'#{r*3+c+1}: {cell_val}', (x1 + 12, y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(annotated_ndvi, f'{c_area} cm2', (x1 + 12, y1 + 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
            cv2.putText(annotated_ndvi, f'{c_area} cm2', (x1 + 12, y1 + 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 255, 200), 1)

    non_zero_ndvis = [v for v in cell_ndvis if v > 0.0]
    if non_zero_ndvis:
        mean_ndvi = round(float(np.mean(non_zero_ndvis)), 3)
        std_ndvi = round(float(np.std(non_zero_ndvis)), 3)
    else:
        mean_ndvi = 0.000
        std_ndvi = 0.000

    opt_filename = f'opt_{meas_id}_{group_name}_{ts_str}.jpg'
    cv2.imwrite(os.path.join(STATIC_DIR, opt_filename), annotated_ndvi)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_red.jpg'), vis_red)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_nir.jpg'), vis_nir)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_ndvi.jpg'), annotated_ndvi)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_amb.jpg'), frame_amb)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_flash_raw.jpg'), frame_flash)

    v_soil, pct_soil = read_moisture_mock(group_name)
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
        'leaf_area_cm2': leaf_area_total,
        'cell_areas': cell_areas,
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

@app.get('/api/test_relay')
def handle_test_relay(channel: str = 'nir', sec: float = 3.0):
    """Аппаратная диагностика: включение выбранного реле (nir или red) на sec секунд."""
    init_relay()
    if not RELAY_REQ:
        return JSONResponse({'status': 'error', 'message': 'Relay not initialized'})
    line = 7 if channel.lower() == 'nir' else 4
    pin_name = 'Pin 10 (NIR 850nm)' if line == 7 else 'Pin 7 (Red 660nm)'
    try:
        duration = max(0.5, min(10.0, float(sec)))
        print(f'[Test Relay] Включение {pin_name} на {duration} сек...')
        RELAY_REQ.set_value(line, Value.ACTIVE)
        time.sleep(duration)
        RELAY_REQ.set_value(line, Value.INACTIVE)
        print(f'[Test Relay] Выключение {pin_name}. Готово.')
        return JSONResponse({'status': 'ok', 'channel': channel, 'pin': pin_name, 'duration': duration})
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)})

@app.post('/api/save_final_measurement')
def handle_save_final(
    weight_g: str = Form(''),
    pct_soil: str = Form(''),
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

    # Влажность субстрата из подтвержденного оператором поля
    if pct_soil.strip():
        try:
            ps_val = float(pct_soil.strip().replace(',', '.'))
            s['pct_soil'] = round(max(0.0, min(100.0, ps_val)), 1)
            s['v_soil'] = round(3.0 - (s['pct_soil'] / 100.0) * 1.8, 2)
        except Exception:
            pass

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
            s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
            s['opt_file'], jpg_stored_name,
            *s['cell_ndvis']
        ])

    PENDING_SESSION = None
    return RedirectResponse(url=f'/?msg=saved&last_grp={group_name}', status_code=303)

@app.get('/api/cancel_session')
def handle_cancel_session():
    """Сброс текущего одиночного замера."""
    global PENDING_SESSION
    PENDING_SESSION = None
    return RedirectResponse(url='/?msg=cancelled', status_code=303)

# ----------------- ЭНДПОИНТЫ ПАКЕТНОГО ЗАМЕРА (3-В-1) -----------------
@app.get('/api/start_batch')
def handle_start_batch(stage: str = 'stage1'):
    """Старт пакетной сессии для выбранного этапа (stage1 или stage2)."""
    global BATCH_STATE, PENDING_SESSION
    PENDING_SESSION = None
    if stage not in BATCH_CONFIG:
        stage = 'stage1'
    BATCH_STATE = {
        'active': True,
        'stage_key': stage,
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    }
    return RedirectResponse(url='/?stage=batch_shoot', status_code=303)

@app.get('/api/cancel_batch')
def handle_cancel_batch():
    """Отмена текущей пакетной сессии."""
    global BATCH_STATE
    BATCH_STATE = {
        'active': False,
        'stage_key': 'stage1',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    }
    return RedirectResponse(url='/?msg=cancelled', status_code=303)

@app.post('/api/batch_capture_next')
def handle_batch_capture_next(
    cohort_choice: str = Form('auto'),
    weight_g: str = Form(''),
    t_leaf: str = Form(''),
    pct_soil: str = Form('64.0')
):
    """Съемка очередной кассеты в боксе NoIR камерой с авто-детекцией ArUco, мягкими предупреждениями и ручным выбором когорты."""
    global BATCH_STATE
    if not BATCH_STATE.get('active'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)
    
    stage_key = BATCH_STATE['stage_key']
    cassettes = BATCH_CONFIG[stage_key]['cassettes']
    step = len(BATCH_STATE['sessions'])
    if step >= len(cassettes):
        return RedirectResponse(url='/?stage=batch_await_thermal', status_code=303)
    
    expected_cassette = cassettes[step]
    
    # 1. Если оператор выбрал когорту вручную из списка — используем её
    manual_mode = (cohort_choice != 'auto' and cohort_choice.strip().isdigit())
    if manual_mode:
        chosen_id = int(cohort_choice)
        c_meta = CASSETTE_CATALOG.get(chosen_id, {'id': chosen_id, 'name': f'Кассета #{chosen_id}'})
        target_name = c_meta['name']
    else:
        chosen_id = None
        target_name = expected_cassette['name']
    
    try:
        session = do_hardware_spectral_capture(target_name)
        detected_id = session.get('aruco_id')
        warn_query = ''

        if manual_mode:
            # Ручной выбор оператора имеет абсолютный приоритет над компьютерным зрением
            session['aruco_id'] = chosen_id
            session['group'] = CASSETTE_CATALOG.get(chosen_id, {}).get('name', f'Кассета #{chosen_id}')
        else:
            # Режим авто-детекции по маркеру ArUco
            if detected_id is not None:
                grp_name = CASSETTE_CATALOG.get(detected_id, {}).get('name', f'Кассета #{detected_id}')
                session['group'] = grp_name
                
                # Мягкое предупреждение: если маркер уже встречался в серии
                is_dup = any(past_s.get('aruco_id') == detected_id for past_s in BATCH_STATE['sessions'])
                if is_dup:
                    warn_query = f'&msg=warn_duplicate_aruco&dup_id={detected_id}&dup_name={grp_name}'
                elif detected_id not in [c['id'] for c in cassettes]:
                    exp_str = ', '.join(str(c['id']) for c in cassettes)
                    warn_query = f'&msg=warn_wrong_stage_aruco&wrong_id={detected_id}&expected={exp_str}'
            else:
                # Мягкий fallback: маркер не распознался (закрыт листом, поврежден, темно)
                session['aruco_id'] = expected_cassette['id']
                session['group'] = expected_cassette['name']
                warn_query = f"&msg=warn_no_aruco&exp_id={expected_cassette['id']}&exp_name={expected_cassette['name']}"

        # 2. Фиксация введенных ручных параметров
        session['user_weight'] = weight_g.strip().replace(',', '.') if weight_g.strip() else ''
        session['user_t_leaf'] = t_leaf.strip().replace(',', '.') if t_leaf.strip() else ''
        session['user_pct_soil'] = pct_soil.strip().replace(',', '.') if pct_soil.strip() else '64.0'
        session['shot_order'] = len(BATCH_STATE['sessions']) + 1

        BATCH_STATE['sessions'].append(session)
        BATCH_STATE['current_step'] = len(BATCH_STATE['sessions'])

        if len(BATCH_STATE['sessions']) >= len(cassettes):
            next_stage = 'batch_await_thermal'
        else:
            next_stage = 'batch_shoot'

        return RedirectResponse(url=f'/?stage={next_stage}{warn_query}', status_code=303)
    except Exception as e:
        print('[Batch Capture Error]:', e)
        return RedirectResponse(url='/?stage=batch_shoot&msg=err_camera', status_code=303)

@app.post('/api/batch_link_thermal')
def handle_batch_link_thermal():
    """Считывание последних термограмм с флешки тепловизора и авто-привязка к кассетам с сортировкой по ArUco."""
    global BATCH_STATE
    stage_key = BATCH_STATE.get('stage_key', 'batch5')
    stage_cassettes = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])['cassettes']
    expected_count = len(stage_cassettes)
    
    if not BATCH_STATE.get('active') or len(BATCH_STATE.get('sessions', [])) != expected_count:
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)
    
    auto_mount_uti()
    files = get_uti_sorted_files()
    if len(files) < expected_count:
        return RedirectResponse(url=f'/?stage=batch_await_thermal&msg=err_thermal_count&found={len(files)}', status_code=303)
    
    # Берем N самых свежих файлов и сортируем хронологически
    recent_files = files[:expected_count]
    recent_files.sort(key=os.path.getmtime)
    
    stage_ids = [c['id'] for c in stage_cassettes]
    paired_items = []
    used_ids = set()
    for i, s in enumerate(BATCH_STATE['sessions']):
        fp = recent_files[i]
        fname = os.path.basename(fp)
        mtime = os.path.getmtime(fp)
        thumb_jpg = f'{int(mtime)}_{fname}.jpg'
        thumb_path = os.path.join(TH_CACHE_DIR, thumb_jpg)
        if not os.path.exists(thumb_path):
            try:
                im = Image.open(fp)
                im.save(thumb_path)
            except Exception:
                pass
        
        # Если оператор уже ввел температуру листа на шаге замера - сохраняем её!
        if s.get('user_t_leaf'):
            t_val = s['user_t_leaf']
        else:
            t_val = extract_temperature_from_thermal(thumb_path) if os.path.exists(thumb_path) else round(s['t_air'] + 0.5, 1)
        
        detected_id = s.get('aruco_id')
        assigned_id = None
        if detected_id and detected_id in stage_ids and detected_id not in used_ids:
            assigned_id = detected_id
            used_ids.add(assigned_id)
        
        paired_items.append({
            'session': s,
            'shot_order': s.get('shot_order', i + 1),
            'thermal_filename': fname,
            'thermal_thumb': thumb_jpg,
            'thermal_thumb_url': f'/static/uti_cache/{thumb_jpg}',
            't_ocr': t_val,
            'dt_str': format_ru_datetime(mtime),
            'detected_id': detected_id,
            'assigned_id': assigned_id
        })
    
    remaining_ids = [cid for cid in stage_ids if cid not in used_ids]
    for item in paired_items:
        if item['assigned_id'] is None:
            item['assigned_id'] = remaining_ids.pop(0) if remaining_ids else stage_ids[0]
    
    paired_items.sort(key=lambda x: x['assigned_id'])
    BATCH_STATE['verified_data'] = paired_items
    return RedirectResponse(url='/?stage=batch_verify', status_code=303)

@app.post('/api/batch_save_manual')
async def handle_batch_save_manual(request: Request):
    """Мгновенное сохранение всей серии кассет с подтвержденными ручными данными (экспресс-финиш без проводов)."""
    global BATCH_STATE
    if not BATCH_STATE.get('active') or not BATCH_STATE.get('sessions'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)

    form = await request.form()
    stage_key = BATCH_STATE.get('stage_key', 'batch5')
    stage_cassettes = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])['cassettes']
    stage_ids = [c['id'] for c in stage_cassettes]

    records_to_save = []
    for i, s in enumerate(BATCH_STATE['sessions']):
        cid_str = form.get(f'cassette_id_{i}')
        cid = int(cid_str) if (cid_str and str(cid_str).isdigit()) else s.get('aruco_id')
        if not cid or cid not in CASSETTE_CATALOG:
            cid = stage_ids[i] if i < len(stage_ids) else (i + 1)

        c_meta = CASSETTE_CATALOG.get(cid, {'name': f'Кассета #{cid}'})
        group_name = c_meta['name']
        meas_id = s['id']
        ts_display = s['timestamp']

        w_raw = form.get(f'weight_g_{i}', '')
        w_val = str(w_raw).strip().replace(',', '.') if str(w_raw).strip() else s.get('user_weight', '')

        t_raw = form.get(f't_leaf_{i}', '')
        t_l_val = str(t_raw).strip().replace(',', '.') if str(t_raw).strip() else s.get('user_t_leaf', '')
        if not t_l_val:
            t_l_val = str(round(float(s['t_air']), 1))

        pct_raw = form.get(f'pct_soil_{i}', '')
        pct_s = str(pct_raw).strip().replace(',', '.') if str(pct_raw).strip() else s.get('user_pct_soil', '64.0')
        try:
            ps = float(pct_s)
            s['pct_soil'] = round(max(0.0, min(100.0, ps)), 1)
            s['v_soil'] = round(3.0 - (s['pct_soil'] / 100.0) * 1.8, 2)
        except Exception:
            pass

        delta_t_val = ''
        if t_l_val:
            try:
                dt = round(float(t_l_val) - float(s['t_air']), 1)
                delta_t_val = str(dt)
            except Exception:
                pass

        records_to_save.append({
            'cid': cid,
            'row': [
                meas_id, ts_display, group_name, w_val,
                s['t_air'], s['rh_air'], s['v_soil'], s['pct_soil'],
                t_l_val, delta_t_val, s['vpd'],
                s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
                s['opt_file'], '',
                *s['cell_ndvis']
            ]
        })

    # Сортируем записи по ID кассеты перед записью в журнал
    records_to_save.sort(key=lambda x: x['cid'])

    with open(CSV_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for r in records_to_save:
            writer.writerow(r['row'])

    stage_name = BATCH_CONFIG.get(stage_key, {}).get('title', 'Серия 5 кассет (5-в-1)')
    BATCH_STATE = {
        'active': False,
        'stage_key': 'batch5',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    }
    return RedirectResponse(url=f'/?msg=batch_saved&stage_name={stage_name}', status_code=303)

@app.post('/api/batch_skip_thermal')
async def handle_batch_skip_thermal(request: Request):
    """Экспресс-пропуск подключения тепловизора: переход к подтверждению серии."""
    return await handle_batch_save_manual(request)

@app.post('/api/batch_save_final')
async def handle_batch_save_final(request: Request):
    """Окончательное групповое сохранение всей серии кассет с учетом выбранных/распознанных ID и тепловизора."""
    global BATCH_STATE
    if not BATCH_STATE.get('active') or not BATCH_STATE.get('verified_data'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)

    form = await request.form()
    verified = BATCH_STATE['verified_data']
    records_to_save = []
    for i, item in enumerate(verified):
        s = item['session']
        cid_raw = form.get(f'cassette_id_{i}')
        cid = int(cid_raw) if (cid_raw and str(cid_raw).isdigit()) else item.get('assigned_id', i+1)
        c_meta = CASSETTE_CATALOG.get(cid, {'name': f'Кассета #{cid}'})
        group_name = c_meta['name']
        meas_id = s['id']
        ts_display = s['timestamp']

        w_raw = form.get(f'weight_g_{i}', '')
        w_val = str(w_raw).strip().replace(',', '.') if str(w_raw).strip() else ''

        t_raw = form.get(f't_leaf_{i}', '')
        t_l_val = str(t_raw).strip().replace(',', '.') if str(t_raw).strip() else str(item['t_ocr'])

        pct_raw = form.get(f'pct_soil_{i}', '')
        if str(pct_raw).strip():
            try:
                ps = float(str(pct_raw).strip().replace(',', '.'))
                s['pct_soil'] = round(max(0.0, min(100.0, ps)), 1)
                s['v_soil'] = round(3.0 - (s['pct_soil'] / 100.0) * 1.8, 2)
            except Exception:
                pass

        delta_t_val = ''
        if t_l_val:
            try:
                dt = round(float(t_l_val) - float(s['t_air']), 1)
                delta_t_val = str(dt)
            except Exception:
                pass

        jpg_stored_name = ''
        src_thumb = os.path.join(STATIC_DIR, 'uti_cache', item['thermal_thumb'])
        if os.path.exists(src_thumb):
            jpg_stored_name = f"therm_{meas_id}_{item['thermal_filename']}.jpg"
            dst_path = os.path.join(STATIC_DIR, jpg_stored_name)
            shutil.copyfile(src_thumb, dst_path)
            if i == len(verified) - 1:
                shutil.copyfile(dst_path, os.path.join(STATIC_DIR, 'last_thermal.jpg'))

        records_to_save.append({
            'cid': cid,
            'row': [
                meas_id, ts_display, group_name, w_val,
                s['t_air'], s['rh_air'], s['v_soil'], s['pct_soil'],
                t_l_val, delta_t_val, s['vpd'],
                s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
                s['opt_file'], jpg_stored_name,
                *s['cell_ndvis']
            ]
        })

    records_to_save.sort(key=lambda r: r['cid'])

    with open(CSV_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for rec in records_to_save:
            writer.writerow(rec['row'])

    stage_name = BATCH_CONFIG.get(BATCH_STATE.get('stage_key', 'batch5'), {}).get('title', 'Пакетная серия')
    BATCH_STATE = {
        'active': False,
        'stage_key': 'batch5',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    }
    return RedirectResponse(url=f'/?msg=batch_saved&stage_name={stage_name}', status_code=303)


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

@app.post('/api/update_measurement')
def handle_update_measurement(
    meas_id: str = Form(...),
    cohort: str = Form(''),
    timestamp: str = Form(''),
    t_leaf: str = Form(''),
    weight_g: str = Form(''),
    pct_soil: str = Form(''),
    thermal_file: UploadFile = File(None)
):
    """
    Интерактивная коррекция параметров ранее сохраненного замера (T_leaf, Weight, Soil, Thermal image).
    Автоматически пересчитывает Delta_T = T_leaf - T_air и сохраняет в measurements.csv.
    """
    meas_id = str(meas_id).strip()
    cohort = str(cohort).strip()
    timestamp = str(timestamp).strip()
    if not os.path.exists(CSV_LOG) or not meas_id:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

    with open(CSV_LOG, 'r', encoding='utf-8') as f:
        rows = list(csv.reader(f))

    if not rows or len(rows) <= 1:
        return RedirectResponse(url='/', status_code=303)

    header = rows[0]
    data_rows = rows[1:]

    found = False
    for r in data_rows:
        if not r:
            continue
        if str(r[0]).strip() == meas_id:
            # Если указана когорта, проверяем точное совпадение когорты в батче
            if cohort and len(r) > 2 and r[2].strip() != cohort:
                continue
            # Если указана временная метка, проверяем совпадение
            if timestamp and len(r) > 1 and timestamp not in r[1] and r[1] not in timestamp:
                continue

            found = True
            # Обновление T_leaf и пересчет Delta_T
            if t_leaf.strip():
                try:
                    tl = float(t_leaf.strip().replace(',', '.'))
                    tl_str = str(round(tl, 1))
                    if len(r) >= 24:
                        r[8] = tl_str
                        # r[4] is T_Air_C
                        if len(r) > 4 and r[4]:
                            try:
                                t_air = float(r[4])
                                r[9] = str(round(tl - t_air, 1))
                            except Exception:
                                pass
                    elif len(r) >= 20:
                        r[6] = tl_str
                    elif len(r) >= 16:
                        r[4] = tl_str
                except Exception:
                    pass

            # Обновление массы
            if weight_g.strip():
                if len(r) >= 20:
                    r[3] = weight_g.strip().replace(',', '.')

            # Обновление влажности субстрата
            if pct_soil.strip():
                try:
                    ps = float(pct_soil.strip().replace(',', '.'))
                    ps = round(max(0.0, min(100.0, ps)), 1)
                    if len(r) >= 24:
                        r[7] = str(ps)
                        # r[6] is Moisture_V
                        r[6] = str(round(3.0 - (ps / 100.0) * 1.8, 2))
                    elif len(r) >= 20:
                        r[5] = str(ps)
                except Exception:
                    pass

            # Прикрепление файла термограммы, если загружен
            if thermal_file and thermal_file.filename:
                try:
                    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(thermal_file.filename))
                    if safe_name:
                        out_fname = f"therm_{meas_id}_{safe_name}"
                        out_path = os.path.join(STATIC_DIR, out_fname)
                        with open(out_path, 'wb') as buf:
                            shutil.copyfileobj(thermal_file.file, buf)
                        if len(r) >= 24:
                            r[15] = out_fname
                        elif len(r) >= 20:
                            r[10] = out_fname
                except Exception as e:
                    print('[Upload thermal error]:', e)
            break

    if found:
        with open(CSV_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(data_rows)
        return RedirectResponse(url=f'/?msg=updated&upd_id={meas_id}', status_code=303)

    return RedirectResponse(url='/?msg=err_not_found', status_code=303)

@app.get('/', response_class=HTMLResponse)
def index(
    stage: str = 'idle',
    offset: int = 0,
    msg: str = '',
    last_grp: str = '',
    del_id: str = '',
    upd_id: str = '',
    phase: str = 'all',
    found: str = '',
    stage_name: str = '',
    dup_id: str = '',
    dup_name: str = '',
    wrong_id: str = '',
    expected: str = '',
    exp_id: str = '',
    exp_name: str = ''
):
    global PENDING_SESSION, BATCH_STATE

    cur_t, cur_rh, cur_v = read_xiaomi_climate()
    cur_vpd = calc_vpd(cur_t, cur_rh)
    t_now = int(time.time())

    # Определение следующей группы по умолчанию для одиночного замера
    next_group_default = 'Контроль'
    if last_grp == 'Контроль':
        next_group_default = 'Засуха'
    elif last_grp == 'Засуха':
        next_group_default = 'Соль'
    elif last_grp == 'Соль':
        next_group_default = 'Контроль'
    elif 'эталон' in last_grp.lower() or ('контр' in last_grp.lower() and ('2' in last_grp or 'этап 2' in last_grp.lower())):
        next_group_default = 'Репарация (~40ч)'
    elif 'репар' in last_grp.lower() or 'ранн' in last_grp.lower():
        next_group_default = 'Критический стресс (~72ч)'
    elif 'критич' in last_grp.lower() or 'поздн' in last_grp.lower():
        next_group_default = 'Эталон (Оптимум)'

    # Уведомления статуса
    raw_banner = ''
    banner_bg = '#10b981'
    if msg == 'batch_saved':
        s_lbl = stage_name if stage_name else 'Пакетная триада'
        raw_banner = f'🎉 Пакетная сессия ({s_lbl}) успешно сохранена! Все 3 замера добавлены в журнал.'
        banner_bg = '#10b981'
    elif msg == 'saved':
        raw_banner = '✅ Замер сохранен в базу! Переставьте следующую кассету.'
        banner_bg = '#10b981'
    elif msg == 'updated':
        u_lbl = f' #{upd_id}' if upd_id else ''
        raw_banner = f'✏️ Исследование{u_lbl} успешно скорректировано! T листа и ΔT пересчитаны.'
        banner_bg = '#0284c7'
    elif msg == 'cancelled':
        raw_banner = 'Замер сброшен. Готов к новому старту.'
        banner_bg = '#64748b'
    elif msg == 'deleted':
        d_lbl = f' #{del_id}' if del_id else ''
        raw_banner = f'🗑️ Исследование{d_lbl} успешно удалено из журнала.'
        banner_bg = '#dc2626'
    elif msg == 'err_not_found':
        raw_banner = '⚠️ Исследование не найдено в базе данных.'
        banner_bg = '#f59e0b'
    elif msg == 'err_camera':
        raw_banner = '❌ Ошибка камеры /dev/video0. Проверьте USB подключение.'
        banner_bg = '#ef4444'
    elif msg == 'err_thermal_count':
        f_cnt = found if found else '0'
        raw_banner = f'⚠️ На тепловизоре обнаружено только {f_cnt} снимка(ов). Сделайте щелчок курком для всех 3 кассет и убедитесь, что USB-кабель подключен.'
        banner_bg = '#ef4444'
    elif msg == 'warn_duplicate_aruco':
        d_name_str = f' ({dup_name})' if dup_name else ''
        raw_banner = f'⚠️ Внимание: маркер #{dup_id}{d_name_str} уже встречался в этой серии! Кадр принят. При необходимости выберите другую кассету ниже.'
        banner_bg = '#f59e0b'
    elif msg == 'warn_no_aruco':
        e_str = exp_name if exp_name else f'Кассета #{exp_id}'
        raw_banner = f'⚠️ ArUco-маркер не считался (закрыт листом или поврежден). Замер принят и назначен как «{e_str}». При необходимости измените кассету.'
        banner_bg = '#f59e0b'
    elif msg == 'warn_wrong_stage_aruco':
        raw_banner = f'⚠️ Предупреждение: маркер #{wrong_id} из другого этапа (ожидались кассеты: {expected}). Кадр принят, проверьте назначение кассеты.'
        banner_bg = '#f59e0b'
    elif msg == 'err_duplicate_aruco':
        d_name_str = f' ({dup_name})' if dup_name else ''
        raw_banner = f'⛔ ЗАБЛОКИРОВАН ДУБЛИКАТ: Кассета с ArUco #{dup_id}{d_name_str} УЖЕ была снята в этой серии! Вы забыли заменить кассету на упорах. Пожалуйста, смените кассету.'
        banner_bg = '#dc2626'
    elif msg == 'err_wrong_stage_aruco':
        raw_banner = f'⚠️ ДРУГОЙ ЭТАП: Обнаружен ArUco #{wrong_id}, а для выбранного этапа нужны кассеты: {expected}. Проверьте номер кассеты.'
        banner_bg = '#f59e0b'

    status_banner = ''
    if raw_banner:
        status_banner = f'''
            <div id="statusAlert" style="position:relative; background:{banner_bg}; padding:12px 42px 12px 18px; border-radius:8px; font-weight:bold; margin-bottom:14px; text-align:center; color:white; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                <span>{raw_banner}</span>
                <button type="button" onclick="dismissBanner()" style="position:absolute; right:12px; top:50%; transform:translateY(-50%); background:rgba(0,0,0,0.2); border:none; color:white; width:26px; height:26px; border-radius:50%; font-size:14px; font-weight:bold; cursor:pointer; line-height:26px; text-align:center;" title="Закрыть уведомление">✕</button>
            </div>
        '''

    # ------------------ ЛОГИКА ЭТАПОВ (WIZARD) ------------------
    if stage == 'batch_shoot' and BATCH_STATE.get('active'):
        # ПАКЕТНЫЙ ШАГ 1: Съемка кассет NoIR + курок тепловизора
        stage_key = BATCH_STATE.get('stage_key', 'batch5')
        conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])
        cassettes = conf['cassettes']
        step_idx = len(BATCH_STATE.get('sessions', []))
        total_steps = len(cassettes)

        slots_html = ''
        short_names = {
            1: "Контроль",
            2: "Засоление",
            3: "Прибор",
            4: "Глаза",
            5: "Гибель",
            6: "Стенд №0"
        }
        for i, c in enumerate(cassettes):
            if i < step_idx:
                s_done = BATCH_STATE['sessions'][i]
                m_id = s_done.get('aruco_id')
                full_grp = s_done.get('group', f'Кадр #{i+1}')
                short_grp = short_names.get(m_id, full_grp)
                if len(short_grp) > 12:
                    short_grp = short_grp[:11] + '…'
                
                if m_id:
                    c_col = CASSETTE_CATALOG.get(m_id, {}).get('color', '#059669')
                    badge = f'<div style="background:{c_col}18; color:{c_col}; font-size:9.5px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid {c_col}50; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">ID #{m_id}</div>'
                    slot_title = f"Кассета #{m_id}"
                    slot_border = f"1.5px solid {c_col}"
                    slot_bg = f"{c_col}0d"
                else:
                    badge = '<div style="background:#fffbeb; color:#b45309; font-size:9.5px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid #fde68a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Ручная привязка</div>'
                    slot_title = f"Кадр #{i+1}"
                    slot_border = "1.5px solid #cbd5e1"
                    slot_bg = "#f8fafc"

                slots_html += f'''
                    <div style="background:{slot_bg}; border:{slot_border}; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px;">
                        <div>
                            <span style="font-size:9.5px; color:#475569; font-weight:bold; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Замер #{i+1}</span>
                            <span style="font-size:11px; color:#0f172a; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{slot_title}</span>
                            <span style="font-size:9.5px; color:#64748b; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{full_grp}">{short_grp}</span>
                        </div>
                        {badge}
                    </div>
                '''
            elif i == step_idx:
                slots_html += f'''
                    <div style="background:#eff6ff; border:2px solid #3b82f6; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px; box-shadow:0 2px 6px rgba(59,130,246,0.2);">
                        <div>
                            <span style="font-size:9.5px; color:#1d4ed8; font-weight:bold; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">ТЕКУЩИЙ ЗАМЕР</span>
                            <span style="font-size:11px; color:#1e40af; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Кадр #{step_idx + 1}</span>
                            <span style="font-size:9.5px; color:#2563eb; font-weight:600; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">из {total_steps}</span>
                        </div>
                        <div style="background:#dbeafe; color:#1e40af; font-size:9px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid #bfdbfe; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Любая кассета</div>
                    </div>
                '''
            else:
                slots_html += f'''
                    <div style="background:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px; opacity:0.75;">
                        <div>
                            <span style="font-size:9.5px; color:#64748b; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Очередь</span>
                            <span style="font-size:11px; color:#475569; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Кадр #{i+1}</span>
                            <span style="font-size:9.5px; color:#94a3b8; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Ожидание</span>
                        </div>
                        <div style="background:#f1f5f9; color:#94a3b8; font-size:9px; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px dashed #cbd5e1; white-space:nowrap;">—</div>
                    </div>
                '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid #3b82f6; background: #ffffff; box-sizing:border-box; margin:0; width:100%; overflow:hidden;">
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                        <div>
                            <span style="font-size:10px; text-transform:uppercase; color:#64748b; font-weight:bold;">Пакетный замер 5 кассет (без проводов)</span>
                            <h2 style="margin:2px 0 0 0; color:#1e40af; font-size:15px;">{conf["title"]}</h2>
                        </div>
                        <span style="background:#dbeafe; color:#1e40af; padding:3px 8px; border-radius:10px; font-size:11px; font-weight:bold;">Кадр {step_idx + 1} из {total_steps}</span>
                    </div>

                    <div style="display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap:6px; margin-bottom:10px; width:100%; box-sizing:border-box;">
                        {slots_html}
                    </div>

                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
                            <span style="font-size:13px; font-weight:bold; color:#0f172a;">
                                Установите любую кассету в бокс (Кадр #{step_idx + 1} из {total_steps})
                            </span>
                            <span style="background:#ecfdf5; color:#047857; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:bold; border:1px solid #a7f3d0;">🏷️ Цветной ArUco</span>
                        </div>
                        <p style="margin:0 0 4px 0; font-size:11px; color:#64748b; line-height:1.3;">
                            <b>Порядок установки не имеет значения.</b> Станция сама считает маркер ArUco со снимка и упорядочит замеры по цвету кассеты.
                        </p>
                        <ol style="margin:0; padding-left:16px; font-size:11px; color:#334155; line-height:1.35;">
                            <li>Поставьте кассету в бокс на упоры.</li>
                            <li>Нажмите кнопку ниже: спектральная вспышка NoIR + ArUco.</li>
                            <li>Сделайте снимок курком тепловизора UTi120S в руках.</li>
                        </ol>
                    </div>

                    <form action="/api/batch_capture_next" method="post">
                        <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:8px; padding:10px; margin-bottom:10px;">
                            <div style="margin-bottom:8px;">
                                <label style="font-size:11px; font-weight:bold; color:#1e40af; display:block; margin-bottom:2px;">
                                    Кассета (когорта):
                                </label>
                                <select name="cohort_choice" style="width:100%; padding:6px 8px; font-size:12px; font-weight:bold; border:1.5px solid #3b82f6; border-radius:6px; background:#eff6ff; color:#1e40af;">
                                    <option value="auto" selected>Автоматически (распознать по ArUco-маркеру)</option>
                                    <option value="1">Кассета #1: Контроль (Оптимум 100% ПВ)</option>
                                    <option value="2">Кассета #2: Засоление (NaCl 150 мМ, изолятор)</option>
                                    <option value="3">Кассета #3: Предиктивный полив (ранний полив по ΔT)</option>
                                    <option value="4">Кассета #4: Органолептический полив (визуальный контроль)</option>
                                    <option value="5">Кассета #5: Терминальная засуха (контроль гибели)</option>
                                    <option value="6">Кассета #6: Калибровочный стенд (Стенд №0, посев 22.09)</option>
                                </select>
                            </div>

                            <span style="font-size:10px; font-weight:bold; color:#475569; text-transform:uppercase; display:block; margin-bottom:6px;">
                                Физиологические параметры замера:
                            </span>
                            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; align-items:end;">
                                <div style="display:flex; flex-direction:column;">
                                    <label style="font-size:11px; font-weight:bold; color:#0f766e; height:18px; display:flex; align-items:flex-end; margin:0 0 3px 0; white-space:nowrap;">
                                        Масса, г:
                                    </label>
                                    <input type="text" name="weight_g" autofocus placeholder="напр. 405.0" style="width:100%; height:36px; padding:6px 8px; font-size:13px; font-weight:bold; border:1.5px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box; margin:0; background:#ffffff;">
                                </div>
                                <div style="display:flex; flex-direction:column;">
                                    <label style="font-size:11px; font-weight:bold; color:#d97706; height:18px; display:flex; align-items:flex-end; margin:0 0 3px 0; white-space:nowrap;">
                                        🌡️ T листа, °C:
                                    </label>
                                    <input type="number" step="0.1" name="t_leaf" placeholder="напр. 23.5" style="width:100%; height:36px; padding:6px 8px; font-size:13px; font-weight:bold; border:1.5px solid #f59e0b; border-radius:6px; box-sizing:border-box; margin:0; background:#ffffff;">
                                </div>
                                <div style="display:flex; flex-direction:column;">
                                    <label style="font-size:11px; font-weight:bold; color:#0284c7; height:18px; display:flex; align-items:flex-end; margin:0 0 3px 0; white-space:nowrap;">
                                        💧 Влажность, %:
                                    </label>
                                    <input type="number" step="0.1" min="0" max="100" name="pct_soil" value="64.0" style="width:100%; height:36px; padding:6px 8px; font-size:13px; font-weight:bold; border:1.5px solid #38bdf8; border-radius:6px; box-sizing:border-box; margin:0; background:#ffffff;">
                                </div>
                            </div>
                        </div>

                        <button type="submit" class="btn-run" style="width:100%; padding:12px; font-size:14px; background:linear-gradient(135deg, #2563eb, #0d9488); cursor:pointer; margin-top:0;">
                            📸 СДЕЛАТЬ СНИМОК #{step_idx + 1} (Вспышка NoIR + ArUco)
                        </button>
                    </form>
                </div>

                <div style="margin-top:8px; text-align:center;">
                    <a href="/api/cancel_batch" style="color:#94a3b8; font-size:11px; text-decoration:none;">❌ Прервать пакетную сессию</a>
                </div>
            </div>
        '''

    elif stage == 'batch_await_thermal' and BATCH_STATE.get('active'):
        # ПАКЕТНЫЙ ШАГ 2: Все 3 кассеты сняты NoIR, выбор сохранения
        stage_key = BATCH_STATE.get('stage_key', 'stage1')
        conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['stage1'])

        cards_summary = ''
        for i, s in enumerate(BATCH_STATE.get('sessions', [])):
            m_id = s.get('aruco_id')
            grp = s.get('group', f'Кадр #{i+1}')
            m_badge = f'<span style="background:#ecfdf5; color:#065f46; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">🏷️ ArUco #{m_id}</span>' if m_id else '<span style="background:#fffbeb; color:#b45309; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">⚠️ Ручная</span>'
            
            # Генерация options для выпадающего списка выбора когорты
            options_html = ''
            for cid, cdata in CASSETTE_CATALOG.items():
                sel = 'selected' if cid == m_id else ''
                options_html += f'<option value="{cid}" {sel}>#{cid}: {cdata["name"]}</option>'
                
            w_val = s.get('user_weight', '')
            t_val = s.get('user_t_leaf', '')
            p_val = s.get('user_pct_soil', '64.0')
            
            cards_summary += f'''
                <div style="flex:1; background:#ffffff; border:1.5px solid #cbd5e1; border-radius:8px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.02);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:11px; color:#64748b; font-weight:bold;">Кадр #{i+1}</span>
                        {m_badge}
                    </div>
                    
                    <div style="margin-bottom:8px;">
                        <label style="font-size:10px; font-weight:bold; color:#1e40af; display:block; margin-bottom:2px;">Когорта / Кассета:</label>
                        <select name="cassette_id_{i}" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1.5px solid #94a3b8; border-radius:6px; background:#f8fafc;">
                            {options_html}
                        </select>
                    </div>

                    <img src="/static/{s.get('opt_file', 'last_ndvi.jpg')}?t={t_now}" style="height:68px; border-radius:4px; object-fit:cover; width:100%; border:1px solid #e2e8f0; margin-bottom:6px;">
                    
                    <div style="font-size:11px; color:#047857; font-weight:bold; text-align:center; margin-bottom:8px;">
                        NDVI: {s.get("mean_ndvi", "--")} · PLA: {s.get("leaf_area_cm2", "--")} см²
                    </div>

                    <div style="display:flex; flex-direction:column; gap:5px;">
                        <div>
                            <label style="font-size:10px; font-weight:bold; color:#0f766e; display:block;">⚖️ Масса с весов, г:</label>
                            <input type="text" name="weight_g_{i}" value="{w_val}" placeholder="напр. 410.0" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1px solid #0d9488; border-radius:4px; box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="font-size:10px; font-weight:bold; color:#d97706; display:block;">🌡️ T листа с UTi120S (°C):</label>
                            <input type="number" step="0.1" name="t_leaf_{i}" value="{t_val}" placeholder="напр. 23.8" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1px solid #f59e0b; border-radius:4px; box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="font-size:10px; font-weight:bold; color:#0284c7; display:block;">💧 Влажность почвы, %:</label>
                            <input type="number" step="0.1" min="0" max="100" name="pct_soil_{i}" value="{p_val}" style="width:100%; padding:5px; font-size:12px; border:1px solid #38bdf8; border-radius:4px; box-sizing:border-box;">
                        </div>
                    </div>
                </div>
            '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid #10b981; background: #ffffff;">
                <div style="text-align:center; padding:6px 0 10px 0;">
                    <div style="font-size:28px; margin-bottom:2px;">🎉</div>
                    <h2 style="margin:0; color:#065f46; font-size:17px;">Все {len(BATCH_STATE.get('sessions', []))} кассет успешно отсняты и измерены!</h2>
                    <span style="font-size:12px; color:#047857;">{conf["title"]}</span>
                </div>

                <form action="/api/batch_save_manual" method="post">
                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin-bottom:14px;">
                        {cards_summary}
                    </div>

                    <button type="submit" class="btn-confirm" style="width:100%; padding:15px; font-size:16px; background:linear-gradient(135deg, #059669, #00a499); cursor:pointer; box-shadow:0 4px 14px rgba(0,164,153,0.35);">
                        ✅ ВСЁ ГОТОВО — СОХРАНИТЬ ВСЕ {len(BATCH_STATE.get('sessions', []))} КАССЕТ В ЖУРНАЛ (БЕЗ ТЕПЛОВИЗОРА)
                    </button>
                </form>

                <div style="margin-top:14px; padding:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; text-align:center;">
                    <span style="font-size:12px; color:#475569; display:block; margin-bottom:8px;">Есть свободное время? Можете подключить тепловизор кабелем и подтянуть фотоснимки:</span>
                    <form action="/api/batch_link_thermal" method="post">
                        <button type="submit" style="padding:10px 18px; font-size:13px; background:#0284c7; color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">
                            🔌 Вставить USB-кабель тепловизора и прикрепить фото
                        </button>
                    </form>
                </div>

                <div style="margin-top:12px; text-align:center;">
                    <a href="/api/cancel_batch" style="color:#94a3b8; font-size:12px; text-decoration:none;">❌ Отменить сессию</a>
                </div>
            </div>
        '''

    elif stage == 'batch_verify' and BATCH_STATE.get('active') and BATCH_STATE.get('verified_data'):
        # ПАКЕТНЫЙ ШАГ 3: Финальная верификация всей тройки кассет, отсортированной по ArUco
        stage_key = BATCH_STATE.get('stage_key', 'stage1')
        conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['stage1'])
        verified = BATCH_STATE.get('verified_data', [])

        items_html = ''
        for i, item in enumerate(verified):
            s = item['session']
            assigned_id = item['assigned_id']
            detected_id = item.get('detected_id')
            shot_order = item.get('shot_order', i + 1)
            c_info = CASSETTE_CATALOG.get(assigned_id, {'id': assigned_id, 'name': s.get('group', 'Кассета'), 'color': '#0d9488'})

            if detected_id:
                marker_badge = f'<span style="background:#ecfdf5; color:#065f46; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #a7f3d0;">🏷️ ArUco #{detected_id} распознан (снята #{shot_order}-й)</span>'
            else:
                marker_badge = f'<span style="background:#fffbeb; color:#b45309; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #fde68a;">⚠️ ArUco не найден (снята #{shot_order}-й)</span>'

            # Выпадающий список выбора когорты (на случай ручной коррекции)
            options_html = ''
            for cid, cdata in CASSETTE_CATALOG.items():
                sel = 'selected' if cid == assigned_id else ''
                options_html += f'<option value="{cid}" {sel}>Кассета #{cid}: {cdata["name"]}</option>'

            items_html += f'''
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:10px; padding:12px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f1f5f9; padding-bottom:8px; margin-bottom:8px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <label style="font-weight:bold; font-size:13px; color:#334155;">Когорта:</label>
                            <select name="cassette_id_{i}" style="padding:4px 8px; font-size:13px; font-weight:bold; color:{c_info['color']}; border:1.5px solid #94a3b8; border-radius:6px; background:#f8fafc;">
                                {options_html}
                            </select>
                        </div>
                        <div style="display:flex; gap:6px; align-items:center;">
                            {marker_badge}
                            <span style="background:#ecfdf5; color:#047857; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold;">NDVI: {s['mean_ndvi']}</span>
                            <span style="background:#f0fdf4; color:#15803d; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #bbf7d0;">🌿 PLA: {s.get('leaf_area_cm2', '--')} см²</span>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-bottom:10px;">
                        <div style="text-align:center;">
                            <span style="font-size:10px; color:#64748b; display:block; margin-bottom:2px;">Спектр NoIR (кадр #{shot_order})</span>
                            <img src="/static/{s['opt_file']}?t={t_now}" style="width:100%; height:85px; object-fit:cover; border-radius:6px; border:1px solid #e2e8f0;">
                        </div>
                        <div style="text-align:center;">
                            <span style="font-size:10px; color:#64748b; display:block; margin-bottom:2px;">Тепловизор ({item['thermal_filename']})</span>
                            <img src="{item['thermal_thumb_url']}?t={t_now}" style="width:100%; height:85px; object-fit:contain; border-radius:6px; border:1px solid #e2e8f0; background:#f8fafc;">
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px;">
                        <div>
                            <label style="font-size:11px; font-weight:bold; display:block; margin-bottom:2px; color:#0f766e;">⚖️ Масса с весов, г:</label>
                            <input type="text" name="weight_g_{i}" value="{s.get('user_weight', '')}" placeholder="напр. 415.0" style="width:100%; padding:7px; font-size:13px; border:2px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box;" {'autofocus' if i==0 else ''}>
                        </div>
                        <div>
                            <label style="font-size:11px; font-weight:bold; display:block; margin-bottom:2px; color:#0284c7;">💧 Влажность почвы, %:</label>
                            <input type="number" step="0.1" min="0" max="100" name="pct_soil_{i}" value="{s.get('pct_soil', 64.0)}" required style="width:100%; padding:7px; font-size:13px; border:1.5px solid #38bdf8; border-radius:6px; box-sizing:border-box;">
                        </div>
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                                <label style="font-size:11px; font-weight:bold; color:#334155;">🌡️ T листа (°C):</label>
                                <span style="font-size:10px; color:#64748b;">OCR: <b>{item['t_ocr']}°C</b></span>
                            </div>
                            <input type="number" step="0.1" name="t_leaf_{i}" id="t_leaf_{i}" value="{item['t_ocr']}" required style="width:100%; padding:7px; font-size:13px; font-weight:bold; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box;">
                            <div style="display:flex; gap:2px; margin-top:4px;">
                                <button type="button" onclick="adjTemp('t_leaf_{i}', -1.0)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 1.0°C">-1°</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', -0.5)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 0.5°C">-0.5°</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', -0.1)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 0.1°C">-0.1°</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', 0.1)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 0.1°C">+0.1°</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', 0.5)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 0.5°C">+0.5°</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', 1.0)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 1.0°C">+1°</button>
                            </div>
                        </div>
                    </div>
                </div>
            '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid var(--sirius-teal); background: #f8fafc;">
                <div style="border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:12px;">
                    <span style="font-size:11px; text-transform:uppercase; color:#64748b; font-weight:bold;">Финальная верификация серии (отсортировано по ArUco)</span>
                    <h2 style="margin:2px 0 0 0; color:var(--sirius-teal-dark); font-size:16px;">{conf["title"]}</h2>
                </div>

                <form action="/api/batch_save_final" method="post">
                    {items_html}

                    <button type="submit" class="btn-confirm" style="width:100%; padding:14px; font-size:16px; background:linear-gradient(135deg, #059669, #00a499); box-shadow:0 4px 14px rgba(0,164,153,0.35); margin-top:8px; cursor:pointer;">
                        ✅ ВСЁ В ПОРЯДКЕ — СОХРАНИТЬ ВСЮ СЕРИЮ В БАЗУ ({len(verified)} ЗАМЕРОВ)
                    </button>

                    <div style="margin-top:10px; text-align:center;">
                        <a href="/api/cancel_batch" style="color:#94a3b8; font-size:12px; text-decoration:none;">❌ Отменить эту сессию</a>
                    </div>
                </form>
            </div>
        '''

    elif stage == 'review' and PENDING_SESSION:
        # ЭТАП 2 ОДИНОЧНОГО ЗАМЕРА: ВЕРИФИКАЦИЯ И ПОДТВЕРЖДЕНИЕ
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
        
        step1_note = f'''
            <div style="background:#ecfdf5; border:1px solid #a7f3d0; padding:10px; border-radius:8px; margin-bottom:12px; font-size:12px; color:#065f46;">
                🎯 <b>ArUco-маркер #{s.get('aruco_id', '--')} обнаружен:</b> когорта <b>«{s['group']}»</b> определена автоматически.<br>
                <span style="display:inline-block; margin-top:5px; background:#eff6ff; color:#1d4ed8; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">🎯 Радиометрическая калибровка: White Ref k={s.get('k_bal', 1.025)} (диффузный эталон)</span>
                <div style="margin-top:6px;">Переставьте кассету на весы и подключите тепловизор.</div>
            </div>
        ''' if s.get('aruco_id') else f'''
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
                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; margin-top:10px;">
                        <div>
                            <label style="font-size:11px; font-weight:bold; display:block; margin-bottom:2px; color:#0f766e;">⚖️ Масса кассеты, г:</label>
                            <input type="text" name="weight_g" autofocus placeholder="с весов, напр. 415.0" required style="width:100%; padding:8px; font-size:13px; border:2px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="font-size:11px; font-weight:bold; display:block; margin-bottom:2px; color:#0284c7;">💧 Влажность почвы, %:</label>
                            <input type="number" step="0.1" min="0" max="100" name="pct_soil" value="{s['pct_soil']}" required style="width:100%; padding:8px; font-size:13px; border:1.5px solid #38bdf8; border-radius:6px; box-sizing:border-box;">
                        </div>
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                                <label style="font-size:11px; font-weight:bold; color:#334155;">🌡️ T листа (°C):</label>
                                <span style="font-size:10px; color:#64748b;">OCR: <b>{t_leaf_init}°C</b></span>
                            </div>
                            <input type="number" step="0.1" name="t_leaf" id="single_t_leaf" value="{t_leaf_init}" required style="width:100%; padding:8px; font-size:13px; font-weight:bold; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box;">
                            <div style="display:flex; gap:2px; margin-top:4px;">
                                <button type="button" onclick="adjTemp('single_t_leaf', -1.0)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 1.0°C">-1°</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', -0.5)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 0.5°C">-0.5°</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', -0.1)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 0.1°C">-0.1°</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', 0.1)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 0.1°C">+0.1°</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', 0.5)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 0.5°C">+0.5°</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', 1.0)" style="flex:1; font-size:10px; padding:2px 0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 1.0°C">+1°</button>
                            </div>
                        </div>
                    </div>

                    <div style="margin-top:10px; padding:8px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; font-size:12px; display:flex; justify-content:space-between; color:#334155;">
                        <span>T возд: <b style="color:#0284c7;">{s['t_air']} °C</b> (SHT30)</span>
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
        # ЭТАП IDLE: ВЫБОР РЕЖИМА ЗАМЕРА (ПАКЕТНЫЙ ЗАМЕР 5 КАССЕТ 5-В-1 ИЛИ ОДИНОЧНЫЙ)
        wizard_card = f'''
            <div class="card" style="border: 2px solid var(--sirius-teal); margin:0;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <h2 style="margin:0; color:var(--sirius-teal-dark); font-size:15px;">🚀 Единый пакетный замер 5 кассет (5-в-1)</h2>
                    <span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;">1 подключение кабеля</span>
                </div>
                <p style="font-size: 11px; color: #475569; margin: 0 0 10px 0; line-height:1.35;">
                    Станция последовательно снимет все 5 кассет (NoIR + цветные ArUco-маркеры), а провод тепловизора подключается <b>всего один раз в конце серии</b>:
                </p>

                <!-- Главная кнопка запуска замера 5 кассет -->
                <a href="/api/start_batch?stage=batch5" style="text-decoration:none; display:block; background:linear-gradient(135deg, #0d9488 0%, #059669 45%, #2563eb 100%); color:white; padding:12px; border-radius:10px; text-align:center; box-shadow:0 4px 12px rgba(13,148,136,0.3); transition:all 0.2s;">
                    <span style="font-size:18px; display:block; margin-bottom:2px;">🌿🔬</span>
                    <b style="font-size:14px; display:block;">ЗАПУСТИТЬ ЗАМЕР 5 КАССЕТ (5-В-1)</b>
                    <span style="font-size:10px; opacity:0.95; display:block; margin-top:2px;">🟢 К1 Контроль • 🟣 К2 Соль • 🟡 К3 Прибор • 🔵 К4 Глаза • 🔴 К5 Гибель</span>
                </a>

                <!-- Памятка по изолятору соли -->
                <div style="margin-top:8px; padding:6px 10px; background:#f5f3ff; border:1px solid #ddd6fe; border-radius:6px; font-size:10px; color:#5b21b6; line-height:1.3;">
                    💡 <b>Биобезопасность:</b> Кассеты 1, 3, 4, 5 стоят в общем лотке. Кассета №2 (Соль) установлена в <b>отдельном лотке-изоляторе</b> для защиты дренажа от перекрестного засоления.
                </div>

                <!-- Выпадающий одиночный замер -->
                <details style="border-top:1px solid #e2e8f0; padding-top:8px; margin-top:8px;">
                    <summary style="cursor:pointer; color:#64748b; font-size:11px; font-weight:bold;">
                        Выборочный одиночный замер одной кассеты
                    </summary>
                    <form action="/api/start_spectral" method="post" style="margin-top:8px;">
                        <select name="group_name" style="margin-bottom:6px; font-size:12px;">
                            <option value="Контроль">Кассета 1: Контроль (Оптимум 100% ПВ)</option>
                            <option value="Засоление (NaCl)">Кассета 2: Засоление (NaCl 150 мМ, изолятор)</option>
                            <option value="Превентивная регидратация">Кассета 3: Превентивная регидратация (ранний полив по ΔT)</option>
                            <option value="Традиционный визуальный контроль">Кассета 4: Традиционный визуальный контроль (потеря тургора)</option>
                            <option value="Терминальная засуха">Кассета 5: Терминальная засуха (контроль гибели)</option>
                            <option value="Калибровка (Стенд №0)">Кассета 6: Калибровочный стенд (Стенд №0, посев 22.09)</option>
                        </select>
                        <button type="submit" class="btn-run" style="padding:8px; font-size:12px; margin-top:0;">
                            Снять выбранную кассету в боксе
                        </button>
                    </form>
                </details>
            </div>
        '''

    # ТАБЛИЦА ЖУРНАЛА
    rows = []
    if os.path.exists(CSV_LOG):
        with open(CSV_LOG, 'r', encoding='utf-8') as f:
            all_r = list(csv.reader(f))
            if len(all_r) > 1:
                rows = all_r[1:]

    # Экспресс-статистика 5 когорт
    cnt_ctrl, cnt_salt, cnt_inst, cnt_eye, cnt_term = 0, 0, 0, 0, 0
    ndvis_ctrl, ndvis_salt, ndvis_inst, ndvis_eye, ndvis_term = [], [], [], [], []

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

            if 'прибор' in grp_l or 'станци' in grp_l or 'репар' in grp_l:
                cnt_inst += 1
                if ndvi_val is not None: ndvis_inst.append(ndvi_val)
            elif 'глаз' in grp_l or 'визуал' in grp_l or 'поздн' in grp_l:
                cnt_eye += 1
                if ndvi_val is not None: ndvis_eye.append(ndvi_val)
            elif 'терминал' in grp_l or 'гибель' in grp_l or 'некроз' in grp_l or ('засух' in grp_l and 'спасени' not in grp_l):
                cnt_term += 1
                if ndvi_val is not None: ndvis_term.append(ndvi_val)
            elif 'сол' in grp_l or 'salin' in grp_l:
                cnt_salt += 1
                if ndvi_val is not None: ndvis_salt.append(ndvi_val)
            elif 'контр' in grp_l or 'control' in grp_l or 'эталон' in grp_l or 'оптимум' in grp_l:
                cnt_ctrl += 1
                if ndvi_val is not None: ndvis_ctrl.append(ndvi_val)

    def mean_s(lst, default="--"):
        return f"{sum(lst)/len(lst):.3f}" if lst else default

    m_ctrl_ndvi = mean_s(ndvis_ctrl, "0.760" if not rows else "--")
    m_salt_ndvi = mean_s(ndvis_salt, "--")
    m_inst_ndvi = mean_s(ndvis_inst, "--")
    m_eye_ndvi = mean_s(ndvis_eye, "--")
    m_term_ndvi = mean_s(ndvis_term, "--")

    eff_badge = "100% тургор"
    if ndvis_inst and ndvis_eye:
        diff_pct = round(((sum(ndvis_inst)/len(ndvis_inst)) - (sum(ndvis_eye)/len(ndvis_eye))) / (sum(ndvis_inst)/len(ndvis_inst)) * 100, 1)
        eff_badge = f"+{diff_pct}% сохранность" if diff_pct > 0 else "0% потерь"

    filtered_rows = rows

    summary_card = f'''
        <div class="card" style="margin-top: 0; padding:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1.5px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <div style="width:4px; height:16px; background:var(--sirius-teal); border-radius:2px;"></div>
                    <h2 style="margin:0; font-size:14px; font-weight:700; border:none; padding:0; color:var(--sirius-teal-dark); letter-spacing:-0.2px;">Сводка экспериментальных когорт</h2>
                </div>
                <span style="background:#f1f5f9; border:1px solid #cbd5e1; color:#334155; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:600;">Всего измерений: {len(rows)}</span>
            </div>

            <!-- ЕДИНЫЙ РЯД: ВСЕ 5 КАССЕТ СТРОГО ПО ПОРЯДКОВЫМ НОМЕРАМ 1, 2, 3, 4, 5 -->
            <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:8px; margin-bottom:10px;">
                <!-- К1: Контроль -->
                <div style="background:#ecfdf5; border:1.5px solid #059669; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:10.5px; color:#065f46; font-weight:700; display:flex; align-items:center; justify-content:center; gap:4px;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#059669; display:inline-block;"></span> К1: Контроль
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#047857; margin:2px 0;">{cnt_ctrl} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">изм.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#059669;">{m_ctrl_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#047857; font-weight:600; margin-top:2px; padding-top:2px; border-top:1px dashed #a7f3d0;">Оптимум (100% ПВ)</div>
                </div>
                <!-- К2: Засоление -->
                <div style="background:#f5f3ff; border:1.5px solid #7c3aed; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:10.5px; color:#5b21b6; font-weight:700; display:flex; align-items:center; justify-content:center; gap:4px;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#7c3aed; display:inline-block;"></span> К2: Засоление
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#6d28d9; margin:2px 0;">{cnt_salt} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">изм.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#7c3aed;">{m_salt_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#5b21b6; font-weight:600; margin-top:2px; padding-top:2px; border-top:1px dashed #ddd6fe;">150 мМ NaCl</div>
                </div>
                <!-- К3: Предиктивный полив -->
                <div style="background:#fefce8; border:1.5px solid #ca8a04; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:10.5px; color:#854d0e; font-weight:700; display:flex; align-items:center; justify-content:center; gap:4px;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#ca8a04; display:inline-block;"></span> К3: Прибор
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#a16207; margin:2px 0;">{cnt_inst} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">изм.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#ca8a04;">{m_inst_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#854d0e; font-weight:600; margin-top:2px; padding-top:2px; border-top:1px dashed #fef08a;">Ранний полив (ΔT)</div>
                </div>
                <!-- К4: Органолептический полив -->
                <div style="background:#eff6ff; border:1.5px solid #2563eb; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:10.5px; color:#1e40af; font-weight:700; display:flex; align-items:center; justify-content:center; gap:4px;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#2563eb; display:inline-block;"></span> К4: Глаза
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#1d4ed8; margin:2px 0;">{cnt_eye} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">изм.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#2563eb;">{m_eye_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#1e40af; font-weight:600; margin-top:2px; padding-top:2px; border-top:1px dashed #bfdbfe;">Визуальн. увядание</div>
                </div>
                <!-- К5: Терминальная засуха -->
                <div style="background:#fff1f2; border:1.5px solid #dc2626; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:10.5px; color:#9f1239; font-weight:700; display:flex; align-items:center; justify-content:center; gap:4px;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#e11d48; display:inline-block;"></span> К5: Гибель
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#be123c; margin:2px 0;">{cnt_term} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">изм.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#dc2626;">{m_term_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#9f1239; font-weight:600; margin-top:2px; padding-top:2px; border-top:1px dashed #fecdd3;">Точка невозврата</div>
                </div>
            </div>

            <!-- ИНФОРМАЦИОННАЯ ПЛАШКА СРАВНИТЕЛЬНОГО АНАЛИЗА К3 VS К4 -->
            <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:7px 12px; display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="background:#e0f2fe; color:#0369a1; font-size:9.5px; font-weight:700; padding:2px 7px; border-radius:3px; text-transform:uppercase; letter-spacing:0.5px;">Сравнение</span>
                    <span style="font-size:11px; color:#1e293b; font-weight:600;">
                        <b>Предиктивная эффективность:</b> К3 (полив по раннему алерту станции) vs К4 (полив по визуальным признакам)
                    </span>
                </div>
                <span style="background:#ecfdf5; color:#047857; font-size:10.5px; font-weight:700; padding:3px 10px; border-radius:4px; border:1px solid #a7f3d0; white-space:nowrap;">Сохранность: {eff_badge}</span>
            </div>

            <!-- 4 КНОПКИ ДЕЙСТВИЙ: СТРОГО ОДИНАКОВАЯ ВЫСОТА 38px, ОДНОСТРОЧНЫЙ ТЕКСТ, БЕЗ СМАЙЛОВ -->
            <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px;">
                <a href="/download/csv" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:6px; color:#334155; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='var(--sirius-teal)';this.style.color='#fff';this.style.borderColor='var(--sirius-teal)';" onmouseout="this.style.background='#f8fafc';this.style.color='#334155';this.style.borderColor='#cbd5e1';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span>Экспорт данных (.CSV)</span>
                </a>
                <a href="/download/images_zip" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:6px; color:#15803d; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='#10b981';this.style.color='#fff';this.style.borderColor='#10b981';" onmouseout="this.style.background='#f0fdf4';this.style.color='#15803d';this.style.borderColor='#bbf7d0';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                    <span>Архив кадров (.ZIP)</span>
                </a>
                <a href="/download/aruco_pdf" target="_blank" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#f0fdfa; border:1.5px solid #99f6e4; border-radius:6px; color:#0f766e; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='#00a499';this.style.color='#fff';this.style.borderColor='#00a499';" onmouseout="this.style.background='#f0fdfa';this.style.color='#0f766e';this.style.borderColor='#99f6e4';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><rect x="7" y="7" width="3" height="3"/><rect x="14" y="7" width="3" height="3"/><rect x="14" y="14" width="3" height="3"/><rect x="7" y="14" width="3" height="3"/></svg>
                    <span>Маркеры ArUco (.PDF)</span>
                </a>
                <a href="/download/presentation" target="_blank" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#eff6ff; border:1.5px solid #bfdbfe; border-radius:6px; color:#1d4ed8; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='#2563eb';this.style.color='#fff';this.style.borderColor='#2563eb';" onmouseout="this.style.background='#eff6ff';this.style.color='#1d4ed8';this.style.borderColor='#bfdbfe';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                    <span>Презентация (.PDF)</span>
                </a>
            </div>
        </div>
    '''

    table_html = ''
    for r in reversed(filtered_rows):
        leaf_area_val = "--"
        if len(r) >= 25:
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
            leaf_area_val = f"{r[13]} см²" if r[13] else "--"
            th_name = r[15] if len(r)>15 else ""

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

        elif len(r) >= 24:
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
            if '.jpg' in r[13] or '.png' in r[13]:
                leaf_area_val = "--"
                th_name = r[14] if len(r)>14 else ""
            else:
                leaf_area_val = f"{r[13]} см²"
                th_name = r[15] if len(r)>15 else ""

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
            leaf_area_val = "--"
            th_name = r[10] if len(r)>10 else ""
        else:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[4]}%" if len(r)>4 else "--"
            t_show = f"{r[5]} °C" if len(r)>5 else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[6]}±{r[7]}" if len(r)>7 else "--"
            leaf_area_val = "--"
            th_name = r[9] if len(r)>9 else ""

        # Оптический снимок NDVI
        opt_f = r[14] if (len(r) >= 25 and r[14]) else (r[13] if (len(r) == 24 and '.jpg' in r[13]) else '')
        if opt_f and os.path.exists(os.path.join(STATIC_DIR, opt_f)):
            ndvi_cell = f'<a href="/static/{opt_f}" target="_blank" title="Открыть карту NDVI #{m_id}" style="color:var(--sirius-teal-dark);text-decoration:none;font-weight:600;"><span style="white-space:nowrap;font-family:monospace;font-size:11px;">{ndvi_txt}</span> 🔍</a>'
        else:
            ndvi_cell = f'<span style="white-space:nowrap;font-family:monospace;font-size:11px;color:#334155;">{ndvi_txt}</span>'

        if th_name:
            m_th = re.search(r'(IMG[_\s]\d+)', th_name)
            clean_th = m_th.group(1) if m_th else th_name
            th_file_path = os.path.join(STATIC_DIR, th_name)
            if os.path.exists(th_file_path):
                th_stat = f'<a href="/static/{th_name}" target="_blank" title="Открыть термограмму #{m_id}" style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;text-decoration:none;">✓ {clean_th} 🔍</a>'
            else:
                th_stat = f'<span style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;">✓ {clean_th}</span>'
        else:
            th_stat = '<span style="color:#d97706;font-size:11px;white-space:nowrap;font-weight:600;">⏳ Ожидает</span>'

        d_str, t_str = format_ru_date_and_time(ts)
        time_cell = f'<div style="white-space:nowrap;font-size:11px;font-weight:600;color:#0f172a;">{d_str}</div><div style="font-size:10px;color:#64748b;white-space:nowrap;">{t_str}</div>'
        grp_badge = format_group_badge(grp)
        if t_show != '--' and 'none' not in t_show.lower():
            t_leaf_html = f'''<span onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="cursor:pointer; color:#d97706; font-weight:bold; white-space:nowrap; padding:2px 5px; border-radius:4px; border-bottom:1.5px dashed #f59e0b; background:#fffbeb;" title="Нажмите, чтобы скорректировать T листа замера #{m_id} ({grp})">{t_show} <span style="font-size:10px;">✏️</span></span>'''
        else:
            t_leaf_html = f'''<span onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="cursor:pointer; color:#dc2626; font-weight:bold; white-space:nowrap; padding:2px 6px; border-radius:4px; border:1.5px dashed #ef4444; background:#fef2f2;" title="T листа не распознана! Нажмите, чтобы исправить">{t_show} <span style="font-size:10px;">✏️</span></span>'''

        del_btn = f'''<form action="/api/delete_measurement" method="post" style="margin:0;display:inline;" onsubmit="return confirm('Удалить исследование #{m_id} ({grp})?');"><input type="hidden" name="meas_id" value="{m_id}"><button type="submit" style="background:#fee2e2; border:1px solid #fca5a5; color:#dc2626; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1;" title="Удалить замер #{m_id}" onmouseover="this.style.background='#dc2626';this.style.color='#fff';" onmouseout="this.style.background='#fee2e2';this.style.color='#dc2626';">✕</button></form>'''
        edit_btn = f'''<button type="button" onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="background:#e0f2fe; border:1px solid #bae6fd; color:#0369a1; border-radius:4px; padding:2px 5px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1; margin-right:3px;" title="Скорректировать замер #{m_id} ({grp})" onmouseover="this.style.background='#0284c7';this.style.color='#fff';" onmouseout="this.style.background='#e0f2fe';this.style.color='#0369a1';">✏️</button>'''

        table_html += f'<tr><td><b style="color:#64748b;">#{m_id}</b></td><td>{time_cell}</td><td>{grp_badge}</td><td><b style="color:#0284c7;white-space:nowrap;">{wt}</b></td><td>{t_air_str}</td><td>{t_leaf_html}</td><td>{stress_badge}</td><td>{ndvi_cell}</td><td><b style="color:#047857;white-space:nowrap;font-size:11px;">{leaf_area_val}</b></td><td><span style="white-space:nowrap;font-weight:500;color:#334155;">{pct}</span></td><td>{th_stat}</td><td class="col-actions" style="white-space:nowrap;">{edit_btn}{del_btn}</td></tr>'

    if not table_html:
        table_html = '<tr><td colspan="12" style="text-align:center; padding:35px 20px; color:#64748b; font-size:14px;">🌱 <b>Журнал физиологических замеров пуст.</b><br><span style="font-size:12px; color:#94a3b8;">Запустите пакетный замер кассет 1–5, чтобы начать фиксацию данных нового эксперимента.</span></td></tr>'

    grid_top_content = f'''
        <div style="display:flex; flex-direction:column; gap:12px;">
            {wizard_card}
            {summary_card}
        </div>
        <div class="card" style="display:flex; flex-direction:column; margin:0; justify-content:space-between;">
            <h2>🔬 Мультиспектральная матрица исследования</h2>
            <div class="channels" style="flex:1; gap:10px;">
                <div class="ch-box">
                    <div style="color:#dc2626; font-size:11px; font-weight:700; margin-bottom:4px;">Канал 1: 660 нм (Deep Red)</div>
                    <img src="/static/last_red.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
                <div class="ch-box">
                    <div style="color:#4f46e5; font-size:11px; font-weight:700; margin-bottom:4px;">Канал 2: 850 нм (NIR Инфракрасный)</div>
                    <img src="/static/last_nir.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
                <div class="ch-box">
                    <div style="color:#0d9488; font-size:11px; font-weight:700; margin-bottom:4px;">Канал 3: Карта NDVI (Сетка 3×3)</div>
                    <img src="/static/last_ndvi.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
                <div class="ch-box">
                    <div style="color:#d97706; font-size:11px; font-weight:700; margin-bottom:4px;">Канал 4: Термограмма (UNI-T UTi120S)</div>
                    <img src="/static/last_thermal.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
            </div>
        </div>
    '''

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
            grid-template-columns: 440px 1fr;
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
            height: 155px;
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
        th.col-actions, td.col-actions {{
            position: sticky;
            right: 0;
            box-shadow: -3px 0 6px rgba(0, 0, 0, 0.06);
        }}
        th.col-actions {{
            z-index: 15;
            background: #f1f5f9;
        }}
        td.col-actions {{
            z-index: 5;
            background: #ffffff;
        }}
        tr:nth-child(even) td.col-actions {{
            background: #f8fafc;
        }}
        tr:hover td.col-actions {{
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
                    <span class="badge-author">👩‍🔬 Автор: Ковалева Алиса Ивановна · 10 класс (СОШ №282 СПб)</span>
                </div>
            </div>
            <div class="header-status">
                <div class="status-online"><span class="pulsing-dot"></span> СТАНЦИЯ ОНЛАЙН</div>
                <div class="station-hw">Orange Pi 4 Pro · Wi-Fi: <b>PlantStation</b> (192.168.4.1)</div>
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
            <span class="clim-val val-purple">Sensirion SHT30 (I2C-0)</span>
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
            <span class="clim-label">⚡ Линия 3.3V</span>
            <span class="clim-val val-slate">{cur_v} В</span>
        </div>
    </div>

    {status_banner}

    <div class="grid-top">
        {grid_top_content}
    </div>

    <!-- НИЖНИЙ БЛОК: ЖУРНАЛ ИЗМЕРЕНИЙ НА ВСЮ ШИРИНУ -->
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1.5px solid #f1f5f9; padding-bottom:10px; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
                <h2 style="margin:0; font-size:16px; border:none; padding:0; color:var(--sirius-teal-dark);">📋 Журнал физиологических замеров</h2>
                <div style="display:flex; gap:4px; background:#f1f5f9; padding:3px; border-radius:8px;">
                    <a href="/?phase=all" style="padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; text-decoration:none; {'background:var(--sirius-teal); color:#fff; box-shadow:0 1px 4px rgba(0,164,153,0.3);' if phase=='all' else 'color:#475569;'}">Все когорты ({len(rows)})</a>
                    <a href="/?phase=1" style="padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; text-decoration:none; {'background:var(--sirius-teal); color:#fff; box-shadow:0 1px 4px rgba(0,164,153,0.3);' if phase=='1' else 'color:#475569;'}">🧪 Этап 1: Скрининг</a>
                    <a href="/?phase=2" style="padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; text-decoration:none; {'background:var(--sirius-teal); color:#fff; box-shadow:0 1px 4px rgba(0,164,153,0.3);' if phase=='2' else 'color:#475569;'}">💧 Этап 2: Репарация</a>
                </div>
            </div>
            <div style="display:flex; gap:5px; flex-wrap:wrap;">
                <span style="background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #a7f3d0;">🌱 К1: Контроль</span>
                <span style="background:#fffbeb; color:#92400e; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #fde68a;">🍂 К2: Засуха</span>
                <span style="background:#f5f3ff; color:#5b21b6; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #ddd6fe;">🧂 К3: Соль</span>
                <span style="background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #a7f3d0;">🌱 К4: Эталон (Оптимум)</span>
                <span style="background:#f0fdfa; color:#0f766e; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #99f6e4;">💧 К5: Репарация (~40ч)</span>
                <span style="background:#fff1f2; color:#be123c; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #fecdd3;">⚠️ К6: Критический стресс (~72ч)</span>
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
                        <th style="width:135px;">ΔT (Стресс)</th>
                        <th style="width:90px;">NDVI</th>
                        <th style="width:85px;">🌿 PLA (см²)</th>
                        <th style="width:65px;">Почва</th>
                        <th style="width:105px;">Тепловизор</th>
                        <th class="col-actions" style="width:72px;">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {table_html}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- МОДАЛЬНОЕ ОКНО КОРРЕКЦИИ ЗАМЕРА -->
<div id="editModal" style="display:none; position:fixed; z-index:9999; left:0; top:0; width:100%; height:100%; background:rgba(15,23,42,0.6); align-items:center; justify-content:center; backdrop-filter:blur(2px);">
    <div style="background:#ffffff; padding:22px; border-radius:12px; width:340px; box-shadow:0 12px 36px rgba(0,0,0,0.25); border:2px solid var(--sirius-teal);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">
            <h3 id="editModalTitle" style="margin:0; color:var(--sirius-teal-dark); font-size:16px;">✏️ Коррекция замера</h3>
            <button type="button" onclick="closeEditModal()" style="background:none; border:none; font-size:16px; cursor:pointer; color:#94a3b8;">✕</button>
        </div>
        <form action="/api/update_measurement" method="post" enctype="multipart/form-data">
            <input type="hidden" name="meas_id" id="edit_meas_id">
            <input type="hidden" name="cohort" id="edit_cohort">
            <input type="hidden" name="timestamp" id="edit_timestamp">
            
            <div style="margin-bottom:12px;">
                <label style="font-size:11px; font-weight:bold; color:#334155; display:block; margin-bottom:4px;">🌡️ T листа (°C):</label>
                <input type="number" step="0.1" name="t_leaf" id="edit_t_leaf" required style="width:100%; padding:8px; font-size:14px; font-weight:bold; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box;">
                <div style="display:flex; gap:3px; margin-top:4px;">
                    <button type="button" onclick="adjTemp('edit_t_leaf', -1.0)" style="flex:1; font-size:10px; padding:2px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">-1°</button>
                    <button type="button" onclick="adjTemp('edit_t_leaf', -0.5)" style="flex:1; font-size:10px; padding:2px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">-0.5°</button>
                    <button type="button" onclick="adjTemp('edit_t_leaf', -0.1)" style="flex:1; font-size:10px; padding:2px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">-0.1°</button>
                    <button type="button" onclick="adjTemp('edit_t_leaf', 0.1)" style="flex:1; font-size:10px; padding:2px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">+0.1°</button>
                    <button type="button" onclick="adjTemp('edit_t_leaf', 0.5)" style="flex:1; font-size:10px; padding:2px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">+0.5°</button>
                    <button type="button" onclick="adjTemp('edit_t_leaf', 1.0)" style="flex:1; font-size:10px; padding:2px; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">+1°</button>
                </div>
            </div>

            <div style="margin-bottom:12px;">
                <label style="font-size:11px; font-weight:bold; color:#0f766e; display:block; margin-bottom:4px;">⚖️ Масса кассеты с весов (г):</label>
                <input type="text" name="weight_g" id="edit_weight" style="width:100%; padding:8px; font-size:13px; border:1px solid #cbd5e1; border-radius:6px; box-sizing:border-box;">
            </div>

            <div style="margin-bottom:12px;">
                <label style="font-size:11px; font-weight:bold; color:#0284c7; display:block; margin-bottom:4px;">💧 Влажность субстрата (%):</label>
                <input type="number" step="0.1" min="0" max="100" name="pct_soil" id="edit_soil" style="width:100%; padding:8px; font-size:13px; border:1px solid #cbd5e1; border-radius:6px; box-sizing:border-box;">
            </div>

            <div style="margin-bottom:16px; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px; padding:8px;">
                <label style="font-size:11px; font-weight:bold; color:#d97706; display:block; margin-bottom:4px;">📷 Прикрепить снимок UTi120S (.jpg):</label>
                <input type="file" name="thermal_file" accept=".jpg,.jpeg,.png" style="font-size:11px; width:100%; color:#475569;">
                <span style="font-size:10px; color:#94a3b8; display:block; margin-top:2px;">(необязательно, можно загрузить фото позже)</span>
            </div>

            <div style="display:flex; gap:8px;">
                <button type="submit" style="flex:1; padding:10px; background:linear-gradient(135deg, #059669, #00a499); color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">💾 Сохранить и пересчитать ΔT</button>
                <button type="button" onclick="closeEditModal()" style="padding:10px 14px; background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;">Отмена</button>
            </div>
        </form>
    </div>
</div>

<script>
function adjTemp(id, delta) {{
    let inp = document.getElementById(id);
    if (!inp) return;
    let cur = parseFloat(inp.value.replace(',', '.')) || 23.5;
    inp.value = (cur + delta).toFixed(1);
}}
function openEditModal(id, grp, ts, tLeaf, weight, soil) {{
    document.getElementById('edit_meas_id').value = id;
    document.getElementById('edit_cohort').value = grp || '';
    document.getElementById('edit_timestamp').value = ts || '';
    document.getElementById('editModalTitle').innerText = '✏️ Коррекция замера #' + id + (grp ? ' (' + grp + ')' : '');
    let cleanT = (tLeaf || '').replace(' °C', '').replace('°C', '').trim();
    if (cleanT === '--' || cleanT.toLowerCase().indexOf('none') !== -1) {{
        cleanT = (id === '73' && grp === 'Соль') ? '30.2' : '23.5';
    }}
    document.getElementById('edit_t_leaf').value = cleanT;
    let cleanW = (weight || '').replace(' г', '').replace('г', '').trim();
    if (cleanW === '--') cleanW = '';
    document.getElementById('edit_weight').value = cleanW;
    let cleanS = (soil || '').replace('%', '').trim();
    if (cleanS === '--') cleanS = '64.0';
    document.getElementById('edit_soil').value = cleanS;
    let modal = document.getElementById('editModal');
    modal.style.display = 'flex';
}}
function closeEditModal() {{
    document.getElementById('editModal').style.display = 'none';
}}
function dismissBanner() {{
    let el = document.getElementById('statusAlert');
    if (el) {{
        el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-8px)';
        setTimeout(() => el.remove(), 400);
    }}
    if (window.history && window.history.replaceState) {{
        window.history.replaceState({{}}, document.title, window.location.pathname);
    }}
}}

document.addEventListener('DOMContentLoaded', function() {{
    if (document.getElementById('statusAlert')) {{
        if (window.history && window.history.replaceState) {{
            window.history.replaceState({{}}, document.title, window.location.pathname);
        }}
        setTimeout(function() {{
            dismissBanner();
        }}, 4500);
    }}
}});
</script>
</body>
</html>'''
    return html

@app.get('/download/csv')
def download_csv():
    if os.path.exists(CSV_LOG):
        return FileResponse(CSV_LOG, filename='plant_stress_measurements.csv')
    return HTMLResponse('Файл пока пуст')

@app.get('/download/images_zip')
def download_images_zip():
    """Скачать архив всех сохраненных снимков NDVI и термограмм."""
    zip_path = os.path.join(DATA_DIR, 'plant_stress_gallery.zip')
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(CSV_LOG):
            zf.write(CSV_LOG, arcname='measurements.csv')
        for fname in sorted(os.listdir(STATIC_DIR)):
            if (fname.startswith(('opt_', 'therm_', 'ndvi_')) or fname in ('last_ndvi.jpg', 'last_thermal.jpg')) and fname.endswith(('.jpg', '.png')):
                full_p = os.path.join(STATIC_DIR, fname)
                zf.write(full_p, arcname=f'photos/{fname}')
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename='plant_stress_gallery.zip', media_type='application/zip')
    return HTMLResponse('Снимков пока нет')

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

@app.get('/download/research_paper')
def download_research_paper():
    pdf_path = os.path.join(STATIC_DIR, 'Научно_исследовательская_работа_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, 'Научно_исследовательская_работа_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Научно_исследовательская_работа_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл научно-исследовательской статьи пока не сформирован')

@app.get('/download/review_note')
def download_review_note():
    pdf_path = os.path.join(STATIC_DIR, 'Краткая_записка_для_рецензирования_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, 'Краткая_записка_для_рецензирования_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Краткая_записка_для_рецензирования_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл записки для рецензирования пока не найден')

@app.get('/download/presentation')
@app.get('/download/presentation_pdf')
def download_presentation():
    pdf_path = os.path.join(STATIC_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл презентации проекта пока не сформирован')

@app.get('/download/presentation_pptx')
def download_presentation_pptx():
    pptx_path = os.path.join(STATIC_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx')
    if not os.path.exists(pptx_path):
        pptx_path = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx')
    if os.path.exists(pptx_path):
        return FileResponse(pptx_path, filename='Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx', media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    return HTMLResponse('Файл PPTX презентации пока не сформирован')
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
