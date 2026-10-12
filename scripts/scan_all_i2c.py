import smbus2
import glob

buses = sorted([int(p.replace('/dev/i2c-', '')) for p in glob.glob('/dev/i2c-*')])
targets = [0x48, 0x49, 0x4A, 0x4B, 0x44, 0x45]

for b in buses:
    found = []
    try:
        bus = smbus2.SMBus(b)
        for addr in targets:
            try:
                bus.read_byte(addr)
                found.append(hex(addr))
            except Exception:
                pass
        bus.close()
    except Exception as e:
        print(f"Bus i2c-{b}: cannot open ({e})")
        continue
    if found:
        print(f"Bus i2c-{b}: FOUND {found}")
    else:
        print(f"Bus i2c-{b}: none of {targets}")
