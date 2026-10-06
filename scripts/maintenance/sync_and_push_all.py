import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)
sftp = ssh.open_sftp()

local_root = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi'

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

files_to_sync = [
    'README.md',
    'web_station.py',
    'hardware/ENCLOSURE_AND_OPTICS.md',
    'docs/SCIENTIFIC_PASSPORT.md',
    'docs/STEP_BY_STEP_ALGORITHM.md',
    'docs/ЛАБОРАТОРНЫЙ_ЖУРНАЛ_ИССЛЕДОВАНИЯ.md',
    'docs/Паспорт_исследовательского_проекта_Ковалева_Алиса.md',
    'docs/Тезисы_научного_доклада_Ковалева_Алиса.md',
    'docs/РЕЧЬ_НА_ЗАЩИТУ_7_МИНУТ.md',
    'docs/ОТВЕТЫ_НА_КАВЕРЗНЫЕ_ВОПРОСЫ_ЖЮРИ.md',
    'scripts/generators/generate_aruco_sheet.py',
    'scripts/generators/generate_defense_speech_and_qa.py',
    'scripts/generators/generate_lab_journal.py',
    'scripts/generators/generate_alisa_journal.py',
    'scripts/generators/generate_alisa_journal_3pages.py',
    'scripts/generators/build_sirius_presentation.py',
    'scripts/generators/generate_presentation_pdf.py',
    'scripts/generators/generate_presentation_pptx.py',
    'scripts/generators/generate_competition_submission.py',
    'scripts/generators/build_all_docx.py',
    'docs/aruco_markers_sheet.html',
    'docs/aruco_markers_sheet.pdf',
    'static/aruco_markers_sheet.html',
    'static/aruco_markers_sheet.pdf',
]

# Add all generated files from docs/
for fname in os.listdir(os.path.join(local_root, 'docs')):
    if fname.endswith(('.docx', '.pdf', '.html', '.pptx', '.md')):
        rel = f'docs/{fname}'
        if rel not in files_to_sync:
            files_to_sync.append(rel)

# Add static presentation/speech files
for fname in ['Сириус_Презентация_2026_Ковалева_Алиса.html', 'Сириус_Презентация_2026_Ковалева_Алиса.pdf', 
              'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.html', 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf',
              'Речь_для_защиты_Большие_Вызовы_Ковалева_Алиса.pdf', 'Ответы_на_вопросы_жюри_Большие_Вызовы_Ковалева_Алиса.pdf']:
    static_path = os.path.join(local_root, 'static', fname)
    if os.path.exists(static_path):
        files_to_sync.append(f'static/{fname}')

print(f"Total files scheduled for SFTP sync: {len(files_to_sync)}")

for rel_path in files_to_sync:
    local_path = os.path.join(local_root, rel_path.replace('/', os.sep))
    if not os.path.exists(local_path):
        print(f"Skipping missing: {rel_path}")
        continue
    remote_path = '/home/pi/plant-stress-ndvi/' + rel_path.replace('\\', '/')
    ensure_remote_dir(os.path.dirname(remote_path))
    print(f"Uploading {rel_path} -> {remote_path} ({os.path.getsize(local_path)} bytes)...")
    sftp.put(local_path, remote_path)

sftp.close()
print("SFTP sync complete! Running git operations on Orange Pi...")

git_cmd = '''
cd /home/pi/plant-stress-ndvi
git status --short
git add -A
git commit -m "docs: standardize academic terminology for rehydration strategies and cohorts for Sirius 2026"
git push origin main
echo "1" | sudo -S systemctl restart plant-station.service
'''

stdin, stdout, stderr = ssh.exec_command(git_cmd)
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("GIT STDOUT:\n", out)
if err:
    print("GIT STDERR:\n", err)

ssh.close()
print("Done!")
