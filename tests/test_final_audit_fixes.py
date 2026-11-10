# -*- coding: utf-8 -*-
"""
Тесты исправлений финального аудита (пункты 1–4):
1. Запрет смешения разных дат в /api/wave2/anova_report и analyze_wave2_dataset (+ кириллица и DW_g/FW_g).
2. Защита от XSS в /wave2_image/{filename}, создание uti_cache и закрытие Image.open.
3. Потокобезопасность Wave2Storage, защита архивных строк в delete_record и отказ перезаписи при сбое чтения.
4. Отсутствие синтетического fallback T_Air_C=24.0, пересчёт Delta_T_C в grab_uti_thermal,
   синхронизация Moisture_V и Water_Dose_ml когорты, валидация пустого thermal_file.filename.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import io
import os

from fastapi.testclient import TestClient
from PIL import Image

import web_station
from core.wave2_anova import analyze_wave2_dataset
from core.wave2_manager import POTS_CATALOG, Wave2Storage


client = TestClient(web_station.app)


def _grcbd_ids():
    return [
        pid
        for pid, meta in POTS_CATALOG.items()
        if meta.get("cohort") in ("Control", "Prevention", "Reaction")
    ]


def test_anova_forbids_mixed_dates_and_handles_cyrillic_and_bad_dw(tmp_path):
    """Разнодневный срез не допускается к 2-way GRCBD; кириллица ID и битые DW_g не ломают расчёт."""
    pots = _grcbd_ids()
    mixed_records = []
    for idx, pid in enumerate(pots):
        raw_id = "К1" if pid == "K1" else pid
        mixed_records.append({
            "ID": raw_id,
            "Timestamp": "2026-11-11 18:30:00" if idx < 3 else "2026-11-10 18:30:00",
            "Weight_g": "95.0",
            "Delta_T_C": "-1.2",
            "NDVI_Mean": "0.60",
            "Leaf_Area_cm2": "12.0",
            "Turgor_Score": "2" if pid.startswith("R") else "4",
            "DW_g": "bad_text" if idx == 0 else "--",
        })

    res = analyze_wave2_dataset(
        mixed_records,
        static_dir=str(tmp_path / "static"),
        docs_dir=str(tmp_path / "docs"),
    )
    assert res["ok"] is True
    assert res["total_measured"] == 18
    assert res["all_balanced_grcbd"] is False
    assert res["confirmatory_grcbd_performed"] is False
    assert res["phase"] == "grcbd_violated"
    assert any("Смешаны замеры разных дат" in reason for reason in res["confirmatory_unavailable_reasons"])
    for row in res["summary_table"]:
        assert row["confirmatory_allowed"] is False
        assert row["f_cohort"] is None
        assert row["p_cohort"] is None


def test_api_anova_report_never_pads_incomplete_today_with_yesterday():
    """При <6 замеров за сегодня API не склеивает их со вчерашним полным днём."""
    storage = Wave2Storage(web_station.DATA_DIR)
    today = datetime.now().strftime("%Y-%m-%d")

    # Сначала только прошлые завершённые дни (2026-11-08 и 2026-11-09) -> берётся строго последний день 2026-11-09
    for day in ("2026-11-08", "2026-11-09"):
        for idx, pid in enumerate(_grcbd_ids()):
            ok, msg = storage.save_or_update_record({
                "ID": pid,
                "Timestamp": f"{day} 18:30:00",
                "Weight_g": "98.0" if day == "2026-11-08" else "94.0",
                "Delta_T_C": str(-1.5 + (idx % 3) * 0.1),
                "NDVI_Mean": "0.60",
                "Leaf_Area_cm2": "11.0",
                "Turgor_Score": "4",
            })
            assert ok, msg

    resp_latest = client.get("/api/wave2/anova_report")
    assert resp_latest.status_code == 200
    d_latest = resp_latest.json()
    assert d_latest["ok"] is True
    assert d_latest["confirmatory_grcbd_performed"] is True
    # Значения массы принадлежат 2026-11-09 (94.0), не смешаны с 98.0
    w_row = next(r for r in d_latest["summary_table"] if r["trait"] == "weight_g")
    assert "94.0" in w_row["k_str"]

    # Добавляем 2 сегодняшних замера -> < 6, не должно склеиваться с 2026-11-09 до N=18!
    for pid in ("K1", "K2"):
        storage.save_or_update_record({
            "ID": pid,
            "Timestamp": f"{today} 18:45:00",
            "Weight_g": "91.0",
            "Delta_T_C": "-1.2",
            "NDVI_Mean": "0.61",
            "Leaf_Area_cm2": "12.0",
            "Turgor_Score": "4",
        })

    resp_inc = client.get("/api/wave2/anova_report")
    assert resp_inc.status_code == 200
    d_inc = resp_inc.json()
    assert d_inc["ok"] is False
    assert d_inc["total_measured"] == 2


def test_wave2_image_view_escapes_xss_and_creates_uti_cache():
    """GET /wave2_image экранирует XSS на 404 и создаёт static/uti_cache при конвертации BMP."""
    xss_resp = client.get("/wave2_image/<img src=x onerror=alert(1)>")
    assert xss_resp.status_code == 404
    assert "<img" not in xss_resp.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in xss_resp.text

    cache_dir = os.path.join(web_station.STATIC_DIR, "uti_cache")
    if os.path.isdir(cache_dir):
        for fn in os.listdir(cache_dir):
            os.remove(os.path.join(cache_dir, fn))
        os.rmdir(cache_dir)

    bmp_path = os.path.join(web_station.STATIC_DIR, "audit_test_cache.bmp")
    with Image.new("RGB", (24, 24), color=(10, 120, 200)) as im:
        im.save(bmp_path, format="BMP")

    bmp_resp = client.get("/wave2_image/audit_test_cache.bmp")
    assert bmp_resp.status_code == 200
    assert bmp_resp.headers["content-type"].startswith("image/jpeg")
    assert os.path.isfile(os.path.join(cache_dir, "audit_test_cache.jpg"))


def test_wave2_storage_lock_archive_delete_guard_and_read_error_safety():
    """Wave2Storage защищает архивные строки, удаляет оба фото сегодняшней строки и выдерживает параллельные записи."""
    storage = Wave2Storage(web_station.DATA_DIR)
    today = datetime.now().strftime("%Y-%m-%d")

    storage.save_or_update_record({
        "ID": "K1",
        "Timestamp": "2026-11-01 18:00:00",
        "Weight_g": "100.0",
        "Opt_File": "K1_arch_opt.jpg",
        "Thermal_File": "K1_arch_th.jpg",
    })
    for col in ("K1_arch_opt.jpg", "K1_arch_th.jpg"):
        with open(os.path.join(storage.images_dir, col), "wb") as f:
            f.write(b"123")

    # Замер за сегодня отсутствует -> архивная запись 2026-11-01 не должна удаляться!
    ok_del_arch, _ = storage.delete_record("K1")
    assert ok_del_arch is False
    resp_del_arch = client.post("/api/wave2/delete_record", data={"pot_id": "K1"})
    assert resp_del_arch.status_code == 200
    assert resp_del_arch.json()["status"] == "error"
    assert len(storage.load_all_records()) == 1
    assert os.path.exists(os.path.join(storage.images_dir, "K1_arch_opt.jpg"))

    # Сегодняшняя запись удаляется вместе со своими Opt_File и Thermal_File
    for fn in ("K1_today_opt.jpg", "K1_today_th.jpg"):
        with open(os.path.join(storage.images_dir, fn), "wb") as f:
            f.write(b"456")
    storage.save_or_update_record({
        "ID": "K1",
        "Timestamp": f"{today} 19:00:00",
        "Weight_g": "95.0",
        "Opt_File": "K1_today_opt.jpg",
        "Thermal_File": "K1_today_th.jpg",
    })
    ok_del_today, _ = storage.delete_record("K1")
    assert ok_del_today is True
    assert not os.path.exists(os.path.join(storage.images_dir, "K1_today_opt.jpg"))
    assert not os.path.exists(os.path.join(storage.images_dir, "K1_today_th.jpg"))
    assert len(storage.load_all_records()) == 1

    # Потокобезопасная параллельная запись 12 разных горшков
    pots = [f"K{i}" for i in range(1, 7)] + [f"P{i}" for i in range(1, 7)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(
            lambda pid: storage.save_or_update_record({"ID": pid, "Weight_g": "93.2"}),
            pots,
        ))
    assert all(ok for ok, _ in results)
    today_ids = {r["ID"] for r in storage.load_today_records(today)}
    assert today_ids == set(pots)

    # При нечитаемом CSV save_or_update_record возвращает ошибку, а не затирает журнал
    with open(storage.csv_path, "wb") as f:
        f.write(b"\xff\xfe\x00broken_utf8")
    ok_corrupt, _ = storage.save_or_update_record({"ID": "R1", "Weight_g": "90.0"})
    assert ok_corrupt is False


def test_update_record_no_24c_fallback_soil_sync_and_grab_uti_recalc(monkeypatch):
    """Без T_Air_C не подставляется 24.0; moisture_pct пересчитывает Moisture_V; grab_uti обновляет Delta_T и дозу."""
    # 1. Сохраняем P1 с пустым T_Air_C ('--') и весом 90.0 г
    storage = Wave2Storage(web_station.DATA_DIR)
    storage.save_or_update_record({
        "ID": "P1",
        "Weight_g": "90.0",
        "T_Air_C": "--",
        "T_Leaf_C": "--",
        "Delta_T_C": "--",
        "Turgor_Score": "4",
        "Water_Dose_ml": "0.0",
    })

    # Редактирование T_Leaf_C при T_Air_C='--' НЕ должно выдумывать Delta_T относительно 24.0
    res_no_air = client.post("/api/wave2/update_record", data={"pot_id": "P1", "t_leaf": "26.5"})
    assert res_no_air.status_code == 200
    assert res_no_air.json()["delta_t"] == "--"
    p1_row = next(r for r in storage.load_today_records() if r["ID"] == "P1")
    assert p1_row["Delta_T_C"] == "--"

    # 2. Обновление moisture_pct на K1 синхронно пересчитывает Moisture_V, а '--' очищает оба поля
    storage.save_or_update_record({"ID": "K1", "Weight_g": "95.0", "T_Air_C": "25.0", "Delta_T_C": "-1.5"})
    res_soil = client.post("/api/wave2/update_record", data={"pot_id": "K1", "moisture_pct": "75.0"})
    assert res_soil.status_code == 200
    k1_row = next(r for r in storage.load_today_records() if r["ID"] == "K1")
    assert k1_row["Moisture_Pct"] == "75.0"
    assert k1_row["Moisture_V"] != "--"
    expected_v = round(web_station.V_DRY - 0.75 * (web_station.V_DRY - web_station.V_WET), 3)
    assert abs(float(k1_row["Moisture_V"]) - expected_v) < 1e-6

    client.post("/api/wave2/update_record", data={"pot_id": "K1", "moisture_pct": "--"})
    k1_cleared = next(r for r in storage.load_today_records() if r["ID"] == "K1")
    assert k1_cleared["Moisture_Pct"] == "--"
    assert k1_cleared["Moisture_V"] == "--"

    # 3. Загружаем контроль K1..K6 (-1.5°C) и P1..P4 (T_Air=25.0): P4 через grab_uti_thermal даёт +2.0°C -> кворум 4/6!
    for i in range(1, 7):
        storage.save_or_update_record({
            "ID": f"K{i}", "Weight_g": "95.0", "T_Air_C": "25.0", "T_Leaf_C": "23.5", "Delta_T_C": "-1.5", "Turgor_Score": "4",
        })
    for i in range(1, 5):
        storage.save_or_update_record({
            "ID": f"P{i}",
            "Weight_g": "90.0",
            "T_Air_C": "25.0",
            "T_Leaf_C": "27.0" if i < 4 else "--",
            "Delta_T_C": "2.0" if i < 4 else "--",
            "Turgor_Score": "4",
            "Water_Dose_ml": "0.0",
        })

    monkeypatch.setattr(
        web_station,
        "grab_latest_uti_thermal_image",
        lambda pot_id, images_dir: (True, f"{pot_id}_grab_th.jpg", 27.2, "OK"),
    )
    grab_res = client.post("/api/wave2/grab_uti_thermal", data={"pot_id": "P4"})
    assert grab_res.status_code == 200
    gj = grab_res.json()
    assert gj["status"] == "ok"
    assert gj["delta_t"] == 2.2
    assert gj["watering_allowed"] is True
    assert "10.0 мл" in gj["dose"]

    # Проверяем, что Water_Dose_ml синхронизировался в CSV и для P4, и для ранее снятых P1..P3
    today_map = {r["ID"]: r for r in storage.load_today_records()}
    assert today_map["P4"]["Delta_T_C"] == "2.2"
    for pid in ("P1", "P2", "P3", "P4"):
        assert today_map[pid]["Water_Dose_ml"] == "10.0"

    # 4. upload_thermal без имени файла возвращает 400 вместо 500
    empty_up = client.post(
        "/api/wave2/upload_thermal",
        data={"pot_id": "K1"},
        files={"thermal_file": ("", io.BytesIO(b""), "application/octet-stream")},
    )
    assert empty_up.status_code in (400, 422)
