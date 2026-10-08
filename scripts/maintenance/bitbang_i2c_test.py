import time
import gpiod
from gpiod.line import Direction, Value, Drive, Bias

chip_path = '/dev/gpiochip0'
PIN_SCL = 34 # PB2
PIN_SDA = 35 # PB3

class BitBangI2C:
    def __init__(self, req):
        self.req = req
        self.delay = 0.00003 # ~15 kHz for extreme reliability

    def _scl(self, val):
        self.req.set_value(PIN_SCL, Value.ACTIVE if val else Value.INACTIVE)
        time.sleep(self.delay)

    def _sda(self, val):
        self.req.set_value(PIN_SDA, Value.ACTIVE if val else Value.INACTIVE)
        time.sleep(self.delay)

    def _read_sda(self):
        return self.req.get_value(PIN_SDA) == Value.ACTIVE

    def start(self):
        self._sda(1)
        self._scl(1)
        self._sda(0)
        self._scl(0)

    def stop(self):
        self._sda(0)
        self._scl(1)
        self._sda(1)

    def write_byte(self, byte):
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            self._sda(bit)
            self._scl(1)
            self._scl(0)
        
        # ACK bit: release SDA (1) and read slave response
        self._sda(1)
        self._scl(1)
        ack = self._read_sda() # In open-drain: 0 = pulled low by slave (ACK)
        self._scl(0)
        return (not ack) # True if slave sent ACK (pulled LOW)

    def read_byte(self, send_ack):
        self._sda(1) # release line
        data = 0
        for i in range(8):
            self._scl(1)
            bit = 1 if self._read_sda() else 0
            data = (data << 1) | bit
            self._scl(0)
        # Send ACK/NACK
        self._sda(0 if send_ack else 1)
        self._scl(1)
        self._scl(0)
        self._sda(1)
        return data

# Unbind twi driver if bound
import subprocess
subprocess.run("echo 2510000.twi > /sys/bus/platform/drivers/sunxi-twi/unbind", shell=True, check=False)
time.sleep(0.1)

cfg = {
    PIN_SCL: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE, drive=Drive.OPEN_DRAIN, bias=Bias.PULL_UP),
    PIN_SDA: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE, drive=Drive.OPEN_DRAIN, bias=Bias.PULL_UP)
}

print("=== Starting Open-Drain BitBang I2C Scan ===")
found = []
with gpiod.request_lines(chip_path, consumer='bb_i2c', config=cfg) as req:
    i2c = BitBangI2C(req)
    
    # Send 18 clock pulses to reset slaves
    for _ in range(18):
        i2c._scl(0)
        i2c._scl(1)
    i2c.stop()
    
    for addr in range(0x08, 0x78):
        i2c.start()
        ack = i2c.write_byte(addr << 1) # write mode
        i2c.stop()
        if ack:
            print(f"Detected ACK at 0x{addr:02X} ({addr})!")
            found.append(hex(addr))

print("Scan complete. Detected devices:", found)

# Test SHT30 read if found
if '0x44' in found:
    print("\n[TEST] Reading SHT30 microclimate...")
    with gpiod.request_lines(chip_path, consumer='bb_sht30', config=cfg) as req:
        i2c = BitBangI2C(req)
        i2c.start()
        i2c.write_byte(0x44 << 1)
        i2c.write_byte(0x2C)
        i2c.write_byte(0x06)
        i2c.stop()
        time.sleep(0.05)
        i2c.start()
        i2c.write_byte((0x44 << 1) | 1) # Read mode
        d = [i2c.read_byte(True) for _ in range(5)]
        d.append(i2c.read_byte(False)) # Last byte NACK
        i2c.stop()
        t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
        rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
        print(f"SHT30 Success: T={t_c:.2f}°C, RH={rh:.1f}%")

# Test ADS1115 read if found
if '0x48' in found:
    print("\n[TEST] Reading ADS1115 ADC on all 4 channels...")
    with gpiod.request_lines(chip_path, consumer='bb_ads', config=cfg) as req:
        i2c = BitBangI2C(req)
        channels = {'A0': 0xC3, 'A1': 0xD3, 'A2': 0xE3, 'A3': 0xF3}
        for ch, cfg_byte in channels.items():
            i2c.start()
            i2c.write_byte(0x48 << 1)
            i2c.write_byte(0x01) # Config reg
            i2c.write_byte(cfg_byte) # MSB
            i2c.write_byte(0x83) # LSB
            i2c.stop()
            time.sleep(0.05)
            # Read conversion reg 0x00
            i2c.start()
            i2c.write_byte(0x48 << 1)
            i2c.write_byte(0x00)
            i2c.stop()
            i2c.start()
            i2c.write_byte((0x48 << 1) | 1)
            msb = i2c.read_byte(True)
            lsb = i2c.read_byte(False)
            i2c.stop()
            val = (msb << 8) | lsb
            if val > 32767: val -= 65536
            v = val * 4.096 / 32768.0
            print(f"ADS1115 {ch}: Raw={val}, Voltage={v:.3f}V")
