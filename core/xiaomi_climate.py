import socket
import json
import time

GATEWAY_IP = "192.168.0.9"
GATEWAY_PORT = 9898
SENSOR_SID = "158d0001576282"

# Cache last valid reading
_cached_climate = {
    "t_c": 24.5,
    "rh_pct": 50.0,
    "battery_v": 3.15,
    "last_updated": 0
}

def get_windowsill_climate(timeout: float = 0.8) -> dict:
    """
    Опрос беспроводного климатического датчика Xiaomi Mijia (SID: 158d0001576282)
    через локальный шлюз Xiaomi Gateway (192.168.0.9:9898 UDP).
    Возвращает dict с температурой и влажностью на подоконнике.
    При задержках возвращает кэшированное значение без блокировки.
    """
    global _cached_climate
    now = time.time()
    # If cached less than 10 seconds ago, return immediately
    if now - _cached_climate["last_updated"] < 10.0:
        return _cached_climate

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        query = json.dumps({"cmd": "read", "sid": SENSOR_SID}).encode()
        s.sendto(query, (GATEWAY_IP, GATEWAY_PORT))
        data, _ = s.recvfrom(2048)
        res = json.loads(data.decode())
        if "data" in res:
            p_data = json.loads(res["data"]) if isinstance(res["data"], str) else res["data"]
            if "temperature" in p_data and "humidity" in p_data:
                t_val = round(float(p_data["temperature"]) / 100.0, 1)
                rh_val = round(float(p_data["humidity"]) / 100.0, 1)
                v_val = round(float(p_data.get("voltage", 3150)) / 1000.0, 2)
                _cached_climate = {
                    "t_c": t_val,
                    "rh_pct": rh_val,
                    "battery_v": v_val,
                    "last_updated": now,
                    "is_live": True
                }
                return _cached_climate
    except Exception as e:
        # Fallback to cached
        pass
    finally:
        s.close()

    _cached_climate["is_live"] = False
    return _cached_climate

if __name__ == "__main__":
    cl = get_windowsill_climate()
    print(f"Windowsill Climate: T = {cl['t_c']} °C, RH = {cl['rh_pct']} %, Battery = {cl['battery_v']} V")
