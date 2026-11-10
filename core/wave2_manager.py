"""
Модуль управления Второй волной эксперимента: Огурец «Каскад» (GRCBD).
Реализует логику фенотипирования, оптическую Z-компенсацию PLA, 
двухфазный кластерный полив и управление базой данных measurements_wave2.csv.
"""

import os
import csv
import re
import logging
import tempfile
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2

logger = logging.getLogger(__name__)
_STORAGE_LOCK = threading.RLock()
from core.agronomic_rules import (
    CONTROL_BASELINE_MIN_QUORUM,
    evaluate_cohort_prevention_trigger,
    evaluate_cohort_reaction_trigger,
    evaluate_control_baseline_quorum,
    parse_optional_float,
    parse_optional_turgor,
)

# ==============================================================================
# 1. КОНФИГУРАЦИЯ КОГОРТ И ДИЗАЙНА GRCBD (20 ГОРШКОВ)
# ==============================================================================

WAVE2_EXPERIMENT_META = {
    "exp_id": "exp_1792918800",
    "name": "Волна 2: Огурец «Каскад» (GRCBD)",
    "plant": "Огурец Каскад",
    "crop": "Cucumis sativus L.",
    "start_date": "2026-10-25",
    "target_weight_net_g": 100.0,
    "pot_height_cm": 7.5,
    "camera_height_cm": 24.5,
    "aruco_floor_size_mm": 15.0,
    "threshold_delta_t": 0.6,
    "cluster_min_plants": 4,
    "cluster_total_plants": 6,
    "control_baseline_min_quorum": CONTROL_BASELINE_MIN_QUORUM,
    "turgor_reaction_trigger_score": 2,
    "emissivity_lwir": 0.98,
    "k_bal_ptfe": 1.150,
    "k_bal_calibration_version": "calib-kbal-s2-2026-11-07",
    "nir_threshold_dn": 4.0,
    "ndvi_threshold": 0.25,
    "min_leaf_component_px": 100,
}

_CYR_TO_LAT_POT_ID = str.maketrans({"К": "K", "П": "P", "Р": "R", "Х": "X", "С": "C"})
_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\b")

TURGOR_SCALE = {
    4: "4 — Полный тургор (вертикальный стебель, норма)",
    3: "3 — Начальная потеря тургора (поникание кончиков)",
    2: "2 — Умеренное увядание (черешки на кромке стаканчика)",
    1: "1 — Глубокое увядание (критический стресс, потеря прочности)"
}

# Каталог 20 сосудов (18 GRCBD в 3 блоках + C20 сателлит-микроскопия + X0 холостой лизиметр)
POTS_CATALOG: Dict[str, Dict[str, Any]] = {
    # ХОЛОСТОЙ ЛИЗИМЕТР (Контроль испарения почвы E по FAO-56)
    "X0": {"id": "X0", "cohort": "Lysimeter_Blank", "block": 0, "color": "#64748b", "badge": "⚖️ Лизиметр Х0 (FAO-56)", "target_weight": 100.0, "has_probe": False},

    # БЛОК 1 (Поддон 1)
    "K1": {"id": "K1", "cohort": "Control", "block": 1, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 100.0, "has_probe": True},
    "K2": {"id": "K2", "cohort": "Control", "block": 1, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 100.0, "has_probe": False},
    "P1": {"id": "P1", "cohort": "Prevention", "block": 1, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 100.0, "has_probe": True},
    "P2": {"id": "P2", "cohort": "Prevention", "block": 1, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 100.0, "has_probe": False},
    "R1": {"id": "R1", "cohort": "Reaction", "block": 1, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 100.0, "has_probe": True},
    "R2": {"id": "R2", "cohort": "Reaction", "block": 1, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 100.0, "has_probe": False},

    # БЛОК 2 (Поддон 2)
    "K3": {"id": "K3", "cohort": "Control", "block": 2, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 100.0, "has_probe": False},
    "K4": {"id": "K4", "cohort": "Control", "block": 2, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 100.0, "has_probe": False},
    "P3": {"id": "P3", "cohort": "Prevention", "block": 2, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 100.0, "has_probe": False},
    "P4": {"id": "P4", "cohort": "Prevention", "block": 2, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 100.0, "has_probe": False},
    "R3": {"id": "R3", "cohort": "Reaction", "block": 2, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 100.0, "has_probe": False},
    "R4": {"id": "R4", "cohort": "Reaction", "block": 2, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 100.0, "has_probe": False},

    # БЛОК 3 (Поддон 3)
    "K5": {"id": "K5", "cohort": "Control", "block": 3, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 100.0, "has_probe": False},
    "K6": {"id": "K6", "cohort": "Control", "block": 3, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 100.0, "has_probe": False},
    "P5": {"id": "P5", "cohort": "Prevention", "block": 3, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 100.0, "has_probe": False},
    "P6": {"id": "P6", "cohort": "Prevention", "block": 3, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 100.0, "has_probe": False},
    "R5": {"id": "R5", "cohort": "Reaction", "block": 3, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 100.0, "has_probe": False},
    "R6": {"id": "R6", "cohort": "Reaction", "block": 3, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 100.0, "has_probe": False},

    # ИЗОЛИРОВАННЫЙ СОСУД (Сателлит-микроскопия)
    "C20": {"id": "C20", "cohort": "Satellite", "block": 0, "color": "#8b5cf6", "badge": "🟣 Сателлит (Микроскопия)", "target_weight": 100.0, "has_probe": False},
}

# Порядок очереди конвейера по когортам: Лизиметр X0 -> Контроль -> Реакция -> Превенция -> Сателлит C20
BATCH_QUEUE_WAVE2 = [
    # 0. Холостой лизиметр FAO-56 (Х0)
    "X0",
    # 1. Контроль (К1–К6)
    "K1", "K2", "K3", "K4", "K5", "K6",
    # 2. Реакция (Р1–Р6)
    "R1", "R2", "R3", "R4", "R5", "R6",
    # 3. Превенция (П1–П6)
    "P1", "P2", "P3", "P4", "P5", "P6",
    # 4. Сателлит-микроскопия (С20)
    "C20"
]

# Структура CSV-журнала (27 колонок: 25 старых + Turgor_Score + Water_Dose_ml)
CSV_HEADER_WAVE2 = [
    'ID', 'Timestamp', 'Group', 'Weight_g', 'T_Air_C', 'RH_Air_Pct',
    'Moisture_V', 'Moisture_Pct', 'T_Leaf_C', 'Delta_T_C', 'VPD_kPa',
    'NDVI_Mean', 'NDVI_Std', 'Leaf_Area_cm2', 'Opt_File', 'Thermal_File',
    'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9',
    'Turgor_Score', 'Water_Dose_ml'
]


# ==============================================================================
# 2. МАТЕМАТИЧЕСКИЕ И ОПТИЧЕСКИЕ ФУНКЦИИ (CV + Z-КАЛИБРОВКА)
# ==============================================================================

def calculate_water_dose(current_weight: Any, target_weight: float = 100.0, pla_cm2: Optional[float] = None) -> Optional[float]:
    """
    Расчет дефицита полива (мл) до целевой массы сосуда.
    По итогам аудита (Option A) активный конвейер Волны 2 передает pla_cm2=None
    (целевая масса строго 100.0 г); опциональный параметр pla_cm2 сохранен для
    исследовательских расчетов (+ round(pla_cm2 * 0.06, 1) при явной передаче).
    """
    if current_weight is None or current_weight == "" or current_weight == "--":
        return None
    try:
        adjusted_target = float(target_weight)
        if pla_cm2 is not None:
            try:
                pla_val = float(pla_cm2)
                if pla_val > 0:
                    adjusted_target += round(pla_val * 0.06, 1)
            except (ValueError, TypeError):
                pass
        deficit = adjusted_target - float(current_weight)
        return round(max(0.0, deficit), 1)
    except (ValueError, TypeError):
        return None
def calculate_delta_t(t_leaf: Any, t_air: Any) -> Optional[float]:
    """Автоматический расчет температурного дифференциала листа Delta T."""
    if t_leaf is None or t_air is None or t_leaf == "" or t_air == "" or t_leaf == "--" or t_air == "--":
        return None
    try:
        return round(float(t_leaf) - float(t_air), 2)
    except (ValueError, TypeError):
        return None


def get_agronomic_ndvi_lut() -> np.ndarray:
    """Agronomic RdYlGn palette from station 1.0."""
    lut = np.zeros((256, 1, 3), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        if t < 0.25:
            k = t / 0.25
            r = int(180 + k * 40)
            g = int(20 + k * 80)
            b = 20
        elif t < 0.60:
            k = (t - 0.25) / 0.35
            r = int(220 - k * 140)
            g = int(100 + k * 120)
            b = 25
        else:
            k = (t - 0.60) / 0.40
            r = int(80 - k * 60)
            g = int(220 - k * 30)
            b = int(25 + k * 30)
        lut[i, 0] = [b, g, r]  # BGR
    return lut

AGRONOMIC_NDVI_LUT = get_agronomic_ndvi_lut()


class ScaleResult(float):
    """Прозрачный float с метаданными детекции ArUco."""
    detected: bool = False
    id: Optional[int] = None
    corners: Optional[np.ndarray] = None
    side_px: float = 0.0

    def __new__(cls, val, detected=False, marker_id=None, corners=None, side_px=0.0):
        obj = super().__new__(cls, val)
        obj.detected = detected
        obj.id = marker_id
        obj.corners = corners
        obj.side_px = side_px
        return obj


def detect_aruco_scale_on_floor(gray_img: np.ndarray, real_size_cm: float = 1.5, secondary_img: np.ndarray = None) -> ScaleResult:
    """
    Детекция ArUco-маркера 15х15 мм на дне бокса с адаптивной контрастной нормализацией (CLAHE).
    Возвращает масштаб: пикселей на сантиметр (px/cm) на плоскости дна.
    Если маркер не найден, возвращает базовое калибровочное значение (40.0 px/cm).
    """
    default_px_per_cm = 40.0
    images_to_try = [gray_img]
    if secondary_img is not None:
        images_to_try.append(secondary_img)

    for cur_img in images_to_try:
        if cur_img is None:
            continue
        try:
            # Адаптивная контрастная нормализация (CLAHE):
            # Инфракрасный канал имеет узкий динамический диапазон (0-30 DN).
            # Растягиваем гистограмму и применяем CLAHE для уверенной детекции ArUco.
            if cur_img.max() > cur_img.min():
                norm_u8 = cv2.normalize(cur_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                gray_u8 = clahe.apply(norm_u8)
            elif cur_img.dtype != np.uint8:
                gray_u8 = np.clip(cur_img, 0, 255).astype(np.uint8)
            else:
                gray_u8 = cur_img

            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            params = (
                cv2.aruco.DetectorParameters()
                if hasattr(cv2.aruco, 'DetectorParameters')
                else cv2.aruco.DetectorParameters_create()
            )
            params.adaptiveThreshWinSizeMin = 3
            params.adaptiveThreshWinSizeMax = 53
            params.adaptiveThreshWinSizeStep = 4

            if hasattr(cv2.aruco, 'ArucoDetector'):
                detector = cv2.aruco.ArucoDetector(aruco_dict, params)
                corners, ids, _ = detector.detectMarkers(gray_u8)
            else:
                corners, ids, _ = cv2.aruco.detectMarkers(gray_u8, aruco_dict, parameters=params)
            
            if ids is not None and len(corners) > 0:
                h_img, w_img = cur_img.shape[:2]
                flat_ids = np.asarray(ids).flatten()
                for idx_c, corner_wrap in enumerate(corners):
                    c = np.asarray(corner_wrap).reshape(4, 2)
                    sides = [float(np.linalg.norm(c[i] - c[(i + 1) % 4])) for i in range(4)]
                    min_side = min(sides)
                    max_side = max(sides)
                    aspect = (min_side / max_side) if max_side > 0 else 0.0
                    cx = float(np.mean(c[:, 0]))
                    cy = float(np.mean(c[:, 1]))
                    # Геометрический и позиционный фильтр против CLAHE-артефактов на стенках бокса:
                    # отвергаем сплющенные/мелкие ложные срабатывания (<30 px, aspect < 0.70) и краевые стены (<15% / >85% X).
                    if (
                        min_side < 30.0
                        or aspect < 0.70
                        or cx < 0.15 * w_img
                        or cx > 0.85 * w_img
                        or cy < 0.05 * h_img
                        or cy > 0.95 * h_img
                    ):
                        continue
                    side_px = sum(sides) / 4.0
                    scale = float(side_px / real_size_cm)
                    mid = int(flat_ids[idx_c])
                    print(f"[ArUco Scale]: Обнаружен маркер ID={mid}, грань={side_px:.1f}px, масштаб дна={scale:.2f} px/cm")
                    return ScaleResult(scale, detected=True, marker_id=mid, corners=c, side_px=side_px)
        except Exception as e:
            print(f"[ArUco Scale Warning]: {e}")

    return ScaleResult(default_px_per_cm, detected=False)


def compute_single_pot_phenotyping(
    red_channel: np.ndarray,
    nir_channel: np.ndarray,
    pot_id: str = "P1",
    k_bal: float = 1.150,
    z_camera_cm: float = 24.5,
    h_pot_cm: float = 7.5
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Высокоточная сегментация одиночного растения огурца.
    1. Расчет канонического NDVI с балансом белого k_bal.
    2. Оптическая Z-компенсация масштаба по высоте горшка.
    3. Выделение суммарного Bounding Box листа и расчет PLA (см²).
    4. Генерация аннотированного кадра с контрастной плашкой метрик.
    """
    h, w = red_channel.shape[:2]
    
    # 1. Полномасштабный расчет NDVI через float32
    red_f = red_channel.astype(np.float32)
    nir_f = nir_channel.astype(np.float32)
    
    # Каноническая нормализация отражения с балансом белого (k_bal * NIR - Red)
    numerator = (k_bal * nir_f) - red_f
    denominator = (k_bal * nir_f) + red_f + 1e-6
    ndvi_raw = numerator / denominator
    ndvi_clamped = np.clip(ndvi_raw, -1.0, 1.0)
    
    # 2. Сегментация мезофилла листа (устранение фона торфа, пластика и боковых стенок бокса)
    nir_thresh = WAVE2_EXPERIMENT_META["nir_threshold_dn"]
    ndvi_thresh = WAVE2_EXPERIMENT_META["ndvi_threshold"]
    raw_mask = (ndvi_clamped > ndvi_thresh) & (nir_f > nir_thresh)
    
    # Отсечение боковых стенок и углов бокса (20% по горизонтали, 10% сверху, 16% снизу)
    margin_x = int(w * 0.20)
    margin_top = int(h * 0.10)
    margin_bottom = int(h * 0.16)
    raw_mask[:, :margin_x] = False
    raw_mask[:, w - margin_x:] = False
    raw_mask[:margin_top, :] = False
    raw_mask[h - margin_bottom:, :] = False

    mask_u8 = raw_mask.astype(np.uint8) * 255
    # Морфологическое связывание и устранение микробликов кутикулы
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel_close)
    
    # Фильтрация шумов через connectedComponentsWithStats с проверкой центроидов
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    clean_mask = np.zeros_like(mask_u8)
    min_px = WAVE2_EXPERIMENT_META["min_leaf_component_px"]
    
    valid_plant_pixels = 0
    plant_boxes = []
    
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_px:
            cx, cy = centroids[label]
            # Растение находится в центральном горшке: отсекаем возможные краевые артефакты дна
            if cx < w * 0.22 or cx > w * 0.78 or cy > h * 0.82:
                continue
            clean_mask[labels == label] = 255
            valid_plant_pixels += area
            x = stats[label, cv2.CC_STAT_LEFT]
            y = stats[label, cv2.CC_STAT_TOP]
            w_box = stats[label, cv2.CC_STAT_WIDTH]
            h_box = stats[label, cv2.CC_STAT_HEIGHT]
            plant_boxes.append((x, y, x + w_box, y + h_box))
            
    # 3. Автоматический расчет Z-масштаба (подобие треугольников)
    # Z_дно = 24.5 см, Z_лист = 24.5 - 7.5 = 17.0 см
    px_per_cm_floor = detect_aruco_scale_on_floor(nir_channel, secondary_img=red_channel)
    z_ratio = z_camera_cm / max(1.0, (z_camera_cm - h_pot_cm))  # 24.5 / 17.0 ≈ 1.441
    px_per_cm_leaf = px_per_cm_floor * z_ratio
    cm2_per_pixel = 1.0 / (px_per_cm_leaf ** 2)
    
    pla_cm2 = float(round(valid_plant_pixels * cm2_per_pixel, 2))
    
    # 4. Расчет среднего NDVI листа с фильтрацией битых артефактных пикселей (0.0 / 1.0)
    if valid_plant_pixels > 0:
        raw_plant_pixels = ndvi_clamped[clean_mask > 0]
        valid_ndvi = raw_plant_pixels[(raw_plant_pixels > 0.0) & (raw_plant_pixels < 1.0)]
        calc_ndvi = valid_ndvi if len(valid_ndvi) > 0 else raw_plant_pixels
        ndvi_mean = float(np.mean(calc_ndvi))
        ndvi_std = float(np.std(calc_ndvi))
    else:
        ndvi_mean = 0.0
        ndvi_std = 0.0
        
    # 5. Отрисовка колоризованного NDVI в агрономической палитре RdYlGn (как на станции 1)
    ndvi_disp = np.clip((ndvi_clamped - 0.20) / 0.65 * 255.0, 0, 255).astype(np.uint8)
    annotated = cv2.LUT(cv2.cvtColor(ndvi_disp, cv2.COLOR_GRAY2BGR), AGRONOMIC_NDVI_LUT)
    # Темный нейтральный фон для почвы, горшка и бокса (как на станции 1)
    annotated[clean_mask == 0] = [35, 15, 30]
    
    # Если найдены компоненты растения, строим единый габаритный прямоугольник
    if plant_boxes:
        min_x = min(b[0] for b in plant_boxes)
        min_y = min(b[1] for b in plant_boxes)
        max_x = max(b[2] for b in plant_boxes)
        max_y = max(b[3] for b in plant_boxes)
        
        # Рисуем яркую зеленую рамку вокруг всего растения
        cv2.rectangle(annotated, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)
        
        # Плашка с метриками над рамкой
        meta_text = f"[{pot_id}] NDVI: {ndvi_mean:.2f} | PLA: {pla_cm2:.1f} cm2"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        (tw, th), _ = cv2.getTextSize(meta_text, font, font_scale, thickness)
        
        # Фон плашки
        badge_y1 = max(0, min_y - th - 10)
        badge_y2 = min_y
        badge_x2 = min(w, min_x + tw + 14)
        cv2.rectangle(annotated, (min_x, badge_y1), (badge_x2, badge_y2), (0, 0, 0), -1)
        cv2.rectangle(annotated, (min_x, badge_y1), (badge_x2, badge_y2), (0, 255, 0), 1)
        cv2.putText(annotated, meta_text, (min_x + 7, badge_y2 - 5), font, font_scale, (255, 255, 255), thickness)

    # Отрисовка обнаруженного ArUco-маркера масштаба на кадре
    if getattr(px_per_cm_floor, 'detected', False) and getattr(px_per_cm_floor, 'corners', None) is not None:
        try:
            pts = px_per_cm_floor.corners.astype(np.int32)
            cv2.polylines(annotated, [pts], isClosed=True, color=(255, 200, 0), thickness=2)
            cx = int(pts[:, 0].mean())
            cy = int(pts[:, 1].mean())
            cv2.putText(annotated, f"ArUco #{px_per_cm_floor.id} ({px_per_cm_floor:.1f} px/cm)", (max(5, cx - 40), max(15, cy - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1, cv2.LINE_AA)
        except Exception:
            pass
        
    metrics = {
        "pot_id": pot_id,
        "valid_pixels": int(valid_plant_pixels),
        "pla_cm2": pla_cm2,
        "ndvi_mean": round(ndvi_mean, 3),
        "ndvi_std": round(ndvi_std, 3),
        "px_per_cm_leaf": float(round(px_per_cm_leaf, 1)),
        "aruco_detected": bool(getattr(px_per_cm_floor, 'detected', False)),
        "aruco_id": getattr(px_per_cm_floor, 'id', None)
    }
    
    return annotated, metrics


def normalize_and_validate_pot_id(pot_id: Any) -> Optional[str]:
    """
    Нормализует и проверяет идентификатор горшка по строгому каталогу `POTS_CATALOG`
    (`K1–K6`, `P1–P6`, `R1–R6`, явные исключения `X0` и `C20`).
    Поддерживает транслитерацию кириллических префиксов (`К/П/Р/Х/С`).
    Пустые, некорректные и неизвестные ID возвращают `None`.
    """
    if pot_id is None or isinstance(pot_id, bool):
        return None
    norm = str(pot_id).strip().upper().translate(_CYR_TO_LAT_POT_ID)
    if not norm or norm not in POTS_CATALOG:
        return None
    return norm


def _extract_record_date(rec: Dict[str, Any]) -> Optional[str]:
    ts = str(rec.get("Timestamp", "")).strip()
    m = _DATE_PREFIX_RE.match(ts)
    return m.group(1) if m else None


# ==============================================================================
# 3. КЛАСТЕРНЫЙ ДВИЖОК ПРИНЯТИЯ РЕШЕНИЙ (DECISION ENGINE)
# ==============================================================================

def evaluate_cohort_cluster_status(records_today: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Кластерный расчет для групп Превенция [П1-П6] и Реакция [Р1-Р6].
    Делегирует классификацию единым правилам core/agronomic_rules.py:
    - Базис Контроля K1–K6: синхронный кворум минимум >= 4 из 6 валидных ΔT одной даты.
    - Превенция: ΔΔT >= +0.6 °C минимум у 4 из 6 растений.
    - Реакция: Turgor_Score <= 2 минимум у 4 из 6 растений.
    Пропуски (None / '' / '--' / 'NaN') не подменяются значениями по умолчанию и не считаются замеренными.
    """
    by_pot: Dict[str, Dict[str, Any]] = {}
    for r in records_today:
        pid = normalize_and_validate_pot_id(r.get("ID"))
        if pid is not None:
            by_pot[pid] = r

    # Базовый живой эталон Контроля (К1-К6) с проверкой синхронности дат и кворума (>= 4/6)
    k_ids = ["K1", "K2", "K3", "K4", "K5", "K6"]
    p_ids = ["P1", "P2", "P3", "P4", "P5", "P6"]
    k_raw_vals: List[Any] = []
    k_dates: set[str] = set()
    for kid in k_ids:
        rec_k = by_pot.get(kid)
        if rec_k is None:
            k_raw_vals.append(None)
            continue
        raw_dt = rec_k.get("Delta_T_C")
        k_raw_vals.append(raw_dt)
        if parse_optional_float(raw_dt) is not None:
            d_k = _extract_record_date(rec_k)
            if d_k:
                k_dates.add(d_k)

    p_dates: set[str] = set()
    for pid in p_ids:
        rec_p = by_pot.get(pid)
        if rec_p is not None and parse_optional_float(rec_p.get("Delta_T_C")) is not None:
            d_p = _extract_record_date(rec_p)
            if d_p:
                p_dates.add(d_p)

    # Если у замеров K или P заданы даты, все задействованные замеры ΔT должны относиться к одному дню
    dates_synchronized = (
        len(k_dates) <= 1
        and len(p_dates) <= 1
        and (not k_dates or not p_dates or k_dates == p_dates)
    )

    k_min_quorum = WAVE2_EXPERIMENT_META["control_baseline_min_quorum"]
    k_total = WAVE2_EXPERIMENT_META["cluster_total_plants"]
    baseline_eval = evaluate_control_baseline_quorum(
        k_raw_vals,
        min_quorum=k_min_quorum,
        total_plants=k_total,
    )
    control_baseline_ready = bool(baseline_eval["ready"] and dates_synchronized)
    mean_control_dt = baseline_eval["mean_control_dt"] if control_baseline_ready else None

    # --- 1. Оценка когорты Превенция (П1-П6) ---
    p_raw_dts: List[float] = []
    p_ddts: List[Optional[float]] = []
    for pid in p_ids:
        if pid not in by_pot:
            p_ddts.append(None)
            continue
        dt_val = parse_optional_float(by_pot[pid].get("Delta_T_C"))
        if dt_val is not None:
            p_raw_dts.append(dt_val)
            # Без синхронного кворумного контрольного базиса K1-K6 ΔΔT не вычисляется
            p_ddts.append((dt_val - mean_control_dt) if control_baseline_ready and mean_control_dt is not None else None)
        else:
            p_ddts.append(None)

    if control_baseline_ready:
        prev_eval = evaluate_cohort_prevention_trigger(
            p_ddts,
            threshold=WAVE2_EXPERIMENT_META["threshold_delta_t"],
            min_plants=WAVE2_EXPERIMENT_META["cluster_min_plants"],
            total_plants=WAVE2_EXPERIMENT_META["cluster_total_plants"],
        )
        p_measured_cnt = prev_eval["total_measured"]
        p_stressed_cnt = prev_eval["triggered_count"]
        p_all_measured = p_measured_cnt == WAVE2_EXPERIMENT_META["cluster_total_plants"]
        p_triggered = prev_eval["is_triggered"]
        p_insufficient = prev_eval["is_insufficient"]
        p_state = prev_eval["state"]
        p_status_text = (
            f"ТРИГГЕР СРАБОТАЛ ({p_stressed_cnt}/6) — ВЫДАТЬ ВОДУ 100% ДЕФИЦИТА!"
            if p_triggered
            else (
                f"Засуха ({p_stressed_cnt}/6) — Полив заблокирован"
                if not p_insufficient
                else f"Недостаточно данных ({p_measured_cnt}/6 измерено, {p_stressed_cnt} со стрессом)"
            )
        )
    else:
        p_measured_cnt = len(p_raw_dts)
        p_stressed_cnt = 0
        p_all_measured = False
        p_triggered = False
        p_insufficient = True
        p_state = "insufficient_data"
        k_cnt = baseline_eval["measured_count"]
        if not dates_synchronized:
            p_status_text = (
                f"Рассинхронизированный контрольный базис K1–K6 (разные даты К/П; ΔT Превенции: {p_measured_cnt}/6) — Полив заблокирован"
            )
        elif k_cnt == 0:
            p_status_text = (
                f"Нет контрольного базиса K1–K6 (0/{k_total}, нужно ≥ {k_min_quorum}; ΔT Превенции: {p_measured_cnt}/6) — Полив заблокирован"
            )
        else:
            p_status_text = (
                f"Неполный контрольный базис K1–K6 ({k_cnt}/{k_total}, нужно ≥ {k_min_quorum}; ΔT Превенции: {p_measured_cnt}/6) — Полив заблокирован"
            )

    # --- 2. Оценка когорты Реакция (Р1-Р6) по 4-балльной шкале (балл <= 2) ---
    r_ids = ["R1", "R2", "R3", "R4", "R5", "R6"]
    r_scores: List[Optional[int]] = [
        parse_optional_turgor(by_pot[pid].get("Turgor_Score")) if pid in by_pot else None
        for pid in r_ids
    ]
    react_eval = evaluate_cohort_reaction_trigger(
        r_scores,
        threshold_score=WAVE2_EXPERIMENT_META["turgor_reaction_trigger_score"],
        min_plants=WAVE2_EXPERIMENT_META["cluster_min_plants"],
        total_plants=WAVE2_EXPERIMENT_META["cluster_total_plants"],
    )
    r_measured_cnt = react_eval["total_measured"]
    r_stressed_cnt = react_eval["triggered_count"]
    r_all_measured = r_measured_cnt == WAVE2_EXPERIMENT_META["cluster_total_plants"]
    r_triggered = react_eval["is_triggered"]
    r_insufficient = react_eval["is_insufficient"]

    return {
        "prevention": {
            "measured_count": p_measured_cnt,
            "stressed_count": p_stressed_cnt,
            "all_measured": p_all_measured,
            "insufficient_data": p_insufficient,
            "control_baseline_ready": control_baseline_ready,
            "control_measured_count": baseline_eval["measured_count"],
            "control_required_quorum": k_min_quorum,
            "dates_synchronized": dates_synchronized,
            "mean_control_dt": mean_control_dt,
            "state": p_state,
            "triggered": p_triggered,
            "status_text": p_status_text,
            "badge_color": "#059669" if p_triggered else ("#dc2626" if not p_insufficient else "#eab308"),
        },
        "reaction": {
            "measured_count": r_measured_cnt,
            "stressed_count": r_stressed_cnt,
            "all_measured": r_all_measured,
            "insufficient_data": r_insufficient,
            "state": react_eval["state"],
            "triggered": r_triggered,
            "status_text": (
                f"УВЯДАНИЕ ({r_stressed_cnt}/6) — РЕАНИМАЦИОННЫЙ ПОЛИВ ВОДОЙ!"
                if r_triggered
                else (
                    f"Тургор в норме ({r_stressed_cnt}/6) — Полив заблокирован"
                    if not r_insufficient
                    else f"Недостаточно данных ({r_measured_cnt}/6 измерено, {r_stressed_cnt} увяло)"
                )
            ),
            "badge_color": "#059669" if r_triggered else ("#2563eb" if not r_insufficient else "#64748b"),
        },
        "satellite": {
            "status_text": "Донор лаковых реплик (долив воды до 100.0 г)",
            "badge_color": "#8b5cf6",
        },
    }


def resolve_cohort_watering_decision(
    pot_id: str,
    raw_deficit_ml: Optional[float],
    cluster_status: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Определяет итоговое решение о поливе конкретного горшка с учетом блокировки когорт Превенции/Реакции.
    Неизвестные и пустые ID строго отклоняются (`watering_allowed=False`) без fallback в Control.
    Исключения `X0` (холостой лизиметр) и `C20` (сателлит) обрабатываются явно.
    """
    pid = normalize_and_validate_pot_id(pot_id)
    if pid is None or pid not in POTS_CATALOG:
        return {
            "watering_allowed": False,
            "effective_dose": 0.0 if raw_deficit_ml is not None else None,
            "raw_deficit": raw_deficit_ml,
            "reason": "unknown_pot_id",
            "status_label": "ПОЛИВ ЗАПРЕЩЁН (неизвестный ID)",
        }

    cohort = POTS_CATALOG[pid]["cohort"]

    if cohort in ("Prevention", "Reaction"):
        key = "prevention" if cohort == "Prevention" else "reaction"
        st = cluster_status.get(key, {})
        if st.get("triggered"):
            return {
                "watering_allowed": True,
                "effective_dose": raw_deficit_ml,
                "raw_deficit": raw_deficit_ml,
                "reason": "triggered",
                "status_label": "ПОЛИВ РАЗРЕШЕН (ТРИГГЕР)",
            }
        if st.get("insufficient_data", True):
            return {
                "watering_allowed": False,
                "effective_dose": 0.0 if raw_deficit_ml is not None else None,
                "raw_deficit": raw_deficit_ml,
                "reason": "insufficient_data",
                "status_label": "Ожидание замера когорты",
            }
        return {
            "watering_allowed": False,
            "effective_dose": 0.0 if raw_deficit_ml is not None else None,
            "raw_deficit": raw_deficit_ml,
            "reason": "blocked",
            "status_label": "ПОЛИВ ЗАБЛОКИРОВАН",
        }

    if cohort == "Control":
        return {
            "watering_allowed": True,
            "effective_dose": raw_deficit_ml,
            "raw_deficit": raw_deficit_ml,
            "reason": "optimum",
            "status_label": "Регламентный долив",
        }

    if pid == "X0" and cohort == "Lysimeter_Blank":
        return {
            "watering_allowed": True,
            "effective_dose": raw_deficit_ml,
            "raw_deficit": raw_deficit_ml,
            "reason": "lysimeter_x0",
            "status_label": "Долив лизиметра X0 (FAO-56)",
        }

    if pid == "C20" and cohort == "Satellite":
        return {
            "watering_allowed": True,
            "effective_dose": raw_deficit_ml,
            "raw_deficit": raw_deficit_ml,
            "reason": "satellite_c20",
            "status_label": "Долив сателлита C20",
        }

    return {
        "watering_allowed": False,
        "effective_dose": 0.0 if raw_deficit_ml is not None else None,
        "raw_deficit": raw_deficit_ml,
        "reason": "unsupported_cohort",
        "status_label": "ПОЛИВ ЗАПРЕЩЁН (неподдерживаемая когорта)",
    }


def evaluate_pot_watering_with_projection(
    today_records: List[Dict[str, Any]],
    pot_id: str,
    updated_fields: Dict[str, Any],
    raw_deficit_ml: Optional[float],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Проецирует текущее измерение/правку горшка в дневной срез и возвращает
    (решение_о_поливе, статус_кластера) для всей группы с учетом новых данных.
    """
    pid = normalize_and_validate_pot_id(pot_id)
    if pid is None:
        cluster_status = evaluate_cohort_cluster_status(today_records)
        decision = resolve_cohort_watering_decision(pot_id, raw_deficit_ml, cluster_status)
        return decision, cluster_status

    existing = next(
        (dict(r) for r in today_records if normalize_and_validate_pot_id(r.get("ID")) == pid),
        {"ID": pid},
    )
    existing.update(updated_fields)
    existing["ID"] = pid
    projected = [
        r for r in today_records if normalize_and_validate_pot_id(r.get("ID")) != pid
    ] + [existing]
    cluster_status = evaluate_cohort_cluster_status(projected)
    decision = resolve_cohort_watering_decision(pid, raw_deficit_ml, cluster_status)
    return decision, cluster_status


def format_watering_decision_output(decision: Dict[str, Any]) -> Dict[str, str]:
    """Единое форматирование текста и HTML ячейки дозы полива для API и таблицы UI."""
    eff = decision.get("effective_dose")
    raw = decision.get("raw_deficit")
    if decision.get("watering_allowed"):
        if eff is not None:
            return {
                "dose_text": f"{float(eff):.1f} мл",
                "dose_html": (
                    f'<span data-watering="allowed" style="display: inline-block; color: #047857; '
                    f'background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; '
                    f'padding: 2px 8px; font-weight: 800;" title="Полив разрешён">{float(eff):.1f}</span>'
                ),
            }
        return {"dose_text": "--", "dose_html": "--"}

    is_insuff = decision.get("reason") == "insufficient_data"
    label = "БЛОК (недостаточно данных)" if is_insuff else "ПОЛИВ ЗАБЛОКИРОВАН"
    def_text = f" (дефицит {float(raw):.1f} мл)" if raw is not None else ""
    tooltip = f"{label}{def_text}"
    dose_val = "0.0" if raw is not None else "--"
    sub_def_html = (
        f' <span style="color: #94a3b8; font-weight: 500; font-size: 11px;" '
        f'title="Расчётный дефицит без полива">({float(raw):.1f})</span>'
        if (raw is not None and float(raw) > 0.0)
        else ""
    )
    return {
        "dose_text": f"{label}{def_text}",
        "dose_html": (
            f'<span data-watering="blocked" style="display: inline-block; color: #dc2626; '
            f'background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; '
            f'padding: 2px 8px; font-weight: 800;" title="{tooltip}">{dose_val}</span>{sub_def_html}'
        ),
    }


# ==============================================================================
# 4. УПРАВЛЕНИЕ ХРАНИЛИЩЕМ CSV (27 КОЛОНОК, ИДЕМПОТЕНТНОСТЬ)
# ==============================================================================

class Wave2Storage:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        # Поддержка канонического таймстемпа exp_1792918800 с fallback на exp_wave2
        exp_target = os.path.join(data_dir, "experiments", "exp_1792918800")
        exp_legacy = os.path.join(data_dir, "experiments", "exp_wave2")
        self.wave2_dir = exp_target if os.path.exists(exp_target) or not os.path.exists(exp_legacy) else exp_legacy
        self.images_dir = os.path.join(self.wave2_dir, "images")
        self.csv_path = os.path.join(self.wave2_dir, "measurements_wave2.csv")
        self._init_storage()
        
    def _init_storage(self):
        os.makedirs(self.images_dir, exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER_WAVE2)

    def _read_all_records_unlocked(self, strict: bool = False) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        if not os.path.exists(self.csv_path):
            return records
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(dict(row))
        except Exception as exc:
            logger.warning("Failed to read Wave 2 CSV %s: %s", self.csv_path, exc)
            if strict:
                raise
            return []
        return records

    def _write_records_atomic_unlocked(self, records: List[Dict[str, Any]]) -> None:
        fd, temp_csv = tempfile.mkstemp(
            dir=self.wave2_dir,
            prefix=".tmp_wave2_",
            suffix=".csv",
        )
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADER_WAVE2)
                writer.writeheader()
                writer.writerows(records)
            os.replace(temp_csv, self.csv_path)
        except Exception:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)
            raise

    def load_all_records(self) -> List[Dict[str, Any]]:
        with _STORAGE_LOCK:
            return self._read_all_records_unlocked(strict=False)

    def load_today_records(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        all_recs = self.load_all_records()
        return [r for r in all_recs if r.get("Timestamp", "").startswith(date_str)]

    def save_or_update_record(self, record_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Идемпотентная потокобезопасная запись: если замер этого горшка за сегодня уже существует,
        он корректно обновляется. Если нет — дописывается новая строка.
        """
        now = datetime.now()
        today_prefix = now.strftime("%Y-%m-%d")
        raw_id = str(record_data.get("ID", "")).strip()
        pot_id = normalize_and_validate_pot_id(raw_id) or raw_id.upper()

        with _STORAGE_LOCK:
            try:
                all_records = self._read_all_records_unlocked(strict=True)
            except Exception as e:
                return False, f"Ошибка чтения журнала: {e}"

            updated = False
            for idx, row in enumerate(all_records):
                row_pid = normalize_and_validate_pot_id(row.get("ID")) or str(row.get("ID", "")).strip().upper()
                if row_pid == pot_id and row.get("Timestamp", "").startswith(today_prefix):
                    for k in CSV_HEADER_WAVE2:
                        if k in record_data:
                            row[k] = str(record_data[k])
                    row["ID"] = pot_id
                    if "Timestamp" in record_data and record_data["Timestamp"]:
                        row["Timestamp"] = str(record_data["Timestamp"])
                    all_records[idx] = row
                    updated = True
                    break

            if not updated:
                new_row = {k: "--" for k in CSV_HEADER_WAVE2}
                new_row.update({k: str(v) for k, v in record_data.items() if k in CSV_HEADER_WAVE2})
                new_row["ID"] = pot_id
                if "Timestamp" not in record_data or not record_data["Timestamp"]:
                    new_row["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
                all_records.append(new_row)

            try:
                self._write_records_atomic_unlocked(all_records)
                return True, ("Запись обновлена" if updated else "Новая запись добавлена")
            except Exception as e:
                return False, f"Ошибка записи: {e}"

    def sync_cohort_water_doses(self, date_str: Optional[str] = None) -> int:
        """
        Пересчитывает `Water_Dose_ml` для уже сохранённых за дату горшков Превенции и Реакции,
        чтобы при срабатывании или сбросе кворума 4/6 CSV оставался согласованным с UI.
        """
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")
        with _STORAGE_LOCK:
            try:
                all_records = self._read_all_records_unlocked(strict=True)
            except Exception:
                return 0

            date_rows = [r for r in all_records if str(r.get("Timestamp", "")).startswith(target_date)]
            if not date_rows:
                return 0

            cluster_status = evaluate_cohort_cluster_status(date_rows)
            changed = 0
            for row in all_records:
                if not str(row.get("Timestamp", "")).startswith(target_date):
                    continue
                pid = normalize_and_validate_pot_id(row.get("ID"))
                if pid is None or POTS_CATALOG[pid]["cohort"] not in ("Prevention", "Reaction"):
                    continue
                raw_def = calculate_water_dose(row.get("Weight_g"), POTS_CATALOG[pid].get("target_weight", 100.0))
                if raw_def is None:
                    continue
                decision = resolve_cohort_watering_decision(pid, raw_def, cluster_status)
                eff_str = str(decision["effective_dose"])
                if row.get("Water_Dose_ml") != eff_str:
                    row["Water_Dose_ml"] = eff_str
                    changed += 1

            if changed > 0:
                self._write_records_atomic_unlocked(all_records)
            return changed

    def delete_record(
        self,
        pot_id: str,
        date_str: Optional[str] = None,
        allow_fallback_any_date: bool = False,
    ) -> Tuple[bool, str]:
        """Потокобезопасное удаление замера горшка (по умолчанию только за активную дату, без порчи архива)."""
        raw_id = str(pot_id).strip()
        norm_id = normalize_and_validate_pot_id(raw_id) or raw_id.upper()
        target_date = date_str if date_str is not None else datetime.now().strftime("%Y-%m-%d")

        with _STORAGE_LOCK:
            try:
                all_records = self._read_all_records_unlocked(strict=True)
            except Exception as e:
                return False, f"Ошибка чтения при удалении: {e}"

            target_idx = None
            for i, r in enumerate(all_records):
                row_pid = normalize_and_validate_pot_id(r.get("ID")) or str(r.get("ID", "")).strip().upper()
                if row_pid == norm_id and str(r.get("Timestamp", "")).startswith(target_date):
                    target_idx = i
                    break

            if target_idx is None and allow_fallback_any_date:
                for i, r in enumerate(all_records):
                    row_pid = normalize_and_validate_pot_id(r.get("ID")) or str(r.get("ID", "")).strip().upper()
                    if row_pid == norm_id:
                        target_idx = i

            if target_idx is None:
                return False, f"Замер для горшка {norm_id} за {target_date} не найден"

            removed_row = all_records[target_idx]
            new_records = [r for i, r in enumerate(all_records) if i != target_idx]

            try:
                self._write_records_atomic_unlocked(new_records)
            except Exception as e:
                return False, f"Ошибка при удалении: {e}"

            still_referenced = {
                os.path.basename(str(r.get(col, "")).strip())
                for r in new_records
                for col in ("Opt_File", "Thermal_File")
                if r.get(col) not in (None, "", "--")
            }
            for col in ("Opt_File", "Thermal_File"):
                fname = str(removed_row.get(col) or "").strip()
                if not fname or fname == "--":
                    continue
                safe_fname = os.path.basename(fname)
                if safe_fname in still_referenced:
                    continue
                img_file_path = os.path.join(self.images_dir, safe_fname)
                if os.path.isfile(img_file_path):
                    try:
                        os.remove(img_file_path)
                    except OSError as exc:
                        logger.warning("Could not remove %s: %s", img_file_path, exc)

            return True, f"Замер горшка {norm_id} за {target_date} успешно удален"

