import os
import json
import csv
import shutil
import time
import zipfile

CSV_HEADER = [
    'ID', 'Timestamp', 'Group', 'Weight_g', 'T_Air_C', 'RH_Air_Pct',
    'Moisture_V', 'Moisture_Pct', 'T_Leaf_C', 'Delta_T_C', 'VPD_kPa',
    'NDVI_Mean', 'NDVI_Std', 'Leaf_Area_cm2', 'Opt_File', 'Thermal_File',
    'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9'
]

class ExperimentManager:
    def __init__(self, base_data_dir: str):
        self.base_data_dir = base_data_dir
        self.exp_base_dir = os.path.join(base_data_dir, 'experiments')
        self.registry_file = os.path.join(self.exp_base_dir, 'experiments.json')
        self.legacy_csv = os.path.join(base_data_dir, 'measurements.csv')
        self._init_storage()

    def _init_storage(self):
        os.makedirs(self.exp_base_dir, exist_ok=True)
        if not os.path.exists(self.registry_file):
            now_str = time.strftime('%Y-%m-%d %H:%M')
            # Initialize exp_1
            exp1_dir = os.path.join(self.exp_base_dir, 'exp_1')
            os.makedirs(os.path.join(exp1_dir, 'images'), exist_ok=True)
            exp1_csv = os.path.join(exp1_dir, 'measurements.csv')

            # If legacy CSV exists and has data, copy it to exp_1
            if os.path.exists(self.legacy_csv) and os.path.getsize(self.legacy_csv) > 50:
                shutil.copy2(self.legacy_csv, exp1_csv)
            else:
                self._write_csv_header(exp1_csv)

            # Initialize exp_2 for the 2nd plant
            exp2_dir = os.path.join(self.exp_base_dir, 'exp_2')
            os.makedirs(os.path.join(exp2_dir, 'images'), exist_ok=True)
            exp2_csv = os.path.join(exp2_dir, 'measurements.csv')
            self._write_csv_header(exp2_csv)

            registry = {
                'active_id': 'exp_1',
                'experiments': [
                    {
                        'id': 'exp_1',
                        'name': 'Серия #1 (Растение 1)',
                        'plant': 'Растение 1',
                        'created_at': now_str,
                        'description': 'Основная серия замеров первой культуры',
                        'folder': 'exp_1'
                    },
                    {
                        'id': 'exp_2',
                        'name': 'Серия #2 (Растение 2)',
                        'plant': 'Растение 2',
                        'created_at': now_str,
                        'description': 'Серия замеров второй культуры',
                        'folder': 'exp_2'
                    }
                ]
            }
            self._save_registry(registry)

    def _write_csv_header(self, filepath: str):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)

    def _load_registry(self) -> dict:
        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'active_id': 'exp_1', 'experiments': []}

    def _save_registry(self, data: dict):
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_experiments(self) -> list:
        reg = self._load_registry()
        active_id = reg.get('active_id', 'exp_1')
        res = []
        for exp in reg.get('experiments', []):
            exp_copy = dict(exp)
            csv_path = os.path.join(self.exp_base_dir, exp['folder'], 'measurements.csv')
            count = 0
            if os.path.exists(csv_path):
                try:
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        lines = [l for l in f if l.strip()]
                        count = max(0, len(lines) - 1)
                except Exception:
                    count = 0
            exp_copy['count'] = count
            exp_copy['is_active'] = (exp['id'] == active_id)
            exp_copy['abs_path'] = os.path.join(self.exp_base_dir, exp['folder'])
            res.append(exp_copy)
        return res

    def get_active_experiment(self) -> dict:
        reg = self._load_registry()
        active_id = reg.get('active_id', 'exp_1')
        for exp in self.get_experiments():
            if exp['id'] == active_id:
                return exp
        exps = self.get_experiments()
        return exps[0] if exps else {}

    def set_active_experiment(self, exp_id: str) -> bool:
        reg = self._load_registry()
        found = any(e['id'] == exp_id for e in reg.get('experiments', []))
        if found:
            reg['active_id'] = exp_id
            self._save_registry(reg)
            return True
        return False

    def create_experiment(self, name: str, plant: str = '', description: str = '') -> dict:
        reg = self._load_registry()
        exp_id = f"exp_{int(time.time())}"
        folder_name = exp_id
        exp_dir = os.path.join(self.exp_base_dir, folder_name)
        os.makedirs(os.path.join(exp_dir, 'images'), exist_ok=True)
        csv_path = os.path.join(exp_dir, 'measurements.csv')
        self._write_csv_header(csv_path)

        now_str = time.strftime('%Y-%m-%d %H:%M')
        new_exp = {
            'id': exp_id,
            'name': name.strip() or f'Серия {len(reg.get("experiments", [])) + 1}',
            'plant': plant.strip() or 'Культура',
            'created_at': now_str,
            'description': description.strip(),
            'folder': folder_name
        }
        reg.setdefault('experiments', []).append(new_exp)
        reg['active_id'] = exp_id
        self._save_registry(reg)
        return new_exp

    def get_active_csv_path(self) -> str:
        active = self.get_active_experiment()
        folder = active.get('folder', 'exp_1')
        csv_path = os.path.join(self.exp_base_dir, folder, 'measurements.csv')
        if not os.path.exists(csv_path):
            self._write_csv_header(csv_path)
        return csv_path

    def get_active_images_dir(self) -> str:
        active = self.get_active_experiment()
        folder = active.get('folder', 'exp_1')
        img_dir = os.path.join(self.exp_base_dir, folder, 'images')
        os.makedirs(img_dir, exist_ok=True)
        return img_dir

    def save_measurement_row(self, row: list):
        # 1. Save to active experiment's CSV
        active_csv = self.get_active_csv_path()
        with open(active_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

        # 2. Also keep global legacy CSV updated for safety/compatibility
        try:
            with open(self.legacy_csv, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception:
            pass

    def copy_file_to_active(self, src_path: str):
        if not src_path or not os.path.exists(src_path):
            return
        try:
            dst_dir = self.get_active_images_dir()
            fname = os.path.basename(src_path)
            shutil.copy2(src_path, os.path.join(dst_dir, fname))
        except Exception as e:
            print(f"[ExperimentManager] Copy image error: {e}")

    def generate_zip(self, exp_id: str, out_zip_path: str) -> str:
        reg = self._load_registry()
        target_exp = None
        for exp in reg.get('experiments', []):
            if exp['id'] == exp_id:
                target_exp = exp
                break
        if not target_exp:
            target_exp = self.get_active_experiment()

        folder = target_exp.get('folder', 'exp_1')
        exp_dir = os.path.join(self.exp_base_dir, folder)
        csv_file = os.path.join(exp_dir, 'measurements.csv')
        img_dir = os.path.join(exp_dir, 'images')

        with zipfile.ZipFile(out_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(csv_file):
                zf.write(csv_file, arcname=f"{target_exp.get('name', 'experiment')}_data.csv")
            if os.path.exists(img_dir):
                for f in sorted(os.listdir(img_dir)):
                    full_p = os.path.join(img_dir, f)
                    if os.path.isfile(full_p):
                        zf.write(full_p, arcname=f"images/{f}")
        return out_zip_path

# Global singleton helper
_exp_manager = None
def get_experiment_manager(base_data_dir: str = None) -> ExperimentManager:
    global _exp_manager
    if _exp_manager is None:
        if base_data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            base_data_dir = os.path.join(base_dir, 'data')
        _exp_manager = ExperimentManager(base_data_dir)
    return _exp_manager
