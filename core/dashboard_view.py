"""
Модуль представления данных и сборки контекста дашборда станции.
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

import os
import re
import csv
import math
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from core.config import settings
from core.experiments import get_experiment_manager
from core.xiaomi_climate import get_windowsill_climate
from core.station_state import (
    CASSETTE_CATALOG, BATCH_CONFIG, get_batch_state, get_pending_session
)
from hardware.hal import get_climate_sensor

STATIC_DIR = settings.STATIC_DIR
DATA_DIR = settings.DATA_DIR

RU_MONTHS = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
]

def calc_vpd(t_c: float, rh_pct: float) -> float:
    """Расчет дефицита упругости водяного пара (Vapor Pressure Deficit, кПа)."""
    try:
        es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
        ea = es * (rh_pct / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return 0.60

def format_ru_datetime(val) -> str:
    """Форматирует дату и время в понятный русский вид: '25 февраля 2026, 14:30:15'."""
    if not val:
        return '--'
    if isinstance(val, (int, float)):
        try:
            val = datetime.fromtimestamp(val)
        except Exception:
            return str(val)
    if isinstance(val, datetime):
        m_name = RU_MONTHS[val.month - 1]
        return f"{val.day} {m_name} {val.year}, {val.strftime('%H:%M:%S')}"
    
    val_str = str(val).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y%m%d_%H%M%S'):
        try:
            dt = datetime.strptime(val_str, fmt)
            m_name = RU_MONTHS[dt.month - 1]
            return f"{dt.day} {m_name} {dt.year}, {dt.strftime('%H:%M:%S')}"
        except ValueError:
            pass
    return val_str

def format_ru_date_and_time(val) -> Tuple[str, str]:
    """Возвращает кортеж (дата, время) для аккуратного двухстрочного отображения."""
    val_str = format_ru_datetime(val)
    if ',' in val_str:
        parts = val_str.split(',', 1)
        return (parts[0].strip(), parts[1].strip())
    return (val_str, '')

def format_group_badge(grp_name: str) -> str:
    """Форматирует название группы в яркий отличительный бейдж в строгом соответствии с цветами когорт."""
    if not grp_name:
        return '--'
    grp_lower = grp_name.strip().lower()

    if 'контр' in grp_lower or 'control' in grp_lower or 'оптимум' in grp_lower or 'эталон' in grp_lower or '#1' in grp_lower:
        return f'<span style="background:#ecfdf5; color:#065f46; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #a7f3d0; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    elif 'осмос' in grp_lower or 'osmo' in grp_lower or 'сол' in grp_lower or 'salin' in grp_lower or 'nacl' in grp_lower or '#2' in grp_lower:
        return f'<span style="background:#f5f3ff; color:#6d28d9; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #ddd6fe; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    elif 'засух' in grp_lower or 'drought' in grp_lower or 'терминал' in grp_lower or 'гибель' in grp_lower or 'некроз' in grp_lower or '#3' in grp_lower:
        return f'<span style="background:#fff1f2; color:#be123c; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fecdd3; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    elif 'превенци' in grp_lower or 'prevent' in grp_lower or 'прибор' in grp_lower or 'станци' in grp_lower or 'предиктив' in grp_lower or 'репар' in grp_lower or 'ранн' in grp_lower or '#4' in grp_lower:
        return f'<span style="background:#fffbeb; color:#b45309; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #fde68a; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    elif 'реакци' in grp_lower or 'react' in grp_lower or 'глаз' in grp_lower or 'визуал' in grp_lower or 'органолепт' in grp_lower or 'тургор' in grp_lower or 'критич' in grp_lower or 'поздн' in grp_lower or '#5' in grp_lower:
        return f'<span style="background:#eff6ff; color:#1d4ed8; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #bfdbfe; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    elif 'калибро' in grp_lower or 'стенд' in grp_lower or '#6' in grp_lower:
        return f'<span style="background:#f1f5f9; color:#475569; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #cbd5e1; font-size:11px; white-space:nowrap;">{grp_name}</span>'
    else:
        return f'<span style="background:#f1f5f9; color:#475569; padding:3px 9px; border-radius:6px; font-weight:700; border:1px solid #e2e8f0; font-size:11px; white-space:nowrap;">{grp_name}</span>'

def build_status_banner(
    msg: str,
    stage_name: str,
    upd_id: str,
    del_id: str,
    found: str,
    dup_id: str,
    dup_name: str,
    wrong_id: str,
    expected: str,
    exp_id: str,
    exp_name: str
) -> str:
    """Генерация всплывающего уведомления станции."""
    raw_banner = ''
    banner_bg = '#10b981'

    if msg == 'batch_saved':
        s_lbl = stage_name if stage_name else 'Пакетная триада'
        raw_banner = f'🎉 Пакетная сессия ({s_lbl}) успешно сохранена! Все замеры добавлены в журнал.'
        banner_bg = '#10b981'
    elif msg == 'saved':
        raw_banner = '✅ Замер сохранен в базу! Переставьте следующую кассету.'
        banner_bg = '#10b981'
    elif msg == 'exp_switched':
        raw_banner = '🔄 Серия опытов успешно переключена!'
        banner_bg = '#0284c7'
    elif msg == 'exp_created':
        raw_banner = '🌱 Новая серия опытов успешно создана и выбрана как активная!'
        banner_bg = '#10b981'
    elif msg == 'updated':
        u_lbl = f' #{upd_id}' if upd_id else ''
        raw_banner = f'✏️ Исследование{u_lbl} успешно скорректировано! T листа и ΔT пересчитаны.'
        banner_bg = '#0284c7'
    elif msg == 'cancelled':
        raw_banner = 'Замер сброшен. Готов к новому старту.'
        banner_bg = '#64748b'
    elif msg == 'deleted':
        d_lbl = f' #{del_id}' if del_id else ''
        raw_banner = f'🗑️ Исследование{d_lbl} успешно удалено из журнала.'
        banner_bg = '#dc2626'
    elif msg == 'err_not_found':
        raw_banner = '⚠️ Исследование не найдено в базе данных.'
        banner_bg = '#f59e0b'
    elif msg == 'err_camera':
        raw_banner = '❌ Ошибка камеры /dev/video0. Проверьте USB подключение.'
        banner_bg = '#ef4444'
    elif msg == 'err_thermal_count':
        f_cnt = found if found else '0'
        raw_banner = f'⚠️ На тепловизоре обнаружено только {f_cnt} снимка(ов). Сделайте щелчок курком для всех кассет и убедитесь, что USB-кабель подключен.'
        banner_bg = '#ef4444'
    elif msg == 'warn_duplicate_aruco':
        d_name_str = f' ({dup_name})' if dup_name else ''
        raw_banner = f'⚠️ Внимание: маркер #{dup_id}{d_name_str} уже встречался в этой серии! Кадр принят. При необходимости выберите другую кассету ниже.'
        banner_bg = '#f59e0b'
    elif msg == 'warn_no_aruco':
        e_str = exp_name if exp_name else f'Кассета #{exp_id}'
        raw_banner = f'⚠️ ArUco-маркер не считался (закрыт листом или поврежден). Замер принят и назначен как «{e_str}». При необходимости измените кассету.'
        banner_bg = '#f59e0b'
    elif msg == 'warn_wrong_stage_aruco':
        raw_banner = f'⚠️ Предупреждение: маркер #{wrong_id} из другого этапа (ожидались кассеты: {expected}). Кадр принят, проверьте назначение кассеты.'
        banner_bg = '#f59e0b'
    elif msg == 'err_duplicate_aruco':
        d_name_str = f' ({dup_name})' if dup_name else ''
        raw_banner = f'⛔ ЗАБЛОКИРОВАН ДУБЛИКАТ: Кассета с ArUco #{dup_id}{d_name_str} УЖЕ была снята в этой серии! Вы забыли заменить кассету на упорах. Пожалуйста, смените кассету.'
        banner_bg = '#dc2626'
    elif msg == 'err_wrong_stage_aruco':
        raw_banner = f'⚠️ ДРУГОЙ ЭТАП: Обнаружен ArUco #{wrong_id}, а для выбранного этапа нужны кассеты: {expected}. Проверьте номер кассеты.'
        banner_bg = '#f59e0b'

    if raw_banner:
        return f'''
            <div id="statusAlert" style="position:relative; background:{banner_bg}; padding:12px 42px 12px 18px; border-radius:8px; font-weight:bold; margin-bottom:14px; text-align:center; color:white; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                <span>{raw_banner}</span>
                <button type="button" onclick="dismissBanner()" style="position:absolute; right:12px; top:50%; transform:translateY(-50%); background:rgba(0,0,0,0.2); border:none; color:white; width:26px; height:26px; border-radius:50%; font-size:14px; font-weight:bold; cursor:pointer; line-height:26px; text-align:center;" title="Закрыть уведомление">✕</button>
            </div>
        '''
    return ''

def build_batch_shoot_view(batch_state: dict) -> dict:
    stage_key = batch_state.get('stage_key', 'batch5')
    conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])
    cassettes = conf['cassettes']
    step_idx = len(batch_state.get('sessions', []))
    total_steps = len(cassettes)

    short_names = {
        1: "Контроль",
        2: "Осмос",
        3: "Засуха",
        4: "Превенция",
        5: "Реакция",
        6: "Стенд №0"
    }
    slots_html = ''
    for i, c in enumerate(cassettes):
        if i < step_idx:
            s_done = batch_state['sessions'][i]
            m_id = s_done.get('aruco_id')
            full_grp = s_done.get('group', f'Кадр #{i+1}')
            short_grp = short_names.get(m_id, full_grp)
            if len(short_grp) > 12:
                short_grp = short_grp[:11] + '…'
            
            if m_id:
                c_col = CASSETTE_CATALOG.get(m_id, {}).get('color', '#059669')
                badge = f'<div style="background:{c_col}18; color:{c_col}; font-size:9.5px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid {c_col}50; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">ID #{m_id}</div>'
                slot_title = f"Кассета #{m_id}"
                slot_border = f"1.5px solid {c_col}"
                slot_bg = f"{c_col}0d"
            else:
                badge = '<div style="background:#fffbeb; color:#b45309; font-size:9.5px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid #fde68a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Ручная привязка</div>'
                slot_title = f"Кадр #{i+1}"
                slot_border = "1.5px solid #cbd5e1"
                slot_bg = "#f8fafc"

            slots_html += f'''
                <div style="background:{slot_bg}; border:{slot_border}; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px;">
                    <div>
                        <span style="font-size:9.5px; color:#475569; font-weight:bold; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Замер #{i+1}</span>
                        <span style="font-size:11px; color:#0f172a; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{slot_title}</span>
                        <span style="font-size:9.5px; color:#64748b; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{full_grp}">{short_grp}</span>
                    </div>
                    {badge}
                </div>
            '''
        elif i == step_idx:
            slots_html += f'''
                <div style="background:#eff6ff; border:2px solid #3b82f6; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px; box-shadow:0 2px 6px rgba(59,130,246,0.2);">
                    <div>
                        <span style="font-size:9.5px; color:#1d4ed8; font-weight:bold; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">ТЕКУЩИЙ ЗАМЕР</span>
                        <span style="font-size:11px; color:#1e40af; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Кадр #{step_idx + 1}</span>
                        <span style="font-size:9.5px; color:#2563eb; font-weight:600; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">из {total_steps}</span>
                    </div>
                    <div style="background:#dbeafe; color:#1e40af; font-size:9px; font-weight:bold; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px solid #bfdbfe; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Любая кассета</div>
                </div>
            '''
        else:
            slots_html += f'''
                <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:6px 4px; text-align:center; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; overflow:hidden; min-width:0; min-height:86px; opacity:0.8;">
                    <div>
                        <span style="font-size:9.5px; color:#94a3b8; font-weight:600; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Ожидание</span>
                        <span style="font-size:11px; color:#64748b; font-weight:bold; display:block; margin:2px 0 1px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Кадр #{i+1}</span>
                        <span style="font-size:9.5px; color:#94a3b8; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">в очереди</span>
                    </div>
                    <div style="background:#f1f5f9; color:#94a3b8; font-size:9px; padding:2px 2px; border-radius:4px; margin-top:4px; border:1px dashed #cbd5e1; white-space:nowrap;">—</div>
                </div>
            '''

    return {
        'conf_title': conf['title'],
        'step_idx': step_idx,
        'total_steps': total_steps,
        'slots_html': slots_html
    }

def build_batch_await_thermal_view(batch_state: dict, t_now: int) -> dict:
    stage_key = batch_state.get('stage_key', 'stage1')
    conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['stage1'])
    all_sessions = batch_state.get('sessions', [])

    det_ids = [s.get('aruco_id') for s in all_sessions if s.get('aruco_id') is not None]
    id_counts = {cid: det_ids.count(cid) for cid in set(det_ids)}
    dup_cids = [cid for cid, cnt in id_counts.items() if cnt > 1]
    has_dups = (len(all_sessions) >= 2 and (len(set(det_ids)) <= 1 or len(dup_cids) > 0))
    missing_w_shots = [i + 1 for i, s in enumerate(all_sessions) if not str(s.get('user_weight', '')).strip()]

    warnings_box = ''
    if has_dups:
        dup_info = ', '.join([f"#{cid} ({CASSETTE_CATALOG.get(cid, {}).get('name', 'Кассета')})" for cid in dup_cids]) if dup_cids else f"#{det_ids[0]}" if det_ids else "не определен"
        warnings_box += f'''
            <div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(245,158,11,0.12);">
                <div style="display:flex; align-items:flex-start; gap:12px;">
                    <span style="font-size:26px; line-height:1;">⚠️</span>
                    <div style="flex:1;">
                        <b style="color:#b45309; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                            ВНИМАНИЕ: ОБНАРУЖЕНЫ ПОВТОРЯЮЩИЕСЯ СНИМКИ ОДНОЙ КАССЕТЫ!
                        </b>
                        <span style="font-size:12px; color:#92400e; display:block; margin-top:4px; line-height:1.45;">
                            В боксе не менялась кассета между кадрами (зафиксированы повторы маркера <b>{dup_info}</b>).
                            Станция автоматически распределила эти замеры по очередным когортам серии, но физически кадры сняты с одного объекта! 
                            При необходимости скорректируйте когорты в выпадающих списках карточек ниже перед фиксацией.
                        </span>
                    </div>
                </div>
            </div>
        '''

    if missing_w_shots:
        shots_str = ', '.join([f'#{sh}' for sh in missing_w_shots])
        warnings_box += f'''
            <div style="background:#eff6ff; border:2px solid #3b82f6; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(59,130,246,0.12);">
                <div style="display:flex; align-items:flex-start; gap:12px;">
                    <span style="font-size:24px; line-height:1;">⚖️</span>
                    <div style="flex:1;">
                        <b style="color:#1d4ed8; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                            ВЕС КАССЕТЫ НЕ ВВЕДЕН ДЛЯ КАДРОВ: {shots_str}!
                        </b>
                        <span style="font-size:12px; color:#1e40af; display:block; margin-top:4px; line-height:1.45;">
                            Для указанных кассет не была зафиксирована масса с лабораторных весов.
                            Рекомендуется ввести массу в граммах в подсвеченных полях <b>«⚖️ Масса с весов»</b> ниже для корректного расчета влагоотдачи и стресс-динамики.
                        </span>
                    </div>
                </div>
            </div>
        '''

    cards_summary = ''
    for i, s in enumerate(all_sessions):
        m_id = s.get('aruco_id')
        m_badge = f'<span style="background:#ecfdf5; color:#065f46; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">🏷️ ArUco #{m_id}</span>' if m_id else '<span style="background:#fffbeb; color:#b45309; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">⚠️ Ручная</span>'
        if m_id and m_id in dup_cids:
            m_badge += ' <span style="background:#fef3c7; color:#92400e; border:1px solid #fcd34d; padding:2px 5px; border-radius:4px; font-size:9.5px; font-weight:bold;">Повтор</span>'
        
        options_html = ''
        for cid, cdata in CASSETTE_CATALOG.items():
            sel = 'selected' if cid == m_id else ''
            options_html += f'<option value="{cid}" {sel}>#{cid}: {cdata["name"]}</option>'
            
        w_val = str(s.get('user_weight', '')).strip()
        t_val = s.get('user_t_leaf', '')
        p_val = s.get('user_pct_soil', '64.0')
        
        if not w_val:
            weight_input_html = f'''
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                    <label style="font-size:10px; font-weight:bold; color:#b45309;">⚖️ Масса, г:</label>
                    <span style="background:#fee2e2; color:#dc2626; border:1px solid #fecdd3; padding:1px 4px; border-radius:3px; font-size:8.5px; font-weight:800;">НЕ ВВЕДЕН ⚠️</span>
                </div>
                <input type="text" name="weight_g_{i}" value="" placeholder="⚠️ Введите вес (г)" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:2px dashed #f59e0b; background:#fffbeb; border-radius:4px; box-sizing:border-box;">
            '''
        else:
            weight_input_html = f'''
                <label style="font-size:10px; font-weight:bold; color:#0f766e; display:block; margin-bottom:2px;">⚖️ Масса с весов, г:</label>
                <input type="text" name="weight_g_{i}" value="{w_val}" placeholder="напр. 410.0" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1px solid #0d9488; border-radius:4px; box-sizing:border-box;">
            '''
        
        cards_summary += f'''
            <div style="flex:1; background:#ffffff; border:1.5px solid #cbd5e1; border-radius:8px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:11px; color:#64748b; font-weight:bold;">Кадр #{i+1}</span>
                    {m_badge}
                </div>
                
                <div style="margin-bottom:8px;">
                    <label style="font-size:10px; font-weight:bold; color:#1e40af; display:block; margin-bottom:2px;">Когорта / Кассета:</label>
                    <select name="cassette_id_{i}" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1.5px solid #94a3b8; border-radius:6px; background:#f8fafc;">
                        {options_html}
                    </select>
                </div>

                <img src="/static/{s.get('opt_file', 'last_ndvi.jpg')}?t={t_now}" style="height:68px; border-radius:4px; object-fit:contain; background:#0f172a; width:100%; border:1px solid #e2e8f0; margin-bottom:6px;">
                
                <div style="font-size:11px; color:#047857; font-weight:bold; text-align:center; margin-bottom:8px;">
                    NDVI: {s.get("mean_ndvi", "--")} · PLA: {s.get("leaf_area_cm2", "--")} см²
                </div>

                <div style="display:flex; flex-direction:column; gap:5px;">
                    <div>
                        {weight_input_html}
                    </div>
                    <div>
                        <label style="font-size:10px; font-weight:bold; color:#d97706; display:block;">🌡️ T листа с UTi120S (°C):</label>
                        <input type="number" step="0.1" name="t_leaf_{i}" value="{t_val}" placeholder="напр. 23.8" style="width:100%; padding:5px; font-size:12px; font-weight:bold; border:1px solid #f59e0b; border-radius:4px; box-sizing:border-box;">
                    </div>
                    <div>
                        <label style="font-size:10px; font-weight:bold; color:#0284c7; display:block;">💧 Влажность почвы, %:</label>
                        <input type="number" step="0.1" min="0" max="100" name="pct_soil_{i}" value="{p_val}" style="width:100%; padding:5px; font-size:12px; border:1px solid #38bdf8; border-radius:4px; box-sizing:border-box;">
                    </div>
                </div>
            </div>
        '''

    return {
        'conf_title': conf['title'],
        'sessions_count': len(all_sessions),
        'warnings_box': warnings_box,
        'cards_summary': cards_summary
    }

def build_batch_verify_view(batch_state: dict, t_now: int) -> dict:
    stage_key = batch_state.get('stage_key', 'stage1')
    conf = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['stage1'])
    verified = batch_state.get('verified_data', [])

    v_det_ids = [item.get('detected_id') for item in verified if item.get('detected_id') is not None]
    v_id_counts = {cid: v_det_ids.count(cid) for cid in set(v_det_ids)}
    v_dup_cids = [cid for cid, cnt in v_id_counts.items() if cnt > 1]
    v_has_dups = (len(verified) >= 2 and (len(set(v_det_ids)) <= 1 or len(v_dup_cids) > 0))
    v_missing_w = [i + 1 for i, item in enumerate(verified) if not str(item['session'].get('user_weight', '')).strip()]

    verify_warnings_box = ''
    if v_has_dups:
        v_dup_info = ', '.join([f"#{cid} ({CASSETTE_CATALOG.get(cid, {}).get('name', 'Кассета')})" for cid in v_dup_cids]) if v_dup_cids else f"#{v_det_ids[0]}" if v_det_ids else "не определен"
        verify_warnings_box += f'''
            <div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(245,158,11,0.12);">
                <div style="display:flex; align-items:flex-start; gap:12px;">
                    <span style="font-size:26px; line-height:1;">⚠️</span>
                    <div style="flex:1;">
                        <b style="color:#b45309; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                            ВНИМАНИЕ: ОБНАРУЖЕНЫ ПОВТОРЯЮЩИЕСЯ СНИМКИ ОДНОЙ КАССЕТЫ!
                        </b>
                        <span style="font-size:12px; color:#92400e; display:block; margin-top:4px; line-height:1.45;">
                            В боксе не менялась кассета между кадрами (зафиксированы повторы маркера <b>{v_dup_info}</b>).
                            Станция автоматически распределила эти кадры по когортам, но оптические снимки относятся к одному растению.
                            Убедитесь в правильности назначения когорт в выпадающих списках перед итоговым сохранением!
                        </span>
                    </div>
                </div>
            </div>
        '''

    if v_missing_w:
        v_shots_str = ', '.join([f'#{sh}' for sh in v_missing_w])
        verify_warnings_box += f'''
            <div style="background:#eff6ff; border:2px solid #3b82f6; border-radius:10px; padding:12px 16px; margin-bottom:14px; box-shadow:0 3px 10px rgba(59,130,246,0.12);">
                <div style="display:flex; align-items:flex-start; gap:12px;">
                    <span style="font-size:24px; line-height:1;">⚖️</span>
                    <div style="flex:1;">
                        <b style="color:#1d4ed8; font-size:14px; display:block; text-transform:uppercase; letter-spacing:0.3px;">
                            ВЕС КАССЕТЫ НЕ ВВЕДЕН: ЗАМЕРЫ {v_shots_str}!
                        </b>
                        <span style="font-size:12px; color:#1e40af; display:block; margin-top:4px; line-height:1.45;">
                            Рекомендуется указать фактическую массу в граммах в подсвеченных полях <b>«⚖️ Масса с весов»</b> ниже перед сохранением в базу данных.
                        </span>
                    </div>
                </div>
            </div>
        '''

    items_html = ''
    for i, item in enumerate(verified):
        s = item['session']
        assigned_id = item['assigned_id']
        detected_id = item.get('detected_id')
        shot_order = item.get('shot_order', i + 1)
        c_info = CASSETTE_CATALOG.get(assigned_id, {'id': assigned_id, 'name': s.get('group', 'Кассета'), 'color': '#0d9488'})

        if detected_id:
            marker_badge = f'<span style="background:#ecfdf5; color:#065f46; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #a7f3d0;">🏷️ ArUco #{detected_id} распознан (снята #{shot_order}-й)</span>'
        else:
            marker_badge = f'<span style="background:#fffbeb; color:#b45309; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #fde68a;">⚠️ ArUco не найден (снята #{shot_order}-й)</span>'

        options_html = ''
        for cid, cdata in CASSETTE_CATALOG.items():
            sel = 'selected' if cid == assigned_id else ''
            options_html += f'<option value="{cid}" {sel}>Кассета #{cid}: {cdata["name"]}</option>'

        items_html += f'''
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:10px; padding:12px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f1f5f9; padding-bottom:8px; margin-bottom:8px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <label style="font-weight:bold; font-size:13px; color:#334155;">Когорта:</label>
                        <select name="cassette_id_{i}" style="padding:4px 8px; font-size:13px; font-weight:bold; color:{c_info['color']}; border:1.5px solid #94a3b8; border-radius:6px; background:#f8fafc;">
                            {options_html}
                        </select>
                    </div>
                    <div style="display:flex; gap:6px; align-items:center;">
                        {marker_badge}
                        <span style="background:#ecfdf5; color:#047857; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold;">NDVI: {s['mean_ndvi']}</span>
                        <span style="background:#f0fdf4; color:#15803d; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #bbf7d0;">🌿 PLA: {s.get('leaf_area_cm2', '--')} см²</span>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-bottom:10px;">
                    <div style="text-align:center;">
                        <span style="font-size:10px; color:#64748b; display:block; margin-bottom:2px;">Спектр NoIR (кадр #{shot_order})</span>
                        <img src="/static/{s['opt_file']}?t={t_now}" style="width:100%; height:85px; object-fit:contain; background:#0f172a; border-radius:6px; border:1px solid #e2e8f0;">
                    </div>
                    <div style="text-align:center;">
                        <span style="font-size:10px; color:#64748b; display:block; margin-bottom:2px;">Тепловизор ({item['thermal_filename']})</span>
                        <img src="{item['thermal_thumb_url']}?t={t_now}" style="width:100%; height:85px; object-fit:contain; border-radius:6px; border:1px solid #e2e8f0; background:#f8fafc;">
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; align-items:start;">
                    <div style="display:flex; flex-direction:column;">
                        <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:#0f766e; white-space:nowrap; margin:0;">⚖️ Масса (г):</label>
                            {'' if str(s.get('user_weight', '')).strip() else '<span style="background:#fee2e2; color:#dc2626; border:1px solid #fecdd3; padding:1px 4px; border-radius:3px; font-size:8.5px; font-weight:800;">НЕТ ВЕСА</span>'}
                        </div>
                        <input type="text" name="weight_g_{i}" value="{s.get('user_weight', '')}" placeholder="с весов (г)" style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid var(--sirius-teal); border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                        <div style="height:22px; margin-top:4px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#64748b; background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; white-space:nowrap;">Весы (нетто)</div>
                    </div>
                    <div style="display:flex; flex-direction:column;">
                        <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:#0284c7; white-space:nowrap; margin:0;">💧 Влажность (%):</label>
                        </div>
                        <input type="number" step="0.1" min="0" max="100" name="pct_soil_{i}" value="{s.get('pct_soil', 64.0)}" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                        <div style="height:22px; margin-top:4px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#0284c7; background:#f0f9ff; border:1px solid #bae6fd; border-radius:4px; font-weight:600; white-space:nowrap;">{s.get('pct_soil', 64.0)}% ПВ</div>
                    </div>
                    <div style="display:flex; flex-direction:column;">
                        <div style="height:22px; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:#334155; white-space:nowrap; margin:0;">🌡️ T листа (°C):</label>
                            <span style="font-size:9.5px; color:#0284c7; background:#e0f2fe; padding:1px 5px; border-radius:3px; font-weight:700; white-space:nowrap;">OCR {item['t_ocr']}°</span>
                        </div>
                        <input type="number" step="0.1" name="t_leaf_{i}" id="t_leaf_{i}" value="{item['t_ocr']}" required style="height:38px; width:100%; padding:6px 10px; font-size:13px; font-weight:700; border:1.5px solid #0284c7; border-radius:6px; box-sizing:border-box; text-align:center; background:#ffffff;">
                        <div style="height:22px; margin-top:4px; display:flex; gap:2px;">
                            <button type="button" onclick="adjTemp('t_leaf_{i}', -1.0)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 1.0°C">-1°</button>
                            <button type="button" onclick="adjTemp('t_leaf_{i}', -0.5)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 0.5°C">-.5°</button>
                            <button type="button" onclick="adjTemp('t_leaf_{i}', -0.1)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Уменьшить на 0.1°C">-.1°</button>
                            <button type="button" onclick="adjTemp('t_leaf_{i}', 0.1)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 0.1°C">+.1°</button>
                            <button type="button" onclick="adjTemp('t_leaf_{i}', 0.5)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 0.5°C">+.5°</button>
                            <button type="button" onclick="adjTemp('t_leaf_{i}', 1.0)" style="flex:1; font-size:9.5px; font-weight:700; padding:0; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;" title="Увеличить на 1.0°C">+1°</button>
                        </div>
                    </div>
                </div>
            </div>
        '''

    return {
        'conf_title': conf['title'],
        'verified_count': len(verified),
        'verify_warnings_box': verify_warnings_box,
        'items_html': items_html
    }

def build_review_view(pending_session: dict, offset: int, t_now: int, uti_info: Optional[dict]) -> dict:
    s = pending_session
    if uti_info:
        thumb_url = uti_info['thumb_url']
        thumb_name = os.path.basename(uti_info['thumb_path'])
        fn_show = uti_info['filename']
        dt_show = uti_info['dt_str']
        t_leaf_init = str(uti_info['t_ocr'])
        nav_buttons = f'''
            <div style="display:flex; justify-content:space-between; margin-top:8px;">
                <a href="/?stage=review&offset={offset+1}" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">◀️ Взять предыдущий снимок</a>
                <span style="color:#94a3b8; font-size:11px;">Снимок {offset+1} из {uti_info['total']}</span>
                {f'<a href="/?stage=review&offset={max(0, offset-1)}" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">Следующий ▶️</a>' if offset > 0 else '<span></span>'}
            </div>
        '''
    else:
        thumb_url = '/static/last_ndvi.jpg'
        thumb_name = ''
        fn_show = 'Тепловизор еще не подключен'
        dt_show = '--'
        t_leaf_init = '23.5'
        nav_buttons = '''
            <div style="margin-top:8px; text-align:center;">
                <a href="/?stage=review&offset=0" style="padding:6px 12px; background:#0284c7; color:white; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">🔄 Найти снимок на тепловизоре</a>
            </div>
        '''

    aruco_badge = f'<span style="background:#059669; color:white; padding:4px 10px; border-radius:8px; font-size:11px; font-weight:700; box-shadow:0 1px 4px rgba(5,150,105,0.3); white-space:nowrap;">🎯 ArUco #{s["aruco_id"]}: {s["group"]}</span>' if s.get('aruco_id') else f'<span style="background:var(--sirius-teal); color:white; padding:4px 10px; border-radius:8px; font-size:11px; font-weight:700; white-space:nowrap;">{s["group"]}</span>'

    step1_note = f'''
        <div style="background:#f0fdf4; border:1.5px solid #bbf7d0; padding:10px 14px; border-radius:8px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                <div style="font-size:12px; color:#166534; font-weight:700; display:flex; align-items:center; gap:5px;">
                    <span>🎯</span> ArUco-маркер #{s.get('aruco_id', '--')} распознан: когорта «{s['group']}»
                </div>
                <span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; padding:2px 8px; border-radius:5px; font-weight:700; font-size:10.5px;">
                    White Ref k={s.get('k_bal', 1.025)} (PTFE)
                </span>
            </div>
            <div style="margin-top:5px; font-size:11.5px; color:#15803d;">
                ⚖️ Переставьте кассету на весы и подключите тепловизор для подтверждения параметров.
            </div>
        </div>
    ''' if s.get('aruco_id') else f'''
        <div style="background:#f0fdfa; border:1.5px solid #ccfbf1; padding:10px 14px; border-radius:8px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                <div style="font-size:12px; color:#0f766e; font-weight:700;">
                    ✓ Спектральный замер выполнен (когорта: «{s['group']}»)
                </div>
                <span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; padding:2px 8px; border-radius:5px; font-weight:700; font-size:10.5px;">
                    White Ref k={s.get('k_bal', 1.025)} (PTFE)
                </span>
            </div>
            <div style="margin-top:5px; font-size:11.5px; color:#0f766e;">
                ⚖️ Переставьте кассету на весы и подключите тепловизор для подтверждения параметров.
            </div>
        </div>
    '''

    return {
        'session': s,
        'aruco_badge': aruco_badge,
        'step1_note': step1_note,
        'thumb_url': thumb_url,
        'thumb_name': thumb_name,
        'fn_show': fn_show,
        'dt_show': dt_show,
        't_leaf_init': t_leaf_init,
        'nav_buttons': nav_buttons,
        't_now': t_now
    }

def build_table_rows_and_stats(rows: List[List[str]]) -> Tuple[List[dict], dict, str]:
    cnt_ctrl, cnt_salt, cnt_inst, cnt_eye, cnt_term = 0, 0, 0, 0, 0
    ndvis_ctrl, ndvis_salt, ndvis_inst, ndvis_eye, ndvis_term = [], [], [], [], []

    for r in rows:
        if len(r) > 2:
            grp_l = r[2].strip().lower()
            ndvi_val = None
            try:
                if len(r) >= 24 and r[11]:
                    ndvi_val = float(r[11])
                elif len(r) >= 20 and r[7]:
                    ndvi_val = float(r[7])
                elif len(r) >= 10 and r[6]:
                    ndvi_val = float(r[6])
            except (ValueError, TypeError):
                pass

            if 'превенци' in grp_l or 'прибор' in grp_l or 'станци' in grp_l:
                cnt_inst += 1
                if ndvi_val is not None: ndvis_inst.append(ndvi_val)
            elif 'реакци' in grp_l or 'глаз' in grp_l or 'визуал' in grp_l:
                cnt_eye += 1
                if ndvi_val is not None: ndvis_eye.append(ndvi_val)
            elif 'засух' in grp_l or 'терминал' in grp_l or 'гибель' in grp_l or 'некроз' in grp_l:
                cnt_term += 1
                if ndvi_val is not None: ndvis_term.append(ndvi_val)
            elif 'осмос' in grp_l or 'сол' in grp_l or 'salin' in grp_l:
                cnt_salt += 1
                if ndvi_val is not None: ndvis_salt.append(ndvi_val)
            elif 'контр' in grp_l or 'control' in grp_l or 'эталон' in grp_l:
                cnt_ctrl += 1
                if ndvi_val is not None: ndvis_ctrl.append(ndvi_val)

    def mean_s(arr, default_v="--"):
        return f"{sum(arr)/len(arr):.3f}" if arr else default_v

    m_ctrl_ndvi = mean_s(ndvis_ctrl, "0.760" if not rows else "--")
    m_salt_ndvi = mean_s(ndvis_salt, "--")
    m_inst_ndvi = mean_s(ndvis_inst, "--")
    m_eye_ndvi = mean_s(ndvis_eye, "--")
    m_term_ndvi = mean_s(ndvis_term, "--")

    eff_badge = "100% тургор"
    if ndvis_inst and ndvis_eye:
        diff_pct = round(((sum(ndvis_inst)/len(ndvis_inst)) - (sum(ndvis_eye)/len(ndvis_eye))) / (sum(ndvis_inst)/len(ndvis_inst)) * 100, 1)
        eff_badge = f"+{diff_pct}% сохранность" if diff_pct > 0 else "0% потерь"

    summary_stats = {
        'cnt_ctrl': cnt_ctrl,
        'm_ctrl_ndvi': m_ctrl_ndvi,
        'cnt_salt': cnt_salt,
        'm_salt_ndvi': m_salt_ndvi,
        'cnt_term': cnt_term,
        'm_term_ndvi': m_term_ndvi,
        'cnt_inst': cnt_inst,
        'm_inst_ndvi': m_inst_ndvi,
        'cnt_eye': cnt_eye,
        'm_eye_ndvi': m_eye_ndvi,
        'eff_badge': eff_badge
    }

    def get_cohort_order(r):
        grp = str(r[2] if len(r) > 2 else '').lower()
        if 'контр' in grp or 'control' in grp or '#1' in grp or 'эталон' in grp: return 1
        if 'осмос' in grp or 'сол' in grp or 'osmo' in grp or '#2' in grp: return 2
        if 'засух' in grp or 'drought' in grp or 'терминал' in grp or '#3' in grp: return 3
        if 'превенци' in grp or 'prevent' in grp or 'прибор' in grp or 'станци' in grp or 'предиктив' in grp or '#4' in grp: return 4
        if 'реакци' in grp or 'react' in grp or 'глаз' in grp or 'визуал' in grp or 'органолепт' in grp or '#5' in grp: return 5
        if 'калибр' in grp or 'стенд' in grp or '#6' in grp: return 6
        return 99

    def parse_row_dt(r):
        ts_str = str(r[1] if len(r) > 1 else '')
        ru_m = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
                'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12}
        try:
            p = ts_str.replace(',', '').split()
            day = int(p[0])
            mon = ru_m.get(p[1].lower(), 10)
            yr = int(p[2])
            t_p = p[3].split(':')
            return datetime(yr, mon, day, int(t_p[0]), int(t_p[1]), int(t_p[2]))
        except Exception:
            return datetime.min

    sorted_by_time = sorted(rows, key=parse_row_dt, reverse=True)
    sessions = []
    cur_sess = []
    for r in sorted_by_time:
        r_dt = parse_row_dt(r)
        if not cur_sess:
            cur_sess.append((r, r_dt))
        else:
            diff = abs((cur_sess[-1][1] - r_dt).total_seconds())
            if diff <= 3600 and len(cur_sess) < 6:
                cur_sess.append((r, r_dt))
            else:
                sessions.append(cur_sess)
                cur_sess = [(r, r_dt)]
    if cur_sess:
        sessions.append(cur_sess)

    ordered_table_rows = []
    for sess in sessions:
        sess_sorted = sorted([item[0] for item in sess], key=get_cohort_order)
        ordered_table_rows.extend(sess_sorted)

    unique_dates = []
    for r in ordered_table_rows:
        ts = r[1] if len(r) > 1 else ''
        d_str, _ = format_ru_date_and_time(ts)
        if d_str and d_str not in unique_dates:
            unique_dates.append(d_str)

    date_idx_map = {d: i for i, d in enumerate(unique_dates)}

    table_rows = []
    table_html = ''
    prev_d_str = None

    for r in ordered_table_rows:
        leaf_area_val = "--"
        if len(r) >= 25:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            if r[4] and r[5]:
                t_air_str = f'<span style="white-space:nowrap;font-size:11px;color:#334155;">{r[4]}°C <span style="color:#cbd5e1;">·</span> <span style="color:#059669;font-weight:600;">{r[5]}%</span></span>'
            else:
                t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[7]}%" if r[7] else "--"
            t_show = f"{r[8]} °C" if r[8] else "--"
            delta_str = f"{r[9]}°C" if r[9] else "--"
            ndvi_txt = f"{r[11]}±{r[12]}" if len(r)>12 else "--"
            leaf_area_val = f"{r[13]} см²" if r[13] else "--"
            th_name = r[15] if len(r)>15 else ""

            if r[9]:
                try:
                    dt_val = float(r[9])
                    if dt_val <= -0.5:
                        stress_badge = f'<span style="background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (Норма)</span>'
                    elif dt_val <= 0.5:
                        stress_badge = f'<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (Нач. стресс)</span>'
                    elif dt_val <= 1.8:
                        stress_badge = f'<span style="background:#fff7ed;color:#c2410c;border:1px solid #fb923c;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:700;">{delta_str} (ОКНО СПАСЕНИЯ)</span>'
                    else:
                        stress_badge = f'<span style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (ТОЧКА НЕВОЗВРАТА)</span>'
                except Exception:
                    stress_badge = f'<span style="white-space:nowrap;font-weight:600;">{delta_str}</span>'
            else:
                stress_badge = '<span style="color:#94a3b8;">--</span>'

        elif len(r) >= 24:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            if r[4] and r[5]:
                t_air_str = f'<span style="white-space:nowrap;font-size:11px;color:#334155;">{r[4]}°C <span style="color:#cbd5e1;">·</span> <span style="color:#059669;font-weight:600;">{r[5]}%</span></span>'
            else:
                t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[7]}%" if r[7] else "--"
            t_show = f"{r[8]} °C" if r[8] else "--"
            delta_str = f"{r[9]}°C" if r[9] else "--"
            ndvi_txt = f"{r[11]}±{r[12]}" if len(r)>12 else "--"
            if '.jpg' in r[13] or '.png' in r[13]:
                leaf_area_val = "--"
                th_name = r[14] if len(r)>14 else ""
            else:
                leaf_area_val = f"{r[13]} см²"
                th_name = r[15] if len(r)>15 else ""

            if r[9]:
                try:
                    dt_val = float(r[9])
                    if dt_val <= -0.5:
                        stress_badge = f'<span style="background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (Норма)</span>'
                    elif dt_val <= 0.5:
                        stress_badge = f'<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (Нач. стресс)</span>'
                    elif dt_val <= 1.8:
                        stress_badge = f'<span style="background:#fff7ed;color:#c2410c;border:1px solid #fb923c;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:700;">{delta_str} (ОКНО СПАСЕНИЯ)</span>'
                    else:
                        stress_badge = f'<span style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:3px 7px;border-radius:4px;font-size:11px;white-space:nowrap;font-weight:600;">{delta_str} (ТОЧКА НЕВОЗВРАТА)</span>'
                except Exception:
                    stress_badge = f'<span style="white-space:nowrap;font-weight:600;">{delta_str}</span>'
            else:
                stress_badge = '<span style="color:#94a3b8;">--</span>'

        elif len(r) >= 20:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = f"{r[3]} г" if r[3] else "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[5]}%" if r[5] else "--"
            t_show = f"{r[6]} °C" if r[6] else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[7]}±{r[8]}" if len(r)>8 else "--"
            leaf_area_val = "--"
            th_name = r[10] if len(r)>10 else ""
        else:
            m_id, ts, grp = r[0], r[1], r[2]
            wt = "--"
            t_air_str = '<span style="color:#94a3b8;">--</span>'
            pct = f"{r[4]}%" if len(r)>4 else "--"
            t_show = f"{r[5]} °C" if len(r)>5 else "--"
            stress_badge = '<span style="color:#94a3b8;">--</span>'
            ndvi_txt = f"{r[6]}±{r[7]}" if len(r)>7 else "--"
            leaf_area_val = "--"
            th_name = r[9] if len(r)>9 else ""

        opt_f = r[14] if (len(r) >= 25 and r[14]) else (r[13] if (len(r) == 24 and '.jpg' in r[13]) else '')
        if opt_f and os.path.exists(os.path.join(STATIC_DIR, opt_f)):
            ndvi_cell = f'<a href="/static/{opt_f}" target="_blank" title="Открыть карту NDVI #{m_id}" style="color:var(--sirius-teal-dark);text-decoration:none;font-weight:600;"><span style="white-space:nowrap;font-family:monospace;font-size:11px;">{ndvi_txt}</span> 🔍</a>'
        else:
            ndvi_cell = f'<span style="white-space:nowrap;font-family:monospace;font-size:11px;color:#334155;">{ndvi_txt}</span>'

        if th_name:
            m_th = re.search(r'(IMG[_\s]\d+)', th_name)
            clean_th = m_th.group(1) if m_th else th_name
            th_file_path = os.path.join(STATIC_DIR, th_name)
            if os.path.exists(th_file_path):
                th_stat = f'<a href="/static/{th_name}" target="_blank" title="Открыть термограмму #{m_id}" style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;text-decoration:none;">✓ {clean_th} 🔍</a>'
            else:
                th_stat = f'<span style="color:#059669;font-weight:bold;font-size:11px;white-space:nowrap;">✓ {clean_th}</span>'
        else:
            th_stat = '<span style="color:#d97706;font-size:11px;white-space:nowrap;font-weight:600;">⏳ Ожидает</span>'

        d_str, t_str = format_ru_date_and_time(ts)
        d_idx = date_idx_map.get(d_str, 0)
        is_odd_date = (d_idx % 2 == 1)
        date_cls = "date-group-odd" if is_odd_date else "date-group-even"
        divider_cls = " date-group-divider" if (prev_d_str is not None and d_str != prev_d_str) else ""
        prev_d_str = d_str
        row_cls = f"{date_cls}{divider_cls}"

        time_cell = f'<div style="white-space:nowrap;font-size:11px;font-weight:600;color:#0f172a;">{d_str}</div><div style="font-size:10px;color:#64748b;white-space:nowrap;">{t_str}</div>'
        grp_badge = format_group_badge(grp)
        if t_show != '--' and 'none' not in t_show.lower():
            t_leaf_html = f'''<span onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="cursor:pointer; color:#d97706; font-weight:bold; white-space:nowrap; padding:2px 5px; border-radius:4px; border-bottom:1.5px dashed #f59e0b; background:#fffbeb;" title="Нажмите, чтобы скорректировать T листа замера #{m_id} ({grp})">{t_show} <span style="font-size:10px;">✏️</span></span>'''
        else:
            t_leaf_html = f'''<span onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="cursor:pointer; color:#dc2626; font-weight:bold; white-space:nowrap; padding:2px 6px; border-radius:4px; border:1.5px dashed #ef4444; background:#fef2f2;" title="T листа не распознана! Нажмите, чтобы исправить">{t_show} <span style="font-size:10px;">✏️</span></span>'''

        del_btn = f'''<form action="/api/delete_measurement" method="post" style="margin:0;display:inline;" onsubmit="return confirm('Удалить исследование #{m_id} ({grp})?');"><input type="hidden" name="meas_id" value="{m_id}"><button type="submit" style="background:#fee2e2; border:1px solid #fca5a5; color:#dc2626; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1;" title="Удалить замер #{m_id}" onmouseover="this.style.background='#dc2626';this.style.color='#fff';" onmouseout="this.style.background='#fee2e2';this.style.color='#dc2626';">✕</button></form>'''
        edit_btn = f'''<button type="button" onclick="openEditModal('{m_id}', '{grp}', '{ts}', '{t_show}', '{wt}', '{pct}')" style="background:#e0f2fe; border:1px solid #bae6fd; color:#0369a1; border-radius:4px; padding:2px 5px; cursor:pointer; font-size:11px; font-weight:bold; line-height:1; margin-right:3px;" title="Скорректировать замер #{m_id} ({grp})" onmouseover="this.style.background='#0284c7';this.style.color='#fff';" onmouseout="this.style.background='#e0f2fe';this.style.color='#0369a1';">✏️</button>'''

        table_rows.append({
            'm_id': m_id,
            'row_cls': row_cls,
            'd_str': d_str,
            't_str': t_str,
            'grp': grp,
            'ts': ts,
            'grp_badge': grp_badge,
            'wt': wt,
            't_air_str': t_air_str,
            't_show': t_show,
            't_leaf_html': t_leaf_html,
            'stress_badge': stress_badge,
            'ndvi_cell': ndvi_cell,
            'leaf_area_val': leaf_area_val,
            'pct': pct,
            'th_stat': th_stat,
            'edit_btn': edit_btn,
            'del_btn': del_btn
        })

        table_html += f'<tr class="{row_cls}"><td><b style="color:#64748b;">#{m_id}</b></td><td>{time_cell}</td><td>{grp_badge}</td><td><b style="color:#0284c7;white-space:nowrap;">{wt}</b></td><td>{t_air_str}</td><td>{t_leaf_html}</td><td>{stress_badge}</td><td>{ndvi_cell}</td><td><b style="color:#047857;white-space:nowrap;font-size:11px;">{leaf_area_val}</b></td><td><span style="white-space:nowrap;font-weight:500;color:#334155;">{pct}</span></td><td>{th_stat}</td><td class="col-actions" style="white-space:nowrap;">{edit_btn}{del_btn}</td></tr>'

    return table_rows, summary_stats, table_html

async def build_dashboard_context(
    request,
    stage: str = 'idle',
    offset: int = 0,
    msg: str = '',
    last_grp: str = '',
    del_id: str = '',
    upd_id: str = '',
    phase: str = 'all',
    found: str = '',
    stage_name: str = '',
    dup_id: str = '',
    dup_name: str = '',
    wrong_id: str = '',
    expected: str = '',
    exp_id: str = '',
    exp_name: str = '',
    get_uti_info_fn = None
) -> Dict[str, Any]:
    """Сборка полного контекста шаблона Jinja2 для главной страницы."""
    box_t, box_rh, cur_v = await get_climate_sensor().read_climate()
    t_now = int(time.time())

    win_clim = get_windowsill_climate()
    tc_val = win_clim.get('t_c') if win_clim else None
    rh_val = win_clim.get('rh_pct') if win_clim else None
    if win_clim and tc_val is not None and (win_clim.get('is_live') or tc_val > 0):
        cur_t = round(float(tc_val), 1)
        cur_rh = round(float(rh_val), 1) if rh_val is not None else box_rh
    else:
        cur_t = box_t
        cur_rh = box_rh

    win_t = cur_t
    win_rh = cur_rh
    cur_vpd = calc_vpd(cur_t, cur_rh)

    exp_mgr = get_experiment_manager(DATA_DIR)
    set_exp_req = request.query_params.get('set_exp')
    if set_exp_req:
        exp_mgr.set_active_experiment(set_exp_req)

    active_exp = exp_mgr.get_active_experiment()
    experiments = exp_mgr.get_experiments()
    active_csv = exp_mgr.get_active_csv_path()

    status_banner = build_status_banner(
        msg=msg,
        stage_name=stage_name,
        upd_id=upd_id,
        del_id=del_id,
        found=found,
        dup_id=dup_id,
        dup_name=dup_name,
        wrong_id=wrong_id,
        expected=expected,
        exp_id=exp_id,
        exp_name=exp_name
    )

    batch_state = get_batch_state()
    pending_session = get_pending_session()

    batch_view = None
    batch_thermal_view = None
    batch_verify_view = None
    review_view = None

    if stage == 'batch_shoot' and batch_state.get('active'):
        batch_view = build_batch_shoot_view(batch_state)
    elif stage == 'batch_await_thermal' and batch_state.get('active'):
        batch_thermal_view = build_batch_await_thermal_view(batch_state, t_now)
    elif stage == 'batch_verify' and batch_state.get('active') and batch_state.get('verified_data'):
        batch_verify_view = build_batch_verify_view(batch_state, t_now)
    elif stage == 'review' and pending_session:
        uti_info = get_uti_info_fn(offset) if get_uti_info_fn else None
        review_view = build_review_view(pending_session, offset, t_now, uti_info)

    rows = []
    if os.path.exists(active_csv):
        with open(active_csv, 'r', encoding='utf-8') as f:
            all_r = list(csv.reader(f))
            if len(all_r) > 1:
                rows = all_r[1:]

    table_rows, summary_stats, table_html = build_table_rows_and_stats(rows)

    return {
        "request": request,
        "status_banner": status_banner,
        "stage": stage,
        "phase": phase,
        "cur_t": cur_t,
        "cur_rh": cur_rh,
        "cur_vpd": cur_vpd,
        "cur_v": cur_v,
        "box_t": box_t,
        "box_rh": box_rh,
        "win_t": win_t,
        "win_rh": win_rh,
        "active_exp": active_exp,
        "experiments": experiments,
        "rows_count": len(rows),
        "batch_state": batch_state,
        "pending_session": pending_session,
        "batch_view": batch_view,
        "batch_thermal_view": batch_thermal_view,
        "batch_verify_view": batch_verify_view,
        "review_view": review_view,
        "summary_stats": summary_stats,
        "table_rows": table_rows,
        "table_html": table_html,
        "t_now": t_now
    }
