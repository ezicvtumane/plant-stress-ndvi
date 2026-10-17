# -*- coding: utf-8 -*-
"""
Statistical Processing, SciPy Hypothesis Testing & Experimental Analytics
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry & Thermometry Station
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
from src import config

logger = logging.getLogger(__name__)


class ExperimentStatistics:
    """
    Performs statistical validation and physiological analytics
    on real experimental time-series from measurements.csv.
    Cohorts: Контроль, Засуха, Осмос, Превенция, Реакция.
    """
    def __init__(self, data_file: Optional[str] = None):
        if data_file:
            self.data_file = Path(data_file)
        else:
            exp_csv = config.DATA_DIR / "experiments/exp_1791463544/measurements.csv"
            root_csv = config.DATA_DIR / "measurements.csv"
            self.data_file = exp_csv if exp_csv.exists() else root_csv
        self.df = None

    def load_dataset(self) -> pd.DataFrame:
        """Loads experimental data strictly from existing measurements.csv log."""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Experimental data file not found: {self.data_file}")

        self.df = pd.read_csv(self.data_file)
        logger.info("Loaded %d experimental records from %s", len(self.df), self.data_file)
        return self.df

    def get_cohort_summary(self) -> pd.DataFrame:
        """Returns descriptive statistics (mean, std) for each cohort."""
        if self.df is None:
            self.load_dataset()

        summary = self.df.groupby("Group").agg({
            "Delta_T_C": ["count", "mean", "std"],
            "NDVI_Mean": ["mean", "std"],
            "Moisture_Pct": ["mean", "std"],
            "Weight_g": ["mean", "std"]
        })
        return summary

    def compare_groups(self, group_a: str = "Контроль", group_b: str = "Засуха") -> Dict[str, Any]:
        """
        Compares two cohorts using Student's t-test and Mann-Whitney U test
        for Delta_T and NDVI.
        """
        if self.df is None:
            self.load_dataset()

        sub_a = self.df[self.df["Group"] == group_a]
        sub_b = self.df[self.df["Group"] == group_b]

        if len(sub_a) == 0 or len(sub_b) == 0:
            raise ValueError(f"Cohort {group_a} or {group_b} has no records in dataset")

        # Delta T (Welch t-test for unequal variances + two-sided Mann-Whitney U)
        t_dt, p_dt_t = stats.ttest_ind(sub_a["Delta_T_C"].dropna(), sub_b["Delta_T_C"].dropna(), equal_var=False)
        u_dt, p_dt_u = stats.mannwhitneyu(sub_a["Delta_T_C"].dropna(), sub_b["Delta_T_C"].dropna(), alternative="two-sided")

        # NDVI (Welch t-test + two-sided Mann-Whitney U)
        t_ndvi, p_ndvi_t = stats.ttest_ind(sub_a["NDVI_Mean"].dropna(), sub_b["NDVI_Mean"].dropna(), equal_var=False)
        u_ndvi, p_ndvi_u = stats.mannwhitneyu(sub_a["NDVI_Mean"].dropna(), sub_b["NDVI_Mean"].dropna(), alternative="two-sided")

        return {
            "group_a": group_a, "group_b": group_b,
            "n_a": len(sub_a), "n_b": len(sub_b),
            "delta_t": {
                "mean_a": float(sub_a["Delta_T_C"].mean()),
                "mean_b": float(sub_b["Delta_T_C"].mean()),
                "t_stat": float(t_dt), "p_ttest": float(p_dt_t), "p_welch": float(p_dt_t),
                "u_stat": float(u_dt), "p_mannwhitney": float(p_dt_u),
            },
            "ndvi": {
                "mean_a": float(sub_a["NDVI_Mean"].mean()),
                "mean_b": float(sub_b["NDVI_Mean"].mean()),
                "t_stat": float(t_ndvi), "p_ttest": float(p_ndvi_t), "p_welch": float(p_ndvi_t),
                "u_stat": float(u_ndvi), "p_mannwhitney": float(p_ndvi_u),
            }
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stats_runner = ExperimentStatistics()
    try:
        df = stats_runner.load_dataset()
        print("=== СВОДНЫЕ ДАННЫЕ РЕАЛЬНОГО ЭКСПЕРИМЕНТА ===")
        print(stats_runner.get_cohort_summary())
        print("\n=== СРАВНЕНИЕ: КОНТРОЛЬ VS ЗАСУХА ===")
        comp = stats_runner.compare_groups("Контроль", "Засуха")
        print(f"Delta_T: Контроль={comp['delta_t']['mean_a']:.2f}°C, Засуха={comp['delta_t']['mean_b']:.2f}°C (p={comp['delta_t']['p_ttest']:.4f})")
        print(f"NDVI: Контроль={comp['ndvi']['mean_a']:.3f}, Засуха={comp['ndvi']['mean_b']:.3f} (p={comp['ndvi']['p_ttest']:.4f})")
    except Exception as e:
        logger.error("Error processing dataset: %s", e)
