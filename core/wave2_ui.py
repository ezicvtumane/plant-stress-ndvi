"""
Генератор пользовательского интерфейса Веб-станции 2.0 (Волна 2: Огурец GRCBD).
Покогортный конвейер съемки: КОНТРОЛЬ -> РЕАКЦИЯ -> ПРЕВЕНЦИЯ -> ПИЛОТ.
Гибкий ввод: температура и масса необязательны при съемке, их можно внести позже из журнала.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.wave2_manager import (
    POTS_CATALOG, BATCH_QUEUE_WAVE2, TURGOR_SCALE,
    evaluate_cohort_cluster_status, calculate_water_dose, WAVE2_EXPERIMENT_META
)


def render_wave2_cluster_banner(records_today: List[Dict[str, Any]]) -> str:
    """Генерация табло кластерных решений (Decision Engine)."""
    status = evaluate_cohort_cluster_status(records_today)
    p = status["prevention"]
    r = status["reaction"]
    e = status["pilot_epin"]

    return f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-bottom: 16px;">
        <!-- Табло Превенции -->
        <div style="background: #ffffff; border: 2px solid {p['badge_color']}; border-radius: 12px; padding: 14px 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; font-size: 15px; color: #0f172a;">🟡 ПРЕВЕНЦИЯ [П1–П6]</span>
                <span style="background: {p['badge_color']}; color: #fff; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 6px;">
                    Стресс: {p['stressed_count']}/6 (порог ≥4)
                </span>
            </div>
            <div style="font-size: 13px; font-weight: 600; color: {p['badge_color']};">
                {p['status_text']}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                Триггер: &Delta;T &ge; +0.6 °C у &ge;4 растений. Замерено: {p['measured_count']}/6.
            </div>
        </div>

        <!-- Табло Реакции -->
        <div style="background: #ffffff; border: 2px solid {r['badge_color']}; border-radius: 12px; padding: 14px 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; font-size: 15px; color: #0f172a;">🔵 РЕАКЦИЯ [Р1–Р6]</span>
                <span style="background: {r['badge_color']}; color: #fff; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 6px;">
                    Увяло: {r['stressed_count']}/6 (порог ≥4)
                </span>
            </div>
            <div style="font-size: 13px; font-weight: 600; color: {r['badge_color']};">
                {r['status_text']}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                Триггер: тургор 2 балла у &ge;4 растений. Замерено: {r['measured_count']}/6.
            </div>
        </div>

        <!-- Табло Эпина -->
        <div style="background: #ffffff; border: 2px solid {e['badge_color']}; border-radius: 12px; padding: 14px 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; font-size: 15px; color: #0f172a;">🔴 ПИЛОТ (ЭПИН) [Э1–Э2]</span>
                <span style="background: {e['badge_color']}; color: #fff; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 6px;">
                    Синхронно с группой П
                </span>
            </div>
            <div style="font-size: 13px; font-weight: 600; color: {e['badge_color']};">
                {e['status_text']}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                Регламент: полив шприцем под корень раствором 2 капли/100 мл до 80г (без опрыскивания листа).
            </div>
        </div>
    </div>
    """


def render_wave2_tray_layout(records_today: List[Dict[str, Any]], active_pot_id: str) -> str:
    """
    Покогортный конвейер съемки:
    1. КОНТРОЛЬ (К1-К6)
    2. РЕАКЦИЯ (Р1-Р6)
    3. ПРЕВЕНЦИЯ (П1-П6)
    4. ПИЛОТ (Э1-Э2)
    """
    by_pot = {str(r.get("ID", "")).strip().upper(): r for r in records_today}

    def render_pot_tile(pid: str) -> str:
        meta = POTS_CATALOG[pid]
        is_measured = pid in by_pot
        is_selected = (pid == active_pot_id)
        
        bg_card = "#eff6ff" if is_selected else ("#f0fdf4" if is_measured else "#f8fafc")
        border_col = "#2563eb" if is_selected else ("#16a34a" if is_measured else "#cbd5e1")
        border_w = "3px" if is_selected else "1px"
        check_icon = "✓" if is_measured else "○"
        check_col = "#16a34a" if is_measured else "#94a3b8"

        rec = by_pot.get(pid, {})
        wt = rec.get('Weight_g', '')
        wt_text = f"{wt} г" if (wt and wt != '--') else ("85.0 г" if not is_measured else "NoIR снят")
        
        dt = rec.get('Delta_T_C', '')
        dt_text = f"ΔT: {dt}°" if (dt and dt != '--') else ("" if not is_measured else "жду ввода")

        return f"""
        <button type="button" onclick="selectWave2Pot('{pid}')" 
            style="display: flex; flex-direction: column; align-items: center; justify-content: space-between;
                   background: {bg_card}; border: {border_w} solid {border_col}; border-radius: 8px;
                   padding: 6px 4px; cursor: pointer; transition: all 0.15s; min-height: 58px; text-align: center; width: 100%;">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 0 4px;">
                <span style="font-weight: 800; font-size: 14px; color: {meta['color']};">{pid}</span>
                <span style="font-weight: 800; font-size: 14px; color: {check_col};">{check_icon}</span>
            </div>
            <div style="font-size: 11px; font-weight: 600; color: #334155;">{wt_text}</div>
            <div style="font-size: 10px; color: #64748b;">{dt_text}</div>
        </button>
        """

    cohort_k = ["K1", "K2", "K3", "K4", "K5", "K6"]
    cohort_r = ["R1", "R2", "R3", "R4", "R5", "R6"]
    cohort_p = ["P1", "P2", "P3", "P4", "P5", "P6"]
    cohort_e = ["E1", "E2"]

    return f"""
    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 14px rgba(0,0,0,0.03);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-weight: 700; font-size: 15px; color: #0f172a;">
                📸 ОЧЕРЕДЬ СЪЕМКИ ПО КОГОРТАМ: КОНТРОЛЬ &rarr; РЕАКЦИЯ &rarr; ПРЕВЕНЦИЯ &rarr; ПИЛОТ
                <span style="font-size: 12px; font-weight: 400; color: #64748b; margin-left: 8px;">
                    (Замерено: {len(by_pot)}/20)
                </span>
            </div>
            <div style="font-size: 12px; color: #64748b;">
                Кликните на горшок для пересъемки
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
            <!-- 1. КОНТРОЛЬ -->
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 10px;">
                <div style="font-size: 12px; font-weight: 800; color: #15803d; margin-bottom: 8px;">1. 🟢 КОНТРОЛЬ (К1–К6)</div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_k)}
                </div>
            </div>

            <!-- 2. РЕАКЦИЯ -->
            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 10px;">
                <div style="font-size: 12px; font-weight: 800; color: #1d4ed8; margin-bottom: 8px;">2. 🔵 РЕАКЦИЯ (Р1–Р6)</div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_r)}
                </div>
            </div>

            <!-- 3. ПРЕВЕНЦИЯ -->
            <div style="background: #fefce8; border: 1px solid #fef08a; border-radius: 10px; padding: 10px;">
                <div style="font-size: 12px; font-weight: 800; color: #a16207; margin-bottom: 8px;">3. 🟡 ПРЕВЕНЦИЯ (П1–П6)</div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_p)}
                </div>
            </div>

            <!-- 4. ПИЛОТ -->
            <div style="background: #fff1f2; border: 1px solid #fecdd3; border-radius: 10px; padding: 10px;">
                <div style="font-size: 12px; font-weight: 800; color: #be123c; margin-bottom: 8px;">4. 🔴 ПИЛОТ (Э1–Э2)</div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_e)}
                </div>
            </div>
        </div>
    </div>

    <!-- Клиентские обработчики для Волны 2 -->
    <script>
    function selectWave2Pot(pid) {{
        const url = new URL(window.location.href);
        url.searchParams.set('pot', pid);
        window.location.href = url.toString();
    }}

    async function submitWave2Measurement(e) {{
        e.preventDefault();
        const btn = document.getElementById('btnCaptureWave2');
        if (btn) {{
            btn.disabled = true;
            btn.innerText = '⏳ ИДЕТ СЪЕМКА NoIR...';
        }}
        
        const form = document.getElementById('wave2Form');
        const formData = new FormData(form);
        
        try {{
            const resp = await fetch('/api/wave2/capture_and_save', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();
            if (res.status === 'ok') {{
                selectWave2Pot(res.next_pot || 'K1');
            }} else {{
                alert('Ошибка съемки: ' + (res.error || 'Неизвестная ошибка'));
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = '📸 СНЯТЬ NoIR И ДАЛЕЕ';
                }}
            }}
        }} catch(err) {{
            alert('Сетевая ошибка при съемке: ' + err);
            if (btn) {{
                btn.disabled = false;
                btn.innerText = '📸 СНЯТЬ NoIR И ДАЛЕЕ';
            }}
        }}
    }}

    async function saveRowEdit(pid) {{
        const wt = document.getElementById('cell_wt_' + pid).value;
        const tl = document.getElementById('cell_tl_' + pid).value;
        const tr = document.getElementById('cell_tr_' + pid).value;
        const btn = document.getElementById('btn_save_' + pid);
        if (btn) {{
            btn.disabled = true;
            btn.innerText = '⏳...';
        }}
        
        const formData = new FormData();
        formData.append('pot_id', pid);
        formData.append('weight_g', wt);
        formData.append('t_leaf', tl);
        formData.append('turgor_score', tr);
        const elSoil = document.getElementById('cell_soil_' + pid);
        if (elSoil) {{
            formData.append('moisture_pct', elSoil.value);
        }}
        
        try {{
            const resp = await fetch('/api/wave2/update_record', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();
            if (res.status === 'ok') {{
                location.reload();
            }} else {{
                alert('Ошибка обновления: ' + (res.error || 'Неизвестная ошибка'));
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = '💾';
                }}
            }}
        }} catch(err) {{
            alert('Ошибка сохранения: ' + err);
            if (btn) {{
                btn.disabled = false;
                btn.innerText = '💾';
            }}
        }}
    }}

    function reshootWave2Pot(pid) {{
        selectWave2Pot(pid);
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    async function deleteWave2Row(pid) {{
        if (!confirm('Вы уверены, что хотите удалить ошибочный замер для горшка [' + pid + ']?')) {{
            return;
        }}
        const formData = new FormData();
        formData.append('pot_id', pid);
        try {{
            const resp = await fetch('/api/wave2/delete_record', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();
            if (res.status === 'ok') {{
                location.reload();
            }} else {{
                alert('Ошибка при удалении: ' + (res.message || res.error || 'Неизвестная ошибка'));
            }}
        }} catch(err) {{
            alert('Сетевая ошибка при удалении: ' + err);
        }}
    }}
    </script>
    """


def render_wave2_active_pot_card(
    active_pot_id: str,
    records_today: List[Dict[str, Any]],
    current_climate: Dict[str, Any]
) -> str:
    """Генерация центральной карточки замера для выбранного горшка."""
    meta = POTS_CATALOG.get(active_pot_id, POTS_CATALOG["K1"])
    by_pot = {str(r.get("ID", "")).strip().upper(): r for r in records_today}
    rec = by_pot.get(active_pot_id, {})
    
    t_air = current_climate.get("t_c", 24.0)
    cur_v = current_climate.get("cur_v")
    current_weight = rec.get("Weight_g", "")
    current_t_leaf = rec.get("T_Leaf_C", "")
    current_turgor = rec.get("Turgor_Score", "1")
    
    has_probe = meta.get("has_probe", False) or active_pot_id in ("K1", "R1", "P1")
    if has_probe:
        if cur_v is not None and cur_v > 0.05:
            live_soil = round(max(0.0, min(100.0, (cur_v - 0.5) / 1.5 * 100)), 1)
            probe_badge = f"<span style='background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 11px; border: 1px solid #bae6fd;'>🌱 Датчик почвы: {live_soil}% ({cur_v:.2f}В)</span>"
        else:
            rec_soil = rec.get("Moisture_Pct", "--")
            probe_badge = f"<span style='background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 11px; border: 1px solid #bae6fd;'>🌱 Датчик почвы: {rec_soil}%</span>" if rec_soil != '--' else "<span style='background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 11px; border: 1px solid #bae6fd;'>🌱 Датчик почвы (подключен)</span>"
    else:
        probe_badge = "<span style='color: #94a3b8; font-size: 11px;'>🌱 Датчик почвы: нет (—)</span>" 

    # Оценка триггера когорты
    status = evaluate_cohort_cluster_status(records_today)
    cohort = meta["cohort"]
    
    # Расчет дозы полива для отображения
    has_wt = current_weight and current_weight != '--'
    raw_dose = calculate_water_dose(float(current_weight) if has_wt else 85.0, 85.0) if has_wt else None
    
    if cohort == "Control":
        if raw_dose is not None:
            dose_html = f"<span style='color: #059669; font-weight: 800; font-size: 18px;'>{raw_dose} мл</span> (Ежедневный долив)"
        else:
            dose_html = "<span style='color: #64748b;'>Введите массу для расчета дозы</span>"
    elif cohort == "Prevention":
        if status["prevention"]["triggered"]:
            dose_html = f"<span style='color: #059669; font-weight: 800; font-size: 18px;'>{raw_dose if raw_dose is not None else ''} мл</span> (ТРИГГЕР СРАБОТАЛ — ПОЛИТЬ!)"
        elif status["prevention"]["all_measured"]:
            dose_html = "<span style='color: #dc2626; font-weight: 800;'>ПОЛИВ ЗАБЛОКИРОВАН (Засуха)</span>"
        else:
            dose_html = "<span style='color: #64748b; font-weight: 600;'>Откроется после замера всей группы П</span>"
    elif cohort == "Reaction":
        if status["reaction"]["triggered"]:
            dose_html = f"<span style='color: #059669; font-weight: 800; font-size: 18px;'>{raw_dose if raw_dose is not None else ''} мл</span> (УВЯДАНИЕ — РЕАНИМАЦИЯ!)"
        elif status["reaction"]["all_measured"]:
            dose_html = "<span style='color: #2563eb; font-weight: 800;'>ПОЛИВ ЗАБЛОКИРОВАН (Тургор в норме)</span>"
        else:
            dose_html = "<span style='color: #64748b; font-weight: 600;'>Откроется после замера всей группы Р</span>"
    else:  # Pilot Epin
        if status["pilot_epin"]["triggered"]:
            dose_html = f"<span style='color: #dc2626; font-weight: 800; font-size: 18px;'>{raw_dose if raw_dose is not None else ''} мл ЭПИНА</span> (под корень шприцем)"
        else:
            dose_html = "<span style='color: #64748b; font-weight: 600;'>Ждём триггера группы П</span>"

    return f"""
    <div class="card" style="border: 2px solid {meta['color']}; margin: 0; display: flex; flex-direction: column; justify-content: space-between; height: 100%; box-sizing: border-box;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                <span style="font-size: 22px; font-weight: 900; color: {meta['color']};">ГОРШОК [{active_pot_id}]</span>
                <span style="font-size: 14px; font-weight: 600; color: #475569;">{meta['badge']}</span>
                {probe_badge}
            </div>
            <div style="font-size: 13px; color: #64748b;">
                Целевая масса: <strong>85.0 г</strong> | T<sub>возд</sub>: <strong>{t_air:.1f} °C</strong>
            </div>
        </div>

        <form id="wave2Form" onsubmit="submitWave2Measurement(event)" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; align-items: end;">
            <input type="hidden" name="pot_id" value="{active_pot_id}">
            <input type="hidden" name="t_air" value="{t_air}">

            <!-- Поле 1: Текущая масса -->
            <div>
                <label style="display: block; font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">
                    1. Текущая масса (г):
                </label>
                <input type="number" step="0.1" name="weight_g" id="wave2_weight" 
                    value="{current_weight if current_weight != '--' else ''}" 
                    placeholder="--"
                    oninput="updateLiveDose()"
                    style="width: 100%; font-size: 15px; font-weight: 700; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box;">
            </div>

            <!-- Поле 2: T_листа -->
            <div>
                <label style="display: block; font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">
                    2. T<sub>листа</sub> (°C) с тепловизора:
                </label>
                <input type="number" step="0.1" name="t_leaf" id="wave2_t_leaf" 
                    value="{current_t_leaf if current_t_leaf != '--' else ''}" 
                    placeholder="--"
                    oninput="updateLiveDeltaT()"
                    style="width: 100%; font-size: 15px; font-weight: 700; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box;">
            </div>

            <!-- Поле 3: Тургор -->
            <div>
                <label style="display: block; font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">
                    3. Оценка тургора:
                </label>
                <select name="turgor_score" id="wave2_turgor" 
                    style="width: 100%; font-size: 14px; font-weight: 600; padding: 9px 10px; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box;">
                    <option value="1" {'selected' if str(current_turgor) == '1' else ''}>{TURGOR_SCALE[1]}</option>
                    <option value="2" {'selected' if str(current_turgor) == '2' else ''}>{TURGOR_SCALE[2]}</option>
                    <option value="3" {'selected' if str(current_turgor) == '3' else ''}>{TURGOR_SCALE[3]}</option>
                </select>
            </div>

            <!-- Кнопка запуска съемки -->
            <div>
                <button type="submit" id="btnCaptureWave2"
                    style="width: 100%; background: linear-gradient(135deg, #059669 0%, #047857 100%); color: #ffffff;
                           font-size: 15px; font-weight: 700; padding: 10px 16px; border: none; border-radius: 8px;
                           cursor: pointer; box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);">
                    📸 СНЯТЬ NoIR И ДАЛЕЕ &rarr;
                </button>
            </div>
        </form>

        <!-- Инфо-строка живых расчетов -->
        <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 10px; border-top: 1px dashed #e2e8f0; font-size: 13px;">
            <div>
                Расчетный &Delta;T: <strong id="live_delta_t" style="font-size: 15px; color: #0284c7;">--</strong>
                <span style="font-size: 11px; color: #64748b;">(лист &epsilon;=0.98)</span>
            </div>
            <div>
                Статус дозы полива: <strong id="live_dose_display">{dose_html}</strong>
            </div>
        </div>
    </div>

    <!-- Клиентский скрипт живых расчетов формы -->
    <script>
    function updateLiveDeltaT() {{
        const inputVal = document.getElementById('wave2_t_leaf').value.trim();
        const dtEl = document.getElementById('live_delta_t');
        if (inputVal === '') {{
            dtEl.innerText = '--';
            dtEl.style.color = '#64748b';
            return;
        }}
        const tLeaf = parseFloat(inputVal);
        const tAir = {t_air};
        if (!isNaN(tLeaf)) {{
            const dt = (tLeaf - tAir).toFixed(2);
            dtEl.innerText = (dt >= 0 ? '+' : '') + dt + ' °C';
            dtEl.style.color = (dt >= 0.6) ? '#dc2626' : (dt < 0 ? '#059669' : '#0284c7');
        }} else {{
            dtEl.innerText = '--';
        }}
    }}
    function updateLiveDose() {{
        const inputVal = document.getElementById('wave2_weight').value.trim();
        const doseEl = document.getElementById('live_dose_display');
        if (inputVal === '') {{
            return;
        }}
        const wt = parseFloat(inputVal);
        if (!isNaN(wt)) {{
            const dose = Math.max(0, 80.0 - wt).toFixed(1);
            if ('{cohort}' === 'Control') {{
                doseEl.innerHTML = '<span style=\"color: #059669; font-weight: 800; font-size: 18px;\">' + dose + ' мл</span> (Ежедневный долив)';
            }}
        }}
    }}
    updateLiveDeltaT();
    </script>
    """


def render_wave2_measurements_table(records: List[Dict[str, Any]]) -> str:
    """
    Генерация таблицы замеров (27 колонок) с возможностью inline-редактирования
    любого параметра прямо в интерфейсе на время проведения замеров.
    """
    rows_html = []
    if not records:
        rows_html.append("""
        <tr>
            <td colspan="12" style="padding: 24px; text-align: center; color: #64748b; font-size: 13px;">
                Замеров Волны 2 пока нет. Выберите горшок выше и нажмите <strong>«Снять NoIR и далее»</strong>.
            </td>
        </tr>
        """)
    else:
        for r in reversed(records[-30:]):  # последние 30 записей
            rec_id = r.get("ID", "--")
            ts = r.get("Timestamp", "--")
            wt = r.get("Weight_g", "")
            t_leaf = r.get("T_Leaf_C", "")
            t_air = r.get("T_Air_C", "--")
            dt = r.get("Delta_T_C", "--")
            turgor = r.get("Turgor_Score", "1")
            dose = r.get("Water_Dose_ml", "--")
            ndvi = r.get("NDVI_Mean", "--")
            pla = r.get("Leaf_Area_cm2", "--")
            opt_file = r.get("Opt_File", "")
            th_file = r.get("Thermal_File", "")
            ndvi_std = r.get("NDVI_Std", "")

            # Форматирование значения NDVI с СКО (как в Волне 1)
            if ndvi != "--" and ndvi != "":
                try:
                    n_val = float(ndvi)
                    if ndvi_std and ndvi_std != "--" and float(ndvi_std) > 0:
                        ndvi_txt = f"{n_val:.3f}±{float(ndvi_std):.3f}"
                    else:
                        ndvi_txt = f"{n_val:.3f}"
                except (ValueError, TypeError):
                    ndvi_txt = str(ndvi)
            else:
                ndvi_txt = "--"

            # Ячейка NDVI с интерактивным просмотром и лупой
            if opt_file and opt_file != "--":
                ndvi_cell = f'''<a href="/wave2_image/{opt_file}" target="_blank" onclick="openImageViewer(\'/wave2_image/{opt_file}\', \'Карта NDVI — Горшок [{rec_id}] ({ndvi_txt})\'); return false;" title="Открыть карту NDVI [{rec_id}]" style="color: #0d9488; text-decoration: none; font-weight: 700; white-space: nowrap;"><span style="font-family: monospace; font-size: 11px;">{ndvi_txt}</span> 🔍</a>'''
            else:
                ndvi_cell = f'''<span style="font-family: monospace; font-size: 11px; color: #334155; font-weight: 600;">{ndvi_txt}</span>'''

            # Ячейка Термограммы с интерактивным просмотром
            if th_file and th_file != "--":
                clean_th = os.path.basename(th_file)
                th_cell = f'''<a href="/wave2_image/{clean_th}" target="_blank" onclick="openImageViewer(\'/wave2_image/{clean_th}\', \'Термограмма UTi120S — Горшок [{rec_id}]\'); return false;" title="Открыть термограмму [{rec_id}]" style="color: #059669; font-weight: 700; font-size: 11px; white-space: nowrap; text-decoration: none; background: #ecfdf5; border: 1px solid #a7f3d0; padding: 2px 6px; border-radius: 4px;">✓ {clean_th} 🔍</a>'''
            else:
                th_cell = '<span style="color: #94a3b8; font-size: 11px;">—</span>'

            meta = POTS_CATALOG.get(rec_id, {})
            color = meta.get("color", "#475569")
            has_probe = meta.get("has_probe", False) or rec_id in ("K1", "R1", "P1")
            soil = r.get("Moisture_Pct", "--")
            if has_probe:
                soil_cell = f'''<input type="number" step="0.1" value="{soil if soil != '--' else ''}" placeholder="--" id="cell_soil_{rec_id}" onkeydown="if(event.key===\'Enter\') saveRowEdit(\'{rec_id}\')" style="width: 55px; padding: 4px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 4px; text-align: center;">'''
            else:
                soil_cell = '<span style="color: #94a3b8; font-weight: 600;">--</span>'

            rows_html.append(f"""
            <tr id="row_{rec_id}" style="border-bottom: 1px solid #f1f5f9;">
                <td style="padding: 8px 10px; font-weight: 800; color: {color};">{rec_id}</td>
                <td style="padding: 8px 10px; font-size: 11px; color: #64748b;">{ts}</td>
                <td style="padding: 6px 4px;">
                    <input type="number" step="0.1" value="{wt if wt != '--' else ''}" placeholder="--" id="cell_wt_{rec_id}" 
                        onkeydown="if(event.key==='Enter') saveRowEdit('{rec_id}')"
                        style="width: 70px; padding: 4px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 4px;">
                </td>
                <td style="padding: 6px 4px;">
                    <input type="number" step="0.1" value="{t_leaf if t_leaf != '--' else ''}" placeholder="--" id="cell_tl_{rec_id}" 
                        onkeydown="if(event.key==='Enter') saveRowEdit('{rec_id}')"
                        style="width: 65px; padding: 4px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 4px;">
                </td>
                <td style="padding: 8px 10px; font-size: 12px; color: #64748b;">{t_air}°</td>
                <td style="padding: 8px 10px; font-size: 12px; font-weight: 700; color: #0284c7;">{dt}</td>
                <td style="padding: 6px 4px; text-align: center;">{soil_cell}</td>
                <td style="padding: 6px 4px;">
                    <select id="cell_tr_{rec_id}" style="padding: 4px; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px;">
                        <option value="1" {'selected' if str(turgor) == '1' else ''}>1</option>
                        <option value="2" {'selected' if str(turgor) == '2' else ''}>2</option>
                        <option value="3" {'selected' if str(turgor) == '3' else ''}>3</option>
                    </select>
                </td>
                <td style="padding: 8px 10px; font-size: 12px; font-weight: 800; color: #059669;">{dose}</td>
                <td style="padding: 8px 10px;">{ndvi_cell}</td>
                <td style="padding: 8px 10px; font-size: 12px;">{pla}</td>
                <td style="padding: 8px 10px;">{th_cell}</td>
                <td style="padding: 6px 4px; text-align: center; white-space: nowrap;">
                    <button type="button" id="btn_save_{rec_id}" onclick="saveRowEdit('{rec_id}')" title="Сохранить изменения" 
                        style="background: #0284c7; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 7px; border: none; border-radius: 4px; cursor: pointer;">
                        💾
                    </button>
                    <button type="button" onclick="reshootWave2Pot('{rec_id}')" title="Выбрать этот горшок и переснять" 
                        style="background: #f59e0b; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 7px; border: none; border-radius: 4px; cursor: pointer; margin-left: 3px;">
                        🔄 Переснять
                    </button>
                    <button type="button" onclick="deleteWave2Row('{rec_id}')" title="Удалить ошибочный замер" 
                        style="background: #ef4444; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 7px; border: none; border-radius: 4px; cursor: pointer; margin-left: 3px;">
                        🗑️
                    </button>
                </td>
            </tr>
            """)

    return f"""
    <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
        <thead>
            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0; color: #475569; position: sticky; top: 0; z-index: 5;">
                <th style="padding: 8px 10px;">ID</th>
                <th style="padding: 8px 10px;">Время</th>
                <th style="padding: 8px 10px;">Масса (г)</th>
                <th style="padding: 8px 10px;">T листа (°C)</th>
                <th style="padding: 8px 10px;">T возд (°C)</th>
                <th style="padding: 8px 10px;">ΔT (°C)</th>
                <th style="padding: 8px 10px;">Почва (%)</th>
                <th style="padding: 8px 10px;">Тургор</th>
                <th style="padding: 8px 10px;">Доза (мл)</th>
                <th style="padding: 8px 10px;">NDVI</th>
                <th style="padding: 8px 10px;">PLA (см²)</th>
                <th style="padding: 8px 10px;">Термограмма</th>
                <th style="padding: 8px 10px; text-align: center;">Действие</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>

    <!-- ИНТЕРАКТИВНЫЙ LIGHTBOX ДЛЯ ПРОСМОТРА NDVI И ТЕРМОГРАММ -->
    <div id="imageViewerModal" style="display:none; position:fixed; z-index:10000; left:0; top:0; width:100%; height:100%; background:rgba(15,23,42,0.85); align-items:center; justify-content:center; backdrop-filter:blur(4px);" onclick="closeImageViewer(event)">
        <div style="background:#ffffff; border-radius:12px; max-width:92vw; max-height:92vh; display:flex; flex-direction:column; box-shadow:0 20px 48px rgba(0,0,0,0.5); border:2px solid #00a499; overflow:hidden;" onclick="event.stopPropagation()">
            <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 18px; background:#f8fafc; border-bottom:1px solid #e2e8f0;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span id="imageViewerIcon" style="font-size:18px;">🔍</span>
                    <h3 id="imageViewerTitle" style="margin:0; font-size:15px; font-weight:800; color:#0f172a;">Просмотр снимка</h3>
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <a id="imageViewerDownload" href="#" target="_blank" style="padding:6px 12px; background:#0284c7; color:#fff; font-size:12px; font-weight:700; text-decoration:none; border-radius:6px;">↗ Открыть в новой вкладке</a>
                    <button type="button" onclick="closeImageViewer()" style="background:#e2e8f0; border:none; width:30px; height:30px; border-radius:6px; font-size:16px; cursor:pointer; font-weight:bold; color:#475569;">✕</button>
                </div>
            </div>
            <div style="padding:16px; display:flex; justify-content:center; align-items:center; background:#0f172a; overflow:auto; max-height:calc(92vh - 70px);">
                <img id="imageViewerImg" src="" alt="Снимок" style="max-width:100%; max-height:75vh; object-fit:contain; border-radius:6px; box-shadow:0 4px 16px rgba(0,0,0,0.4);">
            </div>
        </div>
    </div>

    <script>
    function openImageViewer(url, title) {{
        const modal = document.getElementById('imageViewerModal');
        const img = document.getElementById('imageViewerImg');
        const titleEl = document.getElementById('imageViewerTitle');
        const linkEl = document.getElementById('imageViewerDownload');
        if (!modal || !img) return;
        img.src = url;
        if (titleEl) titleEl.innerText = title || 'Просмотр снимка';
        if (linkEl) linkEl.href = url;
        modal.style.display = 'flex';
    }}
    function closeImageViewer(e) {{
        const modal = document.getElementById('imageViewerModal');
        if (modal) modal.style.display = 'none';
    }}
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') closeImageViewer();
    }});
    </script>
    """

def render_wave2_channels_card(t_now: int) -> str:
    """Генерация карточки 4 мультиспектральных каналов, как на первой станции."""
    return f"""
    <div class="card" style="display: flex; flex-direction: column; margin: 0; justify-content: space-between; height: 100%; box-sizing: border-box;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h2 style="font-size: 15px; margin: 0; color: var(--sirius-teal-dark);">🔬 Мультиспектральная съемка</h2>
            <span style="font-size: 11px; font-weight: 600; color: #64748b;">NoIR IMX179 + LEDs</span>
        </div>
        <div class="channels" style="flex: 1; gap: 10px;">
            <div class="ch-box">
                <div style="color: #dc2626; font-size: 11px; font-weight: 700; margin-bottom: 4px;">Канал 1: 660 нм (Deep Red)</div>
                <img src="/static/last_red.jpg?t={t_now}" class="preview-img" style="height: 150px; width: 100%; object-fit: contain; background: #000; border-radius: 6px;">
            </div>
            <div class="ch-box">
                <div style="color: #4f46e5; font-size: 11px; font-weight: 700; margin-bottom: 4px;">Канал 2: 850 нм (NIR Инфракрасный)</div>
                <img src="/static/last_nir.jpg?t={t_now}" class="preview-img" style="height: 150px; width: 100%; object-fit: contain; background: #000; border-radius: 6px;">
            </div>
            <div class="ch-box">
                <div style="color: #0d9488; font-size: 11px; font-weight: 700; margin-bottom: 4px;">Канал 3: Карта NDVI (Феномика)</div>
                <img src="/static/last_ndvi.jpg?t={t_now}" class="preview-img" style="height: 150px; width: 100%; object-fit: contain; background: #000; border-radius: 6px;">
            </div>
            <div class="ch-box">
                <div style="color: #d97706; font-size: 11px; font-weight: 700; margin-bottom: 4px;">Канал 4: Термограмма (UNI-T UTi120S)</div>
                <img src="/static/last_thermal.jpg?t={t_now}" class="preview-img" style="height: 150px; width: 100%; object-fit: contain; background: #000; border-radius: 6px;">
            </div>
        </div>
    </div>
    """
