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

import asyncio
from concurrent.futures import ThreadPoolExecutor
from hardware.hal import get_climate_sensor, get_soil_sensor, get_relay_controller

import numexpr as ne

# Очередь для I2C запросов (защита от коллизий на шине)
i2c_executor = ThreadPoolExecutor(max_workers=1)

import os
import time
import json
import csv
import re
import glob
import math
import socket
from datetime import datetime
import subprocess
import numpy as np
from src.sensors_ads1115 import _global_reader
from src.profiler import profile_performance  # OPT: performance tracking
import cv2
try:
    import gpiod
    from gpiod.line import Direction, Value
    HAS_GPIOD = True
except ImportError:
    HAS_GPIOD = False
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi import Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
import zipfile
from PIL import Image
import pytesseract

from api.routes.downloads import router as downloads_router
from api.routes.experiments import router as experiments_router
from api.routes.measurements import router as measurements_router
from api.routes.batch import router as batch_router, init_batch_hardware
from core.station_state import (
    CASSETTE_CATALOG, ARUCO_CASSETTE_MAP, BATCH_CONFIG,
    BATCH_STATE, PENDING_SESSION,
    get_pending_session, set_pending_session, clear_pending_session,
    get_batch_state, reset_batch_state
)
from core.dashboard_view import build_dashboard_context
from core.experiments import get_experiment_manager
from core.xiaomi_climate import get_windowsill_climate

RELAY_REQ = None
app = FastAPI(title='Plant Stress Lab Gallery Station')

LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = LOCAL_DIR if os.path.exists(os.path.join(LOCAL_DIR, 'static')) else '/home/pi/plant-stress-ndvi'
DATA_DIR = os.path.join(BASE_DIR, 'data')
CALIBRATION_FILE = os.path.join(DATA_DIR, "calibrated_k_bal.txt")

def get_calibrated_k_bal() -> float:
    try:
        if os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, 'r', encoding='utf-8') as f:
                val = float(f.read().strip())
                if 0.5 <= val <= 10.0:
                    return round(val, 3)
    except Exception:
        pass
    return 4.070

def save_calibrated_k_bal(val: float):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CALIBRATION_FILE, 'w', encoding='utf-8') as f:
            f.write(f"{val:.3f}\n")
    except Exception as e:
        print(f"[Calib Save Error]: {e}")

def get_agronomic_ndvi_lut() -> np.ndarray:
    """
    Стандартная агрономическая палитра RdYlGn (Red-Yellow-Green):
    NDVI < 0.25 (фон, сухая биомасса, некроз) -> Красный
    NDVI 0.25..0.60 (умеренный стресс, замедление роста) -> Оранжевый/Желтый
    NDVI > 0.60 (активная вегетация, норма) -> Сочный насыщенный зеленый
    """
    lut = np.zeros((256, 1, 3), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        if t < 0.25:
            k = t / 0.25
            r = int(180 + k * 40)
            g = int(20 + k * 80)
            b = 20
        elif t < 0.60:
            k = (t - 0.25) / 0.35
            r = int(220 - k * 140)
            g = int(100 + k * 120)
            b = 25
        else:
            k = (t - 0.60) / 0.40
            r = int(80 - k * 60)
            g = int(220 - k * 30)
            b = int(25 + k * 30)
        lut[i, 0] = [b, g, r]  # BGR
    return lut

AGRONOMIC_NDVI_LUT = get_agronomic_ndvi_lut()

STATIC_DIR = os.path.join(BASE_DIR, 'static')
DOCS_DIR = os.path.join(BASE_DIR, 'docs')
TH_CACHE_DIR = os.path.join(STATIC_DIR, 'uti_cache')
UTI_DIR = '/media/uti120s/Images'

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(TH_CACHE_DIR, exist_ok=True)

CSV_LOG = os.path.join(DATA_DIR, 'measurements.csv')


# Сессии, каталог кассет и конфигурации импортированы выше из core.station_state

LAST_VALID_CLIMATE = (24.9, 65.7, 3.21)

def _read_climate_sync():
    """
    Синхронный опрос климата:
    1. Приоритет: Беспроводной датчик Xiaomi Mijia на подоконнике (зона растений),
       так как датчик SHT30 внутри закрытого оптического бокса нагревается от ламп/драйверов (~29°C).
    2. Fallback: Локальный I2C SHT30 в боксе (если шлюз Xiaomi временно недоступен).
    """
    global LAST_VALID_CLIMATE
    try:
        from core.xiaomi_climate import get_windowsill_climate
        win_c = get_windowsill_climate()
        if win_c and win_c.get('is_live') and win_c.get('t_c') is not None:
            t = round(float(win_c['t_c']), 1)
            rh = round(float(win_c['rh_pct']), 1)
            v_rail = round(float(win_c.get('battery_v', 3.15)), 2)
            LAST_VALID_CLIMATE = (t, rh, v_rail)
            return t, rh, v_rail
    except Exception:
        pass

    try:
        import smbus2
        with smbus2.SMBus(0) as bus:
            bus.write_i2c_block_data(0x44, 0x2C, [0x06])
            import time
            time.sleep(0.05)
            d = bus.read_i2c_block_data(0x44, 0x00, 6)
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
    return LAST_VALID_CLIMATE

async def read_climate_async():
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(i2c_executor, _read_climate_sync)

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
    """Форматирует название группы в яркий отличительный бейдж в строгом соответствии с цветами когорт."""
    if not grp_name:
        return '--'
    grp_lower = grp_name.strip().lower()

    # К1: Контроль (#1) — Зеленый (#059669 / #065f46)
    if 'контр' in grp_lower or 'control' in grp_lower or 'оптимум' in grp_lower or 'эталон' in grp_lower or '#1' in grp_lower:
        return f'<span style="background:#ecfdf5; color:#065f46; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # К2: Осмос (#2) — Фиолетовый (#7c3aed / #6d28d9)
    elif 'осмос' in grp_lower or 'osmo' in grp_lower or 'сол' in grp_lower or 'salin' in grp_lower or 'nacl' in grp_lower or '#2' in grp_lower:
        return f'<span style="background:#f5f3ff; color:#6d28d9; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #ddd6fe; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # К3: Засуха (#3) — Красный (#dc2626 / #be123c)
    elif 'засух' in grp_lower or 'drought' in grp_lower or 'терминал' in grp_lower or 'гибель' in grp_lower or 'некроз' in grp_lower or '#3' in grp_lower:
        return f'<span style="background:#fff1f2; color:#be123c; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fecdd3; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # К4: Превенция (#4) — Янтарный / Золотой (#ca8a04 / #b45309)
    elif 'превенци' in grp_lower or 'prevent' in grp_lower or 'прибор' in grp_lower or 'станци' in grp_lower or 'предиктив' in grp_lower or 'репар' in grp_lower or 'ранн' in grp_lower or '#4' in grp_lower:
        return f'<span style="background:#fffbeb; color:#b45309; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fde68a; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # К5: Реакция (#5) — Синий (#2563eb / #1d4ed8)
    elif 'реакци' in grp_lower or 'react' in grp_lower or 'глаз' in grp_lower or 'визуал' in grp_lower or 'органолепт' in grp_lower or 'тургор' in grp_lower or 'критич' in grp_lower or 'поздн' in grp_lower or '#5' in grp_lower:
        return f'<span style="background:#eff6ff; color:#1d4ed8; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #bfdbfe; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # К6: Калибровочный стенд — Серый (#64748b / #475569)
    elif 'калибро' in grp_lower or 'стенд' in grp_lower or '#6' in grp_lower:
        return f'<span style="background:#f1f5f9; color:#475569; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #cbd5e1; font-size:11px; white-space:nowrap;">{grp_name}</span>'

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


def init_relay():
    global RELAY_REQ
    try:
        from hardware.hal import get_relay_controller
        controller = get_relay_controller()
        RELAY_REQ = getattr(controller, 'request', None)
    except Exception:
        RELAY_REQ = None

def cleanup_gpio():
    """Безопасное отключение реле при выходе через абстракцию HAL."""
    get_relay_controller().cleanup()

def get_next_id() -> int:
    """O(1) ID via sidecar counter file instead of O(N) full CSV scan."""
    counter_path = os.path.join(DATA_DIR, '.id_counter')
    try:
        with open(counter_path, 'r') as _f:
            current = int(_f.read().strip())
    except (FileNotFoundError, ValueError):
        if not os.path.exists(CSV_LOG):
            current = 0
        else:
            with open(CSV_LOG, 'r', encoding='utf-8') as _f:
                current = max(0, sum(1 for _ in _f) - 1)  # lines minus header
    next_id = current + 1
    with open(counter_path, 'w') as _f:
        _f.write(str(next_id))
    return next_id

def extract_temperature_from_thermal(img_path: str):
    """
    OCR-распознавание температуры центральной точки из термограммы UTi120S.
    Использует мозаику 2x2 для 4 порогов за 1 вызов tesseract.
    Возвращает (temperature, is_valid).
    """
    try:
        img = cv2.imread(img_path)
        if img is None:
            return (None, False)
        crop = img[0:75, 0:145]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        
        # Строим мозаику 2x2
        thresholds = [210, 195, 225, 180]
        h, w = gray.shape
        mosaic = np.zeros((h*2, w*2), dtype=np.uint8)
        
        for idx, th_val in enumerate(thresholds):
            _, thresh = cv2.threshold(gray, th_val, 255, cv2.THRESH_BINARY)
            r, c = idx // 2, idx % 2
            mosaic[r*h:(r+1)*h, c*w:(c+1)*w] = thresh
            
        txt = pytesseract.image_to_string(mosaic, config='--psm 6 -c tessedit_char_whitelist=0123456789.,C°% \n')
        
        # Ищем все вхождения в мозаике
        for m in re.finditer(r'(\d{1,2})[\.,](\d)', txt):
            val = float(f"{m.group(1)}.{m.group(2)}")
            if 10.0 <= val <= 50.0:
                return (val, True)
                
        for m_int in re.finditer(r'\b(\d{3})\b', txt):
            val = float(m_int.group(1)) / 10.0
            if 10.0 <= val <= 50.0:
                return (val, True)
                
    except Exception as e:
        import logging
        logging.getLogger("OCR").error(f"[OCR Error]: {e}")
        
    return (None, False)
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

        # Настройка параметров детектора (фильтрация шумов матрицы)
        params = (
            cv2.aruco.DetectorParameters()
            if hasattr(cv2.aruco, 'DetectorParameters')
            else cv2.aruco.DetectorParameters_create()
        )
        params.adaptiveThreshWinSizeMin = 5
        params.adaptiveThreshWinSizeMax = 45
        params.adaptiveThreshWinSizeStep = 5
        params.minMarkerPerimeterRate = 0.04  # Защита от шума: периметр не менее 160 px
        params.maxMarkerPerimeterRate = 3.0
        params.polygonalApproxAccuracyRate = 0.05
        params.maxErroneousBitsInBorderRate = 0.25
        params.perspectiveRemoveIgnoredMarginPerCell = 0.13
        params.errorCorrectionRate = 0.6
        if hasattr(cv2.aruco, 'CORNER_REFINE_SUBPIX'):
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

        # Подготовка вариантов изображения для надежного распознавания:
        images_to_try = [gray]
        try:
            _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            images_to_try.append(otsu)
        except Exception:
            pass

        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            images_to_try.append(clahe.apply(gray))
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
                        # Проверка физической площади маркера (защита от фантомных артефактов матрицы)
                        c_area = float(cv2.contourArea(corners[i_idx].reshape((-1, 2)).astype(np.float32)))
                        if c_area < 250.0:
                            continue
                        if m_id in CASSETTE_CATALOG:
                            grp = CASSETTE_CATALOG[m_id]['name']
                            print(f"[ArUco Detected] Найдена кассета #{m_id}: {grp} (area={c_area:.0f}px, словарь {d_type})", flush=True)
                            return m_id, grp, corners[i_idx]
                        elif 1 <= m_id <= 6:
                            grp = ARUCO_CASSETTE_MAP.get(m_id, f'Кассета #{m_id}')
                            print(f"[ArUco Detected] Найдена кассета #{m_id}: {grp} (area={c_area:.0f}px)", flush=True)
                            return m_id, grp, corners[i_idx]
    except Exception as e:
        print('[ArUco Detect Error]:', e, flush=True)
    return None, None, None

def auto_mount_uti():
    """Монтирование USB накопителя тепловизора UTi120S по аппаратному ID."""
    try:
        if os.path.exists(UTI_DIR) and len(os.listdir(UTI_DIR)) > 0:
            return True
    except Exception:
        subprocess.run(['sudo','umount','-l','/media/uti120s'], capture_output=True)  # OPT

    uti_devs = glob.glob('/dev/disk/by-id/usb-STM_UTi120S_*-part1')
    candidate_devs = uti_devs + ['/dev/sdb1', '/dev/sda1', '/dev/sdc1', '/dev/sdd1']

    for dev in candidate_devs:
        if os.path.exists(dev):
            os.makedirs('/media/uti120s', exist_ok=True)
            subprocess.run(['sudo','umount','-l','/media/uti120s'], capture_output=True)  # OPT
            subprocess.run(['sudo','mount','-o','ro',dev,'/media/uti120s'], capture_output=True, timeout=5)  # OPT: no shell injection
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
    t_ocr, ocr_valid = extract_temperature_from_thermal(thumb_path) if os.path.exists(thumb_path) else (None, False)
    if t_ocr is None: t_ocr = 23.5

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

@profile_performance
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

    # Спектральная съемка Logitech C270: 1280x960 (полный сенсор 4:3 без кропа)
    def set_v4l2_exposure(exp_val, gain_val):
        try:
            subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '-c', 
                            f'auto_exposure=1,exposure_time_absolute={exp_val},gain={gain_val},white_balance_automatic=0'], 
                           check=False)
        except Exception:
            pass

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

    init_relay()
    if True:
        # 1. Спектральная съемка NIR 850 нм (высокая экспозиция для преодоления ИК-фильтра C270)
        # 1. Спектральная съемка NIR 850 нм (оптимальная экспозиция 2500/200 под C270 NoIR)
        set_v4l2_exposure(2500, 200)
        time.sleep(0.20)
        get_relay_controller().set_nir(True)
        time.sleep(0.40)
        for _ in range(8): cap.grab()
        ret_n, frame_nir = cap.read()
        get_relay_controller().set_nir(False) # Инфракрасный выключен

        # Темновой фон NIR
        time.sleep(0.15)
        for _ in range(5): cap.grab()
        _, frame_amb_nir = cap.read()

        # 2. Спектральная съемка RED 660 нм (калиброванная экспозиция 120/40 без клиппинга)
        set_v4l2_exposure(120, 40)
        time.sleep(0.20)
        for _ in range(8): cap.grab()
        get_relay_controller().set_red(True)
        time.sleep(0.40)
        for _ in range(8): cap.grab()
        ret_r, frame_red = cap.read()
        get_relay_controller().set_red(False) # Красный выключен

        # Темновой фон RED
        time.sleep(0.15)
        for _ in range(5): cap.grab()
        _, frame_amb_red = cap.read()

        if not ret_r: frame_red = frame_amb_red
        if not ret_n: frame_nir = frame_amb_nir
        frame_amb = frame_amb_red
    else:
        set_v4l2_exposure(2500, 200)
        for _ in range(5): cap.grab()
        ret, frame_amb_nir = cap.read()
        frame_red = frame_amb_nir
        frame_nir = frame_amb_nir
        frame_amb_red = frame_amb_nir
        frame_amb = frame_amb_nir

    cap.release()
    # Возвращаем камеру в штатный режим
    try:
        subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '-c', 'auto_exposure=3'], check=False)
    except Exception:
        pass

    frame_flash = frame_red

    # Оптическая детекция ArUco-маркера кассеты NoIR-камерой:
    # 1) Сначала по NIR-кадру (максимальный контраст черного углеродного тонера и белой бумаги под 850 нм)
    aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_nir)
    # 2) Если не найдено - по кадру RED 660 нм
    if aruco_id is None:
        aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_red)
    # 3) Если не найдено - по фоновому ambient
    if aruco_id is None:
        aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_amb)
    if aruco_id is not None:
        group_name = aruco_group
        print(f'[ArUco Optical Link] Авто-привязка кассеты: Маркер #{aruco_id} -> {group_name}', flush=True)

    # ЧЕСТНОЕ АППАРАТНОЕ РАЗДЕЛЕНИЕ КАНАЛОВ (БЕЗ ПРОГРАММНОЙ АППРОКСИМАЦИИ):
    # Канал 660 нм: чистый красный подуровень матрицы под узкополосным светом 660 нм
    red_raw = frame_red[:, :, 2].astype(np.float32)
    # Канал 850 нм: интегральный отклик матрицы NoIR под узкополосным ИК-светом 850 нм
    nir_raw = frame_nir.astype(np.float32).mean(axis=2)  # OPT: 7 passes -> 1

    # Вычитание фоновой фотометрической засветки с учетом индивидуальных темновых кадров
    amb_red = frame_amb_red[:, :, 2].astype(np.float32)
    amb_nir = frame_amb_nir.astype(np.float32).mean(axis=2)  # OPT: vectorized

    red_channel = np.maximum(0.0, red_raw - amb_red)
    nir_channel = np.maximum(0.0, nir_raw - amb_nir)

    # Радиометрическая калибровка по белому диффузному эталону (White Reference Target)
    h_f, w_f, _ = frame_flash.shape
    is_calib_stand = (group_name in ['Калибровка (Стенд №0)', 'Калибровка'] or (aruco_id is not None and aruco_id == 6))

    if is_calib_stand:
        # Режим Стенда №0: ищем центральную диффузную мишень (ФУМ-эталон)
        blur_sig = cv2.GaussianBlur(red_channel + nir_channel, (15, 15), 0)
        _, _, _, max_loc = cv2.minMaxLoc(blur_sig)
        px, py = max_loc
        hb = 45
        roi_x1, roi_x2 = max(0, px - hb), min(w_f, px + hb)
        roi_y1, roi_y2 = max(0, py - hb), min(h_f, py + hb)
    else:
        # Штатный замер кассет: проверяем контрольную угловую зону
        roi_y1, roi_y2 = int(h_f * 0.04), int(h_f * 0.16)
        roi_x1, roi_x2 = int(w_f * 0.04), int(w_f * 0.16)

    white_red = float(np.mean(red_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    white_nir = float(np.mean(nir_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    
    # Допустимый диапазон отношения Red/NIR для NoIR-камеры [0.5 ... 8.0]
    is_valid_white = (white_nir > 15.0 and white_red > 25.0 and 0.50 <= (white_red / white_nir) <= 8.00)

    if is_valid_white:
        k_bal = round(float(np.clip(white_red / white_nir, 0.50, 8.00)), 3)
        if is_calib_stand:
            save_calibrated_k_bal(k_bal)
            print(f'[Calibration Stand #0] Откалиброван и сохранен k_bal = {k_bal}', flush=True)
    else:
        # Автоматическая загрузка сохраненного физического баланса (4.07)
        k_bal = get_calibrated_k_bal()

    # Калиброванная формула NDVI с учетом балансировочного коэффициента эмиттеров
    if red_channel.dtype != np.float32: red_channel = red_channel.astype(np.float32)
    if nir_channel.dtype != np.float32: nir_channel = nir_channel.astype(np.float32)
    # Использование NumExpr для Zero-copy вычислений и экономии RAM
    ndvi_map = ne.evaluate('(k_bal * nir_channel - red_channel) / (k_bal * nir_channel + red_channel + 1e-8)')
    ndvi_map = np.clip(ndvi_map, -1.0, 1.0)

    # Сегментация проективной листовой поверхности (Projected Leaf Area, PLA)
    # Живой хлорофилл/мезофилл: уверенный порог NDVI > 0.28 (отсекает почву 0.0-0.2, пластик и тени)
    # + выраженный сигнал отражения NIR над темновым шумом (> 22.0 DN)
    leaf_mask = ((ndvi_map > 0.28) & (nir_channel > 22.0)).astype(np.uint8)
    if is_valid_white:
        leaf_mask[roi_y1:roi_y2, roi_x1:roi_x2] = 0

    # 1. Полное геометрическое исключение маркера ArUco вместе с белой бумажной подложкой (расширение на 45%)
    if aruco_corners is not None:
        pts_poly = aruco_corners.reshape((-1, 2)).astype(np.float32)
        center_ar = np.mean(pts_poly, axis=0)
        expanded_poly = ((pts_poly - center_ar) * 1.45 + center_ar).astype(np.int32)
        cv2.fillPoly(leaf_mask, [expanded_poly.reshape((-1, 1, 2))], 0)

    # 2. Исключение паразитных краевых зон (стыки стенок, петли крышки бокса: верх 5%, низ 3%, бока 3%)
    margin_top = int(h_f * 0.05)
    margin_bot = int(h_f * 0.03)
    margin_side = int(w_f * 0.03)
    leaf_mask[:margin_top, :] = 0
    leaf_mask[h_f - margin_bot:, :] = 0
    leaf_mask[:, :margin_side] = 0
    leaf_mask[:, w_f - margin_side:] = 0

    # 3. Морфологическая фильтрация: удаление мелкого точечного шума матрицы (ядро 3x3)
    kernel_noise = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_OPEN, kernel_noise)

    print(f'[DEBUG Capture] NIR: mean={nir_raw.mean():.1f}, p90={np.percentile(nir_raw, 90):.1f}, amb={amb_nir.mean():.1f}', flush=True)
    print(f'[DEBUG Capture] RED: mean={red_raw.mean():.1f}, p90={np.percentile(red_raw, 90):.1f}, amb={amb_red.mean():.1f}', flush=True)
    print(f'[DEBUG Capture] k_bal={k_bal}, ndvi: mean={ndvi_map.mean():.3f}, max={ndvi_map.max():.3f}, leaf_mask={np.sum(leaf_mask)}', flush=True)

    # Визуализаторы:
    # Адаптивная контрастная нормализация Красного канала (660 нм) для оператора (CLAHE):
    p_high_r = float(np.percentile(red_channel, 99.5))
    if p_high_r > 5.0:
        vis_red_mono = np.clip((red_channel / p_high_r) * 255.0, 0, 255).astype(np.uint8)
        clahe_red = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        vis_red_mono = clahe_red.apply(vis_red_mono)
        vis_red = np.zeros_like(frame_red)
        vis_red[:, :, 2] = vis_red_mono
        vis_red[:, :, 0] = (vis_red_mono * 0.15).astype(np.uint8)
        vis_red[:, :, 1] = (vis_red_mono * 0.05).astype(np.uint8)
    else:
        vis_red = frame_red.copy()


    # Адаптивное автоконтрастирование ИК-канала для наглядного отображения на экране:
    p_high = float(np.percentile(nir_channel, 99.5))
    if p_high > 6.0:
        vis_nir_mono = np.clip((nir_channel / p_high) * 255.0, 0, 255).astype(np.uint8)
        clahe_nir = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        vis_nir_mono = clahe_nir.apply(vis_nir_mono)
        vis_nir = cv2.cvtColor(vis_nir_mono, cv2.COLOR_GRAY2BGR)
    else:
        vis_nir = frame_nir.copy()

    # Агрономическая палитра вегетации RdYlGn (Красный = деградация/стресс -> Желтый -> Насыщенный зеленый):
    ndvi_disp = np.clip((ndvi_map - 0.20) / 0.65 * 255.0, 0, 255).astype(np.uint8)
    vis_ndvi_color = cv2.LUT(cv2.cvtColor(ndvi_disp, cv2.COLOR_GRAY2BGR), AGRONOMIC_NDVI_LUT)
    vis_ndvi_color[leaf_mask == 0] = [35, 15, 30] # Темный нейтральный фон для почвы и фона бокса

    h, w, _ = frame_flash.shape
    cell_h, cell_w = h // 3, w // 3
    annotated_ndvi = vis_ndvi_color.copy()

    # Отрисовка зоны радиометрической калибровки White Reference (только если найден реальный эталон)
    if is_valid_white:
        cv2.rectangle(annotated_ndvi, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 255, 255), 2)
        cv2.putText(annotated_ndvi, f'White Ref: k={k_bal}', (roi_x1, max(22, roi_y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'White Ref: k={k_bal}', (roi_x1, max(22, roi_y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
    else:
        # Размещаем в правом верхнем углу под PLA (без наложения на ячейку #1)
        cv2.putText(annotated_ndvi, f'Calib: k={k_bal}', (w - 260, max(26, roi_y1 + 36)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'Calib: k={k_bal}', (w - 260, max(26, roi_y1 + 36)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 255, 200), 1)

    # Отрисовка обнаруженного фидуциального маркера ArUco
    if aruco_corners is not None and aruco_id is not None:
        pts = aruco_corners.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(annotated_ndvi, [pts], True, (0, 255, 128), 3)
        cx = int(np.mean(pts[:, 0, 0]))
        cy = int(np.mean(pts[:, 0, 1]))
        cv2.putText(annotated_ndvi, f'ArUco #{aruco_id}', (max(10, cx - 50), max(30, cy - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'ArUco #{aruco_id}', (max(10, cx - 50), max(30, cy - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 128), 2)

    # ---------------- МОРФОЛОГИЧЕСКИЙ АНАЛИЗ (PLA - Площадь Листьев) ----------------
    # 1. Субпиксельная калибровка масштаба по ArUco-маркеру (15x15 мм = 2.25 см²)
    # 2. Оптическая перспективная Z-компенсация высоты полога гороха:
    #    Z_marker ≈ 24.5 см (дно/клипса кассеты), H_canopy ≈ 10.0 см (ярус листьев) -> k_z = (14.5 / 24.5)² ≈ 0.350
    ARUCO_REAL_AREA_CM2 = 2.25
    Z_CAMERA_MARKER_CM = 24.5
    CANOPY_HEIGHT_CM = 10.0
    k_perspective = float(((Z_CAMERA_MARKER_CM - CANOPY_HEIGHT_CM) / Z_CAMERA_MARKER_CM) ** 2)

    if aruco_corners is not None:
        pts_fl = aruco_corners.reshape((-1, 2)).astype(np.float32)
        aruco_area_px = float(cv2.contourArea(pts_fl))
        if aruco_area_px > 120.0:
            scale_marker = ARUCO_REAL_AREA_CM2 / aruco_area_px
            px_to_cm2 = float(np.clip(scale_marker * k_perspective, 0.00004, 0.00015))
        else:
            px_to_cm2 = 0.00008
    else:
        # Номинальный калиброванный масштаб бокса 1280x960 с учетом Z-перспективы
        px_to_cm2 = 0.00008

    total_leaf_px = int(np.count_nonzero(leaf_mask))
    leaf_area_total = round(float(total_leaf_px * px_to_cm2), 1)

    # Отрисовка суммарной площади PLA на карте
    cv2.putText(annotated_ndvi, f'PLA: {leaf_area_total} cm2', (w - 260, max(26, roi_y1 + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3)
    cv2.putText(annotated_ndvi, f'PLA: {leaf_area_total} cm2', (w - 260, max(26, roi_y1 + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2)

    # OPT: vectorized 3x3 grid — NumPy reshape, no Python loop overhead
    _G = 3
    _nd_g = ndvi_map[:cell_h*_G, :cell_w*_G].reshape(_G, cell_h, _G, cell_w).transpose(0, 2, 1, 3)
    _mk_g = leaf_mask[:cell_h*_G, :cell_w*_G].reshape(_G, cell_h, _G, cell_w).transpose(0, 2, 1, 3)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        _masked = np.where(_mk_g > 0, _nd_g, np.nan).reshape(_G, _G, -1)
        _ndvi_grid = np.nan_to_num(np.nanmean(_masked, axis=2), nan=0.0)
    _area_grid = _mk_g.reshape(_G, _G, -1).sum(axis=2) * px_to_cm2
    cell_areas = [round(float(v), 1) for v in _area_grid.ravel()]
    cell_ndvis = [round(float(v), 3) for v in _ndvi_grid.ravel()]

    for r in range(3):
        for c in range(3):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            idx = r * 3 + c
            c_area = cell_areas[idx]
            cell_val = cell_ndvis[idx]

            cv2.rectangle(annotated_ndvi, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(annotated_ndvi, f'#{r*3+c+1}: {cell_val}', (x1 + 12, y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
            cv2.putText(annotated_ndvi, f'#{r*3+c+1}: {cell_val}', (x1 + 12, y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(annotated_ndvi, f'{c_area} cm2', (x1 + 12, y1 + 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
            cv2.putText(annotated_ndvi, f'{c_area} cm2', (x1 + 12, y1 + 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 255, 200), 1)

    # Честный средневзвешенный расчет NDVI по всем пикселям листьев кассеты:
    leaf_pixels_ndvi = ndvi_map[leaf_mask > 0]
    if len(leaf_pixels_ndvi) > 0:
        mean_ndvi = round(float(np.mean(leaf_pixels_ndvi)), 3)
        std_ndvi = round(float(np.std(leaf_pixels_ndvi)), 3)
    else:
        mean_ndvi = 0.000
        std_ndvi = 0.000

    print(f'[Spectral Capture] ID #{meas_id} [{group_name}]: leaves={total_leaf_px} px ({leaf_area_total} cm2), NDVI mean={mean_ndvi}, cells={cell_ndvis}', flush=True)

    opt_filename = f'opt_{meas_id}_{group_name}_{ts_str}.jpg'
    cv2.imwrite(os.path.join(STATIC_DIR, opt_filename), annotated_ndvi)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_red.jpg'), vis_red)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_nir.jpg'), vis_nir)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_ndvi.jpg'), annotated_ndvi)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_amb.jpg'), frame_amb)
    cv2.imwrite(os.path.join(STATIC_DIR, 'last_flash_raw.jpg'), frame_flash)

    try:
        from src.sensors_ads1115 import SoilMoistureReader
        _reader = SoilMoistureReader()
        v_soil, pct_soil = _reader.get_active_moisture(group_name)
        if v_soil is None:
            v_soil, pct_soil = '', ''
    except Exception:
        v_soil, pct_soil = '', ''

    win_c = get_windowsill_climate()
    if win_c and win_c.get('is_live') and win_c.get('t_c') is not None:
        air_t = round(float(win_c['t_c']), 1)
        air_rh = round(float(win_c['rh_pct']), 1)
    else:
        live_t, live_rh, _ = _read_climate_sync()
        air_t = live_t
        air_rh = live_rh
    cur_vpd = calc_vpd(air_t, air_rh)

    PENDING_SESSION = {
        'id': meas_id,
        'timestamp': ts_display,
        'group': group_name,
        'aruco_id': aruco_id,
        't_air': air_t,
        'rh_air': air_rh,
        't_air_win': air_t,
        'rh_air_win': air_rh,
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
    set_pending_session(PENDING_SESSION)
    return PENDING_SESSION

# ----------------- РЕГИСТРАЦИЯ МОДУЛЬНЫХ МАРШРУТОВ (APIRouter) -----------------
app.include_router(downloads_router)
app.include_router(experiments_router)
app.include_router(measurements_router)
app.include_router(batch_router)

init_batch_hardware(
    spectral_capture_fn=do_hardware_spectral_capture,
    auto_mount_fn=auto_mount_uti,
    get_uti_files_fn=get_uti_sorted_files,
    extract_temp_fn=extract_temperature_from_thermal,
    init_relay_fn=init_relay,
    get_relay_req_fn=lambda: RELAY_REQ,
    format_ru_datetime_fn=format_ru_datetime
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get('/', response_class=HTMLResponse)
async def index(
    request: Request,
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
    context = await build_dashboard_context(
        request=request,
        stage=stage,
        offset=offset,
        msg=msg,
        last_grp=last_grp,
        del_id=del_id,
        upd_id=upd_id,
        phase=phase,
        found=found,
        stage_name=stage_name,
        dup_id=dup_id,
        dup_name=dup_name,
        wrong_id=wrong_id,
        expected=expected,
        exp_id=exp_id,
        exp_name=exp_name,
        get_uti_info_fn=get_file_info_at_index
    )
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)

app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
