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
