# -*- coding: utf-8 -*-
"""
Утилита выгрузки непрерывного суточного климатического архива 24/7
с круглого датчика Xiaomi (Zigbee SID: 158d0001576282) из облака Xiaomi Cloud (Mi Home).

Версия 2.4: 
- Прямой прозрачный вывод реальных ошибок Xiaomi (без перехвата в False).
- Полная поддержка 2FA-подтверждения.
- Охват 32 суток (Волна 1 Горох + Волна 2 Огурец).
"""

import sys
import os
import json
import time
import hashlib
import getpass
import argparse
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from micloud import MiCloud
except ImportError:
    print("[ОШИБКА] Библиотека micloud не установлена. Запустите: python -m pip install micloud")
    sys.exit(1)


TARGET_SID = "158d0001576282"
TARGET_MODELS = ["lumi.sensor_ht", "lumi.sensor_ht.v1", "sensor_ht"]


class DirectMiCloud(MiCloud):
    """Прозрачный клиент MiCloud без подавления ошибок."""

    def login(self):
        self._init_session()
        sign = self._login_step1()
        if not sign:
            raise Exception("Не получен _sign от account.xiaomi.com.")

        if not sign.startswith('http'):
            location = self._login_step2(sign)
        else:
            location = sign

        resp3 = self._login_step3(location)
        if resp3.status_code == 200:
            return True
        else:
            raise Exception(f"Ошибка шага 3 (STS): код {resp3.status_code}, ответ: {resp3.text[:200]}")

    def _login_step2(self, sign):
        url = "https://account.xiaomi.com/pass/serviceLoginAuth2"
        post_data = {
            'sid': "xiaomiio",
            'hash': hashlib.md5(self.password.encode()).hexdigest().upper(),
            'callback': "https://sts.api.io.mi.com/sts",
            'qs': '%3Fsid%3Dxiaomiio%26_json%3Dtrue',
            'user': self.username,
            '_json': 'true'
        }
        if sign:
            post_data['_sign'] = sign

        response = self.session.post(url, data=post_data)
        try:
            response_json = json.loads(response.text.replace("&&&START&&&", ""))
        except Exception:
            raise Exception("Некорректный ответ от account.xiaomi.com: " + response.text[:200])

        if response_json.get('result') != 'ok':
            code = response_json.get('code')
            desc = response_json.get('desc') or response_json.get('description', '')
            notif_url = response_json.get('notificationUrl')

            if notif_url:
                print("\n" + "!" * 70)
                print("[ТРЕБУЕТСЯ ДВУХФАКТОРНОЕ ПОДТВЕРЖДЕНИЕ XIAOMI]")
                print("Откройте эту ссылку в браузере и подтвердите вход:")
                print(f"  {notif_url}")
                print("!" * 70)
                input("\nПосле подтверждения в браузере нажмите [Enter] здесь в консоли...")
                # Повторный запрос
                retry_resp = self.session.post(url, data=post_data)
                response_json = json.loads(retry_resp.text.replace("&&&START&&&", ""))

            if response_json.get('result') != 'ok':
                err_msg = f"Код ошибки Xiaomi: {code} ({desc})"
                if code == 70016:
                    err_msg += "\n\n[!] ПРИЧИНА: Неверный пароль от аккаунта Xiaomi (код 70016)."
                    err_msg += "\n    Попробуйте ввести пароль еще раз, проверьте раскладку (ENG/RUS) и Caps Lock."
                elif code == 10017:
                    err_msg += "\n\n[!] ПРИЧИНА: Пользователь с таким ID/логином не найден (код 10017)."
                elif code == 87001:
                    err_msg += "\n\n[!] ПРИЧИНА: Слишком много неверных попыток (включилась временная защита Xiaomi)."
                raise Exception(err_msg)

        self.user_id = response_json['userId']
        self.ssecurity = response_json['ssecurity']
        self.cuser_id = response_json['cUserId']
        self.pass_token = response_json['passToken']

        location = response_json.get('location')
        if location:
            return location
        else:
            raise Exception("Ошибка получения URL сессии: " + str(response_json.get('code')))


def calculate_vpd(t_c: float, rh_pct: float) -> float:
    if t_c is None or rh_pct is None:
        return 0.0
    es = 0.61078 * (10 ** ((7.5 * t_c) / (237.3 + t_c)))
    ea = es * (rh_pct / 100.0)
    return round(max(0.0, es - ea), 2)


def main():
    parser = argparse.ArgumentParser(description="Выгрузка 24/7 логов климата Xiaomi из Mi Cloud")
    parser.add_argument("--days", type=int, default=32, help="Количество дней вглубь истории")
    parser.add_argument("--server", type=str, default="ru", choices=["ru", "cn", "de", "us", "sg", "i2"])
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    out_csv = args.output or os.path.join(data_dir, "windowsill_climate_history_month_24_7.csv")

    print("=" * 70)
    print("ВЫГРУЗКА ПОЛНОГО МЕСЯЧНОГО 24/7 АРХИВА КЛИМАТА ИЗ MI CLOUD")
    print(f"Охват: {args.days} суток (Волна 1 Горох + Волна 2 Огурец)")
    print(f"Целевой датчик подоконника: SID {TARGET_SID}")
    print("=" * 70)

    user = os.environ.get("XIAOMI_USER")
    password = os.environ.get("XIAOMI_PASS")

    default_uid = "634965042"
    if not user:
        print(f"\nВаш числовой Mi ID: {default_uid}")
        u_input = input(f"Введите логин Mi Home [{default_uid}]: ").strip()
        user = u_input if u_input else default_uid

    if not password:
        password = getpass.getpass("Введите пароль Mi-аккаунта (ввод скрыт): ").strip()

    if not user or not password:
        print("[ОШИБКА] Логин и пароль обязательны.")
        return

    print("\n[1/4] Авторизация на сервере account.xiaomi.com...")
    mc = DirectMiCloud(user, password)
    mc.default_server = args.server

    try:
        mc.login()
        print(f"[УСПЕХ] Успешная авторизация! Ваш подтвержденный Mi ID: {mc.user_id}")
    except Exception as e:
        print(f"\n[ОШИБКА АВТОРИЗАЦИИ]\n{e}")
        return

    print(f"\n[2/4] Опрос списка устройств (сервер: {args.server.upper()})...")
    devices = None
    for srv in [args.server, "cn" if args.server != "cn" else "ru"]:
        try:
            dev_list = mc.get_devices(country=srv)
            if dev_list:
                devices = dev_list
                args.server = srv
                print(f" -> Устройства найдены на сервере '{srv.upper()}' ({len(dev_list)} шт.)")
                break
        except Exception:
            pass

    if not devices:
        print("[ОШИБКА] На серверах RU и CN список устройств пуст. Проверьте правильность региона.")
        return

    target_device = None
    for d in devices:
        did = str(d.get("did", ""))
        model = str(d.get("model", ""))
        name = d.get("name", "")
        if TARGET_SID in did or any(m in model for m in TARGET_MODELS):
            target_device = d
            print(f" -> Найден датчик: {name} (DID: {did}, Модель: {model})")
            break

    if not target_device:
        candidates = [d for d in devices if any(k in d.get("model", "") for k in ["sensor", "weather", "temp"])]
        if candidates:
            target_device = candidates[0]
            print(f" -> Выбран датчик: {target_device.get('name')} ({target_device.get('did')})")
        else:
            print("[ОШИБКА] Датчик температуры не найден в аккаунте.")
            return

    target_did = target_device.get("did")
    now_ts = int(time.time())
    start_ts = now_ts - (args.days * 86400)

    print(f"\n[3/4] Запрос истории за месяц с {datetime.fromtimestamp(start_ts).strftime('%d.%m.%Y')} по {datetime.fromtimestamp(now_ts).strftime('%d.%m.%Y')}...")

    records = {}

    def fetch_key_with_pagination(k_name, out_field):
        url = mc._get_api_url(args.server) + "/user/get_user_device_data"
        cur_end = now_ts
        total_fetched = 0
        
        while cur_end > start_ts:
            params = {
                "data": json.dumps({
                    "did": target_did,
                    "key": k_name,
                    "type": "store",
                    "time_start": start_ts,
                    "time_end": cur_end,
                    "limit": 1000
                })
            }
            try:
                res_str = mc.request(url, params)
                res = json.loads(res_str)
                items = res.get("result", [])
                if not items:
                    break
                
                oldest_in_batch = cur_end
                for it in items:
                    ts = int(it.get("time", 0))
                    if ts < oldest_in_batch:
                        oldest_in_batch = ts
                    val_raw = it.get("value")
                    try:
                        val = float(json.loads(val_raw)[0] if isinstance(val_raw, str) and val_raw.startswith("[") else val_raw)
                    except Exception:
                        continue
                    if val > 1000:
                        val = val / 100.0
                    if ts not in records:
                        records[ts] = {"ts": ts, "temp": None, "rh": None}
                    records[ts][out_field] = round(val, 1)
                    total_fetched += 1
                
                if len(items) < 1000 or oldest_in_batch <= start_ts or oldest_in_batch >= cur_end:
                    break
                cur_end = oldest_in_batch - 1
            except Exception as ex:
                print(f" -> Ошибка при запросе ключа '{k_name}': {ex}")
                break
        print(f" -> Ключ '{k_name}': получено {total_fetched} точек")

    fetch_key_with_pagination("temperature", "temp")
    fetch_key_with_pagination("humidity", "rh")
    if not records:
        fetch_key_with_pagination("prop.temperature", "temp")
        fetch_key_with_pagination("prop.humidity", "rh")

    if not records:
        print("[ОШИБКА] Данные за месяц не вернулись.")
        return

    print(f"\n[4/4] Формирование месячного CSV: {out_csv}")
    sorted_ts = sorted(records.keys())
    alt_out_csv = os.path.join(data_dir, "windowsill_climate_history_24_7.csv")

    def write_csv_file(target_file):
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("Timestamp,DateTime,Phase,T_Windowsill_C,RH_Windowsill_Pct,VPD_kPa\n")
            last_t, last_rh = None, None
            written = 0
            for ts in sorted_ts:
                dt = datetime.fromtimestamp(ts)
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                if dt < datetime(2026, 10, 19):
                    phase = "Wave1_Pea"
                elif dt < datetime(2026, 10, 25):
                    phase = "Intermission"
                else:
                    phase = "Wave2_Cucumber"

                t_val = records[ts]["temp"] if records[ts]["temp"] is not None else last_t
                rh_val = records[ts]["rh"] if records[ts]["rh"] is not None else last_rh
                if t_val is not None:
                    last_t = t_val
                if rh_val is not None:
                    last_rh = rh_val
                if t_val is not None and rh_val is not None:
                    vpd = calculate_vpd(t_val, rh_val)
                    f.write(f"{ts},{dt_str},{phase},{t_val},{rh_val},{vpd}\n")
                    written += 1
            return written

    w1 = write_csv_file(out_csv)
    write_csv_file(alt_out_csv)

    print(f"\n[ГОТОВО!] Успешно сохранено {w1} непрерывных климатических точек 24/7!")
    print(f"• Охват: Волна 1 (Горох) + Межсезонье + Волна 2 (Огурец)")
    print(f"• Файл за весь месяц: {out_csv}")
    print(f"• Файл климата станции: {alt_out_csv}")
    print("=" * 70)


if __name__ == "__main__":
    main()
