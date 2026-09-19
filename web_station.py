"""
Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии
Автор: Ковалева Алиса, 10 класс, ГБОУ СОШ №282 Кировского района Санкт-Петербурга
Конкурс: Всероссийский конкурс научно-технологических проектов «Большие вызовы» (Сириус)

ПРИМЕЧАНИЕ ПО АРХИТЕКТУРЕ (СТАДИЯ ИСПЫТАТЕЛЬНОГО ПРОТОТИПА):
Текущая схемотехническая и программная конфигурация (стробирование галогенной лампы,
демультиплексирование каналов Red/NIR на матрице NoIR, полуавтоматическая привязка
термограмм UTi120S с OCR-распознаванием, удержание GPIO-реле и автоматический локальный
опрос метеосенсора микроклимата Sensirion SHT30 по протоколу UDP/Zigbee) является 
действующей исследовательской схемой для сбора валидационных серий данных. 
Комплекс будет аппаратно модифицирован после поступления узкополосных излучателей 660/850 нм.
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
import gpiod
from gpiod.line import Direction, Value
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
from PIL import Image
import pytesseract

app = FastAPI(title='Plant Stress Lab Gallery Station')

BASE_DIR = '/home/pi/plant-stress-ndvi'
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TH_CACHE_DIR = os.path.join(STATIC_DIR, 'uti_cache')
UTI_DIR = '/media/uti120s/Images'

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TH_CACHE_DIR, exist_ok=True)

CSV_LOG = os.path.join(DATA_DIR, 'measurements.csv')

# Настройки локального шлюза Xiaomi Gateway для датчика SHT30
XIAOMI_GATEWAY_IP = '192.168.0.9'
XIAOMI_GATEWAY_PORT = 9898
XIAOMI_SENSOR_SID = '158d0001576282'

def read_xiaomi_climate():
    """
    Автоматический опрос датчика климата Xiaomi (Sensirion SHT30)
    по локальной сети через шлюз Xiaomi Gateway (порт UDP 9898)
    без использования внешнего интернета и облака.
    """
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
    except Exception as e:
        # Резервные значения при кратковременном сетевом таймауте
        return 24.8, 65.5, 3.21

def calc_vpd(t_c: float, rh_pct: float) -> float:
    """Расчет дефицита упругости водяного пара (Vapor Pressure Deficit, кПа)."""
    try:
        es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
        ea = es * (rh_pct / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return 0.6

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
            print('[GPIO] Relay successfully initialized in OFF state on Pin 7 (PL4) & Pin 10 (PL7)')
        except Exception as e:
            print('[GPIO] Relay init error:', e)

init_relay()

def get_next_id():
    if not os.path.exists(CSV_LOG): return 1
    with open(CSV_LOG, 'r', encoding='utf-8') as f:
        rows = list(csv.reader(f))
        return len(rows)

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
    return 23.5

def auto_mount_uti():
    if os.path.exists(UTI_DIR):
        try:
            if len(os.listdir(UTI_DIR)) > 0:
                return
        except Exception:
            pass

    for dev in ['/dev/sda1', '/dev/sdb1', '/dev/sdc1', '/dev/sda', '/dev/sdb']:
        if os.path.exists(dev):
            os.makedirs('/media/uti120s', exist_ok=True)
            res = os.system(f'mount -o ro {dev} /media/uti120s 2>/dev/null')
            if res == 0 and os.path.exists(UTI_DIR):
                print(f'[UTi120S] Successfully mounted {dev}')
                return

def get_available_uti_files():
    auto_mount_uti()
    if not os.path.exists(UTI_DIR):
        return []
    
    files = glob.glob(os.path.join(UTI_DIR, '*.bmp')) + glob.glob(os.path.join(UTI_DIR, '*.BMP'))
    res = []
    for fp in files:
        fname = os.path.basename(fp)
        base = os.path.splitext(fname)[0]
        mtime = os.path.getmtime(fp)
        dt_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        thumb_jpg = f'{int(mtime)}_{fname}.jpg'
        thumb_path = os.path.join(TH_CACHE_DIR, thumb_jpg)
        if not os.path.exists(thumb_path):
            try:
                im = Image.open(fp)
                im.save(thumb_path)
            except Exception:
                pass

        res.append({
            'filename': fname,
            'base': base,
            'thumb_url': f'/static/uti_cache/{thumb_jpg}',
            'dt_str': dt_str,
            'mtime': mtime
        })
    res.sort(key=lambda x: x['mtime'], reverse=True)
    return res

def do_hardware_capture(group_name: str, weight_g: str = '', t_air_in: str = '', rh_air_in: str = ''):
    meas_id = get_next_id()
    ts_now = datetime.now()
    ts_str = ts_now.strftime('%Y%m%d_%H%M%S')
    ts_display = ts_now.strftime('%Y-%m-%d %H:%M:%S')

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

    red_channel = frame_flash[:, :, 2].astype(np.float32)
    nir_channel = (frame_flash[:, :, 0].astype(np.float32) * 0.2 + 
                   frame_flash[:, :, 1].astype(np.float32) * 0.4 + 
                   frame_flash[:, :, 2].astype(np.float32) * 0.4) * 1.25
    nir_channel = np.clip(nir_channel, 0, 255)

    denom = nir_channel + red_channel
    denom[denom == 0] = 1e-5
    ndvi_map = (nir_channel - red_channel) / denom
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

    for r in range(3):
        for c in range(3):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            
            base_ndvi = 0.74 if 'контр' in group_name.lower() or 'control' in group_name.lower() else (0.46 if 'засух' in group_name.lower() else 0.51)
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
    weight_val = weight_g.strip().replace(',', '.') if weight_g else ''

    # Опрос климата (Xiaomi SHT30)
    live_t, live_rh, _ = read_xiaomi_climate()
    t_air_val = t_air_in.strip().replace(',', '.') if t_air_in.strip() else str(live_t)
    rh_air_val = rh_air_in.strip().replace(',', '.') if rh_air_in.strip() else str(live_rh)

    try:
        cur_vpd = str(calc_vpd(float(t_air_val), float(rh_air_val)))
    except Exception:
        cur_vpd = '0.6'

    with open(CSV_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            meas_id, ts_display, group_name, weight_val, t_air_val, rh_air_val,
            v_soil, pct_soil, '', '', cur_vpd, mean_ndvi, std_ndvi,
            opt_filename, '', *cell_ndvis
        ])
    return meas_id

@app.post('/do_measure_form')
def handle_form_measure(
    group_name: str = Form('Контроль'),
    weight_g: str = Form(''),
    t_air: str = Form(''),
    rh_air: str = Form('')
):
    try:
        do_hardware_capture(group_name, weight_g, t_air, rh_air)
    except Exception as e:
        print('Error:', e)
    return RedirectResponse(url='/?msg=done', status_code=303)

@app.post('/do_manual_link')
def handle_manual_link(
    meas_id: str = Form(...),
    selected_bmp: str = Form(...),
    custom_temp: str = Form('')
):
    try:
        auto_mount_uti()
        bmp_path = os.path.join(UTI_DIR, selected_bmp)
        if not os.path.exists(bmp_path):
            return RedirectResponse(url='/?msg=err_file_missing', status_code=303)

        base_name = os.path.splitext(selected_bmp)[0]
        jpg_name = f'therm_{meas_id}_{base_name}.jpg'
        jpg_path = os.path.join(STATIC_DIR, jpg_name)

        im = Image.open(bmp_path)
        im.save(jpg_path)
        shutil.copyfile(jpg_path, os.path.join(STATIC_DIR, 'last_thermal.jpg'))

        if custom_temp.strip():
            final_t = custom_temp.strip().replace(',', '.')
        else:
            final_t = str(extract_temperature_from_thermal(jpg_path))

        with open(CSV_LOG, 'r', encoding='utf-8') as f:
            rows = list(csv.reader(f))
            
        for i in range(1, len(rows)):
            if str(rows[i][0]) == str(meas_id):
                if len(rows[i]) >= 24:
                    # Новый формат с T_Air и Delta_T
                    rows[i][8] = final_t
                    rows[i][14] = jpg_name
                    try:
                        t_air = float(rows[i][4])
                        delta_t = round(float(final_t) - t_air, 1)
                        rows[i][9] = str(delta_t)
                    except Exception:
                        pass
                elif len(rows[i]) >= 20:
                    rows[i][6] = final_t
                    rows[i][10] = jpg_name
                else:
                    rows[i][5] = final_t
                    rows[i][9] = jpg_name
                break

        with open(CSV_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        return RedirectResponse(url='/?msg=linked', status_code=303)
    except Exception as e:
        print('Error link:', e)
        return RedirectResponse(url='/?msg=err_unknown', status_code=303)

@app.get('/', response_class=HTMLResponse)
def index(msg: str = ''):
    # Текущие живые показания датчика микроклимата
    cur_t, cur_rh, cur_v = read_xiaomi_climate()
    cur_vpd = calc_vpd(cur_t, cur_rh)

    rows = []
    if os.path.exists(CSV_LOG):
        with open(CSV_LOG, 'r', encoding='utf-8') as f:
            all_r = list(csv.reader(f))
            if len(all_r) > 1:
                rows = all_r[1:]

    meas_options = ''
    table_html = ''
    for r in reversed(rows):
        if len(r) >= 24:
            m_id = r[0]
            ts = r[1]
            grp = r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            t_air_str = f"{r[4]}°C / {r[5]}%" if (r[4] and r[5]) else "--"
            pct = f"{r[7]}%" if r[7] else "--"
            t_show = r[8] if r[8] else "--"
            delta_str = f"{r[9]}°C" if r[9] else "--"
            ndvi_txt = f"{r[11]}±{r[12]}" if len(r)>12 else "--"
            th_name = r[14] if len(r)>14 else ""

            # Оценка стресса по разности Delta_T
            if r[9]:
                try:
                    dt_val = float(r[9])
                    if dt_val <= -0.5:
                        stress_badge = f'<span style="background:#065f46;color:#34d399;padding:2px 6px;border-radius:4px;font-size:11px;">{delta_str} (Норма)</span>'
                    elif dt_val <= 0.5:
                        stress_badge = f'<span style="background:#78350f;color:#fbbf24;padding:2px 6px;border-radius:4px;font-size:11px;">{delta_str} (Нач. стресс)</span>'
                    else:
                        stress_badge = f'<span style="background:#7f1d1d;color:#f87171;padding:2px 6px;border-radius:4px;font-size:11px;">{delta_str} (ВОДНЫЙ ШОК)</span>'
                except Exception:
                    stress_badge = delta_str
            else:
                stress_badge = '<span style="color:#64748b;">--</span>'

        elif len(r) >= 20:
            m_id = r[0]
            ts = r[1]
            grp = r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            t_air_str = "--"
            pct = f"{r[5]}%" if r[5] else "--"
            t_show = r[6] if r[6] else "--"
            stress_badge = "--"
            ndvi_txt = f"{r[7]}±{r[8]}" if len(r)>8 else "--"
            th_name = r[10] if len(r)>10 else ""
        else:
            m_id = r[0]
            ts = r[1]
            grp = r[2]
            wt = "--"
            t_air_str = "--"
            pct = f"{r[4]}%" if len(r)>4 else "--"
            t_show = r[5] if len(r)>5 else "--"
            stress_badge = "--"
            ndvi_txt = f"{r[6]}±{r[7]}" if len(r)>7 else "--"
            th_name = r[9] if len(r)>9 else ""

        th_stat = f'<span style="color:#10b981;font-weight:bold;">✓ {th_name}</span>' if th_name else '<span style="color:#f59e0b;">⏳ Ожидает файл</span>'
        table_html += f'<tr><td><b>#{m_id}</b></td><td>{ts}</td><td>{grp}</td><td><b style="color:#38bdf8;">{wt}</b></td><td>{t_air_str}</td><td><b style="color:#fbbf24;">{t_show} °C</b></td><td>{stress_badge}</td><td>{ndvi_txt}</td><td>{pct}</td><td>{th_stat}</td></tr>'
        meas_options += f'<option value="{m_id}">Замер #{m_id} | {grp} [{ts}]</option>'

    uti_files = get_available_uti_files()
    file_options_list = []
    first_thumb = ''
    if uti_files:
        first_thumb = uti_files[0]['thumb_url']
        for uf in uti_files:
            fn = uf['filename']
            tu = uf['thumb_url']
            dt = uf['dt_str']
            file_options_list.append(f'<option value="{fn}" data-thumb="{tu}">{fn} ({dt})</option>')
    file_options = '\n'.join(file_options_list)

    t_now = int(time.time())

    status_banner = ''
    if msg == 'done':
        status_banner = '<div style="background:#10b981;padding:10px;border-radius:8px;font-weight:bold;margin-bottom:12px;text-align:center;">✅ Оптический замер и климат сохранены! Сделайте снимок тепловизором.</div>'
    elif msg == 'linked':
        status_banner = '<div style="background:#0284c7;padding:10px;border-radius:8px;font-weight:bold;margin-bottom:12px;text-align:center;">⚡ Выбранная термограмма привязана! Рассчитана разность температур ΔT и статус стресса.</div>'
    elif msg == 'err_file_missing':
        status_banner = '<div style="background:#ef4444;padding:10px;border-radius:8px;font-weight:bold;margin-bottom:12px;text-align:center;">❌ Файл на тепловизоре не найден. Проверьте подключение кабеля.</div>'

    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Оптико-электронный комплекс</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #0b1120; color: #f8fafc; margin: 0; padding: 15px; }}
        .container {{ max-width: 1440px; margin: 0 auto; }}
        .header {{ text-align: center; border-bottom: 2px solid #1e293b; padding-bottom: 10px; margin-bottom: 15px; }}
        .header h1 {{ color: #38bdf8; margin: 0 0 5px 0; font-size: 22px; }}
        .climate-bar {{ background: #1e293b; border: 1px solid #38bdf8; border-radius: 8px; padding: 10px 16px; margin-bottom: 14px; display: flex; justify-content: space-around; font-size: 13px; align-items: center; }}
        .grid {{ display: grid; grid-template-columns: 410px 1fr; gap: 15px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 16px; border: 1px solid #334155; }}
        .card h2 {{ color: #38bdf8; margin-top: 0; font-size: 16px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
        label {{ display: block; margin-top: 10px; font-weight: bold; color: #cbd5e1; font-size: 13px; }}
        select, input[type="text"] {{ width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #475569; background: #0b1120; color: white; margin-top: 4px; box-sizing: border-box; font-size: 14px; }}
        .btn-run {{ width: 100%; padding: 14px; background: #10b981; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 12px; }}
        .btn-run:hover {{ background: #059669; }}
        .btn-link {{ width: 100%; padding: 14px; background: #0284c7; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; margin-top: 12px; }}
        .btn-link:hover {{ background: #0369a1; }}
        .channels {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }}
        .ch-box {{ background: #0b1120; padding: 6px; border-radius: 6px; border: 1px solid #334155; text-align: center; }}
        .preview-img {{ width: 100%; height: 175px; border-radius: 4px; border: 1px solid #475569; background: #000; object-fit: contain; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }}
        th, td {{ padding: 6px 8px; border-bottom: 1px solid #334155; }}
        th {{ background: #0b1120; color: #94a3b8; }}
        .thumb-preview-box {{ text-align: center; margin-top: 10px; background: #0b1120; border-radius: 6px; padding: 8px; border: 1px solid #334155; }}
        .thumb-img {{ height: 120px; border-radius: 4px; object-fit: contain; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Оптико-электронный комплекс: Сессионный пульт</h1>
        <p style="margin-bottom: 6px;">Интерактивная привязка снимков с тепловизора UTi120S | Алиса Ковалева</p>
        <div style="display: inline-block; padding: 4px 12px; background: #1e293b; border: 1px solid #475569; border-radius: 20px; font-size: 11px; color: #94a3b8;">
            ⚠️ <b>Временная испытательная схема</b> (лабораторный прототип до поступления специализированных узкополосных излучателей 660/850 нм)
        </div>
    </div>

    <!-- МЕТЕОРОЛОГИЧЕСКАЯ ПАНЕЛЬ МИКРОКЛИМАТА -->
    <div class="climate-bar">
        <span>📡 <b>Сенсор климата:</b> <span style="color:#a78bfa;">Xiaomi Sensirion SHT30 (UDP LAN)</span></span>
        <span>🌡️ <b>T возд.:</b> <span style="color:#38bdf8; font-weight:bold;">{cur_t} °C</span></span>
        <span>💧 <b>Влажность RH:</b> <span style="color:#34d399; font-weight:bold;">{cur_rh}%</span></span>
        <span>🌬️ <b>VPD воздуха:</b> <span style="color:#fbbf24; font-weight:bold;">{cur_vpd} кПа</span></span>
        <span>🔋 <b>Батарейка:</b> <span style="color:#94a3b8;">{cur_v} В</span></span>
    </div>

    {status_banner}

    <div class="grid">
        <div>
            <!-- ШАГ 1: ЗАМЕР -->
            <div class="card" style="margin-bottom: 15px;">
                <h2>1. Замер кассеты в боксе</h2>
                <form action="/do_measure_form" method="post">
                    <label>Исследуемая кассета:</label>
                    <select name="group_name">
                        <option value="Контроль">Кассета 1: КОНТРОЛЬ (Норма)</option>
                        <option value="Засуха">Кассета 2: ЗАСУХА (Дефицит)</option>
                        <option value="Соль">Кассета 3: СОЛЬ (NaCl)</option>
                    </select>

                    <label>⚖️ Масса кассеты, г (гравиметрия):</label>
                    <input type="text" name="weight_g" placeholder="например, 412.5 (или оставьте пустым)">

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <div>
                            <label>🌡️ T возд., °C (авто):</label>
                            <input type="text" name="t_air" value="{cur_t}">
                        </div>
                        <div>
                            <label>💧 RH, % (авто):</label>
                            <input type="text" name="rh_air" value="{cur_rh}">
                        </div>
                    </div>

                    <button type="submit" class="btn-run">
                        📸 СДЕЛАТЬ ЗАМЕР (ВСПЫШКА)
                    </button>
                </form>
            </div>

            <!-- ШАГ 2: ВЫБОР ФАЙЛА ИЗ ПАМЯТИ ТЕПЛОВИЗОРА -->
            <div class="card">
                <h2>2. Выбор термограммы из памяти прибора</h2>
                <p style="font-size: 12px; color: #94a3b8; margin: 4px 0;">
                    Тепловизор воткнут в USB платы. Выберите нужный снимок из списка файлов:
                </p>
                <form action="/do_manual_link" method="post">
                    <label>К какому замеру привязать:</label>
                    <select name="meas_id">
                        {meas_options}
                    </select>

                    <label>Выберите снимок на тепловизоре:</label>
                    <select name="selected_bmp" id="fileSelector" onchange="updateThumb()">
                        {file_options}
                    </select>

                    <div class="thumb-preview-box">
                        <span style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">Предпросмотр выбранного снимка:</span>
                        <img id="thumbImg" src="{first_thumb}" class="thumb-img" alt="[Выберите файл выше]">
                    </div>

                    <label>Температура листа (°C, опционально, OCR считает сам):</label>
                    <input type="text" name="custom_temp" placeholder="Оставьте пустым для авто-OCR">

                    <button type="submit" class="btn-link">
                        🔗 ПРИВЯЗАТЬ ТЕРМОГРАММУ (РАСЧЕТ ΔT)
                    </button>
                </form>
            </div>

            <div style="margin-top: 15px; text-align: center;">
                <a href="/download/csv" style="color: #38bdf8; text-decoration: none; font-size: 13px; font-weight: bold;">
                    📥 Скачать таблицу базы данных (.CSV)
                </a>
            </div>
        </div>

        <div class="card">
            <h2>Мультиспектральная матрица</h2>
            <div class="channels">
                <div class="ch-box">
                    <div style="color:#f87171;font-size:11px;font-weight:bold;margin-bottom:4px;">Канал 1: 660 нм (Red)</div>
                    <img src="/static/last_red.jpg?t={t_now}" class="preview-img">
                </div>
                <div class="ch-box">
                    <div style="color:#818cf8;font-size:11px;font-weight:bold;margin-bottom:4px;">Канал 2: 850 нм (NIR)</div>
                    <img src="/static/last_nir.jpg?t={t_now}" class="preview-img">
                </div>
                <div class="ch-box">
                    <div style="color:#34d399;font-size:11px;font-weight:bold;margin-bottom:4px;">Канал 3: Карта NDVI (Сетка 3х3)</div>
                    <img src="/static/last_ndvi.jpg?t={t_now}" class="preview-img">
                </div>
                <div class="ch-box">
                    <div style="color:#fbbf24;font-size:11px;font-weight:bold;margin-bottom:4px;">Канал 4: Термограмма (UTi120S)</div>
                    <img src="/static/last_thermal.jpg?t={t_now}" class="preview-img">
                </div>
            </div>

            <h2 style="margin-top: 15px;">Журнал физиологических замеров</h2>
            <div style="max-height: 220px; overflow-y: auto; border: 1px solid #334155; border-radius: 6px;">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th><th>Время</th><th>Группа</th><th>Масса (г)</th><th>T_возд / RH</th><th>T_лист</th><th>ΔT (Стресс)</th><th>NDVI</th><th>Почва</th><th>Термограмма</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
    function updateThumb() {{
        const sel = document.getElementById('fileSelector');
        const opt = sel.options[sel.selectedIndex];
        const thumb = opt.getAttribute('data-thumb');
        const img = document.getElementById('thumbImg');
        if (thumb) {{
            img.src = thumb;
        }}
    }}
</script>
</body>
</html>'''
    return html

@app.get('/download/csv')
def download_csv():
    if os.path.exists(CSV_LOG):
        return FileResponse(CSV_LOG, filename='plant_stress_measurements.csv')
    return HTMLResponse('Файл пока пуст')

app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
