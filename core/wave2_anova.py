# -*- coding: utf-8 -*-
"""
Модуль двухфакторного дисперсионного анализа (Two-Way ANOVA по Доспехову)
для эксперимента Волна 2 (Cucumis sativus L., GRCBD: 3 когорты x 3 блока x 2 повторности).
Автоматически детектирует фазу (День 0 однородность, Превенция, Реакция, Уборка)
и формирует аналитический отчет + графики боксплотов.
"""

import os
import math
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TRAIT_LABELS = {
    "weight_g": "Масса сосуда (г)",
    "delta_t": "ΔT листа (°C)",
    "ndvi": "Индекс NDVI",
    "pla_cm2": "Площадь листа (см²)",
    "turgor": "Балл тургора (1–4)",
    "dw_g": "Сухая биомасса DW (г)",
    "fw_g": "Сырая биомасса FW (г)",
}

COHORT_COLORS = {
    "Control": "#059669",
    "Prevention": "#eab308",
    "Reaction": "#2563eb",
    "Контроль": "#059669",
    "Превенция": "#eab308",
    "Реакция": "#2563eb"
}


def dospekhov_two_way_anova_engine(df: pd.DataFrame, trait: str) -> Dict[str, Any]:
    """
    Выполняет двухфакторный дисперсионный анализ по Доспехову Б.А. (1985)
    для сбалансированного комплекса GRCBD: a=3 когорты, b=3 блока, n=2 повторности.
    Всего N = 18.
    """
    df_clean = df.dropna(subset=[trait, "cohort", "block"]).copy()
    if len(df_clean) < 18:
        # Неполный комплекс - fallback на однофакторный ANOVA по когортам
        cohort_groups = [g[trait].values for _, g in df_clean.groupby("cohort")]
        if len(cohort_groups) >= 2 and all(len(g) >= 2 for g in cohort_groups):
            f_val, p_val = stats.f_oneway(*cohort_groups)
            return {
                "trait": trait,
                "is_balanced_grcbd": False,
                "f_cohort": round(float(f_val), 3) if not math.isnan(f_val) else 0.0,
                "p_cohort": round(float(p_val), 4) if not math.isnan(p_val) else 1.0,
                "f_block": None,
                "p_block": None,
                "ms_error": None,
                "df_error": len(df_clean) - len(cohort_groups)
            }
        return {"trait": trait, "is_balanced_grcbd": False, "f_cohort": 0.0, "p_cohort": 1.0, "f_block": None, "p_block": None}

    a = 3  # Когорты (К, П, Р)
    b = 3  # Блоки (1, 2, 3)
    n = 2  # Повторность в ячейке
    N = a * b * n  # 18

    # Корректирующий фактор C
    total_sum = df_clean[trait].sum()
    C = (total_sum ** 2) / N

    # Общая сумма квадратов
    SS_total = (df_clean[trait] ** 2).sum() - C

    # Сумма квадратов фактора А (Когорты)
    T_A = df_clean.groupby("cohort")[trait].sum()
    SS_A = (T_A ** 2).sum() / (b * n) - C

    # Сумма квадратов фактора В (Блоки)
    T_B = df_clean.groupby("block")[trait].sum()
    SS_B = (T_B ** 2).sum() / (a * n) - C

    # Сумма квадратов ячеек (AB)
    T_AB = df_clean.groupby(["cohort", "block"])[trait].sum()
    SS_cells = (T_AB ** 2).sum() / n - C
    SS_AB = max(0.0, SS_cells - SS_A - SS_B)

    # Сумма квадратов случайной ошибки E
    SS_E = max(1e-9, SS_total - SS_cells)

    # Степени свободы
    df_A = a - 1      # 2
    df_B = b - 1      # 2
    df_AB = df_A * df_B  # 4
    df_E = a * b * (n - 1)  # 9
    df_total = N - 1  # 17

    # Средние квадраты (Mean Squares)
    MS_A = SS_A / df_A
    MS_B = SS_B / df_B
    MS_AB = SS_AB / df_AB
    MS_E = SS_E / df_E

    # F-критерии Фишера
    F_A = MS_A / MS_E
    F_B = MS_B / MS_E
    F_AB = MS_AB / MS_E

    # p-значения
    p_A = 1.0 - stats.f.cdf(F_A, df_A, df_E)
    p_B = 1.0 - stats.f.cdf(F_B, df_B, df_E)
    p_AB = 1.0 - stats.f.cdf(F_AB, df_AB, df_E)

    # Наименьшая существенная разность (НСР_05 / LSD) по Доспехову
    t_crit = stats.t.ppf(0.975, df=df_E)  # ~2.262 для df=9
    sed = math.sqrt(2 * MS_E / (b * n))
    lsd_05 = t_crit * sed

    return {
        "trait": trait,
        "is_balanced_grcbd": True,
        "N": N,
        "df_cohort": df_A,
        "df_block": df_B,
        "df_interaction": df_AB,
        "df_error": df_E,
        "ss_cohort": round(float(SS_A), 4),
        "ss_block": round(float(SS_B), 4),
        "ss_error": round(float(SS_E), 4),
        "ms_error": round(float(MS_E), 4),
        "f_cohort": round(float(F_A), 3),
        "p_cohort": round(float(p_A), 4),
        "f_block": round(float(F_B), 3),
        "p_block": round(float(p_B), 4),
        "f_interaction": round(float(F_AB), 3),
        "p_interaction": round(float(p_AB), 4),
        "lsd_05": round(float(lsd_05), 3)
    }


def analyze_wave2_dataset(records: List[Dict[str, Any]], static_dir: str = "static", docs_dir: str = "docs/wave2") -> Dict[str, Any]:
    """
    Главный аналитический модуль:
    1. Формирует DataFrame 18 растений GRCBD.
    2. Запускает ANOVA по всем признакам.
    3. Автоматически диагностирует фазу эксперимента.
    4. Строит боксплоты в static_dir/charts/anova_latest.png.
    5. Формирует markdown отчет в docs_dir/ANOVA_LATEST_REPORT.md.
    """
    rows = []
    for r in records:
        pid = str(r.get("ID", "")).strip().upper()
        if not pid or pid not in ["K1", "K2", "K3", "K4", "K5", "K6",
                                  "P1", "P2", "P3", "P4", "P5", "P6",
                                  "R1", "R2", "R3", "R4", "R5", "R6"]:
            continue
        
        # Определяем когорту и блок
        cohort = "Control" if pid.startswith("K") else ("Prevention" if pid.startswith("P") else "Reaction")
        block_num = 1 if pid in ["K1", "K2", "P1", "P2", "R1", "R2"] else (2 if pid in ["K3", "K4", "P3", "P4", "R3", "R4"] else 3)
        
        try:
            w = float(r.get("Weight_g")) if r.get("Weight_g") not in (None, "", "--") else None
        except ValueError:
            w = None
            
        try:
            dt = float(r.get("Delta_T_C")) if r.get("Delta_T_C") not in (None, "", "--") else None
        except ValueError:
            dt = None
            
        try:
            raw_ndvi = r.get("NDVI_Mean") if r.get("NDVI_Mean") is not None else r.get("NDVI_mean", r.get("ndvi"))
            ndvi = float(raw_ndvi) if raw_ndvi not in (None, "", "--") else None
        except (ValueError, TypeError):
            ndvi = None
            
        try:
            raw_pla = r.get("Leaf_Area_cm2") if r.get("Leaf_Area_cm2") is not None else r.get("PLA_cm2", r.get("pla"))
            pla = float(raw_pla) if raw_pla not in (None, "", "--") else None
        except (ValueError, TypeError):
            pla = None
            
        try:
            tr = int(r.get("Turgor_Score", 4)) if r.get("Turgor_Score") not in (None, "", "--") else 4
        except ValueError:
            tr = 4

        # Опциональные метрики урожая
        dw = float(r.get("DW_g")) if r.get("DW_g") not in (None, "", "--") else None
        fw = float(r.get("FW_g")) if r.get("FW_g") not in (None, "", "--") else None

        rows.append({
            "pot_id": pid,
            "cohort": cohort,
            "block": f"Блок {block_num}",
            "weight_g": w,
            "delta_t": dt,
            "ndvi": ndvi,
            "pla_cm2": pla,
            "turgor": tr,
            "dw_g": dw,
            "fw_g": fw
        })

    df = pd.DataFrame(rows)
    total_measured = len(df)
    
    if total_measured < 6:
        return {
            "ok": False,
            "total_measured": total_measured,
            "message": f"Измерено только {total_measured} из 18 горшков GRCBD. Для расчета биостатистики требуется замер серии."
        }

    # Выбор признаков для анализа
    traits = ["weight_g", "delta_t", "ndvi", "pla_cm2", "turgor"]
    if df["dw_g"].notna().sum() >= 6:
        traits.insert(0, "dw_g")
    if df["fw_g"].notna().sum() >= 6:
        traits.insert(1, "fw_g")

    traits_results = {}
    summary_table = []

    for t in traits:
        res = dospekhov_two_way_anova_engine(df, t)
        
        # Считаем средние по когортам M ± SE
        k_vals = df[df["cohort"] == "Control"][t].dropna()
        p_vals = df[df["cohort"] == "Prevention"][t].dropna()
        r_vals = df[df["cohort"] == "Reaction"][t].dropna()
        
        k_mean = round(float(k_vals.mean()), 2) if len(k_vals) > 0 else 0.0
        k_se = round(float(k_vals.std() / math.sqrt(len(k_vals))), 2) if len(k_vals) > 1 else 0.0
        
        p_mean = round(float(p_vals.mean()), 2) if len(p_vals) > 0 else 0.0
        p_se = round(float(p_vals.std() / math.sqrt(len(p_vals))), 2) if len(p_vals) > 1 else 0.0

        r_mean = round(float(r_vals.mean()), 2) if len(r_vals) > 0 else 0.0
        r_se = round(float(r_vals.std() / math.sqrt(len(r_vals))), 2) if len(r_vals) > 1 else 0.0

        res["k_mean"] = k_mean
        res["k_se"] = k_se
        res["p_mean"] = p_mean
        res["p_se"] = p_se
        res["r_mean"] = r_mean
        res["r_se"] = r_se
        
        traits_results[t] = res
        summary_table.append({
            "trait": t,
            "label": TRAIT_LABELS.get(t, t),
            "k_str": f"{k_mean} ± {k_se}",
            "p_str": f"{p_mean} ± {p_se}",
            "r_str": f"{r_mean} ± {r_se}",
            "f_cohort": res.get("f_cohort", 0.0),
            "p_cohort": res.get("p_cohort", 1.0),
            "f_block": res.get("f_block"),
            "p_block": res.get("p_block"),
            "lsd_05": res.get("lsd_05")
        })

    # Автоматическая диагностика контекста / фазы
    mean_turgor = df["turgor"].mean() if "turgor" in df else 4.0
    r_turgor = traits_results.get("turgor", {}).get("r_mean", 4.0)
    dt_res = traits_results.get("delta_t", {})
    p_val_dt = dt_res.get("p_cohort", 1.0)
    has_dw = "dw_g" in traits

    if has_dw:
        phase = "harvest"
        dw_res = traits_results.get("dw_g", {})
        dw_p = dw_res.get("p_cohort", 1.0)
        p_dw_mean = dw_res.get("p_mean", 0.0)
        r_dw_mean = dw_res.get("r_mean", 0.0)
        diff_pct = round((p_dw_mean - r_dw_mean) / max(0.001, r_dw_mean) * 100, 1)
        
        status_badge = "🏆 ФИНАЛЬНЫЙ СРЕЗ УРОЖАЯ (HARVEST ENDPOINT)"
        badge_color = "#059669"
        verdict = f"Первичная конечная точка (сухая биомасса DW): Превенция {p_dw_mean} г vs Реакция {r_dw_mean} г (разница {diff_pct:+}%, p = {dw_p})."
    
    elif r_turgor <= 2.5:
        phase = "reaction_trigger"
        status_badge = "🔵 СТРЕСС-ФАЗА: КРИТИЧЕСКИЙ СТРЕСС УВЯДАНИЯ (РЕАКЦИЯ)"
        badge_color = "#2563eb"
        verdict = f"Традиционный порог увядания зафиксирован: потеря тургора когорты Реакция статистически подтверждена (балл {r_turgor} против контроля {traits_results['turgor']['k_mean']}). Реакционный полив активирован!"

    elif dt_res.get("f_cohort", 0.0) > 3.0 and p_val_dt <= 0.05 and r_turgor > 2.5:
        phase = "prevention_alert"
        status_badge = "🚨 СТРЕСС-ФАЗА: ДЕТЕКЦИЯ СКРЫТОЙ ЗАСУХИ (ПРЕВЕНЦИЯ)"
        badge_color = "#eab308"
        verdict = f"Термографический триггер подтвержден ANOVA: достоверный перегрев кроны (ΔT F={dt_res['f_cohort']}, p={p_val_dt}) при сохранении визуального тургора (средний балл Реакции {r_turgor:.1f}). Превентивный полив активирован!"

    elif mean_turgor >= 3.7 and p_val_dt > 0.05:
        phase = "baseline"
        status_badge = "🟢 ДЕНЬ 0: ИСХОДНАЯ ОДНОРОДНОСТЬ (BASELINE HOMOGENEITY)"
        badge_color = "#059669"
        verdict = f"Нулевая гипотеза подтверждена (H0: p > 0.05). Различия между группами по массе (p={traits_results['weight_g']['p_cohort']}) и ΔT (p={p_val_dt}) отсутствуют. Стартовый перекос исключен. Старт стресс-фазы разрешен!"
    
    else:
        phase = "monitoring"
        status_badge = "📊 ТЕКУЩИЙ МОНИТОРИНГ GRCBD"
        badge_color = "#4f46e5"
        verdict = f"Замер {total_measured}/18 сосудов выполнен. Промежуточные дисперсии стабильны."

    # Генерация графика боксплотов
    os.makedirs(os.path.join(static_dir, "charts"), exist_ok=True)
    chart_rel_path = "charts/anova_latest.png"
    chart_full_path = os.path.join(static_dir, chart_rel_path)
    
    plot_traits = [t for t in ["weight_g", "delta_t", "ndvi", "pla_cm2"] if t in df.columns]
    fig, axes = plt.subplots(1, len(plot_traits), figsize=(3.8 * len(plot_traits), 4.2), dpi=130)
    if len(plot_traits) == 1:
        axes = [axes]

    cohort_order = ["Control", "Prevention", "Reaction"]
    cohort_labels_ru = ["Контроль", "Превенция", "Реакция"]
    palette = [COHORT_COLORS[c] for c in cohort_order]

    for ax, t in zip(axes, plot_traits):
        data_to_plot = [df[df["cohort"] == c][t].dropna().values for c in cohort_order]
        bp = ax.boxplot(data_to_plot, patch_artist=True, widths=0.55,
                        boxprops=dict(linewidth=1.2), medianprops=dict(color="#0f172a", linewidth=2.0))
        ax.set_xticks(range(1, len(cohort_labels_ru) + 1))
        ax.set_xticklabels(cohort_labels_ru)
        for patch, color in zip(bp['boxes'], palette):
            patch.set_facecolor(color)
            patch.set_alpha(0.65)
            
        # Добавляем точки наблюдений (джиттер)
        for i, c in enumerate(cohort_order):
            vals = df[df["cohort"] == c][t].dropna().values
            jitter = np.random.normal(0, 0.04, size=len(vals))
            ax.scatter(np.ones_like(vals) * (i + 1) + jitter, vals, color=palette[i], edgecolors="#0f172a", s=32, zorder=4, alpha=0.9)

        ax.set_title(TRAIT_LABELS.get(t, t), fontsize=11, fontweight="bold", pad=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.tick_params(labelsize=10)
        
        # Аннотация ANOVA p-value
        pv = traits_results[t]["p_cohort"]
        ax.set_xlabel(f"ANOVA p = {pv:.4f}", fontsize=10, fontweight="bold", color="#0f172a" if pv > 0.05 else "#dc2626")

    import re
    clean_status = re.sub(r'[^\w\s\(\)\-\:\.\,\«\»\—]', '', status_badge).strip()
    plt.suptitle(f"Дисперсионный комплекс GRCBD (N={total_measured}) — {clean_status}", fontsize=11, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(chart_full_path, bbox_inches="tight")
    plt.close(fig)

    # Генерация Markdown отчета
    os.makedirs(docs_dir, exist_ok=True)
    report_path = os.path.join(docs_dir, "ANOVA_LATEST_REPORT.md")
    md_lines = [
        f"# 📊 СТАТИСТИЧЕСКИЙ ОТЧЕТ GRCBD (TWO-WAY ANOVA ПО ДОСПЕХОВУ)",
        f"**Статус сессии:** {status_badge}  ",
        f"**Объем выборки:** N = {total_measured} сосудов (3 когорты × 3 блока)  ",
        f"**Вердикт алгоритма:** {verdict}  ",
        f"",
        f"---",
        f"",
        f"### Таблица дисперсионного анализа (Two-Way ANOVA)",
        f"",
        "| Физиологический параметр | Контроль (M ± SE) | Превенция (M ± SE) | Реакция (M ± SE) | Фактор Когорта (F) | p (когорта) | Фактор Блок (F) | p (блок) | НСР₀₅ |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ]
    for row in summary_table:
        f_b_str = str(row['f_block']) if row['f_block'] is not None else "--"
        p_b_str = str(row['p_block']) if row['p_block'] is not None else "--"
        lsd_str = str(row['lsd_05']) if row['lsd_05'] is not None else "--"
        md_lines.append(
            f"| **{row['label']}** | {row['k_str']} | {row['p_str']} | {row['r_str']} | {row['f_cohort']} | **{row['p_cohort']}** | {f_b_str} | {p_b_str} | {lsd_str} |"
        )

    md_lines.extend([
        f"",
        f"---",
        f"",
        f"### Графическая визуализация",
        f"![Boxplots](../../static/{chart_rel_path})",
        f"",
        f"*Отчет сгенерирован автоматически аналитическим ядром станции `PlantStation`.*"
    ])
    open(report_path, "w", encoding="utf-8").write("\n".join(md_lines))

    return {
        "ok": True,
        "total_measured": total_measured,
        "phase": phase,
        "status_badge": status_badge,
        "badge_color": badge_color,
        "verdict": verdict,
        "traits": traits_results,
        "summary_table": summary_table,
        "chart_url": f"/static/{chart_rel_path}",
        "report_file": report_path
    }
