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
import subprocess
import numpy as np
from src.sensors_ads1115 import _global_reader
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
    3: {'id': 3, 'name': 'Терминальная засуха', 'desc': 'Без полива до гибели (некроз)', 'color': '#dc2626', 'stage': 'batch5'},
    4: {'id': 4, 'name': 'Превентивная регидратация', 'desc': 'Полив по алерту станции (ΔT > +0.8°C)', 'color': '#eab308', 'stage': 'batch5'},
    5: {'id': 5, 'name': 'Традиционный визуальный контроль', 'desc': 'Полив при явном увядании листьев', 'color': '#2563eb', 'stage': 'batch5'},
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
        with smbus2.SMBus(0) as bus:
            # Команда замера высокой повторяемости (High repeatability, clock stretching disabled: 0x2C, 0x06)
            bus.write_i2c_block_data(0x44, 0x2C, [0x06])
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
        return '<span style="background:#eff6ff; color:#1e40af; padding:2px 8px; border-radius:6px; font-weight:700; font-size:10.5px; border:1px solid #bfdbfe;">👁 К5: Глаза</span>
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
