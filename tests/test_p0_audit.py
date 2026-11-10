# -*- coding: utf-8 -*-
"""
Тесты критического этапа P0 (Задачи 1, 2, 3 технического аудита):
1. Исправленная (<= 2) и единая логика триггера «Реакция».
2. Отсутствие подстановки тургора = 4 при пропусках в backend, ANOVA и таблице UI
   (при сохранении предвыбора '4' в селекте активной карточки съемки по регламенту оператора).
3. Интеграционная цепочка: web_station -> wave2_manager -> wave2_ui -> решение о поливе.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import web_station
from core.agronomic_rules import (
    parse_optional_turgor,
    evaluate_cohort_reaction_trigger,
    evaluate_cohort_prevention_trigger,
)
from core.wave2_manager import (
    evaluate_cohort_cluster_status,
    resolve_cohort_watering_decision,
    Wave2Storage,
)
from core.wave2_ui import (
    render_wave2_cluster_banner,
    render_wave2_active_pot_card,
    render_wave2_measurements_table,
)
from core.wave2_anova import analyze_wave2_dataset

client = TestClient(web_station.app)


# ------------------------------------------------------------------------------
# ЗАДАЧА 1: Логика триггера «Реакция» (<= 2) и единый путь классификации
# ------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scores,expected_triggered,expected_insufficient,expected_count",
    [
        ([4, 4, 4, 4, 4, 4], False, False, 0),
        ([2, 2, 2, 2, 4, 4], True, False, 4),
        ([2, 2, 2, 4, 4, 4], False, False, 3),
        ([1, 2, 1, 2, 3, 4], True, False, 4),
        ([2, 2, 4, None, None, None], False, True, 2),
        (["4", "4", "--", "", None, "NaN"], False, True, 0),
    ],
)
def test_task1_reaction_trigger_canonical_and_manager_consistency(
    scores, expected_triggered, expected_insufficient, expected_count
):
    """Проверка обязательных комбинаций оценок тургора в agronomic_rules и wave2_manager."""
    rule_res = evaluate_cohort_reaction_trigger(scores)
    assert rule_res["is_triggered"] is expected_triggered
    assert rule_res["is_insufficient"] is expected_insufficient
    assert rule_res["triggered_count"] == expected_count

    records = []
    for idx, val in enumerate(scores, start=1):
        records.append({"ID": f"R{idx}", "Turgor_Score": val if val is not None else "--"})
    mgr_res = evaluate_cohort_cluster_status(records)["reaction"]

    assert mgr_res["triggered"] is expected_triggered
    assert mgr_res["insufficient_data"] is expected_insufficient
    assert mgr_res["stressed_count"] == expected_count
    if expected_insufficient:
        assert "Недостаточно данных" in mgr_res["status_text"]


def test_task1_missing_pot_records_return_insufficient_data():
    """Если измерено < 6 горшков Реакции и кворум 4 не набран — отдельный статус."""
    records = [
        {"ID": "R1", "Turgor_Score": "4"},
        {"ID": "R2", "Turgor_Score": "2"},
        {"ID": "R3", "Turgor_Score": "4"},
    ]
    res = evaluate_cohort_cluster_status(records)
    assert res["reaction"]["triggered"] is False
    assert res["reaction"]["insufficient_data"] is True
    assert res["reaction"]["measured_count"] == 3
    assert res["reaction"]["state"] == "insufficient_data"
    assert "Недостаточно данных" in res["reaction"]["status_text"]


# ------------------------------------------------------------------------------
# ЗАДАЧА 2: Запрет подстановки тургора = 4 для пропущенных измерений
# ------------------------------------------------------------------------------

@pytest.mark.parametrize("raw_val", [None, "", "  ", "--", "nan", "NaN", "None", "null", "0", "5", "abc"])
def test_task2_parse_optional_turgor_returns_none_for_missing(raw_val):
    assert parse_optional_turgor(raw_val) is None


def test_task2_anova_preserves_nan_and_ignores_missing_turgor(tmp_path):
    """Пустые/пропущенные оценки тургора в ANOVA не превращаются в 4 и не запускают реакцию."""
    records = []
    for pid in [f"K{i}" for i in range(1, 7)] + [f"P{i}" for i in range(1, 7)] + [f"R{i}" for i in range(1, 7)]:
        records.append({
            "ID": pid,
            "Weight_g": "98.0",
            "Delta_T_C": "0.1",
            "NDVI_Mean": "0.600",
            "Leaf_Area_cm2": "10.0",
            "Turgor_Score": "--",
        })
    res = analyze_wave2_dataset(records, static_dir=str(tmp_path / "st"), docs_dir=str(tmp_path / "dc"))
    assert res["ok"] is True
    assert res["phase"] == "incomplete_turgor"
    assert res["phase"] != "reaction_trigger"
    turgor_row = next(r for r in res["summary_table"] if r["trait"] == "turgor")
    assert turgor_row["k_str"] == "--"
    assert turgor_row["p_str"] == "--"
    assert turgor_row["r_str"] == "--"
    turgor_stats = res["traits"]["turgor"]
    assert turgor_stats["k_mean"] is None
    assert turgor_stats["p_mean"] is None
    assert turgor_stats["r_mean"] is None


def test_task2_anova_partial_turgor_excludes_missing_from_mean(tmp_path):
    """Частично заполненный тургор (одна 2, один пропуск) дает среднее 2.0, а не (2+4)/2=3.0."""
    records = []
    for i in range(1, 7):
        records.append({"ID": f"K{i}", "Weight_g": "100.0", "Delta_T_C": "-1.0", "NDVI_Mean": "0.6", "Leaf_Area_cm2": "10.0", "Turgor_Score": "4"})
        records.append({"ID": f"P{i}", "Weight_g": "99.0", "Delta_T_C": "-0.8", "NDVI_Mean": "0.6", "Leaf_Area_cm2": "10.0", "Turgor_Score": "4"})
        records.append({
            "ID": f"R{i}",
            "Weight_g": "99.0",
            "Delta_T_C": "-0.8",
            "NDVI_Mean": "0.6",
            "Leaf_Area_cm2": "10.0",
            "Turgor_Score": "2" if i == 1 else "--",
        })
    res = analyze_wave2_dataset(records, static_dir=str(tmp_path / "st"), docs_dir=str(tmp_path / "dc"))
    turgor_stats = res["traits"]["turgor"]
    assert turgor_stats["r_mean"] == 2.0
    assert res["phase"] != "reaction_trigger"


def test_task2_ui_card_defaults_4_while_table_preserves_missing():
    """
    По решению пользователя селект активной карточки предвыбирает '4',
    но таблица журнала сохраняет '--' для пустых строк (не подменяя их на 4).
    """
    records = [{"ID": "R1", "Timestamp": "2026-11-10", "Weight_g": "95.0", "Turgor_Score": "--"}]
    card_html = render_wave2_active_pot_card("R1", records, {"t_c": 24.0, "rh_pct": 50.0, "cur_v": None})
    assert '<option value="4" selected>' in card_html

    table_html = render_wave2_measurements_table(records)
    assert '<option value="--" selected>' in table_html
    assert "ПОЛИВ ЗАБЛОКИРОВАН" in table_html or "БЛОК (недостаточно данных)" in table_html


# ------------------------------------------------------------------------------
# ЗАДАЧА 3: Интеграционные тесты активного пути
# web_station.py -> core/wave2_manager.py -> core/wave2_ui.py -> Решение о поливе
# ------------------------------------------------------------------------------

@pytest.fixture
def mock_capture_hw(monkeypatch, tmp_path):
    """Подменяет аппаратную камеру и I2C-датчик при вызове /api/wave2/capture_and_save."""
    def _fake_capture(pot_id: str):
        return f"{pot_id}_20261110_120000_annotated.jpg", {
            "ndvi_mean": 0.612,
            "ndvi_std": 0.045,
            "pla_cm2": 18.4,
            "aruco_detected": False,
        }

    class _DummyClimate:
        async def read_climate(self):
            return 24.0, 52.0, 1.15

    monkeypatch.setattr(web_station, "do_hardware_capture_wave2", _fake_capture)
    monkeypatch.setattr(web_station, "get_climate_sensor", lambda: _DummyClimate())


def test_task2_and_3_capture_without_turgor_stores_missing_not_4(mock_capture_hw):
    """Вызов capture_and_save без turgor_score оставляет '--' в CSV, не 4."""
    res = client.post("/api/wave2/capture_and_save", data={"pot_id": "R1", "weight_g": "95.0", "t_leaf": "23.5"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["turgor_score"] is None
    assert payload["watering_allowed"] is False

    recs = Wave2Storage(web_station.DATA_DIR).load_today_records()
    r1 = next(r for r in recs if r["ID"] == "R1")
    assert r1["Turgor_Score"] == "--"
    assert r1["Water_Dose_ml"] == "0.0"

    # Обновление массы без передачи turgor_score не должно превращать '--' в 4
    up = client.post("/api/wave2/update_record", data={"pot_id": "R1", "weight_g": "94.0"})
    assert up.status_code == 200
    up_json = up.json()
    assert up_json["turgor_score"] is None
    assert up_json["watering_allowed"] is False

    recs_after = Wave2Storage(web_station.DATA_DIR).load_today_records()
    r1_after = next(r for r in recs_after if r["ID"] == "R1")
    assert r1_after["Turgor_Score"] == "--"


def test_task3_end_to_end_pipeline_turgor_trigger_and_blocking(mock_capture_hw):
    """
    Сквозной сценарий:
    1) Здоровые Контроль (92.5 г), Превенция (dT <= К), Реакция (балл 4):
       Контролю разрешен полив (7.5 мл), Превенция и Реакция заблокированы.
    2) Реакция с баллами 2,2,2,4,4,4: кворум не набран (3/6), полив заблокирован.
    3) Изменение Р4 на балл 2 (2,2,2,2,4,4): срабатывает триггер 4/6, полив Реакции открывается.
    """
    client.get("/?set_exp=exp_1792918800")

    for i in range(1, 7):
        res_k = client.post("/api/wave2/capture_and_save", data={
            "pot_id": f"K{i}", "weight_g": "92.5", "t_leaf": "23.0", "t_air": "24.0", "turgor_score": "4"
        })
        assert res_k.status_code == 200
        assert res_k.json()["watering_allowed"] is True
        assert "7.5 мл" in res_k.json()["dose"]

    for i in range(1, 7):
        res_p = client.post("/api/wave2/capture_and_save", data={
            "pot_id": f"P{i}", "weight_g": "93.0", "t_leaf": "23.0", "t_air": "24.0", "turgor_score": "4"
        })
        assert res_p.status_code == 200
        assert res_p.json()["watering_allowed"] is False

    # Сначала 3 растения Реакции с баллом 2 и 3 с баллом 4 -> не срабатывает!
    for i in range(1, 7):
        sc = "2" if i <= 3 else "4"
        res_r = client.post("/api/wave2/capture_and_save", data={
            "pot_id": f"R{i}", "weight_g": "93.0", "t_leaf": "23.5", "t_air": "24.0", "turgor_score": sc
        })
        assert res_r.status_code == 200
        rj = res_r.json()
        assert rj["watering_allowed"] is False
        assert rj["cluster_status"]["reaction"]["triggered"] is False

    dash_blocked = client.get("/?stage=wave2&pot=R4")
    assert dash_blocked.status_code == 200
    html_blocked = dash_blocked.text
    assert "Увяло: 3/6" in html_blocked
    assert "Тургор в норме (3/6) — Полив заблокирован" in html_blocked
    assert "ПОЛИВ ЗАБЛОКИРОВАН" in html_blocked

    # Понижаем тургор R4 с 4 до 2 -> 2,2,2,2,4,4 -> триггер срабатывает (4/6)!
    res_trig = client.post("/api/wave2/update_record", data={"pot_id": "R4", "turgor_score": "2"})
    assert res_trig.status_code == 200
    trig_json = res_trig.json()
    assert trig_json["cluster_status"]["reaction"]["triggered"] is True
    assert trig_json["cluster_status"]["reaction"]["stressed_count"] == 4
    assert trig_json["watering_allowed"] is True
    assert "7.0 мл" in trig_json["dose"]
    assert trig_json["cluster_status"]["prevention"]["triggered"] is False

    dash_open = client.get("/?stage=wave2&pot=R4")
    assert dash_open.status_code == 200
    html_open = dash_open.text
    assert "Увяло: 4/6" in html_open
    assert "УВЯДАНИЕ (4/6) — РЕАНИМАЦИОННЫЙ ПОЛИВ ВОДОЙ!" in html_open
    assert "7.0 мл" in html_open

    # А вот ANOVA не подменяет данные и тоже видит реакцию по 4 увядшим
    today_recs = Wave2Storage(web_station.DATA_DIR).load_today_records()
    assert len(today_recs) == 18
    # Превенция при этом всё ещё заблокирована
    assert evaluate_cohort_cluster_status(today_recs)["prevention"]["triggered"] is False


def test_task3_missing_control_baseline_blocks_prevention_trigger(mock_capture_hw):
    """
    P0.3: Отсутствие контрольных температур K1-K6 не допускает перехода на
    неподтвержденный абсолютный порог ΔT >= +0.6°C и блокирует полив Превенции.
    """
    from docs.wave2.config_wave2 import evaluate_cluster_triggers

    # 1. Записываем P1-P6 с высоким сырым ΔT = +2.5°C без единого замера K1-K6
    for i in range(1, 7):
        res_p = client.post("/api/wave2/capture_and_save", data={
            "pot_id": f"P{i}",
            "weight_g": "90.0",
            "t_leaf": "26.5",
            "t_air": "24.0",
            "turgor_score": "4",
        })
        assert res_p.status_code == 200
        pj = res_p.json()
        assert pj["watering_allowed"] is False
        assert pj["cluster_status"]["prevention"]["triggered"] is False
        assert pj["cluster_status"]["prevention"]["insufficient_data"] is True
        assert pj["cluster_status"]["prevention"]["control_baseline_ready"] is False
        assert pj["cluster_status"]["prevention"]["stressed_count"] == 0
        assert "Нет контрольного базиса K1–K6" in pj["cluster_status"]["prevention"]["status_text"]

    # То же для K1-K6 с пустой температурой листа (Delta_T_C == "--")
    for i in range(1, 7):
        res_k = client.post("/api/wave2/capture_and_save", data={
            "pot_id": f"K{i}",
            "weight_g": "95.0",
            "t_air": "24.0",
            "turgor_score": "4",
        })
        assert res_k.status_code == 200
        assert res_k.json()["cluster_status"]["prevention"]["triggered"] is False
        assert res_k.json()["cluster_status"]["prevention"]["control_baseline_ready"] is False

    # Проверка helper-функции docs/wave2/config_wave2.py при пустом контроле
    cfg_res = evaluate_cluster_triggers({f"P{i}": {"delta_t": 2.5, "turgor": 4} for i in range(1, 7)})
    assert cfg_res["control_baseline_ready"] is False
    assert cfg_res["mean_control_delta_t"] is None
    assert cfg_res["prevention_triggered"] is False

    # 2. Если у K1-K6 ΔT = +2.0°C (теплый день), то ΔΔT = +0.5 < +0.6 -> полив всё ещё заблокирован
    for i in range(1, 7):
        res_k = client.post("/api/wave2/update_record", data={
            "pot_id": f"K{i}",
            "t_leaf": "26.0",
            "t_air": "24.0",
        })
        assert res_k.status_code == 200
    up_p1_blocked = client.post("/api/wave2/update_record", data={"pot_id": "P1", "weight_g": "90.0"})
    assert up_p1_blocked.status_code == 200
    assert up_p1_blocked.json()["cluster_status"]["prevention"]["control_baseline_ready"] is True
    assert up_p1_blocked.json()["cluster_status"]["prevention"]["triggered"] is False
    assert up_p1_blocked.json()["watering_allowed"] is False

    # 3. Если контроль прохладный (ΔT = -1.0°C), то ΔΔT = +3.5 >= +0.6 -> триггер срабатывает!
    for i in range(1, 7):
        res_k = client.post("/api/wave2/update_record", data={
            "pot_id": f"K{i}",
            "t_leaf": "23.0",
            "t_air": "24.0",
        })
        assert res_k.status_code == 200
    up_p1_open = client.post("/api/wave2/update_record", data={"pot_id": "P1", "weight_g": "90.0"})
    assert up_p1_open.status_code == 200
    assert up_p1_open.json()["cluster_status"]["prevention"]["triggered"] is True
    assert up_p1_open.json()["watering_allowed"] is True
    assert "10.0 мл" in up_p1_open.json()["dose"]


@pytest.mark.parametrize("bad_turgor", ["abc", "0", "9", "nan"])
def test_task3_e2e_invalid_turgor_strings_do_not_coerce_to_4(mock_capture_hw, bad_turgor):
    """P0.3: Нечисловые и некорректные строки Turgor_Score на веб-эндпоинтах сохраняются как '--'."""
    res = client.post("/api/wave2/capture_and_save", data={
        "pot_id": "R1",
        "weight_g": "95.0",
        "t_leaf": "23.5",
        "turgor_score": bad_turgor,
    })
    assert res.status_code == 200
    assert res.json()["turgor_score"] is None
    assert res.json()["watering_allowed"] is False

    up = client.post("/api/wave2/update_record", data={
        "pot_id": "R1",
        "turgor_score": bad_turgor,
    })
    assert up.status_code == 200
    assert up.json()["turgor_score"] is None

    recs = Wave2Storage(web_station.DATA_DIR).load_today_records()
    r1 = next(r for r in recs if r["ID"] == "R1")
    assert r1["Turgor_Score"] == "--"
