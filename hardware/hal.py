import os
import platform
import random
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod

# Определяем, работаем ли мы на реальном железе (aarch64) или на Windows/Mac
IS_EDGE_DEVICE = platform.machine().lower() in ('aarch64', 'armv7l')

i2c_executor = ThreadPoolExecutor(max_workers=1)

# --- Climate Sensor ---
class ClimateSensor(ABC):
    @abstractmethod
    async def read_climate(self) -> tuple[float, float, float]:
        pass

class RealSHT30(ClimateSensor):
    def _read_sync(self):
        try:
            import smbus2
            with smbus2.SMBus(0) as bus:
                bus.write_i2c_block_data(0x44, 0x2C, [0x06])
                time.sleep(0.05)
                d = bus.read_i2c_block_data(0x44, 0x00, 6)
                t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
                rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
                if -20.0 <= t_c <= 70.0 and 0.0 <= rh <= 100.0:
                    return round(float(t_c), 1), round(float(rh), 1), 3.30
        except Exception as e:
            print(f"[SHT30 Error] {e}")
        return 24.8, 65.5, 3.21

    async def read_climate(self) -> tuple[float, float, float]:
        return await asyncio.get_running_loop().run_in_executor(i2c_executor, self._read_sync)

class MockSHT30(ClimateSensor):
    async def read_climate(self) -> tuple[float, float, float]:
        # Эмуляция реальных данных
        return round(24.0 + random.uniform(-1, 1), 1), round(60.0 + random.uniform(-5, 5), 1), 3.30


# --- Soil Sensor ---
class SoilSensor(ABC):
    @abstractmethod
    async def read_moisture(self, group_name: str = '') -> tuple[float, float]:
        pass

class RealADS1115(SoilSensor):
    def _read_sync(self):
        try:
            import smbus2
            with smbus2.SMBus(0) as bus:
                bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
                time.sleep(0.04)
                return bus.read_i2c_block_data(0x48, 0x00, 2)
        except Exception:
            return [0x33, 0x33] # mock fallback

    async def read_moisture(self, group_name: str = '') -> tuple[float, float]:
        data = await asyncio.get_running_loop().run_in_executor(i2c_executor, self._read_sync)
        if data:
            raw_val = (data[0] << 8) | data[1]
            if raw_val > 32767:
                raw_val -= 65536
            v_soil = round(raw_val * 4.096 / 32768.0, 2)
            pct = 100.0 * (2.03 - v_soil) / (2.03 - 0.57)
            return v_soil, round(max(0.0, min(100.0, pct)), 1)
        return 2.03, 0.0

class MockADS1115(SoilSensor):
    async def read_moisture(self, group_name: str = '') -> tuple[float, float]:
        v = round(1.5 + random.uniform(-0.5, 0.5), 2)
        pct = 100.0 * (2.03 - v) / (2.03 - 0.57)
        return v, round(max(0.0, min(100.0, pct)), 1)

# Получение синглтонов
def get_climate_sensor() -> ClimateSensor:
    return RealSHT30() if IS_EDGE_DEVICE else MockSHT30()

def get_soil_sensor() -> SoilSensor:
    return RealADS1115() if IS_EDGE_DEVICE else MockADS1115()

from core.config import settings

# --- Relay Controller ---
class RelayController(ABC):
    @abstractmethod
    def set_nir(self, active: bool):
        pass

    @abstractmethod
    def set_red(self, active: bool):
        pass

    @abstractmethod
    def cleanup(self):
        pass

class RealGPIODRelay(RelayController):
    def __init__(self):
        self._req = None
        try:
            import gpiod
            from gpiod.line import Direction, Value
            
            line_settings = gpiod.LineSettings(
                direction=Direction.OUTPUT,
                output_value=Value.INACTIVE,
                active_low=settings.RELAY_ACTIVE_LOW
            )
            self._req = gpiod.request_lines(
                '/dev/gpiochip4',
                consumer='plant-stress-relay',
                config={
                    settings.RELAY_PIN_NIR: line_settings,
                    settings.RELAY_PIN_RED: line_settings
                }
            )
            # Ensure off
            self.set_nir(False)
            self.set_red(False)
            print('[HAL] GPIO Relay initialized.')
        except Exception as e:
            print(f'[HAL] GPIOD Init Error: {e}')

    def _set_pin(self, pin: int, active: bool):
        if not self._req:
            return
        from gpiod.line import Value
        val = Value.ACTIVE if active else Value.INACTIVE
        self._req.set_value(pin, val)

    def set_nir(self, active: bool):
        self._set_pin(settings.RELAY_PIN_NIR, active)

    def set_red(self, active: bool):
        self._set_pin(settings.RELAY_PIN_RED, active)

    def cleanup(self):
        if self._req:
            self.set_nir(False)
            self.set_red(False)
            self._req.release()
            self._req = None

class MockRelay(RelayController):
    def __init__(self):
        print('[HAL] Mock Relay initialized.')
    def set_nir(self, active: bool):
        pass
    def set_red(self, active: bool):
        pass
    def cleanup(self):
        pass

_relay_instance = None
def get_relay_controller() -> RelayController:
    global _relay_instance
    if not _relay_instance:
        _relay_instance = RealGPIODRelay() if IS_EDGE_DEVICE else MockRelay()
    return _relay_instance
