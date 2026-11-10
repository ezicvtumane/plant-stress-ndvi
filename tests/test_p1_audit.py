# -*- coding: utf-8 -*-
"""
Тесты этапа P1 (Задачи 4, 5, 6, 8, 9, 10 технического аудита):
- Задача 4: Наличие, валидность JPEG и соответствие ID всех 38 первичных снимков от 09.11.2026
- Задача 6: Актуальный каталог POTS_CATALOG (18 GRCBD + C20 + X0 = 20 сосудов)
- Задача 8: Отсутствие устаревшего fallback k_bal = 1.025 в UI
- Задача 9: Воспроизводимость OLS по 3 опубликованным точкам CWSI
- Задача 10: Отключение авто-поправки PLA (Option A) и геометрический фильтр ArUco CLAHE
"""

import csv
import os
import sys
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import web_station
from core.wave2_manager import (
    POTS_CATALOG,
    Wave2Storage,
    calculate_water_dose,
    detect_aruco_scale_on_floor,
)
from core.wave2_ui import render_wave2_active_pot_card
from core.dashboard_view import build_review_view


def test_task4_nov9_primary_images_exist_and_match_ids():
    """Все 38 ссылок от 09.11 в measurements_wave2.csv физически существуют, валидны и без тестовых заглушек."""
    exp_dir = os.path.join(PROJECT_ROOT, "data", "experiments", "exp_1792918800")
    csv_path = os.path.join(exp_dir, "measurements_wave2.csv")
    img_dir = os.path.join(exp_dir, "images")

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    nov9_rows = [r for r in rows if r["Timestamp"].strip().startswith("2026-11-09")]
    assert len(nov9_rows) == 19
    referenced = set()
    for row in nov9_rows:
        pid = row["ID"].strip().upper()
        assert row["Timestamp"].strip() == "2026-11-09"
        for col in ("Opt_File", "Thermal_File"):
            fname = row[col].strip()
            assert fname.startswith(f"{pid}_"), f"{fname} does not match {pid}"
            fpath = os.path.join(img_dir, fname)
            assert os.path.isfile(fpath), f"Missing primary image: {fpath}"
            with open(fpath, "rb") as imf:
                head = imf.read(32)
            assert head.startswith(b"\xff\xd8\xff"), f"Invalid JPEG header in {fname}"
            assert b"FAKE_JPEG_DATA_STREAM" not in head
            referenced.add(fname)

    assert len(referenced) == 38
    actual_files = set(os.listdir(img_dir))
    assert referenced.issubset(actual_files)
    # Старые синтетические файлы-заглушки из коммита cc446725 не должны присутствовать
    removed_dummies = {
        "K1_20261109_205158_thermal.jpg",
        "K1_20261109_205915_thermal.jpg",
        "K1_20261109_211533_thermal.jpg",
        "K1_20261109_212733_thermal.jpg",
        "K1_20261109_212813_thermal.jpg",
        "K2_20261109_205158_thermal.jpg",
    }
    assert actual_files.isdisjoint(removed_dummies)


def test_task6_pots_catalog_design_alignment():
    """Проверка 20-сосудного дизайна: 18 GRCBD (K/P/R x 6) + X0 (лизиметр) + C20 (сателлит), без E1/E2."""
    assert len(POTS_CATALOG) == 20
    assert "E1" not in POTS_CATALOG
    assert "E2" not in POTS_CATALOG
    assert POTS_CATALOG["X0"]["cohort"] == "Lysimeter_Blank"
    assert POTS_CATALOG["C20"]["cohort"] == "Satellite"
    for prefix in ("K", "P", "R"):
        for i in range(1, 7):
            assert f"{prefix}{i}" in POTS_CATALOG


def test_task10_calculate_water_dose_with_and_without_pla_option_a():
    """calculate_water_dose сохраняет опцию PLA, но без передачи PLA считает строго от 100.0 г."""
    assert calculate_water_dose(92.5, 100.0) == 7.5
    assert calculate_water_dose(92.5, 100.0, pla_cm2=None) == 7.5
    # При явной передаче PLA формула продолжает работать для исследований
    assert calculate_water_dose(92.5, 100.0, pla_cm2=50.0) == 10.5


def test_task10_active_pipeline_disables_auto_pla_compensation():
    """
    В активном конвейере (web_station + wave2_ui) наличие Leaf_Area_cm2 в строке
    НЕ завышает целевую массу полива выше 100.0 г (Option A).
    """
    storage = Wave2Storage(web_station.DATA_DIR)
    ok, _ = storage.save_or_update_record({
        "ID": "K1",
        "Weight_g": "92.5",
        "Leaf_Area_cm2": "50.0",
        "Turgor_Score": "4",
        "T_Air_C": "24.0",
        "T_Leaf_C": "23.0",
        "Delta_T_C": "-1.0",
    })
    assert ok is True

    client = TestClient(web_station.app)
    res = client.post("/api/wave2/update_record", data={"pot_id": "K1", "weight_g": "92.5"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["dose"] == "7.5 мл"
    assert payload["raw_deficit_ml"] == 7.5

    recs = storage.load_today_records()
    card_html = render_wave2_active_pot_card("K1", recs, {"t_c": 24.0, "rh_pct": 50.0, "cur_v": None})
    assert "7.5 мл" in card_html
    assert "10.5 мл" not in card_html


def test_task10_aruco_rejects_wall_noise_and_accepts_centered_square_marker():
    """Геометрический и ROI-фильтр ArUco отвергает краевые/сплющенные артефакты и принимает центрированный маркер."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # 1. Реальный маркер, но у правой стенки (cx > 0.85*w) или мелкий/сплющенный (<30 px) должен быть отвергнут
    edge_img = np.full((960, 1280), 40, dtype=np.uint8)
    edge_img[460:550, 1130:1220] = 220  # белая подложка на стенке
    marker_edge = cv2.aruco.generateImageMarker(aruco_dict, 17, 60)
    edge_img[475:535, 1145:1205] = marker_edge
    res_edge = detect_aruco_scale_on_floor(edge_img, real_size_cm=1.5)
    assert res_edge.detected is False
    assert float(res_edge) == pytest.approx(40.0)

    # 2. Слишком мелкий маркер (24x24 px < 30 px) даже в центре отвергается
    tiny_img = np.full((960, 1280), 40, dtype=np.uint8)
    tiny_img[440:500, 600:660] = 220
    tiny_marker = cv2.aruco.generateImageMarker(aruco_dict, 5, 24)
    tiny_img[458:482, 618:642] = tiny_marker
    res_tiny = detect_aruco_scale_on_floor(tiny_img, real_size_cm=1.5)
    assert res_tiny.detected is False

    # 3. Валидный квадратный маркер 90x90 px в центральной зоне дна бокса (90 / 1.5 = 60 px/cm)
    valid_img = np.full((960, 1280), 40, dtype=np.uint8)
    valid_img[380:510, 580:710] = 220  # белая бумага стикера
    marker_90 = cv2.aruco.generateImageMarker(aruco_dict, 1, 90)
    valid_img[400:490, 600:690] = marker_90
    res_valid = detect_aruco_scale_on_floor(valid_img, real_size_cm=1.5)
    assert res_valid.detected is True
    assert res_valid.id == 1
    assert float(res_valid) == pytest.approx(60.0, abs=1.5)


def test_task8_no_stale_1025_kbal_fallback_in_ui():
    """Устаревший fallback 1.025 не отображается в интерфейсе станции."""
    panel = build_review_view(
        {"group": "Контроль", "aruco_id": 1},
        offset=0,
        t_now=0,
        uti_info=None,
    )
    assert "1.025" not in panel["step1_note"]
    assert "k=--" in panel["step1_note"]


def test_task9_cwsi_nwsb_ols_recalculation():
    """Прямая проверка МНК (OLS) по 3 опубликованным точкам CALIBRATION.md."""
    vpd = np.array([0.53, 0.91, 1.61])
    dt = np.array([-0.4, -0.6, -1.7])
    slope_neg, intercept = np.polyfit(vpd, dt, 1)
    y_pred = intercept + slope_neg * vpd
    r2 = 1.0 - float(np.sum((dt - y_pred) ** 2) / np.sum((dt - np.mean(dt)) ** 2))
    assert intercept == pytest.approx(0.3703, abs=1e-3)
    assert -slope_neg == pytest.approx(1.2494, abs=1e-3)
    assert r2 == pytest.approx(0.9562, abs=1e-3)
