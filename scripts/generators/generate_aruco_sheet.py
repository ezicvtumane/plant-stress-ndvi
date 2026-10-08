import os
import cv2
import numpy as np
import shutil
import subprocess

CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_FILE_DIR) in ["generators", "tests"]:
    LOCAL_DIR = os.path.dirname(os.path.dirname(CURRENT_FILE_DIR))
elif os.path.basename(CURRENT_FILE_DIR) == "scripts":
    LOCAL_DIR = os.path.dirname(CURRENT_FILE_DIR)
else:
    LOCAL_DIR = CURRENT_FILE_DIR

STATIC_DIR = os.path.join(LOCAL_DIR, 'static')
ARUCO_DIR = os.path.join(STATIC_DIR, 'aruco')
DOCS_DIR = os.path.join(LOCAL_DIR, 'docs')
USER_DOCS_DIR = r"C:\Users\Администратор\Documents"
os.makedirs(ARUCO_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(USER_DOCS_DIR, exist_ok=True)

# 5 основных когорт биологического эксперимента (Синхронный посев 29.09.2026)
ARUCO_CASSETTES = [
    (1, "КАССЕТА №1: КОНТРОЛЬ (ЭТАЛОН)", 
        "ФИЗИОЛОГИЧЕСКИЙ ОПТИМУМ",
        "Полив чистой водой 100% ПВ (20 мл/сут) · Базовый эталон", 
        "НОРМА"),
    (2, "КАССЕТА №2: ЗАСОЛЕНИЕ", 
        "ОСМОТИЧЕСКИЙ СТРЕСС (NaCl 150 мМ)",
        "Раствор 150 мМ NaCl · Строго отдельный лоток-поддон!", 
        "ОСМОС"),
    (3, "КАССЕТА №3: ТЕРМИНАЛЬНАЯ ЗАСУХА", 
        "ПРЕДЕЛ ЖИЗНЕСПОСОБНОСТИ ТКАНИ",
        "Полное прекращение полива 96+ ч (контроль гибели)", 
        "ГИБЕЛЬ"),
    (4, "КАССЕТА №4: ПРЕВЕНТИВНАЯ РЕГИДРАТАЦИЯ", 
        "КУПИРОВАНИЕ СТРЕССА ПО АЛЕРТУ СТАНЦИИ",
        "Полив строго при ΔT ≥ +0.8°C (~40 ч, до потери тургора)", 
        "АЛЕРТ"),
    (5, "КАССЕТА №5: ВИЗУАЛЬНЫЙ КОНТРОЛЬ", 
        "РЕАКТИВНЫЙ ПОЛИВ (ТРАДИЦИОННЫЙ ОСМОТР)",
        "Полив только при макро-поникании листьев (72–84 ч)", 
        "УВЯДАНИЕ"),
]

# Получаем словарь ArUco 4x4
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

# Генерируем чистовые монохромные PNG маркеров (25x25 мм калибровочные с белой Quiet Zone и тонким черным контуром реза)
for m_id, name, strat, reg, status in ARUCO_CASSETTES:
    if hasattr(aruco_dict, 'generateImageMarker'):
        marker_raw = aruco_dict.generateImageMarker(m_id, 240)
    else:
        marker_raw = cv2.aruco.drawMarker(aruco_dict, m_id, 240)
    
    # 1. Белая защитная зона (Quiet Zone) шириной 24 px
    marker_with_quiet = cv2.copyMakeBorder(
        marker_raw, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255
    )
    # 2. Тонкий контур реза (2 px черная рамка по внешнему краю)
    marker_outlined = cv2.copyMakeBorder(
        marker_with_quiet, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0
    )

    png_path = os.path.join(ARUCO_DIR, f'aruco_{m_id}.png')
    _, buf = cv2.imencode('.png', marker_outlined)
    buf.tofile(png_path)
    print(f'Created clean B&W marker: {png_path}')

# ==============================================================================
# 1. HTML-ВЕРСИЯ ЛИСТА МАРКЕРОВ (КОНТУРНЫЙ Ч/Б ДИЗАЙН ДЛЯ МОНОХРОМНОЙ ПЕЧАТИ)
# ==============================================================================
import base64
import json
with open("/tmp/icons_b64.json", "r") as f_ic:
    ICONS_B64 = json.load(f_ic)
cards_html = ""
for m_id, title, strat, protocol, status in ARUCO_CASSETTES:
    png_path = os.path.join(ARUCO_DIR, f'aruco_{m_id}.png')
    with open(png_path, "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode('utf-8')
    img_src = f"data:image/png;base64,{b64_string}"
    b64_icon = ICONS_B64[m_id - 1]
    icon_src = f"data:image/png;base64,{b64_icon}"
    
    cards_html += f"""
        <div class="marker-card">
            <!-- Левый блок: ArUco-маркер для камеры (основной) -->
            <div class="aruco-box">
                <div class="aruco-img-wrap">
                    <img src="{img_src}" alt="ArUco {m_id}">
                </div>
                <div class="aruco-caption">ARUCO #{m_id}</div>
            </div>

            <!-- Пиктограмма оператора -->
            <div class="pictogram-box">
                <img src="{icon_src}" alt="Icon">
            </div>
            <!-- Центральный блок: Контурный номер для человека (Алисы) -->
            <div class="num-badge">
                <div class="num-sub">КАССЕТА</div>
                <div class="num-val">{m_id}</div>
            </div>

            <!-- Правый блок: Научный регламент и статус -->
            <div class="info-block">
                <div class="header-line">
                    <span class="card-title">{title}</span>
                    <span class="status-tag">[{status}]</span>
                </div>
                <div class="card-strategy">{strat}</div>
                <div class="card-protocol">• Режим: {protocol}</div>
                <div class="tech-pill">[CV Метрология] OpenCV DICT_4X4_50 | ID:{m_id} | S_calib = 6.25 см²</div>
            </div>

            <!-- Резервный компактный маркер для противоположного борта -->
            <div class="reserve-box">
                <div class="reserve-img-wrap">
                    <img src="/static/aruco/aruco_{m_id}.png" alt="ArUco {m_id} Reserve">
                </div>
                <div class="reserve-caption">№{m_id} (Резерв)</div>
            </div>
        </div>
    """

html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Лист гибридных ArUco-маркеров (Ч/Б контурный) | Сириус Большие вызовы</title>
    <style>
        @page {{ size: A4 portrait; margin: 8mm 10mm; }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            color: #000000;
            background: #ffffff;
            margin: 0;
            padding: 0;
            line-height: 1.25;
            -webkit-print-color-adjust: exact;
        }}
        .container {{
            width: 100%;
            max-width: 780px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            border-bottom: 2px solid #000000;
            padding-bottom: 6px;
            margin-bottom: 8px;
        }}
        .header h1 {{
            font-size: 15px;
            font-weight: 800;
            margin: 0 0 2px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .header p {{
            font-size: 9.5px;
            color: #333333;
            margin: 0;
        }}
        .instructions {{
            border: 1px dashed #444444;
            border-radius: 6px;
            padding: 6px 10px;
            margin-bottom: 8px;
            font-size: 9px;
            color: #111111;
            line-height: 1.3;
            background: #ffffff;
        }}
        .cards-list {{
            display: flex;
            flex-direction: column;
            gap: 7px;
        }}
        .marker-card {{
            border: 1.5px solid #000000;
            border-radius: 8px;
            padding: 6px 8px;
            display: flex;
            align-items: center;
            background: #ffffff;
            page-break-inside: avoid;
            gap: 10px;
        }}
        /* ArUco box */
        .aruco-box {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 74px;
            flex-shrink: 0;
        }}
        .aruco-img-wrap {{
            width: 68px;
            height: 68px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .aruco-img-wrap img {{
            width: 64px;
            height: 64px;
            image-rendering: pixelated;
        }}
        .aruco-caption {{
            font-size: 7.5px;
            font-weight: bold;
            font-family: monospace;
            margin-top: 2px;
            color: #222222;
        }}
        /* Pictogram */
        .pictogram-box {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 10px;
        }}
        .pictogram-box img {{
            height: 60px;
            width: auto;
        }}
        /* Number badge */
        .num-badge {{
            width: 70px;
            height: 70px;
            border: 2.5px solid #000000;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            background: #ffffff;
        }}
        .num-sub {{
            font-size: 7.5px;
            font-weight: 700;
            font-family: monospace;
            letter-spacing: 0.5px;
            color: #444444;
            margin-bottom: -4px;
        }}
        .num-val {{
            font-size: 42px;
            font-weight: 900;
            line-height: 1;
            color: #000000;
            font-family: Arial, sans-serif;
        }}
        /* Info block */
        .info-block {{
            flex: 1;
            min-width: 0;
            padding-left: 2px;
        }}
        .header-line {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 2px;
        }}
        .card-title {{
            font-size: 11.5px;
            font-weight: 800;
            color: #000000;
        }}
        .status-tag {{
            font-size: 10px;
            font-weight: 900;
            border: 1px solid #000000;
            padding: 1px 5px;
            border-radius: 3px;
        }}
        .card-strategy {{
            font-size: 9.5px;
            font-weight: 700;
            color: #222222;
            margin-bottom: 2px;
        }}
        .card-protocol {{
            font-size: 8.5px;
            color: #111111;
            margin-bottom: 3px;
        }}
        .tech-pill {{
            display: inline-block;
            font-size: 7.5px;
            font-family: monospace;
            border: 1px solid #666666;
            padding: 1px 5px;
            border-radius: 3px;
            color: #222222;
        }}
        /* Reserve box */
        .reserve-box {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 58px;
            flex-shrink: 0;
            border-left: 1px dashed #888888;
            padding-left: 8px;
        }}
        .reserve-img-wrap {{
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .reserve-img-wrap img {{
            width: 46px;
            height: 46px;
            image-rendering: pixelated;
        }}
        .reserve-caption {{
            font-size: 7px;
            font-family: monospace;
            margin-top: 1px;
            color: #444444;
        }}
        .footer {{
            margin-top: 8px;
            font-size: 8px;
            color: #555555;
            text-align: center;
            border-top: 1px solid #888888;
            padding-top: 4px;
        }}
        .print-btn {{
            display: block;
            margin: 0 auto 10px auto;
            padding: 8px 20px;
            background: #000000;
            color: #ffffff;
            border: 2px solid #000000;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
        }}
        .print-btn:hover {{
            background: #ffffff;
            color: #000000;
        }}
        @media print {{
            .print-btn {{ display: none; }}
            body {{ padding: 0; }}
            .marker-card {{ border: 1.5px solid #000000 !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-btn" onclick="window.print()">🖨️ РАСПЕЧАТАТЬ НА Ч/Б ПРИНТЕРЕ (A4, Ctrl + P)</button>
        <div class="header">
            <h1>Фидуциальные метки кассет: Human-Robot Interface (Ч/Б контурный)</h1>
            <p>Станция спектрального и термографического скрининга стресса растений · 5 синхронных когорт (n = 45)</p>
            <p>Исследовательский проект · Конкурс «Большие вызовы» ОЦ «Сириус» 2026 · Ковалева Алиса</p>
        </div>
        <div class="instructions">
            <b>Инструкция по маркировке кассет для монохромной печати:</b><br>
            • Распечатайте на обычном офисном принтере в масштабе <b>100%</b> (без масштабирования страницы).<br>
            • Вырежьте карточку целиком по внешнему черному контуру и наклейте на лицевой бортик кассеты (камера считывает ArUco, Алиса видит гигантскую цифру <b>1–5</b>).<br>
            • Справа отделен <b>резервный квадратный маркер</b> (№1–5) — его можно наклеить на тыльный бортик для считывания при любом развороте кассеты.<br>
            • После наклейки защитите метки полоской прозрачного скотча для влагозащиты от капель воды при поливе.
        </div>
        <div class="cards-list">
            {cards_html}
        </div>
        <div class="footer">
            Машинное зрение: OpenCV cv2.aruco · Словарь DICT_4X4_50 · Радиометрический калибровочный эталон 25.0×25.0 мм (6.25 см²)
        </div>
    </div>
</body>
</html>
"""

sheet_html_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.html')
with open(sheet_html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f'Created printable HTML: {sheet_html_path}')

# Copy to docs and user Documents
docs_html = os.path.join(DOCS_DIR, 'aruco_markers_sheet.html')
shutil.copy2(sheet_html_path, docs_html)
user_html = os.path.join(USER_DOCS_DIR, 'Лист_ArUco_маркеров_для_5_кассет.html')
shutil.copy2(sheet_html_path, user_html)

# ==============================================================================
# 2. КОМПИЛЯЦИЯ ВЫСОКОТОЧНОГО ВЕКТОРНОГО PDF ЧЕРЕЗ CHROME HEADLESS
# ==============================================================================
pdf_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.pdf')
chrome_paths = [
    r"/usr/bin/chromium",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "google-chrome",
    "chromium"
]
chrome_bin = next((p for p in chrome_paths if os.path.exists(p) or shutil.which(p)), None)

if chrome_bin:
    cmd = [
        chrome_bin,
        '--headless',
        '--disable-gpu',
        '--no-sandbox',
        '--no-pdf-header-footer',
        f'--print-to-pdf={pdf_path}',
        sheet_html_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(pdf_path):
        print(f'Compiled clean B&W PDF: {pdf_path} ({os.path.getsize(pdf_path)/1024:.1f} KB)')
        docs_pdf = os.path.join(DOCS_DIR, 'aruco_markers_sheet.pdf')
        shutil.copy2(pdf_path, docs_pdf)
        user_pdf = os.path.join(USER_DOCS_DIR, 'Лист_ArUco_маркеров_для_5_кассет.pdf')
        shutil.copy2(pdf_path, user_pdf)
        print(f'Copied PDF to {docs_pdf} and {user_pdf}')
    else:
        print('Chrome headless warning:', res.stderr)
else:
    print('Chrome not found for PDF export.')

print('All B&W outline markers generated successfully!')
