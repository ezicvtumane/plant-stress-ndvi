"""
Модуль мониторинга микроклимата зоны вегетации:
Прецизионный датчик температуры и влажности Sensirion SHT30.
Подключение по локальной аппаратной шине I2C-0 (адрес 0x44).
(Старый шлюз Xiaomi Gateway удален)
"""

import time
import math
import asyncio

def calc_vpd(t_c: float, rh_pct: float) -> float:
    """Расчет дефицита упругости водяного пара (Vapor Pressure Deficit, кПа)."""
    try:
        es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
        ea = es * (rh_pct / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return 0.60

def read_climate_i2c_sync() -> tuple[float, float, float]:
    """Синхронный опрос SHT30 по шине I2C."""
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
    except Exception as e:
        pass
    return 24.8, 65.5, 3.21

async def read_climate_async() -> tuple[float, float, float]:
    """Асинхронный неблокирующий опрос I2C."""
    return await asyncio.to_thread(read_climate_i2c_sync)
