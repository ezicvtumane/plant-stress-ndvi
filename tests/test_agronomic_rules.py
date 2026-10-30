"""
Unit-тесты для модуля правил Тимирязевки (серия «Волна 2», Cucumis sativus L.).
Охватывает:
- Правило №1: Динамическая биомасса M_цель(t) и доза долива воды.
- Правило №2: Нормированный триггер ΔΔT и кворум когорты Превенция.
- Правило №3: Лизиметрический контроль чистого испарения субстрата (X0) и расчет истинной транспирации по стандартам FAO-56.
"""

import pytest
from core.agronomic_rules import (
    calc_target_weight,
    calc_watering_dose,
    calc_delta_t,
    calc_mean_control_delta_t,
    calc_delta_delta_t,
    evaluate_cohort_prevention_trigger,
    calc_substrate_evaporation,
    calc_true_transpiration,
    calc_transpiration_intensity,
    analyze_cohort_transpiration,
    BASE_TARE_WEIGHT_G,
    BIOMASS_PLA_COEFF,
    DELTA_DELTA_T_THRESHOLD_C,
    PREVENTION_MIN_TRIGGERED_PLANTS,
    LYSIMETER_POT_ID
)


# --- ТЕСТЫ ПРАВИЛА №1 ---

def test_rule1_dynamic_target_weight():
    """Тест Правила №1: M_цель(t) = 85.0 + PLA * 0.06 г/см²."""
    # Фаза 1: Проросток, нет площади листа
    assert calc_target_weight(0.0) == 85.0
    assert calc_target_weight(None) == 85.0

    # Фаза 2: Нарастание листьев огурца
    assert calc_target_weight(25.0) == 86.5  # 85.0 + 25 * 0.06 = 86.5
    assert calc_target_weight(50.0) == 88.0  # 85.0 + 50 * 0.06 = 88.0
    assert calc_target_weight(100.0) == 91.0 # 85.0 + 100 * 0.06 = 91.0

    # Защита от отрицательных значений
    assert calc_target_weight(-10.0) == 85.0


def test_rule1_watering_dose():
    """Тест расчета прецизионной дозы полива."""
    # При PLA = 25 см², целевая масса 86.5 г
    # Текущая масса 80.0 г -> доза 6.5 мл
    assert calc_watering_dose(80.0, pla_cm2=25.0) == 6.5

    # Текущая масса 86.5 г -> доза 0.0 мл
    assert calc_watering_dose(86.5, pla_cm2=25.0) == 0.0

    # Масса превышает целевую (переувлажнение) -> доза не должна быть отрицательной
    assert calc_watering_dose(89.0, pla_cm2=25.0) == 0.0


# --- ТЕСТЫ ПРАВИЛА №2 ---

def test_rule2_delta_t_and_control_mean():
    """Тест вычисления разницы температур и среднего живого контроля."""
    # Лист охлаждается транспирацией (норма)
    assert calc_delta_t(24.8, 26.6) == -1.8

    # Стресс (устьица закрыты, лист нагрет)
    assert calc_delta_t(27.4, 26.6) == 0.8

    # Средний контроль по 6 горшкам K1–K6
    k_dts = [-1.8, -1.7, -1.9, -1.6, -1.8, -1.7]
    assert calc_mean_control_delta_t(k_dts) == -1.75

    # Пустой список контроля
    assert calc_mean_control_delta_t([]) is None


def test_rule2_delta_delta_t_trigger():
    """Тест нормированного триггера ΔΔT = ΔT_i - mean(ΔT_контроль) >= +0.6°C."""
    mean_ctrl = -1.8

    # Растение с ΔT = -1.2°C (теплее контроля на +0.6°C) -> ТРИГГЕР
    dt, ddt, triggered = calc_delta_delta_t(25.4, 26.6, mean_ctrl)
    assert dt == -1.2
    assert ddt == 0.6
    assert triggered is True

    # Растение с ΔT = -1.3°C (теплее контроля на +0.5°C) -> НЕТ ТРИГГЕРА
    dt, ddt, triggered = calc_delta_delta_t(25.3, 26.6, mean_ctrl)
    assert dt == -1.3
    assert ddt == 0.5
    assert triggered is False

    # Если контроль еще не измерен (None)
    dt, ddt, triggered = calc_delta_delta_t(25.4, 26.6, None)
    assert dt == -1.2
    assert ddt is None
    assert triggered is False


def test_prevention_cohort_quorum():
    """Тест кворума триггера когорты Превенция (>= 4 из 6 растений)."""
    # 3 растения со стрессом из 6 -> кворум НЕ достигнут
    dts_3 = [0.8, 0.7, 0.6, 0.4, 0.2, 0.1]
    res_3 = evaluate_cohort_prevention_trigger(dts_3)
    assert res_3["is_triggered"] is False
    assert res_3["triggered_count"] == 3

    # 4 растения со стрессом из 6 -> кворум ДОСТИГНУТ
    dts_4 = [0.9, 0.8, 0.7, 0.6, 0.3, 0.1]
    res_4 = evaluate_cohort_prevention_trigger(dts_4)
    assert res_4["is_triggered"] is True
    assert res_4["triggered_count"] == 4

    # 5 растений со стрессом -> кворум ДОСТИГНУТ
    dts_5 = [0.9, 0.8, 0.7, 0.65, 0.6, 0.2]
    res_5 = evaluate_cohort_prevention_trigger(dts_5)
    assert res_5["is_triggered"] is True
    assert res_5["triggered_count"] == 5


# --- ТЕСТЫ ПРАВИЛА №3 (Лизиметр X0 и стандарты FAO-56) ---

def test_rule3_substrate_evaporation_x0():
    """Тест вычисления чистого испарения субстрата по лизиметрическому горшку X0."""
    # За сутки масса X0 снизилась с 80.0 г до 76.8 г (испарилось 3.2 г)
    e_sub = calc_substrate_evaporation(80.0, 76.8)
    assert e_sub == 3.2

    # Если X0 долили водой (масса выросла с 76.8 до 80.0) -> испарение 0.0 г
    assert calc_substrate_evaporation(76.8, 80.0) == 0.0

    # Защита от некорректных типов
    assert calc_substrate_evaporation(None, 76.8) == 0.0


def test_rule3_true_transpiration_optimal():
    """Тест расчета истинной транспирации для активно транспирирующего растения."""
    # Горшок K1 потерял 8.5 г за сутки. Испарение субстрата X0 составило 3.2 г.
    # Истинная транспирация T_ист = 8.5 - 3.2 = 5.3 г
    res = calc_true_transpiration(m_plant_prev=81.5, m_plant_curr=73.0, e_substrate=3.2)
    assert res["total_water_loss_g"] == 8.5
    assert res["substrate_evaporation_g"] == 3.2
    assert res["true_transpiration_g"] == 5.3
    assert res["stomatal_status"] == "optimal"
    assert res["is_occluded"] is False


def test_rule3_true_transpiration_occlusion():
    """Тест фиксации устьичной окклюзии (транспирация устьицами прекратилась)."""
    # Горшок R3 (засуха) потерял всего 2.8 г, тогда как даже чистый субстрат потерял 3.2 г.
    # T_ист = 2.8 - 3.2 = -0.4 г <= 0 -> УСТЬИЧНАЯ ОККЛЮЗИЯ
    res = calc_true_transpiration(m_plant_prev=68.0, m_plant_curr=65.2, e_substrate=3.2)
    assert res["total_water_loss_g"] == 2.8
    assert res["true_transpiration_g"] == -0.4
    assert res["stomatal_status"] == "occluded"
    assert res["is_occluded"] is True


def test_rule3_transpiration_intensity():
    """Тест расчета удельной интенсивности транспирации E_tr [мг / (см² · ч)]."""
    # Растение транспирировало 5.3 г (5300 мг) воды за 24 ч при PLA = 40.0 см²
    # E_tr = 5300 / (40.0 * 24) = 5300 / 960 = 5.52 мг/(см²·ч)
    intensity = calc_transpiration_intensity(t_true_g=5.3, pla_cm2=40.0, dt_hours=24.0)
    assert intensity == 5.52

    # При нулевой площади листьев интенсивность не вычисляется
    assert calc_transpiration_intensity(t_true_g=5.3, pla_cm2=0.0) is None


def test_rule3_cohort_analysis():
    """Тест комплексного агрегатора когорты."""
    cohort_data = [
        {'pot_id': 'K1', 'm_prev': 80.0, 'm_curr': 72.0, 'pla': 30.0}, # loss 8.0, T_ист 5.0
        {'pot_id': 'K2', 'm_prev': 80.0, 'm_curr': 73.0, 'pla': 32.0}, # loss 7.0, T_ист 4.0
        {'pot_id': 'K3', 'm_prev': 80.0, 'm_curr': 71.5, 'pla': 35.0}, # loss 8.5, T_ист 5.5
        {'pot_id': 'K4', 'm_prev': 80.0, 'm_curr': 72.5, 'pla': 28.0}, # loss 7.5, T_ист 4.5
        {'pot_id': 'K5', 'm_prev': 80.0, 'm_curr': 73.5, 'pla': 30.0}, # loss 6.5, T_ист 3.5
        {'pot_id': 'K6', 'm_prev': 80.0, 'm_curr': 72.0, 'pla': 33.0}, # loss 8.0, T_ист 5.0
    ]
    e_substrate = 3.0 # Чистое испарение с X0

    res = analyze_cohort_transpiration(cohort_data, e_substrate=e_substrate, dt_hours=24.0)
    assert res["total_plants"] == 6
    assert res["occluded_count"] == 0
    assert res["occlusion_percent"] == 0.0
    assert res["mean_true_transpiration_g"] == 4.58  # (5.0 + 4.0 + 5.5 + 4.5 + 3.5 + 5.0) / 6 = 27.5 / 6 = 4.5833
    assert res["mean_intensity_mg_cm2_h"] is not None
