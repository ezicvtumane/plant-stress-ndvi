import time
import smbus2

bus = smbus2.SMBus(0)
channels = {
    'A0': 0xC3, # 1100 0011: single-ended AIN0, +/-4.096V
    'A1': 0xD3, # 1101 0011: single-ended AIN1, +/-4.096V
    'A2': 0xE3, # 1110 0011: single-ended AIN2, +/-4.096V
    'A3': 0xF3  # 1111 0011: single-ended AIN3, +/-4.096V
}

print("=== ADS1115 All 4 Channels Voltage Reading ===")
for ch, cfg in channels.items():
    try:
        bus.write_i2c_block_data(0x48, 0x01, [cfg, 0x83])
        time.sleep(0.05)
        d = bus.read_i2c_block_data(0x48, 0x00, 2)
        val = (d[0] << 8) | d[1]
        if val > 0x7FFF:
            val -= 0x10000
        volts = val * (4.096 / 32768.0)
        print(f"Channel {ch}: {volts:.3f} V (raw: {val})")
    except Exception as e:
        print(f"Channel {ch} ERROR: {e}")
bus.close()
