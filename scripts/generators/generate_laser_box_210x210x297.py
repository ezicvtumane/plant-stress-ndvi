# -*- coding: utf-8 -*-
"""
Генератор чертежей фотометрической измерительной камеры:
Основание: квадрат 210 x 210 мм.
Высота: 297 мм (стандартный формат А4).
Материал: фанера 4.0 мм (раскрой из 6 стандартных покупных листов фанеры А4 210x297 мм).
Совместимость с кассетой: 130 x 180 x 80 мм.

ВАЖНО:
- Верхняя крышка 210 x 210 мм — СТРОГО ГЛУХАЯ, БЕЗ ОТВЕРСТИЙ (разметка и сверловка по месту).
- Дно 210 x 210 мм — контурная гравировка центрированного ложемента 130 x 180 мм + боковые зоны White Target и ArUco.
- 4 вертикальные стенки высотой 297 мм.
"""

import os
import shutil

BASE_PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_PROJ, 'hardware', 'laser', 'box_210x210x297')
USER_DOCS_DIR = r'C:\Users\Администратор\Documents\Laser_Box_210x210x297'

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(USER_DOCS_DIR, exist_ok=True)

T = 4.0        # Толщина фанеры 4 мм
W_EXT = 210.0  # Внешняя ширина, мм (ровно ширина А4)
D_EXT = 210.0  # Внешняя глубина, мм
H_EXT = 297.0  # Внешняя высота, мм (ровно длина А4)

W_INT = W_EXT - 2 * T # 202 мм
D_INT = D_EXT - 2 * T # 202 мм
H_INT = H_EXT - 2 * T # 289 мм

def make_svg(width, height, content):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}" version="1.1">
<style>
    .cut {{ stroke: #ff0000; stroke-width: 0.15; fill: none; }} /* Красный: контур резки */
    .engrave_line {{ stroke: #0000ff; stroke-width: 0.2; fill: none; stroke-dasharray: 2, 1; }} /* Синий пунктир: разметка */
    .engrave_solid {{ stroke: #0000ff; stroke-width: 0.25; fill: none; }} /* Синий сплошной: гравировка */
    .text_note {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 3.8px; fill: #475569; }}
    .text_title {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 5px; font-weight: bold; fill: #0f172a; }}
</style>
{content}
</svg>'''

def build_panels():
    # =========================================================================
    # 1. КРЫШКА (ВЕРХНЯЯ ПАНЕЛЬ) — 210 x 210 мм, ГЛУХАЯ, БЕЗ ОТВЕРСТИЙ
    # =========================================================================
    top_svg = f'''
    <!-- Заготовка листа А4 (210 x 297 мм) для наглядности позиционирования -->
    <rect x="5" y="5" width="{W_EXT}" height="{W_EXT}" rx="2" class="cut"/>
    
    <!-- Тонкие центровочные оси для удобства ручной сверловки по месту -->
    <line x1="{5 + W_EXT/2}" y1="12" x2="{5 + W_EXT/2}" y2="{5 + W_EXT - 12}" class="engrave_line"/>
    <line x1="12" y1="{5 + W_EXT/2}" x2="{5 + W_EXT - 12}" y2="{5 + W_EXT/2}" class="engrave_line"/>
    <circle cx="{5 + W_EXT/2}" cy="{5 + W_EXT/2}" r="1.5" class="engrave_solid"/>
    
    <text x="12" y="15" class="text_title">1. ВЕРХНЯЯ КРЫШКА (TOP) — ГЛУХАЯ</text>
    <text x="12" y="22" class="text_note">Габариты: {W_EXT:.0f} x {W_EXT:.0f} мм | Вырезается из листа А4 | Отверстия сверлятся по месту</text>
    '''
    with open(os.path.join(OUTPUT_DIR, '1_Kryshka_Top_NoHoles_210x210.svg'), 'w', encoding='utf-8') as f:
        f.write(make_svg(W_EXT + 10, W_EXT + 10, top_svg))

    # =========================================================================
    # 2. ДНО (ОСНОВАНИЕ) — 210 x 210 мм С ГРАВИРОВКОЙ ЛОЖЕМЕНТА 130x180 ММ
    # =========================================================================
    cx, cy = 5 + W_EXT / 2, 5 + W_EXT / 2
    bot_svg = f'''
    <rect x="5" y="5" width="{W_EXT}" height="{W_EXT}" rx="2" class="cut"/>
    
    <!-- Гравировка центрированного посадочного контура кассеты 180 x 130 мм -->
    <!-- Длина 180 мм (по оси Y) и ширина 130 мм (по оси X) -->
    <rect x="{cx - 65}" y="{cy - 90}" width="130" height="180" rx="3" class="engrave_solid"/>
    <text x="{cx}" y="{cy - 4}" class="text_title" text-anchor="middle">ЗОНА КАССЕТЫ</text>
    <text x="{cx}" y="{cy + 4}" class="text_note" text-anchor="middle">130 x 180 x 80 мм</text>
    
    <!-- Боковые зоны для калибровочного эталона и ArUco маркера (по бокам от кассеты) -->
    <!-- Слева: Белый диффузный эталон 25x25 мм -->
    <rect x="{cx - 95}" y="{cy - 12.5}" width="25" height="25" class="engrave_line"/>
    <text x="{cx - 82.5}" y="{cy + 2}" class="text_note" text-anchor="middle" style="font-size:3px;">White</text>

    <!-- Справа: ArUco фидуциальный маркер 25x25 мм -->
    <rect x="{cx + 70}" y="{cy - 12.5}" width="25" height="25" class="engrave_line"/>
    <text x="{cx + 82.5}" y="{cy + 2}" class="text_note" text-anchor="middle" style="font-size:3px;">ArUco</text>

    <text x="12" y="15" class="text_title">2. ДНО (BOTTOM) С ЛОЖЕМЕНТОМ КАССЕТЫ</text>
    <text x="12" y="22" class="text_note">Габариты: {W_EXT:.0f} x {W_EXT:.0f} мм | Вырезается из листа А4</text>
    '''
    with open(os.path.join(OUTPUT_DIR, '2_Dno_Bottom_Loze_210x210.svg'), 'w', encoding='utf-8') as f:
        f.write(make_svg(W_EXT + 10, W_EXT + 10, bot_svg))

    # =========================================================================
    # 3. ЗАДНЯЯ СТЕНКА — 210 x 297 мм (РОВНО ФОРМАТ ЛИСТА А4!)
    # =========================================================================
    back_svg = f'''
    <rect x="5" y="5" width="{W_EXT}" height="{H_EXT}" rx="2" class="cut"/>
    <!-- Кабельный ввод в верхней части задней стенки (d=20 мм) -->
    <circle cx="{5 + W_EXT/2}" cy="35" r="10" class="cut"/>
    <text x="12" y="16" class="text_title">3. ЗАДНЯЯ СТЕНКА (BACK)</text>
    <text x="12" y="23" class="text_note">Габариты: {W_EXT:.0f} x {H_EXT:.0f} мм | Ровно формат листа А4 | Кабельный ввод d=20 мм</text>
    '''
    with open(os.path.join(OUTPUT_DIR, '3_Zadnyaya_Stenka_210x297.svg'), 'w', encoding='utf-8') as f:
        f.write(make_svg(W_EXT + 10, H_EXT + 10, back_svg))

    # =========================================================================
    # 4. БОКОВАЯ СТЕНКА ЛЕВАЯ — 202 x 297 мм (ВЫРЕЗАЕТСЯ ИЗ ЛИСТА А4)
    # =========================================================================
    w_side = D_INT # 202 мм
    left_svg = f'''
    <rect x="5" y="5" width="{w_side}" height="{H_EXT}" rx="2" class="cut"/>
    <!-- Лабиринтная приточная светоловушка внизу (прорези 4x30 мм) -->
    <rect x="30" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="70" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="110" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="150" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="50" y="{H_EXT - 30}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="90" y="{H_EXT - 30}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="130" y="{H_EXT - 30}" width="30" height="4" rx="1.5" class="cut"/>
    
    <text x="12" y="16" class="text_title">4. БОКОВАЯ СТЕНКА ЛЕВАЯ (LEFT)</text>
    <text x="12" y="23" class="text_note">Габариты: {w_side:.0f} x {H_EXT:.0f} мм | Вырезается из листа А4 | Светоловушка</text>
    '''
    with open(os.path.join(OUTPUT_DIR, '4_Bokovaya_Levaya_202x297.svg'), 'w', encoding='utf-8') as f:
        f.write(make_svg(w_side + 10, H_EXT + 10, left_svg))

    # =========================================================================
    # 5. БОКОВАЯ СТЕНКА ПРАВАЯ — 202 x 297 мм (ВЫРЕЗАЕТСЯ ИЗ ЛИСТА А4)
    # =========================================================================
    right_svg = f'''
    <rect x="5" y="5" width="{w_side}" height="{H_EXT}" rx="2" class="cut"/>
    <rect x="30" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="70" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="110" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="150" y="{H_EXT - 40}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="50" y="{H_EXT - 30}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="90" y="{H_EXT - 30}" width="30" height="4" rx="1.5" class="cut"/>
    <rect x="130" y="{H_EXT - 30}" width="30" height="4" rx="1.5" class="cut"/>
    
    <text x="12" y="16" class="text_title">5. БОКОВАЯ СТЕНКА ПРАВАЯ (RIGHT)</text>
    <text x="12" y="23" class="text_note">Габариты: {w_side:.0f} x {H_EXT:.0f} мм | Вырезается из листа А4 | Светоловушка</text>
    '''
    with open(os.path.join(OUTPUT_DIR, '5_Bokovaya_Pravaya_202x297.svg'), 'w', encoding='utf-8') as f:
        f.write(make_svg(w_side + 10, H_EXT + 10, right_svg))

    # =========================================================================
    # 6. СДВИЖНАЯ ДВЕРЦА (ФАСАД) — 198 x 285 мм (ВЫРЕЗАЕТСЯ ИЗ ЛИСТА А4)
    # =========================================================================
    door_w = W_INT - 4.0  # 198 мм (свободный вертикальный ход)
    door_h = H_INT - 4.0  # 285 мм
    door_svg = f'''
    <rect x="5" y="5" width="{door_w}" height="{door_h}" rx="2" class="cut"/>
    
    <!-- Ручка-прорезь для подъема гильотины -->
    <rect x="{5 + door_w/2 - 35}" y="25" width="70" height="18" rx="9" class="cut"/>
    <text x="{5 + door_w/2}" y="20" class="text_title" text-anchor="middle" style="font-size:3.5px;">РУЧКА ПОДЪЕМА</text>

    <!-- Гравировка символики конкурса -->
    <rect x="{5 + door_w/2 - 70}" y="{door_h/2 - 25}" width="140" height="50" rx="5" class="engrave_line"/>
    <text x="{5 + door_w/2}" y="{door_h/2 - 7}" class="text_title" text-anchor="middle" style="font-size:5.5px;">БОЛЬШИЕ ВЫЗОВЫ 2026</text>
    <text x="{5 + door_w/2}" y="{door_h/2 + 5}" class="text_note" text-anchor="middle">Агропромышленные и биотехнологии</text>
    <text x="{5 + door_w/2}" y="{door_h/2 + 14}" class="text_note" text-anchor="middle">ОПТИКО-ЭЛЕКТРОННЫЙ КОМПЛЕКС</text>

    <text x="12" y="{door_h - 12}" class="text_title">6. СДВИЖНАЯ ФАСАДНАЯ ДВЕРЦА</text>
    <text x="12" y="{door_h - 5}" class="text_note">Габариты: {door_w:.0f} x {door_h:.0f} мм | Вырезается из листа А4 | Свободный ход в пазах</text>
    '''
    with open(os.path.join(OUTPUT_DIR, '6_Fasad_Dvertse_198x285.svg'), 'w', encoding='utf-8') as f:
        f.write(make_svg(door_w + 10, door_h + 10, door_svg))

    # =========================================================================
    # 7. ИНСТРУКЦИЯ И КОММЕНТАРИИ
    # =========================================================================
    readme = f'''# Чертежи оптической камеры 210 x 210 x 297 мм (Формат А4 Tower)

### Архитектура камеры:
* **Основание:** Квадрат **210 x 210 мм** (21 x 21 см);
* **Высота камеры:** **297 мм** (ровно длина стандартного листа А4);
* **Материал:** Шлифованная березовая фанера ФК 4.0 мм;
* **Каждая из 6 деталей** спроектирована так, чтобы вырезаться из **одного стандартного покупного листа фанеры формата А4 (210 x 297 мм)**. Всего на корпус требуется ровно 6 листов А4!

### Размещение кассеты 130 x 180 x 80 мм:
* Внутреннее основание: **202 x 202 мм**;
* Кассета размещается вдоль: 180 мм (зазор спереди/сзади по 11 мм);
* Ширина кассеты 130 мм (свободный зазор по бокам: по 36 мм с каждого края);
* По бокам от кассеты на дне размечены места под белый диффузный эталон ($25 \\times 25$ мм) и ArUco-маркер ($25 \\times 25$ мм);
* Руки оператора свободно берут кассету за боковые бортики, не задевая стенки камеры.

### Оптический расчет при высоте 297 мм:
* Высота кассеты: 80 мм;
* Высота растений: 100–120 мм;
* Дистанция от объективов до кассеты: 210 мм;
* **Камера NoIR (угол 65°):** охватывает поле 267 x 267 мм — видит всё основание целиком;
* **Тепловизор UTi120S (угол 50° x 38°):** охватывает поле 196 x 145 мм — кассета 180 x 130 мм идеально входит в термограмму!

### Файлы:
1. `1_Kryshka_Top_NoHoles_210x210.svg` — **Верхняя крышка ГЛУХАЯ, БЕЗ ОТВЕРСТИЙ**.
2. `2_Dno_Bottom_Loze_210x210.svg` — Дно с гравировкой ложемента.
3. `3_Zadnyaya_Stenka_210x297.svg` — Задняя панель с кабельным вводом d=20 мм.
4. `4_Bokovaya_Levaya_202x297.svg` — Левая стенка с лабиринтной светоловушкой.
5. `5_Bokovaya_Pravaya_202x297.svg` — Правая стенка с лабиринтной светоловушкой.
6. `6_Fasad_Dvertse_198x285.svg` — Сдвижная дверца (гильотина) с ручкой и гравировкой.
'''
    with open(os.path.join(OUTPUT_DIR, 'README_BOX_210x210x297.md'), 'w', encoding='utf-8') as f:
        f.write(readme)

    # Копирование в пользовательские Документы
    for fname in os.listdir(OUTPUT_DIR):
        src = os.path.join(OUTPUT_DIR, fname)
        dst = os.path.join(USER_DOCS_DIR, fname)
        shutil.copy2(src, dst)

    print(f"[OK] Все файлы камеры 210x210x297 мм успешно созданы в:")
    print(f"  1. {OUTPUT_DIR}")
    print(f"  2. {USER_DOCS_DIR}")

if __name__ == '__main__':
    build_panels()
