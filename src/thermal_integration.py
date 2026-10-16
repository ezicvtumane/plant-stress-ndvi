"""
UNI-T UTi120S Thermal Imaging Integration & Transpiration Analysis
Author: Alisa Kovaleva
Project: Plant Stress Active Phenotyping System
"""

import logging
from typing import Dict, Optional, Tuple, Any
from pathlib import Path
import cv2
import numpy as np
from src import config

logger = logging.getLogger(__name__)


class ThermalAnalyzer:
    """
    Analyzes thermograms and thermal metrics from UNI-T UTi120S (NETD < 0.06 °C, e = 0.98).
    Calculates:
      1. Leaf-to-air temperature differential: Delta_T = T_leaf - T_air
      2. Crop Water Stress Index (CWSI):
         CWSI = (T_leaf - T_wet) / (T_dry - T_wet)
         - Cancels out absolute sensor bias (+/- 2 deg C) of the microbolometer.
         - CWSI ~ 0.0: Fully open stomata, optimal transpiration.
         - CWSI ~ 1.0: Complete stomatal closure, acute stress.
    """

    def __init__(self, emissivity: float = config.LEAF_EMISSIVITY):
        self.emissivity = emissivity

    def compute_cwsi(
        self,
        t_leaf: float,
        t_air: float,
        t_wet: Optional[float] = None,
        t_dry: Optional[float] = None
    ) -> float:
        """
        Calculates normalized Crop Water Stress Index (CWSI in [0.0, 1.0]).
        If reference targets are not measured directly:
          T_wet = T_air - 3.2 °C (maximum evaporative cooling baseline)
          T_dry = T_air + 2.0 °C (non-transpiring boundary layer baseline)
        """
        tw = t_wet if t_wet is not None else (t_air - 3.2)
        td = t_dry if t_dry is not None else (t_air + 2.0)

        if td <= tw:
            return 0.0

        raw_cwsi = (t_leaf - tw) / (td - tw)
        return float(np.clip(raw_cwsi, 0.0, 1.0))

    def analyze_thermal_data(
        self,
        t_leaf: float,
        t_air: float,
        t_wet: Optional[float] = None,
        t_dry: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Computes Delta_T and CWSI from calibrated radiometer readings and SHT30 air metrics.
        """
        delta_t = t_leaf - t_air
        cwsi = self.compute_cwsi(t_leaf, t_air, t_wet, t_dry)
        is_transpiration_depressed = cwsi >= 0.45 or delta_t >= -0.5

        return {
            "t_leaf_celsius": round(t_leaf, 2),
            "t_air_celsius": round(t_air, 2),
            "delta_t_celsius": round(delta_t, 2),
            "cwsi_index": round(cwsi, 3),
            "transpiration_depressed": is_transpiration_depressed,
            "emissivity": self.emissivity
        }

    def parse_thermal_frame(
        self,
        thermal_image_path: str,
        t_leaf: Optional[float] = None,
        t_air: Optional[float] = None,
        manual_t_wet: Optional[float] = None,
        manual_t_dry: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Validates thermal image file existence and integrity, and computes
        stomatic and CWSI indices using calibrated thermal telemetry.
        """
        path = Path(thermal_image_path)
        if not path.exists():
            raise FileNotFoundError(f"Thermal image not found: {thermal_image_path}")

        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Thermal image unreadable: {thermal_image_path}")

        if t_leaf is None or t_air is None:
            raise ValueError(
                "Calibrated radiometric T_leaf and ambient T_air must be provided "
                "from station telemetry / UTi120S spot readings. Raw pixel intensity "
                "cannot be used for uncalibrated thermal inference."
            )

        res = self.analyze_thermal_data(t_leaf, t_air, manual_t_wet, manual_t_dry)
        res["frame_shape"] = img.shape[:2]
        return res
