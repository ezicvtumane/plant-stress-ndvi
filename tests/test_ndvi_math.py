"""
Unit Tests for NDVI Math, Soil Moisture Calibration and Thermal Metrics
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import numpy as np
import pytest
from src.ndvi_processor import NDVIProcessor
from src.sensors_ads1115 import SoilMoistureReader
from src.statistical_analysis import ExperimentStatistics

def test_soil_moisture_two_point_calibration():
    """Verify linear interpolation between V_DRY (2.75V) and V_WET (1.30V)."""
    reader = SoilMoistureReader(v_dry=2.75, v_wet=1.30)
    
    # Boundary conditions
    assert reader.voltage_to_percentage(2.75) == pytest.approx(0.0, abs=1e-2)
    assert reader.voltage_to_percentage(1.30) == pytest.approx(100.0, abs=1e-2)
    
    # Midpoint (2.025 V -> 50%)
    assert reader.voltage_to_percentage(2.025) == pytest.approx(50.0, abs=0.5)

    # Clamping checks
    assert reader.voltage_to_percentage(3.10) == 0.0
    assert reader.voltage_to_percentage(1.00) == 100.0

def test_k_factor_gray_card_calibration():
    """Verify that k = Red / NIR on 18% gray card with background subtraction."""
    processor = NDVIProcessor(k_factor=1.0)
    
    ambient = np.full((10, 10), 15, dtype=np.uint8)
    nir_flash = np.full((10, 10), 115, dtype=np.uint8)  # Net NIR = 100
    red_flash = np.full((10, 10), 125, dtype=np.uint8)  # Net Red = 110

    k = processor.compute_k_factor_from_gray_card(ambient, nir_flash, red_flash)
    # Expected k = 110 / 100 = 1.10
    assert k == pytest.approx(1.10, abs=1e-3)

def test_ndvi_pixelwise_calculation():
    """Verify healthy vs stressed vegetative index calculation."""
    # With k = 1.0:
    processor = NDVIProcessor(k_factor=1.0)
    
    ambient = np.zeros((20, 20), dtype=np.uint8)
    # Healthy leaf: High NIR (200), Low Red (30)
    # NDVI = (200 - 30) / (200 + 30) = 170 / 230 = ~0.739
    nir = np.full((20, 20), 200, dtype=np.uint8)
    red = np.full((20, 20), 30, dtype=np.uint8)

    ndvi_map, mask, metrics = processor.compute_ndvi_map(ambient, nir, red)

    assert metrics["plant_pixel_count"] == 400
    assert metrics["ndvi_mean"] == pytest.approx(0.7391, abs=1e-2)
    assert metrics["healthy_percent"] == 100.0
    assert metrics["latent_stress_percent"] == 0.0

def test_statistical_significance_computation():
    """Verify synthetic dataset generates p < 0.01 for drought vs control on Day 4."""
    stats_eng = ExperimentStatistics()
    df = stats_eng.load_or_generate_dataset()
    assert len(df) == 30 * 7  # 30 plants over 7 days

    p_ndvi, p_dt, p_sal_ndvi, p_sal_dt = stats_eng.compute_student_t_test(day=4)
    # On Day 4, stress is pronounced and statistically significant
    assert p_ndvi < 0.01
    assert p_dt < 0.01

def test_bayer_demultiplexing_3channel():
    """Verify physical Bayer demultiplexing extracts pure Red channel and averaged NIR."""
    from src.ndvi_processor import NDVIProcessor
    proc = NDVIProcessor(k_factor=1.0)
    
    # 3-channel frame: BGR
    # Ambient: B=5, G=5, R=5
    ambient = np.full((10, 10, 3), 5, dtype=np.uint8)
    
    # NIR flash: B=105, G=105, R=105 -> Mean=105 -> Net NIR = 100
    nir_flash = np.full((10, 10, 3), 105, dtype=np.uint8)
    
    # Red flash (660nm): B=5, G=5, R=105 -> Pure R=105 -> Net Red = 100
    red_flash = np.zeros((10, 10, 3), dtype=np.uint8)
    red_flash[:, :, 0] = 5   # Blue
    red_flash[:, :, 1] = 5   # Green
    red_flash[:, :, 2] = 105 # Red
    
    k = proc.compute_k_factor_from_gray_card(ambient, nir_flash, red_flash)
    # Net Red (100) / Net NIR (100) = 1.0
    assert k == pytest.approx(1.0, abs=1e-3)

def test_cwsi_calculation():
    """Verify Crop Water Stress Index boundaries and normalization."""
    from src.thermal_integration import ThermalAnalyzer
    analyzer = ThermalAnalyzer()

    t_air = 22.0
    t_wet = 18.8  # Transpiring baseline (-3.2 C)
    t_dry = 24.0  # Non-transpiring baseline (+2.0 C)

    # Optimum hydration: T_leaf = T_wet -> CWSI = 0.0
    assert analyzer.compute_cwsi(18.8, t_air, t_wet, t_dry) == pytest.approx(0.0, abs=1e-3)

    # Severe stress: T_leaf = T_dry -> CWSI = 1.0
    assert analyzer.compute_cwsi(24.0, t_air, t_wet, t_dry) == pytest.approx(1.0, abs=1e-3)

    # Moderate stress: T_leaf = 21.4 (midpoint) -> CWSI = 0.5
    assert analyzer.compute_cwsi(21.4, t_air, t_wet, t_dry) == pytest.approx(0.5, abs=1e-2)

