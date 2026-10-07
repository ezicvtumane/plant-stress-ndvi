import logging
import time
import smbus2
from typing import Dict
from src import config

logger = logging.getLogger(__name__)

class SoilMoistureReader:
    def __init__(self, v_dry: float = 2.03, v_wet: float = 0.57):
        self.v_dry = v_dry
        self.v_wet = v_wet
        self.channels_map = {
            'A0': 0xC3, # Контроль
            'A1': 0xD3, # Засоление
            'A2': 0xE3  # Терминальная засуха / Гибель
        }

    def voltage_to_percentage(self, voltage: float) -> float:
        if self.v_dry == self.v_wet: return 0.0
        percentage = ((self.v_dry - voltage) / (self.v_dry - self.v_wet)) * 100.0
        return max(0.0, min(100.0, float(percentage)))

    def read_channels(self) -> Dict[str, Dict[str, float]]:
        res = {}
        try:
            bus = smbus2.SMBus(0)
            for ch_name, config_msb in self.channels_map.items():
                try:
                    bus.write_i2c_block_data(0x48, 0x01, [config_msb, 0x83])
                    time.sleep(0.05)
                    data = bus.read_i2c_block_data(0x48, 0x00, 2)
                    val = (data[0] << 8) | data[1]
                    if val > 0x7FFF: val -= 0x10000
                    voltage = val * (4.096 / 32768.0)
                    pct = self.voltage_to_percentage(voltage)
                    res[ch_name] = {'voltage_V': round(voltage, 4), 'moisture_percent': round(pct, 1)}
                except Exception as e:
                    logger.error(f'ADS1115 {ch_name} read error: {e}')
                    res[ch_name] = {'voltage_V': 0.0, 'moisture_percent': 0.0}
            bus.close()
        except Exception as e:
            logger.error(f'SMBus error: {e}')
            for ch in self.channels_map.keys():
                res[ch] = {'voltage_V': 0.0, 'moisture_percent': 0.0}
        return res

    def read_for_group(self, group_name: str):
        gn = group_name.lower()
        channels = self.read_channels()
        # Маппинг кассет (как просил пользователь)
        if 'контр' in gn or 'эталон' in gn:
            # Контроль -> A0
            ch = 'A0'
        elif 'соль' in gn or 'засол' in gn or 'nacl' in gn:
            # Засоление -> A1
            ch = 'A1'
        elif 'засух' in gn or 'гибел' in gn or 'поздн' in gn or 'термин' in gn:
            # Терминальная засуха (гибель) -> A2
            ch = 'A2'
        else:
            # Для остальных кассет (Превентивная регидратация, визуальный контроль)
            # Пользователь: 'Опрос влажности почвы в этих касетах не осуществляй'
            return 0.0, 0.0
            
        return channels[ch]['voltage_V'], channels[ch]['moisture_percent']

_global_reader = SoilMoistureReader()
