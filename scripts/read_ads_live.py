import smbus2
import time

channels = {"A0": 0xC3, "A1": 0xD3, "A2": 0xE3, "A3": 0xF3}

with smbus2.SMBus(0) as bus:
    for name, cfg in channels.items():
        readings = []
        for _ in range(5):
            bus.write_i2c_block_data(0x48, 0x01, [cfg, 0x83])
            time.sleep(0.04)
            d = bus.read_i2c_block_data(0x48, 0x00, 2)
            raw = (d[0] << 8) | d[1]
            if raw > 0x7FFF:
                raw -= 0x10000
            v = raw * (4.096 / 32768.0)
            readings.append(v)
            time.sleep(0.01)
        avg_v = sum(readings) / len(readings)
        print(f"Channel {name}: {avg_v:.3f} V  (samples: {[round(x, 3) for x in readings]})")

try:
    with smbus2.SMBus(0) as bus:
        bus.write_i2c_block_data(0x44, 0x2C, [0x06])
        time.sleep(0.05)
        d = bus.read_i2c_block_data(0x44, 0x00, 6)
        t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
        rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
        print(f"SHT30 live microclimate: T={t_c:.2f} °C, RH={rh:.2f} %")
except Exception as e:
    print(f"SHT30 read error: {e}")

import sys
sys.path.append('/home/pi/plant-stress-ndvi')
from src.sensors_ads1115 import SoilMoistureReader
reader = SoilMoistureReader()
print("SoilMoistureReader() calculated moisture:", reader.read_channels()['A0'])


