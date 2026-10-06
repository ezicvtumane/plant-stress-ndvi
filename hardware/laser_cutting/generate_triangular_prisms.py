import os
import trimesh
import numpy as np
import shapely.geometry

out_dir = r"C:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\hardware\laser_cutting\3D_печать_уголки_под_магниты"
os.makedirs(out_dir, exist_ok=True)

# ==============================================================================
# ПАРАМЕТРЫ ТРЕУГОЛЬНОЙ ПРИЗМЫ:
# Катеты: Lx = 26.0 мм (по крышке/дну), Lz = 26.0 мм (по боковой стенке)
# Глубина по Y: Ly = 10.0 мм (вглубь бокса от переднего притвора Y=0)
# Центр магнита в угловой системе: X = 8.0 мм, Z = 8.0 мм, Y = 0.0 мм (на передней грани)
# Диаметр магнита: 8.1 мм (радиус R = 4.05 мм), глубина гнезда 2.4 мм
# Стенка до гипотенузы: 3.02 мм
# Стенка до фанерных поверхностей: 3.95 мм
# ==============================================================================

Lx = 26.0
Lz = 26.0
Ly = 10.0
mag_r = 4.05
mag_depth = 2.4

# 1. Базовая треугольная призма (Upper Corner Bracket)
# Треугольник в плоскости X-Z: (0,0) -> (26,0) -> (0,26)
poly = shapely.geometry.Polygon([(0.0, 0.0), (Lx, 0.0), (0.0, Lz)])
prism = trimesh.creation.extrude_polygon(poly, height=Ly)
# Экструзия по умолчанию идет по Z. Поворачиваем вокруг X на -90 град,
# чтобы Z стал Y (глубиной), а Y стал Z (высотой):
rot_x = trimesh.transformations.rotation_matrix(-np.pi/2, [1, 0, 0])
prism.apply_transform(rot_x)
# Проверяем ориентацию:
# X в [0, 26]
# Y в [0, 10] (направление вглубь бокса от фасада Y=0)
# Z в [0, 26]

# Гнездо под магнит:
# Цилиндр вдоль оси Y
mag = trimesh.creation.cylinder(radius=mag_r, height=mag_depth, sections=36)
rot_cyl = trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0])
mag.apply_transform(rot_cyl)
mag.apply_translation([8.0, mag_depth / 2.0, 8.0])

bracket_up = prism.difference(mag)
up_stl_path = os.path.join(out_dir, "upper_corner_bracket.stl")
bracket_up.export(up_stl_path)
print(f"Exported upper_corner_bracket.stl -> Volume: {bracket_up.volume:.1f} mm3")

# 2. Нижняя призма с опорной полочкой 4.2 мм под фасад (Lower Corner Bracket with Shelf)
# Полочка выступает вперед по Y от 0 до -4.2 мм, высота по Z от 0 до 5.0 мм, ширина по X от 0 до 26.0 мм
# Фасад толщиной 4 мм садится на эту ступеньку и не сползает вниз.
shelf = trimesh.creation.box(extents=[Lx, 4.2, 5.0])
shelf.apply_translation([Lx / 2.0, -2.1, 2.5])

lower_body = trimesh.boolean.union([prism, shelf])
bracket_low = lower_body.difference(mag)
low_stl_path = os.path.join(out_dir, "lower_corner_bracket_with_shelf.stl")
bracket_low.export(low_stl_path)
print(f"Exported lower_corner_bracket_with_shelf.stl -> Volume: {bracket_low.volume:.1f} mm3")

# Также зеркальный верхний правый и нижний правый (для удобства печати)
# Хотя в слайсере (Cura/BambuStudio/PrusaSlicer) деталь зеркалится одной кнопкой,
# мы сохраним готовые STL
bracket_up_mirrored = bracket_up.copy()
rot_mirror = trimesh.transformations.reflection_matrix([0, 0, 0], [1, 0, 0])
bracket_up_mirrored.apply_transform(rot_mirror)
bracket_up_mirrored.apply_translation([Lx, 0, 0])
bracket_up_mirrored.export(os.path.join(out_dir, "upper_corner_bracket_mirrored.stl"))

print("All triangular prism STL models successfully generated!")
