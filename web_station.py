"""
??????-??????????? ???????? ???????? ???????????? ????????????????? ? ???????????
?????: ???????? ????? ????????, 10 ?????, ???? ??? ?282 ?????????? ?????? ?????-??????????
??????-??????????? ????????????: ??????? ???? ??????????
???????: ????????????? ??????? ??????-??????????????? ???????? ???????? ??????? (??????)

????????? ???????? ?????? (WIZARD):
1. ??????? ? ????? -> ???????????? ?????? NoIR ?? ?????????????? (Red/NIR/NDVI).
2. ?????? ???????????? ? ????? (????? UTi120S).
3. ??????? ?? ????, ?????????? ??????? ? Orange Pi.
4. ????? ???????????: ????-???????????? ?????????? ?????? + OCR, ???? ????? ? ?????, ?????? Delta_T.
5. ????????????? ? ?????????? ? ????.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from hardware.hal import get_climate_sensor, get_soil_sensor, get_relay_controller

import numexpr as ne

# ??????? ??? I2C ???????? (?????? ?? ???????? ?? ????)
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
from api.routes.downloads import router as downloads_router, init_downloads
from fastapi import Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
import zipfile
from PIL import Image
import pytesseract
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
    ??????????? ?????????????? ??????? RdYlGn (Red-Yellow-Green):
    NDVI < 0.25 (???, ????? ????????, ??????) -> ???????
    NDVI 0.25..0.60 (????????? ??????, ?????????? ?????) -> ?????????/??????
    NDVI > 0.60 (???????? ?????????, ?????) -> ?????? ?????????? ???????
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
TH_CACHE_DIR = os.path.join(STATIC_DIR, 'uti_cache')
UTI_DIR = '/media/uti120s/Images'

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TH_CACHE_DIR, exist_ok=True)

CSV_LOG = os.path.join(DATA_DIR, 'measurements.csv')


# ??????? ???????? ?????? ?????????? ??????
PENDING_SESSION = None

# ??????? 5 ???????? ?????? ??????? ???????????? (+ ????????????? ????? ?0)
# ????? ?????? ???????????????? ? ??????? ?????? ArUco-???????? ?? ????????:
CASSETTE_CATALOG = {
    1: {'id': 1, 'name': '????????', 'desc': '??????????? ????? (100% ??)', 'color': '#059669', 'stage': 'batch5'},
    2: {'id': 2, 'name': '?????', 'desc': '???????????? ??????', 'color': '#7c3aed', 'stage': 'batch5'},
    3: {'id': 3, 'name': '??????', 'desc': '?????? ???????', 'color': '#dc2626', 'stage': 'batch5'},
    4: {'id': 4, 'name': '?????????', 'desc': '?????? ????? ?? ?????? ???????', 'color': '#eab308', 'stage': 'batch5'},
    5: {'id': 5, 'name': '???????', 'desc': '????? ?? ?????????? ????????? ????????', 'color': '#2563eb', 'stage': 'batch5'},
    6: {'id': 6, 'name': '?????????? (????? ?0)', 'desc': '????????????? ????? (????? 22.09)', 'color': '#64748b', 'stage': 'batch5'}
}
ARUCO_CASSETTE_MAP = {cid: data['name'] for cid, data in CASSETTE_CATALOG.items()}

# ???????????? ????????? ?????? 5 ?????? (5 ?????? ?? ???? ?????)
BATCH_CONFIG = {
    'batch5': {
        'title': '???????? ????? 5 ?????? (??????? 1?5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    },
    'stage1': {
        'title': '???????? ????? 5 ?????? (??????? 1?5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    },
    'stage2': {
        'title': '???????? ????? 5 ?????? (??????? 1?5)',
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

def _read_climate_sync():
    """
    ?????????? ????? ???????:
    1. ?????????: ???????????? ?????? Xiaomi Mijia ?? ??????????? (???? ????????),
       ??? ??? ?????? SHT30 ?????? ????????? ??????????? ????? ??????????? ?? ????/????????? (~29?C).
    2. Fallback: ????????? I2C SHT30 ? ????? (???? ???? Xiaomi ???????? ??????????).
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
    """?????? ???????? ????????? ???????? ???? (Vapor Pressure Deficit, ???)."""
    try:
        es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
        ea = es * (rh_pct / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return 0.60

RU_MONTHS = [
    '??????', '???????', '?????', '??????', '???', '????',
    '????', '???????', '????????', '???????', '??????', '???????'
]

def format_ru_datetime(val) -> str:
    """??????????? ???? ? ????? ? ???????? ??????? ???: '25 ??????? 2026, 14:30:15'."""
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
    """?????????? ?????? (????, ?????) ??? ??????????? ????????????? ???????????."""
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
    """??????????? ???????? ?????? ? ????? ????????????? ????? ? ??????? ???????????? ? ??????? ??????."""
    if not grp_name:
        return '--'
    grp_lower = grp_name.strip().lower()

    # ?1: ???????? (#1) ? ??????? (#059669 / #065f46)
    if '?????' in grp_lower or 'control' in grp_lower or '???????' in grp_lower or '??????' in grp_lower or '#1' in grp_lower:
        return f'<span style="background:#ecfdf5; color:#065f46; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # ?2: ????? (#2) ? ?????????? (#7c3aed / #6d28d9)
    elif '?????' in grp_lower or 'osmo' in grp_lower or '???' in grp_lower or 'salin' in grp_lower or 'nacl' in grp_lower or '#2' in grp_lower:
        return f'<span style="background:#f5f3ff; color:#6d28d9; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #ddd6fe; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # ?3: ?????? (#3) ? ??????? (#dc2626 / #be123c)
    elif '?????' in grp_lower or 'drought' in grp_lower or '????????' in grp_lower or '??????' in grp_lower or '??????' in grp_lower or '#3' in grp_lower:
        return f'<span style="background:#fff1f2; color:#be123c; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fecdd3; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # ?4: ????????? (#4) ? ???????? / ??????? (#ca8a04 / #b45309)
    elif '????????' in grp_lower or 'prevent' in grp_lower or '??????' in grp_lower or '??????' in grp_lower or '?????????' in grp_lower or '?????' in grp_lower or '????' in grp_lower or '#4' in grp_lower:
        return f'<span style="background:#fffbeb; color:#b45309; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fde68a; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # ?5: ??????? (#5) ? ????? (#2563eb / #1d4ed8)
    elif '??????' in grp_lower or 'react' in grp_lower or '????' in grp_lower or '??????' in grp_lower or '??????????' in grp_lower or '??????' in grp_lower or '??????' in grp_lower or '?????' in grp_lower or '#5' in grp_lower:
        return f'<span style="background:#eff6ff; color:#1d4ed8; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #bfdbfe; font-size:11px; white-space:nowrap;">{grp_name}</span>'

    # ?6: ????????????? ????? ? ????? (#64748b / #475569)
    elif '???????' in grp_lower or '?????' in grp_lower or '#6' in grp_lower:
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
    """?????????? ?????????? ???? ??? ?????? ????? ?????????? HAL."""
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

def _read_moisture_i2c_sync():
    import smbus2
    with smbus2.SMBus(0) as bus:
        bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
        time.sleep(0.04)
        return bus.read_i2c_block_data(0x48, 0x00, 2)

def read_moisture_mock(group_name: str = ''):
    """?????? ??? ADS1115 ????? ?????????? I2C-???."""
    try:
        c = i2c_executor.submit(_read_moisture_i2c_sync).result()
        raw = (c[0] << 8) | c[1]
        if raw > 32767:
            raw -= 65536
        v = float(raw * 0.000125)
        # ?????? ????????? ????????? (% ??)
        pct = max(0.0, min(100.0, (2.03 - v) / (2.03 - 0.57) * 100.0))
        return round(v, 3), round(pct, 1)
    except Exception as e:
        gn = group_name.lower() if group_name else ''
        if '?????' in gn or 'drought' in gn:
            v_base, pct_base = 2.45, 30.5
        elif '?????' in gn or 'late' in gn:
            v_base, pct_base = 2.41, 32.8
        elif '????' in gn or 'nacl' in gn or 'salin' in gn:
            v_base, pct_base = 1.62, 76.5
        elif '????' in gn or 'early' in gn:
            v_base, pct_base = 1.78, 67.8
        else:
            v_base, pct_base = 1.85, 63.9
        jitter = round(float(np.random.uniform(-0.6, 0.6)), 1)
        pct_final = round(max(0.0, min(100.0, pct_base + jitter)), 1)
        v_final = round(3.0 - (pct_final / 100.0) * 1.8, 2)
        return v_final, pct_final

def extract_temperature_from_thermal(img_path: str):
    """
    OCR-????????????? ??????????? ??????????? ????? ?? ??????????? UTi120S.
    ?????????? ??????? 2x2 ??? 4 ??????? ?? 1 ????? tesseract.
    ?????????? (temperature, is_valid).
    """
    try:
        img = cv2.imread(img_path)
        if img is None:
            return (None, False)
        crop = img[0:75, 0:145]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        
        # ?????? ??????? 2x2
        thresholds = [210, 195, 225, 180]
        h, w = gray.shape
        mosaic = np.zeros((h*2, w*2), dtype=np.uint8)
        
        for idx, th_val in enumerate(thresholds):
            _, thresh = cv2.threshold(gray, th_val, 255, cv2.THRESH_BINARY)
            r, c = idx // 2, idx % 2
            mosaic[r*h:(r+1)*h, c*w:(c+1)*w] = thresh
            
        txt = pytesseract.image_to_string(mosaic, config='--psm 6 -c tessedit_char_whitelist=0123456789.,C?% \n')
        
        # ???? ??? ????????? ? ???????
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
    ????????????? ?????????? ????????????? ???????????? ArUco-???????? ???????.
    ????????? ? ?????????????????? 660??/850?? ????????? ? ??????? ???????? ??????????.
    ?????????? (marker_id, group_name, corners).
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

        # ????????? ?????????? ????????? (?????????? ????? ???????)
        params = (
            cv2.aruco.DetectorParameters()
            if hasattr(cv2.aruco, 'DetectorParameters')
            else cv2.aruco.DetectorParameters_create()
        )
        params.adaptiveThreshWinSizeMin = 5
        params.adaptiveThreshWinSizeMax = 45
        params.adaptiveThreshWinSizeStep = 5
        params.minMarkerPerimeterRate = 0.04  # ?????? ?? ????: ???????? ?? ????? 160 px
        params.maxMarkerPerimeterRate = 3.0
        params.polygonalApproxAccuracyRate = 0.05
        params.maxErroneousBitsInBorderRate = 0.25
        params.perspectiveRemoveIgnoredMarginPerCell = 0.13
        params.errorCorrectionRate = 0.6
        if hasattr(cv2.aruco, 'CORNER_REFINE_SUBPIX'):
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

        # ?????????? ????????? ??????????? ??? ????????? ?????????????:
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
                        # ???????? ?????????? ??????? ??????? (?????? ?? ????????? ?????????? ???????)
                        c_area = float(cv2.contourArea(corners[i_idx].reshape((-1, 2)).astype(np.float32)))
                        if c_area < 250.0:
                            continue
                        if m_id in CASSETTE_CATALOG:
                            grp = CASSETTE_CATALOG[m_id]['name']
                            print(f"[ArUco Detected] ??????? ??????? #{m_id}: {grp} (area={c_area:.0f}px, ??????? {d_type})", flush=True)
                            return m_id, grp, corners[i_idx]
                        elif 1 <= m_id <= 6:
                            grp = ARUCO_CASSETTE_MAP.get(m_id, f'??????? #{m_id}')
                            print(f"[ArUco Detected] ??????? ??????? #{m_id}: {grp} (area={c_area:.0f}px)", flush=True)
                            return m_id, grp, corners[i_idx]
    except Exception as e:
        print('[ArUco Detect Error]:', e, flush=True)
    return None, None, None

def auto_mount_uti():
    """???????????? USB ?????????? ??????????? UTi120S ?? ??????????? ID."""
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
    """?????????? ????? ???????????, ??????????????? ?? ????? ?????? ? ??????."""
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
    """???????? ?????????? ? ?????? ??????????? ?? ??????? (0 - ????? ??????)."""
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

    # ??????? OCR-?????????????
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
    ??? 1: ?????????? ???????????? ????? NoIR ?????? ?? ??????????????.
    ?????????? ??????? ?????? ??????.
    """
    global PENDING_SESSION
    meas_id = get_next_id()
    ts_now = datetime.now()
    ts_str = ts_now.strftime('%Y%m%d_%H%M%S')
    ts_display = format_ru_datetime(ts_now)

    # ???????????? ?????? Logitech C270: 1280x960 (?????? ?????? 4:3 ??? ?????)
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
        # 1. ???????????? ?????? NIR 850 ?? (??????? ?????????? ??? ??????????? ??-??????? C270)
        # 1. ???????????? ?????? NIR 850 ?? (??????????? ?????????? 2500/200 ??? C270 NoIR)
        set_v4l2_exposure(2500, 200)
        time.sleep(0.20)
        get_relay_controller().set_nir(True)
        time.sleep(0.40)
        for _ in range(8): cap.grab()
        ret_n, frame_nir = cap.read()
        get_relay_controller().set_nir(False) # ???????????? ????????

        # ???????? ??? NIR
        time.sleep(0.15)
        for _ in range(5): cap.grab()
        _, frame_amb_nir = cap.read()

        # 2. ???????????? ?????? RED 660 ?? (????????????? ?????????? 120/40 ??? ?????????)
        set_v4l2_exposure(120, 40)
        time.sleep(0.20)
        for _ in range(8): cap.grab()
        get_relay_controller().set_red(True)
        time.sleep(0.40)
        for _ in range(8): cap.grab()
        ret_r, frame_red = cap.read()
        get_relay_controller().set_red(False) # ??????? ????????

        # ???????? ??? RED
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
    # ?????????? ?????? ? ??????? ?????
    try:
        subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '-c', 'auto_exposure=3'], check=False)
    except Exception:
        pass

    frame_flash = frame_red

    # ?????????? ???????? ArUco-??????? ??????? NoIR-???????:
    # 1) ??????? ?? NIR-????? (???????????? ???????? ??????? ??????????? ?????? ? ????? ?????? ??? 850 ??)
    aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_nir)
    # 2) ???? ?? ??????? - ?? ????? RED 660 ??
    if aruco_id is None:
        aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_red)
    # 3) ???? ?? ??????? - ?? ???????? ambient
    if aruco_id is None:
        aruco_id, aruco_group, aruco_corners = detect_aruco_in_image(frame_amb)
    if aruco_id is not None:
        group_name = aruco_group
        print(f'[ArUco Optical Link] ????-???????? ???????: ?????? #{aruco_id} -> {group_name}', flush=True)

    # ??????? ?????????? ?????????? ??????? (??? ??????????? ?????????????):
    # ????? 660 ??: ?????? ??????? ?????????? ??????? ??? ???????????? ?????? 660 ??
    red_raw = frame_red[:, :, 2].astype(np.float32)
    # ????? 850 ??: ???????????? ?????? ??????? NoIR ??? ???????????? ??-?????? 850 ??
    nir_raw = frame_nir.astype(np.float32).mean(axis=2)  # OPT: 7 passes -> 1

    # ????????? ??????? ??????????????? ???????? ? ?????? ?????????????? ???????? ??????
    amb_red = frame_amb_red[:, :, 2].astype(np.float32)
    amb_nir = frame_amb_nir.astype(np.float32).mean(axis=2)  # OPT: vectorized

    red_channel = np.maximum(0.0, red_raw - amb_red)
    nir_channel = np.maximum(0.0, nir_raw - amb_nir)

    # ???????????????? ?????????? ?? ?????? ?????????? ??????? (White Reference Target)
    h_f, w_f, _ = frame_flash.shape
    is_calib_stand = (group_name in ['?????????? (????? ?0)', '??????????'] or (aruco_id is not None and aruco_id == 6))

    if is_calib_stand:
        # ????? ?????? ?0: ???? ??????????? ????????? ?????? (???-??????)
        blur_sig = cv2.GaussianBlur(red_channel + nir_channel, (15, 15), 0)
        _, _, _, max_loc = cv2.minMaxLoc(blur_sig)
        px, py = max_loc
        hb = 45
        roi_x1, roi_x2 = max(0, px - hb), min(w_f, px + hb)
        roi_y1, roi_y2 = max(0, py - hb), min(h_f, py + hb)
    else:
        # ??????? ????? ??????: ????????? ??????????? ??????? ????
        roi_y1, roi_y2 = int(h_f * 0.04), int(h_f * 0.16)
        roi_x1, roi_x2 = int(w_f * 0.04), int(w_f * 0.16)

    white_red = float(np.mean(red_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    white_nir = float(np.mean(nir_channel[roi_y1:roi_y2, roi_x1:roi_x2]))
    
    # ?????????? ???????? ????????? Red/NIR ??? NoIR-?????? [0.5 ... 8.0]
    is_valid_white = (white_nir > 15.0 and white_red > 25.0 and 0.50 <= (white_red / white_nir) <= 8.00)

    if is_valid_white:
        k_bal = round(float(np.clip(white_red / white_nir, 0.50, 8.00)), 3)
        if is_calib_stand:
            save_calibrated_k_bal(k_bal)
            print(f'[Calibration Stand #0] ???????????? ? ???????? k_bal = {k_bal}', flush=True)
    else:
        # ?????????????? ???????? ???????????? ??????????? ??????? (4.07)
        k_bal = get_calibrated_k_bal()

    # ????????????? ??????? NDVI ? ?????? ???????????????? ???????????? ?????????
    if red_channel.dtype != np.float32: red_channel = red_channel.astype(np.float32)
    if nir_channel.dtype != np.float32: nir_channel = nir_channel.astype(np.float32)
    # ????????????? NumExpr ??? Zero-copy ?????????? ? ???????? RAM
    ndvi_map = ne.evaluate('(k_bal * nir_channel - red_channel) / (k_bal * nir_channel + red_channel + 1e-8)')
    ndvi_map = np.clip(ndvi_map, -1.0, 1.0)

    # ??????????? ??????????? ???????? ??????????? (Projected Leaf Area, PLA)
    # ????? ?????????/????????: ????????? ????? NDVI > 0.28 (???????? ????? 0.0-0.2, ??????? ? ????)
    # + ?????????? ?????? ????????? NIR ??? ???????? ????? (> 22.0 DN)
    leaf_mask = ((ndvi_map > 0.28) & (nir_channel > 22.0)).astype(np.uint8)
    if is_valid_white:
        leaf_mask[roi_y1:roi_y2, roi_x1:roi_x2] = 0

    # 1. ?????? ?????????????? ?????????? ??????? ArUco ?????? ? ????? ???????? ????????? (?????????? ?? 45%)
    if aruco_corners is not None:
        pts_poly = aruco_corners.reshape((-1, 2)).astype(np.float32)
        center_ar = np.mean(pts_poly, axis=0)
        expanded_poly = ((pts_poly - center_ar) * 1.45 + center_ar).astype(np.int32)
        cv2.fillPoly(leaf_mask, [expanded_poly.reshape((-1, 1, 2))], 0)

    # 2. ?????????? ?????????? ??????? ??? (????? ??????, ????? ?????? ?????: ???? 5%, ??? 3%, ???? 3%)
    margin_top = int(h_f * 0.05)
    margin_bot = int(h_f * 0.03)
    margin_side = int(w_f * 0.03)
    leaf_mask[:margin_top, :] = 0
    leaf_mask[h_f - margin_bot:, :] = 0
    leaf_mask[:, :margin_side] = 0
    leaf_mask[:, w_f - margin_side:] = 0

    # 3. ??????????????? ??????????: ???????? ??????? ????????? ???? ??????? (???? 3x3)
    kernel_noise = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_OPEN, kernel_noise)

    print(f'[DEBUG Capture] NIR: mean={nir_raw.mean():.1f}, p90={np.percentile(nir_raw, 90):.1f}, amb={amb_nir.mean():.1f}', flush=True)
    print(f'[DEBUG Capture] RED: mean={red_raw.mean():.1f}, p90={np.percentile(red_raw, 90):.1f}, amb={amb_red.mean():.1f}', flush=True)
    print(f'[DEBUG Capture] k_bal={k_bal}, ndvi: mean={ndvi_map.mean():.3f}, max={ndvi_map.max():.3f}, leaf_mask={np.sum(leaf_mask)}', flush=True)

    # ?????????????:
    # ?????????? ??????????? ???????????? ???????? ?????? (660 ??) ??? ????????? (CLAHE):
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


    # ?????????? ???????????????????? ??-?????? ??? ?????????? ??????????? ?? ??????:
    p_high = float(np.percentile(nir_channel, 99.5))
    if p_high > 6.0:
        vis_nir_mono = np.clip((nir_channel / p_high) * 255.0, 0, 255).astype(np.uint8)
        clahe_nir = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        vis_nir_mono = clahe_nir.apply(vis_nir_mono)
        vis_nir = cv2.cvtColor(vis_nir_mono, cv2.COLOR_GRAY2BGR)
    else:
        vis_nir = frame_nir.copy()

    # ?????????????? ??????? ????????? RdYlGn (??????? = ??????????/?????? -> ?????? -> ?????????? ???????):
    ndvi_disp = np.clip((ndvi_map - 0.20) / 0.65 * 255.0, 0, 255).astype(np.uint8)
    vis_ndvi_color = cv2.LUT(cv2.cvtColor(ndvi_disp, cv2.COLOR_GRAY2BGR), AGRONOMIC_NDVI_LUT)
    vis_ndvi_color[leaf_mask == 0] = [35, 15, 30] # ?????? ??????????? ??? ??? ????? ? ???? ?????

    h, w, _ = frame_flash.shape
    cell_h, cell_w = h // 3, w // 3
    annotated_ndvi = vis_ndvi_color.copy()

    # ????????? ???? ???????????????? ?????????? White Reference (?????? ???? ?????? ???????? ??????)
    if is_valid_white:
        cv2.rectangle(annotated_ndvi, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 255, 255), 2)
        cv2.putText(annotated_ndvi, f'White Ref: k={k_bal}', (roi_x1, max(22, roi_y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'White Ref: k={k_bal}', (roi_x1, max(22, roi_y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
    else:
        # ????????? ? ?????? ??????? ???? ??? PLA (??? ????????? ?? ?????? #1)
        cv2.putText(annotated_ndvi, f'Calib: k={k_bal}', (w - 260, max(26, roi_y1 + 36)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'Calib: k={k_bal}', (w - 260, max(26, roi_y1 + 36)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 255, 200), 1)

    # ????????? ????????????? ????????????? ??????? ArUco
    if aruco_corners is not None and aruco_id is not None:
        pts = aruco_corners.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(annotated_ndvi, [pts], True, (0, 255, 128), 3)
        cx = int(np.mean(pts[:, 0, 0]))
        cy = int(np.mean(pts[:, 0, 1]))
        cv2.putText(annotated_ndvi, f'ArUco #{aruco_id}', (max(10, cx - 50), max(30, cy - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        cv2.putText(annotated_ndvi, f'ArUco #{aruco_id}', (max(10, cx - 50), max(30, cy - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 128), 2)

    # ---------------- ??????????????? ?????? (PLA - ??????? ???????) ----------------
    # 1. ????????????? ?????????? ???????? ?? ArUco-??????? (15x15 ?? = 2.25 ???)
    # 2. ?????????? ????????????? Z-??????????? ?????? ?????? ??????:
    #    Z_marker ? 24.5 ?? (???/?????? ???????), H_canopy ? 10.0 ?? (???? ???????) -> k_z = (14.5 / 24.5)? ? 0.350
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
        # ??????????? ????????????? ??????? ????? 1280x960 ? ?????? Z-???????????
        px_to_cm2 = 0.00008

    total_leaf_px = int(np.count_nonzero(leaf_mask))
    leaf_area_total = round(float(total_leaf_px * px_to_cm2), 1)

    # ????????? ????????? ??????? PLA ?? ?????
    cv2.putText(annotated_ndvi, f'PLA: {leaf_area_total} cm2', (w - 260, max(26, roi_y1 + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3)
    cv2.putText(annotated_ndvi, f'PLA: {leaf_area_total} cm2', (w - 260, max(26, roi_y1 + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2)

    # OPT: vectorized 3x3 grid ? NumPy reshape, no Python loop overhead
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

    # ??????? ???????????????? ?????? NDVI ?? ???? ???????? ??????? ???????:
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
    return PENDING_SESSION

@app.post('/api/start_spectral')
def handle_start_spectral(group_name: str = Form('????????')):
    """????? 1-?? ?????: ????????????? ? ?????."""
    try:
        do_hardware_spectral_capture(group_name)
        return RedirectResponse(url='/?stage=review&offset=0', status_code=303)
    except Exception as e:
        print('[Start Spectral Error]:', e)
        return RedirectResponse(url='/?msg=err_camera', status_code=303)

@app.get('/api/test_relay')
def handle_test_relay(channel: str = 'nir', sec: float = 3.0):
    """?????????? ???????????: ????????? ?????????? ???? (nir ??? red) ?? sec ??????."""
    init_relay()
    if not RELAY_REQ:
        return JSONResponse({'status': 'error', 'message': 'Relay not initialized'})
    line = 7 if channel.lower() == 'nir' else 4
    pin_name = 'Pin 10 (NIR 850nm)' if line == 7 else 'Pin 7 (Red 660nm)'
    try:
        duration = max(0.5, min(10.0, float(sec)))
        print(f'[Test Relay] ????????? {pin_name} ?? {duration} ???...')
        RELAY_REQ.set_value(line, Value.ACTIVE)
        time.sleep(duration)
        RELAY_REQ.set_value(line, Value.INACTIVE)
        print(f'[Test Relay] ?????????? {pin_name}. ??????.')
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
    ??? 4: ????????????? ????????????? ?????? ??????????.
    ?????????? ? ???? ?????? ? ??????? ? ????????? ???????.
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

    # ????????? ????????? ?? ??????????????? ?????????? ????
    if pct_soil.strip():
        try:
            ps_val = float(pct_soil.strip().replace(',', '.'))
            s['pct_soil'] = round(max(0.0, min(100.0, ps_val)), 1)
            s['v_soil'] = round(2.03 - (s['pct_soil'] / 100.0) * 1.59, 2)
        except Exception:
            pass

    # ?????? Delta_T
    delta_t_val = ''
    if t_leaf_val:
        try:
            dt = round(float(t_leaf_val) - float(s['t_air']), 1)
            delta_t_val = str(dt)
        except Exception:
            pass

    # ??????????? ??????????? ? ?????????? ?????????
    jpg_stored_name = ''
    if thermal_thumb and os.path.exists(os.path.join(STATIC_DIR, 'uti_cache', os.path.basename(thermal_thumb))):
        src_thumb = os.path.join(STATIC_DIR, 'uti_cache', os.path.basename(thermal_thumb))
        jpg_stored_name = f'therm_{meas_id}_{thermal_filename}.jpg'
        dst_path = os.path.join(STATIC_DIR, jpg_stored_name)
        shutil.copyfile(src_thumb, dst_path)
        shutil.copyfile(dst_path, os.path.join(STATIC_DIR, 'last_thermal.jpg'))

    row_data = [
        meas_id, ts_display, group_name, weight_val,
        s['t_air'], s['rh_air'], s['v_soil'], s['pct_soil'],
        t_leaf_val, delta_t_val, s['vpd'],
        s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
        s['opt_file'], jpg_stored_name,
        *s['cell_ndvis']
    ]
    exp_mgr = get_experiment_manager(DATA_DIR)
    exp_mgr.save_measurement_row(row_data)
    if s.get('opt_file'):
        exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, s['opt_file']))
    if jpg_stored_name:
        exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, jpg_stored_name))

    PENDING_SESSION = None
    return RedirectResponse(url=f'/?msg=saved&last_grp={group_name}', status_code=303)

@app.get('/api/cancel_session')
def handle_cancel_session():
    """????? ???????? ?????????? ??????."""
    global PENDING_SESSION
    PENDING_SESSION = None
    return RedirectResponse(url='/?msg=cancelled', status_code=303)

# ----------------- ????????? ????????? ?????? (3-?-1) -----------------
@app.get('/api/start_batch')
def handle_start_batch(stage: str = 'stage1'):
    """????? ???????? ?????? ??? ?????????? ????? (stage1 ??? stage2)."""
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
    """?????? ??????? ???????? ??????."""
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
    """?????? ????????? ??????? ? ????? NoIR ??????? ? ????-????????? ArUco, ??????? ???????????????? ? ?????? ??????? ???????."""
    global BATCH_STATE
    if not BATCH_STATE.get('active'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)
    
    stage_key = BATCH_STATE['stage_key']
    cassettes = BATCH_CONFIG[stage_key]['cassettes']
    step = len(BATCH_STATE['sessions'])
    if step >= len(cassettes):
        return RedirectResponse(url='/?stage=batch_await_thermal', status_code=303)
    
    expected_cassette = cassettes[step]
    
    # 1. ???? ???????? ?????? ??????? ??????? ?? ?????? ? ?????????? ??
    manual_mode = (cohort_choice != 'auto' and cohort_choice.strip().isdigit())
    if manual_mode:
        chosen_id = int(cohort_choice)
        c_meta = CASSETTE_CATALOG.get(chosen_id, {'id': chosen_id, 'name': f'??????? #{chosen_id}'})
        target_name = c_meta['name']
    else:
        chosen_id = None
        target_name = expected_cassette['name']
    
    try:
        session = do_hardware_spectral_capture(target_name)
        detected_id = session.get('aruco_id')
        warn_query = ''

        if manual_mode:
            # ?????? ????? ????????? ????? ?????????? ????????? ??? ???????????? ???????
            session['aruco_id'] = chosen_id
            session['group'] = CASSETTE_CATALOG.get(chosen_id, {}).get('name', f'??????? #{chosen_id}')
        else:
            # ????? ????-???????? ?? ??????? ArUco
            if detected_id is not None:
                grp_name = CASSETTE_CATALOG.get(detected_id, {}).get('name', f'??????? #{detected_id}')
                session['group'] = grp_name
                
                # ?????? ??????????????: ???? ?????? ??? ?????????? ? ?????
                is_dup = any(past_s.get('aruco_id') == detected_id for past_s in BATCH_STATE['sessions'])
                if is_dup:
                    warn_query = f'&msg=warn_duplicate_aruco&dup_id={detected_id}&dup_name={grp_name}'
                elif detected_id not in [c['id'] for c in cassettes]:
                    exp_str = ', '.join(str(c['id']) for c in cassettes)
                    warn_query = f'&msg=warn_wrong_stage_aruco&wrong_id={detected_id}&expected={exp_str}'
            else:
                # ?????? fallback: ?????? ?? ??????????? (?????? ??????, ?????????, ?????)
                session['aruco_id'] = expected_cassette['id']
                session['group'] = expected_cassette['name']
                warn_query = f"&msg=warn_no_aruco&exp_id={expected_cassette['id']}&exp_name={expected_cassette['name']}"

        # 2. ???????? ????????? ?????? ??????????
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
    """?????????? ????????? ?????????? ? ?????? ??????????? ? ????-???????? ? ???????? ? ??????????? ?? ArUco."""
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
    
    # ????? N ????? ?????? ?????? ? ????????? ??????????????
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
        
        # ???? ???????? ??? ???? ??????????? ????? ?? ???? ?????? - ????????? ??!
        if s.get('user_t_leaf'):
            t_val = s['user_t_leaf']
        else:
            t_val, ocr_valid = extract_temperature_from_thermal(thumb_path) if os.path.exists(thumb_path) else (None, False)
        if t_val is None: t_val = round(s['t_air'] + 0.5, 1)
        
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
    """?????????? ?????????? ???? ????? ?????? ? ??????????????? ??????? ??????? (????????-????? ??? ????????)."""
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

        c_meta = CASSETTE_CATALOG.get(cid, {'name': f'??????? #{cid}'})
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
        if str(pct_raw).strip():
            try:
                ps = float(str(pct_raw).strip().replace(',', '.'))
                s['pct_soil'] = round(max(0.0, min(100.0, ps)), 1)
                s['v_soil'] = round(2.03 - (s['pct_soil'] / 100.0) * 1.59, 2)
            except Exception:
                pass
        elif group_name in ['?????????', '???????']:
            s['pct_soil'] = ''
            s['v_soil'] = ''

        delta_t_val = ''
        base_air_t = float(s.get('t_air_win') or s.get('t_air', 24.5))
        base_rh_air = float(s.get('rh_air_win') or s.get('rh_air', 55.0))
        if t_l_val:
            try:
                dt = round(float(t_l_val) - base_air_t, 1)
                delta_t_val = str(dt)
            except Exception:
                pass

        records_to_save.append({
            'cid': cid,
            'row': [
                meas_id, ts_display, group_name, w_val,
                base_air_t, base_rh_air, s['v_soil'], s['pct_soil'],
                t_l_val, delta_t_val, s['vpd'],
                s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
                s['opt_file'], '',
                *s['cell_ndvis']
            ]
        })

    # ????????? ?????? ?? ID ??????? ????? ??????? ? ??????
    records_to_save.sort(key=lambda x: x['cid'])

    exp_mgr = get_experiment_manager(DATA_DIR)
    for r in records_to_save:
        exp_mgr.save_measurement_row(r['row'])
        opt_f = r['row'][14] if len(r['row']) > 14 else ''
        if opt_f:
            exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, opt_f))

    stage_name = BATCH_CONFIG.get(stage_key, {}).get('title', '????? 5 ?????? (5-?-1)')
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
    """????????-??????? ??????????? ???????????: ??????? ? ????????????? ?????."""
    return await handle_batch_save_manual(request)

@app.post('/api/batch_save_final')
async def handle_batch_save_final(request: Request):
    """????????????? ????????? ?????????? ???? ????? ?????? ? ?????? ?????????/???????????? ID ? ???????????."""
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
        c_meta = CASSETTE_CATALOG.get(cid, {'name': f'??????? #{cid}'})
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
                s['v_soil'] = round(2.03 - (s['pct_soil'] / 100.0) * 1.59, 2)
            except Exception:
                pass
        elif group_name in ['?????????', '???????']:
            s['pct_soil'] = ''
            s['v_soil'] = ''

        delta_t_val = ''
        base_air_t = float(s.get('t_air_win') or s.get('t_air', 24.5))
        base_rh_air = float(s.get('rh_air_win') or s.get('rh_air', 55.0))
        if t_l_val:
            try:
                dt = round(float(t_l_val) - base_air_t, 1)
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
                base_air_t, base_rh_air, s['v_soil'], s['pct_soil'],
                t_l_val, delta_t_val, s['vpd'],
                s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
                s['opt_file'], jpg_stored_name,
                *s['cell_ndvis']
            ]
        })

    records_to_save.sort(key=lambda r: r['cid'])

    exp_mgr = get_experiment_manager(DATA_DIR)
    for rec in records_to_save:
        exp_mgr.save_measurement_row(rec['row'])
        opt_f = rec['row'][14] if len(rec['row']) > 14 else ''
        th_f = rec['row'][15] if len(rec['row']) > 15 else ''
        if opt_f:
            exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, opt_f))
        if th_f:
            exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, th_f))

    stage_name = BATCH_CONFIG.get(BATCH_STATE.get('stage_key', 'batch5'), {}).get('title', '???????? ?????')
    BATCH_STATE = {
        'active': False,
        'stage_key': 'batch5',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    }
    return RedirectResponse(url=f'/?msg=batch_saved&stage_name={stage_name}', status_code=303)


def do_delete_measurement(meas_id: str):
    """???????? ????????????? ?????? ?? ID ?? CSV ???? ?????? (?????????? ? ????? ??????)."""
    meas_id = str(meas_id).strip()
    if not meas_id:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

    exp_mgr = get_experiment_manager(DATA_DIR)
    csv_paths = {CSV_LOG, exp_mgr.get_active_csv_path()}
    for exp in exp_mgr.get_experiments():
        p = os.path.join(DATA_DIR, 'experiments', exp.get('folder', ''), 'measurements.csv')
        if os.path.exists(p):
            csv_paths.add(p)

    any_found = False
    for csv_file in csv_paths:
        if not os.path.exists(csv_file):
            continue
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                rows = list(csv.reader(f))
            if not rows or len(rows) <= 1:
                continue
            header = rows[0]
            new_data = []
            for r in rows[1:]:
                if r and str(r[0]).strip() == meas_id:
                    any_found = True
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
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(new_data)
        except Exception as e:
            print(f"[Delete error in {csv_file}]:", e)

    if any_found:
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
    ????????????? ????????? ?????????? ????? ???????????? ?????? (T_leaf, Weight, Soil, Thermal image).
    ????????????? ????????????? Delta_T = T_leaf - T_air ? ????????? ?? ??? CSV (?????????? ? ?????).
    """
    meas_id = str(meas_id).strip()
    cohort = str(cohort).strip()
    timestamp = str(timestamp).strip()
    if not meas_id:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

    out_fname = None
    if thermal_file and thermal_file.filename:
        try:
            safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(thermal_file.filename))
            if safe_name:
                out_fname = f"therm_{meas_id}_{safe_name}"
                out_path = os.path.join(STATIC_DIR, out_fname)
                with open(out_path, 'wb') as buf:
                    shutil.copyfileobj(thermal_file.file, buf)
                exp_mgr = get_experiment_manager(DATA_DIR)
                exp_mgr.copy_file_to_active(out_path)
        except Exception as e:
            print('[Upload thermal error]:', e)

    exp_mgr = get_experiment_manager(DATA_DIR)
    csv_paths = {CSV_LOG, exp_mgr.get_active_csv_path()}
    for exp in exp_mgr.get_experiments():
        p = os.path.join(DATA_DIR, 'experiments', exp.get('folder', ''), 'measurements.csv')
        if os.path.exists(p):
            csv_paths.add(p)

    any_found = False
    for csv_file in csv_paths:
        if not os.path.exists(csv_file):
            continue
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                rows = list(csv.reader(f))
            if not rows or len(rows) <= 1:
                continue

            header = rows[0]
            data_rows = rows[1:]
            file_found = False

            for r in data_rows:
                if not r:
                    continue
                if str(r[0]).strip() == meas_id:
                    if cohort and len(r) > 2 and r[2].strip() != cohort:
                        continue
                    if timestamp and len(r) > 1 and timestamp not in r[1] and r[1] not in timestamp:
                        continue

                    file_found = True
                    any_found = True

                    if t_leaf.strip():
                        try:
                            tl = float(t_leaf.strip().replace(',', '.'))
                            tl_str = str(round(tl, 1))
                            if len(r) >= 24:
                                r[8] = tl_str
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

                    if weight_g.strip() and len(r) >= 20:
                        r[3] = weight_g.strip().replace(',', '.')

                    if pct_soil.strip():
                        try:
                            ps = float(pct_soil.strip().replace(',', '.'))
                            ps = round(max(0.0, min(100.0, ps)), 1)
                            if len(r) >= 24:
                                r[7] = str(ps)
                                r[6] = str(round(3.0 - (ps / 100.0) * 1.8, 2))
                            elif len(r) >= 20:
                                r[5] = str(ps)
                        except Exception:
                            pass

                    if out_fname:
                        if len(r) >= 24:
                            r[15] = out_fname
                        elif len(r) >= 20:
                            r[10] = out_fname
                    break

            if file_found:
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(data_rows)
        except Exception as e:
            print(f"[Update error in {csv_file}]:", e)

    if any_found:
        return RedirectResponse(url=f'/?msg=updated&upd_id={meas_id}', status_code=303)

    return RedirectResponse(url='/?msg=err_not_found', status_code=303)

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
    global PENDING_SESSION, BATCH_STATE

    box_t, box_rh, cur_v = await get_climate_sensor().read_climate()
    t_now = int(time.time())

    # ???????????? ?????? ???????????? Xiaomi ?? ??????????? (???? ????????)
    win_clim = get_windowsill_climate()
    tc_val = win_clim.get('t_c') if win_clim else None
    rh_val = win_clim.get('rh_pct') if win_clim else None
    if win_clim and tc_val is not None and (win_clim.get('is_live') or tc_val > 0):
        cur_t = round(float(tc_val), 1)
        cur_rh = round(float(rh_val), 1) if rh_val is not None else box_rh
    else:
        cur_t = box_t
        cur_rh = box_rh

    win_t = cur_t
    win_rh = cur_rh
    cur_vpd = calc_vpd(cur_t, cur_rh)

    # ????????????? ? ????? ???????? ????? ??????
    exp_mgr = get_experiment_manager(DATA_DIR)
    set_exp_req = request.query_params.get('set_exp')
    if set_exp_req:
        exp_mgr.set_active_experiment(set_exp_req)

    active_exp = exp_mgr.get_active_experiment()
    experiments = exp_mgr.get_experiments()
    active_csv = exp_mgr.get_active_csv_path()

    # ??????????? ????????? ?????? ?? ????????? ??? ?????????? ??????
    next_group_default = '????????'
    if last_grp == '????????':
        next_group_default = '??????'
    elif last_grp == '??????':
        next_group_default = '?????'
    elif last_grp == '?????':
        next_group_default = '????????'
    elif '??????' in last_grp.lower() or ('?????' in last_grp.lower() and ('2' in last_grp or '???? 2' in last_grp.lower())):
        next_group_default = '????????? (~40?)'
    elif '?????' in last_grp.lower() or '????' in last_grp.lower():
        next_group_default = '??????????? ?????? (~72?)'
    elif '??????' in last_grp.lower() or '?????' in last_grp.lower():
        next_group_default = '?????? (???????)'

    # ??????????? ???????
    raw_banner = ''
    banner_bg = '#10b981'
    if msg == 'batch_saved':
        s_lbl = stage_name if stage_name else '???????? ??????'
        raw_banner = f'?? ???????? ?????? ({s_lbl}) ??????? ?????????! ??? 3 ?????? ????????? ? ??????.'
        banner_bg = '#10b981'
    elif msg == 'saved':
        raw_banner = '? ????? ???????? ? ????! ??????????? ????????? ???????.'
        banner_bg = '#10b981'
    elif msg == 'exp_switched':
        raw_banner = '?? ????? ?????? ??????? ???????????!'
        banner_bg = '#0284c7'
    elif msg == 'exp_created':
        raw_banner = '?? ????? ????? ?????? ??????? ??????? ? ??????? ??? ????????!'
        banner_bg = '#10b981'
    elif msg == 'updated':
        u_lbl = f' #{upd_id}' if upd_id else ''
        raw_banner = f'?? ????????????{u_lbl} ??????? ???????????????! T ????? ? ?T ???????????.'
        banner_bg = '#0284c7'
    elif msg == 'cancelled':
        raw_banner = '????? ???????. ????? ? ?????? ??????.'
        banner_bg = '#64748b'
    elif msg == 'deleted':
        d_lbl = f' #{del_id}' if del_id else ''
        raw_banner = f'??? ????????????{d_lbl} ??????? ??????? ?? ???????.'
        banner_bg = '#dc2626'
    elif msg == 'err_not_found':
        raw_banner = '?? ???????????? ?? ??????? ? ???? ??????.'
        banner_bg = '#f59e0b'
    elif msg == 'err_camera':
        raw_banner = '? ?????? ?????? /dev/video0. ????????? USB ???????????.'
        banner_bg = '#ef4444'
    elif msg == 'err_thermal_count':
        f_cnt = found if found else '0'
        raw_banner = f'?? ?? ??????????? ?????????? ?????? {f_cnt} ??????(??). ???????? ?????? ?????? ??? ???? 3 ?????? ? ?????????, ??? USB-?????? ?????????.'
        banner_bg = '#ef4444'
    elif msg == 'warn_duplicate_aruco':
        d_name_str = f' ({dup_name})' if dup_name else ''
        raw_banner = f'?? ????????: ?????? #{dup_id}{d_name_str} ??? ?????????? ? ???? ?????! ???? ??????. ??? ????????????? ???????? ?????? ??????? ????.'
        banner_bg = '#f59e0b'
    elif msg == 'warn_no_aruco':
        e_str = exp_name if exp_name else f'??????? #{exp_id}'
        raw_banner = f'?? ArUco-?????? ?? ???????? (?????? ?????? ??? ?????????). ????? ?????? ? ???????? ??? ?{e_str}?. ??? ????????????? ???????? ???????.'
        banner_bg = '#f59e0b'
    elif msg == 'warn_wrong_stage_aruco':
        raw_banner = f'?? ??????????????: ?????? #{wrong_id} ?? ??????? ????? (????????? ???????: {expected}). ???? ??????, ????????? ?????????? ???????.'
        banner_bg = '#f59e0b'
    elif msg == 'err_duplicate_aruco':
        d_name_str = f' ({dup_name})' if dup_name else ''
        raw_banner = f'? ???????????? ????????: ??????? ? ArUco #{dup_id}{d_name_str} ??? ???? ????? ? ???? ?????! ?? ?????? ???????? ??????? ?? ??????. ??????????, ??????? ???????.'
        banner_bg = '#dc2626'
    elif msg == 'err_wrong_stage_aruco':
        raw_banner = f'?? ?????? ????: ????????? ArUco #{wrong_id}, ? ??? ?????????? ????? ????? ???????: {expected}. ????????? ????? ???????.'
        banner_bg = '#f59e0b'

    status_banner = ''
    if raw_banner:
        status_banner = f'''
            <div id="statusAlert" style="position:relative; background:{banner_bg}; padding:12px 42px 12px 18px; border-radius:8px; font-weight:bold; margin-bottom:14px; text-align:center; color:white; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                <span>{raw_banner}</span>
                <button type="button" onclick="dismissBanner()" style="position:absolute; right:12px; top:50%; transform:translateY(-50%); background:rgba(0,0,0,0.2); border:none; color:white; width:26px; height:26px; border-radius:50%; font-size:14px; font-weight:bold; cursor:pointer; line-height:26px; text-align:center;" title="??????? ???????????">?</button>
            </div>
        '''

    slots_html = ''
    progress_html = ''
    wizard_card = ''
    summary_card = ''
    main_content = ''
    bg_color = ''
    phase = ''
    status_banner = status_banner if 'status_banner' in locals() else ''
    # ------------------ ?????? ?????? (WIZARD) ------------------
    if stage == 'batch_shoot' and BATCH_STATE.get('active'):
        # ???????? ??? 1: ?????? ?????? NoIR + ????? ???????????
        stage_key = BATCH_STATE.get('stage_key', 'batch5')
        conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])
        cassettes = conf['cassettes']
        step_idx = len(BATCH_STATE.get('sessions', []))
        total_steps = len(cassettes)

        slots_html = ''
        short_names = {
            1: "????????",
            2: "?????",
            3: "??????",
            4: "?????????",
            5: "???????",
            6: "????? ?0"
        }
        for i, c in enumerate(cassettes):
            if i < step_idx:
                s_done = BATCH_STATE['sessions'][i]
                m_id = s_done.get('aruco_id')
                full_grp = s_done.get('group', f'???? #{i+1}')
                short_grp = short_names.get(m_id, full_grp)
                if len(short_grp) > 12:
                    short_grp = short_grp[:11] + '?'
                
                if m_id:
                    c_col = CASSETTE_CATALOG.get(m_id, {}).get('color', '#059669')
                    badge = f'<div style="background:{c_col}18; color:{c_col}; font-size:9.5px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid {c_col}50; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">ID #{m_id}</div>'
                    slot_title = f"??????? #{m_id}"
                    slot_border = f"1.5px solid {c_col}"
                    slot_bg = f"{c_col}0d"
                else:
                    badge = '<div style="background:#fffbeb; color:#b45309; font-size:9.5px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid #fde68a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">?????? ????????</div>'
                    slot_title = f"???? #{i+1}"
                    slot_border = "1.5px solid #cbd5e1"
                    slot_bg = "#f8fafc"

                slots_html += f'''
                    <div style="background:{slot_bg}; border:{slot_border}; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px;">
                        <div>
                            <span style="font-size:9.5px; color:#475569; font-weight:bold; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">????? #{i+1}</span>
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
                            <span style="font-size:9.5px; color:#1d4ed8; font-weight:bold; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">??????? ?????</span>
                            <span style="font-size:11px; color:#1e40af; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">???? #{step_idx + 1}</span>
                            <span style="font-size:9.5px; color:#2563eb; font-weight:600; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">?? {total_steps}</span>
                        </div>
                        <div style="background:#dbeafe; color:#1e40af; font-size:9px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid #bfdbfe; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">????? ???????</div>
                    </div>
                '''
            else:
                slots_html += f'''
                    <div style="background:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px; opacity:0.75;">
                        <div>
                            <span style="font-size:9.5px; color:#64748b; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">???????</span>
                            <span style="font-size:11px; color:#475569; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">???? #{i+1}</span>
                            <span style="font-size:9.5px; color:#94a3b8; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">????????</span>
                        </div>
                        <div style="background:#f1f5f9; color:#94a3b8; font-size:9px; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px dashed #cbd5e1; white-space:nowrap;">?</div>
                    </div>
                '''
        cohort_options_html = '<option value="auto" selected>????????????? (?????????? ?? ArUco-???????)</option>'
        for cid in [1, 2, 3, 4, 5]:
            if cid in CASSETTE_CATALOG:
                cdata = CASSETTE_CATALOG[cid]
                cohort_options_html += f'<option value="{cid}">??????? #{cid}: {cdata["name"]} ({cdata["desc"]})</option>'

        wizard_card = f'''
            <div class="card" style="border: 2px solid #3b82f6; background: #ffffff; box-sizing:border-box; margin:0; width:100%; overflow:hidden;">
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                        <div>
                            <span style="font-size:10px; text-transform:uppercase; color:#64748b; font-weight:bold;">???????? ????? 5 ?????? (??? ????????)</span>
                            <h2 style="margin:2px 0 0 0; color:#1e40af; font-size:15px;">{conf["title"]}</h2>
                        </div>
                        <span style="background:#dbeafe; color:#1e40af; padding:3px 8px; border-radius:10px; font-size:11px; font-weight:bold;">???? {step_idx + 1} ?? {total_steps}</span>
                    </div>

                    <div style="display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap:6px; margin-bottom:10px; width:100%; box-sizing:border-box;">
                        {slots_html}
                    </div>

                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
                            <span style="font-size:13px; font-weight:bold; color:#0f172a;">
                                ?????????? ????? ??????? ? ???? (???? #{step_idx + 1} ?? {total_steps})
                            </span>
                            <span style="background:#ecfdf5; color:#047857; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:bold; border:1px solid #a7f3d0;">??? ??????? ArUco</span>
                        </div>
                        <p style="margin:0 0 4px 0; font-size:11px; color:#64748b; line-height:1.3;">
                            <b>??????? ????????? ?? ????? ????????.</b> ??????? ???? ??????? ?????? ArUco ?? ?????? ? ?????????? ?????? ?? ????? ???????.
                        </p>
                        <ol style="margin:0; padding-left:16px; font-size:11px; color:#334155; line-height:1.35;">
                            <li>????????? ??????? ? ???? ?? ?????.</li>
                            <li>??????? ?????? ????: ???????????? ??????? NoIR + ArUco.</li>
                            <li>???????? ?????? ?????? ??????????? UTi120S ? ?????.</li>
                        </ol>
                    </div>

                    <form action="/api/batch_capture_next" method="post">
                        <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:8px; padding:10px; margin-bottom:10px;">
                            <div style="margin-bottom:8px;">
                                <label style="font-size:11px; font-weight:bold; color:#1e40af; display:block; margin-bottom:2px;">
                                    ??????? (???????):
                                </label>
                                <select name="cohort_choice" style="width:100%; padding:6px 8px; font-size:12px; font-weight:bold; border:1.5px solid #3b82f6; border-radius:6px; background:#eff6ff; color:#1e40af;">
                                    {cohort_options_html}
                                </select>
                            </div>

                            <span style="font-size:10px; font-weight:bold; color:#475569; text-transform:uppercase; display:block; margin-bottom:6px;">
                                ??????????????? ????????? ??????:
                            </span>
                            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; align-items:end;">
                                <div style="display:flex; flex-direction:column;">
                                    <label style="font-size:11px; font-weight:bold; color:#0f766e; height:18px; display:flex; align-items:flex-end; margin:0 0 3px 0; white-space:nowrap;">
                                        ?????, ?:
                                    </label>
                                    <input type="text" name="weight_g" autofocus placeholder="????. 405.0" style="width:100%; height:36px; padding:6px 8px; font-size:13px; font-weight:bold; border:1.5px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box; margin:0; background:#ffffff;">
                                </div>
                                <div style="display:flex; flex-direction:column;">
                                    <label style="font-size:11px; font-weight:bold; color:#d97706; height:18px; display:flex; align-items:flex-end; margin:0 0 3px 0; white-space:nowrap;">
                                        ??? T ?????, ?C:
                                    </label>
                                    <input type="number" step="0.1" name="t_leaf" placeholder="????. 23.5" style="width:100%; height:36px; padding:6px 8px; font-size:13px; font-weight:bold; border:1.5px solid #f59e0b; border-radius:6px; box-sizing:border-box; margin:0; background:#ffffff;">
                                </div>
                                <div style="display:flex; flex-direction:column;">
                                    <label style="font-size:11px; font-weight:bold; color:#0284c7; height:18px; display:flex; align-items:flex-end; margin:0 0 3px 0; white-space:nowrap;">
                                        ?? ?????????, %:
                                    </label>
                                    <input type="number" step="0.1" min="0" max="100" name="pct_soil" value="" placeholder="???? (I2C)" style="width:100%; height:36px; padding:6px 8px; font-size:13px; font-weight:bold; border:1.5px solid #38bdf8; border-radius:6px; box-sizing:border-box; margin:0; background:#ffffff;">
                                </div>
                            </div>
                        </div>

                        <button type="submit" class="btn-run" style="width:100%; padding:12px; font-size:14px; background:linear-gradient(135deg, #2563eb, #0d9488); cursor:pointer; margin-top:0;">
                            ?? ??????? ?????? #{step_idx + 1} (??????? NoIR + ArUco)
                        </button>
                    </form>
                </div>

                <div style="margin-top:8px; text-align:center;">
                    <a href="/api/cancel_batch" style="color:#94a3b8; font-size:11px; text-decoration:none;">? ???????? ???????? ??????</a>
                </div>
            </div>
        '''

    elif stage == 'batch_await_thermal' and BATCH_STATE.get('active'):
        # ???????? ??? 2: ??? ??????? ????? NoIR, ????? ??????????
        stage_key = BATCH_STATE.get('stage_key', 'stage1')
        conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['stage1'])
        all_sessions = BATCH_STATE.get('sessions', [])

        # ??????????? ????? ?????: ???????? ?????????? ? ???????? ?????
        det_ids = [s.get('aruco_id') for s in all_sessions if s.get('aruco_id') is not None]
        id_counts = {cid: det_ids.count(cid) for cid in set(det_ids)}
        dup_cids = [cid for cid, cnt in id_counts.items() if cnt > 1]
        has_dups = (len(all_sessions) >= 2 and (len(set(det_ids)) <= 1 or len(dup_cids) > 0))
        missing_w_shots = [i + 1 for i, s in enumerate(all_sessions) if not str(s.get('user_weight', '')).strip()]

        warnings_box = ''
        if has_dups:
            dup_info = ', '.join([f"#{cid} ({CASSETTE_CATALOG.get(cid, {}).get('name', '???????')})" for cid in dup_cids]) if dup_cids else f"#{det_ids[0]}" if det_ids else "?? ?????????"
            warnings_box += f'''
                <div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(245,158,11,0.12);">
                    <div style="display:flex; align-items:flex-start; gap:12px;">
                        <span style="font-size:26px; line-height:1;">??</span>
                        <div style="flex:1;">
                            <b style="color:#b45309; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                                ????????: ?????????? ????????????? ?????? ????? ???????!
                            </b>
                            <span style="font-size:12px; color:#92400e; display:block; margin-top:4px; line-height:1.45;">
                                ? ????? ?? ???????? ??????? ????? ??????? (????????????? ??????? ??????? <b>{dup_info}</b>).
                                ??????? ????????????? ???????????? ??? ?????? ?? ????????? ???????? ?????, ?? ????????? ????? ????? ? ?????? ???????! 
                                ??? ????????????? ?????????????? ??????? ? ?????????? ??????? ???????? ???? ????? ?????????.
                            </span>
                        </div>
                    </div>
                </div>
            '''

        if missing_w_shots:
            shots_str = ', '.join([f'#{sh}' for sh in missing_w_shots])
            warnings_box += f'''
                <div style="background:#eff6ff; border:2px solid #3b82f6; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(59,130,246,0.12);">
                    <div style="display:flex; align-items:flex-start; gap:12px;">
                        <span style="font-size:24px; line-height:1;">??</span>
                        <div style="flex:1;">
                            <b style="color:#1d4ed8; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                                ??? ??????? ?? ?????? ??? ??????: {shots_str}!
                            </b>
                            <span style="font-size:12px; color:#1e40af; display:block; margin-top:4px; line-height:1.45;">
                                ??? ????????? ?????? ?? ???? ????????????? ????? ? ???????????? ?????.
                                ????????????? ?????? ????? ? ??????? ? ???????????? ????? <b>??? ????? ? ??????</b> ???? ??? ??????????? ??????? ??????????? ? ??????-????????.
                            </span>
                        </div>
                    </div>
                </div>
            '''

        cards_summary = ''
        for i, s in enumerate(all_sessions):
            m_id = s.get('aruco_id')
            grp = s.get('group', f'???? #{i+1}')
            m_badge = f'<span style="background:#ecfdf5; color:#065f46; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">??? ArUco #{m_id}</span>' if m_id else '<span style="background:#fffbeb; color:#b45309; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">?? ??????</span>'
            if m_id and m_id in dup_cids:
                m_badge += ' <span style="background:#fef3c7; color:#92400e; border:1px solid #fcd34d; padding:2px 5px; border-radius:4px; font-size:9.5px; font-weight:bold;">??????</span>'
            
            # ????????? options ??? ??????????? ?????? ?????? ???????
            options_html = ''
            for cid, cdata in CASSETTE_CATALOG.items():
                sel = 'selected' if cid == m_id else ''
                options_html += f'<option value="{cid}" {sel}>#{cid}: {cdata["name"]}</option>'
                
            w_val = str(s.get('user_weight', '')).strip()
            t_val = s.get('user_t_leaf', '')
            p_val = s.get('user_pct_soil', '64.0')
            
            w_is_missing = (not w_val)
            if w_is_missing:
                weight_input_html = f'''
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                        <label style="font-size:10px; font-weight:bold; color:#b45309;">?? ?????, ?:</label>
                        <span style="background:#fee2e2; color:#dc2626; border:1px solid #fecdd3; padding:1px 4px; border-radius:3px; font-size:8.5px; font-weight:800;">?? ?????? ??</span>
                    </div>
                    <input type="text" name="weight_g_{i}" value="" placeholder="?? ??????? ??? (?)" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:2px dashed #f59e0b; background:#fffbeb; border-radius:4px; box-sizing:border-box;">
                '''
            else:
                weight_input_html = f'''
                    <label style="font-size:10px; font-weight:bold; color:#0f766e; display:block; margin-bottom:2px;">?? ????? ? ?????, ?:</label>
                    <input type="text" name="weight_g_{i}" value="{w_val}" placeholder="????. 410.0" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1px solid #0d9488; border-radius:4px; box-sizing:border-box;">
                '''
            
            cards_summary += f'''
                <div style="flex:1; background:#ffffff; border:1.5px solid #cbd5e1; border-radius:8px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.02);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:11px; color:#64748b; font-weight:bold;">???? #{i+1}</span>
                        {m_badge}
                    </div>
                    
                    <div style="margin-bottom:8px;">
                        <label style="font-size:10px; font-weight:bold; color:#1e40af; display:block; margin-bottom:2px;">??????? / ???????:</label>
                        <select name="cassette_id_{i}" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1.5px solid #94a3b8; border-radius:6px; background:#f8fafc;">
                            {options_html}
                        </select>
                    </div>

                    <img src="/static/{s.get('opt_file', 'last_ndvi.jpg')}?t={t_now}" style="height:68px; border-radius:4px; object-fit:contain; background:#0f172a; width:100%; border:1px solid #e2e8f0; margin-bottom:6px;">
                    
                    <div style="font-size:11px; color:#047857; font-weight:bold; text-align:center; margin-bottom:8px;">
                        NDVI: {s.get("mean_ndvi", "--")} ? PLA: {s.get("leaf_area_cm2", "--")} ???
                    </div>

                    <div style="display:flex; flex-direction:column; gap:5px;">
                        <div>
                            {weight_input_html}
                        </div>
                        <div>
                            <label style="font-size:10px; font-weight:bold; color:#d97706; display:block;">??? T ????? ? UTi120S (?C):</label>
                            <input type="number" step="0.1" name="t_leaf_{i}" value="{t_val}" placeholder="????. 23.8" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1px solid #f59e0b; border-radius:4px; box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="font-size:10px; font-weight:bold; color:#0284c7; display:block;">?? ????????? ?????, %:</label>
                            <input type="number" step="0.1" min="0" max="100" name="pct_soil_{i}" value="{p_val}" style="width:100%; padding:5px; font-size:12px; border:1px solid #38bdf8; border-radius:4px; box-sizing:border-box;">
                        </div>
                    </div>
                </div>
            '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid #10b981; background: #ffffff;">
                <div style="text-align:center; padding:6px 0 10px 0;">
                    <div style="font-size:28px; margin-bottom:2px;">??</div>
                    <h2 style="margin:0; color:#065f46; font-size:17px;">??? {len(BATCH_STATE.get('sessions', []))} ?????? ??????? ??????? ? ????????!</h2>
                    <span style="font-size:12px; color:#047857;">{conf["title"]}</span>
                </div>

                {warnings_box}
                <form action="/api/batch_save_manual" method="post">
                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin-bottom:14px;">
                        {cards_summary}
                    </div>

                    <button type="submit" class="btn-confirm" style="width:100%; padding:15px; font-size:16px; background:linear-gradient(135deg, #059669, #00a499); cursor:pointer; box-shadow:0 4px 14px rgba(0,164,153,0.35);">
                        ? ??? ?????? ? ????????? ??? {len(BATCH_STATE.get('sessions', []))} ?????? ? ?????? (??? ???????????)
                    </button>
                </form>

                <div style="margin-top:14px; padding:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; text-align:center;">
                    <span style="font-size:12px; color:#475569; display:block; margin-bottom:8px;">???? ????????? ?????? ?????? ?????????? ?????????? ??????? ? ????????? ??????????:</span>
                    <form action="/api/batch_link_thermal" method="post">
                        <button type="submit" style="padding:10px 18px; font-size:13px; background:#0284c7; color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">
                            ?? ???????? USB-?????? ??????????? ? ?????????? ????
                        </button>
                    </form>
                </div>

                <div style="margin-top:12px; text-align:center;">
                    <a href="/api/cancel_batch" style="color:#94a3b8; font-size:12px; text-decoration:none;">? ???????? ??????</a>
                </div>
            </div>
        '''

    elif stage == 'batch_verify' and BATCH_STATE.get('active') and BATCH_STATE.get('verified_data'):
        # ???????? ??? 3: ????????? ??????????? ????? ??????
        stage_key = BATCH_STATE.get('stage_key', 'stage1')
        conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['stage1'])
        verified = BATCH_STATE.get('verified_data', [])

        # ??????????? ????? ???????????????? ?????
        v_det_ids = [item.get('detected_id') for item in verified if item.get('detected_id') is not None]
        v_id_counts = {cid: v_det_ids.count(cid) for cid in set(v_det_ids)}
        v_dup_cids = [cid for cid, cnt in v_id_counts.items() if cnt > 1]
        v_has_dups = (len(verified) >= 2 and (len(set(v_det_ids)) <= 1 or len(v_dup_cids) > 0))
        v_missing_w = [i + 1 for i, item in enumerate(verified) if not str(item['session'].get('user_weight', '')).strip()]

        verify_warnings_box = ''
        if v_has_dups:
            v_dup_info = ', '.join([f"#{cid} ({CASSETTE_CATALOG.get(cid, {}).get('name', '???????')})" for cid in v_dup_cids]) if v_dup_cids else f"#{v_det_ids[0]}" if v_det_ids else "?? ?????????"
            verify_warnings_box += f'''
                <div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(245,158,11,0.12);">
                    <div style="display:flex; align-items:flex-start; gap:12px;">
                        <span style="font-size:26px; line-height:1;">??</span>
                        <div style="flex:1;">
                            <b style="color:#b45309; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                                ????????: ?????????? ????????????? ?????? ????? ???????!
                            </b>
                            <span style="font-size:12px; color:#92400e; display:block; margin-top:4px; line-height:1.45;">
                                ? ????? ?? ???????? ??????? ????? ??????? (????????????? ??????? ??????? <b>{v_dup_info}</b>).
                                ??????? ????????????? ???????????? ??? ????? ?? ????????, ?? ?????????? ?????? ????????? ? ?????? ????????.
                                ????????? ? ???????????? ?????????? ?????? ? ?????????? ??????? ????? ???????? ???????????!
                            </span>
                        </div>
                    </div>
                </div>
            '''

        if v_missing_w:
            v_shots_str = ', '.join([f'#{sh}' for sh in v_missing_w])
            verify_warnings_box += f'''
                <div style="background:#eff6ff; border:2px solid #3b82f6; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(59,130,246,0.12);">
                    <div style="display:flex; align-items:flex-start; gap:12px;">
                        <span style="font-size:24px; line-height:1;">??</span>
                        <div style="flex:1;">
                            <b style="color:#1d4ed8; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                                ??? ??????? ?? ??????: ?????? {v_shots_str}!
                            </b>
                            <span style="font-size:12px; color:#1e40af; display:block; margin-top:4px; line-height:1.45;">
                                ????????????? ??????? ??????????? ????? ? ??????? ? ???????????? ????? <b>??? ????? ? ??????</b> ???? ????? ??????????? ? ???? ??????.
                            </span>
                        </div>
                    </div>
                </div>
            '''

        items_html = ''
        for i, item in enumerate(verified):
            s = item['session']
            assigned_id = item['assigned_id']
            detected_id = item.get('detected_id')
            shot_order = item.get('shot_order', i + 1)
            c_info = CASSETTE_CATALOG.get(assigned_id, {'id': assigned_id, 'name': s.get('group', '???????'), 'color': '#0d9488'})

            if detected_id:
                marker_badge = f'<span style="background:#ecfdf5; color:#065f46; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #a7f3d0;">??? ArUco #{detected_id} ????????? (????? #{shot_order}-?)</span>'
            else:
                marker_badge = f'<span style="background:#fffbeb; color:#b45309; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #fde68a;">?? ArUco ?? ?????? (????? #{shot_order}-?)</span>'

            # ?????????? ?????? ?????? ??????? (?? ?????? ?????? ?????????)
            options_html = ''
            for cid, cdata in CASSETTE_CATALOG.items():
                sel = 'selected' if cid == assigned_id else ''
                options_html += f'<option value="{cid}" {sel}>??????? #{cid}: {cdata["name"]}</option>'

            items_html += f'''
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:10px; padding:12px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f1f5f9; padding-bottom:8px; margin-bottom:8px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <label style="font-weight:bold; font-size:13px; color:#334155;">???????:</label>
                            <select name="cassette_id_{i}" style="padding:4px 8px; font-size:13px; font-weight:bold; color:{c_info['color']}; border:1.5px solid #94a3b8; border-radius:6px; background:#f8fafc;">
                                {options_html}
                            </select>
                        </div>
                        <div style="display:flex; gap:6px; align-items:center;">
                            {marker_badge}
                            <span style="background:#ecfdf5; color:#047857; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold;">NDVI: {s['mean_ndvi']}</span>
                            <span style="background:#f0fdf4; color:#15803d; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #bbf7d0;">?? PLA: {s.get('leaf_area_cm2', '--')} ???</span>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-bottom:10px;">
                        <div style="text-align:center;">
                            <span style="font-size:10px; color:#64748b; display:block; margin-bottom:2px;">?????? NoIR (???? #{shot_order})</span>
                            <img src="/static/{s['opt_file']}?t={t_now}" style="width:100%; height:85px; object-fit:contain; background:#0f172a; border-radius:6px; border:1px solid #e2e8f0;">
                        </div>
                        <div style="text-align:center;">
                            <span style="font-size:10px; color:#64748b; display:block; margin-bottom:2px;">?????????? ({item['thermal_filename']})</span>
                            <img src="{item['thermal_thumb_url']}?t={t_now}" style="width:100%; height:85px; object-fit:contain; border-radius:6px; border:1px solid #e2e8f0; background:#f8fafc;">
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; align-items:start;">
                        <div style="display:flex; flex-direction:column;">
                            <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                                <label style="font-size:11px; font-weight:700; color:#0f766e; white-space:nowrap; margin:0;">?? ????? (?):</label>
                                {'' if str(s.get('user_weight', '')).strip() else '<span style="background:#fee2e2; color:#dc2626; border:1px solid #fecdd3; padding:1px 4px; border-radius:3px; font-size:8.5px; font-weight:800;">??? ????</span>'}
                            </div>
                            <input type="text" name="weight_g_{i}" value="{s.get('user_weight', '')}" placeholder="? ????? (?)" style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                            <div style="height:22px; margin-top:4px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#64748b; background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; white-space:nowrap;">???? (?????)</div>
                        </div>
                        <div style="display:flex; flex-direction:column;">
                            <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                                <label style="font-size:11px; font-weight:700; color:#0284c7; white-space:nowrap; margin:0;">?? ????????? (%):</label>
                            </div>
                            <input type="number" step="0.1" min="0" max="100" name="pct_soil_{i}" value="{s.get('pct_soil', 64.0)}" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                            <div style="height:22px; margin-top:4px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#0284c7; background:#f0f9ff; border:1px solid #bae6fd; border-radius:4px; font-weight:600; white-space:nowrap;">{s.get('pct_soil', 64.0)}% ??</div>
                        </div>
                        <div style="display:flex; flex-direction:column;">
                            <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                                <label style="font-size:11px; font-weight:700; color:#334155; white-space:nowrap; margin:0;">??? T ????? (?C):</label>
                                <span style="font-size:9.5px; color:#0284c7; background:#e0f2fe; padding:1px 5px; border-radius:3px; font-weight:700; white-space:nowrap;">OCR {item['t_ocr']}?</span>
                            </div>
                            <input type="number" step="0.1" name="t_leaf_{i}" id="t_leaf_{i}" value="{item['t_ocr']}" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                            <div style="height:22px; margin-top:4px; display:flex; gap:2px;">
                                <button type="button" onclick="adjTemp('t_leaf_{i}', -1.0)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 1.0?C">-1?</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', -0.5)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.5?C">-.5?</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', -0.1)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.1?C">-.1?</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', 0.1)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.1?C">+.1?</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', 0.5)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.5?C">+.5?</button>
                                <button type="button" onclick="adjTemp('t_leaf_{i}', 1.0)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 1.0?C">+1?</button>
                            </div>
                        </div>
                    </div>
                </div>
            '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid var(--sirius-teal); background: #f8fafc;">
                <div style="border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:12px;">
                    <span style="font-size:11px; text-transform:uppercase; color:#64748b; font-weight:bold;">????????? ??????????? ????? (????????????? ?? ArUco)</span>
                    <h2 style="margin:2px 0 0 0; color:var(--sirius-teal-dark); font-size:16px;">{conf["title"]}</h2>
                </div>

                {verify_warnings_box}
                <form action="/api/batch_save_final" method="post">
                    {items_html}

                    <button type="submit" class="btn-confirm" style="width:100%; padding:14px; font-size:16px; background:linear-gradient(135deg, #059669, #00a499); box-shadow:0 4px 14px rgba(0,164,153,0.35); margin-top:8px; cursor:pointer;">
                        ? ??? ? ??????? ? ????????? ??? ????? ? ???? ({len(verified)} ???????)
                    </button>

                    <div style="margin-top:10px; text-align:center;">
                        <a href="/api/cancel_batch" style="color:#94a3b8; font-size:12px; text-decoration:none;">? ???????? ??? ??????</a>
                    </div>
                </form>
            </div>
        '''

    elif stage == 'review' and PENDING_SESSION:
        # ???? 2 ?????????? ??????: ??????????? ? ?????????????
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
                    <a href="/?stage=review&offset={offset+1}" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">?? ????? ?????????? ??????</a>
                    <span style="color:#94a3b8; font-size:11px;">?????? {offset+1} ?? {uti_info['total']}</span>
                    {f'<a href="/?stage=review&offset={max(0, offset-1)}" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">????????? ??</a>' if offset > 0 else '<span></span>'}
                </div>
            '''
        else:
            uti_detected = False
            thumb_url = '/static/last_ndvi.jpg'
            thumb_name = ''
            fn_show = '?????????? ??? ?? ?????????'
            dt_show = '--'
            t_leaf_init = '23.5'
            nav_buttons = '''
                <div style="margin-top:8px; text-align:center;">
                    <a href="/?stage=review&offset=0" style="padding:6px 12px; background:#0284c7; color:white; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">?? ????? ?????? ?? ???????????</a>
                </div>
            '''

        aruco_badge = f'<span style="background:#059669; color:white; padding:4px 10px; border-radius:8px; font-size:11px; font-weight:700; box-shadow:0 1px 4px rgba(5,150,105,0.3); white-space:nowrap;">?? ArUco #{s["aruco_id"]}: {s["group"]}</span>' if s.get('aruco_id') else f'<span style="background:var(--sirius-teal); color:white; padding:4px 10px; border-radius:8px; font-size:11px; font-weight:700; white-space:nowrap;">{s["group"]}</span>'

        step1_note = f'''
            <div style="background:#f0fdf4; border:1.5px solid #bbf7d0; padding:10px 14px; border-radius:8px; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                    <div style="font-size:12px; color:#166534; font-weight:700; display:flex; align-items:center; gap:5px;">
                        <span>??</span> ArUco-?????? #{s.get('aruco_id', '--')} ?????????: ??????? ?{s['group']}?
                    </div>
                    <span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; padding:2px 8px; border-radius:5px; font-weight:700; font-size:10.5px;">
                        White Ref k={s.get('k_bal', 1.025)} (PTFE)
                    </span>
                </div>
                <div style="margin-top:5px; font-size:11.5px; color:#15803d;">
                    ?? ??????????? ??????? ?? ???? ? ?????????? ?????????? ??? ????????????? ??????????.
                </div>
            </div>
        ''' if s.get('aruco_id') else f'''
            <div style="background:#f0fdfa; border:1.5px solid #ccfbf1; padding:10px 14px; border-radius:8px; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                    <div style="font-size:12px; color:#0f766e; font-weight:700;">
                        ? ???????????? ????? ???????? (???????: ?{s['group']}?)
                    </div>
                    <span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; padding:2px 8px; border-radius:5px; font-weight:700; font-size:10.5px;">
                        White Ref k={s.get('k_bal', 1.025)} (PTFE)
                    </span>
                </div>
                <div style="margin-top:5px; font-size:11.5px; color:#0f766e;">
                    ?? ??????????? ??????? ?? ???? ? ?????????? ?????????? ??? ????????????? ??????????.
                </div>
            </div>
        '''

        wizard_card = f'''
            <div class="card" style="border: 2px solid var(--sirius-teal); background: #ffffff;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1.5px solid #e2e8f0; padding-bottom:8px; margin-bottom:12px; gap:8px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="background:var(--sirius-teal); color:#ffffff; font-size:10px; font-weight:800; text-transform:uppercase; padding:3px 7px; border-radius:4px; letter-spacing:0.5px;">??? 2</span>
                        <h2 style="margin:0; color:var(--sirius-teal-dark); font-size:16px; font-weight:800; white-space:nowrap;">????????????? ?????? #{s['id']}</h2>
                    </div>
                    {aruco_badge}
                </div>

                {step1_note}

                <form action="/api/save_final_measurement" method="post">
                    <!-- ?????? ??????????? -->
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; text-align:center;">
                        <span style="font-size:12px; color:#475569; display:block; margin-bottom:4px;">
                            ??????????: <b>{fn_show}</b> ({dt_show})
                        </span>
                        <img src="{thumb_url}?t={t_now}" style="height:140px; border-radius:6px; object-fit:contain; border:1px solid #e2e8f0; background:#f8fafc;">
                        {nav_buttons}
                    </div>

                    <input type="hidden" name="thermal_filename" value="{fn_show}">
                    <input type="hidden" name="thermal_thumb" value="{thumb_name}">

                    <!-- ???? ????? (????????? ?? ??????????? ? ?????????) -->
                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; margin-top:12px; align-items:start;">
                        <!-- ??????? 1: ????? -->
                        <div style="display:flex; flex-direction:column;">
                            <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                                <label style="font-size:11px; font-weight:700; color:#0f766e; white-space:nowrap; margin:0;">?? ????? (?):</label>
                            </div>
                            <input type="text" name="weight_g" autofocus placeholder="? ?????, ????. 415.0" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                            <div style="height:22px; margin-top:4px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#64748b; background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; white-space:nowrap;">
                                ???? (?????)
                            </div>
                        </div>

                        <!-- ??????? 2: ????????? ????? -->
                        <div style="display:flex; flex-direction:column;">
                            <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                                <label style="font-size:11px; font-weight:700; color:#0284c7; white-space:nowrap; margin:0;">?? ????????? (%):</label>
                            </div>
                            <input type="number" step="0.1" min="0" max="100" name="pct_soil" value="{s['pct_soil']}" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                            <div style="height:22px; margin-top:4px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#0284c7; background:#f0f9ff; border:1px solid #bae6fd; border-radius:4px; font-weight:600; white-space:nowrap;">
                                {s.get('pct_soil', 0.0)}% ??
                            </div>
                        </div>

                        <!-- ??????? 3: ??????????? ????? -->
                        <div style="display:flex; flex-direction:column;">
                            <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                                <label style="font-size:11px; font-weight:700; color:#334155; white-space:nowrap; margin:0;">??? T ????? (?C):</label>
                                <span style="font-size:9.5px; color:#0284c7; background:#e0f2fe; padding:1px 5px; border-radius:3px; font-weight:700; white-space:nowrap;">OCR {t_leaf_init}?</span>
                            </div>
                            <input type="number" step="0.1" name="t_leaf" id="single_t_leaf" value="{t_leaf_init}" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                            <div style="height:22px; margin-top:4px; display:flex; gap:2px;">
                                <button type="button" onclick="adjTemp('single_t_leaf', -1.0)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 1.0?C">-1?</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', -0.5)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.5?C">-.5?</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', -0.1)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.1?C">-.1?</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', 0.1)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.1?C">+.1?</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', 0.5)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 0.5?C">+.5?</button>
                                <button type="button" onclick="adjTemp('single_t_leaf', 1.0)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="????????? ?? 1.0?C">+1?</button>
                            </div>
                        </div>
                    </div>

                    <div style="margin-top:12px; padding:9px 14px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; font-size:12px; display:flex; justify-content:space-between; align-items:center; color:#334155;">
                        <span>T ????: <b style="color:#0284c7;">{s['t_air']} ?C</b> (SHT30)</span>
                        <span>NDVI: <b style="color:#059669;">{s['mean_ndvi']}</b></span>
                        <span>VPD: <b style="color:#d97706;">{s['vpd']} ???</b></span>
                    </div>

                    <button type="submit" class="btn-confirm" style="width:100%; height:46px; background:linear-gradient(135deg, #059669, #00a499); color:white; border:none; border-radius:8px; font-size:15px; font-weight:800; cursor:pointer; margin-top:12px; box-shadow:0 4px 12px rgba(0,164,153,0.3); display:flex; align-items:center; justify-content:center; gap:8px;">
                        <span>?</span> ??? ? ??????? ? ????????? ? ??????
                    </button>

                    <div style="margin-top:10px; text-align:center;">
                        <a href="/api/cancel_session" style="color:#64748b; font-size:12px; font-weight:600; text-decoration:none; display:inline-flex; align-items:center; gap:4px; padding:4px 8px; border-radius:4px; transition:all 0.2s;" onmouseover="this.style.color='#ef4444';" onmouseout="this.style.color='#64748b';">
                            <span>?</span> ???????? ???? ?????
                        </a>
                    </div>
                </form>
            </div>
        '''

    else:
        # ???? IDLE: ????? ?????? ?????? (???????? ????? 5 ?????? 5-?-1 ??? ?????????)
        wizard_card = f'''
            <div class="card" style="border: 2px solid var(--sirius-teal); margin:0;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <h2 style="margin:0; color:var(--sirius-teal-dark); font-size:15px;">?? ?????? ???????? ????? 5 ?????? (5-?-1)</h2>
                    <span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;">1 ??????????? ??????</span>
                </div>
                <p style="font-size: 11px; color: #475569; margin: 0 0 10px 0; line-height:1.35;">
                    ??????? ??????????????? ?????? ??? 5 ?????? (NoIR + ??????? ArUco-???????), ? ?????? ??????????? ???????????? <b>????? ???? ??? ? ????? ?????</b>:
                </p>

                <!-- ??????? ?????? ??????? ?????? 5 ?????? -->
                <a href="/api/start_batch?stage=batch5" style="text-decoration:none; display:block; background:linear-gradient(135deg, #0d9488 0%, #059669 45%, #2563eb 100%); color:white; padding:12px; border-radius:10px; text-align:center; box-shadow:0 4px 12px rgba(13,148,136,0.3); transition:all 0.2s;">
                    <span style="font-size:18px; display:block; margin-bottom:2px;">????</span>
                    <b style="font-size:14px; display:block;">????????? ????? 5 ?????? (5-?-1)</b>
                    <span style="font-size:10px; opacity:0.95; display:block; margin-top:2px;">?? ?1 ???????? ? ?? ?2 ????? ? ?? ?3 ?????? ? ?? ?4 ????????? ? ?? ?5 ???????</span>
                </a>

                <!-- ??????? ?? ????????? ???? -->
                <div style="margin-top:8px; padding:6px 10px; background:#f5f3ff; border:1px solid #ddd6fe; border-radius:6px; font-size:10px; color:#5b21b6; line-height:1.3;">
                    ?? <b>???????????????:</b> ??????? 1, 3, 4, 5 ????? ? ????? ?????. ??????? ?2 (?????) ??????????? ? <b>????????? ?????-?????????</b> ??? ?????? ??????? ?? ????????????? ????????????? ???????.
                </div>

                <!-- ?????????? ????????? ????? -->
                <details style="border-top:1px solid #e2e8f0; padding-top:8px; margin-top:8px;">
                    <summary style="cursor:pointer; color:#64748b; font-size:11px; font-weight:bold;">
                        ?????????? ????????? ????? ????? ???????
                    </summary>
                    <form action="/api/start_spectral" method="post" style="margin-top:8px;">
                        <select name="group_name" style="margin-bottom:6px; font-size:12px;">
                            <option value="????????">??????? 1: ???????? (??????? 100% ??)</option>
                            <option value="????????? (NaCl)">??????? 2: ????????? (NaCl 100 ??, ????????)</option>
                            <option value="???????????? ????????????">??????? 3: ???????????? ???????????? (?????? ????? ?? ?T)</option>
                            <option value="???????????? ?????????? ????????">??????? 4: ???????????? ?????????? ???????? (?????? ???????)</option>
                            <option value="???????????? ??????">??????? 5: ???????????? ?????? (???????? ??????)</option>
                            <option value="?????????? (????? ?0)">??????? 6: ????????????? ????? (????? ?0, ????? 22.09)</option>
                        </select>
                        <button type="submit" class="btn-run" style="padding:8px; font-size:12px; margin-top:0;">
                            ????? ????????? ??????? ? ?????
                        </button>
                    </form>
                </details>
            </div>
        '''

    # ??????? ??????? ???????? ????? ??????
    rows = []
    if os.path.exists(active_csv):
        with open(active_csv, 'r', encoding='utf-8') as f:
            all_r = list(csv.reader(f))
            if len(all_r) > 1:
                rows = all_r[1:]

    # ????????-?????????? 5 ??????
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

            if '????????' in grp_l or '??????' in grp_l or '??????' in grp_l:
                cnt_inst += 1
                if ndvi_val is not None: ndvis_inst.append(ndvi_val)
            elif '??????' in grp_l or '????' in grp_l or '??????' in grp_l:
                cnt_eye += 1
                if ndvi_val is not None: ndvis_eye.append(ndvi_val)
            elif '?????' in grp_l or '????????' in grp_l or '??????' in grp_l or '??????' in grp_l:
                cnt_term += 1
                if ndvi_val is not None: ndvis_term.append(ndvi_val)
            elif '?????' in grp_l or '???' in grp_l or 'salin' in grp_l:
                cnt_salt += 1
                if ndvi_val is not None: ndvis_salt.append(ndvi_val)
            elif '?????' in grp_l or 'control' in grp_l or '??????' in grp_l or '???????' in grp_l:
                cnt_ctrl += 1
                if ndvi_val is not None: ndvis_ctrl.append(ndvi_val)

    def mean_s(lst, default="--"):
        return f"{sum(lst)/len(lst):.3f}" if lst else default

    m_ctrl_ndvi = mean_s(ndvis_ctrl, "0.760" if not rows else "--")
    m_salt_ndvi = mean_s(ndvis_salt, "--")
    m_inst_ndvi = mean_s(ndvis_inst, "--")
    m_eye_ndvi = mean_s(ndvis_eye, "--")
    m_term_ndvi = mean_s(ndvis_term, "--")

    eff_badge = "100% ??????"
    if ndvis_inst and ndvis_eye:
        diff_pct = round(((sum(ndvis_inst)/len(ndvis_inst)) - (sum(ndvis_eye)/len(ndvis_eye))) / (sum(ndvis_inst)/len(ndvis_inst)) * 100, 1)
        eff_badge = f"+{diff_pct}% ???????????" if diff_pct > 0 else "0% ??????"

    filtered_rows = rows

    summary_card = f'''
        <div class="card" style="margin-top: 0; padding:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1.5px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <div style="width:4px; height:16px; background:var(--sirius-teal); border-radius:2px;"></div>
                    <h2 style="margin:0; font-size:14px; font-weight:700; border:none; padding:0; color:var(--sirius-teal-dark); letter-spacing:-0.2px;">?????? ????????????????? ??????</h2>
                </div>
                <span style="background:#f1f5f9; border:1px solid #cbd5e1; color:#334155; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:600;">????? ?????????: {len(rows)}</span>
            </div>

            <!-- ?????? ???: ??? 5 ?????? ?????? ?? ?????????? ??????? 1, 2, 3, 4, 5 -->
            <div style="display:flex; justify-content:space-between; align-items:stretch; gap:6px; margin-bottom:10px;">
                <!-- ?1: ???????? -->
                <div style="flex:1; background:#ecfdf5; border:1.5px solid #059669; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:9.5px; white-space:nowrap; letter-spacing:-0.2px; color:#065f46; font-weight:800; display:flex; align-items:center; justify-content:center; gap:3px; height:24px; min-height:24px; flex-shrink:0; line-height:1;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#059669; display:inline-block;"></span> ?1: ????????
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#047857; margin:2px 0;">{cnt_ctrl} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">???.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#059669;">{m_ctrl_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#047857; font-weight:600; margin-top:auto; padding-top:4px; border-top:1px dashed #a7f3d0;">??????? (100% ??)</div>
                </div>
                <!-- ?2: ????? -->
                <div style="flex:1; background:#f5f3ff; border:1.5px solid #7c3aed; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:9.5px; white-space:nowrap; letter-spacing:-0.2px; color:#5b21b6; font-weight:800; display:flex; align-items:center; justify-content:center; gap:3px; height:24px; min-height:24px; flex-shrink:0; line-height:1;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#7c3aed; display:inline-block;"></span> ?2: ?????
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#6d28d9; margin:2px 0;">{cnt_salt} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">???.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#7c3aed;">{m_salt_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#5b21b6; font-weight:600; margin-top:auto; padding-top:4px; border-top:1px dashed #ddd6fe;">100 ?? NaCl</div>
                </div>
                <!-- ?3: ???????????? ?????? -->
                <div style="flex:1; background:#fff1f2; border:1.5px solid #dc2626; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:9.5px; white-space:nowrap; letter-spacing:-0.2px; color:#9f1239; font-weight:800; display:flex; align-items:center; justify-content:center; gap:3px; height:24px; min-height:24px; flex-shrink:0; line-height:1;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#e11d48; display:inline-block;"></span> ?3: ??????
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#be123c; margin:2px 0;">{cnt_term} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">???.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#dc2626;">{m_term_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#9f1239; font-weight:600; margin-top:auto; padding-top:4px; border-top:1px dashed #fecdd3;">???????????? ????</div>
                </div>
                <!-- ?4: ???????????? ????? -->
                <div style="flex:1; background:#fefce8; border:1.5px solid #ca8a04; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:9.5px; white-space:nowrap; letter-spacing:-0.2px; color:#854d0e; font-weight:800; display:flex; align-items:center; justify-content:center; gap:3px; height:24px; min-height:24px; flex-shrink:0; line-height:1;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#ca8a04; display:inline-block;"></span> ?4: ?????????
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#a16207; margin:2px 0;">{cnt_inst} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">???.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#ca8a04;">{m_inst_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#854d0e; font-weight:600; margin-top:auto; padding-top:4px; border-top:1px dashed #fef08a;">?????? ????? (?T)</div>
                </div>
                <!-- ?5: ????????????????? ????? -->
                <div style="flex:1; background:#eff6ff; border:1.5px solid #2563eb; border-radius:8px; padding:8px 4px; text-align:center; display:flex; flex-direction:column; min-height:86px; box-sizing:border-box;">
                    <div style="font-size:9.5px; white-space:nowrap; letter-spacing:-0.2px; color:#1e40af; font-weight:800; display:flex; align-items:center; justify-content:center; gap:3px; height:24px; min-height:24px; flex-shrink:0; line-height:1;">
                        <span style="width:7px; height:7px; border-radius:50%; background:#2563eb; display:inline-block;"></span> ?5: ???????
                    </div>
                    <div style="font-size:15px; font-weight:700; color:#1d4ed8; margin:2px 0;">{cnt_eye} <span style="font-size:9.5px; font-weight:normal; color:#64748b;">???.</span></div>
                    <div style="font-size:10px; color:#475569;">NDVI: <b style="color:#2563eb;">{m_eye_ndvi}</b></div>
                    <div style="font-size:8.5px; color:#1e40af; font-weight:600; margin-top:auto; padding-top:4px; border-top:1px dashed #bfdbfe;">?????? ???????</div>
                </div>
            </div>

            <!-- ?????????????? ?????? ?????????????? ??????? ?4 VS ?5 -->
            <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:7px 12px; display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="background:#e0f2fe; color:#0369a1; font-size:9.5px; font-weight:700; padding:2px 7px; border-radius:3px; text-transform:uppercase; letter-spacing:0.5px;">?????????</span>
                    <span style="font-size:11px; color:#1e293b; font-weight:600;">
                        <b>???????????? ?????????????:</b> ?4 (????? ?? ??????? ?????? ???????) vs ?5 (????? ?? ?????????? ?????????)
                    </span>
                </div>
                <span style="background:#ecfdf5; color:#047857; font-size:10.5px; font-weight:700; padding:3px 10px; border-radius:4px; border:1px solid #a7f3d0; white-space:nowrap;">???????????: {eff_badge}</span>
            </div>

            <!-- 4 ?????? ????????: ?????? ?????????? ?????? 38px, ???????????? 2x2 ??? ?????????? -->
            <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:8px;">
                <a href="/download/csv" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:6px; color:#334155; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='var(--sirius-teal)';this.style.color='#fff';this.style.borderColor='var(--sirius-teal)';" onmouseout="this.style.background='#f8fafc';this.style.color='#334155';this.style.borderColor='#cbd5e1';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span>??????? ?????? (.CSV)</span>
                </a>
                <a href="/download/images_zip" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:6px; color:#15803d; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='#10b981';this.style.color='#fff';this.style.borderColor='#10b981';" onmouseout="this.style.background='#f0fdf4';this.style.color='#15803d';this.style.borderColor='#bbf7d0';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                    <span>????? ?????? (.ZIP)</span>
                </a>
                <a href="/download/aruco_pdf" target="_blank" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#f0fdfa; border:1.5px solid #99f6e4; border-radius:6px; color:#0f766e; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='#00a499';this.style.color='#fff';this.style.borderColor='#00a499';" onmouseout="this.style.background='#f0fdfa';this.style.color='#0f766e';this.style.borderColor='#99f6e4';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><rect x="7" y="7" width="3" height="3"/><rect x="14" y="7" width="3" height="3"/><rect x="14" y="14" width="3" height="3"/><rect x="7" y="14" width="3" height="3"/></svg>
                    <span>??????? ArUco (.PDF)</span>
                </a>
                <a href="/download/presentation" target="_blank" style="height:38px; display:flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; box-sizing:border-box; background:#eff6ff; border:1.5px solid #bfdbfe; border-radius:6px; color:#1d4ed8; text-decoration:none; font-size:11px; font-weight:600; white-space:nowrap; transition:all 0.2s;" onmouseover="this.style.background='#2563eb';this.style.color='#fff';this.style.borderColor='#2563eb';" onmouseout="this.style.background='#eff6ff';this.style.color='#1d4ed8';this.style.borderColor='#bfdbfe';">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                    <span>??????????? (.PDF)</span>
                </a>
            </div>
        </div>
    '''

    def get_cohort_order(r):
        grp = str(r[2] if len(r) > 2 else '').lower()
        if '?????' in grp or 'control' in grp or '#1' in grp or '??????' in grp: return 1
        if '?????' in grp or '???' in grp or 'osmo' in grp or '#2' in grp: return 2
        if '?????' in grp or 'drought' in grp or '????????' in grp or '#3' in grp: return 3
        if '????????' in grp or 'prevent' in grp or '??????' in grp or '??????' in grp or '?????????' in grp or '#4' in grp: return 4
        if '??????' in grp or 'react' in grp or '????' in grp or '??????' in grp or '??????????' in grp or '#5' in grp: return 5
        if '??????' in grp or '?????' in grp or '#6' in grp: return 6
        return 99

    def parse_row_dt(r):
        ts_str = str(r[1] if len(r) > 1 else '')
        ru_m = {'??????': 1, '???????': 2, '?????': 3, '??????': 4, '???': 5, '????': 6,
                '????': 7, '???????': 8, '????????': 9, '???????': 10, '??????': 11, '???????': 12}
        try:
            p = ts_str.replace(',', '').split()
            day = int(p[0])
            mon = ru_m.get(p[1].lower(), 10)
            yr = int(p[2])
            t_p = p[3].split(':')
            return datetime(yr, mon, day, int(t_p[0]), int(t_p[1]), int(t_p[2]))
        except Exception:
            return datetime.min

    sorted_by_time = sorted(filtered_rows, key=parse_row_dt, reverse=True)
    sessions = []
    cur_sess = []
    for r in sorted_by_time:
        r_dt = parse_row_dt(r)
        if not cur_sess:
            cur_sess.append((r, r_dt))
        else:
            diff = abs((cur_sess[-1][1] - r_dt).total_seconds())
            if diff <= 3600 and len(cur_sess) < 6:
                cur_sess.append((r, r_dt))
            else:
                sessions.append(cur_sess)
                cur_sess = [(r, r_dt)]
    if cur_sess:
        sessions.append(cur_sess)

    ordered_table_rows = []
    for sess in sessions:
        sess_sorted = sorted([item[0] for item in sess], key=get_cohort_order)
        ordered_table_rows.extend(sess_sorted)

    # ????? ??? ??? ??????? ??????????? ??????????? ???? ?????? ???? (??? ? Excel)
    unique_dates = []
    for r in ordered_table_rows:
        ts = r[1] if len(r) > 1 else ''
        d_str, _ = format_ru_date_and_time(ts)
        if d_str and d_str not in unique_dates:
            unique_dates.append(d_str)

    date_idx_map = {d: i for i, d in enumerate(unique_dates)}

    table_html = ''
    prev_d_str = None
    for r in ordered_table_rows:
        leaf_area_val = "--"
        if len(r) >= 25:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} ?" if r[3] else "--"
            if r[4] and r[5]:
                t_air_str = f'<span style="white-space:nowrap;font-size:11px;color:#334155;">{r[4]}?C <span style="color:#cbd5e1;">?</span> <span style="color:#059669;font-weight:600;">{r[5]}%</span></span>'
            else:
                t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[7]}%" if r[7] else "--"
            t_show = f"{r[8]} ?C" if r[8] else "--"
            delta_str = f"{r[9]}?C" if r[9] else "--"
            ndvi_txt = f"{r[11]}?{r[12]}" if len(r)>12 else "--"
            leaf_area_val = f"{r[13]} ???" if r[13] else "--"
            th_name = r[15] if len(r)>15 else ""

            if r[9]:
                try:
                    dt_val = float(r[9])
                    if dt_val <= -0.5:
                        stress_badge = f'<span style="background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (?????)</span>'
                    elif dt_val <= 0.5:
                        stress_badge = f'<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (???. ??????)</span>'
                    elif dt_val <= 1.8:
                        stress_badge = f'<span style="background:#f0fdfa;color:#0f766e;border:1px solid #99f6e4;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (???? ????????)</span>'
                    else:
                        stress_badge = f'<span style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (????? ??????????)</span>'
                except Exception:
                    stress_badge = f'<span style="white-space:nowrap;font-weight:600;">{delta_str}</span>'
            else:
                stress_badge = '<span style="color:#94a3b8;">--</span>'

        elif len(r) >= 24:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} ?" if r[3] else "--"
            if r[4] and r[5]:
                t_air_str = f'<span style="white-space:nowrap;font-size:11px;color:#334155;">{r[4]}?C <span style="color:#cbd5e1;">?</span> <span style="color:#059669;font-weight:600;">{r[5]}%</span></span>'
            else:
                t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[7]}%" if r[7] else "--"
            t_show = f"{r[8]} ?C" if r[8] else "--"
            delta_str = f"{r[9]}?C" if r[9] else "--"
            ndvi_txt = f"{r[11]}?{r[12]}" if len(r)>12 else "--"
            if '.jpg' in r[13] or '.png' in r[13]:
                leaf_area_val = "--"
                th_name = r[14] if len(r)>14 else ""
            else:
                leaf_area_val = f"{r[13]} ???"
                th_name = r[15] if len(r)>15 else ""

            if r[9]:
                try:
                    dt_val = float(r[9])
                    if dt_val <= -0.5:
                        stress_badge = f'<span style="background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (?????)</span>'
                    elif dt_val <= 0.5:
                        stress_badge = f'<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (???. ??????)</span>'
                    elif dt_val <= 1.8:
                        stress_badge = f'<span style="background:#f0fdfa;color:#0f766e;border:1px solid #99f6e4;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (???? ????????)</span>'
                    else:
                        stress_badge = f'<span style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (????? ??????????)</span>'
                except Exception:
                    stress_badge = f'<span style="white-space:nowrap;font-weight:600;">{delta_str}</span>'
            else:
                stress_badge = '<span style="color:#94a3b8;">--</span>'

        elif len(r) >= 20:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} ?" if r[3] else "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[5]}%" if r[5] else "--"
            t_show = f"{r[6]} ?C" if r[6] else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[7]}?{r[8]}" if len(r)>8 else "--"
            leaf_area_val = "--"
            th_name = r[10] if len(r)>10 else ""
        else:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[4]}%" if len(r)>4 else "--"
            t_show = f"{r[5]} ?C" if len(r)>5 else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[6]}?{r[7]}" if len(r)>7 else "--"
            leaf_area_val = "--"
            th_name = r[9] if len(r)>9 else ""

        # ?????????? ?????? NDVI
        opt_f = r[14] if (len(r) >= 25 and r[14]) else (r[13] if (len(r) == 24 and '.jpg' in r[13]) else '')
        if opt_f and os.path.exists(os.path.join(STATIC_DIR, opt_f)):
            ndvi_cell = f'<a href="/static/{opt_f}" target="_blank" title="??????? ????? NDVI #{m_id}" style="color:var(--sirius-teal-dark);text-decoration:none;font-weight:600;"><span style="white-space:nowrap;font-family:monospace;font-size:11px;">{ndvi_txt}</span> ??</a>'
        else:
            ndvi_cell = f'<span style="white-space:nowrap;font-family:monospace;font-size:11px;color:#334155;">{ndvi_txt}</span>'

        if th_name:
            m_th = re.search(r'(IMG[_\s]\d+)', th_name)
            clean_th = m_th.group(1) if m_th else th_name
            th_file_path = os.path.join(STATIC_DIR, th_name)
            if os.path.exists(th_file_path):
                th_stat = f'<a href="/static/{th_name}" target="_blank" title="??????? ??????????? #{m_id}" style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;text-decoration:none;">? {clean_th} ??</a>'
            else:
                th_stat = f'<span style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;">? {clean_th}</span>'
        else:
            th_stat = '<span style="color:#d97706;font-size:11px;white-space:nowrap;font-weight:600;">? ???????</span>'

        d_str, t_str = format_ru_date_and_time(ts)
        d_idx = date_idx_map.get(d_str, 0)
        is_odd_date = (d_idx % 2 == 1)
        date_cls = "date-group-odd" if is_odd_date else "date-group-even"
        divider_cls = " date-group-divider" if (prev_d_str is not None and d_str != prev_d_str) else ""
        prev_d_str = d_str
        row_cls = f"{date_cls}{divider_cls}"

        time_cell = f'<div style="white-space:nowrap;font-size:11px;font-weight:600;color:#0f172a;">{d_str}</div><div style="font-size:10px;color:#64748b;white-space:nowrap;">{t_str}</div>'
        grp_badge = format_group_badge(grp)
        if t_show != '--' and 'none' not in t_show.lower():
            t_leaf_html = f'''<span onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="cursor:pointer; color:#d97706; font-weight:bold; white-space:nowrap; padding:2px 5px; border-radius:4px; border-bottom:1.5px dashed #f59e0b; background:#fffbeb;" title="???????, ????? ??????????????? T ????? ?????? #{m_id} ({grp})">{t_show} <span style="font-size:10px;">??</span></span>'''
        else:
            t_leaf_html = f'''<span onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="cursor:pointer; color:#dc2626; font-weight:bold; white-space:nowrap; padding:2px 6px; border-radius:4px; border:1.5px dashed #ef4444; background:#fef2f2;" title="T ????? ?? ??????????! ???????, ????? ?????????">{t_show} <span style="font-size:10px;">??</span></span>'''

        del_btn = f'''<form action="/api/delete_measurement" method="post" style="margin:0;display:inline;" onsubmit="return confirm('??????? ???????????? #{m_id} ({grp})?');"><input type="hidden" name="meas_id" value="{m_id}"><button type="submit" style="background:#fee2e2; border:1px solid #fca5a5; color:#dc2626; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1;" title="??????? ????? #{m_id}" onmouseover="this.style.background='#dc2626';this.style.color='#fff';" onmouseout="this.style.background='#fee2e2';this.style.color='#dc2626';">?</button></form>'''
        edit_btn = f'''<button type="button" onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="background:#e0f2fe; border:1px solid #bae6fd; color:#0369a1; border-radius:4px; padding:2px 5px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1; margin-right:3px;" title="??????????????? ????? #{m_id} ({grp})" onmouseover="this.style.background='#0284c7';this.style.color='#fff';" onmouseout="this.style.background='#e0f2fe';this.style.color='#0369a1';">??</button>'''

        table_html += f'<tr class="{row_cls}"><td><b style="color:#64748b;">#{m_id}</b></td><td>{time_cell}</td><td>{grp_badge}</td><td><b style="color:#0284c7;white-space:nowrap;">{wt}</b></td><td>{t_air_str}</td><td>{t_leaf_html}</td><td>{stress_badge}</td><td>{ndvi_cell}</td><td><b style="color:#047857;white-space:nowrap;font-size:11px;">{leaf_area_val}</b></td><td><span style="white-space:nowrap;font-weight:500;color:#334155;">{pct}</span></td><td>{th_stat}</td><td class="col-actions" style="white-space:nowrap;">{edit_btn}{del_btn}</td></tr>'

    if not table_html:
        table_html = '<tr><td colspan="12" style="text-align:center; padding:35px 20px; color:#64748b; font-size:14px;">?? <b>?????? ??????????????? ??????? ????.</b><br><span style="font-size:12px; color:#94a3b8;">????????? ???????? ????? ?????? 1?5, ????? ?????? ???????? ?????? ?????? ????????????.</span></td></tr>'

    grid_top_content = f'''
        <div style="display:flex; flex-direction:column; gap:12px;">
            {wizard_card}
            {summary_card}
        </div>
        <div class="card" style="display:flex; flex-direction:column; margin:0; justify-content:space-between;">
            <h2>?? ?????????????????? ??????? ????????????</h2>
            <div class="channels" style="flex:1; gap:10px;">
                <div class="ch-box">
                    <div style="color:#dc2626; font-size:11px; font-weight:700; margin-bottom:4px;">????? 1: 660 ?? (Deep Red)</div>
                    <img src="/static/last_red.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
                <div class="ch-box">
                    <div style="color:#4f46e5; font-size:11px; font-weight:700; margin-bottom:4px;">????? 2: 850 ?? (NIR ????????????)</div>
                    <img src="/static/last_nir.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
                <div class="ch-box">
                    <div style="color:#0d9488; font-size:11px; font-weight:700; margin-bottom:4px;">????? 3: ????? NDVI (????? 3?3)</div>
                    <img src="/static/last_ndvi.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
                <div class="ch-box">
                    <div style="color:#d97706; font-size:11px; font-weight:700; margin-bottom:4px;">????? 4: ??????????? (UNI-T UTi120S)</div>
                    <img src="/static/last_thermal.jpg?t={t_now}" class="preview-img" style="height:175px;">
                </div>
            </div>
        </div>
    '''
    
    main_content = grid_top_content + f'''
    <div class="card" style="margin-top:20px;">
        <h2>?? ?????? ??????????????? ????????????</h2>
        <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th>ID</th><th>???? ? ?????</th><th>???????</th><th>???(?)</th><th>T ????.</th><th>T ?????</th><th>??????</th><th>NDVI_avg</th><th>???????</th><th>?????</th><th>???????????</th><th>????????</th>
                </tr>
                {table_html}
            </table>
        </div>
    </div>
    '''

    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request,
        "slots_html": slots_html,
        "progress_html": progress_html,
        "main_content": main_content,
        "grid_top_content": grid_top_content,
        "table_html": table_html,
        "status_banner": status_banner,
        "bg_color": bg_color,
        "stage": stage,
        "phase": phase,
        "cur_t": cur_t,
        "cur_rh": cur_rh,
        "cur_vpd": cur_vpd,
        "cur_v": cur_v,
        "box_t": box_t,
        "box_rh": box_rh,
        "active_exp": active_exp,
        "experiments": experiments,
        "rows_count": len(rows),
        "win_t": win_t,
        "win_rh": win_rh
    })
@app.get('/download/pdf')
def download_pdf():
    pdf_path = os.path.join(STATIC_DIR, '??????????_??????_???????_??????_????????_?????.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(STATIC_DIR, 'analysis_report.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='??????????_??????_???????_??????_????????_?????.pdf', media_type='application/pdf')
    return HTMLResponse('????? ???? ?? ???????????')

@app.get('/download/paper')
def download_paper():
    pdf_path = os.path.join(STATIC_DIR, '??????????_??????_???????_??????_????????_?????.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='??????????_??????_???????_??????_????????_?????.pdf', media_type='application/pdf')
    return HTMLResponse('???? ?????? ?? ??????')

@app.get('/download/research_paper')
def download_research_paper():
    pdf_path = os.path.join(STATIC_DIR, '??????_?????????????????_??????_????????_?????.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, '??????_?????????????????_??????_????????_?????.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='??????_?????????????????_??????_????????_?????.pdf', media_type='application/pdf')
    return HTMLResponse('???? ??????-????????????????? ?????? ???? ?? ???????????')


@app.get('/download/presentation')
@app.get('/download/presentation_pdf')
def download_presentation():
    pdf_path = os.path.join(STATIC_DIR, '???????????_???????_??????_2026_????????_?????.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, '???????????_???????_??????_2026_????????_?????.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='???????????_???????_??????_2026_????????_?????.pdf', media_type='application/pdf')
    return HTMLResponse('???? ??????????? ??????? ???? ?? ???????????')

@app.get('/download/presentation_pptx')
def download_presentation_pptx():
    pptx_path = os.path.join(STATIC_DIR, '???????????_???????_??????_2026_????????_?????.pptx')
    if not os.path.exists(pptx_path):
        pptx_path = os.path.join(DOCS_DIR, '???????????_???????_??????_2026_????????_?????.pptx')
    if os.path.exists(pptx_path):
        return FileResponse(pptx_path, filename='???????????_???????_??????_2026_????????_?????.pptx', media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    return HTMLResponse('???? PPTX ??????????? ???? ?? ???????????')
@app.get('/download/aruco_pdf')
def download_aruco_pdf():
    pdf_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='aruco_markers_cassettes.pdf', media_type='application/pdf')
    html_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.html')
    if os.path.exists(html_path):
        return FileResponse(html_path, filename='aruco_markers_cassettes.html', media_type='text/html')
    return HTMLResponse('???? ???????? ?? ??????')

@app.post('/api/experiment/switch')
async def handle_experiment_switch(request: Request):
    """???????????? ???????? ????? ??????."""
    form = await request.form()
    exp_id = form.get('exp_id', '').strip()
    if exp_id:
        exp_mgr = get_experiment_manager(DATA_DIR)
        exp_mgr.set_active_experiment(exp_id)
    return RedirectResponse(url='/?msg=exp_switched', status_code=303)

@app.post('/api/experiment/create')
async def handle_experiment_create(request: Request):
    """???????? ????? ????? ?????? ? ?? ?????????."""
    form = await request.form()
    name = form.get('name', '').strip()
    plant = form.get('plant', '').strip()
    desc = form.get('description', '').strip()
    if name:
        exp_mgr = get_experiment_manager(DATA_DIR)
        exp_mgr.create_experiment(name, plant, desc)
    return RedirectResponse(url='/?msg=exp_created', status_code=303)

@app.get('/download/experiment_zip')
def download_experiment_zip():
    """?????????? ??????? ?????? ???????? ????? ?????? (CSV + ??????)."""
    exp_mgr = get_experiment_manager(DATA_DIR)
    active_exp = exp_mgr.get_active_experiment()
    exp_id = active_exp.get('id', 'exp_1')
    exp_name = active_exp.get('name', 'experiment').replace(' ', '_')
    out_zip = os.path.join(DATA_DIR, f"temp_{exp_id}.zip")
    exp_mgr.generate_zip(exp_id, out_zip)
    if os.path.exists(out_zip):
        return FileResponse(out_zip, filename=f"{exp_name}_export.zip", media_type='application/zip')
    return HTMLResponse('?????? ???????????? ?????? ?????')

@app.get('/download/csv')
def download_active_csv():
    """?????????? CSV ??????? ???????? ????? ??????."""
    exp_mgr = get_experiment_manager(DATA_DIR)
    active_csv = exp_mgr.get_active_csv_path()
    active_exp = exp_mgr.get_active_experiment()
    exp_name = active_exp.get('name', 'measurements').replace(' ', '_')
    if os.path.exists(active_csv):
        return FileResponse(active_csv, filename=f"{exp_name}.csv", media_type='text/csv')
    return HTMLResponse('???? CSV ?? ??????')

@app.get('/download/images_zip')
def download_images_zip():
    """?????????? ?????? ??????? ???????? ?????."""
    exp_mgr = get_experiment_manager(DATA_DIR)
    active_exp = exp_mgr.get_active_experiment()
    exp_id = active_exp.get('id', 'exp_1')
    out_zip = os.path.join(DATA_DIR, f"temp_{exp_id}.zip")
    exp_mgr.generate_zip(exp_id, out_zip)
    if os.path.exists(out_zip):
        return FileResponse(out_zip, filename=f"images_{exp_id}.zip", media_type='application/zip')
    return HTMLResponse('????? ??????? ?? ??????')

app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)

