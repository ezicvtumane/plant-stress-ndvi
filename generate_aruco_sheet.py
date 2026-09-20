import os
import cv2
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(LOCAL_DIR, 'static')
ARUCO_DIR = os.path.join(STATIC_DIR, 'aruco')
os.makedirs(ARUCO_DIR, exist_ok=True)

ARUCO_CASSETTES = [
    (1, "Кассета 1: КОНТРОЛЬ", "Этап 1: Оптимальный полив", "#059669", colors.HexColor("#059669")),
    (2, "Кассета 2: ЗАСУХА", "Этап 1: Без полива 0–96 ч", "#d97706", colors.HexColor("#d97706")),
    (3, "Кассета 3: СОЛЬ", "Этап 1: Раствор NaCl 1.0%", "#7c3aed", colors.HexColor("#7c3aed")),
    (4, "Кассета 4: КОНТРОЛЬ-2", "Этап 2: Параллельный эталон", "#059669", colors.HexColor("#059669")),
    (5, "Кассета 5: РАННЕЕ СПАСЕНИЕ", "Этап 2: Полив ~40 ч (сигнал)", "#0d9488", colors.HexColor("#0d9488")),
    (6, "Кассета 6: ПОЗДНЕЕ СПАСЕНИЕ", "Этап 2: Полив ~72 ч (увядание)", "#e11d48", colors.HexColor("#e11d48")),
]

# Получаем словарь ArUco 4x4
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

# Генерируем 6 PNG маркеров с белой рамкой (Quiet Zone)
for m_id, name, desc, hex_color, _ in ARUCO_CASSETTES:
    if hasattr(aruco_dict, 'generateImageMarker'):
        marker_raw = aruco_dict.generateImageMarker(m_id, 300)
    else:
        marker_raw = cv2.aruco.drawMarker(aruco_dict, m_id, 300)
    
    marker_with_border = cv2.copyMakeBorder(
        marker_raw, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255
    )
    png_path = os.path.join(ARUCO_DIR, f'aruco_{m_id}.png')
    cv2.imwrite(png_path, marker_with_border)
    print(f'Created {png_path}')

# Создаем HTML-версию листа
html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Лист ArUco-маркеров для кассет | Сириус Большие вызовы</title>
    <style>
        @page {{ size: A4 portrait; margin: 12mm 15mm; }}
        body {{ font-family: 'Segoe UI', -apple-system, Roboto, sans-serif; color: #0f172a; margin: 0; padding: 0; background: #ffffff; }}
        .header {{ text-align: center; border-bottom: 2px solid #00a499; padding-bottom: 10px; margin-bottom: 14px; }}
        .header h1 {{ font-size: 18px; margin: 0 0 4px 0; color: #008276; }}
        .header p {{ font-size: 11px; color: #475569; margin: 0; }}
        .instructions {{ background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 11px; color: #0f766e; line-height: 1.45; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }}
        .marker-card {{ border: 1.5px dashed #94a3b8; border-radius: 8px; padding: 12px; display: flex; align-items: center; gap: 14px; background: #ffffff; box-sizing: border-box; page-break-inside: avoid; }}
        .marker-img-wrap {{ width: 85px; height: 85px; border: 1px solid #e2e8f0; background: #ffffff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
        .marker-img-wrap img {{ width: 80px; height: 80px; image-rendering: pixelated; }}
        .marker-info {{ flex: 1; }}
        .marker-tag {{ display: inline-block; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 4px; margin-bottom: 4px; color: #ffffff; }}
        .marker-title {{ font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 2px; }}
        .marker-desc {{ font-size: 11px; color: #64748b; margin-bottom: 6px; }}
        .marker-size-hint {{ font-size: 9.5px; color: #94a3b8; font-family: monospace; }}
        .cut-mark {{ font-size: 10px; color: #94a3b8; margin-top: 4px; font-family: monospace; }}
        .print-btn {{ display: block; margin: 0 auto 16px auto; padding: 10px 24px; background: #00a499; color: #ffffff; border: none; border-radius: 8px; font-size: 14px; font-weight: bold; cursor: pointer; }}
        @media print {{ .print-btn {{ display: none; }} }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ РАСПЕЧАТАТЬ МАРКЕРЫ НА А4 (Ctrl + P)</button>
    <div class="header">
        <h1>Фидуциальные ArUco-маркеры оптического позиционирования кассет</h1>
        <p>Оптико-электронный комплекс · Всероссийский конкурс «Большие вызовы» (Сириус) · Трек «Агропромышленные и биотехнологии»</p>
    </div>
    <div class="instructions">
        <b>Инструкция по маркировке кассет:</b><br>
        1. Распечатайте этот лист на принтере в масштабе <b>100%</b> (без сжатия полей);<br>
        2. Вырежьте маркеры по пунктирным линиям (внешний габарит ~22×22 мм);<br>
        3. Наклейте маркер на левый верхний бортик соответствующей пластиковой кассеты 3×3;<br>
        4. Защитите маркер прозрачной полоской скотча от попадания капель воды и влажного грунта;<br>
        5. При установке кассеты в бокс NoIR-камера комплекса автоматически распознает маркер и привяжет замер к нужной когорте!
    </div>
    <div class="grid">
"""

for m_id, name, desc, hex_color, _ in ARUCO_CASSETTES:
    html_content += f"""
        <div class="marker-card">
            <div class="marker-img-wrap">
                <img src="/static/aruco/aruco_{m_id}.png" alt="ArUco {m_id}">
            </div>
            <div class="marker-info">
                <span class="marker-tag" style="background:{hex_color};">ArUco ID #{m_id} (DICT_4X4_50)</span>
                <div class="marker-title">{name}</div>
                <div class="marker-desc">{desc}</div>
                <div class="marker-size-hint">Размер: 20×20 мм (угол кассеты)</div>
                <div class="cut-mark">✂ Вырезать по внешнему контуру</div>
            </div>
        </div>
    """

html_content += """
    </div>
    <div style="margin-top:20px; font-size:10px; color:#94a3b8; text-align:center; border-top:1px solid #e2e8f0; padding-top:8px;">
        Алгоритм оптической субпиксельной привязки: OpenCV cv2.aruco · Словарь DICT_4X4_50 · Автор: Ковалева Алиса (10 класс)
    </div>
</body>
</html>
"""

sheet_html_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.html')
with open(sheet_html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f'Created printable HTML: {sheet_html_path}')

# Создаем высокоточный PDF через ReportLab
font_paths = ['C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
font_name = 'Helvetica'
for p in font_paths:
    if os.path.exists(p):
        try:
            pdfmetrics.registerFont(TTFont('CyrillicFont', p))
            font_name = 'CyrillicFont'
            break
        except Exception:
            pass

pdf_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.pdf')
c = canvas.Canvas(pdf_path, pagesize=A4)
w, h = A4

# Заголовок
c.setFillColor(colors.HexColor('#008276'))
c.setFont(font_name, 16)
c.drawCentredString(w / 2, h - 35, "Фидуциальные ArUco-маркеры оптического позиционирования кассет")

c.setFillColor(colors.HexColor('#475569'))
c.setFont(font_name, 9)
c.drawCentredString(w / 2, h - 48, "Оптико-электронный комплекс · Всероссийский конкурс «Большие вызовы» ОЦ «Сириус»")
c.drawCentredString(w / 2, h - 60, "Направление «Агропромышленные и биотехнологии» · Автор: Ковалева Алиса (10 класс, СОШ №282 СПб)")

# Разделительная линия
c.setStrokeColor(colors.HexColor('#00a499'))
c.setLineWidth(1.5)
c.line(35, h - 68, w - 35, h - 68)

# Инструкция в плашке
c.setFillColor(colors.HexColor('#f0fdfa'))
c.setStrokeColor(colors.HexColor('#ccfbf1'))
c.roundRect(35, h - 140, w - 70, 64, 6, fill=1, stroke=1)

c.setFillColor(colors.HexColor('#0f766e'))
c.setFont(font_name, 9)
c.drawString(45, h - 86, "ИНСТРУКЦИЯ ПО РАЗМЕЩЕНИЮ МАРКЕРОВ НА КАССЕТАХ:")
c.setFont(font_name, 8)
c.drawString(45, h - 98, "1. Печать листа выполнять в масштабе 100% (A4, без масштабирования страницы в драйвере принтера).")
c.drawString(45, h - 110, "2. Вырежьте маркеры по пунктирным линиям и наклейте на верхний левый бортик соответствующей кассеты 3x3.")
c.drawString(45, h - 122, "3. Наклейте поверх прозрачную полоску скотча для влагозащиты. Комплекс автоматически распознает когорту в боксе.")

# Сетка 2 x 3 карточек маркеров
card_w = (w - 70 - 15) / 2
card_h = 105
start_x = 35
start_y = h - 165

for idx, (m_id, name, desc, hex_c, rep_color) in enumerate(ARUCO_CASSETTES):
    col = idx % 2
    row = idx // 2
    cx = start_x + col * (card_w + 15)
    cy = start_y - row * (card_h + 15) - card_h

    # Пунктирная рамка карточки
    c.setStrokeColor(colors.HexColor('#94a3b8'))
    c.setLineWidth(1)
    c.setDash(4, 3)
    c.roundRect(cx, cy, card_w, card_h, 6, fill=0, stroke=1)
    c.setDash()

    # Картинка маркера (размер 70x70 pt ~ 25x25 мм)
    img_p = os.path.join(ARUCO_DIR, f'aruco_{m_id}.png')
    if os.path.exists(img_p):
        c.drawImage(img_p, cx + 10, cy + 17, width=70, height=70)
        c.setStrokeColor(colors.HexColor('#e2e8f0'))
        c.setLineWidth(0.5)
        c.rect(cx + 10, cy + 17, 70, 70, fill=0, stroke=1)

    # Бейдж ID
    c.setFillColor(rep_color)
    c.roundRect(cx + 90, cy + 76, 125, 16, 3, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(font_name, 8.5)
    c.drawString(cx + 95, cy + 81, f"ArUco ID #{m_id} (DICT_4X4_50)")

    # Название кассеты
    c.setFillColor(colors.HexColor('#0f172a'))
    c.setFont(font_name, 10)
    c.drawString(cx + 90, cy + 62, name)

    # Описание
    c.setFillColor(colors.HexColor('#64748b'))
    c.setFont(font_name, 8)
    c.drawString(cx + 90, cy + 50, desc)

    # Подсказка
    c.setFillColor(colors.HexColor('#94a3b8'))
    c.setFont(font_name, 7.5)
    c.drawString(cx + 90, cy + 34, "Размер: 20x20 мм (угол кассеты)")
    c.drawString(cx + 90, cy + 22, "- - - Вырезать по контуру - - -")

# Футер
c.setStrokeColor(colors.HexColor('#e2e8f0'))
c.line(35, 30, w - 35, 30)
c.setFillColor(colors.HexColor('#94a3b8'))
c.setFont(font_name, 7.5)
c.drawCentredString(w / 2, 20, "Алгоритм субпиксельного оптического позиционирования: OpenCV cv2.aruco · Образовательный центр «Сириус» 2026")

c.save()
print(f'Created printable PDF: {pdf_path}')
