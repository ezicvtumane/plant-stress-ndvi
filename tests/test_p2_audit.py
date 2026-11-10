# -*- coding: utf-8 -*-
"""
Тесты согласованности данных и документации этапа P2 (Задачи 5, 11, 12):
- Сохранность исторических числовых значений биомассы и совместимость CSV
- Сохранение датного формата Timestamp в историческом журнале Волны 2 от 09.11.2026
"""

import csv
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_task12_harvest_validation_scales_compat_and_dw():
    """Исторический CSV контрольного взвешивания не мутируется лишними колонками и сохраняет значения 0.73..0.35 г."""
    csv_path = os.path.join(PROJECT_ROOT, "data", "harvest_validation_scales_day11.csv")
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    assert fieldnames == [
        "Cohort_ID", "Cohort_Name", "ArUco_ID", "Icon_Symbol",
        "Fresh_Weight_g", "Scale_Precision_g", "Tare_Weight_g",
        "Scale_Photo_Filename", "Physiological_Status",
    ]
    assert len(rows) == 5
    expected_dw = {"K1": 0.73, "K2": 0.55, "K3": 0.35, "K4": 0.65, "K5": 0.49}
    for row in rows:
        cid = row["Cohort_ID"]
        assert float(row["Fresh_Weight_g"]) == expected_dw[cid]


def test_task12_series1_fresh_biomass_sums_intact():
    """Исторические суммы сырой биомассы Серии 1 остаются неизменными и согласованными."""
    csv_path = os.path.join(PROJECT_ROOT, "data", "harvest_fresh_biomass.csv")
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    expected_sums = {"K1": 4.25, "K2": 3.15, "K3": 1.83, "K4": 3.87, "K5": 2.85}
    cols = {"K1": "control_k1", "K2": "osmotic_k2", "K3": "drought_k3", "K4": "prevention_k4", "K5": "reaction_k5"}
    for cid, col_name in cols.items():
        total = round(sum(float(r[col_name]) for r in rows), 2)
        assert total == expected_sums[cid]
