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
    assert '85.0' in html

    # 2. Скачивание CSV второй волны
    res_w2_csv = client.get('/download/wave2_csv')
    assert res_w2_csv.status_code == 200

    # 3. Возврат на Серию 1 по умолчанию
    client.get('/?set_exp=exp_1791463544')
