"""
Модуль скачивания отчетов, публикаций, презентаций, ArUco-маркеров и данных экспериментов.
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

import os
import time
import zipfile
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

from core.config import settings
from core.experiments import get_experiment_manager

router = APIRouter(tags=["downloads"])

STATIC_DIR = settings.STATIC_DIR
DATA_DIR = settings.DATA_DIR
CSV_LOG = settings.CSV_LOG
DOCS_DIR = os.path.join(settings.BASE_DIR, 'docs')

def _generate_zip(zip_path: str):
    """Фоновая генерация общего архива галереи."""
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(CSV_LOG):
            zf.write(CSV_LOG, arcname='measurements.csv')
        for fname in sorted(os.listdir(STATIC_DIR)):
            if (fname.startswith(('opt_', 'therm_', 'ndvi_')) or fname in ('last_ndvi.jpg', 'last_thermal.jpg')) and fname.endswith(('.jpg', '.png')):
                full_p = os.path.join(STATIC_DIR, fname)
                zf.write(full_p, arcname=f'photos/{fname}')

@router.get('/download/pdf')
def download_pdf():
    """Скачивание конкурсного отчета в PDF."""
    pdf_path = os.path.join(STATIC_DIR, 'Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(STATIC_DIR, 'analysis_report.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Отчет пока не сформирован')

@router.get('/download/paper')
def download_paper():
    """Скачивание конкурсной работы."""
    pdf_path = os.path.join(STATIC_DIR, 'Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл работы не найден')

@router.get('/download/research_paper')
def download_research_paper():
    """Скачивание научно-исследовательской статьи."""
    pdf_path = os.path.join(STATIC_DIR, 'Научно_исследовательская_работа_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, 'Научно_исследовательская_работа_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Научно_исследовательская_работа_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл научно-исследовательской статьи пока не сформирован')

@router.get('/download/review_note')
def download_review_note():
    """Скачивание краткой записки для рецензирования."""
    pdf_path = os.path.join(STATIC_DIR, 'Краткая_записка_для_рецензирования_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, 'Краткая_записка_для_рецензирования_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Краткая_записка_для_рецензирования_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл записки для рецензирования пока не найден')

@router.get('/download/presentation')
@router.get('/download/presentation_pdf')
def download_presentation():
    """Скачивание презентации проекта в PDF."""
    pdf_path = os.path.join(STATIC_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf', media_type='application/pdf')
    return HTMLResponse('Файл презентации проекта пока не сформирован')

@router.get('/download/presentation_pptx')
def download_presentation_pptx():
    """Скачивание презентации проекта в PPTX."""
    pptx_path = os.path.join(STATIC_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx')
    if not os.path.exists(pptx_path):
        pptx_path = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx')
    if os.path.exists(pptx_path):
        return FileResponse(pptx_path, filename='Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx', media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    return HTMLResponse('Файл PPTX презентации пока не сформирован')

@router.get('/download/aruco_pdf')
def download_aruco_pdf():
    """Скачивание листа ArUco-маркеров для кассет."""
    pdf_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename='aruco_markers_cassettes.pdf', media_type='application/pdf')
    html_path = os.path.join(STATIC_DIR, 'aruco_markers_sheet.html')
    if os.path.exists(html_path):
        return FileResponse(html_path, filename='aruco_markers_cassettes.html', media_type='text/html')
    return HTMLResponse('Лист маркеров не найден')

@router.get('/download/experiment_zip')
def download_experiment_zip():
    """Скачивание полного архива активной серии опытов (CSV + снимки)."""
    exp_mgr = get_experiment_manager(DATA_DIR)
    active_exp = exp_mgr.get_active_experiment()
    exp_id = active_exp.get('id', 'exp_1')
    exp_name = active_exp.get('name', 'experiment').replace(' ', '_')
    out_zip = os.path.join(DATA_DIR, f"temp_{exp_id}.zip")
    exp_mgr.generate_zip(exp_id, out_zip)
    if os.path.exists(out_zip):
        return FileResponse(out_zip, filename=f"{exp_name}_export.zip", media_type='application/zip')
    return HTMLResponse('Ошибка формирования архива серии')

@router.get('/download/csv')
def download_active_csv():
    """Скачивание CSV журнала активной серии опытов."""
    exp_mgr = get_experiment_manager(DATA_DIR)
    active_csv = exp_mgr.get_active_csv_path()
    active_exp = exp_mgr.get_active_experiment()
    exp_name = active_exp.get('name', 'measurements').replace(' ', '_')
    if os.path.exists(active_csv):
        return FileResponse(active_csv, filename=f"{exp_name}.csv", media_type='text/csv')
    return HTMLResponse('Файл CSV не найден')

@router.get('/download/images_zip')
def download_images_zip():
    """Скачивание архива снимков активной серии."""
    exp_mgr = get_experiment_manager(DATA_DIR)
    active_exp = exp_mgr.get_active_experiment()
    exp_id = active_exp.get('id', 'exp_1')
    out_zip = os.path.join(DATA_DIR, f"temp_{exp_id}.zip")
    exp_mgr.generate_zip(exp_id, out_zip)
    if os.path.exists(out_zip):
        return FileResponse(out_zip, filename=f"images_{exp_id}.zip", media_type='application/zip')
    return HTMLResponse('Архив снимков не найден')


def init_downloads(*args, **kwargs):
    """Инициализация модуля загрузок (обратная совместимость)."""
    pass
