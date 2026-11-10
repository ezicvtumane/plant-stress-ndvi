# -*- coding: utf-8 -*-
"""
Модуль двухфакторного дисперсионного анализа (Two-Way ANOVA по Доспехову)
для эксперимента Волна 2 (Cucumis sativus L., GRCBD: 3 когорты x 3 блока x 2 повторности).
Автоматически детектирует фазу (День 0 однородность, Превенция, Реакция, Уборка)
и формирует аналитический отчет + графики боксплотов.
"""

import os
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from core.agronomic_rules import (
    parse_optional_turgor,
    evaluate_cohort_reaction_trigger,
    evaluate_cohort_prevention_trigger,
)

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


def _inspect_grcbd_balance(df_clean: pd.DataFrame) -> Tuple[bool, Optional[str]]:
    """Проверяет точное соответствие матрицы схеме GRCBD 3 когорты × 3 блока × 2 повторности (N=18)."""
    expected_cohorts = ("Control", "Prevention", "Reaction")
    expected_blocks = ("Блок 1", "Блок 2", "Блок 3")

    if len(df_clean) != 18:
        return False, f"Неполный комплекс: {len(df_clean)}/18 валидных наблюдений (выполнен 1-way ANOVA без учета блоков)"

    extra_cohorts = set(df_clean["cohort"].unique()) - set(expected_cohorts)
    if extra_cohorts:
        return False, f"Обнаружены внеплановые когорты {sorted(extra_cohorts)} (выполнен 1-way ANOVA)"

    counts = df_clean.groupby(["cohort", "block"]).size()
    unbalanced_cells = []
    for cohort in expected_cohorts:
        for block in expected_blocks:
            cnt = int(counts.get((cohort, block), 0))
            if cnt != 2:
                unbalanced_cells.append(f"{cohort}/{block}={cnt}")

    if unbalanced_cells:
        return False, f"Нарушен баланс ячеек 3×3×2 ({', '.join(unbalanced_cells)}; выполнен 1-way ANOVA без учета блоков)"
    return True, None


def dospekhov_two_way_anova_engine(df: pd.DataFrame, trait: str) -> Dict[str, Any]:
    """
    Выполняет двухфакторный дисперсионный анализ по Доспехову Б.А. (1985)
    для сбалансированного комплекса GRCBD: a=3 когорты, b=3 блока, n=2 повторности (N=18).
    При неполной/несбалансированной матрице явно переключается на однофакторный 1-way ANOVA
    либо описательную статистику с сохранением предупреждения в model_mode/model_label.
    """
    df_clean = df.dropna(subset=[trait, "cohort", "block"]).copy()
    if "pot_id" in df_clean.columns:
        df_clean = df_clean.drop_duplicates(subset=["pot_id"], keep="last").copy()

    is_balanced, balance_reason = _inspect_grcbd_balance(df_clean)
    if not is_balanced:
        cohort_groups = [g[trait].values for _, g in df_clean.groupby("cohort")]
        if len(cohort_groups) >= 2 and all(len(g) >= 2 for g in cohort_groups):
            f_val, p_val = stats.f_oneway(*cohort_groups)
            return {
                "trait": trait,
                "is_balanced_grcbd": False,
                "model_mode": "one_way_fallback",
                "model_label": "1-way ANOVA (неполн., без блоков)",
                "balance_note": balance_reason,
                "N": int(len(df_clean)),
                "f_cohort": round(float(f_val), 3) if not math.isnan(f_val) else 0.0,
                "p_cohort": round(float(p_val), 4) if not math.isnan(p_val) else 1.0,
                "f_block": None,
                "p_block": None,
                "ms_error": None,
                "df_error": int(len(df_clean) - len(cohort_groups)),
            }
        return {
            "trait": trait,
            "is_balanced_grcbd": False,
            "model_mode": "descriptive_only",
            "model_label": "Описательно (недостаточно данных для ANOVA)",
            "balance_note": balance_reason,
            "N": int(len(df_clean)),
            "f_cohort": 0.0,
            "p_cohort": 1.0,
            "f_block": None,
            "p_block": None,
        }

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
        "model_mode": "two_way_grcbd",
        "model_label": "Two-Way ANOVA (GRCBD 3×3×2)",
        "balance_note": None,
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
    latest_by_pot: Dict[str, Dict[str, Any]] = {}
    duplicate_pots_collapsed = 0
    for r in records:
        pid = str(r.get("ID", "")).strip().upper()
        if not pid or pid not in ["K1", "K2", "K3", "K4", "K5", "K6",
                                  "P1", "P2", "P3", "P4", "P5", "P6",
                                  "R1", "R2", "R3", "R4", "R5", "R6"]:
            continue
        if pid in latest_by_pot:
            duplicate_pots_collapsed += 1
        latest_by_pot[pid] = r

    rows = []
    for pid, r in latest_by_pot.items():
        
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
            
        tr = parse_optional_turgor(r.get("Turgor_Score"))

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

    def _cohort_mean_se(series: pd.Series) -> tuple:
        clean = series.dropna()
        if len(clean) == 0:
            return None, None, "--"
        m = round(float(clean.mean()), 2)
        se = round(float(clean.std() / math.sqrt(len(clean))), 2) if len(clean) > 1 else 0.0
        return m, se, f"{m} ± {se}"

    for t in traits:
        res = dospekhov_two_way_anova_engine(df, t)
        
        # Считаем средние по когортам M ± SE (только по непустым значениям, без подстановки 4 или 0)
        k_mean, k_se, k_str = _cohort_mean_se(df[df["cohort"] == "Control"][t])
        p_mean, p_se, p_str = _cohort_mean_se(df[df["cohort"] == "Prevention"][t])
        r_mean, r_se, r_str = _cohort_mean_se(df[df["cohort"] == "Reaction"][t])

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
            "k_str": k_str,
            "p_str": p_str,
            "r_str": r_str,
            "f_cohort": res.get("f_cohort", 0.0),
            "p_cohort": res.get("p_cohort", 1.0),
            "f_block": res.get("f_block"),
            "p_block": res.get("p_block"),
            "lsd_05": res.get("lsd_05"),
            "is_balanced_grcbd": res.get("is_balanced_grcbd", False),
            "model_mode": res.get("model_mode", "descriptive_only"),
            "model_label": res.get("model_label", ""),
            "balance_note": res.get("balance_note"),
        })

    # Автоматическая диагностика контекста / фазы (синхронизирована с кворумами и знаком ΔT)
    valid_turgor_series = df["turgor"].dropna() if "turgor" in df else pd.Series(dtype=float)
    r_valid_turgor = df[df["cohort"] == "Reaction"]["turgor"].dropna() if "turgor" in df else pd.Series(dtype=float)
    mean_turgor = round(float(valid_turgor_series.mean()), 2) if len(valid_turgor_series) > 0 else None
    r_turgor = round(float(r_valid_turgor.mean()), 2) if len(r_valid_turgor) > 0 else None
    r_eval = evaluate_cohort_reaction_trigger(
        df[df["cohort"] == "Reaction"]["turgor"].tolist() if "turgor" in df else []
    )

    dt_res = traits_results.get("delta_t", {})
    p_val_dt = dt_res.get("p_cohort", 1.0)
    k_dt_mean = dt_res.get("k_mean")
    p_dt_mean = dt_res.get("p_mean")
    p_dt_list = df[df["cohort"] == "Prevention"]["delta_t"].tolist() if "delta_t" in df else []
    p_ddts = [
        None if (val is None or pd.isna(val)) else (float(val) - k_dt_mean if k_dt_mean is not None else float(val))
        for val in p_dt_list
    ]
    p_eval = evaluate_cohort_prevention_trigger(p_ddts)
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
    
    elif r_eval["is_triggered"]:
        phase = "reaction_trigger"
        status_badge = "🔵 СТРЕСС-ФАЗА: КРИТИЧЕСКИЙ СТРЕСС УВЯДАНИЯ (РЕАКЦИЯ)"
        badge_color = "#2563eb"
        k_turgor_disp = traits_results['turgor']['k_mean'] if traits_results['turgor']['k_mean'] is not None else "--"
        verdict = (
            f"Триггер увядания сработал по кворуму ({r_eval['triggered_count']}/6 растений с тургором ≤ 2; "
            f"средний балл Реакции {r_turgor} против контроля {k_turgor_disp}). Реакционный полив активирован!"
        )

    elif (
        dt_res.get("f_cohort", 0.0) > 3.0
        and p_val_dt <= 0.05
        and k_dt_mean is not None
        and p_dt_mean is not None
        and p_dt_mean > k_dt_mean
        and p_eval["is_triggered"]
    ):
        phase = "prevention_alert"
        status_badge = "🚨 СТРЕСС-ФАЗА: ДЕТЕКЦИЯ СКРЫТОЙ ЗАСУХИ (ПРЕВЕНЦИЯ)"
        badge_color = "#eab308"
        r_disp = f"{r_turgor:.1f}" if r_turgor is not None else "--"
        verdict = (
            f"Термографический триггер подтвержден статистически и по кворуму ({p_eval['triggered_count']}/6 с ΔΔT ≥ +0.6°C): "
            f"перегрев Превенции ({p_dt_mean}°C против Контроля {k_dt_mean}°C; ΔT F={dt_res['f_cohort']}, p={p_val_dt}) "
            f"при сохранённом тургоре Реакции (балл {r_disp}). Превентивный полив активирован!"
        )

    elif mean_turgor is not None and len(valid_turgor_series) >= 12 and mean_turgor >= 3.7 and p_val_dt > 0.05:
        phase = "baseline"
        status_badge = "🟢 ДЕНЬ 0: ИСХОДНАЯ ОДНОРОДНОСТЬ (BASELINE HOMOGENEITY)"
        badge_color = "#059669"
        verdict = f"Нулевая гипотеза подтверждена (H0: p > 0.05). Различия между группами по массе (p={traits_results['weight_g']['p_cohort']}) и ΔT (p={p_val_dt}) отсутствуют. Стартовый перекос исключен. Старт стресс-фазы разрешен!"
    
    elif len(valid_turgor_series) < 6:
        phase = "incomplete_turgor"
        status_badge = "⚠️ НЕДОСТАТОЧНО ОЦЕНОК ТУРГОРА"
        badge_color = "#64748b"
        verdict = f"Замерено {total_measured}/18 сосудов, но валидные оценки тургора заполнены только у {len(valid_turgor_series)}/18. Пропуски сохранены как NaN и исключены из расчёта."

    else:
        phase = "monitoring"
        status_badge = "📊 ТЕКУЩИЙ МОНИТОРИНГ GRCBD"
        badge_color = "#4f46e5"
        verdict = f"Замер {total_measured}/18 сосудов выполнен (оценок тургора: {len(valid_turgor_series)}/18). Критерий триггера не достигнут; продолжается мониторинг."

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
        
        # Аннотация ANOVA p-value с явной маркировкой модели (2-way GRCBD vs 1-way)
        tr_res = traits_results[t]
        pv = tr_res["p_cohort"]
        if tr_res.get("is_balanced_grcbd"):
            xlabel = f"2-way ANOVA p = {pv:.4f}"
        elif tr_res.get("model_mode") == "one_way_fallback":
            xlabel = f"1-way p = {pv:.4f} (без блоков)"
        else:
            xlabel = "Описательно (без ANOVA)"
        ax.set_xlabel(xlabel, fontsize=10, fontweight="bold", color="#0f172a" if pv > 0.05 else "#dc2626")

    import re
    clean_status = re.sub(r'[^\w\s\(\)\-\:\.\,\«\»\—]', '', status_badge).strip()
    all_balanced = all(traits_results[t].get("is_balanced_grcbd") for t in traits)
    model_banner = (
        "Two-Way ANOVA (сбалансированный GRCBD 3×3×2, N=18)"
        if all_balanced
        else "Смешанный / неполный срез: признаки с <18 замерами рассчитаны как 1-way ANOVA без фактора Блок или описательно"
    )
    plt.suptitle(f"Мониторинг GRCBD (N={total_measured}) — {clean_status}", fontsize=11, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.14)
    fig.text(0.5, 0.01, f"Статистическая модель: {model_banner}", ha="center", fontsize=8.5, color="#475569")
    plt.savefig(chart_full_path, bbox_inches="tight")
    plt.close(fig)

    # Генерация Markdown отчета с явным разделением описательной, эксплораторной (1-way) и 2-way GRCBD статистики
    os.makedirs(docs_dir, exist_ok=True)
    report_path = os.path.join(docs_dir, "ANOVA_LATEST_REPORT.md")
    md_lines = [
        f"# 📊 СТАТИСТИЧЕСКИЙ ОТЧЕТ МОНИТОРИНГА ВОЛНЫ 2",
        f"**Статус сессии:** {status_badge}  ",
        f"**Объем выборки:** N = {total_measured} уникальных сосудов GRCBD (план: 3 когорты × 3 блока × 2 повторности)  ",
        f"**Режим статистической модели:** {model_banner}  ",
        f"**Вердикт алгоритма:** {verdict}  ",
        f"",
    ]
    if duplicate_pots_collapsed > 0:
        md_lines.append(f"> [!NOTE]\n> Во входной выборке обнаружено и свёрнуто {duplicate_pots_collapsed} дублирующих записей `pot_id` (использована последняя запись по каждому сосуду).\n")
    if not all_balanced:
        md_lines.append("> [!WARNING]\n> **Часть признаков не соответствует полной матрице 3×3×2!** Для таких строк двухфакторный GRCBD ANOVA **не применялся** — вместо него приведён разведочный 1-way ANOVA без учёта фактора блока либо только описательная статистика (`M ± SE`).\n")
    md_lines.extend([
        f"---",
        f"",
        f"### Описательная статистика и сводка дисперсионного анализа",
        f"",
        "| Физиологический параметр | Режим модели | Контроль (M ± SE) | Превенция (M ± SE) | Реакция (M ± SE) | Когорта (F) | p (когорта) | Блок (F) | p (блок) | НСР₀₅ |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])
    for row in summary_table:
        f_b_str = str(row['f_block']) if row['f_block'] is not None else "--"
        p_b_str = str(row['p_block']) if row['p_block'] is not None else "--"
        lsd_str = str(row['lsd_05']) if row['lsd_05'] is not None else "--"
        md_lines.append(
            f"| **{row['label']}** | {row['model_label']} | {row['k_str']} | {row['p_str']} | {row['r_str']} | {row['f_cohort']} | **{row['p_cohort']}** | {f_b_str} | {p_b_str} | {lsd_str} |"
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
        "duplicate_pots_collapsed": duplicate_pots_collapsed,
        "all_balanced_grcbd": all_balanced,
        "model_mode_summary": model_banner,
        "phase": phase,
        "status_badge": status_badge,
        "badge_color": badge_color,
        "verdict": verdict,
        "traits": traits_results,
        "summary_table": summary_table,
        "chart_url": f"/static/{chart_rel_path}",
        "report_file": report_path
    }
