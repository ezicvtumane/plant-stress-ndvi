"""
Интеграционные тесты веб-станции фенотипирования растений (FastAPI + Routers + Jinja2).
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

import pytest
from fastapi.testclient import TestClient
from web_station import app
from core.station_state import get_batch_state, get_pending_session, reset_batch_state

client = TestClient(app)

def test_index_dashboard_renders():
    """Проверка доступности главной страницы дашборда и корректности рендеринга."""
    response = client.get('/')
    assert response.status_code == 200
    html = response.text
    assert 'Большие вызовы' in html
    assert 'Оптико-электронный комплекс' in html
    assert 'static/css/dashboard.css' in html
    assert 'static/js/dashboard.js' in html
    assert 'Журнал физиологических замеров' in html

def test_static_assets_served():
    """Проверка отдачи вынесенных статических ассетов CSS и JS."""
    css_res = client.get('/static/css/dashboard.css')
    assert css_res.status_code == 200
    assert '--sirius-teal' in css_res.text

    js_res = client.get('/static/js/dashboard.js')
    assert js_res.status_code == 200
    assert 'adjTemp' in js_res.text
    assert 'openEditModal' in js_res.text

def test_batch_lifecycle_routes():
    """Проверка маршрутов управления пакетной съемкой кассет."""
    client.get('/?set_exp=exp_1791463544')
    reset_batch_state('batch5')
    
    # 1. Старт пакета -> 303 Redirect на batch_shoot
    start_res = client.get('/api/start_batch?stage=batch5', follow_redirects=False)
    assert start_res.status_code == 303
    assert '/?stage=batch_shoot' in start_res.headers['location']
    
    state = get_batch_state()
    assert state['active'] is True
    assert state['stage_key'] == 'batch5'

    # 2. Рендеринг экрана batch_shoot
    shoot_res = client.get('/?stage=batch_shoot')
    assert shoot_res.status_code == 200
    assert 'Пакетный замер 5 кассет' in shoot_res.text

    # 3. Отмена пакета -> 303 Redirect на cancelled
    cancel_res = client.get('/api/cancel_batch', follow_redirects=False)
    assert cancel_res.status_code == 303
    assert '/?msg=cancelled' in cancel_res.headers['location']

    state = get_batch_state()
    assert state['active'] is False

def test_downloads_routes():
    """Проверка работы роутера скачивания отчетов и CSV."""
    res_csv = client.get('/download/csv')
    assert res_csv.status_code in (200, 303)

    res_aruco = client.get('/download/aruco_pdf')
    assert res_aruco.status_code in (200, 303)

    res_pres = client.get('/download/presentation')
    assert res_pres.status_code in (200, 303)


def test_wave2_dashboard_and_routes():
    """Проверка доступности дашборда Волны 2, лизиметра X0 и скачивания CSV."""
    # 1. Переключение на Волну 2
    res = client.get('/?set_exp=exp_1792918800')
    assert res.status_code == 200
    html = res.text
    assert 'X0' in html
    assert '100.0' in html

    # 2. Скачивание CSV второй волны
    res_w2_csv = client.get('/download/wave2_csv')
    assert res_w2_csv.status_code == 200

    # 3. Возврат на Серию 1 по умолчанию
    client.get('/?set_exp=exp_1791463544')


def test_wave2_update_record_and_thermal():
    """Проверка inline-обновления строки без перезагрузки и загрузки термограммы."""
    # 1. Обновление параметров горшка K1 (масса 92.5 г, T_листа 21.8 °C, T_air 24.0 °C)
    res_up = client.post('/api/wave2/update_record', data={
        'pot_id': 'K1',
        'weight_g': '92.5',
        't_leaf': '21.8',
        't_air': '24.0',
        'turgor_score': '4'
    })
    assert res_up.status_code == 200
    data = res_up.json()
    assert data['status'] == 'ok'
    assert data['pot_id'] == 'K1'
    assert '-2.2°' in data['delta_t']
    assert any(x in data['dose'] for x in ('7.5 мл', '8.3 мл'))

    # 2. Ручной ввод имени термограммы
    res_th_name = client.post('/api/wave2/update_record', data={
        'pot_id': 'K1',
        'thermal_filename': 'IMG_0042.JPG'
    })
    assert res_th_name.status_code == 200
    data_th = res_th_name.json()
    assert data_th['status'] == 'ok'
    assert data_th['thermal_file'] == 'IMG_0042.JPG'
    # Масса и доза должны сохраниться!
    assert any(x in data_th['dose'] for x in ('7.5 мл', '8.3 мл'))

    # 3. Загрузка файла термограммы через /api/wave2/upload_thermal
    fake_img = b"FAKE_JPEG_DATA_STREAM"
    res_upload = client.post('/api/wave2/upload_thermal', data={'pot_id': 'K1'}, files={'thermal_file': ('K1_test.jpg', fake_img, 'image/jpeg')})
    assert res_upload.status_code == 200
    up_data = res_upload.json()
    assert up_data['status'] == 'ok'
    assert 'K1_' in up_data['filename']
    assert up_data['filename'].endswith('.jpg')


def test_wave2_bmp_upload_and_conversion():
    """Проверка загрузки BMP файла с автоматической конвертацией в JPEG для браузера."""
    import io
    from PIL import Image
    # Создаем валидный тестовый BMP в памяти
    im = Image.new('RGB', (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format='BMP')
    buf.seek(0)

    res = client.post('/api/wave2/upload_thermal', data={'pot_id': 'K2'}, files={'thermal_file': ('thermal_K2.bmp', buf, 'image/bmp')})
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'ok'
    assert data['filename'].endswith('.jpg')
    assert data['raw_filename'].endswith('.bmp')


def test_wave2_ui_redesign_and_scrolling():
    """Проверка редизайна колонки термограммы (как NDVI), кнопки 📷 и скролла таблицы."""
    client.post('/api/wave2/update_record', data={'pot_id': 'K1', 'weight_g': '92.5'})
    res = client.get('/?set_exp=exp_1792918800')
    assert res.status_code == 200
    html = res.text
    # 1. Option A: no max-height constraint trapping table scroll
    assert 'max-height: 420px;' not in html
    assert 'max-height: 320px;' not in html
    # 2. Table has sticky top header
    assert 'position: sticky; top: 0;' in html
    # 3. Action column has teal camera button and hidden file input
    assert 'file_th_' in html
    assert 'uploadThermalImage' in html
    assert 'openImageViewer' in html
