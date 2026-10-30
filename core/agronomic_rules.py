"""
Агрономический модуль фенотипирования и водного баланса (серия «Волна 2», Cucumis sativus L.).
Теоретический и методический базис:
- Методика полевого опыта и рандомизированный блочный дизайн GRCBD (Доспехов Б.А., 1985).
- Модель устьичного термогенеза и индекса водного стресса CWSI (Idso, Jackson et al., 1981).
- Стандарты гравиметрического учета эвапотранспирации и лизиметрии FAO-56 (Allen et al., 1998).
"""

from typing import List, Tuple, Optional, Dict, Any

# Константы стандарта Тимирязевки для огурца сорта «Каскад»
BASE_TARE_WEIGHT_G: float = 85.0       # Базовая тарированная масса горшка с субстратом и водой (г)
BIOMASS_PLA_COEFF: float = 0.06        # Эмпирический коэффициент сырой биомассы листа огурца (г/см²)
DELTA_DELTA_T_THRESHOLD_C: float = 0.6 # Порог стрессового отклика относительно контроля (°C)
PREVENTION_MIN_TRIGGERED_PLANTS: int = 4 # Порог кворума для срабатывания превентивного полива (из 6)
TOTAL_COHORT_PLANTS: int = 6
LYSIMETER_POT_ID: str = 'X0'           # Идентификатор лизиметрического контрольного горшка без растения


# --- ПРАВИЛО №1: Адаптивная биомасса и доза долива ---

def calc_target_weight(
    pla_cm2: float = 0.0,
    base_weight: float = BASE_TARE_WEIGHT_G,
    coeff: float = BIOMASS_PLA_COEFF
) -> float:
    """
    Правило №1 Тимирязевки: Расчет динамической целевой массы с учетом нарастания биомассы листа.
    M_цель(t) = 85.0 + (PLA * 0.06 г/см²)
    """
    try:
        pla = max(0.0, float(pla_cm2))
    except (ValueError, TypeError):
        pla = 0.0
    return round(float(base_weight) + (pla * float(coeff)), 1)


def calc_watering_dose(
    current_weight: float,
    pla_cm2: float = 0.0,
    base_weight: float = BASE_TARE_WEIGHT_G,
    coeff: float = BIOMASS_PLA_COEFF
) -> float:
    """
    Правило №1 Тимирязевки: Прецизионная доза долива воды до целевой динамической массы.
    Доза = max(0.0, M_цель(t) - M_тек)
    """
    target = calc_target_weight(pla_cm2, base_weight, coeff)
    try:
        cur_w = float(current_weight)
    except (ValueError, TypeError):
        cur_w = target
    return round(max(0.0, target - cur_w), 1)


# --- ПРАВИЛО №2: Нормированный триггер температуры ---

def calc_delta_t(t_leaf: float, t_air: float) -> float:
    """
    Расчет разницы температур листа и воздуха:
    ΔT = T_лист - T_возд (°C)
    """
    return round(float(t_leaf) - float(t_air), 2)


def calc_mean_control_delta_t(control_delta_ts: List[float]) -> Optional[float]:
    """
    Вычисляет средний ΔT живого синхронного контроля (K1–K6).
    Возвращает None, если данных по контролю пока нет.
    """
    valid_dts = [float(dt) for dt in control_delta_ts if dt is not None]
    if not valid_dts:
        return None
    return round(sum(valid_dts) / len(valid_dts), 2)


def calc_delta_delta_t(
    t_leaf: float,
    t_air: float,
    mean_control_delta_t: Optional[float]
) -> Tuple[float, Optional[float], bool]:
    """
    Правило №2 Тимирязевки: Нормированный триггер стресса относительно синхронного контроля.
    ΔΔT = ΔT_i - mean(ΔT_контроль)

    Возвращает кортеж:
    (delta_t, delta_delta_t, is_triggered)
    Если mean_control_delta_t is None, delta_delta_t будет None, is_triggered = False.
    """
    dt = calc_delta_t(t_leaf, t_air)
    if mean_control_delta_t is None:
        return dt, None, False
    ddt = round(dt - float(mean_control_delta_t), 2)
    triggered = ddt >= DELTA_DELTA_T_THRESHOLD_C
    return dt, ddt, triggered


def evaluate_cohort_prevention_trigger(
    prevention_plants_ddt: List[Optional[float]],
    threshold: float = DELTA_DELTA_T_THRESHOLD_C,
    min_plants: int = PREVENTION_MIN_TRIGGERED_PLANTS
) -> Dict[str, Any]:
    """
    Оценивает кворум срабатывания триггера для когорты Превенция (П1–П6):
    Триггер сработал, если минимум у 4 из 6 растений зафиксирован ΔΔT >= +0.6°C.
    """
    valid_ddts = [val for val in prevention_plants_ddt if val is not None]
    triggered_count = sum(1 for val in valid_ddts if val >= threshold)
    total_measured = len(valid_ddts)
    is_triggered = triggered_count >= min_plants

    return {
        "is_triggered": is_triggered,
        "triggered_count": triggered_count,
        "total_measured": total_measured,
        "required_quorum": min_plants,
        "threshold_c": threshold,
        "status_text": (
            f"🚨 ТРИГГЕР ПРЕВЕНЦИИ СРАБОТАЛ ({triggered_count}/{min_plants} растений ≥ +{threshold}°C)"
            if is_triggered else
            f"✅ Норма когорты ({triggered_count}/{min_plants} превышений порога)"
        )
    }


# --- ПРАВИЛО №3: Лизиметрический контроль X0 и стандарты FAO-56 ---

def calc_substrate_evaporation(
    m_x0_prev: float,
    m_x0_curr: float
) -> float:
    """
    Правило №3 Тимирязевки: Расчет чистого физического испарения с поверхности субстрата по горшку X0.
    E_субстрат(t) = max(0.0, M_X0(t-1) - M_X0(t)) (г)
    Если масса X0 увеличилась (долив воды/тарирование), возвращается 0.0.
    """
    try:
        prev = float(m_x0_prev)
        curr = float(m_x0_curr)
    except (ValueError, TypeError):
        return 0.0
    return round(max(0.0, prev - curr), 2)


def calc_true_transpiration(
    m_plant_prev: float,
    m_plant_curr: float,
    e_substrate: float
) -> Dict[str, Any]:
    """
    Правило №3 Тимирязевки / стандарты FAO-56:
    Расчет истинной транспирации растения за период:
    ΔM_i = M_i(t-1) - M_i(t)
    T_ист,i(t) = ΔM_i - E_субстрат(t)

    Классификация состояния устьичного аппарата:
    - T_ист > 0.5 г: 'optimal' (Активная транспирация, устьица открыты)
    - 0.0 < T_ист <= 0.5 г: 'depressed' (Угнетение транспирации, начальный стресс)
    - T_ист <= 0.0 г: 'occluded' (Устьичная окклюзия / критический водный дефицит)
    """
    try:
        p_prev = float(m_plant_prev)
        p_curr = float(m_plant_curr)
        e_sub = max(0.0, float(e_substrate))
    except (ValueError, TypeError):
        return {
            "total_water_loss_g": 0.0,
            "substrate_evaporation_g": 0.0,
            "true_transpiration_g": 0.0,
            "stomatal_status": "unknown",
            "is_occluded": False
        }

    total_loss = round(max(0.0, p_prev - p_curr), 2)
    t_true = round(total_loss - e_sub, 2)

    if t_true > 0.5:
        status = "optimal"
        is_occluded = False
    elif t_true > 0.0:
        status = "depressed"
        is_occluded = False
    else:
        status = "occluded"
        is_occluded = True

    return {
        "total_water_loss_g": total_loss,
        "substrate_evaporation_g": e_sub,
        "true_transpiration_g": t_true,
        "stomatal_status": status,
        "is_occluded": is_occluded
    }


def calc_transpiration_intensity(
    t_true_g: float,
    pla_cm2: float,
    dt_hours: float = 24.0
) -> Optional[float]:
    """
    Расчет удельной интенсивности транспирации огурца на единицу площади листа:
    E_tr = (T_ист * 1000) / (PLA * dt) [мг / (см² · ч)]
    Возвращает None, если PLA <= 0 или dt_hours <= 0.
    """
    try:
        t_g = float(t_true_g)
        pla = float(pla_cm2)
        dt = float(dt_hours)
    except (ValueError, TypeError):
        return None

    if pla <= 0.0 or dt <= 0.0:
        return None

    # Перевод г -> мг: t_g * 1000
    e_tr = (t_g * 1000.0) / (pla * dt)
    return round(float(e_tr), 2)


def analyze_cohort_transpiration(
    cohort_data: List[Dict[str, Any]],
    e_substrate: float,
    dt_hours: float = 24.0
) -> Dict[str, Any]:
    """
    Статистический агрегатор транспирации по когорте (K, R, P или E):
    Принимает список словарей растений с ключами 'pot_id', 'm_prev', 'm_curr', 'pla'.
    """
    results = []
    t_true_vals = []
    intensities = []
    occluded_count = 0

    for item in cohort_data:
        pot_id = item.get('pot_id', '--')
        m_prev = item.get('m_prev', 0.0)
        m_curr = item.get('m_curr', 0.0)
        pla = item.get('pla', 0.0)

        tr_data = calc_true_transpiration(m_prev, m_curr, e_substrate)
        e_tr = calc_transpiration_intensity(tr_data["true_transpiration_g"], pla, dt_hours)
        tr_data["pot_id"] = pot_id
        tr_data["pla_cm2"] = pla
        tr_data["transpiration_intensity_mg_cm2_h"] = e_tr
        results.append(tr_data)

        t_true_vals.append(tr_data["true_transpiration_g"])
        if e_tr is not None:
            intensities.append(e_tr)
        if tr_data["is_occluded"]:
            occluded_count += 1

    n = len(results)
    mean_t_true = round(sum(t_true_vals) / n, 2) if n > 0 else 0.0
    mean_intensity = round(sum(intensities) / len(intensities), 2) if intensities else None

    return {
        "total_plants": n,
        "occluded_count": occluded_count,
        "occlusion_percent": round((occluded_count / n) * 100.0, 1) if n > 0 else 0.0,
        "mean_true_transpiration_g": mean_t_true,
        "mean_intensity_mg_cm2_h": mean_intensity,
        "plants": results
    }
