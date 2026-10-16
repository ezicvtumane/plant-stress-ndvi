"""
Hardware, Optical and Sensor Configuration
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
TRIPTYCH_DIR = DATA_DIR / "triptychs"

# Ensure directories exist
for d in [RAW_DATA_DIR, PROCESSED_DATA_DIR, TRIPTYCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Camera / Optical Sensor Configuration
# Logitech C270 / diymore IMX179 NoIR sensor running at native 1280x960 (4:3)
CAMERA_INDEX = 0  # /dev/video0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 960
CAMERA_MANUAL_EXPOSURE = 1  # 1 = Manual mode in V4L2
CAMERA_EXPOSURE_VALUE = 120  # Fixed shutter value
CAMERA_AUTO_WB = 0  # 0 = Manual White Balance (AWB disabled)

# Photometric Calibration Parameters (PTFE / Pure Fluoroplastic-4 White Reference)
# k_bal = I_660_ref / I_850_ref (sensor sensitivity ratio balancing 660nm and 850nm)
DEFAULT_K_COEFFICIENT = 4.07
FLAT_FIELD_K_FACTOR = 0.0518  # Lens vignetting compensation factor for edge cells

# Plant Segmentation & Masking
NIR_BACKGROUND_THRESHOLD = 15  # Minimum pixel intensity under 850nm to classify as plant
MIN_CONTOUR_AREA = 500  # Minimum pixel area for valid leaves

# Physiological Stress Thresholds (NDVI)
NDVI_HEALTHY_MIN = 0.60  # Normal active photosynthetic tissue (healthy chloroplasts)
NDVI_STRESS_MIN = 0.35   # Latent stress range: 0.35 < NDVI <= 0.60
NDVI_NECROTIC_MAX = 0.35 # Severe stress / senescence / cellular damage

# Thermal Stress & Physiological Alert Thresholds (Delta_T = T_leaf - T_air)
DELTA_T_OPTIMUM_MAX = 0.0    # Normal transpiration: leaf is cooler than air (Delta_T < 0 C)
DELTA_T_ALERT_THRESHOLD = 0.8 # Early alert threshold: Delta_T >= +0.8 C (stomata closing)
CWSI_ALERT_THRESHOLD = 0.5   # Empirical Crop Water Stress Index alert

# Thermal & NDVI False-Color Palettes
NDVI_COLORMAP = "COLORMAP_JET"      # Standard OpenCV palette for NDVI thermal representation
THERMAL_COLORMAP = "COLORMAP_INFERNO" # High-contrast palette for infrared thermography

# Soil Moisture Sensor Calibration (ADS1115 v1.2 Capacitive Sensor)
# Calibrated for peat substrate in standard seedling cassettes (3.3V supply):
# V_DRY = ~2.03 V (air / dry peat substrate, 0.0% ПВ)
# V_WET = ~0.44 V (water / fully saturated substrate, 100.0% ПВ, Delta_V = 1.59 V)
V_DRY = 2.03
V_WET = 0.44
ADS1115_I2C_ADDRESS = 0x48
ADS1115_I2C_BUS = 0  # /dev/i2c-0 (sun60i-a733-i2c0 overlay)

# Relay GPIO Control Pins (Orange Pi 4 Pro V1.3.2 / Allwinner H6)
# Directly controlling 2-channel 5V relay module via gpiochip1 (Port L lines)
# Pin 10 -> PL7 (line 7 on gpiochip1) for 850nm (NIR)
# Pin 7  -> PL4 (line 4 on gpiochip1) for 660nm (Red)
RELAY_PIN_850NM = 7  # PL7
RELAY_PIN_660NM = 4  # PL4
RELAY_GPIOCHIP = "/dev/gpiochip1"
RELAY_ACTIVE_LOW = True
FLASH_SETTLING_TIME_SEC = 0.15  # Stabilization delay after switching relay before frame capture

# Thermal Imaging Configuration (UNI-T UTi120S)
LEAF_EMISSIVITY = 0.98  # Standard emissivity for plant leaves (Pisum sativum L.)
