"""
ADS1115 ADC & Capacitive Soil Moisture Sensor v1.2 Interface
Author: Alisa Kovaleva
Project: Plant Stress Active Phenotyping System
"""

import logging
import time
import subprocess
from typing import Dict, Tuple, Optional
from src import config

logger = logging.getLogger(__name__)

# Calibration defaults for Capacitive Soil Moisture Sensor v1.2 (3.3V supply)
# Air / dry substrate: ~2.03 V (0.0% ПВ)
# Saturated peat substrate / water: ~0.44 V (100.0% ПВ)
V_DRY_DEFAULT = config.V_DRY
V_WET_DEFAULT = config.V_WET
_LAST_VALID_SOIL = None


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
    
    Hardware architecture:
    - The screening box has a single 3-pin quick-disconnect connector wired directly to Channel A0.
    - Cassettes K1 (Контроль), K2 (Осмос), and K3 (Засуха) connect their probe to A0 upon insertion.
    - Channels A1..A3 are reserved / tied to GND to prevent floating input noise.
    """

    def __init__(self, v_dry: float = config.V_DRY, v_wet: float = config.V_WET):
        self.v_dry = v_dry
        self.v_wet = v_wet
        self.channels_map = {
            'A0': 0xC3,  # Single-ended AIN0, +/-4.096V (Active box sensor connector)
            'A1': 0xD3,  # Single-ended AIN1, +/-4.096V (Reserved / tied to GND)
            'A2': 0xE3,  # Single-ended AIN2, +/-4.096V (Reserved / tied to GND)
            'A3': 0xF3,  # Single-ended AIN3, +/-4.096V (Reserved / tied to GND)
        }
        self.is_hardware_available = False
        self._check_hardware()

    def _check_hardware(self):
        try:
            import smbus2
            with smbus2.SMBus(0) as bus:
                bus.write_quick(0x48)
            self.is_hardware_available = True
        except Exception:
            self.is_hardware_available = False

    def voltage_to_percentage(self, voltage: float) -> float:
        """
        Converts sensor voltage to moisture percentage (0-100%).
        Capacitive sensor voltage drops as moisture rises:
          V >= v_dry -> 0%
          V <= v_wet -> 100%
        Grounded or disconnected channels (< 0.20V) return 0.0%.
        """
        if voltage < 0.20:
            return 0.0
        if self.v_dry == self.v_wet:
            return 0.0
        percentage = ((self.v_dry - voltage) / (self.v_dry - self.v_wet)) * 100.0
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
            for ch_name in self.channels_map.keys():
                ch_num = ch_name.replace('A', '')
                res[ch_name] = {'voltage_V': 0.0, 'moisture_percent': 0.0}
                res[f'channel_{ch_num}'] = res[ch_name]

        return res

    def get_active_moisture(self, group_name: str = '') -> Tuple[Optional[float], Optional[float]]:
        """
        Reads soil moisture for the cassette currently placed in the screening box.
        
        Hardware architecture:
        - The optical box features a single quick-disconnect plug routed to ADC Channel A0.
        - Cassettes K1 (Контроль), K2 (Осмос), and K3 (Засуха) connect their probe to A0.
        - Cohorts K4 (Превенция) and K5 (Реакция) do not use soil probes (gravimetric tracking).
        """
        global _LAST_VALID_SOIL
        gn = (group_name or '').lower()

        # Cohorts K4 and K5 do not have embedded probes
        if any(k in gn for k in ['превен', 'реакц', 'визуал', 'prevent', 'react']):
            return (None, None)

        ch_data = self.read_channels()

        # Primary reading from the active box connector on Channel A0
        if 'A0' in ch_data:
            c = ch_data['A0']
            v = c.get('voltage_V', 0.0)
            if 0.35 <= v <= 2.80:
                pct = c.get('moisture_percent', 0.0)
                _LAST_VALID_SOIL = (v, pct)
                return (v, pct)

        # Fallback to last valid reading if A0 is temporarily unseated or disconnected
        if _LAST_VALID_SOIL is not None:
            return _LAST_VALID_SOIL

        return (None, None)

    def read_for_group(self, group_name: str) -> Tuple[Optional[float], Optional[float]]:
        """Backward-compatible wrapper for get_active_moisture."""
        return self.get_active_moisture(group_name)


_global_reader = SoilMoistureReader()
