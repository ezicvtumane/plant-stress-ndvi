"""
Конфигурация параметров второй волны эксперимента (Огурец «Каскад», GRCBD).
Полностью согласована с агрономическим модулем core/agronomic_rules.py, core/wave2_manager.py и web_station.py.
"""

import os
import sys
from typing import Dict, Any, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.agronomic_rules import (
    CONTROL_BASELINE_MIN_QUORUM,
    evaluate_cohort_prevention_trigger,
    evaluate_cohort_reaction_trigger,
    evaluate_control_baseline_quorum,
    parse_optional_float,
    parse_optional_turgor,
)

EXPERIMENT_META = {
    "title": "Прецизионная оптимизация водного баланса и ранняя индикация стресса",
    "track": "Агропромышленные и биотехнологии (Сириус «Большие вызовы» 2026)",
    "crop": "Cucumis sativus L. (сорт «Каскад»)",
    "start_date": "2026-10-25",
    "target_window": "18:00-18:30",  # Целевое окно (факт 09.11: 19:27-19:40 оптика / 20:48-23:08 тепло)
    "pot_tare_g": 5.0,
    "target_weight_gross_g": 100.0,
    "biomass_pla_coeff": 0.06,  # Правило №1 (опционально) (опционально; в активном этапе Option A отключено)
    "emissivity_lwir": 0.98,
    "threshold_delta_delta_t": 0.6,  # Правило №2: нормированный триггер ΔΔT >= +0.6 °C относительно контроля
    "cluster_min_plants": 4,  # Кворум: минимум 4 из 6 растений когорты
    "cluster_total_plants": 6,
    "control_baseline_min_quorum": CONTROL_BASELINE_MIN_QUORUM,  # Кворум контрольного базиса K1–K6 (4/6)
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
    Правило №1 (CWSI / FAO-56): Расчет динамической целевой массы с поправкой на рост биомассы.
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


def _parse_opt_float(val: Any) -> Optional[float]:
    return parse_optional_float(val)


def evaluate_cluster_triggers(daily_measurements: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Оценка кластерных кворум-триггеров полива для когорт Превенция (П) и Реакция (Р).
    Тонкая обёртка над каноническими правилами core/agronomic_rules.py.
    """
    control_pids = ["K1", "K2", "K3", "K4", "K5", "K6"]
    ctrl_raw = [
        daily_measurements[pid].get("delta_t") if pid in daily_measurements else None
        for pid in control_pids
    ]
    baseline_eval = evaluate_control_baseline_quorum(
        ctrl_raw,
        min_quorum=EXPERIMENT_META["control_baseline_min_quorum"],
        total_plants=EXPERIMENT_META["cluster_total_plants"],
    )
    baseline_ready = baseline_eval["ready"]
    mean_ctrl_dt = baseline_eval["mean_control_dt"]

    p_pids = ["P1", "P2", "P3", "P4", "P5", "P6"]
    p_ddts: List[Optional[float]] = []
    for pid in p_pids:
        if pid not in daily_measurements or not baseline_ready:
            p_ddts.append(None)
            continue
        m = daily_measurements[pid]
        ddt = parse_optional_float(m.get("delta_delta_t"))
        if ddt is None and mean_ctrl_dt is not None:
            dt_val = parse_optional_float(m.get("delta_t"))
            if dt_val is not None:
                ddt = dt_val - mean_ctrl_dt
        p_ddts.append(ddt)

    if baseline_ready:
        prev_eval = evaluate_cohort_prevention_trigger(
            p_ddts,
            threshold=EXPERIMENT_META["threshold_delta_delta_t"],
            min_plants=EXPERIMENT_META["cluster_min_plants"],
            total_plants=EXPERIMENT_META["cluster_total_plants"],
        )
        prevention_triggered = prev_eval["is_triggered"]
        p_stressed_count = prev_eval["triggered_count"]
    else:
        prevention_triggered = False
        p_stressed_count = 0

    r_pids = ["R1", "R2", "R3", "R4", "R5", "R6"]
    r_scores = [
        daily_measurements[pid].get("turgor") if pid in daily_measurements else None
        for pid in r_pids
    ]
    react_eval = evaluate_cohort_reaction_trigger(
        r_scores,
        threshold_score=EXPERIMENT_META["turgor_reaction_trigger_score"],
        min_plants=EXPERIMENT_META["cluster_min_plants"],
        total_plants=EXPERIMENT_META["cluster_total_plants"],
    )

    return {
        "mean_control_delta_t": mean_ctrl_dt,
        "control_baseline_ready": baseline_ready,
        "control_measured_count": baseline_eval["measured_count"],
        "control_required_quorum": baseline_eval["required_quorum"],
        "prevention_triggered": prevention_triggered,
        "prevention_stressed_count": p_stressed_count,
        "reaction_triggered": react_eval["is_triggered"],
        "reaction_stressed_count": react_eval["triggered_count"],
        "satellite": {
            "status_text": "Донор лаковых реплик (долив воды до 100.0 г)",
            "badge_color": "#8b5cf6"
        }
    }
