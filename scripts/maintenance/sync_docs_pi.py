import paramiko
import os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)
sftp = ssh.open_sftp()

files_to_sync = [
    'README.md',
    'docs/STEP_BY_STEP_ALGORITHM.md',
    'docs/SCIENTIFIC_PASSPORT.md',
    'docs/ОТВЕТЫ_НА_КАВЕРЗНЫЕ_ВОПРОСЫ_ЖЮРИ.md',
    'docs/РЕЧЬ_НА_ЗАЩИТУ_7_МИНУТ.md',
    'web_station.py',
    'docs/Научно_исследовательская_работа_Ковалева_Алиса.html',
    'docs/Краткая_записка_для_рецензирования_Ковалева_Алиса.html',
    'docs/Паспорт_исследовательского_проекта_Ковалева_Алиса.md',
    'docs/Тезисы_научного_доклада_Ковалева_Алиса.md',
    'docs/Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.html',
    'docs/ЛАБОРАТОРНЫЙ_ЖУРНАЛ_ИССЛЕДОВАНИЯ.md',
    'docs/aruco_markers_sheet.html',
    'docs/aruco_markers_sheet.pdf',
    'docs/Рабочий_дневник_исследователя_Ковалева_Алиса_3стр.html',
    'docs/Рабочий_дневник_исследователя_Ковалева_Алиса_3стр.pdf',
    'static/aruco_markers_sheet.html',
    'static/aruco_markers_sheet.pdf',
    'static/aruco/aruco_1.png',
    'static/aruco/aruco_2.png',
    'static/aruco/aruco_3.png',
    'static/aruco/aruco_4.png',
    'static/aruco/aruco_5.png',
    'scripts/generators/generate_aruco_sheet.py',
    'scripts/generators/generate_defense_speech_and_qa.py',
    'scripts/generators/generate_alisa_journal_3pages.py',
    'scripts/generators/build_all_docx.py',
    'scripts/generators/build_sirius_presentation.py',
    'docs/Презентация_Большие_Вызовы_2026_Ковалева_Алиса.html',
    'docs/Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf',
    'docs/Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx',
    'static/Презентация_Большие_Вызовы_2026_Ковалева_Алиса.html',
    'static/Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf',
    'static/Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx',
    'docs/Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf',
    'static/Конкурсная_работа_Большие_Вызовы_Ковалева_Алиса.pdf'
]

def ensure_remote_dir(remote_dir):
    parts = remote_dir.strip('/').split('/')
    cur = ''
    for p in parts:
        cur += '/' + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass

for rel_path in files_to_sync:
    local_path = rel_path.replace('/', os.sep)
    if not os.path.exists(local_path):
        print(f"Skipping missing local file: {local_path}")
        continue
    remote_path = '/home/pi/plant-stress-ndvi/' + rel_path.replace('\\', '/')
    ensure_remote_dir(os.path.dirname(remote_path))
    print(f'Uploading {local_path} -> {remote_path}...')
    sftp.put(local_path, remote_path)

sftp.close()
print('SFTP transfer finished.')

cmd = 'cd /home/pi/plant-stress-ndvi && git add -A && git commit -m "docs(sirius): bring all documentation, competition paper, and web station to 100% compliance with Sirius 2026 regulations" && git push origin main && echo "1" | sudo -S systemctl restart plant-station.service'
stdin, stdout, stderr = ssh.exec_command(cmd)
print('GIT OUT:\n', stdout.read().decode('utf-8', errors='ignore'))
print('GIT ERR:\n', stderr.read().decode('utf-8', errors='ignore'))

ssh.close()
