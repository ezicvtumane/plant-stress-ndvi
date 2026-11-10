# -*- coding: utf-8 -*-
import pytest
import pandas as pd
from pathlib import Path
from src.statistical_analysis import ExperimentStatistics

def test_load_real_dataset():
    stats_engine = ExperimentStatistics()
    # Should successfully load real measurements.csv
    df = stats_engine.load_dataset()
    assert len(df) > 0
    assert "Group" in df.columns
    assert "Delta_T_C" in df.columns
    assert "NDVI_Mean" in df.columns

def test_cohort_summary():
    stats_engine = ExperimentStatistics()
    summary = stats_engine.get_cohort_summary()
    assert "Контроль" in summary.index or "Control" in summary.index or len(summary) > 0

def test_missing_file_raises_error():
    fake_engine = ExperimentStatistics(data_file="/tmp/non_existent_file_xyz123.csv")
    with pytest.raises(FileNotFoundError):
        fake_engine.load_dataset()


def test_series1_telemetry_exploratory_facts_and_correlations():
    """Проверка воспроизводимости корреляций и реальной хронологии Серии 1 (n=55)."""
    stats_engine = ExperimentStatistics()
    df = stats_engine.load_dataset()
    assert len(df) == 55

    ctrl = df[df["Group"] == "Контроль"]
    assert round(float(ctrl["NDVI_Mean"].min()), 3) == 0.715
    assert round(float(ctrl["NDVI_Mean"].max()), 3) == 0.811

    oct14 = df[df["Timestamp"].str.contains("14 октября", na=False)].set_index("Group")["Delta_T_C"].to_dict()
    assert oct14["Контроль"] == -1.3
    assert oct14["Превенция"] == -1.3
    assert oct14["Осмос"] == 1.2
    assert oct14["Засуха"] == 1.7
    assert oct14["Реакция"] == 1.8

    comp = stats_engine.compare_groups("Контроль", "Засуха")
    assert comp["exploratory_status"] == "cassette_pseudoreplicated_n1"

    corr = stats_engine.get_telemetry_correlations()
    assert corr["delta_t_vs_ndvi_all"]["n"] == 55
    assert corr["delta_t_vs_ndvi_all"]["pearson_r"] == pytest.approx(-0.4977, abs=1e-3)
    assert corr["moisture_vs_delta_t"]["n"] == 33
    assert corr["moisture_vs_delta_t"]["pearson_r"] == pytest.approx(-0.5797, abs=1e-3)
    assert corr["moisture_vs_weight"]["pearson_r"] == pytest.approx(0.8453, abs=1e-3)

    report_text = (Path(__file__).resolve().parent.parent / "docs" / "STATISTICAL_ANALYSIS_SERIES1.md").read_text(encoding="utf-8")
    assert "exploratory" in report_text.lower()
    assert "0.715" in report_text and "0.811" in report_text
    assert "-0.498" in report_text

