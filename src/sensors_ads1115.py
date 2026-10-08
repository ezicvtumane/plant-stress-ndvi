"""
ADS1115 ADC & Capacitive Soil Moisture Sensor v1.2 Interface
Author: Alisa Kovaleva
Project: Plant Stress Active Phenotyping System
"""

import logging
import time
import subprocess
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Calibration defaults for Capacitive Soil Moisture Sensor v1.2 (3.3V power, peat substrate)
# Air / dry substrate: ~2.45 V (0.0% ПВ)
# Saturated substrate at field capacity: ~0.95 V (100.0% ПВ)
V_DRY_DEFAULT = 2.45
V_WET_DEFAULT = 0.95

CALIB_FILE = "/home/pi/plant-stress-ndvi/data/calibrated_soil.json"

def get_calib_limits() -> Tuple[float, float]:
    try:
        import json, os
        if os.path.exists(CALIB_FILE):
            with open(CALIB_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                vd = float(d.get('v_dry', V_DRY_DEFAULT))
                vw = float(d.get('v_wet', V_WET_DEFAULT))
                if vd > vw:
                    return vd, vw
    except Exception:
        pass
    return V_DRY_DEFAULT, V_WET_DEFAULT

_LAST_VALID_SOIL = (None, None)


def recover_i2c_bus():
    """Recovers the sunxi-twi controller on Allwinner H6/A733 if locked up."""
    try:
        cmd = (
            "echo 2510000.twi > /sys/bus/platform/drivers/sunxi-twi/unbind && "
            "sleep 0.1 && "
            "echo 2510000.twi > /sys/bus/platform/drivers/sunxi-twi/bind"
        )
        subprocess.run(["sudo", "sh", "-c", cmd], check=False, timeout=2.0)
        time.sleep(0.15)
        logger.info("I2C-0 sunxi-twi bus recovered successfully via sysfs rebind")
    except Exception as e:
        logger.warning("I2C bus recovery error: %s", e)


class SoilMoistureReader:
    """
    Manages 16-bit ADC ADS1115 communication over I2C (Bus 0) and converts
    raw voltages from capacitive soil moisture sensors into calibrated volumetric moisture (0-100%).
    Supports dynamic multi-channel detection (A0..A3) and automatic bus unsticking.
    """

    def __init__(self, v_dry: float = V_DRY_DEFAULT, v_wet: float = V_WET_DEFAULT):
        self.v_dry = v_dry
        self.v_wet = v_wet
        self.channels_map = {
            'A0': 0xC3,  # Single-ended AIN0, +/-4.096V
            'A1': 0xD3,  # Single-ended AIN1, +/-4.096V
            'A2': 0xE3,  # Single-ended AIN2, +/-4.096V
            'A3': 0xF3,  # Single-ended AIN3, +/-4.096V
        }
        self.is_hardware_available = False
        self._check_hardware()

    def _check_hardware(self):
        try:
            import smbus2
            with smbus2.SMBus(0) as bus:
                # Quick non-destructive check on address 0x48
                bus.write_quick(0x48)
            self.is_hardware_available = True
        except Exception:
            self.is_hardware_available = False

    def voltage_to_percentage(self, voltage: float) -> float:
        """
        Converts sensor voltage to moisture percentage (0-100%).
        Uses active calibration limits (v_dry, v_wet) for peat substrate.
        """
        v_d, v_w = get_calib_limits()
        if v_d <= v_w:
            return 0.0
        percentage = ((v_d - voltage) / (v_d - v_w)) * 100.0
        return round(max(0.0, min(100.0, float(percentage))), 1)

    def read_channels(self) -> Dict[str, Dict[str, float]]:
        """
        Reads raw voltages and calculates moisture percentages for channels A0..A3.
        Provides both 'A0' and 'channel_0' keys for backward compatibility.
        """
        global _LAST_VALID_SOIL
        res = {}
        bus = None

        try:
            import smbus2
            bus = smbus2.SMBus(0)
            for ch_name, cfg_msb in self.channels_map.items():
                try:
                    bus.write_i2c_block_data(0x48, 0x01, [cfg_msb, 0x83])
                    time.sleep(0.04)
                    data = bus.read_i2c_block_data(0x48, 0x00, 2)
                    raw_val = (data[0] << 8) | data[1]
                    if raw_val > 0x7FFF:
                        raw_val -= 0x10000
                    voltage = round(raw_val * (4.096 / 32768.0), 3)
                    pct = self.voltage_to_percentage(voltage)
                    res[ch_name] = {'voltage_V': voltage, 'moisture_percent': pct}
                    ch_num = ch_name.replace('A', '')
                    res[f'channel_{ch_num}'] = res[ch_name]
                except Exception as e:
                    logger.debug("ADS1115 %s read error: %s", ch_name, e)
                    res[ch_name] = {'voltage_V': 0.0, 'moisture_percent': 0.0}
                    ch_num = ch_name.replace('A', '')
                    res[f'channel_{ch_num}'] = res[ch_name]
            bus.close()
            self.is_hardware_available = True
        except Exception as e:
            logger.warning("I2C Bus error reading ADS1115: %s", e)
            self.is_hardware_available = False
            if bus:
                try:
                    bus.close()
                except Exception:
                    pass
            # Аппаратный отказ или отключенный сенсор: возвращаем честный None
            for ch_name in self.channels_map.keys():
                ch_num = ch_name.replace('A', '')
                res[ch_name] = {'voltage_V': None, 'moisture_percent': None, 'error': 'DISCONNECTED'}
                res[f'channel_{ch_num}'] = res[ch_name]

        return res

    def get_active_moisture(self, group_name: str = '') -> Tuple[float, float]:
        """
        Dynamically finds the connected soil moisture sensor:
        1. If group_name maps to a channel (контроль->A0, осмос/соль->A1, засуха->A2)
           and that channel has a valid sensor voltage (0.35V - 2.80V), use it.
        2. Otherwise, scans all channels (A0..A3) to pick whichever channel has a live sensor
           connected (valid voltage in range 0.35V - 2.80V).
        3. If no channel is active, returns the last known good reading instead of zeroing out.
        """
        global _LAST_VALID_SOIL
        gn = (group_name or '').lower()
        ch_data = self.read_channels()

        preferred_channel = None
        if any(k in gn for k in ['контр', 'control']):
            preferred_channel = 'A0'
        elif any(k in gn for k in ['осмос', 'соль', 'засол', 'osmo', 'salt', 'nacl']):
            preferred_channel = 'A1'
        elif any(k in gn for k in ['засух', 'термин', 'drought']):
            preferred_channel = 'A2'

        # Check preferred channel first
        if preferred_channel and preferred_channel in ch_data:
            c = ch_data[preferred_channel]
            v = c.get('voltage_V', 0.0)
            if 0.35 <= v <= 2.80:
                _LAST_VALID_SOIL = (v, c.get('moisture_percent', 0.0))
                return _LAST_VALID_SOIL

        # If preferred channel is invalid or empty, auto-detect any channel with active sensor
        for ch_key in ['A1', 'A0', 'A2', 'A3']:
            if ch_key in ch_data:
                c = ch_data[ch_key]
                v = c.get('voltage_V', 0.0)
                if 0.35 <= v <= 2.80:
                    _LAST_VALID_SOIL = (v, c.get('moisture_percent', 0.0))
                    return _LAST_VALID_SOIL

        # Если датчик не подключен или не отвечает - возвращаем (None, None)
        return (None, None)

    def read_for_group(self, group_name: str) -> Tuple[float, float]:
        """Backward-compatible wrapper for get_active_moisture."""
        return self.get_active_moisture(group_name)


_global_reader = SoilMoistureReader()
