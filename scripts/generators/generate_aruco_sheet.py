import os
import cv2
import numpy as np
import shutil
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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

# 5 основных когорт биологического эксперимента (синхронный посев 29.09.2026)
ARUCO_CASSETTES = [
    (1, "Кассета №1: КОНТРОЛЬ (Оптимум)", 
        "Оптимальный полив чистой водой (100% ПВ), базовый физиологический эталон", 
        "Регламент: регулярный полив водой 20 мл", 
        "#059669", colors.HexColor("#059669"), "🌱"),
    (2, "Кассета №2: ЗАСОЛЕНИЕ (150 мМ NaCl)", 
        "Осмотический стресс. КРИТИЧЕСКИ ВАЖНО: отдельный герметичный лоток-поддон!", 
        "Регламент: 150 мМ NaCl, строго изолированный поддон!", 
        "#7c3aed", colors.HexColor("#7c3aed"), "🧂"),
    (3, "Кассета №3: ПРЕВЕНТИВНАЯ РЕГИДРАТАЦИЯ", 
        "Засуха -> доклинический полив по алерту станции (ΔT > +0.8°C, ~40 ч, до увядания)", 
        "Регламент: полив водой строго по первому сигналу тревоги комплекса", 
        "#eab308", colors.HexColor("#eab308"), "🔬"),
    (4, "Кассета №4: ВИЗУАЛЬНЫЙ КОНТРОЛЬ", 
        "Засуха -> полив только при явном визуальном поникании листьев (72–84 ч, традиционно)", 
        "Регламент: полив водой при видимой потере тургора (опоздание на 36–48 ч)", 
        "#2563eb", colors.HexColor("#2563eb"), "👁️"),
    (5, "Кассета №5: ТЕРМИНАЛЬНАЯ ЗАСУХА", 
        "Без полива 96+ ч (оцифровка кривой деградации ткани и точки невозврата)", 
        "Регламент: полное прекращение полива до гибели растений", 
        "#dc2626", colors.HexColor("#dc2626"), "⚠️"),
]

# Получаем словарь ArUco 4x4
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

# Генерируем PNG маркеров с белой защитной зоной (Quiet Zone) и яркой цветной рамкой по периметру
for m_id, name, desc, reg, hex_color, _, _ in ARUCO_CASSETTES:
    if hasattr(aruco_dict, 'generateImageMarker'):
        marker_raw = aruco_dict.generateImageMarker(m_id, 240)
    else:
        marker_raw = cv2.aruco.drawMarker(aruco_dict, m_id, 240)
    
    # 1. Белая защитная зона (Quiet Zone) шириной 24 px
    marker_with_quiet = cv2.copyMakeBorder(
        marker_raw, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255
    )
    # 2. Конвертация в 3-канальный BGR
    marker_bgr = cv2.cvtColor(marker_with_quiet, cv2.COLOR_GRAY2BGR)
    
    # 3. Индивидуальная цветная окантовка (14 px) по внешнему периметру кассеты
    h_c = hex_color.lstrip('#')
    rgb = tuple(int(h_c[i:i+2], 16) for i in (0, 2, 4))
    bgr = (rgb[2], rgb[1], rgb[0])
    marker_colored = cv2.copyMakeBorder(
        marker_bgr, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=bgr
    )

    png_path = os.path.join(ARUCO_DIR, f'aruco_{m_id}.png')
    _, buf = cv2.imencode('.png', marker_colored)
    buf.tofile(png_path)
    print(f'Created {png_path} with border {hex_color}')

# ==============================================================================
# 1. HTML-ВЕРСИЯ ЛИСТА МАРКЕРОВ
# ==============================================================================
html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Лист ArUco-маркеров для 5 кассет | Сириус Большие вызовы</title>
    <style>
        @page {{ size: A4 portrait; margin: 10mm 12mm; }}
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', -apple-system, Roboto, sans-serif; color: #0f172a; margin: 0; padding: 0; background: #ffffff; line-height: 1.3; }}
        .container {{ width: 100%; max-width: 780px; margin: 0 auto; }}
        .header {{ text-align: center; border-bottom: 2px solid #00a499; padding-bottom: 8px; margin-bottom: 10px; }}
        .header h1 {{ font-size: 16px; margin: 0 0 4px 0; color: #008276; letter-spacing: 0.2px; }}
        .header p {{ font-size: 10.5px; color: #475569; margin: 0 0 2px 0; }}
        .instructions {{ background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; font-size: 10.5px; color: #0f766e; line-height: 1.35; }}
        .cards-list {{ display: flex; flex-direction: column; gap: 9px; }}
        .marker-card {{ border: 1.5px dashed #cbd5e1; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; background: #ffffff; page-break-inside: avoid; border-left: 6px solid #cbd5e1; }}
        .marker-slot {{ display: flex; flex-direction: column; align-items: center; justify-content: center; width: 84px; flex-shrink: 0; }}
        .marker-img-wrap {{ width: 76px; height: 76px; border-radius: 6px; background: #ffffff; display: flex; align-items: center; justify-content: center; }}
        .marker-img-wrap img {{ width: 70px; height: 70px; image-rendering: pixelated; }}
        .marker-label {{ font-size: 8px; font-weight: bold; font-family: monospace; margin-top: 3px; }}
        .marker-info {{ flex: 1; padding: 0 14px; min-width: 0; }}
        .marker-tag {{ display: inline-block; font-size: 9px; font-weight: 800; padding: 2px 7px; border-radius: 3px; margin-bottom: 3px; color: #ffffff; }}
        .marker-title {{ font-size: 12.5px; font-weight: 700; color: #0f172a; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .marker-desc {{ font-size: 10px; color: #334155; margin-bottom: 2px; }}
        .marker-reg {{ font-size: 9.5px; color: #0f766e; font-weight: 600; }}
        .marker-hint {{ font-size: 8.5px; color: #64748b; font-family: monospace; margin-top: 2px; }}
        .footer {{ margin-top: 10px; font-size: 9px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 6px; }}
        .print-btn {{ display: block; margin: 0 auto 12px auto; padding: 9px 22px; background: #00a499; color: #ffffff; border: none; border-radius: 6px; font-size: 13px; font-weight: bold; cursor: pointer; }}
        @media print {{ .print-btn {{ display: none; }} body {{ padding: 0; }} }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-btn" onclick="window.print()">🖨️ РАСПЕЧАТАТЬ МАРКЕРЫ НА А4 (Ctrl + P)</button>
        <div class="header">
            <h1>Фидуциальные ArUco-маркеры оптического позиционирования кассет</h1>
            <p>Комплект для 5 экспериментальных когорт (Синхронный посев 29.09.2026, кассеты 3×3)</p>
            <p>Оптико-электронный комплекс · Конкурс «Большие вызовы» ОЦ «Сириус» · Ковалева Алиса (10 класс)</p>
        </div>
        <div class="instructions">
            <b>Инструкция по маркировке 5 кассет (Цветовая синхронизация с веб-станцией):</b><br>
            1. Распечатайте лист в масштабе <b>100%</b> (без сжатия полей А4). Каждый маркер обведен <b>своим цветом</b> по периметру: 🟢 К1 Контроль (Зеленый), 🟣 К2 Соль (Фиолетовый), 🟡 К3 Прибор (Желтый), 🔵 К4 Глаза (Синий), 🔴 К5 Гибель (Красный).<br>
            2. Вырежьте маркеры по цветному периметру (~25×25 мм) и наклейте на противоположные уголки соответствующей кассеты (основной + резерв).<br>
            3. Защитите каждый маркер прозрачной полоской скотча для защиты от капель воды при поливе.<br>
            4. При установке кассеты в бокс любой стороной NoIR-камера автоматически распознает маркер и точно привяжет замер к когорте!
        </div>
        <div class="cards-list">
"""

for m_id, name, desc, reg, hex_color, _, emoji in ARUCO_CASSETTES:
    html_content += f"""
            <div class="marker-card" style="border-left-color: {hex_color};">
                <div class="marker-slot">
                    <div class="marker-img-wrap" style="border: 3px solid {hex_color};">
                        <img src="/static/aruco/aruco_{m_id}.png" alt="ArUco {m_id}">
                    </div>
                    <div class="marker-label" style="color:{hex_color};">№{m_id} (Основной)</div>
                </div>
                <div class="marker-info">
                    <span class="marker-tag" style="background:{hex_color};">ArUco ID #{m_id} (DICT_4X4_50)</span>
                    <div class="marker-title">{emoji} {name}</div>
                    <div class="marker-desc">{desc}</div>
                    <div class="marker-reg">📌 {reg}</div>
                    <div class="marker-hint">✂ Цветная рамка периметра: <b>{hex_color}</b> · Вырезать по контуру · Наклеить на бортик кассеты</div>
                </div>
                <div class="marker-slot">
                    <div class="marker-img-wrap" style="border: 3px solid {hex_color};">
                        <img src="/static/aruco/aruco_{m_id}.png" alt="ArUco {m_id}">
                    </div>
                    <div class="marker-label" style="color:{hex_color};">№{m_id} (Резерв)</div>
                </div>
            </div>
    """

html_content += """
        </div>
        <div class="footer">
            Субпиксельная оптическая автопривязка: OpenCV cv2.aruco · Словарь DICT_4X4_50 · Радиометрический эталон 25.0×25.0 мм (6.25 см²)
        </div>
    </div>
</body>
</html>
"""

sheet_html_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.html')
with open(sheet_html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f'Created printable HTML: {sheet_html_path}')

# ==============================================================================
# 2. ВЫСОКОТОЧНЫЙ PDF ЧЕРЕЗ REPORTLAB С БЕЗУПРЕЧНЫМ ВЫРАВНИВАНИЕМ
# ==============================================================================
font_paths = ['C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
font_name = 'Helvetica'
font_bold = 'Helvetica-Bold'
for p in font_paths:
    if os.path.exists(p):
        try:
            pdfmetrics.registerFont(TTFont('CyrillicFont', p))
            font_name = 'CyrillicFont'
            # Проверяем наличие arialbd
            bold_p = p.replace('arial.ttf', 'arialbd.ttf').replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
            if os.path.exists(bold_p):
                pdfmetrics.registerFont(TTFont('CyrillicFontBold', bold_p))
                font_bold = 'CyrillicFontBold'
            else:
                font_bold = 'CyrillicFont'
            break
        except Exception:
            pass

pdf_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.pdf')
c = canvas.Canvas(pdf_path, pagesize=A4)
w, h = A4  # 595.27 x 841.89 pt

# Безопасные симметричные поля
margin_x = 35
content_w = w - 2 * margin_x  # 525.27 pt

# 1. Заголовок (13 pt - гарантированно входит в ширину страницы без обрезания)
c.setFillColor(colors.HexColor('#008276'))
c.setFont(font_bold, 13.5)
c.drawCentredString(w / 2, h - 32, "Фидуциальные ArUco-маркеры оптического позиционирования кассет")

# 2. Подзаголовки
c.setFillColor(colors.HexColor('#475569'))
c.setFont(font_name, 8.5)
c.drawCentredString(w / 2, h - 45, "Комплект для 5 экспериментальных когорт (Синхронный посев 29.09.2026, кассеты 3x3 по 9 растений)")
c.drawCentredString(w / 2, h - 56, "Оптико-электронный комплекс · Конкурс «Большие вызовы» ОЦ «Сириус» · Ковалева Алиса (10 класс)")

# 3. Разделительная линия
c.setStrokeColor(colors.HexColor('#00a499'))
c.setLineWidth(1.5)
c.line(margin_x, h - 63, margin_x + content_w, h - 63)

# 4. Инструкция в плашке
box_top = h - 68
box_h = 50
c.setFillColor(colors.HexColor('#f0fdfa'))
c.setStrokeColor(colors.HexColor('#ccfbf1'))
c.roundRect(margin_x, box_top - box_h, content_w, box_h, 5, fill=1, stroke=1)

c.setFillColor(colors.HexColor('#0f766e'))
c.setFont(font_bold, 8)
c.drawString(margin_x + 10, box_top - 12, "ИНСТРУКЦИЯ ПО МАРКИРОВКЕ 5 КАССЕТ (ЦВЕТОВАЯ СИНХРОНИЗАЦИЯ С ВЕБ-СТАНЦИЕЙ):")
c.setFont(font_name, 7.5)
c.drawString(margin_x + 10, box_top - 23, "1. Маркеры обведены цветом по периметру: К1 Контроль (Зеленый), К2 Соль (Фиол.), К3 Прибор (Желт.), К4 Глаза (Синий), К5 Гибель (Красный).")
c.drawString(margin_x + 10, box_top - 33, "2. Вырежьте маркеры по контуру (~25x25 мм) и наклейте на противоположные бортики кассеты (основной + резерв).")
c.drawString(margin_x + 10, box_top - 43, "3. Наклейте поверх полоску скотча от влаги. При установке кассеты в бокс камера автоматически распознает когорту!")

# 5. Сетка из 5 горизонтальных карточек для 5 кассет
card_h = 110
card_gap = 14
start_y = box_top - box_h - 14  # ~ 709 pt (верх первой карточки)

for idx, (m_id, name, desc, reg, hex_c, rep_color, _) in enumerate(ARUCO_CASSETTES):
    # Нижняя координата карточки (в ReportLab отсчет снизу вверх)
    cy = start_y - (idx + 1) * card_h - idx * card_gap
    cx = margin_x

    # Пунктирная рамка карточки во всю ширину (525 pt)
    c.setStrokeColor(colors.HexColor('#cbd5e1'))
    c.setLineWidth(0.8)
    c.setDash(4, 3)
    c.roundRect(cx, cy, content_w, card_h, 5, fill=0, stroke=1)
    c.setDash()

    # Левая цветная акцентная полоска в тон кассеты
    c.setFillColor(rep_color)
    c.roundRect(cx + 1, cy + 1, 4, card_h - 2, 2, fill=1, stroke=0)

    # Слева: Основной маркер (размер 70x70 pt ~ 25x25 мм) с цветной рамкой по периметру
    img_p = os.path.join(ARUCO_DIR, f'aruco_{m_id}.png')
    m_size = 70
    if os.path.exists(img_p):
        c.drawImage(img_p, cx + 12, cy + 22, width=m_size, height=m_size)
        c.setStrokeColor(rep_color)
        c.setLineWidth(2.5)
        c.roundRect(cx + 10, cy + 20, m_size + 4, m_size + 4, 3, fill=0, stroke=1)
    
    # Подпись под левым маркером
    c.setFillColor(rep_color)
    c.setFont(font_bold, 7)
    c.drawCentredString(cx + 12 + m_size / 2, cy + 9, f"Маркер №{m_id} (Основной)")

    # Справа: Резервный маркер-дубликат (размер 70x70 pt) с цветной рамкой по периметру
    rx = cx + content_w - 12 - m_size
    if os.path.exists(img_p):
        c.drawImage(img_p, rx, cy + 22, width=m_size, height=m_size)
        c.setStrokeColor(rep_color)
        c.setLineWidth(2.5)
        c.roundRect(rx - 2, cy + 20, m_size + 4, m_size + 4, 3, fill=0, stroke=1)
    
    # Подпись под правым маркером
    c.setFillColor(rep_color)
    c.setFont(font_bold, 7)
    c.drawCentredString(rx + m_size / 2, cy + 9, f"Маркер №{m_id} (Резерв)")

    # В центре: Информационный блок (ширина ~330 pt, свободно и без наездов)
    tx = cx + 96
    
    # Бейдж ID
    c.setFillColor(rep_color)
    c.roundRect(tx, cy + 84, 115, 15, 3, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(font_bold, 8)
    c.drawString(tx + 7, cy + 88, f"ArUco ID #{m_id} (DICT_4X4_50)")

    # Название кассеты (крупно и четко)
    c.setFillColor(colors.HexColor('#0f172a'))
    c.setFont(font_bold, 11)
    c.drawString(tx, cy + 67, name)

    # Описание воздействия
    c.setFillColor(colors.HexColor('#334155'))
    c.setFont(font_name, 8.5)
    c.drawString(tx, cy + 51, desc)

    # Регламент полива
    c.setFillColor(rep_color)
    c.setFont(font_bold, 8)
    c.drawString(tx, cy + 35, reg)

    # Подсказка по наклейке
    c.setFillColor(colors.HexColor('#94a3b8'))
    c.setFont(font_name, 7)
    c.drawString(tx, cy + 20, "✂ Вырезать по внешнему контуру · Наклеить на бортик кассеты и защитить скотчем")

# Футер
c.setStrokeColor(colors.HexColor('#e2e8f0'))
c.line(margin_x, 24, margin_x + content_w, 24)
c.setFillColor(colors.HexColor('#94a3b8'))
c.setFont(font_name, 7.5)
c.drawCentredString(w / 2, 14, "Алгоритм субпиксельного оптического позиционирования: OpenCV cv2.aruco · ОЦ «Сириус» 2026")

c.save()
print(f'Created printable PDF: {pdf_path}')

# Копируем PDF и HTML в docs и в папку Документы пользователя
destinations = [
    (sheet_html_path, os.path.join(DOCS_DIR, "aruco_markers_sheet.html")),
    (sheet_html_path, os.path.join(USER_DOCS_DIR, "Лист_ArUco_маркеров_для_кассет.html")),
    (pdf_path, os.path.join(DOCS_DIR, "aruco_markers_sheet.pdf")),
    (pdf_path, os.path.join(USER_DOCS_DIR, "Лист_ArUco_маркеров_для_кассет.pdf")),
]

for src, dst in destinations:
    try:
        shutil.copy2(src, dst)
        print(f"Copied to: {dst}")
    except PermissionError:
        base, ext = os.path.splitext(dst)
        fallback = f"{base}_обновленный{ext}"
        try:
            shutil.copy2(src, fallback)
            print(f"[Warn] File locked, copied to: {fallback}")
        except Exception as e:
            print(f"[Error] Failed to copy to {dst}: {e}")
    except Exception as e:
        print(f"[Error] Failed to copy to {dst}: {e}")
