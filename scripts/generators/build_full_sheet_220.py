import os
import cv2
import numpy as np
import xml.etree.ElementTree as ET
import re

BASE_DIR = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\hardware\laser'
DESK_DIR = r'C:\Users\Администратор\Documents\Laser_Box_NDVI'
LOGOS_DIR = os.path.join(DESK_DIR, 'logos')
LIDBOX_SVG = r'C:\Users\Администратор\Downloads\LidBox (1).svg'

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(DESK_DIR, exist_ok=True)

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

print("Extracting vector logos...")
bv_path, bv_w, bv_h = extract_svg_path(os.path.join(LOGOS_DIR, "bv_spbpu.png"), thresh=220)
agro_path, agro_w, agro_h = extract_svg_path(os.path.join(LOGOS_DIR, "group_35.png"), thresh=235)
wheat_path, wheat_w, wheat_h = extract_svg_path(os.path.join(LOGOS_DIR, "group_35.png"), thresh=235, crop_box=(0, 0, 200, 220))
print(f"Logos extracted: BV({bv_w}x{bv_h}), Agro({agro_w}x{agro_h}), Wheat({wheat_w}x{wheat_h})")

# Load LidBox (1).svg paths
tree = ET.parse(LIDBOX_SVG)
root = tree.getroot()

# Group paths by group id
groups_paths = {}
for g in root.findall('{http://www.w3.org/2000/svg}g'):
    gid = g.attrib.get('id')
    groups_paths[gid] = []
    for p in g.findall('{http://www.w3.org/2000/svg}path'):
        groups_paths[gid].append(p.attrib.get('d', ''))

def make_cut_path(d):
    return f'<path d="{d}" class="cut"/>\n'

# Header and styles
svg_style = '''
<style>
    .cut { stroke: #ff0000; stroke-width: 0.1; fill: none; } /* Красный: Резка (Cut) */
    .engrave { stroke: #0000ff; stroke-width: 0.05; fill: #0000ff; } /* Синий: Заливка/гравировка (Fill) */
    .engrave_line { stroke: #0000ff; stroke-width: 0.2; fill: none; } /* Синий: Контурная гравировка (Line) */
    .text_engrave { font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; fill: #0000ff; text-anchor: middle; }
    .text_note { font-family: monospace; font-size: 3.8px; fill: #555555; }
</style>
'''

# 1. TOP LID (p-5): BBox X=[232.2, 452.4], Y=[10.0, 230.2]
def generate_lid_interior():
    cx = 342.3
    cy = 120.1
    c = f'<text x="{cx}" y="22" class="text_note" text-anchor="middle">КРЫШКА С ОПТИКОЙ (TOP LID) 220x220мм</text>\n'
    
    # Камера NoIR (по центру по X, cy - 25)
    cam_x, cam_y = cx, cy - 25
    c += f'<circle cx="{cam_x}" cy="{cam_y}" r="8.5" class="cut"/> <!-- Окно NoIR d=17мм -->\n'
    for dx, dy in [(-10.5, -6.25), (10.5, -6.25), (-10.5, 6.25), (10.5, 6.25)]:
        c += f'<circle cx="{cam_x + dx}" cy="{cam_y + dy}" r="1.3" class="cut"/> <!-- Крепеж M2.5 -->\n'
    c += f'<text x="{cam_x}" y="{cam_y - 12}" class="text_engrave" style="font-size:3.5px;">NoIR CAMERA</text>\n'

    # Тепловизор UTi120S (cy + 25)
    th_x, th_y = cx, cy + 25
    c += f'<circle cx="{th_x}" cy="{th_y}" r="13" class="cut"/> <!-- Сенсор UTi120S d=26мм -->\n'
    c += f'<rect x="{th_x - 16}" y="{th_y - 18}" width="32" height="36" rx="5" class="cut"/> <!-- Окно прибора -->\n'
    c += f'<text x="{th_x}" y="{th_y + 24}" class="text_engrave" style="font-size:3.5px;">UTi120S THERMAL</text>\n'

    # 2 диода (660 нм Deep Red и 850 нм NIR)
    for led_x, label in [(cx - 50, "660 nm RED"), (cx + 50, "850 nm NIR")]:
        c += f'<circle cx="{led_x}" cy="{cy}" r="10" class="cut"/> <!-- Звезда 20мм -->\n'
        c += f'<circle cx="{led_x}" cy="{cy - 8}" r="1.5" class="cut"/> <!-- Отверстия винтов/проводов -->\n'
        c += f'<circle cx="{led_x}" cy="{cy + 8}" r="1.5" class="cut"/>\n'
        c += f'<text x="{led_x}" y="{cy - 12}" class="text_engrave" style="font-size:3.5px;">{label}</text>\n'

    # Вентилятор 4010
    fan_x, fan_y = cx + 55, cy - 55
    c += f'<circle cx="{fan_x}" cy="{fan_y}" r="17" class="cut"/> <!-- Кулер 4010 d=34мм -->\n'
    for fdx, fdy in [(-16, -16), (16, -16), (-16, 16), (16, 16)]:
        c += f'<circle cx="{fan_x + fdx}" cy="{fan_y + fdy}" r="1.6" class="cut"/> <!-- M3 -->\n'
    c += f'<text x="{fan_x}" y="{fan_y - 19}" class="text_engrave" style="font-size:3.0px;">FAN 4010</text>\n'

    # Кабель-канал
    c += f'<rect x="{cx - 75}" y="{cy - 65}" width="28" height="12" rx="3" class="cut"/> <!-- Кабель-канал -->\n'
    c += f'<text x="{cx - 61}" y="{cy - 68}" class="text_engrave" style="font-size:3.0px;">CABLES</text>\n'
    return c

# 2. BOTTOM PANEL (p-4): BBox X=[10.0, 230.2], Y=[10.0, 230.2]
def generate_bottom_interior():
    cx = 120.1
    cy = 120.1
    c = f'<text x="{cx}" y="22" class="text_note" text-anchor="middle">ДНО КУБА (BOTTOM) 220x220мм</text>\n'
    
    # Центрирующие рамки кассет
    c += f'<rect x="{cx - 60}" y="{cy - 60}" width="120" height="120" class="engrave_line"/>\n'
    c += f'<rect x="{cx - 90}" y="{cy - 67.5}" width="180" height="135" class="engrave_line" stroke-dasharray="4,2"/>\n'
    c += f'<rect x="{cx - 75}" y="{cy - 75}" width="150" height="150" class="engrave_line"/>\n'

    # 4 упора-фиксатора кассеты
    for px, py in [(-80, -70), (80, -70), (-80, 70), (80, 70)]:
        c += f'<circle cx="{cx + px}" cy="{cy + py}" r="1.6" class="cut"/>\n'

    c += f'<text x="{cx}" y="{cy - 5}" class="text_engrave" style="font-size:4.5px;">ЗОНА КАССЕТЫ РАСТЕНИЙ</text>\n'
    c += f'<text x="{cx}" y="{cy + 2}" class="text_engrave" style="font-size:3.5px;">180 × 135 мм (9 ячеек) / 120 × 120 мм</text>\n'
    c += f'<text x="{cx}" y="{cy + 8}" class="text_engrave" style="font-size:3.0px; font-weight:normal;">ArUco MARKER FIELD</text>\n'
    return c

# 3. FRONT WALL (p-0): BBox X=[10.0, 230.2], Y=[450.4, 666.6]
def generate_front_interior():
    cx = 120.1
    oy = 450.4
    h = 216.2
    c = f'<text x="{cx}" y="{oy + 14}" class="text_note" text-anchor="middle">ФАСАД ПРИБОРА (FRONT PANEL)</text>\n'

    # 1. Логотип Большие Вызовы
    bv_target_w = 145.0
    bv_scale = bv_target_w / bv_w
    bv_target_h = bv_h * bv_scale
    bv_x = cx - bv_target_w / 2
    bv_y = oy + 24.0

    c += f'<g transform="translate({bv_x:.2f}, {bv_y:.2f}) scale({bv_scale:.5f})">\n'
    c += f'  <path d="{bv_path}" class="engrave" fill-rule="evenodd"/>\n'
    c += f'</g>\n'

    # 2. Разделитель
    sep_y = bv_y + bv_target_h + 8.0
    c += f'<line x1="{cx - 70}" y1="{sep_y}" x2="{cx + 70}" y2="{sep_y}" class="engrave_line"/>\n'
    c += f'<polygon points="{cx},{sep_y - 1.5} {cx + 2.5},{sep_y} {cx},{sep_y + 1.5} {cx - 2.5},{sep_y}" fill="#0000ff" class="engrave"/>\n'

    # 3. Логотип Агропромышленные и биотехнологии
    agro_target_w = 138.0
    agro_scale = agro_target_w / agro_w
    agro_target_h = agro_h * agro_scale
    agro_x = cx - agro_target_w / 2
    agro_y = sep_y + 7.0

    c += f'<g transform="translate({agro_x:.2f}, {agro_y:.2f}) scale({agro_scale:.5f})">\n'
    c += f'  <path d="{agro_path}" class="engrave" fill-rule="evenodd"/>\n'
    c += f'</g>\n'

    # 4. Авторская табличка
    info_y = agro_y + agro_target_h + 10.0
    c += f'<line x1="{cx - 60}" y1="{info_y}" x2="{cx + 60}" y2="{info_y}" class="engrave_line"/>\n'
    c += f'<text x="{cx}" y="{info_y + 8.0}" class="text_engrave" style="font-size:4.5px; letter-spacing:0.7px;">КОМПЛЕКС NDVI &amp; ТЕРМОГРАФИИ РАСТЕНИЙ</text>\n'
    c += f'<text x="{cx}" y="{info_y + 14.5}" class="text_engrave" style="font-size:3.5px; font-weight:normal;">Автор: Ковалева Алиса • 10 класс, СОШ №282 СПб</text>\n'
    c += f'<text x="{cx}" y="{info_y + 20.0}" class="text_engrave" style="font-size:3.0px; font-weight:normal; fill:#555555;">ОЦ «СИРИУС» • САНКТ-ПЕТЕРБУРГ 2026</text>\n'
    return c

# 4. LEFT WALL (p-3): BBox X=[10.0, 230.2], Y=[232.2, 448.4]
def generate_left_interior():
    cx = 120.1
    oy = 232.2
    c = f'<text x="{cx}" y="{oy + 14}" class="text_note" text-anchor="middle">БОКОВАЯ СТЕНКА ЛЕВАЯ (LEFT WALL)</text>\n'

    # Эмблема Агротехнологий (Колос на чипе)
    w_scale = 58.0 / wheat_w
    w_w_mm = wheat_w * w_scale
    w_h_mm = wheat_h * w_scale
    w_pos_x = cx - w_w_mm / 2
    w_pos_y = oy + 26.0

    c += f'<g transform="translate({w_pos_x:.2f}, {w_pos_y:.2f}) scale({w_scale:.5f})">\n'
    c += f'  <path d="{wheat_path}" class="engrave" fill-rule="evenodd"/>\n'
    c += f'</g>\n'

    c += f'<text x="{cx}" y="{w_pos_y + w_h_mm + 9}" class="text_engrave" style="font-size:5.5px; letter-spacing:0.8px;">АГРОПРОМЫШЛЕННЫЕ</text>\n'
    c += f'<text x="{cx}" y="{w_pos_y + w_h_mm + 16}" class="text_engrave" style="font-size:5.5px; letter-spacing:0.8px;">И БИОТЕХНОЛОГИИ</text>\n'
    c += f'<line x1="{cx - 50}" y1="{w_pos_y + w_h_mm + 21}" x2="{cx + 50}" y2="{w_pos_y + w_h_mm + 21}" class="engrave_line"/>\n'
    c += f'<text x="{cx}" y="{w_pos_y + w_h_mm + 27}" class="text_engrave" style="font-size:3.8px; letter-spacing:0.5px;">СИРИУС • БОЛЬШИЕ ВЫЗОВЫ</text>\n'

    # 3 приточных вент-паза (светоловушка)
    for i in range(3):
        vy = oy + 185 + i * 7
        c += f'<rect x="{cx - 50}" y="{vy}" width="100" height="3" rx="1" class="cut"/>\n'
    return c

# 5. RIGHT WALL (p-2): BBox X=[232.2, 452.4], Y=[232.2, 448.4]
def generate_right_interior():
    cx = 342.3
    oy = 232.2
    c = f'<text x="{cx}" y="{oy + 14}" class="text_note" text-anchor="middle">БОКОВАЯ СТЕНКА ПРАВАЯ (RIGHT WALL)</text>\n'

    c += f'<text x="{cx}" y="{oy + 110}" class="text_engrave" style="font-size:4.8px; letter-spacing:0.8px;">OPTICAL PHENOTYPING</text>\n'
    c += f'<text x="{cx}" y="{oy + 118}" class="text_engrave" style="font-size:4.0px; letter-spacing:0.6px;">ACTIVE DUAL-BAND NDVI CHAMBER</text>\n'
    c += f'<line x1="{cx - 45}" y1="{oy + 123}" x2="{cx + 45}" y2="{oy + 123}" class="engrave_line"/>\n'
    c += f'<text x="{cx}" y="{oy + 130}" class="text_engrave" style="font-size:3.2px;">660 nm &amp; 850 nm SPECTRUM</text>\n'

    for i in range(3):
        vy = oy + 185 + i * 7
        c += f'<rect x="{cx - 50}" y="{vy}" width="100" height="3" rx="1" class="cut"/>\n'
    return c

# 6. BACK WALL (p-1): BBox X=[232.2, 452.4], Y=[450.4, 666.6]
def generate_back_interior():
    cx = 342.3
    oy = 450.4
    c = f'<text x="{cx}" y="{oy + 14}" class="text_note" text-anchor="middle">ЗАДНЯЯ СТЕНКА (BACK WALL)</text>\n'

    # Порт датчика d=16мм
    c += f'<circle cx="{cx}" cy="{oy + 160}" r="8" class="cut"/> <!-- Датчик d=16мм -->\n'
    c += f'<text x="{cx}" y="{oy + 174}" class="text_engrave" style="font-size:3.5px;">SENSOR PORT (SHT30 / SOIL)</text>\n'

    # Порт питания DC & USB Type-C
    c += f'<rect x="{cx - 22}" y="{oy + 45}" width="44" height="14" rx="3" class="cut"/>\n'
    c += f'<text x="{cx}" y="{oy + 40}" class="text_engrave" style="font-size:3.5px;">DC 12V / 5V &amp; USB TYPE-C</text>\n'

    # Вент-лабиринт
    for i in range(2):
        vy = oy + 95 + i * 8
        c += f'<rect x="{cx - 40}" y="{vy}" width="80" height="3.5" rx="1" class="cut"/>\n'
    return c

# --- СОБИРАЕМ МАСТЕР-ФАЙЛ (ПОЛНЫЙ ЛИСТ 490.7 x 676.6 мм) ---
full_svg_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="490.70mm" height="676.60mm" viewBox="0.0 0.0 490.70 676.60" version="1.1">
{svg_style}
<!-- 1. ИСХОДНЫЙ КОНТУР РЕЗКИ ШИП-ПАЗ ИЗ LIDBOX (КРАСНЫЙ СЛОЙ CUT) -->
'''

for gid, paths in groups_paths.items():
    full_svg_content += f'<!-- Group {gid} -->\n<g id="{gid}">\n'
    for d in paths:
        full_svg_content += make_cut_path(d)
    full_svg_content += '</g>\n'

full_svg_content += '''
<!-- 2. ВНУТРЕННЯЯ ОПТИКА, ОТВЕРСТИЯ И ГРАВИРОВКА -->
<g id="interior-optics-and-engraving">
'''
full_svg_content += generate_bottom_interior()
full_svg_content += generate_lid_interior()
full_svg_content += generate_left_interior()
full_svg_content += generate_right_interior()
full_svg_content += generate_front_interior()
full_svg_content += generate_back_interior()
full_svg_content += '</g>\n</svg>'

# Сохраняем полный лист
full_out_path = os.path.join(BASE_DIR, '0_Raskroy_Kuba_220_Full_Sheet.svg')
with open(full_out_path, 'w', encoding='utf-8') as f:
    f.write(full_svg_content)
with open(os.path.join(DESK_DIR, '0_Raskroy_Kuba_220_Full_Sheet.svg'), 'w', encoding='utf-8') as f:
    f.write(full_svg_content)

print(f"[+] Saved FULL master sheet: {full_out_path}")

# --- ТАКЖЕ ДЕЛАЕМ ОТДЕЛЬНЫЕ ПАНЕЛИ ДЛЯ РЕЗКИ ПО ОДНОЙ (для Acmer S1 Pro 380x370 мм) ---
b_dir = os.path.join(BASE_DIR, 'individual_panels_220')
desk_b_dir = os.path.join(DESK_DIR, 'individual_panels_220')
os.makedirs(b_dir, exist_ok=True)
os.makedirs(desk_b_dir, exist_ok=True)

panels_info = [
    ('1_Kryshka_Top_220.svg', 'p-5', generate_lid_interior(), 232.2, 10.0, 220.2, 220.2),
    ('2_Dno_Bottom_220.svg', 'p-4', generate_bottom_interior(), 10.0, 10.0, 220.2, 220.2),
    ('3_Fasad_Front_220.svg', 'p-0', generate_front_interior(), 10.0, 450.4, 220.2, 216.2),
    ('4_Bokovaya_Left_220.svg', 'p-3', generate_left_interior(), 10.0, 232.2, 220.2, 216.2),
    ('5_Bokovaya_Right_220.svg', 'p-2', generate_right_interior(), 232.2, 232.2, 220.2, 216.2),
    ('6_Zadnyaya_Back_220.svg', 'p-1', generate_back_interior(), 232.2, 450.4, 220.2, 216.2),
]

for filename, gid, interior_svg, min_x, min_y, pw, ph in panels_info:
    pad = 10.0
    cw = pw + 2 * pad
    ch = ph + 2 * pad
    dx = pad - min_x
    dy = pad - min_y
    paths_cut = ''.join([make_cut_path(d) for d in groups_paths[gid]])
    content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{cw:.1f}mm" height="{ch:.1f}mm" viewBox="0 0 {cw:.1f} {ch:.1f}" version="1.1">
{svg_style}
<g transform="translate({dx:.2f}, {dy:.2f})">
{paths_cut}
{interior_svg}
</g>
</svg>'''
    with open(os.path.join(b_dir, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    with open(os.path.join(desk_b_dir, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'[+] Saved individual panel: {filename}')

# Фиксаторы-защелки
latches_cut = ''.join([make_cut_path(d) for d in groups_paths['p-6'] + groups_paths['p-7']])
dx_lat = 10.0 - 454.3
dy_lat = 10.0 - 16.9
latches_svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="240mm" viewBox="0 0 50 240" version="1.1">
{svg_style}
<g transform="translate({dx_lat:.2f}, {dy_lat:.2f})">
{latches_cut}
</g>
</svg>'''
with open(os.path.join(b_dir, '7_Fiksatory_Zaschelki.svg'), 'w', encoding='utf-8') as f:
    f.write(latches_svg)
with open(os.path.join(desk_b_dir, '7_Fiksatory_Zaschelki.svg'), 'w', encoding='utf-8') as f:
    f.write(latches_svg)
print('[+] Saved individual: 7_Fiksatory_Zaschelki.svg')

print("[+] All files generated successfully!")

