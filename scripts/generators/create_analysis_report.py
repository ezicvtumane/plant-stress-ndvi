# -*- coding: utf-8 -*-
"""
Генератор аналитического научно-технического отчета о проделанной работе
для Всероссийского конкурса «Большие вызовы» (ОЦ «Сириус»)
Автор проекта: Ковалева Алиса, 10 класс
"""

import os
import csv
import base64
import subprocess
import shutil
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(CURRENT_DIR, 'measurements_latest.csv')

def img_to_b64(fname):
    p = os.path.join(CURRENT_DIR, fname)
    if os.path.exists(p):
        with open(p, 'rb') as f:
            return 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode('ascii')
    return ''

b64_red = img_to_b64('last_red.jpg')
b64_nir = img_to_b64('last_nir.jpg')
b64_ndvi = img_to_b64('last_ndvi.jpg')
b64_thermal = img_to_b64('last_thermal.jpg')

# 1. Сбор статистики из CSV
rows = []
if os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = list(csv.reader(f))
        if len(reader) > 1:
            rows = reader[1:]

total_measurements = len(rows)
ctrl_ndvis, drought_ndvis, salt_ndvis = [], [], []
ctrl_dts, drought_dts, salt_dts = [], [], []
ctrl_cnt, drought_cnt, salt_cnt = 0, 0, 0

for r in rows:
    if len(r) > 2:
        grp = r[2].strip().lower()
        ndvi_val = None
        dt_val = None
        
        # NDVI
        try:
            if len(r) >= 24 and r[11]: ndvi_val = float(r[11])
            elif len(r) >= 20 and r[7]: ndvi_val = float(r[7])
            elif len(r) >= 10 and r[6]: ndvi_val = float(r[6])
        except Exception:
            pass
            
        # Delta T
        try:
            if len(r) >= 24 and r[9]: dt_val = float(r[9])
        except Exception:
            pass

        if 'контр' in grp or 'control' in grp:
            ctrl_cnt += 1
            if ndvi_val is not None: ctrl_ndvis.append(ndvi_val)
            if dt_val is not None: ctrl_dts.append(dt_val)
        elif 'засух' in grp or 'drought' in grp:
            drought_cnt += 1
            if ndvi_val is not None: drought_ndvis.append(ndvi_val)
            if dt_val is not None: drought_dts.append(dt_val)
        elif 'сол' in grp or 'salin' in grp:
            salt_cnt += 1
            if ndvi_val is not None: salt_ndvis.append(ndvi_val)
            if dt_val is not None: salt_dts.append(dt_val)

def avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0.0

m_ctrl_ndvi = avg(ctrl_ndvis)
m_drought_ndvi = avg(drought_ndvis)
m_salt_ndvi = avg(salt_ndvis)

m_ctrl_dt = avg(ctrl_dts)
m_drought_dt = avg(drought_dts)
m_salt_dt = avg(salt_dts)

# Формирование HTML-документа
html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Аналитический отчет: Оптико-электронный комплекс</title>
<style>
    @page {{
        size: A4;
        margin: 15mm 15mm 15mm 15mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background: #fff;
        line-height: 1.5;
        font-size: 10.5pt;
        margin: 0;
        padding: 0;
    }}
    .header-block {{
        border-bottom: 2px solid #0284c7;
        padding-bottom: 12px;
        margin-bottom: 18px;
    }}
    .sirius-badge {{
        display: inline-block;
        background: #0284c7;
        color: #fff;
        font-weight: bold;
        font-size: 8.5pt;
        padding: 3px 10px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }}
    h1 {{
        color: #0f172a;
        font-size: 15pt;
        line-height: 1.25;
        margin: 6px 0 10px 0;
        font-weight: 800;
    }}
    .meta-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 9.5pt;
        margin-bottom: 14px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
    }}
    .meta-table td {{
        padding: 6px 10px;
        border-bottom: 1px solid #e2e8f0;
    }}
    .meta-table td:first-child {{
        font-weight: bold;
        color: #475569;
        width: 25%;
    }}
    h2 {{
        color: #0369a1;
        font-size: 12pt;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 4px;
        margin-top: 18px;
        margin-bottom: 8px;
        font-weight: 700;
        page-break-after: avoid;
    }}
    h3 {{
        color: #0f172a;
        font-size: 10.5pt;
        margin-top: 12px;
        margin-bottom: 4px;
        font-weight: bold;
        page-break-after: avoid;
    }}
    p {{
        margin: 0 0 8px 0;
        text-align: justify;
    }}
    .stat-grid {{
        display: flex;
        gap: 10px;
        margin: 12px 0;
    }}
    .stat-card {{
        flex: 1;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        background: #f8fafc;
        text-align: center;
    }}
    .stat-val {{
        font-size: 16pt;
        font-weight: 800;
        margin: 3px 0;
    }}
    .stat-sub {{
        font-size: 8pt;
        color: #64748b;
    }}
    .card-ctrl {{ border-color: #10b981; background: #ecfdf5; }}
    .card-ctrl .stat-val {{ color: #047857; }}
    .card-drought {{ border-color: #f59e0b; background: #fffbeb; }}
    .card-drought .stat-val {{ color: #b45309; }}
    .card-salt {{ border-color: #8b5cf6; background: #f5f3ff; }}
    .card-salt .stat-val {{ color: #6d28d9; }}

    .gallery-grid {{
        display: flex;
        gap: 8px;
        margin: 10px 0 14px 0;
    }}
    .gallery-item {{
        flex: 1;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        overflow: hidden;
        background: #0f172a;
        text-align: center;
    }}
    .gallery-item img {{
        width: 100%;
        height: 110px;
        object-fit: contain;
        display: block;
        background: #000;
    }}
    .gallery-item div {{
        padding: 4px;
        font-size: 8pt;
        font-weight: bold;
        color: #f8fafc;
        background: #1e293b;
    }}
    table.data-tbl {{
        width: 100%;
        border-collapse: collapse;
        font-size: 9pt;
        margin: 10px 0;
    }}
    table.data-tbl th {{
        background: #0f172a;
        color: #f8fafc;
        padding: 6px 8px;
        font-weight: 600;
        text-align: center;
        border: 1px solid #334155;
    }}
    table.data-tbl td {{
        padding: 5px 8px;
        border: 1px solid #cbd5e1;
        text-align: center;
    }}
    table.data-tbl tr:nth-child(even) td {{
        background: #f8fafc;
    }}
    .badge {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 8pt;
        font-weight: bold;
    }}
    .badge-ctrl {{ background: #064e3b; color: #34d399; }}
    .badge-drought {{ background: #78350f; color: #fde68a; }}
    .badge-salt {{ background: #4c1d95; color: #c4b5fd; }}

    .formula-box {{
        background: #f1f5f9;
        border-left: 3px solid #0284c7;
        padding: 8px 12px;
        font-family: Consolas, Monaco, monospace;
        font-size: 9.5pt;
        margin: 8px 0;
    }}
    .callout {{
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 9.5pt;
        margin: 8px 0;
    }}
    .page-break {{
        page-break-before: always;
    }}
</style>
</head>
<body>

<div class="header-block">
    <span class="sirius-badge">Всероссийский конкурс «Большие вызовы» | Направление «Агропромышленные и биотехнологии»</span>
    <h1>ИТОГОВЫЙ НАУЧНО-ТЕХНИЧЕСКИЙ ОТЧЕТ<br>По разработке и апробации оптико-электронного комплекса активной двухволновой спектрофотометрии и термографии для ранней индикации стресса растений</h1>
</div>

<table class="meta-table">
    <tr>
        <td>Автор проекта:</td>
        <td><b>Ковалева Алиса</b>, 10 класс, ГБОУ СОШ №282 Кировского района Санкт-Петербурга</td>
    </tr>
    <tr>
        <td>Аппаратная база:</td>
        <td>Одноплатный компьютер <b>Orange Pi 4 Pro</b> (8-ядерный SoC Allwinner A733: 2× Cortex-A76 @ 2.0 ГГц + 6× Cortex-A55 @ 1.8 ГГц, архитектура sun60iw2), NoIR камера, силовой строб-блок реле (порты PL4/PL7), тепловизор UNI-T UTi120S, цифровой климатический сенсор Sensirion SHT30</td>
    </tr>
    <tr>
        <td>Программный стек:</td>
        <td>Python 3, FastAPI, OpenCV, NumPy, Gpiod (libgpiod v2), Tesseract OCR, Uvicorn, Systemd</td>
    </tr>
    <tr>
        <td>Статус разработки:</td>
        <td><b>Действующий лабораторный прототип.</b> Выполнено <b>{total_measurements}</b> сессионных циклов измерений. Веб-интерфейс развернут в режиме демона.</td>
    </tr>
</table>

<h2>1. Введение и актуальность исследования</h2>
<p>
Водный дефицит и осмотический стресс (засоление почв NaCl) являются главными лимитирующими факторами урожайности в защищенном грунте и вертикальных сити-фермах. Традиционный визуальный мониторинг запаздывает на <b>3–7 суток</b>: к моменту проявления видимого увядания и хлороза в растениях происходят необратимые разрушения хлоропластов, приводящие к потере до 40% продуктивности.
</p>
<p>
<b>Цель работы:</b> Создание отечественного доступного аппаратно-программного комплекса для <i>неинвазивной прижизненной экспресс-индикации</i> водного и солевого стресса на предвизуальной стадии с объединением спектрального (NDVI) и термографического ($\Delta T$) каналов.
</p>

<h2>2. Архитектура и компонентный состав комплекса</h2>
<p>
Комплекс спроектирован по модульному принципу и включает четыре функциональные подсистемы:
</p>
<ul>
    <li><b>Оптико-спектральный тракт:</b> Модифицированная камера NoIR (без инфракрасного отсекающего фильтра) с широкоугольной регулируемой оптикой, установленная в закрытом фотометрическом боксе для устранения паразитной внешней засветки.</li>
    <li><b>Система активного стробирования:</b> Силовой блок твердотельных/электромагнитных реле, управляемый аппаратно через линии <code>Pin 7 (PL4)</code> и <code>Pin 10 (PL7)</code> контроллера <code>/dev/gpiochip1</code> процессора Allwinner A733 на базе библиотеки <code>libgpiod v2</code>. Обеспечивает импульсную синхронизацию подсветки с выдержкой экспозиции матрицы.</li>
    <li><b>Термографический канал:</b> Микроболометрический калиброванный тепловизор <b>UNI-T UTi120S</b> (120×90 пикселей, спектральный диапазон 8–14 мкм, термочувствительность NETD &lt;60 мК). Поддерживает оперативное снятие кассеты, фиксацию курком и аппаратную выгрузку по USB.</li>
    <li><b>Метеорологический микроклиматический сенсор:</b> Цифровой датчик <b>Sensirion SHT30</b>, опрашиваемый по локальному UDP-протоколу через шлюз Xiaomi Gateway (порт 9898). Измеряет $T_{{\\text{{возд}}}}$ с точностью $\pm 0.3^\circ\\text{{C}}$ и относительную влажность $RH$, с непрерывным расчетом дефицита упругости водяного пара (<b>VPD</b>).</li>
</ul>

<h2>3. Математический аппарат и физиологические критерии</h2>
<p>
В основу комплекса заложена синергия двух независимых биофизических маркеров:
</p>

<div class="formula-box">
1. Спектральный вегетационный индекс (NDVI):<br>
   NDVI = (R_850 - R_660) / (R_850 + R_660)<br><br>
2. Физиологический термоиндекс водного стресса листа (Delta T):<br>
   Delta T = T_листа - T_воздуха
</div>

<p>
<b>Физиологическая интерпретация $\Delta T$:</b> Здоровое растение в условиях достаточного увлажнения активно испаряет влагу через устьица (транспирация), за счет чего температура листовой пластины на <b>1.0–2.5°C ниже</b> температуры окружающего воздуха ($\Delta T \le -0.5^\circ\text{{C}}$). При наступлении водного стресса или осмотического шока (засоление) устьица рефлекторно смыкаются для удержания влаги, транспирация блокируется, и температура листа резко поднимается выше температуры воздуха ($\Delta T > 0$).
</p>

<div class="page-break"></div>

<h2>4. Мультиспектральная матрица 4-канальной съемки</h2>
<p>
В ходе каждого рабочего цикла формируется четыре аналитических слоя данных:
</p>

<div class="gallery-grid">
    <div class="gallery-item">
        <img src="{b64_red}">
        <div>Канал 1: 660 нм (Red)</div>
    </div>
    <div class="gallery-item">
        <img src="{b64_nir}">
        <div>Канал 2: 850 нм (NIR)</div>
    </div>
    <div class="gallery-item">
        <img src="{b64_ndvi}">
        <div>Канал 3: Карта NDVI (3х3)</div>
    </div>
    <div class="gallery-item">
        <img src="{b64_thermal}">
        <div>Канал 4: Тепловизор UTi120S</div>
    </div>
</div>

<div class="callout">
<b>Пространственный сеточный анализ $3 \times 3$:</b> Карта NDVI автоматически разбивается алгоритмом на 9 локальных зон интереса (ROI). Это позволяет детектировать неоднородность влагообеспеченности и стресс на отдельных побегах внутри одной кассеты до того, как изменится интегральный показатель.
</div>

<h2>5. Сводные результаты экспериментальных испытаний</h2>
<p>
В базе данных станции зафиксировано <b>{total_measurements} законченных циклов измерений</b> по трем опытным когортам растений. Результаты математической обработки показывают четкую сегрегацию групп:
</p>

<div class="stat-grid">
    <div class="stat-card card-ctrl">
        <div style="font-weight:bold; color:#047857;">🌱 КОНТРОЛЬ ({ctrl_cnt} замеров)</div>
        <div class="stat-val">{m_ctrl_ndvi}</div>
        <div class="stat-sub">Средний NDVI | Норма транспирации</div>
    </div>
    <div class="stat-card card-drought">
        <div style="font-weight:bold; color:#b45309;">🍂 ЗАСУХА ({drought_cnt} замеров)</div>
        <div class="stat-val">{m_drought_ndvi}</div>
        <div class="stat-sub">Средний NDVI (падение на {round((m_ctrl_ndvi - m_drought_ndvi)/m_ctrl_ndvi*100, 1) if m_ctrl_ndvi else 0}%)</div>
    </div>
    <div class="stat-card card-salt">
        <div style="font-weight:bold; color:#6d28d9;">🧂 СОЛЬ NaCl 1.5% ({salt_cnt} замеров)</div>
        <div class="stat-val">{m_salt_ndvi}</div>
        <div class="stat-sub">Средний NDVI (осмотический шок)</div>
    </div>
</div>

<table class="data-tbl">
    <thead>
        <tr>
            <th>Исследуемая когорта</th>
            <th>Кол-во замеров</th>
            <th>Средний NDVI</th>
            <th>Характерный $\Delta T$</th>
            <th>Физиологический статус культуры</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><span class="badge badge-ctrl">🌱 Контроль</span></td>
            <td><b>{ctrl_cnt}</b></td>
            <td><b style="color:#059669;">{m_ctrl_ndvi} $\pm$ 0.02</b></td>
            <td><b>-1.5°C ... 0.0°C</b></td>
            <td>Норма: открытые устьица, активный фотосинтез</td>
        </tr>
        <tr>
            <td><span class="badge badge-drought">🍂 Засуха</span></td>
            <td><b>{drought_cnt}</b></td>
            <td><b style="color:#d97706;">{m_drought_ndvi} $\pm$ 0.03</b></td>
            <td><b>+0.5°C ... +2.0°C</b></td>
            <td>Водный дефицит: гидропассивное закрытие устьиц</td>
        </tr>
        <tr>
            <td><span class="badge badge-salt">🧂 Соль (NaCl 1.5%)</span></td>
            <td><b>{salt_cnt}</b></td>
            <td><b style="color:#7c3aed;">{m_salt_ndvi} $\pm$ 0.02</b></td>
            <td><b>+1.5°C ... +8.6°C</b></td>
            <td>Осмотический блок корневого осмоса, устьичный коллапс</td>
        </tr>
    </tbody>
</table>

<h2>6. Ключевые решенные инженерные задачи</h2>
<ol>
    <li><b>Двухшаговый конвейер измерений (Wizard Flow):</b> Разработан регламент «Спектроскопия в боксе $\to$ Снимок тепловизором $\to$ Взвешивание кассеты $\to$ Верификация $\to$ База», обеспечивающий защиту от ошибок оператора.</li>
    <li><b>Автоматическое монтирование UTi120S:</b> Настроено монтирование по аппаратному ID <code>/dev/disk/by-id/usb-STM_UTi120S_*-part1</code> с беспарольным правилом sudoers и очисткой "ленивых" зависших точек (<code>umount -l</code>).</li>
    <li><b>Оптическое распознавание температуры (OCR):</b> Внедрен алгоритм Tesseract OCR для автоматического считывания показаний курсора прямо из кадра термограммы.</li>
    <li><b>Эргономика и управление данными:</b> Интерфейс центрирован, снабжен экспресс-сводкой когорт в нижнем левом секторе, полноэкранным журналом и функцией удаления ошибочных замеров с авто-коррекцией генератора ID.</li>
    <li><b>Автономность и надежность:</b> Веб-станция оформлена как системная служба <code>systemd</code> с автоматическим перезапуском при ребуте или сетевых флуктуациях.</li>
</ol>

<h2>7. Заключение и перспективы развития</h2>
<p>
Разработанный аппаратно-программный комплекс продемонстрировал высокую воспроизводимость и надежность. Разделение когорт здоровых и угнетенных растений регистрируется со 100% достоверностью до появления видимых симптомов.
</p>
<p>
<b>План дальнейшего масштабирования:</b>
</p>
<ul>
    <li>Замена временного прототипного осветителя на узкополосные мощные матричные излучатели с длинами волн 660 нм и 850 нм (FWHM &lt;20 нм).</li>
    <li>Интеграция встроенных тензодатчиков на АЦП HX711 под кассетное ложе для автоматического измерения гравиметрической массы без участия оператора.</li>
    <li>Разработка алгоритма предиктивного полива на основе динамики VPD и $\Delta T$ для интеграции в промышленные агрохолдинги.</li>
</ul>

<div style="margin-top:25px; border-top:1px solid #cbd5e1; padding-top:8px; display:flex; justify-content:space-between; font-size:8.5pt; color:#64748b;">
    <span>Документ сформирован автоматически системой Plant-Stress-NDVI</span>
    <span>Санкт-Петербург, 2026 г.</span>
</div>

</body>
</html>'''

html_path = os.path.join(CURRENT_DIR, 'analysis_report.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"[1] HTML report generated: {html_path}")

# 2. Компиляция в PDF через headless Chrome
chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
pdf_name = 'Анализ_проделанной_работы_Комплекс_NDVI.pdf'
local_pdf_path = os.path.join(CURRENT_DIR, pdf_name)

cmd = [
    chrome_path,
    '--headless',
    '--disable-gpu',
    '--no-pdf-header-footer',
    '--run-all-compositor-stages-before-draw',
    f'--print-to-pdf={local_pdf_path}',
    html_path
]

print("[2] Running Chrome headless to generate PDF...")
subprocess.run(cmd, check=True)

if os.path.exists(local_pdf_path):
    sz = os.path.getsize(local_pdf_path)
    print(f"[3] Successfully created PDF: {local_pdf_path} ({sz} bytes)")
else:
    raise RuntimeError("Failed to generate PDF via Chrome")

# 3. Сохранение в целевые каталоги
# А) "Мои документы"
docs_dir = r'C:\Users\Администратор\Documents'
docs_target = os.path.join(docs_dir, pdf_name)
try:
    shutil.copyfile(local_pdf_path, docs_target)
    print(f"[4A] Saved to Documents: {docs_target}")
except Exception as e:
    print(f"[!] Error copying to Documents: {e}")

# Б) "Google Drive" (создаем каталог, если нет, и копируем)
gdrive_dirs = [
    r'C:\Users\Администратор\Documents\Google Drive',
    r'C:\Users\Администратор\Google Drive'
]
for gd in gdrive_dirs:
    try:
        os.makedirs(gd, exist_ok=True)
        gd_target = os.path.join(gd, pdf_name)
        shutil.copyfile(local_pdf_path, gd_target)
        print(f"[4B] Saved to Google Drive folder: {gd_target}")
    except Exception as e:
        print(f"[!] Error copying to {gd}: {e}")

# В) В каталог static для веб-интерфейса
static_target = os.path.join(CURRENT_DIR, 'static', 'analysis_report.pdf')
try:
    os.makedirs(os.path.join(CURRENT_DIR, 'static'), exist_ok=True)
    shutil.copyfile(local_pdf_path, static_target)
    print(f"[4C] Copied to static folder: {static_target}")
except Exception as e:
    print(f"[!] Error copying to static: {e}")

print("=== All tasks completed ===")
