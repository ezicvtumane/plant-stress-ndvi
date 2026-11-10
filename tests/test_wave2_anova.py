# -*- coding: utf-8 -*-
"""
Модульные и интеграционные тесты для биостатистического движка Волна 2
(Two-Way ANOVA по Доспехову, детектор фаз и веб-эндпоинты).
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

import os
import sys
import shutil
import pytest
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from fastapi.testclient import TestClient

from core.wave2_anova import dospekhov_two_way_anova_engine, analyze_wave2_dataset
from web_station import app

client = TestClient(app)


def test_dospekhov_two_way_anova_engine_balanced():
    """Проверка математики Two-Way ANOVA для сбалансированного комплекса 3х3х2 (N=18)."""
    pots = ["K1", "K2", "P1", "P2", "R1", "R2",
            "K3", "K4", "P3", "P4", "R3", "R4",
            "K5", "K6", "P5", "P6", "R5", "R6"]
    
    rows = []
    for pid in pots:
        cohort = "Control" if pid.startswith("K") else ("Prevention" if pid.startswith("P") else "Reaction")
        block = 1 if pid in ["K1", "K2", "P1", "P2", "R1", "R2"] else (2 if pid in ["K3", "K4", "P3", "P4", "R3", "R4"] else 3)
        # Однородные данные вокруг 140 г
        w = 140.0 + np.random.normal(0, 1.5)
        rows.append({"pot_id": pid, "cohort": cohort, "block": f"Блок {block}", "weight_g": w})
        
    df = pd.DataFrame(rows)
    res = dospekhov_two_way_anova_engine(df, "weight_g")

    assert res["is_balanced_grcbd"] is True
    assert res["N"] == 18
    assert res["df_cohort"] == 2
    assert res["df_block"] == 2
    assert res["df_interaction"] == 4
    assert res["df_error"] == 9
    assert res["f_cohort"] >= 0.0
    assert 0.0 <= res["p_cohort"] <= 1.0
    assert res["lsd_05"] > 0.0


def test_analyze_wave2_dataset_baseline_homogeneity(tmp_path):
    """Проверка автоматической детекции фазы 'День 0' при исходной однородности."""
    static_tmp = str(tmp_path / "static")
    docs_tmp = str(tmp_path / "docs")
    
    pots = ["K1", "K2", "K3", "K4", "K5", "K6",
            "P1", "P2", "P3", "P4", "P5", "P6",
            "R1", "R2", "R3", "R4", "R5", "R6"]
    
    records = []
    for pid in pots:
        records.append({
            "ID": pid,
            "Weight_g": 140.0,
            "Delta_T_C": -0.8,
            "NDVI_mean": 0.72,
            "PLA_cm2": 45.0,
            "Turgor_Score": 4
        })

    res = analyze_wave2_dataset(records, static_dir=static_tmp, docs_dir=docs_tmp)
    assert res["ok"] is True
    assert res["total_measured"] == 18
    assert res["phase"] == "baseline"
    assert "🟢 ДЕНЬ 0: ИСХОДНАЯ ОДНОРОДНОСТЬ" in res["status_badge"]
    assert len(res["summary_table"]) >= 5
    assert os.path.exists(os.path.join(static_tmp, "charts", "anova_latest.png"))
    assert os.path.exists(os.path.join(docs_tmp, "ANOVA_LATEST_REPORT.md"))


def test_analyze_wave2_dataset_prevention_and_reaction(tmp_path):
    """Проверка детекции температурного стресса (Превенция) и увядания (Реакция)."""
    static_tmp = str(tmp_path / "static")
    docs_tmp = str(tmp_path / "docs")

    pots = ["K1", "K2", "K3", "K4", "K5", "K6",
            "P1", "P2", "P3", "P4", "P5", "P6",
            "R1", "R2", "R3", "R4", "R5", "R6"]

    # 1. Сценарий Превенции: перегрев ΔT при нормальном тургоре
    records_prev = []
    for pid in pots:
        dt = -0.9 if pid.startswith("K") else 1.8
        records_prev.append({
            "ID": pid,
            "Weight_g": 125.0,
            "Delta_T_C": dt,
            "NDVI_mean": 0.68,
            "PLA_cm2": 44.0,
            "Turgor_Score": 4
        })
    res_p = analyze_wave2_dataset(records_prev, static_dir=static_tmp, docs_dir=docs_tmp)
    assert res_p["phase"] == "prevention_alert"
    assert "🚨 СТРЕСС-ФАЗА: ДЕТЕКЦИЯ СКРЫТОЙ ЗАСУХИ" in res_p["status_badge"]

    # 2. Сценарий Реакции: падение балла тургора
    records_reac = []
    for pid in pots:
        tr = 4 if pid.startswith("K") or pid.startswith("P") else 2
        records_reac.append({
            "ID": pid,
            "Weight_g": 110.0,
            "Delta_T_C": 2.2,
            "NDVI_mean": 0.65,
            "PLA_cm2": 42.0,
            "Turgor_Score": tr
        })
    res_r = analyze_wave2_dataset(records_reac, static_dir=static_tmp, docs_dir=docs_tmp)
    assert res_r["phase"] == "reaction_trigger"
    assert "🔵 СТРЕСС-ФАЗА: КРИТИЧЕСКИЙ СТРЕСС УВЯДАНИЯ" in res_r["status_badge"]


def test_api_wave2_anova_report_endpoint():
    """Проверка ответа FastAPI эндпоинта /api/wave2/anova_report."""
    resp = client.get('/api/wave2/anova_report')
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    # Либо ok=True (если есть замеры), либо ok=False с внятным пояснением
    if data["ok"]:
        assert "status_badge" in data
        assert "summary_table" in data
        assert "traits" in data


def test_wave2_dashboard_contains_anova_ui():
    """Проверка наличия кнопки и модального окна в шаблоне дашборда."""
    resp = client.get('/?stage=wave2')
    assert resp.status_code == 200
    html = resp.text
    assert "openAnovaModal()" in html
    assert "Биостатистика (ANOVA)" in html
    assert 'id="anovaModal"' in html
    assert 'id="anovaTable"' in html
    assert 'id="anovaChartImg"' in html


def test_wave2_anova_reads_csv_column_names(tmp_path):
    """Проверка корректного считывания колонок NDVI_Mean и Leaf_Area_cm2 из CSV."""
    records = []
    for pid in ["K1", "K2", "K3", "K4", "K5", "K6",
                "P1", "P2", "P3", "P4", "P5", "P6",
                "R1", "R2", "R3", "R4", "R5", "R6"]:
        records.append({
            "ID": pid,
            "Weight_g": "100.0",
            "Delta_T_C": "-1.8",
            "NDVI_Mean": "0.620",
            "Leaf_Area_cm2": "12.5",
            "Turgor_Score": "4"
        })
    res = analyze_wave2_dataset(
        records,
        static_dir=str(tmp_path / "static"),
        docs_dir=str(tmp_path / "docs"),
    )
    assert res["ok"] is True
    for row in res["summary_table"]:
        if row["trait"] == "ndvi":
            assert "0.62" in row["k_str"]
        if row["trait"] == "pla_cm2":
            assert "12.5" in row["k_str"]
