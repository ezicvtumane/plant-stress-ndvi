"""
Генератор производственной геометрии бокса 210х210х297 мм с чистыми замками шип-паз (finger joints)
без наложений контуров, без пересечений и без угловых дефектов.
"""

import os

T = 4.0        # Толщина фанеры 4 мм
W = 210.0      # Внутренняя ширина (мм)
D = 210.0      # Внутренняя глубина (мм)
H = 297.0      # Внутренняя высота (мм)

MAG_D = 8.1    # Отверстие под магнит 8х2 мм (+0.1 мм допуск)

OUTPUT_DIR = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\hardware\laser_cutting"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def svg_wrap(w, h, content):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">\n'
        f'  <defs>\n'
        f'    <style>\n'
        f'      .cut {{ fill: none; stroke: #ff0000; stroke-width: 0.15; stroke-linecap: round; stroke-linejoin: round; }}\n'
        f'      .engrave {{ fill: none; stroke: #0000ff; stroke-width: 0.15; stroke-dasharray: 1.5,1.5; }}\n'
        f'      .text {{ font-family: Segoe UI, Arial, sans-serif; font-size: 3.5px; fill: #1e293b; }}\n'
        f'      .title {{ font-family: Segoe UI, Arial, sans-serif; font-size: 5px; font-weight: bold; fill: #0f172a; }}\n'
        f'    </style>\n'
        f'  </defs>\n'
        f'{content}\n'
        f'</svg>'
    )

# ----------------- 1. ЗАДНЯЯ СТЕНКА -----------------
def get_back_wall_path():
    pts = []
    # Верхняя грань: x от -T до W+T (шипы на j = 0, 2, 4, 6)
    pts.append((-T, -T))
    pts.append((30.0, -T))
    pts.append((30.0, 0.0))
    pts.append((60.0, 0.0))
    pts.append((60.0, -T))
    pts.append((90.0, -T))
    pts.append((90.0, 0.0))
    pts.append((120.0, 0.0))
    pts.append((120.0, -T))
    pts.append((150.0, -T))
    pts.append((150.0, 0.0))
    pts.append((180.0, 0.0))
    pts.append((180.0, -T))
    pts.append((W + T, -T))
    
    # Правая грань: y от -T до H+T (шипы на четных k: 0, 2, 4, 6, 8, 10)
    for k in range(11):
        y0, y1 = k * 27.0, (k + 1) * 27.0
        if k % 2 == 0:
            if k > 0:
                pts.append((W + T, y0))
            pts.append((W + T, y1))
        else:
            pts.append((W, y0))
            pts.append((W, y1))
            
    # Нижняя грань: x от W+T до -T (шипы на j = 6, 4, 2, 0)
    pts.append((W + T, H + T))
    pts.append((180.0, H + T))
    pts.append((180.0, H))
    pts.append((150.0, H))
    pts.append((150.0, H + T))
    pts.append((120.0, H + T))
    pts.append((120.0, H))
    pts.append((90.0, H))
    pts.append((90.0, H + T))
    pts.append((60.0, H + T))
    pts.append((60.0, H))
    pts.append((30.0, H))
    pts.append((30.0, H + T))
    pts.append((-T, H + T))
    
    # Левая грань: y от H+T до -T (k от 10 до 0)
    for k in range(10, -1, -1):
        y0, y1 = k * 27.0, (k + 1) * 27.0
        if k % 2 == 0:
            if k < 10:
                pts.append((-T, y1))
            pts.append((-T, y0))
        else:
            pts.append((0.0, y1))
            pts.append((0.0, y0))
            
    return pts

# ----------------- 2. ЛЕВАЯ И ПРАВАЯ СТЕНКИ -----------------
def get_side_wall_path(is_left=True):
    pts = []
    # Начинаем в точке сопряжения пазов (T, 0)
    pts.append((T, 0.0))
    pts.append((30.0, 0.0))
    # j = 1: шип вверх
    pts.append((30.0, -T))
    pts.append((60.0, -T))
    pts.append((60.0, 0.0))
    # j = 2: паз
    pts.append((90.0, 0.0))
    # j = 3: шип вверх
    pts.append((90.0, -T))
    pts.append((120.0, -T))
    pts.append((120.0, 0.0))
    # j = 4: паз
    pts.append((150.0, 0.0))
    # j = 5: шип вверх
    pts.append((150.0, -T))
    pts.append((180.0, -T))
    pts.append((180.0, 0.0))
    # j = 6: до передней грани D
    pts.append((D, 0.0))
    
    # Передняя грань: ровная вертикаль для прилегания фасада
    pts.append((D, H))
    
    # Нижняя грань: от D к T
    pts.append((180.0, H))
    pts.append((180.0, H + T))
    pts.append((150.0, H + T))
    pts.append((150.0, H))
    pts.append((120.0, H))
    pts.append((120.0, H + T))
    pts.append((90.0, H + T))
    pts.append((90.0, H))
    pts.append((60.0, H))
    pts.append((60.0, H + T))
    pts.append((30.0, H + T))
    pts.append((30.0, H))
    pts.append((T, H))
    
    # Задняя грань: снизу вверх (k от 10 до 0)
    for k in range(10, -1, -1):
        y0, y1 = k * 27.0, (k + 1) * 27.0
        if k % 2 == 0:
            # паз внутрь (x = T)
            pts.append((T, y0))
        else:
            # шип наружу (x = 0)
            pts.append((0.0, y1))
            pts.append((0.0, y0))
            pts.append((T, y0))
            
    return pts

# ----------------- 3. ВЕРХНЯЯ КРЫШКА -----------------
def get_top_lid_path():
    pts = []
    # Начинаем в точке (0, T)
    # Задняя грань: пазы под задник на четных j
    pts.append((0.0, T))
    pts.append((30.0, T))
    pts.append((30.0, 0.0))
    pts.append((60.0, 0.0))
    pts.append((60.0, T))
    pts.append((90.0, T))
    pts.append((90.0, 0.0))
    pts.append((120.0, 0.0))
    pts.append((120.0, T))
    pts.append((150.0, T))
    pts.append((150.0, 0.0))
    pts.append((180.0, 0.0))
    pts.append((180.0, T))
    pts.append((W, T))
    
    # Правая грань: пазы под правую стенку на нечетных k (1, 3, 5)
    pts.append((W, 30.0))
    pts.append((W - T, 30.0))
    pts.append((W - T, 60.0))
    pts.append((W, 60.0))
    pts.append((W, 90.0))
    pts.append((W - T, 90.0))
    pts.append((W - T, 120.0))
    pts.append((W, 120.0))
    pts.append((W, 150.0))
    pts.append((W - T, 150.0))
    pts.append((W - T, 180.0))
    pts.append((W, 180.0))
    pts.append((W, D))
    
    # Передняя грань: ровный торец
    pts.append((0.0, D))
    
    # Левая грань: пазы под левую стенку на нечетных k (снизу вверх)
    pts.append((0.0, 180.0))
    pts.append((T, 180.0))
    pts.append((T, 150.0))
    pts.append((0.0, 150.0))
    pts.append((0.0, 120.0))
    pts.append((T, 120.0))
    pts.append((T, 90.0))
    pts.append((0.0, 90.0))
    pts.append((0.0, 60.0))
    pts.append((T, 60.0))
    pts.append((T, 30.0))
    pts.append((0.0, 30.0))
    pts.append((0.0, T))
    
    return pts

# ----------------- 4. ДНО БОКСА -----------------
def get_bottom_plate_path():
    pts_top = get_top_lid_path()
    pts = []
    idx_wd = pts_top.index((W, D))
    pts.extend(pts_top[:idx_wd])
    
    # Выступ порожка спереди (+10 мм)
    shoe_depth = 10.0
    pts.append((W, D))
    pts.append((W + T, D))
    pts.append((W + T, D + shoe_depth))
    pts.append((-T, D + shoe_depth))
    pts.append((-T, D))
    pts.append((0.0, D))
    
    idx_l6 = pts_top.index((0.0, 180.0))
    pts.extend(pts_top[idx_l6:])
    return pts

# ----------------- 5. СЪЕМНЫЙ НАКЛАДНОЙ ФАСАД (ДВЕРЦА) -----------------
def get_facade_path():
    f_w = W + 2 * T # 218.0 мм
    f_h = H         # 297.0 мм
    pts = [
        (0.0, 0.0),
        (f_w, 0.0),
        (f_w, f_h),
        (f_w - 30.0, f_h),
        (f_w - 30.0, f_h + T),
        (f_w - 60.0, f_h + T),
        (f_w - 60.0, f_h),
        (60.0, f_h),
        (60.0, f_h + T),
        (30.0, f_h + T),
        (30.0, f_h),
        (0.0, f_h)
    ]
    return pts

def pts_to_svg(pts, offset_x=0, offset_y=0):
    cmd = []
    for i, (x, y) in enumerate(pts):
        c = "M" if i == 0 else "L"
        cmd.append(f"{c} {(x + offset_x):.2f} {(y + offset_y):.2f}")
    cmd.append("Z")
    return " ".join(cmd)
