import time
import smbus2

print("Monitoring i2c-0 for 5 seconds...")
bus = smbus2.SMBus(0)
for i in range(10):
    res_44 = "NACK"
    res_48 = "NACK"
    try:
        bus.write_quick(0x44)
        res_44 = "ACK"
    except Exception as e:
        res_44 = f"ERR({e.args[0] if e.args else e})"
    
    try:
        bus.write_quick(0x48)
        res_48 = "ACK"
    except Exception as e:
        res_48 = f"ERR({e.args[0] if e.args else e})"
        
    print(f"[{i*0.5:.1f}s] SHT30(0x44): {res_44} | ADS1115(0x48): {res_48}")
    time.sleep(0.5)
bus.close()
