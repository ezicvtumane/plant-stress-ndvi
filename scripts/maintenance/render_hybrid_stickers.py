import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ARTIFACT_DIR = r"C:\Users\Администратор\.gemini\antigravity\brain\1ce5efc4-55e3-45ca-b07c-b34c127075fc"
OUT_IMG = os.path.join(ARTIFACT_DIR, "hybrid_aruco_stickers.png")
LOCAL_OUT = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\static\hybrid_aruco_stickers.png"

# Setup fonts
font_big_num = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 74)
font_title = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 20)
font_subtitle = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 15)
font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
font_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 12)

COHORTS = [
    {
        "id": 1,
        "num": "1",
        "title": "КАССЕТА №1: КОНТРОЛЬ",
        "strategy": "ФИЗИОЛОГИЧЕСКИЙ ОПТИМУМ",
        "protocol": "Полив 100% ПВ (20 мл/сут) · Базовый водный эталон",
        "tech": "OpenCV DICT_4X4_50 | ID:1 | S_calib = 6.25 cm²",
        "bg_color": (236, 253, 245),
        "border_color": (5, 150, 105),
        "text_color": (6, 95, 70),
    },
    {
        "id": 2,
        "num": "2",
        "title": "КАССЕТА №2: ЗАСОЛЕНИЕ",
        "strategy": "ОСМОТИЧЕСКИЙ БЛОК (NaCl 150 мМ)",
        "protocol": "Раствор 150 мМ NaCl · Строго отдельный лоток-поддон!",
        "tech": "OpenCV DICT_4X4_50 | ID:2 | S_calib = 6.25 cm²",
        "bg_color": (245, 243, 255),
        "border_color": (124, 58, 237),
        "text_color": (91, 33, 182),
    },
    {
        "id": 3,
        "num": "3",
        "title": "КАССЕТА №3: ПРЕВЕНТИВНАЯ РЕГИДРАТАЦИЯ",
        "strategy": "КУПИРОВАНИЕ СТРЕССА ПО АЛЕРТУ СТАНЦИИ",
        "protocol": "Полив строго при ΔT ≥ +0.8°C (~40 ч, до потери тургора)",
        "tech": "OpenCV DICT_4X4_50 | ID:3 | S_calib = 6.25 cm²",
        "bg_color": (254, 252, 232),
        "border_color": (180, 83, 9),
        "text_color": (146, 64, 14),
    },
    {
        "id": 4,
        "num": "4",
        "title": "КАССЕТА №4: ТРАДИЦИОННЫЙ ВИЗУАЛЬНЫЙ КОНТРОЛЬ",
        "strategy": "РЕАКТИВНЫЙ ПОЛИВ (ВИЗУАЛЬНЫЙ ОСМОТР)",
        "protocol": "Полив только при макро-поникании листьев (72–84 ч)",
        "tech": "OpenCV DICT_4X4_50 | ID:4 | S_calib = 6.25 cm²",
        "bg_color": (239, 246, 255),
        "border_color": (37, 99, 235),
        "text_color": (30, 64, 175),
    },
    {
        "id": 5,
        "num": "5",
        "title": "КАССЕТА №5: ТЕРМИНАЛЬНАЯ ЗАСУХА",
        "strategy": "ПРЕДЕЛ ЖИЗНЕСПОСОБНОСТИ ТКАНИ",
        "protocol": "Полное прекращение полива 96+ ч (контроль гибели)",
        "tech": "OpenCV DICT_4X4_50 | ID:5 | S_calib = 6.25 cm²",
        "bg_color": (255, 241, 242),
        "border_color": (220, 38, 38),
        "text_color": (159, 18, 57),
    }
]

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

card_w, card_h = 960, 155
padding = 24
total_w = card_w + padding * 2
total_h = 110 + len(COHORTS) * (card_h + 14) + padding

canvas = Image.new("RGB", (total_w, total_h), (248, 250, 252))
draw = ImageDraw.Draw(canvas)

# Header Title
draw.text((padding, 24), "ДИЗАЙН ГИБРИДНЫХ МЕТОК (HUMAN-MACHINE INTERFACE)", fill=(15, 23, 42), font=ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 25))
draw.text((padding, 58), "Канал машинного зрения: OpenCV DICT_4X4_50 (25×25 мм, S = 6.25 см², угол поворота)  |  Канал человека: цветовая дифференциация и крупная цифра", fill=(71, 85, 105), font=font_small)
draw.line([(padding, 88), (total_w - padding, 88)], fill=(226, 232, 240), width=2)

for i, cohort in enumerate(COHORTS):
    y_top = 105 + i * (card_h + 14)
    m_id = cohort["id"]
    
    # ArUco marker
    if hasattr(aruco_dict, 'generateImageMarker'):
        raw_marker = aruco_dict.generateImageMarker(m_id, 116)
    else:
        raw_marker = cv2.aruco.drawMarker(aruco_dict, m_id, 116)
        
    marker_qz = cv2.copyMakeBorder(raw_marker, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=255)
    marker_pil = Image.fromarray(marker_qz).convert("RGB")
    
    # Outer card
    draw.rounded_rectangle([padding, y_top, padding + card_w, y_top + card_h], radius=12, fill=cohort["bg_color"], outline=cohort["border_color"], width=2)
    
    # ArUco on left
    canvas.paste(marker_pil, (padding + 16, y_top + 10))
    
    # Machine Label
    draw.text((padding + 34, y_top + 135), f"ARUCO #{m_id}", fill=(100, 116, 139), font=font_mono)
    
    # Vertical separator line
    draw.line([(padding + 165, y_top + 12), (padding + 165, y_top + card_h - 12)], fill=(203, 213, 225), width=2)
    
    # Human Big Number Badge
    badge_x = padding + 185
    badge_y = y_top + 16
    badge_size = 122
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size], radius=16, fill=cohort["border_color"])
    
    # Subtitle inside badge
    sub_num = "КАССЕТА"
    bbox_s = draw.textbbox((0, 0), sub_num, font=font_mono)
    draw.text((badge_x + (badge_size - (bbox_s[2]-bbox_s[0]))//2, badge_y + 12), sub_num, fill=(241, 245, 249), font=font_mono)
    
    # White large numeral
    num_str = cohort["num"]
    bbox = draw.textbbox((0, 0), num_str, font=font_big_num)
    nw = bbox[2] - bbox[0]
    nh = bbox[3] - bbox[1]
    draw.text((badge_x + (badge_size - nw)//2, badge_y + 30), num_str, fill=(255, 255, 255), font=font_big_num)
    
    # Text details
    det_x = badge_x + badge_size + 24
    draw.text((det_x, y_top + 16), cohort["title"], fill=cohort["text_color"], font=font_title)
    draw.text((det_x, y_top + 47), cohort["strategy"], fill=(30, 41, 59), font=font_subtitle)
    draw.text((det_x, y_top + 76), "• Режим полива: " + cohort["protocol"], fill=(51, 65, 85), font=font_small)
    
    # Tech pill
    pill_text = f"[CV Метрология]  {cohort['tech']}"
    draw.rounded_rectangle([det_x, y_top + 106, det_x + 480, y_top + 134], radius=6, fill=(255, 255, 255), outline=cohort["border_color"], width=1)
    draw.text((det_x + 10, y_top + 112), pill_text, fill=cohort["border_color"], font=font_mono)

canvas.save(OUT_IMG, quality=95)
canvas.save(LOCAL_OUT, quality=95)
print("Updated successfully!")
