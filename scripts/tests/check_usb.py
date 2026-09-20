import os
import glob
import time
import subprocess

def get_current_devices():
    devs = {}
    for p in glob.glob('/sys/bus/usb/devices/*'):
        name = os.path.basename(p)
        if ':' in name:
            continue # skip interfaces
        prod_file = os.path.join(p, 'product')
        speed_file = os.path.join(p, 'speed')
        idv_file = os.path.join(p, 'idVendor')
        idp_file = os.path.join(p, 'idProduct')
        
        prod = open(prod_file).read().strip() if os.path.exists(prod_file) else ''
        speed = open(speed_file).read().strip() if os.path.exists(speed_file) else ''
        idv = open(idv_file).read().strip() if os.path.exists(idv_file) else ''
        idp = open(idp_file).read().strip() if os.path.exists(idp_file) else ''
        
        devs[name] = {
            'product': prod,
            'speed': speed,
            'vid_pid': f"{idv}:{idp}" if idv else ""
        }
    return devs

def main():
    print("=== ТЕКУЩИЕ ПОДКЛЮЧЕННЫЕ УСТРОЙСТВА ===")
    initial = get_current_devices()
    for name, info in sorted(initial.items()):
        if info['vid_pid']:
            print(f"  Порт/Шина [{name}]: VID:PID={info['vid_pid']}, Скорость={info['speed']}M, Устройство='{info['product']}'")
    
    print("\n" + "="*50)
    print("НАЧИНАЮ ОЖИДАНИЕ ПОДКЛЮЧЕНИЯ В ПОРТ (20 секунд)...")
    print("Вставьте флешку / мышь / тепловизор в проверяемый разъем прямо сейчас!")
    print("="*50)

    start_time = time.time()
    detected = False
    
    while time.time() - start_time < 20:
        curr = get_current_devices()
        new_devs = set(curr.keys()) - set(initial.keys())
        removed_devs = set(initial.keys()) - set(curr.keys())
        
        if new_devs:
            for nd in new_devs:
                info = curr[nd]
                print(f"\n[+] ОБНАРУЖЕНО НОВОЕ ПОДКЛЮЧЕНИЕ НА ПОРТУ [{nd}]!")
                print(f"    ID: {info['vid_pid']}")
                print(f"    Устройство: {info['product']}")
                print(f"    Скорость шины: {info['speed']} Mbps")
                print("    ВЫВОД: ПОРТ ПОЛНОСТЬЮ ИСПРАВЕН И ОПРЕДЕЛЯЕТ УСТРОЙСТВА!")
            detected = True
            break
            
        if removed_devs:
            for rd in removed_devs:
                print(f"\n[-] Устройство отключено с порта [{rd}]")
            initial = curr
            
        time.sleep(0.3)
        
    if not detected:
        print("\n[!] За 20 секунд новых устройств не появилось на шине.")
        print("Проверяем лог ядра (dmesg) на случай аппаратных ошибок...")
        res = subprocess.run("echo 1 | sudo -S dmesg | tail -n 15", shell=True, capture_output=True, text=True)
        print(res.stdout)

if __name__ == '__main__':
    main()
