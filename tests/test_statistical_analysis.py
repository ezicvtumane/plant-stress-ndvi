# -*- coding: utf-8 -*-
import pytest
import pandas as pd
from src.statistical_analysis import ExperimentStatistics

def test_anova_day4():
    stats_engine = ExperimentStatistics()
    stats_engine.load_or_generate_dataset()
    res = stats_engine.compute_one_way_anova(day=4)
    
    assert res["day"] == 4
    # On Day 4, Delta_T between Control and Stressed is highly significant (p < 0.001)
    assert res["p_dt"] < 0.001
    assert res["f_dt"] > 50.0
    
    # NDVI drop is also statistically significant
    assert res["p_ndvi"] < 0.001
    assert res["f_ndvi"] > 50.0
    
    # Soil moisture difference is statistically significant
    assert res["p_sm"] < 0.001
    assert res["f_sm"] > 100.0

def test_full_7days_anova_table():
    stats_engine = ExperimentStatistics()
    df_anova = stats_engine.compute_full_7days_anova()
    
    assert len(df_anova) == 7
    assert "F_DeltaT" in df_anova.columns
    assert "p_DeltaT" in df_anova.columns
    assert "F_NDVI" in df_anova.columns
    assert "p_NDVI" in df_anova.columns
