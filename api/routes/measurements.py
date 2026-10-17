"""
Маршруты управления измерениями (CRUD: удаление, интерактивная коррекция, пересчет Delta_T).
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

import os
import csv
import re
import shutil
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import RedirectResponse

from core.config import settings
from core.experiments import get_experiment_manager

router = APIRouter(tags=["measurements"])

STATIC_DIR = settings.STATIC_DIR
DATA_DIR = settings.DATA_DIR
CSV_LOG = settings.CSV_LOG

def do_delete_measurement(meas_id: str):
    """Удаление некорректного замера по ID из CSV базы данных (глобальной и серий опытов)."""
    meas_id = str(meas_id).strip()
    if not meas_id:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

    exp_mgr = get_experiment_manager(DATA_DIR)
    csv_paths = {CSV_LOG, exp_mgr.get_active_csv_path()}
    for exp in exp_mgr.get_experiments():
        p = os.path.join(DATA_DIR, 'experiments', exp.get('folder', ''), 'measurements.csv')
        if os.path.exists(p):
            csv_paths.add(p)

    any_found = False
    for csv_file in csv_paths:
        if not os.path.exists(csv_file):
            continue
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                rows = list(csv.reader(f))
            if not rows or len(rows) <= 1:
                continue
            header = rows[0]
            new_data = []
            for r in rows[1:]:
                if r and str(r[0]).strip() == meas_id:
                    any_found = True
                    try:
                        if len(r) > 13 and r[13]:
                            opt_p = os.path.join(STATIC_DIR, r[13])
                            if os.path.exists(opt_p): os.remove(opt_p)
                        if len(r) > 14 and r[14]:
                            th_p = os.path.join(STATIC_DIR, r[14])
                            if os.path.exists(th_p): os.remove(th_p)
                    except Exception:
                        pass
                else:
                    new_data.append(r)
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(new_data)
        except Exception as e:
            print(f"[Delete error in {csv_file}]:", e)

    if any_found:
        return RedirectResponse(url=f'/?msg=deleted&del_id={meas_id}', status_code=303)
    else:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

@router.post('/api/delete_measurement')
def delete_measurement_post(meas_id: str = Form(...)):
    return do_delete_measurement(meas_id)

@router.get('/api/delete_measurement/{meas_id}')
def delete_measurement_get(meas_id: str):
    return do_delete_measurement(meas_id)

@router.post('/api/update_measurement')
def handle_update_measurement(
    meas_id: str = Form(...),
    cohort: str = Form(''),
    timestamp: str = Form(''),
    t_leaf: str = Form(''),
    weight_g: str = Form(''),
    pct_soil: str = Form(''),
    thermal_file: UploadFile = File(None)
):
    """
    Интерактивная коррекция параметров ранее сохраненного замера (T_leaf, Weight, Soil, Thermal image).
    Автоматически пересчитывает Delta_T = T_leaf - T_air и сохраняет во все CSV (глобальный и серий).
    """
    meas_id = str(meas_id).strip()
    cohort = str(cohort).strip()
    timestamp = str(timestamp).strip()
    if not meas_id:
        return RedirectResponse(url='/?msg=err_not_found', status_code=303)

    out_fname = None
    if thermal_file and thermal_file.filename:
        try:
            safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(thermal_file.filename))
            if safe_name:
                out_fname = f"therm_{meas_id}.jpg"
                out_path = os.path.join(STATIC_DIR, out_fname)
                with open(out_path, 'wb') as buf:
                    shutil.copyfileobj(thermal_file.file, buf)
                exp_mgr = get_experiment_manager(DATA_DIR)
                exp_mgr.copy_file_to_active(out_path)
        except Exception as e:
            print('[Upload thermal error]:', e)

    exp_mgr = get_experiment_manager(DATA_DIR)
    csv_paths = {CSV_LOG, exp_mgr.get_active_csv_path()}
    for exp in exp_mgr.get_experiments():
        p = os.path.join(DATA_DIR, 'experiments', exp.get('folder', ''), 'measurements.csv')
        if os.path.exists(p):
            csv_paths.add(p)

    any_found = False
    for csv_file in csv_paths:
        if not os.path.exists(csv_file):
            continue
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                rows = list(csv.reader(f))
            if not rows or len(rows) <= 1:
                continue

            header = rows[0]
            data_rows = rows[1:]
            file_found = False

            for r in data_rows:
                if not r:
                    continue
                if str(r[0]).strip() == meas_id:
                    if cohort and len(r) > 2 and r[2].strip() != cohort:
                        continue
                    if timestamp and len(r) > 1 and timestamp not in r[1] and r[1] not in timestamp:
                        continue

                    file_found = True
                    any_found = True

                    if t_leaf.strip():
                        try:
                            tl = float(t_leaf.strip().replace(',', '.'))
                            tl_str = str(round(tl, 1))
                            if len(r) >= 24:
                                r[8] = tl_str
                                if len(r) > 4 and r[4]:
                                    try:
                                        t_air = float(r[4])
                                        r[9] = str(round(tl - t_air, 1))
                                    except Exception:
                                        pass
                            elif len(r) >= 20:
                                r[6] = tl_str
                            elif len(r) >= 16:
                                r[4] = tl_str
                        except Exception:
                            pass

                    if weight_g.strip() and len(r) >= 20:
                        r[3] = weight_g.strip().replace(',', '.')

                    raw_ps = pct_soil.strip()
                    if raw_ps in ['--', '-', 'none', 'null', 'n/a', '']:
                        if len(r) >= 24:
                            r[7] = ''
                            r[6] = ''
                        elif len(r) >= 20:
                            r[5] = ''
                    else:
                        try:
                            ps = float(raw_ps.replace(',', '.').replace('%', '').strip())
                            ps = round(max(0.0, min(100.0, ps)), 1)
                            if len(r) >= 24:
                                r[7] = str(ps)
                                r[6] = str(round(3.0 - (ps / 100.0) * 1.8, 2))
                            elif len(r) >= 20:
                                r[5] = str(ps)
                        except Exception:
                            if len(r) >= 24:
                                r[7] = ''
                                r[6] = ''
                            elif len(r) >= 20:
                                r[5] = ''

                    if out_fname:
                        if len(r) >= 24:
                            r[15] = out_fname
                        elif len(r) >= 20:
                            r[10] = out_fname
                    break

            if file_found:
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(data_rows)
        except Exception as e:
            print(f"[Update error in {csv_file}]:", e)

    if any_found:
        return RedirectResponse(url=f'/?msg=updated&upd_id={meas_id}', status_code=303)

    return RedirectResponse(url='/?msg=err_not_found', status_code=303)
