import time
import sys
import smbus2

channels = {
    'A0': 0xC3,  # Single-ended AIN0
    'A1': 0xD3,  # Single-ended AIN1
    'A2': 0xE3,  # Single-ended AIN2
    'A3': 0xF3,  # Single-ended AIN3
}

def read_adc():
    bus = smbus2.SMBus(0)
    results = {}
    for ch, cfg in channels.items():
        try:
            bus.write_i2c_block_data(0x48, 0x01, [cfg, 0x83])
            time.sleep(0.04)
            d = bus.read_i2c_block_data(0x48, 0x00, 2)
            raw = (d[0] << 8) | d[1]
            if raw > 0x7FFF:
                raw -= 0x10000
            v = raw * 4.096 / 32768.0
            results[ch] = (v, raw)
        except Exception as e:
            results[ch] = (None, str(e))
    bus.close()
    return results

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"Reading ADS1115 (0x48) on I2C-0 ({count} samples)...")
    for i in range(count):
        res = read_adc()
        out = []
        for ch in ['A0', 'A1', 'A2', 'A3']:
            v, raw = res[ch]
            if v is not None:
                out.append(f"{ch}: {v:.3f}V (raw {raw})")
            else:
                out.append(f"{ch}: ERR")
        print(f"[{i+1}/{count}] " + " | ".join(out))
        if i < count - 1:
            time.sleep(0.5)
