# -*- coding: utf-8 -*-
"""
Изоляция путей хранилища (data, static, docs/wave2) для тестов FastAPI.
Гарантирует, что запуск pytest никогда не затрагивает реальные CSV-журналы
и экспериментальные архивы в репозитории.
"""

import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.experiments as core_experiments
from core.station_state import reset_batch_state
import web_station


@pytest.fixture(autouse=True)
def isolated_station_storage(tmp_path, monkeypatch):
    """Перенаправляет все операции записи web_station во временную директорию tmp_path."""
    tmp_data = tmp_path / "data"
    tmp_static = tmp_path / "static"
    tmp_docs = tmp_path / "docs"
    tmp_wave2_docs = tmp_docs / "wave2"
    tmp_th_cache = tmp_static / "uti_cache"

    for d in (tmp_data, tmp_static, tmp_docs, tmp_wave2_docs, tmp_th_cache):
        d.mkdir(parents=True, exist_ok=True)

    (tmp_data / "calibrated_k_bal.txt").write_text("1.150\n", encoding="utf-8")
    csv_log = tmp_data / "measurements.csv"
    csv_log.write_text(
        ",".join(core_experiments.CSV_HEADER) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(web_station, "DATA_DIR", str(tmp_data))
    monkeypatch.setattr(web_station, "CALIBRATION_FILE", str(tmp_data / "calibrated_k_bal.txt"))
    monkeypatch.setattr(web_station, "STATIC_DIR", str(tmp_static))
    monkeypatch.setattr(web_station, "DOCS_DIR", str(tmp_docs))
    monkeypatch.setattr(web_station, "WAVE2_DOCS_DIR", str(tmp_wave2_docs))
    monkeypatch.setattr(web_station, "TH_CACHE_DIR", str(tmp_th_cache))
    monkeypatch.setattr(web_station, "CSV_LOG", str(csv_log))
    monkeypatch.setattr(core_experiments, "_exp_manager", None)

    exp_mgr = core_experiments.get_experiment_manager(str(tmp_data))
    reg = exp_mgr._load_registry()
    if not any(e.get("id") == "exp_1791463544" for e in reg.get("experiments", [])):
        exp1_dir = tmp_data / "experiments" / "exp_1791463544"
        (exp1_dir / "images").mkdir(parents=True, exist_ok=True)
        (exp1_dir / "measurements.csv").write_text(
            ",".join(core_experiments.CSV_HEADER) + "\n",
            encoding="utf-8",
        )
        reg["experiments"].append({
            "id": "exp_1791463544",
            "name": "Серия 1 (тест)",
            "plant": "Томат",
            "created_at": "2026-10-08 12:00",
            "description": "Изолированный тестовый эксперимент Серии 1",
            "folder": "exp_1791463544",
        })
        reg["active_id"] = "exp_1791463544"
        exp_mgr._save_registry(reg)

    web_station.ensure_wave2_registered(str(tmp_data))
    reset_batch_state("batch5")
    try:
        yield tmp_path
    finally:
        core_experiments._exp_manager = None
        reset_batch_state("batch5")
