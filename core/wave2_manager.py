"""
Модуль управления Второй волной эксперимента: Огурец «Каскад» (GRCBD).
Реализует логику фенотипирования, оптическую Z-компенсацию PLA, 
двухфазный кластерный полив и управление базой данных measurements_wave2.csv.
"""

import os
import json
import csv
import time
import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2

# ==============================================================================
# 1. КОНФИГУРАЦИЯ КОГОРТ И ДИЗАЙНА GRCBD (20 ГОРШКОВ)
# ==============================================================================

WAVE2_EXPERIMENT_META = {
    "exp_id": "exp_wave2",
    "name": "Волна 2: Огурец «Каскад» (GRCBD)",
    "plant": "Огурец Каскад",
    "crop": "Cucumis sativus L.",
    "start_date": "2026-10-25",
    "target_weight_net_g": 80.0,
    "pot_height_cm": 7.5,
    "camera_height_cm": 24.5,
    "aruco_floor_size_mm": 15.0,
    "threshold_delta_t": 0.6,
    "cluster_min_plants": 4,
    "cluster_total_plants": 6,
    "turgor_reaction_trigger_score": 2,
    "emissivity_lwir": 0.98,
    "k_bal_ptfe": 4.070,
    "nir_threshold_dn": 7.0,
    "ndvi_threshold": 0.26,
    "min_leaf_component_px": 20,
}

TURGOR_SCALE = {
    1: "1 — Полный тургор (Норма, 0–10°)",
    2: "2 — Умеренное увядание (15–25°, потеря тургора)",
    3: "3 — Глубокое увядание (Критический стресс, >30°)"
}

# Каталог 20 горшков (3 поддона по 6 штук + 1 малый лоток пилота)
POTS_CATALOG: Dict[str, Dict[str, Any]] = {
    # БЛОК 1 (Поддон 1)
    "K1": {"id": "K1", "cohort": "Control", "block": 1, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 80.0, "has_probe": True},
    "K2": {"id": "K2", "cohort": "Control", "block": 1, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 80.0, "has_probe": False},
    "P1": {"id": "P1", "cohort": "Prevention", "block": 1, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 80.0, "has_probe": True},
    "P2": {"id": "P2", "cohort": "Prevention", "block": 1, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 80.0, "has_probe": False},
    "R1": {"id": "R1", "cohort": "Reaction", "block": 1, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 80.0, "has_probe": True},
    "R2": {"id": "R2", "cohort": "Reaction", "block": 1, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 80.0, "has_probe": False},

    # БЛОК 2 (Поддон 2)
    "K3": {"id": "K3", "cohort": "Control", "block": 2, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 80.0, "has_probe": False},
    "K4": {"id": "K4", "cohort": "Control", "block": 2, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 80.0, "has_probe": False},
    "P3": {"id": "P3", "cohort": "Prevention", "block": 2, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 80.0, "has_probe": False},
    "P4": {"id": "P4", "cohort": "Prevention", "block": 2, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 80.0, "has_probe": False},
    "R3": {"id": "R3", "cohort": "Reaction", "block": 2, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 80.0, "has_probe": False},
    "R4": {"id": "R4", "cohort": "Reaction", "block": 2, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 80.0, "has_probe": False},

    # БЛОК 3 (Поддон 3)
    "K5": {"id": "K5", "cohort": "Control", "block": 3, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 80.0, "has_probe": False},
    "K6": {"id": "K6", "cohort": "Control", "block": 3, "color": "#059669", "badge": "🟢 Контроль", "target_weight": 80.0, "has_probe": False},
    "P5": {"id": "P5", "cohort": "Prevention", "block": 3, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 80.0, "has_probe": False},
    "P6": {"id": "P6", "cohort": "Prevention", "block": 3, "color": "#eab308", "badge": "🟡 Превенция", "target_weight": 80.0, "has_probe": False},
    "R5": {"id": "R5", "cohort": "Reaction", "block": 3, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 80.0, "has_probe": False},
    "R6": {"id": "R6", "cohort": "Reaction", "block": 3, "color": "#2563eb", "badge": "🔵 Реакция", "target_weight": 80.0, "has_probe": False},

    # ИЗОЛИРОВАННЫЙ ЛОТОК (Пилот Эпин)
    "E1": {"id": "E1", "cohort": "Pilot_Epin", "block": 0, "color": "#dc2626", "badge": "🔴 Пилот (Эпин)", "target_weight": 80.0, "has_probe": False},
    "E2": {"id": "E2", "cohort": "Pilot_Epin", "block": 0, "color": "#dc2626", "badge": "🔴 Пилот (Эпин)", "target_weight": 80.0, "has_probe": False},
}

# Порядок очереди конвейера по когортам: Контроль -> Реакция -> Превенция -> Пилот
BATCH_QUEUE_WAVE2 = [
    # 1. Контроль (К1–К6)
    "K1", "K2", "K3", "K4", "K5", "K6",
    # 2. Реакция (Р1–Р6)
    "R1", "R2", "R3", "R4", "R5", "R6",
    # 3. Превенция (П1–П6)
    "P1", "P2", "P3", "P4", "P5", "P6",
    # 4. Пилот (Э1–Э2)
    "E1", "E2"
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

def calculate_water_dose(current_weight: Any, target_weight: float = 80.0, pla_cm2: Optional[float] = None) -> Optional[float]:
    """Расчет дефицита полива в миллилитрах с динамической компенсацией нарастания биомассы по PLA."""
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


def detect_aruco_scale_on_floor(gray_img: np.ndarray, real_size_cm: float = 1.5) -> float:
    """
    Детекция ArUco-маркера 15х15 мм на дне бокса.
    Возвращает масштаб: пикселей на сантиметр (px/cm) на плоскости дна.
    Если маркер не найден, возвращает базовое калибровочное значение (40.0 px/cm).
    """
    default_px_per_cm = 40.0
    try:
        # Проверяем доступность словаря ArUco
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        if gray_img.dtype != np.uint8:
            gray_u8 = np.clip(gray_img, 0, 255).astype(np.uint8)
        else:
            gray_u8 = gray_img
        params = (
            cv2.aruco.DetectorParameters()
            if hasattr(cv2.aruco, 'DetectorParameters')
            else cv2.aruco.DetectorParameters_create()
        )
        if hasattr(cv2.aruco, 'ArucoDetector'):
            detector = cv2.aruco.ArucoDetector(aruco_dict, params)
            corners, ids, _ = detector.detectMarkers(gray_u8)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray_u8, aruco_dict, parameters=params)
        
        if ids is not None and len(corners) > 0:
            c = corners[0][0]
            # Длина стороны маркера в пикселях (среднее по 4 граням)
            side_px = (
                np.linalg.norm(c[0] - c[1]) +
                np.linalg.norm(c[1] - c[2]) +
                np.linalg.norm(c[2] - c[3]) +
                np.linalg.norm(c[3] - c[0])
            ) / 4.0
            if side_px > 5.0:
                return float(side_px / real_size_cm)
    except Exception as e:
        pass
    return default_px_per_cm


def compute_single_pot_phenotyping(
    red_channel: np.ndarray,
    nir_channel: np.ndarray,
    pot_id: str = "P1",
    k_bal: float = 4.070,
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
    
    # Отсечение боковых стенок бокса (12% по горизонтали, 6% по вертикали)
    margin_x = int(w * 0.12)
    margin_y = int(h * 0.06)
    raw_mask[:, :margin_x] = False
    raw_mask[:, w - margin_x:] = False
    raw_mask[:margin_y, :] = False
    raw_mask[h - margin_y:, :] = False

    mask_u8 = raw_mask.astype(np.uint8) * 255
    
    # Фильтрация мелких шумов (< 20 px) через connectedComponentsWithStats
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    clean_mask = np.zeros_like(mask_u8)
    min_px = WAVE2_EXPERIMENT_META["min_leaf_component_px"]
    
    valid_plant_pixels = 0
    plant_boxes = []
    
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_px:
            clean_mask[labels == label] = 255
            valid_plant_pixels += area
            x = stats[label, cv2.CC_STAT_LEFT]
            y = stats[label, cv2.CC_STAT_TOP]
            w_box = stats[label, cv2.CC_STAT_WIDTH]
            h_box = stats[label, cv2.CC_STAT_HEIGHT]
            plant_boxes.append((x, y, x + w_box, y + h_box))
            
    # 3. Автоматический расчет Z-масштаба (подобие треугольников)
    # Z_дно = 24.5 см, Z_лист = 24.5 - 7.5 = 17.0 см
    px_per_cm_floor = detect_aruco_scale_on_floor(nir_channel)
    z_ratio = z_camera_cm / max(1.0, (z_camera_cm - h_pot_cm))  # 24.5 / 17.0 ≈ 1.441
    px_per_cm_leaf = px_per_cm_floor * z_ratio
    cm2_per_pixel = 1.0 / (px_per_cm_leaf ** 2)
    
    pla_cm2 = round(valid_plant_pixels * cm2_per_pixel, 2)
    
    # 4. Расчет среднего NDVI листа
    if valid_plant_pixels > 0:
        ndvi_mean = float(np.mean(ndvi_clamped[clean_mask > 0]))
        ndvi_std = float(np.std(ndvi_clamped[clean_mask > 0]))
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
        
    metrics = {
        "pot_id": pot_id,
        "valid_pixels": int(valid_plant_pixels),
        "pla_cm2": pla_cm2,
        "ndvi_mean": round(ndvi_mean, 3),
        "ndvi_std": round(ndvi_std, 3),
        "px_per_cm_leaf": round(px_per_cm_leaf, 1)
    }
    
    return annotated, metrics


# ==============================================================================
# 3. КЛАСТЕРНЫЙ ДВИЖОК ПРИНЯТИЯ РЕШЕНИЙ (DECISION ENGINE)
# ==============================================================================

def evaluate_cohort_cluster_status(records_today: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Кластерный расчет для групп Превенция [П1-П6] и Реакция [Р1-Р6].
    Правило: триггер срабатывает строго при пороге >= 4 из 6 растений.
    """
    # Собираем словари по ID горшка за сегодня
    by_pot: Dict[str, Dict[str, Any]] = {}
    for r in records_today:
        pid = str(r.get("ID", "")).strip().upper()
        if pid:
            by_pot[pid] = r
            
    # Базовый живой эталон Контроля (К1-К6 снимаются первыми)
    k_ids = ["K1", "K2", "K3", "K4", "K5", "K6"]
    k_delta_ts = []
    for kid in k_ids:
        if kid in by_pot:
            val = by_pot[kid].get("Delta_T_C")
            try:
                if val is not None and val != "" and val != "--":
                    k_delta_ts.append(float(val))
            except (ValueError, TypeError):
                pass
    mean_control_dt = (sum(k_delta_ts) / len(k_delta_ts)) if k_delta_ts else None

    # --- 1. Оценка когорты Превенция (П1-П6) с нормировкой по живому Контролю (CWSI) ---
    p_ids = ["P1", "P2", "P3", "P4", "P5", "P6"]
    p_measured = [pid for pid in p_ids if pid in by_pot]
    p_stressed = []

    for pid in p_measured:
        d_t = by_pot[pid].get("Delta_T_C")
        try:
            if d_t is not None and d_t != "" and d_t != "--":
                dt_val = float(d_t)
                # Нормированный подъем Delta-Delta-T относительно живого Контроля
                if mean_control_dt is not None:
                    delta_delta_t = dt_val - mean_control_dt
                    if delta_delta_t >= WAVE2_EXPERIMENT_META["threshold_delta_t"]:
                        p_stressed.append(pid)
                else:
                    if dt_val >= WAVE2_EXPERIMENT_META["threshold_delta_t"]:
                        p_stressed.append(pid)
        except (ValueError, TypeError):
            pass
    p_all_measured = (len(p_measured) == 6)
    p_triggered = (len(p_stressed) >= WAVE2_EXPERIMENT_META["cluster_min_plants"])
    
    # --- 2. Анализ группы РЕАКЦИЯ (Р1-Р6) ---
    r_ids = ["R1", "R2", "R3", "R4", "R5", "R6"]
    r_measured = [pid for pid in r_ids if pid in by_pot]
    r_stressed = []
    
    for pid in r_measured:
        t_score = by_pot[pid].get("Turgor_Score")
        try:
            if t_score is not None and int(t_score) >= WAVE2_EXPERIMENT_META["turgor_reaction_trigger_score"]:
                r_stressed.append(pid)
        except (ValueError, TypeError):
            pass
            
    r_all_measured = (len(r_measured) == 6)
    r_triggered = (len(r_stressed) >= WAVE2_EXPERIMENT_META["cluster_min_plants"])
    
    return {
        "prevention": {
            "measured_count": len(p_measured),
            "stressed_count": len(p_stressed),
            "all_measured": p_all_measured,
            "triggered": p_triggered,
            "status_text": (
                f"ТРИГГЕР СРАБОТАЛ ({len(p_stressed)}/6) — ВЫДАТЬ ВОДУ 100% ДЕФИЦИТА!" if p_triggered
                else (f"Засуха ({len(p_stressed)}/6) — Полив заблокирован" if p_all_measured 
                      else f"Идет замер ({len(p_measured)}/6 измерено, {len(p_stressed)} со стрессом)")
            ),
            "badge_color": "#059669" if p_triggered else ("#dc2626" if p_all_measured else "#eab308")
        },
        "reaction": {
            "measured_count": len(r_measured),
            "stressed_count": len(r_stressed),
            "all_measured": r_all_measured,
            "triggered": r_triggered,
            "status_text": (
                f"УВЯДАНИЕ ({len(r_stressed)}/6) — РЕАНИМАЦИОННЫЙ ПОЛИВ ВОДОЙ!" if r_triggered
                else (f"Тургор в норме ({len(r_stressed)}/6) — Полив заблокирован" if r_all_measured
                      else f"Идет замер ({len(r_measured)}/6 измерено, {len(r_stressed)} увяло)")
            ),
            "badge_color": "#059669" if r_triggered else ("#2563eb" if r_all_measured else "#64748b")
        },
        "pilot_epin": {
            "triggered": p_triggered,
            "status_text": (
                "ПОЛИВ РАСТВОРОМ ЭПИНА ПОД КОРЕНЬ ШПРИЦЕМ ДО 80г!" if p_triggered
                else "Ожидание триггера группы П"
            ),
            "badge_color": "#dc2626" if p_triggered else "#64748b"
        }
    }


# ==============================================================================
# 4. УПРАВЛЕНИЕ ХРАНИЛИЩЕМ CSV (27 КОЛОНОК, ИДЕМПОТЕНТНОСТЬ)
# ==============================================================================

class Wave2Storage:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.wave2_dir = os.path.join(data_dir, "experiments", "exp_wave2")
        self.images_dir = os.path.join(self.wave2_dir, "images")
        self.csv_path = os.path.join(self.wave2_dir, "measurements_wave2.csv")
        self._init_storage()
        
    def _init_storage(self):
        os.makedirs(self.images_dir, exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER_WAVE2)

    def load_all_records(self) -> List[Dict[str, Any]]:
        records = []
        if not os.path.exists(self.csv_path):
            return records
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(dict(row))
        except Exception:
            pass
        return records

    def load_today_records(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        all_recs = self.load_all_records()
        today = []
        for r in all_recs:
            ts = r.get("Timestamp", "")
            if ts.startswith(date_str):
                today.append(r)
        return today

    def save_or_update_record(self, record_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Идемпотентная запись: если замер этого горшка за сегодня уже существует,
        он корректно обновляется. Если нет — дописывается новая строка.
        """
        now = datetime.now()
        today_prefix = now.strftime("%Y-%m-%d")
        pot_id = str(record_data.get("ID", "")).strip().upper()
        
        all_records = self.load_all_records()
        updated = False
        
        for idx, row in enumerate(all_records):
            if row.get("ID", "").strip().upper() == pot_id and row.get("Timestamp", "").startswith(today_prefix):
                # Обновляем существующую запись
                for k in CSV_HEADER_WAVE2:
                    if k in record_data:
                        row[k] = str(record_data[k])
                if "Timestamp" in record_data and record_data["Timestamp"]:
                    row["Timestamp"] = str(record_data["Timestamp"])
                all_records[idx] = row
                updated = True
                break
                
        if not updated:
            # Создаем новую запись
            new_row = {k: "--" for k in CSV_HEADER_WAVE2}
            new_row.update({k: str(v) for k, v in record_data.items() if k in CSV_HEADER_WAVE2})
            if "Timestamp" not in record_data or not record_data["Timestamp"]:
                new_row["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
            all_records.append(new_row)
            
        # Запись обратно в CSV
        temp_csv = self.csv_path + ".tmp"
        try:
            with open(temp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADER_WAVE2)
                writer.writeheader()
                writer.writerows(all_records)
            os.replace(temp_csv, self.csv_path)
            return True, ("Запись обновлена" if updated else "Новая запись добавлена")
        except Exception as e:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)
            return False, f"Ошибка записи: {str(e)}"

    def delete_record(self, pot_id: str, date_str: Optional[str] = None) -> Tuple[bool, str]:
        """Удаление замера горшка за сегодня из measurements_wave2.csv."""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        pot_id = str(pot_id).strip().upper()
        all_records = self.load_all_records()
        new_records = []
        deleted = False
        deleted_opt_file = None
        for r in all_records:
            if r.get("ID", "").strip().upper() == pot_id and r.get("Timestamp", "").startswith(date_str):
                deleted = True
                deleted_opt_file = r.get("Opt_File")
            else:
                new_records.append(r)
        if not deleted:
            return False, f"Замер для горшка {pot_id} за сегодня не найден"
        
        temp_csv = self.csv_path + ".tmp"
        try:
            with open(temp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADER_WAVE2)
                writer.writeheader()
                writer.writerows(new_records)
            os.replace(temp_csv, self.csv_path)

            if deleted_opt_file and deleted_opt_file != "--":
                img_file_path = os.path.join(self.images_dir, deleted_opt_file)
                if os.path.exists(img_file_path):
                    try:
                        os.remove(img_file_path)
                    except Exception:
                        pass
            return True, f"Замер горшка {pot_id} успешно удален"
        except Exception as e:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)
            return False, f"Ошибка при удалении: {e}"

