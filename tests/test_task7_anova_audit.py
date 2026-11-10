import importlib.util
from pathlib import Path
import pandas as pd
import pytest

from core.wave2_anova import dospekhov_two_way_anova_engine, analyze_wave2_dataset


def _load_dospekhov_script():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_dospekhov_anova.py"
    spec = importlib.util.spec_from_file_location("run_dospekhov_anova", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_balanced_records(
    k_dt=0.0,
    p_dt=0.0,
    r_dt=0.0,
    r_turgors=None,
    k_turgors=None,
    p_turgors=None,
):
    if r_turgors is None:
        r_turgors = [4, 4, 4, 4, 4, 4]
    if k_turgors is None:
        k_turgors = [4, 4, 4, 4, 4, 4]
    if p_turgors is None:
        p_turgors = [4, 4, 4, 4, 4, 4]

    records = []
    # Small deterministic jitter per pot avoids zero variance in ANOVA
    offsets = [-0.08, 0.08, -0.05, 0.05, -0.06, 0.06]
    for idx in range(6):
        pot_num = idx + 1
        off = offsets[idx]
        records.append({
            "ID": f"K{pot_num}",
            "Weight_g": 120.0 + idx * 0.3,
            "Delta_T_C": (k_dt[idx] if isinstance(k_dt, list) else k_dt) + off,
            "NDVI_Mean": 0.65 + off * 0.1,
            "Leaf_Area_cm2": 22.0 + off,
            "Turgor_Score": k_turgors[idx],
        })
        records.append({
            "ID": f"P{pot_num}",
            "Weight_g": 120.2 + idx * 0.3,
            "Delta_T_C": (p_dt[idx] if isinstance(p_dt, list) else p_dt) + off,
            "NDVI_Mean": 0.64 + off * 0.1,
            "Leaf_Area_cm2": 21.8 + off,
            "Turgor_Score": p_turgors[idx],
        })
        records.append({
            "ID": f"R{pot_num}",
            "Weight_g": 119.9 + idx * 0.3,
            "Delta_T_C": (r_dt[idx] if isinstance(r_dt, list) else r_dt) + off,
            "NDVI_Mean": 0.65 + off * 0.1,
            "Leaf_Area_cm2": 22.1 + off,
            "Turgor_Score": r_turgors[idx],
        })
    return records


def test_task7_engine_strict_balanced_vs_unbalanced_and_descriptive():
    cohorts = ["Control", "Prevention", "Reaction"]
    blocks = ["Блок 1", "Блок 2", "Блок 3"]
    rows = []
    idx = 0
    for c_i, cohort in enumerate(cohorts):
        for b_i, block in enumerate(blocks):
            for rep in range(2):
                idx += 1
                rows.append({
                    "pot_id": f"{cohort[0]}{idx}",
                    "cohort": cohort,
                    "block": block,
                    "weight_g": 100.0 + c_i * 5.0 + b_i * 0.4 + rep * 0.3,
                })
    df_balanced = pd.DataFrame(rows)
    res_bal = dospekhov_two_way_anova_engine(df_balanced, "weight_g")
    assert res_bal["is_balanced_grcbd"] is True
    assert res_bal["model_mode"] == "two_way_grcbd"
    assert res_bal["df_error"] == 9
    assert res_bal["lsd_05"] is not None
    assert res_bal["balance_note"] is None

    # Unbalanced 18 rows: 3 in Control/Блок 1 and 1 in Control/Блок 2
    df_unbal = df_balanced.copy()
    mask = (df_unbal["cohort"] == "Control") & (df_unbal["block"] == "Блок 2")
    first_k_b2 = df_unbal[mask].index[0]
    df_unbal.loc[first_k_b2, "block"] = "Блок 1"
    res_unbal = dospekhov_two_way_anova_engine(df_unbal, "weight_g")
    assert res_unbal["is_balanced_grcbd"] is False
    assert res_unbal["model_mode"] == "one_way_fallback"
    assert "1-way" in res_unbal["model_label"]
    assert "Нарушен баланс ячеек" in (res_unbal["balance_note"] or "")

    # Too few samples -> descriptive_only
    df_tiny = df_balanced.groupby("cohort").head(1).copy()
    res_tiny = dospekhov_two_way_anova_engine(df_tiny, "weight_g")
    assert res_tiny["is_balanced_grcbd"] is False
    assert res_tiny["model_mode"] == "descriptive_only"


def test_task7_incomplete_slice_marks_report_with_warning_banner(tmp_path):
    # Only 12 pots (blocks 1 & 2) -> incomplete 12/18
    records = [r for r in _make_balanced_records() if not r["ID"].endswith(("5", "6"))]
    static_dir = tmp_path / "static"
    docs_dir = tmp_path / "docs"
    res = analyze_wave2_dataset(records, static_dir=str(static_dir), docs_dir=str(docs_dir))
    assert res["ok"] is True
    assert res["total_measured"] == 12
    assert res["all_balanced_grcbd"] is False
    report_text = (docs_dir / "ANOVA_LATEST_REPORT.md").read_text(encoding="utf-8")
    assert "> [!WARNING]" in report_text
    assert "не соответствует полной матрице 3×3×2" in report_text
    assert "1-way ANOVA" in report_text


def test_task7_duplicate_pots_collapsed_and_report_annotated(tmp_path):
    records = _make_balanced_records()
    # Add two duplicate pot measurements (last value wins -> 18 unique GRCBD)
    records.append({**records[0], "Weight_g": 135.5})
    records.append({**records[1], "Delta_T_C": 0.1})

    res = analyze_wave2_dataset(
        records,
        static_dir=str(tmp_path / "static"),
        docs_dir=str(tmp_path / "docs"),
    )
    assert res["ok"] is True
    assert res["total_measured"] == 18
    assert res["duplicate_pots_collapsed"] == 2
    assert res["all_balanced_grcbd"] is True
    report_text = (tmp_path / "docs" / "ANOVA_LATEST_REPORT.md").read_text(encoding="utf-8")
    assert "свёрнуто 2 дублирующих записей `pot_id`" in report_text


def test_task7_reaction_trigger_requires_quorum_not_mean(tmp_path):
    # Case A: 3 plants turgor=1, 3 plants turgor=4 -> mean = 2.5 (old rule triggered!), quorum = 3/6 (<4)
    records_no_quorum = _make_balanced_records(r_turgors=[1, 1, 1, 4, 4, 4])
    res_a = analyze_wave2_dataset(
        records_no_quorum,
        static_dir=str(tmp_path / "static_a"),
        docs_dir=str(tmp_path / "docs_a"),
    )
    assert res_a["ok"] is True
    assert res_a["phase"] != "reaction_trigger"

    # Case B: 4 plants turgor=2, 2 plants turgor=4 -> mean = 2.67 (>2.5), quorum = 4/6 (>=4)
    records_quorum = _make_balanced_records(r_turgors=[2, 2, 2, 2, 4, 4])
    res_b = analyze_wave2_dataset(
        records_quorum,
        static_dir=str(tmp_path / "static_b"),
        docs_dir=str(tmp_path / "docs_b"),
    )
    assert res_b["ok"] is True
    assert res_b["phase"] == "reaction_trigger"
    assert "4/6" in res_b["verdict"]


def test_task7_prevention_alert_requires_positive_ddt_direction_and_quorum(tmp_path):
    # Inverted direction: Control warmer (+1.5°C) than Prevention (-0.5°C) -> high F, p <= 0.05, NO alert!
    records_inverted = _make_balanced_records(k_dt=1.5, p_dt=-0.5, r_dt=0.0)
    res_inv = analyze_wave2_dataset(
        records_inverted,
        static_dir=str(tmp_path / "static_inv"),
        docs_dir=str(tmp_path / "docs_inv"),
    )
    assert res_inv["ok"] is True
    assert res_inv["traits"]["delta_t"]["p_cohort"] <= 0.05
    assert res_inv["phase"] != "prevention_alert"
    assert res_inv["phase"] == "monitoring"

    # True overheat in Prevention (+1.4°C vs Control 0.0°C) with 6/6 ΔΔT >= +0.6°C
    records_pos = _make_balanced_records(k_dt=0.0, p_dt=1.4, r_dt=0.1)
    res_pos = analyze_wave2_dataset(
        records_pos,
        static_dir=str(tmp_path / "static_pos"),
        docs_dir=str(tmp_path / "docs_pos"),
    )
    assert res_pos["ok"] is True
    assert res_pos["phase"] == "prevention_alert"
    assert "6/6" in res_pos["verdict"]


def test_task7_standalone_dospekhov_script_strict_grcbd_and_posthoc():
    mod = _load_dospekhov_script()
    df_ref = mod.generate_reference_dataset()
    assert len(df_ref) == 19
    assert not df_ref["pot_id"].isin(["Э1", "Э2", "C21"]).any()
    sat_rows = df_ref[df_ref["pot_id"] == "C20"]
    assert len(sat_rows) == 1
    assert sat_rows.iloc[0]["cohort"] == "Сателлит"

    df_grcbd = df_ref[df_ref["cohort"].isin(["Контроль", "Превенция", "Реакция"])].copy()
    assert len(df_grcbd) == 18

    res = mod.dospekhov_two_way_anova(df_grcbd, "FW_g")
    assert res["Tukey_HSD_05"] > res["LSD_05"] > 0
    assert res["HCP_05"] == res["Tukey_HSD_05"]
    assert res["df"]["A"] == 2
    assert res["df"]["B"] == 2
    assert res["df"]["AB"] == 4
    assert res["df"]["E"] == 9

    # Reject incomplete matrix
    with pytest.raises(ValueError, match="18"):
        mod.dospekhov_two_way_anova(df_grcbd.iloc[:-1].copy(), "FW_g")

    # Reject unbalanced 18 rows
    df_unbal = df_grcbd.copy()
    idx_move = df_unbal[(df_unbal["cohort"] == "Контроль") & (df_unbal["block"] == "Блок 2")].index[0]
    df_unbal.loc[idx_move, "block"] = "Блок 1"
    with pytest.raises(ValueError, match="баланс ячеек"):
        mod.dospekhov_two_way_anova(df_unbal, "FW_g")

    # Reject NaN
    df_nan = df_grcbd.copy()
    df_nan.iloc[0, df_nan.columns.get_loc("FW_g")] = float("nan")
    with pytest.raises(ValueError, match="NaN"):
        mod.dospekhov_two_way_anova(df_nan, "FW_g")

    # Reject duplicate pot_id (even if length were somehow 18 after dropping)
    df_dup = df_grcbd.copy()
    df_dup.iloc[1, df_dup.columns.get_loc("pot_id")] = df_dup.iloc[0]["pot_id"]
    with pytest.raises(ValueError, match="дубликаты"):
        mod.dospekhov_two_way_anova(df_dup, "FW_g")
