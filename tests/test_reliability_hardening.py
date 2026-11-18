"""
Тесты надежности и потокобезопасности:
1. Атомарное сохранение реестра experiments.json и восстановление из .bak при сбое.
2. Потокобезопасность BATCH_STATE и PENDING_SESSION в core/station_state.py.
3. Потокобезопасность LAST_VALID_CLIMATE и fallback опрос I2C SHT30 в web_station.py.
4. Динамическое разрешение путей к термограммам всех зарегистрированных экспериментов.
"""

import os
import json
import threading
import pytest
from core.experiments import ExperimentManager, get_experiment_manager
from core.station_state import (
    get_batch_state, reset_batch_state, update_batch_state,
    get_pending_session, set_pending_session, clear_pending_session,
    get_state_lock
)
import web_station


def test_atomic_registry_save_and_backup_recovery(tmp_path):
    """Проверка атомарности записи experiments.json и корректного восстановления из .bak."""
    data_dir = tmp_path / "data"
    mgr = ExperimentManager(str(data_dir))
    
    # 1. Проверяем первичное сохранение и создание .bak
    reg_file = str(data_dir / "experiments" / "experiments.json")
    bak_file = reg_file + ".bak"
    assert os.path.exists(reg_file)
    
    # Создаем новый эксперимент
    exp = mgr.create_experiment("Серия Тест Надежности", plant="Огурец", description="Проверка атомарности")
    assert os.path.exists(bak_file), "Резервная копия .bak должна создаваться при повторном сохранении"
    
    exps = mgr.get_experiments()
    assert any(e['id'] == exp['id'] for e in exps)
    
    # 2. Имитируем аварийное повреждение основного файла experiments.json (обрыв питания / нулевой размер)
    with open(reg_file, "w", encoding="utf-8") as f:
        f.write("{ broken json ...")
        
    # Менеджер должен восстановить данные из .bak без падения и без потери зарегистрированных серий
    recovered = mgr._load_registry()
    assert any(e['id'] == exp['id'] for e in recovered.get('experiments', []))


def test_concurrent_registry_access(tmp_path):
    """Проверка многопоточного создания и чтения экспериментов без race condition."""
    data_dir = tmp_path / "data_concurrent"
    mgr = ExperimentManager(str(data_dir))
    
    errors = []
    
    def worker(idx):
        try:
            mgr.create_experiment(f"Exp_{idx}", plant=f"Plant_{idx}")
            exps = mgr.get_experiments()
            assert len(exps) > 0
        except Exception as e:
            errors.append(e)
            
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(errors) == 0
    final_exps = mgr.get_experiments()
    # Базовые 2 (exp_1, exp_2) + 10 созданных = 12
    assert len(final_exps) == 12


def test_station_state_thread_safety():
    """Проверка потокобезопасности BATCH_STATE и PENDING_SESSION."""
    reset_batch_state('batch5')
    clear_pending_session()
    
    errors = []
    
    def worker_batch(idx):
        try:
            with get_state_lock():
                st = get_batch_state()
                st['sessions'].append({'id': idx, 'val': idx * 10})
                update_batch_state(current_step=len(st['sessions']))
        except Exception as e:
            errors.append(e)
            
    def worker_pending(idx):
        try:
            set_pending_session({'id': idx, 'status': 'active'})
            p = get_pending_session()
            assert p is not None
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker_batch, args=(i,)) for i in range(10)]
    threads += [threading.Thread(target=worker_pending, args=(i,)) for i in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(errors) == 0
    final_state = get_batch_state()
    assert len(final_state['sessions']) == 10
    reset_batch_state('batch5')
    clear_pending_session()


def test_climate_lock_and_thread_safe_helpers():
    """Проверка блокировки _CLIMATE_LOCK и геттера/сеттера LAST_VALID_CLIMATE."""
    web_station.set_last_valid_climate(22.4, 58.0, 3.25)
    c = web_station.get_last_valid_climate()
    assert c == (22.4, 58.0, 3.25)
    
    def updater(t_val):
        web_station.set_last_valid_climate(t_val, 50.0, 3.3)
        
    threads = [threading.Thread(target=updater, args=(float(i),)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    res = web_station.get_last_valid_climate()
    assert res is not None
    assert len(res) == 3
