#!/usr/bin/env python3
"""
ACMER S1 Pro Laser Print Server for Orange Pi
Provides:
1. Raw TCP Bridge on port 8088 (for LightBurn Ethernet/TCP connection)
2. Mobile-friendly Web UI on port 8000 (File streaming, Jog, Status, Console)
"""

import os
import sys
import time
import json
import socket
import select
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import serial

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
TCP_PORT = 8088
HTTP_PORT = 8080
UPLOAD_DIR = "/home/pi/laser_jobs"

os.makedirs(UPLOAD_DIR, exist_ok=True)

class LaserManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.ser = None
        self.active_mode = "idle"  # "idle", "lightburn", "streaming"
        
        # State tracking
        self.grbl_status = "Disconnected"
        self.mpos = [0.0, 0.0, 0.0]
        self.wpos = [0.0, 0.0, 0.0]
        self.last_status_raw = ""
        self.last_status_time = 0
        
        # Streaming state
        self.streaming = False
        self.paused = False
        self.stream_filename = ""
        self.stream_total_lines = 0
        self.stream_current_line = 0
        self.stream_start_time = 0
        self.stream_elapsed_time = 0
        self.stream_thread = None
        self.abort_requested = False
        
        # LightBurn client
        self.tcp_client = None
        self.tcp_lock = threading.Lock()
        
        # Console history buffer
        self.console_logs = []
        self.max_logs = 100

        self.connect_serial()
        
        # Background status poller
        self.poller_thread = threading.Thread(target=self._status_poller_loop, daemon=True)
        self.poller_thread.start()

    def log(self, msg, direction="sys"):
        print(f"[{direction}] {msg}", flush=True)
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "dir": direction,
            "text": msg
        }
        with self.lock:
            self.console_logs.append(entry)
            if len(self.console_logs) > self.max_logs:
                self.console_logs.pop(0)

    def connect_serial(self):
        with self.lock:
            if self.ser and self.ser.is_open:
                return True
            try:
                self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
                time.sleep(1.0)
                # Flush startup banner
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.grbl_status = "Connected"
                self.log(f"Connected to {SERIAL_PORT} @ {BAUD_RATE}")
                return True
            except Exception as e:
                self.grbl_status = f"Serial error: {e}"
                self.ser = None
                return False

    def write_raw(self, data: bytes):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(data)
                    return True
                except Exception as e:
                    self.log(f"Write error: {e}")
                    self.ser = None
                    return False
            return False

    def read_raw(self, max_bytes=1024):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    if self.ser.in_waiting > 0:
                        return self.ser.read(min(self.ser.in_waiting, max_bytes))
                except Exception:
                    self.ser = None
            return b""

    def send_command(self, cmd: str):
        cmd = cmd.strip()
        if not cmd:
            return ""
        self.log(cmd, direction="out")
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return "Error: Serial port not open"
            try:
                self.ser.write((cmd + "\n").encode())
                # Read response until ok or error or timeout
                start = time.time()
                resp_lines = []
                while time.time() - start < 1.0:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if line:
                        resp_lines.append(line)
                        self.log(line, direction="in")
                        if line in ("ok", "error") or line.startswith("error:"):
                            break
                    else:
                        time.sleep(0.01)
                return "\n".join(resp_lines)
            except Exception as e:
                return f"Error: {e}"

    def _status_poller_loop(self):
        while True:
            try:
                if not self.ser or not self.ser.is_open:
                    self.connect_serial()
                    time.sleep(2.0)
                    continue

                # Only poll '?' if LightBurn is NOT holding the raw serial and streaming is idle or running
                if self.active_mode != "lightburn":
                    with self.lock:
                        if self.ser and self.ser.is_open:
                            try:
                                self.ser.write(b"?")
                                time.sleep(0.05)
                                while self.ser.in_waiting > 0:
                                    line = self.ser.readline().decode(errors="ignore").strip()
                                    if line.startswith("<") and line.endswith(">"):
                                        self._parse_status(line)
                                    elif line:
                                        self.log(line, direction="in")
                            except Exception:
                                pass
            except Exception:
                pass
            time.sleep(0.5)

    def _parse_status(self, raw_status: str):
        self.last_status_raw = raw_status
        self.last_status_time = time.time()
        # Example: <Idle|MPos:0.000,0.000,0.000|FS:0,0|Pn:P>
        parts = raw_status.strip("<>").split("|")
        if parts:
            self.grbl_status = parts[0]
        for part in parts[1:]:
            if part.startswith("MPos:"):
                coords = [float(x) for x in part[5:].split(",")]
                self.mpos = coords
            elif part.startswith("WPos:"):
                coords = [float(x) for x in part[5:].split(",")]
                self.wpos = coords

    def start_streaming(self, filepath: str):
        if self.streaming:
            return False, "Already streaming a job"
        if self.active_mode == "lightburn":
            return False, "Port is currently in use by LightBurn"
        if not os.path.exists(filepath):
            return False, "File not found"

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip() and not l.strip().startswith(";")]
        
        if not lines:
            return False, "G-code file is empty"

        self.stream_filename = os.path.basename(filepath)
        self.stream_total_lines = len(lines)
        self.stream_current_line = 0
        self.stream_start_time = time.time()
        self.stream_elapsed_time = 0
        self.streaming = True
        self.paused = False
        self.abort_requested = False
        self.active_mode = "streaming"

        self.stream_thread = threading.Thread(target=self._stream_worker, args=(lines,), daemon=True)
        self.stream_thread.start()
        return True, "Streaming started"

    def _stream_worker(self, lines):
        self.log(f"Started job: {self.stream_filename} ({len(lines)} lines)")
        try:
            for idx, line in enumerate(lines):
                while self.paused and not self.abort_requested:
                    time.sleep(0.1)

                if self.abort_requested:
                    self.log("Job aborted by user")
                    break

                self.stream_current_line = idx + 1
                self.stream_elapsed_time = time.time() - self.stream_start_time

                # Send line with handshake
                with self.lock:
                    if not self.ser or not self.ser.is_open:
                        self.log("Serial port lost during stream!")
                        break
                    
                    self.ser.write((line + "\n").encode())

                # Wait for 'ok' or error
                got_ack = False
                timeout_start = time.time()
                while not got_ack and (time.time() - timeout_start < 30.0):
                    if self.abort_requested:
                        break
                    line_resp = ""
                    with self.lock:
                        if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                            line_resp = self.ser.readline().decode(errors="ignore").strip()
                    
                    if line_resp:
                        if line_resp.startswith("<"):
                            self._parse_status(line_resp)
                        elif line_resp == "ok":
                            got_ack = True
                        elif "error" in line_resp.lower():
                            self.log(f"GRBL Error at line {idx+1}: {line_resp}")
                            got_ack = True
                        else:
                            self.log(line_resp, direction="in")
                    else:
                        time.sleep(0.005)

                if not got_ack and not self.abort_requested:
                    self.log(f"Timeout waiting for ok at line {idx+1}")
                    break

            if not self.abort_requested:
                self.log(f"Job completed successfully: {self.stream_filename}")
        except Exception as e:
            self.log(f"Streaming exception: {e}")
        finally:
            self.streaming = False
            self.paused = False
            self.active_mode = "idle"

    def pause_streaming(self):
        if not self.streaming:
            return False, "Not streaming"
        self.paused = True
        self.write_raw(b"!")  # GRBL feed hold
        self.log("Feed hold (!) sent")
        return True, "Paused"

    def resume_streaming(self):
        if not self.streaming or not self.paused:
            return False, "Not paused"
        self.paused = False
        self.write_raw(b"~")  # GRBL resume
        self.log("Cycle resume (~) sent")
        return True, "Resumed"

    def abort_streaming(self):
        if self.streaming:
            self.abort_requested = True
        # Send GRBL soft reset (0x18 / Ctrl+X) and laser off (M5)
        self.write_raw(b"\x18")
        time.sleep(0.1)
        self.write_raw(b"M5\n")
        self.log("Emergency stop / Ctrl+X sent")
        self.streaming = False
        self.paused = False
        self.active_mode = "idle"
        return True, "Aborted & Laser stopped"

laser = LaserManager()

# --- TCP Bridge for LightBurn ---
def run_tcp_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", TCP_PORT))
    server_sock.listen(1)
    laser.log(f"LightBurn TCP server listening on port {TCP_PORT}")

    while True:
        try:
            client_sock, client_addr = server_sock.accept()
            laser.log(f"LightBurn connected from {client_addr}")
            
            # If web streaming is running, reject or alert
            if laser.streaming:
                client_sock.sendall(b"error: Job in progress on web streamer\r\nok\r\n")
                client_sock.close()
                continue

            laser.active_mode = "lightburn"
            client_sock.setblocking(False)

            while True:
                # Check for client disconnect or incoming data
                r_ready, _, _ = select.select([client_sock], [], [], 0.05)
                if client_sock in r_ready:
                    try:
                        data = client_sock.recv(4096)
                        if not data:
                            laser.log("LightBurn disconnected")
                            break
                        laser.write_raw(data)
                    except Exception:
                        break

                # Check for laser serial response to pass back to LightBurn
                laser_data = laser.read_raw(4096)
                if laser_data:
                    try:
                        client_sock.sendall(laser_data)
                    except Exception:
                        break

            client_sock.close()
            laser.active_mode = "idle"
        except Exception as e:
            laser.log(f"TCP server error: {e}")
            time.sleep(1.0)

# --- Web UI & REST API ---
HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ACMER S1 Pro — Laser Server</title>
<style>
  :root {
    --bg: #121820;
    --card: #1c2430;
    --card-border: #2a3748;
    --accent: #ff4757;
    --accent-hover: #ff6b81;
    --blue: #2ed573;
    --text: #e1e8f0;
    --text-muted: #8899a6;
    --btn-jog: #2d3748;
    --btn-jog-hover: #4a5568;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 15px; }
  .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--card-border); padding-bottom: 12px; margin-bottom: 15px; }
  .header h1 { font-size: 1.3rem; color: #fff; display: flex; align-items: center; gap: 8px; }
  .status-badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; text-transform: uppercase; }
  .badge-idle { background: #2ed573; color: #000; }
  .badge-run { background: #ffa502; color: #000; animation: pulse 1s infinite alternate; }
  .badge-alarm { background: #ff4757; color: #fff; }
  .badge-disconnect { background: #747d8c; color: #fff; }
  @keyframes pulse { from { opacity: 0.7; } to { opacity: 1.0; } }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 15px; }
  .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 15px; }
  .card h2 { font-size: 1.05rem; margin-bottom: 12px; color: #70a1ff; border-bottom: 1px solid var(--card-border); padding-bottom: 6px; }

  /* Coordinates */
  .coords { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; text-align: center; margin-bottom: 12px; }
  .coord-box { background: #151b24; padding: 8px; border-radius: 6px; border: 1px solid #2d3748; }
  .coord-label { font-size: 0.75rem; color: var(--text-muted); }
  .coord-val { font-size: 1.25rem; font-weight: bold; color: #fff; font-family: monospace; }

  /* Jog buttons */
  .jog-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; max-width: 240px; margin: 0 auto 12px; }
  .btn { background: var(--btn-jog); color: #fff; border: 1px solid #4a5568; border-radius: 6px; padding: 12px; font-size: 1rem; cursor: pointer; text-align: center; font-weight: bold; }
  .btn:hover { background: var(--btn-jog-hover); }
  .btn-accent { background: #ff4757; border-color: #ff6b81; }
  .btn-accent:hover { background: #ff6b81; }
  .btn-green { background: #2ed573; color: #000; border-color: #7bed9f; }
  .btn-green:hover { background: #7bed9f; }
  .btn-warning { background: #ffa502; color: #000; border-color: #eccc68; }

  .step-selector { display: flex; justify-content: center; gap: 8px; margin-bottom: 12px; }
  .step-selector label { font-size: 0.85rem; background: #151b24; padding: 4px 10px; border-radius: 4px; border: 1px solid #334; cursor: pointer; }
  .step-selector input[type="radio"]:checked + span { color: #70a1ff; font-weight: bold; }

  /* Job Streamer */
  .progress-bar-container { background: #151b24; border-radius: 6px; height: 20px; overflow: hidden; margin: 10px 0; border: 1px solid #334; }
  .progress-bar { background: linear-gradient(90deg, #2ed573, #70a1ff); height: 100%; width: 0%; transition: width 0.3s; }
  .job-controls { display: flex; gap: 8px; margin-top: 10px; }
  .file-item { display: flex; justify-content: space-between; align-items: center; padding: 8px; background: #151b24; border-radius: 6px; margin-bottom: 6px; font-size: 0.85rem; }

  /* Console */
  #console-box { background: #0b0f14; border: 1px solid #222d3d; border-radius: 6px; height: 160px; overflow-y: auto; padding: 8px; font-family: monospace; font-size: 0.75rem; color: #00ff66; margin-bottom: 8px; }
  .console-in { display: flex; gap: 6px; }
  .console-in input { flex: 1; background: #151b24; border: 1px solid #334; color: #fff; padding: 8px; border-radius: 6px; font-family: monospace; }
</style>
</head>
<body>

<div class="header">
  <h1>⚡ ACMER S1 Pro Server</h1>
  <div>
    <span id="status-badge" class="status-badge badge-disconnect">Disconnected</span>
  </div>
</div>

<div class="grid">
  <!-- Status & Jogging -->
  <div class="card">
    <h2>Позиционирование (GRBL Jog)</h2>
    <div class="coords">
      <div class="coord-box"><div class="coord-label">X</div><div id="pos-x" class="coord-val">0.00</div></div>
      <div class="coord-box"><div class="coord-label">Y</div><div id="pos-y" class="coord-val">0.00</div></div>
      <div class="coord-box"><div class="coord-label">Z</div><div id="pos-z" class="coord-val">0.00</div></div>
    </div>

    <div class="step-selector">
      <label><input type="radio" name="step" value="1"> <span>1 мм</span></label>
      <label><input type="radio" name="step" value="10" checked> <span>10 мм</span></label>
      <label><input type="radio" name="step" value="50"> <span>50 мм</span></label>
      <label><input type="radio" name="step" value="100"> <span>100 мм</span></label>
    </div>

    <div class="jog-grid">
      <div></div>
      <button class="btn" onclick="jog(0, 1)">Y+</button>
      <div></div>
      <button class="btn" onclick="jog(-1, 0)">X-</button>
      <button class="btn btn-warning" onclick="sendCmd('$H')" title="Home">⌂</button>
      <button class="btn" onclick="jog(1, 0)">X+</button>
      <div></div>
      <button class="btn" onclick="jog(0, -1)">Y-</button>
      <div></div>
    </div>

    <div style="display:flex; gap:6px; margin-top:8px;">
      <button class="btn" style="flex:1" onclick="sendCmd('G92 X0 Y0')">Обнулить XY</button>
      <button class="btn" style="flex:1" onclick="sendCmd('$X')">Сброс Alarm ($X)</button>
      <button class="btn btn-warning" style="flex:1" onclick="laserTest()">Тест луча 1%</button>
    </div>
  </div>

  <!-- Job Streaming -->
  <div class="card">
    <h2>Автономная резка (G-Code Streamer)</h2>
    <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:8px;">
      LightBurn TCP Порт: <b>192.168.0.23:8088</b> (или загрузите файл сюда):
    </p>

    <input type="file" id="file-input" accept=".gc,.gcode,.nc" style="margin-bottom:8px; font-size:0.85rem;">
    <button class="btn btn-green" style="width:100%; margin-bottom:12px;" onclick="uploadFile()">Загрузить на Orange Pi</button>

    <div style="margin-bottom:10px;">
      <div style="display:flex; justify-content:space-between; font-size:0.85rem;">
        <span id="job-filename">Нет активной задачи</span>
        <span id="job-percent">0%</span>
      </div>
      <div class="progress-bar-container">
        <div id="job-bar" class="progress-bar"></div>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-muted);">
        <span id="job-lines">Строк: 0 / 0</span>
        <span id="job-time">Время: 00:00</span>
      </div>
    </div>

    <div class="job-controls">
      <button id="btn-pause" class="btn btn-warning" style="flex:1" onclick="pauseJob()">Пауза (!)</button>
      <button id="btn-resume" class="btn btn-green" style="flex:1" onclick="resumeJob()">Продолжить (~)</button>
      <button class="btn btn-accent" style="flex:1" onclick="abortJob()">СТОП (E-Stop)</button>
    </div>

    <h3 style="font-size:0.9rem; margin:14px 0 6px; color:#a4b0be;">Файлы на сервере:</h3>
    <div id="file-list" style="max-height:140px; overflow-y:auto;"></div>
  </div>

  <!-- Console -->
  <div class="card" style="grid-column: 1 / -1;">
    <h2>Консоль GRBL</h2>
    <div id="console-box"></div>
    <div class="console-in">
      <input type="text" id="cmd-input" placeholder="Введите команду (например $$ или G0 X10 Y10)..." onkeydown="if(event.key==='Enter') sendConsole()">
      <button class="btn" onclick="sendConsole()">Отправить</button>
    </div>
  </div>
</div>

<script>
  let laserTestActive = false;

  function getStep() {
    const checked = document.querySelector('input[name="step"]:checked');
    return checked ? parseFloat(checked.value) : 10;
  }

  function jog(dx, dy) {
    const s = getStep();
    const x = dx * s;
    const y = dy * s;
    const feed = 2000;
    sendCmd(`$J=G91 G21 X${x} Y${y} F${feed}`);
  }

  function laserTest() {
    if (!laserTestActive) {
      if (confirm('Включить лазер на минимальной мощности (1%) для прицеливания?')) {
        sendCmd('M3 S10');
        laserTestActive = true;
      }
    } else {
      sendCmd('M5');
      laserTestActive = false;
    }
  }

  function sendCmd(cmd) {
    fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cmd: cmd})
    });
  }

  function sendConsole() {
    const el = document.getElementById('cmd-input');
    const val = el.value.trim();
    if (val) {
      sendCmd(val);
      el.value = '';
    }
  }

  function uploadFile() {
    const fileInput = document.getElementById('file-input');
    if (!fileInput.files.length) return alert('Выберите файл G-кода!');
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch('/api/upload', { method: 'POST', body: formData })
      .then(r => r.json())
      .then(data => {
        alert(data.message);
        loadFiles();
      });
  }

  function loadFiles() {
    fetch('/api/files')
      .then(r => r.json())
      .then(files => {
        const list = document.getElementById('file-list');
        list.innerHTML = '';
        files.forEach(f => {
          const div = document.createElement('div');
          div.className = 'file-item';
          div.innerHTML = `
            <span><b>${f.name}</b> (${(f.size/1024).toFixed(1)} KB)</span>
            <div>
              <button class="btn btn-green" style="padding:4px 8px; font-size:0.75rem;" onclick="startJob('${f.name}')">Запуск</button>
              <button class="btn btn-accent" style="padding:4px 8px; font-size:0.75rem;" onclick="deleteFile('${f.name}')">×</button>
            </div>
          `;
          list.appendChild(div);
        });
      });
  }

  function startJob(name) {
    if (confirm(`Запустить резку файла "${name}"? Убедитесь, что вытяжка включена и фокус настроен!`)) {
      fetch('/api/job/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: name})
      }).then(r => r.json()).then(d => alert(d.message));
    }
  }

  function pauseJob() {
    fetch('/api/job/pause', {method: 'POST'});
  }

  function resumeJob() {
    fetch('/api/job/resume', {method: 'POST'});
  }

  function abortJob() {
    if (confirm('АВАРИЙНЫЙ СТОП! Немедленно остановить лазер и моторы?')) {
      fetch('/api/job/abort', {method: 'POST'});
    }
  }

  function deleteFile(name) {
    if (confirm(`Удалить файл ${name}?`)) {
      fetch('/api/files/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: name})
      }).then(() => loadFiles());
    }
  }

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function updateStatus() {
    fetch('/api/status')
      .then(r => r.json())
      .then(data => {
        const badge = document.getElementById('status-badge');
        badge.innerText = data.status;
        badge.className = 'status-badge ' + (
          data.status === 'Idle' ? 'badge-idle' :
          data.status === 'Run' ? 'badge-run' :
          data.status.includes('Alarm') ? 'badge-alarm' : 'badge-disconnect'
        );

        document.getElementById('pos-x').innerText = (data.mpos[0] || 0).toFixed(2);
        document.getElementById('pos-y').innerText = (data.mpos[1] || 0).toFixed(2);
        document.getElementById('pos-z').innerText = (data.mpos[2] || 0).toFixed(2);

        // Job details
        if (data.streaming) {
          document.getElementById('job-filename').innerText = data.job.filename;
          const pct = ((data.job.current / (data.job.total || 1)) * 100).toFixed(1);
          document.getElementById('job-percent').innerText = pct + '%';
          document.getElementById('job-bar').style.width = pct + '%';
          document.getElementById('job-lines').innerText = `Строк: ${data.job.current} / ${data.job.total}`;
          document.getElementById('job-time').innerText = `Время: ${formatTime(data.job.elapsed)}`;
        } else {
          document.getElementById('job-percent').innerText = '0%';
          document.getElementById('job-bar').style.width = '0%';
        }

        // Console
        const box = document.getElementById('console-box');
        box.innerHTML = data.logs.map(l => `<div><span style="color:#666">[${l.time}]</span> <b style="color:${l.dir==='out'?'#70a1ff':'#00ff66'}">${l.dir==='out'?'->':'<-'}</b> ${l.text}</div>`).join('');
        box.scrollTop = box.scrollHeight;
      })
      .catch(() => {});
  }

  loadFiles();
  setInterval(updateStatus, 800);
</script>
</body>
</html>
"""

class LaserHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress spamming stdout with GET requests
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        elif url.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": laser.grbl_status,
                "mpos": laser.mpos,
                "wpos": laser.wpos,
                "streaming": laser.streaming,
                "paused": laser.paused,
                "mode": laser.active_mode,
                "job": {
                    "filename": laser.stream_filename,
                    "total": laser.stream_total_lines,
                    "current": laser.stream_current_line,
                    "elapsed": laser.stream_elapsed_time
                },
                "logs": laser.console_logs[-25:]
            }
            self.wfile.write(json.dumps(resp).encode())
        elif url.path == "/api/files":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            files = []
            for fname in sorted(os.listdir(UPLOAD_DIR)):
                fpath = os.path.join(UPLOAD_DIR, fname)
                if os.path.isfile(fpath):
                    files.append({
                        "name": fname,
                        "size": os.path.getsize(fpath),
                        "mtime": os.path.getmtime(fpath)
                    })
            self.wfile.write(json.dumps(files).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len) if content_len > 0 else b""

        if url.path == "/api/command":
            data = json.loads(post_data.decode()) if post_data else {}
            cmd = data.get("cmd", "")
            res = laser.send_command(cmd)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"result": res}).encode())

        elif url.path == "/api/job/start":
            data = json.loads(post_data.decode()) if post_data else {}
            fname = data.get("filename", "")
            fpath = os.path.join(UPLOAD_DIR, fname)
            ok, msg = laser.start_streaming(fpath)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg}).encode())

        elif url.path == "/api/job/pause":
            ok, msg = laser.pause_streaming()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg}).encode())

        elif url.path == "/api/job/resume":
            ok, msg = laser.resume_streaming()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg}).encode())

        elif url.path == "/api/job/abort":
            ok, msg = laser.abort_streaming()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg}).encode())

        elif url.path == "/api/files/delete":
            data = json.loads(post_data.decode()) if post_data else {}
            fname = data.get("filename", "")
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())

        elif url.path == "/api/upload":
            # Simple multipart/form-data parser for single file
            boundary = self.headers.get("Content-Type", "").split("boundary=")[-1].encode()
            parts = post_data.split(b"--" + boundary)
            saved_name = ""
            for part in parts:
                if b"filename=" in part:
                    header, file_bytes = part.split(b"\r\n\r\n", 1)
                    file_bytes = file_bytes.rstrip(b"\r\n")
                    for h_line in header.decode(errors="ignore").split("\r\n"):
                        if "filename=" in h_line:
                            raw_fname = h_line.split("filename=")[-1].strip('"\'')
                            saved_name = os.path.basename(raw_fname)
                            with open(os.path.join(UPLOAD_DIR, saved_name), "wb") as f:
                                f.write(file_bytes)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": f"Файл {saved_name} успешно сохранён!"}).encode())

        else:
            self.send_response(404)
            self.end_headers()

def run_http_server():
    try:
        server = HTTPServer(("0.0.0.0", HTTP_PORT), LaserHTTPHandler)
        laser.log(f"Web UI server listening on http://0.0.0.0:{HTTP_PORT}")
        server.serve_forever()
    except Exception as e:
        laser.log(f"HTTP server error: {e}")

if __name__ == "__main__":
    laser.log("Starting ACMER S1 Pro Laser Server background threads...")
    t_tcp = threading.Thread(target=run_tcp_server, daemon=True)
    t_tcp.start()

    run_http_server()
