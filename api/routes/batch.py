"""
Маршруты пакетной и одиночной съемки кассет (5-в-1, спектроскопия, термография, ArUco).
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

import os
import time
import shutil
from PIL import Image
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse

try:
    from gpiod.line import Value
except ImportError:
    Value = None

from core.config import settings
from core.experiments import get_experiment_manager
from core.station_state import (
    CASSETTE_CATALOG, BATCH_CONFIG, BATCH_STATE,
    get_pending_session, set_pending_session, clear_pending_session
)

router = APIRouter(tags=["batch_capture"])

STATIC_DIR = settings.STATIC_DIR
DATA_DIR = settings.DATA_DIR
CSV_LOG = settings.CSV_LOG
TH_CACHE_DIR = os.path.join(STATIC_DIR, 'uti_cache')

# Hardware runner hooks (lazy-loaded from web_station to preserve Step 3 logic intact)
_hw_spectral_capture = None
_hw_auto_mount = None
_hw_get_uti_files = None
_hw_extract_temp = None
_hw_init_relay = None
_hw_get_relay_req = None
_hw_format_ru_datetime = None

def init_batch_hardware(
    spectral_capture_fn=None,
    auto_mount_fn=None,
    get_uti_files_fn=None,
    extract_temp_fn=None,
    init_relay_fn=None,
    get_relay_req_fn=None,
    format_ru_datetime_fn=None
):
    global _hw_spectral_capture, _hw_auto_mount, _hw_get_uti_files, _hw_extract_temp
    global _hw_init_relay, _hw_get_relay_req, _hw_format_ru_datetime
    if spectral_capture_fn: _hw_spectral_capture = spectral_capture_fn
    if auto_mount_fn: _hw_auto_mount = auto_mount_fn
    if get_uti_files_fn: _hw_get_uti_files = get_uti_files_fn
    if extract_temp_fn: _hw_extract_temp = extract_temp_fn
    if init_relay_fn: _hw_init_relay = init_relay_fn
    if get_relay_req_fn: _hw_get_relay_req = get_relay_req_fn
    if format_ru_datetime_fn: _hw_format_ru_datetime = format_ru_datetime_fn

def _get_spectral_fn():
    global _hw_spectral_capture
    if _hw_spectral_capture is None:
        import web_station
        _hw_spectral_capture = web_station.do_hardware_spectral_capture
    return _hw_spectral_capture

def _get_auto_mount_fn():
    global _hw_auto_mount
    if _hw_auto_mount is None:
        import web_station
        _hw_auto_mount = web_station.auto_mount_uti
    return _hw_auto_mount

def _get_uti_files_fn():
    global _hw_get_uti_files
    if _hw_get_uti_files is None:
        import web_station
        _hw_get_uti_files = web_station.get_uti_sorted_files
    return _hw_get_uti_files

def _get_extract_temp_fn():
    global _hw_extract_temp
    if _hw_extract_temp is None:
        import web_station
        _hw_extract_temp = web_station.extract_temperature_from_thermal
    return _hw_extract_temp

def _get_init_relay_fn():
    global _hw_init_relay
    if _hw_init_relay is None:
        import web_station
        _hw_init_relay = web_station.init_relay
    return _hw_init_relay

def _get_relay_req_obj():
    global _hw_get_relay_req
    if _hw_get_relay_req is not None:
        return _hw_get_relay_req()
    import web_station
    return web_station.RELAY_REQ

def _get_format_ru_dt():
    global _hw_format_ru_datetime
    if _hw_format_ru_datetime is None:
        import web_station
        _hw_format_ru_datetime = web_station.format_ru_datetime
    return _hw_format_ru_datetime


@router.post('/api/start_spectral')
def handle_start_spectral(group_name: str = Form('Контроль')):
    """Старт 1-го этапа: спектроскопия в боксе."""
    try:
        do_capture = _get_spectral_fn()
        do_capture(group_name)
        return RedirectResponse(url='/?stage=review&offset=0', status_code=303)
    except Exception as e:
        print('[Start Spectral Error]:', e)
        return RedirectResponse(url='/?msg=err_camera', status_code=303)

@router.get('/api/test_relay')
def handle_test_relay(channel: str = 'nir', sec: float = 3.0):
    """Аппаратная диагностика: включение выбранного реле (nir или red) на sec секунд."""
    init_rel = _get_init_relay_fn()
    init_rel()
    relay_req = _get_relay_req_obj()
    if not relay_req:
        return JSONResponse({'status': 'error', 'message': 'Relay not initialized'})
    line = 7 if channel.lower() == 'nir' else 4
    pin_name = 'Pin 10 (NIR 850nm)' if line == 7 else 'Pin 7 (Red 660nm)'
    try:
        duration = max(0.5, min(10.0, float(sec)))
        print(f'[Test Relay] Включение {pin_name} на {duration} сек...')
        if Value:
            relay_req.set_value(line, Value.ACTIVE)
        time.sleep(duration)
        if Value:
            relay_req.set_value(line, Value.INACTIVE)
        print(f'[Test Relay] Выключение {pin_name}. Готово.')
        return JSONResponse({'status': 'ok', 'channel': channel, 'pin': pin_name, 'duration': duration})
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)})

@router.post('/api/save_final_measurement')
def handle_save_final(
    weight_g: str = Form(''),
    pct_soil: str = Form(''),
    t_leaf: str = Form(''),
    thermal_filename: str = Form(''),
    thermal_thumb: str = Form('')
):
    """
    Шаг 4: Окончательное подтверждение замера оператором.
    Сохранение в базу данных и переход к следующей кассете.
    """
    s = get_pending_session()
    if not s:
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)

    meas_id = s['id']
    ts_display = s['timestamp']
    group_name = s['group']

    weight_val = weight_g.strip().replace(',', '.') if weight_g else ''
    t_leaf_val = t_leaf.strip().replace(',', '.') if t_leaf else ''

    if pct_soil.strip():
        try:
            ps_val = float(pct_soil.strip().replace(',', '.'))
            s['pct_soil'] = round(max(0.0, min(100.0, ps_val)), 1)
            s['v_soil'] = round(2.03 - (s['pct_soil'] / 100.0) * 1.59, 2)
        except Exception:
            pass

    delta_t_val = ''
    if t_leaf_val:
        try:
            dt = round(float(t_leaf_val) - float(s['t_air']), 1)
            delta_t_val = str(dt)
        except Exception:
            pass

    jpg_stored_name = ''
    if thermal_thumb and os.path.exists(os.path.join(STATIC_DIR, 'uti_cache', os.path.basename(thermal_thumb))):
        src_thumb = os.path.join(STATIC_DIR, 'uti_cache', os.path.basename(thermal_thumb))
        jpg_stored_name = f'therm_{meas_id}.jpg'
        dst_path = os.path.join(STATIC_DIR, jpg_stored_name)
        shutil.copyfile(src_thumb, dst_path)
        shutil.copyfile(dst_path, os.path.join(STATIC_DIR, 'last_thermal.jpg'))

    row_data = [
        meas_id, ts_display, group_name, weight_val,
        s['t_air'], s['rh_air'], s['v_soil'], s['pct_soil'],
        t_leaf_val, delta_t_val, s['vpd'],
        s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
        s['opt_file'], jpg_stored_name,
        *s['cell_ndvis']
    ]
    exp_mgr = get_experiment_manager(DATA_DIR)
    exp_mgr.save_measurement_row(row_data)
    if s.get('opt_file'):
        exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, s['opt_file']))
    if jpg_stored_name:
        exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, jpg_stored_name))

    clear_pending_session()
    return RedirectResponse(url=f'/?msg=saved&last_grp={group_name}', status_code=303)

@router.get('/api/cancel_session')
def handle_cancel_session():
    """Сброс текущего одиночного замера."""
    clear_pending_session()
    return RedirectResponse(url='/?msg=cancelled', status_code=303)

@router.get('/api/start_batch')
def handle_start_batch(stage: str = 'stage1'):
    """Старт пакетной сессии для выбранного этапа (stage1 или stage2)."""
    clear_pending_session()
    if stage not in BATCH_CONFIG:
        stage = 'stage1'
    BATCH_STATE.clear()
    BATCH_STATE.update({
        'active': True,
        'stage_key': stage,
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    })
    return RedirectResponse(url='/?stage=batch_shoot', status_code=303)

@router.get('/api/cancel_batch')
def handle_cancel_batch():
    """Отмена текущей пакетной сессии."""
    BATCH_STATE.clear()
    BATCH_STATE.update({
        'active': False,
        'stage_key': 'stage1',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    })
    return RedirectResponse(url='/?msg=cancelled', status_code=303)

@router.post('/api/batch_capture_next')
def handle_batch_capture_next(
    cohort_choice: str = Form('auto'),
    weight_g: str = Form(''),
    t_leaf: str = Form(''),
    pct_soil: str = Form('64.0')
):
    """Съемка очередной кассеты в боксе NoIR камерой с авто-детекцией ArUco, мягкими предупреждениями и ручным выбором когорты."""
    if not BATCH_STATE.get('active'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)
    
    stage_key = BATCH_STATE['stage_key']
    cassettes = BATCH_CONFIG[stage_key]['cassettes']
    step = len(BATCH_STATE['sessions'])
    if step >= len(cassettes):
        return RedirectResponse(url='/?stage=batch_await_thermal', status_code=303)
    
    expected_cassette = cassettes[step]
    
    manual_mode = (cohort_choice != 'auto' and cohort_choice.strip().isdigit())
    if manual_mode:
        chosen_id = int(cohort_choice)
        c_meta = CASSETTE_CATALOG.get(chosen_id, {'id': chosen_id, 'name': f'Кассета #{chosen_id}'})
        target_name = c_meta['name']
    else:
        chosen_id = None
        target_name = expected_cassette['name']
    
    try:
        do_capture = _get_spectral_fn()
        session = do_capture(target_name)
        detected_id = session.get('aruco_id')
        warn_query = ''

        if manual_mode:
            session['aruco_id'] = chosen_id
            session['group'] = CASSETTE_CATALOG.get(chosen_id, {}).get('name', f'Кассета #{chosen_id}')
        else:
            if detected_id is not None:
                grp_name = CASSETTE_CATALOG.get(detected_id, {}).get('name', f'Кассета #{detected_id}')
                session['group'] = grp_name
                
                is_dup = any(past_s.get('aruco_id') == detected_id for past_s in BATCH_STATE['sessions'])
                if is_dup:
                    warn_query = f'&msg=warn_duplicate_aruco&dup_id={detected_id}&dup_name={grp_name}'
                elif detected_id not in [c['id'] for c in cassettes]:
                    exp_str = ', '.join(str(c['id']) for c in cassettes)
                    warn_query = f'&msg=warn_wrong_stage_aruco&wrong_id={detected_id}&expected={exp_str}'
            else:
                session['aruco_id'] = expected_cassette['id']
                session['group'] = expected_cassette['name']
                warn_query = f"&msg=warn_no_aruco&exp_id={expected_cassette['id']}&exp_name={expected_cassette['name']}"

        session['user_weight'] = weight_g.strip().replace(',', '.') if weight_g.strip() else ''
        session['user_t_leaf'] = t_leaf.strip().replace(',', '.') if t_leaf.strip() else ''
        session['user_pct_soil'] = pct_soil.strip().replace(',', '.') if pct_soil.strip() else '64.0'
        session['shot_order'] = len(BATCH_STATE['sessions']) + 1

        BATCH_STATE['sessions'].append(session)
        BATCH_STATE['current_step'] = len(BATCH_STATE['sessions'])

        if len(BATCH_STATE['sessions']) >= len(cassettes):
            next_stage = 'batch_await_thermal'
        else:
            next_stage = 'batch_shoot'

        return RedirectResponse(url=f'/?stage={next_stage}{warn_query}', status_code=303)
    except Exception as e:
        print('[Batch Capture Error]:', e)
        return RedirectResponse(url='/?stage=batch_shoot&msg=err_camera', status_code=303)

@router.post('/api/batch_link_thermal')
def handle_batch_link_thermal():
    """Считывание последних термограмм с флешки тепловизора и авто-привязка к кассетам с сортировкой по ArUco."""
    stage_key = BATCH_STATE.get('stage_key', 'batch5')
    stage_cassettes = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])['cassettes']
    expected_count = len(stage_cassettes)
    
    if not BATCH_STATE.get('active') or len(BATCH_STATE.get('sessions', [])) != expected_count:
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)
    
    auto_mount = _get_auto_mount_fn()
    auto_mount()
    get_files = _get_uti_files_fn()
    files = get_files()
    if len(files) < expected_count:
        return RedirectResponse(url=f'/?stage=batch_await_thermal&msg=err_thermal_count&found={len(files)}', status_code=303)
    
    recent_files = files[:expected_count]
    recent_files.sort(key=os.path.getmtime)
    
    stage_ids = [c['id'] for c in stage_cassettes]
    paired_items = []
    used_ids = set()
    extract_temp = _get_extract_temp_fn()
    format_ru_dt = _get_format_ru_dt()

    for i, s in enumerate(BATCH_STATE['sessions']):
        fp = recent_files[i]
        fname = os.path.basename(fp)
        mtime = os.path.getmtime(fp)
        thumb_jpg = f'{int(mtime)}_{fname}.jpg'
        thumb_path = os.path.join(TH_CACHE_DIR, thumb_jpg)
        if not os.path.exists(thumb_path):
            try:
                im = Image.open(fp)
                im.save(thumb_path)
            except Exception:
                pass
        
        if s.get('user_t_leaf'):
            t_val = s['user_t_leaf']
        else:
            t_val, ocr_valid = extract_temp(thumb_path) if os.path.exists(thumb_path) else (None, False)
        if t_val is None: t_val = round(s['t_air'] + 0.5, 1)
        
        detected_id = s.get('aruco_id')
        assigned_id = None
        if detected_id and detected_id in stage_ids and detected_id not in used_ids:
            assigned_id = detected_id
            used_ids.add(assigned_id)
        
        paired_items.append({
            'session': s,
            'shot_order': s.get('shot_order', i + 1),
            'thermal_filename': fname,
            'thermal_thumb': thumb_jpg,
            'thermal_thumb_url': f'/static/uti_cache/{thumb_jpg}',
            't_ocr': t_val,
            'dt_str': format_ru_dt(mtime),
            'detected_id': detected_id,
            'assigned_id': assigned_id
        })
    
    remaining_ids = [cid for cid in stage_ids if cid not in used_ids]
    for item in paired_items:
        if item['assigned_id'] is None:
            item['assigned_id'] = remaining_ids.pop(0) if remaining_ids else stage_ids[0]
    
    paired_items.sort(key=lambda x: x['assigned_id'])
    BATCH_STATE['verified_data'] = paired_items
    return RedirectResponse(url='/?stage=batch_verify', status_code=303)

@router.post('/api/batch_save_manual')
async def handle_batch_save_manual(request: Request):
    """Мгновенное сохранение всей серии кассет с подтвержденными ручными данными (экспресс-финиш без проводов)."""
    if not BATCH_STATE.get('active') or not BATCH_STATE.get('sessions'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)

    form = await request.form()
    stage_key = BATCH_STATE.get('stage_key', 'batch5')
    stage_cassettes = BATCH_CONFIG.get(stage_key, BATCH_CONFIG['batch5'])['cassettes']
    stage_ids = [c['id'] for c in stage_cassettes]

    records_to_save = []
    for i, s in enumerate(BATCH_STATE['sessions']):
        cid_str = form.get(f'cassette_id_{i}')
        cid = int(cid_str) if (cid_str and str(cid_str).isdigit()) else s.get('aruco_id')
        if not cid or cid not in CASSETTE_CATALOG:
            cid = stage_ids[i] if i < len(stage_ids) else (i + 1)

        c_meta = CASSETTE_CATALOG.get(cid, {'name': f'Кассета #{cid}'})
        group_name = c_meta['name']
        meas_id = s['id']
        ts_display = s['timestamp']

        w_raw = form.get(f'weight_g_{i}', '')
        w_val = str(w_raw).strip().replace(',', '.') if str(w_raw).strip() else s.get('user_weight', '')

        t_raw = form.get(f't_leaf_{i}', '')
        t_l_val = str(t_raw).strip().replace(',', '.') if str(t_raw).strip() else s.get('user_t_leaf', '')
        if not t_l_val:
            t_l_val = str(round(float(s['t_air']), 1))

        pct_raw = form.get(f'pct_soil_{i}', '')
        if str(pct_raw).strip():
            try:
                ps = float(str(pct_raw).strip().replace(',', '.'))
                s['pct_soil'] = round(max(0.0, min(100.0, ps)), 1)
                s['v_soil'] = round(2.03 - (s['pct_soil'] / 100.0) * 1.59, 2)
            except Exception:
                pass
        elif group_name in ['Превенция', 'Реакция']:
            s['pct_soil'] = ''
            s['v_soil'] = ''

        delta_t_val = ''
        base_air_t = float(s.get('t_air_win') or s.get('t_air', 24.5))
        base_rh_air = float(s.get('rh_air_win') or s.get('rh_air', 55.0))
        if t_l_val:
            try:
                dt = round(float(t_l_val) - base_air_t, 1)
                delta_t_val = str(dt)
            except Exception:
                pass

        records_to_save.append({
            'cid': cid,
            'row': [
                meas_id, ts_display, group_name, w_val,
                base_air_t, base_rh_air, s['v_soil'], s['pct_soil'],
                t_l_val, delta_t_val, s['vpd'],
                s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
                s['opt_file'], '',
                *s['cell_ndvis']
            ]
        })

    records_to_save.sort(key=lambda x: x['cid'])

    exp_mgr = get_experiment_manager(DATA_DIR)
    for r in records_to_save:
        exp_mgr.save_measurement_row(r['row'])
        opt_f = r['row'][14] if len(r['row']) > 14 else ''
        if opt_f:
            exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, opt_f))

    stage_name = BATCH_CONFIG.get(stage_key, {}).get('title', 'Серия 5 кассет (5-в-1)')
    BATCH_STATE.clear()
    BATCH_STATE.update({
        'active': False,
        'stage_key': 'batch5',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    })
    return RedirectResponse(url=f'/?msg=batch_saved&stage_name={stage_name}', status_code=303)

@router.post('/api/batch_skip_thermal')
async def handle_batch_skip_thermal(request: Request):
    """Экспресс-пропуск подключения тепловизора: переход к подтверждению серии."""
    return await handle_batch_save_manual(request)

@router.post('/api/batch_save_final')
async def handle_batch_save_final(request: Request):
    """Окончательное групповое сохранение всей серии кассет с учетом выбранных/распознанных ID и тепловизора."""
    if not BATCH_STATE.get('active') or not BATCH_STATE.get('verified_data'):
        return RedirectResponse(url='/?msg=err_no_session', status_code=303)

    form = await request.form()
    verified = BATCH_STATE['verified_data']
    records_to_save = []
    for i, item in enumerate(verified):
        s = item['session']
        cid_raw = form.get(f'cassette_id_{i}')
        cid = int(cid_raw) if (cid_raw and str(cid_raw).isdigit()) else item.get('assigned_id', i+1)
        c_meta = CASSETTE_CATALOG.get(cid, {'name': f'Кассета #{cid}'})
        group_name = c_meta['name']
        meas_id = s['id']
        ts_display = s['timestamp']

        w_raw = form.get(f'weight_g_{i}', '')
        w_val = str(w_raw).strip().replace(',', '.') if str(w_raw).strip() else ''

        t_raw = form.get(f't_leaf_{i}', '')
        t_l_val = str(t_raw).strip().replace(',', '.') if str(t_raw).strip() else str(item['t_ocr'])

        pct_raw = form.get(f'pct_soil_{i}', '')
        if str(pct_raw).strip():
            try:
                ps = float(str(pct_raw).strip().replace(',', '.'))
                s['pct_soil'] = round(max(0.0, min(100.0, ps)), 1)
                s['v_soil'] = round(2.03 - (s['pct_soil'] / 100.0) * 1.59, 2)
            except Exception:
                pass
        elif group_name in ['Превенция', 'Реакция']:
            s['pct_soil'] = ''
            s['v_soil'] = ''

        delta_t_val = ''
        base_air_t = float(s.get('t_air_win') or s.get('t_air', 24.5))
        base_rh_air = float(s.get('rh_air_win') or s.get('rh_air', 55.0))
        if t_l_val:
            try:
                dt = round(float(t_l_val) - base_air_t, 1)
                delta_t_val = str(dt)
            except Exception:
                pass

        jpg_stored_name = ''
        src_thumb = os.path.join(STATIC_DIR, 'uti_cache', item['thermal_thumb'])
        if os.path.exists(src_thumb):
            jpg_stored_name = f"therm_{meas_id}.jpg"
            dst_path = os.path.join(STATIC_DIR, jpg_stored_name)
            shutil.copyfile(src_thumb, dst_path)
            if i == len(verified) - 1:
                shutil.copyfile(dst_path, os.path.join(STATIC_DIR, 'last_thermal.jpg'))

        records_to_save.append({
            'cid': cid,
            'row': [
                meas_id, ts_display, group_name, w_val,
                base_air_t, base_rh_air, s['v_soil'], s['pct_soil'],
                t_l_val, delta_t_val, s['vpd'],
                s['mean_ndvi'], s['std_ndvi'], s.get('leaf_area_cm2', ''),
                s['opt_file'], jpg_stored_name,
                *s['cell_ndvis']
            ]
        })

    records_to_save.sort(key=lambda r: r['cid'])

    exp_mgr = get_experiment_manager(DATA_DIR)
    for rec in records_to_save:
        exp_mgr.save_measurement_row(rec['row'])
        opt_f = rec['row'][14] if len(rec['row']) > 14 else ''
        th_f = rec['row'][15] if len(rec['row']) > 15 else ''
        if opt_f:
            exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, opt_f))
        if th_f:
            exp_mgr.copy_file_to_active(os.path.join(STATIC_DIR, th_f))

    stage_name = BATCH_CONFIG.get(BATCH_STATE.get('stage_key', 'batch5'), {}).get('title', 'Пакетная серия')
    BATCH_STATE.clear()
    BATCH_STATE.update({
        'active': False,
        'stage_key': 'batch5',
        'current_step': 0,
        'sessions': [],
        'verified_data': None
    })
    return RedirectResponse(url=f'/?msg=batch_saved&stage_name={stage_name}', status_code=303)
