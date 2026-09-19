"""
Dual-Channel Relay Strobing Controller
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import time
import logging
from src import config

logger = logging.getLogger(__name__)

class RelayController:
    """
    Controls dual-channel relay for active strobed illumination:
    - Channel 1: 850 nm NIR LED matrix
    - Channel 2: 660 nm Deep Red LED
    """
    def __init__(self):
        self.is_hardware = False
        self._gpio = None
        self._init_gpio()

    def _init_gpio(self):
        """Initializes GPIO pins on Armbian / Orange Pi or Linux SBC."""
        try:
            # Try OPi.GPIO or RPi.GPIO or gpiod
            try:
                import OPi.GPIO as GPIO
            except ImportError:
                import RPi.GPIO as GPIO
            
            self._gpio = GPIO
            self._gpio.setmode(GPIO.BOARD)
            self._gpio.setup(config.RELAY_PIN_850NM, GPIO.OUT)
            self._gpio.setup(config.RELAY_PIN_660NM, GPIO.OUT)
            
            # Turn all off initially
            self.all_off()
            self.is_hardware = True
            logger.info("GPIO relay controller initialized successfully.")
        except Exception as e:
            logger.warning("Hardware GPIO not found. Running relay in simulation mode: %s", e)
            self.is_hardware = False

    def _write_pin(self, pin: int, active: bool):
        if not self.is_hardware:
            logger.debug("[MOCK RELAY] Pin %d set to %s", pin, "ON" if active else "OFF")
            return
        
        # Determine logical level based on active-low setting
        level = (self._gpio.LOW if active else self._gpio.HIGH) if config.RELAY_ACTIVE_LOW else (self._gpio.HIGH if active else self._gpio.LOW)
        self._gpio.output(pin, level)

    def set_850nm(self, active: bool):
        """Switches 850 nm NIR illumination channel."""
        self._write_pin(config.RELAY_PIN_850NM, active)
        if active:
            time.sleep(config.FLASH_SETTLING_TIME_SEC)

    def set_660nm(self, active: bool):
        """Switches 660 nm Deep Red illumination channel."""
        self._write_pin(config.RELAY_PIN_660NM, active)
        if active:
            time.sleep(config.FLASH_SETTLING_TIME_SEC)

    def all_off(self):
        """Disables all illumination channels."""
        self._write_pin(config.RELAY_PIN_850NM, False)
        self._write_pin(config.RELAY_PIN_660NM, False)

    def cleanup(self):
        """Cleans up GPIO state upon script termination."""
        self.all_off()
        if self.is_hardware and self._gpio:
            self._gpio.cleanup()
