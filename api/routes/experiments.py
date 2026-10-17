"""
Маршруты управления сериями опытов (растения, когорты, переключение и создание).
Автор: Ковалева Алиса, Большие вызовы (Сириус)
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from core.config import settings
from core.experiments import get_experiment_manager

router = APIRouter(tags=["experiments"])

DATA_DIR = settings.DATA_DIR

@router.post('/api/experiment/switch')
async def handle_experiment_switch(request: Request):
    """Переключение активной серии опытов."""
    form = await request.form()
    exp_id = str(form.get('exp_id', '')).strip()
    if exp_id:
        exp_mgr = get_experiment_manager(DATA_DIR)
        exp_mgr.set_active_experiment(exp_id)
    return RedirectResponse(url='/?msg=exp_switched', status_code=303)

@router.post('/api/experiment/create')
async def handle_experiment_create(request: Request):
    """Создание новой серии опытов и её активация."""
    form = await request.form()
    name = str(form.get('name', '')).strip()
    plant = str(form.get('plant', '')).strip()
    desc = str(form.get('description', '')).strip()
    if name:
        exp_mgr = get_experiment_manager(DATA_DIR)
        exp_mgr.create_experiment(name, plant, desc)
    return RedirectResponse(url='/?msg=exp_created', status_code=303)
