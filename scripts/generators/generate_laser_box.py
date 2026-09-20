import os
import cv2
import numpy as np

BASE_DIR = r'C:\Users\Администратор\Documents\Laser_Box_NDVI'
LOGOS_DIR = os.path.join(BASE_DIR, 'logos')
os.makedirs(BASE_DIR, exist_ok=True)

T = 4.0          # Толщина фанеры 4 мм
CUBE_INT = 200.0 # Внутренний размер: 200x200x200 мм
CUBE_EXT = CUBE_INT + 2 * T # 208x208x208 мм

def read_img_unicode(path):
    with open(path, "rb") as f:
        data = np.frombuffer(f.read(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)

def extract_svg_path(img_path, thresh=220, eps_factor=0.0012, min_area=8, crop_box=None):
    img = read_img_unicode(img_path)
    if len(img.shape) == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray[alpha < 50] = 255
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV)

    if crop_box is not None:
        x1, y1, x2, y2 = crop_box
        binary = binary[y1:y2, x1:x2]

    pts_fg = cv2.findNonZero(binary)
    if pts_fg is None:
        return "", 0, 0
    bx, by, bw, bh = cv2.boundingRect(pts_fg)
    cropped = binary[by:by+bh, bx:bx+bw]

    contours, _ = cv2.findContours(cropped, cv2.RETR_TREE, cv2.CHAIN_APPROX_TC89_KCOS)

    cmds = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, eps_factor * peri, True)
        if len(approx) < 3:
            continue
        pts = approx.reshape(-1, 2)
        c = f"M {pts[0][0]} {pts[0][1]}"
        for pt in pts[1:]:
            c += f" L {pt[0]} {pt[1]}"
        c += " Z"
        cmds.append(c)

    return " ".join(cmds), bw, bh

# Extract paths
bv_path, bv_w, bv_h = extract_svg_path(os.path.join(LOGOS_DIR, "bv_spbpu.png"), thresh=220)
agro_path, agro_w, agro_h = extract_svg_path(os.path.join(LOGOS_DIR, "group_35.png"), thresh=235)
wheat_path, wheat_w, wheat_h = extract_svg_path(os.path.join(LOGOS_DIR, "group_35.png"), thresh=235, crop_box=(0, 0, 200, 220))

def make_svg(width, height, content):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}" version="1.1">
<style>
    .cut {{ stroke: #ff0000; stroke-width: 0.1; fill: none; }} /* Красный: Резка */
    .engrave {{ stroke: #0000ff; stroke-width: 0.1; fill: #0000ff; }} /* Синий: Гравировка */
    .engrave_line {{ stroke: #0000ff; stroke-width: 0.2; fill: none; }}
    .text_engrave {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; fill: #0000ff; text-anchor: middle; }}
    .text_note {{ font-family: monospace; font-size: 3.8px; fill: #555555; }}
</style>
{content}
</svg>'''

# 1. КРЫШКА
def generate_top_content(ox=15, oy=15):
    w_box, h_box = CUBE_EXT, CUBE_EXT
    cx, cy = ox + w_box / 2, oy + h_box / 2
    
    c = f'<rect x="{ox}" y="{oy}" width="{w_box}" height="{h_box}" rx="2" class="cut"/>\n'
    c += f'<text x="{ox + 8}" y="{oy + 12}" class="text_note">1. КРЫШКА КУБА (TOP) 208x208мм | Фанера 4мм</text>\n'
    
    # Камера NoIR
    cam_x, cam_y = cx, cy - 25
    c += f'<circle cx="{cam_x}" cy="{cam_y}" r="8.5" class="cut"/> <!-- NoIR d=17мм -->\n'
    for dx, dy in [(-10.5, -6.25), (10.5, -6.25), (-10.5, 6.25), (10.5, 6.25)]:
        c += f'<circle cx="{cam_x + dx}" cy="{cam_y + dy}" r="1.3" class="cut"/>\n'
        
    # Тепловизор UTi120S
    th_x, th_y = cx, cy + 25
    c += f'<circle cx="{th_x}" cy="{th_y}" r="13" class="cut"/> <!-- Окно сенсора d=26мм -->\n'
    c += f'<rect x="{th_x - 16}" y="{th_y - 18}" width="32" height="36" rx="5" class="cut"/> <!-- Корпус UTi120S -->\n'

    # 2 диода (660 нм и 850 нм)
    for led_x in [cx - 50, cx + 50]:
        c += f'<circle cx="{led_x}" cy="{cy}" r="10" class="cut"/> <!-- LED Star 20мм -->\n'
        c += f'<circle cx="{led_x}" cy="{cy - 8}" r="1.5" class="cut"/>\n'
        c += f'<circle cx="{led_x}" cy="{cy + 8}" r="1.5" class="cut"/>\n'

    # Кулер 4010
    fan_x, fan_y = cx + 60, cy - 60
    c += f'<circle cx="{fan_x}" cy="{fan_y}" r="17" class="cut"/> <!-- Кулер 4010 -->\n'
    for fdx, fdy in [(-16, -16), (16, -16), (-16, 16), (16, 16)]:
        c += f'<circle cx="{fan_x + fdx}" cy="{fan_y + fdy}" r="1.5" class="cut"/>\n'

    # Кабель-канал
    c += f'<rect x="{cx - 75}" y="{cy - 70}" width="28" height="12" rx="3" class="cut"/>\n'

    # Текстовые метки
    c += f'<text x="{cam_x}" y="{cam_y - 12}" class="text_engrave" style="font-size:3.5px;">NoIR CAMERA</text>\n'
    c += f'<text x="{th_x}" y="{th_y + 24}" class="text_engrave" style="font-size:3.5px;">UTi120S THERMAL</text>\n'
    c += f'<text x="{cx - 50}" y="{cy - 12}" class="text_engrave" style="font-size:3.5px;">660 nm RED</text>\n'
    c += f'<text x="{cx + 50}" y="{cy - 12}" class="text_engrave" style="font-size:3.5px;">850 nm NIR</text>\n'
    return c

# 2. ДНО
def generate_bottom_content(ox=15, oy=15):
    w_box, h_box = CUBE_EXT, CUBE_EXT
    cx, cy = ox + w_box / 2, oy + h_box / 2
    
    c = f'<rect x="{ox}" y="{oy}" width="{w_box}" height="{h_box}" rx="2" class="cut"/>\n'
    c += f'<text x="{ox + 8}" y="{oy + 12}" class="text_note">2. ДНО КУБА (BOTTOM) 208x208мм | Фанера 4мм</text>\n'
    
    # Разметка зоны кассеты
    c += f'<rect x="{cx - 60}" y="{cy - 60}" width="120" height="120" class="engrave_line"/>\n'
    c += f'<rect x="{cx - 75}" y="{cy - 75}" width="150" height="150" class="engrave_line"/>\n'
    
    # 4 отверстия фиксаторов
    for px, py in [(-70, -70), (70, -70), (-70, 70), (70, 70)]:
        c += f'<circle cx="{cx + px}" cy="{cy + py}" r="1.6" class="cut"/>\n'

    c += f'<text x="{cx}" y="{cy - 3}" class="text_engrave" style="font-size:4.5px;">ЗОНА ЛОТКА РАСТЕНИЙ</text>\n'
    c += f'<text x="{cx}" y="{cy + 4}" class="text_engrave" style="font-size:3.2px;">120 x 120 мм / 150 x 150 мм</text>\n'
    return c

# 3. БОКОВАЯ СТЕНКА ЛЕВАЯ (С БОЛЬШОЙ ЭМБЛЕМОЙ АГРОТЕХНОЛОГИЙ)
def generate_side_left_content(ox=15, oy=15):
    w, h = CUBE_INT, CUBE_EXT # 200 x 208
    cx = ox + w / 2 + 6
    
    c = f'<rect x="{ox}" y="{oy}" width="{w}" height="{h}" rx="2" class="cut"/>\n'
    c += f'<text x="{ox + 15}" y="{oy + 10}" class="text_note">3. БОКОВАЯ СТЕНКА ЛЕВАЯ 200x208мм (С ЭМБЛЕМОЙ)</text>\n'

    # Вертикальный паз дверцы
    slot_x = ox + 8
    c += f'<rect x="{slot_x}" y="{oy + 4}" width="4.5" height="{h - 8}" rx="1" class="cut"/>\n'

    # Приточный вент-лабиринт
    for i in range(3):
        vy = oy + h - 35 + i * 7
        c += f'<rect x="{ox + 45}" y="{vy}" width="95" height="3" rx="1" class="cut"/>\n'

    # Эмблема Агротехнологий (Колос на микрочипе)
    w_scale = 55.0 / wheat_w
    w_w_mm = wheat_w * w_scale
    w_h_mm = wheat_h * w_scale
    w_pos_x = cx - w_w_mm / 2
    w_pos_y = oy + 32

    c += f'<g transform="translate({w_pos_x:.2f}, {w_pos_y:.2f}) scale({w_scale:.5f})">\n'
    c += f'  <path d="{wheat_path}" class="engrave" fill-rule="evenodd"/>\n'
    c += f'</g>\n'

    c += f'<text x="{cx}" y="{w_pos_y + w_h_mm + 9}" class="text_engrave" style="font-size:5.5px; letter-spacing:0.8px;">АГРОПРОМЫШЛЕННЫЕ</text>\n'
    c += f'<text x="{cx}" y="{w_pos_y + w_h_mm + 16}" class="text_engrave" style="font-size:5.5px; letter-spacing:0.8px;">И БИОТЕХНОЛОГИИ</text>\n'
    c += f'<line x1="{cx - 45}" y1="{w_pos_y + w_h_mm + 21}" x2="{cx + 45}" y2="{w_pos_y + w_h_mm + 21}" class="engrave_line"/>\n'
    c += f'<text x="{cx}" y="{w_pos_y + w_h_mm + 27}" class="text_engrave" style="font-size:3.6px; letter-spacing:0.5px;">СИРИУС • БОЛЬШИЕ ВЫЗОВЫ</text>\n'
    return c

# 4. БОКОВАЯ СТЕНКА ПРАВАЯ
def generate_side_right_content(ox=15, oy=15):
    w, h = CUBE_INT, CUBE_EXT
    c = f'<rect x="{ox}" y="{oy}" width="{w}" height="{h}" rx="2" class="cut"/>\n'
    c += f'<text x="{ox + 15}" y="{oy + 10}" class="text_note">4. БОКОВАЯ СТЕНКА ПРАВАЯ 200x208мм</text>\n'

    slot_x = ox + 8
    c += f'<rect x="{slot_x}" y="{oy + 4}" width="4.5" height="{h - 8}" rx="1" class="cut"/>\n'

    for i in range(3):
        vy = oy + h - 35 + i * 7
        c += f'<rect x="{ox + 45}" y="{vy}" width="95" height="3" rx="1" class="cut"/>\n'
    return c

# 5. ЗАДНЯЯ СТЕНКА
def generate_back_content(ox=15, oy=15):
    w, h = CUBE_EXT, CUBE_EXT
    cx = ox + w / 2
    
    c = f'<rect x="{ox}" y="{oy}" width="{w}" height="{h}" rx="2" class="cut"/>\n'
    c += f'<text x="{ox + 8}" y="{oy + 12}" class="text_note">5. ЗАДНЯЯ СТЕНКА (BACK) 208x208мм | Фанера 4мм</text>\n'

    c += f'<circle cx="{cx}" cy="{oy + h - 25}" r="8" class="cut"/> <!-- Датчик d=16мм -->\n'
    c += f'<rect x="{cx - 20}" y="{oy + 25}" width="40" height="12" rx="3" class="cut"/>\n'

    c += f'<text x="{cx}" y="{oy + h - 14}" class="text_engrave" style="font-size:3.2px;">SENSOR PORT</text>\n'
    c += f'<text x="{cx}" y="{oy + 21}" class="text_engrave" style="font-size:3.2px;">DC &amp; USB CABLE PORT</text>\n'
    return c

# 6. СДВИЖНАЯ ДВЕРЦА С ПОЛНОЙ ГРАВИРОВКОЙ
def generate_door_content(ox=15, oy=15):
    w, h = 186, 200
    cx = ox + w / 2
    
    c = f'<rect x="{ox}" y="{oy}" width="{w}" height="{h}" rx="3" class="cut"/>\n'
    c += f'<text x="{ox + 8}" y="{oy + 10}" class="text_note">6. СДВИЖНАЯ ДВЕРЦА (FRONT FACADE) 186x200мм</text>\n'
    c += f'<rect x="{cx - 35}" y="{oy + 18}" width="70" height="16" rx="8" class="cut"/> <!-- Ручка -->\n'

    # 1. Логотип Большие Вызовы
    bv_target_w = 135.0
    bv_scale = bv_target_w / bv_w
    bv_target_h = bv_h * bv_scale
    bv_x = cx - bv_target_w / 2
    bv_y = oy + 42.0

    c += f'<g transform="translate({bv_x:.2f}, {bv_y:.2f}) scale({bv_scale:.5f})">\n'
    c += f'  <path d="{bv_path}" class="engrave" fill-rule="evenodd"/>\n'
    c += f'</g>\n'

    # 2. Разделитель
    sep_y = bv_y + bv_target_h + 7.0
    c += f'<line x1="{cx - 65}" y1="{sep_y}" x2="{cx + 65}" y2="{sep_y}" class="engrave_line"/>\n'
    c += f'<polygon points="{cx},{sep_y - 1.5} {cx + 2},{sep_y} {cx},{sep_y + 1.5} {cx - 2},{sep_y}" fill="#0000ff" class="engrave"/>\n'

    # 3. Логотип Агропромышленные и биотехнологии
    agro_target_w = 128.0
    agro_scale = agro_target_w / agro_w
    agro_target_h = agro_h * agro_scale
    agro_x = cx - agro_target_w / 2
    agro_y = sep_y + 6.0

    c += f'<g transform="translate({agro_x:.2f}, {agro_y:.2f}) scale({agro_scale:.5f})">\n'
    c += f'  <path d="{agro_path}" class="engrave" fill-rule="evenodd"/>\n'
    c += f'</g>\n'

    # 4. Подпись
    info_y = agro_y + agro_target_h + 10.0
    c += f'<line x1="{cx - 55}" y1="{info_y}" x2="{cx + 55}" y2="{info_y}" class="engrave_line"/>\n'
    c += f'<text x="{cx}" y="{info_y + 7.0}" class="text_engrave" style="font-size:4.2px; letter-spacing:0.6px;">КОМПЛЕКС NDVI &amp; ТЕРМОГРАФИИ РАСТЕНИЙ</text>\n'
    c += f'<text x="{cx}" y="{info_y + 13.0}" class="text_engrave" style="font-size:3.4px; font-weight:normal;">Автор: Ковалева Алиса • 10 класс, СОШ №282 СПб</text>\n'
    c += f'<text x="{cx}" y="{info_y + 18.0}" class="text_engrave" style="font-size:3.0px; font-weight:normal; fill:#555555;">ОЦ «СИРИУС» • САНКТ-ПЕТЕРБУРГ 2026</text>\n'
    return c

# Генерация отдельных файлов
individual_files = {
    '1_Kub_Kryshka_Top.svg': make_svg(240, 240, generate_top_content()),
    '2_Kub_Dno_Bottom.svg': make_svg(240, 240, generate_bottom_content()),
    '3_Kub_Bokovaya_Levaya.svg': make_svg(230, 240, generate_side_left_content()),
    '4_Kub_Bokovaya_Pravaya.svg': make_svg(230, 240, generate_side_right_content()),
    '5_Kub_Zadnyaya_Stenka.svg': make_svg(240, 240, generate_back_content()),
    '6_Kub_Dvertse_Sliding.svg': make_svg(220, 230, generate_door_content())
}

for fname, content in individual_files.items():
    with open(os.path.join(BASE_DIR, fname), 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[+] Saved individual SVG: {fname}")

# Генерация раскладки на два листа рабочего поля Acmer S1 Pro (380 x 370 мм):
# Лист 1: Крышка + Дно (бок о бок: 208 + 10 + 208 = 426 не лезет на 380, поэтому по отдельности или на лист 380x370 помещается 1 крупная деталь + 1 дверь!)
# Лист 1 (380 x 370 мм): Крышка (208x208) сверху-слева + Сдвижная дверца (186x200) рядом:
# 208 + 10 + 186 = 404 мм (чуть больше 380).
# Значит на один лист 380x370 мм идеально ложится 1 деталь 208x208 мм с запасом, либо при фанере 400x300 мм: 1 деталь 208x208 мм на лист!

print("=== All individual SVG files ready in: " + BASE_DIR + " ===")
