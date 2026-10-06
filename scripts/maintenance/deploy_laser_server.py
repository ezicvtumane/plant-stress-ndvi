import os
import paramiko

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting to Orange Pi (192.168.0.23)...")
    ssh.connect('192.168.0.23', username='pi', password='1', timeout=5)
    
    # SFTP upload
    sftp = ssh.open_sftp()
    local_server = os.path.join(os.path.dirname(__file__), "laser_server.py")
    remote_server = "/home/pi/laser_server.py"
    print(f"Uploading {local_server} -> {remote_server}...")
    sftp.put(local_server, remote_server)
    sftp.close()
    
    # Make executable
    ssh.exec_command("chmod +x /home/pi/laser_server.py")
    
    # Create systemd service
    service_content = """[Unit]
Description=ACMER S1 Pro Laser Print Server & LightBurn Bridge
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u /home/pi/laser_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    
    print("Installing systemd unit /etc/systemd/system/laser-server.service...")
    # Write temp file and sudo mv
    sftp = ssh.open_sftp()
    with sftp.file("/home/pi/laser-server.service", "w") as f:
        f.write(service_content)
    sftp.close()
    
    commands = [
        "echo 1 | sudo -S mv /home/pi/laser-server.service /etc/systemd/system/laser-server.service",
        "echo 1 | sudo -S systemctl daemon-reload",
        "echo 1 | sudo -S systemctl enable laser-server.service",
        "echo 1 | sudo -S systemctl restart laser-server.service",
        "sleep 1",
        "systemctl status laser-server.service --no-pager"
    ]
    
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(out.encode('ascii', errors='replace').decode())
        if err and "password" not in err.lower():
            print("ERR:", err.encode('ascii', errors='replace').decode())
            
    ssh.close()
    print("Deployment completed!")

if __name__ == '__main__':
    deploy()
