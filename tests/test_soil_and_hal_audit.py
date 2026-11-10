# -*- coding: utf-8 -*-
"""
Тесты исправления почвенного канала ADS1115 и удаления тихих синтетических заглушек (Point 2):
- web_station / wave2_ui не записывают напряжение шины климата (3.30 В) как Moisture_V / Moisture_Pct
- K1, P1, R1 (has_probe=True) опрашивают get_soil_sensor().read_moisture(..., allow_all_cohorts=True)
- Горшки без датчика и неподключенный АЦП возвращают '--' без утечки предыдущего горшка (_LAST_VALID_SOIL)
- RealSHT30 / RealADS1115 / calc_vpd / _read_climate_sync не подставляют синтетические константы при сбое
- api/routes/measurements.py удаляет Opt_File / Thermal_File по заголовку и использует V_DRY/V_WET
"""

import csv
import io
import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import core.wave2_ui as wave2_ui
import hardware.hal as hal
import web_station
from core.wave2_manager import Wave2Storage
from src.config import V_DRY, V_WET
from src.sensors_ads1115 import SoilMoistureReader

client = TestClient(web_station.app)


@pytest.mark.parametrize("pot_id", ["K1", "P1", "R1"])
def test_wave2_capture_uses_soil_sensor_not_climate_cur_v(monkeypatch, pot_id):
    """Для горшков с датчиком (K1, P1, R1) в CSV пишется ADS1115, а не 3.30 В от SHT30."""
    def _fake_capture(pid: str):
        return f"{pid}_20261110_180000_annotated.jpg", {
            "ndvi_mean": 0.62,
            "ndvi_std": 0.04,
            "pla_cm2": 14.2,
            "aruco_detected": False,
        }

    class _Climate330:
        async def read_climate(self):
            return 24.5, 55.0, 3.30

    seen_calls = []

    class _SoilADC:
        async def read_moisture(self, group_name: str = "", allow_all_cohorts: bool = False):
            seen_calls.append((group_name, allow_all_cohorts))
            return 1.968, 70.0

    monkeypatch.setattr(web_station, "do_hardware_capture_wave2", _fake_capture)
    monkeypatch.setattr(web_station, "get_climate_sensor", lambda: _Climate330())
    monkeypatch.setattr(web_station, "get_soil_sensor", lambda: _SoilADC())
    monkeypatch.setattr(web_station, "get_windowsill_climate", lambda: {"is_live": False})

    res = client.post(
        "/api/wave2/capture_and_save",
        data={"pot_id": pot_id, "weight_g": "95.0", "t_leaf": "23.0", "turgor_score": "4"},
    )
    assert res.status_code == 200
    assert seen_calls and seen_calls[0][1] is True

    recs = Wave2Storage(web_station.DATA_DIR).load_today_records()
    rec = next(r for r in recs if r["ID"] == pot_id)
    assert rec["Moisture_V"] == "1.968"
    assert rec["Moisture_Pct"] == "70.0"
    assert rec["Moisture_V"] != "3.3"


@pytest.mark.parametrize("pot_id,soil_ret", [("K1", (None, None)), ("P1", (None, None)), ("K2", (1.95, 81.9))])
def test_wave2_capture_disconnected_or_no_probe_writes_dashes(monkeypatch, pot_id, soil_ret):
    """При отключенном датчике или горшке без датчика пишутся '--', а не 64.0% / 3.30 В."""
    monkeypatch.setattr(
        web_station,
        "do_hardware_capture_wave2",
        lambda pid: (f"{pid}_20261110_180000_annotated.jpg", {"ndvi_mean": 0.6, "ndvi_std": 0.03, "pla_cm2": 10.0}),
    )

    class _Climate330:
        async def read_climate(self):
            return 24.5, 55.0, 3.30

    called = []

    class _SoilSensor:
        async def read_moisture(self, group_name: str = "", allow_all_cohorts: bool = False):
            called.append(True)
            return soil_ret

    monkeypatch.setattr(web_station, "get_climate_sensor", lambda: _Climate330())
    monkeypatch.setattr(web_station, "get_soil_sensor", lambda: _SoilSensor())
    monkeypatch.setattr(web_station, "get_windowsill_climate", lambda: {"is_live": False})

    res = client.post(
        "/api/wave2/capture_and_save",
        data={"pot_id": pot_id, "weight_g": "96.0", "t_leaf": "23.0", "turgor_score": "4"},
    )
    assert res.status_code == 200
    if pot_id == "K2":
        assert called == []

    recs = Wave2Storage(web_station.DATA_DIR).load_today_records()
    rec = next(r for r in recs if r["ID"] == pot_id)
    assert rec["Moisture_V"] == "--"
    assert rec["Moisture_Pct"] == "--"


def test_soil_reader_no_cross_pot_carryover_and_allow_all_cohorts(monkeypatch):
    """Отсоединенный датчик на следующем горшке не наследует предыдущее показание _LAST_VALID_SOIL."""
    reader = SoilMoistureReader()

    monkeypatch.setattr(reader, "read_channels", lambda: {"A0": {"voltage_V": 1.968, "moisture_percent": 70.0}})
    assert reader.get_active_moisture("🟡 Превенция", allow_all_cohorts=False) == (None, None)
    assert reader.get_active_moisture("🟡 Превенция", allow_all_cohorts=True) == (1.968, 70.0)
    assert reader.get_active_moisture("Контроль") == (1.968, 70.0)

    # Следующий горшок с выдернутым/закороченным к GND разъемом не должен получить 70.0%
    monkeypatch.setattr(reader, "read_channels", lambda: {"A0": {"voltage_V": 0.0, "moisture_percent": 0.0}})
    assert reader.get_active_moisture("Реакция", allow_all_cohorts=True) == (None, None)


def test_hal_and_climate_no_synthetic_fallbacks_on_failure(monkeypatch):
    """RealSHT30 / RealADS1115 / MockADS1115 / calc_vpd не возвращают фиктивных чисел при сбое."""
    with patch.dict(sys.modules, {"smbus2": None}):
        assert hal.RealSHT30()._read_sync() == (None, None, None)

    def _boom(*args, **kwargs):
        raise OSError("I2C offline")

    import asyncio
    monkeypatch.setattr("src.sensors_ads1115.SoilMoistureReader", _boom)
    assert hal.RealADS1115()._read_sync("Контроль", allow_all_cohorts=True) == (None, None)
    assert asyncio.run(hal.MockADS1115().read_moisture("Контроль", allow_all_cohorts=True)) == (None, None)

    monkeypatch.setattr(web_station, "get_windowsill_climate", lambda: {"is_live": False})
    monkeypatch.setattr("core.xiaomi_climate.get_windowsill_climate", lambda *a, **kw: {"is_live": False})
    with patch.dict(sys.modules, {"smbus2": None}):
        assert web_station._read_climate_sync() == (None, None, None)

    assert web_station.calc_vpd(None, 55.0) is None
    assert web_station.calc_vpd(24.0, None) is None


def test_wave2_ui_card_never_converts_cur_v_to_soil_and_handles_none_tair():
    """Карточка UI показывает реальный soil_v/soil_pct и не падает при t_air=None."""
    html_missing = wave2_ui.render_wave2_active_pot_card(
        "K1", [], {"t_c": None, "rh_pct": None, "cur_v": 3.30, "soil_v": None, "soil_pct": None}
    )
    assert "3.30В" not in html_missing
    assert "нет сигнала" in html_missing
    assert "const tAir = null;" in html_missing

    html_live = wave2_ui.render_wave2_active_pot_card(
        "P1", [], {"t_c": 23.5, "rh_pct": 54.0, "cur_v": 3.30, "soil_v": 1.968, "soil_pct": 70.0}
    )
    assert "70.0% (1.968В)" in html_live
    assert "3.30В" not in html_live


def test_measurements_routes_header_delete_and_calibrated_soil_update(tmp_path):
    """Удаление и обновление в api/routes/measurements.py не бьют индексы колонок и используют V_DRY/V_WET."""
    static_dir = web_station.STATIC_DIR
    opt_file = os.path.join(static_dir, "opt_test_99.jpg")
    th_file = os.path.join(static_dir, "th_test_99.jpg")
    with open(opt_file, "wb") as f:
        f.write(b"opt")
    with open(th_file, "wb") as f:
        f.write(b"th")

    row_70 = client.get("/?set_exp=exp_1791463544")
    assert row_70.status_code == 200

    # Записываем строку в активный CSV exp_1791463544
    from core.experiments import CSV_HEADER, get_experiment_manager
    csv_path = get_experiment_manager(web_station.DATA_DIR).get_active_csv_path()
    row = ["99", "2026-10-15 18:00", "Контроль", "95.0", "24.0", "55.0", "1.968", "70.0", "22.5", "-1.5", "1.34", "0.65", "0.05", "12.0", "opt_test_99.jpg", "th_test_99.jpg"] + ["--"] * 9
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerow(row)

    # Проверяем пересчет напряжения почвы по откалиброванным V_DRY/V_WET
    up_res = client.post("/api/update_measurement", data={"meas_id": "99", "pct_soil": "50.0"}, follow_redirects=False)
    assert up_res.status_code == 303
    with open(csv_path, "r", encoding="utf-8") as f:
        updated = list(csv.reader(f))[1]
    assert updated[7] == "50.0"
    assert float(updated[6]) == round(V_DRY - 0.5 * (V_DRY - V_WET), 3)

    # Проверяем удаление Opt_File и Thermal_File (не Leaf_Area_cm2)
    del_res = client.get("/api/delete_measurement/99", follow_redirects=False)
    assert del_res.status_code == 303
    assert not os.path.exists(opt_file)
    assert not os.path.exists(th_file)
