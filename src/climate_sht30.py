"""
Модуль мониторинга микроклимата зоны вегетации:
Прецизионный датчик температуры и влажности Sensirion SHT30.
Подключение по локальной аппаратной шине I2C-0 (адрес 0x44).
"""

import time
import math
import asyncio
from typing import Optional, Tuple

def calc_vpd(t_c: Optional[float], rh_pct: Optional[float]) -> Optional[float]:
    """Расчет дефицита упругости водяного пара (Vapor Pressure Deficit, кПа)."""
    if t_c is None or rh_pct is None:
        return None
    try:
        es = 0.61078 * math.exp((17.27 * float(t_c)) / (float(t_c) + 237.3))
        ea = es * (float(rh_pct) / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return None

def read_climate_i2c_sync() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Синхронный опрос SHT30 по шине I2C с авто-восстановлением шины."""
    try:
        import smbus2
        with smbus2.SMBus(0) as bus:
            bus.write_i2c_block_data(0x44, 0x2C, [0x06])
            time.sleep(0.05)
            d = bus.read_i2c_block_data(0x44, 0x00, 6)
            t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
            rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
            if -20.0 <= t_c <= 70.0 and 0.0 <= rh <= 100.0:
                t = round(float(t_c), 1)
                rh_val = round(float(rh), 1)
                v_rail = 3.30
                return t, rh_val, v_rail
    except Exception:
        try:
            from src.sensors_ads1115 import recover_i2c_bus
            recover_i2c_bus()
        except Exception:
            pass
    return None, None, None

async def read_climate_async() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Асинхронный неблокирующий опрос I2C."""
    return await asyncio.to_thread(read_climate_i2c_sync)
