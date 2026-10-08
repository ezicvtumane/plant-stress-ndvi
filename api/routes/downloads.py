from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import os
import zipfile
import time

router = APIRouter()

# These will be set from main
DATA_DIR = ''
STATIC_DIR = ''
CSV_LOG = ''

def init_downloads(data_dir, static_dir, csv_log):
    global DATA_DIR, STATIC_DIR, CSV_LOG
    DATA_DIR = data_dir
    STATIC_DIR = static_dir
    CSV_LOG = csv_log

def _generate_zip(zip_path: str):
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(CSV_LOG):
            zf.write(CSV_LOG, arcname='measurements.csv')
        for fname in sorted(os.listdir(STATIC_DIR)):
            if (fname.startswith(('opt_', 'therm_', 'ndvi_')) or fname in ('last_ndvi.jpg', 'last_thermal.jpg')) and fname.endswith(('.jpg', '.png')):
                full_p = os.path.join(STATIC_DIR, fname)
                zf.write(full_p, arcname=f'photos/{fname}')

@router.get('/download/csv')
def download_csv():
    if os.path.exists(CSV_LOG):
        return FileResponse(CSV_LOG, filename='plant_stress_measurements.csv')
    return HTMLResponse('Файл пока пуст')

@router.get('/download/images_zip')
def download_images_zip(background_tasks: BackgroundTasks):
    zip_path = os.path.join(DATA_DIR, 'plant_stress_gallery.zip')
    needs_regen = True
    if os.path.exists(zip_path):
        if time.time() - os.path.getmtime(zip_path) < 3600:
            needs_regen = False
    if needs_regen:
        background_tasks.add_task(_generate_zip, zip_path)
        if not os.path.exists(zip_path):
            return JSONResponse({'status': 'processing', 'message': 'Архив формируется в фоне. Обновите страницу через 30 секунд.'}, status_code=202)
    return FileResponse(zip_path, filename='plant_stress_gallery.zip', media_type='application/zip')
