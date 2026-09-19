"""
Full Acquisition Pipeline & Strobe Measurement Orchestrator
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
import cv2
import pandas as pd

from src import config
from src.sensors_ads1115 import SoilMoistureReader
from src.relay_controller import RelayController
from src.camera_v4l2 import CameraV4L2
from src.ndvi_processor import NDVIProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Pipeline")

def run_measurement(sample_id: str, group_name: str, k_factor: float = config.DEFAULT_K_COEFFICIENT):
    """
    Executes an automated three-frame active acquisition cycle:
    1. Soil moisture reading via ADS1115 (Channels A0, A1).
    2. Background ambient illumination frame (Relays OFF).
    3. NIR 850 nm strobe frame (Relay 1 ON).
    4. Deep Red 660 nm strobe frame (Relay 2 ON).
    5. Ambient subtraction, NDVI calculation, and COLORMAP_JET heatmap rendering.
    6. Archiving outputs to data/processed and CSV ledger.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info("Starting acquisition cycle for Sample: %s | Group: %s", sample_id, group_name)

    # 1. Initialize hardware subsystems
    soil_reader = SoilMoistureReader()
    relays = RelayController()
    camera = CameraV4L2()
    processor = NDVIProcessor(k_factor=k_factor)

    try:
        # 2. Read soil moisture ground-truth
        soil_data = soil_reader.read_channels()
        logger.info("Soil Moisture -> A0: %.1f%% (%.3f V), A1: %.1f%% (%.3f V)",
                    soil_data["channel_0"]["moisture_percent"], soil_data["channel_0"]["voltage_V"],
                    soil_data["channel_1"]["moisture_percent"], soil_data["channel_1"]["voltage_V"])

        # 3. Capture Ambient Frame (all LEDs OFF)
        relays.all_off()
        time.sleep(0.1)
        ambient_frame = camera.capture_frame()

        # 4. Capture 850 nm NIR Frame
        relays.set_850nm(True)
        nir_frame = camera.capture_frame()
        relays.set_850nm(False)

        # 5. Capture 660 nm Deep Red Frame
        relays.set_660nm(True)
        red_frame = camera.capture_frame()
        relays.set_660nm(False)

        # 6. Compute NDVI & Metrics
        ndvi_map, mask, metrics = processor.compute_ndvi_map(ambient_frame, nir_frame, red_frame)
        heatmap = processor.render_colormap_jet(ndvi_map, mask)

        # 7. Save Artifacts
        prefix = f"{timestamp}_{group_name}_{sample_id}"
        
        # Save raw images
        cv2.imwrite(str(config.RAW_DATA_DIR / f"{prefix}_ambient.png"), ambient_frame)
        cv2.imwrite(str(config.RAW_DATA_DIR / f"{prefix}_nir850.png"), nir_frame)
        cv2.imwrite(str(config.RAW_DATA_DIR / f"{prefix}_red660.png"), red_frame)

        # Save processed NDVI Heatmap
        heatmap_path = config.PROCESSED_DATA_DIR / f"{prefix}_ndvi_heatmap.png"
        cv2.imwrite(str(heatmap_path), heatmap)

        # Combine measurement summary record
        record = {
            "timestamp": timestamp,
            "sample_id": sample_id,
            "group": group_name,
            "soil_moisture_a0_pct": soil_data["channel_0"]["moisture_percent"],
            "soil_voltage_a0_v": soil_data["channel_0"]["voltage_V"],
            "soil_moisture_a1_pct": soil_data["channel_1"]["moisture_percent"],
            "soil_voltage_a1_v": soil_data["channel_1"]["voltage_V"],
            **metrics,
            "heatmap_file": heatmap_path.name
        }

        # Append to master ledger CSV
        ledger_path = config.DATA_DIR / "measurements_ledger.csv"
        df_new = pd.DataFrame([record])
        if ledger_path.exists():
            df_new.to_csv(ledger_path, mode="a", header=False, index=False)
        else:
            df_new.to_csv(ledger_path, index=False)

        logger.info("Measurement successfully saved. Mean NDVI: %.4f, Stressed area: %.1f%%",
                    metrics["ndvi_mean"], metrics["latent_stress_percent"])
        return record

    finally:
        relays.cleanup()
        camera.release()

def main():
    parser = argparse.ArgumentParser(description="Plant Stress Spectrophotometry Acquisition")
    parser.add_argument("--sample", type=str, default="sample_01", help="Identifier of the plant specimen")
    parser.add_argument("--group", type=str, choices=["Control", "Drought", "Salinity"], default="Control", help="Experimental cohort")
    parser.add_argument("--k", type=float, default=config.DEFAULT_K_COEFFICIENT, help="Calibrated k factor")
    args = parser.parse_args()

    run_measurement(args.sample, args.group, args.k)

if __name__ == "__main__":
    main()
