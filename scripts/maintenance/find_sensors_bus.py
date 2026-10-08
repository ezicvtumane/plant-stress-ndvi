import smbus2

buses = [0, 5, 7, 8, 9, 13, 15]
for b_num in buses:
    try:
        bus = smbus2.SMBus(b_num)
        found = []
        for addr in [0x44, 0x48, 0x45, 0x49, 0x4A, 0x4B]:
            try:
                # Test write 0 bytes or read byte
                bus.write_quick(addr)
                found.append(hex(addr))
            except Exception:
                pass
        bus.close()
        if found:
            print(f"Bus i2c-{b_num}: FOUND {found}")
        else:
            print(f"Bus i2c-{b_num}: none of 0x44/0x48")
    except Exception as e:
        print(f"Bus i2c-{b_num}: error {e}")
