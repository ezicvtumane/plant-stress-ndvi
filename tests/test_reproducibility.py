# -*- coding: utf-8 -*-
"""
Тесты воспроизводимости окружения, CI-конфигурации и read-only анализа реальных данных.
"""

import hashlib
import importlib
import re
from pathlib import Path

from core.wave2_anova import analyze_wave2_dataset
from core.wave2_manager import Wave2Storage
from src.statistical_analysis import ExperimentStatistics

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _parse_requirements_names(req_path: Path) -> set[str]:
    """Извлекает нормализованные имена PyPI-пакетов из requirements.txt."""
    names: set[str] = set()
    for raw_line in req_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        pkg_part = line.split(";", 1)[0].strip()
        pkg_name = re.split(r"[<>=!~\[ ]", pkg_part, maxsplit=1)[0].strip()
        if pkg_name:
            names.add(pkg_name.lower().replace("_", "-"))
    return names


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_core_dependencies_declared_and_importable():
    """Все базовые научные, веб и тестовые зависимости, включая Pillow, должны быть в requirements.txt."""
    declared = _parse_requirements_names(PROJECT_ROOT / "requirements.txt")
    required_pkgs = {
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "opencv-python",
        "pillow",
        "fastapi",
        "uvicorn",
        "jinja2",
        "python-multipart",
        "pydantic",
        "pydantic-settings",
        "numexpr",
        "pytesseract",
        "pytest",
        "httpx",
    }
    missing = sorted(required_pkgs - declared)
    assert not missing, f"В requirements.txt отсутствуют зависимости: {missing}"

    for mod_name in ("PIL", "cv2", "fastapi", "numpy", "scipy", "pandas", "matplotlib", "pytest", "httpx"):
        importlib.import_module(mod_name)


def test_ci_workflow_covers_audit_branches_and_reproducibility():
    """CI workflow должен запускаться на main и fix/**, использовать headless MPL и проверять чистоту дерева."""
    ci_text = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "main" in ci_text
    assert "fix/**" in ci_text
    assert "MPLBACKEND: Agg" in ci_text
    assert "pip install -r requirements.txt" in ci_text
    assert "pip check" in ci_text
    assert "python -m pytest tests/ -v" in ci_text
    assert "git diff --exit-code" in ci_text


def test_committed_wave1_and_wave2_csv_readonly_reproducible(tmp_path):
    """Загрузка и анализ исторических CSV не должны изменять файлы данных на диске."""
    wave1_csv = PROJECT_ROOT / "data" / "measurements.csv"
    wave2_csv = PROJECT_ROOT / "data" / "experiments" / "exp_1792918800" / "measurements_wave2.csv"
    assert wave1_csv.exists()
    assert wave2_csv.exists()

    h1_before = _sha256_file(wave1_csv)
    h2_before = _sha256_file(wave2_csv)

    stats_engine = ExperimentStatistics(data_file=str(wave1_csv))
    df1 = stats_engine.load_dataset()
    summary1 = stats_engine.get_cohort_summary()
    assert len(df1) == 55
    assert len(summary1) >= 5

    storage = Wave2Storage(str(PROJECT_ROOT / "data"))
    recs2 = storage.load_all_records()
    assert len(recs2) >= 18
    latest_by_id = {str(r["ID"]).strip().upper(): r for r in recs2 if str(r.get("ID", "")).strip()}
    plant_records = [r for pid, r in latest_by_id.items() if pid != "X0"]
    res2 = analyze_wave2_dataset(
        plant_records,
        static_dir=str(tmp_path / "static"),
        docs_dir=str(tmp_path / "docs"),
    )
    assert res2["ok"] is True

    assert _sha256_file(wave1_csv) == h1_before
    assert _sha256_file(wave2_csv) == h2_before
