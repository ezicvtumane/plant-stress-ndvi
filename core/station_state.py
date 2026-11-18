"""
Состояние сессий измерений, конфигурации пакетов кассет и каталог когорт.
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

from typing import Optional, Dict, Any, List
import threading

# Потокобезопасная блокировка глобального состояния сессий и пакетов
_STATE_LOCK = threading.RLock()

def get_state_lock() -> threading.RLock:
    return _STATE_LOCK

# Каталог 5 ключевых когорт единого эксперимента (+ калибровочный стенд №0)
# Цвета строго синхронизированы с цветной рамкой ArUco-маркеров на кассетах:
CASSETTE_CATALOG: Dict[int, Dict[str, Any]] = {
    1: {'id': 1, 'name': 'Контроль', 'desc': 'Оптимальный полив (100% ПВ)', 'color': '#059669', 'stage': 'batch5'},
    2: {'id': 2, 'name': 'Осмос', 'desc': 'Осмотический стресс', 'color': '#7c3aed', 'stage': 'batch5'},
    3: {'id': 3, 'name': 'Засуха', 'desc': 'Водный дефицит', 'color': '#dc2626', 'stage': 'batch5'},
    4: {'id': 4, 'name': 'Превенция', 'desc': 'Ранний полив по алерту станции', 'color': '#eab308', 'stage': 'batch5'},
    5: {'id': 5, 'name': 'Реакция', 'desc': 'Полив по визуальным признакам увядания', 'color': '#2563eb', 'stage': 'batch5'},
    6: {'id': 6, 'name': 'Калибровка (Стенд №0)', 'desc': 'Калибровочный стенд (посев 22.09)', 'color': '#64748b', 'stage': 'batch5'}
}

ARUCO_CASSETTE_MAP: Dict[int, str] = {cid: data['name'] for cid, data in CASSETTE_CATALOG.items()}

# Конфигурация пакетного замера 5 кассет
BATCH_CONFIG: Dict[str, Dict[str, Any]] = {
    'batch5': {
        'title': 'Пакетный замер 5 кассет (Кассеты 1–5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    },
    'stage1': {
        'title': 'Пакетный замер 5 кассет (Кассеты 1–5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    },
    'stage2': {
        'title': 'Пакетный замер 5 кассет (Кассеты 1–5)',
        'cassettes': [CASSETTE_CATALOG[1], CASSETTE_CATALOG[2], CASSETTE_CATALOG[3], CASSETTE_CATALOG[4], CASSETTE_CATALOG[5]]
    }
}

# Текущее состояние пакетной съемки (изменяемый словарь)
BATCH_STATE: Dict[str, Any] = {
    'active': False,
    'stage_key': 'batch5',
    'current_step': 0,
    'sessions': [],
    'verified_data': None
}

# Текущая активная сессия одиночного замера
PENDING_SESSION: Optional[Dict[str, Any]] = None

def get_pending_session() -> Optional[Dict[str, Any]]:
    with _STATE_LOCK:
        global PENDING_SESSION
        return dict(PENDING_SESSION) if PENDING_SESSION is not None else None

def set_pending_session(session: Optional[Dict[str, Any]]):
    with _STATE_LOCK:
        global PENDING_SESSION
        PENDING_SESSION = dict(session) if session is not None else None

def clear_pending_session():
    with _STATE_LOCK:
        global PENDING_SESSION
        PENDING_SESSION = None

def get_batch_state() -> Dict[str, Any]:
    with _STATE_LOCK:
        return BATCH_STATE

def reset_batch_state(stage_key: str = 'batch5'):
    with _STATE_LOCK:
        global BATCH_STATE
        BATCH_STATE.clear()
        BATCH_STATE.update({
            'active': False,
            'stage_key': stage_key,
            'current_step': 0,
            'sessions': [],
            'verified_data': None
        })

def update_batch_state(**kwargs):
    with _STATE_LOCK:
        global BATCH_STATE
        BATCH_STATE.update(kwargs)
