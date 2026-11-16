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
