"""
Конфигурация параметров второй волны эксперимента (Огурец «Каскад»).
Используется для интеграции в web_station.py на Orange Pi 4 Pro.
"""

from typing import Dict, Any, List

EXPERIMENT_META = {
    "title": "Прецизионная оптимизация фитоадаптогенов",
    "track": "Агропромышленные и биотехнологии",
    "crop": "Cucumis sativus (сорт Каскад)",
    "start_date": "2026-10-25",
    "measurement_window": "18:00-18:30",
    "target_weight_net_g": 85.0,
    "emissivity_lwir": 0.98,
    "threshold_delta_t": 0.6,
    "cluster_min_plants": 4,
    "cluster_total_plants": 6,
    "turgor_reaction_trigger_score": 2,
}

TURGOR_SCALE = {
    1: "Полный тургор (Норма, 0-10°)",
    2: "Умеренная потеря тургора (Увядание, 15-25°)",
    3: "Глубокое увядание (Коллапс, >30°)"
}

POTS_CONFIG: Dict[str, Dict[str, Any]] = {
    # Блок 1 (Поддон 1)
    "K1": {"cohort": "Control", "block": 1, "color": "green", "aruco_id": 1, "target_weight": 85.0, "probe": True},
    "K2": {"cohort": "Control", "block": 1, "color": "green", "aruco_id": 1, "target_weight": 85.0, "probe": False},
    "P1": {"cohort": "Prevention", "block": 1, "color": "yellow", "aruco_id": 4, "target_weight": 85.0, "probe": True},
    "P2": {"cohort": "Prevention", "block": 1, "color": "yellow", "aruco_id": 4, "target_weight": 85.0, "probe": False},
    "R1": {"cohort": "Reaction", "block": 1, "color": "blue", "aruco_id": 5, "target_weight": 85.0, "probe": True},
    "R2": {"cohort": "Reaction", "block": 1, "color": "blue", "aruco_id": 5, "target_weight": 85.0, "probe": False},

    # Блок 2 (Поддон 2)
    "K3": {"cohort": "Control", "block": 2, "color": "green", "aruco_id": 1, "target_weight": 85.0, "probe": False},
    "K4": {"cohort": "Control", "block": 2, "color": "green", "aruco_id": 1, "target_weight": 85.0, "probe": False},
    "P3": {"cohort": "Prevention", "block": 2, "color": "yellow", "aruco_id": 4, "target_weight": 85.0, "probe": False},
    "P4": {"cohort": "Prevention", "block": 2, "color": "yellow", "aruco_id": 4, "target_weight": 85.0, "probe": False},
    "R3": {"cohort": "Reaction", "block": 2, "color": "blue", "aruco_id": 5, "target_weight": 85.0, "probe": False},
    "R4": {"cohort": "Reaction", "block": 2, "color": "blue", "aruco_id": 5, "target_weight": 85.0, "probe": False},

    # Блок 3 (Поддон 3)
    "K5": {"cohort": "Control", "block": 3, "color": "green", "aruco_id": 1, "target_weight": 85.0, "probe": False},
    "K6": {"cohort": "Control", "block": 3, "color": "green", "aruco_id": 1, "target_weight": 85.0, "probe": False},
    "P5": {"cohort": "Prevention", "block": 3, "color": "yellow", "aruco_id": 4, "target_weight": 85.0, "probe": False},
    "P6": {"cohort": "Prevention", "block": 3, "color": "yellow", "aruco_id": 4, "target_weight": 85.0, "probe": False},
    "R5": {"cohort": "Reaction", "block": 3, "color": "blue", "aruco_id": 5, "target_weight": 85.0, "probe": False},
    "R6": {"cohort": "Reaction", "block": 3, "color": "blue", "aruco_id": 5, "target_weight": 85.0, "probe": False},

    # Изолированный лоток (Пилот)
    "E1": {"cohort": "Pilot_Epin", "block": 0, "color": "red", "aruco_id": 4, "target_weight": 85.0, "probe": False},
    "E2": {"cohort": "Pilot_Epin", "block": 0, "color": "red", "aruco_id": 4, "target_weight": 85.0, "probe": False},
}

TARGET_WEIGHTS = {pot_id: data["target_weight"] for pot_id, data in POTS_CONFIG.items()}


def calculate_water_dose(current_weight: float, target_weight: float = 85.0) -> float:
    """Расчет дефицита полива в миллилитрах."""
    deficit = target_weight - current_weight
    return round(max(0.0, deficit), 1)


def evaluate_cluster_triggers(daily_measurements: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Оценка кластерных триггеров полива для когорт П и Р.
    
    daily_measurements: {
       "P1": {"delta_t": 0.7, "turgor": 1, "weight": 82.0}, ...
    }
    """
    # 1. Анализ группы Превенция (П1-П6)
    p_stressed_count = sum(
        1 for pid in ["P1", "P2", "P3", "P4", "P5", "P6"]
        if daily_measurements.get(pid, {}).get("delta_t", 0.0) >= EXPERIMENT_META["threshold_delta_t"]
    )
    prevention_triggered = p_stressed_count >= EXPERIMENT_META["cluster_min_plants"]

    # 2. Анализ группы Реакция (Р1-Р6)
    r_stressed_count = sum(
        1 for pid in ["R1", "R2", "R3", "R4", "R5", "R6"]
        if daily_measurements.get(pid, {}).get("turgor", 1) >= EXPERIMENT_META["turgor_reaction_trigger_score"]
    )
    reaction_triggered = r_stressed_count >= EXPERIMENT_META["cluster_min_plants"]

    return {
        "prevention_triggered": prevention_triggered,
        "prevention_stressed_count": p_stressed_count,
        "reaction_triggered": reaction_triggered,
        "reaction_stressed_count": r_stressed_count,
        "pilot_epin_triggered": prevention_triggered, # полив Эпином строго синхронен с группой П
    }
