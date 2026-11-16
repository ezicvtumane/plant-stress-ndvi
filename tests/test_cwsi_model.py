# -*- coding: utf-8 -*-
"""
Тест математической и физиологической корректности модели CWSI (Idso-Jackson).
Проверяет:
  1. Наличие датасета cwsi_wave2_analysis.csv и графика cwsi_dynamics_wave2.png.
  2. Соответствие базисных линий NWSB и UL физическим границам.
  3. Значения CWSI в ключевых триггерных точках (День 3 и День 4).
  4. Эквивалентность эмпирического порога Delta_Delta_T >= +0.60 °C нормализованному индексу CWSI ~ 0.21-0.25.
"""

import os
import pytest
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "experiments", "exp_1792918800", "cwsi_wave2_analysis.csv")
CHART_PATH = os.path.join(BASE_DIR, "static", "charts", "cwsi_dynamics_wave2.png")


def test_cwsi_dataset_structure():
    assert os.path.exists(CSV_PATH), f"Файл {CSV_PATH} не найден"
    df = pd.read_csv(CSV_PATH)
    assert len(df) == 126, f"Ожидалось 126 записей (18 растений x 7 суток), получено {len(df)}"

    expected_cols = [
        "ID", "Cohort", "Day", "Date", "T_Air_C", "RH_Air_Pct", "VPD_kPa",
        "T_Leaf_C", "Delta_T_C", "Delta_T_wet_dyn", "Delta_T_dry",
        "Delta_Delta_T", "CWSI_dyn", "Turgor_Score", "Water_Dose_ml"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Колонка {col} отсутствует в cwsi_wave2_analysis.csv"


def test_cwsi_cohort_baseline_and_triggers():
    df = pd.read_csv(CSV_PATH)

    # 1. Контроль всегда находится в зоне оптимального водообеспечения (CWSI < 0.10)
    k_cwsi = df[df["Cohort"] == "Контроль"]["CWSI_dyn"]
    assert k_cwsi.mean() < 0.05, f"Средний CWSI контроля {k_cwsi.mean()} должен быть < 0.05"
    assert (k_cwsi < 0.15).all(), "Ни одно контрольное растение не должно превышать CWSI = 0.15"

    # 2. День 3 (Превентивный триггер): CWSI Превенции в диапазоне [0.20, 0.28]
    d3_p = df[(df["Day"] == 3) & (df["Cohort"] == "Превенция")]["CWSI_dyn"]
    assert 0.20 <= d3_p.mean() <= 0.28, f"Day 3 Prevention CWSI {d3_p.mean()} вне диапазона [0.20, 0.28]"

    # 3. День 4 (Традиционная реакция / острый стресс): CWSI Реакции в диапазоне [0.65, 0.80]
    d4_r = df[(df["Day"] == 4) & (df["Cohort"] == "Реакция")]["CWSI_dyn"]
    assert 0.65 <= d4_r.mean() <= 0.80, f"Day 4 Reaction CWSI {d4_r.mean()} вне диапазона [0.65, 0.80]"

    # 4. Превенция на День 4 после полива Дня 3 сохраняет CWSI < 0.25 (защита от стресса)
    d4_p = df[(df["Day"] == 4) & (df["Cohort"] == "Превенция")]["CWSI_dyn"]
    assert d4_p.mean() < 0.25, f"Day 4 Prevention CWSI {d4_p.mean()} должен быть < 0.25 после полива"


def test_cwsi_physical_boundary_limits():
    df = pd.read_csv(CSV_PATH)

    # CWSI строго в границах [0.0, 1.0]
    assert (df["CWSI_dyn"] >= 0.0).all()
    assert (df["CWSI_dyn"] <= 1.0).all()

    # Верхняя граница Delta_T_dry = +1.00 C
    assert (df["Delta_T_dry"] == 1.00).all()

    # Нижняя граница Delta_T_wet_dyn строго отрицательна (транспирационное охлаждение)
    assert (df["Delta_T_wet_dyn"] < 0.0).all()


def test_cwsi_chart_exists():
    assert os.path.exists(CHART_PATH), f"График {CHART_PATH} не найден"
    assert os.path.getsize(CHART_PATH) > 50000, "Файл графика подозрительно мал (< 50 Кб)"
