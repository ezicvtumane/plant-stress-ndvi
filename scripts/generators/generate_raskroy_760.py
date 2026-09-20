import os

OUT_DIR = r'C:\Users\Администратор\Documents\Laser_Box_NDVI'
os.makedirs(OUT_DIR, exist_ok=True)

def generate_raskroy_svg():
    w_sheet, h_sheet = 760.0, 760.0
    margin = 20.0
    
    # SVG canvas with margin around the sheet
    svg_w = w_sheet + 2 * margin
    svg_h = h_sheet + 2 * margin
    
    ox, oy = margin, margin
    
    c = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}mm" height="{svg_h}mm" viewBox="0 0 {svg_w} {svg_h}" version="1.1">
<style>
    .sheet {{ stroke: #111111; stroke-width: 0.8; fill: #fdfaf2; }}
    .saw_cut {{ stroke: #e65100; stroke-width: 0.5; stroke-dasharray: 4,2; fill: none; }}
    .part_border {{ stroke: #d32f2f; stroke-width: 0.5; fill: #ffffff; }}
    .leftover {{ fill: #e8f5e9; stroke: #2e7d32; stroke-width: 0.5; stroke-dasharray: 2,2; }}
    .title {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 14px; fill: #111111; }}
    .subtitle {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 8px; fill: #555555; }}
    .part_title {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 6.5px; fill: #d32f2f; text-anchor: middle; }}
    .part_dim {{ font-family: monospace; font-size: 5px; fill: #333333; text-anchor: middle; }}
    .saw_label {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 5.5px; fill: #e65100; }}
    .rem_text {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 10px; fill: #2e7d32; text-anchor: middle; }}
</style>

<!-- Лист фанеры 760 x 760 мм -->
<rect x="{ox}" y="{oy}" width="{w_sheet}" height="{h_sheet}" class="sheet"/>
<text x="{ox + 25}" y="{oy + 30}" class="title">КАРТА РАСКРОЯ ЛИСТА ФАНЕРЫ 760 × 760 × 4 мм</text>
<text x="{ox + 25}" y="{oy + 42}" class="subtitle">Оптимизировано под рабочий стол лазерного станка Acmer S1 Pro 20W (380 × 370 мм)</text>

<!-- Полоса 1: Y = 60..300 (высота 240 мм) -->
<!-- Полоса 2: Y = 300..540 (высота 240 мм) -->
<!-- Линии ручного распила (лобзик/ножовка) -->
<line x1="{ox}" y1="{oy + 300}" x2="{ox + w_sheet}" y2="{oy + 300}" class="saw_cut"/>
<text x="{ox + w_sheet - 180}" y="{oy + 296}" class="saw_label">── ЛИНИЯ РАСПИЛА №1 (Y = 300 мм) ──</text>

<line x1="{ox}" y1="{oy + 540}" x2="{ox + w_sheet}" y2="{oy + 540}" class="saw_cut"/>
<text x="{ox + w_sheet - 180}" y="{oy + 536}" class="saw_label">── ЛИНИЯ РАСПИЛА №2 (Y = 540 мм) ──</text>

<!-- Вертикальные линии распила на заготовки 240x240 под станок -->
<line x1="{ox + 245}" y1="{oy + 60}" x2="{ox + 245}" y2="{oy + 540}" class="saw_cut"/>
<line x1="{ox + 490}" y1="{oy + 60}" x2="{ox + 490}" y2="{oy + 540}" class="saw_cut"/>
<line x1="{ox + 735}" y1="{oy + 60}" x2="{ox + 735}" y2="{oy + 540}" class="saw_cut"/>

<!-- ================= РЯД 1: ПОЛОСА 1 (Y = 70..278) ================= -->
<!-- 1. Крышка 208x208 -->
<g transform="translate({ox + 20}, {oy + 75})">
    <rect width="208" height="208" rx="2" class="part_border"/>
    <text x="104" y="100" class="part_title">1. КРЫШКА (TOP)</text>
    <text x="104" y="112" class="part_dim">208 × 208 мм</text>
    <text x="104" y="125" class="part_dim">(Камера, UTi120S, LED 660/850, Кулер)</text>
</g>

<!-- 2. Дно 208x208 -->
<g transform="translate({ox + 265}, {oy + 75})">
    <rect width="208" height="208" rx="2" class="part_border"/>
    <text x="104" y="100" class="part_title">2. ДНО КУБА (BOTTOM)</text>
    <text x="104" y="112" class="part_dim">208 × 208 мм</text>
    <text x="104" y="125" class="part_dim">(Разметка кассет 120/150мм)</text>
</g>

<!-- 3. Задняя стенка 208x208 -->
<g transform="translate({ox + 510}, {oy + 75})">
    <rect width="208" height="208" rx="2" class="part_border"/>
    <text x="104" y="100" class="part_title">3. ЗАДНЯЯ СТЕНКА</text>
    <text x="104" y="112" class="part_dim">208 × 208 мм</text>
    <text x="104" y="125" class="part_dim">(Ввод питания и датчика почвы)</text>
</g>

<!-- ================= РЯД 2: ПОЛОСА 2 (Y = 315..523) ================= -->
<!-- 4. Левая стенка 200x208 -->
<g transform="translate({ox + 20}, {oy + 315})">
    <rect width="200" height="208" rx="2" class="part_border"/>
    <text x="100" y="100" class="part_title">4. ЛЕВАЯ СТЕНКА</text>
    <text x="100" y="112" class="part_dim">200 × 208 мм</text>
    <text x="100" y="125" class="part_dim">(Паз + ЭМБЛЕМА АГРОТЕХ + Вент)</text>
</g>

<!-- 5. Правая стенка 200x208 -->
<g transform="translate({ox + 265}, {oy + 315})">
    <rect width="200" height="208" rx="2" class="part_border"/>
    <text x="100" y="100" class="part_title">5. ПРАВАЯ СТЕНКА</text>
    <text x="100" y="112" class="part_dim">200 × 208 мм</text>
    <text x="100" y="125" class="part_dim">(Паз дверцы + Вент-лабиринт)</text>
</g>

<!-- 6. Сдвижная дверца 186x200 -->
<g transform="translate({ox + 510}, {oy + 319})">
    <rect width="186" height="200" rx="3" class="part_border"/>
    <text x="93" y="95" class="part_title">6. СДВИЖНАЯ ДВЕРЦА</text>
    <text x="93" y="107" class="part_dim">186 × 200 мм</text>
    <text x="93" y="120" class="part_dim">(Ручка + БОЛЬШИЕ ВЫЗОВЫ + АГРО)</text>
</g>

<!-- ================= ДЕЛОВОЙ ОСТАТОК (Y = 540..760) ================= -->
<rect x="{ox}" y="{oy + 540}" width="{w_sheet}" height="{h_sheet - 540}" class="leftover"/>
<text x="{ox + w_sheet / 2}" y="{oy + 635}" class="rem_text">ДЕЛОВОЙ ОСТАТОК ФАНЕРЫ: 760 × 220 мм (29% листа)</text>
<text x="{ox + w_sheet / 2}" y="{oy + 655}" class="rem_text" style="font-size:7px; fill:#388e3c; font-weight:normal;">
    (Остаётся цельным куском для лотков растений, кронштейнов датчиков, корпуса экрана или других проектов)
</text>

<!-- Боковой остаток справа -->
<rect x="{ox + 735}" y="{oy + 60}" width="{w_sheet - 735}" height="480" class="leftover"/>

</svg>'''
    fpath = os.path.join(OUT_DIR, '0_Raskroy_Fanery_760x760.svg')
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f"[+] Created layout map: {fpath}")

generate_raskroy_svg()
