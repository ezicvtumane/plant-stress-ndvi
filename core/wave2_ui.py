"""
Генератор пользовательского интерфейса Веб-станции 2.0 (Волна 2: Огурец GRCBD).
Покогортный конвейер съемки: КОНТРОЛЬ -> РЕАКЦИЯ -> ПРЕВЕНЦИЯ.
Гибкий ввод: температура и масса необязательны при съемке, их можно внести позже из журнала.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.wave2_manager import (
    POTS_CATALOG, BATCH_QUEUE_WAVE2, TURGOR_SCALE,
    evaluate_cohort_cluster_status, resolve_cohort_watering_decision,
    format_watering_decision_output,
    calculate_water_dose, WAVE2_EXPERIMENT_META
)
from core.agronomic_rules import parse_optional_turgor


def render_wave2_cluster_banner(records_today: List[Dict[str, Any]]) -> str:
    """Компактная однострочная сводка статусов когорт (резервный хелпер совместимости)."""
    status = evaluate_cohort_cluster_status(records_today)
    p = status["prevention"]
    r = status["reaction"]
    sat = status.get("satellite", {"status_text": "Донор реплик (до 100.0 г)", "badge_color": "#8b5cf6"})

    return f"""
    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
        <div style="flex: 1 1 260px; background: #ffffff; border: 1px solid {p['badge_color']}; border-radius: 8px; padding: 6px 10px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-size: 11px; color: {p['badge_color']}; font-weight: 700;">🟡 ПРЕВЕНЦИЯ: {p['status_text']}</span>
            <span style="background: {p['badge_color']}; color: #fff; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; white-space: nowrap;">Стресс: {p['stressed_count']}/6</span>
        </div>
        <div style="flex: 1 1 260px; background: #ffffff; border: 1px solid {r['badge_color']}; border-radius: 8px; padding: 6px 10px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-size: 11px; color: {r['badge_color']}; font-weight: 700;">🔵 РЕАКЦИЯ: {r['status_text']}</span>
            <span style="background: {r['badge_color']}; color: #fff; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; white-space: nowrap;">Увяло: {r['stressed_count']}/6</span>
        </div>
        <div style="flex: 1 1 220px; background: #ffffff; border: 1px solid {sat['badge_color']}; border-radius: 8px; padding: 6px 10px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-size: 11px; color: {sat['badge_color']}; font-weight: 700;">🟣 С20: {sat['status_text']}</span>
            <span style="background: {sat['badge_color']}; color: #fff; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; white-space: nowrap;">Микроскопия</span>
        </div>
    </div>
    """


def render_wave2_tray_layout(records_today: List[Dict[str, Any]], active_pot_id: str) -> str:
    """
    Покогортный конвейер съемки со встроенными статусами триггеров в заголовках блоков:
    1. КОНТРОЛЬ (К1-К6)
    2. РЕАКЦИЯ (Р1-Р6)
    3. ПРЕВЕНЦИЯ (П1-П6)
    4. САТЕЛЛИТ (С20) + ЛИЗИМЕТР (Х0)
    """
    by_pot = {str(r.get("ID", "")).strip().upper(): r for r in records_today}
    status = evaluate_cohort_cluster_status(records_today)
    p_st = status["prevention"]
    r_st = status["reaction"]
    sat_st = status.get("satellite", {"status_text": "Донор лаковых реплик (долив до 100.0 г)", "badge_color": "#8b5cf6"})

    def render_pot_tile(pid: str) -> str:
        meta = POTS_CATALOG.get(pid, {"id": pid, "cohort": "Unknown", "block": 0, "color": "#64748b", "badge": pid, "target_weight": 100.0, "has_probe": False})
        is_measured = pid in by_pot
        is_selected = (pid == active_pot_id)
        
        bg_card = "#eff6ff" if is_selected else ("#f0fdf4" if is_measured else "#f8fafc")
        border_col = "#2563eb" if is_selected else ("#16a34a" if is_measured else "#cbd5e1")
        border_w = "3px" if is_selected else "1px"
        check_icon = "✓" if is_measured else "○"
        check_col = "#16a34a" if is_measured else "#94a3b8"

        rec = by_pot.get(pid, {})
        wt = rec.get('Weight_g', '')
        wt_text = f"{wt} г" if (wt and wt != '--') else ("100.0 г" if not is_measured else "NoIR снят")
        
        dt = rec.get('Delta_T_C', '')
        dt_text = f"ΔT: {dt}°" if (dt and dt != '--') else ("" if not is_measured else "жду ввода")

        return f"""
        <button type="button" onclick="selectWave2Pot('{pid}')" 
            style="display: flex; flex-direction: column; align-items: center; justify-content: space-between;
                   background: {bg_card}; border: {border_w} solid {border_col}; border-radius: 7px;
                   padding: 4px 2px; cursor: pointer; transition: all 0.15s; min-height: 48px; text-align: center; width: 100%; box-sizing: border-box; min-width: 0; overflow: hidden;">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 0 3px;">
                <span style="font-weight: 800; font-size: 13px; color: {meta['color']};">{pid}</span>
                <span style="font-weight: 800; font-size: 13px; color: {check_col};">{check_icon}</span>
            </div>
            <div style="font-size: 10.5px; font-weight: 600; color: #334155;">{wt_text}</div>
            <div style="font-size: 9.5px; color: #64748b;">{dt_text}</div>
        </button>
        """

    cohort_x = ["X0"]
    cohort_k = ["K1", "K2", "K3", "K4", "K5", "K6"]
    cohort_r = ["R1", "R2", "R3", "R4", "R5", "R6"]
    cohort_p = ["P1", "P2", "P3", "P4", "P5", "P6"]
    cohort_sat = ["C20"]

    k_measured = sum(1 for k in cohort_k if k in by_pot)
    mean_ctrl_dt = p_st.get("mean_control_dt")
    k_subline = f"Ежедн. долив до 100.0 г · базис ΔT̄={mean_ctrl_dt}°" if mean_ctrl_dt is not None else "Ежедневный полив до 100.0 г (живой базис ΔT)"

    return f"""
    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px 14px; margin-bottom: 10px; box-shadow: 0 3px 10px rgba(0,0,0,0.03);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-weight: 700; font-size: 13.5px; color: #0f172a;">
                📸 ОЧЕРЕДЬ СЪЕМКИ ПО КОГОРТАМ: КОНТРОЛЬ &rarr; РЕАКЦИЯ &rarr; ПРЕВЕНЦИЯ &rarr; САТЕЛЛИТ И ЛИЗИМЕТР
                <span style="font-size: 11.5px; font-weight: 400; color: #64748b; margin-left: 6px;">
                    (Замерено: {len(by_pot)}/{len(POTS_CATALOG)})
                </span>
            </div>
            <div style="font-size: 11px; color: #64748b;">
                Кликните на горшок для пересъемки
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px;">
            <!-- 1. КОНТРОЛЬ -->
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 9px; padding: 7px 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px; margin-bottom: 2px;">
                    <span style="font-size: 11.5px; font-weight: 800; color: #15803d;">1. 🟢 КОНТРОЛЬ (К1–К6)</span>
                    <span style="background: #059669; color: #fff; font-weight: 700; font-size: 10px; padding: 1px 6px; border-radius: 4px; white-space: nowrap;">Эталон: {k_measured}/6</span>
                </div>
                <div title="{k_subline}" style="font-size: 10px; font-weight: 600; color: #166534; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{k_subline}</div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_k)}
                </div>
            </div>

            <!-- 2. РЕАКЦИЯ -->
            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 9px; padding: 7px 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px; margin-bottom: 2px;">
                    <span style="font-size: 11.5px; font-weight: 800; color: #1d4ed8;">2. 🔵 РЕАКЦИЯ (Р1–Р6)</span>
                    <span style="background: {r_st['badge_color']}; color: #fff; font-weight: 700; font-size: 10px; padding: 1px 6px; border-radius: 4px; white-space: nowrap;">Увяло: {r_st['stressed_count']}/6</span>
                </div>
                <div title="{r_st['status_text']} (порог: тургор ≤2 у ≥4/6)" style="font-size: 10px; font-weight: 600; color: {r_st['badge_color']}; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{r_st['status_text']}</div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_r)}
                </div>
            </div>

            <!-- 3. ПРЕВЕНЦИЯ -->
            <div style="background: #fefce8; border: 1px solid #fef08a; border-radius: 9px; padding: 7px 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px; margin-bottom: 2px;">
                    <span style="font-size: 11.5px; font-weight: 800; color: #a16207;">3. 🟡 ПРЕВЕНЦИЯ (П1–П6)</span>
                    <span style="background: {p_st['badge_color']}; color: #fff; font-weight: 700; font-size: 10px; padding: 1px 6px; border-radius: 4px; white-space: nowrap;">Стресс: {p_st['stressed_count']}/6</span>
                </div>
                <div title="{p_st['status_text']} (порог: ΔΔT ≥+0.6°C у ≥4/6)" style="font-size: 10px; font-weight: 600; color: {p_st['badge_color']}; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{p_st['status_text']}</div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_p)}
                </div>
            </div>

            <!-- 4. САТЕЛЛИТ И ЛИЗИМЕТР -->
            <div style="background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 9px; padding: 7px 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px; margin-bottom: 2px;">
                    <span style="font-size: 11.5px; font-weight: 800; color: #6d28d9;">4. 🟣 С20 + ⚖️ Х0</span>
                    <span style="background: {sat_st['badge_color']}; color: #fff; font-weight: 700; font-size: 10px; padding: 1px 6px; border-radius: 4px; white-space: nowrap;">Микроскопия</span>
                </div>
                <div title="{sat_st['status_text']}" style="font-size: 10px; font-weight: 600; color: {sat_st['badge_color']}; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{sat_st['status_text']}</div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px;">
                    {''.join(render_pot_tile(p) for p in cohort_sat + cohort_x)}
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

    async function saveRowEdit(pid, isAuto = false) {{
        const wtEl = document.getElementById('cell_wt_' + pid);
        const tlEl = document.getElementById('cell_tl_' + pid);
        const trEl = document.getElementById('cell_tr_' + pid);
        const soilEl = document.getElementById('cell_soil_' + pid);
        const rowEl = document.getElementById('row_' + pid);
        const btn = document.getElementById('btn_save_' + pid);

        const wt = wtEl ? wtEl.value : '';
        const tl = tlEl ? tlEl.value : '';
        const tr = trEl ? trEl.value : '4';

        if (btn && !isAuto) {{
            btn.disabled = true;
            btn.innerText = '⏳';
        }}

        const formData = new FormData();
        formData.append('pot_id', pid);
        formData.append('weight_g', wt);
        formData.append('t_leaf', tl);
        formData.append('turgor_score', tr);
        if (soilEl) {{
            formData.append('moisture_pct', soilEl.value);
        }}
        const taEl = document.getElementById('cell_ta_' + pid);
        if (taEl && taEl.dataset && taEl.dataset.ta) {{
            formData.append('t_air', taEl.dataset.ta);
        }}

        try {{
            const resp = await fetch('/api/wave2/update_record', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();
            if (res.status === 'ok') {{
                if (res.delta_t !== undefined) {{
                    const dtCell = document.getElementById('cell_dt_' + pid);
                    if (dtCell) dtCell.innerText = res.delta_t;
                }}
                const doseCell = document.getElementById('cell_dose_' + pid);
                if (doseCell) {{
                    if (res.dose_html !== undefined) {{
                        doseCell.innerHTML = res.dose_html;
                    }} else if (res.dose !== undefined) {{
                        doseCell.innerText = res.dose;
                    }}
                }}
                const thSpan = document.querySelector('#cell_th_' + pid + ' a span');
                if (thSpan && tl) {{
                    thSpan.innerText = tl + '°';
                }}
                if (rowEl) {{
                    rowEl.style.transition = 'background-color 0.3s ease';
                    rowEl.style.backgroundColor = '#ecfdf5';
                    setTimeout(() => {{
                        rowEl.style.backgroundColor = '';
                    }}, 1200);
                }}
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = '✅';
                    setTimeout(() => {{
                        btn.innerText = '💾';
                    }}, 1200);
                }}
            }} else {{
                if (!isAuto) {{
                    alert('Ошибка обновления [' + pid + ']: ' + (res.error || res.message || 'Неизвестная ошибка'));
                }}
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = '❌';
                    setTimeout(() => {{ btn.innerText = '💾'; }}, 1500);
                }}
            }}
        }} catch(err) {{
            console.error('Ошибка сохранения [' + pid + ']:', err);
            if (!isAuto) {{
                alert('Ошибка сохранения: ' + err);
            }}
            if (btn) {{
                btn.disabled = false;
                btn.innerText = '❌';
                setTimeout(() => {{ btn.innerText = '💾'; }}, 1500);
            }}
        }}
    }}

    async function uploadThermalImage(pid, inputEl) {{
        if (!inputEl || !inputEl.files || inputEl.files.length === 0) return;
        const file = inputEl.files[0];
        
        const cell = document.getElementById('cell_th_' + pid);
        if (cell) cell.innerHTML = '<span style="color:#0284c7;font-size:11px;font-weight:700;">⏳ Загрузка...</span>';

        const formData = new FormData();
        formData.append('pot_id', pid);
        formData.append('thermal_file', file);

        try {{
            const resp = await fetch('/api/wave2/upload_thermal', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();
            if (res.status === 'ok') {{
                const fname = res.filename;
                let thTxt = '✓';
                if (res.ocr_temp) {{
                    const tlEl = document.getElementById('cell_tl_' + pid);
                    if (tlEl) {{
                        tlEl.value = res.ocr_temp;
                    }}
                    if (res.delta_t !== undefined) {{
                        const dtCell = document.getElementById('cell_dt_' + pid);
                        if (dtCell) dtCell.innerText = res.delta_t;
                    }}
                    thTxt = res.ocr_temp + '°';
                    saveRowEdit(pid, true);
                }} else {{
                    const tlEl = document.getElementById('cell_tl_' + pid);
                    if (tlEl && tlEl.value && tlEl.value !== '--') {{
                        thTxt = tlEl.value + '°';
                    }}
                }}
                if (cell) {{
                    cell.innerHTML = `
                        <a href="/wave2_image/${{fname}}" target="_blank" onclick="openImageViewer('/wave2_image/${{fname}}', 'Термограмма UTi120S — Горшок [${{pid}}] (${{thTxt}})'); return false;" title="Открыть термограмму [${{pid}}]" style="color: #0d9488; text-decoration: none; font-weight: 700; white-space: nowrap;">
                            <span style="font-family: monospace; font-size: 11px;">${{thTxt}}</span> 🔍
                        </a>
                    `;
                }}
                const rowEl = document.getElementById('row_' + pid);
                if (rowEl) {{
                    rowEl.style.transition = 'background-color 0.3s ease';
                    rowEl.style.backgroundColor = '#ecfdf5';
                    setTimeout(() => {{ rowEl.style.backgroundColor = ''; }}, 1200);
                }}
            }} else {{
                alert('Ошибка загрузки термограммы: ' + (res.error || res.message || 'Ошибка'));
                if (cell) {{
                    cell.innerHTML = '<span style="font-family: monospace; font-size: 11px; color: #94a3b8; font-weight: 600;">—</span>';
                }}
            }}
        }} catch(err) {{
            alert('Сетевая ошибка при загрузке: ' + err);
            if (cell) {{
                cell.innerHTML = '<span style="font-family: monospace; font-size: 11px; color: #94a3b8; font-weight: 600;">—</span>';
            }}
        }} finally {{
            if (inputEl) inputEl.value = '';
        }}
    }}

    async function grabUtiThermal(pid) {{
        const cell = document.getElementById('cell_th_' + pid);
        if (cell) cell.innerHTML = '<span style="color:#0284c7;font-size:11px;font-weight:700;">⏳ Считывание с UTi120S...</span>';

        const formData = new FormData();
        formData.append('pot_id', pid);

        try {{
            const resp = await fetch('/api/wave2/grab_uti_thermal', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();
            if (res.status === 'ok') {{
                const fname = res.filename;
                let thTxt = '✓';
                if (res.ocr_temp) {{
                    const tlEl = document.getElementById('cell_tl_' + pid);
                    if (tlEl) {{
                        tlEl.value = res.ocr_temp;
                    }}
                    if (res.delta_t !== undefined) {{
                        const dtCell = document.getElementById('cell_dt_' + pid);
                        if (dtCell) dtCell.innerText = res.delta_t;
                    }}
                    thTxt = res.ocr_temp + '°';
                    saveRowEdit(pid, true);
                }} else {{
                    const tlEl = document.getElementById('cell_tl_' + pid);
                    if (tlEl && tlEl.value && tlEl.value !== '--') {{
                        thTxt = tlEl.value + '°';
                    }}
                }}
                if (cell) {{
                    cell.innerHTML = `
                        <a href="/wave2_image/${{fname}}" target="_blank" onclick="openImageViewer('/wave2_image/${{fname}}', 'Термограмма UTi120S — Горшок [${{pid}}] (${{thTxt}})'); return false;" title="Открыть термограмму [${{pid}}]" style="color: #0d9488; text-decoration: none; font-weight: 700; white-space: nowrap;">
                            <span style="font-family: monospace; font-size: 11px;">${{thTxt}}</span> 🔍
                        </a>
                    `;
                }}
                const rowEl = document.getElementById('row_' + pid);
                if (rowEl) {{
                    rowEl.style.transition = 'background-color 0.3s ease';
                    rowEl.style.backgroundColor = '#ecfdf5';
                    setTimeout(() => {{ rowEl.style.backgroundColor = ''; }}, 1200);
                }}
            }} else {{
                alert('Тепловизор UTi120S: ' + (res.message || res.error || 'Не удалось считать'));
                if (cell) {{
                    cell.innerHTML = '<span style="font-family: monospace; font-size: 11px; color: #94a3b8; font-weight: 600;">—</span>';
                }}
            }}
        }} catch(err) {{
            alert('Сетевая ошибка связи с тепловизором: ' + err);
            if (cell) {{
                cell.innerHTML = '<span style="font-family: monospace; font-size: 11px; color: #94a3b8; font-weight: 600;">—</span>';
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
    parsed_card_turgor = parse_optional_turgor(rec.get("Turgor_Score"))
    current_turgor = str(parsed_card_turgor) if parsed_card_turgor is not None else "4"
    
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

    # Оценка триггера когорты и единое решение о поливе
    status = evaluate_cohort_cluster_status(records_today)
    cohort = meta["cohort"]

    # Расчет дефицита массы без авто-PLA (Option A: целевая масса строго 100.0 г)
    has_wt = current_weight and current_weight != '--'
    raw_dose = calculate_water_dose(float(current_weight) if has_wt else 100.0, 100.0) if has_wt else None
    watering_decision = resolve_cohort_watering_decision(active_pot_id, raw_dose, status)

    if cohort == "Control":
        if raw_dose is not None:
            dose_html = f"<span style='color: #059669; font-weight: 800; font-size: 18px;'>{raw_dose} мл</span> (Ежедневный долив)"
        else:
            dose_html = "<span style='color: #64748b;'>Введите массу для расчета дозы</span>"
    elif cohort in ("Prevention", "Reaction"):
        deficit_note = f" (расчётный дефицит: {raw_dose} мл)" if raw_dose is not None else ""
        if watering_decision["watering_allowed"]:
            action_note = "ТРИГГЕР СРАБОТАЛ — ПОЛИТЬ!" if cohort == "Prevention" else "УВЯДАНИЕ — РЕАНИМАЦИЯ!"
            dose_val_txt = f"{raw_dose} мл" if raw_dose is not None else "введите массу"
            dose_html = f"<span style='color: #059669; font-weight: 800; font-size: 18px;'>{dose_val_txt}</span> ({action_note})"
        elif watering_decision["reason"] == "insufficient_data":
            grp_letter = "П" if cohort == "Prevention" else "Р"
            dose_html = (
                f"<span style='color: #d97706; font-weight: 800;'>ПОЛИВ ЗАБЛОКИРОВАН — недостаточно данных</span>"
                f" <span style='color: #64748b; font-weight: 600;'>(откроется после замера всей группы {grp_letter}){deficit_note}</span>"
            )
        else:
            if cohort == "Prevention":
                dose_html = f"<span style='color: #dc2626; font-weight: 800;'>ПОЛИВ ЗАБЛОКИРОВАН (Засуха)</span><span style='color: #64748b;'>{deficit_note}</span>"
            else:
                dose_html = f"<span style='color: #2563eb; font-weight: 800;'>ПОЛИВ ЗАБЛОКИРОВАН (Тургор в норме)</span><span style='color: #64748b;'>{deficit_note}</span>"
    elif cohort == "Lysimeter_Blank":
        if raw_dose is not None:
            dose_html = f"<span style='color: #475569; font-weight: 800; font-size: 18px;'>{raw_dose} мл</span> (Долив до 100.0 г / учет испарения почвы E)"
        else:
            dose_html = "<span style='color: #64748b;'>Взвесить и долить чистой водой до 100.0 г</span>"
    else:  # Satellite C20
        if raw_dose is not None:
            dose_html = f"<span style='color: #8b5cf6; font-weight: 800; font-size: 18px;'>{raw_dose} мл воды</span> (Долив до 100.0 г / Сателлит-микроскопия)"
        else:
            dose_html = "<span style='color: #8b5cf6;'>Долив чистой водой шприцем до 100.0 г</span>"

    return f"""
    <div class="card" style="border: 2px solid {meta['color']}; margin: 0; display: flex; flex-direction: column; justify-content: space-between; height: 100%; box-sizing: border-box;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                <span style="font-size: 22px; font-weight: 900; color: {meta['color']};">ГОРШОК [{active_pot_id}]</span>
                <span style="font-size: 14px; font-weight: 600; color: #475569;">{meta['badge']}</span>
                {probe_badge}
            </div>
            <div style="font-size: 13px; color: #64748b;">
                Целевая масса: <strong>100.0 г</strong> | T<sub>возд</sub>: <strong>{t_air:.1f} °C</strong>
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
                    <option value="4" {'selected' if str(current_turgor) == '4' else ''}>{TURGOR_SCALE[4]}</option>
                    <option value="3" {'selected' if str(current_turgor) == '3' else ''}>{TURGOR_SCALE[3]}</option>
                    <option value="2" {'selected' if str(current_turgor) == '2' else ''}>{TURGOR_SCALE[2]}</option>
                    <option value="1" {'selected' if str(current_turgor) == '1' else ''}>{TURGOR_SCALE[1]}</option>
                </select>
            </div>

            <!-- Поле 4: Термограмма UTi120S (файл) -->
            <div>
                <label style="display: block; font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">
                    4. Термограмма UTi120S (файл):
                </label>
                <input type="file" name="thermal_file" id="wave2_thermal_file" accept="image/*,.bmp,.BMP,.jpg,.jpeg,.png,.JPG,.PNG"
                    style="width: 100%; font-size: 12px; padding: 7px 8px; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box; background: #fff;">
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
            const dose = Math.max(0, 100.0 - wt).toFixed(1);
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
        records_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for rec_item in records:
            rec_ts = str(rec_item.get("Timestamp", "--")).strip()
            records_by_date.setdefault(rec_ts, []).append(rec_item)
        cluster_by_date = {
            ts_key: evaluate_cohort_cluster_status(day_recs)
            for ts_key, day_recs in records_by_date.items()
        }

        for r in reversed(records[-30:]):  # последние 30 записей
            rec_id = r.get("ID", "--")
            ts = str(r.get("Timestamp", "--")).strip()
            wt = r.get("Weight_g", "")
            t_leaf = r.get("T_Leaf_C", "")
            t_air = r.get("T_Air_C", "--")
            dt = r.get("Delta_T_C", "--")
            parsed_turgor = parse_optional_turgor(r.get("Turgor_Score"))
            turgor = str(parsed_turgor) if parsed_turgor is not None else "--"
            dose = r.get("Water_Dose_ml", "--")
            raw_deficit = None
            if wt not in (None, "", "--"):
                try:
                    raw_deficit = calculate_water_dose(float(str(wt).replace(",", ".")), 100.0)
                except (ValueError, TypeError):
                    raw_deficit = None
            row_cluster = cluster_by_date.get(ts) or evaluate_cohort_cluster_status([])
            decision = resolve_cohort_watering_decision(rec_id, raw_deficit, row_cluster)
            if decision["watering_allowed"] and decision["effective_dose"] is None:
                dose_display = f'<span style="color: #059669; font-weight: 800;">{dose}</span>'
            else:
                dose_display = format_watering_decision_output(decision)["dose_html"]
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

            # Ячейка Термограммы в едином стиле с NDVI (превью с температурой: 24.0° 🔍 или —)
            if th_file and th_file != "--":
                clean_th = os.path.basename(th_file)
                if t_leaf and t_leaf != "--":
                    try:
                        th_txt = f"{float(t_leaf):.1f}°"
                    except (ValueError, TypeError):
                        th_txt = f"{t_leaf}°"
                else:
                    th_txt = "✓"
                th_cell = f'''<div id="cell_th_{rec_id}" style="text-align: center;"><a href="/wave2_image/{clean_th}" target="_blank" onclick="openImageViewer(\'/wave2_image/{clean_th}\', \'Термограмма UTi120S — Горшок [{rec_id}] ({th_txt} OCR)\'); return false;" title="Термограмма [{rec_id}] — {th_txt} (распознано OCR)" style="color: #0d9488; text-decoration: none; font-weight: 700; white-space: nowrap;"><span style="font-family: monospace; font-size: 11px;">{th_txt}</span> 🔍</a></div>'''
            else:
                th_cell = f'''<div id="cell_th_{rec_id}" style="text-align: center;"><span style="font-family: monospace; font-size: 11px; color: #94a3b8; font-weight: 600;">—</span></div>'''

            meta = POTS_CATALOG.get(rec_id, {})
            color = meta.get("color", "#475569")
            has_probe = meta.get("has_probe", False) or rec_id in ("K1", "R1", "P1")
            soil = r.get("Moisture_Pct", "--")
            if has_probe:
                soil_cell = f'''<input type="number" step="0.1" value="{soil if soil != '--' else ''}" placeholder="--" id="cell_soil_{rec_id}" onchange="saveRowEdit(\'{rec_id}\', true)" onkeydown="if(event.key===\'Enter\') this.blur();" style="width: 55px; padding: 4px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 4px; text-align: center;">'''
            else:
                soil_cell = '<span style="color: #94a3b8; font-weight: 600;">--</span>'

            rows_html.append(f"""
            <tr id="row_{rec_id}" style="border-bottom: 1px solid #f1f5f9;">
                <td style="padding: 8px 10px; font-weight: 800; color: {color};">{rec_id}</td>
                <td style="padding: 8px 10px; font-size: 11px; color: #64748b;">{ts}</td>
                <td style="padding: 6px 4px;">
                    <input type="number" step="0.1" value="{wt if wt != '--' else ''}" placeholder="--" id="cell_wt_{rec_id}" 
                        onchange="saveRowEdit('{rec_id}', true)"
                        onkeydown="if(event.key==='Enter') this.blur();"
                        style="width: 70px; padding: 4px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 4px;">
                </td>
                <td style="padding: 6px 4px;">
                    <input type="number" step="0.1" value="{t_leaf if t_leaf != '--' else ''}" placeholder="--" id="cell_tl_{rec_id}" 
                        onchange="saveRowEdit('{rec_id}', true)"
                        onkeydown="if(event.key==='Enter') this.blur();"
                        style="width: 65px; padding: 4px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 4px;">
                </td>
                <td id="cell_ta_{rec_id}" data-ta="{t_air}" style="padding: 8px 10px; font-size: 12px; color: #64748b;">{t_air}°</td>
                <td id="cell_dt_{rec_id}" style="padding: 8px 10px; font-size: 12px; font-weight: 700; color: #0284c7;">{dt}</td>
                <td style="padding: 6px 4px; text-align: center;">{soil_cell}</td>
                <td style="padding: 6px 4px;">
                    <select id="cell_tr_{rec_id}" onchange="saveRowEdit('{rec_id}', true)" style="padding: 4px; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px;">
                        <option value="--" {'selected' if str(turgor) == '--' else ''}>--</option>
                        <option value="4" {'selected' if str(turgor) == '4' else ''}>4</option>
                        <option value="3" {'selected' if str(turgor) == '3' else ''}>3</option>
                        <option value="2" {'selected' if str(turgor) == '2' else ''}>2</option>
                        <option value="1" {'selected' if str(turgor) == '1' else ''}>1</option>
                    </select>
                </td>
                <td id="cell_dose_{rec_id}" style="padding: 8px 10px; font-size: 12px; font-weight: 800; color: #059669;">{dose_display}</td>
                <td style="padding: 8px 10px;">{ndvi_cell}</td>
                <td id="cell_pla_{rec_id}" data-pla="{pla}" style="padding: 8px 10px; font-size: 12px;">{pla}</td>
                <td style="padding: 8px 10px;">{th_cell}</td>
                <td style="padding: 6px 4px; text-align: center; white-space: nowrap;">
                    <input type="file" id="file_th_{rec_id}" accept="image/*,.bmp,.BMP,.jpg,.jpeg,.png,.JPG,.PNG" style="display:none;" onchange="uploadThermalImage('{rec_id}', this)">
                    <button type="button" onclick="document.getElementById('file_th_{rec_id}').click()" title="Загрузить снимок с компьютера через проводник" 
                        style="width: 28px; height: 28px; padding: 0; display: inline-flex; align-items: center; justify-content: center; background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.15s ease;">
                        📷
                    </button>
                    <button type="button" onclick="openUtiFolderModal('{rec_id}')" title="Открыть папку Images на тепловизоре (выбрать, резервировать и стереть)" 
                        style="width: 28px; height: 28px; padding: 0; display: inline-flex; align-items: center; justify-content: center; background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 6px; cursor: pointer; font-size: 13px; margin-left: 4px; transition: all 0.15s ease;">
                        📁
                    </button>
                    <button type="button" onclick="reshootWave2Pot('{rec_id}')" title="Выбрать этот горшок и переснять оптику NoIR" 
                        style="width: 28px; height: 28px; padding: 0; display: inline-flex; align-items: center; justify-content: center; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; cursor: pointer; font-size: 13px; margin-left: 4px; transition: all 0.15s ease;">
                        🔄
                    </button>
                    <button type="button" onclick="deleteWave2Row('{rec_id}')" title="Удалить ошибочный замер" 
                        style="width: 28px; height: 28px; padding: 0; display: inline-flex; align-items: center; justify-content: center; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; cursor: pointer; font-size: 13px; margin-left: 4px; transition: all 0.15s ease;">
                        🗑️
                    </button>
                </td>
            </tr>
            """)

    return f"""
    <table style="width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; text-align: left;">
        <thead>
            <tr style="background: #f8fafc; color: #475569;">
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">ID</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">Время</th>
                <th style="padding: 10px 6px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">Масса (г)</th>
                <th style="padding: 10px 6px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">T листа (°C)</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">T возд (°C)</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">ΔT (°C)</th>
                <th style="padding: 10px 6px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;">Почва (%)</th>
                <th style="padding: 10px 6px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">Тургор</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">Доза (мл)</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">NDVI</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: left;">PLA (см²)</th>
                <th style="padding: 10px 8px; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;">Термограмма</th>
                <th style="padding: 10px 8px; text-align: center; background: #f8fafc; border-bottom: 2px solid var(--sirius-teal); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">Действие</th>
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

    <!-- МОДАЛЬНОЕ ОКНО: ПАПКА IMAGES НА ТЕПЛОВИЗОРЕ UTI120S -->
    <div id="utiFolderModal" style="display:none; position:fixed; z-index:10001; left:0; top:0; width:100%; height:100%; background:rgba(15,23,42,0.7); align-items:center; justify-content:center; backdrop-filter:blur(4px);" onclick="if(event.target===this) closeUtiFolderModal()">
        <div style="background:#ffffff; border-radius:12px; width:720px; max-width:94vw; max-height:88vh; display:flex; flex-direction:column; box-shadow:0 20px 48px rgba(0,0,0,0.4); border:2px solid #6366f1; overflow:hidden;" onclick="event.stopPropagation()">
            <!-- Header -->
            <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 18px; background:#f8fafc; border-bottom:1px solid #e2e8f0;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:20px;">📁</span>
                    <h3 style="margin:0; font-size:15px; font-weight:800; color:#0f172a;">
                        Папка Images на тепловизоре UTi120S
                    </h3>
                    <span id="utiModalTargetBadge" style="background:#6366f1; color:#fff; font-size:12px; font-weight:800; padding:2px 8px; border-radius:6px;">Обзор</span>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                    <button type="button" onclick="refreshUtiFolderList()" title="Обновить список файлов на тепловизоре" style="background:#e0e7ff; color:#4338ca; border:none; padding:5px 10px; border-radius:6px; font-size:12px; font-weight:700; cursor:pointer;">
                        🔄 Обновить
                    </button>
                    <button type="button" onclick="closeUtiFolderModal()" style="background:#e2e8f0; border:none; width:30px; height:30px; border-radius:6px; font-size:16px; cursor:pointer; font-weight:bold; color:#475569;">✕</button>
                </div>
            </div>

            <!-- Инфо-панель: резервирование и стирание -->
            <div style="padding:8px 18px; background:#eef2ff; border-bottom:1px solid #e0e7ff; font-size:11px; color:#3730a3; display:flex; justify-content:space-between; align-items:center;">
                <span>🔒 <strong>Правило забора:</strong> при выборе снимок копируется на станцию, <strong>резервируется в архив</strong> (<code>data/thermal_camera_backup</code>) и <strong>стирается с тепловизора</strong>.</span>
                <span id="utiFilesCountBadge" style="font-weight:700; background:#c7d2fe; color:#312e81; padding:2px 6px; border-radius:4px;">Считывание...</span>
            </div>

            <!-- Быстрый выбор горшка (если открыто из шапки) -->
            <div id="utiPotSelectorBar" style="display:flex; align-items:center; gap:10px; padding:8px 18px; background:#f8fafc; border-bottom:1px solid #f1f5f9;">
                <label style="font-size:12px; font-weight:700; color:#334155;">Целевой горшок для привязки:</label>
                <select id="utiSelectedPot" style="padding:4px 8px; font-size:12px; font-weight:700; border:1px solid #cbd5e1; border-radius:6px; background:#fff;">
                    <option value="K1">K1 (Контроль)</option>
                    <option value="K2">K2 (Контроль)</option>
                    <option value="K3">K3 (Контроль)</option>
                    <option value="K4">K4 (Контроль)</option>
                    <option value="K5">K5 (Контроль)</option>
                    <option value="K6">K6 (Контроль)</option>
                    <option value="R1">R1 (Реакция)</option>
                    <option value="R2">R2 (Реакция)</option>
                    <option value="R3">R3 (Реакция)</option>
                    <option value="R4">R4 (Реакция)</option>
                    <option value="R5">R5 (Реакция)</option>
                    <option value="R6">R6 (Реакция)</option>
                    <option value="P1">P1 (Превенция)</option>
                    <option value="P2">P2 (Превенция)</option>
                    <option value="P3">P3 (Превенция)</option>
                    <option value="P4">P4 (Превенция)</option>
                    <option value="P5">P5 (Превенция)</option>
                    <option value="P6">P6 (Превенция)</option>
                    <option value="X0">X0 (Лизиметр)</option>
                </select>
                <span style="font-size:11px; color:#64748b;">(выберите нужный горшок перед импортом снимка)</span>
            </div>

            <!-- Тело: список файлов на приборе -->
            <div id="utiFolderBody" style="padding:14px 18px; overflow-y:auto; flex:1; max-height:calc(88vh - 160px);">
                <div style="text-align:center; padding:30px; color:#64748b; font-size:13px;">
                    ⏳ Загрузка списка файлов с накопителя тепловизора...
                </div>
            </div>
        </div>
    </div>

    <script>
    let utiCurrentTargetPot = '';

    function openUtiFolderModal(potId) {{
        utiCurrentTargetPot = potId || '';
        const modal = document.getElementById('utiFolderModal');
        const badge = document.getElementById('utiModalTargetBadge');
        const sel = document.getElementById('utiSelectedPot');
        if (sel) {{
            if (utiCurrentTargetPot) sel.value = utiCurrentTargetPot;
        }}
        if (badge) {{
            badge.innerText = utiCurrentTargetPot ? ('Горшок [' + utiCurrentTargetPot + ']') : 'Выбор горшка';
            badge.style.background = utiCurrentTargetPot ? '#059669' : '#6366f1';
        }}
        if (modal) modal.style.display = 'flex';
        refreshUtiFolderList();
    }}

    function closeUtiFolderModal() {{
        const modal = document.getElementById('utiFolderModal');
        if (modal) modal.style.display = 'none';
    }}

    async function refreshUtiFolderList() {{
        const body = document.getElementById('utiFolderBody');
        const cntBadge = document.getElementById('utiFilesCountBadge');
        if (!body) return;
        body.innerHTML = '<div style="text-align:center; padding:30px; color:#64748b; font-size:13px;">⏳ Считывание папки /media/uti120s/Images и распознавание...</div>';
        
        try {{
            const resp = await fetch('/api/wave2/uti_images_list');
            const data = await resp.json();
            if (data.status !== 'ok' || !data.mounted) {{
                if (cntBadge) cntBadge.innerText = '0 файлов';
                body.innerHTML = `
                    <div style="text-align:center; padding:30px; color:#dc2626;">
                        <div style="font-size:24px; margin-bottom:8px;">⚠️</div>
                        <div style="font-weight:700; font-size:14px;">${{data.message || 'Тепловизор не найден'}}</div>
                        <div style="font-size:12px; color:#64748b; margin-top:6px;">Проверьте, что кабель тепловизора UTi120S вставлен в USB-порт станции Orange Pi.</div>
                        <button type="button" onclick="refreshUtiFolderList()" style="margin-top:14px; background:#6366f1; color:#fff; border:none; padding:6px 14px; border-radius:6px; font-weight:700; cursor:pointer;">Повторить попытку</button>
                    </div>
                `;
                return;
            }}

            if (cntBadge) cntBadge.innerText = data.count + ' снимков на карте';

            if (!data.files || data.files.length === 0) {{
                body.innerHTML = `
                    <div style="text-align:center; padding:30px; color:#059669;">
                        <div style="font-size:24px; margin-bottom:8px;">🎉</div>
                        <div style="font-weight:700; font-size:14px;">На тепловизоре нет новых снимков!</div>
                        <div style="font-size:12px; color:#64748b; margin-top:6px;">Все предыдущие кадры уже были скопированы и очищены с карты памяти.</div>
                    </div>
                `;
                return;
            }}

            let html = '';

            // Таблица всех файлов с превью и температурой
            html += `
                <table style="width:100%; border-collapse:collapse; font-size:12px;">
                    <thead>
                        <tr style="background:#f8fafc; border-bottom:1px solid #e2e8f0; color:#64748b; font-size:11px;">
                            <th style="padding:8px 10px; text-align:center; width:135px;">Превью (T° экрана)</th>
                            <th style="padding:8px 10px; text-align:left;">Снимок / Время</th>
                            <th style="padding:8px 10px; text-align:center; width:110px;">Температура</th>
                            <th style="padding:8px 10px; text-align:center; width:140px;">Действие</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            for (const f of data.files) {{
                const safeName = f.name.replace(/[^a-zA-Z0-9_]/g, '_');
                let tempHtml = '';
                let tempTitle = '';
                if (f.ocr_temp !== null && f.ocr_temp !== undefined) {{
                    tempHtml = `<span style="background: #ecfdf5; color: #047857; font-weight: 800; font-size: 13px; padding: 4px 8px; border-radius: 6px; border: 1px solid #a7f3d0; white-space: nowrap;">🌡️ ${{f.ocr_temp}}°C</span>`;
                    tempTitle = ` (${{f.ocr_temp}}°C)`;
                }} else {{
                    tempHtml = `<span id="ocr_box_${{safeName}}"><button type="button" onclick="fetchFileOcr('${{f.name}}', this)" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; padding:3px 7px; border-radius:4px; font-size:11px; font-weight:600; cursor:pointer;" title="Распознать температуру">🔍 Узнать T°</button></span>`;
                }}

                html += `
                    <tr id="uti_row_${{safeName}}" style="border-bottom:1px solid #f1f5f9;">
                        <!-- Превью верхней части с температурой -->
                        <td style="padding:8px 10px; text-align:center; width:135px;">
                            <img src="/api/wave2/uti_preview_thumb/${{f.name}}?mode=top" alt="${{f.name}}" loading="lazy"
                                style="width:125px; height:48px; object-fit:contain; border-radius:6px; cursor:pointer; border:1.5px solid #cbd5e1; box-shadow:0 1px 3px rgba(0,0,0,0.12); display:block; margin:0 auto; background:#000;" 
                                onclick="openImageViewer('/api/wave2/uti_preview_thumb/${{f.name}}?full=1', 'Термограмма UTi120S — ${{f.name}}${{tempTitle}}')"
                                title="Верхняя часть снимка с температурой прибора. Кликните для просмотра всего кадра">
                        </td>
                        <!-- Имя и время -->
                        <td style="padding:8px 10px;">
                            <div style="font-weight:800; font-family:monospace; font-size:13px; color:#0f172a;">${{f.name}}</div>
                            <div style="font-size:11px; color:#64748b; margin-top:2px;">📅 ${{f.mtime_str}} &bull; ${{f.size_kb}} КБ</div>
                        </td>
                        <!-- Температура OCR -->
                        <td style="padding:8px 10px; text-align:center;">
                            ${{tempHtml}}
                        </td>
                        <!-- Кнопка импорта -->
                        <td style="padding:8px 10px; text-align:center;">
                            <button type="button" onclick="importUtiFile('${{f.name}}', this)" style="background:#6366f1; color:#fff; border:none; padding:6px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; white-space:nowrap; box-shadow:0 2px 4px rgba(99,102,241,0.25);">
                                📥 Забрать и стереть
                            </button>
                        </td>
                    </tr>
                `;
            }}

            html += '</tbody></table>';
            body.innerHTML = html;

        }} catch (err) {{
            body.innerHTML = '<div style="color:#dc2626; padding:20px; text-align:center;">Ошибка связи со станцией: ' + err + '</div>';
        }}
    }}

    async function importUtiFile(filename, btnEl) {{
        const sel = document.getElementById('utiSelectedPot');
        const targetPot = (sel && sel.value) ? sel.value : utiCurrentTargetPot;
        if (!targetPot) {{
            alert('Пожалуйста, выберите целевой горшок для привязки снимка!');
            return;
        }}

        if (btnEl) {{
            btnEl.disabled = true;
            btnEl.innerText = '⏳ Забираю...';
        }}

        const formData = new FormData();
        formData.append('pot_id', targetPot);
        formData.append('filename', filename);

        try {{
            const resp = await fetch('/api/wave2/uti_import_file', {{
                method: 'POST',
                body: formData
            }});
            const res = await resp.json();

            if (res.status === 'ok') {{
                const fname = res.filename;
                let thTxt = '✓';
                if (res.ocr_temp !== null && res.ocr_temp !== undefined) {{
                    const tlEl = document.getElementById('cell_tl_' + targetPot);
                    if (tlEl) tlEl.value = res.ocr_temp;
                    if (res.delta_t !== undefined && res.delta_t !== null) {{
                        const dtCell = document.getElementById('cell_dt_' + targetPot);
                        if (dtCell) dtCell.innerText = res.delta_t;
                    }}
                    thTxt = res.ocr_temp + '°';
                    saveRowEdit(targetPot, true);
                }}
                const cell = document.getElementById('cell_th_' + targetPot);
                if (cell) {{
                    cell.innerHTML = `
                        <a href="/wave2_image/${{fname}}" target="_blank" onclick="openImageViewer('/wave2_image/${{fname}}', 'Термограмма UTi120S — Горшок [${{targetPot}}] (${{thTxt}} OCR)'); return false;" title="Термограмма [${{targetPot}}] — ${{thTxt}} (распознано OCR)" style="color: #0d9488; text-decoration: none; font-weight: 700; white-space: nowrap;">
                            <span style="font-family: monospace; font-size: 11px;">${{thTxt}}</span> 🔍
                        </a>
                    `;
                }}
                const rowEl = document.getElementById('row_' + targetPot);
                if (rowEl) {{
                    rowEl.style.transition = 'background-color 0.3s ease';
                    rowEl.style.backgroundColor = '#ecfdf5';
                    setTimeout(() => {{ rowEl.style.backgroundColor = ''; }}, 1200);
                }}

                // Сразу убираем импортированный и удаленный файл из открытого списка модалки
                const fileRow = document.getElementById('uti_row_' + filename.replace(/[^a-zA-Z0-9_-]/g, '_'));
                if (fileRow) {{
                    fileRow.remove();
                }}

                closeUtiFolderModal();
            }} else {{
                alert('Ошибка импорта термограммы: ' + (res.message || res.error || 'Неизвестная ошибка'));
                if (btnEl) {{
                    btnEl.disabled = false;
                    btnEl.innerText = '❌ Ошибка';
                }}
            }}
        }} catch (err) {{
            alert('Сетевая ошибка при импорте: ' + err);
            if (btnEl) {{
                btnEl.disabled = false;
                btnEl.innerText = '❌ Ошибка';
            }}
        }}
    }}
    
    async function fetchFileOcr(filename, btnEl) {{
        if (btnEl) {{
            btnEl.disabled = true;
            btnEl.innerText = '⏳...';
        }}
        try {{
            const resp = await fetch('/api/wave2/uti_ocr_temp/' + encodeURIComponent(filename));
            const res = await resp.json();
            if (res.status === 'ok' && res.ocr_temp !== null && res.ocr_temp !== undefined) {{
                if (btnEl && btnEl.parentElement) {{
                    btnEl.parentElement.innerHTML = `<span style="background: #ecfdf5; color: #047857; font-weight: 800; font-size: 13px; padding: 4px 8px; border-radius: 6px; border: 1px solid #a7f3d0; white-space: nowrap;">🌡️ ${{res.ocr_temp}}°C</span>`;
                }}
            }} else {{
                if (btnEl) {{
                    btnEl.disabled = false;
                    btnEl.innerText = '—';
                }}
            }}
        }} catch(err) {{
            if (btnEl) {{
                btnEl.disabled = false;
                btnEl.innerText = 'Ошибка';
            }}
        }}
    }}

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
