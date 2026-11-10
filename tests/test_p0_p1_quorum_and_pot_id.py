# -*- coding: utf-8 -*-
"""
Тесты обязательных фиксов P0.1 и P0.2:
- P0.1: Запрет полива и сохранения по неизвестному/пустому ID горшка (без fallback в Control),
  явная обработка исключений X0 и C20, кириллическая нормализация, отказ HTTP 400 на всех 6 POST-эндпоинтах Wave 2.
- P0.2: Синхронный кворум контрольного базиса K1–K6 (>= 4 из 6 валидных измерений одной даты),
  запрет принятия решения Превенцией при 0..3 из 6 или наличии NaN/'--'/рассинхрона без подмены пропусков,
  консистентность с docs/wave2/config_wave2.py и подневной группировкой в core/wave2_ui.py.
"""

import io
import math
import os
import pytest
from fastapi.testclient import TestClient

import core.wave2_ui as wave2_ui
import docs.wave2.config_wave2 as config_wave2
import web_station
from core.agronomic_rules import (
    CONTROL_BASELINE_MIN_QUORUM,
    evaluate_control_baseline_quorum,
)
from core.wave2_manager import (
    WAVE2_EXPERIMENT_META,
    Wave2Storage,
    evaluate_cohort_cluster_status,
    evaluate_pot_watering_with_projection,
    normalize_and_validate_pot_id,
    resolve_cohort_watering_decision,
)

client = TestClient(web_station.app)


def _make_day_records(
    k_values,
    p_dt=2.0,
    p_count=6,
    r_turgor=2,
    r_count=6,
    k_dates=None,
    p_date="2026-11-10 18:05:00",
    r_date="2026-11-10 18:10:00",
):
    """Формирует дневной срез замеров K1–K6, P1–P6, R1–R6 для тестов кворума."""
    records = []
    for idx, val in enumerate(k_values, start=1):
        ts = k_dates[idx - 1] if k_dates else f"2026-11-10 18:0{idx}:00"
        records.append({
            "Timestamp": ts,
            "ID": f"K{idx}",
            "Delta_T_C": val if val is not None else "--",
            "Turgor_Score": "4",
        })
    for idx in range(1, p_count + 1):
        records.append({
            "Timestamp": p_date,
            "ID": f"P{idx}",
            "Delta_T_C": str(p_dt),
            "Turgor_Score": "3",
        })
    for idx in range(1, r_count + 1):
        records.append({
            "Timestamp": r_date,
            "ID": f"R{idx}",
            "Delta_T_C": "1.0",
            "Turgor_Score": str(r_turgor),
        })
    return records


# ==============================================================================
# P0.1 — Валидация ID горшка и запрет полива по неизвестным/пустым ID
# ==============================================================================

def test_p01_known_cohorts_and_explicit_exceptions():
    """Известные горшки Control/Prevention/Reaction и явные исключения X0/C20 обрабатываются строго по каталогу."""
    # Готовый синхронный контроль (6/6) и сработавшие триггеры Превенции/Реакции
    recs = _make_day_records([0.0] * 6, p_dt=1.2, r_turgor=2)
    cluster_triggered = evaluate_cohort_cluster_status(recs)

    dec_k = resolve_cohort_watering_decision("K1", 12.0, cluster_triggered)
    assert dec_k["watering_allowed"] is True
    assert dec_k["reason"] == "optimum"
    assert dec_k["effective_dose"] == 12.0

    dec_p = resolve_cohort_watering_decision("P1", 15.0, cluster_triggered)
    assert dec_p["watering_allowed"] is True
    assert dec_p["reason"] == "triggered"
    assert dec_p["effective_dose"] == 15.0

    dec_r = resolve_cohort_watering_decision("R1", 18.0, cluster_triggered)
    assert dec_r["watering_allowed"] is True
    assert dec_r["reason"] == "triggered"
    assert dec_r["effective_dose"] == 18.0

    # При заблокированной Превенции P1 не получает воду, а Control, X0 и C20 — получают по своему регламенту
    recs_norm = _make_day_records([0.0] * 6, p_dt=0.1, r_turgor=4)
    cluster_blocked = evaluate_cohort_cluster_status(recs_norm)

    assert resolve_cohort_watering_decision("P1", 15.0, cluster_blocked)["watering_allowed"] is False
    assert resolve_cohort_watering_decision("R1", 15.0, cluster_blocked)["watering_allowed"] is False

    dec_x0 = resolve_cohort_watering_decision("X0", 7.5, cluster_blocked)
    assert dec_x0["watering_allowed"] is True
    assert dec_x0["reason"] == "lysimeter_x0"
    assert dec_x0["effective_dose"] == 7.5

    dec_c20 = resolve_cohort_watering_decision("C20", 9.0, cluster_blocked)
    assert dec_c20["watering_allowed"] is True
    assert dec_c20["reason"] == "satellite_c20"
    assert dec_c20["effective_dose"] == 9.0

    # Кириллические префиксы нормализуются в латиницу строго по каталогу
    assert normalize_and_validate_pot_id("к1") == "K1"
    assert normalize_and_validate_pot_id("п3") == "P3"
    assert normalize_and_validate_pot_id("р6") == "R6"
    assert normalize_and_validate_pot_id("х0") == "X0"
    assert normalize_and_validate_pot_id("с20") == "C20"


@pytest.mark.parametrize(
    "bad_pot_id",
    ["", "   ", None, False, True, "POT99", "K0", "K7", "K9", "P0", "P7", "R0", "R7", "X1", "C1", "C21", "UNKNOWN", "Контроль"],
)
def test_p01_unknown_and_empty_ids_never_allowed_watering(bad_pot_id):
    """Ни пустой ID, ни произвольная строка не классифицируются как Control и не получают разрешение на полив."""
    recs = _make_day_records([0.0] * 6, p_dt=1.5, r_turgor=1)
    cluster = evaluate_cohort_cluster_status(recs)

    assert normalize_and_validate_pot_id(bad_pot_id) is None

    dec = resolve_cohort_watering_decision(bad_pot_id, 25.0, cluster)
    assert dec["watering_allowed"] is False
    assert dec["reason"] == "unknown_pot_id"
    assert dec["effective_dose"] == 0.0

    dec_none_def = resolve_cohort_watering_decision(bad_pot_id, None, cluster)
    assert dec_none_def["watering_allowed"] is False
    assert dec_none_def["reason"] == "unknown_pot_id"
    assert dec_none_def["effective_dose"] is None

    proj_dec, _ = evaluate_pot_watering_with_projection(recs, bad_pot_id, {"Weight_g": "90.0"}, 10.0)
    assert proj_dec["watering_allowed"] is False
    assert proj_dec["reason"] == "unknown_pot_id"


@pytest.mark.parametrize("bad_pot_id", ["", "   ", "POT99", "K9", "X1", "C21", "ANY_STRING"])
def test_p01_wave2_endpoints_reject_invalid_pot_ids(monkeypatch, bad_pot_id):
    """Все 6 POST-эндпоинтов Wave 2 отклоняют неизвестные/пустые pot_id до вызова железа и записи в CSV."""
    hardware_calls = []

    def _fail_capture(pid):
        hardware_calls.append(("capture", pid))
        raise AssertionError(f"do_hardware_capture_wave2 вызван для невалидного ID {pid}")

    def _fail_grab(pid, images_dir):
        hardware_calls.append(("grab", pid))
        raise AssertionError(f"grab_latest_uti_thermal_image вызван для невалидного ID {pid}")

    monkeypatch.setattr(web_station, "do_hardware_capture_wave2", _fail_capture)
    monkeypatch.setattr(web_station, "grab_latest_uti_thermal_image", _fail_grab)

    r1 = client.post("/api/wave2/capture_and_save", data={"pot_id": bad_pot_id, "weight_g": "95.0"})
    assert r1.status_code == 400
    assert r1.json()["watering_allowed"] is False

    r2 = client.post("/api/wave2/update_record", data={"pot_id": bad_pot_id, "weight_g": "95.0"})
    assert r2.status_code == 400
    assert r2.json()["watering_allowed"] is False

    r3 = client.post("/api/wave2/delete_record", data={"pot_id": bad_pot_id})
    assert r3.status_code == 400
    assert r3.json()["watering_allowed"] is False

    r4 = client.post("/api/wave2/uti_import_file", data={"pot_id": bad_pot_id, "filename": "IR_test.bmp"})
    assert r4.status_code == 400
    assert r4.json()["watering_allowed"] is False

    r5 = client.post("/api/wave2/grab_uti_thermal", data={"pot_id": bad_pot_id})
    assert r5.status_code == 400
    assert r5.json()["watering_allowed"] is False

    r6 = client.post(
        "/api/wave2/upload_thermal",
        data={"pot_id": bad_pot_id},
        files={"thermal_file": ("bad.jpg", io.BytesIO(b"\xff\xd8\xff\xd9"), "image/jpeg")},
    )
    assert r6.status_code == 400
    assert r6.json()["watering_allowed"] is False

    assert hardware_calls == []
    assert Wave2Storage(web_station.DATA_DIR).load_all_records() == []


@pytest.mark.parametrize("special_id", ["X0", "C20", "х0", "с20"])
def test_p01_capture_and_save_accepts_x0_c20_explicitly(monkeypatch, special_id):
    """capture_and_save явно принимает исключения X0 и C20 и нормализует кириллицу."""
    monkeypatch.setattr(
        web_station,
        "do_hardware_capture_wave2",
        lambda pid: (f"{pid}_20261110_180000_annotated.jpg", {"ndvi_mean": 0.5, "ndvi_std": 0.02, "pla_cm2": 0.0}),
    )

    class _ClimateOk:
        async def read_climate(self):
            return 24.0, 50.0, 3.30

    monkeypatch.setattr(web_station, "get_climate_sensor", lambda: _ClimateOk())
    monkeypatch.setattr(web_station, "get_windowsill_climate", lambda: {"is_live": False})

    res = client.post(
        "/api/wave2/capture_and_save",
        data={"pot_id": special_id, "weight_g": "95.0", "turgor_score": ""},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["watering_allowed"] is True
    assert payload["raw_deficit_ml"] == 5.0
    assert payload["dose"] == "5.0 мл"
    expected_reason = "lysimeter_x0" if payload["pot_id"] == "X0" else "satellite_c20"
    assert payload["watering_reason"] == expected_reason


# ==============================================================================
# P0.2 — Кворум контрольного базиса (>= 4/6) и запрет несинхронных/неполных решений
# ==============================================================================

def test_p02_quorum_constant_is_documented_and_consistent():
    """Минимум 4/6 зафиксирован и в ergonomic rules, и в метаданных Wave 2."""
    assert CONTROL_BASELINE_MIN_QUORUM == 4
    assert WAVE2_EXPERIMENT_META["control_baseline_min_quorum"] == 4
    assert config_wave2.EXPERIMENT_META["control_baseline_min_quorum"] == 4


@pytest.mark.parametrize("valid_k_count", [0, 1, 2, 3])
def test_p02_insufficient_control_baseline_blocks_prevention(valid_k_count):
    """0/6, 1/6, 2/6, 3/6 замеров Контроля (включая ранее допускавшийся 1/6) блокируют Превенцию."""
    k_vals = [0.2] * valid_k_count + [None] * (6 - valid_k_count)
    records = _make_day_records(k_vals, p_dt=2.5)  # ΔΔT был бы +2.3°C >= +0.6°C, но базис неполный!

    status = evaluate_cohort_cluster_status(records)
    prev = status["prevention"]
    assert prev["control_measured_count"] == valid_k_count
    assert prev["control_required_quorum"] == 4
    assert prev["control_baseline_ready"] is False
    assert prev["mean_control_dt"] is None
    assert prev["dates_synchronized"] is True
    assert prev["triggered"] is False
    assert prev["insufficient_data"] is True

    decision = resolve_cohort_watering_decision("P1", 12.0, status)
    assert decision["watering_allowed"] is False
    assert decision["reason"] == "insufficient_data"

    # config_wave2 возвращает идентичный статус готовности базиса
    daily_cfg = {f"K{i}": {"delta_t": val} for i, val in enumerate(k_vals, start=1) if val is not None}
    for i in range(1, 7):
        daily_cfg[f"P{i}"] = {"delta_t": 2.5}
    cfg_res = config_wave2.evaluate_cluster_triggers(daily_cfg)
    assert cfg_res["control_baseline_ready"] is False
    assert cfg_res["control_measured_count"] == valid_k_count
    assert cfg_res["mean_control_delta_t"] is None
    assert cfg_res["prevention_triggered"] is False


@pytest.mark.parametrize("valid_k_count", [4, 5, 6])
def test_p02_sufficient_control_quorum_enables_prevention(valid_k_count):
    """При 4/6, 5/6 и 6/6 валидных синхронных замерах Контроля базис готов и триггер Превенции работает."""
    k_dts = [0.2 + 0.1 * i for i in range(valid_k_count)]
    expected_mean = round(sum(k_dts) / valid_k_count, 2)
    k_vals = k_dts + [None] * (6 - valid_k_count)
    records = _make_day_records(k_vals, p_dt=expected_mean + 0.7)

    status = evaluate_cohort_cluster_status(records)
    prev = status["prevention"]
    assert prev["control_baseline_ready"] is True
    assert prev["control_measured_count"] == valid_k_count
    assert prev["mean_control_dt"] == expected_mean
    assert prev["dates_synchronized"] is True
    assert prev["triggered"] is True
    assert prev["insufficient_data"] is False

    decision = resolve_cohort_watering_decision("P1", 14.0, status)
    assert decision["watering_allowed"] is True
    assert decision["reason"] == "triggered"
    assert decision["effective_dose"] == 14.0

    # Паритет с docs/wave2/config_wave2.py
    daily_cfg = {f"K{i}": {"delta_t": k_dts[i - 1]} for i in range(1, valid_k_count + 1)}
    for i in range(1, 7):
        daily_cfg[f"P{i}"] = {"delta_t": expected_mean + 0.7}
    cfg_res = config_wave2.evaluate_cluster_triggers(daily_cfg)
    assert cfg_res["control_baseline_ready"] is True
    assert cfg_res["control_measured_count"] == valid_k_count
    assert cfg_res["mean_control_delta_t"] == expected_mean
    assert cfg_res["prevention_triggered"] is True


def test_p02_na_and_missing_markers_never_imputed():
    """None, '', '--', 'NA', 'NaN', math.nan, bool не заменяются нулями или средними."""
    q_res = evaluate_control_baseline_quorum([0.5, 0.5, 0.5, None, "", "--", "NA", "NaN", float("nan"), True, False])
    assert q_res["measured_count"] == 3
    assert q_res["ready"] is False
    assert q_res["mean_control_dt"] is None

    records = _make_day_records(["0.1", "0.2", "0.3", "--", "NaN", "NA"], p_dt=2.0)
    status = evaluate_cohort_cluster_status(records)
    assert status["prevention"]["control_measured_count"] == 3
    assert status["prevention"]["control_baseline_ready"] is False
    assert status["prevention"]["mean_control_dt"] is None
    assert status["prevention"]["triggered"] is False


def test_p02_desynchronized_control_and_prevention_dates_blocked():
    """Рассинхронизированные замеры (K вчера / P сегодня или разные даты внутри K) блокируют расчёт ΔΔT."""
    # Сценарий 1: все 6 K1–K6 сняты 2026-11-09, а P1–P6 сняты 2026-11-10
    records_diff_days = _make_day_records(
        [0.0] * 6,
        p_dt=2.5,
        k_dates=[f"2026-11-09 18:0{i}:00" for i in range(1, 7)],
        p_date="2026-11-10 18:05:00",
    )
    st1 = evaluate_cohort_cluster_status(records_diff_days)
    assert st1["prevention"]["dates_synchronized"] is False
    assert st1["prevention"]["control_baseline_ready"] is False
    assert st1["prevention"]["mean_control_dt"] is None
    assert st1["prevention"]["triggered"] is False
    assert resolve_cohort_watering_decision("P1", 10.0, st1)["watering_allowed"] is False

    # Сценарий 2: внутри K часть снята 2026-11-09, часть 2026-11-10
    records_mixed_k = _make_day_records(
        [0.0] * 6,
        p_dt=2.5,
        k_dates=["2026-11-09 18:01:00"] * 3 + ["2026-11-10 18:01:00"] * 3,
        p_date="2026-11-10 18:05:00",
    )
    st2 = evaluate_cohort_cluster_status(records_mixed_k)
    assert st2["prevention"]["dates_synchronized"] is False
    assert st2["prevention"]["control_baseline_ready"] is False
    assert st2["prevention"]["triggered"] is False


def test_p02_ui_table_groups_day1_records_by_calendar_day():
    """Таблица Wave 2 группирует замеры одного дня по дате YYYY-MM-DD, а не посекундно."""
    records = _make_day_records([0.0] * 6, p_dt=1.5, r_turgor=4)
    for idx, rec in enumerate(records, start=1):
        rec["Timestamp"] = f"2026-11-10 18:{idx:02d}:{(idx * 7) % 60:02d}"
        rec["Weight_g"] = "90.0"

    html = wave2_ui.render_wave2_measurements_table(records)
    # P1 получает статус разрешённого полива (10.0 мл), так как вся когорта того же дня синхронна
    assert '<tr id="row_P1"' in html
    assert 'data-watering="allowed"' in html
    # Убеждаемся, что для строки P1 не выведена блокировка "Ожидание замера когорты"
    p1_section = html.split('<tr id="row_P1"')[1].split("</tr>")[0]
    assert 'data-watering="allowed"' in p1_section
    assert "10.0" in p1_section
