"""
Конфигурация параметров второй волны эксперимента (Огурец «Каскад», GRCBD).
Полностью согласована с агрономическим модулем core/agronomic_rules.py, core/wave2_manager.py и web_station.py.
"""

from typing import Dict, Any, List, Optional

EXPERIMENT_META = {
    "title": "Прецизионная оптимизация водного баланса и ранняя индикация стресса",
    "track": "Агропромышленные и биотехнологии (Сириус «Большие вызовы» 2026)",
    "crop": "Cucumis sativus L. (сорт «Каскад»)",
    "start_date": "2026-10-25",
    "measurement_window": "18:00-18:30",
    "pot_tare_g": 5.0,
    "target_weight_gross_g": 100.0,
    "biomass_pla_coeff": 0.06,  # Правило №1 Тимирязевки: 0.06 г/см² сырой биомассы листа
    "emissivity_lwir": 0.98,
    "threshold_delta_delta_t": 0.6,  # Правило №2: нормированный триггер ΔΔT >= +0.6 °C относительно контроля
    "cluster_min_plants": 4,  # Кворум: минимум 4 из 6 растений когорты
    "cluster_total_plants": 6,
    "turgor_reaction_trigger_score": 2,  # Балл <= 2: лист лег на бортик горшка
    "k_bal_ptfe": 1.150,
}

TURGOR_SCALE = {
    4: "4 — Оптимум (Норма, угол 0–10°, упругий тургор)",
    3: "3 — Лёгкое поникание в воздухе (30–45°, пластинка не касается бортика)",
    2: "2 — Сильное поникание (Лист лёг на бортик горшка, триггер Реакции)",
    1: "1 — Коллапс (Черешок согнут, пластинка листа лежит на грунте)"
}

POTS_CONFIG: Dict[str, Dict[str, Any]] = {
    # ХОЛОСТОЙ ЛИЗИМЕТР (Контроль чистого испарения почвы E по FAO-56)
    "X0": {"cohort": "Lysimeter", "block": 0, "color": "gray", "target_weight": 100.0, "probe": False, "badge": "⚖️ Лизиметр X0"},

    # БЛОК 1 (Поддон 1)
    "K1": {"cohort": "Control", "block": 1, "color": "green", "target_weight": 100.0, "probe": True, "badge": "🟢 Контроль"},
    "K2": {"cohort": "Control", "block": 1, "color": "green", "target_weight": 100.0, "probe": False, "badge": "🟢 Контроль"},
    "P1": {"cohort": "Prevention", "block": 1, "color": "yellow", "target_weight": 100.0, "probe": True, "badge": "🟡 Превенция"},
    "P2": {"cohort": "Prevention", "block": 1, "color": "yellow", "target_weight": 100.0, "probe": False, "badge": "🟡 Превенция"},
    "R1": {"cohort": "Reaction", "block": 1, "color": "blue", "target_weight": 100.0, "probe": True, "badge": "🔵 Реакция"},
    "R2": {"cohort": "Reaction", "block": 1, "color": "blue", "target_weight": 100.0, "probe": False, "badge": "🔵 Реакция"},

    # БЛОК 2 (Поддон 2)
    "K3": {"cohort": "Control", "block": 2, "color": "green", "target_weight": 100.0, "probe": False, "badge": "🟢 Контроль"},
    "K4": {"cohort": "Control", "block": 2, "color": "green", "target_weight": 100.0, "probe": False, "badge": "🟢 Контроль"},
    "P3": {"cohort": "Prevention", "block": 2, "color": "yellow", "target_weight": 100.0, "probe": False, "badge": "🟡 Превенция"},
    "P4": {"cohort": "Prevention", "block": 2, "color": "yellow", "target_weight": 100.0, "probe": False, "badge": "🟡 Превенция"},
    "R3": {"cohort": "Reaction", "block": 2, "color": "blue", "target_weight": 100.0, "probe": False, "badge": "🔵 Реакция"},
    "R4": {"cohort": "Reaction", "block": 2, "color": "blue", "target_weight": 100.0, "probe": False, "badge": "🔵 Реакция"},

    # БЛОК 3 (Поддон 3)
    "K5": {"cohort": "Control", "block": 3, "color": "green", "target_weight": 100.0, "probe": False, "badge": "🟢 Контроль"},
    "K6": {"cohort": "Control", "block": 3, "color": "green", "target_weight": 100.0, "probe": False, "badge": "🟢 Контроль"},
    "P5": {"cohort": "Prevention", "block": 3, "color": "yellow", "target_weight": 100.0, "probe": False, "badge": "🟡 Превенция"},
    "P6": {"cohort": "Prevention", "block": 3, "color": "yellow", "target_weight": 100.0, "probe": False, "badge": "🟡 Превенция"},
    "R5": {"cohort": "Reaction", "block": 3, "color": "blue", "target_weight": 100.0, "probe": False, "badge": "🔵 Реакция"},
    "R6": {"cohort": "Reaction", "block": 3, "color": "blue", "target_weight": 100.0, "probe": False, "badge": "🔵 Реакция"},

    # ИЗОЛИРОВАННЫЙ СОСУД (Сателлит-микроскопия)
    "C20": {"cohort": "Satellite", "block": 0, "color": "purple", "target_weight": 100.0, "probe": False, "badge": "🟣 Сателлит (Микроскопия)"},
}

TARGET_WEIGHTS = {pot_id: data["target_weight"] for pot_id, data in POTS_CONFIG.items()}


def calculate_target_weight(pla_cm2: float = 0.0, base_weight: float = 100.0) -> float:
    """
    Правило №1 Тимирязевки: Расчет динамической целевой массы с поправкой на рост биомассы.
    M_цель(t) = 100.0 + (PLA * 0.06 г/см²)
    """
    return round(float(base_weight) + (max(0.0, float(pla_cm2)) * EXPERIMENT_META["biomass_pla_coeff"]), 1)


def calculate_water_dose(current_weight: float, pla_cm2: float = 0.0, base_weight: float = 100.0) -> float:
    """
    Прецизионная доза полива шприцем до целевой динамической массы.
    Доза = max(0, M_цель - M_тек)
    """
    target = calculate_target_weight(pla_cm2, base_weight)
    return round(max(0.0, target - float(current_weight)), 1)


def evaluate_cluster_triggers(daily_measurements: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Оценка кластерных кворум-триггеров полива для когорт Превенция (П) и Реакция (Р).
    """
    # 1. Расчет синхронного термального базиса живого Контроля (К1-К6)
    control_pids = ["K1", "K2", "K3", "K4", "K5", "K6"]
    ctrl_dts = [
        daily_measurements[pid]["delta_t"]
        for pid in control_pids
        if pid in daily_measurements and daily_measurements[pid].get("delta_t") is not None
    ]
    mean_ctrl_dt = sum(ctrl_dts) / len(ctrl_dts) if ctrl_dts else 0.0

    # 2. Анализ группы Превенция (П1-П6): триггер по нормированному ΔΔT >= +0.6 °C
    p_pids = ["P1", "P2", "P3", "P4", "P5", "P6"]
    p_stressed_count = 0
    for pid in p_pids:
        if pid in daily_measurements:
            m = daily_measurements[pid]
            ddt = m.get("delta_delta_t")
            if ddt is None and m.get("delta_t") is not None:
                ddt = m["delta_t"] - mean_ctrl_dt
            if ddt is not None and ddt >= EXPERIMENT_META["threshold_delta_delta_t"]:
                p_stressed_count += 1

    prevention_triggered = p_stressed_count >= EXPERIMENT_META["cluster_min_plants"]

    # 3. Анализ группы Реакция (Р1-Р6): триггер по потере тургора (балл <= 2 у >= 4 из 6)
    r_pids = ["R1", "R2", "R3", "R4", "R5", "R6"]
    r_stressed_count = sum(
        1 for pid in r_pids
        if pid in daily_measurements and daily_measurements[pid].get("turgor", 4) <= EXPERIMENT_META["turgor_reaction_trigger_score"]
    )
    reaction_triggered = r_stressed_count >= EXPERIMENT_META["cluster_min_plants"]

    return {
        "mean_control_delta_t": round(mean_ctrl_dt, 2),
        "prevention_triggered": prevention_triggered,
        "prevention_stressed_count": p_stressed_count,
        "reaction_triggered": reaction_triggered,
        "reaction_stressed_count": r_stressed_count,
        "satellite": {
            "status_text": "Донор лаковых реплик (долив воды до 100.0 г)",
            "badge_color": "#8b5cf6"
        }
    }
