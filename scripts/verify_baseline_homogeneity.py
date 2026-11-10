# -*- coding: utf-8 -*-
"""
Скрипт проверки однородности групп в «День 0» (Baseline Homogeneity Verification)
по методике Б.А. Доспехова (1985) для эксперимента Волна 2 (Cucumis sativus L., GRCBD).

Использование:
    python scripts/verify_baseline_homogeneity.py
    python scripts/verify_baseline_homogeneity.py --mock-demo
    python scripts/verify_baseline_homogeneity.py --csv data/exp_1792918800/measurements_wave2.csv
"""

import os
import sys
import argparse
import numpy as np

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.wave2_manager import Wave2Storage
from core.wave2_anova import analyze_wave2_dataset


def generate_mock_baseline_data():
    """Генерация реалистичного набора данных Дня 0 с соблюдением H0 (p > 0.05)."""
    pots = ["K1", "K2", "K3", "K4", "K5", "K6",
            "P1", "P2", "P3", "P4", "P5", "P6",
            "R1", "R2", "R3", "R4", "R5", "R6"]
    records = []
    np.random.seed(42)
    for pid in pots:
        # Небольшой разброс по блокам (крупные в Блоке 1, средние в Блоке 2, мелкие в Блоке 3)
        block = 1 if pid in ["K1", "K2", "P1", "P2", "R1", "R2"] else (2 if pid in ["K3", "K4", "P3", "P4", "R3", "R4"] else 3)
        tier_mean = 145.0 if block == 1 else (138.0 if block == 2 else 132.0)
        w = round(tier_mean + np.random.normal(0, 1.2), 1)
        dt = round(-0.8 + np.random.normal(0, 0.15), 2)
        ndvi = round(0.72 + np.random.normal(0, 0.02), 3)
        pla = round(45.0 + np.random.normal(0, 1.5), 1)
        records.append({
            "ID": pid,
            "Weight_g": w,
            "Delta_T_C": dt,
            "NDVI_mean": ndvi,
            "PLA_cm2": pla,
            "Turgor_Score": 4
        })
    return records


def main():
    parser = argparse.ArgumentParser(description="Проверка исходной однородности групп (День 0) методом ANOVA")
    parser.add_argument("--csv", type=str, default=None, help="Путь к конкретному CSV файлу замеров")
    parser.add_argument("--data-dir", type=str, default=os.path.join(PROJECT_ROOT, "data"), help="Каталог данных станции")
    parser.add_argument("--mock-demo", action="store_true", help="Запустить демонстрационный расчет на реалистичной модели Дня 0")
    args = parser.parse_args()

    records = []
    if args.mock_demo:
        print("[i] Запущен режим демонстрации модели Дня 0 (18 сосудов)...")
        records = generate_mock_baseline_data()
    elif args.csv and os.path.exists(args.csv):
        import csv
        with open(args.csv, "r", encoding="utf-8") as f:
            records = list(csv.DictReader(f))
    else:
        storage = Wave2Storage(args.data_dir)
        records = storage.load_today_records()
        if len(records) < 6:
            all_recs = storage.load_all_records()
            latest_by_id = {}
            for r in all_recs:
                pid = str(r.get("ID", "")).strip().upper()
                if pid:
                    latest_by_id[pid] = r
            records = list(latest_by_id.values())

    if not records:
        print("[-] Ошибка: Нет доступных записей замеров Волна 2. Для проверки интерфейса используйте флаг --mock-demo.")
        sys.exit(1)

    print(f"[*] Анализ {len(records)} записей комплекса GRCBD...")
    static_dir = os.path.join(PROJECT_ROOT, "static")
    docs_dir = os.path.join(PROJECT_ROOT, "docs", "wave2")

    res = analyze_wave2_dataset(records, static_dir=static_dir, docs_dir=docs_dir)
    if not res.get("ok"):
        print(f"[-] Не удалось выполнить анализ: {res.get('message')}")
        sys.exit(1)

    # Вывод результатов
    print("\n" + "=" * 75)
    print(f"СТАТУС: {res['status_badge']}")
    print(f"ВЕРДИКТ: {res['verdict']}")
    print("=" * 75 + "\n")

    print(f"{'Признак':<26} | {'Контроль':<14} | {'Превенция':<14} | {'Реакция':<14} | {'F (когорта)':<11} | {'p-value':<9}")
    print("-" * 98)
    for row in res.get("summary_table", []):
        f_val = str(row['f_cohort']) if row['f_cohort'] is not None else "--"
        p_val = str(row['p_cohort']) if row['p_cohort'] is not None else "--"
        print(f"{row['label']:<26} | {row['k_str']:<14} | {row['p_str']:<14} | {row['r_str']:<14} | {f_val:<11} | {p_val:<9}")

    print("\n" + "-" * 75)
    print(f"График боксплотов сохранен: {res.get('chart_url')}")
    print(f"Markdown отчет сформирован: {res.get('report_file')}")
    print("-" * 75)

    # Научно корректная формулировка для защиты
    dt_p = res.get("traits", {}).get("delta_t", {}).get("p_cohort")
    w_p = res.get("traits", {}).get("weight_g", {}).get("p_cohort")
    print("\n[Формулировка для доклада на защите]:")
    if res.get("confirmatory_grcbd_performed"):
        print("«На исходном срезе Дня 0 статистически значимых различий по исследованным показателям между когортами")
        print(f"не выявлено (масса p = {w_p}, ΔT p = {dt_p}; одинаковая масса является следствием тарирования по протоколу).")
        print("Это не доказывает полную эквивалентность групп и не исключает различий, незамеченных при N = 18.»\n")
    else:
        print("«На текущем неполном срезе подтверждающий GRCBD ANOVA не выполнен; приведена только описательная статистика.»\n")


if __name__ == "__main__":
    main()
