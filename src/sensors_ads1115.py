"""
ADS1115 ADC & Capacitive Soil Moisture Sensor v1.2 Interface
Author: Alisa Kovaleva
Project: Plant Stress Active Phenotyping System
"""

import logging
from typing import Tuple, Dict
from src import config

logger = logging.getLogger(__name__)

class SoilMoistureReader:
    """
    Manages 16-bit ADC ADS1115 communication over I2C and converts raw voltage
    from capacitive sensors v1.2 into calibrated volumetric soil moisture (0-100%).
    """
    def __init__(self, v_dry: float = config.V_DRY, v_wet: float = config.V_WET):
        self.v_dry = v_dry
        self.v_wet = v_wet
        self.is_hardware_available = False
        self._adc = None
        self._chan0 = None
        self._chan1 = None
        
        self._init_hardware()

    def _init_hardware(self):
        """Initializes Adafruit ADS1x15 over I2C."""
        try:
            import board
            import busio
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn

            i2c = busio.I2C(board.SCL, board.SDA)
            self._adc = ADS.ADS1115(i2c, address=config.ADS1115_I2C_ADDRESS)
            self._chan0 = AnalogIn(self._adc, ADS.P0)
            self._chan1 = AnalogIn(self._adc, ADS.P1)
            self.is_hardware_available = True
            logger.info("ADS1115 hardware successfully initialized at 0x%02X", config.ADS1115_I2C_ADDRESS)
        except Exception as e:
            logger.warning("ADS1115 hardware not detected or running in simulation mode: %s", e)
            self.is_hardware_available = False

    def voltage_to_percentage(self, voltage: float) -> float:
        """
        Converts sensor output voltage to moisture percentage (0-100%)
        using linear two-point calibration:
          V_DRY (~2.75 V) -> 0%
          V_WET (~1.30 V) -> 100%
        """
        if self.v_dry == self.v_wet:
            return 0.0
        
        # Capacitive sensor output decreases as moisture increases
        percentage = ((self.v_dry - voltage) / (self.v_dry - self.v_wet)) * 100.0
        # Clamp to 0.0 - 100.0 %
        return max(0.0, min(100.0, float(percentage)))

    def read_channels(self) -> Dict[str, Dict[str, float]]:
        """
        Reads raw voltages and calculates moisture percentages for channels A0 and A1.
        Returns dictionary with voltage and moisture for both channels.
        """
        if self.is_hardware_available:
            v0 = float(self._chan0.voltage)
            v1 = float(self._chan1.voltage)
        else:
            # Simulation fallback for development / testing
            v0 = 1.95  # Moderate moisture
            v1 = 2.45  # Low moisture
        
        m0 = self.voltage_to_percentage(v0)
        m1 = self.voltage_to_percentage(v1)

        return {
            "channel_0": {"voltage_V": round(v0, 4), "moisture_percent": round(m0, 2)},
            "channel_1": {"voltage_V": round(v1, 4), "moisture_percent": round(m1, 2)}
        }
