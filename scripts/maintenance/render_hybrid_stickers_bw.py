import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ARTIFACT_DIR = r"C:\Users\Администратор\.gemini\antigravity\brain\1ce5efc4-55e3-45ca-b07c-b34c127075fc"
OUT_IMG = os.path.join(ARTIFACT_DIR, "hybrid_aruco_stickers_bw.png")
LOCAL_OUT = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\static\hybrid_aruco_stickers_bw.png"

# Setup fonts
font_big_num = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 76)
font_title = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 20)
font_subtitle = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 15)
font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
font_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 12)
font_header = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 24)

COHORTS = [
    {
        "id": 1,
        "num": "1",
        "title": "КАССЕТА №1: КОНТРОЛЬ (ЭТАЛОН)",
        "strategy": "ФИЗИОЛОГИЧЕСКИЙ ОПТИМУМ",
        "protocol": "Полив чистой водой 100% ПВ (20 мл/сут) · Базовый эталон",
        "tech": "OpenCV DICT_4X4_50 | ID:1 | S_calib = 6.25 cm²",
        "status": "НОРМА"
    },
    {
        "id": 2,
        "num": "2",
        "title": "КАССЕТА №2: ЗАСОЛЕНИЕ",
        "strategy": "ОСМОТИЧЕСКИЙ СТРЕСС (NaCl 150 мМ)",
        "protocol": "Раствор 150 мМ NaCl · Строго отдельный лоток-поддон!",
        "tech": "OpenCV DICT_4X4_50 | ID:2 | S_calib = 6.25 cm²",
        "status": "ОСМОС"
    },
    {
        "id": 3,
        "num": "3",
        "title": "КАССЕТА №3: ПРЕВЕНТИВНАЯ РЕГИДРАТАЦИЯ",
        "strategy": "КУПИРОВАНИЕ СТРЕССА ПО АЛЕРТУ СТАНЦИИ",
        "protocol": "Полив строго при ΔT ≥ +0.8°C (~40 ч, до потери тургора)",
        "tech": "OpenCV DICT_4X4_50 | ID:3 | S_calib = 6.25 cm²",
        "status": "АЛЕРТ"
    },
    {
        "id": 4,
        "num": "4",
        "title": "КАССЕТА №4: ВИЗУАЛЬНЫЙ КОНТРОЛЬ",
        "strategy": "РЕАКТИВНЫЙ ПОЛИВ (ТРАДИЦИОННЫЙ ОСМОТР)",
        "protocol": "Полив только при макро-поникании листьев (72–84 ч)",
        "tech": "OpenCV DICT_4X4_50 | ID:4 | S_calib = 6.25 cm²",
        "status": "УВЯДАНИЕ"
    },
    {
        "id": 5,
        "num": "5",
        "title": "КАССЕТА №5: ТЕРМИНАЛЬНАЯ ЗАСУХА",
        "strategy": "ПРЕДЕЛ ЖИЗНЕСПОСОБНОСТИ ТКАНИ",
        "protocol": "Полное прекращение полива 96+ ч (контроль гибели)",
        "tech": "OpenCV DICT_4X4_50 | ID:5 | S_calib = 6.25 cm²",
        "status": "ГИБЕЛЬ"
    }
]

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

card_w, card_h = 1000, 155
padding = 24
total_w = card_w + padding * 2
total_h = 110 + len(COHORTS) * (card_h + 16) + padding

canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
draw = ImageDraw.Draw(canvas)

# Header Title
draw.text((padding, 22), "ГИБРИДНЫЕ ФИДУЦИАЛЬНЫЕ МЕТКИ ДЛЯ Ч/Б ПЕЧАТИ (КОНТУРНЫЙ ДИЗАЙН)", fill=(0, 0, 0), font=font_header)
draw.text((padding, 56), "Оптимизировано для ч/б лазерных/струйных принтеров (без заливок)  |  OpenCV DICT_4X4_50 (25×25 мм, 6.25 см²)", fill=(70, 70, 70), font=font_small)
draw.line([(padding, 85), (total_w - padding, 85)], fill=(0, 0, 0), width=2)

for i, cohort in enumerate(COHORTS):
    y_top = 100 + i * (card_h + 16)
    m_id = cohort["id"]
    
    # ArUco marker
    if hasattr(aruco_dict, 'generateImageMarker'):
        raw_marker = aruco_dict.generateImageMarker(m_id, 116)
    else:
        raw_marker = cv2.aruco.drawMarker(aruco_dict, m_id, 116)
        
    marker_qz = cv2.copyMakeBorder(raw_marker, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=255)
    marker_pil = Image.fromarray(marker_qz).convert("RGB")
    
    # Outer card: clean white background with crisp 2px black outline
    draw.rounded_rectangle([padding, y_top, padding + card_w, y_top + card_h], radius=10, fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    
    # ArUco on left
    canvas.paste(marker_pil, (padding + 16, y_top + 10))
    
    # Machine Label
    draw.text((padding + 36, y_top + 135), f"ARUCO #{m_id}", fill=(60, 60, 60), font=font_mono)
    
    # Vertical separator line
    draw.line([(padding + 165, y_top + 10), (padding + 165, y_top + card_h - 10)], fill=(180, 180, 180), width=1)
    
    # Human Big Number Badge: White box with thick 3px black contour
    badge_x = padding + 185
    badge_y = y_top + 15
    badge_size = 124
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size], radius=14, fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    
    # Subtitle inside badge
    sub_num = "КАССЕТА"
    bbox_s = draw.textbbox((0, 0), sub_num, font=font_mono)
    draw.text((badge_x + (badge_size - (bbox_s[2]-bbox_s[0]))//2, badge_y + 12), sub_num, fill=(80, 80, 80), font=font_mono)
    
    # Black large numeral
    num_str = cohort["num"]
    bbox = draw.textbbox((0, 0), num_str, font=font_big_num)
    nw = bbox[2] - bbox[0]
    nh = bbox[3] - bbox[1]
    draw.text((badge_x + (badge_size - nw)//2, badge_y + 30), num_str, fill=(0, 0, 0), font=font_big_num)
    
    # Text details
    det_x = badge_x + badge_size + 24
    draw.text((det_x, y_top + 16), cohort["title"], fill=(0, 0, 0), font=font_title)
    draw.text((det_x, y_top + 47), cohort["strategy"], fill=(50, 50, 50), font=font_subtitle)
    draw.text((det_x, y_top + 76), "• Режим полива: " + cohort["protocol"], fill=(0, 0, 0), font=font_small)
    
    # Tech pill: white with black outline
    pill_text = f"[CV Метрология]  {cohort['tech']}"
    draw.rounded_rectangle([det_x, y_top + 106, det_x + 480, y_top + 134], radius=5, fill=(255, 255, 255), outline=(0, 0, 0), width=1)
    draw.text((det_x + 10, y_top + 112), pill_text, fill=(0, 0, 0), font=font_mono)
    
    # Status Tag in top-right corner
    status_str = f"[{cohort['status']}]"
    bbox_st = draw.textbbox((0, 0), status_str, font=font_title)
    draw.text((padding + card_w - (bbox_st[2]-bbox_st[0]) - 20, y_top + 16), status_str, fill=(0, 0, 0), font=font_title)

canvas.save(OUT_IMG, quality=95)
canvas.save(LOCAL_OUT, quality=95)
print(f"Generated B&W preview: {OUT_IMG}")
