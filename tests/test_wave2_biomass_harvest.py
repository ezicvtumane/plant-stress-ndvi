# -*- coding: utf-8 -*-
"""
Автоматизированный тест целостности и воспроизводимости деструктивного учета биомассы (Волна 2, Огурец «Каскад»).
Проверяет:
  1. Файл biomass_harvest_wave2.csv: структура, типы, 18 строк (GRCBD 3x3x2).
  2. Баланс сырой массы (FW: K=8.25, P=7.95, R=6.45 г) и сухой массы (DW: K=0.72, P=0.69, R=0.60 г).
  3. Математическую корректность расчета Dry_Matter_pct, Water_Content_pct и WUE.
  4. Наличие на диске фотодоказательств срезки, сушки и морфометрии корней.
  5. Достоверность дисперсионного анализа (Two-Way ANOVA по Б.А. Доспехову).
"""

import os
import pytest
import pandas as pd
import numpy as np
from scipy import stats

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "experiments", "exp_1792918800", "biomass_harvest_wave2.csv")
IMAGES_DIR = os.path.join(BASE_DIR, "docs", "wave2", "images")


def test_biomass_harvest_csv_structure_and_row_count():
    """Проверка структуры и размерности датасета срезки."""
    assert os.path.exists(CSV_PATH), f"Файл {CSV_PATH} не найден на диске"
    df = pd.read_csv(CSV_PATH)
    assert len(df) == 18, f"Ожидалось ровно 18 строк (GRCBD 3x3x2), получено {len(df)}"

    expected_cols = [
        "ID", "Cohort", "Block", "Rep",
        "Fresh_Weight_g", "Dry_Weight_g",
        "Dry_Matter_pct", "Water_Content_pct",
        "Cum_Water_ml", "WUE_mg_ml"
    ]
    assert list(df.columns) == expected_cols, f"Колонки датасета не совпадают с эталоном: {df.columns}"

    # Проверка когорт и блоков
    assert set(df["Cohort"].unique()) == {"Контроль", "Превенция", "Реакция"}
    assert set(df["Block"].unique()) == {1, 2, 3}
    assert (df["Rep"].isin([1, 2])).all()

    # Ровно по 6 растений в каждой когорте
    cohort_counts = df["Cohort"].value_counts()
    assert cohort_counts["Контроль"] == 6
    assert cohort_counts["Превенция"] == 6
    assert cohort_counts["Реакция"] == 6


def test_biomass_harvest_ground_truth_sums():
    """Проверка точного соответствия сумм сырой и сухой массы протоколу."""
    df = pd.read_csv(CSV_PATH)

    fw_sums = df.groupby("Cohort")["Fresh_Weight_g"].sum().round(2)
    assert fw_sums["Контроль"] == 8.25, f"Контроль FW {fw_sums['Контроль']} != 8.25"
    assert fw_sums["Превенция"] == 7.95, f"Превенция FW {fw_sums['Превенция']} != 7.95"
    assert fw_sums["Реакция"] == 6.45, f"Реакция FW {fw_sums['Реакция']} != 6.45"

    dw_sums = df.groupby("Cohort")["Dry_Weight_g"].sum().round(2)
    assert dw_sums["Контроль"] == 0.72, f"Контроль DW {dw_sums['Контроль']} != 0.72"
    assert dw_sums["Превенция"] == 0.69, f"Превенция DW {dw_sums['Превенция']} != 0.69"
    assert dw_sums["Реакция"] == 0.60, f"Реакция DW {dw_sums['Реакция']} != 0.60"


def test_biomass_harvest_formula_integrity():
    """Проверка корректности формул пересчета DM%, WC% и WUE."""
    df = pd.read_csv(CSV_PATH)

    for _, row in df.iterrows():
        calc_dm = round((row["Dry_Weight_g"] / row["Fresh_Weight_g"]) * 100.0, 2)
        assert abs(row["Dry_Matter_pct"] - calc_dm) <= 0.05, f"Ошибка в DM% для {row['ID']}"

        calc_wc = round(100.0 - row["Dry_Matter_pct"], 2)
        assert abs(row["Water_Content_pct"] - calc_wc) <= 0.05, f"Ошибка в WC% для {row['ID']}"

        if row["Cum_Water_ml"] > 0:
            calc_wue = round((row["Dry_Weight_g"] * 1000.0) / row["Cum_Water_ml"], 2)
            assert abs(row["WUE_mg_ml"] - calc_wue) <= 0.05, f"Ошибка в WUE для {row['ID']}"


def test_biomass_harvest_visual_artifacts_exist():
    """Проверка наличия всех ключевых фотодоказательств срезки и корней на диске."""
    critical_images = [
        "24_wave2_biomass_harvest_raw_sheet_handwritten.jpg",
        "37_wave2_roots_comparison_R6_triangle_vs_K2_circle.jpg",
        "38_wave2_root_system_R6_excavated_washed.jpg",
        "39_wave2_root_system_K2_excavated_washed.jpg",
        "40_wave2_root_system_K2_substrate_monolith.jpg",
        "41_wave2_dried_shoot_specimen_DW.jpg",
        "42_wave2_drying_envelopes_notebook_paper.jpg",
        "43_wave2_cat_senior_inspector_quality_control.jpg",
        "44_wave2_microscopy_stomata_open_control_prevention.jpg",
        "45_wave2_microscopy_stomata_closed_reaction_stress.jpg"
    ]
    for img_name in critical_images:
        p = os.path.join(IMAGES_DIR, img_name)
        assert os.path.exists(p), f"Фотодоказательство {p} не найдено на диске"
        assert os.path.getsize(p) > 10000, f"Файл {p} подозрительно мал (< 10 Кб)"


def test_biomass_harvest_two_way_anova_dospekhov():
    """Проверка математической воспроизводимости двухфакторного ANOVA по Доспехову."""
    df = pd.read_csv(CSV_PATH)

    # 1. Сырая масса FW: F > F01 (8.02)
    cohort_order = {"Контроль": 0, "Превенция": 1, "Реакция": 2}
    data_fw = np.zeros((3, 3, 2))
    data_dw = np.zeros((3, 3, 2))

    for _, r in df.iterrows():
        c_idx = cohort_order[r["Cohort"]]
        b_idx = int(r["Block"]) - 1
        rep_idx = int(r["Rep"]) - 1
        data_fw[c_idx, b_idx, rep_idx] = r["Fresh_Weight_g"]
        data_dw[c_idx, b_idx, rep_idx] = r["Dry_Weight_g"]

    def run_anova(arr):
        gm = np.mean(arr)
        ss_tot = np.sum((arr - gm) ** 2)
        mA = np.mean(arr, axis=(1, 2))
        mB = np.mean(arr, axis=(0, 2))
        mAB = np.mean(arr, axis=2)
        ss_A = 6 * np.sum((mA - gm) ** 2)
        ss_B = 6 * np.sum((mB - gm) ** 2)
        ss_AB = 2 * np.sum((mAB - mA[:, None] - mB[None, :] + gm) ** 2)
        ss_E = ss_tot - ss_A - ss_B - ss_AB
        ms_A = ss_A / 2
        ms_E = ss_E / 9
        F_A = ms_A / ms_E
        p_A = 1 - stats.f.cdf(F_A, 2, 9)
        return F_A, p_A

    F_fw, p_fw = run_anova(data_fw)
    assert F_fw > 8.02, f"F-критерий FW {F_fw} должен превышать порог 1% (8.02)"
    assert p_fw < 0.01, f"p-value FW {p_fw} должно быть < 0.01"

    # 2. Сухая масса DW: F > F05 (4.26)
    F_dw, p_dw = run_anova(data_dw)
    assert F_dw > 4.26, f"F-критерий DW {F_dw} должен превышать порог 5% (4.26)"
    assert p_dw < 0.05, f"p-value DW {p_dw} должно быть < 0.05"


def test_biomass_harvest_tukey_hsd_and_api_reproducibility(tmp_path):
    """
    Проверка точных F_блок / F_взаимод, парных сравнений Тьюки HSD (FW и DW: df_e=9 и df_e=13)
    по фактическому biomass_harvest_wave2.csv и воспроизводимости /api/wave2/anova_report.
    """
    import shutil
    from fastapi.testclient import TestClient
    import web_station
    from core.wave2_anova import compute_harvest_biomass_analysis

    res = compute_harvest_biomass_analysis(CSV_PATH)
    assert res is not None

    # FW (полная модель, df_e = 9)
    fw_full = res["fw"]["full_model"]
    assert fw_full["df_error"] == 9
    assert fw_full["f_cohort"] == pytest.approx(9.731, abs=0.002)
    assert fw_full["f_block"] == pytest.approx(31.958, abs=0.002)
    assert fw_full["f_interaction"] == pytest.approx(1.611, abs=0.002)
    assert fw_full["tukey_hsd"]["K-P"]["p"] == pytest.approx(0.7772, abs=0.001)
    assert fw_full["tukey_hsd"]["K-R"]["p"] == pytest.approx(0.0066, abs=0.0005)
    assert fw_full["tukey_hsd"]["P-R"]["p"] == pytest.approx(0.0185, abs=0.0005)

    # DW (полная модель, df_e = 9)
    dw_full = res["dw"]["full_model"]
    assert dw_full["df_error"] == 9
    assert dw_full["f_cohort"] == pytest.approx(6.158, abs=0.002)
    assert dw_full["p_cohort"] == pytest.approx(0.0207, abs=0.0005)
    assert dw_full["tukey_hsd"]["K-P"]["p"] == pytest.approx(0.6873, abs=0.001)
    assert dw_full["tukey_hsd"]["K-R"]["p"] == pytest.approx(0.0203, abs=0.0005)
    assert dw_full["tukey_hsd"]["P-R"]["p"] == pytest.approx(0.0753, abs=0.0005)
    assert dw_full["fisher_lsd"]["P-R"]["p"] == pytest.approx(0.0323, abs=0.0005)

    # DW (аддитивная модель, df_e = 13)
    dw_add = res["dw"]["additive_model"]
    assert dw_add["df_error"] == 13
    assert dw_add["f_cohort"] == pytest.approx(7.567, abs=0.002)
    assert dw_add["p_cohort"] == pytest.approx(0.0066, abs=0.0005)
    assert dw_add["tukey_hsd"]["P-R"]["p"] == pytest.approx(0.0372, abs=0.0005)

    # Сквозная проверка /api/wave2/anova_report на изолированном DATA_DIR с реальными CSV
    exp_dir = os.path.join(web_station.DATA_DIR, "experiments", "exp_1792918800")
    os.makedirs(exp_dir, exist_ok=True)
    src_meas = os.path.join(BASE_DIR, "data", "experiments", "exp_1792918800", "measurements_wave2.csv")
    shutil.copyfile(src_meas, os.path.join(exp_dir, "measurements_wave2.csv"))
    shutil.copyfile(CSV_PATH, os.path.join(exp_dir, "biomass_harvest_wave2.csv"))

    client = TestClient(web_station.app)
    resp = client.get("/api/wave2/anova_report")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["harvest_biomass"] is not None
    assert payload["harvest_biomass"]["fw"]["full_model"]["f_block"] == pytest.approx(31.958, abs=0.002)
    assert payload["harvest_biomass"]["dw"]["additive_model"]["tukey_hsd"]["P-R"]["p"] == pytest.approx(0.0372, abs=0.0005)

    report_md = open(payload["report_file"], encoding="utf-8").read()
    for token in ("31.958", "1.611", "0.7772", "0.0185", "0.6873", "0.0753", "0.0323", "0.0372"):
        assert token in report_md, f"Отчёт /api/wave2/anova_report не содержит ожидаемое значение {token}"
