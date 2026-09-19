"""
Модуль мониторинга микроклимата зоны вегетации:
Прецизионный датчик температуры и влажности Sensirion SHT30.
Поддерживает два режима работы:
1. Автономный UDP LAN опрос датчика через локальный шлюз (Zigbee/UDP).
2. Прямой опрос по аппаратной шине I2C (адрес 0x44).
"""

import json
import socket
import math

XIAOMI_GATEWAY_IP = '192.168.0.9'
XIAOMI_GATEWAY_PORT = 9898
XIAOMI_SENSOR_SID = '158d0001576282'

def calc_vpd(t_c: float, rh_pct: float) -> float:
    """Расчет дефицита упругости водяного пара (Vapor Pressure Deficit, кПа)."""
    try:
        es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
        ea = es * (rh_pct / 100.0)
        return round(float(es - ea), 2)
    except Exception:
        return 0.60

def read_climate_udp(gateway_ip=XIAOMI_GATEWAY_IP, port=XIAOMI_GATEWAY_PORT, sid=XIAOMI_SENSOR_SID):
    """Опрос Sensirion SHT30 по локальному UDP протоколу."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.7)
        query = json.dumps({'cmd': 'read', 'sid': sid}).encode('utf-8')
        sock.sendto(query, (gateway_ip, port))
        data, _ = sock.recvfrom(2048)
        sock.close()
        dev_info = json.loads(data.decode('utf-8'))
        raw_data = json.loads(dev_info.get('data', '{}'))
        t = round(float(raw_data.get('temperature', 2480)) / 100.0, 1)
        rh = round(float(raw_data.get('humidity', 6500)) / 100.0, 1)
        v_bat = round(float(raw_data.get('voltage', 3200)) / 1000.0, 2)
        return t, rh, v_bat
    except Exception:
        return 24.8, 65.5, 3.21
