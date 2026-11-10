# -*- coding: utf-8 -*-
"""
Тесты сверки целостности массивов биомассы Серии 1 (День 11) и согласованности документации.
"""

import csv
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_biomass_arrays():
    wide_root = PROJECT_ROOT / "data" / "harvest_fresh_biomass.csv"
    wide_exp = PROJECT_ROOT / "data" / "experiments" / "exp_1791463544" / "harvest_fresh_biomass.csv"
    long_path = PROJECT_ROOT / "data" / "harvest_biomass_day11.csv"

    assert wide_root.read_text(encoding="utf-8") == wide_exp.read_text(encoding="utf-8")

    rows_wide = list(csv.DictReader(wide_root.read_text(encoding="utf-8").splitlines()))
    rows_long = list(csv.DictReader(long_path.read_text(encoding="utf-8").splitlines()))
    col_map = {
        "K1": "control_k1",
        "K2": "osmotic_k2",
        "K3": "drought_k3",
        "K4": "prevention_k4",
        "K5": "reaction_k5",
    }
    arrays = {}
    for cid, wide_col in col_map.items():
        wide_vals = [float(r[wide_col]) for r in rows_wide]
        long_vals = [float(r["Fresh_Weight_g"]) for r in rows_long if r["Cohort_ID"] == cid]
        assert wide_vals == long_vals, f"Расхождение ячеек {cid} между wide и long CSV"
        arrays[cid] = np.array(long_vals, dtype=float)
    return arrays


def test_series1_biomass_totals_medians_and_deltas():
    """Первичные CSV биомассы Дня 11 должны сходиться до сотых грамма."""
    arrays = _load_biomass_arrays()
    expected_sums = {"K1": 4.25, "K4": 3.87, "K2": 3.15, "K5": 2.85, "K3": 1.83}
    expected_medians = {"K1": 0.47, "K4": 0.32, "K2": 0.36, "K5": 0.38, "K3": 0.19}

    for cid, exp_sum in expected_sums.items():
        assert round(float(arrays[cid].sum()), 2) == exp_sum
        assert round(float(np.median(arrays[cid])), 3) == expected_medians[cid]

    delta_k3_k1_pct = (arrays["K3"].sum() - arrays["K1"].sum()) / arrays["K1"].sum() * 100.0
    delta_k4_k5_pct = (arrays["K4"].sum() - arrays["K5"].sum()) / arrays["K5"].sum() * 100.0
    assert delta_k3_k1_pct == np.round(-56.94, 2) or abs(delta_k3_k1_pct - (-56.94)) < 0.02
    assert abs(delta_k4_k5_pct - 35.79) < 0.02


def test_validation_scales_are_subsamples_of_fresh_biomass():
    """Контрольное взвешивание 0.35–0.73 г соответствует ~16–20% (воздушно-подсушенные пробы) от FW."""
    arrays = _load_biomass_arrays()
    scales_path = PROJECT_ROOT / "data" / "harvest_validation_scales_day11.csv"
    rows = list(csv.DictReader(scales_path.read_text(encoding="utf-8").splitlines()))
    scale_map = {r["Cohort_ID"]: float(r["Fresh_Weight_g"]) for r in rows}

    assert scale_map == {"K1": 0.73, "K2": 0.55, "K3": 0.35, "K4": 0.65, "K5": 0.49}
    for cid, val in scale_map.items():
        ratio = val / float(arrays[cid].sum())
        assert 0.15 <= ratio <= 0.21, f"{cid}: доля {ratio:.3f} вне ожидаемого диапазона подсушенных проб"


def test_docs_free_of_known_biomass_typos():
    """Документация не должна содержать старых опечаток по биомассе (-45.9%, 2.95 г для К5, -32.7% от К4)."""
    qa_text = (PROJECT_ROOT / "docs" / "DEFENSE_QA_GUIDE.md").read_text(encoding="utf-8")
    album_text = (PROJECT_ROOT / "docs" / "PHOTO_ALBUM.md").read_text(encoding="utf-8")
    media_pea_text = (PROJECT_ROOT / "media" / "experiment_series_pea" / "README.md").read_text(encoding="utf-8")
    stat_text = (PROJECT_ROOT / "docs" / "STATISTICAL_ANALYSIS_SERIES1.md").read_text(encoding="utf-8")

    assert "2.95 г" not in qa_text
    assert "45.9%" not in qa_text
    assert "56.9%" in qa_text
    assert "потеря -32.7% массы относительно превенции" not in album_text
    assert "потеря 32.7% массы от К4" not in media_pea_text
    for stale_med in ("| 0.480 |", "| 0.350 |", "| 0.340 |", "| 0.160 |"):
        assert stale_med not in stat_text
