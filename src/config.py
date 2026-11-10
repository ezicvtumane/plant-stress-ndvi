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

# Camera / Optical Sensor Configuration (Evolutionary TRL Progression):
# - Wave 1 (Pisum sativum, TRL 3): Modified Logitech C270 NoIR (1280x960, 4:3)
# - Wave 2 (Cucumis sativus, TRL 4): Industrial Sony IMX179 NoIR M12 sensor (400-1000 nm)
CAMERA_INDEX = 0  # /dev/video0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 960
CAMERA_MANUAL_EXPOSURE = 1  # 1 = Manual mode in V4L2
CAMERA_EXPOSURE_VALUE = 120  # Fixed shutter value
CAMERA_AUTO_WB = 0  # 0 = Manual White Balance (AWB disabled)

# Photometric Calibration Parameters (PTFE / Pure Fluoroplastic-4 White Reference)
# k_bal = I_660_ref / I_850_ref (sensor sensitivity ratio balancing 660nm and 850nm)
DEFAULT_K_COEFFICIENT = 4.07
ACTIVE_KBAL_CALIBRATION_PROFILE = "series2_imx179_v1"
KBAL_CALIBRATION_PROFILES = {
    "series1_c270_v1": {
        "calibration_version": "calib-kbal-s1-2026-10-08",
        "series": "Series 1 (Pisum sativum)",
        "camera": "Logitech C270 NoIR (1280x960)",
        "exposure_profile": "Fixed manual exposure (V4L2)",
        "k_bal": DEFAULT_K_COEFFICIENT,
        "date": "2026-10-08",
        "ptfe_reference_archived": True,
        "notes": "I_660/I_850 = 195.2/48.0; archived in docs/images/calibration_teflon/",
    },
    "series2_imx179_v1": {
        "calibration_version": "calib-kbal-s2-2026-11-07",
        "series": "Series 2 (Cucumis sativus, Wave 2)",
        "camera": "Sony IMX179 NoIR M12 (1280x960)",
        "exposure_profile": "NIR 850nm: 5000us/gain 115; Red 660nm: 100us/gain 40",
        "k_bal": 1.150,
        "date": "2026-11-07",
        "ptfe_reference_archived": False,
        "notes": "Active runtime value stored in data/calibrated_k_bal.txt; raw PTFE frame from 2026-11-07 not archived",
    },
}
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

# Empirical Idso NWSB (Non-Water-Stressed Baseline) parameters for Pisum sativum (Stand #0)
# Delta_T_wet = IDSO_NWSB_INTERCEPT - IDSO_NWSB_SLOPE * VPD
# Exact OLS fit across the 3 verified Stand #0 points from CALIBRATION.md & docs/calibration/
# ((0.53, -0.4), (0.91, -0.6), (1.61, -1.7)) yields a=0.3703, b=1.2494, R^2=0.9562 (p=0.134).
# Replaces unverified legacy constants (a=0.24, b=1.20, claimed R^2=0.985; actual R^2=0.9351).
# Exploratory express-indicator only; Delta_T_dry=+1.50 C is a 1-point Vaseline approximation.
IDSO_NWSB_INTERCEPT = 0.3703
IDSO_NWSB_SLOPE = 1.2494
IDSO_DELTA_T_DRY = 1.50  # 1-point approximation via Oleum Vaselini stomatal block on Stand #0

# Thermal & NDVI False-Color Palettes
NDVI_COLORMAP = "COLORMAP_JET"      # Standard OpenCV palette for NDVI thermal representation
THERMAL_COLORMAP = "COLORMAP_INFERNO" # High-contrast palette for infrared thermography

# Soil Moisture Sensor Calibration (ADS1115 v1.2 Capacitive Sensor)
# Two-point linear calibration for peat substrate (0% ПВ and 70% ПВ reference at 3.3V supply):
# V_DRY = 2.072 V (dry sensor / 0.0% ПВ)
# V_WET = 1.923 V (extrapolated 100.0% ПВ from 1.968 V at 70% ПВ)
V_DRY = 2.072
V_WET = 1.923
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
